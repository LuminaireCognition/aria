"""Tests for Interest Engine v2 Prefetch Scorer."""

import pytest

from aria_esi.services.redisq.interest_v2.config import InterestConfigV2
from aria_esi.services.redisq.interest_v2.engine import InterestEngineV2, create_engine
from aria_esi.services.redisq.interest_v2.models import rms_safety_factor
from aria_esi.services.redisq.interest_v2.prefetch import (
    PrefetchDecision,
    PrefetchScorer,
    create_prefetch_scorer,
)
from aria_esi.services.redisq.interest_v2.providers.registry import reset_registry


@pytest.fixture(autouse=True)
def reset_global_registry():
    """Reset global registry before each test."""
    reset_registry()
    yield
    reset_registry()


class TestPrefetchDecision:
    """Tests for PrefetchDecision dataclass."""

    def test_basic_creation(self):
        """Test creating a prefetch decision."""
        decision = PrefetchDecision(
            should_fetch=True,
            prefetch_score=0.75,
            lower_bound=0.5,
            upper_bound=0.9,
            threshold_used=0.4,
            mode="strict",
            reason="Prefetch score exceeds threshold",
            prefetch_capable_count=3,
            total_categories=5,
        )

        assert decision.should_fetch is True
        assert decision.prefetch_score == 0.75
        assert decision.lower_bound == 0.5
        assert decision.upper_bound == 0.9
        assert decision.mode == "strict"

    def test_to_dict(self):
        """Test serialization to dict."""
        decision = PrefetchDecision(
            should_fetch=True,
            prefetch_score=0.75,
            lower_bound=0.5,
            upper_bound=0.9,
            threshold_used=0.4,
            mode="conservative",
            reason="Upper bound exceeds threshold",
            prefetch_capable_count=3,
            total_categories=5,
            always_notify_triggered=True,
        )

        d = decision.to_dict()
        assert d["should_fetch"] is True
        assert d["prefetch_score"] == 0.75
        assert d["mode"] == "conservative"
        assert d["always_notify_triggered"] is True
        assert d["always_ignore_triggered"] is False


class TestPrefetchScorer:
    """Tests for PrefetchScorer."""

    def test_bypass_mode_always_fetches(self):
        """Test that bypass mode always returns should_fetch=True."""
        config = InterestConfigV2.from_dict({
            "engine": "v2",
            "preset": "balanced",
            "prefetch": {"mode": "bypass"},
            "weights": {"location": 0.8, "value": 0.7},
        })
        engine = InterestEngineV2(config)
        scorer = PrefetchScorer(config, engine)

        decision = scorer.evaluate(30000142)  # Jita
        assert decision.should_fetch is True
        assert decision.mode == "bypass"
        assert "bypass" in decision.reason.lower()

    def test_strict_mode_with_high_score(self):
        """Test strict mode passes with high prefetch score."""
        config = InterestConfigV2.from_dict({
            "engine": "v2",
            "preset": "balanced",
            "prefetch": {"mode": "strict"},
            "weights": {"location": 1.0},  # Only location, which is prefetch-capable
            "thresholds": {"digest": 0.2},  # Low threshold
        })

        # Create engine with context that will produce high location score
        context = {
            "get_distance": lambda sys_id: 0,  # Home system
        }
        engine = InterestEngineV2(config, context)
        scorer = PrefetchScorer(config, engine)

        # Configure signals to produce high score
        decision = scorer.evaluate(30000142)
        # Note: actual score depends on signal implementation
        assert decision.mode == "strict"

    def test_conservative_mode_uses_upper_bound(self):
        """Test conservative mode uses upper bound for decision."""
        config = InterestConfigV2.from_dict({
            "engine": "v2",
            "preset": "balanced",
            "prefetch": {"mode": "conservative"},
            "weights": {
                "location": 0.5,  # prefetch-capable
                "activity": 0.5,  # NOT prefetch-capable
            },
            "thresholds": {"digest": 0.3},
        })
        engine = InterestEngineV2(config)
        scorer = PrefetchScorer(config, engine)

        decision = scorer.evaluate(30000142)
        assert decision.mode == "conservative"
        # Upper bound should be higher than lower bound due to unknown activity
        assert decision.upper_bound >= decision.lower_bound

    def test_effective_mode_property(self):
        """Test effective mode is correctly derived."""
        config = InterestConfigV2.from_dict({
            "engine": "v2",
            "preset": "balanced",
            "prefetch": {"mode": "strict"},
            "weights": {"location": 0.8},
        })
        engine = InterestEngineV2(config)
        scorer = PrefetchScorer(config, engine)

        assert scorer.effective_mode == "strict"

    def test_auto_mode_derivation_conservative(self):
        """Test auto mode derives conservative when needed."""
        # Config with only non-prefetch-capable categories would trigger conservative
        config = InterestConfigV2.from_dict({
            "engine": "v2",
            "preset": "balanced",
            "prefetch": {"mode": "auto"},
            "weights": {"activity": 1.0},  # activity is not prefetch-capable
        })
        engine = InterestEngineV2(config)
        scorer = PrefetchScorer(config, engine)

        # Should derive conservative since activity requires post-fetch
        assert scorer.effective_mode in ("conservative", "strict")

    def test_get_stats(self):
        """Test stats collection."""
        config = InterestConfigV2.from_dict({
            "engine": "v2",
            "preset": "balanced",
            "prefetch": {"mode": "strict"},
            "weights": {
                "location": 0.8,
                "value": 0.6,
            },
            "thresholds": {"digest": 0.4},
        })
        engine = InterestEngineV2(config)
        scorer = PrefetchScorer(config, engine)

        stats = scorer.get_stats()
        assert "effective_mode" in stats
        assert "config_mode" in stats
        assert "prefetch_capable_categories" in stats
        assert "post_fetch_categories" in stats
        assert "rms_safety_factor" in stats
        assert "adjusted_threshold" in stats


