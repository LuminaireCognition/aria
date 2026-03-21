"""Roaming route computation helpers."""

from __future__ import annotations

import math
from collections import deque
from typing import TYPE_CHECKING

import numpy as np

from aria_esi.store.activity import ActivityData, get_activity_cache

if TYPE_CHECKING:
    from aria_esi.universe.graph import UniverseGraph


async def collect_bfs_data(
    universe: UniverseGraph,
    origin_idx: int,
    max_radius: int,
    avoid_indices: set[int] | None = None,
) -> dict[int, int]:
    """
    BFS from origin collecting distance for all systems in range.

    Returns:
        dict mapping vertex idx -> distance from origin
    """
    avoid = avoid_indices or set()
    g = universe.graph
    visited: dict[int, int] = {origin_idx: 0}
    queue: deque[tuple[int, int]] = deque([(origin_idx, 0)])

    while queue:
        current, dist = queue.popleft()
        if dist >= max_radius:
            continue
        for neighbor in g.neighbors(current):
            if neighbor not in visited and neighbor not in avoid:
                visited[neighbor] = dist + 1
                queue.append((neighbor, dist + 1))

    return visited


async def fetch_activity_for_systems(
    system_ids: list[int],
) -> dict[int, ActivityData]:
    """Fetch activity data from cache for a set of system IDs."""
    cache = get_activity_cache()
    all_activity = await cache.get_all_activity()
    result: dict[int, ActivityData] = {}
    for sid in system_ids:
        result[sid] = all_activity.get(sid, ActivityData(system_id=sid))
    return result


def classify_systems(
    universe: UniverseGraph,
    visited: dict[int, int],
    activity_data: dict[int, ActivityData],
    activity_type: str,
    hotspot_threshold: int,
) -> tuple[dict[int, str], dict[int, float], float]:
    """
    Classify systems as hunt, threat, or transit.

    Returns:
        (classification, hunt_metrics, hunt_threshold)
    """
    # Collect hunt metric values for P75 computation
    hunt_values: list[float] = []

    hunt_metrics: dict[int, float] = {}
    threat_metrics: dict[int, float] = {}

    for idx in visited:
        system_id = int(universe.system_ids[idx])
        act = activity_data.get(system_id, ActivityData(system_id=system_id))

        if activity_type == "ratting":
            hunt_metric = float(act.npc_kills)
            threat_metric = float(act.ship_kills + act.pod_kills)
        else:  # kills
            hunt_metric = float(act.ship_kills + act.pod_kills)
            threat_metric = float(act.ship_jumps)

        hunt_metrics[idx] = hunt_metric
        threat_metrics[idx] = threat_metric

        if hunt_metric > 0:
            hunt_values.append(hunt_metric)

    # Compute adaptive threshold
    min_floor = 50.0 if activity_type == "ratting" else 3.0
    if hunt_values:
        hunt_threshold = max(float(np.percentile(hunt_values, 75)), min_floor)
    else:
        hunt_threshold = min_floor

    # Classify
    classification: dict[int, str] = {}
    for idx in visited:
        hunt_val = hunt_metrics[idx]
        threat_val = threat_metrics[idx]

        if activity_type == "kills":
            # For kills, threat uses ship_jumps as traffic proxy
            # High-traffic pipe systems are camped, not hunting grounds
            is_threat = threat_val >= hotspot_threshold * 50
        else:
            is_threat = threat_val >= hotspot_threshold

        if is_threat:
            classification[idx] = "threat"
        elif hunt_val >= hunt_threshold:
            classification[idx] = "hunt"
        else:
            classification[idx] = "transit"

    return classification, hunt_metrics, hunt_threshold


def greedy_forward_walk(
    universe: UniverseGraph,
    origin_idx: int,
    target_jumps: int,
    classification: dict[int, str],
    hunt_metrics: dict[int, float],
    avoid_hotspots: bool,
    direction_idx: int | None,
    visited_bfs: dict[int, int],
    avoid_indices: set[int] | None = None,
) -> list[int]:
    """
    Greedy forward walk with 3-jump lookahead.

    Returns list of vertex indices forming the route.
    """
    avoid = avoid_indices or set()
    g = universe.graph
    route = [origin_idx]
    visited: set[int] = {origin_idx}

    # Pre-compute direction distances if needed
    direction_distances: dict[int, int] | None = None
    if direction_idx is not None:
        direction_distances = _bfs_distances(g, direction_idx, max_depth=target_jumps * 3)

    current = origin_idx
    while len(route) - 1 < target_jumps:
        neighbors = [n for n in g.neighbors(current) if n not in visited and n not in avoid]

        # Filter out threat systems when avoid_hotspots is on
        if avoid_hotspots:
            neighbors = [n for n in neighbors if classification.get(n) != "threat"]

        if not neighbors:
            break

        # Score each candidate with 3-jump lookahead
        best_candidate = None
        best_score = -float("inf")
        best_connections = float("inf")

        for candidate in neighbors:
            score = _score_candidate(
                candidate,
                visited,
                g,
                classification,
                hunt_metrics,
                avoid_hotspots,
                avoid,
                direction_idx,
                direction_distances,
                origin_idx,
                depth=3,
            )
            connections = len(list(g.neighbors(candidate)))
            # Prefer higher score; on tie, prefer fewer connections
            # (explore dead-ends before they become traps)
            if score > best_score or (score == best_score and connections < best_connections):
                best_score = score
                best_candidate = candidate
                best_connections = connections

        if best_candidate is None:
            break

        route.append(best_candidate)
        visited.add(best_candidate)
        current = best_candidate

    return route


