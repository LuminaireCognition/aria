"""
Tests for Interest Engine v2 feature flags.
"""


from aria_esi.services.redisq.interest_v2.features import (
    FeatureFlags,
    get_feature_flags,
    init_feature_flags,
    set_feature_flags,
)


class TestFeatureFlags:
    """Tests for FeatureFlags dataclass."""

    def test_defaults(self):
        flags = FeatureFlags()
        assert flags.rule_dsl is False
        assert flags.custom_signals is False
        assert flags.custom_presets is True  # Enabled by default
        assert flags.custom_scaling is False
        assert flags.delivery_webhook is True  # Enabled by default
        assert flags.delivery_slack is False
        assert flags.default_engine == "v1"

    def test_from_config_empty(self):
        flags = FeatureFlags.from_config(None)
        assert flags.rule_dsl is False
        assert flags.custom_presets is True

    def test_from_config_flat(self):
        config = {
            "features": {
                "rule_dsl": True,
                "custom_signals": True,
                "delivery_slack": True,
            }
        }
        flags = FeatureFlags.from_config(config)
        assert flags.rule_dsl is True
        assert flags.custom_signals is True
        assert flags.delivery_slack is True
        # Defaults preserved for unspecified
        assert flags.custom_presets is True

    def test_from_config_nested(self):
        """Test with just the features dict directly."""
        config = {
            "rule_dsl": True,
            "default_engine": "v2",
        }
        flags = FeatureFlags.from_config(config)
        assert flags.rule_dsl is True
        assert flags.default_engine == "v2"

    def test_to_dict(self):
        flags = FeatureFlags(rule_dsl=True, delivery_slack=True)
        result = flags.to_dict()
        assert result["rule_dsl"] is True
        assert result["delivery_slack"] is True
        assert result["custom_presets"] is True  # Default

    def test_is_delivery_enabled_builtin(self):
        flags = FeatureFlags()
        # Discord and log are always enabled
        assert flags.is_delivery_enabled("discord") is True
        assert flags.is_delivery_enabled("log") is True

    def test_is_delivery_enabled_optional(self):
        flags = FeatureFlags(delivery_slack=True)
        assert flags.is_delivery_enabled("slack") is True
        assert flags.is_delivery_enabled("email") is False

    def test_validate_rule_dsl_disabled(self):
        flags = FeatureFlags(rule_dsl=False)
        ok, error = flags.validate_rule_dsl()
        assert ok is False
        assert "rule_dsl" in error

    def test_validate_rule_dsl_enabled(self):
        flags = FeatureFlags(rule_dsl=True)
        ok, error = flags.validate_rule_dsl()
        assert ok is True
        assert error is None

    def test_validate_custom_signals(self):
        flags = FeatureFlags(custom_signals=False)
        ok, error = flags.validate_custom_signals()
        assert ok is False

        flags = FeatureFlags(custom_signals=True)
        ok, error = flags.validate_custom_signals()
        assert ok is True

    def test_validate_custom_scaling(self):
        flags = FeatureFlags(custom_scaling=False)
        ok, error = flags.validate_custom_scaling()
        assert ok is False
        assert "built-in" in error.lower()


class TestGlobalFeatureFlags:
    """Tests for global feature flags management."""

    def test_get_before_set(self):
        # Should return defaults

        # Temporarily clear global
        import aria_esi.services.redisq.interest_v2.features as features_module

        original = features_module._global_features
        features_module._global_features = None

        try:
            flags = get_feature_flags()
            assert flags is not None
            assert flags.rule_dsl is False
        finally:
            features_module._global_features = original

    def test_set_and_get(self):
        import aria_esi.services.redisq.interest_v2.features as features_module

        original = features_module._global_features

        try:
            custom_flags = FeatureFlags(rule_dsl=True, delivery_slack=True)
            set_feature_flags(custom_flags)

            retrieved = get_feature_flags()
            assert retrieved.rule_dsl is True
            assert retrieved.delivery_slack is True
        finally:
            features_module._global_features = original

    def test_init_from_config(self):
        import aria_esi.services.redisq.interest_v2.features as features_module

        original = features_module._global_features

        try:
            config = {
                "features": {
                    "rule_dsl": True,
                    "default_engine": "v2",
                }
            }
            flags = init_feature_flags(config)
            assert flags.rule_dsl is True
            assert flags.default_engine == "v2"

            # Should be set globally
            retrieved = get_feature_flags()
            assert retrieved.rule_dsl is True
        finally:
            features_module._global_features = original
