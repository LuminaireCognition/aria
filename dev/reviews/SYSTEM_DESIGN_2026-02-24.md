# System Design and Modularity Review
**Date:** 2026-02-24
**Prompt:** dev/prompts/architecture/system_design.md
**Reviewer:** Claude Opus 4.6

---

## Executive Summary

ARIA is a 490-file Python codebase organized under a single top-level package (`aria_esi`) with 10 subpackages. The architecture exhibits strong domain modeling and a well-considered layering strategy that cleanly separates CLI presentation, MCP server transport, business logic services, and data access. However, several structural debts have accumulated: circular dependencies between `core`, `mcp`, `fitting`, and `commands` packages; the `mcp` package has evolved into a hybrid that serves as both transport layer and shared data access layer; and singleton/global state management is inconsistent across modules.

Overall the system is healthy for its size and maturity. The findings below are ordered by severity, with 0 Critical, 3 High, 7 Medium, 4 Low, and 3 Informational findings.

---

## 1. Module Dependency Map

### Subpackage Inventory

| Subpackage | Role | Files |
|------------|------|-------|
| `core` | Shared infrastructure: HTTP client, auth, config, formatters, logging, security | 15 |
| `commands` | CLI command implementations (argparse handlers) | 30 |
| `mcp` | MCP server: dispatchers, tools, market DB, SDE queries, activity cache | ~80 |
| `services` | Business logic: navigation, loop planning, arbitrage, redisq, sovereignty | ~90 |
| `models` | Pydantic/dataclass response models for market, SDE, fitting | 5 |
| `fitting` | EFT parser, EOS bridge, skill registry, tank classifier | 7 |
| `universe` | Graph data structure, serialization, builder | 4 |
| `cache` | Legacy universe cache (JSON-based) | 2 |
| `persona` | Persona context compiler | 2 |
| `_vendor` | Vendored EOS library | ~200 |
| `data` | Static data files (universe graph, sovereignty YAML) | N/A |

### Dependency Graph (Intended Layers)

```
                    +-----------+
                    | commands  |  CLI presentation
                    +-----+-----+
                          |
                    +-----v-----+
                    |   mcp     |  MCP transport + dispatchers
                    +-----+-----+
                          |
                    +-----v-----+
                    | services  |  Business logic
                    +-----+-----+
                          |
          +------+--------+--------+------+
          |      |        |        |      |
      +---v--+  v     +--v---+ +--v--+ +-v------+
      | core | models | fit  | |cache| |universe|
      +------+        +------+ +-----+ +--------+
```

### Actual Dependency Violations (Circular)

```
core <-> commands          (freshness_adapters.py imports commands.sync_profile, commands.skills)
core <-> mcp               (client.py, constants.py import mcp.sde.queries)
fitting <-> commands       (skills.py imports commands.skills.load_cached_skills)
fitting <-> mcp            (eft_parser.py imports mcp.market.database; skill_registry.py imports mcp.sde.queries)
models <-> mcp             (market.py imports mcp.market.database)
services <-> mcp           (arbitrage_engine.py, history_cache.py, market_refresh.py import mcp.market.database_async)
```

---

## 2. Findings

### HIGH Severity

#### H1: `core` package depends on `mcp` and `commands` (layer inversion)

**File:** `src/aria_esi/core/client.py:L873`, `src/aria_esi/core/constants.py:L96`, `src/aria_esi/core/freshness_adapters.py:L29,L58`

**Finding:** The `core` package -- intended as the foundation layer with zero upward dependencies -- imports from both `mcp.sde.queries` and `commands.sync_profile`/`commands.skills`. These are deferred (inside-function) imports that avoid import-time cycles, but they still create a logical layer violation: the foundation depends on layers above it.

- `core/client.py` calls `mcp.sde.queries.get_sde_query_service()` for station name resolution
- `core/constants.py` calls `mcp.sde.queries.get_sde_query_service()` for ship group IDs
- `core/freshness_adapters.py` calls `commands.sync_profile.sync_profile()` and `commands.skills.cmd_sync_skills()`