def _score_candidate(
    candidate_idx: int,
    visited: set[int],
    g,
    classification: dict[int, str],
    hunt_metrics: dict[int, float],
    avoid_hotspots: bool,
    avoid: set[int],
    direction_idx: int | None,
    direction_distances: dict[int, int] | None,
    origin_idx: int,
    depth: int = 3,
) -> float:
    """Score a candidate next-hop by reachable activity."""
    reachable = _bfs_unvisited(
        candidate_idx, visited, g, avoid_hotspots, classification, avoid, max_depth=depth
    )

    activity_score = sum(
        hunt_metrics.get(idx, 0) / math.sqrt(max(hop_dist, 1))
        for idx, hop_dist in reachable
        if classification.get(idx) == "hunt"
    )

    # If no activity found, prefer systems with more unvisited neighbors (keep options open)
    if activity_score == 0:
        activity_score = len(reachable) * 0.01

    # Direction bias
    direction_score = 0.0
    if direction_idx is not None and direction_distances is not None:
        origin_dist = direction_distances.get(origin_idx, 999)
        candidate_dist = direction_distances.get(candidate_idx, 999)
        if origin_dist > 0:
            direction_score = (origin_dist - candidate_dist) / max(origin_dist, 1)

    return activity_score * (1.0 + 0.15 * direction_score)


def _bfs_unvisited(
    start: int,
    visited: set[int],
    g,
    avoid_hotspots: bool,
    classification: dict[int, str],
    avoid: set[int],
    max_depth: int = 3,
) -> list[tuple[int, int]]:
    """BFS from start through unvisited systems, returning (idx, hop_distance)."""
    result: list[tuple[int, int]] = []
    seen: set[int] = {start}
    frontier: deque[tuple[int, int]] = deque([(start, 0)])

    while frontier:
        current, dist = frontier.popleft()
        if dist > 0:
            result.append((current, dist))
        if dist >= max_depth:
            continue
        for neighbor in g.neighbors(current):
            if neighbor in seen or neighbor in visited or neighbor in avoid:
                continue
            if avoid_hotspots and classification.get(neighbor) == "threat":
                continue
            seen.add(neighbor)
            frontier.append((neighbor, dist + 1))

    return result


def _bfs_distances(g, origin: int, max_depth: int = 100) -> dict[int, int]:
    """Simple BFS to compute distances from origin to all reachable systems."""
    distances: dict[int, int] = {origin: 0}
    queue: deque[tuple[int, int]] = deque([(origin, 0)])
    while queue:
        current, dist = queue.popleft()
        if dist >= max_depth:
            continue
        for neighbor in g.neighbors(current):
            if neighbor not in distances:
                distances[neighbor] = dist + 1
                queue.append((neighbor, dist + 1))
    return distances


def sweep_retrace(
    universe: UniverseGraph,
    route: list[int],
    target_jumps: int,
    classification: dict[int, str],
    hunt_metrics: dict[int, float],
    avoid_hotspots: bool,
    avoid_indices: set[int] | None = None,
) -> tuple[list[int], list[int]]:
    """
    Attempt to extend route by retracing through 1-2 transit systems.

    Returns:
        (extended_route, retrace_indices) — retrace_indices are the systems revisited
    """
    avoid = avoid_indices or set()
    g = universe.graph
    visited = set(route)
    endpoint = route[-1]
    retrace_indices: list[int] = []
    max_retrace = 2

    if len(route) - 1 >= target_jumps:
        return route, retrace_indices

    # Look for hunt systems reachable through 1-2 already-visited transit systems
    for reachable_via in g.neighbors(endpoint):
        if len(retrace_indices) >= max_retrace:
            break
        if len(route) - 1 >= target_jumps:
            break
        if reachable_via not in visited:
            continue
        if reachable_via in avoid:
            continue
        # Must be a transit system (not hunt)
        if classification.get(reachable_via) != "transit":
            continue

        # Check if this transit system connects to unvisited hunt systems
        for beyond in g.neighbors(reachable_via):
            if beyond in visited or beyond in avoid:
                continue
            if avoid_hotspots and classification.get(beyond) == "threat":
                continue
            if classification.get(beyond) == "hunt":
                # Found a hunt system reachable through 1 transit retrace
                route.append(reachable_via)
                retrace_indices.append(reachable_via)
                route.append(beyond)
                visited.add(beyond)

                # Continue forward walk from new position
                current = beyond
                while len(route) - 1 < target_jumps:
                    neighbors = [
                        n for n in g.neighbors(current) if n not in visited and n not in avoid
                    ]
                    if avoid_hotspots:
                        neighbors = [n for n in neighbors if classification.get(n) != "threat"]
                    if not neighbors:
                        break
                    # Simple greedy: prefer hunt systems
                    best = max(neighbors, key=lambda n: hunt_metrics.get(n, 0))
                    route.append(best)
                    visited.add(best)
                    current = best
                break

    return route, retrace_indices
