"""
Tests for Market Dispatcher Action Implementations.

Tests the parameter validation for market dispatcher actions.
Implementation tests are intentionally limited to validation logic
to avoid brittle mocking of internal functions.
"""

from __future__ import annotations

import asyncio

import pytest

from aria_esi.mcp.errors import InvalidParameterError


# =============================================================================
# Prices Action Tests
# =============================================================================


class TestPricesAction:
    """Tests for market prices action."""

    def test_prices_requires_items(self, market_dispatcher):
        """Prices action requires items parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="prices"))

        assert "items" in str(exc.value).lower()

    def test_prices_empty_items_raises_error(self, market_dispatcher):
        """Empty items list raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="prices", items=[]))

        assert "items" in str(exc.value).lower()


# =============================================================================
# Orders Action Tests
# =============================================================================


class TestOrdersAction:
    """Tests for market orders action."""

    def test_orders_requires_item(self, market_dispatcher):
        """Orders action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="orders"))

        assert "item" in str(exc.value).lower()


# =============================================================================
# Valuation Action Tests
# =============================================================================


class TestValuationAction:
    """Tests for market valuation action."""

    def test_valuation_requires_items(self, market_dispatcher):
        """Valuation action requires items parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="valuation"))

        assert "items" in str(exc.value).lower()


# =============================================================================
# Spread Action Tests
# =============================================================================


class TestSpreadAction:
    """Tests for market spread action."""

    def test_spread_requires_items(self, market_dispatcher):
        """Spread action requires items parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="spread"))

        assert "items" in str(exc.value).lower()


# =============================================================================
# History Action Tests
# =============================================================================


class TestHistoryAction:
    """Tests for market history action."""

    def test_history_requires_item(self, market_dispatcher):
        """History action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="history"))

        assert "item" in str(exc.value).lower()


# =============================================================================
# Find Nearby Action Tests
# =============================================================================


class TestFindNearbyAction:
    """Tests for market find_nearby action."""

    def test_find_nearby_requires_item(self, market_dispatcher):
        """Find nearby requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="find_nearby", origin="Jita"))

        assert "item" in str(exc.value).lower()

    def test_find_nearby_requires_origin(self, market_dispatcher):
        """Find nearby requires origin parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="find_nearby", item="Tritanium"))

        assert "origin" in str(exc.value).lower()


# =============================================================================
# NPC Sources Action Tests
# =============================================================================


class TestNPCSourcesAction:
    """Tests for market npc_sources action."""

    def test_npc_sources_requires_item(self, market_dispatcher):
        """NPC sources requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="npc_sources"))

        assert "item" in str(exc.value).lower()


# =============================================================================
# Arbitrage Detail Action Tests
# =============================================================================


class TestArbitrageDetailAction:
    """Tests for market arbitrage_detail action."""

    def test_arbitrage_detail_requires_type_name(self, market_dispatcher):
        """Arbitrage detail requires type_name."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                market_dispatcher(
                    action="arbitrage_detail",
                    buy_region="jita",
                    sell_region="amarr"
                )
            )

        assert "type_name" in str(exc.value).lower()

    def test_arbitrage_detail_requires_buy_region(self, market_dispatcher):
        """Arbitrage detail requires buy_region."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                market_dispatcher(
                    action="arbitrage_detail",
                    type_name="Tritanium",
                    sell_region="amarr"
                )
            )

        assert "buy_region" in str(exc.value).lower()

    def test_arbitrage_detail_requires_sell_region(self, market_dispatcher):
        """Arbitrage detail requires sell_region."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                market_dispatcher(
                    action="arbitrage_detail",
                    type_name="Tritanium",
                    buy_region="jita"
                )
            )

        assert "sell_region" in str(exc.value).lower()


# =============================================================================
# Route Value Action Tests
# =============================================================================


