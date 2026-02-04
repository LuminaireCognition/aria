"""
Tests for NPC faction mapping and trigger evaluation.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from aria_esi.services.redisq.models import ProcessedKill
from aria_esi.services.redisq.notifications.npc_factions import (
    NPCFactionMapper,
    NPCFactionTriggerResult,
    get_npc_faction_mapper,
    reset_npc_faction_mapper,
)


class TestNPCFactionTriggerResult:
    """Tests for NPCFactionTriggerResult dataclass."""

    def test_to_dict(self):
        """Test serialization to dict."""
        result = NPCFactionTriggerResult(
            matched=True,
            faction="serpentis",
            corporation_id=1000135,
            corporation_name="Serpentis Corporation",
            role="attacker",
        )

        d = result.to_dict()

        assert d["matched"] is True
        assert d["faction"] == "serpentis"
        assert d["corporation_id"] == 1000135
        assert d["corporation_name"] == "Serpentis Corporation"
        assert d["role"] == "attacker"


class TestNPCFactionMapper:
    """Tests for NPCFactionMapper class."""

    @pytest.fixture
    def sample_reference_data(self):
        """Create sample NPC corporation reference data."""
        return {
            "serpentis": {
                "faction_id": 500020,
                "name": "Serpentis",
                "corporations": [
                    {"id": 1000135, "name": "Serpentis Corporation"},
                    {"id": 1000157, "name": "Serpentis Inquest"},
                ],
            },
            "angel_cartel": {
                "faction_id": 500011,
                "name": "Angel Cartel",
                "corporations": [
                    {"id": 1000124, "name": "Archangels"},
                    {"id": 1000136, "name": "Guardian Angels"},
                ],
            },
        }

    @pytest.fixture
    def mapper_with_data(self, sample_reference_data, tmp_path):
        """Create mapper with sample data."""
        ref_file = tmp_path / "npc_corporations.json"
        ref_file.write_text(json.dumps(sample_reference_data))
        return NPCFactionMapper(ref_file)

    def test_load_mapping(self, mapper_with_data):
        """Test that mapping loads correctly."""
        assert mapper_with_data.is_loaded
        assert mapper_with_data.faction_count == 2
        assert mapper_with_data.corporation_count == 4

    def test_get_faction_for_corp(self, mapper_with_data):
        """Test corp → faction lookup."""
        assert mapper_with_data.get_faction_for_corp(1000135) == "serpentis"
        assert mapper_with_data.get_faction_for_corp(1000157) == "serpentis"
        assert mapper_with_data.get_faction_for_corp(1000124) == "angel_cartel"
        assert mapper_with_data.get_faction_for_corp(1000136) == "angel_cartel"

    def test_get_faction_for_corp_unknown(self, mapper_with_data):
        """Test unknown corp returns None."""
        assert mapper_with_data.get_faction_for_corp(99999999) is None

    def test_get_corp_name(self, mapper_with_data):
        """Test corp ID → name lookup."""
        assert mapper_with_data.get_corp_name(1000135) == "Serpentis Corporation"
        assert mapper_with_data.get_corp_name(1000136) == "Guardian Angels"

    def test_get_corp_name_unknown(self, mapper_with_data):
        """Test unknown corp name returns None."""
        assert mapper_with_data.get_corp_name(99999999) is None

    def test_get_corps_for_faction(self, mapper_with_data):
        """Test faction → corps lookup."""
        serpentis_corps = mapper_with_data.get_corps_for_faction("serpentis")
        assert serpentis_corps == {1000135, 1000157}

        angel_corps = mapper_with_data.get_corps_for_faction("angel_cartel")
        assert angel_corps == {1000124, 1000136}

    def test_get_corps_for_faction_case_insensitive(self, mapper_with_data):
        """Test faction lookup is case-insensitive."""
        corps1 = mapper_with_data.get_corps_for_faction("SERPENTIS")
        corps2 = mapper_with_data.get_corps_for_faction("Serpentis")
        corps3 = mapper_with_data.get_corps_for_faction("serpentis")

        assert corps1 == corps2 == corps3

    def test_get_corps_for_faction_unknown(self, mapper_with_data):
        """Test unknown faction returns empty set."""
        assert mapper_with_data.get_corps_for_faction("unknown_faction") == set()

    def test_get_faction_display_name(self, mapper_with_data):
        """Test faction display name lookup."""
        assert mapper_with_data.get_faction_display_name("serpentis") == "Serpentis"
        assert mapper_with_data.get_faction_display_name("angel_cartel") == "Angel Cartel"

    def test_get_faction_display_name_unknown(self, mapper_with_data):
        """Test unknown faction returns title-cased key."""
        assert mapper_with_data.get_faction_display_name("unknown") == "Unknown"

    def test_get_all_faction_keys(self, mapper_with_data):
        """Test getting all faction keys."""
        keys = mapper_with_data.get_all_faction_keys()
        assert set(keys) == {"serpentis", "angel_cartel"}

    def test_is_valid_faction(self, mapper_with_data):
        """Test faction validation."""
        assert mapper_with_data.is_valid_faction("serpentis") is True
        assert mapper_with_data.is_valid_faction("SERPENTIS") is True
        assert mapper_with_data.is_valid_faction("unknown") is False

    def test_is_npc_corp(self, mapper_with_data):
        """Test NPC corp detection."""
        assert mapper_with_data.is_npc_corp(1000135) is True
        assert mapper_with_data.is_npc_corp(99999999) is False

    def test_missing_file(self, tmp_path):
        """Test handling of missing reference file."""
        mapper = NPCFactionMapper(tmp_path / "nonexistent.json")
        assert mapper.is_loaded is False
        assert mapper.faction_count == 0

    def test_invalid_json(self, tmp_path):
        """Test handling of invalid JSON."""
        ref_file = tmp_path / "invalid.json"
        ref_file.write_text("not valid json")
        mapper = NPCFactionMapper(ref_file)
        assert mapper.is_loaded is False


class TestNPCFactionMapperSingleton:
    """Tests for module-level singleton."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_npc_faction_mapper()

    def teardown_method(self):
        """Reset singleton after each test."""
        reset_npc_faction_mapper()

    def test_get_singleton(self):
        """Test singleton returns same instance."""
        mapper1 = get_npc_faction_mapper()
        mapper2 = get_npc_faction_mapper()
        assert mapper1 is mapper2

    def test_reset_singleton(self):
        """Test resetting singleton."""
        mapper1 = get_npc_faction_mapper()
        reset_npc_faction_mapper()
        mapper2 = get_npc_faction_mapper()
        assert mapper1 is not mapper2


