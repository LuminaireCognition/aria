"""
Tests for UniverseGraph dataclass.

STP-001: Core Data Model Tests
"""

import struct

import igraph as ig
import numpy as np
import pytest

from aria_esi.universe import SecurityClass, SerializationError, UniverseGraph
from aria_esi.universe.serialization import (
    FORMAT_VERSION,
    MAGIC,
    detect_format,
    save_universe_graph,
)
from aria_esi.universe.serialization import (
    load_universe_graph as load_safe,
)


@pytest.fixture
def mock_universe() -> UniverseGraph:
    """
    Create a minimal mock universe for testing.

    Graph structure:
        Jita (high-sec 0.95) -- Perimeter (high-sec 0.90)
             |                        |
        Maurasi (high-sec 0.65) -- Urlen (high-sec 0.85)
             |
        Sivala (low-sec 0.35)
             |
        Ala (null-sec -0.2)

    Jita and Maurasi are border systems (adjacent to low-sec)
    """
    # Create graph with 6 systems
    g = ig.Graph(n=6, edges=[
        (0, 1),  # Jita -- Perimeter
        (0, 2),  # Jita -- Maurasi
        (1, 3),  # Perimeter -- Urlen
        (2, 3),  # Maurasi -- Urlen
        (2, 4),  # Maurasi -- Sivala
        (4, 5),  # Sivala -- Ala
    ], directed=False)

    # System data
    systems = [
        {"name": "Jita", "id": 30000142, "sec": 0.95, "const": 20000020, "region": 10000002},
        {"name": "Perimeter", "id": 30000144, "sec": 0.90, "const": 20000020, "region": 10000002},
        {"name": "Maurasi", "id": 30000140, "sec": 0.65, "const": 20000020, "region": 10000002},
        {"name": "Urlen", "id": 30000138, "sec": 0.85, "const": 20000020, "region": 10000002},
        {"name": "Sivala", "id": 30000160, "sec": 0.35, "const": 20000021, "region": 10000002},
        {"name": "Ala", "id": 30000161, "sec": -0.2, "const": 20000022, "region": 10000003},
    ]

    # Build indexes
    name_to_idx = {s["name"]: i for i, s in enumerate(systems)}
    idx_to_name = {i: s["name"] for i, s in enumerate(systems)}
    name_to_id = {s["name"]: s["id"] for s in systems}
    id_to_idx = {s["id"]: i for i, s in enumerate(systems)}
    name_lookup = {s["name"].lower(): s["name"] for s in systems}

    # Build numpy arrays
    security = np.array([s["sec"] for s in systems], dtype=np.float32)
    system_ids = np.array([s["id"] for s in systems], dtype=np.int32)
    constellation_ids = np.array([s["const"] for s in systems], dtype=np.int32)
    region_ids = np.array([s["region"] for s in systems], dtype=np.int32)

    # Build security sets
    highsec = frozenset(i for i in range(6) if security[i] >= 0.45)
    lowsec = frozenset(i for i in range(6) if 0.0 < security[i] < 0.45)
    nullsec = frozenset(i for i in range(6) if security[i] <= 0.0)

    # Border systems: high-sec systems adjacent to low/null-sec
    # Maurasi (idx=2) is adjacent to Sivala (low-sec)
    border = frozenset([2])

    # Region systems
    region_systems = {
        10000002: [0, 1, 2, 3, 4],  # The Forge
        10000003: [5],  # Some region for Ala
    }

    # Name lookups
    constellation_names = {
        20000020: "Kimotoro",
        20000021: "Otanuomi",
        20000022: "Somewhere",
    }
    region_names = {
        10000002: "The Forge",
        10000003: "Outer Region",
    }
    region_name_lookup = {name.lower(): rid for rid, name in region_names.items()}

    return UniverseGraph(
        graph=g,
        name_to_idx=name_to_idx,
        idx_to_name=idx_to_name,
        name_to_id=name_to_id,
        id_to_idx=id_to_idx,
        security=security,
        system_ids=system_ids,
        constellation_ids=constellation_ids,
        region_ids=region_ids,
        name_lookup=name_lookup,
        constellation_names=constellation_names,
        region_names=region_names,
        region_name_lookup=region_name_lookup,
        border_systems=border,
        region_systems=region_systems,
        highsec_systems=highsec,
        lowsec_systems=lowsec,
        nullsec_systems=nullsec,
        version="test-1.0",
        system_count=6,
        stargate_count=6,
    )


