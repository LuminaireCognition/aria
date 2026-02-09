"""
Tests for Universe Graph Serialization.

Tests safe serialization using msgpack + igraph picklez format.
"""

from __future__ import annotations

import struct
import tempfile
from pathlib import Path

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
        """FORMAT_VERSION is correctly defined."""
        from aria_esi.universe.serialization import FORMAT_VERSION

        assert FORMAT_VERSION == 1

    def test_header_size(self):
        """HEADER_SIZE is correctly defined."""
        from aria_esi.universe.serialization import HEADER_SIZE

        # 4 (magic) + 2 (version) + 4 (metadata length)
        assert HEADER_SIZE == 10


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
