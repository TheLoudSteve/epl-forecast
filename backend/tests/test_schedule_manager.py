from schedule_manager import is_match_event_summary


def test_match_summary_accepts_provider_badges_before_football_emoji():
    """Calendar badges must not prevent live-match polling from starting."""
    assert is_match_event_summary('🟣⚽️ Arsenal v Coventry City')
    assert is_match_event_summary('📰⚽️ Brentford v Tottenham Hotspur')
    assert is_match_event_summary('⚽️ Sunderland v Arsenal')


def test_match_summary_rejects_non_fixture_calendar_events():
    assert not is_match_event_summary('Premier League awards ceremony')
    assert not is_match_event_summary('⚽️ Fixture announcement')
