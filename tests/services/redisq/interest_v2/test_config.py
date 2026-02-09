"""
Tests for Interest Engine v2 configuration.
"""


from aria_esi.services.redisq.interest_v2.config import (
    InterestConfigV2,
    PrefetchConfig,
    RulesConfig,
    ThresholdsConfig,
    parse_customize_adjustment,
)
from aria_esi.services.redisq.interest_v2.models import AggregationMode, ConfigTier


class TestThresholdsConfig:
    """Tests for ThresholdsConfig."""

    def test_defaults(self):
        config = ThresholdsConfig()
        assert config.priority == 0.85
        assert config.notify == 0.60
        assert config.digest == 0.40

    def test_from_dict(self):
        data = {"priority": 0.9, "notify": 0.7, "digest": 0.5}
        config = ThresholdsConfig.from_dict(data)
        assert config.priority == 0.9
        assert config.notify == 0.7
        assert config.digest == 0.5

    def test_validation_ordering(self):
        # Valid ordering
        config = ThresholdsConfig(priority=0.9, notify=0.6, digest=0.3)
        assert config.validate() == []

        # Invalid: digest > notify
        config = ThresholdsConfig(priority=0.9, notify=0.5, digest=0.7)
        errors = config.validate()
        assert len(errors) == 1
        assert "digest" in errors[0] and "notify" in errors[0]

        # Invalid: notify > priority
        config = ThresholdsConfig(priority=0.5, notify=0.7, digest=0.3)
        errors = config.validate()
        assert len(errors) == 1
        assert "notify" in errors[0] and "priority" in errors[0]


class TestPrefetchConfig:
    """Tests for PrefetchConfig."""

    def test_defaults(self):
        config = PrefetchConfig()
        assert config.mode == "auto"
        assert config.min_threshold is None
        assert config.unknown_assumption == 1.0

    def test_validation_invalid_mode(self):
        config = PrefetchConfig(mode="invalid")
        errors = config.validate()
        assert len(errors) == 1
        assert "Invalid prefetch mode" in errors[0]

    def test_validation_threshold_range(self):
        config = PrefetchConfig(min_threshold=1.5)
        errors = config.validate()
        assert len(errors) == 1
        assert "min_threshold" in errors[0]


class TestRulesConfig:
    """Tests for RulesConfig."""

    def test_defaults(self):
        config = RulesConfig()
        assert config.always_notify == []
        assert config.always_ignore == []
        assert not config.has_gates()
        assert not config.has_custom_rules()

    def test_has_gates(self):
        config = RulesConfig(require_all=["location"])
        assert config.has_gates()

        config = RulesConfig(require_any=["politics", "value"])
        assert config.has_gates()

    def test_has_custom_rules(self):
        config = RulesConfig(custom={"my_rule": {"template": "value_above"}})
        assert config.has_custom_rules()


