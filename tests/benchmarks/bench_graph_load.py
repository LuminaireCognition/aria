"""
Graph Loading Performance Benchmarks

Tests graph loading and basic query performance against latency targets.

Latency Targets (from STP-012):
- Graph load: <50ms target, 100ms max
- Name resolution: <0.01ms target, 0.1ms max
- Neighbor query: <0.1ms target, 0.5ms max

STP-012: Testing & Deployment
"""

import pytest


@pytest.mark.benchmark
class TestGraphLoadBenchmarks:
    """Graph loading and basic query benchmarks."""

    def test_graph_load_time(self, real_graph_path, benchmark):
        """
        Benchmark graph loading from pickle.

        Target: <50ms
        Maximum: 100ms
        """
        if real_graph_path is None:
            pytest.skip("Real universe graph not available")

        from aria_esi.universe.builder import load_universe_graph

        result = benchmark(load_universe_graph, real_graph_path)

        # Verify loaded graph is valid
        assert result.system_count > 5000
        assert result.stargate_count > 5000

    def test_name_resolution(self, benchmark_universe, benchmark):
        """
        Benchmark case-insensitive name resolution.

        Target: <0.01ms
        Maximum: 0.1ms
        """
        def run():
            return benchmark_universe.resolve_name("jita")

        result = benchmark(run)
        assert result is not None

    def test_name_resolution_miss(self, benchmark_universe, benchmark):
        """
        Benchmark name resolution for unknown system.

        Should still be fast even for cache miss.
        """
        def run():
            return benchmark_universe.resolve_name("nonexistent_system_xyz")

        result = benchmark(run)
        assert result is None

    def test_neighbor_query(self, benchmark_universe, benchmark):
        """
        Benchmark neighbor lookup with security values.

        Target: <0.1ms
        Maximum: 0.5ms
        """
        jita = benchmark_universe.resolve_name("Jita")

        def run():
            return benchmark_universe.neighbors_with_security(jita)

        result = benchmark(run)
        assert len(result) > 0

    def test_security_class_lookup(self, benchmark_universe, benchmark):
        """Benchmark security classification lookup."""
        jita = benchmark_universe.resolve_name("Jita")

        def run():
            return benchmark_universe.security_class(jita)

        result = benchmark(run)
        assert result == "HIGH"

    def test_border_system_check(self, benchmark_universe, benchmark):
        """Benchmark border system membership test."""
        # Find a known border system
        border_idx = next(iter(benchmark_universe.border_systems), None)
        if border_idx is None:
            pytest.skip("No border systems in graph")

        def run():
            return benchmark_universe.is_border_system(border_idx)

        result = benchmark(run)
        assert result is True
