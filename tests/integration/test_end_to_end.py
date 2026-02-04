"""
End-to-End Integration Tests

Tests complete workflows from graph building to query execution.

STP-012: Testing & Deployment
"""

import json
import time

import pytest


@pytest.mark.integration
class TestGraphBuildWorkflow:
    """End-to-end graph building tests."""

    def test_build_from_cache(self, sample_cache_path, tmp_path):
        """Complete workflow: cache -> graph -> safe format file."""
        from aria_esi.universe.builder import build_universe_graph, load_universe_graph

        output_path = tmp_path / "test_universe.universe"

        # Build graph from cache
        graph = build_universe_graph(sample_cache_path, output_path)

        # Verify graph properties
        assert graph.system_count == 6  # 6 systems in sample cache
        assert graph.stargate_count > 0
        assert len(graph.highsec_systems) > 0
        assert len(graph.lowsec_systems) > 0

        # Verify file was created
        assert output_path.exists()

        # Load and verify using safe format
        loaded = load_universe_graph(output_path, skip_integrity_check=True)

        assert loaded.system_count == graph.system_count
        assert loaded.version == graph.version

    def test_build_and_query(self, sample_cache_path, tmp_path):
        """Build graph and execute queries."""
        from aria_esi.universe.builder import build_universe_graph, load_universe_graph

        output_path = tmp_path / "test_universe.universe"

        # Build
        build_universe_graph(sample_cache_path, output_path)

        # Load fresh (skip integrity check for test pickles that don't match manifest)
        graph = load_universe_graph(output_path, skip_integrity_check=True)

        # Execute queries
        jita_idx = graph.resolve_name("Jita")
        assert jita_idx is not None
        assert graph.security_class(jita_idx) == "HIGH"

        # Test routing
        perimeter_idx = graph.resolve_name("Perimeter")
        path = graph.graph.get_shortest_paths(jita_idx, perimeter_idx)[0]
        assert len(path) == 2  # Direct connection


@pytest.mark.integration
class TestQueryWorkflows:
    """Test typical query workflows."""

    def test_route_planning_workflow(self, sample_graph):
        """Complete route planning workflow."""
        # 1. Resolve names
        origin = sample_graph.resolve_name("Jita")
        destination = sample_graph.resolve_name("Aufay")

        assert origin is not None
        assert destination is not None

        # 2. Calculate route
        path = sample_graph.graph.get_shortest_paths(origin, destination)[0]
        assert len(path) > 0

        # 3. Analyze security
        security_counts = {"HIGH": 0, "LOW": 0, "NULL": 0}
        for idx in path:
            sec_class = sample_graph.security_class(idx)
            security_counts[sec_class] += 1

        # Route should pass through both high and low sec
        assert security_counts["HIGH"] > 0
        assert security_counts["LOW"] > 0

    def test_border_exploration_workflow(self, sample_graph):
        """Complete border system exploration workflow."""
        from collections import deque

        # 1. Start from a system
        origin = sample_graph.resolve_name("Jita")

        # 2. BFS to find borders
        visited = {origin: 0}
        queue = deque([(origin, 0)])
        borders_found = []

        while queue:
            vertex, dist = queue.popleft()
            if dist > 10:
                continue

            if vertex in sample_graph.border_systems:
                borders_found.append((vertex, dist))

            for neighbor in sample_graph.graph.neighbors(vertex):
                if neighbor not in visited:
                    visited[neighbor] = dist + 1
                    queue.append((neighbor, dist + 1))

        # 3. Should find Sivala as border
        border_names = [sample_graph.idx_to_name[v] for v, _ in borders_found]
        assert "Sivala" in border_names

    def test_security_analysis_workflow(self, sample_graph):
        """Analyze security profile of systems."""
        # Count systems by security class
        high_count = len(sample_graph.highsec_systems)
        low_count = len(sample_graph.lowsec_systems)
        null_count = len(sample_graph.nullsec_systems)

        # Verify counts
        assert high_count + low_count + null_count == sample_graph.system_count

        # Verify border detection
        for border_idx in sample_graph.border_systems:
            # Border must be highsec
            assert border_idx in sample_graph.highsec_systems

            # Border must have lowsec neighbor
            neighbors = sample_graph.graph.neighbors(border_idx)
            has_lowsec = any(
                sample_graph.security[n] < 0.45 for n in neighbors
            )
            assert has_lowsec


@pytest.mark.integration
class TestPerformanceWorkflows:
    """Test performance-sensitive workflows."""

    def test_query_latency(self, sample_graph):
        """Verify queries complete within latency budget."""
        # Name resolution should be very fast
        start = time.perf_counter()
        for _ in range(100):
            sample_graph.resolve_name("Jita")
        elapsed = (time.perf_counter() - start) / 100

        # Should be well under 1ms per query
        assert elapsed < 0.001

    def test_route_latency(self, sample_graph):
        """Verify route calculation completes quickly."""
        origin = sample_graph.resolve_name("Jita")
        dest = sample_graph.resolve_name("Ala")

        start = time.perf_counter()
        for _ in range(10):
            sample_graph.graph.get_shortest_paths(origin, dest)
        elapsed = (time.perf_counter() - start) / 10

        # Should complete in under 10ms for small graph
        assert elapsed < 0.010


@pytest.mark.integration
class TestCLIIntegration:
    """Test CLI command integration."""

    def test_universe_command_import(self):
        """Universe CLI command imports successfully."""
        from aria_esi.commands import universe

        assert hasattr(universe, "register_parsers")

    def test_universe_build_function(self, sample_cache_path, tmp_path, monkeypatch):
        """Universe build command works end-to-end."""
        from aria_esi.commands.universe import cmd_graph_build

        # Create mock args
        class Args:
            def __init__(self):
                self.force = True
                self.cache = str(sample_cache_path)
                self.output = str(tmp_path / "universe.pkl")

        args = Args()

        # Run the command
        result = cmd_graph_build(args)

        assert result["status"] == "success"
        assert result["graph"]["systems"] == 6


@pytest.mark.integration
class TestDataIntegrity:
    """Test data integrity across operations."""

    def test_safe_format_roundtrip(self, sample_graph, tmp_path):
        """Graph survives safe format roundtrip."""
        from aria_esi.universe.serialization import load_universe_graph, save_universe_graph

        path = tmp_path / "roundtrip.universe"

        # Save
        save_universe_graph(sample_graph, path)

        # Load
        loaded = load_universe_graph(path)

        # Verify integrity
        assert loaded.system_count == sample_graph.system_count
        assert loaded.stargate_count == sample_graph.stargate_count
        assert len(loaded.border_systems) == len(sample_graph.border_systems)

        # Verify routing still works
        jita_old = sample_graph.resolve_name("Jita")
        jita_new = loaded.resolve_name("Jita")
        assert jita_old == jita_new

    def test_cache_version_tracking(self, sample_cache_data):
        """Cache version is preserved through build."""
        import tempfile
        from pathlib import Path

        from aria_esi.universe.builder import build_universe_graph

        # Create cache with specific version
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            sample_cache_data["generated"] = "test-version-123"
            json.dump(sample_cache_data, f)
            cache_path = Path(f.name)

        try:
            graph = build_universe_graph(cache_path)
            assert graph.version == "test-version-123"
        finally:
            cache_path.unlink()
