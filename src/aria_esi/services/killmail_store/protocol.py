"""
Killmail Store Protocol Interface.

This file defines the abstract interface for killmail storage implementations.
Referenced from: KILLMAIL_STORE_REDESIGN_PROPOSAL.md (Design Decision D1)

The protocol enables pluggable storage backends (SQLite, Redis, PostgreSQL)
while providing a consistent API for ingest, workers, and MCP queries.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class KillmailRecord:
    """Core killmail data from zKillboard RedisQ."""

    kill_id: int
    kill_time: int  # Unix timestamp
    solar_system_id: int
    zkb_hash: str
    zkb_total_value: float | None
    zkb_points: int | None
    zkb_is_npc: bool
    zkb_is_solo: bool
    zkb_is_awox: bool
    ingested_at: int  # When we received it

    # Denormalized for fast filtering (from zkb package)
    # NOTE: ESI is authoritative for display. See D6: Data Authority.
    victim_ship_type_id: int | None
    victim_corporation_id: int | None
    victim_alliance_id: int | None


@dataclass
class ESIKillmail:
    """Full killmail details from ESI."""

    kill_id: int
    fetched_at: int
    fetch_status: str  # 'success', 'unfetchable'
    fetch_attempts: int

    # Victim details
    victim_character_id: int | None
    victim_ship_type_id: int | None
    victim_corporation_id: int | None
    victim_alliance_id: int | None
    victim_damage_taken: int | None

    # Attacker summary
    attacker_count: int | None
    final_blow_character_id: int | None
    final_blow_ship_type_id: int | None
    final_blow_corporation_id: int | None

    # Serialized complex data
    attackers_json: str | None
    items_json: str | None
    position_json: str | None

    @property
    def is_unfetchable(self) -> bool:
        """Check if this is a sentinel row for unfetchable kills."""
        return self.fetch_status == "unfetchable"


@dataclass
class WorkerState:
    """Worker checkpoint and health state."""

    worker_name: str
    last_processed_time: int  # Unix timestamp of newest processed kill
    last_poll_at: int | None
    consecutive_failures: int


@dataclass
class ESIClaim:
    """ESI fetch claim for coordination."""

    kill_id: int
    claimed_by: str
    claimed_at: int

    def is_stale(self, threshold_seconds: int = 60) -> bool:
        """Check if claim has expired (holder likely crashed)."""
        import time

        return (time.time() - self.claimed_at) > threshold_seconds


@dataclass
class StoreStats:
    """Storage statistics for observability."""

    total_killmails: int
    total_esi_details: int
    total_esi_unfetchable: int
    oldest_killmail_time: int | None
    newest_killmail_time: int | None
    database_size_bytes: int


# =============================================================================
# Protocol Interface
# =============================================================================


@runtime_checkable
class KillmailStore(Protocol):
    """
    Abstract interface for killmail storage.

    Implementations must be async-compatible and handle concurrent access
    from multiple components (ingest writer, workers, MCP queries).

    Design notes:
    - All timestamps are Unix epoch integers
    - kill_id is globally unique (assigned by CCP)
    - ESI details are lazy-populated and may have sentinel rows for failures
    """

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the store, running migrations if needed.

        Must be called before any other operations.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the store and release resources."""
        ...

    # -------------------------------------------------------------------------
    # Core Killmail Operations
    # -------------------------------------------------------------------------

    @abstractmethod
    async def insert_kill(self, kill: KillmailRecord) -> None:
        """
        Insert a killmail record from RedisQ.

        Idempotent: duplicate kill_id is silently ignored.
        """
        ...

    @abstractmethod
    async def insert_kills_batch(self, kills: list[KillmailRecord]) -> int:
        """
        Insert multiple killmail records in a single transaction.

        Idempotent: duplicate kill_ids are silently ignored.

        Returns:
            Number of records actually inserted (excluding duplicates).
        """
        ...

    @abstractmethod
    async def insert_esi_details(self, kill_id: int, details: ESIKillmail) -> None:
        """
        Insert or update ESI details for a killmail.

        Called after successful ESI fetch.
        """
        ...

    @abstractmethod
    async def insert_esi_unfetchable(self, kill_id: int) -> None:
        """
        Mark a killmail as permanently unfetchable.

        Inserts sentinel row (fetched_at=0, fetch_status='unfetchable').
        Prevents future fetch attempts.
        """
        ...

    @abstractmethod
    async def get_esi_details(self, kill_id: int) -> ESIKillmail | None:
        """
        Get ESI details for a killmail.

        Returns None if not yet fetched.
        Returns sentinel (is_unfetchable=True) if permanently failed.
        """
        ...

    @abstractmethod
    async def get_esi_fetch_attempts(self, kill_id: int) -> int:
        """Get number of ESI fetch attempts for a killmail."""
        ...

    @abstractmethod
    async def increment_esi_fetch_attempts(self, kill_id: int, error: str | None = None) -> None:
        """
        Increment ESI fetch attempt counter.

        Creates row in esi_fetch_attempts if not exists.
        Updates attempts count and last_attempt_at timestamp.
        Optionally records error message for debugging.
        """
        ...

    @abstractmethod
    async def delete_esi_fetch_attempts(self, kill_id: int) -> None:
        """
        Delete ESI fetch attempts record.

        Called after successful ESI fetch (data now in esi_details)
        or after inserting unfetchable sentinel.
        """
        ...

    @abstractmethod
    async def query_kills(
        self,
        systems: list[int] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        min_value: int | None = None,
        limit: int = 100,
        cursor: tuple[int, int] | None = None,
    ) -> list[KillmailRecord]:
        """
        Query killmails with optional filters.

        Args:
            systems: Filter by solar_system_id (None = all systems)
            since: Filter kills after this time
            until: Filter kills before this time
            min_value: Minimum zkb_total_value
            limit: Maximum results to return
            cursor: Pagination cursor (kill_time, kill_id)

        Returns:
            Killmails ordered by kill_time DESC, kill_id DESC
        """
        ...

    @abstractmethod
    async def get_kill(self, kill_id: int) -> KillmailRecord | None:
        """Get a single killmail by ID."""
        ...

    # -------------------------------------------------------------------------
    # Worker State Management
    # -------------------------------------------------------------------------

    @abstractmethod
    async def get_worker_state(self, worker_name: str) -> WorkerState | None:
        """
        Get worker checkpoint state.

        Returns None if worker has never run (cold start).
        """
        ...

    @abstractmethod
    async def update_worker_state(
        self,
        worker_name: str,
        last_processed_time: int | None = None,
        last_poll_at: int | None = None,
        consecutive_failures: int | None = None,
    ) -> None:
        """
        Update worker state fields.

        Creates worker_state row if not exists.
        Only updates fields that are not None.
        """
        ...

    # -------------------------------------------------------------------------
    # Duplicate Detection and Delivery Tracking
    # -------------------------------------------------------------------------

    @abstractmethod
    async def is_kill_processed(self, worker_name: str, kill_id: int) -> bool:
        """Check if a kill has already been processed by this worker."""
        ...

    @abstractmethod
    async def mark_kill_processed(
        self, worker_name: str, kill_id: int, status: str = "delivered"
    ) -> None:
        """
        Record that a kill has been processed.

        Args:
            worker_name: The processing worker
            kill_id: The killmail ID
            status: 'delivered', 'failed', or 'pending'
        """
        ...

    @abstractmethod
    async def get_delivery_attempts(self, worker_name: str, kill_id: int) -> int:
        """Get number of delivery attempts for a kill."""
        ...

    @abstractmethod
    async def increment_delivery_attempts(self, worker_name: str, kill_id: int) -> None:
        """Increment delivery attempt counter."""
        ...

    # -------------------------------------------------------------------------
    # ESI Fetch Coordination
    # -------------------------------------------------------------------------

    @abstractmethod
    async def try_claim_esi_fetch(self, kill_id: int, worker_name: str) -> bool:
        """
        Attempt to claim exclusive ESI fetch rights for a killmail.

        Uses INSERT OR IGNORE for atomic claim acquisition.

        Returns:
            True if claim acquired, False if another worker holds claim.
        """
        ...

    @abstractmethod
    async def delete_esi_claim(self, kill_id: int) -> None:
        """Release ESI fetch claim (call after fetch completes)."""
        ...

    @abstractmethod
    async def get_esi_claim(self, kill_id: int) -> ESIClaim | None:
        """Get current ESI fetch claim for inspection."""
        ...

    # -------------------------------------------------------------------------
    # Maintenance Operations
    # -------------------------------------------------------------------------

    @abstractmethod
    async def expunge_before(self, cutoff: datetime) -> int:
        """
        Delete killmails older than cutoff.

        Also cascades to esi_details for affected kills.

        Returns:
            Count of killmails deleted.
        """
        ...

    @abstractmethod
    async def expunge_processed_kills(self, older_than_seconds: int = 3600) -> int:
        """
        Delete old processed_kills entries.

        Default retention: 1 hour (must exceed max out-of-order delay).

        Returns:
            Count of entries deleted.
        """
        ...

    @abstractmethod
    async def expunge_stale_esi_claims(self, threshold_seconds: int = 60) -> int:
        """
        Delete abandoned ESI fetch claims.

        Claims older than threshold are assumed from crashed workers.

        Returns:
            Count of claims deleted.
        """
        ...

    @abstractmethod
    async def expunge_orphaned_esi_attempts(self) -> int:
        """
        Delete ESI fetch attempts for expunged killmails.

        Cleans up esi_fetch_attempts entries where the parent killmail
        no longer exists (was expunged before ESI fetch completed).

        Returns:
            Count of orphaned entries deleted.
        """
        ...

    @abstractmethod
    async def expunge_orphaned_state(self, active_profiles: set[str]) -> int:
        """
        Remove state for deleted notification profiles.

        Args:
            active_profiles: Names of currently configured profiles.

        Returns:
            Count of orphaned entries deleted.
        """
        ...

    @abstractmethod
    async def optimize_database(self) -> None:
        """
        Run storage optimization (e.g., PRAGMA optimize for SQLite).

        Call after expunge operations to maintain index efficiency.
        """
        ...

    @abstractmethod
    async def get_stats(self) -> StoreStats:
        """Get storage statistics for observability."""
        ...
