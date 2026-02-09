"""
Integration Tests for Context-Aware Topology.

Tests the full pipeline from config to filtering.
"""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.interest import (
    ContextAwareTopologyConfig,
    InterestCalculator,
    InterestScore,
)
from aria_esi.services.redisq.interest.layers import (
    EntityConfig,
    EntityLayer,
    GeographicConfig,
    GeographicLayer,
)
from tests.mcp.conftest import create_mock_universe

from .conftest import MockGeographicLayer, make_kill

# =============================================================================
# Test Universe Setup
# =============================================================================


TEST_SYSTEMS = [
    {"name": "Tama", "id": 30002537, "sec": 0.3, "const": 20000001, "region": 10000001},
    {"name": "Kedama", "id": 30002538, "sec": 0.2, "const": 20000001, "region": 10000001},
    {"name": "Sujarento", "id": 30002539, "sec": 0.4, "const": 20000001, "region": 10000001},
    {"name": "Jita", "id": 30000142, "sec": 0.9, "const": 20000020, "region": 10000002},
    {"name": "Perimeter", "id": 30000144, "sec": 0.9, "const": 20000020, "region": 10000002},
    {"name": "Distant", "id": 30003458, "sec": 0.5, "const": 20000003, "region": 10000003},
]

TEST_EDGES = [
    (0, 1),  # Tama -- Kedama
    (1, 2),  # Kedama -- Sujarento
    (2, 3),  # Sujarento -- Jita
    (3, 4),  # Jita -- Perimeter
]


@pytest.fixture
def test_universe():
    """Create test universe."""
    return create_mock_universe(TEST_SYSTEMS, TEST_EDGES)


# =============================================================================
# Config Tests
# =============================================================================


class TestContextAwareTopologyConfig:
    """Tests for ContextAwareTopologyConfig."""

    def test_from_dict_parses_all_sections(self) -> None:
        """Config parses all sections from dict."""
        data = {
            "enabled": True,
            "archetype": "hunter",
            "geographic": {
                "systems": [{"name": "Tama", "classification": "home"}]
            },
            "entity": {"corp_id": 98000001},
            "routes": [{"waypoints": ["Tama", "Jita"]}],
            "fetch_threshold": 0.1,
        }

        config = ContextAwareTopologyConfig.from_dict(data)

        assert config.enabled is True
        assert config.archetype == "hunter"
        assert config.has_geographic is True
        assert config.has_entity is True
        assert config.has_routes is True
        assert config.fetch_threshold == 0.1

    def test_empty_config_is_disabled(self) -> None:
        """Empty config results in disabled state."""
        config = ContextAwareTopologyConfig.from_dict(None)

        assert config.enabled is False
        assert config.has_geographic is False
        assert config.has_entity is False
        assert config.has_routes is False

    def test_validate_catches_threshold_errors(self) -> None:
        """Validation catches invalid thresholds."""
        config = ContextAwareTopologyConfig(
            enabled=True,
            fetch_threshold=1.5,  # Invalid
            log_threshold=0.2,
            digest_threshold=0.1,  # Out of order
        )

        errors = config.validate()

        assert any("fetch_threshold" in e for e in errors)
        assert any("digest_threshold" in e or "must be >=" in e for e in errors)

    def test_validate_catches_invalid_classification(self) -> None:
        """Validation catches invalid system classification."""
        config = ContextAwareTopologyConfig(
            enabled=True,
            geographic={
                "systems": [
                    {"name": "Tama", "classification": "invalid_type"}
                ]
            },
        )

        errors = config.validate()

        assert any("invalid classification" in e for e in errors)


# =============================================================================
# Full Pipeline Tests
# =============================================================================


