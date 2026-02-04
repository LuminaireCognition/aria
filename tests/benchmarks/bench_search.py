"""
Search and Border Detection Performance Benchmarks

Tests search, border finding, and analysis performance.

Latency Targets (from STP-012):
- System lookup: <0.1ms target, 0.5ms max
- Border search: <2ms target, 5ms max
- System search: <5ms target, 10ms max
- Loop planning: <20ms target, 50ms max
- Route analysis: <2ms target, 5ms max

STP-012: Testing & Deployment
"""

from collections import deque

import pytest


@pytest.mark.benchmark
class TestBorderSearchBenchmarks:
    """Border system detection benchmarks."""

    def test_find_borders_from_dodixie(self, benchmark_universe, benchmark):
        """
        Benchmark finding border systems near Dodixie.

        Dodixie is a trade hub with nearby low-sec.
        """
        dodixie = benchmark_universe.resolve_name("Dodixie")
        if dodixie is None:
            pytest.skip("Dodixie not found in graph")

        def find_borders(origin_idx, limit=10, max_jumps=15):
            """BFS to find nearby border systems."""
            g = benchmark_universe.graph
            borders = []
            visited = {origin_idx: 0}
            queue = deque([(origin_idx, 0)])

            while queue and len(borders) < limit * 2:
                vertex, dist = queue.popleft()
                if dist > max_jumps:
                    continue
                if vertex in benchmark_universe.border_systems:
                    borders.append((vertex, dist))
                for neighbor in g.neighbors(vertex):
                    if neighbor not in visited:
                        visited[neighbor] = dist + 1
                        queue.append((neighbor, dist + 1))

            borders.sort(key=lambda x: x[1])
            return borders[:limit]

        result = benchmark(find_borders, dodixie)
        # May be empty if no borders nearby

    def test_find_borders_from_jita(self, benchmark_universe, benchmark):
        """
        Benchmark finding border systems near Jita.

        Jita is deep in highsec - borders may be further.
        """
        jita = benchmark_universe.resolve_name("Jita")
        if jita is None:
            pytest.skip("Jita not found in graph")

        def find_borders(origin_idx, limit=10, max_jumps=20):
            """BFS to find nearby border systems."""
            g = benchmark_universe.graph
            borders = []
            visited = {origin_idx: 0}
            queue = deque([(origin_idx, 0)])

            while queue and len(borders) < limit * 2:
                vertex, dist = queue.popleft()
                if dist > max_jumps:
                    continue
                if vertex in benchmark_universe.border_systems:
                    borders.append((vertex, dist))
                for neighbor in g.neighbors(vertex):
                    if neighbor not in visited:
                        visited[neighbor] = dist + 1
                        queue.append((neighbor, dist + 1))

            borders.sort(key=lambda x: x[1])
            return borders[:limit]

        result = benchmark(find_borders, jita)


@pytest.mark.benchmark
class TestSystemSearchBenchmarks:
    """System search benchmarks."""

    def test_search_by_security(self, benchmark_universe, benchmark):
        """Benchmark filtering systems by security range."""
        import numpy as np

        security = benchmark_universe.security

        def search_lowsec():
            """Find all low-sec systems."""
            return np.where((security > 0.0) & (security < 0.45))[0]

        result = benchmark(search_lowsec)
        assert len(result) > 0

    def test_search_by_region(self, benchmark_universe, benchmark):
        """Benchmark searching systems in a specific region."""
        # Find The Forge region ID
        forge_id = None
        for rid, name in benchmark_universe.region_names.items():
            if name == "The Forge":
                forge_id = rid
                break

        if forge_id is None:
            pytest.skip("The Forge region not found")

        def search_region():
            return benchmark_universe.region_systems.get(forge_id, [])

        result = benchmark(search_region)
        assert len(result) > 0

    def test_search_with_distance(self, benchmark_universe, benchmark):
        """Benchmark BFS-based distance-limited search."""
        jita = benchmark_universe.resolve_name("Jita")
        if jita is None:
            pytest.skip("Jita not found in graph")

        def bfs_search(origin_idx, max_jumps=10):
            """Search systems within distance limit."""
            g = benchmark_universe.graph
            visited = {origin_idx: 0}
            queue = deque([(origin_idx, 0)])
            results = []

            while queue:
                vertex, dist = queue.popleft()
                if dist > max_jumps:
                    continue
                results.append((vertex, dist))
                for neighbor in g.neighbors(vertex):
                    if neighbor not in visited:
                        visited[neighbor] = dist + 1
                        queue.append((neighbor, dist + 1))

            return results

        result = benchmark(bfs_search, jita)
        assert len(result) > 0


@pytest.mark.benchmark
class TestAnalysisBenchmarks:
    """Route analysis benchmarks."""

    def test_analyze_route_security(self, benchmark_universe, benchmark):
        """Benchmark security analysis of a route."""
        jita = benchmark_universe.resolve_name("Jita")
        amarr = benchmark_universe.resolve_name("Amarr")

        if jita is None or amarr is None:
            pytest.skip("Jita or Amarr not found in graph")

        path = benchmark_universe.graph.get_shortest_paths(jita, amarr)[0]
        if not path:
            pytest.skip("No path found between Jita and Amarr")

        def analyze_route(route):
            """Analyze security profile of a route."""
            security = benchmark_universe.security
            high = sum(1 for v in route if security[v] >= 0.45)
            low = sum(1 for v in route if 0.0 < security[v] < 0.45)
            null = sum(1 for v in route if security[v] <= 0.0)
            lowest = min(security[v] for v in route)
            return {
                "total": len(route),
                "high": high,
                "low": low,
                "null": null,
                "lowest": lowest,
            }

        result = benchmark(analyze_route, path)
        assert result["total"] == len(path)

    def test_find_chokepoints(self, benchmark_universe, benchmark):
        """Benchmark chokepoint detection in a route."""
        jita = benchmark_universe.resolve_name("Jita")
        dodixie = benchmark_universe.resolve_name("Dodixie")

        if jita is None or dodixie is None:
            pytest.skip("Jita or Dodixie not found in graph")

        path = benchmark_universe.graph.get_shortest_paths(jita, dodixie)[0]
        if len(path) < 3:
            pytest.skip("Path too short for chokepoint analysis")

        def find_chokepoints(route):
            """Find security transitions (chokepoints)."""
            security = benchmark_universe.security
            chokepoints = []
            for i in range(1, len(route)):
                prev_sec = security[route[i - 1]]
                curr_sec = security[route[i]]
                prev_high = prev_sec >= 0.45
                curr_high = curr_sec >= 0.45
                if prev_high != curr_high:
                    chokepoints.append(route[i])
            return chokepoints

        result = benchmark(find_chokepoints, path)
        # May be empty if route stays in one security class
