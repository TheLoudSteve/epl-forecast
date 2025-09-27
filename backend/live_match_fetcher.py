import json
import os
import boto3
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from decimal import Decimal
import icalendar
from dateutil import tz

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
s3 = boto3.client('s3', region_name=region)

# @newrelic.agent.lambda_handler if NEW_RELIC_ENABLED else lambda x: x
def lambda_handler(event, context):
    """
    Lambda function to check for live matches and update data if needed
    OPTIMIZATION: Quick pre-check to avoid expensive ICS processing on non-match days
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

        # DYNAMIC SCHEDULING: Detect execution mode (dynamic vs legacy)
        is_dynamic_mode = detect_dynamic_scheduling_mode(event)
        execution_mode = 'dynamic' if is_dynamic_mode else 'legacy'

        print(f"Execution mode: {execution_mode}")

        # Add execution mode to New Relic
        if NEW_RELIC_ENABLED:
            newrelic.agent.add_custom_attribute('execution_mode', execution_mode)
            newrelic.agent.record_custom_metric(f'Custom/LiveFetcher/{execution_mode.title()}Execution', 1)

        # DYNAMIC MODE: Skip ICS processing, directly call RapidAPI
        if is_dynamic_mode:
            return handle_dynamic_scheduled_match(table_name, rapidapi_key, event)

        # LEGACY MODE: Continue with existing logic (ICS parsing + quick checks)
        print("Running in LEGACY mode - using existing ICS parsing logic")

        # COST OPTIMIZATION: Quick pre-check before expensive ICS processing
        quick_check = quick_match_day_check()
        if not quick_check['likely_match_day']:
            print(f"Quick check: No matches likely today - {quick_check['reason']}")
            # Record skipped execution for monitoring
            if NEW_RELIC_ENABLED:
                newrelic.agent.record_custom_metric('Custom/LiveFetcher/QuickCheckSkipped', 1)
                newrelic.agent.add_custom_attribute('skip_reason', quick_check['reason'])

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Quick check: No matches likely - skipped expensive processing',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'reason': quick_check['reason'],
                    'optimization': 'quick_check_skip',
                    'execution_mode': 'legacy'
                })
            }

        print(f"Quick check passed: {quick_check['reason']} - proceeding with full match check")

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

            # CRITICAL: Explicitly exit early to avoid timeout
            print("Function exiting early - no further processing needed")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No live matches - skipped API call',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'match_happening': False,
                    'match_context': match_context,
                    'execution_mode': 'legacy'
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
            snapshot = _get_forecast_history_manager().save_forecast_snapshot(
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
            notification_result = _get_notification_manager().process_forecast_update(
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
                'execution_mode': 'legacy',
                'notifications_sent': notification_result.get('notifications_sent', 0)
            })
        }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'execution_mode': 'legacy'
            })
        }

def detect_dynamic_scheduling_mode(event: Dict[str, Any]) -> bool:
    """
    Detect if this execution is from dynamic scheduling (Schedule Manager) or legacy polling.

    Dynamic mode indicators:
    1. Event source is 'schedule-manager'
    2. Event contains 'dynamic_scheduling': True
    3. Event contains match_info from Schedule Manager

    Args:
        event: Lambda event payload

    Returns:
        True if dynamic mode, False if legacy mode
    """
    try:
        # Check for Schedule Manager event markers
        if isinstance(event, dict):
            # Direct marker from Schedule Manager
            if event.get('dynamic_scheduling') is True:
                return True

            # Event source from Schedule Manager
            if event.get('source') == 'schedule-manager':
                return True

            # Check for match_info payload (Schedule Manager specific)
            if 'match_info' in event:
                return True

        return False

    except Exception as e:
        print(f"Error detecting dynamic mode, defaulting to legacy: {e}")
        return False


def handle_dynamic_scheduled_match(table_name: str, rapidapi_key: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle dynamically scheduled match execution - optimized path without ICS parsing.

    When Schedule Manager triggers this function, we know a match is happening,
    so we can skip all the expensive ICS processing and go directly to RapidAPI.

    Args:
        table_name: DynamoDB table name
        rapidapi_key: RapidAPI key
        event: Lambda event with match info

    Returns:
        Standard Lambda response
    """
    try:
        print("🚀 DYNAMIC MODE: Processing scheduled match without ICS parsing")

        # Extract match info if available
        match_info = event.get('match_info', {})
        match_context = match_info.get('summary', 'Scheduled match')

        print(f"Match context from Schedule Manager: {match_context}")

        # Record dynamic execution metrics
        if NEW_RELIC_ENABLED:
            newrelic.agent.record_custom_metric('Custom/LiveFetcher/DynamicModeExecution', 1)
            newrelic.agent.add_custom_attribute('match_context', match_context)
            newrelic.agent.add_custom_attribute('scheduled_by', 'schedule_manager')

        # Get DynamoDB table
        table = dynamodb.Table(table_name)

        # Since we're dynamically scheduled, we know matches are happening
        # Skip ICS processing and go directly to RapidAPI
        print("Fetching fresh EPL data (dynamic scheduling - no ICS check needed)")

        epl_data = fetch_epl_data(rapidapi_key, f"Dynamic: {match_context}")
        print(f"Fetched EPL data with {len(epl_data.get('table', []))} teams")

        # Calculate forecasts
        forecast_data = calculate_forecasts(epl_data)
        print(f"Calculated forecast data for {len(forecast_data.get('teams', []))} teams")

        # Store in DynamoDB
        store_data(table, forecast_data)
        print("Successfully stored dynamic match data in DynamoDB")

        # Save forecast snapshot to history
        try:
            context = f"Dynamic match update - {match_context}"
            snapshot = _get_forecast_history_manager().save_forecast_snapshot(
                forecast_data,
                context=context
            )
            print(f"Successfully saved dynamic match forecast snapshot with timestamp {snapshot.timestamp}")
        except Exception as snapshot_error:
            print(f"Error saving dynamic match forecast snapshot: {snapshot_error}")

        # Process notifications for position changes
        notification_result = {'notifications_sent': 0}
        try:
            notification_result = _get_notification_manager().process_forecast_update(
                forecast_data,
                context=f"Dynamic: {match_context}"
            )
            print(f"Dynamic match notification processing result: {notification_result}")
        except Exception as notification_error:
            print(f"Error processing dynamic match notifications: {notification_error}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Dynamic scheduled match processed successfully',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'teams_processed': len(forecast_data.get('teams', [])),
                'match_context': match_context,
                'execution_mode': 'dynamic',
                'notifications_sent': notification_result.get('notifications_sent', 0)
            })
        }

    except Exception as e:
        print(f"Error in dynamic mode: {str(e)}")
        if NEW_RELIC_ENABLED:
            newrelic.agent.record_exception()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'execution_mode': 'dynamic'
            })
        }


