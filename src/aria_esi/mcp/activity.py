"""
Activity Cache for ESI Activity Data.

Provides in-memory caching of live ESI activity data including:
- System kills (ship, pod, NPC)
- System jumps (traffic)
- Faction Warfare system status

STP-013: Activity Overlay Tools
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Literal

from ..core.logging import get_logger

logger = get_logger("aria_universe.activity")


@dataclass
class ActivityData:
    """Cached activity data for a single system."""

    system_id: int
    ship_kills: int = 0
    pod_kills: int = 0
    npc_kills: int = 0
    ship_jumps: int = 0


FWContestedStatus = Literal["uncontested", "contested", "vulnerable"]
"""Faction Warfare contested status."""


@dataclass
class FWSystemData:
    """Cached Faction Warfare data for a single system."""

    system_id: int
    owner_faction_id: int
    occupier_faction_id: int
    contested: FWContestedStatus
    victory_points: int
    victory_points_threshold: int


class ActivityCache:
    """
    In-memory cache for ESI activity data.

    Fetches galaxy-wide data on first access, refreshes after TTL.
    Uses asyncio.Lock to prevent duplicate ESI calls from concurrent requests.

    Thread-safety: This cache is designed for use within a single async event loop.
    The locks prevent concurrent coroutines from duplicating ESI requests.
    """

    def __init__(self, ttl_seconds: int = 600, fw_ttl_seconds: int = 1800):
        """
        Initialize activity cache.

        Args:
            ttl_seconds: TTL for kills/jumps data (default: 10 minutes)
            fw_ttl_seconds: TTL for FW data (default: 30 minutes)
        """
        self.ttl_seconds = ttl_seconds
        self.fw_ttl_seconds = fw_ttl_seconds
        self._kills_data: dict[int, ActivityData] = {}
        self._jumps_data: dict[int, int] = {}
        self._fw_data: dict[int, FWSystemData] = {}
        self._kills_timestamp: float = 0
        self._jumps_timestamp: float = 0
        self._fw_timestamp: float = 0
        # Locks prevent concurrent refreshes
        self._kills_lock = asyncio.Lock()
        self._jumps_lock = asyncio.Lock()
        self._fw_lock = asyncio.Lock()

    async def get_activity(self, system_id: int) -> ActivityData:
        """
        Get activity data for a system, refreshing cache if stale.

        Args:
            system_id: EVE system ID

        Returns:
            ActivityData with kills and jumps, or zeros if no data
        """
        await self._ensure_kills_fresh()
        await self._ensure_jumps_fresh()

        base = self._kills_data.get(system_id, ActivityData(system_id=system_id))
        # Merge jumps data
        return ActivityData(
            system_id=system_id,
            ship_kills=base.ship_kills,
            pod_kills=base.pod_kills,
            npc_kills=base.npc_kills,
            ship_jumps=self._jumps_data.get(system_id, 0),
        )

    async def get_kills(self, system_id: int) -> int:
        """Get total PvP kills (ship + pod) for a system."""
        await self._ensure_kills_fresh()
        data = self._kills_data.get(system_id, ActivityData(system_id=system_id))
        return data.ship_kills + data.pod_kills

    async def get_jumps(self, system_id: int) -> int:
        """Get jump count for a system."""
        await self._ensure_jumps_fresh()
        return self._jumps_data.get(system_id, 0)

    async def get_npc_kills(self, system_id: int) -> int:
        """Get NPC kills (ratting activity) for a system."""
        await self._ensure_kills_fresh()
        data = self._kills_data.get(system_id, ActivityData(system_id=system_id))
        return data.npc_kills

    async def get_fw_status(self, system_id: int) -> FWSystemData | None:
        """Get FW status for a system, or None if not a FW system."""
        await self._ensure_fw_fresh()
        return self._fw_data.get(system_id)

    async def get_all_activity(self) -> dict[int, ActivityData]:
        """Get all cached activity data."""
        await self._ensure_kills_fresh()
        await self._ensure_jumps_fresh()

        # Merge kills and jumps into unified ActivityData
        result: dict[int, ActivityData] = {}
        all_ids = set(self._kills_data.keys()) | set(self._jumps_data.keys())

        for system_id in all_ids:
            kills = self._kills_data.get(system_id)
            jumps = self._jumps_data.get(system_id, 0)
            result[system_id] = ActivityData(
                system_id=system_id,
                ship_kills=kills.ship_kills if kills else 0,
                pod_kills=kills.pod_kills if kills else 0,
                npc_kills=kills.npc_kills if kills else 0,
                ship_jumps=jumps,
            )

        return result

    async def get_all_fw(self) -> dict[int, FWSystemData]:
        """Get all cached FW data."""
        await self._ensure_fw_fresh()
        return dict(self._fw_data)

    def get_cache_status(self) -> dict[str, Any]:
        """Return cache status for diagnostics."""
        now = time.time()
        return {
            "kills": {
                "cached_systems": len(self._kills_data),
                "age_seconds": int(now - self._kills_timestamp) if self._kills_timestamp else None,
                "ttl_seconds": self.ttl_seconds,
                "stale": (now - self._kills_timestamp) > self.ttl_seconds
                if self._kills_timestamp
                else True,
            },
            "jumps": {
                "cached_systems": len(self._jumps_data),
                "age_seconds": int(now - self._jumps_timestamp) if self._jumps_timestamp else None,
                "ttl_seconds": self.ttl_seconds,
                "stale": (now - self._jumps_timestamp) > self.ttl_seconds
                if self._jumps_timestamp
                else True,
            },
            "fw": {
                "cached_systems": len(self._fw_data),
                "age_seconds": int(now - self._fw_timestamp) if self._fw_timestamp else None,
                "ttl_seconds": self.fw_ttl_seconds,
                "stale": (now - self._fw_timestamp) > self.fw_ttl_seconds
                if self._fw_timestamp
                else True,
            },
        }

    def get_kills_cache_age(self) -> int | None:
        """Get age of kills cache in seconds, or None if never populated."""
        if self._kills_timestamp == 0:
            return None
        return int(time.time() - self._kills_timestamp)

    async def _ensure_kills_fresh(self) -> None:
        """Refresh kills data if TTL expired."""
        if time.time() - self._kills_timestamp > self.ttl_seconds:
            async with self._kills_lock:
                # Double-check after acquiring lock
                if time.time() - self._kills_timestamp > self.ttl_seconds:
                    await self._refresh_kills()

    async def _ensure_jumps_fresh(self) -> None:
        """Refresh jumps data if TTL expired."""
        if time.time() - self._jumps_timestamp > self.ttl_seconds:
            async with self._jumps_lock:
                if time.time() - self._jumps_timestamp > self.ttl_seconds:
                    await self._refresh_jumps()

    async def _ensure_fw_fresh(self) -> None:
        """Refresh FW data if TTL expired."""
        if time.time() - self._fw_timestamp > self.fw_ttl_seconds:
            async with self._fw_lock:
                if time.time() - self._fw_timestamp > self.fw_ttl_seconds:
                    await self._refresh_fw()

    async def _refresh_kills(self) -> None:
        """Fetch fresh kills data from ESI."""
        try:
            from .esi_client import get_async_esi_client

            client = await get_async_esi_client()
            data = await client.get("/universe/system_kills/")

            if isinstance(data, list):
                self._kills_data = {
                    item["system_id"]: ActivityData(
                        system_id=item["system_id"],
                        ship_kills=item.get("ship_kills", 0),
                        pod_kills=item.get("pod_kills", 0),
                        npc_kills=item.get("npc_kills", 0),
                    )
                    for item in data
                }
                self._kills_timestamp = time.time()
                logger.debug("Refreshed kills cache: %d systems", len(self._kills_data))
        except Exception as e:
            # On error, keep stale data (better than nothing)
            logger.warning("Failed to refresh kills cache: %s", e)

    async def _refresh_jumps(self) -> None:
        """Fetch fresh jumps data from ESI."""
        try:
            from .esi_client import get_async_esi_client

            client = await get_async_esi_client()
            data = await client.get("/universe/system_jumps/")

            if isinstance(data, list):
                self._jumps_data = {item["system_id"]: item.get("ship_jumps", 0) for item in data}
                self._jumps_timestamp = time.time()
                logger.debug("Refreshed jumps cache: %d systems", len(self._jumps_data))
        except Exception as e:
            logger.warning("Failed to refresh jumps cache: %s", e)

    async def _refresh_fw(self) -> None:
        """Fetch fresh FW data from ESI."""
        try:
            from .esi_client import get_async_esi_client

            client = await get_async_esi_client()
            data = await client.get("/fw/systems/")

            if isinstance(data, list):
                self._fw_data = {
                    item["solar_system_id"]: FWSystemData(
                        system_id=item["solar_system_id"],
                        owner_faction_id=item.get("owner_faction_id", 0),
                        occupier_faction_id=item.get("occupier_faction_id", 0),
                        contested=item.get("contested", "uncontested"),
                        victory_points=item.get("victory_points", 0),
                        victory_points_threshold=item.get("victory_points_threshold", 0),
                    )
                    for item in data
                }
                self._fw_timestamp = time.time()
                logger.debug("Refreshed FW cache: %d systems", len(self._fw_data))
        except Exception as e:
            logger.warning("Failed to refresh FW cache: %s", e)


# Module-level singleton
_activity_cache: ActivityCache | None = None


def get_activity_cache() -> ActivityCache:
    """Get or create the activity cache singleton."""
    global _activity_cache
    if _activity_cache is None:
        _activity_cache = ActivityCache()
    return _activity_cache


def reset_activity_cache() -> None:
    """Reset the activity cache singleton (for testing)."""
    global _activity_cache
    _activity_cache = None


ActivityLevel = Literal["none", "low", "medium", "high", "extreme"]


def classify_activity(value: int, activity_type: str) -> ActivityLevel:
    """
    Classify activity level based on value and type.

    Thresholds tuned for EVE Online typical activity:
    - Kills: Most systems have 0-5, >20 is notable, >50 is extreme
    - Jumps: Trade hubs have thousands, >500 is busy for low-sec
    - Ratting: Varies by region, >100 is active

    Args:
        value: Activity value (kills, jumps, etc.)
        activity_type: Type of activity ("kills", "jumps", "ratting")

    Returns:
        Activity level: "none", "low", "medium", "high", "extreme"
    """
    if activity_type == "kills":
        if value == 0:
            return "none"
        elif value < 5:
            return "low"
        elif value < 20:
            return "medium"
        elif value < 50:
            return "high"
        else:
            return "extreme"
    elif activity_type == "jumps":
        if value < 50:
            return "low"
        elif value < 200:
            return "medium"
        elif value < 500:
            return "high"
        else:
            return "extreme"
    elif activity_type == "ratting":
        if value < 50:
            return "low"
        elif value < 100:
            return "medium"
        elif value < 300:
            return "high"
        else:
            return "extreme"
    return "none"


# Faction ID to name mapping
FACTION_NAMES: dict[int, str] = {
    500001: "Caldari State",
    500002: "Minmatar Republic",
    500003: "Amarr Empire",
    500004: "Gallente Federation",
}


def get_faction_name(faction_id: int) -> str:
    """Get faction name from ID."""
    return FACTION_NAMES.get(faction_id, f"Unknown ({faction_id})")


def get_faction_id(faction_name: str) -> int | None:
    """Get faction ID from name (case-insensitive)."""
    name_lower = faction_name.lower()
    for fid, fname in FACTION_NAMES.items():
        if name_lower in fname.lower():
            return fid
    return None
