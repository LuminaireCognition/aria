# STP-004: MCP Server Core

**Status:** Draft
**Priority:** P0 - Foundation
**Depends On:** STP-001, STP-002, STP-003
**Blocks:** STP-005 through STP-010

## Objective

Implement the MCP server entry point, graph loading, tool registration framework, and error handling infrastructure.

## Scope

### In Scope
- `UniverseServer` class with lifecycle management
- Graph loading at startup
- Tool registration pattern
- Error exception classes
- MCP-compliant error responses
- Server entry point (`main()`)
- Module structure (`__init__.py`)

### Out of Scope
- Individual tool implementations (STP-005 through STP-010)
- CLI integration (STP-011)

## File Location

```
aria_esi/mcp/__init__.py
aria_esi/mcp/server.py
aria_esi/mcp/errors.py
aria_esi/mcp/tools.py (stub for registration)
```

## Implementation

### Error Classes

```python
# aria_esi/mcp/errors.py

class UniverseError(Exception):
    """Base exception for universe queries."""
    code: str = "UNIVERSE_ERROR"

    def to_mcp_error(self) -> dict:
        """Convert to MCP error response format."""
        return {
            "error": {
                "code": self.code,
                "message": str(self),
                "data": self._error_data()
            }
        }

    def _error_data(self) -> dict:
        return {}


class SystemNotFoundError(UniverseError):
    """Raised when a system name cannot be resolved."""
    code = "SYSTEM_NOT_FOUND"

    def __init__(self, name: str, suggestions: list[str] | None = None):
        self.name = name
        self.suggestions = suggestions or []
        super().__init__(f"Unknown system: {name}")

    def _error_data(self) -> dict:
        return {"suggestions": self.suggestions}


class RouteNotFoundError(UniverseError):
    """Raised when no route exists between systems."""
    code = "ROUTE_NOT_FOUND"

    def __init__(self, origin: str, destination: str, reason: str | None = None):
        self.origin = origin
        self.destination = destination
        self.reason = reason
        msg = f"No route from {origin} to {destination}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)

    def _error_data(self) -> dict:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "reason": self.reason
        }


class InvalidParameterError(UniverseError):
    """Raised for invalid tool parameters."""
    code = "INVALID_PARAMETER"

    def __init__(self, param: str, value: any, reason: str):
        self.param = param
        self.value = value
        self.reason = reason
        super().__init__(f"Invalid {param}: {reason}")

    def _error_data(self) -> dict:
        return {
            "parameter": self.param,
            "value": str(self.value),
            "reason": self.reason
        }
```

### Server Class

```python
# aria_esi/mcp/server.py

import asyncio
import os
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from ..universe.graph import UniverseGraph
from ..universe.builder import load_universe_graph

DEFAULT_GRAPH_PATH = Path(__file__).parent.parent / "data" / "universe.pkl"


class UniverseServer:
    """MCP server for EVE Online universe queries."""

    def __init__(self, graph_path: Path | None = None):
        """
        Initialize server with graph path.

        Args:
            graph_path: Path to universe.pkl. Defaults to package data directory.
                       Can be overridden with ARIA_UNIVERSE_GRAPH env var.
        """
        self.graph_path = graph_path or Path(
            os.environ.get("ARIA_UNIVERSE_GRAPH", DEFAULT_GRAPH_PATH)
        )
        self.universe: UniverseGraph | None = None
        self.server = Server("aria-universe")
        self._tools_registered = False

    def load_graph(self) -> None:
        """Load pre-built universe graph from pickle."""
        self.universe = load_universe_graph(self.graph_path)

    def register_tools(self) -> None:
        """Register all MCP tools with the server."""
        if self._tools_registered:
            return
        from .tools import register_tools
        register_tools(self.server, self.universe)
        self._tools_registered = True

    async def run(self) -> None:
        """Start MCP server with stdio transport."""
        self.load_graph()
        self.register_tools()

        async with stdio_server() as (read, write):
            await self.server.run(
                read,
                write,
                self.server.create_initialization_options()
            )


def main() -> None:
    """Entry point for MCP server."""
    import logging

    log_level = os.environ.get("ARIA_UNIVERSE_LOG_LEVEL", "WARNING")
    logging.basicConfig(level=getattr(logging, log_level))

    server = UniverseServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
```

### Tool Registration Framework

