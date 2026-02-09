"""
Location Signals for Interest Engine v2.

Signals:
- GeographicSignal: Distance-based scoring from configured systems
- SecuritySignal: Security band matching (high/low/null/wh)

Both are prefetch-capable (system_id available in RedisQ).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import SignalScore
from ..providers.base import BaseSignalProvider

if TYPE_CHECKING:
    from ...models import ProcessedKill


class GeographicSignal(BaseSignalProvider):
    """
    Distance-based scoring from configured home/hunting/transit systems.

    Uses graph distance (jump count) to score proximity to operational areas.

    Config:
        systems: List of {"name": str, "id": int, "classification": str}
                 classification: "home", "hunting", or "transit"
        weights: Optional dict of classification -> {distance: weight}
                 Default weights provided per classification

    Prefetch capable: YES (system_id available)
    """

    _name = "geographic"
    _category = "location"
    _prefetch_capable = True

    # Default distance weights by classification
    DEFAULT_WEIGHTS = {
        "home": {0: 1.0, 1: 0.95, 2: 0.8, 3: 0.5},
        "hunting": {0: 1.0, 1: 0.85, 2: 0.5},
        "transit": {0: 0.7, 1: 0.3},
    }

    def score(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> SignalScore:
        """Score based on distance from configured systems."""
        systems = config.get("systems", [])
        if not systems:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="No systems configured",
                prefetch_capable=True,
            )

        # Get distance calculator from context
        get_distance = config.get("get_distance")
        if not get_distance:
            # Fallback: check if system is in configured list directly
            return self._score_direct_match(system_id, systems, config)

        # Find best score across all configured systems
        best_score = 0.0
        best_reason = "Outside monitored area"

        weights = config.get("weights", self.DEFAULT_WEIGHTS)

        for sys_config in systems:
            sys_id = sys_config.get("id")
            sys_name = sys_config.get("name", str(sys_id))
            classification = sys_config.get("classification", "home")

            if sys_id is None:
                continue

            try:
                distance = get_distance(sys_id, system_id)
            except Exception:
                continue

            if distance is None:
                continue

            # Get weight for this distance/classification
            class_weights = weights.get(classification, self.DEFAULT_WEIGHTS.get("home", {}))

            # Find applicable weight (highest distance that applies)
            score = 0.0
            for max_dist, weight in sorted(class_weights.items(), reverse=True):
                if distance <= max_dist:
                    score = weight
                    break

            if score > best_score:
                best_score = score
                if distance == 0:
                    best_reason = f"In {sys_name} ({classification})"
                else:
                    best_reason = f"{distance} jumps from {sys_name} ({classification})"

        return SignalScore(
            signal=self._name,
            score=best_score,
            reason=best_reason,
            prefetch_capable=True,
            raw_value={"system_id": system_id},
        )

    def _score_direct_match(
        self,
        system_id: int,
        systems: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> SignalScore:
        """Score when no distance function is available (direct ID match only)."""
        for sys_config in systems:
            sys_id = sys_config.get("id")
            sys_name = sys_config.get("name", str(sys_id))
            classification = sys_config.get("classification", "home")

            if sys_id == system_id:
                # Exact match - use weight for distance 0
                weights = config.get("weights", self.DEFAULT_WEIGHTS)
                class_weights = weights.get(classification, {})
                score = class_weights.get(0, 1.0)

                return SignalScore(
                    signal=self._name,
                    score=score,
                    reason=f"In {sys_name} ({classification})",
                    prefetch_capable=True,
                )

        return SignalScore(
            signal=self._name,
            score=0.0,
            reason="Outside monitored area",
            prefetch_capable=True,
        )

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate geographic signal config."""
        errors = []
        systems = config.get("systems", [])

        if not systems:
            errors.append("At least one system must be configured")
            return errors

        for i, sys in enumerate(systems):
            if "id" not in sys and "name" not in sys:
                errors.append(f"systems[{i}]: must have 'id' or 'name'")

            classification = sys.get("classification", "home")
            if classification not in ("home", "hunting", "transit"):
                errors.append(
                    f"systems[{i}]: classification must be home/hunting/transit, "
                    f"got '{classification}'"
                )

        return errors


class SecuritySignal(BaseSignalProvider):
    """
    Security band matching signal.

    Scores systems based on their security status matching configured preferences.

    Config:
        bands: List of security bands to match ("high", "low", "null", "wh")
        scores: Optional dict of band -> score (default 1.0 for match, 0.0 for no match)
        invert: If True, score 1.0 for NOT matching bands (exclude mode)

    Prefetch capable: YES (system_id -> security lookup)
    """

    _name = "security"
    _category = "location"
    _prefetch_capable = True

    def score(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> SignalScore:
        """Score based on security band matching."""
        bands = config.get("bands", [])
        if not bands:
            # No bands configured = no filtering
            return SignalScore(
                signal=self._name,
                score=1.0,
                reason="No security filter",
                prefetch_capable=True,
            )

        # Get security status from context or lookup
        security = config.get("security_status")
        if security is None:
            get_security = config.get("get_security")
            if get_security:
                try:
                    security = get_security(system_id)
                except Exception:
                    security = None

        if security is None:
            return SignalScore(
                signal=self._name,
                score=0.5,  # Unknown - neutral score
                reason="Security status unknown",
                prefetch_capable=True,
            )

        # Determine band from security value
        if security >= 0.5:
            band = "high"
        elif security > 0.0:
            band = "low"
        elif security <= -0.5:
            band = "wh"
        else:
            band = "null"

        # Normalize configured bands
        configured_bands = {b.lower() for b in bands}
        invert = config.get("invert", False)
        scores = config.get("scores", {})

        matched = band in configured_bands

        if invert:
            matched = not matched

        if matched:
            score = scores.get(band, 1.0)
            reason = f"Security band '{band}' matches"
        else:
            score = 0.0
            reason = f"Security band '{band}' not in {configured_bands}"

        return SignalScore(
            signal=self._name,
            score=score,
            reason=reason,
            prefetch_capable=True,
            raw_value={"security": security, "band": band},
        )

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate security signal config."""
        errors = []
        bands = config.get("bands", [])
        valid_bands = {"high", "low", "null", "wh"}

        for band in bands:
            if band.lower() not in valid_bands:
                errors.append(f"Unknown security band: '{band}'. Valid: {valid_bands}")

        return errors
