"""
Tests for Interest Engine v2 models.
"""

import pytest

from aria_esi.services.redisq.interest_v2.models import (
    CANONICAL_CATEGORIES,
    AggregationMode,
    CategoryScore,
    ConfigTier,
    InterestResultV2,
    NotificationTier,
    RuleMatch,
    SignalScore,
    rms_safety_factor,
    validate_category,
)


class TestSignalScore:
    """Tests for SignalScore dataclass."""

    def test_basic_creation(self):
        score = SignalScore(signal="geographic", score=0.75, reason="Close to home")
        assert score.signal == "geographic"
        assert score.score == 0.75
        assert score.reason == "Close to home"
        assert score.weight == 1.0
        assert score.prefetch_capable is True

    def test_score_clamping(self):
        # Score above 1.0 should be clamped
        score = SignalScore(signal="test", score=1.5)
        assert score.score == 1.0

        # Score below 0.0 should be clamped
        score = SignalScore(signal="test", score=-0.5)
        assert score.score == 0.0

    def test_matches_property_explicit(self):
        # Explicit match
        score = SignalScore(signal="test", score=0.2, match=True)
        assert score.matches is True

        score = SignalScore(signal="test", score=0.8, match=False)
        assert score.matches is False

    def test_matches_property_derived(self):
        # Derived from score (threshold = 0.3)
        score = SignalScore(signal="test", score=0.5)
        assert score.matches is True

        score = SignalScore(signal="test", score=0.2)
        assert score.matches is False

        score = SignalScore(signal="test", score=0.3)  # Exactly at threshold
        assert score.matches is True

    def test_to_dict(self):
        score = SignalScore(
            signal="geographic",
            score=0.75,
            reason="Close",
            weight=0.8,
            raw_value=3,  # 3 hops
        )
        result = score.to_dict()
        assert result["signal"] == "geographic"
        assert result["score"] == 0.75
        assert result["weight"] == 0.8
        assert result["match"] is True
        assert result["reason"] == "Close"
        assert result["raw_value"] == 3


class TestCategoryScore:
    """Tests for CategoryScore dataclass."""

    def test_basic_creation(self):
        cat = CategoryScore(
            category="location",
            score=0.8,
            weight=0.7,
            match=True,
        )
        assert cat.category == "location"
        assert cat.score == 0.8
        assert cat.weight == 0.7
        assert cat.match is True
        assert cat.penalty_factor == 1.0

    def test_penalized_score(self):
        cat = CategoryScore(
            category="politics",
            score=0.8,
            weight=0.5,
            penalty_factor=0.5,
        )
        assert cat.penalized_score == 0.4

    def test_weighted_score(self):
        cat = CategoryScore(
            category="value",
            score=0.8,
            weight=0.6,
            penalty_factor=0.75,
        )
        # weighted = penalized * weight = (0.8 * 0.75) * 0.6 = 0.36
        assert cat.weighted_score == pytest.approx(0.36)

    def test_is_configured(self):
        cat = CategoryScore(category="location", score=0.5, weight=0.5)
        assert not cat.is_configured

        cat.signals["geographic"] = SignalScore(signal="geographic", score=0.5)
        assert cat.is_configured

    def test_is_enabled(self):
        cat = CategoryScore(category="location", score=0.5, weight=0.0)
        assert not cat.is_enabled

        cat = CategoryScore(category="location", score=0.5, weight=0.5)
        assert cat.is_enabled

    def test_prefetch_capable_all_signals(self):
        cat = CategoryScore(category="location", score=0.5, weight=0.5)
        cat.signals["geo"] = SignalScore(signal="geo", score=0.5, prefetch_capable=True)
        cat.signals["sec"] = SignalScore(signal="sec", score=0.6, prefetch_capable=True)
        assert cat.prefetch_capable is True

    def test_prefetch_capable_mixed_signals(self):
        cat = CategoryScore(category="activity", score=0.5, weight=0.5)
        cat.signals["gatecamp"] = SignalScore(signal="gatecamp", score=0.5, prefetch_capable=False)
        cat.signals["spike"] = SignalScore(signal="spike", score=0.6, prefetch_capable=True)
        assert cat.prefetch_capable is False  # One post-fetch = all post-fetch


class TestRuleMatch:
    """Tests for RuleMatch dataclass."""

    def test_basic_creation(self):
        match = RuleMatch(rule_id="corp_member_victim", matched=True, reason="Corp member died")
        assert match.rule_id == "corp_member_victim"
        assert match.matched is True
        assert match.reason == "Corp member died"
        assert match.prefetch_capable is True

    def test_to_dict(self):
        match = RuleMatch(
            rule_id="high_value",
            matched=True,
            reason="Value 5B >= threshold 1B",
            prefetch_capable=True,
        )
        result = match.to_dict()
        assert result["rule_id"] == "high_value"
        assert result["matched"] is True
        assert result["reason"] == "Value 5B >= threshold 1B"