class TestResolveNameCaseInsensitive:
    """Test case-insensitive name resolution."""

    def test_lowercase(self, mock_universe: UniverseGraph):
        """Lowercase name resolves correctly."""
        assert mock_universe.resolve_name("jita") == 0

    def test_uppercase(self, mock_universe: UniverseGraph):
        """Uppercase name resolves correctly."""
        assert mock_universe.resolve_name("JITA") == 0

    def test_mixed_case(self, mock_universe: UniverseGraph):
        """Mixed case name resolves correctly."""
        assert mock_universe.resolve_name("JiTa") == 0

    def test_all_cases_equal(self, mock_universe: UniverseGraph):
        """All case variations resolve to same index."""
        lower = mock_universe.resolve_name("jita")
        upper = mock_universe.resolve_name("JITA")
        mixed = mock_universe.resolve_name("JiTa")
        proper = mock_universe.resolve_name("Jita")

        assert lower == upper == mixed == proper


class TestResolveNameUnknown:
    """Test unknown name handling."""

    def test_unknown_returns_none(self, mock_universe: UniverseGraph):
        """Unknown names return None."""
        assert mock_universe.resolve_name("NonexistentSystem") is None

    def test_empty_string_returns_none(self, mock_universe: UniverseGraph):
        """Empty string returns None."""
        assert mock_universe.resolve_name("") is None

    def test_partial_match_returns_none(self, mock_universe: UniverseGraph):
        """Partial matches don't resolve."""
        assert mock_universe.resolve_name("Jit") is None


class TestSecurityClassBoundaries:
    """Test security classification thresholds."""

    def test_high_sec_at_threshold(self, mock_universe: UniverseGraph):
        """Security exactly at 0.45 is HIGH."""
        # Modify security for testing boundary
        mock_universe.security[0] = 0.45
        assert mock_universe.security_class(0) == "HIGH"

    def test_high_sec_above_threshold(self, mock_universe: UniverseGraph):
        """Security above 0.45 is HIGH."""
        jita_idx = mock_universe.resolve_name("Jita")
        assert mock_universe.security_class(jita_idx) == "HIGH"

    def test_low_sec_below_threshold(self, mock_universe: UniverseGraph):
        """Security below 0.45 but above 0 is LOW."""
        sivala_idx = mock_universe.resolve_name("Sivala")
        assert mock_universe.security_class(sivala_idx) == "LOW"

    def test_null_sec_at_zero(self, mock_universe: UniverseGraph):
        """Security at 0.0 is NULL."""
        mock_universe.security[5] = 0.0
        assert mock_universe.security_class(5) == "NULL"

    def test_null_sec_negative(self, mock_universe: UniverseGraph):
        """Negative security is NULL."""
        ala_idx = mock_universe.resolve_name("Ala")
        assert mock_universe.security_class(ala_idx) == "NULL"

    def test_low_sec_boundary_just_above_zero(self, mock_universe: UniverseGraph):
        """Security just above 0.0 is LOW."""
        mock_universe.security[4] = 0.01
        assert mock_universe.security_class(4) == "LOW"

    def test_low_sec_boundary_just_below_threshold(self, mock_universe: UniverseGraph):
        """Security just below 0.45 is LOW."""
        mock_universe.security[4] = 0.44
        assert mock_universe.security_class(4) == "LOW"


class TestNeighborsWithSecurity:
    """Test neighbor query with security values."""

    def test_returns_valid_format(self, mock_universe: UniverseGraph):
        """Neighbor query returns correct format."""
        jita_idx = mock_universe.resolve_name("Jita")
        neighbors = mock_universe.neighbors_with_security(jita_idx)

        assert isinstance(neighbors, list)
        assert all(isinstance(n, tuple) and len(n) == 2 for n in neighbors)
        assert all(isinstance(n[0], int) and isinstance(n[1], float) for n in neighbors)

    def test_jita_neighbors(self, mock_universe: UniverseGraph):
        """Jita has correct neighbors."""
        jita_idx = mock_universe.resolve_name("Jita")
        neighbors = mock_universe.neighbors_with_security(jita_idx)

        # Jita is connected to Perimeter (1) and Maurasi (2)
        neighbor_indices = {n[0] for n in neighbors}
        assert neighbor_indices == {1, 2}

    def test_neighbor_security_values(self, mock_universe: UniverseGraph):
        """Neighbor security values are accurate."""
        jita_idx = mock_universe.resolve_name("Jita")
        neighbors = mock_universe.neighbors_with_security(jita_idx)

        for idx, sec in neighbors:
            expected_sec = float(mock_universe.security[idx])
            assert sec == pytest.approx(expected_sec, rel=1e-5)


