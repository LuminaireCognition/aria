"""
Notification Throttle Manager.

Prevents notification spam by tracking last sent time per (system, trigger_type) tuple.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .triggers import TriggerType


@dataclass
class ThrottleManager:
    """
    Manages notification throttling per (system_id, trigger_type).

    Prevents repeated notifications for the same system and trigger type
    within a configurable window.
    """

    throttle_minutes: int = 5
    _last_sent: dict[tuple[int, str], float] = field(default_factory=dict)

    def should_send(self, system_id: int, trigger_type: TriggerType) -> bool:
        """
        Check if a notification should be sent.

        Args:
            system_id: Solar system ID
            trigger_type: Type of trigger (watchlist, gatecamp, high_value)

        Returns:
            True if notification should be sent, False if throttled
        """
        key = (system_id, trigger_type.value)
        last_time = self._last_sent.get(key)

        if last_time is None:
            return True

        throttle_seconds = self.throttle_minutes * 60
        return (time.time() - last_time) >= throttle_seconds

    def record_sent(self, system_id: int, trigger_type: TriggerType) -> None:
        """
        Record that a notification was sent.

        Args:
            system_id: Solar system ID
            trigger_type: Type of trigger
        """
        key = (system_id, trigger_type.value)
        self._last_sent[key] = time.time()

    def cleanup_expired(self) -> int:
        """
        Remove expired throttle entries to prevent memory growth.

        Removes entries older than 2x the throttle window.

        Returns:
            Number of entries removed
        """
        expiry_seconds = self.throttle_minutes * 60 * 2
        cutoff = time.time() - expiry_seconds

        expired_keys = [key for key, ts in self._last_sent.items() if ts < cutoff]
        for key in expired_keys:
            del self._last_sent[key]

        return len(expired_keys)

    def get_remaining_seconds(self, system_id: int, trigger_type: TriggerType) -> float:
        """
        Get remaining throttle time for a system/trigger pair.

        Args:
            system_id: Solar system ID
            trigger_type: Type of trigger

        Returns:
            Seconds until throttle expires (0 if not throttled)
        """
        key = (system_id, trigger_type.value)
        last_time = self._last_sent.get(key)

        if last_time is None:
            return 0.0

        throttle_seconds = self.throttle_minutes * 60
        elapsed = time.time() - last_time
        remaining = throttle_seconds - elapsed

        return max(0.0, remaining)

    @property
    def active_throttles(self) -> int:
        """Get count of active (non-expired) throttle entries."""
        throttle_seconds = self.throttle_minutes * 60
        cutoff = time.time() - throttle_seconds
        return sum(1 for ts in self._last_sent.values() if ts >= cutoff)
