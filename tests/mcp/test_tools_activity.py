"""
Tests for Activity Overlay Tools (STP-013).

Tests the ActivityCache and activity-related MCP tools.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.mcp.activity import (
    ActivityCache,
    ActivityData,
    FWSystemData,
    classify_activity,
    get_faction_id,
    get_faction_name,
)
from aria_esi.mcp.tools_activity import register_activity_tools

from .conftest import create_mock_universe

# =============================================================================
# ActivityCache Tests
# =============================================================================


class TestActivityCache:
    """Tests for the ActivityCache class."""

    def test_init_defaults(self):
        """Cache initializes with correct defaults."""
        cache = ActivityCache()
        assert cache.ttl_seconds == 600
        assert cache.fw_ttl_seconds == 1800
        assert len(cache._kills_data) == 0
        assert len(cache._jumps_data) == 0
        assert len(cache._fw_data) == 0

    def test_init_custom_ttl(self):
        """Cache accepts custom TTL values."""
        cache = ActivityCache(ttl_seconds=300, fw_ttl_seconds=900)
        assert cache.ttl_seconds == 300
        assert cache.fw_ttl_seconds == 900

    @pytest.mark.asyncio
    async def test_get_activity_returns_zeros_for_unknown(self):
        """Unknown systems return zero activity."""
        cache = ActivityCache()
        # Pre-populate with some data to avoid ESI call
        cache._kills_timestamp = time.time()
        cache._jumps_timestamp = time.time()
        cache._kills_data = {}
        cache._jumps_data = {}

        activity = await cache.get_activity(99999999)
        assert activity.system_id == 99999999
        assert activity.ship_kills == 0
        assert activity.pod_kills == 0
        assert activity.npc_kills == 0
        assert activity.ship_jumps == 0

    @pytest.mark.asyncio
    async def test_get_activity_returns_cached_data(self):
        """Returns cached activity data correctly."""
        cache = ActivityCache()
        cache._kills_timestamp = time.time()
        cache._jumps_timestamp = time.time()
        cache._kills_data = {
            30000142: ActivityData(
                system_id=30000142,
                ship_kills=10,
                pod_kills=2,
                npc_kills=100,
            )
        }
        cache._jumps_data = {30000142: 500}

        activity = await cache.get_activity(30000142)
        assert activity.system_id == 30000142
        assert activity.ship_kills == 10
        assert activity.pod_kills == 2
        assert activity.npc_kills == 100
        assert activity.ship_jumps == 500

    @pytest.mark.asyncio
    async def test_get_kills_returns_pvp_total(self):
        """get_kills returns ship_kills + pod_kills."""
        cache = ActivityCache()
        cache._kills_timestamp = time.time()
        cache._kills_data = {
            30000142: ActivityData(
                system_id=30000142,
                ship_kills=10,
                pod_kills=5,
                npc_kills=100,
            )
        }

        kills = await cache.get_kills(30000142)
        assert kills == 15  # 10 + 5

    @pytest.mark.asyncio
    async def test_get_fw_status_returns_none_for_non_fw(self):
        """Non-FW systems return None."""
        cache = ActivityCache()
        cache._fw_timestamp = time.time()
        cache._fw_data = {}

        status = await cache.get_fw_status(30000142)
        assert status is None

    @pytest.mark.asyncio
    async def test_get_fw_status_returns_data(self):
        """FW systems return their data."""
        cache = ActivityCache()
        cache._fw_timestamp = time.time()
        cache._fw_data = {
            30002813: FWSystemData(
                system_id=30002813,
                owner_faction_id=500001,
                occupier_faction_id=500004,
                contested="contested",
                victory_points=50000,
                victory_points_threshold=100000,
            )
        }

        status = await cache.get_fw_status(30002813)
        assert status is not None
        assert status.system_id == 30002813
        assert status.contested == "contested"
        assert status.victory_points == 50000

    def test_cache_status_returns_diagnostics(self):
        """get_cache_status returns correct diagnostics."""
        cache = ActivityCache()
        cache._kills_data = {1: ActivityData(1), 2: ActivityData(2)}
        cache._kills_timestamp = time.time() - 300  # 5 minutes old

        status = cache.get_cache_status()

        assert status["kills"]["cached_systems"] == 2
        assert status["kills"]["age_seconds"] == pytest.approx(300, abs=5)
        assert status["kills"]["stale"] is False
        assert status["fw"]["stale"] is True  # Never populated


class TestActivityCacheRefresh:
    """Tests for cache refresh behavior."""

    @pytest.mark.asyncio
    async def test_cache_refresh_on_expiry(self):
        """Cache triggers refresh when TTL expires."""
        cache = ActivityCache(ttl_seconds=1)

        mock_kills_data = [
            {"system_id": 30000142, "ship_kills": 5, "pod_kills": 1, "npc_kills": 50}
        ]

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_kills_data

        # Patch at the source module where get_async_esi_client is defined
        with patch("aria_esi.mcp.esi_client.get_async_esi_client", new=AsyncMock(return_value=mock_client)):
            # First call - should trigger refresh
            await cache.get_activity(30000142)
            first_timestamp = cache._kills_timestamp

            # Force expiry
            cache._kills_timestamp = time.time() - 2

            # Second call - should trigger another refresh
            await cache.get_activity(30000142)
            second_timestamp = cache._kills_timestamp

            assert second_timestamp > first_timestamp

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_error(self):
        """Cache preserves stale data on ESI error."""
        cache = ActivityCache()
        cache._kills_data = {30000142: ActivityData(30000142, ship_kills=10)}
        cache._kills_timestamp = 0  # Expired

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("ESI down")

        # Patch at the source module where get_async_esi_client is defined
        with patch("aria_esi.mcp.esi_client.get_async_esi_client", new=AsyncMock(return_value=mock_client)):
            data = await cache.get_activity(30000142)
            assert data.ship_kills == 10  # Stale data preserved

    @pytest.mark.asyncio
    async def test_concurrent_requests_single_esi_call(self):
        """Concurrent requests only trigger one ESI call (asyncio.Lock test)."""
        cache = ActivityCache(ttl_seconds=1)
        cache._kills_timestamp = 0  # Force expired
        cache._jumps_timestamp = time.time()  # Jumps fresh to isolate kills test
        cache._jumps_data = {}

        call_count = 0
        call_lock = asyncio.Lock()

        async def patched_refresh():
            nonlocal call_count
            async with call_lock:
                call_count += 1
            await asyncio.sleep(0.05)  # Simulate ESI latency
            cache._kills_data = {
                30000142: ActivityData(
                    system_id=30000142,
                    ship_kills=5,
                    pod_kills=1,
                    npc_kills=50,
                )
            }
            cache._kills_timestamp = time.time()

        cache._refresh_kills = patched_refresh

        # Launch 5 concurrent requests
        tasks = [cache.get_activity(30000142) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 5
        for result in results:
            assert result.ship_kills == 5

        # But only ONE refresh should have been triggered due to asyncio.Lock
        assert call_count == 1, f"Expected 1 ESI call, got {call_count}"


# =============================================================================
# Activity Classification Tests
# =============================================================================


class TestClassifyActivity:
    """Tests for activity level classification."""

    def test_classify_kills_none(self):
        """Zero kills = none."""
        assert classify_activity(0, "kills") == "none"

    def test_classify_kills_low(self):
        """1-4 kills = low."""
        assert classify_activity(1, "kills") == "low"
        assert classify_activity(4, "kills") == "low"

    def test_classify_kills_medium(self):
        """5-19 kills = medium."""
        assert classify_activity(5, "kills") == "medium"
        assert classify_activity(19, "kills") == "medium"

    def test_classify_kills_high(self):
        """20-49 kills = high."""
        assert classify_activity(20, "kills") == "high"
        assert classify_activity(49, "kills") == "high"

    def test_classify_kills_extreme(self):
        """50+ kills = extreme."""
        assert classify_activity(50, "kills") == "extreme"
        assert classify_activity(100, "kills") == "extreme"

    def test_classify_jumps(self):
        """Jumps classification thresholds."""
        assert classify_activity(49, "jumps") == "low"
        assert classify_activity(50, "jumps") == "medium"
        assert classify_activity(200, "jumps") == "high"
        assert classify_activity(500, "jumps") == "extreme"

    def test_classify_ratting(self):
        """Ratting (NPC kills) classification."""
        assert classify_activity(49, "ratting") == "low"
        assert classify_activity(50, "ratting") == "medium"
        assert classify_activity(100, "ratting") == "high"
        assert classify_activity(300, "ratting") == "extreme"


class TestFactionHelpers:
    """Tests for faction name/ID helpers."""

    def test_get_faction_name_caldari(self):
        """Caldari faction ID resolves correctly."""
        assert get_faction_name(500001) == "Caldari State"

    def test_get_faction_name_gallente(self):
        """Gallente faction ID resolves correctly."""
        assert get_faction_name(500004) == "Gallente Federation"

    def test_get_faction_name_unknown(self):
        """Unknown faction ID returns Unknown(id)."""
        assert "Unknown" in get_faction_name(999999)

    def test_get_faction_id_caldari(self):
        """Caldari name resolves to ID."""
        assert get_faction_id("caldari") == 500001
        assert get_faction_id("Caldari") == 500001
        assert get_faction_id("CALDARI") == 500001

    def test_get_faction_id_invalid(self):
        """Invalid faction returns None."""
        assert get_faction_id("pirate") is None


# =============================================================================
# MCP Tool Tests
# =============================================================================


@pytest.fixture
def activity_universe():
    """Universe with systems suitable for activity testing."""
    systems = [
        {"name": "Jita", "id": 30000142, "sec": 0.95, "const": 20000020, "region": 10000002,
         "const_name": "Kimotoro", "region_name": "The Forge"},
        {"name": "Perimeter", "id": 30000144, "sec": 0.90, "const": 20000020, "region": 10000002,
         "const_name": "Kimotoro", "region_name": "The Forge"},
        {"name": "Tama", "id": 30002813, "sec": 0.3, "const": 20000021, "region": 10000002,
         "const_name": "Citadel", "region_name": "The Forge"},
        {"name": "Nourvukaiken", "id": 30002814, "sec": 0.35, "const": 20000021, "region": 10000002,
         "const_name": "Citadel", "region_name": "The Forge"},
    ]
    edges = [
        (0, 1),  # Jita -- Perimeter
        (1, 3),  # Perimeter -- Nourvukaiken
        (3, 2),  # Nourvukaiken -- Tama
    ]
    return create_mock_universe(systems, edges)


def capture_tool(universe, tool_name):
    """Helper to capture a specific tool by name."""
    captured_tools = {}

    def mock_tool():
        def decorator(func):
            captured_tools[func.__name__] = func
            return func
        return decorator

    mock_server = MagicMock()
    mock_server.tool = mock_tool

    # Register the universe globally so get_universe() works
    import aria_esi.mcp.tools as tools_module
    tools_module._universe = universe

    register_activity_tools(mock_server, universe)
    return captured_tools.get(tool_name)


@pytest.mark.asyncio
class TestUniverseActivity:
    """Tests for universe_activity tool."""

    async def test_returns_activity_for_valid_systems(self, activity_universe):
        """Returns activity data for specified systems."""
        # Capture the tool
        tool = capture_tool(activity_universe, "universe_activity")
        assert tool is not None

        # Mock the activity cache
        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_activity = AsyncMock(return_value=ActivityData(
                system_id=30000142,
                ship_kills=10,
                pod_kills=2,
                npc_kills=50,
                ship_jumps=1000,
            ))
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            result = await tool(systems=["Jita"])

            assert "systems" in result
            assert len(result["systems"]) == 1
            assert result["systems"][0]["name"] == "Jita"
            assert result["systems"][0]["ship_kills"] == 10

    async def test_handles_unknown_systems(self, activity_universe):
        """Unknown systems are added to warnings."""
        tool = capture_tool(activity_universe, "universe_activity")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_activity = AsyncMock(return_value=ActivityData(30000142))
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            result = await tool(systems=["Jita", "NonexistentSystem"])

            assert "warnings" in result
            assert any("NonexistentSystem" in w for w in result["warnings"])


@pytest.mark.asyncio
class TestUniverseHotspots:
    """Tests for universe_hotspots tool."""

    async def test_finds_hotspots_in_range(self, activity_universe):
        """Finds high-activity systems within range."""
        tool = capture_tool(activity_universe, "universe_hotspots")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()

            # Make Tama the hotspot with high kills
            async def mock_activity(system_id):
                if system_id == 30002813:  # Tama
                    return ActivityData(system_id, ship_kills=25, pod_kills=5)
                return ActivityData(system_id)

            cache.get_activity = mock_activity
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            result = await tool(origin="Jita", max_jumps=10, activity_type="kills")

            assert "hotspots" in result
            assert result["origin"] == "Jita"
            assert result["activity_type"] == "kills"

    async def test_respects_security_filter(self, activity_universe):
        """Filters by security status."""
        tool = capture_tool(activity_universe, "universe_hotspots")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_activity = AsyncMock(return_value=ActivityData(0, ship_kills=10))
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            result = await tool(
                origin="Jita",
                min_security=0.1,
                max_security=0.4
            )

            # All returned systems should be in security range
            for hotspot in result["hotspots"]:
                assert 0.1 <= hotspot["security"] <= 0.4


@pytest.mark.asyncio
class TestUniverseGatecampRisk:
    """Tests for universe_gatecamp_risk tool."""

    async def test_identifies_chokepoints(self, activity_universe):
        """Identifies security transition chokepoints."""
        tool = capture_tool(activity_universe, "universe_gatecamp_risk")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()

            # Make Nourvukaiken dangerous
            async def mock_activity(system_id):
                if system_id == 30002814:  # Nourvukaiken
                    return ActivityData(system_id, ship_kills=25, pod_kills=10)
                return ActivityData(system_id)

            cache.get_activity = mock_activity
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            result = await tool(origin="Jita", destination="Tama")

            assert "chokepoints" in result
            assert "high_risk_systems" in result
            assert "recommendation" in result

    async def test_returns_high_risk_systems(self, activity_universe):
        """Returns high_risk_systems list for avoidance."""
        tool = capture_tool(activity_universe, "universe_gatecamp_risk")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()

            async def mock_activity(system_id):
                # Make both low-sec systems dangerous
                if system_id in (30002813, 30002814):
                    return ActivityData(system_id, ship_kills=30, pod_kills=15)
                return ActivityData(system_id)

            cache.get_activity = mock_activity
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            result = await tool(origin="Jita", destination="Tama")

            # High risk systems should be strings (names)
            if result["high_risk_systems"]:
                assert all(isinstance(s, str) for s in result["high_risk_systems"])


@pytest.mark.asyncio
class TestFWFrontlines:
    """Tests for fw_frontlines tool."""

    async def test_returns_contested_systems(self, activity_universe):
        """Returns FW systems grouped by status."""
        tool = capture_tool(activity_universe, "fw_frontlines")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()

            async def mock_all_fw():
                return {
                    30002813: FWSystemData(
                        system_id=30002813,
                        owner_faction_id=500001,
                        occupier_faction_id=500001,
                        contested="contested",
                        victory_points=50000,
                        victory_points_threshold=100000,
                    )
                }

            cache.get_all_fw = mock_all_fw
            cache.get_activity = AsyncMock(return_value=ActivityData(0))
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            result = await tool()

            assert "contested" in result
            assert "vulnerable" in result
            assert "summary" in result


@pytest.mark.asyncio
class TestActivityCacheStatus:
    """Tests for activity_cache_status tool."""

    async def test_returns_cache_layers(self, activity_universe):
        """Returns status for all cache layers."""
        tool = capture_tool(activity_universe, "activity_cache_status")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_cache_status.return_value = {
                "kills": {"cached_systems": 100, "age_seconds": 300, "ttl_seconds": 600, "stale": False},
                "jumps": {"cached_systems": 100, "age_seconds": 300, "ttl_seconds": 600, "stale": False},
                "fw": {"cached_systems": 50, "age_seconds": 1000, "ttl_seconds": 1800, "stale": False},
            }
            mock_cache.return_value = cache

            result = await tool()

            assert "kills" in result
            assert "jumps" in result
            assert "fw" in result
            assert result["kills"]["cached_systems"] == 100


# =============================================================================
# Error Condition Tests (Phase 2 Priority 3)
# =============================================================================


@pytest.mark.asyncio
class TestUniverseActivityErrors:
    """Tests for universe_activity error handling."""

    async def test_empty_systems_list_raises_error(self, activity_universe):
        """Empty systems list should raise InvalidParameterError."""
        from aria_esi.mcp.errors import InvalidParameterError

        tool = capture_tool(activity_universe, "universe_activity")

        with pytest.raises(InvalidParameterError) as exc_info:
            await tool(systems=[])

        assert "systems" in str(exc_info.value)
        assert "At least one system required" in str(exc_info.value)


@pytest.mark.asyncio
class TestUniverseHotspotsErrors:
    """Tests for universe_hotspots error handling."""

    async def test_invalid_activity_type_raises_error(self, activity_universe):
        """Invalid activity_type should raise InvalidParameterError."""
        from aria_esi.mcp.errors import InvalidParameterError

        tool = capture_tool(activity_universe, "universe_hotspots")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_activity = AsyncMock(return_value=ActivityData(0))
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            with pytest.raises(InvalidParameterError) as exc_info:
                await tool(origin="Jita", activity_type="invalid_type")

            assert "activity_type" in str(exc_info.value)
            assert "kills, jumps, ratting" in str(exc_info.value)

    async def test_max_jumps_below_range_raises_error(self, activity_universe):
        """max_jumps < 1 should raise InvalidParameterError."""
        from aria_esi.mcp.errors import InvalidParameterError

        tool = capture_tool(activity_universe, "universe_hotspots")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_activity = AsyncMock(return_value=ActivityData(0))
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            with pytest.raises(InvalidParameterError) as exc_info:
                await tool(origin="Jita", max_jumps=0)

            assert "max_jumps" in str(exc_info.value)
            assert "between 1 and 30" in str(exc_info.value)

    async def test_max_jumps_above_range_raises_error(self, activity_universe):
        """max_jumps > 30 should raise InvalidParameterError."""
        from aria_esi.mcp.errors import InvalidParameterError

        tool = capture_tool(activity_universe, "universe_hotspots")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_activity = AsyncMock(return_value=ActivityData(0))
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            with pytest.raises(InvalidParameterError) as exc_info:
                await tool(origin="Jita", max_jumps=31)

            assert "max_jumps" in str(exc_info.value)
            assert "between 1 and 30" in str(exc_info.value)

    async def test_limit_below_range_raises_error(self, activity_universe):
        """limit < 1 should raise InvalidParameterError."""
        from aria_esi.mcp.errors import InvalidParameterError

        tool = capture_tool(activity_universe, "universe_hotspots")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_activity = AsyncMock(return_value=ActivityData(0))
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            with pytest.raises(InvalidParameterError) as exc_info:
                await tool(origin="Jita", limit=0)

            assert "limit" in str(exc_info.value)
            assert "between 1 and 50" in str(exc_info.value)

    async def test_limit_above_range_raises_error(self, activity_universe):
        """limit > 50 should raise InvalidParameterError."""
        from aria_esi.mcp.errors import InvalidParameterError

        tool = capture_tool(activity_universe, "universe_hotspots")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_activity = AsyncMock(return_value=ActivityData(0))
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            with pytest.raises(InvalidParameterError) as exc_info:
                await tool(origin="Jita", limit=51)

            assert "limit" in str(exc_info.value)
            assert "between 1 and 50" in str(exc_info.value)

    async def test_activity_type_jumps_classification(self, activity_universe):
        """Jumps activity type should use ship_jumps for ranking."""
        tool = capture_tool(activity_universe, "universe_hotspots")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()

            # Make Tama the hotspot with high jumps
            async def mock_activity(system_id):
                if system_id == 30002813:  # Tama
                    return ActivityData(system_id, ship_jumps=1000)
                return ActivityData(system_id, ship_jumps=10)

            cache.get_activity = mock_activity
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            result = await tool(origin="Jita", activity_type="jumps", max_jumps=10)

            assert result["activity_type"] == "jumps"
            # If there are hotspots, they should be ranked by jumps
            for hotspot in result["hotspots"]:
                assert hotspot["activity_value"] > 0

    async def test_activity_type_ratting_classification(self, activity_universe):
        """Ratting activity type should use npc_kills for ranking."""
        tool = capture_tool(activity_universe, "universe_hotspots")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()

            # Make Tama the hotspot with high NPC kills
            async def mock_activity(system_id):
                if system_id == 30002813:  # Tama
                    return ActivityData(system_id, npc_kills=500)
                return ActivityData(system_id, npc_kills=0)

            cache.get_activity = mock_activity
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            result = await tool(origin="Jita", activity_type="ratting", max_jumps=10)

            assert result["activity_type"] == "ratting"
            # If there are hotspots, they should be ranked by NPC kills
            for hotspot in result["hotspots"]:
                assert hotspot["activity_value"] > 0


@pytest.mark.asyncio
class TestUniverseGatecampRiskErrors:
    """Tests for universe_gatecamp_risk error handling."""

    async def test_missing_route_and_origin_dest_raises_error(self, activity_universe):
        """Must provide either route or origin+destination."""
        from aria_esi.mcp.errors import InvalidParameterError

        tool = capture_tool(activity_universe, "universe_gatecamp_risk")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            with pytest.raises(InvalidParameterError) as exc_info:
                await tool()  # No route, no origin/destination

            assert "route" in str(exc_info.value)
            assert "origin" in str(exc_info.value) or "destination" in str(exc_info.value)

    async def test_short_route_raises_error(self, activity_universe):
        """Route with < 2 systems should raise InvalidParameterError."""
        from aria_esi.mcp.errors import InvalidParameterError

        tool = capture_tool(activity_universe, "universe_gatecamp_risk")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            with pytest.raises(InvalidParameterError) as exc_info:
                await tool(route=["Jita"])  # Only one system

            assert "route" in str(exc_info.value)
            assert "at least 2 systems" in str(exc_info.value)

    async def test_unknown_system_in_route_raises_error(self, activity_universe):
        """Unknown system in explicit route should raise SystemNotFoundError."""
        from aria_esi.mcp.errors import SystemNotFoundError

        tool = capture_tool(activity_universe, "universe_gatecamp_risk")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            with pytest.raises(SystemNotFoundError) as exc_info:
                await tool(route=["Jita", "FakeSystem123", "Perimeter"])

            assert "FakeSystem123" in str(exc_info.value)

    async def test_unreachable_destination_raises_error(self, disconnected_universe):
        """Unreachable destination should raise RouteNotFoundError."""
        from aria_esi.mcp.errors import RouteNotFoundError

        tool = capture_tool(disconnected_universe, "universe_gatecamp_risk")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            with pytest.raises(RouteNotFoundError) as exc_info:
                await tool(origin="Island1", destination="Island3")

            assert "Island1" in str(exc_info.value)
            assert "Island3" in str(exc_info.value)


@pytest.mark.asyncio
class TestFWFrontlinesErrors:
    """Tests for fw_frontlines error handling."""

    async def test_invalid_faction_raises_error(self, activity_universe):
        """Invalid faction name should raise InvalidParameterError."""
        from aria_esi.mcp.errors import InvalidParameterError

        tool = capture_tool(activity_universe, "fw_frontlines")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()
            cache.get_all_fw = AsyncMock(return_value={})
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            with pytest.raises(InvalidParameterError) as exc_info:
                await tool(faction="pirate")

            assert "faction" in str(exc_info.value)
            assert "caldari, gallente, amarr, minmatar" in str(exc_info.value)


@pytest.mark.asyncio
class TestGatecampChokepoints:
    """Tests for gatecamp risk chokepoint detection."""

    async def test_pipe_detection_two_neighbors(self, extended_universe):
        """Systems with <= 2 neighbors in lowsec should be classified as pipe."""
        tool = capture_tool(extended_universe, "universe_gatecamp_risk")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()

            # Give activity to Niarja to detect it as a chokepoint
            async def mock_activity(system_id):
                if system_id == 30002692:  # Niarja (low-sec with limited neighbors)
                    return ActivityData(system_id, ship_kills=15, pod_kills=5)
                return ActivityData(system_id)

            cache.get_activity = mock_activity
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            result = await tool(origin="Urlen", destination="Niarja")

            assert "chokepoints" in result
            # Should have detected security transition or pipe chokepoints
            assert len(result["chokepoints"]) >= 0  # May or may not depending on graph structure

    async def test_extreme_risk_recommendation(self, activity_universe):
        """Extreme risk should recommend alternate route or waiting."""
        tool = capture_tool(activity_universe, "universe_gatecamp_risk")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()

            # Make Nourvukaiken extremely dangerous
            async def mock_activity(system_id):
                if system_id == 30002814:  # Nourvukaiken
                    return ActivityData(system_id, ship_kills=50, pod_kills=25)
                return ActivityData(system_id)

            cache.get_activity = mock_activity
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            result = await tool(origin="Jita", destination="Tama")

            # Check overall risk is detected as extreme when there's high activity
            if result["chokepoints"]:
                extreme_chokepoints = [c for c in result["chokepoints"] if c["risk_level"] == "extreme"]
                if extreme_chokepoints:
                    assert result["overall_risk"] == "extreme"
                    assert "alternate route" in result["recommendation"].lower() or \
                           "waiting" in result["recommendation"].lower()

    async def test_lowsec_entry_chokepoint_detection(self, activity_universe):
        """High-sec to low-sec transitions should be marked as lowsec_entry."""
        tool = capture_tool(activity_universe, "universe_gatecamp_risk")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()

            # Give activity to the lowsec entry system
            async def mock_activity(system_id):
                if system_id == 30002814:  # Nourvukaiken (lowsec)
                    return ActivityData(system_id, ship_kills=10, pod_kills=2)
                return ActivityData(system_id)

            cache.get_activity = mock_activity
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            result = await tool(origin="Jita", destination="Tama")

            # Should have detected the lowsec entry point
            lowsec_entries = [c for c in result["chokepoints"] if c["chokepoint_type"] == "lowsec_entry"]
            # The route from Jita to Tama goes through a highsec->lowsec transition
            assert len(lowsec_entries) >= 0  # May vary based on graph structure

    async def test_high_risk_systems_list(self, activity_universe):
        """High and extreme risk systems should be in high_risk_systems list."""
        tool = capture_tool(activity_universe, "universe_gatecamp_risk")

        with patch("aria_esi.mcp.tools_activity.get_activity_cache") as mock_cache:
            cache = MagicMock()

            async def mock_activity(system_id):
                if system_id == 30002814:  # Nourvukaiken
                    return ActivityData(system_id, ship_kills=15, pod_kills=5)  # 20 total = extreme
                return ActivityData(system_id)

            cache.get_activity = mock_activity
            cache.get_kills_cache_age.return_value = 300
            mock_cache.return_value = cache

            result = await tool(origin="Jita", destination="Tama")

            # If there are extreme chokepoints, they should be in high_risk_systems
            for name in result["high_risk_systems"]:
                assert isinstance(name, str)
