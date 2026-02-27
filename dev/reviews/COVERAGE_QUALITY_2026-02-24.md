# Test Coverage Adequacy Review
**Date:** 2026-02-24
**Prompt:** dev/prompts/testing/coverage_quality.md
**Reviewer:** Claude Opus 4.6

---

## Executive Summary

The ARIA codebase reports **60.33% total line+branch coverage** against a **59% fail_under threshold**, leaving only 1.33 percentage points of headroom. The test suite is large (6,271 passing tests) and well-structured, but coverage is unevenly distributed: the MCP dispatcher/tools layer, services layer (interest_v2, navigation, loop_planning), and fitting modules are well-tested (85-100%), while the CLI commands layer, several MCP market tools, the SDE importer, and the ESI client/auth stack have significant gaps (0-35%). Branch coverage is enabled but no separate branch threshold is enforced. The CI pipeline runs coverage on every push/PR across three Python versions but does not upload coverage to any external tracking service, making trend analysis impossible.

**Key numbers:**
- 6,271 tests passing, 17 skipped, 34 deselected
- Total: 41,140 statements, 14,937 missed, 13,286 branches, 1,280 branch misses
- 60.33% combined coverage (includes vendored EOS code which drags down the number)
- Threshold: 59% (lowered from 60 after archetype framework removal)

---

## 1. Coverage Inventory

### 1a. Well-Tested Modules (>= 90% coverage)

| Module | Coverage | Notes |
|--------|----------|-------|
| `core/formatters.py` | 100% | |
| `core/path_security.py` | 95% | Security-critical, good |
| `core/logging.py` | 96% | |
| `fitting/tank_classifier.py` | 99% | |
| `fitting/eos_data.py` | 97% | |
| `mcp/models.py` | 100% | |
| `mcp/errors.py` | 100% | |
| `mcp/validation.py` | 100% | |
| `mcp/context_budget.py` | 100% | |
| `mcp/context_policy.py` | 100% | |
| `mcp/tools.py` | 99% | |
| `mcp/sde/tools_item.py` | 94% | |
| `mcp/sde/tools_activities.py` | 90% | |
| `mcp/sde/tools_agents.py` | 85% | |
| `mcp/market/clients.py` | 95% | |
| `mcp/market/tools_history.py` | 93% | |
| `mcp/dispatchers/universe.py` | 86% | 1,442 stmts, very large |
| `models/market.py` | 99% | |
| `models/fitting.py` | 100% | |
| `models/sde.py` | 100% | |
| `services/navigation/*` | 90-100% | All modules |
| `services/loop_planning/*` | 93-100% | All modules |
| `services/arbitrage_fees.py` | 100% | |
| `services/arbitrage_freshness.py` | 100% | |
| `services/character_industry.py` | 100% | |
| `services/hauling_score.py` | 98% | |
| `services/industry_costs.py` | 97% | |
| `services/reactions.py` | 96% | |
| `services/sovereignty/coalition_service.py` | 96% | |
| `services/sovereignty/database.py` | 95% | |
| `services/redisq/interest_v2/` (most) | 86-100% | Well-tested subsystem |
| `services/redisq/notifications/` (most) | 77-100% | Good subsystem coverage |
| `universe/graph.py` | 100% | |
| `universe/serialization.py` | 97% | |
| `persona/compiler.py` | 92% | |
| `cache/__init__.py` | 98% | |

### 1b. Moderately Tested Modules (50-89%)