def quick_match_day_check() -> Dict[str, Any]:
    """
    COST OPTIMIZATION: Quick check to avoid expensive ICS processing on obvious non-match days.

    Uses simple heuristics to determine if it's worth doing full ICS processing:
    1. Premier League typically plays Saturday/Sunday/Wednesday/Monday
    2. Season runs roughly August-May
    3. No matches during certain international breaks

    Returns:
        dict: {'likely_match_day': bool, 'reason': str}
    """
    now = datetime.now(tz.gettz('Europe/London'))
    current_day = now.weekday()  # 0=Monday, 6=Sunday
    current_month = now.month
    current_hour = now.hour

    # Quick seasonal check: Premier League season typically August (8) to May (5)
    if current_month in [6, 7]:  # June-July: Summer break
        return {
            'likely_match_day': False,
            'reason': f'Summer break (month {current_month})'
        }

    # Quick day-of-week check: Most EPL matches on Sat(5), Sun(6), Mon(0), Wed(2), Thu(3)
    # Tue(1), Fri(4) are very rare for EPL matches
    if current_day in [1, 4]:  # Tuesday, Friday
        return {
            'likely_match_day': False,
            'reason': f'Rare match day: {["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][current_day]}'
        }

    # Quick time-of-day check: EPL matches typically 12:30-21:00 London time
    # Outside these hours + 3-hour buffer, very unlikely to have live matches
    if current_hour < 9 or current_hour > 24:  # Before 9am or after midnight
        return {
            'likely_match_day': False,
            'reason': f'Outside typical match hours ({current_hour:02d}:xx London time)'
        }

    # If we pass all quick checks, it's worth doing full ICS processing
    return {
        'likely_match_day': True,
        'reason': f'{["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][current_day]} {current_hour:02d}:xx in season'
    }


def check_if_match_happening(s3_bucket: str) -> Dict[str, Any]:
    """
    Check ICS feed to determine if matches are happening
    Match window: 15 minutes before kickoff to 30 minutes after final whistle
    Returns dict with 'happening' boolean and 'context' string
    """
    try:
        ics_content = None
        cache_hit = False

        # Try to get cached ICS from S3 first (cache for 29 hours - schedules rarely change)
        try:
            response = s3.get_object(Bucket=s3_bucket, Key='epl_fixtures.ics')
            last_modified = response['LastModified']
            now = datetime.now(timezone.utc)

            # Use cache if less than 29 hours old (schedules rarely change, 29h creates daily rotation)
            if (now - last_modified.replace(tzinfo=timezone.utc)).total_seconds() < 104400:
                ics_content = response['Body'].read()
                cache_hit = True
                print("Using cached ICS data from S3")
            else:
                print("Cached ICS data is stale, fetching fresh")
        except Exception as cache_error:
            print(f"Could not retrieve cached ICS: {cache_error}")

        # Fetch fresh ICS if no valid cache
        if ics_content is None:
            print("Fetching fresh ICS data from source")
            ics_url = "https://ics.ecal.com/ecal-sub/68a47e3ff49aba000867f867/English%20Premier%20League.ics"
            response = requests.get(ics_url, timeout=30)
            response.raise_for_status()
            ics_content = response.content

            # Cache fresh ICS data in S3
            s3.put_object(
                Bucket=s3_bucket,
                Key='epl_fixtures.ics',
                Body=ics_content,
                ContentType='text/calendar'
            )
        
        # Parse calendar
        cal = icalendar.Calendar.from_ical(ics_content)
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
            print(f"ICS processing: cache_hit={cache_hit}, matches_found={matches_found}, active_matches={len(active_matches)}")
            return {
                'happening': True,
                'context': context,
                'matches': active_matches,
                'total_matches_checked': matches_found,
                'cache_hit': cache_hit
            }
        else:
            context = f"No live matches (checked {matches_found} total matches)"
            print(f"ICS processing: cache_hit={cache_hit}, matches_found={matches_found}, active_matches=0")
            print(context)
            return {
                'happening': False,
                'context': context,
                'matches': [],
                'total_matches_checked': matches_found,
                'cache_hit': cache_hit
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