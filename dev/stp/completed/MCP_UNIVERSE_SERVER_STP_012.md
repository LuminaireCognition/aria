# STP-012: Testing & Deployment

**Status:** Complete
**Priority:** P1 - Required for Release
**Depends On:** All previous STPs
**Blocks:** None

## Objective

Define the testing strategy, benchmark requirements, and deployment checklist for the MCP Universe Server. This ensures production readiness and establishes quality gates.

## Scope

### In Scope
- Test directory structure
- Unit test requirements per component
- Integration test suite
- Performance benchmark suite
- Test fixtures and utilities
- CI/CD integration
- Deployment checklist
- MCP configuration for Claude Code

### Out of Scope
- Load testing (beyond latency benchmarks)
- Security auditing
- Monitoring/alerting (post-deployment)

## Test Directory Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── universe/
│   ├── test_graph.py              # UniverseGraph unit tests
│   ├── test_builder.py            # Builder unit tests
│   └── fixtures/
│       └── sample_cache.json      # Minimal test data
├── mcp/
│   ├── test_models.py             # Pydantic model tests
│   ├── test_server.py             # Server lifecycle tests
│   ├── test_errors.py             # Error handling tests
│   ├── test_tools_route.py        # Route tool tests
│   ├── test_tools_systems.py      # Systems tool tests
│   ├── test_tools_borders.py      # Borders tool tests
│   ├── test_tools_search.py       # Search tool tests
│   ├── test_tools_loop.py         # Loop tool tests
│   └── test_tools_analyze.py      # Analyze tool tests
├── cli/
│   └── test_universe.py           # CLI command tests
├── integration/
│   ├── test_mcp_protocol.py       # Full MCP integration
│   └── test_end_to_end.py         # Complete workflows
└── benchmarks/
    ├── conftest.py                # Benchmark fixtures
    ├── bench_graph_load.py        # Graph loading benchmarks
    ├── bench_route.py             # Route calculation benchmarks
    └── bench_search.py            # Search benchmarks
```

## Shared Fixtures

```python
# tests/conftest.py

import json
import pickle
import pytest
from pathlib import Path
from aria_esi.universe.builder import build_universe_graph
from aria_esi.universe.graph import UniverseGraph
from aria_esi.mcp.server import UniverseServer


@pytest.fixture(scope="session")
def sample_cache_path(tmp_path_factory) -> Path:
    """Create minimal universe cache for fast tests."""
    cache = {
        "systems": {
            "30000142": {
                "system_id": 30000142,
                "name": "Jita",
                "security_status": 0.9459,
                "constellation_id": 20000020,
                "region_id": 10000002,
                "stargates": [50001248, 50001249]
            },
            "30000144": {
                "system_id": 30000144,
                "name": "Perimeter",
                "security_status": 0.9072,
                "constellation_id": 20000020,
                "region_id": 10000002,
                "stargates": [50001250]
            },
            # Add more systems as needed for tests
        },
        "stargates": {
            "50001248": {"destination_system_id": 30000144},
            "50001249": {"destination_system_id": 30000145},
            "50001250": {"destination_system_id": 30000142}
        },
        "constellations": {
            "20000020": {"name": "Kimotoro"}
        },
        "regions": {
            "10000002": {"name": "The Forge"}
        },
        "version": "test-1.0"
    }

    path = tmp_path_factory.mktemp("data") / "universe_cache.json"
    path.write_text(json.dumps(cache))
    return path


@pytest.fixture(scope="session")
def sample_graph(sample_cache_path, tmp_path_factory) -> UniverseGraph:
    """Build sample graph for testing."""
    output = tmp_path_factory.mktemp("data") / "universe.pkl"
    return build_universe_graph(sample_cache_path, output)


@pytest.fixture(scope="session")
def sample_graph_path(sample_graph, tmp_path_factory) -> Path:
    """Path to sample graph pickle."""
    path = tmp_path_factory.mktemp("data") / "universe.pkl"
    with open(path, "wb") as f:
        pickle.dump(sample_graph, f, protocol=pickle.HIGHEST_PROTOCOL)
    return path


@pytest.fixture
def mock_server(sample_graph_path) -> UniverseServer:
    """Create mock server with sample graph."""
    server = UniverseServer(graph_path=sample_graph_path)
    server.load_graph()
    server.register_tools()
    return server


# For tests that need real universe data
@pytest.fixture(scope="session")
def real_graph_path() -> Path | None:
    """Path to real universe.pkl if available."""
    path = Path(__file__).parent.parent / "aria_esi" / "data" / "universe.pkl"
    if path.exists():
        return path
    return None


@pytest.fixture
def real_universe(real_graph_path) -> UniverseGraph | None:
    """Load real universe graph if available."""
    if real_graph_path is None:
        pytest.skip("Real universe graph not available")
    from aria_esi.universe.builder import load_universe_graph
    return load_universe_graph(real_graph_path)
```

## Benchmark Suite

```python
# tests/benchmarks/bench_route.py

import pytest
import time


@pytest.mark.benchmark
class TestRouteBenchmarks:
    """Route calculation performance benchmarks."""

    def test_route_jita_to_amarr(self, real_universe, benchmark):
        """Benchmark Jita → Amarr route (cross-region)."""
        jita = real_universe.resolve_name("Jita")
        amarr = real_universe.resolve_name("Amarr")

        def run():
            return real_universe.graph.get_shortest_paths(jita, amarr)[0]

        result = benchmark(run)
        assert len(result) > 10  # Verify actual route

    def test_route_local(self, real_universe, benchmark):
        """Benchmark local route (same region)."""
        jita = real_universe.resolve_name("Jita")
        perimeter = real_universe.resolve_name("Perimeter")

        def run():
            return real_universe.graph.get_shortest_paths(jita, perimeter)[0]

        benchmark(run)

    def test_route_safe_mode(self, real_universe, benchmark):
        """Benchmark safe mode routing (weighted)."""
        from aria_esi.mcp.tools_route import _compute_safe_weights, _calculate_route

        jita = real_universe.resolve_name("Jita")
        dodixie = real_universe.resolve_name("Dodixie")

        def run():
            weights = _compute_safe_weights(real_universe)
            return real_universe.graph.get_shortest_paths(
                jita, dodixie, weights=weights
            )[0]

        benchmark(run)