**Impact:** Any change to MCP SDE queries or CLI command signatures can break the core package. This makes `core` fragile and harder to test in isolation. It also means `core` cannot be extracted as an independent library.

**Fix:**
1. Extract `get_sde_query_service().get_station_info()` and `get_all_ship_group_ids()` into a thin SDE abstraction in `core/` or a new `core/sde_facade.py` that provides a Protocol. Have the MCP SDE module register itself as the implementation at startup.
2. Move `freshness_adapters.py` out of `core/` into `services/` or a new `sync/` package. It is glue code between freshness checking and sync commands -- not core infrastructure.
3. For `constants.py`, inject the ship-group-ID resolver via a callback registration pattern rather than importing from `mcp`.

---

#### H2: `mcp` package is a hybrid transport-and-data-access layer

**File:** `src/aria_esi/mcp/market/database.py`, `src/aria_esi/mcp/market/database_async.py`, `src/aria_esi/mcp/sde/queries.py`

**Finding:** The `mcp` package contains both MCP server transport logic (dispatchers, tool registration, server lifecycle) *and* core data access logic (MarketDatabase, AsyncMarketDatabase, SDE query service). These database/query modules are imported by 6+ packages outside MCP: `core`, `models`, `fitting`, `services`, `commands`.

The `mcp.market.database` module alone is imported from:
- `core/client.py` (station lookup)
- `core/constants.py` (ship groups)
- `models/market.py` (region resolution)
- `fitting/eft_parser.py` (type resolution)
- `fitting/skill_registry.py` (SDE queries)
- `services/arbitrage_engine.py`, `services/history_cache.py`, `services/market_refresh.py` (market data)

**Impact:** The MCP package cannot be removed or replaced without breaking most of the application. The package name `mcp` implies "Model Context Protocol transport layer" but it actually serves as the shared data access layer. This confuses developers and creates artificial coupling.

**Fix:** Extract shared data-access components into a dedicated `data_access` or `db` subpackage:
- `mcp/market/database.py` -> `db/market.py`
- `mcp/market/database_async.py` -> `db/market_async.py`
- `mcp/sde/queries.py` -> `db/sde_queries.py`
- `mcp/market/schema.py` -> `db/market_schema.py`

This would let `mcp/` remain a pure transport layer while `db/` becomes the shared data access layer that all packages can import cleanly.

---

#### H3: Inconsistent singleton and global state management

**File:** Multiple locations (see details below)

**Finding:** The codebase uses four different patterns for singleton/global state:

| Pattern | Example | Count |
|---------|---------|-------|
| `@lru_cache(maxsize=1)` | `core/config.py:get_settings()` | 2 |
| Class-level `_instance` with `get_instance()` | `mcp/policy.py:PolicyEngine`, `fitting/eos_bridge.py:EOSBridge` | 2 |
| Module-level `global _var` with getter | `mcp/market/database.py:get_market_database()`, `mcp/tools.py:get_universe()`, `mcp/esi_client.py` | ~12 |
| Module-level mutable global without getter | `cache/__init__.py:_cache` | 2 |

Key locations:
- `src/aria_esi/mcp/market/database.py:L2334-2355` -- global with defensive `"_market_db" not in globals()` check
- `src/aria_esi/mcp/activity.py:L284-292` -- global `_activity_cache`
- `src/aria_esi/mcp/esi_client.py:L49-199` -- two globals (`_client`, `_auth_client`) with different lifecycle patterns
- `src/aria_esi/fitting/skill_registry.py:L156-195` -- global with `_registry_attempted` flag
- `src/aria_esi/core/constants.py:L89-113` -- global with threading lock

**Impact:** Inconsistent lifecycle management makes it hard to reason about initialization order, test isolation (which `reset_*` function to call?), and thread safety. The `get_market_database()` function's `"_market_db" not in globals()` pattern is a code smell suggesting the variable declaration order matters.

**Fix:**
1. Standardize on one pattern. Recommended: `@lru_cache(maxsize=1)` for simple singletons, class-level `_instance` with lock for thread-safe singletons.
2. Create a `core/registry.py` or `core/container.py` that acts as a lightweight service locator. Register singletons there with `register()` and `get()`, with a single `reset_all()` for test teardown.
3. At minimum, audit all `global` declarations and ensure each has a corresponding `reset_*` function for testing.

