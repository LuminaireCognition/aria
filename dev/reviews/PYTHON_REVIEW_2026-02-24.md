# Python Code Quality Review: ARIA ESI

**Reviewer:** Claude Opus 4.6
**Date:** 2026-02-24
**Scope:** Full Python codebase review (second review; prior review dated 2026-01-23)

---

## 1) Codebase Map

### Quantitative Overview

| Metric | Value |
|--------|-------|
| Total source lines (non-vendor) | ~121,600 |
| Total test lines | ~108,780 |
| Test-to-source ratio | 0.89:1 |
| Python files (source) | ~180 |
| Python files (tests) | ~160 |
| Top-level packages | 10 (`cache`, `commands`, `core`, `data`, `fitting`, `mcp`, `models`, `persona`, `services`, `universe`) |
| Entrypoints | 2 (`aria-esi` CLI, `aria-universe` MCP server) |
| Python version | >=3.11 |
| Package version | 2.0.0 (pyproject.toml) / 1.0.0 (__init__.py) |

### Key Modules and Packages

```
src/aria_esi/
├── __init__.py              # Package init, re-exports core classes (version: 1.0.0 - STALE)
├── __main__.py              # CLI entrypoint (argparse, 27 command phases)
├── core/                    # Infrastructure layer
│   ├── auth.py              # Two-tier credentials: keyring + file (831 lines)
│   ├── client.py            # Sync ESI HTTP client using httpx (922 lines)
│   ├── async_client.py      # Async ESI HTTP client using httpx (560 lines)
│   ├── config.py            # pydantic-settings with ARIA_ prefix (400 lines)
│   ├── retry.py             # Dual retry: tenacity or simple fallback (469 lines)
│   ├── logging.py           # Structured logging, text/JSON modes (247 lines)
│   ├── path_security.py     # Path traversal protection (333 lines)
│   ├── constants.py         # Game constants, trade hubs, ship groups
│   ├── data_integrity.py    # SHA256 checksum verification
│   ├── formatters.py        # ISK/duration/number formatting
│   ├── freshness.py         # Data freshness tracking
│   ├── freshness_adapters.py # Adapter layer for freshness
│   ├── keyring_backend.py   # Secure credential storage backend
│   └── __init__.py          # Massive re-export (~220 lines)
│
├── models/                  # Pydantic v2 data models
│   ├── market.py            # Market/arbitrage models (1,101 lines)
│   ├── fitting.py           # Ship fitting models
│   └── sde.py               # Static Data Export models
│
├── services/                # Business logic layer
│   ├── arbitrage_engine.py  # Cross-region arbitrage detection
│   ├── market_refresh.py    # Scope-based market data refresh
│   ├── history_cache.py     # Market history caching
│   ├── navigation/          # Route planning service
│   ├── loop_planning.py     # TSP-approximate circular routes
│   ├── redisq/              # Real-time intel (poller, notifications, interest engine)
│   ├── sovereignty/         # Sovereignty and coalition data
│   ├── killmail_store/      # Killmail persistence
│   └── __init__.py          # Lazy imports via __getattr__ (81 lines)
│
├── mcp/                     # MCP server + tool implementations
│   ├── server.py            # FastMCP server lifecycle (173 lines)
│   ├── tools.py             # Tool registration + system name resolution (264 lines)
│   ├── errors.py            # Structured exception hierarchy (124 lines)
│   ├── models.py            # Pydantic response models (530 lines)
│   ├── activity.py          # Activity data caching
│   ├── context.py           # Output wrapping, truncation
│   ├── context_budget.py    # Context window tracking
│   ├── context_policy.py    # Token budgeting
│   ├── policy.py            # Capability gating
│   ├── esi_client.py        # Singleton async client management
│   ├── dispatchers/         # 8 unified dispatchers (8,208 lines total)
│   │   ├── universe.py      # 14 actions (3,798 lines - LARGEST FILE)
│   │   ├── market.py        # 19 actions (1,236 lines)
│   │   ├── sde.py           # 10 actions (777 lines)
│   │   ├── killmails.py     # 4 actions (633 lines)
│   │   ├── fitting.py       # 3 actions (536 lines)
│   │   ├── skills.py        # 10 actions (469 lines)
│   │   ├── pilot.py         # 3 actions (435 lines)
│   │   └── status.py        # Unified status (324 lines)
│   ├── market/              # Market tool implementations (~15 files)
│   ├── sde/                 # SDE tool implementations (~10 files)
│   └── fitting/             # Fitting tool implementations
│
├── commands/                # CLI command modules (~30 files)
├── universe/                # igraph-based graph + serialization
│   ├── graph.py             # UniverseGraph dataclass (igraph + NumPy)
│   ├── builder.py           # Graph construction from ESI
│   └── serialization.py     # Graph save/load (msgpack + legacy pickle)
│
├── fitting/                 # EOS integration
│   ├── eft_parser.py        # EFT format parsing
│   ├── eos_bridge.py        # EOS engine bridge
│   ├── eos_data.py          # EOS data management
│   ├── skill_registry.py    # Pilot skill registry
│   └── skills.py            # Skill requirement analysis
│
├── cache/                   # Cache construction
├── persona/                 # Persona context compilation
├── data/                    # Static data files
└── _vendor/                 # Vendored dependencies (EOS fitting engine)
```

