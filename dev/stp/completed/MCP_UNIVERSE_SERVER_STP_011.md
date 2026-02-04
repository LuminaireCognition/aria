# STP-011: CLI Integration

**Status:** Complete
**Priority:** P1 - Required for Deployment
**Depends On:** STP-001, STP-003, STP-004
**Blocks:** STP-012

## Objective

Implement CLI commands for building, verifying, and inspecting the universe graph. These commands integrate with the existing `aria-esi` CLI and support the deployment workflow.

## Scope

### In Scope
- `aria-esi graph-build` - Build graph from JSON cache
- `aria-esi graph-verify` - Verify graph integrity
- `aria-esi graph-stats` - Display graph statistics
- Integration with existing CLI structure
- Progress output and error handling

### Out of Scope
- MCP server launch (handled by pyproject.toml entry point)
- Universe cache generation (existing functionality)

## File Location

```
aria_esi/commands/universe.py (extended with graph commands)
tests/test_commands.py (extended with graph command tests)
```

Implementation uses the existing argparse-based CLI structure. Commands are registered as `graph-build`, `graph-verify`, `graph-stats` subcommands.

## Implementation

### CLI Commands

```python
# aria_esi/commands/universe.py

import argparse
import time
from pathlib import Path

from ..universe.builder import (
    DEFAULT_CACHE_PATH,
    DEFAULT_GRAPH_PATH,
    build_universe_graph,
    load_universe_graph,
)
from ..core import get_utc_timestamp


def cmd_graph_build(args: argparse.Namespace) -> dict:
    """Build universe graph from JSON cache."""
    query_ts = get_utc_timestamp()

    cache_path = Path(args.cache) if args.cache else DEFAULT_CACHE_PATH
    output_path = Path(args.output) if args.output else DEFAULT_GRAPH_PATH

    if output_path.exists() and not args.force:
        return {
            "error": "output_exists",
            "message": f"Output file exists: {output_path}",
            "hint": "Use --force to overwrite",
            "query_timestamp": query_ts,
        }

    if not cache_path.exists():
        return {
            "error": "cache_not_found",
            "message": f"Cache file not found: {cache_path}",
            "query_timestamp": query_ts,
        }

    start = time.perf_counter()
    try:
        universe = build_universe_graph(cache_path, output_path)
        elapsed = time.perf_counter() - start

        return {
            "query_timestamp": query_ts,
            "status": "success",
            "message": f"Built universe graph in {elapsed:.2f}s",
            "graph": {
                "systems": universe.system_count,
                "stargates": universe.stargate_count,
                "border_systems": len(universe.border_systems),
            },
            "output": {
                "path": str(output_path),
                "size_kb": round(output_path.stat().st_size / 1024, 1),
            },
        }
    except Exception as e:
        return {
            "error": "build_failed",
            "message": f"Build failed: {e}",
            "query_timestamp": query_ts,
        }


def cmd_graph_verify(args: argparse.Namespace) -> dict:
    """Verify universe graph integrity."""
    query_ts = get_utc_timestamp()
    graph_path = Path(args.graph) if args.graph else DEFAULT_GRAPH_PATH

    if not graph_path.exists():
        return {
            "error": "graph_not_found",
            "message": f"Graph file not found: {graph_path}",
            "query_timestamp": query_ts,
        }

    errors = []
    checks = []

    try:
        start = time.perf_counter()
        universe = load_universe_graph(graph_path)
        load_time = time.perf_counter() - start
        checks.append({"check": "load", "status": "pass", "load_time_ms": round(load_time * 1000, 1)})
    except Exception as e:
        return {
            "error": "load_failed",
            "message": f"Could not load graph: {e}",
            "query_timestamp": query_ts,
        }

    # Validation checks...
    # (see full implementation in aria_esi/commands/universe.py)

    return {
        "query_timestamp": query_ts,
        "status": "PASSED" if not errors else "FAILED",
        "checks": checks,
        "errors": errors if errors else None,
    }


def cmd_graph_stats(args: argparse.Namespace) -> dict:
    """Display universe graph statistics."""
    # (see full implementation in aria_esi/commands/universe.py)
    pass
```

### Argument Parser Registration

