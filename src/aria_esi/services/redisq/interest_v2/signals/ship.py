"""
Ship Signal for Interest Engine v2.

Scores kills based on victim ship class and characteristics.

Prefetch capable: YES (victim ship_type_id available in RedisQ)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import SignalScore
from ..providers.base import BaseSignalProvider

if TYPE_CHECKING:
    from ...models import ProcessedKill


# Ship class definitions for matching
SHIP_CLASSES = {
    # Industrial ships
    "freighter": {34328, 20183, 20187, 20185, 20189},
    "jump_freighter": {28844, 28846, 28848, 28850},
    "industrial": {
        648,  # Badger
        649,  # Tayra
        650,  # Sigil
        651,  # Bestower
        652,  # Nereus
        653,  # Kryos
        654,  # Epithal
        655,  # Miasmos
        656,  # Hoarder
        657,  # Wreathe
        658,  # Mammoth
        659,  # Iteron Mark V
        # ... more industrials
    },
    "dst": {12753, 12729, 12733, 12743},  # Deep Space Transports
    "blockade_runner": {12731, 12735, 12745, 12747},
    "orca": {28606},
    "bowhead": {42246},
    "rorqual": {28352},
    # Mining ships
    "mining_barge": {17476, 17478, 17480},  # Procurer, Retriever, Covetor
    "exhumer": {22544, 22546, 22548},  # Skiff, Mackinaw, Hulk
    "mining_frigate": {32880, 33697},  # Venture, Endurance
    # Capital ships
    "carrier": {23757, 23911, 23915, 24483},
    "supercarrier": {23919, 22852, 23913, 23917},
    "dreadnought": {19720, 19722, 19724, 19726},
    "titan": {671, 3764, 11567, 45649},
    "fax": {37604, 37605, 37606, 37607},  # Force Auxiliaries
    # Pods
    "capsule": {670, 33328},
    # Structures (for reference)
    "citadel": {35832, 35833, 35834},  # Astrahus, Fortizar, Keepstar
}

# Ship group IDs for broader matching
SHIP_GROUPS = {
    "freighter": 513,
    "jump_freighter": 902,
    "industrial": 28,
    "capsule": 29,
    "carrier": 547,
    "supercarrier": 659,
    "dreadnought": 485,
    "titan": 30,
    "fax": 1538,
}


class ShipSignal(BaseSignalProvider):
    """
    Ship class-based scoring signal.

    Scores kills based on victim ship type matching preferred or excluded classes.

    Config:
        prefer: List of ship classes to score higher
        exclude: List of ship classes to score lower/filter
        prefer_score: Score for preferred ships (default: 1.0)
        exclude_score: Score for excluded ships (default: 0.0)
        default_score: Score for unmatched ships (default: 0.5)
        capitals_only: If True, only match capital ships

    Prefetch capable: YES (victim ship_type_id in RedisQ)
    """

    _name = "ship"
    _category = "ship"
    _prefetch_capable = True

    DEFAULT_PREFER_SCORE = 1.0
    DEFAULT_EXCLUDE_SCORE = 0.0
    DEFAULT_SCORE = 0.5

    def score(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> SignalScore:
        """Score based on ship class."""
        if kill is None:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="No kill data",
                prefetch_capable=True,
            )

        ship_type_id = kill.victim_ship_type_id
        if ship_type_id is None:
            return SignalScore(
                signal=self._name,
                score=config.get("default_score", self.DEFAULT_SCORE),
                reason="Unknown ship type",
                prefetch_capable=True,
            )

        # Check exclusions first
        exclude = config.get("exclude", [])
        for ship_class in exclude:
            if self._matches_class(ship_type_id, ship_class, config):
                score = config.get("exclude_score", self.DEFAULT_EXCLUDE_SCORE)
                return SignalScore(
                    signal=self._name,
                    score=score,
                    reason=f"Excluded ship class: {ship_class}",
                    prefetch_capable=True,
                    raw_value={"type_id": ship_type_id, "class": ship_class},
                )

        # Check preferences
        prefer = config.get("prefer", [])
        for ship_class in prefer:
            if self._matches_class(ship_type_id, ship_class, config):
                score = config.get("prefer_score", self.DEFAULT_PREFER_SCORE)
                return SignalScore(
                    signal=self._name,
                    score=score,
                    reason=f"Preferred ship class: {ship_class}",
                    prefetch_capable=True,
                    raw_value={"type_id": ship_type_id, "class": ship_class},
                )

        # Check capitals_only filter
        if config.get("capitals_only", False):
            capital_classes = {"carrier", "supercarrier", "dreadnought", "titan", "fax", "rorqual"}
            for cap_class in capital_classes:
                if self._matches_class(ship_type_id, cap_class, config):
                    return SignalScore(
                        signal=self._name,
                        score=config.get("prefer_score", self.DEFAULT_PREFER_SCORE),
                        reason=f"Capital ship: {cap_class}",
                        prefetch_capable=True,
                        raw_value={"type_id": ship_type_id, "class": cap_class},
                    )
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="Not a capital ship",
                prefetch_capable=True,
            )

        # Default score
        return SignalScore(
            signal=self._name,
            score=config.get("default_score", self.DEFAULT_SCORE),
            reason="No ship class match",
            prefetch_capable=True,
            raw_value={"type_id": ship_type_id},
        )

    def _matches_class(
        self,
        ship_type_id: int,
        ship_class: str,
        config: dict[str, Any],
    ) -> bool:
        """Check if ship type matches a class."""
        ship_class = ship_class.lower().replace(" ", "_").replace("-", "_")

        # Check against our built-in mappings
        type_ids = SHIP_CLASSES.get(ship_class, set())
        if ship_type_id in type_ids:
            return True

        # Check group ID if provided in config
        group_id = config.get("victim_group_id")
        if group_id is not None:
            expected_group = SHIP_GROUPS.get(ship_class)
            if expected_group is not None and group_id == expected_group:
                return True

        return False

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate ship signal config."""
        errors = []

        valid_classes = set(SHIP_CLASSES.keys())

        for field in ("prefer", "exclude"):
            classes = config.get(field, [])
            for ship_class in classes:
                normalized = ship_class.lower().replace(" ", "_").replace("-", "_")
                if normalized not in valid_classes:
                    errors.append(
                        f"Unknown ship class in {field}: '{ship_class}'. "
                        f"Valid classes: {sorted(valid_classes)}"
                    )

        for score_field in ("prefer_score", "exclude_score", "default_score"):
            if score_field in config:
                score = config[score_field]
                if not isinstance(score, (int, float)) or not (0 <= score <= 1):
                    errors.append(f"'{score_field}' must be between 0 and 1")

        return errors