### Entrypoints

| Name | Module | Purpose |
|------|--------|---------|
| `aria-esi` | `aria_esi.__main__:main` | CLI with 27+ subcommands |
| `aria-universe` | `aria_esi.mcp.server:main` | MCP server for Claude Code |

### Architecture

The codebase follows a layered architecture:

```
Commands (CLI) ─────┐
                    ├──► Services ──► Core (client, auth, config, retry)
MCP Dispatchers ────┘         │
                              ├──► Models (Pydantic v2)
                              └──► Universe (igraph graph)
```

Key architectural decisions:
- **Dispatcher consolidation**: ~45 individual MCP tools consolidated into 8 domain dispatchers to reduce LLM attention degradation
- **Singleton + reset pattern**: Global module-level singletons with `get_*()` / `reset_*()` pairs for testability
- **Dual client**: Sync `ESIClient` for CLI, async `AsyncESIClient` for MCP server
- **Optional dependencies**: `tenacity` (retry), `openai`, `google-genai` are optional with graceful fallback
- **Vendored EOS**: Fitting engine vendored at `_vendor/eos/` to avoid external dependency

---

## 2) Quality Assessment

### 2.1 Architecture and Layering

**Rating: 4/5**

The architecture is well-structured with clear separation between infrastructure (`core/`), business logic (`services/`), presentation (`commands/`, `mcp/dispatchers/`), and data models (`models/`). The `services/__init__.py` uses `__getattr__` for lazy imports, which prevents circular dependencies.

**Strengths:**
- Clean layering: commands and dispatchers never bypass services to access core directly for business logic
- Dispatcher pattern effectively reduces the MCP tool surface area for LLM consumption
- Universe graph uses frozen dataclass with `slots=True` and NumPy arrays for O(1) lookups
- Services layer properly separates business logic from transport (CLI vs MCP)

**Weaknesses:**
- `mcp/dispatchers/universe.py` at 3,798 lines is the largest file in the codebase. It consolidates 14 action handlers into a single module. This should be decomposed into sub-modules per action group (routing, borders, activity, analysis)
- `core/__init__.py` is a ~220-line re-export barrel that creates a "god module" import surface. Consumers should import from specific submodules instead
- The `commands/navigation.py` module duplicates activity caching logic that also exists in `mcp/activity.py`

### 2.2 API Design (Public Interfaces)

**Rating: 4/5**

Public APIs are generally well-designed with clear naming and consistent patterns.

**Strengths:**
- MCP dispatchers present a uniform `action` parameter interface across all domains
- System name resolution with auto-correction and correction tracking is user-friendly
- `ResolvedSystem` frozen dataclass cleanly separates resolution from correction tracking
- `collect_corrections()` utility elegantly aggregates corrections from multiple resolved systems

**Weaknesses:**
- `_build_url()` in `client.py` manually constructs query strings (`"&".join(f"{k}={v}" ...)`) instead of using `httpx`'s built-in `params` argument. This bypasses URL encoding and could produce malformed URLs with special characters
- `create_async_client()` calls `await client.__aenter__()` directly instead of using `async with`. This is an anti-pattern that makes resource cleanup less reliable
- `ESIClient.__del__()` for cleanup is fragile -- `__del__` is not guaranteed to run and can cause issues during interpreter shutdown

