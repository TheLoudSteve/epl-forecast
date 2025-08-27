import json
import os
import boto3
import requests
from datetime import datetime, timezone
from typing import Dict, List, Any
from decimal import Decimal

# New Relic monitoring
try:
    import newrelic.agent
    # Initialize if environment variables are set
    if os.environ.get('NEW_RELIC_LICENSE_KEY'):
        newrelic.agent.initialize()
        NEW_RELIC_ENABLED = True
    else:
        NEW_RELIC_ENABLED = False
except ImportError:
    NEW_RELIC_ENABLED = False

# Use the region from environment or default to us-east-1 for backward compatibility
region = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=region)

@newrelic.agent.lambda_handler() if NEW_RELIC_ENABLED else lambda x: x
def lambda_handler(event, context):
    """
    Lambda function to fetch EPL data on schedule (2x daily at 00:00 and 12:00 UTC)
    This ensures fresh data is always available and prevents DynamoDB TTL expiration
    """
    try:
        print(f"Scheduled data fetch triggered with event: {event}")
        
        # Add New Relic custom attributes
        if NEW_RELIC_ENABLED:
            newrelic.agent.add_custom_attribute('lambda.event_type', 'scheduled_fetch')
            newrelic.agent.add_custom_attribute('lambda.environment', os.environ.get('ENVIRONMENT', 'unknown'))
        
        table_name = os.environ['DYNAMODB_TABLE']
        rapidapi_key = os.environ['RAPIDAPI_KEY']
        
        print(f"Environment variables - Table: {table_name}")
        
        table = dynamodb.Table(table_name)
        
        print("Starting scheduled data fetch...")
        
        # Fetch current EPL table
        epl_data = fetch_epl_data(rapidapi_key)
        print(f"Fetched EPL data with {len(epl_data.get('table', []))} teams")
        
        # Calculate forecasts
        forecast_data = calculate_forecasts(epl_data)
        print(f"Calculated forecast data for {len(forecast_data.get('teams', []))} teams")
        
        # Store in DynamoDB
        store_data(table, forecast_data)
        print("Successfully stored data in DynamoDB")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Scheduled data updated successfully',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'teams_processed': len(forecast_data.get('teams', []))
            })
        }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        }

def fetch_epl_data(rapidapi_key: str) -> Dict[str, Any]:
    """
    Fetch current EPL table from RapidAPI
    """
    url = "https://football-web-pages1.p.rapidapi.com/league-table.json"
    querystring = {"comp": "1", "team": "1"}
    
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": "football-web-pages1.p.rapidapi.com"
    }
    
    print(f"Calling RapidAPI: {url}")
    print(f"Headers: X-RapidAPI-Host: {headers['X-RapidAPI-Host']}")
    print(f"Params: {querystring}")
    
    # Record New Relic custom metric for RapidAPI call
    environment = os.environ.get('ENVIRONMENT', 'unknown')
    if NEW_RELIC_ENABLED:
        newrelic.agent.record_custom_metric('Custom/RapidAPI/CallMade', 1)
        newrelic.agent.add_custom_attribute('rapidapi.call_reason', 'scheduled_update')
        newrelic.agent.add_custom_attribute('rapidapi.environment', environment)
        newrelic.agent.add_custom_attribute('rapidapi.url', url)
        newrelic.agent.add_custom_attribute('rapidapi.timestamp', datetime.now(timezone.utc).isoformat())
    
    start_time = datetime.now(timezone.utc)
    response = requests.get(url, headers=headers, params=querystring, timeout=30)
    end_time = datetime.now(timezone.utc)
    response_time_ms = (end_time - start_time).total_seconds() * 1000
    
    print(f"API Response Status: {response.status_code}")
    print(f"API Response Time: {response_time_ms:.2f}ms")
    print(f"API Response Headers: {dict(response.headers)}")
    
    # Record response metrics
    if NEW_RELIC_ENABLED:
        newrelic.agent.record_custom_metric('Custom/RapidAPI/ResponseTime', response_time_ms)
        newrelic.agent.record_custom_metric(f'Custom/RapidAPI/StatusCode/{response.status_code}', 1)
        newrelic.agent.add_custom_attribute('rapidapi.response_status', response.status_code)
        newrelic.agent.add_custom_attribute('rapidapi.response_time_ms', response_time_ms)
    
    response.raise_for_status()
    
    data = response.json()
    print(f"API Response Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
    print(f"API Response sample: {str(data)[:500]}...")
    
    # Record successful API call metrics
    if NEW_RELIC_ENABLED:
        teams_count = len(data.get('league-table', {}).get('teams', []))
        if teams_count == 0 and 'table' in data:
            teams_count = len(data.get('table', []))
        newrelic.agent.record_custom_metric('Custom/RapidAPI/TeamsReturned', teams_count)
        newrelic.agent.add_custom_attribute('rapidapi.teams_count', teams_count)
    
    return data

def calculate_forecasts(epl_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate forecasted final table based on points per game
    """
    teams = []
    
    # Extract team data from API response - correct structure is league-table.teams
    table_data = epl_data.get('league-table', {}).get('teams', [])
    print(f"Table data found: {len(table_data)} teams")
    
    if not table_data:
        print("WARNING: No table data found in API response!")
        print(f"Available keys in epl_data: {list(epl_data.keys())}")
        # Try alternative key structures
        if 'table' in epl_data:
            table_data = epl_data.get('table', [])
            print(f"Found table data instead: {len(table_data)} teams")
        elif 'standings' in epl_data:
            table_data = epl_data.get('standings', [])
            print(f"Found standings data instead: {len(table_data)} teams")
    
    for team_data in table_data:
        # Extract data from the correct API structure
        all_matches = team_data.get('all-matches', {})
        played = all_matches.get('played', 0)
        points = team_data.get('total-points', 0)
        
        if played > 0:
            points_per_game = points / played
            forecasted_points = points_per_game * 38  # Full season is 38 games
        else:
            points_per_game = 0
            forecasted_points = 0
        
        team = {
            'name': team_data.get('name', ''),
            'played': played,
            'won': all_matches.get('won', 0),
            'drawn': all_matches.get('drawn', 0),
            'lost': all_matches.get('lost', 0),
            'for': all_matches.get('for', 0),
            'against': all_matches.get('against', 0),
            'goal_difference': all_matches.get('goal-difference', 0),
            'points': points,
            'points_per_game': Decimal(str(round(points_per_game, 2))),
            'forecasted_points': Decimal(str(round(forecasted_points, 1))),
            'current_position': team_data.get('position', 0)
        }
        teams.append(team)
    
    # Sort by forecasted points (descending), then by goal difference, then by goals for
    teams.sort(key=lambda x: (-x['forecasted_points'], -x['goal_difference'], -x['for']))
    
    # Add forecasted position
    for i, team in enumerate(teams):
        team['forecasted_position'] = i + 1
    
    return {
        'teams': teams,
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'total_teams': len(teams),
        'update_type': 'scheduled'
    }

def store_data(table, data: Dict[str, Any]) -> None:
    """
    Store forecast data in DynamoDB
    """
    # Store with TTL of 24 hours
    ttl = int((datetime.now(timezone.utc).timestamp() + 86400))
    
    table.put_item(
        Item={
            'id': 'current_forecast',
            'data': data,
            'ttl': ttl
        }
    )