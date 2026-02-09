"""
Time Signal for Interest Engine v2.

Scores based on time-of-day windows and activity patterns.

Prefetch capable: YES (timestamp available in RedisQ)
"""

from __future__ import annotations

from datetime import datetime, timezone
from datetime import time as dt_time
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from ..models import SignalScore
from ..providers.base import BaseSignalProvider

if TYPE_CHECKING:
    from ...models import ProcessedKill


class TimeSignal(BaseSignalProvider):
    """
    Time-based scoring signal.

    Scores kills based on when they occurred relative to configured windows.

    Config:
        windows: List of time windows with scores
                 [{"start": "18:00", "end": "23:00", "score": 1.0, "label": "Prime time"}]
        timezone: Timezone for window evaluation (default: UTC)
        default_score: Score when outside all windows (default: 0.5)

    Prefetch capable: YES (kill timestamp in RedisQ)
    """

    _name = "time"
    _category = "time"
    _prefetch_capable = True

    DEFAULT_SCORE = 0.5

    def score(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> SignalScore:
        """Score based on kill time."""
        windows = config.get("windows", [])

        if not windows:
            return SignalScore(
                signal=self._name,
                score=1.0,  # No windows = no time filtering
                reason="No time windows configured",
                prefetch_capable=True,
            )

        # Get kill time
        if kill is None:
            # Use current time for prefetch
            kill_time = datetime.now(timezone.utc)
        else:
            kill_time = kill.kill_time
            if kill_time.tzinfo is None:
                kill_time = kill_time.replace(tzinfo=timezone.utc)

        # Convert to configured timezone
        tz_str = config.get("timezone", "UTC")
        try:
            tz = ZoneInfo(tz_str)
            local_time = kill_time.astimezone(tz)
        except Exception:
            local_time = kill_time

        current_time = local_time.time()

        # Check each window
        for window in windows:
            try:
                start = _parse_time(window.get("start", "00:00"))
                end = _parse_time(window.get("end", "23:59"))

                if _time_in_window(current_time, start, end):
                    score = window.get("score", 1.0)
                    label = window.get("label", f"{start}-{end}")
                    return SignalScore(
                        signal=self._name,
                        score=score,
                        reason=f"In time window: {label}",
                        prefetch_capable=True,
                        raw_value={"time": current_time.isoformat(), "window": label},
                    )
            except Exception:
                continue

        # Outside all windows
        default_score = config.get("default_score", self.DEFAULT_SCORE)
        return SignalScore(
            signal=self._name,
            score=default_score,
            reason="Outside configured time windows",
            prefetch_capable=True,
            raw_value={"time": current_time.isoformat()},
        )

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate time signal config."""
        errors = []
        windows = config.get("windows", [])

        for i, window in enumerate(windows):
            if not isinstance(window, dict):
                errors.append(f"windows[{i}] must be a dictionary")
                continue

            for field in ("start", "end"):
                if field not in window:
                    errors.append(f"windows[{i}] missing '{field}'")
                else:
                    try:
                        _parse_time(window[field])
                    except ValueError:
                        errors.append(f"windows[{i}].{field} must be in HH:MM format")

            if "score" in window:
                score = window["score"]
                if not isinstance(score, (int, float)) or not (0 <= score <= 1):
                    errors.append(f"windows[{i}].score must be between 0 and 1")

        # Validate timezone
        tz_str = config.get("timezone", "UTC")
        try:
            ZoneInfo(tz_str)
        except Exception:
            errors.append(f"Invalid timezone: '{tz_str}'")

        return errors


def _parse_time(time_str: str) -> dt_time:
    """Parse HH:MM time string."""
    if not time_str or len(time_str) < 4:
        raise ValueError(f"Invalid time format: {time_str}")

    parts = time_str.split(":")
    if len(parts) < 2:
        raise ValueError(f"Invalid time format: {time_str}")

    hours = int(parts[0])
    minutes = int(parts[1])

    return dt_time(hour=hours, minute=minutes)


def _time_in_window(check: dt_time, start: dt_time, end: dt_time) -> bool:
    """Check if time is within window (handles overnight windows)."""
    if start <= end:
        # Normal window (e.g., 09:00-17:00)
        return start <= check <= end
    else:
        # Overnight window (e.g., 22:00-06:00)
        return check >= start or check <= end
