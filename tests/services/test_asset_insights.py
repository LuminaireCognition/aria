"""
Tests for Asset Insights Service.
"""

import pytest

from aria_esi.services.asset_insights import (
    _extract_system_name,
    find_duplicate_ships,
    generate_insights_summary,
    get_forgotten_asset_threshold,
    get_trade_hub_station_ids,
    get_trade_hub_system_names,
    identify_forgotten_assets,
    suggest_consolidations,
)


class TestTradeHubData:
    """Test trade hub reference data loading."""

    @pytest.mark.unit
    def test_get_trade_hub_station_ids_returns_list(self):
        """Should return list of station IDs."""
        ids = get_trade_hub_station_ids()
        assert isinstance(ids, list)
        assert len(ids) >= 5
        assert 60003760 in ids  # Jita

    @pytest.mark.unit
    def test_get_trade_hub_system_names_returns_list(self):
        """Should return list of system names."""
        names = get_trade_hub_system_names()
        assert isinstance(names, list)
        assert "Jita" in names
        assert "Amarr" in names
        assert "Dodixie" in names

    @pytest.mark.unit
    def test_get_forgotten_asset_threshold(self):
        """Should return threshold value."""
        threshold = get_forgotten_asset_threshold()
        assert threshold == 5_000_000  # 5M ISK


class TestExtractSystemName:
    """Test system name extraction from station names."""

    @pytest.mark.unit
    def test_extracts_from_npc_station(self):
        """Should extract system from NPC station name."""
        assert _extract_system_name("Jita IV - Moon 4 - Caldari Navy Assembly Plant") == "Jita"
        assert _extract_system_name("Dodixie IX - Moon 20 - Federation Navy Assembly Plant") == "Dodixie"

    @pytest.mark.unit
    def test_handles_roman_numerals(self):
        """Should strip roman numeral planet designators."""
        assert _extract_system_name("Amarr VIII - Something") == "Amarr"
        assert _extract_system_name("Rens VI - Moon 8 - Station") == "Rens"

    @pytest.mark.unit
    def test_handles_structures(self):
        """Should return None for structures."""
        assert _extract_system_name("Structure (12345)") is None

    @pytest.mark.unit
    def test_handles_unknown_locations(self):
        """Should return None for unknown formats."""
        assert _extract_system_name("Location-12345") is None


class TestIdentifyForgottenAssets:
    """Test forgotten asset identification."""

    @pytest.fixture
    def sample_assets(self):
        """Sample asset data."""
        return {
            # Trade hub - should be excluded
            60003760: [{"type_id": 1, "item_id": 100}],
            # Small value location - should be included
            60001234: [
                {"type_id": 2, "item_id": 101},
                {"type_id": 3, "item_id": 102},
            ],
            # High value location - should be excluded
            60005678: [{"type_id": 4, "item_id": 103}],
        }

    @pytest.fixture
    def sample_names(self):
        """Sample location names."""
        return {
            60003760: "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            60001234: "Arnon IX - Moon 3 - Sisters of EVE Bureau",
            60005678: "Hek VIII - Moon 12 - Boundless Creation Factory",
        }

    @pytest.fixture
    def sample_values(self):
        """Sample location values."""
        return {
            60003760: 500_000_000,  # 500M in Jita
            60001234: 2_500_000,    # 2.5M in Arnon - forgotten
            60005678: 50_000_000,   # 50M in Hek - not forgotten
        }

    @pytest.mark.unit
    def test_identifies_low_value_non_hub_locations(
        self, sample_assets, sample_names, sample_values
    ):
        """Should identify locations under threshold not in hubs."""
        forgotten = identify_forgotten_assets(
            sample_assets, sample_names, sample_values
        )

        assert len(forgotten) == 1
        assert forgotten[0]["location_id"] == 60001234
        assert forgotten[0]["total_value"] == 2_500_000
        assert forgotten[0]["item_count"] == 2

    @pytest.mark.unit
    def test_excludes_trade_hubs(self, sample_assets, sample_names, sample_values):
        """Should exclude trade hub stations."""
        # Add low value to Jita
        sample_values[60003760] = 1_000_000

        forgotten = identify_forgotten_assets(
            sample_assets, sample_names, sample_values
        )

        # Jita should not appear even though value is low
        location_ids = [f["location_id"] for f in forgotten]
        assert 60003760 not in location_ids

    @pytest.mark.unit
    def test_custom_threshold(self, sample_assets, sample_names, sample_values):
        """Should respect custom threshold."""
        # With 1M threshold, Arnon (2.5M) should not be forgotten
        forgotten = identify_forgotten_assets(
            sample_assets, sample_names, sample_values, threshold=1_000_000
        )
        assert len(forgotten) == 0

        # With 10M threshold, more locations would be included
        sample_values[60005678] = 8_000_000  # Below 10M
        forgotten = identify_forgotten_assets(
            sample_assets, sample_names, sample_values, threshold=10_000_000
        )
        assert len(forgotten) == 2

    @pytest.mark.unit
    def test_extracts_system_name(self, sample_assets, sample_names, sample_values):
        """Should extract system name from station name."""
        forgotten = identify_forgotten_assets(
            sample_assets, sample_names, sample_values
        )

        assert len(forgotten) == 1
        assert forgotten[0]["system_name"] == "Arnon"

    @pytest.mark.unit
    def test_sorts_by_value_ascending(self):
        """Should sort results by value (lowest first)."""
        assets = {
            60001111: [{"type_id": 1}],
            60002222: [{"type_id": 2}],
            60003333: [{"type_id": 3}],
        }
        names = {
            60001111: "System A - Station",
            60002222: "System B - Station",
            60003333: "System C - Station",
        }
        values = {
            60001111: 3_000_000,
            60002222: 1_000_000,
            60003333: 2_000_000,
        }

        forgotten = identify_forgotten_assets(assets, names, values)

        assert len(forgotten) == 3
        assert forgotten[0]["total_value"] == 1_000_000
        assert forgotten[1]["total_value"] == 2_000_000
        assert forgotten[2]["total_value"] == 3_000_000