### 2.3 Type Hints and Static Analysis

**Rating: 3/5**

The project has a well-documented gradual mypy adoption roadmap (6 phases), currently at Phase 4. Security-critical modules (`auth.py`, `keyring_backend.py`) have strict typing enforced.

**Strengths:**
- 187 files use `from __future__ import annotations` for forward reference support
- Gradual mypy roadmap is clearly documented in `pyproject.toml` with phase tracking
- Security modules have `disallow_untyped_defs = true` and `warn_return_any = true`
- Pydantic models use `Field()` validators extensively (`ge=`, `le=`, `description=`)
- `Literal` types used appropriately for constrained string values (`SecurityFilter`, `ActivityLevel`, `ThreatLevel`)

**Weaknesses:**
- 5 mypy error codes remain globally disabled: `misc`, `var-annotated`, `index` (75 errors), `operator`, `call-overload`
- `ignore_missing_imports = true` globally -- this suppresses real errors alongside optional dependency imports
- Several dispatcher modules have per-file `attr-defined` and `union-attr` disabled, indicating incomplete type narrowing
- `check_untyped_defs = false` globally means the bodies of untyped functions are not checked at all
- Legacy `Optional` and `Union` usage persists despite `UP007`/`UP045` being available (these are suppressed in ruff as style preference, which is reasonable)
- `RetryError = Exception  # type: ignore[assignment]` in retry.py is a crude workaround for conditional imports

### 2.4 Static Analysis and Linting

**Rating: 4/5**

The project uses ruff for linting and formatting, with pre-commit hooks for enforcement.

**Strengths:**
- Ruff configured with a solid rule set: `E`, `W`, `F`, `I`, `B`, `C4`, `UP`
- Pre-commit hooks run ruff lint, ruff format, mypy, deprecated term checking, and COMMANDS.md freshness validation
- CI pipeline includes gitleaks for secret scanning
- Only 1 TODO/FIXME in non-vendor source code (excellent hygiene)
- Per-file ignores are well-documented and justified

**Weaknesses:**
- `B904` (raise-from) is globally suppressed with a TODO comment. This means exception chaining (`raise X from Y`) is not enforced anywhere, losing causal context in tracebacks. Only 42 occurrences of `raise ... from` exist across the entire codebase
- `B905` (zip-strict) is suppressed, missing opportunities to catch length-mismatch bugs
- No `SIM`, `RET`, `PTH`, or `PERF` rule sets enabled -- these catch common simplification opportunities and pathlib usage

### 2.5 Data Model Integrity

**Rating: 5/5**

Pydantic v2 models are exemplary across the codebase.

**Strengths:**
- Two base model classes (`MCPModel`, `MarketModel`) with consistent `ConfigDict(frozen=True, extra="forbid", ser_json_inf_nan="constants")`
- `frozen=True` prevents accidental mutation and enables hashing
- `extra="forbid"` catches typos in field names during construction
- `Field()` validators with `ge=`, `le=` constraints on security values (`-1.0` to `1.0`), ISK amounts, counts
- `default_factory=list` used consistently for mutable defaults
- Clear model hierarchy: `SystemInfo` contains `NeighborInfo` list and optional `SovereigntyInfo`
- Market models use `TypedDict` for trade hub configuration

**No significant weaknesses identified.**

### 2.6 Error Handling

**Rating: 3/5**

Error handling is functional but has systemic issues with broad exception catching and missing exception chaining.

**Strengths:**
- Structured MCP exception hierarchy: `UniverseError` base with `SystemNotFoundError`, `NoRouteError`, `InsufficientBordersError` -- each with `to_mcp_error()` for clean MCP error responses
- `SystemNotFoundError` includes suggestions for typo correction
- `RetryableESIError` and `NonRetryableESIError` cleanly separate retry-eligible failures
- `classify_httpx_error()` and `classify_http_error()` map HTTP status codes to appropriate exception types

**Weaknesses:**
- **224 broad `except Exception as e:` catches** across 74 files. Many of these should catch specific exception types
- **52 bare `except Exception:` catches** (without `as e`) across 33 files -- these silently swallow exceptions
- **B904 suppressed globally**: `raise X from Y` exception chaining is not enforced. When exceptions are re-raised inside `except` blocks, the original traceback is lost. Only 42 uses of `raise ... from` exist vs. 276 total broad catches
- `commands/universe.py` alone has 27 `except Exception` catches (6 bare + 21 with `as e`)
- Several `except Exception: pass` patterns in cleanup code that could mask real errors