---

### MEDIUM Severity

#### M1: Duplicate exception hierarchies at service and MCP layers

**File:** `src/aria_esi/services/navigation/errors.py`, `src/aria_esi/mcp/errors.py`, `src/aria_esi/services/loop_planning/errors.py`

**Finding:** There are parallel exception hierarchies:

| Service Layer | MCP Layer |
|---------------|-----------|
| `services.navigation.errors.RouteNotFoundError` | `mcp.errors.RouteNotFoundError` |
| `services.navigation.errors.SystemNotFoundError` | `mcp.errors.SystemNotFoundError` |
| `services.loop_planning.errors.InsufficientBordersError` | `mcp.errors.InsufficientBordersError` |

The MCP `InsufficientBordersError` uses multiple inheritance from both `UniverseError` and the service error (line 96), which works but is fragile. The `RouteNotFoundError` and `SystemNotFoundError` have near-identical structures duplicated across layers.

**Impact:** Two independent exception types with the same name and purpose in different packages create confusion. Catching the wrong one silently swallows errors. The MRO of the diamond-inheriting `InsufficientBordersError` is delicate.

**Fix:** Define canonical exceptions in the service layer. Have the MCP layer either:
- Re-export them (simplest), or
- Catch service exceptions and wrap them in MCP-specific responses at the dispatcher boundary (cleanest separation)

The current diamond inheritance pattern in `InsufficientBordersError` should be replaced with catch-and-wrap.

---

#### M2: `commands/__init__.py` eagerly imports all command modules

**File:** `src/aria_esi/commands/__init__.py:L22-43`

**Finding:** The commands `__init__.py` imports all 20+ command modules at package import time. This means importing `aria_esi.commands` triggers imports of every command's dependencies.

**Impact:** Increased startup time for any code path that touches `commands`. Since `core.freshness_adapters` imports from `commands`, this chain can pull in a large dependency tree even for simple operations. The `__main__.py` already does lazy per-phase imports in `build_parser()`, but those are redundant because `__init__.py` already imported everything.

**Fix:** Remove the eager imports from `commands/__init__.py`. Keep only the `__all__` list. The `__main__.py` already handles lazy imports in `build_parser()`. Alternatively, use `__getattr__` lazy loading as `services/__init__.py` does.

---

#### M3: ESI response types duplicated between sync and async clients

**File:** `src/aria_esi/core/client.py:L31-60`, `src/aria_esi/core/async_client.py:L38-60`

**Finding:** `ESIResponse` and `AsyncESIResponse` are near-identical dataclasses with the same fields (`data`, `headers`, `status_code`) and the same `last_modified_timestamp` property. They are defined independently in separate files.

**Impact:** Any fix to response handling (e.g., header normalization) must be applied in two places. The two types are not interchangeable despite having the same structure, so code that works with "an ESI response" must know which client produced it.

**Fix:** Define a single `ESIResponse` dataclass (or Protocol) in `core/models.py` and use it from both clients. The async client can return the same type since the response itself isn't async.

---

#### M4: The `cache` module is a legacy parallel to `universe` + `mcp`

**File:** `src/aria_esi/cache/__init__.py`

**Finding:** The `cache` module provides JSON-backed universe queries (`get_system`, `get_system_by_name`, `find_border_systems_in_region`) using a `universe_cache.json` file. This duplicates functionality provided by `universe.UniverseGraph` (which uses igraph + msgpack for O(1) lookups) and the MCP tools.

The `cache` module uses BFS on a JSON dict (O(V+E) per query) vs igraph's C-speed pathfinding. The `data/universe_cache.json` file is 14+ MB of redundant data alongside the 3MB `universe.universe` binary graph.

**Impact:** Two parallel ways to query universe data with different performance characteristics. New code may accidentally use the slower path. The JSON cache file bloats the repository.

**Fix:** Audit callers of `cache/__init__.py`. If all can use `UniverseGraph` instead, deprecate the cache module and remove `universe_cache.json` from the data directory. If the cache module serves a different use case (e.g., offline/no-igraph environments), document it explicitly.