class TestSuggestConsolidations:
    """Test consolidation suggestions."""

    @pytest.fixture
    def sample_forgotten(self):
        """Sample forgotten assets."""
        return [
            {
                "location_id": 60001234,
                "location_name": "Arnon IX - Sisters Bureau",
                "total_value": 2_500_000,
                "item_count": 5,
                "system_name": "Arnon",
            },
        ]

    @pytest.mark.unit
    def test_suggests_without_route_calculator(self, sample_forgotten):
        """Should work without route calculator."""
        suggestions = suggest_consolidations(
            sample_forgotten,
            home_systems=["Dodixie"],
            route_calculator=None,
        )

        assert len(suggestions) == 1
        assert suggestions[0]["recommendation"] == "manual_check"
        assert suggestions[0]["to_home"] is None
        assert suggestions[0]["to_nearest_hub"] is None

    @pytest.mark.unit
    def test_suggests_with_route_calculator(self, sample_forgotten):
        """Should calculate routes when calculator provided."""
        # Mock route calculator
        def mock_routes(origin, dest):
            routes = {
                ("Arnon", "Dodixie"): 5,
                ("Arnon", "Jita"): 15,
                ("Arnon", "Amarr"): 10,
                ("Arnon", "Rens"): 20,
                ("Arnon", "Hek"): 22,
            }
            return routes.get((origin, dest))

        suggestions = suggest_consolidations(
            sample_forgotten,
            home_systems=["Dodixie"],
            route_calculator=mock_routes,
        )

        assert len(suggestions) == 1
        assert suggestions[0]["to_home"]["system"] == "Dodixie"
        assert suggestions[0]["to_home"]["jumps"] == 5
        assert suggestions[0]["to_nearest_hub"]["system"] == "Dodixie"
        assert suggestions[0]["to_nearest_hub"]["jumps"] == 5
        assert suggestions[0]["recommendation"] == "consolidate_home"

    @pytest.mark.unit
    def test_recommends_hub_when_closer(self, sample_forgotten):
        """Should recommend hub when closer than home."""
        def mock_routes(origin, dest):
            routes = {
                ("Arnon", "Masalle"): 20,  # Home is far
                ("Arnon", "Jita"): 15,
                ("Arnon", "Amarr"): 10,  # Amarr is closest
                ("Arnon", "Dodixie"): 5,
                ("Arnon", "Rens"): 25,
                ("Arnon", "Hek"): 30,
            }
            return routes.get((origin, dest))

        # Home is Masalle (20 jumps), but Dodixie is only 5 jumps
        suggestions = suggest_consolidations(
            sample_forgotten,
            home_systems=["Masalle"],
            route_calculator=mock_routes,
        )

        assert suggestions[0]["recommendation"] == "consolidate_hub"
        assert suggestions[0]["to_nearest_hub"]["system"] == "Dodixie"

    @pytest.mark.unit
    def test_handles_missing_system_name(self):
        """Should handle assets without extractable system name."""
        forgotten = [
            {
                "location_id": 123456,
                "location_name": "Structure (123456)",
                "total_value": 1_000_000,
                "item_count": 2,
                "system_name": None,
            },
        ]

        suggestions = suggest_consolidations(
            forgotten,
            home_systems=["Jita"],
            route_calculator=lambda o, d: 10,
        )

        assert len(suggestions) == 1
        assert suggestions[0]["recommendation"] == "manual_check"


