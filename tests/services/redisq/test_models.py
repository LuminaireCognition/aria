"""
Tests for RedisQ models.
"""

from __future__ import annotations

import time
from datetime import datetime

from aria_esi.services.redisq.models import (
    PollerStatus,
    ProcessedKill,
    QueuedKill,
    RedisQConfig,
)


class TestQueuedKill:
    """Tests for QueuedKill dataclass."""

    def test_from_redisq_package(self, sample_redisq_package):
        """Test creating QueuedKill from RedisQ package."""
        now = time.time()
        queued = QueuedKill.from_redisq_package(
            sample_redisq_package["package"],
            now,
        )

        assert queued.kill_id == 123456789
        assert queued.hash == "abc123def456"
        assert queued.zkb_data["totalValue"] == 150000000.0
        assert queued.queued_at == now

    def test_from_redisq_package_missing_data(self):
        """Test handling of missing data in package."""
        package = {"killmail": {}, "zkb": {}}
        queued = QueuedKill.from_redisq_package(package, time.time())

        assert queued.kill_id == 0
        assert queued.hash == ""


class TestProcessedKill:
    """Tests for ProcessedKill dataclass."""

    def test_to_db_row(self):
        """Test conversion to database row."""
        kill = ProcessedKill(
            kill_id=123456789,
            kill_time=datetime(2024, 1, 15, 12, 34, 56),
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

        row = kill.to_db_row()

        assert row[0] == 123456789  # kill_id
        assert row[2] == 30000142  # solar_system_id
        assert row[6] == 2  # attacker_count
        assert "[98000002]" in row[7]  # attacker_corps JSON
        assert "[17812, 24690]" in row[9]  # attacker_ship_types JSON
        assert row[12] == 0  # is_pod_kill

    def test_from_db_row_dict(self):
        """Test creation from database row dict."""
        row = {
            "kill_id": 123456789,
            "kill_time": 1705321496,
            "solar_system_id": 30000142,
            "victim_ship_type_id": 17740,
            "victim_corporation_id": 98000001,
            "victim_alliance_id": 99000001,
            "attacker_count": 2,
            "attacker_corps": "[98000002]",
            "attacker_alliances": "[99000002]",
            "attacker_ship_types": "[17812, 24690]",
            "final_blow_ship_type_id": 17812,
            "total_value": 150000000.0,
            "is_pod_kill": 0,
        }

        kill = ProcessedKill.from_db_row(row)

        assert kill.kill_id == 123456789
        assert kill.solar_system_id == 30000142
        assert kill.attacker_corps == [98000002]
        assert kill.attacker_ship_types == [17812, 24690]
        assert kill.is_pod_kill is False


class TestRedisQConfig:
    """Tests for RedisQConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RedisQConfig()

        assert config.enabled is False
        assert config.queue_id == ""
        assert config.poll_interval_seconds == 10
        assert config.filter_regions == []
        assert config.min_value_isk == 0
        assert config.retention_hours == 24

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RedisQConfig(
            enabled=True,
            queue_id="test-123",
            filter_regions=[10000002, 10000043],
            min_value_isk=10000000,
            retention_hours=48,
        )

        assert config.enabled is True
        assert config.queue_id == "test-123"
        assert config.filter_regions == [10000002, 10000043]
        assert config.min_value_isk == 10000000
        assert config.retention_hours == 48


class TestPollerStatus:
    """Tests for PollerStatus dataclass."""

    def test_to_dict(self):
        """Test conversion to JSON-serializable dict."""
        now = datetime.utcnow()
        status = PollerStatus(
            is_running=True,
            queue_id="test-123",
            last_poll_time=now,
            last_kill_time=now,
            kills_processed=100,
            kills_filtered=25,
            fetch_queue_size=5,
            errors_last_hour=2,
            filter_regions=[10000002],
        )

        result = status.to_dict()

        assert result["is_running"] is True
        assert result["queue_id"] == "test-123"
        assert result["kills_processed"] == 100
        assert result["kills_filtered"] == 25
        assert result["filter_regions"] == [10000002]
        assert result["last_poll_time"] is not None
        # Entity tracking fields have defaults
        assert "entity_tracking" in result
        assert result["entity_tracking"]["watched_entity_kills"] == 0

    def test_to_dict_none_times(self):
        """Test dict conversion with None datetime values."""
        status = PollerStatus(is_running=False)
        result = status.to_dict()

        assert result["last_poll_time"] is None
        assert result["last_kill_time"] is None


class TestQueuedKillExtended:
    """Extended tests for QueuedKill dataclass."""

    def test_from_redisq_package_new_format(self):
        """Test creating QueuedKill from new (2025+) RedisQ format."""
        package = {
            "killID": 987654321,
            "killmail": {
                "solar_system_id": 30000142,
                "killmail_time": "2024-01-15T12:34:56Z",
            },
            "zkb": {
                "hash": "newhash123",
                "totalValue": 250000000.0,
            },
        }
        queued = QueuedKill.from_redisq_package(package, 1705321496.0)

        assert queued.kill_id == 987654321
        assert queued.hash == "newhash123"
        assert queued.solar_system_id == 30000142
        assert queued.kill_time is not None
        assert queued.kill_time > 0

    def test_from_redisq_package_invalid_kill_time(self):
        """Test handling of invalid kill_time format."""
        package = {
            "killID": 123,
            "killmail": {
                "killmail_time": "invalid-time",
            },
            "zkb": {"hash": "test"},
        }
        queued = QueuedKill.from_redisq_package(package, 1705321496.0)

        assert queued.kill_id == 123
        assert queued.kill_time is None  # Failed to parse

    def test_to_killmail_record(self):
        """Test converting QueuedKill to KillmailRecord."""
        queued = QueuedKill(
            kill_id=123456789,
            hash="abc123",
            zkb_data={
                "totalValue": 150000000.0,
                "points": 10,
                "npc": False,
                "solo": True,
                "awox": False,
            },
            queued_at=1705321496.0,
            solar_system_id=30000142,
            kill_time=1705321400,  # Actual kill time
        )

        record = queued.to_killmail_record()

        assert record.kill_id == 123456789
        assert record.zkb_hash == "abc123"
        assert record.zkb_total_value == 150000000.0
        assert record.zkb_points == 10
        assert record.zkb_is_npc is False
        assert record.zkb_is_solo is True
        assert record.kill_time == 1705321400  # Uses actual kill time
        assert record.solar_system_id == 30000142

    def test_to_killmail_record_fallback_time(self):
        """Test to_killmail_record uses queued_at when kill_time is None."""
        queued = QueuedKill(
            kill_id=123,
            hash="test",
            zkb_data={},
            queued_at=1705321496.0,
            solar_system_id=None,
            kill_time=None,
        )

        record = queued.to_killmail_record()

        assert record.kill_time == 1705321496  # Falls back to queued_at


class TestProcessedKillFromTuple:
    """Tests for ProcessedKill.from_db_row with tuple input."""

    def test_from_db_row_tuple(self):
        """Test creation from database row tuple."""
        row = (
            123456789,  # kill_id
            1705321496,  # kill_time
            30000142,  # solar_system_id
            17740,  # victim_ship_type_id
            98000001,  # victim_corporation_id
            99000001,  # victim_alliance_id
            2,  # attacker_count
            "[98000002]",  # attacker_corps
            "[99000002]",  # attacker_alliances
            "[17812, 24690]",  # attacker_ship_types
            17812,  # final_blow_ship_type_id
            150000000.0,  # total_value
            0,  # is_pod_kill
        )

        kill = ProcessedKill.from_db_row(row)

        assert kill.kill_id == 123456789
        assert kill.solar_system_id == 30000142
        assert kill.attacker_corps == [98000002]
        assert kill.attacker_ship_types == [17812, 24690]
        assert kill.is_pod_kill is False

    def test_from_db_row_tuple_empty_lists(self):
        """Test handling of empty JSON lists in tuple."""
        row = (
            123,  # kill_id
            1705321496,  # kill_time
            30000142,  # solar_system_id
            None,  # victim_ship_type_id
            None,  # victim_corporation_id
            None,  # victim_alliance_id
            0,  # attacker_count
            "",  # attacker_corps (empty)
            "",  # attacker_alliances (empty)
            "",  # attacker_ship_types (empty)
            None,  # final_blow_ship_type_id
            None,  # total_value
            1,  # is_pod_kill
        )

        kill = ProcessedKill.from_db_row(row)

        assert kill.attacker_corps == []
        assert kill.attacker_alliances == []
        assert kill.attacker_ship_types == []
        assert kill.total_value == 0.0
        assert kill.is_pod_kill is True


class TestRedisQConfigFromSettings:
    """Tests for RedisQConfig.from_settings factory method."""

    def test_from_settings_with_values(self):
        """Test creating config from settings object."""
        from unittest.mock import MagicMock

        mock_settings = MagicMock()
        mock_settings.redisq_enabled = True
        mock_settings.redisq_regions = [10000002, 10000043]
        mock_settings.redisq_min_value = 10000000
        mock_settings.redisq_retention_hours = 48

        config = RedisQConfig.from_settings(mock_settings, queue_id="my-queue-123")

        assert config.enabled is True
        assert config.queue_id == "my-queue-123"
        assert config.filter_regions == [10000002, 10000043]
        assert config.min_value_isk == 10000000
        assert config.retention_hours == 48

    def test_from_settings_with_defaults(self):
        """Test creating config from settings with missing attributes."""
        mock_settings = object()  # Bare object with no attributes

        config = RedisQConfig.from_settings(mock_settings)

        assert config.enabled is False
        assert config.queue_id == ""
        assert config.filter_regions == []
        assert config.min_value_isk == 0
        assert config.retention_hours == 24