```python
# aria_esi/mcp/tools.py

from mcp.server import Server
from ..universe.graph import UniverseGraph
from .errors import SystemNotFoundError

# Global reference for tool implementations
_universe: UniverseGraph | None = None


def register_tools(server: Server, universe: UniverseGraph) -> None:
    """Register all universe tools with MCP server."""
    global _universe
    _universe = universe

    # Tools will be registered here as they are implemented
    # Each tool module will add its registration in subsequent STPs

    # Placeholder for tool registration pattern:
    # from .tools_route import register_route_tools
    # from .tools_systems import register_systems_tools
    # ...
    # register_route_tools(server, universe)


def get_universe() -> UniverseGraph:
    """Get the loaded universe graph for tool implementations."""
    if _universe is None:
        raise RuntimeError("Universe graph not loaded")
    return _universe


def resolve_system_name(name: str) -> int:
    """
    Resolve system name to vertex index with error handling.

    Raises:
        SystemNotFoundError: If system cannot be resolved.
    """
    universe = get_universe()
    idx = universe.resolve_name(name)
    if idx is None:
        # Find suggestions using fuzzy matching
        suggestions = _find_suggestions(name, universe)
        raise SystemNotFoundError(name, suggestions)
    return idx


def _find_suggestions(name: str, universe: UniverseGraph, limit: int = 3) -> list[str]:
    """Find similar system names for error suggestions."""
    name_lower = name.lower()
    matches = []

    for canonical_lower, canonical in universe.name_lookup.items():
        # Simple prefix/substring matching
        if canonical_lower.startswith(name_lower) or name_lower in canonical_lower:
            matches.append(canonical)
            if len(matches) >= limit:
                break

    return matches
```

### Module Init

```python
# aria_esi/mcp/__init__.py

from .server import UniverseServer, main
from .errors import (
    UniverseError,
    SystemNotFoundError,
    RouteNotFoundError,
    InvalidParameterError,
)

__all__ = [
    "UniverseServer",
    "main",
    "UniverseError",
    "SystemNotFoundError",
    "RouteNotFoundError",
    "InvalidParameterError",
]
```

## Dependencies

```toml
# pyproject.toml additions
[project.dependencies]
mcp = ">=1.0.0"

[project.scripts]
aria-universe = "aria_esi.mcp.server:main"
```

## Acceptance Criteria

1. [ ] `UniverseServer` initializes without errors
2. [ ] Graph loads successfully from pickle
3. [ ] Server starts and accepts stdio connections
4. [ ] Error classes serialize to MCP format
5. [ ] `SystemNotFoundError` includes suggestions
6. [ ] Environment variables respected (ARIA_UNIVERSE_GRAPH, LOG_LEVEL)
7. [ ] Entry point registered in pyproject.toml
8. [ ] Module exports all public classes

## Test Requirements

```python
# tests/mcp/test_server.py

def test_server_initialization():
    """Server initializes without loading graph."""
    server = UniverseServer()
    assert server.universe is None
    assert server.server is not None


def test_server_loads_graph(test_graph_path):
    """Server loads graph on demand."""
    server = UniverseServer(graph_path=test_graph_path)
    server.load_graph()
    assert server.universe is not None
    assert server.universe.system_count > 0


def test_env_var_graph_path(monkeypatch, tmp_path):
    """Server respects ARIA_UNIVERSE_GRAPH env var."""
    custom_path = tmp_path / "custom.pkl"
    monkeypatch.setenv("ARIA_UNIVERSE_GRAPH", str(custom_path))
    server = UniverseServer()
    assert server.graph_path == custom_path


# tests/mcp/test_errors.py

def test_system_not_found_mcp_format():
    """Error serializes to MCP format."""
    error = SystemNotFoundError("Juta", suggestions=["Jita", "Jatate"])
    mcp_error = error.to_mcp_error()

    assert mcp_error["error"]["code"] == "SYSTEM_NOT_FOUND"
    assert "Juta" in mcp_error["error"]["message"]
    assert mcp_error["error"]["data"]["suggestions"] == ["Jita", "Jatate"]


def test_route_not_found_mcp_format():
    """Route error includes origin and destination."""
    error = RouteNotFoundError("System A", "System B", reason="No gate connection")
    mcp_error = error.to_mcp_error()

    assert mcp_error["error"]["code"] == "ROUTE_NOT_FOUND"
    assert mcp_error["error"]["data"]["origin"] == "System A"
    assert mcp_error["error"]["data"]["destination"] == "System B"


def test_resolve_system_name_success(mock_universe):
    """Valid name resolves to index."""
    # Requires mocked universe with Jita
    idx = resolve_system_name("Jita")
    assert idx is not None


def test_resolve_system_name_error(mock_universe):
    """Invalid name raises with suggestions."""
    with pytest.raises(SystemNotFoundError) as exc:
        resolve_system_name("Juta")
    assert "Jita" in exc.value.suggestions
```

## Estimated Effort

- Implementation: Medium
- Testing: Small
- Total: Medium

## Notes

- Server uses stdio transport for Claude Code integration
- Tool registration is deferred to allow modular tool addition
- Fuzzy name matching uses simple prefix/substring for now; could upgrade to Levenshtein
- Logging level defaults to WARNING to reduce noise
