# ARIA Context Policy

This document defines context management rules for ARIA's MCP tool outputs to prevent context overflow and ensure consistent response structure.

## 1. Context Segments and Ordering

| Segment | Max Size | Priority | Load Order |
|---------|----------|----------|------------|
| CLAUDE.md | 20 KB | System | 1 (always) |
| Pilot Profile | 3 KB | Session | 2 |
| Persona Files | 15 KB | Session | 3 |
| Session Context | 2 KB | Session | 4 |
| Skill Base | 5 KB | Invocation | 5 |
| Skill Overlay | 2 KB | Invocation | 6 |
| Tool Results | 10 KB per call | Dynamic | 7 |

## 2. Budgets and Limits

### Per-Tool Output Limits

| Tool | Max Items | Max Size | Truncation Strategy |
|------|-----------|----------|---------------------|
| universe.route | 100 jumps | 5 KB | Summarize middle hops |
| universe.search | 50 systems | 3 KB | Top-N by relevance |
| universe.borders | 50 systems | 3 KB | Top-N by distance |
| universe.loop | 50 systems | 3 KB | N/A (algorithm-bounded) |
| market.orders | 20 per side | 3 KB | Top by price |
| market.arbitrage | 20 opportunities | 5 KB | Top by margin |
| sde.search | 20 items | 2 KB | Top by match score |
| sde.agent_search | 30 agents | 3 KB | Top by distance |
| skills.easy_80_plan | 30 skills | 3 KB | Core skills first |

### Total Context Budget

- **Soft limit:** 50 KB of tool output per conversation turn (advisory warning)
- **Hard limit:** 100 KB (advisory warning, no automatic enforcement)

**Note:** Budget tracking is advisory-only. Warnings are attached to `_meta` but no automatic summarization or truncation occurs at the conversation level. Per-tool limits (above) are enforced.

## 3. Tool Output Metadata

All tool outputs should include metadata via `_meta` field:

```json
{
  "systems": [...],
  "_meta": {
    "count": 45,
    "truncated": true,
    "truncated_from": 120,
    "timestamp": "2026-01-22T12:00:00+00:00"
  }
}
```

### Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| `count` | int | Number of items in output |
| `truncated` | bool | Whether output was truncated (omit if false) |
| `truncated_from` | int | Original count before truncation (only if truncated) |
| `timestamp` | string | ISO 8601 timestamp when output was generated |

### Implementation

Use the context utilities in `src/aria_esi/mcp/context.py` with centralized limits from `src/aria_esi/mcp/context_policy.py`:

```python
from aria_esi.mcp.context import wrap_output, wrap_output_multi, wrap_scalar_output, create_error_meta
from aria_esi.mcp.context_policy import UNIVERSE, MARKET, SDE, SKILLS

# For single-list outputs with automatic truncation
result = wrap_output({"systems": systems_list}, "systems", max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS)

# For multi-list outputs (e.g., buy/sell orders)
result = wrap_output_multi(
    {"buy_orders": buys, "sell_orders": sells},
    [("buy_orders", MARKET.OUTPUT_MAX_ORDERS), ("sell_orders", MARKET.OUTPUT_MAX_ORDERS)]
)

# For scalar outputs
result = wrap_scalar_output({"item": item_data})

# For errors
result = create_error_meta("NOT_FOUND", "System not found")
```

### Centralized Limits

All output limits are defined in `src/aria_esi/mcp/context_policy.py` as frozen dataclasses:

```python
from aria_esi.mcp.context_policy import UNIVERSE, MARKET, SDE, SKILLS, FITTING, GLOBAL

# Use in validation
if limit > UNIVERSE.SEARCH_MAX_LIMIT:
    raise InvalidParameterError("limit", limit, f"Max is {UNIVERSE.SEARCH_MAX_LIMIT}")

# Use in wrap_output
result = wrap_output(data, "systems", max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS)
```

Domain-specific limit classes:
- `UNIVERSE` - Navigation tools (search, borders, loop, etc.)
- `MARKET` - Market tools (orders, arbitrage, nearby, etc.)
- `SDE` - Static data (search, agents, skills, etc.)
- `SKILLS` - Skill planning (training time, Easy 80%, etc.)
- `FITTING` - Ship fitting tools
- `GLOBAL` - Cross-domain limits (output size, error truncation)

## 4. Summarization Triggers

| Condition | Action |
|-----------|--------|
| Route > 20 jumps | Summarize middle segment |
| List > 30 items | Truncate with count |
| History > 30 days | Aggregate to daily stats |
| Skill tree > 20 skills | Group by category |

### Route Summarization Example

For routes longer than 20 jumps:
- Show first 5 systems with full detail
- Show summary: security breakdown (highsec/lowsec/nullsec counts), lowest security system
- Show last 5 systems with full detail

Use `summarize_route()` for route outputs:

```python
from aria_esi.mcp.context import summarize_route
from aria_esi.mcp.context_policy import UNIVERSE

result = summarize_route(
    route_data,
    systems_key="systems",
    threshold=UNIVERSE.ROUTE_SUMMARIZE_THRESHOLD,  # 20
    head=UNIVERSE.ROUTE_SHOW_HEAD,                 # 5
    tail=UNIVERSE.ROUTE_SHOW_TAIL,                 # 5
)
```