| Module | Coverage | Notes |
|--------|----------|-------|
| `core/auth.py` | 59% | Security-critical, mypy-strict |
| `core/client.py` | 64% | Core HTTP client |
| `core/keyring_backend.py` | 59% | Security-critical |
| `core/retry.py` | 75% | |
| `core/async_client.py` | 78% | |
| `core/data_integrity.py` | 72% | |
| `core/freshness.py` | 86% | |
| `fitting/eos_bridge.py` | 85% | |
| `fitting/skills.py` | 75% | |
| `fitting/eft_parser.py` | 81% | |
| `fitting/skill_registry.py` | 83% | |
| `mcp/context.py` | 82% | |
| `mcp/policy.py` | 86% | |
| `mcp/esi_client.py` | 44% | |
| `mcp/server.py` | 57% | |
| `mcp/sde/queries.py` | 77% | |
| `mcp/sde/tools_easy80.py` | 59% | |
| `mcp/sde/tools_minmax.py` | 59% | |
| `mcp/market/database.py` | 57% | |
| `mcp/market/clipboard.py` | 86% | |
| `mcp/market/cache.py` | 37% | |
| `mcp/dispatchers/status.py` | 61% | |
| `mcp/dispatchers/sde.py` | 44% | |
| `mcp/dispatchers/skills.py` | 41% | |
| `mcp/dispatchers/killmails.py` | 33% | |
| `mcp/dispatchers/market.py` | 31% | |
| `mcp/dispatchers/fitting.py` | 27% | |
| `services/planet_cache.py` | 68% | |
| `services/asset_insights.py` | 88% | |
| `services/asset_snapshots.py` | 90% | |
| `services/industry_chains.py` | 83% | |
| `services/history_cache.py` | 93% | |
| `services/redisq/database.py` | 88% | |
| `services/redisq/entity_filter.py` | 86% | |
| `services/redisq/entity_watchlist.py` | 54% | |
| `services/redisq/poller.py` | 81% | |
| `services/redisq/topology.py` | 79% | |
| `services/redisq/war_context.py` | 64% | |
| `services/redisq/notifications/manager.py` | 81% | |
| `services/redisq/notifications/worker.py` | 82% | |
| `services/redisq/notifications/supervisor.py` | 74% | |
| `services/redisq/notifications/persona.py` | 77% | |
| `commands/character.py` | 92% | |
| `commands/orders.py` | 82% | |
| `commands/mail.py` | 84% | |
| `commands/agents_research.py` | 86% | |
| `commands/loyalty.py` | 74% | |
| `commands/assets.py` | 71% | |
| `commands/corporation.py` | 71% | |
| `commands/mining.py` | 78% | |
| `commands/wallet.py` | 78% | |
| `commands/industry.py` | 74% | |
| `commands/clones.py` | 74% | |
| `commands/contracts.py` | 79% | |
| `commands/persona.py` | 63% | |
| `commands/sde.py` | 63% | |
| `commands/navigation.py` | 65% | |
| `commands/notifications.py` | 55% | |
| `commands/skills.py` | 56% | |
| `commands/pilot.py` | 52% | |
| `universe/builder.py` | 87% | |

### 1c. Poorly Tested or Untested Modules (< 50% or 0%)

