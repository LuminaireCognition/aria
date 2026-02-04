"""
Tests for Interest Engine v2 Explain Command.
"""

from __future__ import annotations

from aria_esi.services.redisq.interest_v2.cli.explain import (
    explain_kill,
    explain_prefetch,
    format_explanation,
)
from aria_esi.services.redisq.interest_v2.models import (
    AggregationMode,
    CategoryScore,
    ConfigTier,
    InterestResultV2,
    NotificationTier,
    RuleMatch,
    SignalScore,
)


def _make_basic_result(
    tier: NotificationTier = NotificationTier.NOTIFY,
    interest: float = 0.7,
) -> InterestResultV2:
    """Create a basic result for testing."""
    result = InterestResultV2(
        system_id=30000142,
        kill_id=12345678,
        mode=AggregationMode.WEIGHTED,
        config_tier=ConfigTier.INTERMEDIATE,
        preset="trade-hub",
        is_prefetch=False,
        thresholds={"priority": 0.85, "notify": 0.60, "digest": 0.40},
    )
    result.tier = tier
    result.interest = interest

    # Add some category scores
    loc = CategoryScore(category="location", score=0.8, weight=1.0, match=True)
    loc.signals = {"geographic": SignalScore(signal="geographic", score=0.8, prefetch_capable=True, reason="Near home")}

    val = CategoryScore(category="value", score=0.6, weight=0.7, match=True)
    val.signals = {"value": SignalScore(signal="value", score=0.6, prefetch_capable=True, raw_value=150000000)}

    result.category_scores = {"location": loc, "value": val}

    return result


class TestExplainKill:
    """Tests for explain_kill function."""

    def test_basic_explanation_includes_header(self):
        """Explanation includes header with kill/system info."""
        result = _make_basic_result()

        explanation = explain_kill(result)

        assert "12345678" in explanation  # kill_id
        assert "30000142" in explanation  # system_id

    def test_explanation_includes_tier(self):
        """Explanation includes final tier."""
        result = _make_basic_result(tier=NotificationTier.PRIORITY)

        explanation = explain_kill(result)

        assert "PRIORITY" in explanation

    def test_explanation_includes_mode(self):
        """Explanation includes aggregation mode."""
        result = _make_basic_result()

        explanation = explain_kill(result)

        assert "weighted" in explanation.lower()

    def test_explanation_includes_category_breakdown(self):
        """Explanation includes category scores."""
        result = _make_basic_result()

        explanation = explain_kill(result)

        assert "location" in explanation.lower()
        assert "value" in explanation.lower()

    def test_explanation_includes_thresholds(self):
        """Explanation includes threshold values."""
        result = _make_basic_result()

        explanation = explain_kill(result)

        assert "0.85" in explanation  # priority threshold
        assert "0.60" in explanation  # notify threshold

    def test_verbose_shows_raw_values(self):
        """Verbose mode shows raw signal values."""
        result = _make_basic_result()

        explanation = explain_kill(result, verbose=True)

        assert "150000000" in explanation  # raw_value from value signal


class TestExplainIgnored:
    """Tests for explaining ignored kills."""

    def test_ignored_kill_shows_reason(self):
        """Ignored kills show which rule matched."""
        result = _make_basic_result(tier=NotificationTier.FILTER, interest=0.0)
        result.always_ignore_matched = [
            RuleMatch(rule_id="pod_only", matched=True, reason="Pod kill detected")
        ]

        explanation = explain_kill(result)

        assert "IGNORED" in explanation
        assert "pod_only" in explanation
        assert "Pod kill" in explanation


class TestExplainAlwaysNotify:
    """Tests for explaining always_notify bypass."""

    def test_always_notify_bypass_shown(self):
        """always_notify bypass shows which rule matched."""
        result = _make_basic_result()
        result.always_notify_matched = [
            RuleMatch(rule_id="high_value", matched=True, reason="Kill value > 1B")
        ]

        explanation = explain_kill(result)

        assert "high_value" in explanation
        assert "1B" in explanation


class TestExplainGateFailure:
    """Tests for explaining gate failures."""

    def test_gate_failure_shows_reason(self):
        """Gate failures show which gate failed."""
        result = _make_basic_result(tier=NotificationTier.FILTER, interest=0.0)
        result.require_all_passed = False
        result.gate_failure_reason = "require_all: category 'politics' did not match"

        explanation = explain_kill(result)

        assert "GATE FAILED" in explanation
        assert "require_all" in explanation
        assert "politics" in explanation