@pytest.mark.benchmark
class TestGraphBenchmarks:
    """Graph loading and query benchmarks."""

    def test_graph_load_time(self, real_graph_path, benchmark):
        """Benchmark graph loading from pickle."""
        from aria_esi.universe.builder import load_universe_graph

        def run():
            return load_universe_graph(real_graph_path)

        result = benchmark(run)
        assert result.system_count > 5000

    def test_name_resolution(self, real_universe, benchmark):
        """Benchmark name resolution."""
        def run():
            return real_universe.resolve_name("jita")

        benchmark(run)

    def test_neighbor_query(self, real_universe, benchmark):
        """Benchmark neighbor lookup."""
        jita = real_universe.resolve_name("Jita")

        def run():
            return real_universe.neighbors_with_security(jita)

        benchmark(run)
```

### Benchmark Configuration

```ini
# pytest.ini
[pytest]
markers =
    benchmark: marks tests as benchmarks (deselect with '-m "not benchmark"')
    slow: marks tests as slow (deselect with '-m "not slow"')

addopts = -m "not benchmark"
```

```bash
# Run benchmarks
uv run pytest tests/benchmarks/ -v --benchmark-enable --benchmark-json=benchmark.json

# Run with comparison
uv run pytest tests/benchmarks/ --benchmark-compare
```

## Latency Requirements

| Operation | Target | Maximum |
|-----------|--------|---------|
| Graph load | <50ms | 100ms |
| Name resolution | <0.01ms | 0.1ms |
| Route (shortest) | <2ms | 5ms |
| Route (safe/unsafe) | <5ms | 10ms |
| System lookup | <0.1ms | 0.5ms |
| Border search | <2ms | 5ms |
| System search | <5ms | 10ms |
| Loop planning | <20ms | 50ms |
| Route analysis | <2ms | 5ms |

## CI/CD Integration

```yaml
# .github/workflows/test-universe.yml

name: Universe MCP Tests

on:
  push:
    paths:
      - 'aria_esi/universe/**'
      - 'aria_esi/mcp/**'
      - 'tests/**'
  pull_request:
    paths:
      - 'aria_esi/universe/**'
      - 'aria_esi/mcp/**'
      - 'tests/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync

      - name: Run unit tests
        run: uv run pytest tests/ -v --ignore=tests/benchmarks/

      - name: Run benchmarks
        run: uv run pytest tests/benchmarks/ -v --benchmark-enable

  build-graph:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Build graph
        run: |
          uv run aria-esi universe build --force
          uv run aria-esi universe verify

      - name: Upload graph artifact
        uses: actions/upload-artifact@v4
        with:
          name: universe-graph
          path: aria_esi/data/universe.pkl
```

## Deployment Checklist

### Pre-Deployment

- [ ] All unit tests pass: `uv run pytest tests/ --ignore=tests/benchmarks/`
- [ ] All integration tests pass: `uv run pytest tests/integration/`
- [ ] Benchmarks within latency targets: `uv run pytest tests/benchmarks/ --benchmark-enable`
- [ ] No security vulnerabilities: `uv run pip-audit`

### Build Graph

- [ ] Universe cache is current: Check `universe_cache.json` date
- [ ] Build graph: `uv run aria-esi universe build --force`
- [ ] Verify graph: `uv run aria-esi universe verify`
- [ ] Check statistics: `uv run aria-esi universe stats --detailed`

### Configure MCP

- [ ] Add to `.claude/settings.local.json`:

```json
{
  "mcpServers": {
    "aria-universe": {
      "command": "uv",
      "args": ["run", "python", "-m", "aria_esi.mcp.server"],
      "cwd": "/Users/jskelton/EveOnline"
    }
  }
}
```

### Verify Integration

- [ ] Restart Claude Code
- [ ] Check MCP connection in Claude Code logs
- [ ] Test basic query: Ask Claude "what is the route from Jita to Amarr?"
- [ ] Test border query: Ask Claude "find border systems near Dodixie"

### Post-Deployment

- [ ] Document any issues in CHANGELOG.md
- [ ] Update version in pyproject.toml if needed
- [ ] Tag release if appropriate

## Rollback Procedure

If issues occur:

1. Remove MCP configuration from settings
2. Restart Claude Code
3. Debug using standalone tests
4. Fix and redeploy

## Monitoring

For production use, consider adding:

```python
# aria_esi/mcp/metrics.py

import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def timed_tool(func):
    """Decorator to log tool execution times."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logger.info(f"{func.__name__} completed in {elapsed*1000:.2f}ms")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.error(f"{func.__name__} failed after {elapsed*1000:.2f}ms: {e}")
            raise
    return wrapper
```

## Estimated Effort

- Test implementation: Large
- Benchmark implementation: Medium
- CI/CD setup: Small
- Documentation: Small
- Total: Large

## Notes

- Use session-scoped fixtures for expensive graph loading
- Real universe tests require built graph (skip if unavailable)
- Benchmark suite separate from unit tests for CI speed
- Latency targets based on design document requirements
