import json
import os
import boto3
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from decimal import Decimal
import icalendar
from dateutil import tz
from forecast_history import forecast_history_manager
from notification_logic import notification_manager

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
s3 = boto3.client('s3', region_name=region)

@newrelic.agent.lambda_handler() if NEW_RELIC_ENABLED else lambda x: x
def lambda_handler(event, context):
    """
    Lambda function to check for live matches and update data if needed
    Runs every 2 minutes but only calls RapidAPI during match windows
    """
    try:
        print(f"Live match check triggered with event: {event}")
        
        # Add New Relic custom attributes
        if NEW_RELIC_ENABLED:
            newrelic.agent.add_custom_attribute('lambda.event_type', 'live_match_check')
            newrelic.agent.add_custom_attribute('lambda.environment', os.environ.get('ENVIRONMENT', 'unknown'))
        
        table_name = os.environ['DYNAMODB_TABLE']
        s3_bucket = os.environ['S3_BUCKET']
        rapidapi_key = os.environ['RAPIDAPI_KEY']
        
        print(f"Environment variables - Table: {table_name}, Bucket: {s3_bucket}")
        
        # Check if we should update based on live matches
        match_result = check_if_match_happening(s3_bucket)
        match_happening = match_result.get('happening', False)
        match_context = match_result.get('context', 'No matches detected')
        
        print(f"Live match check result: {match_happening}")
        print(f"Match context: {match_context}")
        
        if not match_happening:
            print("No live matches detected - skipping API call")
            # Record New Relic metric for skipped call
            if NEW_RELIC_ENABLED:
                newrelic.agent.record_custom_metric('Custom/RapidAPI/CallSkipped', 1)
                newrelic.agent.add_custom_attribute('rapidapi.skip_reason', 'no_live_matches')
                newrelic.agent.add_custom_attribute('rapidapi.environment', os.environ.get('ENVIRONMENT', 'unknown'))
                
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No live matches - skipped API call',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'match_happening': False,
                    'match_context': match_context
                })
            }
        
        # Match is happening - fetch fresh data
        print("Live match detected - fetching fresh data...")
        
        table = dynamodb.Table(table_name)
        
        # Fetch current EPL table with match context
        epl_data = fetch_epl_data(rapidapi_key, match_context)
        print(f"Fetched EPL data with {len(epl_data.get('table', []))} teams")
        
        # Calculate forecasts
        forecast_data = calculate_forecasts(epl_data)
        print(f"Calculated forecast data for {len(forecast_data.get('teams', []))} teams")
        
        # Store in DynamoDB
        store_data(table, forecast_data)
        print("Successfully stored live match data in DynamoDB")
        
        # Save forecast snapshot to history
        try:
            context = f"Live match update - {match_context}"
            snapshot = forecast_history_manager.save_forecast_snapshot(
                forecast_data, 
                context=context
            )
            print(f"Successfully saved live match forecast snapshot with timestamp {snapshot.timestamp}")
        except Exception as snapshot_error:
            print(f"Error saving live match forecast snapshot: {snapshot_error}")
            # Don't fail the entire function if snapshot saving fails
        
        # Process notifications for position changes during live matches
        notification_result = {'notifications_sent': 0}
        try:
            notification_result = notification_manager.process_forecast_update(
                forecast_data,
                context=f"after {match_context}"
            )
            print(f"Live match notification processing result: {notification_result}")
        except Exception as notification_error:
            print(f"Error processing live match notifications: {notification_error}")
            # Don't fail the entire function if notification processing fails
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Live match data updated successfully',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'teams_processed': len(forecast_data.get('teams', [])),
                'match_happening': True,
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

def check_if_match_happening(s3_bucket: str) -> Dict[str, Any]:
    """
    Check ICS feed to determine if matches are happening
    Match window: 15 minutes before kickoff to 30 minutes after final whistle
    Returns dict with 'happening' boolean and 'context' string
    """
    try:
        # Fetch ICS feed
        ics_url = "https://ics.ecal.com/ecal-sub/68a47e3ff49aba000867f867/English%20Premier%20League.ics"
        response = requests.get(ics_url, timeout=30)
        response.raise_for_status()
        
        # Cache ICS data in S3
        s3.put_object(
            Bucket=s3_bucket,
            Key='epl_fixtures.ics',
            Body=response.content,
            ContentType='text/calendar'
        )
        
        # Parse calendar
        cal = icalendar.Calendar.from_ical(response.content)
        london_tz = tz.gettz('Europe/London')
        now = datetime.now(london_tz)
        
        print(f"Checking for matches around current time: {now.strftime('%Y-%m-%d %H:%M %Z')}")
        
        # Check for matches in the specified window
        matches_found = 0
        active_matches = []
        
        for component in cal.walk():
            if component.name == "VEVENT":
                start_time = component.get('dtstart').dt
                if isinstance(start_time, datetime):
                    start_time = start_time.astimezone(london_tz)
                    
                    # Match window: 15 minutes before kickoff to 30 minutes after match end
                    # Assume match lasts ~2 hours, so 30 min after = 2.5 hours after start
                    match_start = start_time - timedelta(minutes=15)
                    match_end = start_time + timedelta(hours=2, minutes=30)
                    
                    matches_found += 1
                    
                    if match_start <= now <= match_end:
                        match_summary = component.get('summary', 'Unknown Match')
                        active_matches.append({
                            'summary': match_summary,
                            'start_time': start_time.strftime('%Y-%m-%d %H:%M %Z'),
                            'status': 'live' if start_time <= now else 'pre-match'
                        })
                        print(f"LIVE MATCH DETECTED: {match_summary}")
                        print(f"  Start: {start_time.strftime('%Y-%m-%d %H:%M %Z')}")
                        print(f"  Window: {match_start.strftime('%H:%M')} - {match_end.strftime('%H:%M')}")
                        print(f"  Current: {now.strftime('%H:%M')}")
        
        if active_matches:
            context = f"{len(active_matches)} active match(es): " + ", ".join([m['summary'] for m in active_matches])
            return {
                'happening': True,
                'context': context,
                'matches': active_matches,
                'total_matches_checked': matches_found
            }
        else:
            context = f"No live matches (checked {matches_found} total matches)"
            print(context)
            return {
                'happening': False,
                'context': context,
                'matches': [],
                'total_matches_checked': matches_found
            }
        
    except Exception as e:
        error_context = f"Error checking ICS feed: {str(e)}"
        print(error_context)
        # Conservative approach: if we can't check, don't make unnecessary API calls
        return {
            'happening': False,
            'context': error_context,
            'matches': [],
            'total_matches_checked': 0
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
    
    print(f"Calling RapidAPI for live match data: {url}")
    print(f"Match context: {match_context}")
    
    # Record New Relic custom metric for RapidAPI call
    environment = os.environ.get('ENVIRONMENT', 'unknown')
    if NEW_RELIC_ENABLED:
        newrelic.agent.record_custom_metric('Custom/RapidAPI/CallMade', 1)
        newrelic.agent.record_custom_metric('Custom/RapidAPI/LiveMatchCall', 1)
        newrelic.agent.add_custom_attribute('rapidapi.call_reason', 'live_match_update')
        newrelic.agent.add_custom_attribute('rapidapi.environment', environment)
        newrelic.agent.add_custom_attribute('rapidapi.url', url)
        newrelic.agent.add_custom_attribute('rapidapi.match_context', match_context)
        newrelic.agent.add_custom_attribute('rapidapi.timestamp', datetime.now(timezone.utc).isoformat())
    
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
        newrelic.agent.record_custom_metric('Custom/RapidAPI/LiveMatchResponseTime', response_time_ms)
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