"""
Tests for Interest Calculation Models.

Tests data classes and helper functions for interest scoring.
"""

from __future__ import annotations

import time

import pytest


# =============================================================================
# Interest Tier Tests
# =============================================================================


class TestGetTier:
    """Test get_tier function."""

    def test_filter_tier(self):
        """Score at or below 0.0 is 'filter'."""
        from aria_esi.services.redisq.interest.models import get_tier

        assert get_tier(0.0) == "filter"
        assert get_tier(-0.5) == "filter"

    def test_log_only_tier(self):
        """Score between 0.0 and 0.3 is 'log_only'."""
        from aria_esi.services.redisq.interest.models import get_tier

        assert get_tier(0.1) == "log_only"
        assert get_tier(0.29) == "log_only"

    def test_digest_tier(self):
        """Score between 0.3 and 0.6 is 'digest'."""
        from aria_esi.services.redisq.interest.models import get_tier

        assert get_tier(0.3) == "digest"
        assert get_tier(0.5) == "digest"
        assert get_tier(0.59) == "digest"

    def test_standard_tier(self):
        """Score between 0.6 and 0.8 is 'standard'."""
        from aria_esi.services.redisq.interest.models import get_tier

        assert get_tier(0.6) == "standard"
        assert get_tier(0.7) == "standard"
        assert get_tier(0.79) == "standard"

    def test_priority_tier(self):
        """Score at or above 0.8 is 'priority'."""
        from aria_esi.services.redisq.interest.models import get_tier

        assert get_tier(0.8) == "priority"
        assert get_tier(1.0) == "priority"
        assert get_tier(1.5) == "priority"


# =============================================================================
# LayerScore Tests
# =============================================================================


class TestLayerScore:
    """Test LayerScore dataclass."""

    def test_basic_creation(self):
        """Create LayerScore with required fields."""
        from aria_esi.services.redisq.interest.models import LayerScore

        score = LayerScore(layer="geographic", score=0.7)

        assert score.layer == "geographic"
        assert score.score == 0.7
        assert score.reason is None

    def test_with_reason(self):
        """Create LayerScore with reason."""
        from aria_esi.services.redisq.interest.models import LayerScore

        score = LayerScore(layer="entity", score=1.0, reason="Corp member loss")

        assert score.reason == "Corp member loss"

    def test_repr_with_reason(self):
        """Repr includes reason when present."""
        from aria_esi.services.redisq.interest.models import LayerScore

        score = LayerScore(layer="entity", score=1.0, reason="Corp member loss")
        result = repr(score)

        assert "entity" in result
        assert "1.00" in result
        assert "Corp member loss" in result

    def test_repr_without_reason(self):
        """Repr works without reason."""
        from aria_esi.services.redisq.interest.models import LayerScore

        score = LayerScore(layer="geographic", score=0.5)
        result = repr(score)

        assert "geographic" in result
        assert "0.50" in result


# =============================================================================
# PatternEscalation Tests
# =============================================================================


class TestPatternEscalation:
    """Test PatternEscalation dataclass."""

    def test_default_values(self):
        """Default multiplier is 1.0."""
        from aria_esi.services.redisq.interest.models import PatternEscalation

        esc = PatternEscalation()

        assert esc.multiplier == 1.0
        assert esc.reason is None
        assert esc.expires_at is None

    def test_is_expired_no_expiry(self):
        """Non-expiring escalation never expires."""
        from aria_esi.services.redisq.interest.models import PatternEscalation

        esc = PatternEscalation(multiplier=2.0)

        assert esc.is_expired() is False
        assert esc.is_expired(time.time() + 1000000) is False

    def test_is_expired_future_expiry(self):
        """Future expiry is not expired."""
        from aria_esi.services.redisq.interest.models import PatternEscalation

        future_time = time.time() + 3600
        esc = PatternEscalation(multiplier=2.0, expires_at=future_time)

        assert esc.is_expired() is False

    def test_is_expired_past_expiry(self):
        """Past expiry is expired."""
        from aria_esi.services.redisq.interest.models import PatternEscalation

        past_time = time.time() - 3600
        esc = PatternEscalation(multiplier=2.0, expires_at=past_time)

        assert esc.is_expired() is True

    def test_is_expired_with_explicit_now(self):
        """Test is_expired with explicit now parameter."""
        from aria_esi.services.redisq.interest.models import PatternEscalation

        esc = PatternEscalation(multiplier=2.0, expires_at=1000.0)

        assert esc.is_expired(now=500.0) is False
        assert esc.is_expired(now=1500.0) is True

    def test_repr_with_reason(self):
        """Repr includes reason when present."""
        from aria_esi.services.redisq.interest.models import PatternEscalation

        esc = PatternEscalation(multiplier=2.0, reason="Gatecamp detected")
        result = repr(esc)

        assert "2" in result
        assert "Gatecamp detected" in result

    def test_repr_without_reason(self):
        """Repr works without reason."""
        from aria_esi.services.redisq.interest.models import PatternEscalation

        esc = PatternEscalation(multiplier=1.5)
        result = repr(esc)

        assert "1.5" in result


# =============================================================================
# InterestScore Tests
# =============================================================================


