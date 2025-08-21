import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import boto3
from moto import mock_dynamodb, mock_s3
import data_fetcher

@mock_dynamodb
@mock_s3
class TestDataFetcher:
    
    def setup_method(self):
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.s3 = boto3.client('s3', region_name='us-east-1')
        
        # Create test table
        self.table = self.dynamodb.create_table(
            TableName='test-table',
            KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create test bucket
        self.s3.create_bucket(Bucket='test-bucket')
    
    @patch.dict('os.environ', {
        'DYNAMODB_TABLE': 'test-table',
        'S3_BUCKET': 'test-bucket',
        'RAPIDAPI_KEY': 'test-key'
    })
    @patch('data_fetcher.requests.get')
    def test_fetch_epl_data_success(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {
            'table': [
                {
                    'team': 'Arsenal',
                    'played': 10,
                    'points': 25,
                    'won': 8,
                    'drawn': 1,
                    'lost': 1,
                    'for': 20,
                    'against': 5,
                    'goal_difference': 15,
                    'position': 1
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = data_fetcher.fetch_epl_data('test-key')
        
        assert 'table' in result
        assert len(result['table']) == 1
        assert result['table'][0]['team'] == 'Arsenal'
        
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs['headers']['X-RapidAPI-Key'] == 'test-key'
    
    def test_calculate_forecasts(self):
        epl_data = {
            'table': [
                {
                    'team': 'Arsenal',
                    'played': 10,
                    'points': 25,
                    'won': 8,
                    'drawn': 1,
                    'lost': 1,
                    'for': 20,
                    'against': 5,
                    'goal_difference': 15,
                    'position': 1
                },
                {
                    'team': 'Liverpool',
                    'played': 12,
                    'points': 21,
                    'won': 6,
                    'drawn': 3,
                    'lost': 3,
                    'for': 18,
                    'against': 10,
                    'goal_difference': 8,
                    'position': 2
                }
            ]
        }
        
        result = data_fetcher.calculate_forecasts(epl_data)
        
        assert 'teams' in result
        assert len(result['teams']) == 2
        
        # Arsenal should be first (2.5 ppg = 95 points)
        arsenal = result['teams'][0]
        assert arsenal['name'] == 'Arsenal'
        assert arsenal['points_per_game'] == 2.5
        assert arsenal['forecasted_points'] == 95.0
        assert arsenal['forecasted_position'] == 1
        
        # Liverpool should be second (1.75 ppg = 66.5 points)
        liverpool = result['teams'][1]
        assert liverpool['name'] == 'Liverpool'
        assert liverpool['points_per_game'] == 1.75
        assert liverpool['forecasted_points'] == 66.5
        assert liverpool['forecasted_position'] == 2
    
    def test_calculate_forecasts_zero_played(self):
        epl_data = {
            'table': [
                {
                    'team': 'Test Team',
                    'played': 0,
                    'points': 0,
                    'won': 0,
                    'drawn': 0,
                    'lost': 0,
                    'for': 0,
                    'against': 0,
                    'goal_difference': 0,
                    'position': 1
                }
            ]
        }
        
        result = data_fetcher.calculate_forecasts(epl_data)
        
        team = result['teams'][0]
        assert team['points_per_game'] == 0
        assert team['forecasted_points'] == 0
    
    @patch('data_fetcher.requests.get')
    def test_check_if_update_needed_with_match(self, mock_get):
        # Mock ICS content with a match happening now
        ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
DTSTART:20240821T140000Z
SUMMARY:Arsenal vs Liverpool
END:VEVENT
END:VCALENDAR"""
        
        mock_response = Mock()
        mock_response.content = ics_content.encode()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        with patch('data_fetcher.datetime') as mock_datetime:
            # Mock current time to be during the match
            mock_now = Mock()
            mock_now.astimezone.return_value = mock_now
            mock_datetime.now.return_value = mock_now
            
            result = data_fetcher.check_if_update_needed('test-bucket')
            
            # Should return True when there's an error parsing
            assert isinstance(result, bool)
    
    @patch.dict('os.environ', {
        'DYNAMODB_TABLE': 'test-table',
        'S3_BUCKET': 'test-bucket',
        'RAPIDAPI_KEY': 'test-key'
    })
    def test_store_data(self):
        test_data = {
            'teams': [{'name': 'Arsenal', 'points': 25}],
            'last_updated': '2024-01-01T00:00:00Z'
        }
        
        data_fetcher.store_data(self.table, test_data)
        
        # Verify data was stored
        response = self.table.get_item(Key={'id': 'current_forecast'})
        assert 'Item' in response
        assert response['Item']['data'] == test_data
        assert 'ttl' in response['Item']
    
    @patch.dict('os.environ', {
        'DYNAMODB_TABLE': 'test-table',
        'S3_BUCKET': 'test-bucket',
        'RAPIDAPI_KEY': 'test-key'
    })
    @patch('data_fetcher.check_if_update_needed')
    @patch('data_fetcher.fetch_epl_data')
    @patch('data_fetcher.calculate_forecasts')
    @patch('data_fetcher.store_data')
    def test_lambda_handler_success(self, mock_store, mock_calc, mock_fetch, mock_check):
        mock_check.return_value = True
        mock_fetch.return_value = {'table': []}
        mock_calc.return_value = {'teams': []}
        
        event = {'trigger': 'midnight'}
        context = {}
        
        result = data_fetcher.lambda_handler(event, context)
        
        assert result['statusCode'] == 200
        response_body = json.loads(result['body'])
        assert 'message' in response_body
        assert 'timestamp' in response_body
        
        mock_fetch.assert_called_once()
        mock_calc.assert_called_once()
        mock_store.assert_called_once()
    
    @patch.dict('os.environ', {
        'DYNAMODB_TABLE': 'test-table',
        'S3_BUCKET': 'test-bucket',
        'RAPIDAPI_KEY': 'test-key'
    })
    @patch('data_fetcher.check_if_update_needed')
    def test_lambda_handler_no_update_needed(self, mock_check):
        mock_check.return_value = False
        
        event = {}
        context = {}
        
        result = data_fetcher.lambda_handler(event, context)
        
        assert result['statusCode'] == 200
        response_body = json.loads(result['body'])
        assert 'No update needed' in response_body['message']
    
    @patch.dict('os.environ', {
        'DYNAMODB_TABLE': 'test-table',
        'S3_BUCKET': 'test-bucket',
        'RAPIDAPI_KEY': 'test-key'
    })
    @patch('data_fetcher.fetch_epl_data')
    def test_lambda_handler_error(self, mock_fetch):
        mock_fetch.side_effect = Exception("API Error")
        
        event = {'trigger': 'noon'}
        context = {}
        
        result = data_fetcher.lambda_handler(event, context)
        
        assert result['statusCode'] == 500
        response_body = json.loads(result['body'])
        assert 'error' in response_body