| Module | Coverage | Stmts | Notes |
|--------|----------|-------|-------|
| `cache/builder.py` | **0%** | 81 | Universe cache builder |
| `core/freshness_adapters.py` | **0%** | 33 | Freshness sync bridges |
| `models/config_types.py` | **0%** | 69 | TypedDict definitions |
| `mcp/fitting/__init__.py` | **0%** | 2 | Import only |
| `mcp/fitting/tools.py` | **0%** | 7 | Fitting tool registration |
| `mcp/fitting/tools_stats.py` | **0%** | 49 | Fitting stats calculator |
| `mcp/fitting/tools_status.py` | **0%** | 15 | Fitting status tool |
| `mcp/market/schema.py` | **0%** | 6 | Market schema |
| `mcp/market/scope_refresh.py` | **0%** | 259 | Scope refresh logic |
| `mcp/market/tools.py` | 12% | 25 | Market tool registration |
| `mcp/market/tools_analysis.py` | **0%** | 72 | Market analysis tool |
| `mcp/market/tools_arbitrage.py` | 17% | 171 | Arbitrage tool |
| `mcp/market/tools_management.py` | **0%** | 327 | Management tools |
| `mcp/market/tools_nearby.py` | 30% | 236 | Nearby market finder |
| `mcp/market/tools_npc.py` | **0%** | 201 | NPC source finder |
| `mcp/market/tools_orders.py` | **0%** | 64 | Orders tool |
| `mcp/market/tools_prices.py` | **0%** | 57 | Prices tool |
| `mcp/market/tools_route.py` | **0%** | 136 | Route value tool |
| `mcp/market/tools_scope_refresh.py` | **0%** | 15 | Scope refresh tool |
| `mcp/market/tools_valuation.py` | **0%** | 81 | Valuation tool |
| `mcp/market/database_async.py` | 14% | 369 | Async database layer |
| `mcp/sde/importer.py` | 11% | 867 | SDE importer (large) |
| `mcp/sde/tools.py` | **0%** | 19 | SDE tool registration |
| `mcp/sde/tools_blueprint.py` | **0%** | 99 | Blueprint info tool |
| `mcp/sde/tools_corporation.py` | **0%** | 76 | Corporation info tool |
| `mcp/sde/tools_skills.py` | 34% | 110 | Skills tree tool |
| `mcp/dispatchers/pilot.py` | 8% | 161 | Pilot dispatcher |
| `commands/market.py` | 12% | 229 | Market CLI commands |
| `commands/redisq.py` | 19% | 458 | RedisQ CLI commands |
| `commands/pi.py` | 9% | 251 | PI CLI commands |
| `commands/fitting.py` | 35% | 259 | Fitting CLI commands |
| `commands/fittings.py` | 7% | 152 | Fittings CLI commands |
| `commands/killmail.py` | 8% | 170 | Killmail CLI (single) |
| `commands/killmails.py` | 28% | 351 | Killmails CLI (bulk) |
| `commands/universe.py` | 26% | 793 | Universe CLI commands |
| `commands/sovereignty.py` | 32% | 303 | Sovereignty CLI commands |
| `commands/validation.py` | 9% | 148 | Validation CLI commands |
| `commands/sync_profile.py` | 10% | 183 | Profile sync CLI |
| `services/arbitrage_engine.py` | 40% | 258 | Arbitrage calculations |
| `services/market_refresh.py` | 33% | 270 | Market refresh service |
| `services/redisq/__init__.py` | 9% | 22 | RedisQ entrypoint |
| `services/redisq/backfill.py` | **0%** | 111 | Gap recovery from zKillboard |
| `services/redisq/fetch_queue.py` | 30% | 131 | Async fetch queue |
| `services/sovereignty/__init__.py` | 62% | 29 | Sovereignty init |

---

## 2. Coverage Gap Findings

### Finding 1: MCP Market Tools Entirely Untested

**Severity:** Critical
**File:** `src/aria_esi/mcp/market/tools_orders.py`, `tools_prices.py`, `tools_valuation.py`, `tools_route.py`, `tools_npc.py`, `tools_management.py`, `tools_analysis.py`, `tools_scope_refresh.py` (all 0%)
**Finding:** Eight MCP market tool modules totaling ~955 statements have zero test coverage. These are the actual implementations invoked by the market dispatcher.
**Impact:** Market operations are among the most-used MCP actions (prices, orders, valuation). Zero coverage means any regression in these critical paths would go undetected. The dispatcher layer (`dispatchers/market.py` at 31%) has some coverage through action routing tests, but the tool implementation functions themselves are entirely untested.
**Fix:** Create `tests/mcp/market/test_tools_prices.py`, `test_tools_npc.py`, `test_tools_management.py`, `test_tools_route.py`, and `test_tools_analysis.py`. Focus on testing happy paths with mocked SDE/database backends, error responses for missing items, and edge cases (empty order books, unknown regions). Target 80%+ coverage for each.

### Finding 2: Security-Critical Auth Module at 59% Coverage

**Severity:** Critical
**File:** `src/aria_esi/core/auth.py:L244-L826`
**Finding:** The auth module handles credential resolution, token management, OAuth refresh, and file-permission enforcement. It has 351 statements with 128 uncovered (59% coverage). The uncovered lines include token refresh logic (L501-L532), OAuth exchange (L574-L599), and keyring integration paths (L727-L779).
**Impact:** Auth is a security-critical module (annotated with strict mypy in `pyproject.toml`). Untested OAuth token refresh and credential storage paths could harbor bugs leading to authentication failures or, worse, credential exposure. The pyproject.toml comment even acknowledges this: "Core modules (auth, client, retry) have 49-73% coverage."
**Fix:** Add tests for:
- Token refresh flow (mock httpx responses for success/expired/network error)
- Keyring-based credential load/store (mock `keyring_backend` functions)
- File permission validation (create temp files with various modes)
- OAuth callback handling
- Edge case: expired refresh token, revoked token

### Finding 3: SDE Importer at 11% Coverage with 867 Statements

