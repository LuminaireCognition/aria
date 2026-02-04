"""
Route Calculation Performance Benchmarks

Tests route calculation performance for different modes and distances.

Latency Targets (from STP-012):
- Route (shortest): <2ms target, 5ms max
- Route (safe/unsafe): <5ms target, 10ms max

STP-012: Testing & Deployment
"""

import pytest


@pytest.mark.benchmark
class TestRouteBenchmarks:
    """Route calculation performance benchmarks."""

    def test_route_jita_to_amarr(self, benchmark_universe, benchmark):
        """
        Benchmark Jita -> Amarr route (cross-region).

        This is a long route spanning multiple regions.
        """
        jita = benchmark_universe.resolve_name("Jita")
        amarr = benchmark_universe.resolve_name("Amarr")

        if jita is None or amarr is None:
            pytest.skip("Jita or Amarr not found in graph")

        def run():
            return benchmark_universe.graph.get_shortest_paths(jita, amarr)[0]

        result = benchmark(run)
        assert len(result) > 10  # Verify actual route was found

    def test_route_local_same_constellation(self, benchmark_universe, benchmark):
        """
        Benchmark local route within same constellation.

        Short routes should be very fast.
        """
        jita = benchmark_universe.resolve_name("Jita")
        perimeter = benchmark_universe.resolve_name("Perimeter")

        if jita is None or perimeter is None:
            pytest.skip("Jita or Perimeter not found in graph")

        def run():
            return benchmark_universe.graph.get_shortest_paths(jita, perimeter)[0]

        result = benchmark(run)
        assert len(result) > 0

    def test_route_cross_empire(self, benchmark_universe, benchmark):
        """
        Benchmark Jita -> Dodixie route (cross-empire).

        Tests a typical trade route.
        """
        jita = benchmark_universe.resolve_name("Jita")
        dodixie = benchmark_universe.resolve_name("Dodixie")

        if jita is None or dodixie is None:
            pytest.skip("Jita or Dodixie not found in graph")

        def run():
            return benchmark_universe.graph.get_shortest_paths(jita, dodixie)[0]

        result = benchmark(run)
        assert len(result) > 5

    def test_route_safe_mode_weights(self, benchmark_universe, benchmark):
        """
        Benchmark weighted route calculation (safe mode).

        Computing edge weights adds overhead to route calculation.
        """
        jita = benchmark_universe.resolve_name("Jita")
        dodixie = benchmark_universe.resolve_name("Dodixie")

        if jita is None or dodixie is None:
            pytest.skip("Jita or Dodixie not found in graph")

        def compute_safe_weights():
            """Compute safe mode edge weights."""
            weights = []
            for edge in benchmark_universe.graph.es:
                src_sec = benchmark_universe.security[edge.source]
                dst_sec = benchmark_universe.security[edge.target]

                if dst_sec >= 0.45:
                    weights.append(1)
                elif src_sec >= 0.45:
                    weights.append(50)  # Entering low-sec penalty
                else:
                    weights.append(10)  # Staying in low-sec
            return weights

        def run():
            weights = compute_safe_weights()
            return benchmark_universe.graph.get_shortest_paths(
                jita, dodixie, weights=weights
            )[0]

        result = benchmark(run)
        assert len(result) > 0

    def test_route_null_to_null(self, benchmark_universe, benchmark):
        """
        Benchmark null-sec route if possible.

        Null-sec routes may have different characteristics.
        """
        # Find two null-sec systems
        nullsec = list(benchmark_universe.nullsec_systems)[:2]
        if len(nullsec) < 2:
            pytest.skip("Not enough null-sec systems in graph")

        src, dst = nullsec[0], nullsec[1]

        def run():
            return benchmark_universe.graph.get_shortest_paths(src, dst)[0]

        result = benchmark(run)
        # May return empty path if disconnected


@pytest.mark.benchmark
class TestRouteMultipleBenchmarks:
    """Benchmarks for multiple route calculations."""

    def test_batch_routes(self, benchmark_universe, benchmark):
        """
        Benchmark calculating multiple routes in sequence.

        Simulates a typical session workload.
        """
        systems = ["Jita", "Amarr", "Dodixie", "Rens", "Hek"]
        indices = [benchmark_universe.resolve_name(s) for s in systems]
        valid = [i for i in indices if i is not None]

        if len(valid) < 2:
            pytest.skip("Not enough trade hubs found in graph")

        def run():
            routes = []
            for i in range(len(valid) - 1):
                path = benchmark_universe.graph.get_shortest_paths(
                    valid[i], valid[i + 1]
                )[0]
                routes.append(path)
            return routes

        result = benchmark(run)
        assert len(result) == len(valid) - 1