```python
def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register universe command parsers."""

    # Graph build command
    graph_build_parser = subparsers.add_parser(
        "graph-build",
        help="Build universe graph from JSON cache",
    )
    graph_build_parser.add_argument(
        "--cache", "-c",
        help=f"Path to universe_cache.json (default: {DEFAULT_CACHE_PATH})",
    )
    graph_build_parser.add_argument(
        "--output", "-o",
        help=f"Output path for universe.pkl (default: {DEFAULT_GRAPH_PATH})",
    )
    graph_build_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing output file",
    )
    graph_build_parser.set_defaults(func=cmd_graph_build)

    # Graph verify command
    graph_verify_parser = subparsers.add_parser(
        "graph-verify",
        help="Verify universe graph integrity",
    )
    graph_verify_parser.add_argument(
        "--graph", "-g",
        help=f"Path to universe.pkl (default: {DEFAULT_GRAPH_PATH})",
    )
    graph_verify_parser.set_defaults(func=cmd_graph_verify)

    # Graph stats command
    graph_stats_parser = subparsers.add_parser(
        "graph-stats",
        help="Display universe graph statistics",
    )
    graph_stats_parser.add_argument(
        "--graph", "-g",
        help=f"Path to universe.pkl (default: {DEFAULT_GRAPH_PATH})",
    )
    graph_stats_parser.add_argument(
        "--detailed", "-d",
        action="store_true",
        help="Show detailed statistics",
    )
    graph_stats_parser.set_defaults(func=cmd_graph_stats)
```

### pyproject.toml Entry Points

```toml
[project.scripts]
aria-esi = "aria_esi.__main__:main"
aria-universe = "aria_esi.mcp.server:main"
```

## Acceptance Criteria

1. [x] `graph-build` creates valid pickle from JSON
2. [x] `graph-build` shows progress and statistics
3. [x] `graph-build --force` overwrites existing file
4. [x] `graph-verify` checks all integrity conditions
5. [x] `graph-verify` exits with non-zero on failure
6. [x] `graph-stats` displays comprehensive statistics
7. [x] `graph-stats --detailed` shows region breakdown
8. [x] Commands integrate with existing CLI structure (argparse)
9. [x] Error messages are helpful and actionable

## Test Requirements

```python
# tests/commands/test_universe.py

import argparse
import pytest
from aria_esi.commands.universe import cmd_graph_build, cmd_graph_verify, cmd_graph_stats


def test_build_command(tmp_path, sample_cache):
    """Build command creates graph."""
    output = tmp_path / "test.pkl"
    args = argparse.Namespace(
        cache=str(sample_cache),
        output=str(output),
        force=False,
    )
    result = cmd_graph_build(args)
    assert result.get("status") == "success"
    assert output.exists()


def test_build_requires_force(tmp_path, sample_cache):
    """Build refuses to overwrite without --force."""
    output = tmp_path / "test.pkl"
    output.touch()  # Create existing file

    args = argparse.Namespace(
        cache=str(sample_cache),
        output=str(output),
        force=False,
    )
    result = cmd_graph_build(args)
    assert result.get("error") == "output_exists"


def test_verify_command(test_graph):
    """Verify command checks graph."""
    args = argparse.Namespace(graph=str(test_graph))
    result = cmd_graph_verify(args)
    assert result.get("status") == "PASSED"


def test_verify_fails_on_bad_graph(tmp_path):
    """Verify fails on corrupt graph."""
    bad_graph = tmp_path / "bad.pkl"
    bad_graph.write_bytes(b"not a pickle")

    args = argparse.Namespace(graph=str(bad_graph))
    result = cmd_graph_verify(args)
    assert result.get("error") == "load_failed"


def test_stats_command(test_graph):
    """Stats command displays statistics."""
    args = argparse.Namespace(graph=str(test_graph), detailed=False)
    result = cmd_graph_stats(args)
    assert "systems" in result
    assert result["systems"]["total"] > 0


def test_stats_detailed(test_graph):
    """Stats --detailed shows regions."""
    args = argparse.Namespace(graph=str(test_graph), detailed=True)
    result = cmd_graph_stats(args)
    assert "top_regions" in result
```

## Estimated Effort

- Implementation: Medium
- Testing: Small
- Total: Medium

## Notes

- Uses existing argparse-based CLI structure
- Build command is idempotent - same input produces same output
- Verify is useful for CI/CD pipelines
- Stats helps debug data issues
