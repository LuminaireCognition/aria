"""
Tests for InterestCalculator.
"""

from __future__ import annotations

from aria_esi.services.redisq.interest import (
    InterestCalculator,
    InterestScore,
    LayerScore,
)
from aria_esi.services.redisq.interest.models import (
    get_tier,
)

from .conftest import (
    MockEntityLayer,
    MockGeographicLayer,
    MockPatternLayer,
    make_kill,
)

# =============================================================================
# Tier Classification Tests
# =============================================================================


class TestTierClassification:
    """Tests for interest tier classification."""

    def test_tier_filter_at_zero(self) -> None:
        """Interest 0.0 maps to filter tier."""
        assert get_tier(0.0) == "filter"

    def test_tier_log_only_below_threshold(self) -> None:
        """Interest below 0.3 maps to log_only tier."""
        assert get_tier(0.1) == "log_only"
        assert get_tier(0.29) == "log_only"

    def test_tier_digest_mid_range(self) -> None:
        """Interest 0.3-0.6 maps to digest tier."""
        assert get_tier(0.3) == "digest"
        assert get_tier(0.5) == "digest"
        assert get_tier(0.59) == "digest"

    def test_tier_standard_above_digest(self) -> None:
        """Interest 0.6-0.8 maps to standard tier."""
        assert get_tier(0.6) == "standard"
        assert get_tier(0.7) == "standard"
        assert get_tier(0.79) == "standard"

    def test_tier_priority_high_interest(self) -> None:
        """Interest >= 0.8 maps to priority tier."""
        assert get_tier(0.8) == "priority"
        assert get_tier(0.9) == "priority"
        assert get_tier(1.0) == "priority"


# =============================================================================
# Calculator Core Tests
# =============================================================================


class TestCalculatorCore:
    """Tests for InterestCalculator basic functionality."""

    def test_empty_calculator_returns_zero(self) -> None:
        """Calculator with no layers returns zero interest."""
        calculator = InterestCalculator(layers=[])
        score = calculator.calculate_system_interest(30002537)

        assert score.interest == 0.0
        assert score.dominant_layer == "none"
        assert score.tier == "filter"

    def test_single_layer_score_passthrough(self) -> None:
        """Single layer score becomes final interest."""
        geo_layer = MockGeographicLayer(interest_map={30002537: 0.9})
        calculator = InterestCalculator(layers=[geo_layer])

        score = calculator.calculate_system_interest(30002537)

        assert score.interest == 0.9
        assert score.dominant_layer == "geographic"
        assert "geographic" in score.layer_scores

    def test_max_layer_wins(self) -> None:
        """Interest is max of layer scores, not sum."""
        geo_layer = MockGeographicLayer(interest_map={30002537: 0.5})
        entity_layer = MockEntityLayer(
            corp_id=98000001,
            watched_corps={98506879},
        )
        calculator = InterestCalculator(layers=[geo_layer, entity_layer])

        # Kill with watched corp attacker (0.9 from entity)
        kill = make_kill(
            system_id=30002537,
            attacker_corps=[98506879],
        )

        score = calculator.calculate_kill_interest(30002537, kill)

        # Entity layer (0.9) should win over geographic (0.5)
        assert score.interest == 0.9
        assert score.dominant_layer == "entity"
        assert score.layer_scores["geographic"].score == 0.5
        assert score.layer_scores["entity"].score == 0.9

    def test_corp_member_loss_always_max_interest(self) -> None:
        """Corp member losses always get interest 1.0 regardless of location."""
        # System NOT in geographic topology
        geo_layer = MockGeographicLayer(interest_map={})  # Empty - nothing tracked
        entity_layer = MockEntityLayer(corp_id=98000001)

        calculator = InterestCalculator(layers=[geo_layer, entity_layer])

        # Corp member dies in distant system
        kill = make_kill(
            victim_corp=98000001,
            system_id=30000142,  # Jita - not in topology
        )

        score = calculator.calculate_kill_interest(30000142, kill)

        assert score.interest == 1.0
        assert score.dominant_layer == "entity"
        assert score.layer_scores["entity"].reason == "corp member loss"

    def test_should_fetch_respects_threshold(self) -> None:
        """should_fetch() returns True only when above threshold."""
        geo_layer = MockGeographicLayer(
            interest_map={
                30002537: 0.5,  # Above threshold
                30002538: 0.0,  # At threshold
            }
        )
        calculator = InterestCalculator(
            layers=[geo_layer],
            fetch_threshold=0.0,
        )

        # System with interest should be fetched
        assert calculator.should_fetch(30002537) is True

        # System at threshold should NOT be fetched (> not >=)
        assert calculator.should_fetch(30002538) is False

        # Unknown system should NOT be fetched
        assert calculator.should_fetch(99999999) is False