Summarized routes include `_meta.summarized = true` and `_meta.original_count`.

## 5. Provenance Rules

All data presented must cite source:

| Source | Citation Format |
|--------|-----------------|
| SDE | "Per SDE: {description}" |
| EOS | "Calculated: {value} (EOS)" |
| ESI | "Current: {value} (as of {timestamp})" |
| Wiki | "Reference: wiki.eveuniversity.org" |

See `docs/DATA_VERIFICATION.md` for the full trust hierarchy.

## 6. Secret/PII Handling

| Data Type | Handling |
|-----------|----------|
| OAuth tokens | Never in tool output |
| Character names | Pass through (public) |
| Wallet balance | Only on explicit request |
| Corporation keys | Redact in logs |
| User passwords | N/A (not stored) |

### Sanitization Layers

1. **Input sanitization:** `sanitize_field()` for user-provided project data
2. **Output sanitization:** Strip HTML, limit lengths, escape markdown
3. **Logging sanitization:** Redact tokens in structured logs

## 7. Error Response Format

Errors should use consistent structure:

```json
{
  "error": true,
  "error_code": "NOT_FOUND",
  "message": "System 'Xyzzy' not found in universe",
  "_meta": {
    "count": 0,
    "timestamp": "2026-01-22T12:00:00+00:00"
  }
}
```

### Standard Error Codes

| Code | Description |
|------|-------------|
| `NOT_FOUND` | Requested resource not found |
| `INVALID_PARAMS` | Invalid or missing parameters |
| `RATE_LIMITED` | Too many requests |
| `AUTH_REQUIRED` | Authentication needed |
| `CAPABILITY_DENIED` | Action blocked by policy |

Error messages are truncated at 500 characters.

## 8. Cache Invalidation

YAML configuration caches check file modification time on access:

| Cache | File | TTL |
|-------|------|-----|
| Easy 80% efficacy rules | `reference/skills/efficacy_rules.yaml` | mtime-based |
| Easy 80% meta alternatives | `reference/skills/meta_alternatives.yaml` | mtime-based |
| Breakpoint skills | `reference/skills/breakpoint_skills.yaml` | mtime-based |
| Activity skill plans | `reference/activities/skill_plans.yaml` | mtime-based |

Runtime caches use TTL:

| Cache | TTL | Reset Function |
|-------|-----|----------------|
| Activity (kills/jumps) | 10 min | `reset_activity_cache()` |
| Market prices | 5 min | `reset_market_cache()` |
| SDE queries | Until reimport | `reset_sde_query_service()` |

## 9. Singleton Management

All module-level singletons must have reset functions for testing:

```python
# Pattern for singleton caches
_cache: dict | None = None

def reset_cache() -> None:
    """Reset cache for testing."""
    global _cache
    _cache = None
```

The `reset_all_singletons()` fixture in `tests/conftest.py` resets all singletons before and after each test.

## 10. Structured Logging and Budget Tracking

MCP dispatchers use the `@log_context` decorator for observability and budget tracking:

```python
from aria_esi.mcp.context import log_context

@server.tool()
@log_context("universe")
async def universe(action: str, ...) -> dict:
    ...
```

The decorator logs:
- **Start (DEBUG)**: Dispatcher, action, sanitized parameters
- **Complete (INFO)**: Dispatcher, action, elapsed_ms, output_count, truncated, output_bytes, budget_bytes_used
- **Error (WARNING)**: Dispatcher, action, elapsed_ms, error, error_type

Enable JSON logging with `ARIA_LOG_JSON=1` for structured log aggregation.

### Context Budget Tracking

The decorator automatically tracks cumulative output size across tool calls:

```python
from aria_esi.mcp.context_budget import get_context_budget, reset_context_budget

# Budget is tracked automatically by @log_context
# When limits are exceeded, _meta includes budget_warning
```

**Note:** `reset_context_budget()` is available but not currently called in production. Budget accumulates across all tool calls in a session. This may cause persistent warnings if many tools are invoked.

Budget warnings are automatically added to `_meta` when limits are exceeded:
- **Soft limit (50 KB)**: Advisory warning with remaining budget
- **Hard limit (100 KB)**: Advisory warning suggesting scope reduction

**Note:** These are advisory signals only. No automatic enforcement occurs at the conversation level. The LLM may use these warnings to self-limit follow-up queries, but truncation/summarization is not automatic. Per-tool limits are enforced independently.

## Related Documentation

- `docs/DATA_VERIFICATION.md` - Data trust hierarchy
- `docs/DATA_FILES.md` - File paths and volatility
- `src/aria_esi/mcp/context.py` - Output metadata utilities and route summarization
- `src/aria_esi/mcp/context_budget.py` - Context budget tracking
- `src/aria_esi/mcp/context_policy.py` - Centralized limit definitions
- `src/aria_esi/mcp/policy.py` - Capability policy engine