class TestInterestConfigV2:
    """Tests for InterestConfigV2."""

    def test_defaults(self):
        config = InterestConfigV2()
        assert config.engine == "v1"
        assert config.mode == AggregationMode.WEIGHTED
        assert config.tier == ConfigTier.SIMPLE
        assert not config.is_v2

    def test_tier_detection_simple(self):
        """Simple tier: preset only, no weights or signals."""
        config = InterestConfigV2(preset="trade-hub")
        assert config.tier == ConfigTier.SIMPLE

        # With customize
        config = InterestConfigV2(
            preset="trade-hub",
            customize={"location": "+20%"},
        )
        assert config.tier == ConfigTier.SIMPLE

    def test_tier_detection_intermediate(self):
        """Intermediate tier: has weights but no signals."""
        config = InterestConfigV2(
            preset="trade-hub",
            weights={"location": 0.8, "value": 0.7},
        )
        assert config.tier == ConfigTier.INTERMEDIATE

    def test_tier_detection_advanced(self):
        """Advanced tier: has signals block."""
        config = InterestConfigV2(
            preset="trade-hub",
            weights={"location": 0.8},
            signals={"location": {"geographic": {}}},
        )
        assert config.tier == ConfigTier.ADVANCED

    def test_is_v2(self):
        config = InterestConfigV2(engine="v2")
        assert config.is_v2

        config = InterestConfigV2(engine="v1")
        assert not config.is_v2

    def test_from_dict_full(self, advanced_tier_config):
        """Test parsing a full advanced config."""
        config = InterestConfigV2.from_dict(advanced_tier_config)
        assert config.engine == "v2"
        assert config.mode == AggregationMode.WEIGHTED
        assert config.tier == ConfigTier.ADVANCED
        assert config.weights == {"location": 0.7, "value": 0.7, "politics": 0.2}
        assert config.signals is not None
        assert "corp_member_victim" in config.rules.always_notify
        assert "npc_only" in config.rules.always_ignore

    def test_validation_simple_tier_requires_preset(self):
        """Simple tier requires a preset."""
        config = InterestConfigV2(engine="v2")
        errors = config.validate()
        assert any("preset" in e for e in errors)

    def test_validation_simple_tier_no_weights(self):
        """Simple tier doesn't allow explicit weights."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": 0.8},
        )
        # This becomes intermediate tier, not an error
        assert config.tier == ConfigTier.INTERMEDIATE

    def test_validation_intermediate_tier_requires_preset(self):
        """Intermediate tier requires preset for signal defaults."""
        config = InterestConfigV2(
            engine="v2",
            weights={"location": 0.8, "value": 0.7},
        )
        errors = config.validate()
        assert any("preset" in e.lower() for e in errors)

    def test_validation_weight_non_negative(self):
        """Weights must be non-negative."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": -0.5, "value": 0.7},
        )
        errors = config.validate()
        assert any("non-negative" in e for e in errors)

    def test_validation_weight_all_zero(self):
        """All-zero weights should fail validation."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": 0, "value": 0, "politics": 0},
        )
        errors = config.validate()
        assert any("all category weights are zero" in e.lower() for e in errors)

    def test_validation_unknown_category(self):
        """Unknown category names should fail validation."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": 0.8, "invalid_category": 0.5},
        )
        errors = config.validate()
        assert any("Unknown category" in e for e in errors)

    def test_validation_require_all_with_disabled_category(self):
        """require_all with disabled category is an error."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": 0.8, "politics": 0},
            rules=RulesConfig(require_all=["politics"]),
        )
        errors = config.validate()
        assert any("disabled" in e.lower() and "require_all" in e for e in errors)

    def test_validation_mode_max_requires_bypass(self):
        """mode: max requires prefetch.mode: bypass."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            mode=AggregationMode.MAX,
            prefetch=PrefetchConfig(mode="strict"),
        )
        errors = config.validate()
        assert any("bypass" in e.lower() for e in errors)

    def test_to_dict_roundtrip(self, advanced_tier_config):
        """Test config can be converted to dict and back."""
        config = InterestConfigV2.from_dict(advanced_tier_config)
        result = config.to_dict()

        # Reparse
        config2 = InterestConfigV2.from_dict(result)
        assert config2.engine == config.engine
        assert config2.tier == config.tier
        assert config2.weights == config.weights


class TestParseCustomizeAdjustment:
    """Tests for customize slider parsing."""

    def test_positive_percent(self):
        assert parse_customize_adjustment("+20%") == 1.2

    def test_negative_percent(self):
        assert parse_customize_adjustment("-10%") == 0.9

    def test_zero_percent(self):
        assert parse_customize_adjustment("0%") == 1.0

    def test_empty_string(self):
        assert parse_customize_adjustment("") == 1.0

    def test_max_reduction(self):
        # -100% should give 0.0, not negative
        assert parse_customize_adjustment("-100%") == 0.0

    def test_large_increase(self):
        assert parse_customize_adjustment("+100%") == 2.0

    def test_whitespace(self):
        assert parse_customize_adjustment("  +20%  ") == 1.2