class TestFullPipeline:
    """Tests for full interest calculation pipeline."""

    def test_corp_loss_always_notifies(self, test_universe) -> None:
        """Corp member loss returns 1.0 regardless of location."""
        # Build calculator with geographic and entity layers
        geo_config = GeographicConfig.from_dict({
            "systems": [{"name": "Tama", "classification": "home"}]
        })
        geo_layer = GeographicLayer.from_config(geo_config, test_universe)

        entity_layer = EntityLayer.from_config(
            EntityConfig(corp_id=98000001)
        )

        calculator = InterestCalculator(layers=[geo_layer, entity_layer])

        # Create kill in distant system (not in geography)
        kill = make_kill(
            victim_corp=98000001,  # Our corp
            system_id=30003458,  # "Distant" - not in geographic layer
        )

        # Calculate interest
        score = calculator.calculate_kill_interest(30003458, kill)

        # Should be 1.0 because entity layer (corp loss) overrides everything
        assert score.interest == 1.0
        assert score.dominant_layer == "entity"
        assert "corp member" in score.dominant_reason.lower()

    def test_geographic_only_matches_legacy_behavior(self, test_universe) -> None:
        """Geographic-only config should behave like legacy topology."""
        # Build calculator from direct geographic config (legacy-equivalent weights)
        geo_layer = GeographicLayer.from_legacy_config(
            operational_systems=["Tama"],
            interest_weights={
                "operational": 1.0,
                "hop_1": 1.0,
                "hop_2": 0.7,
            },
            graph=test_universe,
        )

        calculator = InterestCalculator(layers=[geo_layer])

        # Check operational system
        score = calculator.calculate_system_interest(30002537)  # Tama
        assert score.interest == 1.0

        # Check 1-hop neighbor
        score = calculator.calculate_system_interest(30002538)  # Kedama
        assert score.interest == 1.0

        # Check 2-hop neighbor
        score = calculator.calculate_system_interest(30002539)  # Sujarento
        assert score.interest == 0.7

        # Check distant system (not in topology)
        score = calculator.calculate_system_interest(30003458)
        assert score.interest == 0.0

    def test_entity_layer_requires_kill_context(self) -> None:
        """Entity layer returns 0 without kill context."""
        entity_layer = EntityLayer.from_config(
            EntityConfig(corp_id=98000001)
        )

        calculator = InterestCalculator(layers=[entity_layer])

        # System-only check returns 0 (no kill to inspect)
        score = calculator.calculate_system_interest(30002537)
        assert score.interest == 0.0

        # With kill context, returns interest
        kill = make_kill(victim_corp=98000001, system_id=30002537)
        score = calculator.calculate_kill_interest(30002537, kill)
        assert score.interest == 1.0

    def test_max_layer_wins(self) -> None:
        """Interest is max of all layer scores."""
        # Layer returning 0.5
        layer_low = MockGeographicLayer(interest_map={30002537: 0.5})

        # Layer returning 0.8
        layer_high = MockGeographicLayer(interest_map={30002537: 0.8})
        layer_high._name = "high_layer"

        calculator = InterestCalculator(layers=[layer_low, layer_high])

        score = calculator.calculate_system_interest(30002537)

        assert score.interest == 0.8
        assert score.dominant_layer == "high_layer"

    def test_escalation_multiplier_applied(self) -> None:
        """Pattern escalation multiplies base interest."""
        from aria_esi.services.redisq.interest.layers import PatternConfig, PatternLayer

        geo_layer = MockGeographicLayer(interest_map={30002537: 0.6})

        pattern_layer = PatternLayer.from_config(PatternConfig())
        pattern_layer.set_escalation(30002537, 1.5, "Gatecamp")

        calculator = InterestCalculator(layers=[geo_layer])
        calculator.set_pattern_layer(pattern_layer)

        score = calculator.calculate_system_interest(30002537)

        # 0.6 * 1.5 = 0.9
        assert score.interest == pytest.approx(0.9)
        assert score.base_interest == pytest.approx(0.6)
        assert score.escalation is not None
        assert score.escalation.multiplier == 1.5

    def test_escalation_capped_at_1_0(self) -> None:
        """Escalation cannot push interest above 1.0."""
        from aria_esi.services.redisq.interest.layers import PatternConfig, PatternLayer

        geo_layer = MockGeographicLayer(interest_map={30002537: 0.9})

        pattern_layer = PatternLayer.from_config(PatternConfig())
        pattern_layer.set_escalation(30002537, 1.5, "Gatecamp")

        calculator = InterestCalculator(layers=[geo_layer])
        calculator.set_pattern_layer(pattern_layer)

        score = calculator.calculate_system_interest(30002537)

        # 0.9 * 1.5 = 1.35, capped at 1.0
        assert score.interest == 1.0
        assert score.base_interest == 0.9


# =============================================================================
# Tier Classification Tests
# =============================================================================


