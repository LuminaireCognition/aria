"""
Database Migration Runner for Killmail Store.

Applies versioned SQL migrations on startup to manage schema evolution.
See KILLMAIL_STORE_REDESIGN_PROPOSAL.md D9: Database Schema Migrations.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

logger = logging.getLogger(__name__)

# Directory containing migration SQL files
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class MigrationRunner:
    """
    Apply database migrations on startup.

    Migration files should be named: NNN_description.sql
    where NNN is a zero-padded version number (e.g., 001, 002).

    Migrations are applied in order and tracked in the schema_migrations table.
    """

    def __init__(self, db: aiosqlite.Connection):
        """
        Initialize the migration runner.

        Args:
            db: Open database connection
        """
        self.db = db

    async def run_migrations(self) -> int:
        """
        Apply pending migrations.

        Returns:
            Number of migrations applied.
        """
        await self._ensure_migrations_table()
        current_version = await self._get_current_version()
        applied = 0

        # Get all migration files sorted by version
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

        for migration_file in migration_files:
            version = self._parse_version(migration_file.name)
            if version is None:
                logger.warning("Skipping invalid migration file: %s", migration_file.name)
                continue

            if version > current_version:
                await self._apply_migration(version, migration_file)
                applied += 1

        if applied > 0:
            logger.info("Applied %d database migration(s)", applied)

        return applied

    async def _ensure_migrations_table(self) -> None:
        """Create schema_migrations table if it doesn't exist."""
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at INTEGER NOT NULL,
                description TEXT
            )
            """
        )
        await self.db.commit()

    async def _get_current_version(self) -> int:
        """
        Get the current schema version.

        Returns:
            Latest applied migration version, or 0 if none applied.
        """
        cursor = await self.db.execute("SELECT MAX(version) FROM schema_migrations")
        row = await cursor.fetchone()
        return row[0] if row and row[0] is not None else 0

    async def _apply_migration(self, version: int, path: Path) -> None:
        """
        Apply a single migration within a transaction.

        Args:
            version: Migration version number
            path: Path to the migration SQL file
        """
        sql = path.read_text()
        description = self._parse_description(path.name)

        logger.info("Applying migration %03d: %s", version, description)

        # Execute the migration script
        await self.db.executescript(sql)

        # Record the migration
        await self.db.execute(
            """
            INSERT INTO schema_migrations (version, applied_at, description)
            VALUES (?, ?, ?)
            """,
            (version, int(time.time()), description),
        )
        await self.db.commit()

        logger.info("Migration %03d applied successfully", version)

    @staticmethod
    def _parse_version(filename: str) -> int | None:
        """
        Parse version number from migration filename.

        Args:
            filename: Migration filename (e.g., "001_initial_schema.sql")

        Returns:
            Version number, or None if parsing fails.
        """
        parts = filename.split("_", 1)
        if not parts:
            return None
        try:
            return int(parts[0])
        except ValueError:
            return None

    @staticmethod
    def _parse_description(filename: str) -> str:
        """
        Parse description from migration filename.

        Args:
            filename: Migration filename (e.g., "001_initial_schema.sql")

        Returns:
            Human-readable description.
        """
        # Remove extension
        name = filename.rsplit(".", 1)[0]
        # Remove version prefix
        parts = name.split("_", 1)
        if len(parts) > 1:
            return parts[1].replace("_", " ")
        return name