# =============================================================================
# Escalation Multiplier Tests
# =============================================================================


class TestEscalationMultiplier:
    """Tests for pattern escalation multiplier."""

    def test_escalation_multiplier_applied(self) -> None:
        """Escalation multiplier increases final interest."""
        geo_layer = MockGeographicLayer(interest_map={30002540: 0.5})
        pattern_layer = MockPatternLayer(
            escalations={30002540: (1.5, "Active gatecamp")}
        )

        calculator = InterestCalculator(layers=[geo_layer])
        calculator.set_pattern_layer(pattern_layer)

        score = calculator.calculate_system_interest(30002540)

        # 0.5 * 1.5 = 0.75
        assert score.interest == 0.75
        assert score.base_interest == 0.5
        assert score.escalation is not None
        assert score.escalation.multiplier == 1.5
        assert score.escalation.reason == "Active gatecamp"

    def test_escalation_capped_at_one(self) -> None:
        """Final interest is capped at 1.0 even with high escalation."""
        geo_layer = MockGeographicLayer(interest_map={30002540: 0.9})
        pattern_layer = MockPatternLayer(
            escalations={30002540: (1.5, "Active gatecamp")}
        )

        calculator = InterestCalculator(layers=[geo_layer])
        calculator.set_pattern_layer(pattern_layer)

        score = calculator.calculate_system_interest(30002540)

        # 0.9 * 1.5 = 1.35, but capped at 1.0
        assert score.interest == 1.0
        assert score.base_interest == 0.9

    def test_no_escalation_when_multiplier_is_one(self) -> None:
        """No escalation object when multiplier is 1.0."""
        geo_layer = MockGeographicLayer(interest_map={30002537: 0.5})
        pattern_layer = MockPatternLayer(escalations={})  # No escalations

        calculator = InterestCalculator(layers=[geo_layer])
        calculator.set_pattern_layer(pattern_layer)

        score = calculator.calculate_system_interest(30002537)

        assert score.interest == 0.5
        assert score.escalation is None  # No escalation when multiplier is 1.0


# =============================================================================
# Layer Management Tests
# =============================================================================


class TestLayerManagement:
    """Tests for adding and managing layers."""

    def test_add_layer(self) -> None:
        """Can add layers after construction."""
        calculator = InterestCalculator(layers=[])
        geo_layer = MockGeographicLayer(interest_map={30002537: 0.7})

        calculator.add_layer(geo_layer)

        assert "geographic" in calculator.layer_names
        assert calculator.get_layer("geographic") is geo_layer

    def test_get_nonexistent_layer_returns_none(self) -> None:
        """get_layer returns None for unknown layer."""
        calculator = InterestCalculator(layers=[])
        assert calculator.get_layer("nonexistent") is None

    def test_layer_names_includes_pattern(self) -> None:
        """layer_names includes pattern layer with marker."""
        geo_layer = MockGeographicLayer()
        pattern_layer = MockPatternLayer()

        calculator = InterestCalculator(layers=[geo_layer])
        calculator.set_pattern_layer(pattern_layer)

        assert "geographic" in calculator.layer_names
        assert "pattern (escalation)" in calculator.layer_names


# =============================================================================
# InterestScore Model Tests
# =============================================================================


