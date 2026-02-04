"""
Safe serialization for UniverseGraph.

This module provides pickle-free serialization using a hybrid format:
- msgpack for Python data structures (dicts, arrays, frozensets)
- igraph's native binary format for graph topology

Container format (.universe file):
    Offset  Size  Description
    0       4     Magic: b'ARIA'
    4       2     Version: 0x0001 (big-endian)
    6       4     Metadata length N (big-endian)
    10      N     msgpack metadata
    10+N    4     Graph length M (big-endian)
    14+N    M     igraph picklez blob (gzipped)

Security:
    This format eliminates pickle.load() for Python data, removing the
    primary RCE attack vector. The igraph picklez format is still used
    for graph topology, but only contains graph structure (vertices/edges),
    not arbitrary Python objects.

STP-001: Core Data Model - Safe Serialization Extension
"""

from __future__ import annotations

import io
import struct
from pathlib import Path
from typing import TYPE_CHECKING

import igraph as ig
import msgpack

from aria_esi.core.logging import get_logger

if TYPE_CHECKING:
    from aria_esi.universe.graph import UniverseGraph

logger = get_logger(__name__)

# Container format constants
MAGIC = b"ARIA"
FORMAT_VERSION = 1  # Increment when format changes incompatibly
HEADER_SIZE = 10  # 4 (magic) + 2 (version) + 4 (metadata length)


class SerializationError(Exception):
    """Error during serialization or deserialization."""

    pass


def save_universe_graph(universe: UniverseGraph, path: Path) -> None:
    """
    Serialize UniverseGraph to container format.

    Args:
        universe: UniverseGraph instance to serialize
        path: Output file path (should use .universe extension)

    Raises:
        SerializationError: If serialization fails
    """
    try:
        # 1. Convert Python data to dict
        metadata = universe.to_dict()

        # 2. Pack metadata with msgpack
        metadata_bytes = msgpack.packb(metadata, use_bin_type=True)

        # 3. Serialize igraph to picklez (gzipped binary)
        graph_buffer = io.BytesIO()
        universe.graph.write_picklez(graph_buffer)
        graph_bytes = graph_buffer.getvalue()

        # 4. Build container
        with open(path, "wb") as f:
            # Magic bytes
            f.write(MAGIC)

            # Version (big-endian uint16)
            f.write(struct.pack(">H", FORMAT_VERSION))

            # Metadata length + data
            f.write(struct.pack(">I", len(metadata_bytes)))
            f.write(metadata_bytes)

            # Graph length + data
            f.write(struct.pack(">I", len(graph_bytes)))
            f.write(graph_bytes)

        logger.debug(
            "Saved universe graph: metadata=%d bytes, graph=%d bytes",
            len(metadata_bytes),
            len(graph_bytes),
        )

    except Exception as e:
        raise SerializationError(f"Failed to save universe graph: {e}") from e


def load_universe_graph(path: Path) -> UniverseGraph:
    """
    Deserialize UniverseGraph from container format.

    Args:
        path: Path to .universe file

    Returns:
        Reconstructed UniverseGraph instance

    Raises:
        SerializationError: If file format is invalid or unsupported
    """
    # Import here to avoid circular dependency
    from aria_esi.universe.graph import UniverseGraph

    try:
        with open(path, "rb") as f:
            # 1. Validate magic bytes
            magic = f.read(4)
            if magic != MAGIC:
                raise SerializationError(
                    f"Invalid file format: expected magic {MAGIC!r}, got {magic!r}"
                )

            # 2. Check version
            version_bytes = f.read(2)
            version = struct.unpack(">H", version_bytes)[0]
            if version > FORMAT_VERSION:
                raise SerializationError(
                    f"Unsupported format version: {version} (max supported: {FORMAT_VERSION})"
                )

            # 3. Read metadata
            metadata_len_bytes = f.read(4)
            metadata_len = struct.unpack(">I", metadata_len_bytes)[0]
            metadata_bytes = f.read(metadata_len)
            metadata = msgpack.unpackb(metadata_bytes, raw=False)

            # 4. Read graph
            graph_len_bytes = f.read(4)
            graph_len = struct.unpack(">I", graph_len_bytes)[0]
            graph_bytes = f.read(graph_len)

            # 5. Reconstruct igraph from picklez
            graph_buffer = io.BytesIO(graph_bytes)
            graph = ig.Graph.Read_Picklez(graph_buffer)

            # 6. Reconstruct UniverseGraph
            return UniverseGraph.from_dict(metadata, graph)

    except SerializationError:
        raise
    except Exception as e:
        raise SerializationError(f"Failed to load universe graph: {e}") from e


def detect_format(path: Path) -> str:
    """
    Detect file format by magic bytes.

    Args:
        path: Path to graph file

    Returns:
        Format string: "universe" for new format, "pickle" for legacy

    Raises:
        SerializationError: If file is empty or unreadable
    """
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
            if magic == MAGIC:
                return "universe"
            # Pickle files start with various protocol markers
            # Protocol 4+ starts with 0x80 0x04
            # Protocol 5+ starts with 0x80 0x05
            if magic and magic[0] == 0x80:
                return "pickle"
            # Could be protocol 0-2 (text-based) or other format
            return "unknown"
    except Exception as e:
        raise SerializationError(f"Cannot detect format for {path}: {e}") from e
