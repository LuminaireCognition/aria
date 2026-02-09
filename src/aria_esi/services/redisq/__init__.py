"""
RedisQ Real-Time Kill Intelligence Service.

Provides real-time killmail streaming via zKillboard's RedisQ service
for minute-level threat awareness.
"""

from __future__ import annotations

__all__ = [
    # Models
    "QueuedKill",
    "ProcessedKill",
    "RedisQConfig",
    # Database
    "RealtimeKillsDatabase",
    # Processing
    "KillFilter",
    "parse_esi_killmail",
    "is_pod_kill",
    # Poller
    "RedisQPoller",
    "get_poller",
    "reset_poller",
    # Backfill
    "backfill_from_zkillboard",
    "startup_recovery",
    # Threat Cache (Phase 2)
    "ThreatCache",
    "get_threat_cache",
    "GatecampStatus",
    "RealtimeActivitySummary",
    "detect_gatecamp",
]


def __getattr__(name: str):
    """Lazy import components to avoid circular imports."""
    if name in ("QueuedKill", "ProcessedKill", "RedisQConfig"):
        from .models import ProcessedKill, QueuedKill, RedisQConfig

        return {
            "QueuedKill": QueuedKill,
            "ProcessedKill": ProcessedKill,
            "RedisQConfig": RedisQConfig,
        }[name]

    if name == "RealtimeKillsDatabase":
        from .database import RealtimeKillsDatabase

        return RealtimeKillsDatabase

    if name in ("KillFilter", "parse_esi_killmail", "is_pod_kill"):
        from . import processor

        return getattr(processor, name)

    if name in ("RedisQPoller", "get_poller", "reset_poller"):
        from . import poller

        return getattr(poller, name)

    if name in ("backfill_from_zkillboard", "startup_recovery"):
        from . import backfill

        return getattr(backfill, name)

    if name in (
        "ThreatCache",
        "get_threat_cache",
        "GatecampStatus",
        "RealtimeActivitySummary",
        "detect_gatecamp",
    ):
        from . import threat_cache

        return getattr(threat_cache, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
