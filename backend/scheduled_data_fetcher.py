import json
import os
import boto3
import requests
from datetime import datetime, timezone
from typing import Dict, List, Any
from decimal import Decimal
from forecast_history import forecast_history_manager
from notification_logic import notification_manager

# New Relic monitoring
try:
    import newrelic.agent
    print("New Relic agent imported successfully")
    # Initialize if environment variables are set
    if os.environ.get('NEW_RELIC_LICENSE_KEY'):
        print("NEW_RELIC_LICENSE_KEY found, initializing New Relic agent...")
        # For Lambda, we need to initialize without config file and rely on env vars
        newrelic.agent.initialize(config_file=None, environment='production')
        NEW_RELIC_ENABLED = True
        print(f"New Relic agent initialized successfully for app: {os.environ.get('NEW_RELIC_APP_NAME', 'EPL-Forecast-Lambda')}")
        print(f"New Relic Account ID: {os.environ.get('NEW_RELIC_ACCOUNT_ID', 'Not Set')}")
    else:
        print("NEW_RELIC_LICENSE_KEY not found, New Relic disabled")
        NEW_RELIC_ENABLED = False
except ImportError as e:
    print(f"Failed to import New Relic agent: {e}")
    NEW_RELIC_ENABLED = False
except Exception as e:
    print(f"Error initializing New Relic agent: {e}")
    NEW_RELIC_ENABLED = False

# Use the region from environment or default to us-east-1 for backward compatibility
region = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=region)

# @newrelic.agent.lambda_handler if NEW_RELIC_ENABLED else lambda x: x
def lambda_handler(event, context):
    """
    Lambda function to fetch EPL data on schedule (1x daily at 00:00 UTC)
    This ensures fresh data is always available and prevents DynamoDB TTL expiration
    """
    try:
        print(f"Scheduled data fetch triggered with event: {event}")
        
        # Add New Relic custom attributes
        if NEW_RELIC_ENABLED:
            newrelic.agent.add_custom_attribute('lambda.event_type', 'scheduled_fetch')
            newrelic.agent.add_custom_attribute('lambda.environment', os.environ.get('ENVIRONMENT', 'unknown'))
        
        table_name = os.environ['DYNAMODB_TABLE']
        football_data_api_key = os.environ['FOOTBALL_DATA_API_KEY']

        print(f"Environment variables - Table: {table_name}")

        table = dynamodb.Table(table_name)

        print("Starting scheduled data fetch...")

        # Fetch current EPL table
        epl_data = fetch_epl_data(football_data_api_key)
        print(f"Fetched EPL data with {len(epl_data.get('table', []))} teams")
        
        # Calculate forecasts
        forecast_data = calculate_forecasts(epl_data)
        print(f"Calculated forecast data for {len(forecast_data.get('teams', []))} teams")
        
        # Store in DynamoDB
        store_data(table, forecast_data)
        print("Successfully stored data in DynamoDB")
        
        # Save forecast snapshot to history
        try:
            snapshot = forecast_history_manager.save_forecast_snapshot(
                forecast_data, 
                context="Scheduled update"
            )
            print(f"Successfully saved forecast snapshot with timestamp {snapshot.timestamp}")
        except Exception as snapshot_error:
            print(f"Error saving forecast snapshot: {snapshot_error}")
            # Don't fail the entire function if snapshot saving fails
        
        # Process notifications for position changes
        notification_result = {'notifications_sent': 0}
        try:
            notification_result = notification_manager.process_forecast_update(
                forecast_data,
                context="Scheduled update"
            )
            print(f"Notification processing result: {notification_result}")
        except Exception as notification_error:
            print(f"Error processing notifications: {notification_error}")
            # Don't fail the entire function if notification processing fails
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Scheduled data updated successfully',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'teams_processed': len(forecast_data.get('teams', [])),
                'notifications_sent': notification_result.get('notifications_sent', 0)
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

