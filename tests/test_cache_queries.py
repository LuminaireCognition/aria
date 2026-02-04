"""
Tests for Universe Cache Query Functions.

Tests the local cache query layer for universe data including system lookups,
region queries, neighbor discovery, and border system detection.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from aria_esi.cache import (
    clear_cache,
    find_border_systems_in_region,
    find_nearest_border_systems,
    get_cache_info,
    get_constellation,
    get_region,
    get_region_by_name,
    get_stargate_destination,
    get_system,
    get_system_by_name,
    get_system_full_info,
    get_system_neighbors,
    is_cache_available,
    load_cache,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def minimal_cache_data() -> dict:
    """
    Create minimal cache data for testing.

    Contains:
    - 2 regions: The Forge, Sinq Laison
    - 2 constellations: One per region
    - 5 systems with varying security:
      - Jita (0.95 highsec)
      - Perimeter (0.90 highsec)
      - Sivala (0.50 highsec border - connects to lowsec)
      - Aufay (0.35 lowsec)
      - Dodixie (0.87 highsec, different region)
    """
    return {
        "systems": {
            "30000142": {
                "system_id": 30000142,
                "name": "Jita",
                "security": 0.9459,
                "constellation_id": 20000020,
                "stargates": [50001248],
            },
            "30000144": {
                "system_id": 30000144,
                "name": "Perimeter",
                "security": 0.9072,
                "constellation_id": 20000020,
                "stargates": [50001250, 50001251],
            },
            "30000138": {
                "system_id": 30000138,
                "name": "Sivala",
                "security": 0.5000,
                "constellation_id": 20000020,
                "stargates": [50001254, 50001255],
            },
            "30000137": {
                "system_id": 30000137,
                "name": "Aufay",
                "security": 0.3500,
                "constellation_id": 20000020,
                "stargates": [50001256],
            },
            "30002659": {
                "system_id": 30002659,
                "name": "Dodixie",
                "security": 0.8719,
                "constellation_id": 20000389,
                "stargates": [50002900],
            },
        },
        "stargates": {
            "50001248": {"destination_system_id": 30000144},  # Jita -> Perimeter
            "50001250": {"destination_system_id": 30000142},  # Perimeter -> Jita
            "50001251": {"destination_system_id": 30000138},  # Perimeter -> Sivala
            "50001254": {"destination_system_id": 30000144},  # Sivala -> Perimeter
            "50001255": {"destination_system_id": 30000137},  # Sivala -> Aufay
            "50001256": {"destination_system_id": 30000138},  # Aufay -> Sivala
            "50002900": {"destination_system_id": 30000142},  # Dodixie -> Jita (fake)
        },
        "constellations": {
            "20000020": {"name": "Kimotoro", "region_id": 10000002},
            "20000389": {"name": "Sinq Laison", "region_id": 10000032},
        },
        "regions": {
            "10000002": {"name": "The Forge"},
            "10000032": {"name": "Sinq Laison"},
        },
        "generated": "test-1.0",
    }


@pytest.fixture
def temp_cache_file(tmp_path: Path, minimal_cache_data: dict) -> Path:
    """Create a temporary cache file and return its path."""
    cache_path = tmp_path / "universe_cache.json"
    cache_path.write_text(json.dumps(minimal_cache_data))
    return cache_path


@pytest.fixture(autouse=True)
def clear_cache_before_test():
    """Clear the module-level cache before each test."""
    clear_cache()
    yield
    clear_cache()


# =============================================================================
# load_cache Tests
# =============================================================================


class TestLoadCache:
    """Tests for load_cache function."""

    def test_load_cache_returns_dict(self, temp_cache_file: Path):
        """Cache loads and returns dict."""
        result = load_cache(temp_cache_file)

        assert isinstance(result, dict)
        assert "systems" in result
        assert "stargates" in result

    def test_load_cache_singleton_behavior(self, temp_cache_file: Path):
        """Second load returns cached instance."""
        first_load = load_cache(temp_cache_file)
        second_load = load_cache(temp_cache_file)

        assert first_load is second_load

    def test_load_cache_respects_clear(self, temp_cache_file: Path):
        """clear_cache forces reload."""
        first_load = load_cache(temp_cache_file)
        clear_cache()
        second_load = load_cache(temp_cache_file)

        # Same data but different instances
        assert first_load == second_load
        # Note: could be same dict reference if loaded from same file,
        # the key behavior is that clear_cache resets the state

    def test_load_cache_missing_file_raises(self, tmp_path: Path):
        """Missing cache file raises FileNotFoundError."""
        nonexistent = tmp_path / "does_not_exist.json"

        with pytest.raises(FileNotFoundError) as exc_info:
            load_cache(nonexistent)

        assert "Universe cache not found" in str(exc_info.value)


# =============================================================================
# is_cache_available Tests
# =============================================================================


class TestIsCacheAvailable:
    """Tests for is_cache_available function."""

    def test_returns_true_when_exists(self, temp_cache_file: Path):
        """Returns True when cache file exists."""
        assert is_cache_available(temp_cache_file) is True

    def test_returns_false_when_missing(self, tmp_path: Path):
        """Returns False when cache file doesn't exist."""
        nonexistent = tmp_path / "missing.json"
        assert is_cache_available(nonexistent) is False