---

#### M5: `services/__init__.py` lazy-import `__getattr__` is fragile

**File:** `src/aria_esi/services/__init__.py:L33-81`, `src/aria_esi/services/navigation/__init__.py:L51-102`, `src/aria_esi/services/sovereignty/__init__.py:L39-87`

**Finding:** Three `__init__.py` files use `__getattr__` with long `if/elif` chains for lazy importing. The `services/navigation/__init__.py` chains 20+ names through `__getattr__`. These chains must be manually kept in sync with `__all__` lists and actual module contents.

**Impact:** Missing a name in the chain causes `AttributeError` at runtime instead of `ImportError` at import time. IDE autocompletion and type checking are degraded. Adding a new export requires touching both `__getattr__` and `__all__`.

**Fix:** Use `importlib` with a lookup dict pattern:
```python
_LAZY_IMPORTS = {
    "NavigationService": (".router", "NavigationService"),
    "RouteMode": (".router", "RouteMode"),
    ...
}

def __getattr__(name):
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(module_path, __name__)
        return getattr(mod, attr)
    raise AttributeError(...)
```

This is more maintainable and makes the mapping explicit.

---

#### M6: No common base exception for the entire ARIA package

**File:** Various error modules across the codebase

**Finding:** The codebase has multiple independent exception hierarchies with no common root:

| Base Exception | Package |
|----------------|---------|
| `ESIError` | `core/client.py` |
| `CredentialsError` | `core/auth.py` |
| `IntegrityError` | `core/data_integrity.py` |
| `PathValidationError` | `core/path_security.py` |
| `UniverseError` | `mcp/errors.py` |
| `NavigationError` | `services/navigation/errors.py` |
| `LoopPlanningError` | `services/loop_planning/errors.py` |
| `EOSBridgeError` | `fitting/eos_bridge.py` |
| `EFTParseError` | `fitting/eft_parser.py` |
| `SDENotSeededError` | `mcp/sde/queries.py` |
| `PolicyError` | `mcp/policy.py` |

**Impact:** There is no way to catch "any ARIA error" at an application boundary. The `__main__.py` catches bare `Exception` as a result (line 598). Libraries that embed ARIA cannot distinguish ARIA errors from standard library errors.

**Fix:** Define `class AriaError(Exception)` in `core/exceptions.py` and have all domain exceptions inherit from it. This enables `except AriaError` at application boundaries while preserving specific catch patterns.

---

#### M7: Mixed use of Pydantic and dataclass models

**File:** `src/aria_esi/mcp/models.py` (Pydantic), `src/aria_esi/models/fitting.py`, `src/aria_esi/services/killmail_store/protocol.py` (dataclass)

**Finding:** The codebase uses both Pydantic `BaseModel` (via `MCPModel`, `MarketModel`, `SDEModel`) and stdlib `@dataclass` for data structures serving similar purposes. The split appears to be:
- Pydantic: MCP response models, market/SDE models (serialization-heavy)
- Dataclass: Internal service types, protocol data classes, fitting models

This is a reasonable split, but there is no documented policy on when to use which.

**Impact:** Contributors may choose inconsistently. Some fitting models that cross the MCP boundary (e.g., `FitStatsResult`) are dataclasses that get serialized to JSON via `asdict()` rather than Pydantic's `.model_dump()`, losing validation benefits.

**Fix:** Document the policy: "Pydantic for API boundary models (MCP responses, CLI output). Dataclass for internal service types and protocol contracts." Consider migrating `FitStatsResult` and related types to Pydantic since they are MCP response types.

---

### LOW Severity

#### L1: `fitting` package depends on both `commands` and `mcp` for data

**File:** `src/aria_esi/fitting/skills.py:L146`, `src/aria_esi/fitting/eft_parser.py:L47,L424`, `src/aria_esi/fitting/skill_registry.py:L169`

**Finding:** The fitting package imports from three different layers:
- `commands.skills.load_cached_skills` for skill cache
- `mcp.market.database.MarketDatabase` for type resolution
- `mcp.sde.queries` for skill registry population