### 2.7 Async Correctness

**Rating: 3/5**

The async layer works but contains duplication and anti-patterns.

**Strengths:**
- `AsyncESIClient` properly uses `httpx.AsyncClient` for true async I/O
- `asyncio.Lock` used for rate limiting in async context
- Proper `__aenter__`/`__aexit__` context manager protocol implemented
- `pytest-asyncio` in dev dependencies for async test support

**Weaknesses:**
- **`AsyncESIResponse` duplicates `ESIResponse`**: The two dataclasses are structurally identical (same fields, same properties for `last_modified_timestamp`, `expires_timestamp`, `total_pages`). A shared base or single class should be used
- **`AsyncESIError` duplicates `ESIError`**: Same pattern -- identical exception classes defined twice
- **`create_async_client()` calls `__aenter__` directly**: `await client.__aenter__()` bypasses the context manager protocol. If an error occurs between `__aenter__` and eventual `aclose()`, the client leaks. Should use `async with` or document the ownership contract
- `time` module imported inside methods in `async_client.py` instead of at module level
- No timeout propagation from `AsyncESIClient` to individual requests in some code paths

### 2.8 Resource Management

**Rating: 3/5**

Resource management relies heavily on singletons with manual cleanup.

**Strengths:**
- `ESIClient` implements `__enter__`/`__exit__` for context manager usage
- SQLite connections managed through dedicated database classes with close methods
- `reset_*()` functions on every singleton enable clean test teardown
- `conftest.py` has an autouse `reset_all_singletons` fixture that resets 30+ singletons between tests

**Weaknesses:**
- **30+ global singletons** require manual `reset_*()` calls. Adding a new singleton requires updating `conftest.py`. A dependency injection container or registry would be more maintainable
- `ESIClient.__del__()` is used for "opportunistic cleanup" but `__del__` has well-documented problems: not guaranteed to run, can raise during interpreter shutdown, prevents garbage collection of reference cycles
- `create_async_client()` creates a client without a context manager, requiring callers to remember `aclose()`
- No connection pooling strategy is documented for the async client in MCP server context

### 2.9 Logging and Observability

**Rating: 4/5**

Logging infrastructure is well-designed with both text and JSON output modes.

**Strengths:**
- Custom `AriaFormatter` supports both human-readable text and machine-parseable JSON output
- Module-level logger cache prevents repeated logger creation
- `get_logger(__name__)` pattern used consistently
- `ARIA_LOG_LEVEL` and `ARIA_LOG_JSON` environment variables for configuration
- `ARIA_DEBUG_TIMING` for performance debugging
- `reset_logging()` iterates `logging.Logger.manager.loggerDict` for clean test teardown

**Weaknesses:**
- `auth.py` uses `print()` to stderr for permission warnings instead of the logging framework
- `client.py` uses `logging.getLogger(__name__)` directly instead of the project's `get_logger()` wrapper
- No structured fields/context (e.g., correlation IDs, pilot IDs) attached to log records by default
- Log levels are not consistently applied -- some `logger.warning()` calls report informational conditions

### 2.10 Configuration Management

**Rating: 4/5**

Configuration is well-structured with pydantic-settings.

**Strengths:**
- `AriaSettings` uses `pydantic-settings` with `ARIA_` prefix for environment variables
- Singleton via `@lru_cache(maxsize=1)` with `reset_settings()` for testing
- External API keys loaded with `validation_alias` to allow non-prefixed env vars
- `.env` file discovery walks up the directory tree to find the project root
- Break-glass modes (`ARIA_ALLOW_UNSAFE_PATHS`, `ARIA_ALLOW_UNPINNED`, `ARIA_MCP_BYPASS_POLICY`) are clearly documented

**Weaknesses:**
- Path resolution (`_ENV_FILE`, `_INSTANCE_ROOT`) happens at module import time, making it difficult to override in tests
- `Optional` type annotations on settings fields use the legacy style (`Optional[str]`) rather than `str | None`
- No configuration schema validation beyond what pydantic-settings provides -- complex cross-field constraints are not validated

### 2.11 Testing Infrastructure

**Rating: 4/5**