class TestInterestScore:
    """Test InterestScore dataclass."""

    def test_basic_creation(self):
        """Create InterestScore with required fields."""
        from aria_esi.services.redisq.interest.models import InterestScore

        score = InterestScore(
            system_id=30000142,
            interest=0.7,
            base_interest=0.7,
            dominant_layer="geographic",
        )

        assert score.system_id == 30000142
        assert score.interest == 0.7
        assert score.tier == "standard"

    def test_tier_property(self):
        """Tier property returns correct tier."""
        from aria_esi.services.redisq.interest.models import InterestScore

        score = InterestScore(
            system_id=30000142,
            interest=0.9,
            base_interest=0.9,
            dominant_layer="entity",
        )

        assert score.tier == "priority"

    def test_should_fetch(self):
        """should_fetch is True when tier is not filter."""
        from aria_esi.services.redisq.interest.models import InterestScore

        # Filter tier - should not fetch
        low = InterestScore(
            system_id=1,
            interest=0.0,
            base_interest=0.0,
            dominant_layer="geographic",
        )
        assert low.should_fetch is False

        # Higher tier - should fetch
        high = InterestScore(
            system_id=1,
            interest=0.5,
            base_interest=0.5,
            dominant_layer="geographic",
        )
        assert high.should_fetch is True

    def test_should_notify(self):
        """should_notify is True for standard and priority tiers."""
        from aria_esi.services.redisq.interest.models import InterestScore

        # Digest tier - should not notify
        digest = InterestScore(
            system_id=1,
            interest=0.5,
            base_interest=0.5,
            dominant_layer="geographic",
        )
        assert digest.should_notify is False

        # Standard tier - should notify
        standard = InterestScore(
            system_id=1,
            interest=0.7,
            base_interest=0.7,
            dominant_layer="geographic",
        )
        assert standard.should_notify is True

    def test_is_priority(self):
        """is_priority is True for priority tier."""
        from aria_esi.services.redisq.interest.models import InterestScore

        priority = InterestScore(
            system_id=1,
            interest=0.9,
            base_interest=0.9,
            dominant_layer="entity",
        )
        assert priority.is_priority is True

    def test_is_digest(self):
        """is_digest is True for digest tier."""
        from aria_esi.services.redisq.interest.models import InterestScore

        digest = InterestScore(
            system_id=1,
            interest=0.5,
            base_interest=0.5,
            dominant_layer="geographic",
        )
        assert digest.is_digest is True

    def test_dominant_reason(self):
        """dominant_reason returns reason from dominant layer."""
        from aria_esi.services.redisq.interest.models import (
            InterestScore,
            LayerScore,
        )

        score = InterestScore(
            system_id=30000142,
            interest=1.0,
            base_interest=1.0,
            dominant_layer="entity",
            layer_scores={
                "geographic": LayerScore(layer="geographic", score=0.5),
                "entity": LayerScore(
                    layer="entity", score=1.0, reason="Corp member loss"
                ),
            },
        )

        assert score.dominant_reason == "Corp member loss"

    def test_dominant_reason_missing_layer(self):
        """dominant_reason returns None when layer not in scores."""
        from aria_esi.services.redisq.interest.models import InterestScore

        score = InterestScore(
            system_id=1,
            interest=0.5,
            base_interest=0.5,
            dominant_layer="missing",
            layer_scores={},
        )

        assert score.dominant_reason is None

    def test_get_layer_breakdown(self):
        """get_layer_breakdown returns sorted list."""
        from aria_esi.services.redisq.interest.models import (
            InterestScore,
            LayerScore,
        )

        score = InterestScore(
            system_id=1,
            interest=0.8,
            base_interest=0.8,
            dominant_layer="entity",
            layer_scores={
                "geographic": LayerScore(layer="geographic", score=0.3),
                "entity": LayerScore(layer="entity", score=0.8, reason="Corp loss"),
                "route": LayerScore(layer="route", score=0.5),
            },
        )

        breakdown = score.get_layer_breakdown()

        assert len(breakdown) == 3
        # Sorted by score descending
        assert breakdown[0][0] == "entity"
        assert breakdown[0][1] == 0.8
        assert breakdown[1][0] == "route"
        assert breakdown[2][0] == "geographic"

    def test_to_dict(self):
        """to_dict returns JSON-serializable dict."""
        from aria_esi.services.redisq.interest.models import (
            InterestScore,
            LayerScore,
        )

        score = InterestScore(
            system_id=30000142,
            interest=0.75,
            base_interest=0.75,
            dominant_layer="geographic",
            layer_scores={
                "geographic": LayerScore(layer="geographic", score=0.75, reason="Home"),
            },
        )

        result = score.to_dict()

        assert result["system_id"] == 30000142
        assert result["interest"] == 0.75
        assert result["dominant_layer"] == "geographic"
        assert result["tier"] == "standard"
        assert "geographic" in result["layer_scores"]

    def test_to_dict_with_escalation(self):
        """to_dict includes escalation when present."""
        from aria_esi.services.redisq.interest.models import (
            InterestScore,
            PatternEscalation,
        )

        score = InterestScore(
            system_id=30000142,
            interest=1.0,
            base_interest=0.5,
            dominant_layer="geographic",
            escalation=PatternEscalation(multiplier=2.0, reason="Gatecamp"),
        )

        result = score.to_dict()

        assert "escalation" in result
        assert result["escalation"]["multiplier"] == 2.0
        assert result["escalation"]["reason"] == "Gatecamp"

    def test_repr(self):
        """Repr includes key information."""
        from aria_esi.services.redisq.interest.models import InterestScore

        score = InterestScore(
            system_id=30000142,
            interest=0.7,
            base_interest=0.7,
            dominant_layer="geographic",
        )
        result = repr(score)

        assert "30000142" in result
        assert "0.70" in result
        assert "standard" in result
        assert "geographic" in result
