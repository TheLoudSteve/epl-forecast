#!/usr/bin/env python3
"""
Test script for Dynamic vs Legacy execution mode detection in LiveMatchFetcher

This validates that the LiveMatchFetcher correctly detects and handles both
dynamic scheduling (from Schedule Manager) and legacy polling modes.
"""

import sys
import os
from unittest.mock import Mock, patch

# Add backend to path for imports
sys.path.append(os.path.dirname(__file__))

def test_dynamic_mode_detection():
    """Test dynamic mode detection logic"""
    print("🧪 Testing dynamic mode detection...")

    from live_match_fetcher import detect_dynamic_scheduling_mode

    test_cases = [
        # Dynamic mode cases
        ({'dynamic_scheduling': True}, True, "Direct dynamic flag"),
        ({'source': 'schedule-manager'}, True, "Schedule Manager source"),
        ({'match_info': {'summary': 'Arsenal vs City'}}, True, "Match info present"),
        ({'source': 'schedule-manager', 'dynamic_scheduling': True}, True, "Multiple indicators"),

        # Legacy mode cases
        ({}, False, "Empty event"),
        ({'source': 'eventbridge'}, False, "EventBridge source"),
        ({'dynamic_scheduling': False}, False, "Explicit legacy flag"),
        ({'other_data': 'value'}, False, "Other data"),
    ]

    passed = 0
    failed = 0

    for event, expected, description in test_cases:
        result = detect_dynamic_scheduling_mode(event)
        if result == expected:
            print(f"   ✅ {description}: {result} (expected)")
            passed += 1
        else:
            print(f"   ❌ {description}: {result} (expected {expected})")
            failed += 1

    print(f"   Dynamic mode detection: {passed} passed, {failed} failed\n")
    return failed == 0


def test_event_payloads():
    """Test realistic event payloads"""
    print("🧪 Testing realistic event payloads...")

    from live_match_fetcher import detect_dynamic_scheduling_mode

    # Schedule Manager event (dynamic)
    schedule_manager_event = {
        'source': 'schedule-manager',
        'match_info': {
            'summary': 'Arsenal vs Manchester City',
            'start_time': '2025-09-25T14:30:00+00:00',
            'rule_name': 'epl-dynamic-match-20250925-1430-arsenal-vs-city'
        },
        'dynamic_scheduling': True
    }

    # EventBridge timer event (legacy)
    eventbridge_timer_event = {
        'version': '0',
        'id': 'timer-event',
        'detail-type': 'Scheduled Event',
        'source': 'aws.events',
        'account': '123456789012',
        'time': '2025-09-25T14:30:00Z',
        'region': 'us-west-2',
        'detail': {}
    }

    # Manual invocation event (legacy)
    manual_event = {}

    test_cases = [
        (schedule_manager_event, True, "Schedule Manager event"),
        (eventbridge_timer_event, False, "EventBridge timer event"),
        (manual_event, False, "Manual invocation")
    ]

    passed = 0
    failed = 0

    for event, expected, description in test_cases:
        result = detect_dynamic_scheduling_mode(event)
        mode = "dynamic" if result else "legacy"
        expected_mode = "dynamic" if expected else "legacy"

        if result == expected:
            print(f"   ✅ {description}: {mode} mode detected")
            passed += 1
        else:
            print(f"   ❌ {description}: {mode} mode detected (expected {expected_mode})")
            failed += 1

    print(f"   Event payload tests: {passed} passed, {failed} failed\n")
    return failed == 0


def test_backwards_compatibility():
    """Test that existing functionality is preserved"""
    print("🧪 Testing backwards compatibility...")

    # Simulate existing EventBridge timer events (the way it currently works)
    existing_events = [
        {},  # Empty event (manual trigger)
        {'source': 'aws.events'},  # EventBridge event
        {'Records': []},  # S3 event format (if used)
    ]

    from live_match_fetcher import detect_dynamic_scheduling_mode

    all_legacy = True
    for i, event in enumerate(existing_events):
        is_dynamic = detect_dynamic_scheduling_mode(event)
        if is_dynamic:
            print(f"   ❌ Event {i+1} incorrectly detected as dynamic: {event}")
            all_legacy = False
        else:
            print(f"   ✅ Event {i+1} correctly detected as legacy: {event}")

    if all_legacy:
        print(f"   ✅ All existing event types correctly default to legacy mode")
    else:
        print(f"   ❌ Some existing events incorrectly detected as dynamic")

    print(f"   Backwards compatibility: {'PASS' if all_legacy else 'FAIL'}\n")
    return all_legacy


def main():
    """Run all tests"""
    print("🚀 LiveMatchFetcher Dynamic/Legacy Mode Tests")
    print("=" * 60)

    tests = [
        test_dynamic_mode_detection,
        test_event_payloads,
        test_backwards_compatibility
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__} failed with error: {e}")

    print("📊 Test Summary")
    print(f"Tests Passed: {passed}")
    print(f"Tests Failed: {failed}")

    if failed == 0:
        print("🎉 All tests passed! LiveMatchFetcher is ready for dual-mode operation.")
        print("\n📋 Capabilities Validated:")
        print("   ✅ Dynamic mode detection works correctly")
        print("   ✅ Legacy mode preserved for existing triggers")
        print("   ✅ Backwards compatibility maintained")
        print("   ✅ Ready for Schedule Manager integration")
        return True
    else:
        print("⚠️  Some tests failed. Review before deployment.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)