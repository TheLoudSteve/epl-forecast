"""
Schedule Manager for EPL Forecast - Intelligent Scheduling System

This function replaces constant polling with dynamic EventBridge rule creation
based on actual fixture data, dramatically reducing Lambda costs on non-match days.

Runs daily to:
1. Parse ICS feed to extract upcoming EPL matches
2. Create EventBridge rules for match windows (15min before to 30min after)
3. Clean up expired rules from previous matches
4. Store schedule state for monitoring and debugging

EPLF-40: Core Schedule Manager implementation for dev environment
"""

import json
import os
import boto3
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import icalendar
import zoneinfo

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

# AWS clients
region = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=region)
s3 = boto3.client('s3', region_name=region)
events = boto3.client('events', region_name=region)

# @newrelic.agent.lambda_handler if NEW_RELIC_ENABLED else lambda x: x
def lambda_handler(event, context):
    """
    Schedule Manager Lambda function - Runs every 15 minutes for precise match window control

    Enables 2-minute polling rule when:
    - Any match starts in next 15 minutes, OR
    - Any match is currently active (started but not yet ended)

    Disables 2-minute polling rule when:
    - No matches starting in next 15 minutes AND
    - No matches ending in last 30 minutes
    """
    try:
        print(f"Schedule Manager triggered with event: {event}")

        # Add New Relic custom attributes
        if NEW_RELIC_ENABLED:
            newrelic.agent.add_custom_attribute('lambda.event_type', 'schedule_manager')
            newrelic.agent.add_custom_attribute('lambda.environment', os.environ.get('ENVIRONMENT', 'unknown'))

        schedule_table_name = os.environ['SCHEDULE_TABLE']
        s3_bucket = os.environ['S3_BUCKET']
        environment = os.environ.get('ENVIRONMENT', 'dev')

        print(f"Environment: {environment}")
        print(f"Schedule Table: {schedule_table_name}")
        print(f"S3 Bucket: {s3_bucket}")

        schedule_table = dynamodb.Table(schedule_table_name)

        # Step 1: Parse ICS feed to find matches in active/upcoming window
        print("🔍 Step 1: Checking for active or upcoming matches...")
        matches = parse_ics_schedule(s3_bucket)
        print(f"Found {len(matches)} matches in ICS feed")

        # Step 2: Determine if we're in a match window
        print("⏰ Step 2: Evaluating match window status...")
        window_status = evaluate_match_window(matches)
        print(f"Match window active: {window_status['is_active']}")
        print(f"Reason: {window_status['reason']}")

        # Step 3: Enable/disable the 2-minute polling rule based on match window
        print("🎛️ Step 3: Managing 2-minute polling rule...")
        rule_result = manage_polling_rule(window_status, matches, environment)
        print(f"Rule state: {rule_result['state']}")

        # Step 4: Store schedule state in DynamoDB
        print("💾 Step 4: Storing schedule state...")
        schedule_state = {
            'matches_in_feed': len(matches),
            'window_active': window_status['is_active'],
            'window_reason': window_status['reason'],
            'active_matches': window_status.get('active_matches', []),
            'upcoming_matches': window_status.get('upcoming_matches', []),
            'rule_state': rule_result['state'],
            'matches': matches
        }
        store_schedule_state(schedule_table, schedule_state)

        # Record metrics
        if NEW_RELIC_ENABLED:
            newrelic.agent.record_custom_metric('Custom/ScheduleManager/MatchesInFeed', len(matches))
            newrelic.agent.record_custom_metric('Custom/ScheduleManager/WindowActive', 1 if window_status['is_active'] else 0)
            newrelic.agent.record_custom_metric('Custom/ScheduleManager/RuleEnabled', 1 if rule_result['state'] == 'ENABLED' else 0)

            # Record match window evaluation event
            newrelic.agent.record_custom_event('MatchWindowEvaluation', {
                'window_active': window_status['is_active'],
                'active_matches': len(window_status.get('active_matches', [])),
                'upcoming_matches': len(window_status.get('upcoming_matches', [])),
                'rule_state': rule_result['state'],
                'reason': window_status['reason']
            })

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Schedule Manager completed successfully',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'window_active': window_status['is_active'],
                'window_reason': window_status['reason'],
                'rule_state': rule_result['state'],
                'active_matches': window_status.get('active_matches', []),
                'upcoming_matches': window_status.get('upcoming_matches', [])
            })
        }

    except Exception as e:
        print(f"Schedule Manager error: {str(e)}")
        if NEW_RELIC_ENABLED:
            newrelic.agent.record_exception()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        }


