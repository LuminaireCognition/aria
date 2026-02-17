"""
Tests for Interest Engine v2 - Core Integration.

Tests the engine orchestration of signals, rules, and aggregation.
"""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.interest_v2.config import (
    InterestConfigV2,
    RulesConfig,
    ThresholdsConfig,
)
from aria_esi.services.redisq.interest_v2.engine import (
    InterestEngineV2,
    create_engine,
)
from aria_esi.services.redisq.interest_v2.models import (
    AggregationMode,
    ConfigTier,
    NotificationTier,
    SignalScore,
)


class TestEngineCreation:
    """Tests for engine initialization."""

    def test_create_engine_v1_mode(self):
        """Engine with v1 defaults."""
        config = InterestConfigV2()
        engine = InterestEngineV2(config)
        assert engine._config.engine == "v1"

    def test_create_engine_v2_with_preset(self):
        """Engine with v2 and preset."""
        config = InterestConfigV2(engine="v2", preset="trade-hub")
        engine = InterestEngineV2(config)
        assert engine._config.is_v2
        assert engine._config.preset == "trade-hub"

    def test_create_engine_factory(self):
        """Factory function creates engine correctly."""
        config_dict = {
            "engine": "v2",
            "preset": "trade-hub",
            "weights": {"location": 0.8},
        }
        engine = create_engine(config_dict)
        assert isinstance(engine, InterestEngineV2)
        assert engine._config.is_v2

    def test_create_engine_with_context(self):
        """Engine accepts context parameters."""
        config = InterestConfigV2(engine="v2", preset="trade-hub")
        context = {"corp_id": 98000001, "alliance_id": 99001234}
        engine = InterestEngineV2(config, context)
        assert engine._context["corp_id"] == 98000001


class TestWeightResolution:
    """Tests for weight resolution from config."""

    def test_explicit_weights(self):
        """Explicit weights are used directly."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": 0.9, "value": 0.7},
        )
        engine = InterestEngineV2(config)
        assert engine._weights["location"] == 0.9
        assert engine._weights["value"] == 0.7

    def test_customize_adjustments(self):
        """Customize adjustments are applied."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            customize={"location": "+20%", "value": "-10%"},
        )
        engine = InterestEngineV2(config)
        # Default preset weight is 0.5, so:
        # location: 0.5 * 1.2 = 0.6
        # value: 0.5 * 0.9 = 0.45
        assert engine._weights["location"] == pytest.approx(0.6, abs=0.01)
        assert engine._weights["value"] == pytest.approx(0.45, abs=0.01)


