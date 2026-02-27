"""
Tests for aria_esi.store.market.schema

Tests SQL schema constants and helper SQL-generating functions.
"""

from aria_esi.store.market.schema import (
    ARBITRAGE_SCHEMA_SQL,
    get_arbitrage_detection_sql,
    get_stale_regions_sql,
)


class TestArbitrageSchemaSQL:
    """Tests for the ARBITRAGE_SCHEMA_SQL constant."""

    def test_is_non_empty_string(self):
        assert isinstance(ARBITRAGE_SCHEMA_SQL, str)
        assert len(ARBITRAGE_SCHEMA_SQL) > 0

    def test_contains_region_prices_table(self):
        assert "CREATE TABLE IF NOT EXISTS region_prices" in ARBITRAGE_SCHEMA_SQL

    def test_contains_region_item_tracking_table(self):
        assert "CREATE TABLE IF NOT EXISTS region_item_tracking" in ARBITRAGE_SCHEMA_SQL

    def test_contains_arbitrage_opportunities_table(self):
        assert "CREATE TABLE IF NOT EXISTS arbitrage_opportunities" in ARBITRAGE_SCHEMA_SQL

    def test_contains_region_refresh_tracking_table(self):
        assert "CREATE TABLE IF NOT EXISTS region_refresh_tracking" in ARBITRAGE_SCHEMA_SQL

    def test_contains_schema_version_insert(self):
        assert "arbitrage_schema_version" in ARBITRAGE_SCHEMA_SQL


class TestGetArbitrageDetectionSQL:
    """Tests for get_arbitrage_detection_sql()."""

    def test_returns_string(self):
        sql = get_arbitrage_detection_sql()
        assert isinstance(sql, str)

    def test_default_parameters(self):
        sql = get_arbitrage_detection_sql()
        assert "5.0" in sql
        assert "LIMIT 50" in sql

    def test_custom_parameters(self):
        sql = get_arbitrage_detection_sql(min_profit_pct=10.0, min_volume=25, limit=100)
        assert "10.0" in sql
        assert ">= 25" in sql
        assert "LIMIT 100" in sql

    def test_joins_region_prices(self):
        sql = get_arbitrage_detection_sql()
        assert "FROM region_prices" in sql
        assert "JOIN region_prices" in sql

    def test_selects_profit_fields(self):
        sql = get_arbitrage_detection_sql()
        assert "profit_per_unit" in sql
        assert "profit_pct" in sql
        assert "available_volume" in sql

    def test_orders_by_profit(self):
        sql = get_arbitrage_detection_sql()
        assert "ORDER BY profit_pct DESC" in sql


class TestGetStaleRegionsSQL:
    """Tests for get_stale_regions_sql()."""

    def test_returns_string(self):
        sql = get_stale_regions_sql()
        assert isinstance(sql, str)

    def test_default_age(self):
        sql = get_stale_regions_sql()
        assert "300" in sql

    def test_custom_age(self):
        sql = get_stale_regions_sql(max_age_seconds=600)
        assert "600" in sql

    def test_queries_refresh_tracking(self):
        sql = get_stale_regions_sql()
        assert "FROM region_refresh_tracking" in sql

    def test_orders_by_staleness(self):
        sql = get_stale_regions_sql()
        assert "ORDER BY last_refresh ASC" in sql
