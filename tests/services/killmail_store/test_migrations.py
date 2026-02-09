"""Tests for MigrationRunner."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

pytestmark = pytest.mark.asyncio

from aria_esi.services.killmail_store.migrations import MigrationRunner


class TestMigrationRunner:
    """Tests for MigrationRunner."""

    async def test_run_migrations_on_fresh_db(self, tmp_path: Path) -> None:
        """Test running migrations on a fresh database."""
        db_path = tmp_path / "test.db"

        async with aiosqlite.connect(db_path) as db:
            runner = MigrationRunner(db)
            applied = await runner.run_migrations()

            # At least one migration should be applied
            assert applied >= 1

            # Verify schema_migrations table exists
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            )
            row = await cursor.fetchone()
            assert row is not None

            # Verify migrations are recorded
            cursor = await db.execute("SELECT version FROM schema_migrations")
            rows = await cursor.fetchall()
            assert len(rows) >= 1

    async def test_run_migrations_is_idempotent(self, tmp_path: Path) -> None:
        """Test that running migrations twice doesn't reapply."""
        db_path = tmp_path / "test.db"

        async with aiosqlite.connect(db_path) as db:
            runner = MigrationRunner(db)

            # First run
            applied1 = await runner.run_migrations()
            assert applied1 >= 1

            # Second run - should apply nothing
            applied2 = await runner.run_migrations()
            assert applied2 == 0

    async def test_migrations_create_tables(self, tmp_path: Path) -> None:
        """Test that migrations create all expected tables."""
        db_path = tmp_path / "test.db"

        async with aiosqlite.connect(db_path) as db:
            runner = MigrationRunner(db)
            await runner.run_migrations()

            # Check for expected tables
            expected_tables = [
                "killmails",
                "esi_details",
                "worker_state",
                "processed_kills",
                "esi_fetch_attempts",
                "esi_fetch_claims",
                "schema_migrations",
            ]

            for table in expected_tables:
                cursor = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                )
                row = await cursor.fetchone()
                assert row is not None, f"Table {table} not found"

    async def test_migrations_create_indices(self, tmp_path: Path) -> None:
        """Test that migrations create expected indices."""
        db_path = tmp_path / "test.db"

        async with aiosqlite.connect(db_path) as db:
            runner = MigrationRunner(db)
            await runner.run_migrations()

            # Check for some key indices
            expected_indices = [
                "idx_killmails_system_time",
                "idx_killmails_time",
                "idx_killmails_value",
            ]

            for index in expected_indices:
                cursor = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (index,),
                )
                row = await cursor.fetchone()
                assert row is not None, f"Index {index} not found"

    async def test_parse_version(self) -> None:
        """Test version parsing from filenames."""
        assert MigrationRunner._parse_version("001_initial.sql") == 1
        assert MigrationRunner._parse_version("002_add_column.sql") == 2
        assert MigrationRunner._parse_version("100_big_change.sql") == 100
        assert MigrationRunner._parse_version("invalid.sql") is None

    async def test_parse_description(self) -> None:
        """Test description parsing from filenames."""
        assert MigrationRunner._parse_description("001_initial_schema.sql") == "initial schema"
        assert MigrationRunner._parse_description("002_add_processed_kills.sql") == "add processed kills"