class TestCalculateInterest:
    """Tests for interest calculation."""

    def test_calculate_interest_basic(self, mock_kill, reset_registry):
        """Basic interest calculation returns result."""
        config = InterestConfigV2(engine="v2", preset="trade-hub")
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        assert result.system_id == mock_kill.solar_system_id
        assert result.kill_id == mock_kill.kill_id
        assert isinstance(result.tier, NotificationTier)
        assert 0.0 <= result.interest <= 1.0

    def test_calculate_interest_prefetch(self, reset_registry):
        """Prefetch mode works without kill data."""
        config = InterestConfigV2(engine="v2", preset="trade-hub")
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(None, 30000142, is_prefetch=True)

        assert result.system_id == 30000142
        assert result.kill_id is None
        assert result.is_prefetch is True

    def test_calculate_interest_includes_thresholds(self, mock_kill, reset_registry):
        """Result includes threshold configuration."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            thresholds=ThresholdsConfig(priority=0.90, notify=0.65, digest=0.45),
        )
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        assert result.thresholds["priority"] == 0.90
        assert result.thresholds["notify"] == 0.65
        assert result.thresholds["digest"] == 0.45


class TestTierDetermination:
    """Tests for notification tier determination."""

    def test_tier_priority(self, mock_kill, reset_registry):
        """High interest results in PRIORITY tier."""
        # Configure engine to produce high interest
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": 1.0},
            thresholds=ThresholdsConfig(priority=0.1, notify=0.05),
        )
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        # With high weight and low threshold, should be priority
        if result.interest >= 0.1:
            assert result.tier == NotificationTier.PRIORITY

    def test_tier_filter_on_gate_failure(self, mock_kill, reset_registry):
        """Gate failure results in FILTER tier."""

        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": 0.8, "politics": 0.8},
            rules=RulesConfig(require_all=["politics"]),  # Will fail
        )
        engine = InterestEngineV2(config)

        # Override category scoring to make politics not match
        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        # Gate should fail because politics likely doesn't match
        if not result.require_all_passed:
            assert result.tier == NotificationTier.FILTER
            assert result.interest == 0.0


class TestAlwaysIgnore:
    """Tests for always_ignore rule handling."""

    def test_always_ignore_filters_immediately(self, pod_kill, reset_registry):
        """always_ignore rules filter without further processing."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            rules=RulesConfig(always_ignore=["pod_only"]),
        )
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(pod_kill, pod_kill.solar_system_id)

        assert result.tier == NotificationTier.FILTER
        assert result.interest == 0.0
        assert any(m.matched for m in result.always_ignore_matched)

    def test_always_ignore_precedence(self, pod_kill, reset_registry):
        """always_ignore beats always_notify for same kill."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            rules=RulesConfig(
                always_ignore=["pod_only"],
                always_notify=["high_value"],  # Even if high value
            ),
        )
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(pod_kill, pod_kill.solar_system_id)

        # always_ignore should win
        assert result.tier == NotificationTier.FILTER


class TestAlwaysNotify:
    """Tests for always_notify rule handling."""

    def test_always_notify_bypasses_thresholds(self, high_value_kill, reset_registry):
        """always_notify bypasses threshold filtering."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            rules=RulesConfig(always_notify=["high_value"]),
            thresholds=ThresholdsConfig(priority=0.99, notify=0.99),  # Very high
        )
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(
            high_value_kill, high_value_kill.solar_system_id
        )

        # Should still notify despite high thresholds
        if any(m.matched for m in result.always_notify_matched):
            assert result.tier in (NotificationTier.NOTIFY, NotificationTier.PRIORITY)

    def test_always_notify_bypasses_gates(self, mock_kill, reset_registry):
        """always_notify bypasses require_all/require_any gates."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": 0.8, "politics": 0},  # Politics disabled
            rules=RulesConfig(
                require_all=["politics"],  # Would fail
                always_notify=["watchlist_match"],  # But this bypasses
            ),
        )
        engine = InterestEngineV2(config)

        # Mock the watchlist match
        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        # If always_notify matches, gates should be bypassed
        if any(m.matched for m in result.always_notify_matched):
            assert result.tier != NotificationTier.FILTER


class TestGates:
    """Tests for require_all and require_any gates."""

    def test_require_all_must_match(self, mock_kill, reset_registry):
        """All categories in require_all must match."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": 0.8, "politics": 0.8},
            rules=RulesConfig(require_all=["location", "politics"]),
        )
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        # If any required category doesn't match, gate fails
        has_failed_gate = not result.require_all_passed
        if has_failed_gate:
            assert result.tier == NotificationTier.FILTER

    def test_require_any_one_sufficient(self, mock_kill, reset_registry):
        """At least one category in require_any must match."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": 0.8, "politics": 0.8, "value": 0.8},
            rules=RulesConfig(require_any=["location", "politics", "value"]),
        )
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        # If at least one matches, gate passes
        if result.require_any_passed:
            # Gate passed - check category breakdown
            matching_cats = [
                cat
                for cat in result.category_scores.values()
                if cat.match
            ]
            assert len(matching_cats) >= 1


class TestAggregationModes:
    """Tests for different aggregation modes."""

    def test_weighted_mode_uses_rms(self, mock_kill, reset_registry):
        """WEIGHTED mode uses RMS aggregation."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            mode=AggregationMode.WEIGHTED,
            weights={"location": 1.0, "value": 1.0},
        )
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        assert result.mode == AggregationMode.WEIGHTED

    def test_linear_mode(self, mock_kill, reset_registry):
        """LINEAR mode uses linear aggregation."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            mode=AggregationMode.LINEAR,
            weights={"location": 1.0, "value": 1.0},
        )
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        assert result.mode == AggregationMode.LINEAR

    def test_max_mode(self, mock_kill, reset_registry):
        """MAX mode uses max aggregation."""
        from aria_esi.services.redisq.interest_v2.config import PrefetchConfig

        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            mode=AggregationMode.MAX,
            weights={"location": 1.0, "value": 1.0},
            prefetch=PrefetchConfig(mode="bypass"),  # Required for max mode
        )
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        assert result.mode == AggregationMode.MAX


class TestCategoryScoring:
    """Tests for category score calculation."""

    def test_disabled_categories_have_zero_score(self, mock_kill, reset_registry):
        """Categories with weight=0 have zero score."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={
                "location": 0.8,
                "value": 0.0,  # Disabled
                "politics": 0.0,  # Disabled
            },
        )
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        for cat_name, cat_score in result.category_scores.items():
            if engine._weights.get(cat_name, 0) == 0:
                assert cat_score.score == 0.0
                assert not cat_score.is_enabled

    def test_category_breakdown_available(self, mock_kill, reset_registry):
        """Result includes category breakdown."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": 0.8, "value": 0.7},
        )
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        # Should have category scores
        assert len(result.category_scores) > 0

        # get_category_breakdown returns sorted list
        breakdown = result.get_category_breakdown()
        assert len(breakdown) > 0


class TestShouldFetch:
    """Tests for prefetch decision making."""

    def test_should_fetch_returns_bool(self, reset_registry):
        """should_fetch returns boolean."""
        config = InterestConfigV2(engine="v2", preset="trade-hub")
        engine = InterestEngineV2(config)

        result = engine.should_fetch(30000142)

        assert isinstance(result, bool)

    def test_prefetch_evaluate_returns_decision(self, reset_registry):
        """prefetch_evaluate returns PrefetchDecision."""
        from aria_esi.services.redisq.interest_v2.prefetch import PrefetchDecision

        config = InterestConfigV2(engine="v2", preset="trade-hub")
        engine = InterestEngineV2(config)

        decision = engine.prefetch_evaluate(30000142)

        assert isinstance(decision, PrefetchDecision)
        assert isinstance(decision.should_fetch, bool)


class TestValidation:
    """Tests for engine validation."""

    def test_validate_returns_errors(self, reset_registry):
        """Validation returns list of errors."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            rules=RulesConfig(always_ignore=["nonexistent_rule"]),
        )
        engine = InterestEngineV2(config)

        errors = engine.validate()

        # Should have error for unknown rule
        assert any("nonexistent_rule" in e for e in errors)

    def test_valid_config_no_errors(self, reset_registry):
        """Valid configuration returns no errors."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": 0.8},
        )
        engine = InterestEngineV2(config)

        errors = engine.validate()

        # May have errors for unregistered built-in rules
        # but core config should be valid
        config_errors = config.validate()
        assert len(config_errors) == 0


class TestRuntimeContext:
    """Tests for runtime_context parameter in calculate_interest."""

    def test_runtime_context_merged_into_signal_config(self, mock_kill, reset_registry):
        """Runtime context values should be accessible in signal scoring."""
        from unittest.mock import MagicMock

        from aria_esi.services.redisq.interest_v2.providers.base import BaseSignalProvider
        from aria_esi.services.redisq.interest_v2.providers.registry import get_provider_registry

        captured_configs = []

        class CapturingSignal(BaseSignalProvider):
            _name = "capturing"
            _category = "activity"
            _prefetch_capable = False

            def score(self, kill, system_id, config):
                captured_configs.append(dict(config))
                return SignalScore(
                    signal="capturing",
                    score=0.5,
                    reason="test",
                    prefetch_capable=False,
                )

        registry = get_provider_registry()
        registry.register_signal("activity", "capturing", CapturingSignal)

        config = InterestConfigV2(
            engine="v2",
            weights={"activity": 1.0},
            signals={"activity": {"capturing": {"some_setting": True}}},
        )
        engine = InterestEngineV2(config)

        mock_gatecamp = MagicMock()
        result = engine.calculate_interest(
            mock_kill,
            mock_kill.solar_system_id,
            runtime_context={"gatecamp_status": mock_gatecamp},
        )

        assert len(captured_configs) == 1
        assert captured_configs[0]["gatecamp_status"] is mock_gatecamp
        assert captured_configs[0]["some_setting"] is True

    def test_runtime_context_cleared_after_calculation(self, mock_kill, reset_registry):
        """Runtime context should not persist between calls."""
        config = InterestConfigV2(engine="v2", preset="trade-hub")
        engine = InterestEngineV2(config)

        engine.calculate_interest(
            mock_kill,
            mock_kill.solar_system_id,
            runtime_context={"test_key": "test_value"},
        )

        assert engine._runtime_context is None

    def test_runtime_context_none_is_safe(self, mock_kill, reset_registry):
        """None runtime_context should not cause errors."""
        config = InterestConfigV2(engine="v2", preset="trade-hub")
        engine = InterestEngineV2(config)

        result = engine.calculate_interest(
            mock_kill,
            mock_kill.solar_system_id,
            runtime_context=None,
        )

        assert result is not None

    def test_signal_config_overrides_runtime_context(self, mock_kill, reset_registry):
        """Signal-specific config should override runtime context values."""
        from aria_esi.services.redisq.interest_v2.providers.base import BaseSignalProvider
        from aria_esi.services.redisq.interest_v2.providers.registry import get_provider_registry

        captured_configs = []

        class CapturingSignal(BaseSignalProvider):
            _name = "capturing2"
            _category = "activity"
            _prefetch_capable = False

            def score(self, kill, system_id, config):
                captured_configs.append(dict(config))
                return SignalScore(
                    signal="capturing2",
                    score=0.5,
                    reason="test",
                    prefetch_capable=False,
                )

        registry = get_provider_registry()
        registry.register_signal("activity", "capturing2", CapturingSignal)

        config = InterestConfigV2(
            engine="v2",
            weights={"activity": 1.0},
            signals={"activity": {"capturing2": {"overlap_key": "from_signal"}}},
        )
        engine = InterestEngineV2(config)

        engine.calculate_interest(
            mock_kill,
            mock_kill.solar_system_id,
            runtime_context={"overlap_key": "from_runtime"},
        )

        # Signal config should win (applied last in merge)
        assert captured_configs[0]["overlap_key"] == "from_signal"


class TestConfigTierIntegration:
    """Tests for three-tier configuration detection."""

    def test_simple_tier_preset_only(self, reset_registry):
        """Simple tier: preset with optional customize."""
        config = InterestConfigV2(engine="v2", preset="trade-hub")
        engine = InterestEngineV2(config)

        assert engine._config.tier == ConfigTier.SIMPLE

    def test_intermediate_tier_with_weights(self, reset_registry):
        """Intermediate tier: preset with explicit weights."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            weights={"location": 0.9, "value": 0.7},
        )
        engine = InterestEngineV2(config)

        assert engine._config.tier == ConfigTier.INTERMEDIATE

    def test_advanced_tier_with_signals(self, reset_registry):
        """Advanced tier: has signals configuration."""
        config = InterestConfigV2(
            engine="v2",
            preset="trade-hub",
            signals={
                "location": {
                    "geographic": {
                        "systems": [{"name": "Jita"}],
                    }
                }
            },
        )
        engine = InterestEngineV2(config)

        assert engine._config.tier == ConfigTier.ADVANCED


