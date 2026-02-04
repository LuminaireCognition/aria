"""
Tests for Entity Interest Layer.
"""

from __future__ import annotations

from aria_esi.services.redisq.interest.layers import (
    ALLIANCE_MEMBER_ATTACKER_INTEREST,
    ALLIANCE_MEMBER_VICTIM_INTEREST,
    CORP_MEMBER_ATTACKER_INTEREST,
    CORP_MEMBER_VICTIM_INTEREST,
    WAR_TARGET_INTEREST,
    WATCHLIST_ENTITY_INTEREST,
    EntityConfig,
    EntityLayer,
)

from .conftest import make_kill

# =============================================================================
# Test Constants
# =============================================================================

OUR_CORP_ID = 98000001
OUR_ALLIANCE_ID = 99000001
ENEMY_CORP_ID = 98506879
WAR_TARGET_ID = 98000002
WATCHED_ALLIANCE_ID = 99000002


# =============================================================================
# Configuration Tests
# =============================================================================


class TestEntityConfig:
    """Tests for EntityConfig."""

    def test_from_dict_parses_all_fields(self) -> None:
        """Config parses all fields from dict."""
        data = {
            "corp_id": OUR_CORP_ID,
            "alliance_id": OUR_ALLIANCE_ID,
            "watched_corps": [ENEMY_CORP_ID],
            "watched_alliances": [WATCHED_ALLIANCE_ID],
            "war_targets": [WAR_TARGET_ID],
        }

        config = EntityConfig.from_dict(data)

        assert config.corp_id == OUR_CORP_ID
        assert config.alliance_id == OUR_ALLIANCE_ID
        assert ENEMY_CORP_ID in config.watched_corps
        assert WATCHED_ALLIANCE_ID in config.watched_alliances
        assert WAR_TARGET_ID in config.war_targets

    def test_empty_config_returns_defaults(self) -> None:
        """Empty/None config returns defaults."""
        config = EntityConfig.from_dict(None)

        assert config.corp_id is None
        assert config.alliance_id is None
        assert len(config.watched_corps) == 0

    def test_is_configured_with_corp_id(self) -> None:
        """Config with corp_id is considered configured."""
        config = EntityConfig(corp_id=OUR_CORP_ID)
        assert config.is_configured is True

    def test_is_configured_with_watched_corps(self) -> None:
        """Config with watched_corps is considered configured."""
        config = EntityConfig(watched_corps={ENEMY_CORP_ID})
        assert config.is_configured is True

    def test_not_configured_when_empty(self) -> None:
        """Empty config is not considered configured."""
        config = EntityConfig()
        assert config.is_configured is False


# =============================================================================
# System-Only Scoring Tests
# =============================================================================


class TestEntityLayerSystemScoring:
    """Tests for score_system (no kill context)."""

    def test_system_only_returns_zero(self) -> None:
        """Entity layer requires kill context - system-only returns 0."""
        layer = EntityLayer(config=EntityConfig(corp_id=OUR_CORP_ID))

        score = layer.score_system(30000142)  # Any system

        assert score.score == 0.0
        assert score.reason is None

    def test_system_only_score_regardless_of_config(self) -> None:
        """Even with full config, system-only scoring returns 0."""
        config = EntityConfig(
            corp_id=OUR_CORP_ID,
            alliance_id=OUR_ALLIANCE_ID,
            watched_corps={ENEMY_CORP_ID},
            war_targets={WAR_TARGET_ID},
        )
        layer = EntityLayer(config=config)

        score = layer.score_system(30000142)

        assert score.score == 0.0


# =============================================================================
# Corp Member Loss Tests (CRITICAL)
# =============================================================================


class TestCorpMemberLoss:
    """Tests for corp member loss detection - the most critical feature."""

    def test_corp_member_loss_always_returns_1_0(self) -> None:
        """Corp member victim ALWAYS returns 1.0 interest."""
        layer = EntityLayer(config=EntityConfig(corp_id=OUR_CORP_ID))

        kill = make_kill(victim_corp=OUR_CORP_ID)
        score = layer.score_kill(30000142, kill)

        assert score.score == CORP_MEMBER_VICTIM_INTEREST
        assert score.score == 1.0  # Explicit assertion
        assert "corp member loss" in score.reason

    def test_corp_member_loss_in_distant_system(self) -> None:
        """Corp loss in distant system still returns 1.0."""
        layer = EntityLayer(config=EntityConfig(corp_id=OUR_CORP_ID))

        # System 30003458 is in Syndicate - far from typical operational areas
        kill = make_kill(
            victim_corp=OUR_CORP_ID,
            system_id=30003458,
        )
        score = layer.score_kill(30003458, kill)

        assert score.score == 1.0
        assert "corp member loss" in score.reason

    def test_corp_member_loss_overrides_all_other_matches(self) -> None:
        """Corp member loss takes priority over other matches."""
        config = EntityConfig(
            corp_id=OUR_CORP_ID,
            alliance_id=OUR_ALLIANCE_ID,
            watched_corps={ENEMY_CORP_ID},
        )
        layer = EntityLayer(config=config)

        # Kill where corp member dies to a watched enemy
        kill = make_kill(
            victim_corp=OUR_CORP_ID,
            victim_alliance=OUR_ALLIANCE_ID,
            attacker_corps=[ENEMY_CORP_ID],
        )
        score = layer.score_kill(30000142, kill)

        # Should be 1.0 for corp member loss, not 0.9 for watched enemy
        assert score.score == 1.0
        assert "corp member loss" in score.reason