def fetch_epl_data(api_key: str) -> Dict[str, Any]:
    """
    Fetch current EPL standings from football-data.org API
    """
    url = "https://api.football-data.org/v4/competitions/PL/standings"

    headers = {
        "X-Auth-Token": api_key
    }

    print(f"Calling football-data.org API: {url}")

    # Record New Relic custom metric for API call
    environment = os.environ.get('ENVIRONMENT', 'unknown')
    if NEW_RELIC_ENABLED:
        print("Recording New Relic metrics for football-data.org API call...")
        newrelic.agent.record_custom_metric('Custom/FootballDataAPI/CallMade', 1)
        newrelic.agent.add_custom_attribute('football_data_api.call_reason', 'scheduled_update')
        newrelic.agent.add_custom_attribute('football_data_api.environment', environment)
        newrelic.agent.add_custom_attribute('football_data_api.url', url)
        newrelic.agent.add_custom_attribute('football_data_api.timestamp', datetime.now(timezone.utc).isoformat())
        print("New Relic metrics recorded for API call")

    start_time = datetime.now(timezone.utc)
    response = requests.get(url, headers=headers, timeout=30)
    end_time = datetime.now(timezone.utc)
    response_time_ms = (end_time - start_time).total_seconds() * 1000

    print(f"API Response Status: {response.status_code}")
    print(f"API Response Time: {response_time_ms:.2f}ms")
    print(f"API Response Headers: {dict(response.headers)}")

    # Record response metrics
    if NEW_RELIC_ENABLED:
        print(f"Recording New Relic response metrics: status={response.status_code}, time={response_time_ms:.2f}ms")
        newrelic.agent.record_custom_metric('Custom/FootballDataAPI/ResponseTime', response_time_ms)
        newrelic.agent.record_custom_metric(f'Custom/FootballDataAPI/StatusCode/{response.status_code}', 1)
        newrelic.agent.add_custom_attribute('football_data_api.response_status', response.status_code)
        newrelic.agent.add_custom_attribute('football_data_api.response_time_ms', response_time_ms)
        print("New Relic response metrics recorded")

    response.raise_for_status()

    data = response.json()
    print(f"API Response Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
    print(f"API Response sample: {str(data)[:500]}...")

    # Record successful API call metrics
    if NEW_RELIC_ENABLED:
        # football-data.org returns: {"standings": [{"type": "TOTAL", "table": [...]}]}
        teams_count = 0
        if 'standings' in data and len(data['standings']) > 0:
            # Find the TOTAL standings (as opposed to HOME/AWAY)
            for standing in data['standings']:
                if standing.get('type') == 'TOTAL':
                    teams_count = len(standing.get('table', []))
                    break
        newrelic.agent.record_custom_metric('Custom/FootballDataAPI/TeamsReturned', teams_count)
        newrelic.agent.add_custom_attribute('football_data_api.teams_count', teams_count)

    return data

def calculate_forecasts(epl_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate forecasted final table based on points per game

    football-data.org API structure:
    {
        "standings": [
            {
                "type": "TOTAL",
                "table": [
                    {
                        "position": 1,
                        "team": {"name": "Arsenal", ...},
                        "playedGames": 10,
                        "won": 7,
                        "draw": 2,
                        "lost": 1,
                        "points": 23,
                        "goalsFor": 20,
                        "goalsAgainst": 10,
                        "goalDifference": 10
                    }
                ]
            }
        ]
    }
    """
    teams = []

    # Extract TOTAL standings table from football-data.org response
    table_data = []
    if 'standings' in epl_data:
        for standing in epl_data['standings']:
            if standing.get('type') == 'TOTAL':
                table_data = standing.get('table', [])
                break

    print(f"Table data found: {len(table_data)} teams")

    if not table_data:
        print("WARNING: No TOTAL standings table found in API response!")
        print(f"Available keys in epl_data: {list(epl_data.keys())}")
        if 'standings' in epl_data:
            print(f"Standings types available: {[s.get('type') for s in epl_data['standings']]}")

    for team_data in table_data:
        played = team_data.get('playedGames', 0)
        points = team_data.get('points', 0)

        if played > 0:
            points_per_game = points / played
            forecasted_points = points_per_game * 38  # Full season is 38 games
        else:
            points_per_game = 0
            forecasted_points = 0

        team = {
            'name': team_data.get('team', {}).get('name', ''),
            'played': played,
            'won': team_data.get('won', 0),
            'drawn': team_data.get('draw', 0),  # Note: API uses 'draw' not 'drawn'
            'lost': team_data.get('lost', 0),
            'for': team_data.get('goalsFor', 0),
            'against': team_data.get('goalsAgainst', 0),
            'goal_difference': team_data.get('goalDifference', 0),
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
    # Store with TTL of 7 days (604800 seconds)
    # Provides safety buffer - data refreshes 2x daily but won't expire if there are issues
    ttl = int((datetime.now(timezone.utc).timestamp() + 604800))
    
    table.put_item(
        Item={
            'id': 'current_forecast',
            'data': data,
            'ttl': ttl
        }
    )