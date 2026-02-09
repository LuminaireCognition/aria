"""
Tests for Local Area Dispatcher Action (STP-014).

Tests the local_area action for orientation intel in unknown space.
Covers threat classification, hotspots, quiet zones, ratting banks,
escape routes, and security borders.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.mcp.activity import ActivityCache, ActivityData
from aria_esi.mcp.errors import InvalidParameterError
from aria_esi.mcp.models import (
    EscapeRoute,
    LocalAreaResult,
    LocalSystemActivity,
    SecurityBorder,
    ThreatSummary,
)

from .conftest import STANDARD_EDGES, STANDARD_SYSTEMS, create_mock_universe

# =============================================================================
# Response Model Unit Tests
# =============================================================================


class TestThreatSummary:
    """Tests for ThreatSummary model."""

    def test_low_threat_level(self):
        """LOW threat with minimal activity."""
        summary = ThreatSummary(
            level="LOW",
            total_kills=5,
            total_pods=1,
            active_camps=[],
            hotspot_count=0,
        )
        assert summary.level == "LOW"
        assert summary.total_kills == 5
        assert len(summary.active_camps) == 0

    def test_high_threat_with_camps(self):
        """HIGH threat with active gatecamps."""
        summary = ThreatSummary(
            level="HIGH",
            total_kills=25,
            total_pods=10,
            active_camps=["Tama", "Amamake"],
            hotspot_count=3,
        )
        assert summary.level == "HIGH"
        assert len(summary.active_camps) == 2
        assert "Tama" in summary.active_camps

    def test_extreme_threat_level(self):
        """EXTREME threat with multiple camps."""
        summary = ThreatSummary(
            level="EXTREME",
            total_kills=100,
            total_pods=50,
            active_camps=["A", "B", "C"],
            hotspot_count=10,
        )
        assert summary.level == "EXTREME"


class TestLocalSystemActivity:
    """Tests for LocalSystemActivity model."""

    def test_basic_system_activity(self):
        """System activity with all fields."""
        activity = LocalSystemActivity(
            system="Tama",
            system_id=30002813,
            security=0.35,
            security_class="LOW",
            region="The Citadel",
            jumps=5,
            ship_kills=20,
            pod_kills=10,
            npc_kills=50,
            ship_jumps=200,
            activity_level="high",
            reason="gatecamp",
        )
        assert activity.system == "Tama"
        assert activity.security_class == "LOW"
        assert activity.reason == "gatecamp"
        assert activity.activity_level == "high"

    def test_quiet_system_defaults(self):
        """Quiet system with minimal activity."""
        activity = LocalSystemActivity(
            system="EmptySpace",
            system_id=30000001,
            security=-0.5,
            security_class="NULL",
            region="Deep Null",
            jumps=10,
        )
        assert activity.ship_kills == 0
        assert activity.pod_kills == 0
        assert activity.activity_level == "none"
        assert activity.reason is None


class TestEscapeRoute:
    """Tests for EscapeRoute model."""

    def test_highsec_escape(self):
        """Escape route to high-sec."""
        route = EscapeRoute(
            destination="Jita",
            destination_type="highsec",
            jumps=15,
            via_system="BorderSystem",
            route_security="mixed",
        )
        assert route.destination_type == "highsec"
        assert route.jumps == 15
        assert route.route_security == "mixed"

    def test_lowsec_escape_from_null(self):
        """Escape route from null to low-sec."""
        route = EscapeRoute(
            destination="Amamake",
            destination_type="lowsec",
            jumps=3,
            route_security="lowsec",
        )
        assert route.destination_type == "lowsec"
        assert route.via_system is None


class TestSecurityBorder:
    """Tests for SecurityBorder model."""

    def test_high_to_low_border(self):
        """High-sec to low-sec border."""
        border = SecurityBorder(
            system="Maurasi",
            system_id=30000140,
            security=0.65,
            jumps=2,
            border_type="high_to_low",
            adjacent_system="Sivala",
            adjacent_security=0.35,
        )
        assert border.border_type == "high_to_low"
        assert border.adjacent_system == "Sivala"

    def test_low_to_null_border(self):
        """Low-sec to null-sec border."""
        border = SecurityBorder(
            system="Sivala",
            system_id=30000160,
            security=0.35,
            jumps=3,
            border_type="low_to_null",
            adjacent_system="Ala",
            adjacent_security=-0.2,
        )
        assert border.border_type == "low_to_null"


class TestLocalAreaResult:
    """Tests for complete LocalAreaResult model."""

    def test_complete_result(self):
        """Full local area result with all fields."""
        result = LocalAreaResult(
            origin="Tama",
            origin_id=30002813,
            security=0.35,
            security_class="LOW",
            region="The Citadel",
            constellation="Mivora",
            threat_summary=ThreatSummary(
                level="MEDIUM",
                total_kills=15,
                total_pods=5,
                active_camps=[],
                hotspot_count=2,
            ),
            hotspots=[],
            quiet_zones=[],
            ratting_banks=[],
            escape_routes=[],
            borders=[],
            systems_scanned=50,
            search_radius=10,
            cache_age_seconds=120,
            realtime_healthy=True,
        )
        assert result.origin == "Tama"
        assert result.threat_summary.level == "MEDIUM"
        assert result.systems_scanned == 50
        assert result.realtime_healthy is True


# =============================================================================
# Helper Functions Tests
# =============================================================================


class TestBorderClassification:
    """Tests for _classify_border helper."""

    def test_high_to_low_transition(self):
        """High-sec to low-sec is a border."""
        from aria_esi.mcp.dispatchers.universe import _classify_border

        assert _classify_border(0.65, 0.35) == "high_to_low"

    def test_low_to_high_transition(self):
        """Low-sec to high-sec is a border."""
        from aria_esi.mcp.dispatchers.universe import _classify_border

        assert _classify_border(0.35, 0.65) == "low_to_high"

    def test_low_to_null_transition(self):
        """Low-sec to null-sec is a border."""
        from aria_esi.mcp.dispatchers.universe import _classify_border

        assert _classify_border(0.25, -0.2) == "low_to_null"

    def test_null_to_low_transition(self):
        """Null-sec to low-sec is a border."""
        from aria_esi.mcp.dispatchers.universe import _classify_border

        assert _classify_border(-0.2, 0.25) == "null_to_low"

    def test_same_security_class_no_border(self):
        """Same security class is not a border."""
        from aria_esi.mcp.dispatchers.universe import _classify_border

        # High to high
        assert _classify_border(0.95, 0.65) is None
        # Low to low
        assert _classify_border(0.35, 0.25) is None
        # Null to null
        assert _classify_border(-0.2, -0.5) is None


class TestThreatLevelClassification:
    """Tests for _classify_threat_level helper."""

    def test_low_threat_minimal_activity(self):
        """LOW threat with minimal activity."""
        from aria_esi.mcp.dispatchers.universe import _classify_threat_level

        assert _classify_threat_level(total_kills=5, hotspot_count=0, camp_count=0) == "LOW"

    def test_medium_threat_moderate_activity(self):
        """MEDIUM threat with moderate activity."""
        from aria_esi.mcp.dispatchers.universe import _classify_threat_level

        assert _classify_threat_level(total_kills=25, hotspot_count=2, camp_count=0) == "MEDIUM"

    def test_high_threat_high_kills(self):
        """HIGH threat with high kill count."""
        from aria_esi.mcp.dispatchers.universe import _classify_threat_level

        assert _classify_threat_level(total_kills=50, hotspot_count=3, camp_count=0) == "HIGH"

    def test_high_threat_many_hotspots(self):
        """HIGH threat with many hotspots."""
        from aria_esi.mcp.dispatchers.universe import _classify_threat_level

        assert _classify_threat_level(total_kills=10, hotspot_count=5, camp_count=0) == "HIGH"

    def test_high_threat_one_camp(self):
        """HIGH threat with one active camp."""
        from aria_esi.mcp.dispatchers.universe import _classify_threat_level

        assert _classify_threat_level(total_kills=5, hotspot_count=0, camp_count=1) == "HIGH"

    def test_extreme_threat_multiple_camps(self):
        """EXTREME threat with multiple camps."""
        from aria_esi.mcp.dispatchers.universe import _classify_threat_level

        assert _classify_threat_level(total_kills=5, hotspot_count=0, camp_count=3) == "EXTREME"


# =============================================================================
# Dispatcher Integration Tests
# =============================================================================


class TestLocalAreaDispatcher:
    """Integration tests for the local_area action in universe dispatcher."""

    @pytest.fixture
    def standard_universe(self):
        """Standard 6-system test universe."""
        return create_mock_universe(STANDARD_SYSTEMS, STANDARD_EDGES)

    @pytest.fixture
    def mock_activity_cache(self):
        """Mock activity cache with test data."""
        cache = MagicMock(spec=ActivityCache)
        cache.get_kills_cache_age.return_value = 120

        # Activity data for test systems
        activity_data = {
            30000142: ActivityData(system_id=30000142, ship_kills=5, pod_kills=2, npc_kills=50),  # Jita
            30000144: ActivityData(system_id=30000144, ship_kills=1, pod_kills=0, npc_kills=10),  # Perimeter
            30000140: ActivityData(system_id=30000140, ship_kills=0, pod_kills=0, npc_kills=0),   # Maurasi
            30000138: ActivityData(system_id=30000138, ship_kills=0, pod_kills=0, npc_kills=5),   # Urlen
            30000160: ActivityData(system_id=30000160, ship_kills=15, pod_kills=5, npc_kills=200),  # Sivala - hotspot
            30000161: ActivityData(system_id=30000161, ship_kills=2, pod_kills=1, npc_kills=500),   # Ala - ratting bank
        }

        async def get_all_activity():
            return activity_data

        cache.get_all_activity = get_all_activity
        return cache

    @pytest.mark.asyncio
    async def test_local_area_requires_origin(self, standard_universe):
        """local_area action requires origin parameter."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with pytest.raises(InvalidParameterError) as exc:
            await _local_area(
                origin=None,
                max_jumps=10,
                include_realtime=False,
                hotspot_threshold=5,
                quiet_threshold=0,
                ratting_threshold=100,
            )

        assert "origin" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_local_area_validates_max_jumps_range(self, standard_universe, mock_activity_cache):
        """max_jumps must be between 1 and 30."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                # Too high (>30)
                with pytest.raises(InvalidParameterError) as exc:
                    await _local_area(
                        origin="Jita",
                        max_jumps=50,
                        include_realtime=False,
                        hotspot_threshold=5,
                        quiet_threshold=0,
                        ratting_threshold=100,
                    )
                assert "max_jumps" in str(exc.value).lower()

                # Negative value
                with pytest.raises(InvalidParameterError) as exc:
                    await _local_area(
                        origin="Jita",
                        max_jumps=-5,
                        include_realtime=False,
                        hotspot_threshold=5,
                        quiet_threshold=0,
                        ratting_threshold=100,
                    )
                assert "max_jumps" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_local_area_basic_execution(self, standard_universe, mock_activity_cache):
        """local_area action executes successfully with valid parameters."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                result = await _local_area(
                    origin="Jita",
                    max_jumps=5,
                    include_realtime=False,
                    hotspot_threshold=5,
                    quiet_threshold=0,
                    ratting_threshold=100,
                )

        assert isinstance(result, dict)
        assert result["origin"] == "Jita"
        assert result["security_class"] == "HIGH"
        assert "threat_summary" in result
        assert "hotspots" in result
        assert "quiet_zones" in result
        assert "borders" in result
        assert result["systems_scanned"] > 0

    @pytest.mark.asyncio
    async def test_local_area_identifies_hotspots(self, standard_universe, mock_activity_cache):
        """Hotspots are correctly identified based on threshold."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                result = await _local_area(
                    origin="Jita",
                    max_jumps=5,
                    include_realtime=False,
                    hotspot_threshold=5,  # Sivala has 20 kills
                    quiet_threshold=0,
                    ratting_threshold=100,
                )

        hotspots = result.get("hotspots", [])
        hotspot_names = [h["system"] for h in hotspots]

        # Sivala should be a hotspot (15 ship + 5 pod = 20 kills)
        assert "Sivala" in hotspot_names

    @pytest.mark.asyncio
    async def test_local_area_identifies_quiet_zones(self, standard_universe, mock_activity_cache):
        """Quiet zones are correctly identified."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                result = await _local_area(
                    origin="Jita",
                    max_jumps=5,
                    include_realtime=False,
                    hotspot_threshold=5,
                    quiet_threshold=0,  # Only systems with 0 PvP kills
                    ratting_threshold=100,
                )

        quiet_zones = result.get("quiet_zones", [])
        quiet_names = [q["system"] for q in quiet_zones]

        # Maurasi and Urlen have 0 PvP kills
        assert "Maurasi" in quiet_names or "Urlen" in quiet_names

    @pytest.mark.asyncio
    async def test_local_area_identifies_ratting_banks(self, standard_universe, mock_activity_cache):
        """Ratting banks are correctly identified based on NPC kills."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                result = await _local_area(
                    origin="Jita",
                    max_jumps=5,
                    include_realtime=False,
                    hotspot_threshold=5,
                    quiet_threshold=0,
                    ratting_threshold=100,  # Ala has 500 NPC kills
                )

        ratting_banks = result.get("ratting_banks", [])

        # Ala and Sivala have high NPC kills
        assert len(ratting_banks) >= 1

    @pytest.mark.asyncio
    async def test_local_area_detects_security_borders(self, standard_universe, mock_activity_cache):
        """Security borders are detected correctly."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                result = await _local_area(
                    origin="Maurasi",  # Border system
                    max_jumps=5,
                    include_realtime=False,
                    hotspot_threshold=5,
                    quiet_threshold=0,
                    ratting_threshold=100,
                )

        borders = result.get("borders", [])

        # Should find high_to_low and low_to_null borders
        assert len(borders) > 0

    @pytest.mark.asyncio
    async def test_local_area_threat_summary(self, standard_universe, mock_activity_cache):
        """Threat summary is correctly calculated."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                result = await _local_area(
                    origin="Jita",
                    max_jumps=5,
                    include_realtime=False,
                    hotspot_threshold=5,
                    quiet_threshold=0,
                    ratting_threshold=100,
                )

        threat = result["threat_summary"]
        assert "level" in threat
        assert threat["level"] in ["LOW", "MEDIUM", "HIGH", "EXTREME"]
        assert threat["total_kills"] >= 0
        assert threat["total_pods"] >= 0

    @pytest.mark.asyncio
    async def test_local_area_from_lowsec_origin(self, standard_universe, mock_activity_cache):
        """local_area works from low-sec origin."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                result = await _local_area(
                    origin="Sivala",
                    max_jumps=5,
                    include_realtime=False,
                    hotspot_threshold=5,
                    quiet_threshold=0,
                    ratting_threshold=100,
                )

        assert result["origin"] == "Sivala"
        assert result["security_class"] == "LOW"
        assert result["systems_scanned"] > 0

    @pytest.mark.asyncio
    async def test_local_area_from_nullsec_origin(self, standard_universe, mock_activity_cache):
        """local_area works from null-sec origin."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                result = await _local_area(
                    origin="Ala",
                    max_jumps=5,
                    include_realtime=False,
                    hotspot_threshold=5,
                    quiet_threshold=0,
                    ratting_threshold=100,
                )

        assert result["origin"] == "Ala"
        assert result["security_class"] == "NULL"

        # Should find escape routes to safer space
        escape_routes = result.get("escape_routes", [])
        # From null, should find low-sec escape
        if escape_routes:
            route_types = [r["destination_type"] for r in escape_routes]
            assert "lowsec" in route_types or "highsec" in route_types

    @pytest.mark.asyncio
    async def test_local_area_cache_age_reported(self, standard_universe, mock_activity_cache):
        """Cache age is included in result."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                result = await _local_area(
                    origin="Jita",
                    max_jumps=3,
                    include_realtime=False,
                    hotspot_threshold=5,
                    quiet_threshold=0,
                    ratting_threshold=100,
                )

        assert "cache_age_seconds" in result
        assert result["cache_age_seconds"] == 120  # From mock

    @pytest.mark.asyncio
    async def test_local_area_realtime_default_off(self, standard_universe, mock_activity_cache):
        """Real-time data is off by default."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                result = await _local_area(
                    origin="Jita",
                    max_jumps=3,
                    include_realtime=False,
                    hotspot_threshold=5,
                    quiet_threshold=0,
                    ratting_threshold=100,
                )

        # Without include_realtime=True, should be False
        assert result.get("realtime_healthy") is False

    @pytest.mark.asyncio
    async def test_local_area_results_sorted_correctly(self, standard_universe, mock_activity_cache):
        """Results are sorted by appropriate criteria."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                result = await _local_area(
                    origin="Jita",
                    max_jumps=5,
                    include_realtime=False,
                    hotspot_threshold=1,
                    quiet_threshold=0,
                    ratting_threshold=100,
                )

        hotspots = result.get("hotspots", [])
        if len(hotspots) >= 2:
            # Should be sorted by kills descending
            for i in range(len(hotspots) - 1):
                kills_i = hotspots[i]["ship_kills"] + hotspots[i]["pod_kills"]
                kills_next = hotspots[i + 1]["ship_kills"] + hotspots[i + 1]["pod_kills"]
                assert kills_i >= kills_next

        quiet_zones = result.get("quiet_zones", [])
        if len(quiet_zones) >= 2:
            # Should be sorted by distance ascending
            for i in range(len(quiet_zones) - 1):
                assert quiet_zones[i]["jumps"] <= quiet_zones[i + 1]["jumps"]

    @pytest.mark.asyncio
    async def test_local_area_respects_result_limits(self, standard_universe, mock_activity_cache):
        """Results are limited to 10 per category."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                result = await _local_area(
                    origin="Jita",
                    max_jumps=5,
                    include_realtime=False,
                    hotspot_threshold=5,
                    quiet_threshold=0,
                    ratting_threshold=100,
                )

        assert len(result.get("hotspots", [])) <= 10
        assert len(result.get("quiet_zones", [])) <= 10
        assert len(result.get("ratting_banks", [])) <= 10
        assert len(result.get("borders", [])) <= 10

    @pytest.mark.asyncio
    async def test_local_area_gatecamp_and_high_kills_not_double_counted(
        self, standard_universe, mock_activity_cache
    ):
        """A system that is both a gatecamp and has high kills should only count once in hotspot_count."""
        from aria_esi.mcp.dispatchers.universe import _local_area

        # Create mock threat cache that reports Sivala as a gatecamp
        mock_threat_cache = MagicMock()
        mock_threat_cache.is_healthy.return_value = True

        # Mock gatecamp detection for Sivala
        mock_activity_summary = MagicMock()
        mock_gatecamp = MagicMock()
        mock_gatecamp.system_name = "Sivala"
        mock_activity_summary.gatecamp = mock_gatecamp

        # get_activity_for_systems returns {system_id: ActivitySummary}
        mock_threat_cache.get_activity_for_systems.return_value = {
            30000160: mock_activity_summary  # Sivala
        }

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
                with patch(
                    "aria_esi.services.redisq.threat_cache.get_threat_cache",
                    return_value=mock_threat_cache,
                ):
                    result = await _local_area(
                        origin="Jita",
                        max_jumps=5,
                        include_realtime=True,  # Enable realtime to use threat cache
                        hotspot_threshold=5,  # Sivala has 15+5=20 kills, so it's a hotspot
                        quiet_threshold=0,
                        ratting_threshold=100,
                    )

        # Sivala should appear in hotspots only once
        hotspots = result.get("hotspots", [])
        sivala_entries = [h for h in hotspots if h["system"] == "Sivala"]
        assert len(sivala_entries) == 1, "Sivala should appear exactly once in hotspots"

        # The hotspot_count in threat_summary should reflect actual count
        # Sivala is both a gatecamp AND has high kills - should only be counted once
        threat = result["threat_summary"]
        assert threat["hotspot_count"] == len(hotspots), (
            f"hotspot_count ({threat['hotspot_count']}) should match actual hotspots ({len(hotspots)})"
        )


# =============================================================================
# Escape Route Tests
# =============================================================================


class TestEscapeRoutes:
    """Tests for escape route calculation."""

    @pytest.fixture
    def standard_universe(self):
        """Standard 6-system test universe."""
        return create_mock_universe(STANDARD_SYSTEMS, STANDARD_EDGES)

    @pytest.fixture
    def mock_activity_cache(self):
        """Mock activity cache with empty data."""
        cache = MagicMock(spec=ActivityCache)
        cache.get_kills_cache_age.return_value = 60

        async def get_all_activity():
            return {}

        cache.get_all_activity = get_all_activity
        return cache

    @pytest.mark.asyncio
    async def test_escape_from_null_finds_lowsec(self, standard_universe, mock_activity_cache):
        """Escape from null-sec finds nearest low-sec."""
        from aria_esi.mcp.dispatchers.universe import _find_escape_routes

        # Build visited dict like BFS would
        visited = {5: 0, 4: 1, 2: 2, 3: 3, 0: 3, 1: 4}  # From Ala (idx 5)
        origin_idx = 5  # Ala (null-sec)
        origin_sec = -0.2

        routes = await _find_escape_routes(
            standard_universe, origin_idx, origin_sec, visited, max_jumps=5
        )

        # Should find Sivala as nearest low-sec
        lowsec_routes = [r for r in routes if r.destination_type == "lowsec"]
        assert len(lowsec_routes) >= 1
        assert lowsec_routes[0].destination == "Sivala"
        assert lowsec_routes[0].jumps == 1

    @pytest.mark.asyncio
    async def test_escape_from_null_finds_highsec(self, standard_universe, mock_activity_cache):
        """Escape from null-sec finds high-sec."""
        from aria_esi.mcp.dispatchers.universe import _find_escape_routes

        visited = {5: 0, 4: 1, 2: 2, 3: 3, 0: 3, 1: 4}  # From Ala
        origin_idx = 5
        origin_sec = -0.2

        routes = await _find_escape_routes(
            standard_universe, origin_idx, origin_sec, visited, max_jumps=5
        )

        # Should find high-sec escape
        highsec_routes = [r for r in routes if r.destination_type == "highsec"]
        assert len(highsec_routes) >= 1

    @pytest.mark.asyncio
    async def test_escape_from_lowsec_finds_highsec(self, standard_universe, mock_activity_cache):
        """Escape from low-sec finds high-sec."""
        from aria_esi.mcp.dispatchers.universe import _find_escape_routes

        visited = {4: 0, 2: 1, 5: 1, 0: 2, 3: 2, 1: 3}  # From Sivala (idx 4)
        origin_idx = 4  # Sivala (low-sec)
        origin_sec = 0.35

        routes = await _find_escape_routes(
            standard_universe, origin_idx, origin_sec, visited, max_jumps=5
        )

        # Should find Maurasi as nearest high-sec
        highsec_routes = [r for r in routes if r.destination_type == "highsec"]
        assert len(highsec_routes) >= 1
        assert highsec_routes[0].destination == "Maurasi"
        assert highsec_routes[0].jumps == 1

    @pytest.mark.asyncio
    async def test_escape_from_highsec_no_routes(self, standard_universe, mock_activity_cache):
        """Escape from high-sec returns no escape routes (already safe)."""
        from aria_esi.mcp.dispatchers.universe import _find_escape_routes

        visited = {0: 0, 1: 1, 2: 1, 3: 2}  # From Jita (idx 0)
        origin_idx = 0  # Jita (high-sec)
        origin_sec = 0.95

        routes = await _find_escape_routes(
            standard_universe, origin_idx, origin_sec, visited, max_jumps=3
        )

        # High-sec doesn't need escape routes
        assert len(routes) == 0


# =============================================================================
# Nearest Activity Predicates Tests
# =============================================================================


class TestNearestActivityPredicates:
    """Tests for activity-based predicates in universe_nearest."""

    @pytest.fixture
    def standard_universe(self):
        """Standard 6-system test universe."""
        return create_mock_universe(STANDARD_SYSTEMS, STANDARD_EDGES)

    @pytest.fixture
    def mock_activity_cache_for_nearest(self):
        """Mock activity cache for nearest tool tests."""
        cache = MagicMock(spec=ActivityCache)
        cache.get_kills_cache_age.return_value = 60

        activity_data = {
            30000142: ActivityData(system_id=30000142, ship_kills=10, pod_kills=5, npc_kills=100),  # Jita - active
            30000144: ActivityData(system_id=30000144, ship_kills=2, pod_kills=0, npc_kills=20),   # Perimeter - low
            30000140: ActivityData(system_id=30000140, ship_kills=0, pod_kills=0, npc_kills=0),    # Maurasi - quiet
            30000138: ActivityData(system_id=30000138, ship_kills=0, pod_kills=0, npc_kills=5),    # Urlen - quiet
            30000160: ActivityData(system_id=30000160, ship_kills=8, pod_kills=2, npc_kills=300),  # Sivala - medium
            30000161: ActivityData(system_id=30000161, ship_kills=1, pod_kills=0, npc_kills=500),  # Ala - ratting
        }

        async def get_all_activity():
            return activity_data

        cache.get_all_activity = get_all_activity
        return cache

    @pytest.fixture
    def nearest_tool(self, standard_universe, mock_activity_cache_for_nearest):
        """Create nearest tool with mocked dependencies."""
        from aria_esi.mcp.tools_nearest import register_nearest_tools

        mock_server = MagicMock()
        captured_func = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_func
                captured_func = func
                return func
            return decorator

        mock_server.tool = mock_tool

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            register_nearest_tools(mock_server, standard_universe)

        original_func = captured_func

        async def patched_nearest(**kwargs):
            with patch("aria_esi.mcp.tools._universe", standard_universe):
                with patch("aria_esi.mcp.tools_nearest.get_activity_cache", return_value=mock_activity_cache_for_nearest):
                    return await original_func(**kwargs)

        return patched_nearest

    def test_max_kills_parameter_validation(self, nearest_tool):
        """max_kills must be >= 0."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(nearest_tool(
                origin="Jita",
                max_kills=-1,
            ))
        assert "max_kills" in str(exc.value).lower()

    def test_min_npc_kills_parameter_validation(self, nearest_tool):
        """min_npc_kills must be >= 0."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(nearest_tool(
                origin="Jita",
                min_npc_kills=-5,
            ))
        assert "min_npc_kills" in str(exc.value).lower()

    def test_activity_level_parameter_validation(self, nearest_tool):
        """activity_level must be valid enum value."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(nearest_tool(
                origin="Jita",
                activity_level="invalid",
            ))
        assert "activity_level" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_find_quiet_systems_with_max_kills(self, standard_universe, mock_activity_cache_for_nearest):
        """Find quiet systems with max_kills=0."""
        from aria_esi.mcp.tools_nearest import register_nearest_tools

        mock_server = MagicMock()
        captured_func = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_func
                captured_func = func
                return func
            return decorator

        mock_server.tool = mock_tool

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            register_nearest_tools(mock_server, standard_universe)

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.tools_nearest.get_activity_cache", return_value=mock_activity_cache_for_nearest):
                result = await captured_func(
                    origin="Jita",
                    max_kills=0,
                    limit=10,
                )

        systems = result.get("systems", [])
        system_names = [s["name"] for s in systems]  # Use 'name' not 'system'

        # Maurasi and Urlen have 0 PvP kills
        assert "Maurasi" in system_names or "Urlen" in system_names

    @pytest.mark.asyncio
    async def test_find_ratting_systems_with_min_npc_kills(self, standard_universe, mock_activity_cache_for_nearest):
        """Find ratting systems with min_npc_kills threshold."""
        from aria_esi.mcp.tools_nearest import register_nearest_tools

        mock_server = MagicMock()
        captured_func = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_func
                captured_func = func
                return func
            return decorator

        mock_server.tool = mock_tool

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            register_nearest_tools(mock_server, standard_universe)

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.tools_nearest.get_activity_cache", return_value=mock_activity_cache_for_nearest):
                result = await captured_func(
                    origin="Jita",
                    min_npc_kills=100,
                    limit=10,
                )

        systems = result.get("systems", [])

        # Jita (100), Sivala (300), Ala (500) have >= 100 NPC kills
        assert len(systems) >= 1

    @pytest.mark.asyncio
    async def test_predicates_include_cache_age(self, standard_universe, mock_activity_cache_for_nearest):
        """Activity predicates include cache age in result."""
        from aria_esi.mcp.tools_nearest import register_nearest_tools

        mock_server = MagicMock()
        captured_func = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_func
                captured_func = func
                return func
            return decorator

        mock_server.tool = mock_tool

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            register_nearest_tools(mock_server, standard_universe)

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.tools_nearest.get_activity_cache", return_value=mock_activity_cache_for_nearest):
                result = await captured_func(
                    origin="Jita",
                    max_kills=10,
                    limit=5,
                )

        # When activity predicates are used, cache_age should be included
        assert "activity_cache_age_seconds" in result

    @pytest.mark.asyncio
    async def test_combined_activity_and_security_predicates(self, standard_universe, mock_activity_cache_for_nearest):
        """Activity predicates work with security filters."""
        from aria_esi.mcp.tools_nearest import register_nearest_tools

        mock_server = MagicMock()
        captured_func = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_func
                captured_func = func
                return func
            return decorator

        mock_server.tool = mock_tool

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            register_nearest_tools(mock_server, standard_universe)

        with patch("aria_esi.mcp.tools._universe", standard_universe):
            with patch("aria_esi.mcp.tools_nearest.get_activity_cache", return_value=mock_activity_cache_for_nearest):
                result = await captured_func(
                    origin="Jita",
                    max_kills=20,  # Higher threshold to include Sivala
                    security_max=0.4,  # Low-sec only
                    limit=10,
                )

        systems = result.get("systems", [])

        # Should only return low-sec systems
        for system in systems:
            assert system["security"] < 0.45


# =============================================================================
# Activity Classification Tests
# =============================================================================


class TestActivityClassification:
    """Tests for classify_activity function."""

    def test_classify_zero_kills(self):
        """Zero kills classifies as 'none'."""
        from aria_esi.mcp.activity import classify_activity

        assert classify_activity(0, "kills") == "none"

    def test_classify_low_kills(self):
        """Low kills classify correctly."""
        from aria_esi.mcp.activity import classify_activity

        assert classify_activity(3, "kills") == "low"

    def test_classify_medium_kills(self):
        """Medium kills classify correctly."""
        from aria_esi.mcp.activity import classify_activity

        assert classify_activity(10, "kills") == "medium"

    def test_classify_high_kills(self):
        """High kills classify correctly."""
        from aria_esi.mcp.activity import classify_activity

        assert classify_activity(25, "kills") == "high"

    def test_classify_extreme_kills(self):
        """Extreme kills classify correctly."""
        from aria_esi.mcp.activity import classify_activity

        assert classify_activity(100, "kills") == "extreme"