class TestSystemInfo:
    """Test system information retrieval methods."""

    def test_get_system_id(self, mock_universe: UniverseGraph):
        """System ID retrieval works correctly."""
        jita_idx = mock_universe.resolve_name("Jita")
        assert mock_universe.get_system_id(jita_idx) == 30000142

    def test_get_region_name(self, mock_universe: UniverseGraph):
        """Region name retrieval works correctly."""
        jita_idx = mock_universe.resolve_name("Jita")
        assert mock_universe.get_region_name(jita_idx) == "The Forge"

    def test_get_region_name_unknown(self, mock_universe: UniverseGraph):
        """Unknown region returns 'Unknown'."""
        # Set an unknown region ID
        mock_universe.region_ids[0] = 99999999
        assert mock_universe.get_region_name(0) == "Unknown"

    def test_get_constellation_name(self, mock_universe: UniverseGraph):
        """Constellation name retrieval works correctly."""
        jita_idx = mock_universe.resolve_name("Jita")
        assert mock_universe.get_constellation_name(jita_idx) == "Kimotoro"

    def test_get_constellation_name_unknown(self, mock_universe: UniverseGraph):
        """Unknown constellation returns 'Unknown'."""
        mock_universe.constellation_ids[0] = 99999999
        assert mock_universe.get_constellation_name(0) == "Unknown"


class TestBorderSystems:
    """Test border system detection."""

    def test_is_border_system_true(self, mock_universe: UniverseGraph):
        """Border system correctly identified."""
        maurasi_idx = mock_universe.resolve_name("Maurasi")
        assert mock_universe.is_border_system(maurasi_idx) is True

    def test_is_border_system_false(self, mock_universe: UniverseGraph):
        """Non-border system correctly identified."""
        jita_idx = mock_universe.resolve_name("Jita")
        assert mock_universe.is_border_system(jita_idx) is False

    def test_get_adjacent_lowsec_for_border(self, mock_universe: UniverseGraph):
        """Border system returns adjacent low-sec systems."""
        maurasi_idx = mock_universe.resolve_name("Maurasi")
        adjacent = mock_universe.get_adjacent_lowsec(maurasi_idx)

        assert "Sivala" in adjacent

    def test_get_adjacent_lowsec_for_non_border(self, mock_universe: UniverseGraph):
        """Non-border system returns empty list."""
        jita_idx = mock_universe.resolve_name("Jita")
        adjacent = mock_universe.get_adjacent_lowsec(jita_idx)

        assert adjacent == []


class TestSecuritySets:
    """Test pre-computed security sets."""

    def test_highsec_systems(self, mock_universe: UniverseGraph):
        """High-sec systems correctly identified."""
        # Jita, Perimeter, Maurasi, Urlen are high-sec
        assert 0 in mock_universe.highsec_systems  # Jita
        assert 1 in mock_universe.highsec_systems  # Perimeter
        assert 2 in mock_universe.highsec_systems  # Maurasi
        assert 3 in mock_universe.highsec_systems  # Urlen

    def test_lowsec_systems(self, mock_universe: UniverseGraph):
        """Low-sec systems correctly identified."""
        assert 4 in mock_universe.lowsec_systems  # Sivala

    def test_nullsec_systems(self, mock_universe: UniverseGraph):
        """Null-sec systems correctly identified."""
        assert 5 in mock_universe.nullsec_systems  # Ala

    def test_security_sets_mutually_exclusive(self, mock_universe: UniverseGraph):
        """No system appears in multiple security sets."""
        for i in range(mock_universe.system_count):
            in_high = i in mock_universe.highsec_systems
            in_low = i in mock_universe.lowsec_systems
            in_null = i in mock_universe.nullsec_systems

            count = sum([in_high, in_low, in_null])
            assert count == 1, f"System {i} appears in {count} security sets"


