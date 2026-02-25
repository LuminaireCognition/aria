"""
Tests for Universe Graph Serialization.

Tests safe serialization using msgpack + safe binary edge list format (v2).
"""

from __future__ import annotations

import gzip
import io
import struct
import tempfile
import warnings
from pathlib import Path

import igraph as ig
import pytest

from tests.mcp.conftest import create_mock_universe, STANDARD_SYSTEMS, STANDARD_EDGES


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def standard_universe():
    """Standard 6-system universe for serialization tests."""
    return create_mock_universe(STANDARD_SYSTEMS, STANDARD_EDGES)


@pytest.fixture
def temp_file():
    """Temporary file for serialization tests."""
    with tempfile.NamedTemporaryFile(suffix=".universe", delete=False) as f:
        yield Path(f.name)
    # Cleanup
    Path(f.name).unlink(missing_ok=True)


# =============================================================================
# SerializationError Tests
# =============================================================================


class TestSerializationError:
    """Test SerializationError exception."""

    def test_can_instantiate(self):
        """Can create SerializationError."""
        from aria_esi.universe.serialization import SerializationError

        error = SerializationError("Test error")
        assert str(error) == "Test error"

    def test_is_exception(self):
        """SerializationError is an Exception."""
        from aria_esi.universe.serialization import SerializationError

        assert issubclass(SerializationError, Exception)


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Test module constants."""

    def test_magic_bytes(self):
        """MAGIC is correctly defined."""
        from aria_esi.universe.serialization import MAGIC

        assert MAGIC == b"ARIA"

    def test_format_version(self):
        """FORMAT_VERSION is 2 (safe binary edge list)."""
        from aria_esi.universe.serialization import FORMAT_VERSION

        assert FORMAT_VERSION == 2

    def test_header_size(self):
        """HEADER_SIZE is correctly defined."""
        from aria_esi.universe.serialization import HEADER_SIZE

        # 4 (magic) + 2 (version) + 4 (metadata length)
        assert HEADER_SIZE == 10


# =============================================================================
# Safe Binary Edge List Tests
# =============================================================================


class TestSafeEdgeList:
    """Test the safe binary edge list format (v2 graph blob)."""

    def test_roundtrip_simple_graph(self):
        """Simple graph survives roundtrip through binary format."""
        from aria_esi.universe.serialization import _bytes_to_graph, _graph_to_bytes

        graph = ig.Graph(n=4, edges=[(0, 1), (1, 2), (2, 3)], directed=False)
        data = _graph_to_bytes(graph)
        restored = _bytes_to_graph(data)

        assert restored.vcount() == 4
        assert restored.ecount() == 3
        assert set(restored.get_edgelist()) == {(0, 1), (1, 2), (2, 3)}

    def test_roundtrip_empty_graph(self):
        """Empty graph (no edges) survives roundtrip."""
        from aria_esi.universe.serialization import _bytes_to_graph, _graph_to_bytes

        graph = ig.Graph(n=5, edges=[], directed=False)
        data = _graph_to_bytes(graph)
        restored = _bytes_to_graph(data)

        assert restored.vcount() == 5
        assert restored.ecount() == 0

    def test_roundtrip_zero_vertex_graph(self):
        """Graph with zero vertices survives roundtrip."""
        from aria_esi.universe.serialization import _bytes_to_graph, _graph_to_bytes

        graph = ig.Graph(n=0, edges=[], directed=False)
        data = _graph_to_bytes(graph)
        restored = _bytes_to_graph(data)

        assert restored.vcount() == 0
        assert restored.ecount() == 0

    def test_malformed_data_too_short(self):
        """Rejects data that is too short."""
        from aria_esi.universe.serialization import SerializationError, _bytes_to_graph

        # Gzip some data that's too short for the header
        data = gzip.compress(b"\x00\x00")

        with pytest.raises(SerializationError, match="too short"):
            _bytes_to_graph(data)

    def test_malformed_data_wrong_size(self):
        """Rejects data with incorrect size for claimed edge count."""
        from aria_esi.universe.serialization import SerializationError, _bytes_to_graph

        # Header claims 2 edges but only provides data for 1
        buf = struct.pack(">II", 3, 2)  # 3 vertices, 2 edges
        buf += struct.pack(">II", 0, 1)  # Only 1 edge
        data = gzip.compress(buf)

        with pytest.raises(SerializationError, match="size mismatch"):
            _bytes_to_graph(data)

    def test_out_of_range_vertex_index(self):
        """Rejects edges with vertex index >= n_vertices."""
        from aria_esi.universe.serialization import SerializationError, _bytes_to_graph

        # 3 vertices, edge (0, 5) — 5 is out of range
        buf = struct.pack(">II", 3, 1)  # 3 vertices, 1 edge
        buf += struct.pack(">II", 0, 5)  # vertex 5 out of range
        data = gzip.compress(buf)

        with pytest.raises(SerializationError, match="out-of-range"):
            _bytes_to_graph(data)

    def test_bad_gzip_data(self):
        """Rejects data that isn't valid gzip."""
        from aria_esi.universe.serialization import SerializationError, _bytes_to_graph

        with pytest.raises(SerializationError, match="decompress"):
            _bytes_to_graph(b"not gzip data")

    def test_graph_is_undirected(self):
        """Restored graph is undirected."""
        from aria_esi.universe.serialization import _bytes_to_graph, _graph_to_bytes

        graph = ig.Graph(n=3, edges=[(0, 1)], directed=False)
        data = _graph_to_bytes(graph)
        restored = _bytes_to_graph(data)

        assert not restored.is_directed()