# =============================================================================
# Corp Member Kill Tests
# =============================================================================


class TestCorpMemberKill:
    """Tests for when corp members get kills."""

    def test_corp_member_attacker_returns_high_interest(self) -> None:
        """Corp member as attacker returns 0.9 interest."""
        layer = EntityLayer(config=EntityConfig(corp_id=OUR_CORP_ID))

        kill = make_kill(attacker_corps=[OUR_CORP_ID])
        score = layer.score_kill(30000142, kill)

        assert score.score == CORP_MEMBER_ATTACKER_INTEREST
        assert "corp member kill" in score.reason


# =============================================================================
# Alliance Tests
# =============================================================================


class TestAllianceMatching:
    """Tests for alliance-based interest."""

    def test_alliance_member_victim_returns_interest(self) -> None:
        """Alliance member victim returns 0.8 interest."""
        layer = EntityLayer(config=EntityConfig(alliance_id=OUR_ALLIANCE_ID))

        kill = make_kill(victim_alliance=OUR_ALLIANCE_ID)
        score = layer.score_kill(30000142, kill)

        assert score.score == ALLIANCE_MEMBER_VICTIM_INTEREST
        assert "alliance member loss" in score.reason

    def test_alliance_member_attacker_returns_interest(self) -> None:
        """Alliance member attacker returns 0.75 interest."""
        layer = EntityLayer(config=EntityConfig(alliance_id=OUR_ALLIANCE_ID))

        kill = make_kill(attacker_alliances=[OUR_ALLIANCE_ID])
        score = layer.score_kill(30000142, kill)

        assert score.score == ALLIANCE_MEMBER_ATTACKER_INTEREST
        assert "alliance member kill" in score.reason

    def test_corp_victim_takes_priority_over_alliance(self) -> None:
        """Corp member loss (1.0) beats alliance member loss (0.8)."""
        config = EntityConfig(
            corp_id=OUR_CORP_ID,
            alliance_id=OUR_ALLIANCE_ID,
        )
        layer = EntityLayer(config=config)

        # Both corp and alliance match
        kill = make_kill(
            victim_corp=OUR_CORP_ID,
            victim_alliance=OUR_ALLIANCE_ID,
        )
        score = layer.score_kill(30000142, kill)

        assert score.score == 1.0  # Corp loss, not alliance loss


# =============================================================================
# War Target Tests
# =============================================================================


class TestWarTargets:
    """Tests for war target tracking."""

    def test_war_target_killed_returns_0_95(self) -> None:
        """War target as victim returns 0.95 interest."""
        config = EntityConfig(war_targets={WAR_TARGET_ID})
        layer = EntityLayer(config=config)

        kill = make_kill(victim_corp=WAR_TARGET_ID)
        score = layer.score_kill(30000142, kill)

        assert score.score == WAR_TARGET_INTEREST
        assert "war target killed" in score.reason

    def test_war_target_attacker_returns_0_95(self) -> None:
        """War target as attacker returns 0.95 interest."""
        config = EntityConfig(war_targets={WAR_TARGET_ID})
        layer = EntityLayer(config=config)

        kill = make_kill(attacker_corps=[WAR_TARGET_ID])
        score = layer.score_kill(30000142, kill)

        assert score.score == WAR_TARGET_INTEREST
        assert "war target activity" in score.reason

    def test_add_and_remove_war_target(self) -> None:
        """Can dynamically add and remove war targets."""
        layer = EntityLayer(config=EntityConfig())

        # Initially no war targets
        kill = make_kill(victim_corp=WAR_TARGET_ID)
        assert layer.score_kill(30000142, kill).score == 0.0

        # Add war target
        layer.add_war_target(WAR_TARGET_ID)
        assert layer.score_kill(30000142, kill).score == WAR_TARGET_INTEREST

        # Remove war target
        layer.remove_war_target(WAR_TARGET_ID)
        assert layer.score_kill(30000142, kill).score == 0.0


# =============================================================================
# Watchlist Tests
# =============================================================================


