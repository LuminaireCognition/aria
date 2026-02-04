"""
Activity Signal for Interest Engine v2.

Scores based on activity patterns like gatecamps and kill spikes.

Prefetch capable: NO (requires activity pattern analysis)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import SignalScore
from ..providers.base import BaseSignalProvider

if TYPE_CHECKING:
    from ...models import ProcessedKill


class ActivitySignal(BaseSignalProvider):
    """
    Activity pattern-based scoring signal.

    Detects and scores dangerous activity patterns:
    - Gatecamps (multiple kills in short time at same location)
    - Kill spikes (sudden activity increase)
    - Sustained activity (ongoing elevated kills)

    Config:
        gatecamp: {"enabled": bool, "score": float, "min_confidence": str}
        spike: {"enabled": bool, "score": float, "threshold": float}
        sustained: {"enabled": bool, "score": float, "window_minutes": int}

    Prefetch capable: NO (requires activity history analysis)
    """

    _name = "activity"
    _category = "activity"
    _prefetch_capable = False

    # Default scores for activity patterns
    DEFAULT_GATECAMP_SCORE = 0.9
    DEFAULT_SPIKE_SCORE = 0.7
    DEFAULT_SUSTAINED_SCORE = 0.5

    def score(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> SignalScore:
        """Score based on activity patterns."""
        # Get activity context from config
        gatecamp_status = config.get("gatecamp_status")
        activity_data = config.get("activity_data")

        if not gatecamp_status and not activity_data:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="No activity data available",
                prefetch_capable=False,
            )

        scores = []
        reasons = []

        # Check gatecamp
        gatecamp_config = config.get("gatecamp", {"enabled": True})
        if gatecamp_config.get("enabled", True) and gatecamp_status:
            confidence = getattr(gatecamp_status, "confidence", None)
            min_confidence = gatecamp_config.get("min_confidence", "medium")

            confidence_levels = {"low": 1, "medium": 2, "high": 3}
            if confidence and confidence_levels.get(confidence, 0) >= confidence_levels.get(
                min_confidence, 2
            ):
                score = gatecamp_config.get("score", self.DEFAULT_GATECAMP_SCORE)
                scores.append(score)
                reasons.append(f"Gatecamp ({confidence})")

        # Check spike
        spike_config = config.get("spike", {"enabled": True})
        if spike_config.get("enabled", True) and activity_data:
            spike_detected = activity_data.get("spike_detected", False)
            if spike_detected:
                score = spike_config.get("score", self.DEFAULT_SPIKE_SCORE)
                scores.append(score)
                reasons.append("Activity spike")

        # Check sustained activity
        sustained_config = config.get("sustained", {"enabled": True})
        if sustained_config.get("enabled", True) and activity_data:
            sustained_kills = activity_data.get("sustained_kills", 0)
            threshold = sustained_config.get("threshold", 5)

            if sustained_kills >= threshold:
                score = sustained_config.get("score", self.DEFAULT_SUSTAINED_SCORE)
                scores.append(score)
                reasons.append(f"Sustained activity ({sustained_kills} kills)")

        if not scores:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="No notable activity patterns",
                prefetch_capable=False,
            )

        # Take maximum score
        final_score = max(scores)
        reason = "; ".join(reasons)

        return SignalScore(
            signal=self._name,
            score=final_score,
            reason=reason,
            prefetch_capable=False,
            raw_value={"patterns": reasons},
        )

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate activity signal config."""
        errors = []

        for pattern in ("gatecamp", "spike", "sustained"):
            pattern_config = config.get(pattern, {})
            if not isinstance(pattern_config, dict):
                errors.append(f"'{pattern}' config must be a dictionary")
                continue

            if "score" in pattern_config:
                score = pattern_config["score"]
                if not isinstance(score, (int, float)) or not (0 <= score <= 1):
                    errors.append(f"'{pattern}.score' must be between 0 and 1")

        # Validate gatecamp confidence
        gatecamp_config = config.get("gatecamp", {})
        if "min_confidence" in gatecamp_config:
            confidence = gatecamp_config["min_confidence"]
            if confidence not in ("low", "medium", "high"):
                errors.append(
                    f"gatecamp.min_confidence must be low/medium/high, got '{confidence}'"
                )

        return errors