The testing infrastructure is comprehensive and well-organized.

**Strengths:**
- Test-to-source ratio of 0.89:1 (108,780 test lines / 121,600 source lines)
- Multi-tier marker system: `unit`, `integration`, `slow`, `benchmark`, `golden`, `contract`, `structure`, `semantic`, `tier1`, `tier2`, `tier3`
- `conftest.py` (1,228 lines) provides extensive fixtures for ESI responses, credentials, universe graphs
- Session-scoped fixtures for expensive operations (universe graph building)
- `reset_all_singletons` autouse fixture resets 30+ singletons between tests
- Helper assertions: `approx_sec()`, `approx_isk()`, `assert_highsec()`, `assert_lowsec()`, `assert_nullsec()`
- CI runs on Python 3.11, 3.12, and 3.13
- `ARIA_NO_KEYRING=1` set in conftest before imports to prevent D-Bus hangs in CI

**Weaknesses:**
- Coverage threshold is 59% (`fail_under = 59`) -- below industry standard of 70-80%. Comment in config notes this was lowered after removing well-tested code
- `__main__.py` is excluded from coverage, but it contains non-trivial logic (command registration, error handling)
- `cmd_test_core()` in `__main__.py` makes live ESI API calls -- this function is not suitable for CI and not excluded from the package
- Some test warning filters suppress real concerns (e.g., `"ignore:unclosed database:ResourceWarning"`)
- Benchmark tests require a real universe graph and are excluded from default test runs

### 2.12 Performance Considerations

**Rating: 4/5**

Performance-critical paths are well-optimized.

**Strengths:**
- Universe graph uses igraph with pre-indexed lookups: `name_lookup` dict for O(1) name resolution, `frozenset` for border system checks
- NumPy arrays for security values enable vectorized comparisons
- Session-scoped caching for expensive universe graph construction in tests
- Lazy imports in `services/__init__.py` prevent unnecessary module loading
- Activity data cache with TTL to avoid re-fetching global ESI datasets per query
- Levenshtein distance implementation uses O(min(m,n)) space DP with early termination for length differences

**Weaknesses:**
- `_build_url()` constructs query strings manually on every request -- micro-optimization but indicates unfamiliarity with httpx's built-in `params` parameter
- No connection pool size tuning documented for httpx clients
- `_find_suggestions()` iterates all system names (~8,000) for fuzzy matching with no index structure
- Rate limiting in sync client uses `time.sleep()` which blocks the thread entirely

### 2.13 Security Hygiene

**Rating: 4/5**

Security is taken seriously with multiple defensive layers.

**Strengths:**
- Path security module (`path_security.py`) validates allowlisted prefixes, allowlisted extensions, rejects path traversal (`..`), and checks symlink containment
- Two-tier credential security: system keyring (Tier II) with fallback to plaintext JSON (Tier I)
- `validate_pilot_id()` prevents path traversal in pilot ID parameters
- gitleaks in CI pipeline for secret scanning
- `ARIA_ALLOW_UNSAFE_PATHS` break-glass mode requires explicit opt-in
- Data integrity verification with SHA256 checksums
- `.env` and credential files documented as "DO NOT READ" in CLAUDE.md

**Weaknesses:**
- `_build_url()` does not URL-encode query parameter values -- if user-controlled data flows into params, it could produce malformed or injectable URLs
- Token refresh is performed via subprocess call to an external script -- this makes the security boundary harder to audit
- `ignore_missing_imports = true` in mypy means type stubs for security-relevant libraries (keyring) are not checked
- No Content Security Policy or input sanitization documented for the MCP server responses

---

## 3) Priority-Ranked Action List

### P0 -- Critical (fix before next release)

1. **Version mismatch**: `__init__.py` declares `__version__ = "1.0.0"` while `pyproject.toml` declares `version = "2.0.0"`. Any code or tooling checking `aria_esi.__version__` gets the wrong value. Single-source the version from `pyproject.toml` using `importlib.metadata`.

2. **URL encoding gap in `_build_url()`**: Manual query string construction (`f"{k}={v}"`) does not URL-encode values. Use `httpx`'s `params` argument or `urllib.parse.urlencode()`. This is a correctness and potential security issue.

