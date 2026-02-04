"""
Tests for RedisQ processor module.
"""

from __future__ import annotations

from aria_esi.services.redisq.processor import (
    KillFilter,
    is_pod_kill,
    parse_esi_killmail,
)


class TestIsPodKill:
    """Tests for pod detection."""

    def test_capsule_is_pod(self):
        """Test standard capsule detection."""
        assert is_pod_kill(670) is True

    def test_genolution_capsule_is_pod(self):
        """Test Genolution capsule detection."""
        assert is_pod_kill(33328) is True

    def test_regular_ship_not_pod(self):
        """Test regular ship is not a pod."""
        assert is_pod_kill(17740) is False  # Hurricane
        assert is_pod_kill(24690) is False  # Talos

    def test_none_not_pod(self):
        """Test None is not a pod."""
        assert is_pod_kill(None) is False


class TestParseEsiKillmail:
    """Tests for ESI killmail parsing."""

    def test_parse_full_killmail(self, sample_esi_killmail, sample_zkb_data):
        """Test parsing a complete killmail."""
        kill = parse_esi_killmail(sample_esi_killmail, sample_zkb_data)

        assert kill.kill_id == 123456789
        assert kill.solar_system_id == 30000142
        assert kill.victim_ship_type_id == 17740
        assert kill.victim_corporation_id == 98000001
        assert kill.victim_alliance_id == 99000001
        assert kill.attacker_count == 2
        assert 98000002 in kill.attacker_corps
        assert 99000002 in kill.attacker_alliances
        assert 17812 in kill.attacker_ship_types
        assert 24690 in kill.attacker_ship_types
        assert kill.final_blow_ship_type_id == 17812
        assert kill.total_value == 150000000.0
        assert kill.is_pod_kill is False

    def test_parse_pod_kill(self, sample_pod_killmail, sample_zkb_data):
        """Test parsing a pod kill."""
        kill = parse_esi_killmail(sample_pod_killmail, sample_zkb_data)

        assert kill.victim_ship_type_id == 670
        assert kill.is_pod_kill is True

    def test_parse_no_alliance(self, sample_esi_killmail, sample_zkb_data):
        """Test parsing killmail where victim has no alliance."""
        sample_esi_killmail["victim"]["alliance_id"] = None
        kill = parse_esi_killmail(sample_esi_killmail, sample_zkb_data)

        assert kill.victim_alliance_id is None

    def test_deduplicate_attacker_corps(self, sample_esi_killmail, sample_zkb_data):
        """Test that attacker corps are deduplicated."""
        # Both attackers have same corp
        kill = parse_esi_killmail(sample_esi_killmail, sample_zkb_data)

        assert kill.attacker_corps == [98000002]  # Only one entry


