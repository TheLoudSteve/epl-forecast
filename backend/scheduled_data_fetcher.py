import json
import os
import boto3
import requests
from datetime import datetime, timezone
from typing import Dict, List, Any
from decimal import Decimal
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError, after_log, before_sleep_log
import logging

# Set up logging for retry tracking
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
from forecast_history import forecast_history_manager
from notification_logic import notification_manager

# New Relic monitoring
try:
    import newrelic.agent
    NEW_RELIC_ENABLED = True
    # Initialize New Relic agent
    newrelic.agent.initialize()
except ImportError:
    NEW_RELIC_ENABLED = False

# Use the region from environment or default to us-east-1 for backward compatibility
region = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=region)

@newrelic.agent.lambda_handler() if NEW_RELIC_ENABLED else lambda f: f
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

def _log_retry_attempt(retry_state):
    """Callback to log and track retry attempts in New Relic."""
    attempt_number = retry_state.attempt_number
    print(f"Retrying football-data.org API call (attempt {attempt_number}/3)...")
    if NEW_RELIC_ENABLED:
        newrelic.agent.record_custom_event('FootballAPIRetry', {
            'attempt_number': attempt_number,
            'max_attempts': 3
        })

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=_log_retry_attempt,
    reraise=True
)
def fetch_epl_data(api_key: str) -> Dict[str, Any]:
    """
    Fetch current EPL standings from football-data.org API with retry logic.
    Retries up to 3 times with exponential backoff (2s, 4s, 8s).
    """
    url = "https://api.football-data.org/v4/competitions/PL/standings"

    headers = {
        "X-Auth-Token": api_key
    }

    print(f"Calling football-data.org API: {url}")

    # Record New Relic custom event for API call
    environment = os.environ.get('ENVIRONMENT', 'unknown')
    if NEW_RELIC_ENABLED:
        print("Recording New Relic event for football-data.org API call...")
        newrelic.agent.add_custom_attribute('football_data_api.call_reason', 'scheduled_update')
        newrelic.agent.add_custom_attribute('football_data_api.environment', environment)
        print("New Relic attributes added for API call")

    start_time = datetime.now(timezone.utc)
    response = requests.get(url, headers=headers, timeout=30)
    end_time = datetime.now(timezone.utc)
    response_time_ms = (end_time - start_time).total_seconds() * 1000

    print(f"API Response Status: {response.status_code}")
    print(f"API Response Time: {response_time_ms:.2f}ms")
    print(f"API Response Headers: {dict(response.headers)}")

    # Record response event
    if NEW_RELIC_ENABLED:
        print(f"Recording New Relic response event: status={response.status_code}, time={response_time_ms:.2f}ms")
        newrelic.agent.record_custom_event('FootballAPICall', {
            'response_status': response.status_code,
            'response_time_ms': response_time_ms,
            'call_reason': 'scheduled_update',
            'environment': environment,
            'api_url': url
        })
        newrelic.agent.add_custom_attribute('football_data_api.response_status', response.status_code)
        newrelic.agent.add_custom_attribute('football_data_api.response_time_ms', response_time_ms)
        print("New Relic response event recorded")

    response.raise_for_status()

    data = response.json()
    print(f"API Response Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
    print(f"API Response sample: {str(data)[:500]}...")

    # Add teams count as custom attribute
    if NEW_RELIC_ENABLED:
        # football-data.org returns: {"standings": [{"type": "TOTAL", "table": [...]}]}
        teams_count = 0
        if 'standings' in data and len(data['standings']) > 0:
            # Find the TOTAL standings (as opposed to HOME/AWAY)
            for standing in data['standings']:
                if standing.get('type') == 'TOTAL':
                    teams_count = len(standing.get('table', []))
                    break
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