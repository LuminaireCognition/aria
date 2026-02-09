"""
Tests for RedisQ database operations.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from aria_esi.services.redisq.database import (
    RealtimeKillsDatabase,
)
from aria_esi.services.redisq.models import ProcessedKill


@pytest.fixture
def db(tmp_path: Path) -> RealtimeKillsDatabase:
    """Create a test database."""
    db_path = tmp_path / "test.db"

    # Initialize schema by creating the market database tables first
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS realtime_kills (
            kill_id INTEGER PRIMARY KEY,
            kill_time INTEGER NOT NULL,
            solar_system_id INTEGER NOT NULL,
            victim_ship_type_id INTEGER,
            victim_corporation_id INTEGER,
            victim_alliance_id INTEGER,
            attacker_count INTEGER,
            attacker_corps TEXT,
            attacker_alliances TEXT,
            attacker_ship_types TEXT,
            final_blow_ship_type_id INTEGER,
            total_value REAL,
            is_pod_kill INTEGER DEFAULT 0,
            watched_entity_match INTEGER DEFAULT 0,
            watched_entity_ids TEXT,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        );

        CREATE INDEX IF NOT EXISTS idx_kills_system_time ON realtime_kills(solar_system_id, kill_time);
        CREATE INDEX IF NOT EXISTS idx_kills_time ON realtime_kills(kill_time);

        CREATE TABLE IF NOT EXISTS redisq_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        );
    """)
    conn.commit()
    conn.close()

    # Use ensure_schema=False to skip MarketDatabase init (tables created above)
    db = RealtimeKillsDatabase(db_path, ensure_schema=False)
    yield db
    db.close()


@pytest.fixture
def sample_kill() -> ProcessedKill:
    """Sample processed kill for testing."""
    return ProcessedKill(
        kill_id=123456789,
        kill_time=datetime.utcnow(),
        solar_system_id=30000142,
        victim_ship_type_id=17740,
        victim_corporation_id=98000001,
        victim_alliance_id=99000001,
        attacker_count=2,
        attacker_corps=[98000002],
        attacker_alliances=[99000002],
        attacker_ship_types=[17812, 24690],
        final_blow_ship_type_id=17812,
        total_value=150000000.0,
        is_pod_kill=False,
    )


