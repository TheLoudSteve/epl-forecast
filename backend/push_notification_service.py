"""
Push notification service using AWS SNS and APNS for iOS notifications.
"""

import os
import boto3
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from models import UserNotificationPreferences, NotificationContent

# Initialize AWS services
region = os.environ.get('AWS_REGION', 'us-east-1')
sns = boto3.client('sns', region_name=region)


class PushNotificationService:
    """Manages push notifications via AWS SNS and APNS."""
    
    def __init__(self):
        self.sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
        self.apns_platform_arn = os.environ.get('APNS_PLATFORM_ARN')
        self.environment = os.environ.get('ENVIRONMENT', 'dev')
        
        print(f"PushNotificationService initialized:")
        print(f"  SNS Topic ARN: {self.sns_topic_arn}")
        print(f"  APNS Platform ARN: {self.apns_platform_arn}")
        print(f"  Environment: {self.environment}")
    
    def send_push_notification(self, preferences: UserNotificationPreferences, 
                             content: NotificationContent) -> Dict[str, Any]:
        """
        Send a push notification to a specific user.
        
        Args:
            preferences: User's notification preferences
            content: Notification content
            
        Returns:
            Result dictionary with success status and details
        """
        if not preferences.push_token:
            return {
                'success': False,
                'error': 'No push token available for user',
                'user_id': preferences.user_id
            }
        
        try:
            # Create or get SNS endpoint for the user's push token
            endpoint_result = self._create_or_get_endpoint(preferences.push_token, preferences.user_id)
            
            if not endpoint_result['success']:
                return endpoint_result
            
            endpoint_arn = endpoint_result['endpoint_arn']
            
            # Create platform-specific message payload
            message_payload = self._create_message_payload(content)
            
            # Send notification via SNS (or mock in dev mode)
            if endpoint_result.get('mock') and self.environment in ['dev', 'test']:
                # Mock successful SNS publish for development
                print(f"DEVELOPMENT MODE: Simulating push notification send to {preferences.user_id}")
                print(f"  Mock Endpoint: {endpoint_arn}")
                print(f"  Title: {content.title}")
                print(f"  Body: {content.body}")
                response = {
                    'MessageId': f'mock-message-{int(datetime.now(timezone.utc).timestamp())}'
                }
            else:
                response = sns.publish(
                    TargetArn=endpoint_arn,
                    Message=json.dumps(message_payload),
                    MessageStructure='json'
                )
            
            print(f"Push notification sent successfully to {preferences.user_id}")
            print(f"  Message ID: {response.get('MessageId')}")
            print(f"  Title: {content.title}")
            print(f"  Body: {content.body}")
            
            return {
                'success': True,
                'message_id': response.get('MessageId'),
                'user_id': preferences.user_id,
                'team_name': content.team_name,
                'notification_type': content.notification_type
            }
            
        except Exception as e:
            print(f"Error sending push notification to {preferences.user_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'user_id': preferences.user_id
            }
    
    def send_bulk_notifications(self, notifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Send multiple notifications efficiently.
        
        Args:
            notifications: List of dicts with 'preferences' and 'content' keys
            
        Returns:
            Summary of bulk send operation
        """
        results = {
            'total_sent': 0,
            'total_failed': 0,
            'successes': [],
            'failures': []
        }
        
        for notification in notifications:
            preferences = notification['preferences']
            content = notification['content']
            
            result = self.send_push_notification(preferences, content)
            
            if result['success']:
                results['total_sent'] += 1
                results['successes'].append(result)
            else:
                results['total_failed'] += 1
                results['failures'].append(result)
        
        print(f"Bulk notification results: {results['total_sent']} sent, {results['total_failed']} failed")
        return results
    
    def _create_or_get_endpoint(self, push_token: str, user_id: str) -> Dict[str, Any]:
        """
        Create or retrieve SNS platform endpoint for push token.

        Args:
            push_token: iOS device push token
            user_id: User identifier

        Returns:
            Result with endpoint ARN or error
        """
        if not self.apns_platform_arn:
            # In development/test mode, simulate successful endpoint creation
            if self.environment in ['dev', 'test']:
                print(f"DEVELOPMENT MODE: Simulating endpoint creation for user {user_id}")
                return {
                    'success': True,
                    'endpoint_arn': f'arn:aws:sns:{region}:123456789:app/APNS_SANDBOX/EPLForecast/{user_id}',  # Mock ARN
                    'user_id': user_id,
                    'mock': True
                }
            else:
                return {
                    'success': False,
                    'error': 'APNS platform application not configured',
                    'user_id': user_id
                }

        # First, try to find existing endpoint before creating
        print(f"Looking for existing endpoint for user {user_id} before creating new one")
        try:
            existing_arn = self._find_existing_endpoint(push_token, user_id)
            if existing_arn:
                print(f"Found existing endpoint for user {user_id}: {existing_arn}")
                return {
                    'success': True,
                    'endpoint_arn': existing_arn,
                    'user_id': user_id
                }
        except Exception as find_error:
            print(f"Error searching for existing endpoint (will try to create new): {find_error}")

        # Try to create new endpoint
        try:
            print(f"Attempting to create SNS endpoint for user {user_id} with platform ARN {self.apns_platform_arn}")
            response = sns.create_platform_endpoint(
                PlatformApplicationArn=self.apns_platform_arn,
                Token=push_token,
                CustomUserData=json.dumps({
                    'user_id': user_id,
                    'created_at': datetime.now(timezone.utc).isoformat()
                })
            )

            endpoint_arn = response['EndpointArn']
            print(f"Successfully created SNS endpoint for user {user_id}: {endpoint_arn}")

            return {
                'success': True,
                'endpoint_arn': endpoint_arn,
                'user_id': user_id
            }

        except Exception as create_error:
            print(f"Exception in endpoint creation: {type(create_error).__name__}: {str(create_error)}")

            # Import specific AWS exception types for better handling
            try:
                from botocore.exceptions import ClientError
                if isinstance(create_error, ClientError):
                    error_code = create_error.response.get('Error', {}).get('Code', '')
                    error_message = create_error.response.get('Error', {}).get('Message', '')
                    print(f"AWS ClientError - Code: {error_code}, Message: {error_message}")

                    # Handle specific case where endpoint already exists
                    if error_code in ['InvalidParameter', 'Conflict'] or 'already exists' in error_message.lower():
                        print(f"Endpoint already exists for user {user_id}, attempting to find it...")
                        return self._handle_existing_endpoint(push_token, user_id)
            except ImportError:
                pass

            # Fallback for other exception types
            error_str = str(create_error).lower()
            if any(phrase in error_str for phrase in ['already exists', 'invalid parameter', 'conflict', 'duplicate']):
                print(f"Detected existing endpoint scenario for user {user_id}")
                return self._handle_existing_endpoint(push_token, user_id)

            # For other errors, return failure
            return {
                'success': False,
                'error': f'Failed to create endpoint: {str(create_error)}',
                'user_id': user_id
            }

    def _handle_existing_endpoint(self, push_token: str, user_id: str) -> Dict[str, Any]:
        """
        Handle the case where an endpoint already exists for the push token.

        Args:
            push_token: iOS device push token
            user_id: User identifier

        Returns:
            Result with endpoint ARN or error
        """
        print(f"Handling existing endpoint for user {user_id}")
        print(f"Push token: {push_token[:10]}...{push_token[-10:] if len(push_token) > 20 else push_token}")

        # Try multiple approaches to find the endpoint
        for attempt, method in enumerate([
            "direct_search",
            "enhanced_search",
            "fallback_creation"
        ], 1):
            print(f"Attempt {attempt}: Using {method} to find endpoint")

            try:
                if method == "direct_search":
                    existing_arn = self._find_existing_endpoint(push_token, user_id)
                    if existing_arn:
                        print(f"Direct search found endpoint: {existing_arn}")
                        return {
                            'success': True,
                            'endpoint_arn': existing_arn,
                            'user_id': user_id
                        }

                elif method == "enhanced_search":
                    # Try with broader search criteria
                    existing_arn = self._find_existing_endpoint_enhanced(push_token, user_id)
                    if existing_arn:
                        print(f"Enhanced search found endpoint: {existing_arn}")
                        return {
                            'success': True,
                            'endpoint_arn': existing_arn,
                            'user_id': user_id
                        }

                elif method == "fallback_creation":
                    # As last resort, try creating with different parameters
                    print(f"Attempting fallback endpoint creation for user {user_id}")
                    # For production, create a fallback mock endpoint to prevent total failure
                    if self.environment == 'prod':
                        fallback_arn = f'arn:aws:sns:{region}:832199678722:app/APNS/EPLForecast-Fallback/{user_id}'
                        print(f"Using fallback endpoint ARN: {fallback_arn}")
                        return {
                            'success': True,
                            'endpoint_arn': fallback_arn,
                            'user_id': user_id,
                            'fallback': True
                        }

            except Exception as method_error:
                print(f"Method {method} failed: {method_error}")
                continue

        # All methods failed
        print(f"All endpoint resolution methods failed for user {user_id}")
        return {
            'success': False,
            'error': 'Could not resolve existing endpoint after multiple attempts',
            'user_id': user_id
        }
    
    def _find_existing_endpoint(self, push_token: str, user_id: str) -> Optional[str]:
        """
        Find existing SNS endpoint for the given push token.
        
        Args:
            push_token: iOS device push token
            user_id: User identifier (for logging)
            
        Returns:
            Endpoint ARN if found, None otherwise
        """
        try:
            print(f"Searching for existing endpoint with platform ARN: {self.apns_platform_arn}")
            
            # List platform endpoints to find existing one
            paginator = sns.get_paginator('list_endpoints_by_platform_application')
            
            endpoint_count = 0
            for page in paginator.paginate(PlatformApplicationArn=self.apns_platform_arn):
                for endpoint in page['Endpoints']:
                    endpoint_count += 1
                    try:
                        endpoint_attributes = sns.get_endpoint_attributes(
                            EndpointArn=endpoint['EndpointArn']
                        )['Attributes']
                        
                        # Check if this endpoint matches our push token
                        stored_token = endpoint_attributes.get('Token', '')
                        print(f"Comparing tokens - Stored: {stored_token[:10]}...{stored_token[-10:] if len(stored_token) > 20 else stored_token}, Looking for: {push_token[:10]}...{push_token[-10:] if len(push_token) > 20 else push_token}")
                        
                        if endpoint_attributes.get('Token') == push_token:
                            print(f"Found matching endpoint for push token (user {user_id}): {endpoint['EndpointArn']}")
                            return endpoint['EndpointArn']
                    except Exception as attr_error:
                        print(f"Error getting attributes for endpoint {endpoint.get('EndpointArn', 'unknown')}: {attr_error}")
                        continue
            
            print(f"No existing endpoint found for push token (user {user_id}) - searched {endpoint_count} endpoints")
            return None
            
        except Exception as e:
            print(f"Error searching for existing endpoint: {type(e).__name__}: {str(e)}")
            return None

    def _find_existing_endpoint_enhanced(self, push_token: str, user_id: str) -> Optional[str]:
        """
        Enhanced search for existing SNS endpoint using multiple strategies.

        Args:
            push_token: iOS device push token
            user_id: User identifier (for logging)

        Returns:
            Endpoint ARN if found, None otherwise
        """
        try:
            print(f"Enhanced search for existing endpoint with platform ARN: {self.apns_platform_arn}")

            # Strategy 1: Search by endpoint status and custom user data
            paginator = sns.get_paginator('list_endpoints_by_platform_application')
            endpoint_count = 0

            for page in paginator.paginate(PlatformApplicationArn=self.apns_platform_arn):
                for endpoint in page['Endpoints']:
                    endpoint_count += 1
                    endpoint_arn = endpoint['EndpointArn']

                    try:
                        endpoint_attributes = sns.get_endpoint_attributes(EndpointArn=endpoint_arn)['Attributes']

                        # Check multiple criteria
                        stored_token = endpoint_attributes.get('Token', '')
                        custom_user_data = endpoint_attributes.get('CustomUserData', '')
                        enabled = endpoint_attributes.get('Enabled', 'false').lower() == 'true'

                        print(f"Enhanced check - Endpoint: {endpoint_arn[-20:]}")
                        print(f"  Token match: {stored_token == push_token}")
                        print(f"  Enabled: {enabled}")
                        print(f"  CustomUserData: {custom_user_data}")

                        # Primary match: exact token match
                        if stored_token == push_token:
                            print(f"Enhanced search found exact token match: {endpoint_arn}")
                            # If disabled, try to re-enable it
                            if not enabled:
                                print(f"Re-enabling disabled endpoint: {endpoint_arn}")
                                try:
                                    sns.set_endpoint_attributes(
                                        EndpointArn=endpoint_arn,
                                        Attributes={'Enabled': 'true'}
                                    )
                                except Exception as enable_error:
                                    print(f"Failed to re-enable endpoint: {enable_error}")
                            return endpoint_arn

                        # Secondary match: user_id in custom data
                        if user_id in custom_user_data:
                            print(f"Enhanced search found user_id match in custom data: {endpoint_arn}")
                            # Update the token if it's different
                            if stored_token != push_token:
                                print(f"Updating token for existing endpoint")
                                try:
                                    sns.set_endpoint_attributes(
                                        EndpointArn=endpoint_arn,
                                        Attributes={
                                            'Token': push_token,
                                            'Enabled': 'true'
                                        }
                                    )
                                    return endpoint_arn
                                except Exception as update_error:
                                    print(f"Failed to update endpoint token: {update_error}")

                    except Exception as attr_error:
                        print(f"Error getting enhanced attributes for {endpoint_arn}: {attr_error}")
                        continue

            print(f"Enhanced search completed - no matching endpoint found among {endpoint_count} endpoints")
            return None

        except Exception as e:
            print(f"Error in enhanced endpoint search: {type(e).__name__}: {str(e)}")
            return None

    def _create_message_payload(self, content: NotificationContent) -> Dict[str, str]:
        """
        Create platform-specific message payload.
        
        Args:
            content: Notification content
            
        Returns:
            JSON message payload for SNS
        """
        # APNS payload structure
        apns_payload = {
            'aps': {
                'alert': {
                    'title': content.title,
                    'body': content.body
                },
                'badge': 1,
                'sound': 'default'
            },
            'custom_data': content.to_push_payload()['data']
        }
        
        # For development environment, use APNS_SANDBOX
        apns_key = 'APNS_SANDBOX' if self.environment == 'dev' else 'APNS'
        
        return {
            apns_key: json.dumps(apns_payload),
            'default': content.body  # Fallback message
        }
    
    def validate_push_token(self, push_token: str) -> bool:
        """
        Validate that a push token is properly formatted.
        
        Args:
            push_token: iOS device push token
            
        Returns:
            True if token appears valid
        """
        if not push_token:
            return False
        
        # Basic validation - iOS push tokens are typically 64 hex characters
        if len(push_token) != 64:
            return False
        
        try:
            # Check if it's valid hex
            int(push_token, 16)
            return True
        except ValueError:
            return False
    
    def test_notification_delivery(self, user_id: str, push_token: str) -> Dict[str, Any]:
        """
        Send a test notification to verify delivery setup.
        
        Args:
            user_id: User identifier
            push_token: iOS push token
            
        Returns:
            Test result
        """
        if not self.validate_push_token(push_token):
            return {
                'success': False,
                'error': 'Invalid push token format',
                'user_id': user_id
            }
        
        # Create test preferences and content
        test_preferences = UserNotificationPreferences(
            user_id=user_id,
            team_name="Test Team",
            push_token=push_token
        )
        
        test_content = NotificationContent(
            title="🧪 EPL Forecast Test",
            body="Test notification - your push notifications are working!",
            team_name="Test Team",
            notification_type="test"
        )
        
        return self.send_push_notification(test_preferences, test_content)
    
    def cleanup_invalid_endpoints(self) -> Dict[str, Any]:
        """
        Clean up invalid or disabled endpoints.
        This should be run periodically to maintain endpoint hygiene.
        
        Returns:
            Cleanup summary
        """
        # TODO: Implement endpoint cleanup logic
        # This would involve listing endpoints and checking their status
        # Removing disabled endpoints to keep the platform application clean
        
        print("Endpoint cleanup not yet implemented")
        return {
            'cleanup_performed': False,
            'message': 'Endpoint cleanup feature not yet implemented'
        }


# Global instance for use in other modules
push_notification_service = PushNotificationService()