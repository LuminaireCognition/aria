"""
Unit tests for ThreatCache class.

Tests the threat cache query methods, health checking,
and graceful degradation behavior.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from aria_esi.services.redisq.database import RealtimeKillsDatabase
from aria_esi.services.redisq.models import ProcessedKill
from aria_esi.services.redisq.threat_cache import (
    GatecampStatus,
    RealtimeActivitySummary,
    ThreatCache,
)


def make_kill(
    kill_id: int = 1,
    kill_time: datetime | None = None,
    system_id: int = 30000142,
    victim_corp: int = 1,
    attacker_count: int = 10,
    is_pod: bool = False,
    value: float = 10_000_000,
) -> ProcessedKill:
    """Create a test kill with sensible defaults."""
    if kill_time is None:
        kill_time = datetime.now(timezone.utc).replace(tzinfo=None)

    return ProcessedKill(
        kill_id=kill_id,
        kill_time=kill_time,
        solar_system_id=system_id,
        victim_ship_type_id=670 if is_pod else 587,
        victim_corporation_id=victim_corp,
        victim_alliance_id=None,
        attacker_count=attacker_count,
        attacker_corps=[100, 101],
        attacker_alliances=[],
        attacker_ship_types=[587],
        final_blow_ship_type_id=587,
        total_value=value,
        is_pod_kill=is_pod,
    )


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = RealtimeKillsDatabase(db_path, ensure_schema=False)

        # Manually create schema for testing
        conn = db._get_connection()
        conn.executescript("""
            CREATE TABLE realtime_kills (
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

            CREATE INDEX idx_kills_system_time ON realtime_kills(solar_system_id, kill_time);
            CREATE INDEX idx_kills_time ON realtime_kills(kill_time);

            CREATE TABLE redisq_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE gatecamp_detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                detected_at INTEGER NOT NULL,
                confidence TEXT,
                kill_count INTEGER,
                attacker_corps TEXT,
                force_asymmetry REAL,
                is_smartbomb INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            );

            CREATE INDEX idx_detections_system_time ON gatecamp_detections(system_id, detected_at);
        """)
        conn.commit()

        yield db
        db.close()


class TestThreatCacheHealth:
    """Tests for health checking."""

    def test_unhealthy_when_no_poll_time(self, temp_db, monkeypatch):
        """Cache should be unhealthy when no poll time recorded."""
        # Patch to use our temp db
        from aria_esi.services.redisq import threat_cache as tc

        monkeypatch.setattr(tc, "_threat_cache", None)

        cache = ThreatCache()
        cache._db = temp_db

        assert cache.is_healthy() is False

    def test_unhealthy_when_poll_time_stale(self, temp_db, monkeypatch):
        """Cache should be unhealthy when last poll is too old."""
        from aria_esi.services.redisq import threat_cache as tc

        monkeypatch.setattr(tc, "_threat_cache", None)

        # Set stale poll time
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        temp_db.set_last_poll_time(stale_time.replace(tzinfo=None))

        cache = ThreatCache()
        cache._db = temp_db

        assert cache.is_healthy() is False

    def test_healthy_when_poll_time_fresh(self, temp_db, monkeypatch):
        """Cache should be healthy when last poll is recent."""
        from aria_esi.services.redisq import threat_cache as tc

        monkeypatch.setattr(tc, "_threat_cache", None)

        # Set fresh poll time
        fresh_time = datetime.now(timezone.utc) - timedelta(minutes=2)
        temp_db.set_last_poll_time(fresh_time.replace(tzinfo=None))

        cache = ThreatCache()
        cache._db = temp_db

        assert cache.is_healthy() is True


class TestThreatCacheQueries:
    """Tests for query methods."""

    def test_get_recent_kills_returns_kills(self, temp_db, monkeypatch):
        """Should return recent kills from database."""
        from aria_esi.services.redisq import threat_cache as tc

        monkeypatch.setattr(tc, "_threat_cache", None)

        # Add some kills
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for i in range(5):
            kill = make_kill(
                kill_id=i,
                kill_time=now - timedelta(minutes=i * 5),
                system_id=30000142,
            )
            temp_db.save_kill(kill)

        cache = ThreatCache()
        cache._db = temp_db

        kills = cache.get_recent_kills(system_id=30000142, since_minutes=30)
        assert len(kills) == 5

    def test_get_recent_kills_respects_time_filter(self, temp_db, monkeypatch):
        """Should only return kills within time window."""
        import time

        from aria_esi.services.redisq import threat_cache as tc

        monkeypatch.setattr(tc, "_threat_cache", None)

        # Use Unix timestamps directly to avoid timezone issues
        # Kill times are stored as integers in the database
        now_ts = int(time.time())
        conn = temp_db._get_connection()

        # Insert kills with explicit timestamps
        # Kill 1: 5 minutes ago (within 30 min window)
        conn.execute(
            "INSERT INTO realtime_kills (kill_id, kill_time, solar_system_id) VALUES (?, ?, ?)",
            (1, now_ts - 300, 30000142),
        )
        # Kill 2: 10 minutes ago (within 30 min window)
        conn.execute(
            "INSERT INTO realtime_kills (kill_id, kill_time, solar_system_id) VALUES (?, ?, ?)",
            (2, now_ts - 600, 30000142),
        )
        # Kill 3: 2 hours ago (outside 30 min window)
        conn.execute(
            "INSERT INTO realtime_kills (kill_id, kill_time, solar_system_id) VALUES (?, ?, ?)",
            (3, now_ts - 7200, 30000142),
        )
        conn.commit()

        cache = ThreatCache()
        cache._db = temp_db

        # Only kills within 30 minutes
        kills = cache.get_recent_kills(since_minutes=30)
        assert len(kills) == 2
        # Verify correct kills returned
        kill_ids = {k.kill_id for k in kills}
        assert kill_ids == {1, 2}

    def test_get_kills_in_systems(self, temp_db, monkeypatch):
        """Should return kills from multiple systems."""
        from aria_esi.services.redisq import threat_cache as tc

        monkeypatch.setattr(tc, "_threat_cache", None)

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Kills in different systems
        temp_db.save_kill(make_kill(kill_id=1, system_id=30000142))  # Jita
        temp_db.save_kill(make_kill(kill_id=2, system_id=30002187))  # Amarr
        temp_db.save_kill(make_kill(kill_id=3, system_id=30002659))  # Dodixie

        cache = ThreatCache()
        cache._db = temp_db

        # Only Jita and Amarr
        kills = cache.get_kills_in_systems([30000142, 30002187])
        assert len(kills) == 2


class TestGatecampStatusRetrieval:
    """Tests for gatecamp status retrieval."""

    def test_gatecamp_detected_when_criteria_met(self, temp_db, monkeypatch):
        """Should detect gatecamp when kill pattern matches."""
        from aria_esi.services.redisq import threat_cache as tc

        monkeypatch.setattr(tc, "_threat_cache", None)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        system_id = 30000142

        # Add kills that match camp pattern
        for i in range(1, 4):
            temp_db.save_kill(
                make_kill(
                    kill_id=i,
                    kill_time=now - timedelta(minutes=i),
                    system_id=system_id,
                    victim_corp=i,  # Different victims
                    attacker_count=10,
                )
            )

        cache = ThreatCache()
        cache._db = temp_db

        status = cache.get_gatecamp_status(system_id, system_name="Jita")

        assert status is not None
        assert status.system_id == system_id
        assert status.system_name == "Jita"
        assert status.kill_count == 3

    def test_no_gatecamp_when_insufficient_kills(self, temp_db, monkeypatch):
        """Should return None when insufficient kills."""
        from aria_esi.services.redisq import threat_cache as tc

        monkeypatch.setattr(tc, "_threat_cache", None)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        system_id = 30000142

        # Only 2 kills (need 3 minimum)
        for i in range(1, 3):
            temp_db.save_kill(
                make_kill(
                    kill_id=i,
                    kill_time=now - timedelta(minutes=i),
                    system_id=system_id,
                )
            )

        cache = ThreatCache()
        cache._db = temp_db

        status = cache.get_gatecamp_status(system_id)
        assert status is None


class TestActivitySummary:
    """Tests for activity summary generation."""

    def test_activity_summary_counts_kills(self, temp_db, monkeypatch):
        """Should count kills correctly for time windows."""
        from aria_esi.services.redisq import threat_cache as tc

        monkeypatch.setattr(tc, "_threat_cache", None)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        system_id = 30000142

        # 2 kills in last 10 minutes
        temp_db.save_kill(make_kill(kill_id=1, kill_time=now - timedelta(minutes=5)))
        temp_db.save_kill(make_kill(kill_id=2, kill_time=now - timedelta(minutes=8)))

        # 2 more kills in last hour
        temp_db.save_kill(make_kill(kill_id=3, kill_time=now - timedelta(minutes=30)))
        temp_db.save_kill(make_kill(kill_id=4, kill_time=now - timedelta(minutes=45)))

        cache = ThreatCache()
        cache._db = temp_db

        summary = cache.get_activity_summary(system_id)

        assert summary.kills_10m == 2
        assert summary.kills_1h == 4

    def test_activity_summary_tracks_pod_kills(self, temp_db, monkeypatch):
        """Should count pod kills separately."""
        from aria_esi.services.redisq import threat_cache as tc

        monkeypatch.setattr(tc, "_threat_cache", None)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        system_id = 30000142

        # Ship kills and pod kills
        temp_db.save_kill(make_kill(kill_id=1, is_pod=False))
        temp_db.save_kill(make_kill(kill_id=2, is_pod=True))
        temp_db.save_kill(make_kill(kill_id=3, is_pod=False))
        temp_db.save_kill(make_kill(kill_id=4, is_pod=True))

        cache = ThreatCache()
        cache._db = temp_db

        summary = cache.get_activity_summary(system_id)

        assert summary.kills_1h == 4
        assert summary.pod_kills_1h == 2


class TestDetectionDeduplication:
    """Tests for detection deduplication."""

    def test_duplicate_detections_prevented(self, temp_db, monkeypatch):
        """Should not save duplicate detections within 5 minute window."""

        from aria_esi.services.redisq import threat_cache as tc

        monkeypatch.setattr(tc, "_threat_cache", None)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        system_id = 30000142

        # Add kills that trigger gatecamp detection
        for i in range(1, 4):
            temp_db.save_kill(
                make_kill(
                    kill_id=i,
                    kill_time=now - timedelta(minutes=i),
                    system_id=system_id,
                    victim_corp=i,
                    attacker_count=10,
                )
            )

        cache = ThreatCache()
        cache._db = temp_db

        # First call saves detection
        status1 = cache.get_gatecamp_status(system_id, "Jita")
        assert status1 is not None

        # Second call within 5 minutes should not save duplicate
        status2 = cache.get_activity_summary(system_id, "Jita")
        assert status2.gatecamp is not None

        # Check only one detection was saved
        conn = temp_db._get_connection()
        count = conn.execute(
            "SELECT COUNT(*) FROM gatecamp_detections WHERE system_id = ?",
            (system_id,),
        ).fetchone()[0]

        assert count == 1

    def test_detections_allowed_after_window(self, temp_db, monkeypatch):
        """Should allow new detections after 5 minute window expires."""
        import time

        from aria_esi.services.redisq import threat_cache as tc

        monkeypatch.setattr(tc, "_threat_cache", None)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        system_id = 30000142
        conn = temp_db._get_connection()

        # Insert an old detection (6 minutes ago)
        old_detection_time = int(time.time()) - 360
        conn.execute(
            "INSERT INTO gatecamp_detections (system_id, detected_at, confidence) VALUES (?, ?, ?)",
            (system_id, old_detection_time, "high"),
        )
        conn.commit()

        # Add kills that trigger gatecamp detection
        for i in range(1, 4):
            temp_db.save_kill(
                make_kill(
                    kill_id=i,
                    kill_time=now - timedelta(minutes=i),
                    system_id=system_id,
                    victim_corp=i,
                    attacker_count=10,
                )
            )

        cache = ThreatCache()
        cache._db = temp_db

        # Should save new detection since old one is outside 5 min window
        status = cache.get_gatecamp_status(system_id, "Jita")
        assert status is not None

        # Check we now have 2 detections
        count = conn.execute(
            "SELECT COUNT(*) FROM gatecamp_detections WHERE system_id = ?",
            (system_id,),
        ).fetchone()[0]

        assert count == 2


class TestCleanup:
    """Tests for data cleanup."""

    def test_cleanup_old_data(self, temp_db, monkeypatch):
        """Should clean up old kills and detections."""
        from aria_esi.services.redisq import threat_cache as tc

        monkeypatch.setattr(tc, "_threat_cache", None)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        conn = temp_db._get_connection()

        # Add old and new kills
        old_time = now - timedelta(hours=48)
        temp_db.save_kill(make_kill(kill_id=1, kill_time=old_time))
        temp_db.save_kill(make_kill(kill_id=2, kill_time=now))

        # Add old and new detections
        import time

        old_detected = int(time.time()) - (8 * 86400)  # 8 days ago
        new_detected = int(time.time())

        conn.execute(
            "INSERT INTO gatecamp_detections (system_id, detected_at, confidence) VALUES (?, ?, ?)",
            (30000142, old_detected, "high"),
        )
        conn.execute(
            "INSERT INTO gatecamp_detections (system_id, detected_at, confidence) VALUES (?, ?, ?)",
            (30000142, new_detected, "high"),
        )
        conn.commit()

        cache = ThreatCache()
        cache._db = temp_db

        kills_deleted, detections_deleted = cache.cleanup_old_data(
            kill_retention_hours=24,
            detection_retention_days=7,
        )

        assert kills_deleted == 1
        assert detections_deleted == 1

        # Verify remaining data
        remaining_kills = cache.get_recent_kills(since_minutes=120)
        assert len(remaining_kills) == 1
        assert remaining_kills[0].kill_id == 2


class TestDataclassSerialization:
    """Tests for dataclass serialization."""

    def test_gatecamp_status_to_dict(self):
        """GatecampStatus should serialize correctly."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        status = GatecampStatus(
            system_id=30000142,
            system_name="Jita",
            kill_count=5,
            window_minutes=10,
            attacker_corps=[100, 101],
            attacker_alliances=[200],
            attacker_ships=[587, 588],
            confidence="high",
            last_kill_time=now,
            is_smartbomb_camp=False,
            force_asymmetry=8.5,
        )

        result = status.to_dict()

        assert result["system_id"] == 30000142
        assert result["system_name"] == "Jita"
        assert result["kill_count"] == 5
        assert result["confidence"] == "high"
        assert result["attacker_corps"] == [100, 101]
        assert result["last_kill_time"] is not None

    def test_realtime_activity_summary_to_dict(self):
        """RealtimeActivitySummary should serialize correctly."""
        summary = RealtimeActivitySummary(
            system_id=30000142,
            kills_10m=3,
            kills_1h=10,
            pod_kills_10m=1,
            pod_kills_1h=4,
            recent_kills=[{"kill_id": 1}],
            gatecamp=None,
        )

        result = summary.to_dict()

        assert result["kills_10m"] == 3
        assert result["kills_1h"] == 10
        assert result["pod_kills_1h"] == 4
        assert "gatecamp" not in result  # None not included

    def test_realtime_activity_summary_includes_gatecamp(self):
        """Summary should include gatecamp when present."""
        gatecamp = GatecampStatus(
            system_id=30000142,
            confidence="high",
            kill_count=5,
        )

        summary = RealtimeActivitySummary(
            system_id=30000142,
            kills_10m=5,
            kills_1h=5,
            gatecamp=gatecamp,
        )

        result = summary.to_dict()
        assert "gatecamp" in result
        assert result["gatecamp"]["confidence"] == "high"
