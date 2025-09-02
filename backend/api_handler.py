import json
import os
import boto3
from datetime import datetime, timezone
from typing import Dict, Any
from decimal import Decimal
from models import UserNotificationPreferences, NotificationTiming, NotificationSensitivity, EPL_TEAMS
from notification_logic import notification_manager
from notification_content_generator import notification_content_generator
from notification_rate_limiter import notification_rate_limiter

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

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

@newrelic.agent.lambda_handler() if NEW_RELIC_ENABLED else lambda x: x
def lambda_handler(event, context):
    """
    Lambda function to handle API requests
    """
    print("=== LAMBDA HANDLER CALLED ===")
    print(f"NEW_RELIC_ENABLED value: {NEW_RELIC_ENABLED}")
    print(f"NEW_RELIC_LICENSE_KEY env var: {'SET' if os.environ.get('NEW_RELIC_LICENSE_KEY') else 'NOT SET'}")
    
    # Debug New Relic transaction capture
    if NEW_RELIC_ENABLED:
        print("NEW_RELIC_ENABLED is True, attempting manual transaction creation...")
        try:
            application = newrelic.agent.application()
            print(f"New Relic application object: {application}")
            print(f"Application active: {application.active}")
            
            # Force a custom event to test connection
            newrelic.agent.record_custom_event('APIHandlerInvocation', {
                'path': event.get('path', 'unknown'),
                'httpMethod': event.get('httpMethod', 'unknown'),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            print("Custom event recorded successfully")
            
            # Test if the decorator is being applied correctly
            print(f"Lambda handler function name: {lambda_handler.__name__}")
            print(f"Lambda handler function: {lambda_handler}")
            
        except Exception as e:
            print(f"Error with New Relic transaction setup: {e}")
    else:
        print("NEW_RELIC_ENABLED is False - this explains why no transactions are captured!")
    print(f"Event keys: {list(event.keys()) if event else 'None'}")
    print(f"Context: {type(context)}")
    
    try:
        path = event.get('path', '')
        http_method = event.get('httpMethod', '')
        
        # Add New Relic custom attributes
        if NEW_RELIC_ENABLED:
            newrelic.agent.add_custom_attribute('api.path', path)
            newrelic.agent.add_custom_attribute('api.method', http_method)
            newrelic.agent.add_custom_attribute('lambda.environment', os.environ.get('ENVIRONMENT', 'unknown'))
        
        if path == '/health' and http_method == 'GET':
            return handle_health_check()
        elif path == '/table' and http_method == 'GET':
            return handle_table_request()
        elif path == '/debug' and http_method == 'GET':
            return handle_debug_request()
        elif path == '/preferences' and http_method == 'GET':
            return handle_get_preferences(event)
        elif path == '/preferences' and http_method in ['POST', 'PUT']:
            return handle_update_preferences(event)
        elif path == '/preferences/register' and http_method == 'POST':
            return handle_register_push_token(event)
        elif path == '/preferences/test' and http_method == 'POST':
            return handle_test_notification(event)
        elif path == '/preferences/preview' and http_method == 'GET':
            return handle_notification_preview(event)
        elif path == '/preferences/stats' and http_method == 'GET':
            return handle_notification_stats(event)
        else:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Not found'}, cls=DecimalEncoder)
            }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': 'Internal server error',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }, cls=DecimalEncoder)
        }

def handle_health_check():
    """
    Health check endpoint
    """
    return {
        'statusCode': 200,
        'headers': get_cors_headers(),
        'body': json.dumps({
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'service': 'epl-forecast-api'
        }, cls=DecimalEncoder)
    }

def handle_table_request():
    """
    Get forecasted EPL table
    """
    table_name = os.environ['DYNAMODB_TABLE']
    table = dynamodb.Table(table_name)
    
    try:
        print(f"Querying DynamoDB table: {table_name}")
        # Get current forecast data
        response = table.get_item(Key={'id': 'current_forecast'})
        print(f"DynamoDB response: {response}")
        
        if 'Item' not in response:
            print("No item found in DynamoDB with key 'current_forecast'")
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'error': 'No forecast data available',
                    'message': 'Data may still be loading. Please try again in a few minutes.'
                }, cls=DecimalEncoder)
            }
        
        forecast_data = response['Item']['data']
        print(f"Forecast data keys: {list(forecast_data.keys())}")
        print(f"Number of teams in forecast: {len(forecast_data.get('teams', []))}")
        
        # Add API metadata (DecimalEncoder will handle Decimal conversion automatically)
        api_response = {
            'forecast_table': forecast_data.get('teams', []),
            'metadata': {
                'last_updated': forecast_data['last_updated'],
                'total_teams': forecast_data['total_teams'],
                'api_version': '1.0',
                'description': 'EPL table forecasted to 38 games based on current points per game'
            }
        }
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(api_response, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"Database error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': 'Failed to retrieve data',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }, cls=DecimalEncoder)
        }