**Impact:** The fitting package cannot be used without both the CLI commands layer and the MCP data layer being available, even though fitting is a computation library.

**Fix:** Fitting should accept its dependencies via constructor injection or function parameters. For example, `fetch_pilot_skills()` should accept a `SkillSource` protocol rather than importing a specific command module. The type resolver in `eft_parser.py` already accepts `MarketDatabase | None` as a parameter -- extend this pattern consistently.

---

#### L2: Test files exist inside src/ package

**File:** `src/aria_esi/mcp/market/tests/`

**Finding:** There is a `tests/` directory inside the `src/aria_esi/mcp/market/` package. While the coverage config excludes `*/tests/*`, these files are included in the wheel distribution.

**Impact:** Test code ships to production. Test fixtures may contain mock data that inflates package size.

**Fix:** Move `src/aria_esi/mcp/market/tests/` to `tests/mcp/market/` to match the project-level test directory structure. Update any relative import paths in the test files.

---

#### L3: `__main__.py` uses phased comments that don't match current architecture

**File:** `src/aria_esi/__main__.py:L427-551`

**Finding:** The `build_parser()` function registers commands in blocks labeled "Phase 2" through "Phase 27", a legacy from incremental development. These phase numbers are now meaningless -- there is no Phase 19, and Phases 23+ coexist with Phase 2.

**Impact:** The comments create a false impression of a staged rollout that no longer exists. New contributors may wonder what phase they're in.

**Fix:** Replace phase comments with logical groupings: "# Navigation Commands", "# Market Commands", "# Authentication-Required Commands", etc. This matches the help text structure.

---

#### L4: Market database singleton declares variable after getter function

**File:** `src/aria_esi/mcp/market/database.py:L2334-2355`

**Finding:** The `_market_db` variable is declared on line 2355 *after* the `get_market_database()` function on line 2334 that references it. The getter uses `"_market_db" not in globals()` as a guard, suggesting this ordering has caused bugs before.

**Impact:** Confusing code that's easy to break. The `globals()` check is non-idiomatic Python.

**Fix:** Move `_market_db: MarketDatabase | None = None` above the getter function. Replace the `globals()` check with `if _market_db is None:`, which is the standard pattern used everywhere else.

---

### INFORMATIONAL

#### I1: Well-designed protocol usage in `interest_v2` subsystem

**File:** `src/aria_esi/services/redisq/interest_v2/providers/base.py`

**Finding:** The interest engine v2 subsystem demonstrates exemplary interface design with:
- `Protocol` classes for compile-time checking (`SignalProvider`, `RuleProvider`, `ScalingProvider`, `DeliveryProvider`)
- `ABC` base classes with shared logic (`BaseSignalProvider`, etc.)
- Clean provider registration via `ProviderRegistry`
- Separation of interface (Protocol) from partial implementation (ABC)

This is the gold standard in the codebase for extensibility design.

---

#### I2: Configuration management is well-centralized

**File:** `src/aria_esi/core/config.py`

**Finding:** The `AriaSettings` class using `pydantic-settings` provides:
- Single source of truth for all environment variables
- Type-safe validation at startup
- `.env` file discovery with project root detection
- Computed properties for derived values
- Break-glass flags for security overrides
- Singleton access via `get_settings()` with `reset_settings()` for testing

This is clean, well-documented configuration management.

---

#### I3: Context policy and output budget system is thoughtfully designed

**File:** `src/aria_esi/mcp/context_policy.py`, `src/aria_esi/mcp/context_budget.py`, `src/aria_esi/mcp/policy.py`

**Finding:** The MCP layer has a three-part policy system:
1. **Context policy** (`context_policy.py`): Frozen dataclasses defining per-domain output limits
2. **Context budget** (`context_budget.py`): Token-aware output truncation
3. **Capability policy** (`policy.py`): Sensitivity-based access control with audit logging

This provides defense-in-depth at the MCP boundary, limiting both data volume and access scope.

---

## 3. Interface Contract Assessment

### Explicit Interfaces