class TestMetadata:
    """Test metadata attributes."""

    def test_system_count(self, mock_universe: UniverseGraph):
        """System count is accurate."""
        assert mock_universe.system_count == 6

    def test_stargate_count(self, mock_universe: UniverseGraph):
        """Stargate count is accurate."""
        assert mock_universe.stargate_count == 6

    def test_version(self, mock_universe: UniverseGraph):
        """Version string is set."""
        assert mock_universe.version == "test-1.0"


class TestModuleExports:
    """Test module exports."""

    def test_universe_graph_exported(self):
        """UniverseGraph is exported from universe module."""
        from aria_esi.universe import UniverseGraph
        assert UniverseGraph is not None

    def test_security_class_exported(self):
        """SecurityClass is exported from universe module."""
        assert SecurityClass is not None


class TestToDictRoundtrip:
    """Test to_dict() and from_dict() serialization."""

    def test_to_dict_returns_dict(self, mock_universe: UniverseGraph):
        """to_dict() returns a dictionary."""
        result = mock_universe.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_excludes_graph(self, mock_universe: UniverseGraph):
        """to_dict() does not include igraph instance."""
        result = mock_universe.to_dict()
        assert "graph" not in result

    def test_from_dict_reconstructs_data(self, mock_universe: UniverseGraph):
        """from_dict() reconstructs UniverseGraph correctly."""
        data = mock_universe.to_dict()
        restored = UniverseGraph.from_dict(data, mock_universe.graph)

        # Check all fields match
        assert restored.name_to_idx == mock_universe.name_to_idx
        assert restored.idx_to_name == mock_universe.idx_to_name
        assert restored.name_to_id == mock_universe.name_to_id
        assert restored.id_to_idx == mock_universe.id_to_idx
        assert restored.version == mock_universe.version
        assert restored.system_count == mock_universe.system_count
        assert restored.stargate_count == mock_universe.stargate_count

    def test_frozensets_restored(self, mock_universe: UniverseGraph):
        """Frozensets are restored correctly."""
        data = mock_universe.to_dict()
        restored = UniverseGraph.from_dict(data, mock_universe.graph)

        assert restored.border_systems == mock_universe.border_systems
        assert restored.highsec_systems == mock_universe.highsec_systems
        assert restored.lowsec_systems == mock_universe.lowsec_systems
        assert restored.nullsec_systems == mock_universe.nullsec_systems

    def test_name_lookup_preserved(self, mock_universe: UniverseGraph):
        """Name resolution works after roundtrip."""
        data = mock_universe.to_dict()
        restored = UniverseGraph.from_dict(data, mock_universe.graph)

        # Test case-insensitive lookup
        assert restored.resolve_name("jita") == mock_universe.resolve_name("jita")
        assert restored.resolve_name("PERIMETER") == mock_universe.resolve_name("PERIMETER")


class TestNumpyDtypePreserved:
    """Test NumPy array dtype preservation."""

    def test_security_dtype_float32(self, mock_universe: UniverseGraph):
        """Security array remains float32 after roundtrip."""
        data = mock_universe.to_dict()
        restored = UniverseGraph.from_dict(data, mock_universe.graph)

        assert restored.security.dtype == np.float32

    def test_system_ids_dtype_int32(self, mock_universe: UniverseGraph):
        """System IDs array remains int32 after roundtrip."""
        data = mock_universe.to_dict()
        restored = UniverseGraph.from_dict(data, mock_universe.graph)

        assert restored.system_ids.dtype == np.int32

    def test_constellation_ids_dtype_int32(self, mock_universe: UniverseGraph):
        """Constellation IDs array remains int32 after roundtrip."""
        data = mock_universe.to_dict()
        restored = UniverseGraph.from_dict(data, mock_universe.graph)

        assert restored.constellation_ids.dtype == np.int32

    def test_region_ids_dtype_int32(self, mock_universe: UniverseGraph):
        """Region IDs array remains int32 after roundtrip."""
        data = mock_universe.to_dict()
        restored = UniverseGraph.from_dict(data, mock_universe.graph)

        assert restored.region_ids.dtype == np.int32

    def test_security_values_match(self, mock_universe: UniverseGraph):
        """Security values are identical after roundtrip."""
        data = mock_universe.to_dict()
        restored = UniverseGraph.from_dict(data, mock_universe.graph)

        np.testing.assert_array_equal(restored.security, mock_universe.security)