def handle_debug_request():
    """
    Debug endpoint to check DynamoDB contents
    """
    table_name = os.environ['DYNAMODB_TABLE']
    table = dynamodb.Table(table_name)
    
    try:
        # Get current forecast data
        response = table.get_item(Key={'id': 'current_forecast'})
        
        debug_info = {
            'table_name': table_name,
            'item_exists': 'Item' in response,
            'response_keys': list(response.keys()),
            'raw_response': str(response)[:1000] + '...' if len(str(response)) > 1000 else str(response)
        }
        
        if 'Item' in response:
            debug_info['item_keys'] = list(response['Item'].keys())
            if 'data' in response['Item']:
                debug_info['data_keys'] = list(response['Item']['data'].keys())
                if 'teams' in response['Item']['data']:
                    debug_info['teams_count'] = len(response['Item']['data']['teams'])
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(debug_info, indent=2, cls=DecimalEncoder)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': f'Debug error: {str(e)}',
                'table_name': table_name
            }, cls=DecimalEncoder)
        }

def handle_get_preferences(event: Dict[str, Any]):
    """
    Get user notification preferences
    """
    user_id = get_user_id_from_event(event)
    if not user_id:
        return {
            'statusCode': 400,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'User ID required in X-User-ID header'}, cls=DecimalEncoder)
        }
    
    preferences_table_name = os.environ['USER_PREFERENCES_TABLE']
    preferences_table = dynamodb.Table(preferences_table_name)
    
    try:
        response = preferences_table.get_item(Key={'user_id': user_id})
        
        if 'Item' in response:
            # Convert DynamoDB item back to preferences object
            preferences = UserNotificationPreferences.from_dynamodb_item(response['Item'])
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'preferences': preferences.to_dynamodb_item(),
                    'available_teams': EPL_TEAMS
                }, cls=DecimalEncoder)
            }
        else:
            # Return default preferences
            default_preferences = UserNotificationPreferences(
                user_id=user_id,
                team_name="Arsenal"  # Default team
            )
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'preferences': default_preferences.to_dynamodb_item(),
                    'available_teams': EPL_TEAMS,
                    'is_default': True
                }, cls=DecimalEncoder)
            }
            
    except Exception as e:
        print(f"Error getting preferences: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Failed to retrieve preferences'}, cls=DecimalEncoder)
        }

def handle_update_preferences(event: Dict[str, Any]):
    """
    Update user notification preferences
    """
    user_id = get_user_id_from_event(event)
    if not user_id:
        return {
            'statusCode': 400,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'User ID required in X-User-ID header'}, cls=DecimalEncoder)
        }
    
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Invalid JSON in request body'}, cls=DecimalEncoder)
        }
    
    # Validate team name
    team_name = body.get('team_name', '')
    if team_name and team_name not in EPL_TEAMS:
        return {
            'statusCode': 400,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': f'Invalid team name. Must be one of: {", ".join(EPL_TEAMS)}'
            }, cls=DecimalEncoder)
        }
    
    # Validate notification timing
    timing = body.get('notification_timing', 'immediate')
    try:
        notification_timing = NotificationTiming(timing)
    except ValueError:
        return {
            'statusCode': 400,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': f'Invalid notification timing. Must be one of: {[t.value for t in NotificationTiming]}'
            }, cls=DecimalEncoder)
        }
    
    # Validate notification sensitivity
    sensitivity = body.get('notification_sensitivity', 'any_change')
    try:
        notification_sensitivity = NotificationSensitivity(sensitivity)
    except ValueError:
        return {
            'statusCode': 400,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': f'Invalid notification sensitivity. Must be one of: {[s.value for s in NotificationSensitivity]}'
            }, cls=DecimalEncoder)
        }
    
    # Create preferences object
    preferences = UserNotificationPreferences(
        user_id=user_id,
        team_name=team_name,
        enabled=body.get('enabled', True),
        notification_timing=notification_timing,
        notification_sensitivity=notification_sensitivity,
        push_token=body.get('push_token'),
        email_address=body.get('email_address'),
        email_notifications_enabled=body.get('email_notifications_enabled', False)
    )
    
    # Save to DynamoDB
    preferences_table_name = os.environ['USER_PREFERENCES_TABLE']
    preferences_table = dynamodb.Table(preferences_table_name)
    
    try:
        preferences_table.put_item(Item=preferences.to_dynamodb_item())
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'message': 'Preferences updated successfully',
                'preferences': preferences.to_dynamodb_item()
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"Error saving preferences: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Failed to save preferences'}, cls=DecimalEncoder)
        }

