"""
Sovereignty Service Package.

Provides sovereignty and coalition territory data for navigation and intelligence.

Exports:
- SovereigntyDatabase: SQLite-backed sovereignty cache
- SovereigntyEntry, AllianceInfo, CoalitionInfo: Data models
- fetch_sovereignty_map: ESI fetcher for /sovereignty/map/

Usage:
    from aria_esi.services.sovereignty import (
        get_sovereignty_database,
        fetch_sovereignty_map,
    )

    # Fetch from ESI
    sov_data = fetch_sovereignty_map_sync()

    # Query cached data
    db = get_sovereignty_database()
    sov = db.get_sovereignty(system_id=30000142)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .database import (
        AllianceRecord,
        CoalitionRecord,
        SovereigntyDatabase,
        SovereigntyRecord,
    )
    from .models import AllianceInfo, CoalitionInfo, SovereigntyEntry, SovereigntyStatus


def __getattr__(name: str):
    """Lazy import to avoid circular dependencies."""
    if name == "SovereigntyDatabase":
        from .database import SovereigntyDatabase

        return SovereigntyDatabase

    if name == "get_sovereignty_database":
        from .database import get_sovereignty_database

        return get_sovereignty_database

    if name == "reset_sovereignty_database":
        from .database import reset_sovereignty_database

        return reset_sovereignty_database

    if name in ("SovereigntyRecord", "AllianceRecord", "CoalitionRecord"):
        from . import database

        return getattr(database, name)

    if name in ("SovereigntyEntry", "AllianceInfo", "CoalitionInfo", "SovereigntyStatus"):
        from . import models

        return getattr(models, name)

    if name in ("fetch_sovereignty_map", "fetch_alliance_info", "fetch_alliances_batch"):
        from . import fetcher

        return getattr(fetcher, name)

    if name in ("fetch_sovereignty_map_sync", "fetch_alliances_batch_sync"):
        from . import fetcher

        return getattr(fetcher, name)

    if name in (
        "CoalitionRegistry",
        "get_coalition_registry",
        "reset_coalition_registry",
        "analyze_territory",
        "get_systems_by_coalition",
    ):
        from . import coalition_service

        return getattr(coalition_service, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Database
    "SovereigntyDatabase",
    "get_sovereignty_database",
    "reset_sovereignty_database",
    "SovereigntyRecord",
    "AllianceRecord",
    "CoalitionRecord",
    # Models
    "SovereigntyEntry",
    "AllianceInfo",
    "CoalitionInfo",
    "SovereigntyStatus",
    # Fetcher
    "fetch_sovereignty_map",
    "fetch_alliance_info",
    "fetch_alliances_batch",
    "fetch_sovereignty_map_sync",
    "fetch_alliances_batch_sync",
    # Coalition Service
    "CoalitionRegistry",
    "get_coalition_registry",
    "reset_coalition_registry",
    "analyze_territory",
    "get_systems_by_coalition",
]