class TestKillOperations:
    """Tests for kill CRUD operations."""

    def test_save_and_get_kill(self, db: RealtimeKillsDatabase, sample_kill):
        """Test saving and retrieving a kill."""
        db.save_kill(sample_kill)

        retrieved = db.get_kill(sample_kill.kill_id)

        assert retrieved is not None
        assert retrieved.kill_id == sample_kill.kill_id
        assert retrieved.solar_system_id == sample_kill.solar_system_id
        assert retrieved.victim_ship_type_id == sample_kill.victim_ship_type_id
        assert retrieved.attacker_corps == sample_kill.attacker_corps
        assert retrieved.is_pod_kill == sample_kill.is_pod_kill

    def test_get_nonexistent_kill(self, db: RealtimeKillsDatabase):
        """Test getting a kill that doesn't exist."""
        retrieved = db.get_kill(999999999)
        assert retrieved is None

    def test_kill_exists(self, db: RealtimeKillsDatabase, sample_kill):
        """Test checking if a kill exists."""
        assert db.kill_exists(sample_kill.kill_id) is False

        db.save_kill(sample_kill)

        assert db.kill_exists(sample_kill.kill_id) is True

    def test_save_kills_batch(self, db: RealtimeKillsDatabase):
        """Test batch saving multiple kills."""
        kills = [
            ProcessedKill(
                kill_id=i,
                kill_time=datetime.utcnow(),
                solar_system_id=30000142,
                victim_ship_type_id=17740,
                victim_corporation_id=98000001,
                victim_alliance_id=None,
                attacker_count=1,
                attacker_corps=[],
                attacker_alliances=[],
                attacker_ship_types=[],
                final_blow_ship_type_id=None,
                total_value=10000000.0,
                is_pod_kill=False,
            )
            for i in range(1, 6)
        ]

        count = db.save_kills_batch(kills)

        assert count == 5
        assert db.get_kill_count() == 5

    def test_get_recent_kills(self, db: RealtimeKillsDatabase):
        """Test getting recent kills."""
        # Use explicit timestamps for reliable testing
        now_ts = time.time()
        now = datetime.fromtimestamp(now_ts)

        # Create kills at different times
        for i, delta in enumerate([5, 30, 90]):
            kill = ProcessedKill(
                kill_id=i + 1,
                kill_time=datetime.fromtimestamp(now_ts - delta * 60),
                solar_system_id=30000142,
                victim_ship_type_id=17740,
                victim_corporation_id=98000001,
                victim_alliance_id=None,
                attacker_count=1,
                attacker_corps=[],
                attacker_alliances=[],
                attacker_ship_types=[],
                final_blow_ship_type_id=None,
                total_value=10000000.0,
                is_pod_kill=False,
            )
            db.save_kill(kill)

        # Get kills from last hour
        recent = db.get_recent_kills(since_minutes=60, limit=10)
        assert len(recent) == 2  # 5 and 30 minutes ago

        # Get all kills
        all_kills = db.get_recent_kills(since_minutes=120, limit=10)
        assert len(all_kills) == 3

    def test_get_recent_kills_by_system(self, db: RealtimeKillsDatabase):
        """Test filtering recent kills by system."""
        now = datetime.utcnow()

        # Create kills in different systems
        for i, system in enumerate([30000142, 30000142, 30002187]):
            kill = ProcessedKill(
                kill_id=i + 1,
                kill_time=now - timedelta(minutes=5),
                solar_system_id=system,
                victim_ship_type_id=17740,
                victim_corporation_id=98000001,
                victim_alliance_id=None,
                attacker_count=1,
                attacker_corps=[],
                attacker_alliances=[],
                attacker_ship_types=[],
                final_blow_ship_type_id=None,
                total_value=10000000.0,
                is_pod_kill=False,
            )
            db.save_kill(kill)

        # Filter to Jita
        jita_kills = db.get_recent_kills(
            system_id=30000142,
            since_minutes=60,
            limit=10,
        )
        assert len(jita_kills) == 2

    def test_cleanup_old_kills(self, db: RealtimeKillsDatabase):
        """Test cleanup of old kills."""
        # Use explicit timestamps for reliable testing
        now_ts = time.time()

        # Create kills at different ages
        for i, hours in enumerate([1, 12, 30]):
            kill = ProcessedKill(
                kill_id=i + 1,
                kill_time=datetime.fromtimestamp(now_ts - hours * 3600),
                solar_system_id=30000142,
                victim_ship_type_id=17740,
                victim_corporation_id=98000001,
                victim_alliance_id=None,
                attacker_count=1,
                attacker_corps=[],
                attacker_alliances=[],
                attacker_ship_types=[],
                final_blow_ship_type_id=None,
                total_value=10000000.0,
                is_pod_kill=False,
            )
            db.save_kill(kill)

        # Clean up kills older than 24 hours
        deleted = db.cleanup_old_kills(retention_hours=24)

        assert deleted == 1  # Only the 30-hour-old kill
        assert db.get_kill_count() == 2


class TestStateOperations:
    """Tests for state persistence operations."""

    def test_set_and_get_state(self, db: RealtimeKillsDatabase):
        """Test setting and getting state values."""
        db.set_state("test_key", "test_value")

        retrieved = db.get_state("test_key")

        assert retrieved == "test_value"

    def test_get_nonexistent_state(self, db: RealtimeKillsDatabase):
        """Test getting state that doesn't exist."""
        retrieved = db.get_state("nonexistent")
        assert retrieved is None

    def test_queue_id_persistence(self, db: RealtimeKillsDatabase):
        """Test queue ID persistence."""
        assert db.get_queue_id() is None

        db.set_queue_id("aria-test123")

        assert db.get_queue_id() == "aria-test123"

    def test_last_poll_time_persistence(self, db: RealtimeKillsDatabase):
        """Test last poll time persistence."""
        assert db.get_last_poll_time() is None

        now = datetime.utcnow()
        db.set_last_poll_time(now)

        retrieved = db.get_last_poll_time()
        assert retrieved is not None
        # Allow 1 second tolerance for timestamp conversion
        assert abs((retrieved - now).total_seconds()) < 1


class TestStatistics:
    """Tests for database statistics."""

    def test_get_stats_empty(self, db: RealtimeKillsDatabase):
        """Test stats on empty database."""
        stats = db.get_stats()

        assert stats["total_kills"] == 0
        assert stats["kills_last_hour"] == 0
        assert stats["latest_kill_time"] is None
        assert stats["last_poll_time"] is None

    def test_get_stats_with_data(self, db: RealtimeKillsDatabase, sample_kill):
        """Test stats with data."""
        db.save_kill(sample_kill)
        db.set_queue_id("test-queue")

        stats = db.get_stats()

        assert stats["total_kills"] == 1
        assert stats["kills_last_hour"] == 1
        assert stats["latest_kill_time"] is not None
        assert stats["queue_id"] == "test-queue"
