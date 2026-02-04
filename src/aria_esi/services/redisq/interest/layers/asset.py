"""
Asset Interest Layer.

Calculates interest based on corp structure and office locations.
Systems with corp assets automatically receive high interest.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .....core.logging import get_logger
from ..models import LayerScore
from .base import BaseLayer

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


# =============================================================================
# Default Interest Scores
# =============================================================================

STRUCTURE_INTEREST = 1.0  # Corp structures get max interest
OFFICE_INTEREST = 0.8  # Corp offices are important but less critical


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class AssetConfig:
    """Configuration for the asset layer."""

    # What types of assets to track
    structures: bool = True
    offices: bool = True

    # Interest scores per asset type
    structure_interest: float = STRUCTURE_INTEREST
    office_interest: float = OFFICE_INTEREST

    # How often to refresh from ESI (hours)
    refresh_hours: int = 4

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AssetConfig:
        """Create from config dict."""
        if not data:
            return cls()

        return cls(
            structures=data.get("structures", True),
            offices=data.get("offices", True),
            structure_interest=data.get("structure_interest", STRUCTURE_INTEREST),
            office_interest=data.get("office_interest", OFFICE_INTEREST),
            refresh_hours=data.get("refresh_hours", 4),
        )


# =============================================================================
# Asset Layer
# =============================================================================


@dataclass
class AssetLayer(BaseLayer):
    """
    Asset-based interest layer.

    Automatically includes systems containing corp assets:
    - Structures (Raitaru, Azbel, etc.): interest 1.0
    - Offices in NPC stations: interest 0.8

    This ensures corp infrastructure is always monitored without
    manual configuration.

    Asset locations are refreshed periodically from ESI.

    Example usage:
        layer = AssetLayer.from_config(config)
        await layer.refresh_from_esi(corp_id)
    """

    _name: str = "asset"
    config: AssetConfig = field(default_factory=AssetConfig)

    # Pre-computed asset locations: system_id -> asset_type
    _asset_systems: dict[int, str] = field(default_factory=dict)

    # Refresh tracking
    _last_refresh: float = 0.0
    _corp_id: int | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def total_systems(self) -> int:
        """Total number of systems with assets."""
        return len(self._asset_systems)

    def score_system(self, system_id: int) -> LayerScore:
        """
        Score a system based on asset presence.

        Args:
            system_id: Solar system ID

        Returns:
            LayerScore with asset-based interest
        """
        asset_type = self._asset_systems.get(system_id)

        if asset_type == "structure":
            return LayerScore(
                layer=self.name,
                score=self.config.structure_interest,
                reason="corp structure",
            )
        elif asset_type == "office":
            return LayerScore(
                layer=self.name,
                score=self.config.office_interest,
                reason="corp office",
            )

        return LayerScore(layer=self.name, score=0.0, reason=None)

    def needs_refresh(self) -> bool:
        """
        Check if asset data should be refreshed.

        Returns:
            True if refresh is needed
        """
        if self._last_refresh == 0.0:
            return True

        refresh_interval = self.config.refresh_hours * 3600
        return (time.time() - self._last_refresh) > refresh_interval

    async def refresh_from_esi(self, corp_id: int) -> int:
        """
        Refresh asset locations from ESI.

        Args:
            corp_id: Corporation ID to fetch assets for

        Returns:
            Number of asset systems found

        Note:
            This is a stub implementation. Actual ESI calls would require
            proper authentication and scope validation.
        """
        # This would make ESI calls in production:
        # - GET /corporations/{corp_id}/structures/ for structures
        # - GET /corporations/{corp_id}/assets/ filtered for offices
        #
        # For now, this serves as documentation of the interface.

        self._corp_id = corp_id
        self._last_refresh = time.time()

        logger.info(
            "Asset layer refresh complete: %d systems tracked",
            len(self._asset_systems),
        )

        return len(self._asset_systems)

    def add_structure(self, system_id: int) -> None:
        """
        Manually add a structure system.

        Args:
            system_id: System containing the structure
        """
        if self.config.structures:
            self._asset_systems[system_id] = "structure"
            logger.debug("Added structure in system %d", system_id)

    def add_office(self, system_id: int) -> None:
        """
        Manually add an office system.

        Args:
            system_id: System containing the office
        """
        if self.config.offices:
            # Don't override structure with office
            if system_id not in self._asset_systems:
                self._asset_systems[system_id] = "office"
                logger.debug("Added office in system %d", system_id)

    def remove_asset(self, system_id: int) -> None:
        """
        Remove an asset system.

        Args:
            system_id: System to remove
        """
        self._asset_systems.pop(system_id, None)
        logger.debug("Removed asset in system %d", system_id)

    def clear_assets(self) -> None:
        """Clear all tracked assets."""
        self._asset_systems.clear()
        self._last_refresh = 0.0

    def get_structure_systems(self) -> list[int]:
        """Get all systems with structures."""
        return [sid for sid, t in self._asset_systems.items() if t == "structure"]

    def get_office_systems(self) -> list[int]:
        """Get all systems with offices."""
        return [sid for sid, t in self._asset_systems.items() if t == "office"]

    @classmethod
    def from_config(cls, config: AssetConfig) -> AssetLayer:
        """Create layer from configuration."""
        return cls(config=config)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "config": {
                "structures": self.config.structures,
                "offices": self.config.offices,
                "structure_interest": self.config.structure_interest,
                "office_interest": self.config.office_interest,
                "refresh_hours": self.config.refresh_hours,
            },
            "asset_systems": {
                str(sid): asset_type for sid, asset_type in self._asset_systems.items()
            },
            "last_refresh": self._last_refresh,
            "corp_id": self._corp_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetLayer:
        """Deserialize from dictionary."""
        config = AssetConfig.from_dict(data.get("config"))

        asset_systems = {}
        for system_id_str, asset_type in data.get("asset_systems", {}).items():
            asset_systems[int(system_id_str)] = asset_type

        layer = cls(
            config=config,
            _asset_systems=asset_systems,
            _last_refresh=data.get("last_refresh", 0.0),
            _corp_id=data.get("corp_id"),
        )
        return layer