class TestInterestResultV2:
    """Tests for InterestResultV2 dataclass."""

    def test_basic_creation(self):
        result = InterestResultV2(
            system_id=30000142,
            interest=0.75,
            tier=NotificationTier.NOTIFY,
        )
        assert result.system_id == 30000142
        assert result.interest == 0.75
        assert result.tier == NotificationTier.NOTIFY
        assert result.should_notify is True
        assert result.should_fetch is True

    def test_tier_properties(self):
        # Priority
        result = InterestResultV2(system_id=1, tier=NotificationTier.PRIORITY)
        assert result.is_priority is True
        assert result.should_notify is True

        # Digest
        result = InterestResultV2(system_id=1, tier=NotificationTier.DIGEST)
        assert result.is_digest is True
        assert result.should_notify is False
        assert result.should_fetch is True

        # Filter
        result = InterestResultV2(system_id=1, tier=NotificationTier.FILTER)
        assert result.should_fetch is False

    def test_bypassed_scoring(self):
        result = InterestResultV2(system_id=1)
        assert result.bypassed_scoring is False

        result.always_notify_matched = [
            RuleMatch(rule_id="corp_member_victim", matched=True)
        ]
        assert result.bypassed_scoring is True

    def test_was_ignored(self):
        result = InterestResultV2(system_id=1)
        assert result.was_ignored is False

        result.always_ignore_matched = [RuleMatch(rule_id="npc_only", matched=True)]
        assert result.was_ignored is True

    def test_dominant_category(self):
        result = InterestResultV2(system_id=1)
        result.category_scores = {
            "location": CategoryScore(category="location", score=0.8, weight=0.5),
            "value": CategoryScore(category="value", score=0.6, weight=0.5),
            "politics": CategoryScore(category="politics", score=0.9, weight=0),  # Disabled
        }
        # Politics has highest score but weight=0, so location wins
        assert result.dominant_category == "location"

    def test_explain(self):
        result = InterestResultV2(
            system_id=30000142,
            interest=0.75,
            tier=NotificationTier.NOTIFY,
            thresholds={"notify": 0.6},
        )
        result.category_scores = {
            "location": CategoryScore(category="location", score=0.8, weight=0.7, match=True),
        }
        result.category_scores["location"].signals["geographic"] = SignalScore(
            signal="geographic", score=0.8, reason="Home system"
        )

        explanation = result.explain()
        assert "30000142" in explanation
        assert "Location" in explanation
        assert "geographic" in explanation
        assert "NOTIFY" in explanation


class TestRMSSafetyFactor:
    """Tests for RMS safety factor calculation."""

    def test_single_category(self):
        assert rms_safety_factor(1) == 1.0

    def test_two_categories(self):
        # 1/sqrt(2) ≈ 0.707
        assert rms_safety_factor(2) == pytest.approx(0.707, rel=0.01)

    def test_three_categories(self):
        # 1/sqrt(3) ≈ 0.577
        assert rms_safety_factor(3) == pytest.approx(0.577, rel=0.01)

    def test_four_categories(self):
        # 1/sqrt(4) = 0.5
        assert rms_safety_factor(4) == 0.5

    def test_five_plus_categories(self):
        # Floor at 0.45
        assert rms_safety_factor(5) == pytest.approx(0.447, rel=0.01)
        assert rms_safety_factor(10) >= 0.45

    def test_zero_categories(self):
        # Edge case: 0 categories
        assert rms_safety_factor(0) == 1.0


class TestValidateCategory:
    """Tests for category validation."""

    def test_valid_categories(self):
        for cat in CANONICAL_CATEGORIES:
            assert validate_category(cat) is True

    def test_invalid_category(self):
        assert validate_category("invalid") is False
        assert validate_category("") is False
        assert validate_category("Location") is False  # Case sensitive


class TestEnums:
    """Tests for enum values."""

    def test_aggregation_mode(self):
        assert AggregationMode.WEIGHTED.value == "weighted"
        assert AggregationMode.LINEAR.value == "linear"
        assert AggregationMode.MAX.value == "max"

    def test_config_tier(self):
        assert ConfigTier.SIMPLE.value == "simple"
        assert ConfigTier.INTERMEDIATE.value == "intermediate"
        assert ConfigTier.ADVANCED.value == "advanced"

    def test_notification_tier(self):
        assert NotificationTier.FILTER.value == "filter"
        assert NotificationTier.LOG_ONLY.value == "log_only"
        assert NotificationTier.DIGEST.value == "digest"
        assert NotificationTier.NOTIFY.value == "notify"
        assert NotificationTier.PRIORITY.value == "priority"