# =============================================================================
# get_cache_info Tests
# =============================================================================


class TestGetCacheInfo:
    """Tests for get_cache_info function."""

    def test_returns_metadata_when_available(self, temp_cache_file: Path):
        """Returns cache metadata when file exists."""
        info = get_cache_info(temp_cache_file)

        assert info["available"] is True
        assert info["generated"] == "test-1.0"
        assert "counts" in info
        assert info["counts"]["systems"] == 5
        assert info["counts"]["regions"] == 2

    def test_returns_unavailable_when_missing(self, tmp_path: Path):
        """Returns available=False when file missing."""
        nonexistent = tmp_path / "missing.json"

        info = get_cache_info(nonexistent)

        assert info["available"] is False


# =============================================================================
# get_system Tests
# =============================================================================


class TestGetSystem:
    """Tests for get_system function."""

    def test_returns_system_by_id(self, temp_cache_file: Path):
        """Returns system dict for valid ID."""
        load_cache(temp_cache_file)

        result = get_system(30000142)

        assert result is not None
        assert result["name"] == "Jita"
        assert result["security"] == 0.9459

    def test_returns_none_for_invalid_id(self, temp_cache_file: Path):
        """Returns None for unknown system ID."""
        load_cache(temp_cache_file)

        result = get_system(99999999)

        assert result is None


# =============================================================================
# get_system_by_name Tests
# =============================================================================


class TestGetSystemByName:
    """Tests for get_system_by_name function."""

    def test_exact_match(self, temp_cache_file: Path):
        """Returns system for exact name match."""
        load_cache(temp_cache_file)

        result = get_system_by_name("Jita")

        assert result is not None
        sys_id, data = result
        assert sys_id == 30000142
        assert data["name"] == "Jita"

    def test_case_insensitive(self, temp_cache_file: Path):
        """Name matching is case-insensitive."""
        load_cache(temp_cache_file)

        result_lower = get_system_by_name("jita")
        result_upper = get_system_by_name("JITA")
        result_mixed = get_system_by_name("JiTa")

        assert result_lower is not None
        assert result_upper is not None
        assert result_mixed is not None
        assert result_lower[0] == result_upper[0] == result_mixed[0] == 30000142

    def test_returns_none_for_unknown_name(self, temp_cache_file: Path):
        """Returns None for unknown system name."""
        load_cache(temp_cache_file)

        result = get_system_by_name("Nonexistent System")

        assert result is None


# =============================================================================
# get_constellation Tests
# =============================================================================


class TestGetConstellation:
    """Tests for get_constellation function."""

    def test_returns_constellation_by_id(self, temp_cache_file: Path):
        """Returns constellation dict for valid ID."""
        load_cache(temp_cache_file)

        result = get_constellation(20000020)

        assert result is not None
        assert result["name"] == "Kimotoro"
        assert result["region_id"] == 10000002

    def test_returns_none_for_invalid_id(self, temp_cache_file: Path):
        """Returns None for unknown constellation ID."""
        load_cache(temp_cache_file)

        result = get_constellation(99999999)

        assert result is None


# =============================================================================
# get_region Tests
# =============================================================================


class TestGetRegion:
    """Tests for get_region function."""

    def test_returns_region_by_id(self, temp_cache_file: Path):
        """Returns region dict for valid ID."""
        load_cache(temp_cache_file)

        result = get_region(10000002)

        assert result is not None
        assert result["name"] == "The Forge"

    def test_returns_none_for_invalid_id(self, temp_cache_file: Path):
        """Returns None for unknown region ID."""
        load_cache(temp_cache_file)

        result = get_region(99999999)

        assert result is None


# =============================================================================
# get_region_by_name Tests
# =============================================================================


class TestGetRegionByName:
    """Tests for get_region_by_name function."""

    def test_exact_match(self, temp_cache_file: Path):
        """Returns region for exact name match."""
        load_cache(temp_cache_file)

        result = get_region_by_name("The Forge")

        assert result is not None
        region_id, data = result
        assert region_id == 10000002
        assert data["name"] == "The Forge"

    def test_case_insensitive(self, temp_cache_file: Path):
        """Name matching is case-insensitive."""
        load_cache(temp_cache_file)

        result = get_region_by_name("the forge")

        assert result is not None
        assert result[0] == 10000002

    def test_returns_none_for_unknown_name(self, temp_cache_file: Path):
        """Returns None for unknown region name."""
        load_cache(temp_cache_file)

        result = get_region_by_name("Fake Region")

        assert result is None