3. **Enable `B904` (raise-from)**: With only 42 existing `raise ... from` usages and 276 broad exception catches, exception chaining is almost never used. Enable the rule, add `from e` to existing re-raises, and use `from None` for intentional suppression. This dramatically improves debugging.

### P1 -- High (address within next sprint)

4. **Decompose `universe.py` dispatcher**: At 3,798 lines, this file is unmaintainable. Split into sub-modules by action group: `routing.py` (route, analyze, gatecamp_risk), `borders.py` (borders, loop, nearest), `activity.py` (activity, hotspots, fw_frontlines), `search.py` (systems, search, optimize_waypoints), `local_area.py`.

5. **Eliminate sync/async client duplication**: `ESIResponse` / `AsyncESIResponse` and `ESIError` / `AsyncESIError` are identical. Extract a shared `ESIResponse` class used by both clients. The error classes can be unified since they carry no async-specific behavior.

6. **Replace `create_async_client()` anti-pattern**: Replace `await client.__aenter__()` with a documented factory that returns a properly managed client, or require callers to use `async with`.

7. **Reduce broad exception catching**: Audit the 276 broad `except Exception` catches. Priority targets:
   - `commands/universe.py` (27 catches)
   - `mcp/dispatchers/universe.py` (7 catches)
   - `mcp/market/cache.py` (11 catches)
   - `services/redisq/poller.py` (12 catches)
   Replace with specific exception types where the failure mode is known.

### P2 -- Medium (address within next quarter)

8. **Raise coverage threshold to 65%**: Current threshold is 59%. The test infrastructure is excellent -- the gap is likely in command modules and service edge cases. Target 65% in Q1, 70% in Q2.

9. **Replace global singletons with a registry**: The 30+ `global` + `reset_*()` pattern is fragile. Implement a lightweight service registry or context object that holds all singletons and can be reset atomically. This also enables per-test isolation without autouse fixtures.

10. **Advance mypy to Phase 5**: Enable `check_untyped_defs = true` globally and `disallow_untyped_defs = true` on core modules. Resolve the 75 `index` errors currently suppressed. Use per-module overrides to gate the rollout.

11. **Remove `__del__` from `ESIClient`**: Replace with explicit lifecycle management. The `__del__` method is unreliable and can mask resource leaks. Use `contextlib.closing()` or `atexit` registration if cleanup at shutdown is needed.

12. **Standardize logging**: Replace `print()` calls in `auth.py` with `logger.warning()`. Ensure all modules use `get_logger()` instead of `logging.getLogger()` directly.

### P3 -- Low (backlog)

13. **Enable additional ruff rules**: Add `SIM` (simplification), `RET` (return statements), `PTH` (pathlib), `PERF` (performance) rule sets. These catch common improvements without high noise.

14. **Add structured log context**: Attach correlation IDs and pilot IDs to log records for request tracing in the MCP server.

15. **Document connection pool strategy**: Add configuration for httpx connection pool sizes, especially for the MCP server's async client.

16. **Clean up `core/__init__.py`**: Reduce the barrel re-export to only truly public API symbols, or remove it entirely and have consumers import from specific submodules.

---

## 4) Patch-Ready Recommendations (Top 3)

### Recommendation 1: Fix version mismatch with `importlib.metadata`

**File:** `src/aria_esi/__init__.py`

**Current:**
```python
__version__ = "1.0.0"
```

**Proposed:**
```python
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("aria")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"  # Not installed as package
```

**Rationale:** Single-sources version from `pyproject.toml` via installed package metadata. The `except` branch handles development mode where the package may not be formally installed. Eliminates the 1.0.0 vs 2.0.0 discrepancy permanently.

**Impact:** Low risk. Only changes how `__version__` is populated. All downstream consumers (`aria_esi.__version__`) get the correct value automatically.

---

### Recommendation 2: Fix URL encoding in `_build_url()`

**File:** `src/aria_esi/core/client.py`

**Current (lines 196-225):**
```python
def _build_url(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> str:
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    url = f"{self.base_url}{endpoint}"
    query_params = {"datasource": self.datasource}
    if params:
        query_params.update(params)
    if "?" in url:
        url += "&"
    else:
        url += "?"
    query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
    return url + query_string
```

**Proposed:**
```python
def _build_url(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> str:
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    url = f"{self.base_url}{endpoint}"
    query_params = {"datasource": self.datasource}
    if params:
        query_params.update(params)
    return str(httpx.URL(url, params=query_params))
```

