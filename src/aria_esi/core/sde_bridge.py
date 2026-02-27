"""
SDE Bridge — Callback registry for core → SDE decoupling.

Core modules (constants.py, client.py) need SDE data but must not
import from the MCP layer.  This module provides a registration
mechanism: the MCP layer registers provider callbacks at startup,
and core modules call the bridge functions which delegate to those
callbacks (or return None if the MCP layer isn't loaded).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

# ---------------------------------------------------------------------------
# Provider callbacks (set by MCP layer at startup)
# ---------------------------------------------------------------------------

_ship_group_ids_provider: Optional[Callable[[], set[int]]] = None
_station_name_provider: Optional[Callable[[int], Optional[str]]] = None


# ---------------------------------------------------------------------------
# Registration API (called by MCP layer)
# ---------------------------------------------------------------------------


def register_ship_group_ids_provider(provider: Callable[[], set[int]]) -> None:
    """Register the callback that returns all ship group IDs from SDE."""
    global _ship_group_ids_provider
    _ship_group_ids_provider = provider


def register_station_name_provider(provider: Callable[[int], Optional[str]]) -> None:
    """Register the callback that resolves station_id → station name from SDE."""
    global _station_name_provider
    _station_name_provider = provider


# ---------------------------------------------------------------------------
# Query API (called by core modules)
# ---------------------------------------------------------------------------


def get_ship_group_ids_from_sde() -> Optional[set[int]]:
    """Return ship group IDs via registered provider, or None if unavailable."""
    if _ship_group_ids_provider is None:
        return None
    try:
        return _ship_group_ids_provider()
    except Exception:  # noqa: BLE001 -- broad handler
        return None


def get_station_name_from_sde(station_id: int) -> Optional[str]:
    """Return station name via registered provider, or None if unavailable."""
    if _station_name_provider is None:
        return None
    try:
        return _station_name_provider(station_id)
    except Exception:  # noqa: BLE001 -- broad handler
        return None


# ---------------------------------------------------------------------------
# Testing helpers
# ---------------------------------------------------------------------------


def reset_sde_bridge() -> None:
    """Reset all registered providers. For testing only."""
    global _ship_group_ids_provider, _station_name_provider
    _ship_group_ids_provider = None
    _station_name_provider = None