class TestNPCFactionPatternDetection:
    """Tests for NPC faction activity pattern detection."""

    @pytest.fixture
    def sample_reference_data(self):
        """Create sample NPC corporation reference data."""
        return {
            "serpentis": {
                "faction_id": 500020,
                "name": "Serpentis",
                "corporations": [
                    {"id": 1000135, "name": "Serpentis Corporation"},
                ],
            },
        }

    @pytest.fixture
    def mapper(self, sample_reference_data, tmp_path):
        """Create mapper with sample data."""
        ref_file = tmp_path / "npc_corporations.json"
        ref_file.write_text(json.dumps(sample_reference_data))
        # Reset singleton and set up with our test data
        reset_npc_faction_mapper()
        return NPCFactionMapper(ref_file)

    def test_pattern_not_detected_without_npc_result(self):
        """Test pattern not detected when npc_result is None."""
        from unittest.mock import MagicMock

        from aria_esi.services.redisq.notifications.patterns import PatternDetector

        mock_cache = MagicMock()
        detector = PatternDetector(mock_cache)

        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now() - timedelta(minutes=2),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=3,
            attacker_corps=[1000135],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=15_000_000,
            is_pod_kill=False,
        )

        # Call _detect_npc_faction_activity directly
        result = detector._detect_npc_faction_activity(
            kill=kill,
            npc_result=None,  # No NPC result
            system_kills=[],
        )

        assert result is None

    def test_pattern_detected_with_multiple_kills(self, mapper):
        """Test pattern detected when 2+ faction kills in system."""
        from unittest.mock import MagicMock, patch

        from aria_esi.services.redisq.notifications.patterns import PatternDetector

        mock_cache = MagicMock()
        detector = PatternDetector(mock_cache)

        npc_result = NPCFactionTriggerResult(
            matched=True,
            faction="serpentis",
            corporation_id=1000135,
            corporation_name="Serpentis Corporation",
            role="attacker",
        )

        current_kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now() - timedelta(minutes=2),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=3,
            attacker_corps=[1000135],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=15_000_000,
            is_pod_kill=False,
        )

        prior_kill = ProcessedKill(
            kill_id=12345677,
            kill_time=datetime.now() - timedelta(minutes=10),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000002,
            victim_alliance_id=None,
            attacker_count=3,
            attacker_corps=[1000135],  # Same faction corp
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=10_000_000,
            is_pod_kill=False,
        )

        # Patch the get_npc_faction_mapper to return our test mapper
        with patch(
            "aria_esi.services.redisq.notifications.npc_factions.get_npc_faction_mapper",
            return_value=mapper,
        ):
            result = detector._detect_npc_faction_activity(
                kill=current_kill,
                npc_result=npc_result,
                system_kills=[prior_kill],  # 1 prior kill
            )

        assert result is not None
        assert result.pattern_type == "npc_faction_activity"
        assert result.context["faction"] == "serpentis"
        assert result.context["kill_count"] == 2  # current + prior

    def test_pattern_not_detected_single_kill(self, mapper):
        """Test pattern not detected with only 1 kill (no prior kills)."""
        from unittest.mock import MagicMock, patch

        from aria_esi.services.redisq.notifications.patterns import PatternDetector

        mock_cache = MagicMock()
        detector = PatternDetector(mock_cache)

        npc_result = NPCFactionTriggerResult(
            matched=True,
            faction="serpentis",
            corporation_id=1000135,
            corporation_name="Serpentis Corporation",
            role="attacker",
        )

        current_kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now() - timedelta(minutes=2),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=3,
            attacker_corps=[1000135],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=15_000_000,
            is_pod_kill=False,
        )

        with patch(
            "aria_esi.services.redisq.notifications.npc_factions.get_npc_faction_mapper",
            return_value=mapper,
        ):
            result = detector._detect_npc_faction_activity(
                kill=current_kill,
                npc_result=npc_result,
                system_kills=[],  # No prior kills
            )

        # Should be None since only 1 kill (below threshold of 2)
        assert result is None


