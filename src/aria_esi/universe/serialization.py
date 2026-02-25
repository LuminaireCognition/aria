"""
Safe serialization for UniverseGraph.

This module provides pickle-free serialization using a hybrid format:
- msgpack for Python data structures (dicts, arrays, frozensets)
- Custom binary edge list for graph topology (no pickle)

Container format (.universe file):
    Offset  Size  Description
    0       4     Magic: b'ARIA'
    4       2     Version: 0x0002 (big-endian)
    6       4     Metadata length N (big-endian)
    10      N     msgpack metadata
    10+N    4     Graph length M (big-endian)
    14+N    M     Graph blob (format depends on version)

Graph blob format by version:
    v1: igraph picklez (gzipped pickle — DEPRECATED, read-only)
    v2: gzipped edge list — safe binary format:
        [uint32 n_vertices][uint32 n_edges][uint32 u, uint32 v]...

Security:
    v2 eliminates all pickle deserialization. The graph blob contains only
    unsigned 32-bit integers (vertex counts and edge pairs), making arbitrary
    code execution impossible during deserialization.

STP-001: Core Data Model - Safe Serialization Extension
"""

from __future__ import annotations

import gzip
import io
import struct
import warnings
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
FORMAT_VERSION = 2  # v2: safe binary edge list (no pickle)
HEADER_SIZE = 10  # 4 (magic) + 2 (version) + 4 (metadata length)

# Edge list binary format constants
_UINT32 = struct.Struct(">I")
_EDGE_PAIR = struct.Struct(">II")


class SerializationError(Exception):
    """Error during serialization or deserialization."""

    pass


# =============================================================================
# Safe Binary Edge List (v2)
# =============================================================================


def _graph_to_bytes(graph: ig.Graph) -> bytes:
    """
    Serialize an igraph graph to a gzipped binary edge list.

    Format: gzip([uint32 n_vertices][uint32 n_edges][uint32 u, uint32 v]...)

    Only topology is serialized — no vertex/edge attributes.

    Args:
        graph: igraph.Graph instance (must be undirected)

    Returns:
        Gzipped bytes containing the edge list

    Raises:
        SerializationError: If graph has too many vertices for uint32
    """
    n_vertices = graph.vcount()
    n_edges = graph.ecount()

    if n_vertices > 0xFFFFFFFF:
        raise SerializationError(f"Graph has {n_vertices} vertices, exceeding uint32 max")

    # Build raw buffer: header + edges
    buf = io.BytesIO()
    buf.write(_UINT32.pack(n_vertices))
    buf.write(_UINT32.pack(n_edges))

    for edge in graph.es:
        buf.write(_EDGE_PAIR.pack(edge.source, edge.target))

    return gzip.compress(buf.getvalue())


def _bytes_to_graph(data: bytes) -> ig.Graph:
    """
    Deserialize a gzipped binary edge list to an igraph graph.

    Performs strict validation:
    - Size checks to ensure complete data
    - Vertex index bounds checking for every edge

    Args:
        data: Gzipped bytes from _graph_to_bytes()

    Returns:
        igraph.Graph instance (undirected, no attributes)

    Raises:
        SerializationError: If data is malformed or contains invalid indices
    """
    try:
        raw = gzip.decompress(data)
    except Exception as e:
        raise SerializationError(f"Failed to decompress graph data: {e}") from e

    # Need at least 8 bytes for header (n_vertices + n_edges)
    if len(raw) < 8:
        raise SerializationError(f"Graph data too short: {len(raw)} bytes (minimum 8)")

    n_vertices = _UINT32.unpack_from(raw, 0)[0]
    n_edges = _UINT32.unpack_from(raw, 4)[0]

    expected_size = 8 + n_edges * 8
    if len(raw) != expected_size:
        raise SerializationError(
            f"Graph data size mismatch: expected {expected_size} bytes "
            f"(header + {n_edges} edges), got {len(raw)}"
        )

    # Parse edges with bounds checking
    edges: list[tuple[int, int]] = []
    offset = 8
    for i in range(n_edges):
        u, v = _EDGE_PAIR.unpack_from(raw, offset)
        if u >= n_vertices or v >= n_vertices:
            raise SerializationError(
                f"Edge {i} has out-of-range vertex index: ({u}, {v}) with n_vertices={n_vertices}"
            )
        edges.append((u, v))
        offset += 8

    return ig.Graph(n=n_vertices, edges=edges, directed=False)


# =============================================================================
# Save / Load
# =============================================================================


def save_universe_graph(universe: UniverseGraph, path: Path) -> None:
    """
    Serialize UniverseGraph to container format (always writes v2).

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

        # 3. Serialize graph to safe binary edge list
        graph_bytes = _graph_to_bytes(universe.graph)

        # 4. Build container
        with open(path, "wb") as f:
            # Magic bytes
            f.write(MAGIC)

            # Version (big-endian uint16) — always write v2
            f.write(struct.pack(">H", FORMAT_VERSION))

            # Metadata length + data
            f.write(struct.pack(">I", len(metadata_bytes)))
            f.write(metadata_bytes)

            # Graph length + data
            f.write(struct.pack(">I", len(graph_bytes)))
            f.write(graph_bytes)

        logger.debug(
            "Saved universe graph v2: metadata=%d bytes, graph=%d bytes",
            len(metadata_bytes),
            len(graph_bytes),
        )

    except Exception as e:
        raise SerializationError(f"Failed to save universe graph: {e}") from e


def load_universe_graph(path: Path) -> UniverseGraph:
    """
    Deserialize UniverseGraph from container format.

    Supports both v1 (legacy pickle, with deprecation warning) and v2 (safe edge list).

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

            # 4. Read graph blob
            graph_len_bytes = f.read(4)
            graph_len = struct.unpack(">I", graph_len_bytes)[0]
            graph_bytes = f.read(graph_len)

            # 5. Deserialize graph based on version
            if version == 1:
                # Legacy v1: igraph picklez (deprecated)
                warnings.warn(
                    "Loading v1 universe graph (pickle format). "
                    "Rebuild with 'uv run aria-esi universe --build' to upgrade to v2.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                logger.warning(
                    "Loading v1 universe graph (pickle). Rebuild to upgrade to safe v2 format."
                )
                graph_buffer = io.BytesIO(graph_bytes)
                graph = ig.Graph.Read_Picklez(graph_buffer)
            else:
                # v2: safe binary edge list
                graph = _bytes_to_graph(graph_bytes)

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
