"""
Advanced notification content generation with contextual messaging and templates.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from models import (
    UserNotificationPreferences, PositionChange, NotificationContent, 
    SignificantPositionType, ForecastSnapshot
)


class NotificationContentGenerator:
    """Generates contextual notification content for different scenarios."""
    
    def __init__(self):
        # Emoji mappings for different contexts
        self.position_emojis = {
            'title': '🏆',
            'champions_league': '⭐',
            'europa': '🌟',  
            'relegation': '⚠️',
            'up': '📈',
            'down': '📉',
            'stable': '➡️',
            'test': '🧪'
        }
        
        # Context-specific templates
        self.title_templates = {
            'title_gained': "{emoji} {team} forecasted for 1st place!",
            'title_lost': "{emoji} {team} dropped from 1st place",
            'champions_league_in': "{emoji} {team} into Champions League positions!",
            'champions_league_out': "{emoji} {team} dropped out of Champions League",
            'europa_in': "{emoji} {team} into Europa League positions!",
            'europa_out': "{emoji} {team} dropped out of Europa League",
            'relegation_in': "{emoji} {team} in relegation zone",
            'relegation_out': "{emoji} {team} out of relegation zone!",
            'significant_up': "{emoji} {team} climbed to {position}",
            'significant_down': "{emoji} {team} dropped to {position}",
            'minor_up': "{emoji} {team} moved up in forecast",
            'minor_down': "{emoji} {team} moved down in forecast",
            'test': "{emoji} EPL Forecast Test - {team}"
        }
    
    def generate_position_change_notification(
        self, 
        preferences: UserNotificationPreferences,
        change: PositionChange,
        previous_snapshot: ForecastSnapshot,
        new_snapshot: ForecastSnapshot,
        context: str = ""
    ) -> NotificationContent:
        """
        Generate notification content for a position change.
        
        Args:
            preferences: User's notification preferences
            change: Position change details
            previous_snapshot: Previous forecast snapshot
            new_snapshot: New forecast snapshot
            context: Additional context about the change
            
        Returns:
            NotificationContent with contextual title and body
        """
        # Determine the significance and type of change
        change_type, significance = self._analyze_position_change(
            change, previous_snapshot, new_snapshot
        )
        
        # Generate title based on change type
        title = self._generate_title(change, change_type, significance)
        
        # Generate detailed body text
        body = self._generate_body(change, change_type, context, preferences)
        
        return NotificationContent(
            title=title,
            body=body,
            team_name=change.team_name,
            position_change=change,
            notification_type="position_change"
        )
    
    def generate_test_notification(
        self, 
        preferences: UserNotificationPreferences
    ) -> NotificationContent:
        """Generate a test notification for user verification."""
        
        title = self.title_templates['test'].format(
            emoji=self.position_emojis['test'],
            team=preferences.team_name
        )
        
        body = (f"Test notification for {preferences.team_name} forecast updates. "
                f"Settings: {preferences.notification_timing.value}, "
                f"{preferences.notification_sensitivity.value}")
        
        return NotificationContent(
            title=title,
            body=body,
            team_name=preferences.team_name,
            notification_type="test"
        )
    
    def generate_end_of_day_summary(
        self,
        preferences: UserNotificationPreferences,
        changes: List[PositionChange],
        context: str = ""
    ) -> NotificationContent:
        """
        Generate an end-of-day summary notification with multiple changes.
        
        Args:
            preferences: User's notification preferences
            changes: List of position changes for the day
            context: Context about what caused the changes
            
        Returns:
            Summary notification content
        """
        team_name = preferences.team_name
        team_changes = [c for c in changes if c.team_name.lower() == team_name.lower()]
        
        if not team_changes:
            # No changes for user's team
            title = f"📊 {team_name} forecast update"
            body = f"{team_name}'s forecasted position remains unchanged today"
        elif len(team_changes) == 1:
            # Single change - use regular generation
            # This is a simplified version for end-of-day
            change = team_changes[0]
            movement = "up" if change.is_improvement() else "down"
            emoji = self.position_emojis[movement]
            
            title = f"{emoji} {team_name} daily forecast update"
            body = (f"{team_name} moved {movement} from position {change.previous_position} "
                   f"to {change.new_position}")
        else:
            # Multiple changes throughout the day
            net_change = team_changes[-1].new_position - team_changes[0].previous_position
            if net_change < 0:
                emoji = self.position_emojis['up']
                direction = f"up {abs(net_change)} position{'s' if abs(net_change) > 1 else ''}"
            elif net_change > 0:
                emoji = self.position_emojis['down']
                direction = f"down {net_change} position{'s' if net_change > 1 else ''}"
            else:
                emoji = self.position_emojis['stable']
                direction = "with no net change"
            
            title = f"{emoji} {team_name} daily summary"
            body = (f"{team_name} had {len(team_changes)} forecast updates today, "
                   f"ending {direction}")
        
        if context:
            body += f" ({context})"
        
        return NotificationContent(
            title=title,
            body=body,
            team_name=team_name,
            notification_type="daily_summary"
        )
    
    def _analyze_position_change(
        self, 
        change: PositionChange,
        previous_snapshot: ForecastSnapshot,
        new_snapshot: ForecastSnapshot
    ) -> Tuple[str, str]:
        """
        Analyze a position change to determine its type and significance.
        
        Returns:
            Tuple of (change_type, significance_level)
        """
        prev_pos = change.previous_position
        new_pos = change.new_position
        
        # Check for crossing significant boundaries
        if prev_pos != 1 and new_pos == 1:
            return ('title_gained', 'high')
        elif prev_pos == 1 and new_pos != 1:
            return ('title_lost', 'high')
        elif prev_pos > 4 and new_pos <= 4:
            return ('champions_league_in', 'high')
        elif prev_pos <= 4 and new_pos > 4:
            return ('champions_league_out', 'high')
        elif prev_pos > 7 and new_pos <= 7:
            return ('europa_in', 'medium')
        elif prev_pos <= 7 and new_pos > 7:
            return ('europa_out', 'medium')
        elif prev_pos < 18 and new_pos >= 18:
            return ('relegation_in', 'high')
        elif prev_pos >= 18 and new_pos < 18:
            return ('relegation_out', 'high')
        elif abs(new_pos - prev_pos) >= 3:
            # Significant movement (3+ positions)
            return ('significant_up' if change.is_improvement() else 'significant_down', 'medium')
        else:
            # Minor movement
            return ('minor_up' if change.is_improvement() else 'minor_down', 'low')
    
    def _generate_title(self, change: PositionChange, change_type: str, significance: str) -> str:
        """Generate notification title based on change analysis."""
        
        emoji_map = {
            'title_gained': self.position_emojis['title'],
            'title_lost': self.position_emojis['down'],
            'champions_league_in': self.position_emojis['champions_league'],
            'champions_league_out': self.position_emojis['down'],
            'europa_in': self.position_emojis['europa'],
            'europa_out': self.position_emojis['down'],
            'relegation_in': self.position_emojis['relegation'],
            'relegation_out': self.position_emojis['up'],
            'significant_up': self.position_emojis['up'],
            'significant_down': self.position_emojis['down'],
            'minor_up': self.position_emojis['up'],
            'minor_down': self.position_emojis['down']
        }
        
        emoji = emoji_map.get(change_type, '📊')
        team = change.team_name
        position = self._ordinal_position(change.new_position)
        
        template = self.title_templates.get(change_type, "{emoji} {team} position update")
        
        return template.format(
            emoji=emoji,
            team=team,
            position=position
        )
    
    def _generate_body(
        self, 
        change: PositionChange, 
        change_type: str,
        context: str,
        preferences: UserNotificationPreferences
    ) -> str:
        """Generate detailed notification body text."""
        
        team = change.team_name
        prev_pos = self._ordinal_position(change.previous_position)
        new_pos = self._ordinal_position(change.new_position)
        
        # Base movement description
        if change.is_improvement():
            movement_desc = f"moved up from {prev_pos} to {new_pos}"
        else:
            movement_desc = f"dropped from {prev_pos} to {new_pos}"
        
        # Add points context if available
        points_diff = change.points_difference
        if abs(points_diff) > 0.1:  # Avoid tiny differences
            if points_diff > 0:
                points_desc = f" (+{points_diff:.1f} points)"
            else:
                points_desc = f" ({points_diff:.1f} points)"
        else:
            points_desc = ""
        
        body = f"{team} {movement_desc} in the EPL forecast{points_desc}"
        
        # Add context if provided
        if context and context.strip():
            # Clean up context formatting
            clean_context = context.strip()
            if not clean_context.startswith("after"):
                clean_context = f"after {clean_context}"
            body += f" {clean_context}"
        
        # Add significance-based additional info
        if change_type == 'title_gained':
            body += " 🏆 Title contenders!"
        elif change_type == 'champions_league_in':
            body += " ⭐ Champions League qualification!"
        elif change_type == 'relegation_in':
            body += " ⚠️ Relegation battle intensifies"
        elif change_type == 'relegation_out':
            body += " 🙌 Climbing away from relegation"
        
        return body
    
    def _ordinal_position(self, position: int) -> str:
        """Convert position number to ordinal (1st, 2nd, 3rd, etc.)."""
        if 10 <= position % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(position % 10, 'th')
        return f"{position}{suffix}"
    
    def get_notification_preview(
        self,
        preferences: UserNotificationPreferences,
        change_scenarios: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Generate preview notifications for different scenarios.
        Useful for showing users what their notifications will look like.
        
        Args:
            preferences: User's notification preferences
            change_scenarios: List of mock position change scenarios
            
        Returns:
            List of preview notifications with title/body
        """
        previews = []
        
        # Add test notification preview
        test_notification = self.generate_test_notification(preferences)
        previews.append({
            'type': 'Test Notification',
            'title': test_notification.title,
            'body': test_notification.body
        })
        
        # Generate previews for different scenarios
        for scenario in change_scenarios:
            # Create mock PositionChange
            mock_change = PositionChange(
                team_name=preferences.team_name,
                previous_position=scenario['previous_position'],
                new_position=scenario['new_position'],
                previous_points=scenario.get('previous_points', 50.0),
                new_points=scenario.get('new_points', 51.0),
                change_context=scenario.get('context', 'match result'),
                timestamp=int(datetime.now(timezone.utc).timestamp())
            )
            
            # Create mock snapshots (simplified)
            prev_snapshot = None  # Would need full implementation
            new_snapshot = None   # Would need full implementation
            
            # Generate notification (with simplified logic for preview)
            change_type, significance = self._analyze_position_change(
                mock_change, prev_snapshot, new_snapshot
            )
            
            title = self._generate_title(mock_change, change_type, significance)
            body = self._generate_body(
                mock_change, change_type, scenario.get('context', ''), preferences
            )
            
            previews.append({
                'type': scenario.get('name', f"Position {scenario['new_position']}"),
                'title': title,
                'body': body
            })
        
        return previews


# Global instance for use in other modules
notification_content_generator = NotificationContentGenerator()