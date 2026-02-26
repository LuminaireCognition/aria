"""
Tests for Market NPC Sources MCP Tools (integration-style).

Tests item resolution, SDE seeding lookup, ESI fallback scanning,
corporation region mapping, NPC order filtering, and error handling
for the _npc_sources_impl function and register_npc_tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.mcp.market.tools_npc import (
    NPCOrder,
    NPCSourceInfo,
    NPCSourcesResult,
    _npc_sources_impl,
    register_npc_tools,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@dataclass
class TypeInfo:
    """Mock type info returned by resolve_type_name."""

    type_id: int
    type_name: str


@dataclass
class MockCorporationRegions:
    """Mock result from get_corporation_regions."""

    regions: list[tuple[int, str, int]]


@dataclass
class MockStationInfo:
    """Mock station info from get_stations_bulk."""

    corporation_id: int
    corporation_name: str
    station_name: str


def _mock_cursor_factory(rows, has_table=True):
    """Create a mock connection that returns specified cursor results."""
    conn = MagicMock()

    # Track calls to differentiate between table check and data queries
    call_count = 0

    def mock_execute(query, params=None):
        nonlocal call_count
        cursor = MagicMock()

        if "sqlite_master" in query:
            # Table existence check
            cursor.fetchone.return_value = ("npc_seeding",) if has_table else None
        elif "npc_seeding" in query and "npc_corporations" in query:
            # Seeding corps query
            cursor.fetchall.return_value = rows
        else:
            cursor.fetchall.return_value = []
            cursor.fetchone.return_value = None

        call_count += 1
        return cursor

    conn.execute = mock_execute
    return conn


@pytest.fixture
def npc_tools():
    """Register NPC tools and yield tools dict with mocks."""
    server = MagicMock()
    tools = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    server.tool = tool_decorator

    register_npc_tools(server)
    return tools


# =============================================================================
# Model Tests
# =============================================================================


class TestNPCModels:
    """Tests for NPC source data models."""

    def test_npc_order_creation(self):
        """NPCOrder can be created with valid data."""
        order = NPCOrder(
            order_id=1,
            price=100000.0,
            volume_remain=50,
            location_id=60003760,
            location_name="Jita IV - Moon 4",
            system_id=30000142,
            system_name="Jita",
            duration=365,
            is_npc=True,
        )

        assert order.order_id == 1
        assert order.price == 100000.0
        assert order.is_npc is True
        assert order.duration == 365

    def test_npc_source_info_creation(self):
        """NPCSourceInfo can be created with orders."""
        order = NPCOrder(
            order_id=1,
            price=100000.0,
            volume_remain=50,
            location_id=60003760,
            system_id=30000142,
            duration=365,
            is_npc=True,
        )
        source = NPCSourceInfo(
            corporation_id=1000125,
            corporation_name="Sisters of EVE",
            region_id=10000002,
            region_name="The Forge",
            orders=[order],
            order_count=1,
        )

        assert source.corporation_name == "Sisters of EVE"
        assert len(source.orders) == 1
        assert source.order_count == 1

    def test_npc_sources_result_found(self):
        """NPCSourcesResult with found sources."""
        result = NPCSourcesResult(
            type_id=34,
            type_name="Tritanium",
            found=True,
            sources=[],
            total_orders=0,
            warnings=[],
        )

        assert result.found is True
        assert result.type_id == 34

    def test_npc_sources_result_not_found(self):
        """NPCSourcesResult when no sources found."""
        result = NPCSourcesResult(
            type_id=34,
            type_name="Tritanium",
            found=False,
            sources=[],
            total_orders=0,
            warnings=["Not NPC-seeded"],
        )

        assert result.found is False
        assert len(result.warnings) == 1


# =============================================================================
# _npc_sources_impl: Item Resolution Tests
# =============================================================================


class TestNPCSourcesItemResolution:
    """Tests for item resolution in _npc_sources_impl."""

    @pytest.mark.asyncio
    async def test_unknown_item_returns_type_not_found(self):
        """Unknown item returns TYPE_NOT_FOUND error with suggestions."""
        mock_db = MagicMock()
        mock_db.resolve_type_name.return_value = None
        mock_db.find_type_suggestions.return_value = ["Pioneer Blueprint"]

        with patch(
            "aria_esi.mcp.market.tools_npc.get_market_database",
            return_value=mock_db,
        ):
            result = await _npc_sources_impl("Pioner Blueprint")

        assert result["error"]["code"] == "TYPE_NOT_FOUND"
        assert "Pioner Blueprint" in result["error"]["message"]
        assert "Pioneer Blueprint" in result["error"]["data"]["suggestions"]


# =============================================================================
# _npc_sources_impl: SDE Table Tests
# =============================================================================


class TestNPCSourcesSDE:
    """Tests for SDE npc_seeding table handling."""

    @pytest.mark.asyncio
    async def test_no_npc_seeding_table_returns_warning(self):
        """Missing npc_seeding table returns warning message."""
        mock_db = MagicMock()
        mock_db.resolve_type_name.return_value = TypeInfo(73790, "Pioneer Blueprint")
        mock_db._get_connection.return_value = _mock_cursor_factory([], has_table=False)

        with patch(
            "aria_esi.mcp.market.tools_npc.get_market_database",
            return_value=mock_db,
        ):
            result = await _npc_sources_impl("Pioneer Blueprint")

        assert result["found"] is False
        assert any("SDE data not seeded" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_no_seeding_corps_triggers_esi_fallback(self):
        """No seeding corps in SDE triggers ESI fallback scan."""
        mock_db = MagicMock()
        mock_db.resolve_type_name.return_value = TypeInfo(73790, "Pioneer Blueprint")
        mock_db._get_connection.return_value = _mock_cursor_factory([], has_table=True)

        with (
            patch(
                "aria_esi.mcp.market.tools_npc.get_market_database",
                return_value=mock_db,
            ),
            patch(
                "aria_esi.mcp.market.tools_npc._esi_fallback_scan",
                new_callable=AsyncMock,
                return_value=([], ["ESI fallback found nothing"], 0),
            ) as mock_fallback,
        ):
            result = await _npc_sources_impl("Pioneer Blueprint")

        mock_fallback.assert_awaited_once()
        assert result["found"] is False


# =============================================================================
# _npc_sources_impl: Happy Path Tests
# =============================================================================


class TestNPCSourcesHappyPath:
    """Tests for successful NPC source queries."""

    @pytest.mark.asyncio
    async def test_sde_corps_with_esi_orders(self):
        """SDE has corps, ESI returns NPC orders (364+ day duration)."""
        mock_db = MagicMock()
        mock_db.resolve_type_name.return_value = TypeInfo(73790, "Pioneer Blueprint")
        mock_db._get_connection.return_value = _mock_cursor_factory(
            [(1000125, "Sisters of EVE")], has_table=True
        )

        # Mock SDE query service for corp region lookup
        mock_query_service = MagicMock()
        mock_query_service.get_corporation_regions.return_value = MockCorporationRegions(
            regions=[(10000002, "The Forge", 5)]
        )

        # Mock ESI client returning NPC orders
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            return_value=[
                {
                    "order_id": 1001,
                    "price": 50000000.0,
                    "volume_remain": 100,
                    "location_id": 60003760,
                    "system_id": 30000142,
                    "duration": 365,
                    "type_id": 73790,
                },
                {
                    "order_id": 1002,
                    "price": 100.0,
                    "volume_remain": 500,
                    "location_id": 60003760,
                    "system_id": 30000142,
                    "duration": 30,  # Player order, should be filtered
                    "type_id": 73790,
                },
            ]
        )

        with (
            patch(
                "aria_esi.mcp.market.tools_npc.get_market_database",
                return_value=mock_db,
            ),
            patch(
                "aria_esi.mcp.market.tools_npc.get_sde_query_service",
                return_value=mock_query_service,
            ),
            patch(
                "aria_esi.store.esi_client.get_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
        ):
            result = await _npc_sources_impl("Pioneer Blueprint")

        assert result["found"] is True
        assert result["total_orders"] == 1  # Only the 365-day order
        assert len(result["sources"]) == 1
        assert result["sources"][0]["corporation_name"] == "Sisters of EVE"
        assert result["sources"][0]["orders"][0]["duration"] == 365

    @pytest.mark.asyncio
    async def test_limit_clamps_orders(self):
        """Limit parameter clamps the number of returned orders."""
        mock_db = MagicMock()
        mock_db.resolve_type_name.return_value = TypeInfo(73790, "Pioneer Blueprint")
        mock_db._get_connection.return_value = _mock_cursor_factory(
            [(1000125, "Sisters of EVE")], has_table=True
        )

        mock_query_service = MagicMock()
        mock_query_service.get_corporation_regions.return_value = MockCorporationRegions(
            regions=[(10000002, "The Forge", 5)]
        )

        # Return multiple NPC orders
        npc_orders = [
            {
                "order_id": 1000 + i,
                "price": 50000000.0 + i * 100,
                "volume_remain": 100,
                "location_id": 60003760,
                "system_id": 30000142,
                "duration": 365,
                "type_id": 73790,
            }
            for i in range(10)
        ]

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=npc_orders)

        with (
            patch(
                "aria_esi.mcp.market.tools_npc.get_market_database",
                return_value=mock_db,
            ),
            patch(
                "aria_esi.mcp.market.tools_npc.get_sde_query_service",
                return_value=mock_query_service,
            ),
            patch(
                "aria_esi.store.esi_client.get_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
        ):
            result = await _npc_sources_impl("Pioneer Blueprint", limit=3)

        assert result["total_orders"] == 3
        assert len(result["sources"][0]["orders"]) == 3


# =============================================================================
# _npc_sources_impl: Corporation Mapping Tests
# =============================================================================


class TestNPCSourcesCorpMapping:
    """Tests for corporation-to-region mapping."""

    @pytest.mark.asyncio
    async def test_unmapped_corps_use_empire_trade_hub_fallback(self):
        """Corps without region mapping fall back to empire trade hubs."""
        mock_db = MagicMock()
        mock_db.resolve_type_name.return_value = TypeInfo(34, "Tritanium Blueprint")
        mock_db._get_connection.return_value = _mock_cursor_factory(
            [(9999, "Unknown Corp")], has_table=True
        )

        # SDE returns no regions for this corp
        mock_query_service = MagicMock()
        mock_query_service.get_corporation_regions.return_value = MockCorporationRegions(
            regions=[]
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=[])

        with (
            patch(
                "aria_esi.mcp.market.tools_npc.get_market_database",
                return_value=mock_db,
            ),
            patch(
                "aria_esi.mcp.market.tools_npc.get_sde_query_service",
                return_value=mock_query_service,
            ),
            patch(
                "aria_esi.store.esi_client.get_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
            patch(
                "aria_esi.mcp.market.tools_npc._esi_fallback_scan",
                new_callable=AsyncMock,
                return_value=([], [], 0),
            ),
        ):
            result = await _npc_sources_impl("Tritanium Blueprint")

        # Should have warnings about fallback usage
        assert any("empire trade hub fallback" in w.lower() for w in result["warnings"])


# =============================================================================
# _npc_sources_impl: ESI Error Handling Tests
# =============================================================================


class TestNPCSourcesESIErrors:
    """Tests for ESI client error handling."""

    @pytest.mark.asyncio
    async def test_esi_client_creation_failure(self):
        """ESI client creation failure returns ESI_UNAVAILABLE."""
        mock_db = MagicMock()
        mock_db.resolve_type_name.return_value = TypeInfo(73790, "Pioneer Blueprint")
        mock_db._get_connection.return_value = _mock_cursor_factory(
            [(1000125, "Sisters of EVE")], has_table=True
        )

        mock_query_service = MagicMock()
        mock_query_service.get_corporation_regions.return_value = MockCorporationRegions(
            regions=[(10000002, "The Forge", 5)]
        )

        with (
            patch(
                "aria_esi.mcp.market.tools_npc.get_market_database",
                return_value=mock_db,
            ),
            patch(
                "aria_esi.mcp.market.tools_npc.get_sde_query_service",
                return_value=mock_query_service,
            ),
            patch(
                "aria_esi.store.esi_client.get_async_esi_client",
                new_callable=AsyncMock,
                side_effect=ConnectionError("ESI down"),
            ),
        ):
            result = await _npc_sources_impl("Pioneer Blueprint")

        assert result["error"]["code"] == "ESI_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_individual_region_query_failure_produces_warning(self):
        """Failure querying a single region produces warning, doesn't crash."""
        mock_db = MagicMock()
        mock_db.resolve_type_name.return_value = TypeInfo(73790, "Pioneer Blueprint")
        mock_db._get_connection.return_value = _mock_cursor_factory(
            [(1000125, "Sisters of EVE")], has_table=True
        )

        mock_query_service = MagicMock()
        mock_query_service.get_corporation_regions.return_value = MockCorporationRegions(
            regions=[
                (10000002, "The Forge", 5),
                (10000043, "Domain", 3),
            ]
        )

        mock_client = AsyncMock()
        call_count = 0

        async def mock_get(url, params=None):
            nonlocal call_count
            call_count += 1
            if "10000002" in url:
                raise TimeoutError("Region query timed out")
            return [
                {
                    "order_id": 2001,
                    "price": 50000000.0,
                    "volume_remain": 100,
                    "location_id": 60008494,
                    "system_id": 30002187,
                    "duration": 365,
                    "type_id": 73790,
                }
            ]

        mock_client.get = mock_get

        with (
            patch(
                "aria_esi.mcp.market.tools_npc.get_market_database",
                return_value=mock_db,
            ),
            patch(
                "aria_esi.mcp.market.tools_npc.get_sde_query_service",
                return_value=mock_query_service,
            ),
            patch(
                "aria_esi.store.esi_client.get_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
        ):
            result = await _npc_sources_impl("Pioneer Blueprint")

        # Should still succeed with the Domain result
        assert result["found"] is True
        assert result["total_orders"] == 1
        # Should have a warning about The Forge failure
        assert any("The Forge" in w for w in result["warnings"])


# =============================================================================
# Tool Registration Tests
# =============================================================================


class TestNPCToolRegistration:
    """Tests for register_npc_tools tool registration."""

    def test_tool_registered_with_correct_name(self, npc_tools):
        """market_npc_sources tool is registered."""
        assert "market_npc_sources" in npc_tools

    @pytest.mark.asyncio
    async def test_tool_delegates_to_impl(self, npc_tools):
        """Registered tool delegates to _npc_sources_impl."""
        with patch(
            "aria_esi.mcp.market.tools_npc._npc_sources_impl",
            new_callable=AsyncMock,
            return_value={"found": False},
        ) as mock_impl:
            result = await npc_tools["market_npc_sources"](item="Test", limit=5)

        mock_impl.assert_awaited_once_with("Test", 5)
        assert result == {"found": False}