def parse_ics_schedule(s3_bucket: str) -> List[Dict[str, Any]]:
    """
    Parse ICS feed to extract all EPL matches (for window evaluation).

    Args:
        s3_bucket: S3 bucket for ICS caching

    Returns:
        List of match dictionaries with timing and metadata
    """
    matches = []

    try:
        # Get ICS content
        ics_content = get_ics_content(s3_bucket)

        # Parse calendar
        cal = icalendar.Calendar.from_ical(ics_content)
        london_tz = zoneinfo.ZoneInfo('Europe/London')
        now = datetime.now(london_tz)

        # Look ahead 24 hours (enough to check for upcoming matches)
        # Look back 3 hours (enough to check for recently ended matches)
        window_start = now - timedelta(hours=3)
        window_end = now + timedelta(hours=24)

        print(f"Searching for matches between {window_start.strftime('%Y-%m-%d %H:%M %Z')} and {window_end.strftime('%Y-%m-%d %H:%M %Z')}")

        for component in cal.walk():
            if component.name == "VEVENT":
                start_time = component.get('dtstart').dt
                if isinstance(start_time, datetime):
                    start_time = start_time.astimezone(london_tz)

                    # Only include matches in our search window
                    if window_start <= start_time <= window_end:
                        match_summary = component.get('summary', 'Unknown Match')

                        # Filter out non-match events (awards, announcements, etc.)
                        # Real matches start with ⚽️ emoji
                        if not str(match_summary).startswith('⚽️'):
                            print(f"Skipping non-match event: {match_summary}")
                            continue

                        # Calculate match window: 15min before to 2.5 hours after kickoff
                        match_window_start = start_time - timedelta(minutes=15)
                        match_window_end = start_time + timedelta(hours=2, minutes=30)

                        match_info = {
                            'summary': str(match_summary),
                            'start_time': start_time.isoformat(),
                            'window_start': match_window_start.isoformat(),
                            'window_end': match_window_end.isoformat(),
                            'match_date': start_time.strftime('%Y-%m-%d')
                        }

                        matches.append(match_info)
                        print(f"Match found: {match_summary} at {start_time.strftime('%Y-%m-%d %H:%M %Z')}")

        # Sort by start time
        matches.sort(key=lambda x: x['start_time'])

        print(f"Total matches found: {len(matches)}")
        return matches

    except Exception as e:
        print(f"Error parsing ICS schedule: {e}")
        return []


