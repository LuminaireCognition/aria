"""
Tests for commentary warrant checker.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from aria_esi.services.redisq.models import ProcessedKill
from aria_esi.services.redisq.notifications.patterns import DetectedPattern, PatternContext
from aria_esi.services.redisq.notifications.warrant import (
    DEFAULT_THRESHOLD_OPPORTUNISTIC,
    DEFAULT_THRESHOLD_SKIP,
    DEFAULT_TIMEOUT_GENERATE_MS,
    DEFAULT_TIMEOUT_OPPORTUNISTIC_MS,
    CommentaryDecision,
    WarrantChecker,
)


class TestCommentaryDecision:
    """Tests for CommentaryDecision dataclass."""

    def test_to_dict(self):
        """Test serialization to dict."""
        decision = CommentaryDecision(
            action="generate",
            reason="High-value patterns detected",
            timeout_ms=3000,
            warrant_score=0.7,
        )

        result = decision.to_dict()

        assert result["action"] == "generate"
        assert result["reason"] == "High-value patterns detected"
        assert result["timeout_ms"] == 3000
        assert result["warrant_score"] == 0.7


class TestWarrantChecker:
    """Tests for WarrantChecker class."""

    @pytest.fixture
    def sample_kill(self):
        """Create sample ProcessedKill."""
        return ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now() - timedelta(minutes=2),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=99000001,
            attacker_count=8,
            attacker_corps=[98000002],
            attacker_alliances=[99000002],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )

    @pytest.fixture
    def checker(self):
        """Create default WarrantChecker."""
        return WarrantChecker()

    def test_default_thresholds(self, checker):
        """Test default threshold values."""
        assert checker.threshold_skip == DEFAULT_THRESHOLD_SKIP
        assert checker.threshold_opportunistic == DEFAULT_THRESHOLD_OPPORTUNISTIC
        assert checker.timeout_opportunistic_ms == DEFAULT_TIMEOUT_OPPORTUNISTIC_MS
        assert checker.timeout_generate_ms == DEFAULT_TIMEOUT_GENERATE_MS

    def test_skip_below_threshold(self, checker, sample_kill):
        """Test skip decision when below threshold."""
        # No patterns = 0.0 warrant score
        context = PatternContext(
            kill=sample_kill,
            patterns=[],
        )

        decision = checker.should_generate_commentary(context)

        assert decision.action == "skip"
        assert decision.timeout_ms == 0
        assert decision.warrant_score == 0.0

    def test_skip_with_low_score(self, checker, sample_kill):
        """Test skip decision with pattern below threshold."""
        # Single pattern with weight 0.2 (below default 0.3 threshold)
        context = PatternContext(
            kill=sample_kill,
            patterns=[
                DetectedPattern(
                    pattern_type="low_pattern",
                    description="Test",
                    weight=0.2,
                )
            ],
        )

        decision = checker.should_generate_commentary(context)

        assert decision.action == "skip"
        assert "below skip threshold" in decision.reason

    def test_opportunistic_between_thresholds(self, checker, sample_kill):
        """Test opportunistic decision when between thresholds."""
        # Pattern with weight 0.4 (between 0.3 skip and 0.5 opportunistic)
        context = PatternContext(
            kill=sample_kill,
            patterns=[
                DetectedPattern(
                    pattern_type="repeat_attacker",
                    description="Same attackers with 4 kills",
                    weight=0.4,
                )
            ],
        )

        decision = checker.should_generate_commentary(context)

        assert decision.action == "opportunistic"
        assert decision.timeout_ms == DEFAULT_TIMEOUT_OPPORTUNISTIC_MS
        assert decision.warrant_score == 0.4
        assert "opportunistic" in decision.reason.lower()

    def test_generate_above_threshold(self, checker, sample_kill):
        """Test generate decision when above opportunistic threshold."""
        # Patterns totaling 0.7 (above 0.5 threshold)
        context = PatternContext(
            kill=sample_kill,
            patterns=[
                DetectedPattern(
                    pattern_type="gank_rotation",
                    description="Gank rotation detected",
                    weight=0.5,
                ),
                DetectedPattern(
                    pattern_type="unusual_victim",
                    description="High value loss",
                    weight=0.3,
                ),
            ],
        )

        decision = checker.should_generate_commentary(context)

        assert decision.action == "generate"
        assert decision.timeout_ms == DEFAULT_TIMEOUT_GENERATE_MS
        assert decision.warrant_score == 0.8

    def test_custom_thresholds(self, sample_kill):
        """Test with custom threshold values."""
        checker = WarrantChecker(
            threshold_skip=0.1,
            threshold_opportunistic=0.3,
            timeout_opportunistic_ms=1000,
            timeout_generate_ms=5000,
        )

        # Pattern at 0.2 should now be opportunistic (not skip)
        context = PatternContext(
            kill=sample_kill,
            patterns=[
                DetectedPattern(
                    pattern_type="low_pattern",
                    description="Test",
                    weight=0.2,
                )
            ],
        )

        decision = checker.should_generate_commentary(context)

        assert decision.action == "opportunistic"
        assert decision.timeout_ms == 1000

    def test_from_config(self, sample_kill):
        """Test creation from config dict."""
        config = {
            "threshold_skip": 0.2,
            "threshold_opportunistic": 0.6,
            "timeout_opportunistic_ms": 2000,
            "timeout_generate_ms": 4000,
        }

        checker = WarrantChecker.from_config(config)

        assert checker.threshold_skip == 0.2
        assert checker.threshold_opportunistic == 0.6
        assert checker.timeout_opportunistic_ms == 2000
        assert checker.timeout_generate_ms == 4000

    def test_from_config_defaults(self):
        """Test from_config with empty dict uses defaults."""
        checker = WarrantChecker.from_config({})

        assert checker.threshold_skip == DEFAULT_THRESHOLD_SKIP
        assert checker.threshold_opportunistic == DEFAULT_THRESHOLD_OPPORTUNISTIC

    def test_pattern_names_in_reason(self, checker, sample_kill):
        """Test that pattern names are included in decision reason."""
        context = PatternContext(
            kill=sample_kill,
            patterns=[
                DetectedPattern(
                    pattern_type="gank_rotation",
                    description="Test",
                    weight=0.5,
                ),
                DetectedPattern(
                    pattern_type="repeat_attacker",
                    description="Test",
                    weight=0.4,
                ),
            ],
        )

        decision = checker.should_generate_commentary(context)

        assert "gank_rotation" in decision.reason
        assert "repeat_attacker" in decision.reason


class TestWarrantScoreEdgeCases:
    """Tests for edge cases in warrant scoring."""

    @pytest.fixture
    def sample_kill(self):
        """Create sample ProcessedKill."""
        return ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now() - timedelta(minutes=2),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=99000001,
            attacker_count=8,
            attacker_corps=[98000002],
            attacker_alliances=[99000002],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )

    def test_exactly_at_skip_threshold(self, sample_kill):
        """Test behavior exactly at skip threshold."""
        checker = WarrantChecker(threshold_skip=0.3)

        context = PatternContext(
            kill=sample_kill,
            patterns=[
                DetectedPattern(pattern_type="test", description="Test", weight=0.3),
            ],
        )

        decision = checker.should_generate_commentary(context)

        # At threshold should be opportunistic, not skip
        assert decision.action == "opportunistic"

    def test_exactly_at_opportunistic_threshold(self, sample_kill):
        """Test behavior exactly at opportunistic threshold."""
        checker = WarrantChecker(threshold_opportunistic=0.5)

        context = PatternContext(
            kill=sample_kill,
            patterns=[
                DetectedPattern(pattern_type="test", description="Test", weight=0.5),
            ],
        )

        decision = checker.should_generate_commentary(context)

        # At threshold should be generate
        assert decision.action == "generate"
