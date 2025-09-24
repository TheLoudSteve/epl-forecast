#!/usr/bin/env python3
"""
Simple test of dynamic mode detection logic without AWS dependencies
"""

def detect_dynamic_scheduling_mode(event):
    """
    Simplified version of the detection logic for testing
    """
    try:
        if isinstance(event, dict):
            if event.get('dynamic_scheduling') is True:
                return True
            if event.get('source') == 'schedule-manager':
                return True
            if 'match_info' in event:
                return True
        return False
    except Exception as e:
        print(f"Error detecting dynamic mode, defaulting to legacy: {e}")
        return False


def main():
    print("🧪 Testing dynamic mode detection logic...")

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
        ({'source': 'aws.events'}, False, "AWS Events source"),
    ]

    passed = 0
    failed = 0

    for event, expected, description in test_cases:
        result = detect_dynamic_scheduling_mode(event)
        mode = "dynamic" if result else "legacy"
        expected_mode = "dynamic" if expected else "legacy"

        if result == expected:
            print(f"   ✅ {description}: {mode} mode")
            passed += 1
        else:
            print(f"   ❌ {description}: {mode} mode (expected {expected_mode})")
            failed += 1

    print(f"\n📊 Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 Dynamic mode detection logic working correctly!")
        return True
    else:
        print("⚠️  Detection logic needs review")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)