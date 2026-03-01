"""
Tests for batch name resolution module.

Tests resolve_type_ids and resolve_station_names with SDE, ESI, and fallback paths.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from aria_esi.commands._resolution import resolve_station_names, resolve_type_ids


# =============================================================================
# resolve_type_ids Tests
# =============================================================================


class TestResolveTypeIds:
    """Test resolve_type_ids batch resolution."""

    def test_empty_input(self):
        """Returns empty dict for empty input."""
        result = resolve_type_ids(set())
        assert result == {}

    def test_sde_hit(self):
        """Resolves types from SDE database."""
        from aria_esi.store.market.database import TypeInfo

        mock_db = MagicMock()
        mock_db.resolve_type_ids_batch.return_value = {
            34: TypeInfo(type_id=34, type_name="Tritanium", group_id=18, category_id=4, market_group_id=375, volume=0.01),
            35: TypeInfo(type_id=35, type_name="Pyerite", group_id=18, category_id=4, market_group_id=375, volume=0.01),
        }

        with patch("aria_esi.store.market.database.get_market_database", return_value=mock_db):
            result = resolve_type_ids({34, 35})

        assert result[34]["name"] == "Tritanium"
        assert result[34]["group_id"] == 18
        assert result[34]["market_group_id"] == 375
        assert result[35]["name"] == "Pyerite"

    def test_esi_fallback(self):
        """Falls back to ESI for IDs not in SDE."""
        mock_db = MagicMock()
        mock_db.resolve_type_ids_batch.return_value = {}  # SDE has nothing

        mock_esi = MagicMock()
        mock_esi.post.return_value = [
            {"id": 999, "name": "Special Item", "category": "inventory_type"},
        ]

        with patch("aria_esi.store.market.database.get_market_database", return_value=mock_db):
            result = resolve_type_ids({999}, esi_client=mock_esi)

        assert result[999]["name"] == "Special Item"
        assert result[999]["group_id"] == 0  # ESI fallback doesn't have group_id
        mock_esi.post.assert_called_once_with("/universe/names/", data=[999])

    def test_unknown_fallback(self):
        """Returns Unknown-{id} for IDs not found anywhere."""
        mock_db = MagicMock()
        mock_db.resolve_type_ids_batch.return_value = {}

        with patch("aria_esi.store.market.database.get_market_database", return_value=mock_db):
            result = resolve_type_ids({99999})  # No ESI client provided

        assert result[99999]["name"] == "Unknown-99999"
        assert result[99999]["group_id"] == 0

    def test_sde_failure_fallthrough(self):
        """Continues to ESI/fallback when SDE raises exception."""
        with patch("aria_esi.store.market.database.get_market_database", side_effect=Exception("DB not available")):
            result = resolve_type_ids({34})

        assert result[34]["name"] == "Unknown-34"

    def test_mixed_sde_and_fallback(self):
        """SDE resolves some IDs, rest get Unknown fallback."""
        from aria_esi.store.market.database import TypeInfo

        mock_db = MagicMock()
        mock_db.resolve_type_ids_batch.return_value = {
            34: TypeInfo(type_id=34, type_name="Tritanium", group_id=18, category_id=4, market_group_id=375, volume=0.01),
        }

        with patch("aria_esi.store.market.database.get_market_database", return_value=mock_db):
            result = resolve_type_ids({34, 99999})  # No ESI client

        assert result[34]["name"] == "Tritanium"
        assert result[99999]["name"] == "Unknown-99999"


# =============================================================================
# resolve_station_names Tests
# =============================================================================


class TestResolveStationNames:
    """Test resolve_station_names batch resolution."""

    def test_empty_input(self):
        """Returns empty dict for empty input."""
        result = resolve_station_names(set())
        assert result == {}

    def test_esi_resolution(self):
        """Resolves station names via ESI POST."""
        mock_esi = MagicMock()
        mock_esi.post.return_value = [
            {"id": 60003760, "name": "Jita IV - Moon 4 - Caldari Navy Assembly Plant", "category": "station"},
        ]

        result = resolve_station_names({60003760}, esi_client=mock_esi)

        assert result[60003760] == "Jita IV - Moon 4 - Caldari Navy Assembly Plant"
        mock_esi.post.assert_called_once()

    def test_structure_fallback(self):
        """Uses Structure-{id} for unresolved IDs >= 100M."""
        result = resolve_station_names({1_000_000_001})  # No ESI client
        assert result[1_000_000_001] == "Structure-1000000001"

    def test_station_fallback(self):
        """Uses Station-{id} for unresolved IDs < 100M."""
        result = resolve_station_names({60003760})  # No ESI client
        assert result[60003760] == "Station-60003760"

    def test_esi_failure_fallthrough(self):
        """Falls back gracefully when ESI fails."""
        from aria_esi.core import ESIError

        mock_esi = MagicMock()
        mock_esi.post.side_effect = ESIError("Service unavailable", status_code=503)

        result = resolve_station_names({60003760}, esi_client=mock_esi)

        assert result[60003760] == "Station-60003760"


# =============================================================================
# MarketDatabase.resolve_type_ids_batch Tests
# =============================================================================


class TestResolveTypeIdsBatch:
    """Test MarketDatabase.resolve_type_ids_batch method."""

    def test_empty_input(self, tmp_path):
        """Returns empty dict for empty input."""
        from aria_esi.store.market.database import MarketDatabase

        db = MarketDatabase(db_path=str(tmp_path / "test.db"))
        try:
            result = db.resolve_type_ids_batch(set())
            assert result == {}
        finally:
            db.close()

    def test_resolves_seeded_types(self, tmp_path):
        """Resolves types that exist in the database."""
        from aria_esi.store.market.database import MarketDatabase

        db = MarketDatabase(db_path=str(tmp_path / "test.db"))
        try:
            # Insert test types
            conn = db._get_connection()
            conn.execute(
                "INSERT INTO types (type_id, type_name, type_name_lower, group_id, category_id, market_group_id, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (34, "Tritanium", "tritanium", 18, 4, 375, 0.01),
            )
            conn.execute(
                "INSERT INTO types (type_id, type_name, type_name_lower, group_id, category_id, market_group_id, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (35, "Pyerite", "pyerite", 18, 4, 375, 0.01),
            )
            conn.commit()

            result = db.resolve_type_ids_batch({34, 35, 99999})

            assert 34 in result
            assert result[34].type_name == "Tritanium"
            assert result[34].group_id == 18
            assert 35 in result
            assert result[35].type_name == "Pyerite"
            assert 99999 not in result  # Not in DB
        finally:
            db.close()

    def test_chunked_queries(self, tmp_path):
        """Handles more IDs than chunk size."""
        from aria_esi.store.market.database import MarketDatabase

        db = MarketDatabase(db_path=str(tmp_path / "test.db"))
        try:
            # Insert a type
            conn = db._get_connection()
            conn.execute(
                "INSERT INTO types (type_id, type_name, type_name_lower, group_id, category_id, market_group_id, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (1, "TestItem", "testitem", 1, 1, 1, 1.0),
            )
            conn.commit()

            # Query with 600 IDs (exceeds 500 chunk size)
            big_set = set(range(1, 601))
            result = db.resolve_type_ids_batch(big_set)

            # Should find the one we inserted
            assert 1 in result
            assert result[1].type_name == "TestItem"
            assert len(result) == 1  # Only the one we inserted
        finally:
            db.close()
