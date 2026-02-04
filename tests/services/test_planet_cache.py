"""
Tests for Planet Cache Service.
"""

from pathlib import Path

import pytest

from aria_esi.services.planet_cache import (
    PLANET_TYPE_IDS,
    PlanetCacheService,
    _find_single_planet_options,
    _trace_to_p0,
    find_planets_for_product,
    find_planets_for_resource,
    get_planet_cache_service,
    get_resources_for_planet_type,
)


@pytest.fixture
def temp_cache_path(tmp_path: Path) -> Path:
    """Create a temporary cache path."""
    return tmp_path / "planet_types.json"


@pytest.fixture
def cache_service(temp_cache_path: Path) -> PlanetCacheService:
    """Create a cache service with temp path."""
    return PlanetCacheService(temp_cache_path)


@pytest.fixture
def sample_planets() -> list[dict]:
    """Sample planet data."""
    return [
        {"planet_id": 40001, "type_id": 2016, "type_name": "Barren"},
        {"planet_id": 40002, "type_id": 13, "type_name": "Gas"},
        {"planet_id": 40003, "type_id": 11, "type_name": "Temperate"},
    ]


class TestPlanetTypeConstants:
    """Test planet type ID mappings."""

    @pytest.mark.unit
    def test_planet_type_ids_complete(self):
        """Should have all standard planet types."""
        assert "Barren" in PLANET_TYPE_IDS.values()
        assert "Gas" in PLANET_TYPE_IDS.values()
        assert "Ice" in PLANET_TYPE_IDS.values()
        assert "Lava" in PLANET_TYPE_IDS.values()
        assert "Oceanic" in PLANET_TYPE_IDS.values()
        assert "Plasma" in PLANET_TYPE_IDS.values()
        assert "Storm" in PLANET_TYPE_IDS.values()
        assert "Temperate" in PLANET_TYPE_IDS.values()

    @pytest.mark.unit
    def test_planet_type_ids_has_8_types(self):
        """Should have exactly 8 planet types."""
        assert len(PLANET_TYPE_IDS) == 8


class TestPlanetCacheService:
    """Test PlanetCacheService functionality."""

    @pytest.mark.unit
    def test_load_cache_creates_empty_on_missing(self, cache_service: PlanetCacheService):
        """Should return empty cache when file doesn't exist."""
        cache = cache_service.load_cache()
        assert cache == {"systems": {}, "metadata": {}}

    @pytest.mark.unit
    def test_add_system(self, cache_service: PlanetCacheService, sample_planets: list):
        """Should add system to cache."""
        cache_service.add_system("Jita", 30000142, sample_planets)

        planets = cache_service.get_system_planets("Jita")
        assert planets is not None
        assert len(planets) == 3

    @pytest.mark.unit
    def test_case_insensitive_lookup(self, cache_service: PlanetCacheService, sample_planets: list):
        """Should support case-insensitive system lookup."""
        cache_service.add_system("Jita", 30000142, sample_planets)

        assert cache_service.get_system_planets("jita") is not None
        assert cache_service.get_system_planets("JITA") is not None
        assert cache_service.get_system_planets("JiTa") is not None

    @pytest.mark.unit
    def test_get_planet_types_in_system(self, cache_service: PlanetCacheService, sample_planets: list):
        """Should return set of planet types."""
        cache_service.add_system("Jita", 30000142, sample_planets)

        types = cache_service.get_planet_types_in_system("Jita")
        assert types == {"Barren", "Gas", "Temperate"}

    @pytest.mark.unit
    def test_is_system_cached(self, cache_service: PlanetCacheService, sample_planets: list):
        """Should correctly check if system is cached."""
        assert not cache_service.is_system_cached("Jita")

        cache_service.add_system("Jita", 30000142, sample_planets)

        assert cache_service.is_system_cached("Jita")
        assert cache_service.is_system_cached("jita")  # Case insensitive
        assert not cache_service.is_system_cached("Amarr")

    @pytest.mark.unit
    def test_save_and_load_cache(self, cache_service: PlanetCacheService, sample_planets: list):
        """Should persist cache to disk."""
        cache_service.add_system("Jita", 30000142, sample_planets)
        cache_service.save_cache()

        # Create new service with same path
        new_service = PlanetCacheService(cache_service.cache_path)
        planets = new_service.get_system_planets("Jita")

        assert planets is not None
        assert len(planets) == 3

    @pytest.mark.unit
    def test_save_updates_metadata(self, cache_service: PlanetCacheService, sample_planets: list):
        """Should update metadata on save."""
        cache_service.add_system("Jita", 30000142, sample_planets)
        cache_service.save_cache()

        stats = cache_service.get_cache_stats()
        assert stats["systems_count"] == 1
        assert stats["planets_count"] == 3
        assert "last_updated" in stats

    @pytest.mark.unit
    def test_find_systems_with_planet_types(self, cache_service: PlanetCacheService):
        """Should find systems with required planet types."""
        cache_service.add_system("System A", 1, [
            {"planet_id": 1, "type_name": "Barren"},
            {"planet_id": 2, "type_name": "Gas"},
        ])
        cache_service.add_system("System B", 2, [
            {"planet_id": 3, "type_name": "Barren"},
            {"planet_id": 4, "type_name": "Temperate"},
        ])
        cache_service.add_system("System C", 3, [
            {"planet_id": 5, "type_name": "Ice"},
        ])

        # Find systems with both Barren and Gas
        matches = cache_service.find_systems_with_planet_types({"Barren", "Gas"})
        assert len(matches) == 1
        assert matches[0]["system_name"] == "System A"

        # Find systems with just Barren
        matches = cache_service.find_systems_with_planet_types({"Barren"})
        assert len(matches) == 2

    @pytest.mark.unit
    def test_clear_cache(self, cache_service: PlanetCacheService, sample_planets: list):
        """Should clear all cached data."""
        cache_service.add_system("Jita", 30000142, sample_planets)
        cache_service.save_cache()

        assert cache_service.cache_path.exists()

        cache_service.clear_cache()

        assert not cache_service.cache_path.exists()
        assert cache_service.get_system_planets("Jita") is None


