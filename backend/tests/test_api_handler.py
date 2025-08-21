import pytest
import json
from unittest.mock import Mock, patch
import boto3
from moto import mock_dynamodb
import api_handler

@mock_dynamodb
class TestAPIHandler:
    
    def setup_method(self):
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Create test table
        self.table = self.dynamodb.create_table(
            TableName='test-table',
            KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
    
    @patch.dict('os.environ', {'DYNAMODB_TABLE': 'test-table'})
    def test_handle_health_check(self):
        result = api_handler.handle_health_check()
        
        assert result['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in result['headers']
        
        body = json.loads(result['body'])
        assert body['status'] == 'healthy'
        assert 'timestamp' in body
        assert body['service'] == 'epl-forecast-api'
    
    @patch.dict('os.environ', {'DYNAMODB_TABLE': 'test-table'})
    def test_handle_table_request_success(self):
        # Insert test data
        test_data = {
            'teams': [
                {
                    'name': 'Arsenal',
                    'forecasted_points': 95.0,
                    'points_per_game': 2.5,
                    'forecasted_position': 1
                }
            ],
            'last_updated': '2024-01-01T00:00:00Z',
            'total_teams': 1
        }
        
        self.table.put_item(
            Item={
                'id': 'current_forecast',
                'data': test_data,
                'ttl': 1234567890
            }
        )
        
        result = api_handler.handle_table_request()
        
        assert result['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in result['headers']
        
        body = json.loads(result['body'])
        assert 'forecast_table' in body
        assert 'metadata' in body
        assert len(body['forecast_table']) == 1
        assert body['forecast_table'][0]['name'] == 'Arsenal'
        assert body['metadata']['total_teams'] == 1
    
    @patch.dict('os.environ', {'DYNAMODB_TABLE': 'test-table'})
    def test_handle_table_request_no_data(self):
        result = api_handler.handle_table_request()
        
        assert result['statusCode'] == 404
        assert 'Access-Control-Allow-Origin' in result['headers']
        
        body = json.loads(result['body'])
        assert 'No forecast data available' in body['error']
    
    def test_get_cors_headers(self):
        headers = api_handler.get_cors_headers()
        
        assert headers['Access-Control-Allow-Origin'] == '*'
        assert headers['Access-Control-Allow-Headers'] == 'Content-Type'
        assert headers['Access-Control-Allow-Methods'] == 'GET, OPTIONS'
        assert headers['Content-Type'] == 'application/json'
    
    @patch.dict('os.environ', {'DYNAMODB_TABLE': 'test-table'})
    def test_lambda_handler_health_endpoint(self):
        event = {
            'path': '/health',
            'httpMethod': 'GET'
        }
        context = {}
        
        result = api_handler.lambda_handler(event, context)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['status'] == 'healthy'
    
    @patch.dict('os.environ', {'DYNAMODB_TABLE': 'test-table'})
    def test_lambda_handler_table_endpoint(self):
        # Insert test data
        test_data = {
            'teams': [{'name': 'Arsenal', 'forecasted_points': 95.0}],
            'last_updated': '2024-01-01T00:00:00Z',
            'total_teams': 1
        }
        
        self.table.put_item(
            Item={
                'id': 'current_forecast',
                'data': test_data,
                'ttl': 1234567890
            }
        )
        
        event = {
            'path': '/table',
            'httpMethod': 'GET'
        }
        context = {}
        
        result = api_handler.lambda_handler(event, context)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert 'forecast_table' in body
    
    @patch.dict('os.environ', {'DYNAMODB_TABLE': 'test-table'})
    def test_lambda_handler_not_found(self):
        event = {
            'path': '/unknown',
            'httpMethod': 'GET'
        }
        context = {}
        
        result = api_handler.lambda_handler(event, context)
        
        assert result['statusCode'] == 404
        body = json.loads(result['body'])
        assert body['error'] == 'Not found'
    
    @patch.dict('os.environ', {'DYNAMODB_TABLE': 'test-table'})
    @patch('api_handler.handle_table_request')
    def test_lambda_handler_internal_error(self, mock_handler):
        mock_handler.side_effect = Exception("Database error")
        
        event = {
            'path': '/table',
            'httpMethod': 'GET'
        }
        context = {}
        
        result = api_handler.lambda_handler(event, context)
        
        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert 'Internal server error' in body['error']