"""
Shared forecast calculation logic for EPL Forecast

This module provides shared calculation logic used by both scheduled_data_fetcher
and live_match_fetcher to avoid code duplication.

EPLF-64: Extract shared forecast calculation logic to common module
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any


def calculate_forecasts(epl_data: Dict[str, Any], update_type: str = 'scheduled') -> Dict[str, Any]:
    """
    Calculate forecasted final table based on points per game

    Args:
        epl_data: Raw EPL standings data from football-data.org API
        update_type: Type of update ('scheduled' or 'live_match')

    Returns:
        Dict containing teams with forecast data and metadata

    football-data.org API structure:
    {
        "standings": [
            {
                "type": "TOTAL",
                "table": [
                    {
                        "position": 1,
                        "team": {"name": "Arsenal", ...},
                        "playedGames": 10,
                        "won": 7,
                        "draw": 2,
                        "lost": 1,
                        "points": 23,
                        "goalsFor": 20,
                        "goalsAgainst": 10,
                        "goalDifference": 10
                    }
                ]
            }
        ]
    }
    """
    teams = []

    # Extract TOTAL standings table from football-data.org response
    table_data = []
    if 'standings' in epl_data:
        for standing in epl_data['standings']:
            if standing.get('type') == 'TOTAL':
                table_data = standing.get('table', [])
                break

    # Process each team
    for team_data in table_data:
        played = team_data.get('playedGames', 0)
        points = team_data.get('points', 0)

        if played > 0:
            points_per_game = points / played
            forecasted_points = points_per_game * 38
        else:
            points_per_game = 0
            forecasted_points = 0

        team = {
            'name': team_data.get('team', {}).get('name', ''),
            'played': played,
            'won': team_data.get('won', 0),
            'drawn': team_data.get('draw', 0),
            'lost': team_data.get('lost', 0),
            'for': team_data.get('goalsFor', 0),
            'against': team_data.get('goalsAgainst', 0),
            'goal_difference': team_data.get('goalDifference', 0),
            'points': points,
            'points_per_game': Decimal(str(round(points_per_game, 2))),
            'forecasted_points': Decimal(str(round(forecasted_points, 1))),
            'current_position': team_data.get('position', 0)
        }
        teams.append(team)

    # Sort by forecasted points, then goal difference, then goals for
    teams.sort(key=lambda x: (-x['forecasted_points'], -x['goal_difference'], -x['for']))

    # Add forecasted position
    for i, team in enumerate(teams):
        team['forecasted_position'] = i + 1

    return {
        'teams': teams,
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'total_teams': len(teams),
        'update_type': update_type
    }
