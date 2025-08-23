import json
import os
import boto3
from datetime import datetime, timezone
from typing import Dict, Any

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

def lambda_handler(event, context):
    """
    Lambda function to handle API requests
    """
    try:
        path = event.get('path', '')
        http_method = event.get('httpMethod', '')
        
        if path == '/health' and http_method == 'GET':
            return handle_health_check()
        elif path == '/table' and http_method == 'GET':
            return handle_table_request()
        else:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Not found'})
            }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': 'Internal server error',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
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
        })
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
                })
            }
        
        forecast_data = response['Item']['data']
        
        # Add API metadata
        api_response = {
            'forecast_table': forecast_data['teams'],
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
            'body': json.dumps(api_response)
        }
        
    except Exception as e:
        print(f"Database error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': 'Failed to retrieve data',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
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