| Interface | Type | Quality |
|-----------|------|---------|
| `KillmailStore` | Protocol (runtime_checkable) | Excellent -- comprehensive, well-documented |
| `LLMProvider` | Protocol | Good -- minimal, focused |
| `SignalProvider` / `RuleProvider` / `ScalingProvider` / `DeliveryProvider` | Protocol + ABC | Excellent -- dual-layer design |
| `Provider` (base) | Protocol | Good -- name/validate contract |

### Implicit Interfaces

| Interface | Issue |
|-----------|-------|
| Market database access | No Protocol -- `MarketDatabase` is imported directly as a concrete class |
| SDE query access | No Protocol -- `get_sde_query_service()` returns concrete `SDEQueryService` |
| Universe graph access | No Protocol -- `UniverseGraph` is a concrete dataclass |
| Command handler registration | Convention-based -- `register_parsers(subparsers)` function signature by convention |
| MCP tool registration | Convention-based -- `register_*_tools(server, universe)` function signature |

### Assessment

The codebase uses explicit protocols in its newest and most complex subsystem (killmail store, interest engine) but relies on implicit conventions in older code (market database, SDE queries, CLI commands). The command registration pattern (`register_parsers`) is consistent but could benefit from a Protocol definition.

---

## 4. Configuration Management Assessment

### Strengths

- **Centralized settings**: `core/config.py` with `AriaSettings(BaseSettings)` is the single source
- **Environment variable naming**: Consistent `ARIA_` prefix
- **Validation**: Pydantic handles type coercion and validation
- **Break-glass controls**: `allow_unsafe_paths`, `allow_unpinned`, `mcp_bypass_policy`
- **Data path management**: All paths derived from `instance_root` property

### Weaknesses

- **Scattered constants**: `ACTIVITY_CACHE_TTL = 600` defined in `commands/navigation.py` and separately in `mcp/activity.py`. These could diverge.
- **Schema versions**: `SCHEMA_VERSION = 9` in `mcp/market/database.py` is not part of the centralized config
- **No environment validation at startup**: Settings are validated on first access (lazy), not at process start. An invalid `ARIA_UNIVERSE_GRAPH` path won't fail until the MCP server tries to load the graph.

---

## 5. Actionable Recommendations (Ranked by Priority)

### Priority 1: Eliminate `core` upward dependencies (H1)

**Effort:** Medium | **Impact:** High

1. Move `freshness_adapters.py` from `core/` to `services/freshness/`
2. Create `core/sde_facade.py` with a Protocol and callback-registration for SDE lookups
3. Remove all `core -> mcp` and `core -> commands` imports

This unblocks `core` as a true foundation layer.

### Priority 2: Extract shared data access from `mcp` (H2)

**Effort:** High | **Impact:** High

1. Create `src/aria_esi/db/` package
2. Move `mcp/market/database.py`, `database_async.py`, `schema.py` to `db/market/`
3. Move `mcp/sde/queries.py`, `schema.py` to `db/sde/`
4. Update all import paths (approximately 20 files)
5. Keep `mcp/market/tools_*.py` and `mcp/sde/tools_*.py` in `mcp/` as pure tool handlers

### Priority 3: Standardize singleton pattern (H3)

**Effort:** Low | **Impact:** Medium

1. Choose `@lru_cache(maxsize=1)` as the standard for simple singletons
2. Use class-level `_instance` with `threading.Lock` for singletons needing lifecycle management
3. Ensure every singleton has a `reset_*()` function
4. Fix the `get_market_database()` variable ordering (L4)

### Priority 4: Define `AriaError` base exception (M6)

**Effort:** Low | **Impact:** Medium

1. Create `core/exceptions.py` with `class AriaError(Exception)`
2. Have all domain exception bases inherit from it
3. Replace bare `Exception` catches in `__main__.py` with `AriaError`

### Priority 5: Consolidate exception hierarchies (M1)

**Effort:** Low | **Impact:** Medium

1. Use service-layer exceptions as canonical
2. Replace diamond inheritance in `mcp.errors.InsufficientBordersError` with catch-and-wrap at the dispatcher boundary
3. Remove duplicate `RouteNotFoundError` and `SystemNotFoundError` from `mcp.errors`

