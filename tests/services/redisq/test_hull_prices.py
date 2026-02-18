"""Tests for ShipPriceLookup service."""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.hull_prices import ShipPriceLookup


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