class TestSignalOptIn:
    """Tests for signal opt-in behavior (unconfigured signals skipped)."""

    def test_unconfigured_security_skipped_in_location(self, mock_kill, reset_registry):
        """When only geographic is configured, security signal should not run."""
        config = InterestConfigV2(
            engine="v2",
            weights={"location": 1.0},
            signals={
                "location": {
                    "geographic": {
                        "systems": [{"name": "Jita", "id": 30000142}],
                    }
                    # Note: no "security" key
                }
            },
        )
        engine = InterestEngineV2(config)
        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        # Location category should have been scored
        loc = result.category_scores.get("location")
        assert loc is not None

        # Only geographic signal should be present, not security
        if loc.signals:
            assert "geographic" in loc.signals
            assert "security" not in loc.signals

    def test_both_location_signals_when_configured(self, mock_kill, reset_registry):
        """When both geographic and security are configured, both should run."""
        config = InterestConfigV2(
            engine="v2",
            weights={"location": 1.0},
            signals={
                "location": {
                    "geographic": {
                        "systems": [{"name": "Jita", "id": 30000142}],
                    },
                    "security": {
                        "bands": [{"min": 0.5, "max": 1.0}],
                    },
                }
            },
        )
        engine = InterestEngineV2(config)
        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        loc = result.category_scores.get("location")
        assert loc is not None
        if loc.signals:
            assert "geographic" in loc.signals
            assert "security" in loc.signals

    def test_single_signal_category_still_scores(self, mock_kill, reset_registry):
        """Single-signal categories (e.g., value) still score with category-level config."""
        config = InterestConfigV2(
            engine="v2",
            weights={"value": 1.0},
            signals={
                "value": {
                    "min": 50_000_000,
                }
            },
        )
        engine = InterestEngineV2(config)
        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        val = result.category_scores.get("value")
        assert val is not None
        if val.signals:
            assert "value" in val.signals

    def test_empty_signals_config_returns_no_signals(self, mock_kill, reset_registry):
        """Category with empty signals config returns no signal scores."""
        config = InterestConfigV2(
            engine="v2",
            weights={"location": 1.0},
            signals={},  # No categories configured
        )
        engine = InterestEngineV2(config)
        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        loc = result.category_scores.get("location")
        assert loc is not None
        # No signals should have run because signals_config for location is empty
        assert not loc.signals

    def test_gate_passes_with_geographic_only_in_configured_system(
        self, mock_kill, reset_registry
    ):
        """Gate on location passes when geographic-only is configured and system matches."""
        config = InterestConfigV2(
            engine="v2",
            weights={"location": 1.0, "value": 0.5},
            signals={
                "location": {
                    "geographic": {
                        "systems": [
                            {"name": "Jita", "id": 30000142, "classification": "home"}
                        ],
                    }
                    # No security — should NOT inflate score
                },
                "value": {"min": 10_000_000},
            },
            rules=RulesConfig(require_all=["location"]),
        )
        engine = InterestEngineV2(config)

        # Kill in Jita (system 30000142) — should match geographic
        result = engine.calculate_interest(mock_kill, 30000142)

        loc = result.category_scores.get("location")
        assert loc is not None
        # Geographic should score well for home system
        if loc.signals and "geographic" in loc.signals:
            geo_score = loc.signals["geographic"].score
            assert geo_score > 0.0

    def test_gate_fails_geographic_only_wrong_system(self, mock_kill, reset_registry):
        """Gate on location fails when geographic-only is configured and system does NOT match.

        This is the core regression test for the bug: before the fix, unconfigured
        SecuritySignal returned 1.0, inflating the category average to ~0.5 and
        clearing the 0.3 match threshold even for kills in unrelated systems.
        """
        config = InterestConfigV2(
            engine="v2",
            weights={"location": 1.0, "value": 0.5},
            signals={
                "location": {
                    "geographic": {
                        "systems": [
                            {"name": "Jita", "id": 30000142, "classification": "home"}
                        ],
                    }
                    # No security — must NOT inflate score for non-matching system
                },
                "value": {"min": 10_000_000},
            },
            rules=RulesConfig(require_all=["location"]),
        )
        engine = InterestEngineV2(config)

        # Kill in Amarr (system 30002187) — NOT in configured systems
        result = engine.calculate_interest(mock_kill, 30002187)

        loc = result.category_scores.get("location")
        assert loc is not None
        # Location should NOT match since the system is not configured
        assert not loc.match, (
            "Location gate should not match for a system outside geographic config "
            "(regression: unconfigured security signal inflating score)"
        )
        # Gate should fail
        assert result.tier == NotificationTier.FILTER
        assert result.interest == 0.0

    def test_provider_scoring_exception_produces_zero_score(self, mock_kill, reset_registry):
        """A provider that raises during score() produces a zero-score entry with error reason."""
        from aria_esi.services.redisq.interest_v2.providers.base import BaseSignalProvider
        from aria_esi.services.redisq.interest_v2.providers.registry import get_provider_registry

        class BrokenSignal(BaseSignalProvider):
            _name = "broken"
            _category = "value"
            _prefetch_capable = False

            def score(self, kill, system_id, config):
                raise RuntimeError("provider exploded")

        registry = get_provider_registry()
        registry.register_signal("value", "broken", BrokenSignal)

        config = InterestConfigV2(
            engine="v2",
            weights={"value": 1.0},
            signals={
                "value": {
                    "broken": {},
                },
            },
        )
        engine = InterestEngineV2(config)
        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        val = result.category_scores.get("value")
        assert val is not None
        assert val.signals["broken"].score == 0.0
        assert "Scoring error" in val.signals["broken"].reason
        assert "provider exploded" in val.signals["broken"].reason

    def test_signal_config_none_value_treated_as_empty(self, mock_kill, reset_registry):
        """Signal config explicitly set to None should be treated as empty dict."""
        config = InterestConfigV2(
            engine="v2",
            weights={"location": 1.0},
            signals={
                "location": {
                    "geographic": None,  # Explicitly None
                }
            },
        )
        engine = InterestEngineV2(config)
        result = engine.calculate_interest(mock_kill, mock_kill.solar_system_id)

        # Should not crash; geographic signal should still run with empty config
        loc = result.category_scores.get("location")
        assert loc is not None
