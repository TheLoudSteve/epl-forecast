"""
Data models for EPL Forecast notification system.
"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from enum import Enum
import json
import time


class NotificationTiming(Enum):
    """Timing options for notifications."""
    IMMEDIATE = "immediate"
    END_OF_DAY = "end_of_day"


class NotificationSensitivity(Enum):
    """Sensitivity levels for position change notifications."""
    ANY_CHANGE = "any_change"
    SIGNIFICANT_ONLY = "significant_only"


class SignificantPositionType(Enum):
    """Types of significant position changes."""
    TITLE_POSITION = "title_position"  # 1st place
    CHAMPIONS_LEAGUE = "champions_league"  # Top 4
    RELEGATION = "relegation"  # Bottom 3


@dataclass
class UserNotificationPreferences:
    """User notification preferences data model."""
    
    user_id: str  # Device ID or user identifier
    team_name: str  # Which EPL team to track
    enabled: bool = True
    notification_timing: NotificationTiming = NotificationTiming.IMMEDIATE
    notification_sensitivity: NotificationSensitivity = NotificationSensitivity.ANY_CHANGE
    push_token: Optional[str] = None
    email_address: Optional[str] = None
    email_notifications_enabled: bool = False
    created_at: Optional[int] = None
    updated_at: Optional[int] = None
    
    def __post_init__(self):
        """Set timestamps if not provided."""
        current_time = int(time.time())
        if self.created_at is None:
            self.created_at = current_time
        self.updated_at = current_time
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = asdict(self)
        # Convert enums to string values
        item['notification_timing'] = self.notification_timing.value
        item['notification_sensitivity'] = self.notification_sensitivity.value
        return item
    
    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'UserNotificationPreferences':
        """Create instance from DynamoDB item."""
        # Convert string enum values back to enums
        if 'notification_timing' in item:
            item['notification_timing'] = NotificationTiming(item['notification_timing'])
        if 'notification_sensitivity' in item:
            item['notification_sensitivity'] = NotificationSensitivity(item['notification_sensitivity'])
        
        return cls(**item)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        data = self.to_dynamodb_item()
        return json.dumps(data, default=str)


@dataclass
class ForecastPosition:
    """Represents a team's forecasted position."""
    
    team_name: str
    position: int
    points: float
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    
    def is_significant_position(self) -> list[SignificantPositionType]:
        """Check if this position is significant (title, Champions League, relegation)."""
        significant_types = []
        
        if self.position == 1:
            significant_types.append(SignificantPositionType.TITLE_POSITION)
        
        if 1 <= self.position <= 4:
            significant_types.append(SignificantPositionType.CHAMPIONS_LEAGUE)
        
        if 18 <= self.position <= 20:  # Assuming 20 teams in Premier League
            significant_types.append(SignificantPositionType.RELEGATION)
        
        return significant_types


@dataclass
class ForecastSnapshot:
    """Historical snapshot of all team positions."""
    
    timestamp: int
    season: str
    teams: list[ForecastPosition]
    context: Optional[str] = None  # e.g., "after Arsenal vs Chelsea"
    
    def get_team_position(self, team_name: str) -> Optional[ForecastPosition]:
        """Get position data for a specific team."""
        for team in self.teams:
            if team.team_name.lower() == team_name.lower():
                return team
        return None
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            'snapshot_id': f"snapshot_{self.timestamp}",
            'timestamp': self.timestamp,
            'season': self.season,
            'teams': [asdict(team) for team in self.teams],
            'context': self.context
        }


@dataclass
class PositionChange:
    """Represents a change in team's forecasted position."""
    
    team_name: str
    previous_position: int
    new_position: int
    previous_points: float
    new_points: float
    change_context: str
    timestamp: int
    
    @property
    def position_difference(self) -> int:
        """Calculate position change (negative = moved up, positive = moved down)."""
        return self.new_position - self.previous_position
    
    @property
    def points_difference(self) -> float:
        """Calculate points difference."""
        return self.new_points - self.previous_points
    
    def is_improvement(self) -> bool:
        """Check if this represents an improvement (moving up the table)."""
        return self.position_difference < 0
    
    def is_significant_change(self, previous_snapshot: ForecastSnapshot, new_snapshot: ForecastSnapshot) -> bool:
        """Check if this change crosses significant position boundaries."""
        prev_team = previous_snapshot.get_team_position(self.team_name)
        new_team = new_snapshot.get_team_position(self.team_name)
        
        if not prev_team or not new_team:
            return False
        
        prev_significant = set(prev_team.is_significant_position())
        new_significant = set(new_team.is_significant_position())
        
        # Check if moved into or out of any significant position
        return prev_significant != new_significant


@dataclass
class NotificationContent:
    """Content for a notification."""
    
    title: str
    body: str
    team_name: str
    position_change: Optional[PositionChange] = None
    notification_type: str = "position_change"
    
    def to_push_payload(self) -> Dict[str, Any]:
        """Convert to push notification payload."""
        return {
            'title': self.title,
            'body': self.body,
            'data': {
                'team_name': self.team_name,
                'notification_type': self.notification_type,
                'position_change': asdict(self.position_change) if self.position_change else None
            }
        }


# EPL team names for validation
EPL_TEAMS = [
    "Arsenal", "Aston Villa", "Brighton", "Burnley", "Chelsea", 
    "Crystal Palace", "Everton", "Fulham", "Liverpool", "Luton Town",
    "Manchester City", "Manchester United", "Newcastle United", "Nottingham Forest",
    "Sheffield United", "Tottenham", "West Ham", "Wolves", "Bournemouth", "Brentford"
]