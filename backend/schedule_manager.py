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

@newrelic.agent.lambda_handler if NEW_RELIC_ENABLED else lambda x: x
def lambda_handler(event, context):
    """
    Schedule Manager Lambda function - Daily ICS parsing and EventBridge rule management

    This function is the core of the intelligent scheduling system that replaces
    constant polling (720 executions/day) with precise match-window scheduling.
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

        # Step 1: Parse ICS feed to extract upcoming matches
        print("🔍 Step 1: Parsing ICS feed for upcoming matches...")
        matches = parse_ics_schedule(s3_bucket)
        print(f"Found {len(matches)} upcoming matches in next 48 hours")

        # Step 2: Clean up old/expired EventBridge rules
        print("🧹 Step 2: Cleaning up expired EventBridge rules...")
        cleanup_result = cleanup_old_rules(environment)
        print(f"Cleanup result: {cleanup_result}")

        # Step 3: Create EventBridge rules for upcoming matches
        print("📅 Step 3: Creating EventBridge rules for match windows...")
        rules_created = create_match_rules(matches, environment)
        print(f"Created {len(rules_created)} EventBridge rules")

        # Step 4: Store schedule state in DynamoDB
        print("💾 Step 4: Storing schedule state...")
        schedule_state = {
            'matches_found': len(matches),
            'rules_created': len(rules_created),
            'rules_cleaned': cleanup_result.get('rules_deleted', 0),
            'matches': matches,
            'created_rules': rules_created
        }
        store_schedule_state(schedule_table, schedule_state)

        # Record metrics
        if NEW_RELIC_ENABLED:
            newrelic.agent.record_custom_metric('Custom/ScheduleManager/MatchesFound', len(matches))
            newrelic.agent.record_custom_metric('Custom/ScheduleManager/RulesCreated', len(rules_created))
            newrelic.agent.record_custom_metric('Custom/ScheduleManager/RulesDeleted', cleanup_result.get('rules_deleted', 0))

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Schedule Manager completed successfully',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'matches_found': len(matches),
                'rules_created': len(rules_created),
                'rules_cleaned': cleanup_result.get('rules_deleted', 0),
                'next_matches': [
                    {
                        'summary': match['summary'],
                        'start_time': match['start_time'],
                        'rule_name': match['rule_name']
                    }
                    for match in matches[:3]  # Show next 3 matches
                ]
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
    Parse ICS feed to extract upcoming EPL matches for next 48 hours.

    This replaces the constant ICS parsing that was happening every 2 minutes
    in live_match_fetcher with a single daily parse.

    Args:
        s3_bucket: S3 bucket for ICS caching

    Returns:
        List of match dictionaries with timing and metadata
    """
    matches = []

    try:
        # Get ICS content (similar to live_match_fetcher logic but simplified)
        ics_content = get_ics_content(s3_bucket)

        # Parse calendar
        cal = icalendar.Calendar.from_ical(ics_content)
        london_tz = zoneinfo.ZoneInfo('Europe/London')
        now = datetime.now(london_tz)

        # Look ahead 48 hours for upcoming matches
        window_end = now + timedelta(hours=48)

        print(f"Searching for matches between {now.strftime('%Y-%m-%d %H:%M %Z')} and {window_end.strftime('%Y-%m-%d %H:%M %Z')}")

        for component in cal.walk():
            if component.name == "VEVENT":
                start_time = component.get('dtstart').dt
                if isinstance(start_time, datetime):
                    start_time = start_time.astimezone(london_tz)

                    # Only include matches in our 48-hour window
                    if now <= start_time <= window_end:
                        match_summary = component.get('summary', 'Unknown Match')

                        # Calculate match window: 15min before to 2.5 hours after
                        window_start = start_time - timedelta(minutes=15)
                        window_end_match = start_time + timedelta(hours=2, minutes=30)

                        match_info = {
                            'summary': str(match_summary),
                            'start_time': start_time.isoformat(),
                            'window_start': window_start.isoformat(),
                            'window_end': window_end_match.isoformat(),
                            'rule_name': create_rule_name(match_summary, start_time),
                            'match_date': start_time.strftime('%Y-%m-%d')
                        }

                        matches.append(match_info)
                        print(f"Match found: {match_summary} at {start_time.strftime('%Y-%m-%d %H:%M %Z')}")

        # Sort by start time
        matches.sort(key=lambda x: x['start_time'])

        print(f"Total matches found in next 48 hours: {len(matches)}")
        return matches

    except Exception as e:
        print(f"Error parsing ICS schedule: {e}")
        # Don't fail completely - return empty list to allow cleanup to proceed
        return []


def get_ics_content(s3_bucket: str) -> bytes:
    """
    Get ICS content from S3 cache or fetch fresh from source.
    Similar to logic in live_match_fetcher but simplified.
    """
    try:
        # Try S3 cache first
        response = s3.get_object(Bucket=s3_bucket, Key='epl_fixtures.ics')
        last_modified = response['LastModified']
        now = datetime.now(timezone.utc)

        # Use cache if less than 6 hours old (fresher than live_match_fetcher's 29h)
        if (now - last_modified.replace(tzinfo=timezone.utc)).total_seconds() < 21600:
            print("Using cached ICS data from S3")
            return response['Body'].read()
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

    return ics_content