**Rationale:** `httpx.URL` handles URL encoding, merging with existing query strings, and special character escaping. The current implementation does not encode values, so a parameter value containing `&` or `=` would produce a malformed URL. Using httpx's own URL builder is both correct and idiomatic.

**Impact:** Low-to-medium risk. All ESI requests flow through this method. The behavioral change is that parameter values are now properly encoded. ESI parameter values are typically numeric IDs and string constants, so the risk of a behavioral change is minimal, but all routes, markets, and system lookups flow through here.

---

### Recommendation 3: Eliminate sync/async response class duplication

**Files:**
- `src/aria_esi/core/client.py` (ESIResponse, ESIError)
- `src/aria_esi/core/async_client.py` (AsyncESIResponse, AsyncESIError)

**Current:** Two identical `@dataclass` classes with identical properties (`last_modified_timestamp`, `expires_timestamp`, `total_pages`) and two identical exception classes.

**Proposed:** Create `src/aria_esi/core/esi_types.py`:

```python
"""Shared types for sync and async ESI clients."""
from __future__ import annotations

from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any


@dataclass
class ESIResponse:
    """ESI response with headers for conditional requests."""
    data: dict | list | None
    headers: dict[str, str] = field(default_factory=dict)
    status_code: int = 200

    @property
    def last_modified_timestamp(self) -> int | None:
        header = self.headers.get("Last-Modified") or self.headers.get("last-modified")
        if not header:
            return None
        try:
            dt = parsedate_to_datetime(header)
            return int(dt.timestamp())
        except (ValueError, TypeError):
            return None

    @property
    def expires_timestamp(self) -> int | None:
        header = self.headers.get("Expires") or self.headers.get("expires")
        if not header:
            return None
        try:
            dt = parsedate_to_datetime(header)
            return int(dt.timestamp())
        except (ValueError, TypeError):
            return None

    @property
    def total_pages(self) -> int:
        header = self.headers.get("X-Pages") or self.headers.get("x-pages")
        if not header:
            return 1
        try:
            return int(header)
        except (ValueError, TypeError):
            return 1


class ESIError(Exception):
    """Base ESI client error."""
    pass
```

Then in both `client.py` and `async_client.py`:
```python
from .esi_types import ESIResponse, ESIError
# Remove local ESIResponse/AsyncESIResponse and ESIError/AsyncESIError definitions
# Add backward-compatible aliases if needed:
AsyncESIResponse = ESIResponse  # Backward compatibility
AsyncESIError = ESIError
```

**Rationale:** Eliminates ~120 lines of duplicated code. Changes to response parsing (e.g., adding a new header property) need only happen once. The `ESIResponse` class carries no sync/async behavior -- it is a pure data container.

**Impact:** Medium risk. Any code importing `AsyncESIResponse` or `AsyncESIError` by name needs the backward-compatible alias or a migration. A `grep` shows these are used primarily within the `async_client.py` module itself and its direct consumers, so the blast radius is limited.

---

## 5) Tooling and Standards Proposal

### Current Tooling Stack

| Tool | Version | Purpose | Status |
|------|---------|---------|--------|
| ruff | >=0.4.0 | Lint + format | Active, pre-commit |
| mypy | >=1.8.0 | Type checking | Active, pre-commit, Phase 4 |
| pytest | >=8.0 | Testing | Active, CI |
| pytest-xdist | >=3.5 | Parallel test execution | Active |
| pytest-cov | >=4.0 | Coverage | Active, 59% threshold |
| pytest-asyncio | >=0.23.0 | Async test support | Active |
| pytest-httpx | >=0.30 | HTTP mocking | Active |
| pytest-benchmark | >=4.0.0 | Performance benchmarks | Active |
| syrupy | >=4.0.0 | Snapshot testing | Active |
| pre-commit | >=3.6.0 | Hook management | Active |
| gitleaks | CI only | Secret scanning | Active |
| lychee | CI only | Link checking | Active |
| time-machine | >=2.10.0 | Time mocking | Active |
| jsonschema | >=4.20.0 | Schema validation | Active |
| tiktoken | >=0.12.0 | Token counting | Active |

### Proposed Changes

#### Short-term (next 2 sprints)

