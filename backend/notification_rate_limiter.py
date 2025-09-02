"""
Rate limiting and notification management to prevent spam and optimize delivery.
"""

import os
import boto3
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from models import UserNotificationPreferences, NotificationContent
import json


@dataclass
class NotificationRecord:
    """Record of a sent notification for rate limiting purposes."""
    
    user_id: str
    team_name: str
    notification_type: str
    timestamp: int
    message_id: Optional[str] = None
    content_hash: Optional[str] = None  # To detect duplicate content
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item."""
        return {
            'record_id': f"{self.user_id}#{self.timestamp}",
            'user_id': self.user_id,
            'team_name': self.team_name,
            'notification_type': self.notification_type,
            'timestamp': self.timestamp,
            'message_id': self.message_id,
            'content_hash': self.content_hash,
            'ttl': self.timestamp + (7 * 24 * 60 * 60)  # 7 days retention
        }


class NotificationRateLimiter:
    """Manages notification rate limiting and delivery optimization."""
    
    def __init__(self):
        self.region = os.environ.get('AWS_REGION', 'us-east-1')
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        
        # For now, we'll use the forecast history table to store rate limiting data
        # In production, you'd want a dedicated table
        self.history_table_name = os.environ.get('FORECAST_HISTORY_TABLE')
        self.history_table = self.dynamodb.Table(self.history_table_name) if self.history_table_name else None
        
        # Rate limiting configuration
        self.rate_limits = {
            'max_notifications_per_hour': 5,  # Per user
            'max_notifications_per_day': 20,   # Per user
            'min_time_between_notifications': 300,  # 5 minutes in seconds
            'duplicate_content_window': 3600,  # 1 hour in seconds
            'cooldown_after_burst': 1800,  # 30 minutes after hitting hourly limit
        }
        
        print(f"NotificationRateLimiter initialized with limits: {self.rate_limits}")
    
    def can_send_notification(self, preferences: UserNotificationPreferences, 
                            content: NotificationContent) -> Tuple[bool, str]:
        """
        Check if a notification can be sent based on rate limiting rules.
        
        Args:
            preferences: User's notification preferences
            content: Notification content to send
            
        Returns:
            Tuple of (can_send: bool, reason: str)
        """
        if not self.history_table:
            print("Warning: Rate limiting table not configured, allowing all notifications")
            return True, "Rate limiting not configured"
        
        user_id = preferences.user_id
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        try:
            # Get recent notification history for this user
            recent_notifications = self._get_recent_notifications(user_id, current_time)
            
            # Check hourly rate limit
            hourly_count = len([n for n in recent_notifications 
                               if current_time - n['timestamp'] <= 3600])
            
            if hourly_count >= self.rate_limits['max_notifications_per_hour']:
                # Check if we're in cooldown period
                last_notification_time = max([n['timestamp'] for n in recent_notifications], 
                                           default=0)
                cooldown_remaining = (last_notification_time + 
                                    self.rate_limits['cooldown_after_burst']) - current_time
                
                if cooldown_remaining > 0:
                    return False, f"Rate limit exceeded. Cooldown for {cooldown_remaining // 60} more minutes"
            
            # Check daily rate limit
            daily_count = len([n for n in recent_notifications 
                              if current_time - n['timestamp'] <= 86400])
            
            if daily_count >= self.rate_limits['max_notifications_per_day']:
                return False, "Daily notification limit exceeded"
            
            # Check minimum time between notifications
            if recent_notifications:
                last_notification_time = max([n['timestamp'] for n in recent_notifications])
                time_since_last = current_time - last_notification_time
                
                if time_since_last < self.rate_limits['min_time_between_notifications']:
                    wait_time = self.rate_limits['min_time_between_notifications'] - time_since_last
                    return False, f"Too soon since last notification. Wait {wait_time // 60} more minutes"
            
            # Check for duplicate content
            content_hash = self._generate_content_hash(content)
            duplicate_window = self.rate_limits['duplicate_content_window']
            
            for notification in recent_notifications:
                if (notification.get('content_hash') == content_hash and 
                    current_time - notification['timestamp'] < duplicate_window):
                    return False, "Duplicate notification content within window"
            
            return True, "Notification allowed"
            
        except Exception as e:
            print(f"Error checking rate limits for user {user_id}: {e}")
            # Fail open - allow notification if rate limiting check fails
            return True, f"Rate limiting check failed: {str(e)}"
    
    def record_sent_notification(self, preferences: UserNotificationPreferences,
                               content: NotificationContent, message_id: str) -> bool:
        """
        Record a sent notification for rate limiting tracking.
        
        Args:
            preferences: User's notification preferences
            content: Notification content that was sent
            message_id: SNS message ID from successful send
            
        Returns:
            True if record was saved successfully
        """
        if not self.history_table:
            return True  # Skip recording if table not configured
        
        try:
            record = NotificationRecord(
                user_id=preferences.user_id,
                team_name=preferences.team_name,
                notification_type=content.notification_type,
                timestamp=int(datetime.now(timezone.utc).timestamp()),
                message_id=message_id,
                content_hash=self._generate_content_hash(content)
            )
            
            # Store in DynamoDB (reusing forecast history table with different key pattern)
            item = record.to_dynamodb_item()
            item['snapshot_id'] = f"notification_{record.user_id}_{record.timestamp}"
            
            self.history_table.put_item(Item=item)
            
            print(f"Recorded notification for rate limiting: {record.user_id} - {content.notification_type}")
            return True
            
        except Exception as e:
            print(f"Error recording notification for rate limiting: {e}")
            return False
    
    def get_user_notification_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get notification statistics for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with user's notification statistics
        """
        if not self.history_table:
            return {'error': 'Rate limiting not configured'}
        
        try:
            current_time = int(datetime.now(timezone.utc).timestamp())
            recent_notifications = self._get_recent_notifications(user_id, current_time)
            
            # Calculate stats
            hourly_count = len([n for n in recent_notifications 
                               if current_time - n['timestamp'] <= 3600])
            daily_count = len([n for n in recent_notifications 
                              if current_time - n['timestamp'] <= 86400])
            weekly_count = len([n for n in recent_notifications 
                               if current_time - n['timestamp'] <= 604800])
            
            last_notification_time = max([n['timestamp'] for n in recent_notifications], 
                                       default=0)
            
            # Check current limits
            can_send_now, reason = self.can_send_notification_by_user_id(user_id)
            
            return {
                'user_id': user_id,
                'notifications_last_hour': hourly_count,
                'notifications_last_day': daily_count,
                'notifications_last_week': weekly_count,
                'last_notification_time': last_notification_time,
                'can_send_notification': can_send_now,
                'rate_limit_reason': reason if not can_send_now else None,
                'rate_limits': self.rate_limits,
                'next_allowed_time': self._calculate_next_allowed_time(user_id, current_time)
            }
            
        except Exception as e:
            print(f"Error getting notification stats for user {user_id}: {e}")
            return {'error': str(e)}
    
    def can_send_notification_by_user_id(self, user_id: str) -> Tuple[bool, str]:
        """
        Quick check if a user can receive notifications (without full content).
        
        Args:
            user_id: User identifier
            
        Returns:
            Tuple of (can_send: bool, reason: str)
        """
        if not self.history_table:
            return True, "Rate limiting not configured"
        
        try:
            current_time = int(datetime.now(timezone.utc).timestamp())
            recent_notifications = self._get_recent_notifications(user_id, current_time)
            
            # Check hourly rate limit
            hourly_count = len([n for n in recent_notifications 
                               if current_time - n['timestamp'] <= 3600])
            
            if hourly_count >= self.rate_limits['max_notifications_per_hour']:
                return False, "Hourly rate limit exceeded"
            
            # Check daily rate limit
            daily_count = len([n for n in recent_notifications 
                              if current_time - n['timestamp'] <= 86400])
            
            if daily_count >= self.rate_limits['max_notifications_per_day']:
                return False, "Daily rate limit exceeded"
            
            # Check minimum time between notifications
            if recent_notifications:
                last_notification_time = max([n['timestamp'] for n in recent_notifications])
                time_since_last = current_time - last_notification_time
                
                if time_since_last < self.rate_limits['min_time_between_notifications']:
                    return False, "Too soon since last notification"
            
            return True, "User can receive notifications"
            
        except Exception as e:
            print(f"Error checking rate limits for user {user_id}: {e}")
            return True, f"Rate limiting check failed: {str(e)}"
    
    def _get_recent_notifications(self, user_id: str, current_time: int) -> List[Dict[str, Any]]:
        """Get recent notification records for a user."""
        try:
            # Look back 24 hours for recent notifications
            start_time = current_time - 86400
            
            # Query notification records (stored with snapshot_id pattern notification_*)
            response = self.history_table.scan(
                FilterExpression='begins_with(snapshot_id, :prefix) AND user_id = :user_id AND #ts >= :start_time',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':prefix': 'notification_',
                    ':user_id': user_id,
                    ':start_time': start_time
                }
            )
            
            return response.get('Items', [])
            
        except Exception as e:
            print(f"Error retrieving recent notifications for user {user_id}: {e}")
            return []
    
    def _generate_content_hash(self, content: NotificationContent) -> str:
        """Generate a hash for notification content to detect duplicates."""
        import hashlib
        
        # Create a hash based on title and body
        content_string = f"{content.title}|{content.body}|{content.team_name}"
        return hashlib.md5(content_string.encode()).hexdigest()[:16]
    
    def _calculate_next_allowed_time(self, user_id: str, current_time: int) -> Optional[int]:
        """Calculate when the user can next receive a notification."""
        try:
            recent_notifications = self._get_recent_notifications(user_id, current_time)
            
            if not recent_notifications:
                return current_time  # Can send immediately
            
            last_notification_time = max([n['timestamp'] for n in recent_notifications])
            min_wait_time = last_notification_time + self.rate_limits['min_time_between_notifications']
            
            # Check hourly limits
            hourly_notifications = [n for n in recent_notifications 
                                   if current_time - n['timestamp'] <= 3600]
            
            if len(hourly_notifications) >= self.rate_limits['max_notifications_per_hour']:
                # Need to wait until oldest hourly notification expires, plus cooldown
                oldest_hourly = min([n['timestamp'] for n in hourly_notifications])
                hourly_reset_time = oldest_hourly + 3600 + self.rate_limits['cooldown_after_burst']
                min_wait_time = max(min_wait_time, hourly_reset_time)
            
            return max(min_wait_time, current_time)
            
        except Exception as e:
            print(f"Error calculating next allowed time for user {user_id}: {e}")
            return current_time
    
    def cleanup_old_records(self, days_to_keep: int = 7) -> Dict[str, Any]:
        """
        Clean up old notification records (handled by TTL, but manual cleanup available).
        
        Args:
            days_to_keep: Number of days of records to retain
            
        Returns:
            Cleanup summary
        """
        if not self.history_table:
            return {'error': 'Rate limiting table not configured'}
        
        try:
            cutoff_time = int(datetime.now(timezone.utc).timestamp()) - (days_to_keep * 86400)
            
            # Scan for old notification records
            response = self.history_table.scan(
                FilterExpression='begins_with(snapshot_id, :prefix) AND #ts < :cutoff',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':prefix': 'notification_',
                    ':cutoff': cutoff_time
                },
                ProjectionExpression='snapshot_id'
            )
            
            old_records = response.get('Items', [])
            
            # Delete old records in batches
            deleted_count = 0
            with self.history_table.batch_writer() as batch:
                for record in old_records:
                    batch.delete_item(Key={'snapshot_id': record['snapshot_id']})
                    deleted_count += 1
            
            print(f"Cleaned up {deleted_count} old notification records")
            
            return {
                'success': True,
                'records_deleted': deleted_count,
                'cutoff_time': cutoff_time,
                'days_kept': days_to_keep
            }
            
        except Exception as e:
            print(f"Error during notification records cleanup: {e}")
            return {'error': str(e)}


# Global instance for use in other modules
notification_rate_limiter = NotificationRateLimiter()