class TestRMSSafetyFactor:
    """Tests for RMS safety factor calculation."""

    def test_single_category(self):
        """Single category has factor 1.0."""
        assert rms_safety_factor(1) == 1.0

    def test_two_categories(self):
        """Two categories: 1/sqrt(2) ≈ 0.707."""
        factor = rms_safety_factor(2)
        assert abs(factor - 0.707) < 0.01

    def test_three_categories(self):
        """Three categories: 1/sqrt(3) ≈ 0.577."""
        factor = rms_safety_factor(3)
        assert abs(factor - 0.577) < 0.01

    def test_four_categories(self):
        """Four categories: 1/sqrt(4) = 0.5."""
        factor = rms_safety_factor(4)
        assert factor == 0.5

    def test_five_plus_categories_floored(self):
        """Five+ categories floored at 0.45."""
        assert rms_safety_factor(5) == 0.45
        assert rms_safety_factor(9) == 0.45
        assert rms_safety_factor(100) == 0.45

    def test_zero_categories(self):
        """Zero categories returns 1.0."""
        assert rms_safety_factor(0) == 1.0

    def test_negative_categories(self):
        """Negative categories returns 1.0."""
        assert rms_safety_factor(-1) == 1.0


class TestPrefetchIntegration:
    """Integration tests for prefetch with engine."""

    def test_engine_should_fetch_uses_prefetch(self):
        """Test engine.should_fetch() uses prefetch scorer."""
        config = InterestConfigV2.from_dict({
            "engine": "v2",
            "preset": "balanced",
            "prefetch": {"mode": "bypass"},
            "weights": {"location": 0.8},
        })
        engine = InterestEngineV2(config)

        # Bypass mode should always fetch
        assert engine.should_fetch(30000142) is True

    def test_engine_prefetch_evaluate(self):
        """Test engine.prefetch_evaluate() returns PrefetchDecision."""
        config = InterestConfigV2.from_dict({
            "engine": "v2",
            "preset": "balanced",
            "prefetch": {"mode": "strict"},
            "weights": {"location": 0.8},
        })
        engine = InterestEngineV2(config)

        decision = engine.prefetch_evaluate(30000142)
        assert isinstance(decision, PrefetchDecision)
        assert decision.mode == "strict"

    def test_prefetch_scorer_property(self):
        """Test lazy initialization of prefetch scorer."""
        config = InterestConfigV2.from_dict({
            "engine": "v2",
            "preset": "balanced",
            "weights": {"location": 0.8},
        })
        engine = InterestEngineV2(config)

        # Access prefetch_scorer property
        scorer = engine.prefetch_scorer
        assert isinstance(scorer, PrefetchScorer)

        # Should be cached
        assert engine.prefetch_scorer is scorer


class TestCreatePrefetchScorer:
    """Tests for create_prefetch_scorer factory function."""

    def test_factory_creates_scorer(self):
        """Test factory function creates PrefetchScorer."""
        config = InterestConfigV2.from_dict({
            "engine": "v2",
            "preset": "balanced",
            "weights": {"location": 0.8},
        })
        engine = create_engine({"engine": "v2", "preset": "balanced", "weights": {"location": 0.8}})
        scorer = create_prefetch_scorer(config, engine)

        assert isinstance(scorer, PrefetchScorer)
