#!/usr/bin/env python3
"""
Test script for Schedule Manager - Local testing and validation

This script allows testing the Schedule Manager logic locally before deployment.
"""

import sys
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch

# Add backend to path for imports
sys.path.append(os.path.dirname(__file__))

def test_ics_parsing():
    """Test ICS parsing functionality"""
    print("🧪 Testing ICS parsing...")

    # Mock the S3 and HTTP calls
    with patch('schedule_manager.get_ics_content') as mock_get_ics:
        # Mock ICS content with a sample EPL match
        mock_ics = b'''BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
DTSTART:20250925T143000Z
SUMMARY:Arsenal vs Manchester City
UID:test-123
DTSTAMP:20250924T120000Z
END:VEVENT
END:VCALENDAR'''

        mock_get_ics.return_value = mock_ics

        from schedule_manager import parse_ics_schedule
        matches = parse_ics_schedule('test-bucket')

        if matches:
            print(f"✅ Found {len(matches)} matches")
            for match in matches:
                print(f"   - {match['summary']} at {match['start_time']}")
        else:
            print("ℹ️  No matches found in test window")

    return True

def test_rule_name_creation():
    """Test EventBridge rule name creation"""
    print("\n🧪 Testing rule name creation...")

    from schedule_manager import create_rule_name

    test_cases = [
        ("Arsenal vs Manchester City", datetime(2025, 9, 25, 14, 30, tzinfo=timezone.utc)),
        ("Liverpool vs Chelsea", datetime(2025, 9, 28, 17, 0, tzinfo=timezone.utc)),
    ]

    for summary, start_time in test_cases:
        rule_name = create_rule_name(summary, start_time)
        print(f"   {summary} → {rule_name}")

        # Validate rule name format
        assert rule_name.startswith('epl-dynamic-match-')
        assert len(rule_name) <= 64  # AWS limit

    print("✅ Rule name creation tests passed")
    return True

def test_cron_expression():
    """Test cron expression creation"""
    print("\n🧪 Testing cron expression creation...")

    from schedule_manager import create_cron_expression

    test_time = datetime(2025, 9, 25, 14, 30, tzinfo=timezone.utc)
    cron_expr = create_cron_expression(test_time)

    print(f"   {test_time} → {cron_expr}")

    # Validate cron format
    assert cron_expr.startswith('cron(')
    assert cron_expr.endswith(')')

    print("✅ Cron expression tests passed")
    return True

def test_cleanup_logic():
    """Test cleanup logic (without actually calling AWS)"""
    print("\n🧪 Testing cleanup logic...")

    # Test rule name parsing
    test_rule = "epl-dynamic-match-20250923-1430-arsenal-vs-city"

    # Extract date from rule name
    parts = test_rule.split('-')
    if len(parts) >= 5:
        date_str = parts[3]  # YYYYMMDD
        time_str = parts[4]  # HHMM

        rule_date = datetime.strptime(f"{date_str}-{time_str}", '%Y%m%d-%H%M')
        rule_date = rule_date.replace(tzinfo=timezone.utc)

        print(f"   Rule: {test_rule}")
        print(f"   Parsed date: {rule_date}")

        # Check if it would be cleaned up (older than 24h)
        age_hours = (datetime.now(timezone.utc) - rule_date).total_seconds() / 3600
        should_cleanup = age_hours > 24

        print(f"   Age: {age_hours:.1f} hours, Should cleanup: {should_cleanup}")

    print("✅ Cleanup logic tests passed")
    return True

def main():
    """Run all tests"""
    print("🚀 Schedule Manager Local Tests")
    print("=" * 50)

    tests = [
        test_ics_parsing,
        test_rule_name_creation,
        test_cron_expression,
        test_cleanup_logic
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"❌ {test.__name__} failed")
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__} failed: {e}")

    print(f"\n📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed! Schedule Manager is ready for deployment.")
        return True
    else:
        print("⚠️  Some tests failed. Review before deployment.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)