class TestKillFilter:
    """Tests for kill filtering."""

    def test_no_filters_passes_all(self, sample_esi_killmail, sample_zkb_data):
        """Test that empty filter passes all kills."""
        kill_filter = KillFilter()
        kill = parse_esi_killmail(sample_esi_killmail, sample_zkb_data)

        assert kill_filter.should_process(kill) is True

    def test_min_value_filter(self, sample_esi_killmail, sample_zkb_data):
        """Test minimum value filter."""
        kill = parse_esi_killmail(sample_esi_killmail, sample_zkb_data)

        # Should pass - value is 150M
        high_filter = KillFilter(min_value=100_000_000)
        assert high_filter.should_process(kill) is True

        # Should fail - value is below threshold
        too_high = KillFilter(min_value=200_000_000)
        assert too_high.should_process(kill) is False

    def test_get_filter_summary(self):
        """Test filter summary generation."""
        kill_filter = KillFilter(
            regions={10000002, 10000043},
            min_value=10_000_000,
        )

        summary = kill_filter.get_filter_summary()

        assert 10000002 in summary["regions"]
        assert 10000043 in summary["regions"]
        assert summary["min_value_isk"] == 10_000_000

    def test_get_filter_summary_no_filters(self):
        """Test filter summary with no active filters."""
        kill_filter = KillFilter()
        summary = kill_filter.get_filter_summary()

        assert summary["regions"] == "all"
        assert summary["min_value_isk"] == "none"

    def test_get_filter_summary_with_entity_filter(self):
        """Test filter summary with entity filter active."""
        from unittest.mock import MagicMock

        mock_entity_filter = MagicMock()
        mock_entity_filter.is_active = True
        mock_entity_filter.watched_corp_count = 5
        mock_entity_filter.watched_alliance_count = 2

        kill_filter = KillFilter(entity_filter=mock_entity_filter)
        summary = kill_filter.get_filter_summary()

        assert summary["entity_tracking"]["active"] is True
        assert summary["entity_tracking"]["watched_corps"] == 5
        assert summary["entity_tracking"]["watched_alliances"] == 2

    def test_region_filter(self, sample_esi_killmail, sample_zkb_data):
        """Test region-based filtering."""
        kill = parse_esi_killmail(sample_esi_killmail, sample_zkb_data)

        # System 30000142 (Jita) - we need to mock region lookup
        kill_filter = KillFilter(regions={10000002})  # The Forge
        kill_filter._system_regions[30000142] = 10000002

        # Should pass - system is in allowed region
        assert kill_filter.should_process(kill) is True

        # Different region
        wrong_region_filter = KillFilter(regions={10000043})  # Domain
        wrong_region_filter._system_regions[30000142] = 10000002

        # Should fail - system not in allowed region
        assert wrong_region_filter.should_process(kill) is False

    def test_process_kill_passes_filters(self, sample_esi_killmail, sample_zkb_data):
        """Test process_kill returns True when filters pass."""
        kill = parse_esi_killmail(sample_esi_killmail, sample_zkb_data)
        kill_filter = KillFilter()

        should_store, entity_match = kill_filter.process_kill(kill)

        assert should_store is True
        assert entity_match is None

    def test_process_kill_fails_filters(self, sample_esi_killmail, sample_zkb_data):
        """Test process_kill returns False when filters fail."""
        kill = parse_esi_killmail(sample_esi_killmail, sample_zkb_data)
        # Value is 150M, require 500M
        kill_filter = KillFilter(min_value=500_000_000)

        should_store, entity_match = kill_filter.process_kill(kill)

        assert should_store is False
        assert entity_match is None

    def test_process_kill_with_entity_filter(self, sample_esi_killmail, sample_zkb_data):
        """Test process_kill invokes entity filter."""
        from unittest.mock import MagicMock

        kill = parse_esi_killmail(sample_esi_killmail, sample_zkb_data)

        mock_entity_filter = MagicMock()
        mock_match = MagicMock()
        mock_entity_filter.check_kill.return_value = mock_match

        kill_filter = KillFilter(entity_filter=mock_entity_filter)
        should_store, entity_match = kill_filter.process_kill(kill)

        assert should_store is True
        assert entity_match is mock_match
        mock_entity_filter.check_kill.assert_called_once_with(kill)

    def test_get_region_for_system_cached(self, sample_esi_killmail, sample_zkb_data):
        """Test _get_region_for_system uses cache."""
        kill_filter = KillFilter()
        kill_filter._system_regions[30000142] = 10000002

        result = kill_filter._get_region_for_system(30000142)

        assert result == 10000002

    def test_get_region_for_system_unknown(self):
        """Test _get_region_for_system returns None for unknown system."""
        kill_filter = KillFilter()

        result = kill_filter._get_region_for_system(99999999)

        assert result is None


class TestParseEsiKillmailEdgeCases:
    """Tests for edge cases in killmail parsing."""

    def test_parse_invalid_kill_time(self, sample_zkb_data):
        """Test parsing with invalid kill time falls back to now."""
        esi_data = {
            "killmail_id": 123,
            "killmail_time": "invalid-time",
            "solar_system_id": 30000142,
            "victim": {},
            "attackers": [],
        }

        kill = parse_esi_killmail(esi_data, sample_zkb_data)

        assert kill.kill_id == 123
        # Should have a valid time (fallback to utcnow)
        assert kill.kill_time is not None

    def test_parse_empty_kill_time(self, sample_zkb_data):
        """Test parsing with empty kill time."""
        esi_data = {
            "killmail_id": 123,
            "killmail_time": "",
            "solar_system_id": 30000142,
            "victim": {},
            "attackers": [],
        }

        kill = parse_esi_killmail(esi_data, sample_zkb_data)

        assert kill.kill_time is not None

    def test_parse_missing_zkb_value(self, sample_esi_killmail):
        """Test parsing with missing zKB total value."""
        zkb_data = {}  # No totalValue

        kill = parse_esi_killmail(sample_esi_killmail, zkb_data)

        assert kill.total_value == 0.0


class TestCreateFilterFromConfig:
    """Tests for create_filter_from_config function."""

    def test_creates_filter_with_regions(self):
        """Test creating filter with regions from config."""
        from unittest.mock import MagicMock

        from aria_esi.services.redisq.processor import create_filter_from_config

        mock_config = MagicMock()
        mock_config.filter_regions = [10000002, 10000043]
        mock_config.min_value_isk = 10_000_000

        result = create_filter_from_config(mock_config)

        assert 10000002 in result.regions
        assert 10000043 in result.regions
        assert result.min_value == 10_000_000

    def test_creates_filter_no_regions(self):
        """Test creating filter with no regions."""
        from unittest.mock import MagicMock

        from aria_esi.services.redisq.processor import create_filter_from_config

        mock_config = MagicMock()
        mock_config.filter_regions = None
        mock_config.min_value_isk = 0

        result = create_filter_from_config(mock_config)

        assert result.regions == set()
        assert result.min_value == 0
