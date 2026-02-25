"""
Tests for Market Orders MCP Tools (integration-style).

Tests item resolution, ESI order fetching, region handling,
sorting, spread calculation, and error responses for the
market_orders tool via register_order_tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.mcp.market.tools_orders import register_order_tools


# =============================================================================
# Test Fixtures
# =============================================================================


@dataclass
class TypeInfo:
    """Mock type info returned by resolve_type_name."""

    type_id: int
    type_name: str


@pytest.fixture
def order_tools():
    """Register order tools and yield tools dict with mocks."""
    server = MagicMock()
    tools = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    server.tool = tool_decorator

    with patch(
        "aria_esi.mcp.market.tools_orders.get_market_database"
    ) as mock_db_fn:
        register_order_tools(server)
        yield tools, mock_db_fn


def _make_esi_order(
    order_id: int,
    price: float,
    is_buy: bool,
    volume: int = 1000,
    location_id: int = 60003760,
    system_id: int = 30000142,
) -> dict:
    """Create a mock ESI order dict."""
    return {
        "order_id": order_id,
        "type_id": 34,
        "is_buy_order": is_buy,
        "price": price,
        "volume_remain": volume,
        "volume_total": volume * 2,
        "location_id": location_id,
        "system_id": system_id,
        "range": "station",
        "min_volume": 1,
        "duration": 90,
        "issued": "2026-02-01T00:00:00Z",
    }


# =============================================================================
# Happy Path Tests
# =============================================================================


class TestMarketOrdersHappyPath:
    """Tests for successful market_orders queries."""

    @pytest.mark.asyncio
    async def test_resolves_item_and_returns_orders(self, order_tools):
        """Resolves item name, fetches ESI orders, returns sorted result."""
        tools, mock_db_fn = order_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        buy_orders = [
            _make_esi_order(1, 5.50, True),
            _make_esi_order(2, 6.00, True),
            _make_esi_order(3, 5.80, True),
        ]
        sell_orders = [
            _make_esi_order(101, 7.00, False),
            _make_esi_order(102, 6.50, False),
            _make_esi_order(103, 6.80, False),
        ]

        mock_client = AsyncMock()

        async def mock_get(url, params=None):
            if params and params.get("order_type") == "buy":
                return buy_orders
            return sell_orders

        mock_client.get = mock_get

        with patch(
            "aria_esi.mcp.esi_client.get_async_esi_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await tools["market_orders"](item="Tritanium")

        assert result["type_name"] == "Tritanium"
        assert result["type_id"] == 34
        assert result["region"] == "The Forge"
        assert result["total_buy_orders"] == 3
        assert result["total_sell_orders"] == 3
        # Buy orders sorted descending: 6.00, 5.80, 5.50
        assert result["best_buy"] == 6.00
        # Sell orders sorted ascending: 6.50, 6.80, 7.00
        assert result["best_sell"] == 6.50
        assert result["spread"] == 0.50
        assert result["warnings"] == []

    @pytest.mark.asyncio
    async def test_buy_only_filter(self, order_tools):
        """When order_type='buy', only buy orders are fetched."""
        tools, mock_db_fn = order_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=[_make_esi_order(1, 5.50, True)])

        with patch(
            "aria_esi.mcp.esi_client.get_async_esi_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await tools["market_orders"](item="Tritanium", order_type="buy")

        assert result["total_buy_orders"] == 1
        assert result["total_sell_orders"] == 0
        assert result["best_sell"] is None


# =============================================================================
# Item Resolution Error Tests
# =============================================================================


class TestMarketOrdersItemResolution:
    """Tests for item resolution failures."""

    @pytest.mark.asyncio
    async def test_unknown_item_returns_type_not_found(self, order_tools):
        """Unknown item returns TYPE_NOT_FOUND error with suggestions."""
        tools, mock_db_fn = order_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = None
        db.find_type_suggestions.return_value = ["PLEX", "Compressed Nocxium"]

        result = await tools["market_orders"](item="Plex")

        assert result["error"]["code"] == "TYPE_NOT_FOUND"
        assert "Plex" in result["error"]["message"]
        assert "PLEX" in result["error"]["data"]["suggestions"]


# =============================================================================
# Region Handling Tests
# =============================================================================


class TestMarketOrdersRegionHandling:
    """Tests for region resolution in market_orders."""

    @pytest.mark.asyncio
    async def test_custom_region_id_bypasses_hub_resolution(self, order_tools):
        """Direct region_id bypasses trade hub resolution."""
        tools, mock_db_fn = order_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=[])

        with patch(
            "aria_esi.mcp.esi_client.get_async_esi_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await tools["market_orders"](
                item="Tritanium", region_id=10000057
            )

        assert result["region_id"] == 10000057
        assert result["region"] == "Region 10000057"


# =============================================================================
# ESI Error Handling Tests
# =============================================================================


class TestMarketOrdersESIErrors:
    """Tests for ESI error handling."""

    @pytest.mark.asyncio
    async def test_esi_client_error_returns_esi_unavailable(self, order_tools):
        """ESI client creation failure returns ESI_UNAVAILABLE."""
        tools, mock_db_fn = order_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        with patch(
            "aria_esi.mcp.esi_client.get_async_esi_client",
            new_callable=AsyncMock,
            side_effect=ConnectionError("ESI down"),
        ):
            result = await tools["market_orders"](item="Tritanium")

        assert result["error"]["code"] == "ESI_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_individual_order_fetch_error_produces_warning(self, order_tools):
        """Failure fetching one side of orders produces warning, not full error."""
        tools, mock_db_fn = order_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        mock_client = AsyncMock()
        call_count = 0

        async def mock_get(url, params=None):
            nonlocal call_count
            call_count += 1
            if params and params.get("order_type") == "buy":
                raise TimeoutError("Buy orders timed out")
            return [_make_esi_order(101, 7.00, False)]

        mock_client.get = mock_get

        with patch(
            "aria_esi.mcp.esi_client.get_async_esi_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await tools["market_orders"](item="Tritanium")

        assert len(result["warnings"]) >= 1
        assert "Buy orders unavailable" in result["warnings"][0]
        assert result["total_sell_orders"] == 1


# =============================================================================
# Limit Clamping Tests
# =============================================================================


class TestMarketOrdersLimitClamping:
    """Tests for order limit clamping behavior."""

    @pytest.mark.asyncio
    async def test_limit_clamps_output_count(self, order_tools):
        """Orders are limited to the requested count."""
        tools, mock_db_fn = order_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        # Return more orders than the limit
        sell_orders = [_make_esi_order(100 + i, 6.0 + i * 0.1, False) for i in range(10)]

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=sell_orders)

        with patch(
            "aria_esi.mcp.esi_client.get_async_esi_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await tools["market_orders"](
                item="Tritanium", order_type="sell", limit=3
            )

        assert len(result["sell_orders"]) == 3
        # Total reflects all orders found, not just limited
        assert result["total_sell_orders"] == 10