**Severity:** High
**File:** `src/aria_esi/mcp/sde/importer.py:L196-L1877`
**Finding:** The SDE importer is the largest non-vendor module in the codebase (867 statements) and handles downloading and parsing the EVE static data export into the local database. Only 11% of it is covered.
**Impact:** The SDE importer runs infrequently (after game patches), but when it fails, it breaks all SDE-dependent features (item lookup, skill requirements, blueprints, agents). Bugs in the import logic could silently corrupt the database with missing or malformed data.
**Fix:** Create `tests/mcp/sde/test_importer.py` with:
- Unit tests for individual table import functions using mock YAML data
- Integration test verifying a small subset imports correctly into an in-memory SQLite database
- Error handling tests for malformed SDE data
- Target 50%+ coverage on the most critical parsing functions

### Finding 4: Core HTTP Client at 64% Coverage

**Severity:** High
**File:** `src/aria_esi/core/client.py:L360-L922`
**Finding:** The ESI HTTP client has 329 statements with 109 uncovered (64% coverage). Untested areas include error handling for rate limits (L360-L390), paginated response handling (L489-L511), and response header parsing (L872-L922).
**Impact:** As the foundational HTTP layer, bugs here cascade to every ESI-backed feature. Rate-limit handling, pagination, and error classification are the most operationally important paths.
**Fix:** Add tests using `pytest-httpx` for:
- Rate-limited responses (429 status, `Retry-After` header)
- Paginated responses (multiple pages with `X-Pages` header)
- Network errors and timeout handling
- Conditional request headers (`If-None-Match`, 304 responses)

### Finding 5: MCP Fitting Tools Module Cluster at 0%

**Severity:** High
**File:** `src/aria_esi/mcp/fitting/tools.py` (0%), `tools_stats.py` (0%), `tools_status.py` (0%)
**Finding:** The entire MCP fitting tools layer is untested. The fitting dispatcher (`dispatchers/fitting.py`) is at 27%. Tests exist for the underlying fitting engine (`tests/fitting/`) at 75-99%, but the MCP tool wrappers that translate between MCP protocol and fitting engine are not tested.
**Impact:** The fitting MCP tools are a primary user-facing feature. The tool wrappers handle input validation, result formatting, and error translation -- all of which could fail independently of the fitting engine.
**Fix:** Create `tests/mcp/fitting/test_tools_stats.py` testing:
- EFT parsing through the MCP interface
- Stats calculation result formatting
- Error handling for invalid EFT input
- The `calculate_stats`, `check_requirements`, `extract_requirements` action routing

### Finding 6: CLI Command Layer Systematically Under-Tested

**Severity:** High
**File:** Multiple files in `src/aria_esi/commands/` (see inventory above)
**Finding:** 18 out of 32 command modules are below 50% coverage. Several are under 15%: `pi.py` (9%), `fittings.py` (7%), `killmail.py` (8%), `validation.py` (9%), `sync_profile.py` (10%), `market.py` (12%), `redisq.py` (19%). This represents approximately 4,200 untested statements.
**Impact:** The CLI is the fallback interface when MCP is unavailable and also serves as the operational management layer (sync, validation, redisq control). Low coverage means operational commands could silently break.
**Fix:** Prioritize by usage frequency and criticality:
1. `commands/market.py` - price lookups via CLI (users depend on this)
2. `commands/redisq.py` - real-time intel management (operational)
3. `commands/fitting.py` / `fittings.py` - fitting operations
4. `commands/killmail.py` / `killmails.py` - kill analysis
5. `commands/pi.py` - planetary interaction
Use the existing `tests/commands/conftest.py` patterns to mock ESI responses.

### Finding 7: Backfill Service Completely Untested

**Severity:** High
**File:** `src/aria_esi/services/redisq/backfill.py` (0%, 111 stmts)
**Finding:** The zKillboard gap recovery/backfill service has zero test coverage. This module handles downloading missed kills when the poller has been offline.
**Impact:** When the poller goes offline and restarts, backfill is the safety net ensuring no kills are lost. A bug here means permanent data loss in the killmail store, with no visibility that it occurred.
**Fix:** Create `tests/services/redisq/test_backfill.py` with:
- Mock zKillboard API responses
- Backfill gap calculation logic
- Error handling for API rate limits and network failures
- Integration test with mock killmail store

