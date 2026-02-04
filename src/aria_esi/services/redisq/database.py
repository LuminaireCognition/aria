"""
RedisQ Database Operations.

Handles persistence of realtime kills and service state.
Uses the shared ARIA database (aria.db).
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.config import get_settings
from ...core.logging import get_logger

if TYPE_CHECKING:
    from .entity_filter import EntityMatchResult
    from .models import ProcessedKill

logger = get_logger(__name__)


class RealtimeKillsDatabase:
    """
    Database operations for realtime kill data.

    Uses the shared ARIA SQLite database. The schema is created
    by MarketDatabase initialization (SCHEMA_VERSION >= 5).
    """

    def __init__(self, db_path: Path | str | None = None, ensure_schema: bool = True):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database. Defaults to settings.db_path
            ensure_schema: If True, ensure MarketDatabase has initialized schema.
                          Set to False for testing with pre-created tables.
        """
        if db_path is None:
            db_path = get_settings().db_path
        self.db_path = Path(db_path)
        self._ensure_schema = ensure_schema

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: sqlite3.Connection | None = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            # Ensure schema is initialized via MarketDatabase first
            # This triggers migrations if needed
            if self._ensure_schema:
                self._run_schema_init()

            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row

        return self._conn

    def _run_schema_init(self) -> None:
        """Ensure the database schema is up to date via MarketDatabase."""
        from ...mcp.market.database import MarketDatabase

        # MarketDatabase initialization runs migrations
        market_db = MarketDatabase(self.db_path)
        market_db._get_connection()
        market_db.close()

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # =========================================================================
    # Kill Operations
    # =========================================================================

    def save_kill(
        self,
        kill: ProcessedKill,
        entity_match: EntityMatchResult | None = None,
    ) -> None:
        """
        Save a single processed kill to the database.

        Args:
            kill: ProcessedKill to save
            entity_match: Optional entity match result for watched entity tracking
        """
        import json

        conn = self._get_connection()

        # Build base row
        row = kill.to_db_row()

        # Add entity match data
        watched_match = 1 if (entity_match and entity_match.has_match) else 0
        watched_ids = (
            json.dumps(entity_match.all_matched_ids)
            if (entity_match and entity_match.has_match)
            else None
        )

        conn.execute(
            """
            INSERT OR REPLACE INTO realtime_kills (
                kill_id, kill_time, solar_system_id, victim_ship_type_id,
                victim_corporation_id, victim_alliance_id, attacker_count,
                attacker_corps, attacker_alliances, attacker_ship_types,
                final_blow_ship_type_id, total_value, is_pod_kill,
                watched_entity_match, watched_entity_ids
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row + (watched_match, watched_ids),
        )
        conn.commit()

    def save_kills_batch(self, kills: list[ProcessedKill]) -> int:
        """
        Save multiple kills in a transaction.

        Args:
            kills: List of ProcessedKill objects

        Returns:
            Number of rows inserted
        """
        if not kills:
            return 0

        conn = self._get_connection()
        cursor = conn.executemany(
            """
            INSERT OR REPLACE INTO realtime_kills (
                kill_id, kill_time, solar_system_id, victim_ship_type_id,
                victim_corporation_id, victim_alliance_id, attacker_count,
                attacker_corps, attacker_alliances, attacker_ship_types,
                final_blow_ship_type_id, total_value, is_pod_kill
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [k.to_db_row() for k in kills],
        )
        conn.commit()
        return cursor.rowcount

    def get_kill(self, kill_id: int) -> ProcessedKill | None:
        """
        Get a single kill by ID.

        Args:
            kill_id: Kill ID to retrieve

        Returns:
            ProcessedKill if found, None otherwise
        """
        from .models import ProcessedKill

        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM realtime_kills WHERE kill_id = ?",
            (kill_id,),
        ).fetchone()

        return ProcessedKill.from_db_row(row) if row else None

    def get_recent_kills(
        self,
        system_id: int | None = None,
        since_minutes: int = 60,
        limit: int = 100,
    ) -> list[ProcessedKill]:
        """
        Get recent kills, optionally filtered by system.

        Args:
            system_id: Filter to specific system (None = all systems)
            since_minutes: How far back to look
            limit: Maximum results to return

        Returns:
            List of ProcessedKill objects, newest first
        """
        from .models import ProcessedKill

        conn = self._get_connection()
        cutoff = int(time.time()) - (since_minutes * 60)

        if system_id is not None:
            rows = conn.execute(
                """
                SELECT * FROM realtime_kills
                WHERE solar_system_id = ? AND kill_time > ?
                ORDER BY kill_time DESC
                LIMIT ?
                """,
                (system_id, cutoff, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM realtime_kills
                WHERE kill_time > ?
                ORDER BY kill_time DESC
                LIMIT ?
                """,
                (cutoff, limit),
            ).fetchall()

        return [ProcessedKill.from_db_row(row) for row in rows]

    def get_kills_in_systems(
        self,
        system_ids: list[int],
        since_minutes: int = 60,
    ) -> list[ProcessedKill]:
        """
        Get recent kills in multiple systems.

        Args:
            system_ids: System IDs to query
            since_minutes: How far back to look

        Returns:
            List of ProcessedKill objects, newest first
        """
        from .models import ProcessedKill

        if not system_ids:
            return []

        conn = self._get_connection()
        cutoff = int(time.time()) - (since_minutes * 60)

        placeholders = ",".join("?" * len(system_ids))
        params = system_ids + [cutoff]

        rows = conn.execute(
            f"""
            SELECT * FROM realtime_kills
            WHERE solar_system_id IN ({placeholders}) AND kill_time > ?
            ORDER BY kill_time DESC
            """,
            params,
        ).fetchall()

        return [ProcessedKill.from_db_row(row) for row in rows]

    def get_latest_kill_time(self) -> datetime | None:
        """
        Get the timestamp of the most recent kill in the database.

        Returns:
            Datetime of latest kill, or None if no kills
        """
        conn = self._get_connection()
        row = conn.execute("SELECT MAX(kill_time) as max_time FROM realtime_kills").fetchone()

        if row and row["max_time"]:
            return datetime.fromtimestamp(row["max_time"])
        return None

    def kill_exists(self, kill_id: int) -> bool:
        """
        Check if a kill already exists in the database.

        Args:
            kill_id: Kill ID to check

        Returns:
            True if exists, False otherwise
        """
        conn = self._get_connection()
        row = conn.execute(
            "SELECT 1 FROM realtime_kills WHERE kill_id = ?",
            (kill_id,),
        ).fetchone()
        return row is not None

    def cleanup_old_kills(self, retention_hours: int = 24) -> int:
        """
        Remove kills older than retention period.

        Args:
            retention_hours: Hours to retain kills

        Returns:
            Number of rows deleted
        """
        conn = self._get_connection()
        cutoff = int(time.time()) - (retention_hours * 3600)

        cursor = conn.execute(
            "DELETE FROM realtime_kills WHERE kill_time < ?",
            (cutoff,),
        )
        conn.commit()

        deleted = cursor.rowcount
        if deleted > 0:
            logger.info("Cleaned up %d old kills (retention: %dh)", deleted, retention_hours)

        return deleted

    def get_watched_entity_kills(
        self,
        since_minutes: int = 60,
        system_ids: list[int] | None = None,
        limit: int = 100,
    ) -> list[ProcessedKill]:
        """
        Get recent kills involving watched entities.

        Args:
            since_minutes: How far back to look
            system_ids: Optional filter to specific systems
            limit: Maximum results to return

        Returns:
            List of ProcessedKill objects involving watched entities
        """
        from .models import ProcessedKill

        conn = self._get_connection()
        cutoff = int(time.time()) - (since_minutes * 60)

        if system_ids:
            placeholders = ",".join("?" * len(system_ids))
            params = system_ids + [cutoff, limit]
            rows = conn.execute(
                f"""
                SELECT * FROM realtime_kills
                WHERE watched_entity_match = 1
                  AND solar_system_id IN ({placeholders})
                  AND kill_time > ?
                ORDER BY kill_time DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM realtime_kills
                WHERE watched_entity_match = 1
                  AND kill_time > ?
                ORDER BY kill_time DESC
                LIMIT ?
                """,
                (cutoff, limit),
            ).fetchall()

        return [ProcessedKill.from_db_row(row) for row in rows]

    def get_watched_entity_kill_count(self, since_minutes: int = 60) -> int:
        """
        Get count of kills involving watched entities.

        Args:
            since_minutes: How far back to look

        Returns:
            Number of kills
        """
        conn = self._get_connection()
        cutoff = int(time.time()) - (since_minutes * 60)

        row = conn.execute(
            """
            SELECT COUNT(*) FROM realtime_kills
            WHERE watched_entity_match = 1 AND kill_time > ?
            """,
            (cutoff,),
        ).fetchone()

        return row[0] if row else 0

    def get_kill_count(self, since_minutes: int | None = None) -> int:
        """
        Get count of kills in database.

        Args:
            since_minutes: Optional time filter

        Returns:
            Number of kills
        """
        conn = self._get_connection()

        if since_minutes is not None:
            cutoff = int(time.time()) - (since_minutes * 60)
            row = conn.execute(
                "SELECT COUNT(*) FROM realtime_kills WHERE kill_time > ?",
                (cutoff,),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM realtime_kills").fetchone()

        return row[0] if row else 0

    # =========================================================================
    # State Operations
    # =========================================================================

    def get_state(self, key: str) -> str | None:
        """
        Get a state value.

        Args:
            key: State key

        Returns:
            State value or None if not found
        """
        conn = self._get_connection()
        row = conn.execute(
            "SELECT value FROM redisq_state WHERE key = ?",
            (key,),
        ).fetchone()
        return row["value"] if row else None

    def set_state(self, key: str, value: str) -> None:
        """
        Set a state value.

        Args:
            key: State key
            value: State value
        """
        conn = self._get_connection()
        now = int(time.time())
        conn.execute(
            """
            INSERT OR REPLACE INTO redisq_state (key, value, updated_at)
            VALUES (?, ?, ?)
            """,
            (key, value, now),
        )
        conn.commit()

    def get_last_poll_time(self) -> datetime | None:
        """
        Get the timestamp of the last successful poll.

        Returns:
            Datetime of last poll, or None
        """
        value = self.get_state("last_poll_time")
        if value:
            return datetime.fromtimestamp(float(value))
        return None

    def set_last_poll_time(self, timestamp: datetime) -> None:
        """
        Set the timestamp of the last successful poll.

        Args:
            timestamp: Poll timestamp
        """
        self.set_state("last_poll_time", str(timestamp.timestamp()))

    def get_queue_id(self) -> str | None:
        """
        Get the persisted RedisQ queue ID.

        Returns:
            Queue ID or None if not set
        """
        return self.get_state("queue_id")

    def set_queue_id(self, queue_id: str) -> None:
        """
        Set the RedisQ queue ID.

        Args:
            queue_id: Queue ID to persist
        """
        self.set_state("queue_id", queue_id)

    def get_stats(self) -> dict:
        """
        Get database statistics for realtime kills.

        Returns:
            Dict with counts and freshness info
        """
        conn = self._get_connection()
        now = int(time.time())

        total_count = conn.execute("SELECT COUNT(*) FROM realtime_kills").fetchone()[0]

        # Kills in last hour
        hour_ago = now - 3600
        hour_count = conn.execute(
            "SELECT COUNT(*) FROM realtime_kills WHERE kill_time > ?",
            (hour_ago,),
        ).fetchone()[0]

        # Latest kill time
        latest_row = conn.execute("SELECT MAX(kill_time) FROM realtime_kills").fetchone()
        latest_time = latest_row[0] if latest_row[0] else None

        # Last poll time
        last_poll = self.get_last_poll_time()

        return {
            "total_kills": total_count,
            "kills_last_hour": hour_count,
            "latest_kill_time": datetime.fromtimestamp(latest_time).isoformat()
            if latest_time
            else None,
            "last_poll_time": last_poll.isoformat() if last_poll else None,
            "queue_id": self.get_queue_id(),
        }


# =============================================================================
# Module-level singleton
# =============================================================================

_realtime_db: RealtimeKillsDatabase | None = None


def get_realtime_database() -> RealtimeKillsDatabase:
    """Get or create the realtime kills database singleton."""
    global _realtime_db
    if _realtime_db is None:
        _realtime_db = RealtimeKillsDatabase()
    return _realtime_db


def reset_realtime_database() -> None:
    """
    Reset the realtime database singleton.

    Closes the existing connection and clears the singleton.
    Use for testing to ensure clean state between tests.
    """
    global _realtime_db
    if _realtime_db is not None:
        _realtime_db.close()
        _realtime_db = None