class TestFindDuplicateShips:
    """Test duplicate ship detection."""

    @pytest.fixture
    def ship_group_ids(self):
        """Ship group IDs for testing."""
        return {25, 26, 27, 28}  # Frigate, Cruiser, etc.

    @pytest.fixture
    def type_info(self):
        """Type info for testing."""
        return {
            587: {"name": "Rifter", "group_id": 25},
            24690: {"name": "Vexor", "group_id": 26},
            17715: {"name": "Gila", "group_id": 26},
        }

    @pytest.mark.unit
    def test_finds_same_location_duplicates(self, ship_group_ids, type_info):
        """Should find multiple ships of same type at same location."""
        assets = [
            {"type_id": 587, "location_id": 100, "is_singleton": True, "location": "Station A"},
            {"type_id": 587, "location_id": 100, "is_singleton": True, "location": "Station A"},
            {"type_id": 587, "location_id": 100, "is_singleton": True, "location": "Station A"},
        ]

        duplicates = find_duplicate_ships(assets, type_info, ship_group_ids)

        # Should find same-location duplicate
        same_loc = [d for d in duplicates if d["note"] == "same_location"]
        assert len(same_loc) == 1
        assert same_loc[0]["type_name"] == "Rifter"
        assert same_loc[0]["total_count"] == 3

    @pytest.mark.unit
    def test_finds_multi_location_duplicates(self, ship_group_ids, type_info):
        """Should find same ship type at different locations."""
        assets = [
            {"type_id": 24690, "location_id": 100, "is_singleton": True, "location": "Station A"},
            {"type_id": 24690, "location_id": 200, "is_singleton": True, "location": "Station B"},
        ]

        duplicates = find_duplicate_ships(assets, type_info, ship_group_ids)

        # Should find multi-location entry
        multi_loc = [d for d in duplicates if d["note"] == "multiple_locations"]
        assert len(multi_loc) == 1
        assert multi_loc[0]["type_name"] == "Vexor"
        assert multi_loc[0]["total_count"] == 2
        assert len(multi_loc[0]["instances"]) == 2

    @pytest.mark.unit
    def test_ignores_packaged_ships(self, ship_group_ids, type_info):
        """Should ignore packaged (not assembled) ships."""
        assets = [
            {"type_id": 587, "location_id": 100, "is_singleton": False},  # Packaged
            {"type_id": 587, "location_id": 100, "is_singleton": False},  # Packaged
        ]

        duplicates = find_duplicate_ships(assets, type_info, ship_group_ids)
        assert len(duplicates) == 0

    @pytest.mark.unit
    def test_ignores_non_ships(self, ship_group_ids, type_info):
        """Should ignore non-ship items."""
        type_info[123] = {"name": "Tritanium", "group_id": 999}  # Not a ship
        assets = [
            {"type_id": 123, "location_id": 100, "is_singleton": True},
            {"type_id": 123, "location_id": 100, "is_singleton": True},
        ]

        duplicates = find_duplicate_ships(assets, type_info, ship_group_ids)
        assert len(duplicates) == 0

    @pytest.mark.unit
    def test_ignores_single_ships(self, ship_group_ids, type_info):
        """Should not report single ships as duplicates."""
        assets = [
            {"type_id": 587, "location_id": 100, "is_singleton": True, "location": "A"},
            {"type_id": 24690, "location_id": 200, "is_singleton": True, "location": "B"},
            {"type_id": 17715, "location_id": 300, "is_singleton": True, "location": "C"},
        ]

        duplicates = find_duplicate_ships(assets, type_info, ship_group_ids)
        assert len(duplicates) == 0


class TestGenerateInsightsSummary:
    """Test insight summary generation."""

    @pytest.mark.unit
    def test_generates_summary(self):
        """Should generate complete summary."""
        forgotten = [
            {"location_id": 1, "total_value": 1_000_000, "item_count": 5},
            {"location_id": 2, "total_value": 2_000_000, "item_count": 3},
        ]
        consolidations = [
            {"recommendation": "consolidate_home"},
            {"recommendation": "consolidate_hub"},
            {"recommendation": "consolidate_hub"},
        ]
        duplicates = [
            {"note": "same_location", "total_count": 3},
            {"note": "multiple_locations", "total_count": 2},
        ]

        summary = generate_insights_summary(forgotten, consolidations, duplicates)

        assert summary["forgotten_assets"]["location_count"] == 2
        assert summary["forgotten_assets"]["total_value"] == 3_000_000
        assert summary["forgotten_assets"]["total_items"] == 8

        assert summary["consolidation_suggestions"]["total"] == 3
        assert summary["consolidation_suggestions"]["recommend_home"] == 1
        assert summary["consolidation_suggestions"]["recommend_hub"] == 2

        assert summary["duplicate_ships"]["same_location_types"] == 1
        assert summary["duplicate_ships"]["multi_location_types"] == 1

        assert summary["has_insights"] is True

    @pytest.mark.unit
    def test_handles_empty_inputs(self):
        """Should handle empty inputs gracefully."""
        summary = generate_insights_summary([], [], [])

        assert summary["forgotten_assets"]["location_count"] == 0
        assert summary["has_insights"] is False
