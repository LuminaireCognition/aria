# Type Checking Roadmap

ARIA uses a gradual typing adoption strategy with mypy. This document tracks progress and provides guidance for contributors.

## Current Status: Phase 4 (In Progress)

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Baseline (syntax errors, undefined names) | Complete |
| 2 | `union-attr`, `attr-defined` | Complete |
| 3 | `arg-type`, `return-value` | Complete |
| 4 | `assignment`, `index`, `operator` | In Progress |
| 5 | `disallow_untyped_defs` on core modules | Planned |
| 6 | Strict mode on all modules | Planned |

## Running Type Checks

```bash
# Run mypy on the entire codebase
uv run mypy src/aria_esi/

# Check specific module
uv run mypy src/aria_esi/core/auth.py

# With verbose output
uv run mypy src/aria_esi/ --show-error-context
```

## Security-Critical Modules (Strict Typing)

The following modules handle credentials and have strict typing enforced (Phase 5 partial):

- `aria_esi.core.auth` - OAuth token management
- `aria_esi.core.keyring_backend` - Secure credential storage

These modules have:
- `disallow_untyped_defs = true` - All functions must have type hints
- `check_untyped_defs = true` - Type check inside untyped functions
- `disallow_incomplete_defs = true` - No partial type hints
- `warn_return_any = true` - Warn on returning `Any`

## Disabled Error Codes

Currently disabled for future phases:

| Code | Reason | Estimated Errors |
|------|--------|------------------|
| `misc` | Conditional exception aliases | Low |
| `var-annotated` | `defaultdict`/`dict` literals need annotations | Moderate |
| `index` | Invalid index type for typed containers | ~75 |
| `operator` | Unsupported operand types | Moderate |
| `call-overload` | Dict typing causing `__getitem__` errors | Low |

## Per-Module Overrides

### MCP Dispatchers (Incomplete Implementations)

```toml
# Modules with missing _impl functions
[[tool.mypy.overrides]]
module = [
    "aria_esi.mcp.dispatchers.sde",
    "aria_esi.mcp.dispatchers.skills",
    "aria_esi.mcp.dispatchers.market",
]
disable_error_code = ["attr-defined"]
```

### Market Tools (Async Client Issues)

```toml
[[tool.mypy.overrides]]
module = [
    "aria_esi.mcp.market.tools_analysis",
    "aria_esi.mcp.market.tools_nearby",
    "aria_esi.mcp.market.tools_arbitrage",
    "aria_esi.mcp.market.tools_prices",
    "aria_esi.services.history_cache",
    "aria_esi.services.market_refresh",
]
disable_error_code = ["attr-defined", "union-attr"]
```

## Adding Types to New Code

When writing new code:

1. **Always add type hints** to function signatures
2. **Use `Optional[T]`** for nullable values (or `T | None` for Python 3.10+)
3. **Prefer specific types** over `Any`
4. **Add `# type: ignore[error-code]`** only when necessary, with comment explaining why

### Example

```python
from typing import Optional

def calculate_profit(
    cost: float,
    price: float,
    tax_rate: Optional[float] = None
) -> float:
    """Calculate profit margin."""
    effective_tax = tax_rate if tax_rate is not None else 0.0
    return price * (1 - effective_tax) - cost
```

## Common Type Patterns in ARIA

### ESI Response Handling

```python
from typing import TypedDict

class AssetEntry(TypedDict):
    item_id: int
    type_id: int
    quantity: int
    location_id: int

def process_assets(assets: list[AssetEntry]) -> dict[int, int]:
    """Group assets by type_id."""
    result: dict[int, int] = {}
    for asset in assets:
        tid = asset["type_id"]
        result[tid] = result.get(tid, 0) + asset["quantity"]
    return result
```

### Optional Dependencies

```python
# Conditional imports use type: ignore[assignment]
try:
    from tenacity import retry  # type: ignore[assignment]
except ImportError:
    retry = None  # type: ignore[assignment]
```

## Contributing

When fixing type errors:

1. Check if the error is in the disabled list (might not be ready to fix)
2. Prefer fixing the underlying issue over adding `# type: ignore`
3. If adding `# type: ignore`, include the specific error code
4. Run `uv run mypy src/aria_esi/` before submitting PR

## Related Documentation

- [PYTHON_ENVIRONMENT.md](PYTHON_ENVIRONMENT.md) - Development setup
- [pyproject.toml](../pyproject.toml) - Full mypy configuration (L181-275)
