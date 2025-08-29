import json
import os
import boto3
from datetime import datetime, timezone
from typing import Dict, Any
from decimal import Decimal

# New Relic monitoring
try:
    import newrelic.agent
    print(f"New Relic version: {newrelic.version}")
    # Initialize if environment variables are set
    if os.environ.get('NEW_RELIC_LICENSE_KEY'):
        license_key = os.environ.get('NEW_RELIC_LICENSE_KEY', 'Not Set')
        app_name = os.environ.get('NEW_RELIC_APP_NAME', 'Not Set')
        account_id = os.environ.get('NEW_RELIC_ACCOUNT_ID', 'Not Set')
        print(f"New Relic License Key (first 8): {license_key[:8]}")
        print(f"New Relic App Name: {app_name}")
        print(f"New Relic Account ID: {account_id}")
        
        newrelic.agent.initialize()
        print("New Relic agent initialized successfully")
        NEW_RELIC_ENABLED = True
    else:
        print("New Relic license key not found")
        NEW_RELIC_ENABLED = False
except ImportError as e:
    print(f"New Relic import failed: {e}")
    NEW_RELIC_ENABLED = False
except Exception as e:
    print(f"New Relic initialization failed: {e}")
    NEW_RELIC_ENABLED = False

print(f"New Relic enabled: {NEW_RELIC_ENABLED}")

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
    if NEW_RELIC_ENABLED:
        print("New Relic transaction starting...")
        
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

def get_cors_headers():
    """
    Get CORS headers for API responses
    """
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Content-Type': 'application/json'
    }