### Finding 8: Market Database Async Layer at 14% Coverage

**Severity:** High
**File:** `src/aria_esi/mcp/market/database_async.py` (14%, 369 stmts)
**Finding:** The async SQLite database layer for market data is nearly untested. This module handles all persistent market data operations in the MCP server.
**Impact:** Market data integrity depends on this layer. Bugs in SQL queries, transaction handling, or connection management could corrupt market data or cause server crashes.
**Fix:** Create `tests/mcp/market/test_database_async.py` using `aiosqlite` with in-memory databases. Test:
- Schema creation and migrations
- CRUD operations for orders, prices, history
- Concurrent access patterns
- Error handling for database locks

### Finding 9: Threshold Too Low and Shrinking

**Severity:** Medium
**File:** `pyproject.toml:L132`
**Finding:** The `fail_under` threshold was lowered from 60% to 59% after removing the archetype framework, as noted in the comment: "Threshold lowered from 60 after archetype framework removal (well-tested code deleted)." Current coverage at 60.33% gives only 1.33pp of headroom.
**Impact:** Any new feature with moderate complexity that ships without tests could push coverage below the threshold. More concerning, the direction is downward (threshold decreased, not increased).
**Fix:**
1. Raise `fail_under` to 60% now (current coverage is 60.33%)
2. Add a ratchet mechanism: after each coverage improvement, bump the threshold to (current - 0.5%) to prevent backsliding
3. Track coverage as a CI artifact and add a coverage diff comment to PRs

### Finding 10: No Coverage Trend Tracking

**Severity:** Medium
**File:** `.github/workflows/ci.yml:L78-L79`
**Finding:** CI generates coverage XML (`--cov-report=xml`) but does not upload it to any tracking service (Codecov, Coveralls, etc.) or retain it as a CI artifact. There is no PR coverage diff comment.
**Impact:** Without trend tracking, there is no way to detect gradual coverage erosion. Reviewers cannot see whether a PR improves or degrades coverage without running tests locally.
**Fix:**
1. Add `actions/upload-artifact@v4` step to store coverage XML
2. Integrate with Codecov or Coveralls (free for open source)
3. Add a PR comment bot showing coverage diff (e.g., `codecov/codecov-action@v4`)

### Finding 11: Vendored EOS Code Included in Coverage

**Severity:** Medium
**File:** `pyproject.toml:L117-L124` (`[tool.coverage.run]`)
**Finding:** The vendored EOS fitting engine (`_vendor/eos/`) is included in coverage measurement. It contains thousands of statements with highly variable coverage (0-100%) that the team does not maintain. This inflates the denominator and makes the overall percentage misleading.
**Impact:** Including vendor code means that improvements to ARIA's own code have a diluted effect on the overall percentage. It also makes it harder to reason about actual project coverage.
**Fix:** Add `"*/_vendor/*"` to `[tool.coverage.run] omit`:
```toml
[tool.coverage.run]
omit = [
    "tests/*",
    "*/__pycache__/*",
    "*/__main__.py",
    "*/tests/*",
    "*/_vendor/*",  # Vendored code - not maintained by this project
]
```
This will give a more accurate picture of first-party code coverage. After this change, re-baseline the `fail_under` threshold.

### Finding 12: MCP Dispatcher Layer Coverage Gap Pattern

**Severity:** Medium
**File:** `src/aria_esi/mcp/dispatchers/pilot.py` (8%), `fitting.py` (27%), `market.py` (31%), `killmails.py` (33%), `skills.py` (41%), `sde.py` (44%)
**Finding:** Six of eight MCP dispatchers are below 50% coverage. The dispatchers route action strings to implementation functions and handle parameter validation. Tests exist for `universe.py` (86%) and basic action routing in `test_dispatchers.py`, but the actual `_impl_*` methods in most dispatchers are untested.
**Impact:** The dispatcher layer is the primary integration point between the MCP protocol and business logic. Input validation, error formatting, and parameter coercion happen here. When these dispatchers are poorly tested, invalid inputs can reach the business logic layer unchecked.
**Fix:** Extend `tests/mcp/dispatchers/` with implementation-level tests for each dispatcher's `_impl_*` methods. Prioritize `pilot.py` (8%) and `fitting.py` (27%) first.

