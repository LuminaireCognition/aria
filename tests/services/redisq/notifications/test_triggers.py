"""
Tests for notification trigger evaluation.

Tests TriggerType enum, TriggerResult dataclass, evaluate_triggers function,
and related helper functions like _resolve_entity_name and _evaluate_political_entity_kill.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from aria_esi.services.redisq.notifications.config import (
    NPCFactionKillConfig,
    PoliticalEntityKillConfig,
    TriggerConfig,
)
from aria_esi.services.redisq.notifications.triggers import (
    TriggerResult,
    TriggerType,
    _evaluate_political_entity_kill,
    _resolve_entity_name,
    evaluate_triggers,
)

from .conftest import (
    make_entity_match,
    make_gatecamp_status,
    make_npc_faction_result,
    make_processed_kill,
    make_war_context,
)


class TestTriggerType:
    """Tests for TriggerType enum."""

    def test_trigger_type_values(self):
        """Verify all expected trigger types exist."""
        assert TriggerType.WATCHLIST_ACTIVITY.value == "watchlist_activity"
        assert TriggerType.GATECAMP_DETECTED.value == "gatecamp_detected"
        assert TriggerType.HIGH_VALUE.value == "high_value"
        assert TriggerType.WAR_ENGAGEMENT.value == "war_engagement"
        assert TriggerType.NPC_FACTION_KILL.value == "npc_faction_kill"
        assert TriggerType.POLITICAL_ENTITY.value == "political_entity"
        assert TriggerType.INTEREST_V2.value == "interest_v2"

    def test_trigger_type_count(self):
        """Verify expected number of trigger types."""
        assert len(TriggerType) == 7


class TestTriggerResult:
    """Tests for TriggerResult dataclass."""

    def test_default_values(self):
        """TriggerResult has sensible defaults."""
        result = TriggerResult()
        assert result.should_notify is False
        assert result.trigger_types is None
        assert result.gatecamp_status is None
        assert result.war_context is None
        assert result.npc_faction is None
        assert result.political_entity is None

    def test_primary_trigger_empty(self):
        """primary_trigger returns None when no triggers."""
        result = TriggerResult(should_notify=False, trigger_types=None)
        assert result.primary_trigger is None

    def test_primary_trigger_with_triggers(self):
        """primary_trigger returns first trigger."""
        result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.HIGH_VALUE, TriggerType.WATCHLIST_ACTIVITY],
        )
        assert result.primary_trigger == TriggerType.HIGH_VALUE

    def test_is_war_engagement_false(self):
        """is_war_engagement is False when no war context."""
        result = TriggerResult()
        assert result.is_war_engagement is False

    def test_is_war_engagement_true(self):
        """is_war_engagement is True when war context present."""
        war_context = make_war_context(is_war_engagement=True)
        result = TriggerResult(war_context=war_context)
        assert result.is_war_engagement is True

    def test_is_war_engagement_with_non_war_context(self):
        """is_war_engagement is False when context exists but not war engagement."""
        war_context = make_war_context(is_war_engagement=False)
        result = TriggerResult(war_context=war_context)
        assert result.is_war_engagement is False

    def test_is_npc_faction_kill_false(self):
        """is_npc_faction_kill is False when no NPC faction result."""
        result = TriggerResult()
        assert result.is_npc_faction_kill is False

    def test_is_npc_faction_kill_true(self):
        """is_npc_faction_kill is True when NPC faction matched."""
        npc_result = make_npc_faction_result(matched=True)
        result = TriggerResult(npc_faction=npc_result)
        assert result.is_npc_faction_kill is True

    def test_is_npc_faction_kill_not_matched(self):
        """is_npc_faction_kill is False when NPC faction exists but not matched."""
        npc_result = make_npc_faction_result(matched=False)
        result = TriggerResult(npc_faction=npc_result)
        assert result.is_npc_faction_kill is False

    def test_is_political_entity_kill_false(self):
        """is_political_entity_kill is False when no political entity result."""
        result = TriggerResult()
        assert result.is_political_entity_kill is False

    def test_is_political_entity_kill_true(self):
        """is_political_entity_kill is True when political entity matched."""
        from .conftest import make_political_entity_result

        political_result = make_political_entity_result(matched=True)
        result = TriggerResult(political_entity=political_result)
        assert result.is_political_entity_kill is True


class TestEvaluateTriggers:
    """Tests for evaluate_triggers function."""

    def test_no_triggers_matched(self):
        """Returns empty result when nothing matches."""
        kill = make_processed_kill(total_value=100)  # Below threshold
        triggers = TriggerConfig(
            watchlist_activity=True,
            gatecamp_detected=True,
            high_value_threshold=1_000_000_000,
        )

        result = evaluate_triggers(
            kill=kill,
            entity_match=None,
            gatecamp_status=None,
            triggers=triggers,
        )

        assert result.should_notify is False
        assert result.trigger_types is None

    def test_high_value_trigger(self):
        """High value kill triggers notification."""
        kill = make_processed_kill(total_value=2_000_000_000)
        triggers = TriggerConfig(high_value_threshold=1_000_000_000)

        result = evaluate_triggers(
            kill=kill,
            entity_match=None,
            gatecamp_status=None,
            triggers=triggers,
        )

        assert result.should_notify is True
        assert TriggerType.HIGH_VALUE in result.trigger_types

    def test_watchlist_trigger(self):
        """Watchlist match triggers notification."""
        kill = make_processed_kill(total_value=100)
        entity_match = make_entity_match(has_match=True)
        triggers = TriggerConfig(watchlist_activity=True)

        result = evaluate_triggers(
            kill=kill,
            entity_match=entity_match,
            gatecamp_status=None,
            triggers=triggers,
        )

        assert result.should_notify is True
        assert TriggerType.WATCHLIST_ACTIVITY in result.trigger_types

    def test_watchlist_trigger_disabled(self):
        """Watchlist trigger disabled doesn't match."""
        kill = make_processed_kill(total_value=100)
        entity_match = make_entity_match(has_match=True)
        triggers = TriggerConfig(
            watchlist_activity=False,
            high_value_threshold=10_000_000_000,
        )

        result = evaluate_triggers(
            kill=kill,
            entity_match=entity_match,
            gatecamp_status=None,
            triggers=triggers,
        )

        assert result.should_notify is False

    def test_gatecamp_high_confidence(self):
        """Gatecamp with high confidence triggers notification."""
        kill = make_processed_kill(total_value=100)
        gatecamp = make_gatecamp_status(confidence="high", kill_count=5)
        triggers = TriggerConfig(
            gatecamp_detected=True,
            high_value_threshold=10_000_000_000,
        )

        result = evaluate_triggers(
            kill=kill,
            entity_match=None,
            gatecamp_status=gatecamp,
            triggers=triggers,
        )

        assert result.should_notify is True
        assert TriggerType.GATECAMP_DETECTED in result.trigger_types
        assert result.gatecamp_status is gatecamp

    def test_gatecamp_medium_confidence(self):
        """Gatecamp with medium confidence triggers notification."""
        kill = make_processed_kill(total_value=100)
        gatecamp = make_gatecamp_status(confidence="medium", kill_count=3)
        triggers = TriggerConfig(
            gatecamp_detected=True,
            high_value_threshold=10_000_000_000,
        )

        result = evaluate_triggers(
            kill=kill,
            entity_match=None,
            gatecamp_status=gatecamp,
            triggers=triggers,
        )

        assert result.should_notify is True
        assert TriggerType.GATECAMP_DETECTED in result.trigger_types

    def test_gatecamp_low_confidence_no_trigger(self):
        """Gatecamp with low confidence doesn't trigger."""
        kill = make_processed_kill(total_value=100)
        gatecamp = make_gatecamp_status(confidence="low", kill_count=1)
        triggers = TriggerConfig(
            gatecamp_detected=True,
            high_value_threshold=10_000_000_000,
        )

        result = evaluate_triggers(
            kill=kill,
            entity_match=None,
            gatecamp_status=gatecamp,
            triggers=triggers,
        )

        assert result.should_notify is False

    def test_war_engagement_trigger(self):
        """War engagement triggers notification when enabled."""
        kill = make_processed_kill(total_value=100)
        war_context = make_war_context(is_war_engagement=True)
        triggers = TriggerConfig(
            war_activity=True,
            high_value_threshold=10_000_000_000,
        )

        result = evaluate_triggers(
            kill=kill,
            entity_match=None,
            gatecamp_status=None,
            triggers=triggers,
            war_context=war_context,
        )

        assert result.should_notify is True
        assert TriggerType.WAR_ENGAGEMENT in result.trigger_types
        assert result.war_context is war_context

    def test_war_engagement_disabled(self):
        """War engagement doesn't trigger when disabled."""
        kill = make_processed_kill(total_value=100)
        war_context = make_war_context(is_war_engagement=True)
        triggers = TriggerConfig(
            war_activity=False,
            high_value_threshold=10_000_000_000,
        )

        result = evaluate_triggers(
            kill=kill,
            entity_match=None,
            gatecamp_status=None,
            triggers=triggers,
            war_context=war_context,
        )

        # Should not trigger (war_activity disabled)
        assert result.should_notify is False

    def test_war_suppresses_gatecamp(self):
        """War engagement suppresses gatecamp trigger by default."""
        kill = make_processed_kill(total_value=100)
        war_context = make_war_context(is_war_engagement=True)
        gatecamp = make_gatecamp_status(confidence="high", kill_count=5)
        triggers = TriggerConfig(
            war_activity=True,
            war_suppress_gatecamp=True,
            gatecamp_detected=True,
            high_value_threshold=10_000_000_000,
        )

        result = evaluate_triggers(
            kill=kill,
            entity_match=None,
            gatecamp_status=gatecamp,
            triggers=triggers,
            war_context=war_context,
        )

        assert result.should_notify is True
        # War engagement should be present
        assert TriggerType.WAR_ENGAGEMENT in result.trigger_types
        # Gatecamp should NOT be present (suppressed)
        assert TriggerType.GATECAMP_DETECTED not in result.trigger_types

    def test_war_does_not_suppress_gatecamp_when_disabled(self):
        """Gatecamp trigger not suppressed when war_suppress_gatecamp is False."""
        kill = make_processed_kill(total_value=100)
        war_context = make_war_context(is_war_engagement=True)
        gatecamp = make_gatecamp_status(confidence="high", kill_count=5)
        triggers = TriggerConfig(
            war_activity=True,
            war_suppress_gatecamp=False,
            gatecamp_detected=True,
            high_value_threshold=10_000_000_000,
        )

        result = evaluate_triggers(
            kill=kill,
            entity_match=None,
            gatecamp_status=gatecamp,
            triggers=triggers,
            war_context=war_context,
        )

        # Both triggers should be present
        assert TriggerType.WAR_ENGAGEMENT in result.trigger_types
        assert TriggerType.GATECAMP_DETECTED in result.trigger_types

    def test_multiple_triggers(self):
        """Multiple triggers can match simultaneously."""
        kill = make_processed_kill(total_value=2_000_000_000)
        entity_match = make_entity_match(has_match=True)
        gatecamp = make_gatecamp_status(confidence="high")
        triggers = TriggerConfig(
            watchlist_activity=True,
            gatecamp_detected=True,
            high_value_threshold=1_000_000_000,
        )

        result = evaluate_triggers(
            kill=kill,
            entity_match=entity_match,
            gatecamp_status=gatecamp,
            triggers=triggers,
        )

        assert result.should_notify is True
        assert len(result.trigger_types) == 3
        assert TriggerType.WATCHLIST_ACTIVITY in result.trigger_types
        assert TriggerType.GATECAMP_DETECTED in result.trigger_types
        assert TriggerType.HIGH_VALUE in result.trigger_types

    def test_npc_faction_kill_trigger(self):
        """NPC faction kill triggers notification."""
        kill = make_processed_kill(
            total_value=100,
            attacker_corps=[1000125],  # Serpentis corp ID
        )
        triggers = TriggerConfig(
            npc_faction_kill=NPCFactionKillConfig(
                enabled=True,
                factions=["serpentis"],
                as_attacker=True,
            ),
            high_value_threshold=10_000_000_000,
        )

        # Create mock mapper
        mapper = MagicMock()
        mapper.get_corps_for_faction.return_value = {1000125}
        mapper.get_faction_for_corp.return_value = "serpentis"
        mapper.get_corp_name.return_value = "Serpentis Corporation"

        result = evaluate_triggers(
            kill=kill,
            entity_match=None,
            gatecamp_status=None,
            triggers=triggers,
            npc_faction_mapper=mapper,
        )

        assert result.should_notify is True
        assert TriggerType.NPC_FACTION_KILL in result.trigger_types
        assert result.npc_faction is not None
        assert result.npc_faction.matched is True

    def test_political_entity_trigger_corp_victim(self):
        """Political entity trigger matches victim corporation."""
        kill = make_processed_kill(
            total_value=100,
            victim_corporation_id=98000001,
        )
        triggers = TriggerConfig(
            political_entity=PoliticalEntityKillConfig(
                enabled=True,
                corporations=[98000001],
                as_victim=True,
            ),
            high_value_threshold=10_000_000_000,
        )

        # Populate resolved IDs
        triggers.political_entity._resolved_corp_ids = {98000001}

        with patch(
            "aria_esi.services.redisq.notifications.triggers._resolve_entity_name"
        ) as mock_resolve:
            mock_resolve.return_value = "Test Corporation"

            result = evaluate_triggers(
                kill=kill,
                entity_match=None,
                gatecamp_status=None,
                triggers=triggers,
            )

        assert result.should_notify is True
        assert TriggerType.POLITICAL_ENTITY in result.trigger_types
        assert result.political_entity is not None
        assert result.political_entity.matched is True
        assert result.political_entity.role == "victim"