# =============================================================================
# V1 Migration Tests
# =============================================================================


class TestV1Migration:
    """Test loading v1 (pickle) files and migration to v2."""

    def test_v1_file_loads_with_deprecation_warning(self, standard_universe, temp_file):
        """v1 file loads successfully but emits deprecation warning."""
        from aria_esi.universe.serialization import (
            MAGIC,
            load_universe_graph,
        )

        # Build a v1 file manually (with pickle graph blob)
        import msgpack

        metadata = standard_universe.to_dict()
        metadata_bytes = msgpack.packb(metadata, use_bin_type=True)

        graph_buffer = io.BytesIO()
        standard_universe.graph.write_picklez(graph_buffer)
        graph_bytes = graph_buffer.getvalue()

        with open(temp_file, "wb") as f:
            f.write(MAGIC)
            f.write(struct.pack(">H", 1))  # Version 1
            f.write(struct.pack(">I", len(metadata_bytes)))
            f.write(metadata_bytes)
            f.write(struct.pack(">I", len(graph_bytes)))
            f.write(graph_bytes)

        # Load should work but warn
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            loaded = load_universe_graph(temp_file)

        assert loaded.graph.vcount() == standard_universe.graph.vcount()
        assert loaded.graph.ecount() == standard_universe.graph.ecount()

        deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1
        assert "v1" in str(deprecation_warnings[0].message).lower()

    def test_save_always_writes_v2(self, standard_universe, temp_file):
        """save_universe_graph always writes v2 format."""
        from aria_esi.universe.serialization import FORMAT_VERSION, save_universe_graph

        save_universe_graph(standard_universe, temp_file)

        with open(temp_file, "rb") as f:
            f.read(4)  # Skip magic
            version = struct.unpack(">H", f.read(2))[0]
            assert version == FORMAT_VERSION
            assert version == 2


# =============================================================================
# Save/Load Roundtrip Tests
# =============================================================================


class TestSaveLoadRoundtrip:
    """Test save_universe_graph and load_universe_graph functions."""

    def test_roundtrip_preserves_graph(self, standard_universe, temp_file):
        """Save and load preserves graph structure."""
        from aria_esi.universe.serialization import (
            load_universe_graph,
            save_universe_graph,
        )

        # Save
        save_universe_graph(standard_universe, temp_file)

        # Load
        loaded = load_universe_graph(temp_file)

        # Verify graph structure
        assert loaded.graph.vcount() == standard_universe.graph.vcount()
        assert loaded.graph.ecount() == standard_universe.graph.ecount()

    def test_roundtrip_preserves_systems(self, standard_universe, temp_file):
        """Save and load preserves system names."""
        from aria_esi.universe.serialization import (
            load_universe_graph,
            save_universe_graph,
        )

        save_universe_graph(standard_universe, temp_file)
        loaded = load_universe_graph(temp_file)

        # Verify system names preserved (idx_to_name maps index to name)
        assert loaded.idx_to_name == standard_universe.idx_to_name

    def test_roundtrip_preserves_security(self, standard_universe, temp_file):
        """Save and load preserves security status."""
        from aria_esi.universe.serialization import (
            load_universe_graph,
            save_universe_graph,
        )

        save_universe_graph(standard_universe, temp_file)
        loaded = load_universe_graph(temp_file)

        # Verify security values preserved
        assert list(loaded.security) == list(standard_universe.security)

    def test_roundtrip_preserves_name_index(self, standard_universe, temp_file):
        """Save and load preserves name-to-index mapping."""
        from aria_esi.universe.serialization import (
            load_universe_graph,
            save_universe_graph,
        )

        save_universe_graph(standard_universe, temp_file)
        loaded = load_universe_graph(temp_file)

        # Verify name index preserved
        assert loaded.name_to_idx == standard_universe.name_to_idx

    def test_roundtrip_preserves_border_status(self, standard_universe, temp_file):
        """Save and load preserves border system status."""
        from aria_esi.universe.serialization import (
            load_universe_graph,
            save_universe_graph,
        )

        save_universe_graph(standard_universe, temp_file)
        loaded = load_universe_graph(temp_file)

        # Verify border_systems preserved (frozenset of border system indices)
        assert loaded.border_systems == standard_universe.border_systems

    def test_file_created(self, standard_universe, temp_file):
        """Save creates file."""
        from aria_esi.universe.serialization import save_universe_graph

        save_universe_graph(standard_universe, temp_file)

        assert temp_file.exists()
        assert temp_file.stat().st_size > 0


