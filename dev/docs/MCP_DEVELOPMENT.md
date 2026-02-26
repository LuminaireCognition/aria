# MCP Dispatcher Development Guide

How to add new actions to ARIA's MCP dispatchers.

## Overview

ARIA's MCP server exposes 6 dispatchers, each handling multiple actions via a single tool entry point:

| Dispatcher | Source | Actions |
|------------|--------|---------|
| `universe()` | `src/aria_esi/mcp/dispatchers/universe/` | 14 navigation/intel actions |
| `market()` | `src/aria_esi/mcp/dispatchers/market.py` | 18 market/trade actions |
| `sde()` | `src/aria_esi/mcp/dispatchers/sde.py` | 9 static data actions |
| `skills()` | `src/aria_esi/mcp/dispatchers/skills.py` | 10 skill planning actions |
| `fitting()` | `src/aria_esi/mcp/dispatchers/fitting.py` | 3 fitting actions |
| `status()` | `src/aria_esi/mcp/dispatchers/status.py` | 1 health check |

Each dispatcher is registered in `src/aria_esi/mcp/server.py`.

## Adding a New Action

### Step 1: Implement the Tool Function

Create or extend a tools file in the appropriate module. For example, adding a new market action:

```python
# src/aria_esi/mcp/market/tools_my_action.py

from aria_esi.mcp.context import wrap_output, wrap_scalar_output, create_error_meta
from aria_esi.mcp.context_policy import MARKET

async def my_action(item: str, region: str = "jita", **kwargs) -> dict:
    """Implement the action logic."""
    # ... fetch data, compute results ...

    # For list outputs (auto-truncates):
    return wrap_output({"results": results}, "results", max_items=MARKET.OUTPUT_MAX_ORDERS)

    # For scalar outputs:
    return wrap_scalar_output({"item": item_data})

    # For errors:
    return create_error_meta("NOT_FOUND", f"Item '{item}' not found")
```

### Step 2: Add the Action to the Dispatcher

Edit the dispatcher file (e.g., `src/aria_esi/mcp/dispatchers/market.py`):

```python
async def market(action: str, **kwargs) -> dict:
    match action:
        # ... existing actions ...
        case "my_action":
            return await my_action(**kwargs)
        case _:
            return create_error_meta("INVALID_PARAMS", f"Unknown action: {action}")
```

### Step 3: Update the Dispatcher Docstring

The dispatcher's docstring is what Claude sees as the tool description. Add your action to the docstring's action list and parameter documentation.

### Step 4: Register in CLAUDE.md (if user-facing)

If the action should be mentioned in the system prompt, update the dispatcher table in `CLAUDE.md`.

## Context Policy Compliance

All tool outputs must follow the context policy defined in [CONTEXT_POLICY.md](CONTEXT_POLICY.md).

### Output Wrapping

Always use the context utilities — never return raw dicts:

```python
from aria_esi.mcp.context import wrap_output, wrap_output_multi, wrap_scalar_output

# Single list: auto-truncates and adds _meta
wrap_output({"systems": data}, "systems", max_items=50)

# Multiple lists (e.g., buy/sell orders):
wrap_output_multi(data, [("buy_orders", 20), ("sell_orders", 20)])

# Scalar (single item, no truncation):
wrap_scalar_output({"item": item_data})
```

### Centralized Limits

Define output limits in `src/aria_esi/mcp/context_policy.py`:

```python
@dataclass(frozen=True)
class MarketPolicy:
    OUTPUT_MAX_ORDERS: int = 20
    OUTPUT_MAX_ARBITRAGE: int = 20
    # Add your limit here:
    OUTPUT_MAX_MY_ACTION: int = 30
```

### Metadata

Every response includes `_meta` with:
- `count` — number of items returned
- `truncated` / `truncated_from` — if output was truncated
- `timestamp` — ISO 8601 generation time

## Error Handling

Use consistent error patterns:

```python
from aria_esi.mcp.context import create_error_meta
from aria_esi.mcp.errors import InvalidParameterError

# Parameter validation (raises, caught by dispatcher)
if limit > MARKET.SEARCH_MAX_LIMIT:
    raise InvalidParameterError("limit", limit, f"Max is {MARKET.SEARCH_MAX_LIMIT}")

# Graceful not-found (returns error dict)
return create_error_meta("NOT_FOUND", f"System '{name}' not found in universe")
```

### Standard Error Codes

| Code | When |
|------|------|
| `NOT_FOUND` | Requested resource doesn't exist |
| `INVALID_PARAMS` | Bad or missing parameters |
| `RATE_LIMITED` | Too many requests |
| `AUTH_REQUIRED` | ESI authentication needed |
| `CAPABILITY_DENIED` | Action blocked by policy |

## Testing

### Unit Tests (Tier 1)

MCP dispatcher tests live in `tests/mcp/`:

```python
import pytest

@pytest.mark.tier1
async def test_my_action_basic():
    """Test basic my_action behavior."""
    result = await my_action(item="Tritanium", region="jita")
    assert "results" in result
    assert "_meta" in result

@pytest.mark.tier1
async def test_my_action_not_found():
    """Test error handling for missing items."""
    result = await my_action(item="NonexistentItem")
    assert result.get("error") is True
    assert result["error_code"] == "NOT_FOUND"
```

### Running Tests

```bash
# MCP tests only
uv run pytest tests/mcp/ -m tier1

# All fast tests
uv run pytest -m "not tier2 and not tier3"
```

## CLI Fallback Pattern

If your MCP action should also be available via CLI (for when MCP is unavailable):

1. Create a CLI command in `src/aria_esi/commands/`
2. Register it in the CLI entry point
3. Add the fallback mapping to CLAUDE.md's MCP Fallback Behavior table

Not all MCP actions need CLI equivalents — only those used by skills that must work without MCP.

## Logging and Observability

Dispatchers use the `@log_context` decorator:

```python
from aria_esi.mcp.context import log_context

@server.tool()
@log_context("market")
async def market(action: str, ...) -> dict:
    ...
```

This automatically logs start, completion, and errors with timing and output size.

## Related Documentation

- [CONTEXT_POLICY.md](CONTEXT_POLICY.md) — Output limits and metadata format
- `src/aria_esi/mcp/context.py` — Output wrapping utilities
- `src/aria_esi/mcp/context_policy.py` — Centralized limit definitions
- `src/aria_esi/mcp/errors.py` — Error types