class TestRouteValueAction:
    """Tests for market route_value action."""

    def test_route_value_requires_items(self, market_dispatcher):
        """Route value requires items parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                market_dispatcher(
                    action="route_value",
                    route=["Jita", "Amarr"]
                )
            )

        assert "items" in str(exc.value).lower()

    def test_route_value_requires_route(self, market_dispatcher):
        """Route value requires route parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                market_dispatcher(
                    action="route_value",
                    items=[{"name": "Tritanium", "quantity": 1000}]
                )
            )

        assert "route" in str(exc.value).lower()


# =============================================================================
# Watchlist Action Tests
# =============================================================================


class TestWatchlistCreateAction:
    """Tests for market watchlist_create action."""

    def test_watchlist_create_requires_name(self, market_dispatcher):
        """Watchlist create requires name parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="watchlist_create"))

        assert "name" in str(exc.value).lower()


class TestWatchlistAddItemAction:
    """Tests for market watchlist_add_item action."""

    def test_watchlist_add_item_requires_watchlist_name(self, market_dispatcher):
        """Watchlist add item requires watchlist_name."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                market_dispatcher(action="watchlist_add_item", item_name="Tritanium")
            )

        assert "watchlist_name" in str(exc.value).lower()

    def test_watchlist_add_item_requires_item_name(self, market_dispatcher):
        """Watchlist add item requires item_name."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                market_dispatcher(action="watchlist_add_item", watchlist_name="test")
            )

        assert "item_name" in str(exc.value).lower()


class TestWatchlistGetAction:
    """Tests for market watchlist_get action."""

    def test_watchlist_get_requires_name(self, market_dispatcher):
        """Watchlist get requires name parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="watchlist_get"))

        assert "name" in str(exc.value).lower()


class TestWatchlistDeleteAction:
    """Tests for market watchlist_delete action."""

    def test_watchlist_delete_requires_name(self, market_dispatcher):
        """Watchlist delete requires name parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="watchlist_delete"))

        assert "name" in str(exc.value).lower()


# =============================================================================
# Scope Action Tests
# =============================================================================


class TestScopeCreateAction:
    """Tests for market scope_create action."""

    def test_scope_create_requires_name(self, market_dispatcher):
        """Scope create requires name parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                market_dispatcher(
                    action="scope_create",
                    scope_type="station",
                    location_id=60003760,
                    watchlist_name="test"
                )
            )

        assert "name" in str(exc.value).lower()

    def test_scope_create_requires_scope_type(self, market_dispatcher):
        """Scope create requires scope_type parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                market_dispatcher(
                    action="scope_create",
                    name="test_scope",
                    location_id=60003760,
                    watchlist_name="test"
                )
            )

        assert "scope_type" in str(exc.value).lower()

    def test_scope_create_requires_location_id(self, market_dispatcher):
        """Scope create requires location_id parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                market_dispatcher(
                    action="scope_create",
                    name="test_scope",
                    scope_type="station",
                    watchlist_name="test"
                )
            )

        assert "location_id" in str(exc.value).lower()

    def test_scope_create_requires_watchlist_name(self, market_dispatcher):
        """Scope create requires watchlist_name parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                market_dispatcher(
                    action="scope_create",
                    name="test_scope",
                    scope_type="station",
                    location_id=60003760
                )
            )

        assert "watchlist_name" in str(exc.value).lower()


class TestScopeDeleteAction:
    """Tests for market scope_delete action."""

    def test_scope_delete_requires_name(self, market_dispatcher):
        """Scope delete requires name parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="scope_delete"))

        assert "name" in str(exc.value).lower()


class TestScopeRefreshAction:
    """Tests for market scope_refresh action."""

    def test_scope_refresh_requires_scope_name(self, market_dispatcher):
        """Scope refresh requires scope_name parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="scope_refresh"))

        assert "scope_name" in str(exc.value).lower()


# =============================================================================
# Invalid Action Tests
# =============================================================================


class TestMarketInvalidActions:
    """Tests for invalid action handling."""

    def test_invalid_action_raises_error(self, market_dispatcher):
        """Unknown action raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="nonexistent_action"))

        assert "action" in str(exc.value)
        assert "must be one of" in str(exc.value).lower()

    def test_empty_action_raises_error(self, market_dispatcher):
        """Empty action raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action=""))

        assert "action" in str(exc.value)
