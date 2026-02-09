"""
RedisQ Data Models.

Data classes for kills queued from RedisQ, processed killmails,
and service configuration.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..killmail_store import KillmailRecord


@dataclass
class QueuedKill:
    """
    Kill notification received from RedisQ.

    RedisQ returns kill ID and hash, not full killmail data.
    Full killmail must be fetched from ESI using the hash.
    """

    kill_id: int
    hash: str
    zkb_data: dict[str, Any]
    queued_at: float  # Unix timestamp when queued
    solar_system_id: int | None = None  # For topology pre-filter (if available in package)
    kill_time: int | None = None  # Actual kill time from ESI (Unix timestamp)

    @classmethod
    def from_redisq_package(cls, package: dict[str, Any], queued_at: float) -> QueuedKill:
        """
        Create QueuedKill from RedisQ package response.

        Handles both old and new (2025+) RedisQ formats:
        - New format: {"killID": 123, "zkb": {...}}
        - Old format: {"killmail": {"killmail_id": 123}, "zkb": {...}}

        Args:
            package: The 'package' dict from RedisQ response
            queued_at: Unix timestamp when received

        Returns:
            QueuedKill instance
        """
        zkb = package.get("zkb", {})

        # New format (2025+): killID is directly in package
        kill_id = package.get("killID")
        killmail = package.get("killmail", {})

        if kill_id is None:
            # Old format fallback: killmail_id nested in killmail dict
            kill_id = killmail.get("killmail_id", 0)

        # Extract solar_system_id for topology pre-filter
        # New format includes it in killmail object within package
        solar_system_id = killmail.get("solar_system_id")

        # Parse kill_time from killmail data (ISO 8601 format)
        kill_time: int | None = None
        kill_time_str = killmail.get("killmail_time")
        if kill_time_str:
            try:
                from datetime import datetime

                # ESI returns ISO format: 2024-01-15T12:34:56Z
                dt = datetime.fromisoformat(kill_time_str.replace("Z", "+00:00"))
                kill_time = int(dt.timestamp())
            except (ValueError, AttributeError):
                pass

        return cls(
            kill_id=kill_id or 0,
            hash=zkb.get("hash", ""),
            zkb_data=zkb,
            queued_at=queued_at,
            solar_system_id=solar_system_id,
            kill_time=kill_time,
        )

    def to_killmail_record(self) -> KillmailRecord:
        """
        Convert to KillmailRecord for persistent storage.

        Creates a minimal record from RedisQ data (before ESI fetch).
        ESI details are fetched and stored separately.

        Returns:
            KillmailRecord with zKillboard data
        """
        from ..killmail_store import KillmailRecord

        zkb = self.zkb_data or {}

        # Extract victim info from killmail data if available
        # (new RedisQ format includes partial killmail)
        victim = zkb.get("victim", {})

        # Use actual kill_time if available, fall back to queued_at
        effective_kill_time = self.kill_time if self.kill_time else int(self.queued_at)

        return KillmailRecord(
            kill_id=self.kill_id,
            kill_time=effective_kill_time,
            solar_system_id=self.solar_system_id or 0,
            zkb_hash=self.hash,
            zkb_total_value=zkb.get("totalValue"),
            zkb_points=zkb.get("points"),
            zkb_is_npc=zkb.get("npc", False),
            zkb_is_solo=zkb.get("solo", False),
            zkb_is_awox=zkb.get("awox", False),
            ingested_at=int(time.time()),
            victim_ship_type_id=victim.get("ship_type_id"),
            victim_corporation_id=victim.get("corporation_id"),
            victim_alliance_id=victim.get("alliance_id"),
        )


@dataclass
class ProcessedKill:
    """
    Fully processed killmail ready for database storage.

    Contains extracted and normalized data from ESI killmail
    combined with zKillboard metadata.
    """

    kill_id: int
    kill_time: datetime
    solar_system_id: int
    victim_ship_type_id: int | None
    victim_corporation_id: int | None
    victim_alliance_id: int | None
    attacker_count: int
    attacker_corps: list[int]
    attacker_alliances: list[int]
    attacker_ship_types: list[int]
    final_blow_ship_type_id: int | None
    total_value: float
    is_pod_kill: bool

    def to_db_row(self) -> tuple:
        """
        Convert to database row tuple for INSERT.

        Returns:
            Tuple matching realtime_kills table columns
        """
        import json

        return (
            self.kill_id,
            int(self.kill_time.timestamp()),
            self.solar_system_id,
            self.victim_ship_type_id,
            self.victim_corporation_id,
            self.victim_alliance_id,
            self.attacker_count,
            json.dumps(self.attacker_corps),
            json.dumps(self.attacker_alliances),
            json.dumps(self.attacker_ship_types),
            self.final_blow_ship_type_id,
            self.total_value,
            1 if self.is_pod_kill else 0,
        )

    @classmethod
    def from_db_row(cls, row: dict | tuple) -> ProcessedKill:
        """
        Create ProcessedKill from database row.

        Args:
            row: Database row (dict or tuple)

        Returns:
            ProcessedKill instance
        """
        import json

        if isinstance(row, tuple):
            return cls(
                kill_id=row[0],
                kill_time=datetime.fromtimestamp(row[1]),
                solar_system_id=row[2],
                victim_ship_type_id=row[3],
                victim_corporation_id=row[4],
                victim_alliance_id=row[5],
                attacker_count=row[6],
                attacker_corps=json.loads(row[7]) if row[7] else [],
                attacker_alliances=json.loads(row[8]) if row[8] else [],
                attacker_ship_types=json.loads(row[9]) if row[9] else [],
                final_blow_ship_type_id=row[10],
                total_value=row[11] or 0.0,
                is_pod_kill=bool(row[12]),
            )
        else:
            return cls(
                kill_id=row["kill_id"],
                kill_time=datetime.fromtimestamp(row["kill_time"]),
                solar_system_id=row["solar_system_id"],
                victim_ship_type_id=row["victim_ship_type_id"],
                victim_corporation_id=row["victim_corporation_id"],
                victim_alliance_id=row["victim_alliance_id"],
                attacker_count=row["attacker_count"],
                attacker_corps=json.loads(row["attacker_corps"]) if row["attacker_corps"] else [],
                attacker_alliances=json.loads(row["attacker_alliances"])
                if row["attacker_alliances"]
                else [],
                attacker_ship_types=json.loads(row["attacker_ship_types"])
                if row["attacker_ship_types"]
                else [],
                final_blow_ship_type_id=row["final_blow_ship_type_id"],
                total_value=row["total_value"] or 0.0,
                is_pod_kill=bool(row["is_pod_kill"]),
            )


@dataclass
class RedisQConfig:
    """
    Configuration for RedisQ polling service.

    Loaded from AriaSettings and persisted state.
    """

    enabled: bool = False
    queue_id: str = ""
    poll_interval_seconds: int = 10
    filter_regions: list[int] = field(default_factory=list)
    min_value_isk: int = 0
    retention_hours: int = 24

    @classmethod
    def from_settings(cls, settings: Any, queue_id: str = "") -> RedisQConfig:
        """
        Create config from AriaSettings.

        Args:
            settings: AriaSettings instance
            queue_id: Persisted queue ID (empty to generate new)

        Returns:
            RedisQConfig instance
        """
        return cls(
            enabled=getattr(settings, "redisq_enabled", False),
            queue_id=queue_id,
            poll_interval_seconds=10,
            filter_regions=getattr(settings, "redisq_regions", []),
            min_value_isk=getattr(settings, "redisq_min_value", 0),
            retention_hours=getattr(settings, "redisq_retention_hours", 24),
        )


@dataclass
class IngestMetrics:
    """Metrics for killmail ingest pipeline."""

    received_total: int = 0
    written_total: int = 0
    dropped_total: int = 0
    queue_depth: int = 0
    last_drop_time: datetime | None = None


@dataclass
class PollerStatus:
    """
    Status snapshot of the RedisQ poller.

    Used for status reporting and health checks.
    """

    is_running: bool = False
    queue_id: str = ""
    last_poll_time: datetime | None = None
    last_kill_time: datetime | None = None
    kills_processed: int = 0
    kills_filtered: int = 0
    fetch_queue_size: int = 0
    errors_last_hour: int = 0
    filter_regions: list[int] = field(default_factory=list)

    # Entity tracking stats
    watched_entity_kills: int = 0
    watched_corps_count: int = 0
    watched_alliances_count: int = 0

    # Topology pre-filter stats
    topology_active: bool = False
    topology_systems_tracked: int = 0
    topology_passed: int = 0
    topology_filtered: int = 0

    # Ingest pipeline stats (killmail store)
    ingest: IngestMetrics | None = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        result = {
            "is_running": self.is_running,
            "queue_id": self.queue_id,
            "last_poll_time": self.last_poll_time.isoformat() if self.last_poll_time else None,
            "last_kill_time": self.last_kill_time.isoformat() if self.last_kill_time else None,
            "kills_processed": self.kills_processed,
            "kills_filtered": self.kills_filtered,
            "fetch_queue_size": self.fetch_queue_size,
            "errors_last_hour": self.errors_last_hour,
            "filter_regions": self.filter_regions,
            "entity_tracking": {
                "watched_entity_kills": self.watched_entity_kills,
                "watched_corps": self.watched_corps_count,
                "watched_alliances": self.watched_alliances_count,
            },
        }

        # Include topology stats if active
        if self.topology_active:
            result["topology"] = {
                "active": self.topology_active,
                "systems_tracked": self.topology_systems_tracked,
                "passed": self.topology_passed,
                "filtered": self.topology_filtered,
            }

        # Include ingest stats if available
        if self.ingest:
            result["ingest"] = {
                "received_total": self.ingest.received_total,
                "written_total": self.ingest.written_total,
                "dropped_total": self.ingest.dropped_total,
                "queue_depth": self.ingest.queue_depth,
                "last_drop_time": (
                    self.ingest.last_drop_time.isoformat() if self.ingest.last_drop_time else None
                ),
            }

        return result
