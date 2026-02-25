"""
Tests for core SDE bridge — callback registry for core → SDE decoupling.
"""

from __future__ import annotations

import pytest

from aria_esi.core.sde_bridge import (
    get_ship_group_ids_from_sde,
    get_station_name_from_sde,
    register_ship_group_ids_provider,
    register_station_name_provider,
    reset_sde_bridge,
)


@pytest.fixture(autouse=True)
def _clean_bridge():
    """Reset bridge state before and after each test."""
    reset_sde_bridge()
    yield
    reset_sde_bridge()


class TestShipGroupIdsBridge:
    """Tests for ship group IDs provider."""

    def test_no_provider_returns_none(self):
        """Without a registered provider, returns None."""
        assert get_ship_group_ids_from_sde() is None

    def test_provider_returns_data(self):
        """Registered provider returns its data."""
        register_ship_group_ids_provider(lambda: {25, 26, 27})
        result = get_ship_group_ids_from_sde()
        assert result == {25, 26, 27}

    def test_provider_exception_returns_none(self):
        """If provider raises, returns None instead of propagating."""

        def bad_provider():
            raise RuntimeError("SDE unavailable")

        register_ship_group_ids_provider(bad_provider)
        assert get_ship_group_ids_from_sde() is None


class TestStationNameBridge:
    """Tests for station name provider."""

    def test_no_provider_returns_none(self):
        """Without a registered provider, returns None."""
        assert get_station_name_from_sde(60003760) is None

    def test_provider_returns_name(self):
        """Registered provider returns station name."""
        names = {60003760: "Jita IV - Moon 4 - Caldari Navy Assembly Plant"}
        register_station_name_provider(lambda sid: names.get(sid))
        assert get_station_name_from_sde(60003760) == "Jita IV - Moon 4 - Caldari Navy Assembly Plant"

    def test_provider_returns_none_for_unknown(self):
        """Provider returns None for unknown station."""
        register_station_name_provider(lambda sid: None)
        assert get_station_name_from_sde(99999) is None

    def test_provider_exception_returns_none(self):
        """If provider raises, returns None."""

        def bad_provider(sid):
            raise RuntimeError("DB error")

        register_station_name_provider(bad_provider)
        assert get_station_name_from_sde(60003760) is None


class TestResetBridge:
    """Tests for reset functionality."""

    def test_reset_clears_providers(self):
        """After reset, providers are gone."""
        register_ship_group_ids_provider(lambda: {1, 2, 3})
        register_station_name_provider(lambda sid: "test")

        assert get_ship_group_ids_from_sde() == {1, 2, 3}
        assert get_station_name_from_sde(1) == "test"

        reset_sde_bridge()

        assert get_ship_group_ids_from_sde() is None
        assert get_station_name_from_sde(1) is None