### Finding 13: Keyring Backend Security Module at 59%

**Severity:** Medium
**File:** `src/aria_esi/core/keyring_backend.py:L51-L332`
**Finding:** The keyring integration module has 113 statements with 47 uncovered (59% coverage). Untested paths include GNOME Keyring detection (L64-L86), keyring fallback logic (L199-L210), and keyring error handling (L226-L257).
**Impact:** The keyring backend is part of the Tier II security model. Untested fallback logic could result in credentials silently falling back to plaintext storage without user awareness, or keyring failures not being properly communicated.
**Fix:** Add tests mocking various keyring states:
- GNOME Keyring locked vs unlocked
- Keyring unavailable (ImportError)
- Keyring store/retrieve failures
- Fallback to plaintext path notification

### Finding 14: Scope Refresh Module at 0% (259 stmts)

**Severity:** Medium
**File:** `src/aria_esi/mcp/market/scope_refresh.py` (0%, 259 stmts)
**Finding:** The market scope refresh module is entirely untested. It handles refreshing ESI market order data for custom market scopes.
**Impact:** Ad-hoc market scopes are a documented feature (referenced in `CLAUDE.md` and `docs/ADHOC_MARKETS.md`). If scope refresh breaks, users lose the ability to get up-to-date market data for custom locations.
**Fix:** Create `tests/mcp/market/test_scope_refresh.py` testing the refresh lifecycle with mocked ESI responses.

### Finding 15: Branch Coverage Not Separately Enforced

**Severity:** Medium
**File:** `pyproject.toml:L125-L132`
**Finding:** Branch coverage is enabled (`branch = true`) but the `fail_under` threshold applies to combined line+branch coverage. There is no separate branch coverage threshold.
**Impact:** It is possible to have high line coverage but poor branch coverage, leaving error-handling paths untested. The 1,280 missed branches in the current report confirm this pattern.
**Fix:** Consider adding a separate branch coverage enforcement. Coverage.py does not natively support separate thresholds, but a CI script could parse the XML report and fail if branch coverage falls below a minimum (e.g., 50%).

### Finding 16: No Per-Module Coverage Thresholds

**Severity:** Low
**File:** `pyproject.toml:L127-L132`
**Finding:** Coverage thresholds are global only. Critical modules (auth, keyring, path_security) share the same 59% minimum as utility modules.
**Impact:** Security-critical modules could theoretically have very low coverage as long as the global average stays above threshold.
**Fix:** Use `coverage.py`'s `[tool.coverage.report]` `fail_under` with `--include` in CI to enforce per-module thresholds for critical paths:
```bash
# In CI, add a step:
uv run coverage report --include="src/aria_esi/core/auth.py" --fail-under=70
uv run coverage report --include="src/aria_esi/core/path_security.py" --fail-under=90
```

### Finding 17: Tests Exist in Source Tree

**Severity:** Low
**File:** `src/aria_esi/mcp/market/tests/` directory
**Finding:** There are test files inside the source tree at `src/aria_esi/mcp/market/tests/` (test_adhoc_schema.py, test_arbitrage.py, test_management_tools.py, test_scope_refresh.py). While these are excluded from coverage via `*/tests/*` in the omit config, having tests in the source tree is unusual.
**Impact:** These tests may or may not be collected by pytest (depends on `testpaths` config). They create confusion about where test files should live and could potentially end up in the wheel distribution.
**Fix:** Move these test files to `tests/mcp/market/` to follow the established convention. Update any relative imports as needed.

### Finding 18: Coverage Exclusion Lines Could Be More Complete

**Severity:** Info
**File:** `pyproject.toml:L135-L141`
**Finding:** The `exclude_lines` configuration covers common patterns (`pragma: no cover`, `if __name__`, `raise NotImplementedError`, `if TYPE_CHECKING`, `@overload`) but misses some patterns that appear in the codebase: `pass` in abstract methods, `...` (ellipsis) in protocol/abstract methods, and `@abstractmethod` decorated methods.
**Impact:** Minor -- abstract methods and protocol stubs contribute small amounts to the uncovered count.
**Fix:** Add to `exclude_lines`:
```toml
exclude_lines = [
    # existing...
    "\\.\\.\\.",       # ellipsis in abstract/protocol methods
    "@abstractmethod",
]
```

