"""
Tests for pattern detection in Discord notifications.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from aria_esi.services.redisq.models import ProcessedKill
from aria_esi.services.redisq.notifications.patterns import (
    KNOWN_GANK_CORPS,
    PATTERN_WEIGHTS,
    DetectedPattern,
    PatternContext,
    PatternDetector,
)


class TestDetectedPattern:
    """Tests for DetectedPattern dataclass."""

    def test_to_dict(self):
        """Test serialization to dict."""
        pattern = DetectedPattern(
            pattern_type="repeat_attacker",
            description="Same attackers with 5 kills",
            weight=0.4,
            context={"kills_count": 5},
        )

        result = pattern.to_dict()

        assert result["pattern_type"] == "repeat_attacker"
        assert result["description"] == "Same attackers with 5 kills"
        assert result["weight"] == 0.4
        assert result["context"]["kills_count"] == 5


class TestPatternContext:
    """Tests for PatternContext dataclass."""

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

    def test_warrant_score_empty(self, sample_kill):
        """Test warrant score with no patterns."""
        context = PatternContext(
            kill=sample_kill,
            patterns=[],
        )

        assert context.warrant_score() == 0.0
        assert not context.has_patterns

    def test_warrant_score_single_pattern(self, sample_kill):
        """Test warrant score with single pattern."""
        context = PatternContext(
            kill=sample_kill,
            patterns=[
                DetectedPattern(
                    pattern_type="repeat_attacker",
                    description="Test",
                    weight=0.4,
                )
            ],
        )

        assert context.warrant_score() == 0.4
        assert context.has_patterns

    def test_warrant_score_multiple_patterns(self, sample_kill):
        """Test warrant score with multiple patterns."""
        context = PatternContext(
            kill=sample_kill,
            patterns=[
                DetectedPattern(pattern_type="repeat_attacker", description="Test", weight=0.4),
                DetectedPattern(pattern_type="unusual_victim", description="Test", weight=0.3),
            ],
        )

        assert context.warrant_score() == 0.7
        assert context.has_patterns

    def test_warrant_score_capped_at_one(self, sample_kill):
        """Test warrant score is capped at 1.0."""
        context = PatternContext(
            kill=sample_kill,
            patterns=[
                DetectedPattern(pattern_type="gank_rotation", description="Test", weight=0.5),
                DetectedPattern(pattern_type="war_target_activity", description="Test", weight=0.5),
                DetectedPattern(pattern_type="unusual_victim", description="Test", weight=0.3),
            ],
        )

        assert context.warrant_score() == 1.0

    def test_get_pattern_descriptions(self, sample_kill):
        """Test getting pattern descriptions."""
        context = PatternContext(
            kill=sample_kill,
            patterns=[
                DetectedPattern(pattern_type="repeat_attacker", description="Desc 1", weight=0.4),
                DetectedPattern(pattern_type="unusual_victim", description="Desc 2", weight=0.3),
            ],
        )

        descriptions = context.get_pattern_descriptions()
        assert descriptions == ["Desc 1", "Desc 2"]

    def test_to_dict(self, sample_kill):
        """Test serialization to dict."""
        context = PatternContext(
            kill=sample_kill,
            patterns=[
                DetectedPattern(pattern_type="repeat_attacker", description="Test", weight=0.4),
            ],
            same_attacker_kills_1h=3,
            same_system_kills_1h=5,
            is_watched_entity=True,
            watched_entity_kills_1h=2,
        )

        result = context.to_dict()

        assert result["kill_id"] == 12345678
        assert len(result["patterns"]) == 1
        assert result["same_attacker_kills_1h"] == 3
        assert result["same_system_kills_1h"] == 5
        assert result["is_watched_entity"] is True
        assert result["watched_entity_kills_1h"] == 2
        assert result["warrant_score"] == 0.4


class TestPatternDetector:
    """Tests for PatternDetector class."""

    @pytest.fixture
    def mock_threat_cache(self):
        """Create mock ThreatCache."""
        cache = MagicMock()
        cache.get_recent_kills.return_value = []
        cache._get_db.return_value.get_watched_entity_kills.return_value = []
        return cache

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
    def high_value_kill(self):
        """Create high value ProcessedKill."""
        return ProcessedKill(
            kill_id=12345679,
            kill_time=datetime.now() - timedelta(minutes=1),
            solar_system_id=30002813,
            victim_ship_type_id=42246,  # Titan
            victim_corporation_id=98000001,
            victim_alliance_id=99000001,
            attacker_count=50,
            attacker_corps=[98000002],
            attacker_alliances=[99000002],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=85_000_000_000,  # 85B ISK
            is_pod_kill=False,
        )

    @pytest.mark.asyncio
    async def test_detect_no_patterns(self, mock_threat_cache, sample_kill):
        """Test detection with no patterns."""
        detector = PatternDetector(mock_threat_cache)

        result = await detector.detect_patterns(sample_kill)

        assert result.kill == sample_kill
        assert len(result.patterns) == 0
        assert result.warrant_score() == 0.0

    @pytest.mark.asyncio
    async def test_detect_repeat_attacker(self, mock_threat_cache, sample_kill):
        """Test repeat attacker pattern detection."""
        # Create prior kills from same attacker corp
        prior_kills = [
            ProcessedKill(
                kill_id=12345670 + i,
                kill_time=datetime.now() - timedelta(minutes=10 + i),
                solar_system_id=30002813,
                victim_ship_type_id=17740,
                victim_corporation_id=98000003,
                victim_alliance_id=None,
                attacker_count=5,
                attacker_corps=[98000002],  # Same attacker corp
                attacker_alliances=[],
                attacker_ship_types=[11993],
                final_blow_ship_type_id=11993,
                total_value=100_000_000,
                is_pod_kill=False,
            )
            for i in range(3)  # 3 prior kills
        ]
        mock_threat_cache.get_recent_kills.return_value = prior_kills

        detector = PatternDetector(mock_threat_cache)
        result = await detector.detect_patterns(sample_kill)

        # Should detect repeat_attacker pattern
        pattern_types = [p.pattern_type for p in result.patterns]
        assert "repeat_attacker" in pattern_types

        # Warrant score should include repeat_attacker weight
        assert result.warrant_score() >= PATTERN_WEIGHTS["repeat_attacker"]

    @pytest.mark.asyncio
    async def test_detect_gank_rotation(self, mock_threat_cache):
        """Test gank rotation pattern detection."""
        # Create kill from known gank corp (SAFETY.)
        gank_kill = ProcessedKill(
            kill_id=12345680,
            kill_time=datetime.now() - timedelta(minutes=1),
            solar_system_id=30002813,
            victim_ship_type_id=17480,  # Retriever
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=10,
            attacker_corps=[98506879],  # SAFETY.
            attacker_alliances=[],
            attacker_ship_types=[621],  # Catalyst
            final_blow_ship_type_id=621,
            total_value=50_000_000,
            is_pod_kill=False,
        )

        # Prior kills from same gank corp
        prior_kills = [
            ProcessedKill(
                kill_id=12345670 + i,
                kill_time=datetime.now() - timedelta(minutes=10 + i),
                solar_system_id=30002813,
                victim_ship_type_id=17480,
                victim_corporation_id=98000003,
                victim_alliance_id=None,
                attacker_count=10,
                attacker_corps=[98506879],  # SAFETY.
                attacker_alliances=[],
                attacker_ship_types=[621],
                final_blow_ship_type_id=621,
                total_value=50_000_000,
                is_pod_kill=False,
            )
            for i in range(2)  # 2 prior kills
        ]
        mock_threat_cache.get_recent_kills.return_value = prior_kills

        detector = PatternDetector(mock_threat_cache)
        result = await detector.detect_patterns(gank_kill)

        # Should detect gank_rotation pattern
        pattern_types = [p.pattern_type for p in result.patterns]
        assert "gank_rotation" in pattern_types

    @pytest.mark.asyncio
    async def test_detect_unusual_victim(self, mock_threat_cache, high_value_kill):
        """Test unusual victim (high value) pattern detection."""
        detector = PatternDetector(mock_threat_cache)
        result = await detector.detect_patterns(high_value_kill)

        # Should detect unusual_victim pattern
        pattern_types = [p.pattern_type for p in result.patterns]
        assert "unusual_victim" in pattern_types

        # Check context has value info
        pattern = next(p for p in result.patterns if p.pattern_type == "unusual_victim")
        assert pattern.context["total_value"] == 85_000_000_000
        assert "85.0B" in pattern.context["value_display"]

    @pytest.mark.asyncio
    async def test_detect_war_target_activity(self, mock_threat_cache, sample_kill):
        """Test war target activity pattern detection."""
        from aria_esi.services.redisq.entity_filter import EntityMatchResult

        # Create entity match
        entity_match = EntityMatchResult(
            has_match=True,
            attacker_corp_matches=[98000002],
        )

        # Prior watched entity kills
        watched_kills = [sample_kill, sample_kill]  # 2 kills
        mock_threat_cache._get_db.return_value.get_watched_entity_kills.return_value = watched_kills

        detector = PatternDetector(mock_threat_cache)
        result = await detector.detect_patterns(sample_kill, entity_match=entity_match)

        # Should detect war_target_activity pattern
        pattern_types = [p.pattern_type for p in result.patterns]
        assert "war_target_activity" in pattern_types
        assert result.is_watched_entity

    @pytest.mark.asyncio
    async def test_multiple_patterns(self, mock_threat_cache):
        """Test detection of multiple patterns."""
        # High value kill from known gank corp
        gank_high_value = ProcessedKill(
            kill_id=12345680,
            kill_time=datetime.now() - timedelta(minutes=1),
            solar_system_id=30002813,
            victim_ship_type_id=42246,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=15,
            attacker_corps=[98506879],  # SAFETY.
            attacker_alliances=[],
            attacker_ship_types=[621],
            final_blow_ship_type_id=621,
            total_value=85_000_000_000,  # High value
            is_pod_kill=False,
        )

        # Prior kills
        prior_kills = [
            ProcessedKill(
                kill_id=12345670 + i,
                kill_time=datetime.now() - timedelta(minutes=10 + i),
                solar_system_id=30002813,
                victim_ship_type_id=17480,
                victim_corporation_id=98000003,
                victim_alliance_id=None,
                attacker_count=10,
                attacker_corps=[98506879],
                attacker_alliances=[],
                attacker_ship_types=[621],
                final_blow_ship_type_id=621,
                total_value=50_000_000,
                is_pod_kill=False,
            )
            for i in range(3)
        ]
        mock_threat_cache.get_recent_kills.return_value = prior_kills

        detector = PatternDetector(mock_threat_cache)
        result = await detector.detect_patterns(gank_high_value)

        # Should detect multiple patterns
        pattern_types = [p.pattern_type for p in result.patterns]
        assert "gank_rotation" in pattern_types
        assert "unusual_victim" in pattern_types

        # Warrant score should be sum of pattern weights
        expected_min = PATTERN_WEIGHTS["gank_rotation"] + PATTERN_WEIGHTS["unusual_victim"]
        assert result.warrant_score() >= expected_min


class TestKnownGankCorps:
    """Tests for known gank corp constants."""

    def test_safety_in_known_corps(self):
        """Test SAFETY. corp ID is in known gank corps."""
        assert 98506879 in KNOWN_GANK_CORPS

    def test_code_in_known_corps(self):
        """Test CODE. corp ID is in known gank corps."""
        assert 98326526 in KNOWN_GANK_CORPS
