"""
Forecast history tracking utilities for position change detection.
"""

import os
import boto3
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from models import ForecastSnapshot, ForecastPosition, PositionChange

# Initialize DynamoDB
region = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=region)


class ForecastHistoryManager:
    """Manages forecast history storage and retrieval."""
    
    def __init__(self):
        self.history_table_name = os.environ.get('FORECAST_HISTORY_TABLE')
        self.history_table = dynamodb.Table(self.history_table_name) if self.history_table_name else None
    
    def save_forecast_snapshot(self, forecast_data: Dict[str, Any], context: Optional[str] = None) -> ForecastSnapshot:
        """
        Save a forecast snapshot to DynamoDB history table.
        Saves both a timestamped snapshot AND overwrites the "latest" snapshot for efficient retrieval.

        Args:
            forecast_data: The forecast data from calculate_forecasts()
            context: Optional context about what triggered this update

        Returns:
            ForecastSnapshot object
        """
        if not self.history_table:
            raise ValueError("FORECAST_HISTORY_TABLE environment variable not set")

        timestamp = int(datetime.now(timezone.utc).timestamp())
        season = "2024-25"  # TODO: Make this dynamic

        # Convert forecast data to ForecastPosition objects
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

        # Create snapshot
        snapshot = ForecastSnapshot(
            timestamp=timestamp,
            season=season,
            teams=teams,
            context=context
        )

        # Save to DynamoDB with TTL (90 days)
        ttl = timestamp + (90 * 24 * 60 * 60)  # 90 days from now

        item = snapshot.to_dynamodb_item()
        item['ttl'] = ttl

        # Save both timestamped snapshot AND "latest" snapshot
        # 1. Save timestamped snapshot for history
        self.history_table.put_item(Item=item)

        # 2. Overwrite "latest" snapshot for efficient retrieval (no Scan needed!)
        latest_item = item.copy()
        latest_item['snapshot_id'] = f'latest-{season}'
        self.history_table.put_item(Item=latest_item)

        print(f"Saved forecast snapshot with {len(teams)} teams to history table (timestamp: {timestamp}, latest: latest-{season})")
        return snapshot
    
    def get_latest_snapshot(self) -> Optional[ForecastSnapshot]:
        """
        Get the most recent forecast snapshot using efficient get_item (99% cost reduction vs Scan).

        Uses the 'latest-{season}' key which is overwritten on each save_forecast_snapshot().
        Historical timestamped snapshots are still preserved for time-series queries.

        Returns:
            Latest ForecastSnapshot or None if no history exists
        """
        if not self.history_table:
            return None

        try:
            season = "2024-25"  # TODO: Make this dynamic

            # Single get_item - 100x faster and cheaper than Scan!
            response = self.history_table.get_item(
                Key={'snapshot_id': f'latest-{season}'}
            )

            if 'Item' not in response:
                print(f"No latest snapshot found for season {season}")
                return None

            item = response['Item']
            return self._item_to_snapshot(item)

        except Exception as e:
            print(f"Error retrieving latest snapshot: {e}")
            return None
    
    def get_snapshot_before_timestamp(self, before_timestamp: int) -> Optional[ForecastSnapshot]:
        """
        Get the most recent snapshot before a given timestamp.
        
        Args:
            before_timestamp: Unix timestamp
            
        Returns:
            ForecastSnapshot or None
        """
        if not self.history_table:
            return None
            
        try:
            response = self.history_table.scan(
                FilterExpression='#ts < :timestamp',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={':timestamp': before_timestamp},
                Limit=10  # Get a few to find the most recent
            )
            
            items = response.get('Items', [])
            if not items:
                return None
            
            # Sort by timestamp and get most recent
            items.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            return self._item_to_snapshot(items[0])
            
        except Exception as e:
            print(f"Error retrieving snapshot before timestamp {before_timestamp}: {e}")
            return None
    
    def _item_to_snapshot(self, item: Dict[str, Any]) -> ForecastSnapshot:
        """Convert DynamoDB item to ForecastSnapshot object."""
        teams = []
        for team_data in item.get('teams', []):
            position = ForecastPosition(
                team_name=team_data.get('team_name', ''),
                position=team_data.get('position', 0),
                points=team_data.get('points', 0.0),
                played=team_data.get('played', 0),
                won=team_data.get('won', 0),
                drawn=team_data.get('drawn', 0),
                lost=team_data.get('lost', 0),
                goals_for=team_data.get('goals_for', 0),
                goals_against=team_data.get('goals_against', 0),
                goal_difference=team_data.get('goal_difference', 0)
            )
            teams.append(position)
        
        return ForecastSnapshot(
            timestamp=item.get('timestamp', 0),
            season=item.get('season', ''),
            teams=teams,
            context=item.get('context')
        )
    
    def detect_position_changes(self, previous_snapshot: ForecastSnapshot, 
                              current_snapshot: ForecastSnapshot) -> List[PositionChange]:
        """
        Detect position changes between two snapshots.
        
        Args:
            previous_snapshot: Previous forecast snapshot
            current_snapshot: Current forecast snapshot
            
        Returns:
            List of PositionChange objects
        """
        changes = []
        
        # Create lookup dictionaries for easy comparison
        previous_positions = {team.team_name: team for team in previous_snapshot.teams}
        current_positions = {team.team_name: team for team in current_snapshot.teams}
        
        # Check each team for position changes
        for team_name, current_team in current_positions.items():
            previous_team = previous_positions.get(team_name)
            
            if not previous_team:
                # New team (shouldn't happen in EPL, but handle gracefully)
                continue
            
            if previous_team.position != current_team.position:
                change = PositionChange(
                    team_name=team_name,
                    previous_position=previous_team.position,
                    new_position=current_team.position,
                    previous_points=previous_team.points,
                    new_points=current_team.points,
                    change_context=current_snapshot.context or "Position update",
                    timestamp=current_snapshot.timestamp
                )
                changes.append(change)
        
        print(f"Detected {len(changes)} position changes between snapshots")
        return changes
    
    def cleanup_old_snapshots(self, days_to_keep: int = 90):
        """
        Clean up snapshots older than specified days (already handled by TTL, but can be used for manual cleanup).
        
        Args:
            days_to_keep: Number of days of history to keep
        """
        if not self.history_table:
            return
            
        cutoff_timestamp = int(datetime.now(timezone.utc).timestamp()) - (days_to_keep * 24 * 60 * 60)
        
        try:
            # Scan for old items (this is expensive, so TTL is preferred)
            response = self.history_table.scan(
                FilterExpression='#ts < :cutoff',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={':cutoff': cutoff_timestamp},
                ProjectionExpression='snapshot_id'
            )
            
            # Delete old items in batches
            with self.history_table.batch_writer() as batch:
                for item in response.get('Items', []):
                    batch.delete_item(Key={'snapshot_id': item['snapshot_id']})
            
            print(f"Cleaned up {len(response.get('Items', []))} old snapshots")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")


# Global instance for use in Lambda functions
forecast_history_manager = ForecastHistoryManager()