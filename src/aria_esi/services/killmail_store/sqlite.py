"""
SQLite Implementation of Killmail Store.

Uses WAL mode for concurrent read/write access across multiple processes.
See KILLMAIL_STORE_REDESIGN_PROPOSAL.md D1: Storage Engine.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

from .migrations import MigrationRunner
from .protocol import (
    ESIClaim,
    ESIKillmail,
    KillmailRecord,
    StoreStats,
    WorkerState,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SQLiteKillmailStore:
    """
    SQLite implementation of KillmailStore.

    Uses WAL mode for concurrent read/write access.
    See killmail_store_schema.sql for table definitions.

    Connection configuration:
        PRAGMA journal_mode=WAL
        PRAGMA busy_timeout=5000
        PRAGMA synchronous=NORMAL
        PRAGMA foreign_keys=ON
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        read_only: bool = False,
    ):
        """
        Initialize the store.

        Args:
            db_path: Path to database file. Defaults to {instance_root}/cache/killmails.db.
            read_only: Open in read-only mode (for MCP server).
        """
        if db_path is None:
            from ...core.config import get_settings

            db_path = get_settings().killmail_db_path

        self.db_path = Path(db_path)
        self.read_only = read_only
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """
        Initialize database, running migrations if needed.

        Must be called before any other operations.
        """
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Open connection
        if self.read_only:
            # Read-only mode for MCP server
            uri = f"file:{self.db_path}?mode=ro"
            self._db = await aiosqlite.connect(uri, uri=True)
            await self._db.execute("PRAGMA query_only=ON")
        else:
            self._db = await aiosqlite.connect(self.db_path)

            # Configure for concurrent access
            await self._db.execute("PRAGMA journal_mode=WAL")
            await self._db.execute("PRAGMA busy_timeout=5000")
            await self._db.execute("PRAGMA synchronous=NORMAL")
            await self._db.execute("PRAGMA foreign_keys=ON")

            # Run migrations
            runner = MigrationRunner(self._db)
            await runner.run_migrations()

        # Enable row factory for dict access
        self._db.row_factory = aiosqlite.Row

        logger.info(
            "Killmail store initialized: %s (read_only=%s)",
            self.db_path,
            self.read_only,
        )

    async def close(self) -> None:
        """Close the store and release resources."""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Killmail store closed")

    @property
    def db(self) -> aiosqlite.Connection:
        """Get the database connection, raising if not initialized."""
        if self._db is None:
            raise RuntimeError("Store not initialized. Call initialize() first.")
        return self._db

    # -------------------------------------------------------------------------
    # Core Killmail Operations
    # -------------------------------------------------------------------------

    async def insert_kill(self, kill: KillmailRecord) -> None:
        """Insert a killmail record from RedisQ (idempotent)."""
        await self.db.execute(
            """
            INSERT OR IGNORE INTO killmails (
                kill_id, kill_time, solar_system_id, zkb_hash,
                zkb_total_value, zkb_points, zkb_is_npc, zkb_is_solo, zkb_is_awox,
                ingested_at, victim_ship_type_id, victim_corporation_id, victim_alliance_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kill.kill_id,
                kill.kill_time,
                kill.solar_system_id,
                kill.zkb_hash,
                kill.zkb_total_value,
                kill.zkb_points,
                kill.zkb_is_npc,
                kill.zkb_is_solo,
                kill.zkb_is_awox,
                kill.ingested_at,
                kill.victim_ship_type_id,
                kill.victim_corporation_id,
                kill.victim_alliance_id,
            ),
        )
        await self.db.commit()

    async def insert_kills_batch(self, kills: list[KillmailRecord]) -> int:
        """Insert multiple killmail records in a single transaction."""
        if not kills:
            return 0

        cursor = await self.db.executemany(
            """
            INSERT OR IGNORE INTO killmails (
                kill_id, kill_time, solar_system_id, zkb_hash,
                zkb_total_value, zkb_points, zkb_is_npc, zkb_is_solo, zkb_is_awox,
                ingested_at, victim_ship_type_id, victim_corporation_id, victim_alliance_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    k.kill_id,
                    k.kill_time,
                    k.solar_system_id,
                    k.zkb_hash,
                    k.zkb_total_value,
                    k.zkb_points,
                    k.zkb_is_npc,
                    k.zkb_is_solo,
                    k.zkb_is_awox,
                    k.ingested_at,
                    k.victim_ship_type_id,
                    k.victim_corporation_id,
                    k.victim_alliance_id,
                )
                for k in kills
            ],
        )
        await self.db.commit()
        return cursor.rowcount

    async def insert_esi_details(self, kill_id: int, details: ESIKillmail) -> None:
        """Insert or update ESI details for a killmail."""
        await self.db.execute(
            """
            INSERT OR REPLACE INTO esi_details (
                kill_id, fetched_at, fetch_status, fetch_attempts,
                victim_character_id, victim_ship_type_id, victim_corporation_id,
                victim_alliance_id, victim_damage_taken,
                attacker_count, final_blow_character_id, final_blow_ship_type_id,
                final_blow_corporation_id,
                attackers_json, items_json, position_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kill_id,
                details.fetched_at,
                details.fetch_status,
                details.fetch_attempts,
                details.victim_character_id,
                details.victim_ship_type_id,
                details.victim_corporation_id,
                details.victim_alliance_id,
                details.victim_damage_taken,
                details.attacker_count,
                details.final_blow_character_id,
                details.final_blow_ship_type_id,
                details.final_blow_corporation_id,
                details.attackers_json,
                details.items_json,
                details.position_json,
            ),
        )
        await self.db.commit()

    async def insert_esi_unfetchable(self, kill_id: int) -> None:
        """Mark a killmail as permanently unfetchable."""
        await self.db.execute(
            """
            INSERT OR REPLACE INTO esi_details (
                kill_id, fetched_at, fetch_status, fetch_attempts
            ) VALUES (?, 0, 'unfetchable', 0)
            """,
            (kill_id,),
        )
        await self.db.commit()

    async def get_esi_details(self, kill_id: int) -> ESIKillmail | None:
        """Get ESI details for a killmail."""
        cursor = await self.db.execute(
            """
            SELECT kill_id, fetched_at, fetch_status, fetch_attempts,
                   victim_character_id, victim_ship_type_id, victim_corporation_id,
                   victim_alliance_id, victim_damage_taken,
                   attacker_count, final_blow_character_id, final_blow_ship_type_id,
                   final_blow_corporation_id,
                   attackers_json, items_json, position_json
            FROM esi_details
            WHERE kill_id = ?
            """,
            (kill_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        return ESIKillmail(
            kill_id=row["kill_id"],
            fetched_at=row["fetched_at"],
            fetch_status=row["fetch_status"],
            fetch_attempts=row["fetch_attempts"],
            victim_character_id=row["victim_character_id"],
            victim_ship_type_id=row["victim_ship_type_id"],
            victim_corporation_id=row["victim_corporation_id"],
            victim_alliance_id=row["victim_alliance_id"],
            victim_damage_taken=row["victim_damage_taken"],
            attacker_count=row["attacker_count"],
            final_blow_character_id=row["final_blow_character_id"],
            final_blow_ship_type_id=row["final_blow_ship_type_id"],
            final_blow_corporation_id=row["final_blow_corporation_id"],
            attackers_json=row["attackers_json"],
            items_json=row["items_json"],
            position_json=row["position_json"],
        )

    async def get_esi_fetch_attempts(self, kill_id: int) -> int:
        """Get number of ESI fetch attempts for a killmail."""
        cursor = await self.db.execute(
            "SELECT attempts FROM esi_fetch_attempts WHERE kill_id = ?",
            (kill_id,),
        )
        row = await cursor.fetchone()
        return row["attempts"] if row else 0

    async def increment_esi_fetch_attempts(self, kill_id: int, error: str | None = None) -> None:
        """Increment ESI fetch attempt counter."""
        now = int(time.time())
        await self.db.execute(
            """
            INSERT INTO esi_fetch_attempts (kill_id, attempts, last_attempt_at, last_error)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(kill_id) DO UPDATE SET
                attempts = attempts + 1,
                last_attempt_at = ?,
                last_error = ?
            """,
            (kill_id, now, error, now, error),
        )
        await self.db.commit()

    async def delete_esi_fetch_attempts(self, kill_id: int) -> None:
        """Delete ESI fetch attempts record."""
        await self.db.execute(
            "DELETE FROM esi_fetch_attempts WHERE kill_id = ?",
            (kill_id,),
        )
        await self.db.commit()

    async def query_kills(
        self,
        systems: list[int] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        min_value: int | None = None,
        limit: int = 100,
        cursor: tuple[int, int] | None = None,
    ) -> list[KillmailRecord]:
        """Query killmails with optional filters."""
        conditions: list[str] = []
        params: list[int | float] = []

        if systems:
            placeholders = ",".join("?" * len(systems))
            conditions.append(f"solar_system_id IN ({placeholders})")
            params.extend(systems)

        if since:
            conditions.append("kill_time >= ?")
            params.append(int(since.timestamp()))

        if until:
            conditions.append("kill_time <= ?")
            params.append(int(until.timestamp()))

        if min_value is not None:
            conditions.append("zkb_total_value >= ?")
            params.append(min_value)

        if cursor:
            cursor_time, cursor_id = cursor
            conditions.append("(kill_time, kill_id) < (?, ?)")
            params.append(cursor_time)
            params.append(cursor_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        query = f"""
            SELECT kill_id, kill_time, solar_system_id, zkb_hash,
                   zkb_total_value, zkb_points, zkb_is_npc, zkb_is_solo, zkb_is_awox,
                   ingested_at, victim_ship_type_id, victim_corporation_id, victim_alliance_id
            FROM killmails
            WHERE {where_clause}
            ORDER BY kill_time DESC, kill_id DESC
            LIMIT ?
        """

        cursor_result = await self.db.execute(query, params)
        rows = await cursor_result.fetchall()

        return [self._row_to_killmail(row) for row in rows]

    async def get_kill(self, kill_id: int) -> KillmailRecord | None:
        """Get a single killmail by ID."""
        cursor = await self.db.execute(
            """
            SELECT kill_id, kill_time, solar_system_id, zkb_hash,
                   zkb_total_value, zkb_points, zkb_is_npc, zkb_is_solo, zkb_is_awox,
                   ingested_at, victim_ship_type_id, victim_corporation_id, victim_alliance_id
            FROM killmails
            WHERE kill_id = ?
            """,
            (kill_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_killmail(row)

    def _row_to_killmail(self, row: aiosqlite.Row) -> KillmailRecord:
        """Convert a database row to KillmailRecord."""
        return KillmailRecord(
            kill_id=row["kill_id"],
            kill_time=row["kill_time"],
            solar_system_id=row["solar_system_id"],
            zkb_hash=row["zkb_hash"],
            zkb_total_value=row["zkb_total_value"],
            zkb_points=row["zkb_points"],
            zkb_is_npc=bool(row["zkb_is_npc"]),
            zkb_is_solo=bool(row["zkb_is_solo"]),
            zkb_is_awox=bool(row["zkb_is_awox"]),
            ingested_at=row["ingested_at"],
            victim_ship_type_id=row["victim_ship_type_id"],
            victim_corporation_id=row["victim_corporation_id"],
            victim_alliance_id=row["victim_alliance_id"],
        )

    # -------------------------------------------------------------------------
    # Worker State Management
    # -------------------------------------------------------------------------

    async def get_worker_state(self, worker_name: str) -> WorkerState | None:
        """Get worker checkpoint state."""
        cursor = await self.db.execute(
            """
            SELECT worker_name, last_processed_time, last_poll_at, consecutive_failures
            FROM worker_state
            WHERE worker_name = ?
            """,
            (worker_name,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        return WorkerState(
            worker_name=row["worker_name"],
            last_processed_time=row["last_processed_time"],
            last_poll_at=row["last_poll_at"],
            consecutive_failures=row["consecutive_failures"],
        )

    async def update_worker_state(
        self,
        worker_name: str,
        last_processed_time: int | None = None,
        last_poll_at: int | None = None,
        consecutive_failures: int | None = None,
    ) -> None:
        """Update worker state fields."""
        # Build upsert with only non-None fields
        updates: list[str] = []
        params: list[int | str] = []

        if last_processed_time is not None:
            updates.append("last_processed_time = ?")
            params.append(last_processed_time)

        if last_poll_at is not None:
            updates.append("last_poll_at = ?")
            params.append(last_poll_at)

        if consecutive_failures is not None:
            updates.append("consecutive_failures = ?")
            params.append(consecutive_failures)

        if not updates:
            return

        # Prepare default values for insert
        default_time = last_processed_time if last_processed_time is not None else int(time.time())

        await self.db.execute(
            f"""
            INSERT INTO worker_state (worker_name, last_processed_time, last_poll_at, consecutive_failures)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(worker_name) DO UPDATE SET {", ".join(updates)}
            """,
            (worker_name, default_time, last_poll_at, consecutive_failures or 0, *params),
        )
        await self.db.commit()

    # -------------------------------------------------------------------------
    # Duplicate Detection and Delivery Tracking
    # -------------------------------------------------------------------------

    async def is_kill_processed(self, worker_name: str, kill_id: int) -> bool:
        """Check if a kill has already been processed by this worker."""
        cursor = await self.db.execute(
            """
            SELECT 1 FROM processed_kills
            WHERE worker_name = ? AND kill_id = ?
            """,
            (worker_name, kill_id),
        )
        row = await cursor.fetchone()
        return row is not None

    async def mark_kill_processed(
        self, worker_name: str, kill_id: int, status: str = "delivered"
    ) -> None:
        """Record that a kill has been processed."""
        now = int(time.time())
        await self.db.execute(
            """
            INSERT OR REPLACE INTO processed_kills (
                worker_name, kill_id, processed_at, delivery_status, delivery_attempts
            ) VALUES (?, ?, ?, ?, 1)
            """,
            (worker_name, kill_id, now, status),
        )
        await self.db.commit()

    async def get_delivery_attempts(self, worker_name: str, kill_id: int) -> int:
        """Get number of delivery attempts for a kill."""
        cursor = await self.db.execute(
            """
            SELECT delivery_attempts FROM processed_kills
            WHERE worker_name = ? AND kill_id = ?
            """,
            (worker_name, kill_id),
        )
        row = await cursor.fetchone()
        return row["delivery_attempts"] if row else 0

    async def increment_delivery_attempts(self, worker_name: str, kill_id: int) -> None:
        """Increment delivery attempt counter."""
        now = int(time.time())
        await self.db.execute(
            """
            INSERT INTO processed_kills (worker_name, kill_id, processed_at, delivery_status, delivery_attempts)
            VALUES (?, ?, ?, 'pending', 1)
            ON CONFLICT(worker_name, kill_id) DO UPDATE SET
                delivery_attempts = delivery_attempts + 1,
                processed_at = ?
            """,
            (worker_name, kill_id, now, now),
        )
        await self.db.commit()

    # -------------------------------------------------------------------------
    # ESI Fetch Coordination
    # -------------------------------------------------------------------------

    async def try_claim_esi_fetch(self, kill_id: int, worker_name: str) -> bool:
        """Attempt to claim exclusive ESI fetch rights for a killmail."""
        now = int(time.time())
        cursor = await self.db.execute(
            """
            INSERT OR IGNORE INTO esi_fetch_claims (kill_id, claimed_by, claimed_at)
            VALUES (?, ?, ?)
            """,
            (kill_id, worker_name, now),
        )
        await self.db.commit()

        # Check if we got the claim
        if cursor.rowcount > 0:
            return True

        # Check if the existing claim is ours
        check = await self.db.execute(
            "SELECT claimed_by FROM esi_fetch_claims WHERE kill_id = ?",
            (kill_id,),
        )
        row = await check.fetchone()
        return row is not None and row["claimed_by"] == worker_name

    async def delete_esi_claim(self, kill_id: int) -> None:
        """Release ESI fetch claim."""
        await self.db.execute(
            "DELETE FROM esi_fetch_claims WHERE kill_id = ?",
            (kill_id,),
        )
        await self.db.commit()

    async def get_esi_claim(self, kill_id: int) -> ESIClaim | None:
        """Get current ESI fetch claim for inspection."""
        cursor = await self.db.execute(
            """
            SELECT kill_id, claimed_by, claimed_at
            FROM esi_fetch_claims
            WHERE kill_id = ?
            """,
            (kill_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        return ESIClaim(
            kill_id=row["kill_id"],
            claimed_by=row["claimed_by"],
            claimed_at=row["claimed_at"],
        )

    # -------------------------------------------------------------------------
    # Maintenance Operations
    # -------------------------------------------------------------------------

    async def expunge_before(self, cutoff: datetime) -> int:
        """Delete killmails older than cutoff."""
        cutoff_ts = int(cutoff.timestamp())
        cursor = await self.db.execute(
            "DELETE FROM killmails WHERE kill_time < ?",
            (cutoff_ts,),
        )
        await self.db.commit()
        return cursor.rowcount

    async def expunge_processed_kills(self, older_than_seconds: int = 3600) -> int:
        """Delete old processed_kills entries."""
        cutoff = int(time.time()) - older_than_seconds
        cursor = await self.db.execute(
            "DELETE FROM processed_kills WHERE processed_at < ?",
            (cutoff,),
        )
        await self.db.commit()
        return cursor.rowcount

    async def expunge_stale_esi_claims(self, threshold_seconds: int = 60) -> int:
        """Delete abandoned ESI fetch claims."""
        cutoff = int(time.time()) - threshold_seconds
        cursor = await self.db.execute(
            "DELETE FROM esi_fetch_claims WHERE claimed_at < ?",
            (cutoff,),
        )
        await self.db.commit()
        return cursor.rowcount

    async def expunge_orphaned_esi_attempts(self) -> int:
        """Delete ESI fetch attempts for expunged killmails."""
        cursor = await self.db.execute(
            """
            DELETE FROM esi_fetch_attempts
            WHERE kill_id NOT IN (SELECT kill_id FROM killmails)
            """
        )
        await self.db.commit()
        return cursor.rowcount

    async def expunge_orphaned_state(self, active_profiles: set[str]) -> int:
        """Remove state for deleted notification profiles."""
        if not active_profiles:
            # If no profiles, don't delete anything (safety)
            return 0

        placeholders = ",".join("?" * len(active_profiles))
        profile_list = list(active_profiles)

        # Delete from worker_state
        cursor1 = await self.db.execute(
            f"DELETE FROM worker_state WHERE worker_name NOT IN ({placeholders})",
            profile_list,
        )
        count1 = cursor1.rowcount

        # Delete from processed_kills
        cursor2 = await self.db.execute(
            f"DELETE FROM processed_kills WHERE worker_name NOT IN ({placeholders})",
            profile_list,
        )
        count2 = cursor2.rowcount

        await self.db.commit()
        return count1 + count2

    async def optimize_database(self) -> None:
        """Run storage optimization."""
        await self.db.execute("PRAGMA optimize")
        await self.db.commit()
        logger.debug("Database optimization complete")

    async def get_stats(self) -> StoreStats:
        """Get storage statistics for observability."""
        # Count killmails
        cursor = await self.db.execute("SELECT COUNT(*) FROM killmails")
        row = await cursor.fetchone()
        total_killmails = row[0]

        # Count ESI details
        cursor = await self.db.execute(
            "SELECT COUNT(*) FROM esi_details WHERE fetch_status = 'success'"
        )
        row = await cursor.fetchone()
        total_esi_details = row[0]

        # Count unfetchable
        cursor = await self.db.execute(
            "SELECT COUNT(*) FROM esi_details WHERE fetch_status = 'unfetchable'"
        )
        row = await cursor.fetchone()
        total_esi_unfetchable = row[0]

        # Get time bounds
        cursor = await self.db.execute("SELECT MIN(kill_time), MAX(kill_time) FROM killmails")
        row = await cursor.fetchone()
        oldest_time = row[0]
        newest_time = row[1]

        # Get database size
        try:
            db_size = self.db_path.stat().st_size
        except OSError:
            db_size = 0

        return StoreStats(
            total_killmails=total_killmails,
            total_esi_details=total_esi_details,
            total_esi_unfetchable=total_esi_unfetchable,
            oldest_killmail_time=oldest_time,
            newest_killmail_time=newest_time,
            database_size_bytes=db_size,
        )
