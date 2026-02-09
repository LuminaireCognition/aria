"""
Graph Builder - Convert universe_cache.json to optimized UniverseGraph.

This module provides the build pipeline that converts the JSON universe cache
into an optimized binary file containing a fully-indexed UniverseGraph.

STP-003: Graph Builder

Security:
    The .universe format uses msgpack for Python data and igraph's native
    format for graph topology, eliminating pickle.load() for arbitrary
    Python objects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import igraph as ig
import numpy as np

from aria_esi.core.logging import get_logger

from .graph import UniverseGraph
from .serialization import (
    SerializationError,
    detect_format,
)
from .serialization import (
    load_universe_graph as load_safe,
)
from .serialization import (
    save_universe_graph as save_safe,
)

if TYPE_CHECKING:
    from typing import Any

logger = get_logger(__name__)


class UniverseBuildError(Exception):
    """Error building or loading universe graph."""

    pass


# Default paths relative to package
DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_CACHE_PATH = DATA_DIR / "universe_cache.json"
# New default: .universe format (safe serialization)
DEFAULT_GRAPH_PATH = DATA_DIR / "universe.universe"


def build_universe_graph(
    cache_path: Path | None = None,
    output_path: Path | None = None,
) -> UniverseGraph:
    """
    Convert universe_cache.json to optimized UniverseGraph.

    Args:
        cache_path: Path to universe_cache.json (defaults to package data dir)
        output_path: Optional path to save .universe graph

    Returns:
        UniverseGraph instance ready for queries
    """
    if cache_path is None:
        cache_path = DEFAULT_CACHE_PATH

    # Load and validate JSON cache
    try:
        with open(cache_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise UniverseBuildError(
            f"Universe cache not found: {cache_path}\n"
            "Run 'uv run aria-esi universe --build' to generate it."
        )
    except json.JSONDecodeError as e:
        raise UniverseBuildError(
            f"Invalid JSON in universe cache: {cache_path}\n"
            f"Parse error: {e}\n"
            "The cache file may be corrupted. Try rebuilding with 'uv run aria-esi universe --build'."
        )

    # Validate required keys
    required_keys = ["systems", "stargates"]
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise UniverseBuildError(
            f"Universe cache missing required keys: {missing}\n"
            "The cache file may be from an older version. Try rebuilding."
        )

    systems = data["systems"]
    stargates = data["stargates"]
    constellations = data.get("constellations", {})
    regions = data.get("regions", {})

    # Build stable vertex ordering (sorted by system_id)
    # Note: system IDs are stored as string keys in JSON
    system_list = sorted(
        [(int(sys_id), sys_data) for sys_id, sys_data in systems.items()],
        key=lambda x: x[0],
    )
    n = len(system_list)

    # Build name indexes
    name_to_idx = {sys[1]["name"]: i for i, sys in enumerate(system_list)}
    idx_to_name = {i: sys[1]["name"] for i, sys in enumerate(system_list)}
    name_to_id = {sys[1]["name"]: sys[0] for sys in system_list}
    id_to_idx = {sys[0]: i for i, sys in enumerate(system_list)}
    name_lookup = {sys[1]["name"].lower(): sys[1]["name"] for sys in system_list}

    # Resolve region_id for each system via constellation
    # constellation_id -> region_id mapping
    const_to_region = {
        int(const_id): const_data.get("region_id", 0)
        for const_id, const_data in constellations.items()
    }

    # Build edge list from stargates
    edges = _build_edge_list(system_list, stargates, name_to_idx, id_to_idx)

    # Create igraph
    g = ig.Graph(n=n, edges=list(edges), directed=False)

    # Vectorized attributes
    security = np.array(
        [sys[1]["security"] for sys in system_list],
        dtype=np.float32,
    )
    system_ids = np.array(
        [sys[0] for sys in system_list],
        dtype=np.int32,
    )
    constellation_ids = np.array(
        [sys[1]["constellation_id"] for sys in system_list],
        dtype=np.int32,
    )
    # Get region_id via constellation lookup
    region_ids = np.array(
        [const_to_region.get(sys[1]["constellation_id"], 0) for sys in system_list],
        dtype=np.int32,
    )

    # Pre-compute security sets
    highsec = frozenset(i for i in range(n) if security[i] >= 0.45)
    lowsec = frozenset(i for i in range(n) if 0.0 < security[i] < 0.45)
    nullsec = frozenset(i for i in range(n) if security[i] <= 0.0)

    # Pre-compute border systems
    border_systems = _compute_border_systems(g, security, highsec)

    # Region index
    region_systems = _build_region_index(system_list, const_to_region)

    # Name lookups for constellations and regions
    constellation_names = {int(k): v["name"] for k, v in constellations.items()}
    region_names = {int(k): v["name"] for k, v in regions.items()}

    # O(1) region name resolution (case-insensitive)
    region_name_lookup = {v["name"].lower(): int(k) for k, v in regions.items()}

    universe = UniverseGraph(
        graph=g,
        name_to_idx=name_to_idx,
        idx_to_name=idx_to_name,
        name_to_id=name_to_id,
        id_to_idx=id_to_idx,
        name_lookup=name_lookup,
        security=security,
        system_ids=system_ids,
        constellation_ids=constellation_ids,
        region_ids=region_ids,
        constellation_names=constellation_names,
        region_names=region_names,
        region_name_lookup=region_name_lookup,
        border_systems=border_systems,
        region_systems=region_systems,
        highsec_systems=highsec,
        lowsec_systems=lowsec,
        nullsec_systems=nullsec,
        version=data.get("generated", "unknown"),
        system_count=n,
        stargate_count=len(edges),
    )

    if output_path:
        # Use safe serialization format
        save_safe(universe, output_path)
        logger.info("Saved universe graph to %s (safe format)", output_path)

    return universe


def _build_edge_list(
    system_list: list[tuple[int, dict[str, Any]]],
    stargates: dict[str, dict[str, Any]],
    name_to_idx: dict[str, int],
    id_to_idx: dict[int, int],
) -> set[tuple[int, int]]:
    """
    Build undirected edge set from stargate data.

    Args:
        system_list: List of (system_id, system_data) tuples
        stargates: Stargate data mapping gate_id -> {destination_system_id}
        name_to_idx: System name to vertex index mapping
        id_to_idx: System ID to vertex index mapping

    Returns:
        Set of (src_idx, dst_idx) tuples with normalized edge direction
    """
    edges: set[tuple[int, int]] = set()
    for sys_id, sys_data in system_list:
        src_idx = id_to_idx[sys_id]
        for gate_id in sys_data.get("stargates", []):
            gate = stargates.get(str(gate_id))
            if gate:
                dest_id = gate["destination_system_id"]
                if dest_id in id_to_idx:
                    dst_idx = id_to_idx[dest_id]
                    # Normalize edge direction for deduplication
                    edge = (min(src_idx, dst_idx), max(src_idx, dst_idx))
                    edges.add(edge)
    return edges


def _compute_border_systems(
    g: ig.Graph,
    security: np.ndarray,
    highsec: frozenset[int],
) -> frozenset[int]:
    """
    Identify high-sec systems adjacent to low/null-sec.

    Args:
        g: igraph Graph instance
        security: Array of security values indexed by vertex
        highsec: Set of high-sec vertex indices

    Returns:
        Set of border system vertex indices
    """
    return frozenset(
        v for v in highsec if g.neighbors(v) and any(security[n] < 0.45 for n in g.neighbors(v))
    )


def _build_region_index(
    system_list: list[tuple[int, dict[str, Any]]],
    const_to_region: dict[int, int],
) -> dict[int, list[int]]:
    """
    Build region_id -> [vertex_idx, ...] mapping.

    Args:
        system_list: List of (system_id, system_data) tuples
        const_to_region: Constellation ID to region ID mapping

    Returns:
        Mapping of region IDs to lists of vertex indices
    """
    region_systems: dict[int, list[int]] = {}
    for i, (_, sys_data) in enumerate(system_list):
        rid = const_to_region.get(sys_data["constellation_id"], 0)
        if rid not in region_systems:
            region_systems[rid] = []
        region_systems[rid].append(i)
    return region_systems


def load_universe_graph(
    graph_path: Path | None = None,
    *,
    skip_integrity_check: bool = False,
) -> UniverseGraph:
    """
    Load pre-built universe graph from file.

    Supports only the .universe format (safe serialization).

    Args:
        graph_path: Path to graph file (defaults to package data dir)
        skip_integrity_check: Skip checksum verification (for testing only)

    Returns:
        UniverseGraph instance ready for queries

    Raises:
        UniverseBuildError: If the file is missing, corrupted, or incompatible
        IntegrityError: If checksum verification fails

    Security:
        The .universe format uses msgpack for metadata, eliminating pickle
        deserialization of arbitrary Python objects.
    """
    if graph_path is None:
        if DEFAULT_GRAPH_PATH.exists():
            graph_path = DEFAULT_GRAPH_PATH
        else:
            raise UniverseBuildError(
                f"Universe graph not found at {DEFAULT_GRAPH_PATH}\n"
                "Run 'uv run aria-esi universe --build' to generate it."
            )

    # Verify file exists first
    if not graph_path.exists():
        raise UniverseBuildError(
            f"Universe graph not found: {graph_path}\n"
            "Run 'uv run aria-esi universe --build' to generate it."
        )

    # Detect format by magic bytes
    try:
        file_format = detect_format(graph_path)
    except SerializationError as e:
        raise UniverseBuildError(str(e)) from e

    if file_format == "universe":
        # New safe format - integrity check on msgpack data
        if not skip_integrity_check:
            from aria_esi.core.data_integrity import IntegrityError, verify_universe_graph_integrity

            try:
                verify_universe_graph_integrity(graph_path)
            except IntegrityError:
                raise
            except Exception as e:
                logger.warning("Integrity check failed with unexpected error: %s", e)

        try:
            return load_safe(graph_path)
        except SerializationError as e:
            raise UniverseBuildError(
                f"Failed to load universe graph: {graph_path}\n"
                f"Error: {e}\n"
                "The file may be corrupted. Try rebuilding with 'uv run aria-esi universe --build'."
            ) from e

    else:
        raise UniverseBuildError(
            f"Unknown file format for {graph_path}. "
            "Expected .universe format.\n"
            "Try rebuilding with 'uv run aria-esi universe --build'."
        )