def evaluate_match_window(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluate if we're currently in a match window that requires 2-minute polling.

    Enable polling if:
    - Any match starts in next 15 minutes, OR
    - Any match is currently active (between window_start and window_end)

    Args:
        matches: List of match dictionaries from parse_ics_schedule

    Returns:
        Dict with 'is_active' bool, 'reason' string, and lists of active/upcoming matches
    """
    london_tz = zoneinfo.ZoneInfo('Europe/London')
    now = datetime.now(london_tz)

    active_matches = []
    upcoming_matches = []

    for match in matches:
        start_time = datetime.fromisoformat(match['start_time'])
        window_start = datetime.fromisoformat(match['window_start'])
        window_end = datetime.fromisoformat(match['window_end'])

        # Check if match is currently active (we're in the match window)
        if window_start <= now <= window_end:
            active_matches.append({
                'summary': match['summary'],
                'start_time': match['start_time'],
                'status': 'active'
            })

        # Check if match starts in next 15 minutes
        time_until_start = (start_time - now).total_seconds() / 60
        if 0 <= time_until_start <= 15:
            upcoming_matches.append({
                'summary': match['summary'],
                'start_time': match['start_time'],
                'minutes_until_start': round(time_until_start, 1)
            })

    # Determine if window is active
    if active_matches:
        return {
            'is_active': True,
            'reason': f'{len(active_matches)} active match(es): {", ".join(m["summary"] for m in active_matches)}',
            'active_matches': active_matches,
            'upcoming_matches': upcoming_matches
        }
    elif upcoming_matches:
        return {
            'is_active': True,
            'reason': f'{len(upcoming_matches)} match(es) starting in next 15 min: {", ".join(m["summary"] for m in upcoming_matches)}',
            'active_matches': active_matches,
            'upcoming_matches': upcoming_matches
        }
    else:
        return {
            'is_active': False,
            'reason': 'No active or upcoming matches in next 15 minutes',
            'active_matches': [],
            'upcoming_matches': []
        }


def get_ics_content(s3_bucket: str) -> bytes:
    """
    Get ICS content from S3 cache or fetch fresh from source.

    Cache duration: 29 hours (creates daily rotation with some overlap)
    Rationale: EPL fixture schedules change at least a week in advance
    """
    try:
        # Try S3 cache first
        response = s3.get_object(Bucket=s3_bucket, Key='epl_fixtures.ics')
        last_modified = response['LastModified']
        now = datetime.now(timezone.utc)

        # Use cache if less than 29 hours old (104400 seconds)
        if (now - last_modified.replace(tzinfo=timezone.utc)).total_seconds() < 104400:
            print("Using cached ICS data from S3")
            return response['Body'].read()
        else:
            print("Cached ICS data is stale (>29h old), fetching fresh")
    except Exception as cache_error:
        print(f"Could not retrieve cached ICS: {cache_error}")

    # Fetch fresh ICS data
    print("Fetching fresh ICS data from source")
    ics_url = "https://ics.ecal.com/ecal-sub/68a47e3ff49aba000867f867/English%20Premier%20League.ics"
    response = requests.get(ics_url, timeout=30)
    response.raise_for_status()

    ics_content = response.content

    # Update S3 cache
    s3.put_object(
        Bucket=s3_bucket,
        Key='epl_fixtures.ics',
        Body=ics_content,
        ContentType='text/calendar'
    )
    print("Updated S3 cache with fresh ICS data")

    return ics_content




def manage_polling_rule(window_status: Dict[str, Any], matches: List[Dict[str, Any]], environment: str) -> Dict[str, Any]:
    """
    Enable or disable the 2-minute polling rule based on match window status.

    Args:
        window_status: Result from evaluate_match_window
        matches: List of all matches for context
        environment: 'dev' or 'prod'

    Returns:
        Dict with rule state and details
    """
    try:
        rule_name = f"epl-live-match-monitor-{environment}"
        recurring_cron = "cron(*/2 * * * ? *)"  # Every 2 minutes

        # Determine rule state based on window status
        if window_status['is_active']:
            rule_state = 'ENABLED'
            description = f"EPL Live Match Monitor - ENABLED: {window_status['reason']}"
            print(f"🟢 Enabling 2-minute polling rule")
            print(f"   Reason: {window_status['reason']}")
        else:
            rule_state = 'DISABLED'
            description = f"EPL Live Match Monitor - DISABLED: {window_status['reason']}"
            print(f"🔴 Disabling 2-minute polling rule")
            print(f"   Reason: {window_status['reason']}")

        # Create/update EventBridge rule
        rule_response = events.put_rule(
            Name=rule_name,
            ScheduleExpression=recurring_cron,
            Description=description,
            State=rule_state
        )

        # Add target (LiveMatchFetcher function)
        live_fetcher_arn = f"arn:aws:lambda:{region}:{get_account_id()}:function:epl-live-fetcher-{environment}"

        # Create input payload with match context
        input_payload = {
            'source': 'schedule-manager',
            'dynamic_scheduling': True,
            'window_active': window_status['is_active'],
            'active_matches': window_status.get('active_matches', []),
            'upcoming_matches': window_status.get('upcoming_matches', []),
            'match_info': {
                'summary': window_status['reason'],
                'window_status': 'active' if window_status['is_active'] else 'inactive'
            }
        }

        events.put_targets(
            Rule=rule_name,
            Targets=[{
                'Id': '1',
                'Arn': live_fetcher_arn,
                'Input': json.dumps(input_payload)
            }]
        )

        print(f"✅ Successfully {'enabled' if rule_state == 'ENABLED' else 'disabled'} rule: {rule_name}")

        return {
            'state': rule_state,
            'rule_name': rule_name,
            'rule_arn': rule_response['RuleArn'],
            'reason': window_status['reason']
        }

    except Exception as e:
        print(f"❌ Error managing polling rule: {e}")
        return {
            'state': 'ERROR',
            'error': str(e)
        }




def store_schedule_state(table, schedule_state: Dict[str, Any]) -> None:
    """
    Store schedule state in DynamoDB for monitoring and debugging.
    """
    try:
        timestamp = datetime.now(timezone.utc)

        table.put_item(
            Item={
                'schedule_id': 'latest',
                'timestamp': int(timestamp.timestamp()),
                'match_date': timestamp.strftime('%Y-%m-%d'),
                'schedule_state': schedule_state,
                'last_updated': timestamp.isoformat(),
                'ttl': int((timestamp + timedelta(days=7)).timestamp())  # Keep for 7 days
            }
        )

        print("Schedule state stored successfully")

    except Exception as e:
        print(f"Error storing schedule state: {e}")
        # Don't fail the entire function if storage fails


def get_account_id() -> str:
    """Get current AWS account ID."""
    try:
        return boto3.client('sts').get_caller_identity()['Account']
    except:
        return '000000000000'  # Fallback for local testing