### Priority 6: Lazy-load commands `__init__.py` (M2)

**Effort:** Low | **Impact:** Low

Replace eager imports in `commands/__init__.py` with `__getattr__` lazy loading (or remove imports entirely since `__main__.py` already handles them).

### Priority 7: Unify ESI response types (M3)

**Effort:** Low | **Impact:** Low

Define `ESIResponse` once in `core/models.py` and use it from both sync and async clients.

### Priority 8: Deprecate legacy cache module (M4)

**Effort:** Medium | **Impact:** Low

Audit `cache/__init__.py` callers. If all can use `UniverseGraph`, deprecate the module and remove the 14MB JSON file.

---

## Appendix A: Files Examined

Key files reviewed in this analysis:

- `src/aria_esi/__init__.py` -- Package root and re-exports
- `src/aria_esi/__main__.py` -- CLI entry point and command registration
- `src/aria_esi/core/__init__.py` -- Core re-exports (219 lines)
- `src/aria_esi/core/config.py` -- Centralized configuration
- `src/aria_esi/core/client.py` -- Sync ESI client
- `src/aria_esi/core/async_client.py` -- Async ESI client
- `src/aria_esi/core/auth.py` -- Authentication and credentials
- `src/aria_esi/core/constants.py` -- Shared constants with SDE fallback
- `src/aria_esi/core/freshness.py` -- Freshness-gated auto-sync
- `src/aria_esi/core/freshness_adapters.py` -- Adapter glue (layer violation)
- `src/aria_esi/commands/__init__.py` -- Eager command imports
- `src/aria_esi/commands/navigation.py` -- CLI navigation commands
- `src/aria_esi/mcp/__init__.py` -- MCP package exports
- `src/aria_esi/mcp/server.py` -- MCP server lifecycle
- `src/aria_esi/mcp/errors.py` -- MCP exception hierarchy
- `src/aria_esi/mcp/models.py` -- MCP response models
- `src/aria_esi/mcp/policy.py` -- Capability policy engine
- `src/aria_esi/mcp/context_policy.py` -- Context budget limits
- `src/aria_esi/mcp/dispatchers/__init__.py` -- Dispatcher registration
- `src/aria_esi/mcp/dispatchers/universe.py` -- Universe dispatcher
- `src/aria_esi/mcp/market/database.py` -- Market SQLite database
- `src/aria_esi/mcp/market/database_async.py` -- Async market database
- `src/aria_esi/mcp/sde/queries.py` -- SDE query service
- `src/aria_esi/mcp/fitting/tools.py` -- Fitting tool registration
- `src/aria_esi/models/__init__.py` -- Model re-exports
- `src/aria_esi/models/config_types.py` -- TypedDict definitions
- `src/aria_esi/models/market.py` -- Market Pydantic models
- `src/aria_esi/services/__init__.py` -- Lazy service exports
- `src/aria_esi/services/navigation/__init__.py` -- Navigation service lazy exports
- `src/aria_esi/services/navigation/errors.py` -- Navigation exceptions
- `src/aria_esi/services/loop_planning/errors.py` -- Loop planning exceptions
- `src/aria_esi/services/sovereignty/__init__.py` -- Sovereignty lazy exports
- `src/aria_esi/services/killmail_store/protocol.py` -- KillmailStore protocol
- `src/aria_esi/services/redisq/interest_v2/providers/base.py` -- Provider protocols
- `src/aria_esi/services/redisq/notifications/llm_providers/_protocol.py` -- LLM protocol
- `src/aria_esi/fitting/eos_bridge.py` -- EOS integration
- `src/aria_esi/fitting/eft_parser.py` -- EFT format parser
- `src/aria_esi/fitting/skills.py` -- Skill fetching for fitting
- `src/aria_esi/fitting/skill_registry.py` -- Skill registry
- `src/aria_esi/universe/__init__.py` -- Universe package exports
- `src/aria_esi/universe/graph.py` -- UniverseGraph data structure
- `src/aria_esi/cache/__init__.py` -- Legacy JSON cache
- `src/aria_esi/persona/__init__.py` -- Persona compiler
- `pyproject.toml` -- Project configuration and tooling
