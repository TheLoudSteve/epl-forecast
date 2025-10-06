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
from forecast_calculator import calculate_forecasts

# Use the region from environment or default to us-east-1 for backward compatibility
region = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=region)
cloudwatch = boto3.client('cloudwatch', region_name=region)

def lambda_handler(event, context):
    """
    Lambda function to fetch EPL data on schedule (1x daily at 00:00 UTC)
    This ensures fresh data is always available and prevents DynamoDB TTL expiration
    """
    try:
        print(f"Scheduled data fetch triggered with event: {event}")
        
        table_name = os.environ['DYNAMODB_TABLE']
        football_data_api_key = os.environ['FOOTBALL_DATA_API_KEY']

        print(f"Environment variables - Table: {table_name}")

        table = dynamodb.Table(table_name)

        print("Starting scheduled data fetch...")

        # Fetch current EPL table
        epl_data = fetch_epl_data(football_data_api_key)
        print(f"Fetched EPL data with {len(epl_data.get('table', []))} teams")
        
        # Calculate forecasts
        forecast_data = calculate_forecasts(epl_data, update_type='scheduled')
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

    environment = os.environ.get('ENVIRONMENT', 'unknown')
    start_time = datetime.now(timezone.utc)
    response = requests.get(url, headers=headers, timeout=30)
    end_time = datetime.now(timezone.utc)
    response_time_ms = (end_time - start_time).total_seconds() * 1000

    print(f"API Response Status: {response.status_code}")
    print(f"API Response Time: {response_time_ms:.2f}ms")
    print(f"API Response Headers: {dict(response.headers)}")

    # Publish CloudWatch metrics
    try:
        cloudwatch.put_metric_data(
            Namespace='EPLForecast/FootballAPI',
            MetricData=[
                {
                    'MetricName': 'APICallCount',
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': end_time,
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': environment},
                        {'Name': 'StatusCode', 'Value': str(response.status_code)},
                        {'Name': 'CallReason', 'Value': 'scheduled_update'}
                    ]
                },
                {
                    'MetricName': 'APIResponseTime',
                    'Value': response_time_ms,
                    'Unit': 'Milliseconds',
                    'Timestamp': end_time,
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': environment},
                        {'Name': 'StatusCode', 'Value': str(response.status_code)}
                    ]
                }
            ]
        )
        print(f"Published CloudWatch metrics: status={response.status_code}, time={response_time_ms:.2f}ms")
    except Exception as e:
        print(f"Failed to publish CloudWatch metrics: {e}")

    response.raise_for_status()

    data = response.json()
    print(f"API Response Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
    print(f"API Response sample: {str(data)[:500]}...")

    return data
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