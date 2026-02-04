"""
Assets Signal for Interest Engine v2.

Scores kills near corp structures and offices.

Prefetch capable: NO (requires asset location lookup)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import SignalScore
from ..providers.base import BaseSignalProvider

if TYPE_CHECKING:
    from ...models import ProcessedKill


class AssetSignal(BaseSignalProvider):
    """
    Corp asset-based scoring signal.

    Scores kills occurring in systems with corp structures or offices.

    Config:
        structures: {"enabled": bool, "score": float}
        offices: {"enabled": bool, "score": float}
        structure_systems: List of system IDs with corp structures
        office_systems: List of system IDs with corp offices

    Prefetch capable: NO (requires corp asset data)
    """

    _name = "assets"
    _category = "assets"
    _prefetch_capable = False

    DEFAULT_STRUCTURE_SCORE = 1.0
    DEFAULT_OFFICE_SCORE = 0.8

    def score(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> SignalScore:
        """Score based on asset proximity."""
        structure_systems = set(config.get("structure_systems", []))
        office_systems = set(config.get("office_systems", []))

        if not structure_systems and not office_systems:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="No asset systems configured",
                prefetch_capable=False,
            )

        # Check structures first (higher priority)
        structure_config = config.get("structures", {"enabled": True})
        if structure_config.get("enabled", True) and system_id in structure_systems:
            score = structure_config.get("score", self.DEFAULT_STRUCTURE_SCORE)
            return SignalScore(
                signal=self._name,
                score=score,
                reason="System has corp structure",
                prefetch_capable=False,
                raw_value={"asset_type": "structure"},
            )

        # Check offices
        office_config = config.get("offices", {"enabled": True})
        if office_config.get("enabled", True) and system_id in office_systems:
            score = office_config.get("score", self.DEFAULT_OFFICE_SCORE)
            return SignalScore(
                signal=self._name,
                score=score,
                reason="System has corp office",
                prefetch_capable=False,
                raw_value={"asset_type": "office"},
            )

        return SignalScore(
            signal=self._name,
            score=0.0,
            reason="No corp assets in system",
            prefetch_capable=False,
        )

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate assets signal config."""
        errors = []

        for asset_type in ("structures", "offices"):
            asset_config = config.get(asset_type, {})
            if not isinstance(asset_config, dict):
                errors.append(f"'{asset_type}' config must be a dictionary")
                continue

            if "score" in asset_config:
                score = asset_config["score"]
                if not isinstance(score, (int, float)) or not (0 <= score <= 1):
                    errors.append(f"'{asset_type}.score' must be between 0 and 1")

        return errors
