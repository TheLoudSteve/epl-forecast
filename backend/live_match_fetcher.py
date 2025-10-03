import json
import os
import boto3
import requests
from datetime import datetime, timezone
from typing import Dict, Any
from decimal import Decimal

# Lazy import heavy modules only when needed
forecast_history_manager = None
notification_manager = None

def _get_forecast_history_manager():
    """Lazy load forecast history manager only when needed."""
    global forecast_history_manager
    if forecast_history_manager is None:
        from forecast_history import forecast_history_manager
    return forecast_history_manager

def _get_notification_manager():
    """Lazy load notification manager only when needed."""
    global notification_manager
    if notification_manager is None:
        from notification_logic import notification_manager
    return notification_manager

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

# @newrelic.agent.lambda_handler if NEW_RELIC_ENABLED else lambda x: x
def lambda_handler(event, context):
    """
    Lambda function triggered by Schedule Manager when matches are scheduled.
    Directly fetches EPL data and updates forecasts - no ICS parsing needed.
    """
    try:
        print(f"Match update triggered with event: {event}")

        # Add New Relic custom attributes
        if NEW_RELIC_ENABLED:
            newrelic.agent.add_custom_attribute('lambda.event_type', 'scheduled_match_update')
            newrelic.agent.add_custom_attribute('lambda.environment', os.environ.get('ENVIRONMENT', 'unknown'))

        table_name = os.environ['DYNAMODB_TABLE']
        rapidapi_key = os.environ['RAPIDAPI_KEY']

        print(f"Environment variables - Table: {table_name}")

        # Extract match info from event
        match_info = event.get('match_info', {})
        match_context = match_info.get('summary', 'Scheduled match')

        print(f"Processing scheduled match: {match_context}")

        # Record execution metrics
        if NEW_RELIC_ENABLED:
            newrelic.agent.add_custom_attribute('match_context', match_context)
            newrelic.agent.record_custom_metric('Custom/LiveFetcher/ScheduledExecution', 1)

        # Get DynamoDB table
        table = dynamodb.Table(table_name)

        # Fetch fresh EPL data
        print("Fetching fresh EPL data from RapidAPI")
        epl_data = fetch_epl_data(rapidapi_key, match_context)
        print(f"Fetched EPL data with {len(epl_data.get('table', []))} teams")

        # Calculate forecasts
        forecast_data = calculate_forecasts(epl_data)
        print(f"Calculated forecast data for {len(forecast_data.get('teams', []))} teams")

        # Store in DynamoDB
        store_data(table, forecast_data)
        print("Successfully stored match data in DynamoDB")

        # Save forecast snapshot to history
        try:
            context = f"Match update - {match_context}"
            snapshot = _get_forecast_history_manager().save_forecast_snapshot(
                forecast_data,
                context=context
            )
            print(f"Successfully saved forecast snapshot with timestamp {snapshot.timestamp}")
        except Exception as snapshot_error:
            print(f"Error saving forecast snapshot: {snapshot_error}")

        # Process notifications for position changes
        notification_result = {'notifications_sent': 0}
        try:
            notification_result = _get_notification_manager().process_forecast_update(
                forecast_data,
                context=match_context
            )
            print(f"Notification processing result: {notification_result}")
        except Exception as notification_error:
            print(f"Error processing notifications: {notification_error}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Match data updated successfully',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'teams_processed': len(forecast_data.get('teams', [])),
                'match_context': match_context,
                'notifications_sent': notification_result.get('notifications_sent', 0)
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        if NEW_RELIC_ENABLED:
            newrelic.agent.record_exception()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        }


def fetch_epl_data(rapidapi_key: str, match_context: str = "") -> Dict[str, Any]:
    """
    Fetch current EPL table from RapidAPI
    """
    url = "https://football-web-pages1.p.rapidapi.com/league-table.json"
    querystring = {"comp": "1", "team": "1"}

    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": "football-web-pages1.p.rapidapi.com"
    }

    print(f"Calling RapidAPI for match data: {url}")
    print(f"Match context: {match_context}")

    # Record New Relic custom metric for RapidAPI call
    environment = os.environ.get('ENVIRONMENT', 'unknown')
    if NEW_RELIC_ENABLED:
        newrelic.agent.record_custom_metric('Custom/RapidAPI/CallMade', 1)
        newrelic.agent.record_custom_metric('Custom/RapidAPI/MatchCall', 1)
        newrelic.agent.add_custom_attribute('rapidapi.call_reason', 'match_update')
        newrelic.agent.add_custom_attribute('rapidapi.environment', environment)
        newrelic.agent.add_custom_attribute('rapidapi.match_context', match_context)

    start_time = datetime.now(timezone.utc)
    response = requests.get(url, headers=headers, params=querystring, timeout=30)
    end_time = datetime.now(timezone.utc)
    response_time_ms = (end_time - start_time).total_seconds() * 1000

    print(f"API Response Status: {response.status_code}")
    print(f"API Response Time: {response_time_ms:.2f}ms")

    # Record response metrics
    if NEW_RELIC_ENABLED:
        newrelic.agent.record_custom_metric('Custom/RapidAPI/ResponseTime', response_time_ms)
        newrelic.agent.record_custom_metric(f'Custom/RapidAPI/StatusCode/{response.status_code}', 1)
        newrelic.agent.add_custom_attribute('rapidapi.response_status', response.status_code)
        newrelic.agent.add_custom_attribute('rapidapi.response_time_ms', response_time_ms)

    response.raise_for_status()

    data = response.json()
    print(f"API Response Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

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
    
    # Extract team data from API response
    table_data = epl_data.get('league-table', {}).get('teams', [])
    
    if not table_data:
        # Try alternative key structures
        if 'table' in epl_data:
            table_data = epl_data.get('table', [])
        elif 'standings' in epl_data:
            table_data = epl_data.get('standings', [])
    
    for team_data in table_data:
        # Extract data from the correct API structure
        all_matches = team_data.get('all-matches', {})
        played = all_matches.get('played', 0)
        points = team_data.get('total-points', 0)
        
        if played > 0:
            points_per_game = points / played
            forecasted_points = points_per_game * 38
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
        'update_type': 'live_match'
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