class TestFormatExplanation:
    """Tests for structured JSON explanation."""

    def test_format_returns_dict(self):
        """format_explanation returns a dictionary."""
        result = _make_basic_result()

        formatted = format_explanation(result)

        assert isinstance(formatted, dict)

    def test_format_includes_basic_fields(self):
        """Formatted output includes basic fields."""
        result = _make_basic_result()

        formatted = format_explanation(result)

        assert formatted["system_id"] == 30000142
        assert formatted["kill_id"] == 12345678
        assert formatted["tier"] == "notify"
        assert formatted["interest"] == 0.7
        assert formatted["mode"] == "weighted"

    def test_format_includes_categories(self):
        """Formatted output includes category breakdown."""
        result = _make_basic_result()

        formatted = format_explanation(result)

        assert "categories" in formatted
        assert len(formatted["categories"]) == 2

        # Check category structure
        loc = next(c for c in formatted["categories"] if c["category"] == "location")
        assert loc["score"] == 0.8
        assert loc["weight"] == 1.0
        assert loc["match"] is True

    def test_format_includes_signals(self):
        """Formatted output includes signal details."""
        result = _make_basic_result()

        formatted = format_explanation(result)

        loc = next(c for c in formatted["categories"] if c["category"] == "location")
        assert "signals" in loc
        assert len(loc["signals"]) == 1

        geo = loc["signals"][0]
        assert geo["signal"] == "geographic"
        assert geo["score"] == 0.8

    def test_format_includes_thresholds(self):
        """Formatted output includes thresholds."""
        result = _make_basic_result()

        formatted = format_explanation(result)

        assert "thresholds" in formatted
        assert formatted["thresholds"]["priority"] == 0.85

    def test_format_ignored_kill(self):
        """Formatted output for ignored kills."""
        result = _make_basic_result(tier=NotificationTier.FILTER, interest=0.0)
        result.always_ignore_matched = [
            RuleMatch(rule_id="npc_only", matched=True)
        ]

        formatted = format_explanation(result)

        assert "ignored_by" in formatted
        assert "npc_only" in formatted["ignored_by"]

    def test_format_always_notify(self):
        """Formatted output for always_notify bypass."""
        result = _make_basic_result()
        result.always_notify_matched = [
            RuleMatch(rule_id="watchlist_match", matched=True)
        ]

        formatted = format_explanation(result)

        assert "always_notify" in formatted
        assert "watchlist_match" in formatted["always_notify"]

    def test_format_gate_failure(self):
        """Formatted output for gate failures."""
        result = _make_basic_result(tier=NotificationTier.FILTER, interest=0.0)
        result.require_all_passed = False
        result.require_any_passed = True
        result.gate_failure_reason = "Test failure"

        formatted = format_explanation(result)

        assert "gates" in formatted
        assert formatted["gates"]["require_all_passed"] is False
        assert formatted["gates"]["failure_reason"] == "Test failure"


class TestExplainPrefetch:
    """Tests for prefetch explanation."""

    def test_prefetch_explanation_includes_system(self):
        """Prefetch explanation includes system ID."""
        result = InterestResultV2(
            system_id=30000142,
            kill_id=None,
            mode=AggregationMode.WEIGHTED,
            config_tier=ConfigTier.SIMPLE,
            preset="trade-hub",
            is_prefetch=True,
            thresholds={},
        )

        explanation = explain_prefetch(result)

        assert "30000142" in explanation
        assert "Prefetch" in explanation

    def test_prefetch_with_decision(self):
        """Prefetch explanation includes decision details."""
        from aria_esi.services.redisq.interest_v2.prefetch import PrefetchDecision

        result = InterestResultV2(
            system_id=30000142,
            kill_id=None,
            mode=AggregationMode.WEIGHTED,
            config_tier=ConfigTier.SIMPLE,
            preset="trade-hub",
            is_prefetch=True,
            thresholds={},
        )

        decision = PrefetchDecision(
            should_fetch=True,
            prefetch_score=0.7,
            mode="strict",
            reason="Lower bound exceeds threshold",
            lower_bound=0.65,
            upper_bound=0.85,
            threshold_used=0.45,
            prefetch_capable_count=3,
            total_categories=5,
        )

        explanation = explain_prefetch(result, decision)

        assert "strict" in explanation
        assert "0.65" in explanation  # lower bound
        assert "0.85" in explanation  # upper bound
        assert "FETCH" in explanation

    def test_prefetch_drop_decision(self):
        """Prefetch explanation shows DROP decision."""
        from aria_esi.services.redisq.interest_v2.prefetch import PrefetchDecision

        result = InterestResultV2(
            system_id=30000142,
            kill_id=None,
            mode=AggregationMode.WEIGHTED,
            config_tier=ConfigTier.SIMPLE,
            preset="trade-hub",
            is_prefetch=True,
            thresholds={},
        )

        decision = PrefetchDecision(
            should_fetch=False,
            prefetch_score=0.2,
            mode="strict",
            reason="Upper bound below threshold",
            lower_bound=0.1,
            upper_bound=0.3,
            threshold_used=0.45,
            prefetch_capable_count=3,
            total_categories=5,
        )

        explanation = explain_prefetch(result, decision)

        assert "DROP" in explanation
        assert "below threshold" in explanation.lower()
