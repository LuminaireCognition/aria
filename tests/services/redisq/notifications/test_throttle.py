"""
Tests for notification throttle manager.
"""

from __future__ import annotations

import time

from aria_esi.services.redisq.notifications.throttle import ThrottleManager
from aria_esi.services.redisq.notifications.triggers import TriggerType


class TestThrottleManager:
    """Tests for ThrottleManager."""

    def test_first_send_allowed(self):
        """First notification for a system/trigger should always be allowed."""
        throttle = ThrottleManager(throttle_minutes=5)

        assert throttle.should_send(30000142, TriggerType.WATCHLIST_ACTIVITY) is True
        assert throttle.should_send(30000142, TriggerType.GATECAMP_DETECTED) is True
        assert throttle.should_send(30000143, TriggerType.WATCHLIST_ACTIVITY) is True

    def test_duplicate_throttled(self):
        """Duplicate notification within window should be throttled."""
        throttle = ThrottleManager(throttle_minutes=5)

        # First send allowed
        assert throttle.should_send(30000142, TriggerType.WATCHLIST_ACTIVITY) is True
        throttle.record_sent(30000142, TriggerType.WATCHLIST_ACTIVITY)

        # Duplicate should be throttled
        assert throttle.should_send(30000142, TriggerType.WATCHLIST_ACTIVITY) is False

    def test_different_systems_independent(self):
        """Different systems should have independent throttles."""
        throttle = ThrottleManager(throttle_minutes=5)

        # Record send for system 1
        throttle.record_sent(30000142, TriggerType.WATCHLIST_ACTIVITY)

        # System 2 should still be allowed
        assert throttle.should_send(30000143, TriggerType.WATCHLIST_ACTIVITY) is True

    def test_different_triggers_independent(self):
        """Different trigger types should have independent throttles."""
        throttle = ThrottleManager(throttle_minutes=5)

        # Record watchlist trigger
        throttle.record_sent(30000142, TriggerType.WATCHLIST_ACTIVITY)

        # Gatecamp trigger should still be allowed
        assert throttle.should_send(30000142, TriggerType.GATECAMP_DETECTED) is True

    def test_remaining_seconds(self):
        """Get remaining throttle time."""
        throttle = ThrottleManager(throttle_minutes=5)

        # No throttle - should return 0
        assert throttle.get_remaining_seconds(30000142, TriggerType.WATCHLIST_ACTIVITY) == 0.0

        # After recording, should return approximately throttle window
        throttle.record_sent(30000142, TriggerType.WATCHLIST_ACTIVITY)
        remaining = throttle.get_remaining_seconds(30000142, TriggerType.WATCHLIST_ACTIVITY)
        assert 298 <= remaining <= 300  # ~5 minutes with small tolerance

    def test_active_throttles_count(self):
        """Count active (non-expired) throttles."""
        throttle = ThrottleManager(throttle_minutes=5)

        assert throttle.active_throttles == 0

        throttle.record_sent(30000142, TriggerType.WATCHLIST_ACTIVITY)
        assert throttle.active_throttles == 1

        throttle.record_sent(30000143, TriggerType.GATECAMP_DETECTED)
        assert throttle.active_throttles == 2

    def test_cleanup_expired(self):
        """Cleanup removes expired entries."""
        throttle = ThrottleManager(throttle_minutes=0)  # Immediate expiry for testing

        # Record some sends
        throttle._last_sent[(30000142, "watchlist_activity")] = time.time() - 1000

        # Cleanup should remove old entries
        removed = throttle.cleanup_expired()
        assert removed == 1
        assert throttle.active_throttles == 0


class TestThrottleManagerEdgeCases:
    """Edge case tests for ThrottleManager."""

    def test_zero_throttle_window(self):
        """Zero throttle window allows immediate re-sends."""
        throttle = ThrottleManager(throttle_minutes=0)

        throttle.record_sent(30000142, TriggerType.WATCHLIST_ACTIVITY)

        # Should be allowed immediately with 0 throttle
        assert throttle.should_send(30000142, TriggerType.WATCHLIST_ACTIVITY) is True

    def test_large_throttle_window(self):
        """Large throttle window properly throttles."""
        throttle = ThrottleManager(throttle_minutes=60)

        throttle.record_sent(30000142, TriggerType.WATCHLIST_ACTIVITY)

        # Should be throttled with large window
        assert throttle.should_send(30000142, TriggerType.WATCHLIST_ACTIVITY) is False
        remaining = throttle.get_remaining_seconds(30000142, TriggerType.WATCHLIST_ACTIVITY)
        assert remaining > 3500  # ~59 minutes