class TestNPCFactionTriggerEvaluation:
    """Tests for NPC faction trigger evaluation in triggers.py."""

    @pytest.fixture
    def sample_reference_data(self):
        """Create sample NPC corporation reference data."""
        return {
            "serpentis": {
                "faction_id": 500020,
                "name": "Serpentis",
                "corporations": [
                    {"id": 1000135, "name": "Serpentis Corporation"},
                ],
            },
            "angel_cartel": {
                "faction_id": 500011,
                "name": "Angel Cartel",
                "corporations": [
                    {"id": 1000136, "name": "Guardian Angels"},
                ],
            },
        }

    @pytest.fixture
    def mapper(self, sample_reference_data, tmp_path):
        """Create mapper with sample data."""
        ref_file = tmp_path / "npc_corporations.json"
        ref_file.write_text(json.dumps(sample_reference_data))
        return NPCFactionMapper(ref_file)

    @pytest.fixture
    def kill_with_npc_attacker(self):
        """Create kill where Serpentis is attacker."""
        return ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now() - timedelta(minutes=2),
            solar_system_id=30002813,
            victim_ship_type_id=17740,  # Retriever
            victim_corporation_id=98000001,  # Player corp
            victim_alliance_id=None,
            attacker_count=3,
            attacker_corps=[1000135],  # Serpentis Corporation
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=15_000_000,
            is_pod_kill=False,
        )

    @pytest.fixture
    def kill_with_npc_victim(self):
        """Create kill where NPC is victim."""
        return ProcessedKill(
            kill_id=12345679,
            kill_time=datetime.now() - timedelta(minutes=1),
            solar_system_id=30002813,
            victim_ship_type_id=17480,
            victim_corporation_id=1000136,  # Guardian Angels (victim)
            victim_alliance_id=None,
            attacker_count=1,
            attacker_corps=[98000001],  # Player corp
            attacker_alliances=[],
            attacker_ship_types=[24690],
            final_blow_ship_type_id=24690,
            total_value=500_000,
            is_pod_kill=False,
        )

    @pytest.fixture
    def kill_no_npc(self):
        """Create kill with no NPC involvement."""
        return ProcessedKill(
            kill_id=12345680,
            kill_time=datetime.now() - timedelta(minutes=1),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],  # Player corp
            attacker_alliances=[],
            attacker_ship_types=[621],
            final_blow_ship_type_id=621,
            total_value=50_000_000,
            is_pod_kill=False,
        )

    def test_trigger_matches_npc_attacker(self, mapper, kill_with_npc_attacker):
        """Test trigger fires when NPC is attacker."""
        from aria_esi.services.redisq.notifications.config import (
            NPCFactionKillConfig,
            TriggerConfig,
        )
        from aria_esi.services.redisq.notifications.triggers import (
            TriggerType,
            evaluate_triggers,
        )

        triggers = TriggerConfig(
            watchlist_activity=False,
            gatecamp_detected=False,
            npc_faction_kill=NPCFactionKillConfig(
                enabled=True,
                factions=["serpentis"],
                as_attacker=True,
                as_victim=False,
            ),
        )

        result = evaluate_triggers(
            kill=kill_with_npc_attacker,
            entity_match=None,
            gatecamp_status=None,
            triggers=triggers,
            npc_faction_mapper=mapper,
        )

        assert result.should_notify
        assert TriggerType.NPC_FACTION_KILL in result.trigger_types
        assert result.npc_faction is not None
        assert result.npc_faction.matched
        assert result.npc_faction.faction == "serpentis"
        assert result.npc_faction.role == "attacker"

    def test_trigger_matches_npc_victim(self, mapper, kill_with_npc_victim):
        """Test trigger fires when NPC is victim (as_victim=True)."""
        from aria_esi.services.redisq.notifications.config import (
            NPCFactionKillConfig,
            TriggerConfig,
        )
        from aria_esi.services.redisq.notifications.triggers import (
            TriggerType,
            evaluate_triggers,
        )

        triggers = TriggerConfig(
            watchlist_activity=False,
            gatecamp_detected=False,
            npc_faction_kill=NPCFactionKillConfig(
                enabled=True,
                factions=["angel_cartel"],
                as_attacker=False,
                as_victim=True,
            ),
        )

        result = evaluate_triggers(
            kill=kill_with_npc_victim,
            entity_match=None,
            gatecamp_status=None,
            triggers=triggers,
            npc_faction_mapper=mapper,
        )

        assert result.should_notify
        assert TriggerType.NPC_FACTION_KILL in result.trigger_types
        assert result.npc_faction is not None
        assert result.npc_faction.faction == "angel_cartel"
        assert result.npc_faction.role == "victim"

    def test_trigger_no_match_wrong_faction(self, mapper, kill_with_npc_attacker):
        """Test trigger doesn't fire for wrong faction."""
        from aria_esi.services.redisq.notifications.config import (
            NPCFactionKillConfig,
            TriggerConfig,
        )
        from aria_esi.services.redisq.notifications.triggers import evaluate_triggers

        triggers = TriggerConfig(
            watchlist_activity=False,
            gatecamp_detected=False,
            npc_faction_kill=NPCFactionKillConfig(
                enabled=True,
                factions=["guristas"],  # Not serpentis
                as_attacker=True,
            ),
        )

        result = evaluate_triggers(
            kill=kill_with_npc_attacker,
            entity_match=None,
            gatecamp_status=None,
            triggers=triggers,
            npc_faction_mapper=mapper,
        )

        assert not result.should_notify
        assert result.npc_faction is None

    def test_trigger_no_match_as_victim_disabled(self, mapper, kill_with_npc_victim):
        """Test trigger doesn't fire when as_victim=False."""
        from aria_esi.services.redisq.notifications.config import (
            NPCFactionKillConfig,
            TriggerConfig,
        )
        from aria_esi.services.redisq.notifications.triggers import evaluate_triggers

        triggers = TriggerConfig(
            npc_faction_kill=NPCFactionKillConfig(
                enabled=True,
                factions=["angel_cartel"],
                as_attacker=True,
                as_victim=False,  # Disabled
            ),
        )

        result = evaluate_triggers(
            kill=kill_with_npc_victim,
            entity_match=None,
            gatecamp_status=None,
            triggers=triggers,
            npc_faction_mapper=mapper,
        )

        # NPC is only in victim role, as_victim is disabled
        assert result.npc_faction is None

    def test_trigger_no_match_no_npc(self, mapper, kill_no_npc):
        """Test trigger doesn't fire when no NPC involved."""
        from aria_esi.services.redisq.notifications.config import (
            NPCFactionKillConfig,
            TriggerConfig,
        )
        from aria_esi.services.redisq.notifications.triggers import evaluate_triggers

        triggers = TriggerConfig(
            npc_faction_kill=NPCFactionKillConfig(
                enabled=True,
                factions=["serpentis", "angel_cartel"],
                as_attacker=True,
                as_victim=True,
            ),
        )

        result = evaluate_triggers(
            kill=kill_no_npc,
            entity_match=None,
            gatecamp_status=None,
            triggers=triggers,
            npc_faction_mapper=mapper,
        )

        assert result.npc_faction is None

    def test_trigger_disabled(self, mapper, kill_with_npc_attacker):
        """Test trigger doesn't fire when disabled."""
        from aria_esi.services.redisq.notifications.config import (
            NPCFactionKillConfig,
            TriggerConfig,
        )
        from aria_esi.services.redisq.notifications.triggers import evaluate_triggers

        triggers = TriggerConfig(
            npc_faction_kill=NPCFactionKillConfig(
                enabled=False,  # Disabled
                factions=["serpentis"],
            ),
        )

        result = evaluate_triggers(
            kill=kill_with_npc_attacker,
            entity_match=None,
            gatecamp_status=None,
            triggers=triggers,
            npc_faction_mapper=mapper,
        )

        assert result.npc_faction is None

    def test_multiple_factions_configured(self, mapper, kill_with_npc_attacker):
        """Test trigger works with multiple factions configured."""
        from aria_esi.services.redisq.notifications.config import (
            NPCFactionKillConfig,
            TriggerConfig,
        )
        from aria_esi.services.redisq.notifications.triggers import (
            TriggerType,
            evaluate_triggers,
        )

        triggers = TriggerConfig(
            npc_faction_kill=NPCFactionKillConfig(
                enabled=True,
                factions=["serpentis", "angel_cartel", "guristas"],
                as_attacker=True,
            ),
        )

        result = evaluate_triggers(
            kill=kill_with_npc_attacker,
            entity_match=None,
            gatecamp_status=None,
            triggers=triggers,
            npc_faction_mapper=mapper,
        )

        assert result.should_notify
        assert TriggerType.NPC_FACTION_KILL in result.trigger_types
        assert result.npc_faction.faction == "serpentis"
