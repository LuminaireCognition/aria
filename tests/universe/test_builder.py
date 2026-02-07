"""
Tests for UniverseGraph builder.

STP-003: Graph Builder Tests
"""

import json
import time
from pathlib import Path

import pytest

from aria_esi.universe import (
    DEFAULT_CACHE_PATH,
    build_universe_graph,
    load_universe_graph,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_cache(tmp_path: Path) -> Path:
    """
    Create minimal universe cache for testing.

    Graph structure:
        Jita (high-sec 0.95) -- Perimeter (high-sec 0.90)
             |
        New Caldari (high-sec 0.85) -- Uedama (high-sec 0.50)
                                            |
                                       Sivala (low-sec 0.35)
                                            |
                                       Ala (null-sec -0.2)

    Border systems: Uedama (adjacent to Sivala)
    """
    cache = {
        "generated": "2026-01-17T00:00:00Z",
        "regions": {
            "10000002": {"name": "The Forge"},
            "10000033": {"name": "The Citadel"},
        },
        "constellations": {
            "20000020": {"name": "Kimotoro", "region_id": 10000002},
            "20000404": {"name": "Saatuban", "region_id": 10000033},
        },
        "systems": {
            "30000142": {
                "name": "Jita",
                "security": 0.95,
                "constellation_id": 20000020,
                "stargates": [50001, 50002],
            },
            "30000144": {
                "name": "Perimeter",
                "security": 0.90,
                "constellation_id": 20000020,
                "stargates": [50003],
            },
            "30000145": {
                "name": "New Caldari",
                "security": 0.85,
                "constellation_id": 20000020,
                "stargates": [50004, 50005],
            },
            "30002768": {
                "name": "Uedama",
                "security": 0.50,
                "constellation_id": 20000404,
                "stargates": [50006, 50007],
            },
            "30002769": {
                "name": "Sivala",
                "security": 0.35,
                "constellation_id": 20000404,
                "stargates": [50008, 50009],
            },
            "30002770": {
                "name": "Ala",
                "security": -0.2,
                "constellation_id": 20000404,
                "stargates": [50010],
            },
        },
        "stargates": {
            # Jita -- Perimeter
            "50001": {"destination_system_id": 30000144},
            "50003": {"destination_system_id": 30000142},
            # Jita -- New Caldari
            "50002": {"destination_system_id": 30000145},
            "50004": {"destination_system_id": 30000142},
            # New Caldari -- Uedama
            "50005": {"destination_system_id": 30002768},
            "50006": {"destination_system_id": 30000145},
            # Uedama -- Sivala
            "50007": {"destination_system_id": 30002769},
            "50008": {"destination_system_id": 30002768},
            # Sivala -- Ala
            "50009": {"destination_system_id": 30002770},
            "50010": {"destination_system_id": 30002769},
        },
    }
    cache_path = tmp_path / "universe_cache.json"
    cache_path.write_text(json.dumps(cache))
    return cache_path


@pytest.fixture
def sample_universe(sample_cache: Path):
    """Build universe from sample cache."""
    return build_universe_graph(sample_cache)


# =============================================================================
# Build Function Tests
# =============================================================================


class TestBuildCreatesValidGraph:
    """Test that builder produces valid UniverseGraph."""

    def test_produces_non_empty_graph(self, sample_universe):
        """Builder produces graph with systems."""
        assert sample_universe.system_count > 0
        assert sample_universe.stargate_count > 0

    def test_system_count_matches_input(self, sample_universe):
        """System count matches input cache."""
        assert sample_universe.system_count == 6

    def test_stargate_count_matches_unique_edges(self, sample_universe):
        """Stargate count is number of unique edges (bidirectional deduped)."""
        # 5 unique connections in sample data
        assert sample_universe.stargate_count == 5

    def test_graph_is_undirected(self, sample_universe):
        """Graph is undirected."""
        assert not sample_universe.graph.is_directed()


class TestAllSystemsIndexed:
    """Test that all systems from cache are indexed."""

    def test_all_names_resolvable(self, sample_universe):
        """All system names can be resolved."""
        names = ["Jita", "Perimeter", "New Caldari", "Uedama", "Sivala", "Ala"]
        for name in names:
            assert sample_universe.resolve_name(name) is not None

    def test_name_to_idx_complete(self, sample_universe):
        """name_to_idx has all systems."""
        assert len(sample_universe.name_to_idx) == 6

    def test_idx_to_name_complete(self, sample_universe):
        """idx_to_name has all systems."""
        assert len(sample_universe.idx_to_name) == 6

    def test_id_to_idx_complete(self, sample_universe):
        """id_to_idx has all systems."""
        assert len(sample_universe.id_to_idx) == 6


class TestStargatesCreateBidirectionalEdges:
    """Test that stargates create proper bidirectional edges."""

    def test_jita_perimeter_connected(self, sample_universe):
        """Jita and Perimeter are connected."""
        jita_idx = sample_universe.resolve_name("Jita")
        perimeter_idx = sample_universe.resolve_name("Perimeter")
        neighbors = sample_universe.graph.neighbors(jita_idx)
        assert perimeter_idx in neighbors

    def test_connection_is_bidirectional(self, sample_universe):
        """Connections work in both directions."""
        jita_idx = sample_universe.resolve_name("Jita")
        perimeter_idx = sample_universe.resolve_name("Perimeter")

        # Jita -> Perimeter
        jita_neighbors = sample_universe.graph.neighbors(jita_idx)
        assert perimeter_idx in jita_neighbors

        # Perimeter -> Jita
        perimeter_neighbors = sample_universe.graph.neighbors(perimeter_idx)
        assert jita_idx in perimeter_neighbors

    def test_no_duplicate_edges(self, sample_universe):
        """No duplicate edges in the graph."""
        edge_count = sample_universe.graph.ecount()
        # Each edge should appear exactly once
        assert edge_count == sample_universe.stargate_count


# =============================================================================
# Border System Tests
# =============================================================================


class TestBorderSystemsIdentified:
    """Test border system detection."""

    def test_uedama_is_border(self, sample_universe):
        """Uedama (high-sec adjacent to Sivala low-sec) is a border system."""
        uedama_idx = sample_universe.resolve_name("Uedama")
        assert uedama_idx in sample_universe.border_systems

    def test_jita_not_border(self, sample_universe):
        """Jita (not adjacent to low-sec) is not a border system."""
        jita_idx = sample_universe.resolve_name("Jita")
        assert jita_idx not in sample_universe.border_systems

    def test_lowsec_not_border(self, sample_universe):
        """Low-sec systems are not border systems."""
        sivala_idx = sample_universe.resolve_name("Sivala")
        assert sivala_idx not in sample_universe.border_systems

    def test_border_has_lowsec_neighbor(self, sample_universe):
        """Border systems have at least one low-sec neighbor."""
        for idx in sample_universe.border_systems:
            # Must be high-sec
            assert sample_universe.security[idx] >= 0.45
            # Must have at least one low/null neighbor
            neighbors = sample_universe.graph.neighbors(idx)
            assert any(sample_universe.security[n] < 0.45 for n in neighbors)


# =============================================================================
# Security Set Tests
# =============================================================================


class TestSecuritySetsPartition:
    """Test security set partitioning."""

    def test_all_systems_in_one_set(self, sample_universe):
        """Every system is in exactly one security set."""
        for i in range(sample_universe.system_count):
            in_high = i in sample_universe.highsec_systems
            in_low = i in sample_universe.lowsec_systems
            in_null = i in sample_universe.nullsec_systems

            count = sum([in_high, in_low, in_null])
            assert count == 1, f"System {i} appears in {count} security sets"

    def test_sets_cover_all_systems(self, sample_universe):
        """Security sets cover all systems."""
        total = (
            len(sample_universe.highsec_systems)
            + len(sample_universe.lowsec_systems)
            + len(sample_universe.nullsec_systems)
        )
        assert total == sample_universe.system_count

    def test_highsec_threshold(self, sample_universe):
        """High-sec systems have security >= 0.45."""
        for idx in sample_universe.highsec_systems:
            assert sample_universe.security[idx] >= 0.45

    def test_lowsec_threshold(self, sample_universe):
        """Low-sec systems have 0.0 < security < 0.45."""
        for idx in sample_universe.lowsec_systems:
            assert 0.0 < sample_universe.security[idx] < 0.45

    def test_nullsec_threshold(self, sample_universe):
        """Null-sec systems have security <= 0.0."""
        for idx in sample_universe.nullsec_systems:
            assert sample_universe.security[idx] <= 0.0


# =============================================================================
# Universe Roundtrip Tests
# =============================================================================


class TestUniverseRoundtrip:
    """Test .universe serialization and deserialization."""

    def test_saves_to_universe(self, sample_cache: Path, tmp_path: Path):
        """Builder saves .universe when output_path provided."""
        output = tmp_path / "universe.universe"
        build_universe_graph(sample_cache, output)
        assert output.exists()

    def test_universe_file_not_empty(self, sample_cache: Path, tmp_path: Path):
        """.universe file has content."""
        output = tmp_path / "universe.universe"
        build_universe_graph(sample_cache, output)
        assert output.stat().st_size > 0

    def test_roundtrip_preserves_system_count(self, sample_cache: Path, tmp_path: Path):
        """Graph survives save/load."""
        output = tmp_path / "universe.universe"
        original = build_universe_graph(sample_cache, output)
        # skip_integrity_check=True for test-generated graphs that don't match manifest
        loaded = load_universe_graph(output, skip_integrity_check=True)
        assert loaded.system_count == original.system_count

    def test_roundtrip_preserves_stargate_count(self, sample_cache: Path, tmp_path: Path):
        """Stargate count preserved after save/load."""
        output = tmp_path / "universe.universe"
        original = build_universe_graph(sample_cache, output)
        # skip_integrity_check=True for test-generated graphs that don't match manifest
        loaded = load_universe_graph(output, skip_integrity_check=True)
        assert loaded.stargate_count == original.stargate_count

    def test_roundtrip_preserves_name_resolution(self, sample_cache: Path, tmp_path: Path):
        """Name resolution works after save/load."""
        output = tmp_path / "universe.universe"
        build_universe_graph(sample_cache, output)
        # skip_integrity_check=True for test-generated graphs that don't match manifest
        loaded = load_universe_graph(output, skip_integrity_check=True)
        assert loaded.resolve_name("Jita") is not None
        assert loaded.resolve_name("jita") == loaded.resolve_name("JITA")


# =============================================================================
# Name Resolution Tests
# =============================================================================


class TestNameResolution:
    """Test name resolution after build."""

    def test_case_insensitive_resolution(self, sample_universe):
        """Name resolution is case-insensitive."""
        assert sample_universe.resolve_name("jita") == sample_universe.resolve_name("JITA")
        assert sample_universe.resolve_name("Jita") == sample_universe.resolve_name("jItA")

    def test_unknown_name_returns_none(self, sample_universe):
        """Unknown names return None."""
        assert sample_universe.resolve_name("NonexistentSystem") is None


# =============================================================================
# Region Index Tests
# =============================================================================


class TestRegionIndex:
    """Test region system index."""

    def test_region_systems_populated(self, sample_universe):
        """Region systems mapping is populated."""
        assert len(sample_universe.region_systems) > 0

    def test_region_contains_expected_systems(self, sample_universe):
        """Regions contain expected systems."""
        # The Forge (10000002) should have Jita, Perimeter, New Caldari
        forge_systems = sample_universe.region_systems.get(10000002, [])
        jita_idx = sample_universe.resolve_name("Jita")
        assert jita_idx in forge_systems

    def test_region_names_populated(self, sample_universe):
        """Region names mapping is populated."""
        assert 10000002 in sample_universe.region_names
        assert sample_universe.region_names[10000002] == "The Forge"


# =============================================================================
# Constellation Tests
# =============================================================================


class TestConstellationData:
    """Test constellation data in built graph."""

    def test_constellation_ids_populated(self, sample_universe):
        """Constellation IDs are populated for all systems."""
        assert len(sample_universe.constellation_ids) == sample_universe.system_count

    def test_constellation_names_populated(self, sample_universe):
        """Constellation names mapping is populated."""
        assert 20000020 in sample_universe.constellation_names
        assert sample_universe.constellation_names[20000020] == "Kimotoro"


# =============================================================================
# Version Metadata Tests
# =============================================================================


class TestVersionMetadata:
    """Test version metadata."""

    def test_version_set(self, sample_universe):
        """Version is set from generated field."""
        assert sample_universe.version == "2026-01-17T00:00:00Z"


# =============================================================================
# Default Path Tests
# =============================================================================


class TestDefaultPaths:
    """Test default path handling."""

    def test_default_cache_path_exists(self):
        """Default cache path points to existing file."""
        assert DEFAULT_CACHE_PATH.exists()

    def test_build_with_default_cache(self):
        """Can build from default cache path."""
        # This tests real data
        universe = build_universe_graph()
        assert universe.system_count > 5000  # EVE has ~8000+ systems


# =============================================================================
# Real Graph Tests (with actual universe_cache.json)
# =============================================================================


@pytest.mark.slow
@pytest.mark.benchmark
class TestRealGraphPerformance:
    """Performance tests with real universe data."""

    def test_build_produces_valid_graph(self):
        """Building from real cache produces valid graph."""
        universe = build_universe_graph()
        assert universe.system_count > 0
        assert universe.stargate_count > 0

    def test_known_systems_exist(self):
        """Known EVE systems exist in built graph."""
        universe = build_universe_graph()
        assert universe.resolve_name("Jita") is not None
        assert universe.resolve_name("Amarr") is not None
        assert universe.resolve_name("Dodixie") is not None

    def test_universe_size_reasonable(self, tmp_path: Path):
        """.universe file is under 2MB."""
        output = tmp_path / "universe.universe"
        build_universe_graph(output_path=output)
        size_mb = output.stat().st_size / (1024 * 1024)
        assert size_mb < 2.0, f"Universe graph size {size_mb:.2f}MB exceeds 2MB limit"

    def test_load_performance(self, tmp_path: Path):
        """Graph loads within 60ms latency budget.

        Note: Budget relaxed from 50ms to 60ms after P0 security changes
        uses safe msgpack serialization + checksum verification.
        The ~10ms overhead is acceptable for eliminating RCE vulnerability.
        """
        output = tmp_path / "universe.universe"
        build_universe_graph(output_path=output)

        start = time.perf_counter()
        # skip_integrity_check=True for test-generated graphs that don't match manifest
        load_universe_graph(output, skip_integrity_check=True)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.060, f"Load time {elapsed*1000:.1f}ms exceeds 60ms budget"