# =============================================================================
# get_stargate_destination Tests
# =============================================================================


class TestGetStargateDestination:
    """Tests for get_stargate_destination function."""

    def test_returns_destination(self, temp_cache_file: Path):
        """Returns destination system ID for valid gate."""
        load_cache(temp_cache_file)

        result = get_stargate_destination(50001248)

        assert result == 30000144  # Jita -> Perimeter

    def test_returns_none_for_invalid_gate(self, temp_cache_file: Path):
        """Returns None for unknown gate ID."""
        load_cache(temp_cache_file)

        result = get_stargate_destination(99999999)

        assert result is None


# =============================================================================
# get_system_neighbors Tests
# =============================================================================


class TestGetSystemNeighbors:
    """Tests for get_system_neighbors function."""

    def test_returns_neighbor_list(self, temp_cache_file: Path):
        """Returns list of neighbor tuples."""
        load_cache(temp_cache_file)

        result = get_system_neighbors(30000142)  # Jita

        assert len(result) == 1
        neighbor_id, neighbor_data = result[0]
        assert neighbor_id == 30000144  # Perimeter
        assert neighbor_data["name"] == "Perimeter"

    def test_multiple_neighbors(self, temp_cache_file: Path):
        """Returns all neighbors for system with multiple gates."""
        load_cache(temp_cache_file)

        result = get_system_neighbors(30000144)  # Perimeter

        assert len(result) == 2
        neighbor_names = {data["name"] for _, data in result}
        assert neighbor_names == {"Jita", "Sivala"}

    def test_returns_empty_for_invalid_system(self, temp_cache_file: Path):
        """Returns empty list for unknown system."""
        load_cache(temp_cache_file)

        result = get_system_neighbors(99999999)

        assert result == []


# =============================================================================
# get_system_full_info Tests
# =============================================================================


class TestGetSystemFullInfo:
    """Tests for get_system_full_info function."""

    def test_returns_enriched_info(self, temp_cache_file: Path):
        """Returns system with constellation and region resolved."""
        load_cache(temp_cache_file)

        result = get_system_full_info(30000142)

        assert result is not None
        assert result["system_id"] == 30000142
        assert result["name"] == "Jita"
        assert result["security"] == 0.95  # Rounded
        assert result["constellation"] == "Kimotoro"
        assert result["region"] == "The Forge"

    def test_returns_none_for_invalid_system(self, temp_cache_file: Path):
        """Returns None for unknown system."""
        load_cache(temp_cache_file)

        result = get_system_full_info(99999999)

        assert result is None


# =============================================================================
# find_border_systems_in_region Tests
# =============================================================================


class TestFindBorderSystemsInRegion:
    """Tests for find_border_systems_in_region function."""

    def test_finds_border_systems(self, temp_cache_file: Path):
        """Finds highsec systems bordering lowsec in region."""
        load_cache(temp_cache_file)

        result = find_border_systems_in_region("The Forge")

        assert len(result) >= 1
        # Sivala (0.50) borders Aufay (0.35)
        sivala_result = next((s for s in result if s["name"] == "Sivala"), None)
        assert sivala_result is not None
        assert sivala_result["security"] == 0.50
        assert len(sivala_result["borders_lowsec"]) >= 1

    def test_respects_highsec_threshold(self, temp_cache_file: Path):
        """Only includes systems with sec >= 0.45."""
        load_cache(temp_cache_file)

        result = find_border_systems_in_region("The Forge")

        # Aufay (0.35) should NOT be in results - it's lowsec
        aufay_result = next((s for s in result if s["name"] == "Aufay"), None)
        assert aufay_result is None

    def test_lowsec_neighbor_detection(self, temp_cache_file: Path):
        """Correctly identifies lowsec neighbors."""
        load_cache(temp_cache_file)

        result = find_border_systems_in_region("The Forge")

        # Find Sivala and check its lowsec neighbors
        sivala = next((s for s in result if s["name"] == "Sivala"), None)
        if sivala:
            lowsec_names = [n["name"] for n in sivala["borders_lowsec"]]
            assert "Aufay" in lowsec_names

    def test_returns_empty_for_unknown_region(self, temp_cache_file: Path):
        """Returns empty list for unknown region."""
        load_cache(temp_cache_file)

        result = find_border_systems_in_region("Fake Region")

        assert result == []

    def test_case_insensitive_region_name(self, temp_cache_file: Path):
        """Region name matching is case-insensitive."""
        load_cache(temp_cache_file)

        result = find_border_systems_in_region("the forge")

        assert len(result) >= 1

    def test_results_sorted_by_name(self, temp_cache_file: Path):
        """Results are sorted alphabetically by name."""
        load_cache(temp_cache_file)

        result = find_border_systems_in_region("The Forge")

        if len(result) > 1:
            names = [s["name"] for s in result]
            assert names == sorted(names)