class TestResolveEntityName:
    """Tests for _resolve_entity_name function."""

    def test_resolve_corporation_success(self):
        """Successfully resolves corporation name."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"name": "Test Corporation"}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            # Clear cache for this test
            from aria_esi.services.redisq.notifications import triggers

            triggers._entity_name_cache.clear()

            result = _resolve_entity_name("corporation", 98000001)

            assert result == "Test Corporation"
            mock_get.assert_called_once()
            assert "corporations" in mock_get.call_args[0][0]

    def test_resolve_alliance_success(self):
        """Successfully resolves alliance name."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"name": "Test Alliance"}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            # Clear cache
            from aria_esi.services.redisq.notifications import triggers

            triggers._entity_name_cache.clear()

            result = _resolve_entity_name("alliance", 99000001)

            assert result == "Test Alliance"
            assert "alliances" in mock_get.call_args[0][0]

    def test_resolve_uses_cache(self):
        """Subsequent calls use cache."""
        from aria_esi.services.redisq.notifications import triggers

        # Pre-populate cache
        triggers._entity_name_cache[("corporation", 98000001)] = "Cached Corp"

        result = _resolve_entity_name("corporation", 98000001)

        assert result == "Cached Corp"

    def test_resolve_request_error_returns_fallback(self):
        """Request error returns fallback name."""
        import requests

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.RequestException("Connection failed")

            # Clear cache
            from aria_esi.services.redisq.notifications import triggers

            triggers._entity_name_cache.clear()

            result = _resolve_entity_name("corporation", 98000001)

            assert result == "Corp 98000001"

    def test_resolve_unknown_entity_type(self):
        """Unknown entity type returns fallback."""
        from aria_esi.services.redisq.notifications import triggers

        triggers._entity_name_cache.clear()

        result = _resolve_entity_name("unknown", 12345)

        assert result == "Alliance 12345"  # Default fallback format


