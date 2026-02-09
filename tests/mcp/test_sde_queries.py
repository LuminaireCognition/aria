"""
Unit Tests for SDEQueryService.

These tests use mock data to test the query service without requiring
a seeded database. For integration tests with real data, see
tests/integration/test_sde_data_integrity.py.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.mcp.sde.queries import (
    CorporationRegions,
    SDENotSeededError,
    SDEQueryService,
    get_sde_query_service,
    reset_sde_query_service,
)


@pytest.fixture
def mock_db():
    """Create a mock database with SDE tables."""
    # Create an in-memory SQLite database with mock data
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create tables
    conn.executescript(
        """
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO metadata VALUES ('sde_import_timestamp', '2024-01-01T00:00:00Z');

        CREATE TABLE npc_corporations (
            corporation_id INTEGER PRIMARY KEY,
            corporation_name TEXT,
            corporation_name_lower TEXT,
            faction_id INTEGER
        );

        CREATE TABLE stations (
            station_id INTEGER PRIMARY KEY,
            station_name TEXT,
            station_name_lower TEXT,
            system_id INTEGER,
            region_id INTEGER,
            corporation_id INTEGER
        );

        CREATE TABLE regions (
            region_id INTEGER PRIMARY KEY,
            region_name TEXT,
            region_name_lower TEXT
        );

        CREATE TABLE npc_seeding (
            type_id INTEGER,
            corporation_id INTEGER,
            PRIMARY KEY (type_id, corporation_id)
        );

        CREATE TABLE categories (
            category_id INTEGER PRIMARY KEY,
            category_name TEXT,
            category_name_lower TEXT
        );

        -- Insert test data
        INSERT INTO regions VALUES (10000057, 'Outer Ring', 'outer ring');
        INSERT INTO regions VALUES (10000002, 'The Forge', 'the forge');
        INSERT INTO regions VALUES (10000041, 'Syndicate', 'syndicate');

        INSERT INTO npc_corporations VALUES (1000129, 'Outer Ring Excavations', 'outer ring excavations', 500014);
        INSERT INTO npc_corporations VALUES (1000130, 'Sisters of EVE', 'sisters of eve', 500003);

        INSERT INTO stations VALUES (60015140, 'ORE Station 1', 'ore station 1', 30001, 10000057, 1000129);
        INSERT INTO stations VALUES (60015141, 'ORE Station 2', 'ore station 2', 30002, 10000057, 1000129);
        INSERT INTO stations VALUES (60015142, 'Sisters Station 1', 'sisters station 1', 30003, 10000041, 1000130);
        INSERT INTO stations VALUES (60015143, 'Sisters Station 2', 'sisters station 2', 30004, 10000002, 1000130);

        INSERT INTO npc_seeding VALUES (32881, 1000129);  -- Venture Blueprint by ORE
        INSERT INTO npc_seeding VALUES (32881, 1000115);  -- Venture Blueprint by Univ Caille

        INSERT INTO categories VALUES (6, 'Ship', 'ship');
        INSERT INTO categories VALUES (9, 'Blueprint', 'blueprint');
        """
    )
    conn.commit()

    # Mock database object
    mock = MagicMock()
    mock._get_connection.return_value = conn
    yield mock
    conn.close()


@pytest.fixture
def query_service(mock_db):
    """Create a query service with mock database."""
    return SDEQueryService(mock_db)


class TestCorporationRegions:
    """Test CorporationRegions data class."""

    def test_primary_region_id(self):
        """Primary region should be first in list."""
        regions = CorporationRegions(
            corporation_id=1000129,
            corporation_name="Outer Ring Excavations",
            regions=((10000057, "Outer Ring", 4), (10000002, "The Forge", 2)),
        )

        assert regions.primary_region_id == 10000057
        assert regions.primary_region_name == "Outer Ring"

    def test_empty_regions(self):
        """Empty regions should return None for primary."""
        regions = CorporationRegions(
            corporation_id=1000129,
            corporation_name="Outer Ring Excavations",
            regions=(),
        )

        assert regions.primary_region_id is None
        assert regions.primary_region_name is None

    def test_total_stations(self):
        """Total stations should sum all regions."""
        regions = CorporationRegions(
            corporation_id=1000129,
            corporation_name="Outer Ring Excavations",
            regions=((10000057, "Outer Ring", 4), (10000002, "The Forge", 2)),
        )

        assert regions.total_stations == 6

    def test_immutable(self):
        """CorporationRegions should be frozen."""
        regions = CorporationRegions(
            corporation_id=1000129,
            corporation_name="Outer Ring Excavations",
            regions=(),
        )

        with pytest.raises(AttributeError):
            regions.corporation_id = 999


class TestSDEQueryService:
    """Test SDEQueryService methods."""

    def test_get_corporation_regions_found(self, query_service):
        """Should return regions for existing corporation."""
        result = query_service.get_corporation_regions(1000129)

        assert result is not None
        assert result.corporation_id == 1000129
        assert result.corporation_name == "Outer Ring Excavations"
        assert result.primary_region_name == "Outer Ring"
        assert len(result.regions) == 1  # Only Outer Ring in our test data
        assert result.total_stations == 2

    def test_get_corporation_regions_not_found(self, query_service):
        """Should return None for non-existent corporation."""
        result = query_service.get_corporation_regions(999999999)
        assert result is None

    def test_get_corporation_regions_cached(self, query_service):
        """Repeated calls should return cached result."""
        result1 = query_service.get_corporation_regions(1000129)
        result2 = query_service.get_corporation_regions(1000129)

        assert result1 is result2  # Same object (cached)

    def test_get_npc_seeding_corporations(self, query_service):
        """Should return seeding corporations for item."""
        result = query_service.get_npc_seeding_corporations(32881)

        # Our mock data has one seeding entry for ORE
        assert len(result) >= 1
        corp_ids = [corp_id for corp_id, _ in result]
        assert 1000129 in corp_ids

    def test_get_npc_seeding_corporations_not_found(self, query_service):
        """Should return empty tuple for non-seeded item."""
        result = query_service.get_npc_seeding_corporations(999999)
        assert result == ()

    def test_get_category_id(self, query_service):
        """Should return category ID by name."""
        assert query_service.get_category_id("Ship") == 6
        assert query_service.get_category_id("Blueprint") == 9

    def test_get_category_id_case_insensitive(self, query_service):
        """Category lookup should be case-insensitive."""
        assert query_service.get_category_id("ship") == 6
        assert query_service.get_category_id("SHIP") == 6

    def test_get_category_id_not_found(self, query_service):
        """Should return None for non-existent category."""
        result = query_service.get_category_id("NonExistent")
        assert result is None

    def test_invalidate_all(self, query_service):
        """Invalidate should clear all caches."""
        # Populate caches
        query_service.get_corporation_regions(1000129)
        query_service.get_category_id("Ship")

        assert len(query_service._corp_regions) > 0
        assert len(query_service._category_ids) > 0

        # Invalidate
        query_service.invalidate_all()

        assert len(query_service._corp_regions) == 0
        assert len(query_service._category_ids) == 0
        assert query_service._cache_import_timestamp is None

    def test_cache_invalidation_on_timestamp_change(self, query_service):
        """Cache should invalidate when import timestamp changes."""
        # Populate cache
        result1 = query_service.get_corporation_regions(1000129)
        assert 1000129 in query_service._corp_regions

        # Simulate timestamp change
        query_service._cache_import_timestamp = "different-timestamp"

        # Next query should trigger invalidation and re-query
        result2 = query_service.get_corporation_regions(1000129)

        # Both should have valid data (but may be different objects if re-queried)
        assert result2 is not None
        assert result2.corporation_id == 1000129


class TestSDENotSeededError:
    """Test SDE not seeded detection."""

    def test_ensure_sde_seeded_missing_tables(self):
        """Should raise when required tables are missing."""
        # Create empty database
        conn = sqlite3.connect(":memory:")
        try:
            mock_db = MagicMock()
            mock_db._get_connection.return_value = conn

            service = SDEQueryService(mock_db)

            with pytest.raises(SDENotSeededError) as exc_info:
                service.ensure_sde_seeded()

            assert "SDE tables missing" in str(exc_info.value)
            assert "aria-esi sde-seed" in str(exc_info.value)
        finally:
            conn.close()


class TestCacheWarming:
    """Test cache warming functionality."""

    def test_warm_caches_with_data(self, query_service):
        """Warm caches should populate common lookups."""
        stats = query_service.warm_caches()

        # We have ORE in our mock data
        assert stats["corporations"] >= 1
        assert stats["categories"] >= 1

    def test_warm_caches_without_sde(self):
        """Warm caches should not fail without SDE data."""
        # Create empty database
        conn = sqlite3.connect(":memory:")
        try:
            mock_db = MagicMock()
            mock_db._get_connection.return_value = conn

            service = SDEQueryService(mock_db)
            stats = service.warm_caches()

            # Should return zeros, not crash
            assert stats["corporations"] == 0
            assert stats["categories"] == 0
        finally:
            conn.close()


class TestSingletonAccessor:
    """Test singleton accessor functions."""

    def test_get_sde_query_service(self):
        """Singleton should return same instance."""
        reset_sde_query_service()

        mock_conn = sqlite3.connect(":memory:")
        try:
            with patch("aria_esi.mcp.market.database.get_market_database") as mock:
                mock_db = MagicMock()
                mock_conn.row_factory = sqlite3.Row
                mock_conn.execute(
                    "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)"
                )
                mock_db._get_connection.return_value = mock_conn
                mock.return_value = mock_db

                service1 = get_sde_query_service()
                service2 = get_sde_query_service()

                assert service1 is service2
        finally:
            mock_conn.close()

    def test_reset_sde_query_service(self):
        """Reset should clear singleton."""
        reset_sde_query_service()

        mock_conn = sqlite3.connect(":memory:")
        try:
            with patch("aria_esi.mcp.market.database.get_market_database") as mock:
                mock_db = MagicMock()
                mock_conn.row_factory = sqlite3.Row
                mock_conn.execute(
                    "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)"
                )
                mock_db._get_connection.return_value = mock_conn
                mock.return_value = mock_db

                service1 = get_sde_query_service()
                reset_sde_query_service()
                service2 = get_sde_query_service()

                assert service1 is not service2
        finally:
            mock_conn.close()


class TestCorporationInfo:
    """Test get_corporation_info method."""

    def test_get_corporation_info(self, query_service):
        """Should return full corporation info."""
        result = query_service.get_corporation_info(1000129)

        assert result is not None
        assert result.corporation_id == 1000129
        assert result.corporation_name == "Outer Ring Excavations"
        assert result.faction_id == 500014
        assert result.station_count == 2
        assert len(result.regions) == 1
        assert result.seeds_items
        assert result.seeded_item_count == 1  # Venture Blueprint

    def test_get_corporation_info_not_found(self, query_service):
        """Should return None for non-existent corporation."""
        result = query_service.get_corporation_info(999999999)
        assert result is None

    def test_get_corporation_info_cached(self, query_service):
        """Repeated calls should return cached result."""
        result1 = query_service.get_corporation_info(1000129)
        result2 = query_service.get_corporation_info(1000129)

        assert result1 is result2