---

## 3. Coverage Tooling and Enforcement Assessment

### 3a. Coverage Configuration

| Aspect | Status | Assessment |
|--------|--------|------------|
| Coverage tool | pytest-cov (coverage.py) | Good |
| Branch coverage | Enabled | Good |
| Source specification | `src/aria_esi` | Correct |
| Omit patterns | tests, __pycache__, __main__ | Missing `_vendor` |
| fail_under | 59% | Too low, shrinking |
| Exclude lines | Standard patterns | Missing ellipsis/abstract |
| HTML report | Configured | Good for local dev |

### 3b. CI Enforcement

| Aspect | Status | Assessment |
|--------|--------|------------|
| Coverage runs on PR | Yes (3 Python versions) | Good |
| Coverage gate enforced | Yes (via fail_under) | Works but threshold low |
| Coverage artifact uploaded | No | Gap -- no trend tracking |
| Coverage diff on PR | No | Gap -- no reviewer visibility |
| Per-module thresholds | No | Gap for critical modules |
| Coverage badge | No | Minor -- nice to have |

### 3c. Test Infrastructure Quality

| Aspect | Status | Assessment |
|--------|--------|------------|
| Parallel test execution | pytest-xdist available | Good |
| Async test support | pytest-asyncio | Good |
| HTTP mocking | pytest-httpx | Good |
| Snapshot testing | syrupy | Good |
| Time mocking | time-machine | Good |
| Test markers | Well-defined (unit, integration, etc.) | Good |
| Benchmark separation | `--no-cov` flag, separate marker | Good |
| Conftest organization | Per-directory conftest files | Good |

---

## 4. Critical Path Coverage Assessment

### 4a. Authentication and Security

| Path | Module | Coverage | Verdict |
|------|--------|----------|---------|
| OAuth token refresh | `core/auth.py` | 59% | **Insufficient** |
| Credential storage | `core/keyring_backend.py` | 59% | **Insufficient** |
| Path traversal prevention | `core/path_security.py` | 95% | Good |
| Persona file validation | `persona/compiler.py` | 92% | Good |
| File permissions check | `core/auth.py` | Partial | Needs more |

### 4b. Data Integrity

| Path | Module | Coverage | Verdict |
|------|--------|----------|---------|
| Universe graph load/verify | `universe/graph.py`, `serialization.py` | 97-100% | Good |
| SDE data import | `mcp/sde/importer.py` | 11% | **Insufficient** |
| Market data storage | `mcp/market/database_async.py` | 14% | **Insufficient** |
| Killmail store | `services/killmail_store/sqlite.py` | 93% | Good |
| Navigation routing | `services/navigation/router.py` | 94% | Good |

### 4c. Core Business Logic

| Path | Module | Coverage | Verdict |
|------|--------|----------|---------|
| Route calculation | `services/navigation/*` | 90-100% | Good |
| Loop planning | `services/loop_planning/*` | 93-100% | Good |
| Fitting stats | `fitting/eos_bridge.py` | 85% | Adequate |
| Interest scoring (killmail) | `services/redisq/interest_v2/*` | 86-100% | Good |
| Arbitrage calculation | `services/arbitrage_engine.py` | 40% | **Insufficient** |
| Market refresh | `services/market_refresh.py` | 33% | **Insufficient** |

### 4d. Error Handling and Edge Cases

| Path | Coverage | Verdict |
|------|----------|---------|
| HTTP rate limiting (429) | Not covered (`client.py` L360-390) | **Gap** |
| ESI pagination edge cases | Not covered (`client.py` L489-511) | **Gap** |
| Retry exhaustion | Partially covered (`retry.py` 75%) | Partial |
| Database connection failures | Partially covered | Partial |
| Malformed ESI responses | Partially covered (varies by module) | Partial |
| Empty market order books | Not covered (market tools at 0%) | **Gap** |

---

## 5. Actionable Recommendations (Ranked by Priority)

### Priority 1 (P0) -- Address within 2 weeks

1. **Exclude vendored code from coverage** -- Add `"*/_vendor/*"` to `[tool.coverage.run] omit`. This is a one-line config change that immediately gives accurate coverage numbers for first-party code. Re-baseline `fail_under` after.