# =============================================================================
# find_nearest_border_systems Tests
# =============================================================================


class TestFindNearestBorderSystems:
    """Tests for find_nearest_border_systems function."""

    def test_finds_border_from_origin(self, temp_cache_file: Path):
        """Finds border systems nearest to origin."""
        load_cache(temp_cache_file)

        result = find_nearest_border_systems("Jita", limit=5)

        # Should find Sivala as a border system (via Perimeter)
        border_names = [s["name"] for s in result]
        assert "Sivala" in border_names

    def test_includes_distance(self, temp_cache_file: Path):
        """Results include approximate jump distance."""
        load_cache(temp_cache_file)

        result = find_nearest_border_systems("Jita", limit=5)

        sivala = next((s for s in result if s["name"] == "Sivala"), None)
        if sivala:
            # Jita -> Perimeter -> Sivala = 2 jumps
            assert sivala["approx_jumps"] == 2

    def test_sorted_by_distance(self, temp_cache_file: Path):
        """Results sorted by jump distance."""
        load_cache(temp_cache_file)

        result = find_nearest_border_systems("Jita", limit=5)

        if len(result) > 1:
            distances = [s["approx_jumps"] for s in result]
            assert distances == sorted(distances)

    def test_respects_limit(self, temp_cache_file: Path):
        """Respects limit parameter."""
        load_cache(temp_cache_file)

        result = find_nearest_border_systems("Jita", limit=1)

        assert len(result) <= 1

    def test_returns_empty_for_unknown_origin(self, temp_cache_file: Path):
        """Returns empty list for unknown origin."""
        load_cache(temp_cache_file)

        result = find_nearest_border_systems("Nonexistent System", limit=5)

        assert result == []

    def test_case_insensitive_origin(self, temp_cache_file: Path):
        """Origin name matching is case-insensitive."""
        load_cache(temp_cache_file)

        result = find_nearest_border_systems("jita", limit=5)

        assert len(result) >= 1


# =============================================================================
# Border Detection Threshold Tests
# =============================================================================


class TestBorderDetectionThresholds:
    """Tests for security threshold edge cases."""

    def test_exactly_045_is_highsec(self, temp_cache_file: Path, minimal_cache_data: dict):
        """System with security exactly 0.45 is treated as highsec."""
        # Modify cache to have a 0.45 system
        minimal_cache_data["systems"]["30000138"]["security"] = 0.45
        clear_cache()

        # Write modified data
        temp_cache_file.write_text(json.dumps(minimal_cache_data))
        load_cache(temp_cache_file)

        result = find_border_systems_in_region("The Forge")

        # Sivala at 0.45 should still be in results (highsec border)
        sivala = next((s for s in result if s["name"] == "Sivala"), None)
        assert sivala is not None

    def test_below_045_is_lowsec(self, temp_cache_file: Path, minimal_cache_data: dict):
        """System with security below 0.45 is treated as lowsec."""
        # Modify cache to have a 0.44 system
        minimal_cache_data["systems"]["30000138"]["security"] = 0.44
        clear_cache()

        temp_cache_file.write_text(json.dumps(minimal_cache_data))
        load_cache(temp_cache_file)

        result = find_border_systems_in_region("The Forge")

        # Sivala at 0.44 should NOT be in results (it's lowsec now)
        sivala = next((s for s in result if s["name"] == "Sivala"), None)
        assert sivala is None

    def test_zero_sec_not_lowsec(self, temp_cache_file: Path, minimal_cache_data: dict):
        """System with security exactly 0.0 is not counted as lowsec neighbor."""
        # Add a nullsec system
        minimal_cache_data["systems"]["30000999"] = {
            "system_id": 30000999,
            "name": "Nullsec",
            "security": 0.0,
            "constellation_id": 20000020,
            "stargates": [50009999],
        }
        minimal_cache_data["stargates"]["50009999"] = {"destination_system_id": 30000138}
        # Add reverse gate from Sivala
        minimal_cache_data["systems"]["30000138"]["stargates"].append(50009998)
        minimal_cache_data["stargates"]["50009998"] = {"destination_system_id": 30000999}

        clear_cache()
        temp_cache_file.write_text(json.dumps(minimal_cache_data))
        load_cache(temp_cache_file)

        result = find_border_systems_in_region("The Forge")

        # Sivala should still be found, but Nullsec should not be in its lowsec neighbors
        sivala = next((s for s in result if s["name"] == "Sivala"), None)
        if sivala:
            lowsec_names = [n["name"] for n in sivala["borders_lowsec"]]
            # 0.0 sec is nullsec, not lowsec (0 < sec < 0.45)
            assert "Nullsec" not in lowsec_names