def handle_register_push_token(event: Dict[str, Any]):
    """
    Register or update push notification token
    """
    user_id = get_user_id_from_event(event)
    if not user_id:
        return {
            'statusCode': 400,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'User ID required in X-User-ID header'}, cls=DecimalEncoder)
        }
    
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Invalid JSON in request body'}, cls=DecimalEncoder)
        }
    
    push_token = body.get('push_token', '')
    if not push_token:
        return {
            'statusCode': 400,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'push_token required in request body'}, cls=DecimalEncoder)
        }
    
    preferences_table_name = os.environ['USER_PREFERENCES_TABLE']
    preferences_table = dynamodb.Table(preferences_table_name)
    
    try:
        # Get existing preferences or create default
        response = preferences_table.get_item(Key={'user_id': user_id})
        
        if 'Item' in response:
            preferences = UserNotificationPreferences.from_dynamodb_item(response['Item'])
        else:
            preferences = UserNotificationPreferences(
                user_id=user_id,
                team_name="Arsenal"  # Default team
            )
        
        # Update push token
        preferences.push_token = push_token
        
        # Save updated preferences
        preferences_table.put_item(Item=preferences.to_dynamodb_item())
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'message': 'Push token registered successfully',
                'user_id': user_id
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"Error registering push token: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Failed to register push token'}, cls=DecimalEncoder)
        }

def handle_test_notification(event: Dict[str, Any]):
    """
    Send a test notification to verify setup
    """
    user_id = get_user_id_from_event(event)
    if not user_id:
        return {
            'statusCode': 400,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'User ID required in X-User-ID header'}, cls=DecimalEncoder)
        }
    
    try:
        result = notification_manager.send_test_notification(user_id)
        
        if 'error' in result:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps(result, cls=DecimalEncoder)
            }
        else:
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps(result, cls=DecimalEncoder)
            }
            
    except Exception as e:
        print(f"Error sending test notification: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': 'Failed to send test notification',
                'details': str(e)
            }, cls=DecimalEncoder)
        }

def handle_notification_preview(event: Dict[str, Any]):
    """
    Get preview notifications for different scenarios
    """
    user_id = get_user_id_from_event(event)
    if not user_id:
        return {
            'statusCode': 400,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'User ID required in X-User-ID header'}, cls=DecimalEncoder)
        }
    
    preferences_table_name = os.environ['USER_PREFERENCES_TABLE']
    preferences_table = dynamodb.Table(preferences_table_name)
    
    try:
        # Get user preferences
        response = preferences_table.get_item(Key={'user_id': user_id})
        
        if 'Item' in response:
            preferences = UserNotificationPreferences.from_dynamodb_item(response['Item'])
        else:
            # Use default preferences for preview
            preferences = UserNotificationPreferences(
                user_id=user_id,
                team_name="Arsenal"  # Default team
            )
        
        # Define preview scenarios
        scenarios = [
            {
                'name': 'Title Position',
                'previous_position': 2,
                'new_position': 1,
                'context': 'Manchester City vs Liverpool result'
            },
            {
                'name': 'Champions League Entry',
                'previous_position': 5,
                'new_position': 4,
                'context': 'Tottenham vs Chelsea result'
            },
            {
                'name': 'Relegation Danger',
                'previous_position': 17,
                'new_position': 18,
                'context': 'Burnley vs Sheffield United result'
            },
            {
                'name': 'Escaping Relegation',
                'previous_position': 19,
                'new_position': 17,
                'context': 'crucial win against relegation rivals'
            },
            {
                'name': 'Minor Improvement',
                'previous_position': 8,
                'new_position': 7,
                'context': 'improved goal difference'
            }
        ]
        
        # Generate preview notifications
        previews = notification_content_generator.get_notification_preview(
            preferences, scenarios
        )
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'user_id': user_id,
                'team_name': preferences.team_name,
                'notification_settings': {
                    'timing': preferences.notification_timing.value,
                    'sensitivity': preferences.notification_sensitivity.value,
                    'enabled': preferences.enabled
                },
                'previews': previews
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"Error generating notification preview: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': 'Failed to generate notification preview',
                'details': str(e)
            }, cls=DecimalEncoder)
        }

def handle_notification_stats(event: Dict[str, Any]):
    """
    Get notification statistics and rate limiting info for a user
    """
    user_id = get_user_id_from_event(event)
    if not user_id:
        return {
            'statusCode': 400,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'User ID required in X-User-ID header'}, cls=DecimalEncoder)
        }
    
    try:
        # Get notification statistics
        stats = notification_rate_limiter.get_user_notification_stats(user_id)
        
        # Add current time for client reference
        stats['current_time'] = int(datetime.now(timezone.utc).timestamp())
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(stats, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"Error getting notification stats: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': 'Failed to get notification statistics',
                'details': str(e)
            }, cls=DecimalEncoder)
        }

def get_user_id_from_event(event: Dict[str, Any]) -> str:
    """
    Extract user ID from event headers
    """
    headers = event.get('headers', {})
    # Check both X-User-ID and x-user-id (case insensitive)
    for key, value in headers.items():
        if key.lower() == 'x-user-id':
            return value
    return ''

def get_cors_headers():
    """
    Get CORS headers for API responses
    """
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-User-ID',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, OPTIONS',
        'Content-Type': 'application/json'
    }