# =============================================================================
# File Format Tests
# =============================================================================


class TestFileFormat:
    """Test the container file format."""

    def test_magic_bytes_written(self, standard_universe, temp_file):
        """File starts with ARIA magic bytes."""
        from aria_esi.universe.serialization import MAGIC, save_universe_graph

        save_universe_graph(standard_universe, temp_file)

        with open(temp_file, "rb") as f:
            magic = f.read(4)
            assert magic == MAGIC

    def test_version_written(self, standard_universe, temp_file):
        """File contains version number."""
        from aria_esi.universe.serialization import FORMAT_VERSION, save_universe_graph

        save_universe_graph(standard_universe, temp_file)

        with open(temp_file, "rb") as f:
            f.read(4)  # Skip magic
            version_bytes = f.read(2)
            version = struct.unpack(">H", version_bytes)[0]
            assert version == FORMAT_VERSION


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestLoadErrors:
    """Test load_universe_graph error handling."""

    def test_invalid_magic(self, temp_file):
        """Raises SerializationError for invalid magic."""
        from aria_esi.universe.serialization import load_universe_graph, SerializationError

        # Write file with wrong magic
        with open(temp_file, "wb") as f:
            f.write(b"FAKE")

        with pytest.raises(SerializationError) as exc_info:
            load_universe_graph(temp_file)

        assert "magic" in str(exc_info.value).lower()

    def test_unsupported_version(self, temp_file):
        """Raises SerializationError for unsupported version."""
        from aria_esi.universe.serialization import (
            MAGIC,
            SerializationError,
            load_universe_graph,
        )

        # Write file with future version
        with open(temp_file, "wb") as f:
            f.write(MAGIC)
            f.write(struct.pack(">H", 999))  # Version 999

        with pytest.raises(SerializationError) as exc_info:
            load_universe_graph(temp_file)

        assert "version" in str(exc_info.value).lower()

    def test_nonexistent_file(self, temp_file):
        """Raises SerializationError for nonexistent file."""
        from aria_esi.universe.serialization import SerializationError, load_universe_graph

        # Ensure file doesn't exist
        temp_file.unlink(missing_ok=True)

        with pytest.raises(SerializationError):
            load_universe_graph(temp_file)


# =============================================================================
# Format Detection Tests
# =============================================================================


class TestDetectFormat:
    """Test detect_format function."""

    def test_detects_universe_format(self, standard_universe, temp_file):
        """Detects .universe format correctly."""
        from aria_esi.universe.serialization import detect_format, save_universe_graph

        save_universe_graph(standard_universe, temp_file)
        result = detect_format(temp_file)

        assert result == "universe"

    def test_detects_pickle_format(self, temp_file):
        """Detects pickle format by protocol marker."""
        from aria_esi.universe.serialization import detect_format

        # Write fake pickle header (protocol 4)
        with open(temp_file, "wb") as f:
            f.write(b"\x80\x04")

        result = detect_format(temp_file)
        assert result == "pickle"

    def test_detects_unknown_format(self, temp_file):
        """Returns unknown for unrecognized format."""
        from aria_esi.universe.serialization import detect_format

        # Write random data
        with open(temp_file, "wb") as f:
            f.write(b"random data here")

        result = detect_format(temp_file)
        assert result == "unknown"

    def test_empty_file(self, temp_file):
        """Handles empty file."""
        from aria_esi.universe.serialization import detect_format

        # Create empty file
        with open(temp_file, "wb") as f:
            pass

        result = detect_format(temp_file)
        assert result == "unknown"

    def test_nonexistent_file_raises(self):
        """Raises SerializationError for nonexistent file."""
        from aria_esi.universe.serialization import SerializationError, detect_format

        with pytest.raises(SerializationError):
            detect_format(Path("/nonexistent/file.universe"))
