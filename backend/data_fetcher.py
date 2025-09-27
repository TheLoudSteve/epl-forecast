import json
import os
import boto3
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from decimal import Decimal
import icalendar
from dateutil import tz

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

@newrelic.agent.lambda_handler if NEW_RELIC_ENABLED else lambda x: x
def lambda_handler(event, context):
    """
    Lambda function to fetch EPL data and calculate forecasts
    """
    try:
        print(f"Lambda triggered with event: {event}")
        
        # Add New Relic custom attributes
        if NEW_RELIC_ENABLED:
            newrelic.agent.add_custom_attribute('lambda.event_type', event.get('source', 'unknown'))
            newrelic.agent.add_custom_attribute('lambda.environment', os.environ.get('ENVIRONMENT', 'unknown'))
        
        table_name = os.environ['DYNAMODB_TABLE']
        s3_bucket = os.environ['S3_BUCKET']
        rapidapi_key = os.environ['RAPIDAPI_KEY']
        
        print(f"Environment variables - Table: {table_name}, Bucket: {s3_bucket}")
        
        table = dynamodb.Table(table_name)
        
        # Check if we should update based on environment
        environment = os.environ.get('ENVIRONMENT', 'dev')
        
        if environment == 'dev':
            # Test/dev: Only update at scheduled times (12am/12pm UTC)
            if not is_scheduled_time():
                print(f"Skipping update - not scheduled time in {environment} environment")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Skipped - not scheduled time',
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'environment': environment
                    })
                }
        else:
            # Production: Check both scheduled times AND live matches
            is_scheduled = is_scheduled_time()
            is_match_happening = check_if_update_needed(s3_bucket)
            
            print(f"Production environment - Scheduled time: {is_scheduled}, Match happening: {is_match_happening}")
            
            if not is_scheduled and not is_match_happening:
                print("Skipping update - not scheduled time and no live matches")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Skipped - not scheduled time and no live matches',
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'environment': environment,
                        'scheduled_time': is_scheduled,
                        'match_happening': is_match_happening
                    })
                }
        
        print("Starting data fetch...")
        
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
                'message': 'Data updated successfully',
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
    
    response = requests.get(url, headers=headers, params=querystring, timeout=30)
    print(f"API Response Status: {response.status_code}")
    print(f"API Response Headers: {dict(response.headers)}")
    
    response.raise_for_status()
    
    data = response.json()
    print(f"API Response Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
    print(f"API Response sample: {str(data)[:500]}...")
    
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
        'total_teams': len(teams)
    }

def is_scheduled_time() -> bool:
    """
    Check if current time is during scheduled update windows (12am or 12pm UTC)
    Allows a 15-minute window around each scheduled time
    """
    now = datetime.now(timezone.utc)
    current_hour = now.hour
    current_minute = now.minute
    
    # Check if we're within 15 minutes of 12am (midnight) UTC: 23:45-00:15
    midnight_window = (current_hour == 23 and current_minute >= 45) or \
                      (current_hour == 0 and current_minute <= 15)
                      
    # Check if we're within 15 minutes of 12pm (noon) UTC: 11:45-12:15
    noon_window = (current_hour == 11 and current_minute >= 45) or \
                  (current_hour == 12 and current_minute <= 15)
    
    is_scheduled = midnight_window or noon_window
    print(f"Time check - Current: {now.strftime('%H:%M')} UTC, Midnight: {midnight_window}, Noon: {noon_window}, Scheduled: {is_scheduled}")
    
    return is_scheduled

def check_if_update_needed(s3_bucket: str) -> bool:
    """
    Check ICS feed to determine if matches are happening
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
        
        # Check for matches in progress (15 min before to 30 min after)
        for component in cal.walk():
            if component.name == "VEVENT":
                start_time = component.get('dtstart').dt
                if isinstance(start_time, datetime):
                    start_time = start_time.astimezone(london_tz)
                    
                    # Calculate match window (5 min before to 3 hours after)
                    match_start = start_time - timedelta(minutes=5)
                    match_end = start_time + timedelta(hours=3)
                    
                    if match_start <= now <= match_end:
                        return True
        
        return False
        
    except Exception as e:
        print(f"Error checking ICS feed: {str(e)}")
        # If we can't check, assume no matches are happening to avoid excessive API calls
        return False

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