2. **Test MCP market tools** -- Create tests for the eight 0%-coverage market tool modules. These are the most-used MCP actions. Start with `tools_prices.py` and `tools_orders.py` (the two most fundamental).

3. **Test auth token refresh** -- Add tests for `core/auth.py` L501-L599 covering token refresh, OAuth exchange, and keyring integration. These are security-critical paths.

### Priority 2 (P1) -- Address within 1 month

4. **Test MCP fitting tools layer** -- Create tests for `mcp/fitting/tools_stats.py` and the dispatcher's `_impl` methods.

5. **Test SDE importer core functions** -- Add tests for the most critical parsing functions in `mcp/sde/importer.py`. Full coverage is not necessary, but import-table functions for types, skills, and blueprints should be tested.

6. **Test backfill service** -- Create tests for `services/redisq/backfill.py` to protect the gap recovery safety net.

7. **Add coverage trend tracking** -- Integrate Codecov or equivalent into CI. Add PR coverage diff comments.

8. **Raise fail_under to 60%** -- Coverage is already at 60.33%. After excluding vendor code, first-party coverage should be higher. Set the threshold appropriately.

### Priority 3 (P2) -- Address within quarter

9. **Test MCP dispatcher impl methods** -- Systematically test `_impl_*` methods in `dispatchers/pilot.py`, `fitting.py`, `market.py`, `killmails.py`.

10. **Test core HTTP client edge cases** -- Add rate-limit, pagination, and error-handling tests for `core/client.py`.

11. **Test CLI command layer** -- Prioritize `commands/market.py`, `commands/redisq.py`, `commands/fitting.py`.

12. **Add per-module coverage thresholds** -- Enforce minimum coverage for `core/auth.py` (70%), `core/path_security.py` (90%), `core/client.py` (70%).

13. **Move in-source tests** -- Relocate `src/aria_esi/mcp/market/tests/` to `tests/mcp/market/`.

### Priority 4 (P3) -- Nice to have

14. **Add branch-only coverage gate** -- Parse coverage XML in CI to enforce a minimum branch coverage percentage.

15. **Expand coverage exclusion patterns** -- Add `\\.\\.\\.` and `@abstractmethod` to `exclude_lines`.

16. **Create coverage dashboard** -- Track coverage by module group over time to identify trending gaps.

---

## Appendix: Module Coverage Summary by Package

| Package | Modules | Avg Coverage | Min Coverage | Notes |
|---------|---------|-------------|-------------|-------|
| `core/` | 12 | ~73% | 0% (freshness_adapters) | Auth/client need attention |
| `commands/` | 32 | ~45% | 7% (fittings) | Systematically under-tested |
| `fitting/` | 7 | ~86% | 75% (skills) | Good |
| `mcp/` (top-level) | 12 | ~77% | 44% (esi_client) | Mixed |
| `mcp/dispatchers/` | 8 | ~42% | 8% (pilot) | Gap in impl testing |
| `mcp/market/` | 16 | ~22% | 0% (many) | Major gap |
| `mcp/sde/` | 12 | ~43% | 0% (several) | Importer is biggest gap |
| `mcp/fitting/` | 3 | ~0% | 0% | Untested |
| `models/` | 4 | ~75% | 0% (config_types) | TypedDict module is fine at 0% |
| `persona/` | 2 | ~92% | 92% | Good |
| `services/` (top-level) | 12 | ~73% | 33% (market_refresh) | Mixed |
| `services/navigation/` | 4 | ~96% | 90% | Good |
| `services/loop_planning/` | 5 | ~97% | 93% | Good |
| `services/killmail_store/` | 5 | ~89% | 80% (protocol) | Good |
| `services/redisq/` (core) | 10 | ~54% | 0% (backfill) | Backfill is critical gap |
| `services/redisq/interest_v2/` | 25 | ~90% | 48% (signals init) | Well-tested |
| `services/redisq/notifications/` | 20 | ~87% | 72% (esi_coordinator) | Good |
| `services/sovereignty/` | 5 | ~89% | 62% (init) | Good |
| `universe/` | 4 | ~96% | 87% (builder) | Good |
| `cache/` | 2 | ~49% | 0% (builder) | Cache builder untested |
