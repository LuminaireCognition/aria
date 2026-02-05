"""Tests for sovereignty data models."""

import pytest

from aria_esi.services.sovereignty.models import (
    AllianceInfo,
    CoalitionInfo,
    SovereigntyEntry,
    SovereigntyStatus,
    TerritoryStats,
)


class TestSovereigntyEntry:
    """Tests for SovereigntyEntry dataclass."""

    def test_create_with_alliance(self):
        """Test creating a sovereignty entry with alliance ownership."""
        entry = SovereigntyEntry(
            system_id=30004759,
            alliance_id=1354830081,
            corporation_id=98169165,
        )
        assert entry.system_id == 30004759
        assert entry.alliance_id == 1354830081
        assert entry.corporation_id == 98169165
        assert entry.faction_id is None

    def test_create_with_faction(self):
        """Test creating a sovereignty entry with NPC faction ownership."""
        entry = SovereigntyEntry(
            system_id=30003135,
            faction_id=500010,  # Serpentis
        )
        assert entry.system_id == 30003135
        assert entry.alliance_id is None
        assert entry.faction_id == 500010

    def test_create_unclaimed(self):
        """Test creating an unclaimed system entry."""
        entry = SovereigntyEntry(system_id=30000001)
        assert entry.system_id == 30000001
        assert entry.alliance_id is None
        assert entry.faction_id is None
        assert entry.corporation_id is None


class TestAllianceInfo:
    """Tests for AllianceInfo dataclass."""

    def test_create_basic(self):
        """Test creating basic alliance info."""
        info = AllianceInfo(
            alliance_id=1354830081,
            name="Goonswarm Federation",
            ticker="CONDI",
        )
        assert info.alliance_id == 1354830081
        assert info.name == "Goonswarm Federation"
        assert info.ticker == "CONDI"
        assert info.executor_corporation_id is None

    def test_create_full(self):
        """Test creating alliance info with all fields."""
        info = AllianceInfo(
            alliance_id=1354830081,
            name="Goonswarm Federation",
            ticker="CONDI",
            executor_corporation_id=98169165,
            faction_id=500001,  # Caldari for FW
        )
        assert info.executor_corporation_id == 98169165
        assert info.faction_id == 500001


class TestCoalitionInfo:
    """Tests for CoalitionInfo dataclass."""

    def test_create_coalition(self):
        """Test creating coalition info."""
        info = CoalitionInfo(
            coalition_id="imperium",
            display_name="The Imperium",
            aliases=["goons", "gsf", "bees"],
            alliance_ids=[1354830081, 937872513],
        )
        assert info.coalition_id == "imperium"
        assert info.display_name == "The Imperium"
        assert len(info.aliases) == 3
        assert "goons" in info.aliases
        assert len(info.alliance_ids) == 2


class TestTerritoryStats:
    """Tests for TerritoryStats dataclass."""

    def test_create_coalition_stats(self):
        """Test creating territory stats for a coalition."""
        stats = TerritoryStats(
            entity_id="imperium",
            entity_name="The Imperium",
            entity_type="coalition",
            system_count=479,
            region_ids=[10000060, 10000061],
            constellation_ids=[20000871, 20000872, 20000873],
        )
        assert stats.entity_type == "coalition"
        assert stats.system_count == 479
        assert len(stats.region_ids) == 2

    def test_create_alliance_stats(self):
        """Test creating territory stats for an alliance."""
        stats = TerritoryStats(
            entity_id=1354830081,
            entity_name="Goonswarm Federation",
            entity_type="alliance",
            system_count=200,
            region_ids=[10000060],
            constellation_ids=[20000871],
            capital_system_id=30004759,
        )
        assert stats.entity_type == "alliance"
        assert stats.capital_system_id == 30004759


class TestSovereigntyStatus:
    """Tests for SovereigntyStatus dataclass."""

    def test_create_player_sov(self):
        """Test creating status for player-held sovereignty."""
        status = SovereigntyStatus(
            system_id=30004759,
            alliance_id=1354830081,
            alliance_name="Goonswarm Federation",
            faction_id=None,
            faction_name=None,
            coalition_id="imperium",
            coalition_name="The Imperium",
            updated_at=1700000000,
        )
        assert status.system_id == 30004759
        assert status.alliance_name == "Goonswarm Federation"
        assert status.coalition_id == "imperium"

    def test_create_npc_sov(self):
        """Test creating status for NPC null-sec."""
        status = SovereigntyStatus(
            system_id=30003135,
            alliance_id=None,
            alliance_name=None,
            faction_id=500010,
            faction_name="Serpentis Corporation",
            coalition_id=None,
            coalition_name=None,
            updated_at=1700000000,
        )
        assert status.alliance_id is None
        assert status.faction_name == "Serpentis Corporation"