class TestResourceLookup:
    """Test resource and planet type lookups."""

    @pytest.mark.unit
    def test_get_resources_for_barren(self):
        """Should return correct resources for Barren planets."""
        resources = get_resources_for_planet_type("Barren")
        assert "Base Metals" in resources
        assert "Heavy Metals" in resources
        # Barren has 7 resources
        assert len(resources) == 7

    @pytest.mark.unit
    def test_get_resources_for_unknown_type(self):
        """Should return empty list for unknown type."""
        resources = get_resources_for_planet_type("Unknown")
        assert resources == []

    @pytest.mark.unit
    def test_find_planets_for_resource(self):
        """Should find planet types with a resource."""
        planets = find_planets_for_resource("Aqueous Liquids")
        assert "Barren" in planets
        assert "Gas" in planets
        assert "Temperate" in planets

    @pytest.mark.unit
    def test_find_planets_for_unknown_resource(self):
        """Should return empty list for unknown resource."""
        planets = find_planets_for_resource("Unknown Resource")
        assert planets == []


class TestProductLookup:
    """Test PI product tracing."""

    @pytest.mark.unit
    def test_find_planets_for_p1(self):
        """Should find planets for P1 product."""
        result = find_planets_for_product("Water")
        assert result["product_tier"] == "P1"
        assert "Aqueous Liquids" in result["required_p0"]

    @pytest.mark.unit
    def test_find_planets_for_p2(self):
        """Should find planets for P2 product."""
        result = find_planets_for_product("Mechanical Parts")
        assert result["product_tier"] == "P2"
        # Mechanical Parts needs Precious Metals + Reactive Metals
        # Which come from Noble Metals + Base Metals
        assert "Noble Metals" in result["required_p0"]
        assert "Base Metals" in result["required_p0"]

    @pytest.mark.unit
    def test_find_planets_for_p3(self):
        """Should find planets for P3 product."""
        result = find_planets_for_product("Robotics")
        assert result["product_tier"] == "P3"
        # Robotics needs Consumer Electronics + Mechanical Parts
        # Which traces back to 4 P0 resources
        assert len(result["required_p0"]) == 4

    @pytest.mark.unit
    def test_find_planets_for_unknown(self):
        """Should return error for unknown product."""
        result = find_planets_for_product("Unknown Product")
        assert "error" in result

    @pytest.mark.unit
    def test_single_planet_options(self):
        """Should find single-planet options when available."""
        result = find_planets_for_product("Mechanical Parts")
        # Mechanical Parts can be made on Barren or Plasma (both have Base + Noble Metals)
        assert len(result["single_planet_options"]) >= 1


class TestFactoryFunction:
    """Test factory function."""

    @pytest.mark.unit
    def test_get_planet_cache_service_default_path(self):
        """Should create service with default path."""
        service = get_planet_cache_service()
        assert isinstance(service, PlanetCacheService)

    @pytest.mark.unit
    def test_get_planet_cache_service_custom_path(self, tmp_path: Path):
        """Should accept custom cache path."""
        custom_path = tmp_path / "custom_cache.json"
        service = get_planet_cache_service(custom_path)
        assert service.cache_path == custom_path