1. **Add ruff rule sets**: Enable `SIM`, `RET`, `PTH`, `PERF` incrementally. Run `ruff check --select SIM --statistics` first to gauge the volume of findings.

2. **Enable B904**: Remove `B904` from the ignore list. Run `ruff check --select B904 --fix` to auto-add `from e` where possible. Manual review for cases where `from None` is appropriate.

3. **Pin ruff version in pre-commit**: Use a specific version (e.g., `v0.9.x`) rather than `>=0.4.0` to prevent unexpected lint rule changes from breaking CI.

4. **Add `--strict-markers` enforcement**: Already present in `addopts`. Verify all custom markers are declared (they are -- 12 markers defined).

#### Medium-term (next quarter)

5. **Mypy Phase 5**: Enable `check_untyped_defs = true` globally. Add `disallow_untyped_defs = true` on `core/` modules one at a time. Target: all `core/` modules strictly typed by end of quarter.

6. **Coverage target 65%**: Add coverage enforcement for new code via `--cov-fail-under` in CI. Consider `diff-cover` for PR-level coverage enforcement.

7. **Add `bandit` to CI**: Static security analysis. Run with `ruff check --select S` (ruff includes bandit rules via the `S` rule set). This catches hardcoded passwords, `eval()` usage, and other security patterns.

8. **Adopt `pyright` as secondary type checker**: Pyright catches different issues than mypy, particularly around type narrowing and exhaustiveness checks. Run in CI as informational (non-blocking) initially.

#### Long-term (6 months)

9. **Dependency injection**: Replace the singleton + reset pattern with a lightweight DI container. `dependency-injector` or a custom `ServiceRegistry` class would reduce the conftest surface area from 30+ reset calls to a single registry reset.

10. **API documentation**: Generate API docs from docstrings using `mkdocstrings` or `sphinx-autodoc`. The docstrings are already high-quality -- they just need to be published.

11. **Property-based testing**: Add `hypothesis` for testing system name resolution, URL building, and market calculations. These are pure functions with well-defined domains that benefit from generative testing.

---

## Scoring Rubric

| Area | Score | Rationale |
|------|-------|-----------|
| **Code clarity** | 4/5 | Excellent docstrings, clear naming, well-commented. Deducted for 3,798-line dispatcher and barrel re-exports |
| **Type safety** | 3/5 | Gradual mypy adoption with clear roadmap, but 5 error codes disabled globally, `ignore_missing_imports = true`, many untyped functions unchecked |
| **Testability** | 4/5 | Excellent fixture infrastructure, multi-tier markers, 30+ singleton resets. Deducted for 59% coverage threshold and singleton-heavy architecture |
| **Reliability** | 3/5 | 276 broad exception catches, missing exception chaining, `__del__` for cleanup, manual URL construction. Dual retry (tenacity/fallback) is a strength |
| **Security hygiene** | 4/5 | Path validation, keyring integration, gitleaks, break-glass modes. Deducted for unencoded URL params and `ignore_missing_imports` on security libs |
| **Maintainability** | 4/5 | Clean architecture, good separation of concerns, comprehensive tooling. Deducted for sync/async duplication and singleton proliferation |

**Overall: 3.7/5** -- A well-architected codebase with strong data modeling and tooling, held back by exception handling patterns, type coverage gaps, and accumulated technical debt in the client layer. The gradual mypy roadmap and multi-tier test strategy show clear engineering intent; the primary risks are in the 276 broad catches and the duplicated client code.

---

## Delta from Previous Review (2026-01-23)

Key changes since the January review:

| Area | January | February | Trend |
|------|---------|----------|-------|
| Dispatchers | 6 | 8 (+killmails, pilot) | Improved |
| Coverage threshold | 60% | 59% | Slightly regressed (code removed) |
| Source lines | ~87K | ~121K | +40% growth |
| Test lines | ~85K | ~108K | +27% growth |
| mypy phase | 3 | 4 | Advancing |
| Singleton count | ~20 | ~30+ | Growing (needs addressing) |
| Version mismatch | Not noted | 1.0.0 vs 2.0.0 | New issue |

The codebase has grown significantly (+34K source lines, +23K test lines) since January, with new capabilities in killmail analysis, pilot data, sovereignty, and real-time intel. The architectural quality has been maintained through this growth, with the dispatcher pattern scaling well. The primary new concern is singleton proliferation keeping pace with feature growth.