class TestInterestScoreModel:
    """Tests for InterestScore data class."""

    def test_tier_property(self) -> None:
        """tier property reflects interest value."""
        score = InterestScore(
            system_id=30002537,
            interest=0.9,
            base_interest=0.9,
            dominant_layer="entity",
        )
        assert score.tier == "priority"

    def test_should_notify_for_standard_and_priority(self) -> None:
        """should_notify is True for standard and priority tiers."""
        standard = InterestScore(
            system_id=1,
            interest=0.7,
            base_interest=0.7,
            dominant_layer="geographic",
        )
        priority = InterestScore(
            system_id=1,
            interest=0.9,
            base_interest=0.9,
            dominant_layer="entity",
        )
        digest = InterestScore(
            system_id=1,
            interest=0.4,
            base_interest=0.4,
            dominant_layer="geographic",
        )

        assert standard.should_notify is True
        assert priority.should_notify is True
        assert digest.should_notify is False

    def test_layer_breakdown_sorted_by_score(self) -> None:
        """get_layer_breakdown returns scores in descending order."""
        score = InterestScore(
            system_id=1,
            interest=0.9,
            base_interest=0.9,
            dominant_layer="entity",
            layer_scores={
                "geographic": LayerScore("geographic", 0.5, "in area"),
                "entity": LayerScore("entity", 0.9, "corp loss"),
                "route": LayerScore("route", 0.0, None),
            },
        )

        breakdown = score.get_layer_breakdown()

        assert breakdown[0] == ("entity", 0.9, "corp loss")
        assert breakdown[1] == ("geographic", 0.5, "in area")
        assert breakdown[2] == ("route", 0.0, None)

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict serializes all relevant fields."""
        score = InterestScore(
            system_id=30002537,
            interest=0.9,
            base_interest=0.9,
            dominant_layer="entity",
            layer_scores={
                "entity": LayerScore("entity", 0.9, "corp loss"),
            },
        )

        d = score.to_dict()

        assert d["system_id"] == 30002537
        assert d["interest"] == 0.9
        assert d["dominant_layer"] == "entity"
        assert d["tier"] == "priority"
        assert "entity" in d["layer_scores"]


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for graceful error handling."""

    def test_layer_exception_doesnt_crash(self) -> None:
        """Layer throwing exception doesn't crash calculator."""

        class FailingLayer(MockGeographicLayer):
            def score_system(self, system_id: int) -> LayerScore:
                raise ValueError("Intentional test failure")

        calculator = InterestCalculator(layers=[FailingLayer()])

        # Should not raise, returns zero score for failed layer
        score = calculator.calculate_system_interest(30002537)

        assert score.interest == 0.0
        assert "Error" in score.layer_scores["geographic"].reason


# =============================================================================
# Integration-Style Tests
# =============================================================================


class TestMultiLayerIntegration:
    """Tests with multiple layers working together."""

    def test_geographic_only_matches_legacy_behavior(self) -> None:
        """With only geographic layer, behaves like legacy topology."""
        # Simulate legacy topology: only geographic interest matters
        geo_layer = MockGeographicLayer(
            interest_map={
                30002537: 1.0,  # Tama - operational
                30002538: 1.0,  # Kedama - hop 1
                30002539: 0.7,  # 2-hop
            }
        )

        calculator = InterestCalculator(layers=[geo_layer])

        # Operational system
        score = calculator.calculate_system_interest(30002537)
        assert score.interest == 1.0
        assert score.should_fetch is True

        # 2-hop system
        score = calculator.calculate_system_interest(30002539)
        assert score.interest == 0.7
        assert score.should_fetch is True

        # Unknown system
        score = calculator.calculate_system_interest(30000142)
        assert score.interest == 0.0
        assert score.should_fetch is False

    def test_full_pipeline_corp_loss_always_notifies(self) -> None:
        """Corp member loss triggers priority notification everywhere."""
        # Geographic layer doesn't include distant system
        geo_layer = MockGeographicLayer(interest_map={30002537: 1.0})
        # Entity layer with our corp
        entity_layer = MockEntityLayer(corp_id=98000001)

        calculator = InterestCalculator(layers=[geo_layer, entity_layer])

        # Corp member dies far away (system not in geo topology)
        distant_system = 30003458  # Syndicate - definitely not near Tama
        kill = make_kill(
            victim_corp=98000001,
            system_id=distant_system,
        )

        # System-only check might return low interest
        system_score = calculator.calculate_system_interest(distant_system)
        # But with kill context, entity layer returns 1.0
        kill_score = calculator.calculate_kill_interest(distant_system, kill)

        assert kill_score.interest == 1.0
        assert kill_score.dominant_layer == "entity"
        assert kill_score.should_notify is True
        assert kill_score.is_priority is True

    def test_explain_system_generates_readable_output(self) -> None:
        """explain_system produces human-readable breakdown."""
        geo_layer = MockGeographicLayer(interest_map={30002537: 0.5})
        entity_layer = MockEntityLayer(corp_id=98000001)

        calculator = InterestCalculator(layers=[geo_layer, entity_layer])

        explanation = calculator.explain_system(30002537)

        assert "Interest Breakdown" in explanation
        assert "30002537" in explanation
        assert "geographic" in explanation
        assert "entity" in explanation
