# ARIA Universe MCP Server

High-performance EVE Online universe navigation server using the Model Context Protocol (MCP).

## Overview

The ARIA Universe MCP Server provides sub-millisecond query responses for:

- **Route Planning** - Calculate optimal routes between systems with security preferences
- **Border Discovery** - Find high-sec systems adjacent to low-sec space
- **Loop Planning** - Create circular mining/patrol routes through border systems
- **System Lookups** - Batch queries for system information
- **Security Analysis** - Analyze routes for chokepoints and danger zones

## Quick Start

### 1. Build the Universe Graph

The server requires a pre-built universe graph:

```bash
# Build from universe cache (one-time setup)
uv run aria-esi graph-build

# Verify the graph
uv run aria-esi graph-verify
```

### 2. Configure MCP Server

Add to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "aria-universe": {
      "command": "uv",
      "args": ["run", "python", "-m", "aria_esi.mcp.server"],
      "cwd": "/path/to/EveOnline/.claude/scripts"
    }
  }
}
```

### 3. Verify Connection

The server is running if you see `universe_route`, `universe_loop`, etc. in your available MCP tools.

## Available Tools

| Tool | Description |
|------|-------------|
| `universe_route` | Point-to-point navigation with security modes |
| `universe_systems` | Batch lookup of system details |
| `universe_borders` | Find high-sec systems bordering low-sec |
| `universe_search` | Filter systems by security, region, distance |
| `universe_loop` | Plan circular routes through border systems |
| `universe_analyze` | Route security analysis, chokepoints |
| `universe_nearest` | Find nearest systems matching predicates |

### Route Modes

- `shortest` - Minimum jumps regardless of security
- `safe` - Prioritize high-sec, heavy penalty for entering low/null
- `unsafe` - Prefer low-sec (for hunting routes)

### System Avoidance

All routing tools support `avoid_systems` to route around known danger zones:

```python
universe_route("Jita", "Dodixie", avoid_systems=["Uedama", "Sivala"])
universe_loop("Masalle", avoid_systems=["Niarja"])
```

## CLI Fallback

When the MCP server is unavailable, equivalent CLI commands exist:

```bash
# Route planning
uv run aria-esi route Jita Amarr --safe

# Border discovery
uv run aria-esi borders --system Masalle --limit 10

# Loop planning
uv run aria-esi loop Sortet --target-jumps 20 --min-borders 3
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ARIA_UNIVERSE_GRAPH` | `src/aria_esi/data/universe.universe` | Path to the universe graph (supports .universe and legacy .pkl) |
| `ARIA_UNIVERSE_LOG_LEVEL` | `WARNING` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |

## Troubleshooting

### Server Won't Start

**Problem:** "Graph not found" error

**Solution:** Build the graph first:
```bash
uv run aria-esi graph-build
```

**Problem:** "Could not load graph" error

**Solution:** Graph may be corrupted. Rebuild it:
```bash
uv run aria-esi graph-build --force
uv run aria-esi graph-verify
```

### Tools Not Appearing

**Problem:** MCP tools don't show up in Claude's tool list

**Check:**
1. Verify `.mcp.json` path is correct
2. Ensure `cwd` points to the `.claude/scripts` directory
3. Check server logs: `ARIA_UNIVERSE_LOG_LEVEL=DEBUG uv run python -m aria_esi.mcp.server`

### Slow Performance

**Problem:** Queries taking longer than expected

**Check:**
1. Verify graph loaded once: first query may take 50-100ms for graph load
2. Subsequent queries should be <5ms
3. Run `uv run aria-esi graph-stats` to verify graph integrity

## Cache Management

### Updating the Universe Cache

The universe cache (`universe_cache.json`) contains static EVE Online system/stargate data. Update when:

- CCP adds/removes systems (rare)
- Triglavian invasions change system connections (historical)
- New expansions modify the stargate network

**Update procedure:**

```bash
# 1. Regenerate cache from ESI (requires network)
uv run python -m aria_esi.cache.builder

# 2. Rebuild the graph
uv run aria-esi graph-build --force

# 3. Verify the new graph
uv run aria-esi graph-verify
```

### Cache Versioning

The graph stores a version string from the cache. Check version:

```bash
uv run aria-esi graph-stats | grep Version
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Claude Code Session                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐   stdio/JSON-RPC   ┌────────────────────┐    │
│  │   Claude     │◄─────────────────►│  aria-universe MCP │    │
│  │   (LLM)      │                    │  Server            │    │
│  └──────────────┘                    └─────────┬──────────┘    │
│                                                │               │
│                                                ▼               │
│                                      ┌────────────────────┐    │
│                                      │   UniverseGraph    │    │
│                                      │  (in-memory)       │    │
│                                      └─────────┬──────────┘    │
│                                                │               │
│                                                ▼               │
│                                      ┌────────────────────┐    │
│                                      │   universe.pkl     │    │
│                                      │  (loaded at start) │    │
│                                      └────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Known Limitations

### Wormhole Systems

J-space (wormhole) systems have no stargate connections. The server will return an error for wormhole routing:

```
"No route available - wormhole systems have no stargate connections"
```

### Pochven (Triglavian Space)

Triglavian "minor victory" systems have altered connectivity that may not be fully represented. Use with caution for Pochven routing.

### Single Instance

The MCP server uses stdio transport, supporting one Claude session at a time. For multiple sessions, each needs its own server process.

## Performance Targets

| Operation | Target | Typical |
|-----------|--------|---------|
| Graph load | <100ms | ~50ms |
| Route query | <5ms | <2ms |
| Border search | <5ms | <2ms |
| Loop planning | <50ms | <20ms |
| System lookup | <1ms | <0.5ms |

## Development

### Running Tests

```bash
# Unit tests
uv run pytest tests/mcp/ -v

# With coverage
uv run pytest tests/mcp/ --cov=aria_esi.mcp --cov-report=term-missing

# Benchmarks (requires real graph)
uv run pytest tests/benchmarks/ -v -m benchmark --benchmark-enable
```

### Building from Source

```bash
# Install dependencies
uv sync --extra universe --extra dev

# Build graph
uv run aria-esi graph-build

# Run server
uv run python -m aria_esi.mcp.server
```