def create_rule_name(match_summary: str, start_time: datetime) -> str:
    """
    Create a consistent rule name for EventBridge rules.

    Format: epl-dynamic-match-YYYYMMDD-HHMM-{team-summary}
    """
    # Clean up match summary for rule name
    clean_summary = ''.join(c for c in str(match_summary) if c.isalnum() or c in ['-', ' '])
    clean_summary = clean_summary.replace(' ', '-').lower()[:30]  # Limit length

    time_str = start_time.strftime('%Y%m%d-%H%M')
    return f"epl-dynamic-match-{time_str}-{clean_summary}"


def create_match_rules(matches: List[Dict[str, Any]], environment: str) -> List[Dict[str, Any]]:
    """
    Create EventBridge rules for each upcoming match window.

    This is the core intelligence - creating precise scheduling instead of constant polling.
    """
    created_rules = []

    for match in matches:
        try:
            rule_name = match['rule_name']
            start_window = datetime.fromisoformat(match['window_start'])
            end_window = datetime.fromisoformat(match['window_end'])

            print(f"Creating rule: {rule_name}")
            print(f"  Match: {match['summary']}")
            print(f"  Window: {start_window.strftime('%Y-%m-%d %H:%M')} to {end_window.strftime('%H:%M')}")

            # Create EventBridge rule with cron expression for start time
            # We'll create a rule that triggers at the start of the match window
            # and the live_match_fetcher will handle the duration
            start_cron = create_cron_expression(start_window)

            rule_response = events.put_rule(
                Name=rule_name,
                ScheduleExpression=start_cron,
                Description=f"EPL Match: {match['summary']} - Auto-generated by Schedule Manager",
                State='ENABLED'
            )

            # Add target (LiveMatchFetcher function)
            live_fetcher_arn = f"arn:aws:lambda:{region}:{get_account_id()}:function:epl-live-fetcher-{environment}"

            events.put_targets(
                Rule=rule_name,
                Targets=[
                    {
                        'Id': '1',
                        'Arn': live_fetcher_arn,
                        'Input': json.dumps({
                            'source': 'schedule-manager',
                            'match_info': match,
                            'dynamic_scheduling': True
                        })
                    }
                ]
            )

            created_rule = {
                'rule_name': rule_name,
                'rule_arn': rule_response['RuleArn'],
                'match_summary': match['summary'],
                'start_time': match['start_time'],
                'cron_expression': start_cron
            }

            created_rules.append(created_rule)
            print(f"✅ Created rule: {rule_name}")

        except Exception as e:
            print(f"❌ Error creating rule for {match.get('summary', 'Unknown')}: {e}")
            continue

    return created_rules


def create_cron_expression(dt: datetime) -> str:
    """
    Create AWS EventBridge cron expression from datetime.

    Format: cron(minute hour day month ? year)
    """
    # Convert to UTC for EventBridge
    dt_utc = dt.astimezone(timezone.utc)
    return f"cron({dt_utc.minute} {dt_utc.hour} {dt_utc.day} {dt_utc.month} ? {dt_utc.year})"


def cleanup_old_rules(environment: str) -> Dict[str, Any]:
    """
    Clean up expired EventBridge rules to prevent accumulation.

    Removes rules that are more than 24 hours old.
    """
    try:
        # List all rules with our naming pattern
        response = events.list_rules(NamePrefix='epl-dynamic-match-')
        rules = response.get('Rules', [])

        deleted_count = 0
        errors = []

        for rule in rules:
            rule_name = rule['Name']

            try:
                # Extract date from rule name (format: epl-dynamic-match-YYYYMMDD-HHMM-...)
                parts = rule_name.split('-')
                if len(parts) >= 5:
                    date_str = parts[3]  # YYYYMMDD
                    time_str = parts[4]  # HHMM

                    # Parse rule date
                    rule_date = datetime.strptime(f"{date_str}-{time_str}", '%Y%m%d-%H%M')
                    rule_date = rule_date.replace(tzinfo=timezone.utc)

                    # Delete if more than 24 hours old
                    if (datetime.now(timezone.utc) - rule_date).total_seconds() > 86400:
                        print(f"Deleting expired rule: {rule_name}")

                        # Remove targets first
                        events.remove_targets(Rule=rule_name, Ids=['1'])

                        # Delete rule
                        events.delete_rule(Name=rule_name)
                        deleted_count += 1

            except Exception as rule_error:
                print(f"Error processing rule {rule_name}: {rule_error}")
                errors.append(str(rule_error))
                continue

        print(f"Cleanup complete: deleted {deleted_count} expired rules")

        return {
            'rules_deleted': deleted_count,
            'errors': errors,
            'total_rules_found': len(rules)
        }

    except Exception as e:
        print(f"Error during cleanup: {e}")
        return {
            'rules_deleted': 0,
            'errors': [str(e)],
            'total_rules_found': 0
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