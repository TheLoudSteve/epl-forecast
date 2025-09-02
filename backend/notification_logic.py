"""
Notification logic for detecting position changes and triggering notifications.
"""

import os
import boto3
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from models import (
    UserNotificationPreferences, NotificationTiming, NotificationSensitivity,
    ForecastSnapshot, PositionChange, NotificationContent
)
from forecast_history import forecast_history_manager
from push_notification_service import push_notification_service
from notification_content_generator import notification_content_generator
from notification_rate_limiter import notification_rate_limiter

# Initialize DynamoDB
region = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=region)


class NotificationManager:
    """Manages position change detection and notification triggering."""
    
    def __init__(self):
        self.preferences_table_name = os.environ.get('USER_PREFERENCES_TABLE')
        self.preferences_table = dynamodb.Table(self.preferences_table_name) if self.preferences_table_name else None
    
    def process_forecast_update(self, forecast_data: Dict[str, Any], context: str = "Forecast update") -> Dict[str, Any]:
        """
        Process a forecast update, detect changes, and trigger notifications.
        
        Args:
            forecast_data: The new forecast data
            context: Context about what triggered this update
            
        Returns:
            Summary of notifications processed
        """
        if not self.preferences_table:
            print("USER_PREFERENCES_TABLE not configured, skipping notifications")
            return {'error': 'Preferences table not configured'}
        
        # Get the latest snapshot before this update
        current_snapshot = forecast_history_manager.get_latest_snapshot()
        if not current_snapshot:
            print("No previous forecast history found, skipping position change detection")
            return {'message': 'No previous history for comparison', 'notifications_sent': 0}
        
        # Create new snapshot (this should already be saved by the calling function)
        new_snapshot = self._create_snapshot_from_data(forecast_data, context)
        
        # Detect position changes
        position_changes = forecast_history_manager.detect_position_changes(
            current_snapshot, new_snapshot
        )
        
        if not position_changes:
            print("No position changes detected")
            return {'message': 'No position changes detected', 'notifications_sent': 0}
        
        print(f"Detected {len(position_changes)} position changes")
        
        # Get all user preferences
        user_preferences = self._get_all_user_preferences()
        
        notifications_processed = 0
        notifications_sent = 0
        
        # Process notifications for each user
        for preferences in user_preferences:
            if not preferences.enabled:
                continue
            
            # Check if user's team has position changes
            user_team_changes = [
                change for change in position_changes 
                if change.team_name.lower() == preferences.team_name.lower()
            ]
            
            if not user_team_changes:
                continue
            
            for change in user_team_changes:
                notifications_processed += 1
                
                # Check if this change meets user's sensitivity settings
                if self._should_notify_user(preferences, change, current_snapshot, new_snapshot):
                    # Create notification content
                    notification_content = self._create_notification_content(
                        preferences, change, context, current_snapshot, new_snapshot
                    )
                    
                    # Check rate limiting before sending
                    can_send, rate_limit_reason = notification_rate_limiter.can_send_notification(
                        preferences, notification_content
                    )
                    
                    if not can_send:
                        print(f"Rate limiting blocked notification for {preferences.user_id}: {rate_limit_reason}")
                        continue
                    
                    # Send notification based on user's timing preference
                    if preferences.notification_timing == NotificationTiming.IMMEDIATE:
                        if self._send_immediate_notification(preferences, notification_content):
                            notifications_sent += 1
                    else:  # END_OF_DAY
                        if self._queue_end_of_day_notification(preferences, notification_content):
                            notifications_sent += 1
        
        return {
            'message': f'Processed {notifications_processed} potential notifications, sent {notifications_sent}',
            'position_changes_detected': len(position_changes),
            'notifications_processed': notifications_processed,
            'notifications_sent': notifications_sent,
            'changes': [
                {
                    'team': change.team_name,
                    'previous_position': change.previous_position,
                    'new_position': change.new_position,
                    'movement': 'up' if change.is_improvement() else 'down'
                }
                for change in position_changes
            ]
        }
    
    def _create_snapshot_from_data(self, forecast_data: Dict[str, Any], context: str) -> ForecastSnapshot:
        """Create a ForecastSnapshot from forecast data."""
        from models import ForecastPosition
        
        timestamp = int(datetime.now(timezone.utc).timestamp())
        teams = []
        
        for team_data in forecast_data.get('teams', []):
            position = ForecastPosition(
                team_name=team_data.get('name', ''),
                position=team_data.get('forecasted_position', 0),
                points=float(team_data.get('forecasted_points', 0)),
                played=team_data.get('played', 0),
                won=team_data.get('won', 0),
                drawn=team_data.get('drawn', 0),
                lost=team_data.get('lost', 0),
                goals_for=team_data.get('for', 0),
                goals_against=team_data.get('against', 0),
                goal_difference=team_data.get('goal_difference', 0)
            )
            teams.append(position)
        
        return ForecastSnapshot(
            timestamp=timestamp,
            season="2024-25",  # TODO: Make dynamic
            teams=teams,
            context=context
        )
    
    def _get_all_user_preferences(self) -> List[UserNotificationPreferences]:
        """Get all user preferences from DynamoDB."""
        try:
            response = self.preferences_table.scan()
            preferences = []
            
            for item in response.get('Items', []):
                try:
                    user_prefs = UserNotificationPreferences.from_dynamodb_item(item)
                    preferences.append(user_prefs)
                except Exception as e:
                    print(f"Error parsing user preferences for {item.get('user_id', 'unknown')}: {e}")
                    continue
            
            # Handle pagination if needed
            while 'LastEvaluatedKey' in response:
                response = self.preferences_table.scan(
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                for item in response.get('Items', []):
                    try:
                        user_prefs = UserNotificationPreferences.from_dynamodb_item(item)
                        preferences.append(user_prefs)
                    except Exception as e:
                        print(f"Error parsing user preferences for {item.get('user_id', 'unknown')}: {e}")
                        continue
            
            print(f"Retrieved {len(preferences)} user preferences")
            return preferences
            
        except Exception as e:
            print(f"Error retrieving user preferences: {e}")
            return []
    
    def _should_notify_user(self, preferences: UserNotificationPreferences, 
                           change: PositionChange, previous_snapshot: ForecastSnapshot, 
                           new_snapshot: ForecastSnapshot) -> bool:
        """
        Determine if a user should be notified based on their sensitivity settings.
        
        Args:
            preferences: User's notification preferences
            change: The position change
            previous_snapshot: Previous forecast snapshot
            new_snapshot: New forecast snapshot
            
        Returns:
            True if user should be notified
        """
        if preferences.notification_sensitivity == NotificationSensitivity.ANY_CHANGE:
            return True  # Notify for any position change
        
        # For SIGNIFICANT_ONLY, check if this crosses significant boundaries
        return change.is_significant_change(previous_snapshot, new_snapshot)
    
    def _create_notification_content(self, preferences: UserNotificationPreferences, 
                                   change: PositionChange, context: str,
                                   previous_snapshot: ForecastSnapshot,
                                   new_snapshot: ForecastSnapshot) -> NotificationContent:
        """
        Create notification content for a position change using the enhanced content generator.
        
        Args:
            preferences: User's preferences
            change: The position change
            context: Context about the change
            previous_snapshot: Previous forecast snapshot
            new_snapshot: New forecast snapshot
            
        Returns:
            NotificationContent object
        """
        return notification_content_generator.generate_position_change_notification(
            preferences, change, previous_snapshot, new_snapshot, context
        )
    
    def _send_immediate_notification(self, preferences: UserNotificationPreferences, 
                                   content: NotificationContent) -> bool:
        """
        Send an immediate notification.
        
        Args:
            preferences: User's preferences
            content: Notification content
            
        Returns:
            True if notification was sent successfully
        """
        print(f"[IMMEDIATE NOTIFICATION] To: {preferences.user_id} | Team: {content.team_name}")
        print(f"  Title: {content.title}")
        print(f"  Body: {content.body}")
        
        # Send via push notification service
        result = push_notification_service.send_push_notification(preferences, content)
        
        if result['success']:
            message_id = result.get('message_id', 'N/A')
            print(f"  ✅ Push notification sent successfully (MessageID: {message_id})")
            
            # Record the successful notification for rate limiting
            notification_rate_limiter.record_sent_notification(preferences, content, str(message_id))
            
            return True
        else:
            print(f"  ❌ Push notification failed: {result.get('error', 'Unknown error')}")
            return False
    
    def _queue_end_of_day_notification(self, preferences: UserNotificationPreferences, 
                                     content: NotificationContent) -> bool:
        """
        Queue an end-of-day notification.
        
        Args:
            preferences: User's preferences
            content: Notification content
            
        Returns:
            True if notification was queued successfully
        """
        # TODO: Implement end-of-day notification queuing (probably using EventBridge scheduled events)
        print(f"[END-OF-DAY QUEUED] To: {preferences.user_id} | Team: {content.team_name}")
        print(f"  Title: {content.title}")
        print(f"  Body: {content.body}")
        
        # For now, just log the notification
        # In the future, this will store notifications for batched sending
        return True
    
    def send_test_notification(self, user_id: str) -> Dict[str, Any]:
        """
        Send a test notification for a specific user.
        
        Args:
            user_id: User ID to send test notification to
            
        Returns:
            Result of test notification
        """
        try:
            # Get user preferences
            response = self.preferences_table.get_item(Key={'user_id': user_id})
            if 'Item' not in response:
                return {'error': 'User preferences not found'}
            
            preferences = UserNotificationPreferences.from_dynamodb_item(response['Item'])
            
            # Create test notification content using the enhanced generator
            test_content = notification_content_generator.generate_test_notification(preferences)
            
            # Check rate limiting for test notifications (more lenient for tests)
            can_send, rate_limit_reason = notification_rate_limiter.can_send_notification_by_user_id(preferences.user_id)
            
            if not can_send and "Daily" not in rate_limit_reason:  # Allow tests even with hourly limits
                print(f"Rate limiting would block test notification: {rate_limit_reason}")
                # For test notifications, we'll show the limit but still try to send
            
            # Send via push notification service directly for test
            result = push_notification_service.send_push_notification(preferences, test_content)
            
            # Record test notification if successful
            if result['success'] and result.get('message_id'):
                notification_rate_limiter.record_sent_notification(
                    preferences, test_content, str(result['message_id'])
                )
            
            if result['success']:
                return {
                    'success': True,
                    'message': 'Test notification sent successfully',
                    'message_id': result.get('message_id'),
                    'user_id': user_id,
                    'team': preferences.team_name
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', 'Failed to send test notification'),
                    'user_id': user_id,
                    'team': preferences.team_name
                }
            
        except Exception as e:
            print(f"Error sending test notification: {e}")
            return {'error': f'Failed to send test notification: {str(e)}'}


# Global instance for use in Lambda functions
notification_manager = NotificationManager()