class TestTierClassification:
    """Tests for interest tier classification."""

    def test_tier_filter(self) -> None:
        """Score 0.0 maps to filter tier."""
        score = InterestScore(
            system_id=30002537,
            interest=0.0,
            base_interest=0.0,
            dominant_layer="none",
            layer_scores={},
        )
        assert score.tier == "filter"

    def test_tier_log_only(self) -> None:
        """Score < 0.3 maps to log_only tier."""
        score = InterestScore(
            system_id=30002537,
            interest=0.2,
            base_interest=0.2,
            dominant_layer="geographic",
            layer_scores={},
        )
        assert score.tier == "log_only"

    def test_tier_digest(self) -> None:
        """Score < 0.6 maps to digest tier."""
        score = InterestScore(
            system_id=30002537,
            interest=0.5,
            base_interest=0.5,
            dominant_layer="geographic",
            layer_scores={},
        )
        assert score.tier == "digest"

    def test_tier_standard(self) -> None:
        """Score < 0.8 maps to standard tier."""
        score = InterestScore(
            system_id=30002537,
            interest=0.7,
            base_interest=0.7,
            dominant_layer="geographic",
            layer_scores={},
        )
        assert score.tier == "standard"

    def test_tier_priority(self) -> None:
        """Score >= 0.8 maps to priority tier."""
        score = InterestScore(
            system_id=30002537,
            interest=0.9,
            base_interest=0.9,
            dominant_layer="entity",
            layer_scores={},
        )
        assert score.tier == "priority"


# =============================================================================
# Build Calculator Tests
# =============================================================================


class TestBuildCalculator:
    """Tests for config.build_calculator()."""

    def test_build_with_geographic_only(self, test_universe) -> None:
        """Can build calculator with just geographic layer."""
        config = ContextAwareTopologyConfig(
            enabled=True,
            geographic={
                "systems": [{"name": "Tama", "classification": "home"}]
            },
        )

        calculator = config.build_calculator(graph=test_universe)

        assert len(calculator.layers) == 1
        assert calculator.layers[0].name == "geographic"

    def test_build_with_entity_only(self) -> None:
        """Can build calculator with just entity layer."""
        config = ContextAwareTopologyConfig(
            enabled=True,
            entity={"corp_id": 98000001},
        )

        calculator = config.build_calculator()

        assert len(calculator.layers) == 1
        assert calculator.layers[0].name == "entity"

    def test_build_with_all_layers(self, test_universe) -> None:
        """Can build calculator with all layers."""
        config = ContextAwareTopologyConfig(
            enabled=True,
            geographic={
                "systems": [{"name": "Tama", "classification": "home"}]
            },
            entity={"corp_id": 98000001},
            routes=[{"waypoints": ["Tama", "Jita"]}],
            assets={"structures": True},
            patterns={"gatecamp_detection": True},
        )

        calculator = config.build_calculator(graph=test_universe)

        # Should have 4 layers (geographic, entity, route, asset)
        # Pattern is added as escalation layer, not regular layer
        assert len(calculator.layers) == 4
        assert calculator.pattern_layer is not None

        layer_names = {layer.name for layer in calculator.layers}
        assert "geographic" in layer_names
        assert "entity" in layer_names
        assert "route" in layer_names
        assert "asset" in layer_names

    def test_build_with_archetype_preset(self, test_universe) -> None:
        """Archetype preset is applied during build."""
        # Industrial preset enables assets layer by default
        config = ContextAwareTopologyConfig(
            enabled=True,
            archetype="industrial",
            geographic={
                "systems": [{"name": "Jita", "classification": "home"}]
            },
        )

        calculator = config.build_calculator(graph=test_universe)

        # Industrial preset has assets.structures=True and assets.offices=True
        # So we should have geographic + asset layers
        layer_names = {layer.name for layer in calculator.layers}
        assert "geographic" in layer_names
        assert "asset" in layer_names

    def test_build_with_archetype_user_override(self, test_universe) -> None:
        """User config overrides archetype preset values."""
        # Industrial preset has log_threshold=0.4, user overrides to 0.5
        config = ContextAwareTopologyConfig(
            enabled=True,
            archetype="industrial",
            geographic={
                "systems": [{"name": "Jita", "classification": "home"}]
            },
            log_threshold=0.5,
        )

        # Verify user override is preserved in _to_mergeable_dict
        mergeable = config._to_mergeable_dict()
        assert mergeable.get("log_threshold") == 0.5

    def test_build_with_unknown_archetype(self, test_universe) -> None:
        """Unknown archetype is ignored with warning."""
        config = ContextAwareTopologyConfig(
            enabled=True,
            archetype="nonexistent_archetype",
            geographic={
                "systems": [{"name": "Tama", "classification": "home"}]
            },
        )

        # Should still build successfully, just without preset
        calculator = config.build_calculator(graph=test_universe)
        assert len(calculator.layers) == 1  # Only geographic, no preset additions