class TestEvaluatePoliticalEntityKill:
    """Tests for _evaluate_political_entity_kill function."""

    def test_min_value_filtering(self):
        """Kills below min_value are filtered."""
        kill = make_processed_kill(
            total_value=50_000_000,
            victim_corporation_id=98000001,
        )
        config = PoliticalEntityKillConfig(
            enabled=True,
            corporations=[98000001],
            min_value=100_000_000,
        )
        config._resolved_corp_ids = {98000001}

        result = _evaluate_political_entity_kill(kill, config)

        assert result is None

    def test_victim_corporation_match(self):
        """Matches when victim corp is watched."""
        kill = make_processed_kill(
            total_value=100_000_000,
            victim_corporation_id=98000001,
        )
        config = PoliticalEntityKillConfig(
            enabled=True,
            corporations=[98000001],
            as_victim=True,
        )
        config._resolved_corp_ids = {98000001}

        with patch(
            "aria_esi.services.redisq.notifications.triggers._resolve_entity_name"
        ) as mock_resolve:
            mock_resolve.return_value = "Test Corp"
            result = _evaluate_political_entity_kill(kill, config)

        assert result is not None
        assert result.matched is True
        assert result.entity_type == "corporation"
        assert result.role == "victim"

    def test_victim_alliance_match(self):
        """Matches when victim alliance is watched."""
        kill = make_processed_kill(
            total_value=100_000_000,
            victim_alliance_id=99000001,
        )
        config = PoliticalEntityKillConfig(
            enabled=True,
            alliances=[99000001],
            as_victim=True,
        )
        config._resolved_alliance_ids = {99000001}

        with patch(
            "aria_esi.services.redisq.notifications.triggers._resolve_entity_name"
        ) as mock_resolve:
            mock_resolve.return_value = "Test Alliance"
            result = _evaluate_political_entity_kill(kill, config)

        assert result is not None
        assert result.entity_type == "alliance"
        assert result.role == "victim"

    def test_attacker_corporation_match(self):
        """Matches when attacker corp is watched."""
        kill = make_processed_kill(
            total_value=100_000_000,
            attacker_corps=[98000002, 98000003],
        )
        config = PoliticalEntityKillConfig(
            enabled=True,
            corporations=[98000002],
            as_attacker=True,
        )
        config._resolved_corp_ids = {98000002}

        with patch(
            "aria_esi.services.redisq.notifications.triggers._resolve_entity_name"
        ) as mock_resolve:
            mock_resolve.return_value = "Attacker Corp"
            result = _evaluate_political_entity_kill(kill, config)

        assert result is not None
        assert result.entity_type == "corporation"
        assert result.role == "attacker"

    def test_attacker_alliance_match(self):
        """Matches when attacker alliance is watched."""
        kill = make_processed_kill(
            total_value=100_000_000,
            attacker_alliances=[99000002],
        )
        config = PoliticalEntityKillConfig(
            enabled=True,
            alliances=[99000002],
            as_attacker=True,
        )
        config._resolved_alliance_ids = {99000002}

        with patch(
            "aria_esi.services.redisq.notifications.triggers._resolve_entity_name"
        ) as mock_resolve:
            mock_resolve.return_value = "Attacker Alliance"
            result = _evaluate_political_entity_kill(kill, config)

        assert result is not None
        assert result.entity_type == "alliance"
        assert result.role == "attacker"

    def test_no_watched_entities(self):
        """Returns None when no entities are configured."""
        kill = make_processed_kill(total_value=100_000_000)
        config = PoliticalEntityKillConfig(
            enabled=True,
            corporations=[],
            alliances=[],
        )

        result = _evaluate_political_entity_kill(kill, config)

        assert result is None

    def test_as_victim_disabled(self):
        """Doesn't match victim when as_victim is False."""
        kill = make_processed_kill(
            total_value=100_000_000,
            victim_corporation_id=98000001,
        )
        config = PoliticalEntityKillConfig(
            enabled=True,
            corporations=[98000001],
            as_victim=False,
            as_attacker=True,
        )
        config._resolved_corp_ids = {98000001}

        result = _evaluate_political_entity_kill(kill, config)

        assert result is None

    def test_as_attacker_disabled(self):
        """Doesn't match attacker when as_attacker is False."""
        kill = make_processed_kill(
            total_value=100_000_000,
            attacker_corps=[98000002],
        )
        config = PoliticalEntityKillConfig(
            enabled=True,
            corporations=[98000002],
            as_victim=True,
            as_attacker=False,
        )
        config._resolved_corp_ids = {98000002}

        result = _evaluate_political_entity_kill(kill, config)

        assert result is None

    def test_uses_raw_config_when_no_resolved_ids(self):
        """Falls back to raw config when resolved IDs not set."""
        kill = make_processed_kill(
            total_value=100_000_000,
            victim_corporation_id=98000001,
        )
        config = PoliticalEntityKillConfig(
            enabled=True,
            corporations=[98000001],  # Integer in raw config
            as_victim=True,
        )
        # Don't set _resolved_corp_ids

        with patch(
            "aria_esi.services.redisq.notifications.triggers._resolve_entity_name"
        ) as mock_resolve:
            mock_resolve.return_value = "Test Corp"
            result = _evaluate_political_entity_kill(kill, config)

        assert result is not None
        assert result.matched is True
