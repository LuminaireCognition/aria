"""Tests for ShipPriceLookup service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from aria_esi.services.redisq.hull_prices import (
    ShipPriceLookup,
    get_ship_price_lookup,
    reset_ship_price_lookup,
)


class TestShipPriceLookup:
    """Tests for ShipPriceLookup."""

    def test_get_hull_value_found(self) -> None:
        """Test returns price for known ship."""
        lookup = ShipPriceLookup()
        # Manually populate for testing
        lookup._prices = {24690: 15_000_000.0, 17736: 1_200_000_000.0}
        lookup._loaded = True

        assert lookup.get_hull_value(24690) == 15_000_000.0
        assert lookup.get_hull_value(17736) == 1_200_000_000.0

    def test_get_hull_value_not_found(self) -> None:
        """Test returns None for non-ship type."""
        lookup = ShipPriceLookup()
        lookup._prices = {24690: 15_000_000.0}
        lookup._loaded = True

        assert lookup.get_hull_value(99999) is None

    def test_get_hull_value_empty(self) -> None:
        """Test returns None before load()."""
        lookup = ShipPriceLookup()
        assert lookup.get_hull_value(24690) is None
        assert lookup.is_loaded is False
        assert lookup.ship_count == 0

    def test_ship_count(self) -> None:
        """Test ship_count property."""
        lookup = ShipPriceLookup()
        lookup._prices = {1: 100.0, 2: 200.0, 3: 300.0}
        assert lookup.ship_count == 3

    def test_is_loaded_default(self) -> None:
        """Test is_loaded is False by default."""
        lookup = ShipPriceLookup()
        assert lookup.is_loaded is False

    def test_is_loaded_after_manual_set(self) -> None:
        """Test is_loaded after setting."""
        lookup = ShipPriceLookup()
        lookup._loaded = True
        assert lookup.is_loaded is True


class TestShipPriceLookupLoad:
    """Tests for ShipPriceLookup.load() async method."""

    @pytest.mark.asyncio
    async def test_load_success(self) -> None:
        """Test successful load from ESI."""
        lookup = ShipPriceLookup()

        # Mock _get_ship_type_ids to return known ships
        ship_type_ids = {24690, 17740, 17812}  # Vexor, Hurricane, Brutix
        esi_response = [
            {"type_id": 24690, "adjusted_price": 15_000_000.0},
            {"type_id": 17740, "adjusted_price": 45_000_000.0},
            {"type_id": 17812, "adjusted_price": 35_000_000.0},
            {"type_id": 34, "adjusted_price": 5.0},  # Tritanium - not a ship
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = esi_response

        with (
            patch.object(lookup, "_get_ship_type_ids", return_value=ship_type_ids),
            patch("aria_esi.services.redisq.hull_prices.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = MagicMock()
            mock_client.__aenter__ = lambda self: self._async_enter()
            mock_client._async_enter = lambda: _async_return(mock_client)
            mock_client.__aexit__ = lambda self, *args: _async_return(None)
            mock_client.get = lambda url: _async_return(mock_response)
            mock_client_cls.return_value = mock_client

            await lookup.load()

        assert lookup.is_loaded is True
        assert lookup.ship_count == 3
        assert lookup.get_hull_value(24690) == 15_000_000.0
        assert lookup.get_hull_value(17740) == 45_000_000.0
        assert lookup.get_hull_value(34) is None  # Not a ship

    @pytest.mark.asyncio
    async def test_load_empty_sde(self) -> None:
        """Test load with no ship type_ids from SDE."""
        lookup = ShipPriceLookup()

        with patch.object(lookup, "_get_ship_type_ids", return_value=set()):
            await lookup.load()

        assert lookup.is_loaded is True
        assert lookup.ship_count == 0

    @pytest.mark.asyncio
    async def test_load_esi_error_status(self) -> None:
        """Test load with non-200 ESI response."""
        lookup = ShipPriceLookup()

        mock_response = MagicMock()
        mock_response.status_code = 503

        with (
            patch.object(lookup, "_get_ship_type_ids", return_value={24690}),
            patch("aria_esi.services.redisq.hull_prices.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = MagicMock()
            mock_client.__aenter__ = lambda self: _async_return(mock_client)
            mock_client.__aexit__ = lambda self, *args: _async_return(None)
            mock_client.get = lambda url: _async_return(mock_response)
            mock_client_cls.return_value = mock_client

            await lookup.load()

        assert lookup.is_loaded is True
        assert lookup.ship_count == 0

    @pytest.mark.asyncio
    async def test_load_network_exception(self) -> None:
        """Test load with network exception."""
        lookup = ShipPriceLookup()

        with (
            patch.object(lookup, "_get_ship_type_ids", return_value={24690}),
            patch("aria_esi.services.redisq.hull_prices.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = MagicMock()
            mock_client.__aenter__ = lambda self: _async_return(mock_client)
            mock_client.__aexit__ = lambda self, *args: _async_return(None)
            mock_client.get = lambda url: _async_raise(httpx.ConnectError("Connection refused"))
            mock_client_cls.return_value = mock_client

            await lookup.load()

        assert lookup.is_loaded is True
        assert lookup.ship_count == 0

    @pytest.mark.asyncio
    async def test_load_filters_entries_without_adjusted_price(self) -> None:
        """Test load skips entries missing adjusted_price."""
        lookup = ShipPriceLookup()

        esi_response = [
            {"type_id": 24690, "adjusted_price": 15_000_000.0},
            {"type_id": 17740},  # No adjusted_price
            {"type_id": 17812, "adjusted_price": None},  # Explicit None
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = esi_response

        with (
            patch.object(
                lookup, "_get_ship_type_ids", return_value={24690, 17740, 17812}
            ),
            patch("aria_esi.services.redisq.hull_prices.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = MagicMock()
            mock_client.__aenter__ = lambda self: _async_return(mock_client)
            mock_client.__aexit__ = lambda self, *args: _async_return(None)
            mock_client.get = lambda url: _async_return(mock_response)
            mock_client_cls.return_value = mock_client

            await lookup.load()

        assert lookup.ship_count == 1
        assert lookup.get_hull_value(24690) == 15_000_000.0
        assert lookup.get_hull_value(17740) is None


class TestGetShipTypIds:
    """Tests for ShipPriceLookup._get_ship_type_ids."""

    def test_sde_exception_returns_empty(self) -> None:
        """Test returns empty set if SDE query fails."""
        lookup = ShipPriceLookup()

        with patch(
            "aria_esi.mcp.market.database.get_market_database",
            side_effect=RuntimeError("No SDE"),
        ):
            result = lookup._get_ship_type_ids()

        assert result == set()


class TestSingleton:
    """Tests for module-level singleton functions."""

    def test_get_ship_price_lookup_creates_instance(self) -> None:
        """Test get_ship_price_lookup creates new instance."""
        reset_ship_price_lookup()
        try:
            lookup = get_ship_price_lookup()
            assert isinstance(lookup, ShipPriceLookup)
        finally:
            reset_ship_price_lookup()

    def test_get_ship_price_lookup_returns_same_instance(self) -> None:
        """Test get_ship_price_lookup returns same instance on repeated calls."""
        reset_ship_price_lookup()
        try:
            lookup1 = get_ship_price_lookup()
            lookup2 = get_ship_price_lookup()
            assert lookup1 is lookup2
        finally:
            reset_ship_price_lookup()

    def test_reset_creates_new_instance(self) -> None:
        """Test reset_ship_price_lookup allows new instance creation."""
        reset_ship_price_lookup()
        try:
            lookup1 = get_ship_price_lookup()
            reset_ship_price_lookup()
            lookup2 = get_ship_price_lookup()
            assert lookup1 is not lookup2
        finally:
            reset_ship_price_lookup()


# =============================================================================
# Async helpers
# =============================================================================


async def _async_return(value):
    """Helper to return a value from an async context."""
    return value


async def _async_raise(exc):
    """Helper to raise an exception from an async context."""
    raise exc
