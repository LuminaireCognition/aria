"""
Sovereignty Data Models.

Dataclasses for sovereignty and coalition territory data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class SovereigntyEntry:
    """
    Sovereignty entry for a single system.

    From ESI GET /sovereignty/map/:
    - system_id: Solar system ID
    - alliance_id: Alliance holding sovereignty (null for NPC space)
    - faction_id: NPC faction for NPC null-sec (e.g., Serpentis, Sansha)
    """

    system_id: int
    alliance_id: int | None = None
    faction_id: int | None = None
    corporation_id: int | None = None


@dataclass
class AllianceInfo:
    """
    Alliance information for sovereignty display.

    Cached from ESI GET /alliances/{id}/ to avoid repeated lookups.
    """

    alliance_id: int
    name: str
    ticker: str
    executor_corporation_id: int | None = None
    faction_id: int | None = None  # If alliance is part of FW


@dataclass
class CoalitionInfo:
    """
    Coalition information for territory grouping.

    Coalitions are player-defined alliances of alliances.
    Not tracked by ESI - requires manual/community data.
    """

    coalition_id: str  # e.g., "imperium", "panfam"
    display_name: str  # e.g., "The Imperium", "PanFam"
    aliases: list[str]  # e.g., ["goons", "gsf", "bees"]
    alliance_ids: list[int]  # Member alliance IDs


@dataclass
class TerritoryStats:
    """
    Aggregated territory statistics for a coalition or alliance.
    """

    entity_id: str | int  # Coalition ID or alliance ID
    entity_name: str
    entity_type: str  # "coalition" or "alliance"
    system_count: int
    region_ids: list[int]
    constellation_ids: list[int]
    capital_system_id: int | None = None  # TCU/iHub staging


@dataclass
class SovereigntyStatus:
    """
    Full sovereignty status for cache/database storage.
    """

    system_id: int
    alliance_id: int | None
    alliance_name: str | None
    faction_id: int | None
    faction_name: str | None
    coalition_id: str | None
    coalition_name: str | None
    updated_at: int  # Unix timestamp