class TestWatchlist:
    """Tests for watched entity tracking."""

    def test_watched_corp_victim_returns_interest(self) -> None:
        """Watched corp as victim returns 0.9 interest."""
        config = EntityConfig(watched_corps={ENEMY_CORP_ID})
        layer = EntityLayer(config=config)

        kill = make_kill(victim_corp=ENEMY_CORP_ID)
        score = layer.score_kill(30000142, kill)

        assert score.score == WATCHLIST_ENTITY_INTEREST
        assert "watched corp victim" in score.reason

    def test_watched_corp_attacker_returns_interest(self) -> None:
        """Watched corp as attacker returns 0.9 interest."""
        config = EntityConfig(watched_corps={ENEMY_CORP_ID})
        layer = EntityLayer(config=config)

        kill = make_kill(attacker_corps=[ENEMY_CORP_ID])
        score = layer.score_kill(30000142, kill)

        assert score.score == WATCHLIST_ENTITY_INTEREST
        assert "watched corp attacker" in score.reason

    def test_watched_alliance_victim_returns_interest(self) -> None:
        """Watched alliance as victim returns 0.9 interest."""
        config = EntityConfig(watched_alliances={WATCHED_ALLIANCE_ID})
        layer = EntityLayer(config=config)

        kill = make_kill(victim_alliance=WATCHED_ALLIANCE_ID)
        score = layer.score_kill(30000142, kill)

        assert score.score == WATCHLIST_ENTITY_INTEREST
        assert "watched alliance victim" in score.reason

    def test_watched_alliance_attacker_returns_interest(self) -> None:
        """Watched alliance as attacker returns 0.9 interest."""
        config = EntityConfig(watched_alliances={WATCHED_ALLIANCE_ID})
        layer = EntityLayer(config=config)

        kill = make_kill(attacker_alliances=[WATCHED_ALLIANCE_ID])
        score = layer.score_kill(30000142, kill)

        assert score.score == WATCHLIST_ENTITY_INTEREST
        assert "watched alliance attacker" in score.reason


# =============================================================================
# Multiple Matches Tests
# =============================================================================


class TestMultipleMatches:
    """Tests for kills with multiple entity matches."""

    def test_multiple_matches_uses_highest(self) -> None:
        """When multiple entities match, highest interest wins."""
        config = EntityConfig(
            watched_corps={ENEMY_CORP_ID},  # 0.9
            war_targets={WAR_TARGET_ID},  # 0.95
        )
        layer = EntityLayer(config=config)

        # Both watched and war target attack
        kill = make_kill(
            attacker_corps=[ENEMY_CORP_ID, WAR_TARGET_ID],
        )
        score = layer.score_kill(30000142, kill)

        # War target (0.95) should win over watched (0.9)
        assert score.score == WAR_TARGET_INTEREST
        assert "war target" in score.reason

    def test_no_match_returns_zero(self) -> None:
        """Kill with no entity matches returns 0."""
        config = EntityConfig(
            corp_id=OUR_CORP_ID,
            watched_corps={ENEMY_CORP_ID},
        )
        layer = EntityLayer(config=config)

        # Random kill with unknown entities
        kill = make_kill(
            victim_corp=12345678,
            attacker_corps=[87654321],
        )
        score = layer.score_kill(30000142, kill)

        assert score.score == 0.0
        assert score.reason is None


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for serialization and deserialization."""

    def test_to_dict_includes_config(self) -> None:
        """to_dict serializes configuration."""
        config = EntityConfig(
            corp_id=OUR_CORP_ID,
            alliance_id=OUR_ALLIANCE_ID,
            watched_corps={ENEMY_CORP_ID},
            war_targets={WAR_TARGET_ID},
        )
        layer = EntityLayer(config=config)

        data = layer.to_dict()

        assert data["config"]["corp_id"] == OUR_CORP_ID
        assert data["config"]["alliance_id"] == OUR_ALLIANCE_ID
        assert ENEMY_CORP_ID in data["config"]["watched_corps"]
        assert WAR_TARGET_ID in data["config"]["war_targets"]

    def test_from_dict_restores_layer(self) -> None:
        """from_dict restores layer with config."""
        config = EntityConfig(
            corp_id=OUR_CORP_ID,
            watched_corps={ENEMY_CORP_ID},
        )
        layer = EntityLayer(config=config)

        data = layer.to_dict()
        restored = EntityLayer.from_dict(data)

        # Check restored layer works
        kill = make_kill(victim_corp=OUR_CORP_ID)
        score = restored.score_kill(30000142, kill)

        assert score.score == 1.0


# =============================================================================
# Integration with Calculator
# =============================================================================


class TestCalculatorIntegration:
    """Tests verifying entity layer integrates correctly with calculator."""

    def test_entity_layer_with_calculator(self) -> None:
        """Entity layer works with InterestCalculator."""
        from aria_esi.services.redisq.interest import InterestCalculator

        from .conftest import MockGeographicLayer

        # Geographic layer doesn't include the kill's system
        geo_layer = MockGeographicLayer(interest_map={})

        # Entity layer with our corp
        entity_layer = EntityLayer(config=EntityConfig(corp_id=OUR_CORP_ID))

        calculator = InterestCalculator(layers=[geo_layer, entity_layer])

        # Corp member dies in random system
        kill = make_kill(victim_corp=OUR_CORP_ID, system_id=30000142)

        # System-only check returns 0 (geographic empty, entity needs kill)
        system_score = calculator.calculate_system_interest(30000142)
        assert system_score.interest == 0.0

        # Kill check returns 1.0 (entity layer dominates)
        kill_score = calculator.calculate_kill_interest(30000142, kill)
        assert kill_score.interest == 1.0
        assert kill_score.dominant_layer == "entity"
