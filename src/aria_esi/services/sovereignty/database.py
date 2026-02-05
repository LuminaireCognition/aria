"""
Sovereignty Database.

SQLite-backed storage for sovereignty data with schema migrations.
Follows the pattern from mcp/market/database.py.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.config import get_settings
from ...core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Schema version for migrations
SCHEMA_VERSION = 1

# Database file name (separate from market database)
DATABASE_NAME = "sovereignty.db"


# =============================================================================
# Database Schema
# =============================================================================

SCHEMA_SQL = """
-- Sovereignty map from ESI GET /sovereignty/map/
CREATE TABLE IF NOT EXISTS sovereignty_map (
    system_id INTEGER PRIMARY KEY,
    alliance_id INTEGER,              -- NULL = unclaimed/NPC
    corporation_id INTEGER,           -- Corporation holding sov (if any)
    faction_id INTEGER,               -- For NPC null-sec
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sov_alliance ON sovereignty_map(alliance_id);
CREATE INDEX IF NOT EXISTS idx_sov_faction ON sovereignty_map(faction_id);

-- Alliance name cache
CREATE TABLE IF NOT EXISTS alliances (
    alliance_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    ticker TEXT NOT NULL,
    executor_corporation_id INTEGER,
    faction_id INTEGER,
    updated_at INTEGER NOT NULL
);

-- Coalition mappings (from YAML config)
CREATE TABLE IF NOT EXISTS coalitions (
    coalition_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    aliases TEXT NOT NULL,           -- JSON array of alias strings
    updated_at INTEGER NOT NULL
);

-- Coalition membership (alliance -> coalition)
CREATE TABLE IF NOT EXISTS coalition_members (
    alliance_id INTEGER PRIMARY KEY,
    coalition_id TEXT NOT NULL,
    added_at INTEGER NOT NULL,
    FOREIGN KEY (coalition_id) REFERENCES coalitions(coalition_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_coalition_members_coalition ON coalition_members(coalition_id);

-- Database metadata
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Insert schema version
INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '1');
"""


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SovereigntyRecord:
    """Sovereignty record from database."""

    system_id: int
    alliance_id: int | None
    corporation_id: int | None
    faction_id: int | None
    updated_at: int


@dataclass
class AllianceRecord:
    """Alliance record from database."""

    alliance_id: int
    name: str
    ticker: str
    executor_corporation_id: int | None
    faction_id: int | None
    updated_at: int


@dataclass
class CoalitionRecord:
    """Coalition record from database."""

    coalition_id: str
    display_name: str
    aliases: list[str]
    updated_at: int


# =============================================================================
# Database Class
# =============================================================================


class SovereigntyDatabase:
    """
    SQLite database for sovereignty data.

    Handles sovereignty caching, alliance names, and coalition mappings.
    Thread-safe for read operations; write operations should be serialized.
    """

    def __init__(self, db_path: Path | str | None = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database. Defaults to {instance_root}/cache/sovereignty.db
        """
        if db_path is None:
            settings = get_settings()
            db_path = settings.cache_dir / DATABASE_NAME
        self.db_path = Path(db_path)

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: sqlite3.Connection | None = None
        self._initialized = False

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,  # Allow multi-thread reads
            )
            self._conn.row_factory = sqlite3.Row
            # Enable foreign key constraints for cascade deletes
            self._conn.execute("PRAGMA foreign_keys = ON")

            if not self._initialized:
                self._initialize_schema()
                self._initialized = True

        return self._conn

    def _initialize_schema(self) -> None:
        """Create database schema if needed and run migrations."""
        conn = self._conn
        if conn is None:
            return

        # Check current schema version
        current_version = self._get_schema_version()

        # Run migrations if needed
        if current_version < SCHEMA_VERSION:
            self._run_migrations(current_version)

        # Run full schema (IF NOT EXISTS is safe for existing tables)
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        logger.info("Sovereignty database initialized at %s", self.db_path)

    def _get_schema_version(self) -> int:
        """Get current schema version from metadata table."""
        conn = self._conn
        if conn is None:
            return 0

        try:
            row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
            return int(row["value"]) if row else 0
        except sqlite3.OperationalError:
            # metadata table doesn't exist yet
            return 0

    def _run_migrations(self, from_version: int) -> None:
        """Run schema migrations from current version to SCHEMA_VERSION."""
        conn = self._conn
        if conn is None:
            return

        # Future migrations will be added here
        # Migration 1 -> 2 example:
        # if from_version < 2:
        #     logger.info("Running migration 1 -> 2: ...")
        #     conn.executescript("""...""")
        #     conn.commit()

        pass  # No migrations needed for version 1

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # =========================================================================
    # Sovereignty Map Operations
    # =========================================================================

    def get_sovereignty(self, system_id: int) -> SovereigntyRecord | None:
        """
        Get sovereignty for a single system.

        Args:
            system_id: Solar system ID

        Returns:
            SovereigntyRecord if found, None otherwise
        """
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM sovereignty_map WHERE system_id = ?",
            (system_id,),
        ).fetchone()

        return self._row_to_sovereignty(row) if row else None

    def get_sovereignty_batch(
        self, system_ids: Sequence[int]
    ) -> dict[int, SovereigntyRecord]:
        """
        Get sovereignty for multiple systems.

        Args:
            system_ids: System IDs to look up

        Returns:
            Dict mapping system_id to SovereigntyRecord
        """
        if not system_ids:
            return {}

        conn = self._get_connection()
        placeholders = ",".join("?" * len(system_ids))
        rows = conn.execute(
            f"SELECT * FROM sovereignty_map WHERE system_id IN ({placeholders})",
            list(system_ids),
        ).fetchall()

        return {row["system_id"]: self._row_to_sovereignty(row) for row in rows}

    def get_systems_by_alliance(self, alliance_id: int) -> list[int]:
        """
        Get all systems held by an alliance.

        Args:
            alliance_id: Alliance ID

        Returns:
            List of system IDs
        """
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT system_id FROM sovereignty_map WHERE alliance_id = ?",
            (alliance_id,),
        ).fetchall()

        return [row["system_id"] for row in rows]

    def get_systems_by_faction(self, faction_id: int) -> list[int]:
        """
        Get all systems held by an NPC faction.

        Args:
            faction_id: NPC faction ID

        Returns:
            List of system IDs
        """
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT system_id FROM sovereignty_map WHERE faction_id = ?",
            (faction_id,),
        ).fetchall()

        return [row["system_id"] for row in rows]

    def save_sovereignty(self, record: SovereigntyRecord) -> None:
        """Save a single sovereignty record."""
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO sovereignty_map
            (system_id, alliance_id, corporation_id, faction_id, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.system_id,
                record.alliance_id,
                record.corporation_id,
                record.faction_id,
                record.updated_at,
            ),
        )
        conn.commit()

    def save_sovereignty_batch(self, records: Sequence[SovereigntyRecord]) -> int:
        """
        Save multiple sovereignty records in a transaction.

        Args:
            records: Records to save

        Returns:
            Number of rows inserted/updated
        """
        if not records:
            return 0

        conn = self._get_connection()
        conn.executemany(
            """
            INSERT OR REPLACE INTO sovereignty_map
            (system_id, alliance_id, corporation_id, faction_id, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (r.system_id, r.alliance_id, r.corporation_id, r.faction_id, r.updated_at)
                for r in records
            ],
        )
        conn.commit()
        return len(records)

    def clear_sovereignty(self) -> int:
        """
        Clear all sovereignty data.

        Returns:
            Number of rows deleted
        """
        conn = self._get_connection()
        cursor = conn.execute("DELETE FROM sovereignty_map")
        conn.commit()
        return cursor.rowcount

    def _row_to_sovereignty(self, row: sqlite3.Row) -> SovereigntyRecord:
        """Convert database row to SovereigntyRecord."""
        return SovereigntyRecord(
            system_id=row["system_id"],
            alliance_id=row["alliance_id"],
            corporation_id=row["corporation_id"],
            faction_id=row["faction_id"],
            updated_at=row["updated_at"],
        )

    # =========================================================================
    # Alliance Operations
    # =========================================================================

    def get_alliance(self, alliance_id: int) -> AllianceRecord | None:
        """Get alliance info by ID."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM alliances WHERE alliance_id = ?",
            (alliance_id,),
        ).fetchone()

        return self._row_to_alliance(row) if row else None

    def get_alliances_batch(
        self, alliance_ids: Sequence[int]
    ) -> dict[int, AllianceRecord]:
        """Get multiple alliances by ID."""
        if not alliance_ids:
            return {}

        conn = self._get_connection()
        placeholders = ",".join("?" * len(alliance_ids))
        rows = conn.execute(
            f"SELECT * FROM alliances WHERE alliance_id IN ({placeholders})",
            list(alliance_ids),
        ).fetchall()

        return {row["alliance_id"]: self._row_to_alliance(row) for row in rows}

    def save_alliance(self, record: AllianceRecord) -> None:
        """Save alliance info."""
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO alliances
            (alliance_id, name, ticker, executor_corporation_id, faction_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.alliance_id,
                record.name,
                record.ticker,
                record.executor_corporation_id,
                record.faction_id,
                record.updated_at,
            ),
        )
        conn.commit()

    def save_alliances_batch(self, records: Sequence[AllianceRecord]) -> int:
        """Save multiple alliance records."""
        if not records:
            return 0

        conn = self._get_connection()
        conn.executemany(
            """
            INSERT OR REPLACE INTO alliances
            (alliance_id, name, ticker, executor_corporation_id, faction_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r.alliance_id,
                    r.name,
                    r.ticker,
                    r.executor_corporation_id,
                    r.faction_id,
                    r.updated_at,
                )
                for r in records
            ],
        )
        conn.commit()
        return len(records)

    def _row_to_alliance(self, row: sqlite3.Row) -> AllianceRecord:
        """Convert database row to AllianceRecord."""
        return AllianceRecord(
            alliance_id=row["alliance_id"],
            name=row["name"],
            ticker=row["ticker"],
            executor_corporation_id=row["executor_corporation_id"],
            faction_id=row["faction_id"],
            updated_at=row["updated_at"],
        )

    # =========================================================================
    # Coalition Operations
    # =========================================================================

    def get_coalition(self, coalition_id: str) -> CoalitionRecord | None:
        """Get coalition by ID."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM coalitions WHERE coalition_id = ?",
            (coalition_id,),
        ).fetchone()

        return self._row_to_coalition(row) if row else None

    def get_coalition_by_alias(self, alias: str) -> CoalitionRecord | None:
        """
        Find coalition by alias (case-insensitive).

        Args:
            alias: Alias to search for (e.g., "goons", "bees")

        Returns:
            CoalitionRecord if found
        """
        conn = self._get_connection()
        alias_lower = alias.lower()

        # Search in aliases JSON array
        rows = conn.execute(
            "SELECT * FROM coalitions"
        ).fetchall()

        for row in rows:
            aliases = json.loads(row["aliases"])
            if alias_lower in [a.lower() for a in aliases]:
                return self._row_to_coalition(row)
            # Also check coalition_id and display_name
            if (
                row["coalition_id"].lower() == alias_lower
                or row["display_name"].lower() == alias_lower
            ):
                return self._row_to_coalition(row)

        return None

    def get_all_coalitions(self) -> list[CoalitionRecord]:
        """Get all coalitions."""
        conn = self._get_connection()
        rows = conn.execute("SELECT * FROM coalitions ORDER BY display_name").fetchall()
        return [self._row_to_coalition(row) for row in rows]

    def get_coalition_for_alliance(self, alliance_id: int) -> str | None:
        """
        Get coalition ID for an alliance.

        Args:
            alliance_id: Alliance ID

        Returns:
            Coalition ID if alliance is in a coalition, None otherwise
        """
        conn = self._get_connection()
        row = conn.execute(
            "SELECT coalition_id FROM coalition_members WHERE alliance_id = ?",
            (alliance_id,),
        ).fetchone()

        return row["coalition_id"] if row else None

    def get_coalition_alliances(self, coalition_id: str) -> list[int]:
        """Get all alliance IDs in a coalition."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT alliance_id FROM coalition_members WHERE coalition_id = ?",
            (coalition_id,),
        ).fetchall()

        return [row["alliance_id"] for row in rows]

    def save_coalition(self, record: CoalitionRecord) -> None:
        """Save coalition record."""
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO coalitions
            (coalition_id, display_name, aliases, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                record.coalition_id,
                record.display_name,
                json.dumps(record.aliases),
                record.updated_at,
            ),
        )
        conn.commit()

    def save_coalition_members(
        self, coalition_id: str, alliance_ids: Sequence[int]
    ) -> int:
        """
        Save coalition membership (replaces existing).

        Args:
            coalition_id: Coalition ID
            alliance_ids: Alliance IDs to add

        Returns:
            Number of members added
        """
        conn = self._get_connection()
        now = int(time.time())

        # Remove existing members for this coalition
        conn.execute(
            "DELETE FROM coalition_members WHERE coalition_id = ?",
            (coalition_id,),
        )

        # Add new members
        if alliance_ids:
            conn.executemany(
                """
                INSERT OR REPLACE INTO coalition_members
                (alliance_id, coalition_id, added_at)
                VALUES (?, ?, ?)
                """,
                [(aid, coalition_id, now) for aid in alliance_ids],
            )

        conn.commit()
        return len(alliance_ids)

    def clear_coalitions(self) -> int:
        """
        Remove all coalition data from the database.

        Used before reloading coalition data to ensure deleted coalitions
        from YAML don't persist as stale entries.

        Returns:
            Number of coalitions deleted
        """
        conn = self._get_connection()

        # Get count before deletion
        count = conn.execute("SELECT COUNT(*) FROM coalitions").fetchone()[0]

        # Clear members first (foreign key relationship)
        conn.execute("DELETE FROM coalition_members")
        conn.execute("DELETE FROM coalitions")

        conn.commit()
        return count

    def _row_to_coalition(self, row: sqlite3.Row) -> CoalitionRecord:
        """Convert database row to CoalitionRecord."""
        return CoalitionRecord(
            coalition_id=row["coalition_id"],
            display_name=row["display_name"],
            aliases=json.loads(row["aliases"]),
            updated_at=row["updated_at"],
        )

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict:
        """
        Get database statistics.

        Returns:
            Dict with counts and freshness info
        """
        conn = self._get_connection()
        now = int(time.time())

        sov_count = conn.execute("SELECT COUNT(*) FROM sovereignty_map").fetchone()[0]
        alliance_count = conn.execute("SELECT COUNT(*) FROM alliances").fetchone()[0]
        coalition_count = conn.execute("SELECT COUNT(*) FROM coalitions").fetchone()[0]

        # Get freshness
        sov_oldest = conn.execute(
            "SELECT MIN(updated_at) FROM sovereignty_map"
        ).fetchone()[0]
        sov_newest = conn.execute(
            "SELECT MAX(updated_at) FROM sovereignty_map"
        ).fetchone()[0]

        return {
            "sovereignty_count": sov_count,
            "alliance_count": alliance_count,
            "coalition_count": coalition_count,
            "sov_oldest_seconds": now - sov_oldest if sov_oldest else None,
            "sov_newest_seconds": now - sov_newest if sov_newest else None,
            "database_path": str(self.db_path),
            "database_size_kb": round(self.db_path.stat().st_size / 1024, 1)
            if self.db_path.exists()
            else 0,
        }


# =============================================================================
# Singleton
# =============================================================================

_sovereignty_db: SovereigntyDatabase | None = None


def get_sovereignty_database() -> SovereigntyDatabase:
    """Get or create the sovereignty database singleton."""
    global _sovereignty_db
    if _sovereignty_db is None:
        _sovereignty_db = SovereigntyDatabase()
    return _sovereignty_db


def reset_sovereignty_database() -> None:
    """
    Reset the sovereignty database singleton.

    Closes the existing connection and clears the singleton.
    Use for testing to ensure clean state between tests.
    """
    global _sovereignty_db
    if _sovereignty_db is not None:
        _sovereignty_db.close()
        _sovereignty_db = None
