"""
Tests for entity-aware kill filtering.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from aria_esi.services.redisq.entity_filter import (
    EntityAwareFilter,
    EntityMatchResult,
)
from aria_esi.services.redisq.models import ProcessedKill


@pytest.fixture
def sample_kill() -> ProcessedKill:
    """Sample processed kill for testing."""
    return ProcessedKill(
        kill_id=123456789,
        kill_time=datetime.now(),
        solar_system_id=30000142,
        victim_ship_type_id=17740,
        victim_corporation_id=98000001,
        victim_alliance_id=99000001,
        attacker_count=3,
        attacker_corps=[98000002, 98000003],
        attacker_alliances=[99000002],
        attacker_ship_types=[17812, 24690],
        final_blow_ship_type_id=17812,
        total_value=150000000.0,
        is_pod_kill=False,
    )


class TestEntityMatchResult:
    """Tests for EntityMatchResult dataclass."""

    def test_empty_result(self):
        """Test empty match result."""
        result = EntityMatchResult()

        assert result.has_match is False
        assert result.all_matched_ids == []
        assert result.match_types == []

    def test_victim_corp_match(self):
        """Test result with victim corp match."""
        result = EntityMatchResult(
            has_match=True,
            victim_corp_match=98000001,
        )

        assert result.has_match is True
        assert 98000001 in result.all_matched_ids
        assert "victim_corp" in result.match_types

    def test_attacker_alliance_match(self):
        """Test result with attacker alliance match."""
        result = EntityMatchResult(
            has_match=True,
            attacker_alliance_matches=[99000001, 99000002],
        )

        assert 99000001 in result.all_matched_ids
        assert 99000002 in result.all_matched_ids
        assert "attacker_alliance" in result.match_types

    def test_multiple_matches(self):
        """Test result with multiple match types."""
        result = EntityMatchResult(
            has_match=True,
            victim_corp_match=98000001,
            attacker_corp_matches=[98000002],
            attacker_alliance_matches=[99000001],
        )

        assert len(result.all_matched_ids) == 3
        assert len(result.match_types) == 3

    def test_to_dict(self):
        """Test JSON serialization."""
        result = EntityMatchResult(
            has_match=True,
            victim_corp_match=98000001,
        )

        d = result.to_dict()

        assert d["has_match"] is True
        assert d["victim_corp_match"] == 98000001
        assert 98000001 in d["all_matched_ids"]


class TestEntityAwareFilter:
    """Tests for EntityAwareFilter class."""

    def test_no_watched_entities(self, sample_kill):
        """Test filter with no watched entities."""
        filter = EntityAwareFilter()
        filter._watched_corps = set()
        filter._watched_alliances = set()
        filter._cache_loaded = True

        result = filter.check_kill(sample_kill)

        assert result.has_match is False

    def test_victim_corp_watched(self, sample_kill):
        """Test detecting watched victim corporation."""
        filter = EntityAwareFilter()
        filter._watched_corps = {98000001}
        filter._watched_alliances = set()
        filter._cache_loaded = True

        result = filter.check_kill(sample_kill)

        assert result.has_match is True
        assert result.victim_corp_match == 98000001

    def test_victim_alliance_watched(self, sample_kill):
        """Test detecting watched victim alliance."""
        filter = EntityAwareFilter()
        filter._watched_corps = set()
        filter._watched_alliances = {99000001}
        filter._cache_loaded = True

        result = filter.check_kill(sample_kill)

        assert result.has_match is True
        assert result.victim_alliance_match == 99000001

    def test_attacker_corp_watched(self, sample_kill):
        """Test detecting watched attacker corporation."""
        filter = EntityAwareFilter()
        filter._watched_corps = {98000002}
        filter._watched_alliances = set()
        filter._cache_loaded = True

        result = filter.check_kill(sample_kill)

        assert result.has_match is True
        assert 98000002 in result.attacker_corp_matches

    def test_attacker_alliance_watched(self, sample_kill):
        """Test detecting watched attacker alliance."""
        filter = EntityAwareFilter()
        filter._watched_corps = set()
        filter._watched_alliances = {99000002}
        filter._cache_loaded = True

        result = filter.check_kill(sample_kill)

        assert result.has_match is True
        assert 99000002 in result.attacker_alliance_matches

    def test_multiple_attacker_matches(self, sample_kill):
        """Test matching multiple attackers."""
        filter = EntityAwareFilter()
        filter._watched_corps = {98000002, 98000003}
        filter._watched_alliances = set()
        filter._cache_loaded = True

        result = filter.check_kill(sample_kill)

        assert result.has_match is True
        assert 98000002 in result.attacker_corp_matches
        assert 98000003 in result.attacker_corp_matches

    def test_is_entity_watched(self):
        """Test checking if specific entity is watched."""
        filter = EntityAwareFilter()
        filter._watched_corps = {98000001}
        filter._watched_alliances = {99000001}
        filter._cache_loaded = True

        assert filter.is_entity_watched(98000001, "corporation") is True
        assert filter.is_entity_watched(98000002, "corporation") is False
        assert filter.is_entity_watched(99000001, "alliance") is True
        assert filter.is_entity_watched(99000002, "alliance") is False

    def test_is_active(self):
        """Test checking if filter has any watched entities."""
        filter = EntityAwareFilter()
        filter._watched_corps = set()
        filter._watched_alliances = set()
        filter._cache_loaded = True

        assert filter.is_active is False

        filter._watched_corps = {98000001}
        assert filter.is_active is True

    def test_watched_counts(self):
        """Test getting watched entity counts."""
        filter = EntityAwareFilter()
        filter._watched_corps = {98000001, 98000002}
        filter._watched_alliances = {99000001}
        filter._cache_loaded = True

        assert filter.watched_corp_count == 2
        assert filter.watched_alliance_count == 1