class TestSafeFileRoundtrip:
    """Test file serialization with safe format."""

    def test_save_creates_file(self, mock_universe: UniverseGraph, tmp_path):
        """save_universe_graph creates a file."""
        path = tmp_path / "test.universe"
        save_universe_graph(mock_universe, path)

        assert path.exists()
        assert path.stat().st_size > 0

    def test_load_restores_data(self, mock_universe: UniverseGraph, tmp_path):
        """load_universe_graph restores data correctly."""
        path = tmp_path / "test.universe"
        save_universe_graph(mock_universe, path)

        restored = load_safe(path)

        assert restored.system_count == mock_universe.system_count
        assert restored.stargate_count == mock_universe.stargate_count
        assert restored.version == mock_universe.version

    def test_name_resolution_works_after_load(self, mock_universe: UniverseGraph, tmp_path):
        """Name resolution works after file roundtrip."""
        path = tmp_path / "test.universe"
        save_universe_graph(mock_universe, path)

        restored = load_safe(path)

        assert restored.resolve_name("jita") == 0
        assert restored.resolve_name("Perimeter") == 1

    def test_graph_queries_work_after_load(self, mock_universe: UniverseGraph, tmp_path):
        """Graph queries work after file roundtrip."""
        path = tmp_path / "test.universe"
        save_universe_graph(mock_universe, path)

        restored = load_safe(path)

        # Test neighbor query
        jita_idx = restored.resolve_name("Jita")
        neighbors = restored.neighbors_with_security(jita_idx)
        assert len(neighbors) > 0

    def test_security_sets_work_after_load(self, mock_universe: UniverseGraph, tmp_path):
        """Security set membership works after file roundtrip."""
        path = tmp_path / "test.universe"
        save_universe_graph(mock_universe, path)

        restored = load_safe(path)

        # Jita should be in highsec
        jita_idx = restored.resolve_name("Jita")
        assert jita_idx in restored.highsec_systems


class TestFormatDetection:
    """Test file format detection."""

    def test_detect_universe_format(self, mock_universe: UniverseGraph, tmp_path):
        """Detect .universe format by magic bytes."""
        path = tmp_path / "test.universe"
        save_universe_graph(mock_universe, path)

        assert detect_format(path) == "universe"

    def test_detect_pickle_format(self, mock_universe: UniverseGraph, tmp_path):
        """Detect pickle format by magic bytes."""
        import pickle

        path = tmp_path / "test.pkl"
        with open(path, "wb") as f:
            pickle.dump(mock_universe, f, protocol=pickle.HIGHEST_PROTOCOL)

        assert detect_format(path) == "pickle"


class TestRejectsInvalidMagic:
    """Test rejection of invalid file formats."""

    def test_rejects_wrong_magic(self, tmp_path):
        """File with wrong magic bytes is rejected."""
        path = tmp_path / "bad.universe"
        with open(path, "wb") as f:
            f.write(b"BAAD")  # Wrong magic
            f.write(struct.pack(">H", FORMAT_VERSION))
            f.write(struct.pack(">I", 0))

        with pytest.raises(SerializationError, match="Invalid file format"):
            load_safe(path)

    def test_rejects_empty_file(self, tmp_path):
        """Empty file is rejected."""
        path = tmp_path / "empty.universe"
        path.write_bytes(b"")

        with pytest.raises(SerializationError):
            load_safe(path)

    def test_rejects_truncated_file(self, tmp_path):
        """Truncated file is rejected."""
        path = tmp_path / "truncated.universe"
        with open(path, "wb") as f:
            f.write(MAGIC)
            # Missing version and data

        with pytest.raises(SerializationError):
            load_safe(path)


class TestRejectsFutureVersion:
    """Test rejection of unsupported format versions."""

    def test_rejects_future_version(self, tmp_path):
        """File with future version is rejected."""
        path = tmp_path / "future.universe"
        with open(path, "wb") as f:
            f.write(MAGIC)
            f.write(struct.pack(">H", FORMAT_VERSION + 100))  # Future version
            f.write(struct.pack(">I", 0))
            f.write(struct.pack(">I", 0))

        with pytest.raises(SerializationError, match="Unsupported format version"):
            load_safe(path)
