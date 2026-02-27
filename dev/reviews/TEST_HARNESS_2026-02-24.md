# Test Harness Review
**Date:** 2026-02-24
**Prompt:** dev/prompts/testing/test_harness.md
**Reviewer:** Claude Opus 4.6

---

## 1. Current Harness Inventory

### 1.1 Test Runner Configuration

| Component | Tool | Configuration File |
|-----------|------|--------------------|
| Runner | pytest 8.0+ | `pyproject.toml` `[tool.pytest.ini_options]` |
| Parallel execution | pytest-xdist 3.5+ | `-n auto` (recommended, not in addopts) |
| Coverage | pytest-cov 4.0+ | `[tool.coverage.run]`, `[tool.coverage.report]` |
| Async support | pytest-asyncio 0.23+ | Decorator-based (`@pytest.mark.asyncio`) |
| HTTP mocking | pytest-httpx 0.30+ | Conditional skip if unavailable |
| Benchmarking | pytest-benchmark 4.0+ | Marker-gated (`-m benchmark`) |
| Snapshot testing | syrupy 4.0+ | `tests/skills/__snapshots__/` |
| Time freezing | time-machine 2.10+ | Optional, graceful skip if missing |
| Schema validation | jsonschema 4.20+ | Conditional skip if missing |
| Linting | ruff 0.4+ | `.pre-commit-config.yaml`, `[tool.ruff]` |
| Type checking | mypy 1.8+ | `[tool.mypy]`, pre-commit hook |
| Package management | uv + hatchling | `uv.lock`, `pyproject.toml` |

### 1.2 Test File Counts

| Category | Files | Tests Collected |
|----------|-------|-----------------|
| Total test files | ~275 | 6,322 |
| Default run (no benchmark/semantic/tier3) | ~250 | 6,288 |
| Benchmark tests | 3 bench files | 23 |
| Semantic tests (LLM-as-judge) | 1 | 9 |
| Golden/snapshot tests | 1 | 15 |
| Contract tests (Layer 1) | 1 | 71 |
| Integration tests | 4 | 165 |
| Unit-marked tests | ~18 files | 190 |
| Tier 1 (mock MCP) | 1 | 137 |
| Tier 2 (API integration) | 1 | 2 |
| conftest.py files | 13 | N/A |

### 1.3 Directory Structure

```
tests/
├── conftest.py                    # Root: ESI fixtures, time/RNG, singleton resets
├── fixtures/esi/                  # Externalized ESI JSON responses
├── benchmarks/                    # Performance benchmarks (real graph required)
│   └── conftest.py               # benchmark_universe fixture
├── commands/                      # CLI command tests
│   └── conftest.py               # Mock credentials, ESI responses
├── core/                          # Core library tests (config, retry, path security)
├── fitting/                       # Ship fitting module tests
│   └── conftest.py               # ParsedFit fixtures, mock EOS, mock market DB
├── integration/                   # Full MCP protocol integration tests
│   └── conftest.py               # integration_server fixture
├── mcp/                           # MCP server and tool tests
│   ├── conftest.py               # Mock universe factory, dispatcher helpers
│   ├── dispatchers/              # Dispatcher action tests
│   │   └── conftest.py           # Dispatcher factory, activity cache mocks
│   └── market/                   # Market tool tests
├── models/                        # Pydantic model tests
├── services/                      # Service layer tests
│   ├── killmail_store/           # SQLite killmail store
│   │   └── conftest.py           # Async store fixtures
│   ├── loop_planning/            # Loop planning algorithm tests
│   ├── navigation/               # Router tests
│   └── redisq/                   # Real-time kill processing
│       ├── conftest.py           # RedisQ package fixtures, mock settings
│       ├── interest_v2/          # Interest engine v2
│       │   ├── conftest.py       # Mock kills, configs, delivery fixtures
│       │   └── signals/
│       │       └── conftest.py   # Signal-specific fixtures (value, ship, time, etc.)
│       └── notifications/
│           └── conftest.py       # Factory functions for notification objects
├── skills/                        # AI skill testing (3-layer validation)
│   ├── conftest.py               # Mock MCP tracker, schema/fixture loading
│   ├── schemas/                  # 21 JSON schema files (YAML)
│   ├── fixtures/                 # ~70 YAML test fixtures across 17 skills
│   ├── evals/                    # G-Eval configs for semantic tests
│   ├── ground_truth/             # Ground truth data (.gitkeep only)
│   ├── __snapshots__/            # Syrupy snapshot files
│   └── integration/              # MCP mocker, ESI mocker, invokers
├── unit/                          # Unit tests (gatecamp, realtime, threat, war)
└── universe/                      # Universe graph builder/serialization tests
```

### 1.4 CI Workflows

| Workflow | Trigger | What It Runs |
|----------|---------|--------------|
| `ci.yml` | Push/PR to main | Security scan, lint+mypy, tests (3.11/3.12/3.13) |
| `test-universe.yml` | Push/PR touching MCP/universe | MCP unit tests, integration tests, benchmarks (main only) |
| `tier2-skill-tests.yml` | Weekly Monday 06:00 UTC | Tier 1 sanity then Tier 2 API integration |
| `data-health.yml` | Weekly Wednesday 06:00 UTC | EOS tag verification, SDE URL reachability |

### 1.5 Coverage Configuration

- **Source**: `src/aria_esi`
- **Branch coverage**: enabled (`branch = true`)
- **Fail threshold**: 59% (documented comment explains regression from archetype framework removal)
- **Exclusions**: `pragma: no cover`, `__main__`, `NotImplementedError`, `TYPE_CHECKING`, `@overload`
- **Omissions**: tests, `__pycache__`, `__main__.py`

---

## 2. Layer Definition & Boundaries

### 2.1 Unit Tests

**Harness support: Strong**

The vast majority of the 6,288 default tests are de facto unit tests. They test individual functions, classes, and modules in isolation using `MagicMock`, `monkeypatch`, and `tmp_path`. Key characteristics:

- Minimal mocking overhead via the `create_mock_universe()` factory in `tests/mcp/conftest.py`
- Floating-point helpers (`approx_sec`, `approx_isk`, `assert_highsec`) in root conftest
- Security-focused tests (`test_path_security.py`) with thorough edge-case coverage
- SDE mock database (`mock_sde_db`) built in `tmp_path` with `sqlite3`

**Weakness**: Only 190 tests are explicitly marked `@pytest.mark.unit`. The majority of tests are unmarked, relying on the default pytest collection. This makes it impossible to run "only unit tests" with confidence. The `unit` marker is underused.

### 2.2 Integration Tests

**Harness support: Good**

Integration tests are well-structured across two axes:

1. **MCP Protocol Integration** (`tests/integration/`): Tests server lifecycle, tool registration, route calculation through the full stack. Uses `sample_graph_path` (session-scoped, built from minimal cache data) to avoid depending on the real universe graph.

2. **Skill Integration Tiers** (`tests/skills/test_integration.py`): A 3-tier system:
   - **Tier 1**: Mock MCP dispatcher calls (137 tests, always available)
   - **Tier 2**: Anthropic API with mock tools (2 tests, weekly CI)
   - **Tier 3**: Full Claude CLI (manual, excluded from default run via `-m "not tier3"`)

**Weakness**: The `integration` marker (165 tests) does not distinguish between "real MCP protocol" integration and "mock integration with fixtures." Some `@pytest.mark.integration` tests are closer to unit tests in practice.

### 2.3 Contract Tests

**Harness support: Good**

`tests/skills/test_contracts.py` (71 tests, marked `@pytest.mark.contract`) validates that skills invoke the correct MCP dispatchers with correct parameters. The `MockMCPTracker` dataclass in `tests/skills/conftest.py` provides:

- `record_call()` / `was_called()` / `called_with()` for assertion
- `set_response()` for configuring mock returns
- `get_calls()` for inspecting call history

**Weakness**: Contract tests currently validate call recording rather than actual dispatcher invocation. They record calls manually (`mock_mcp.record_call(...)`) rather than intercepting real calls. This means the contract tests verify the test's own expectations, not the skill's actual behavior. The tests are more "contract specification" than "contract enforcement."

### 2.4 Golden/Snapshot Tests

**Harness support: Good**

`tests/skills/test_skill_outputs.py` (15 tests, marked `@pytest.mark.golden`) uses syrupy for snapshot testing:

- Snapshot file: `tests/skills/__snapshots__/test_skill_outputs.ambr`
- `normalize_volatile_fields()` fixture strips timestamps, cache ages before comparison
- Status output golden test validates full response structure

Additionally, the structural validation layer (`tests/skills/test_structure.py`, marked `@pytest.mark.structure`) provides:
- JSON Schema validation against 21 YAML schema files
- Fact assertion engine (`assert_fact()`) with JSONPath-like expressions
- ~70 YAML test fixtures defining expected outputs per skill

**Weakness**: Only 15 golden tests exist. The snapshot file contains a single snapshot (`TestStatusOutputGolden.test_status_output_structure`). Most golden tests in `test_skill_outputs.py` are `skipif` gated on optional dependencies.

---

## 3. Domain-Aware Harness Evaluation

### 3.1 ESI Integration

**Token Refresh**: Mocked via `mock_credentials_data` fixture with static `access_token`, `refresh_token`, and `token_expiry`. The `mock_authenticated_client` in `commands/conftest.py` provides `get_dict_safe`/`get_list_safe` delegation. No tests exercise the actual OAuth refresh flow (appropriate for unit/integration layers, but no contract tests for the refresh path exist).

**Rate Limits**: The retry module (`core/retry.py`) is tested in `test_retry.py` for retryable status codes (429, 502, 503, 504) and backoff configuration. `pytest-httpx` is used for HTTP-level mocking when available. Rate limit header parsing is implicitly covered.

**Schema Drift**: ESI response fixtures are externalized in `tests/fixtures/esi/` (5 files covering character, killmails, universe). The `load_esi_fixture()` helper and `esi_fixture_loader` pytest fixture provide clean loading. However, there are only 5 fixture files, covering a small fraction of the ~30+ ESI endpoints the project uses. Most ESI responses are inlined as fixture return values in conftest files.

**Verdict**: The ESI mocking infrastructure is mature but the externalized fixture coverage is thin. Most ESI data is duplicated across conftest files rather than centralized.

### 3.2 MCP Dispatchers

**Action Routing**: The `create_dispatcher()` factory in `tests/mcp/dispatchers/conftest.py` captures registered tool functions by replacing `mock_server.tool` with a capturing decorator. This is well-designed and used consistently.

**Parameter Validation**: `test_sde_actions.py`, `test_skills_actions.py`, `test_market_actions.py`, etc. verify that missing required parameters raise `InvalidParameterError`. All invalid/empty action strings are tested.

**Error Propagation**: Custom exception hierarchy (`SystemNotFoundError`, `RouteNotFoundError`, `InsufficientBordersError`, `InvalidParameterError`) is tested in `test_edge_cases.py` and `test_errors.py`. Error messages include contextual data (found/required counts, suggestions).

**Verdict**: Strong coverage of the dispatcher layer. The capture pattern is clean and the error tests are thorough.

### 3.3 EVE Mechanics

**Floating-Point Tolerance**: Root conftest provides `approx_sec()` (rel=1e-4 for security status), `approx_isk()` (rel=1e-6 for ISK), and security class assertion helpers (`assert_highsec`, `assert_lowsec`, `assert_nullsec`). These are domain-aware and well-documented.

**Deterministic Calculations**: The `seeded_rng` fixture (seed=42) and `seed_global_random` fixture provide reproducible randomness. The universe graph factory (`create_mock_universe()`) produces deterministic graph structures with known properties.

**Verdict**: Good. The tolerance helpers are appropriate for EVE's numeric domains. Consider adding `approx_dps()` for damage calculations.

### 3.4 Persona/Skills

**Missing Overlay Simulation**: The `test_skill_preflight.py` and `test_persona.py` files exist at the top level but were not deeply examined. The skill conftest provides `MockMCPTracker` and fixture loading infrastructure. No explicit tests for "overlay missing, fall back to base" were found in the fixture set.

**Context Staleness**: The session initialization protocol in CLAUDE.md describes staleness checking, but no dedicated test exercises the `persona_context.branch` vs profile `faction` mismatch detection flow.

**Verdict**: The 3-layer skill validation (contract, structure, semantic) is architecturally impressive but the actual test count is modest. Most skill fixtures are structural validation inputs, not integration tests.

---

## 4. Mock Strategy Verification

### 4.1 What IS Mocked (Correctly)

| Category | Implementation | Assessment |
|----------|---------------|------------|
| ESI API responses | `MagicMock(spec=ESIClient)`, inline fixtures, `pytest-httpx` | Correct |
| Current time | `time-machine` (comprehensive) + `mock_utc_now` (targeted) | Correct |
| File system | `tmp_path` / `tmp_path_factory` for test databases, graphs, credentials | Correct |
| Randomness | `seeded_rng` (isolated) + `seed_global_random` (global, opt-in) | Correct |
| D-Bus/keyring | `ARIA_NO_KEYRING=1` env var set in root conftest | Correct |
| Singletons | `reset_all_singletons` autouse fixture resets ~30 singletons | Correct |

### 4.2 What is NOT Mocked (Correctly)

| Category | Evidence | Assessment |
|----------|----------|------------|
| SDE data | `mock_sde_db` uses real SQLite with test data; `SDEQueryService` is real | Correct |
| Route algorithms | `sample_graph` fixture builds real graph via `build_universe_graph()` | Correct |
| Pydantic validation | Real models used (`ParsedFit`, `FitStatsResult`, `PriceResult`, etc.) | Correct |
| Universe graph | `create_mock_universe()` constructs real `UniverseGraph` with igraph | Correct |

### 4.3 Anti-Pattern: Duplicated Mock Data

The `MockProcessedKill` dataclass is defined in three separate conftest files:
- `tests/services/redisq/interest_v2/conftest.py`
- `tests/services/redisq/interest_v2/signals/conftest.py`
- `tests/services/redisq/notifications/conftest.py` (factory function variant)

While the implementations differ slightly (the signals version adds `hull_value` and `kill_time`), this duplication risks drift. The notifications version uses `MagicMock` instead of a dataclass, which loses type safety.

---

## 5. Edge Case Coverage

### 5.1 Data Edge Cases

| Edge Case | Coverage | File |
|-----------|----------|------|
| Empty system list | Tested | `test_edge_cases.py::TestEmptyInputs` |
| Single-system universe | Tested | `test_edge_cases.py::TestMinimalUniverse` |
| Disconnected graph | Tested | `test_edge_cases.py::TestDisconnectedUniverse` |
| Inverted security range | Tested | `test_edge_cases.py::TestBoundaryConditions` |
| Case-insensitive names | Tested | `test_edge_cases.py::TestCaseSensitivity` |
| Path traversal attacks | Thoroughly tested | `test_path_security.py` (20+ test cases) |
| Symlink escape | Tested with OS-aware skip | `test_path_security.py::test_detects_symlink_escape` |
| Binary/UTF-8 errors | Tested | `test_path_security.py::test_rejects_binary_file_as_utf8_error` |
| Empty credentials | Tested | Root conftest `mock_credentials_data` |
| BPO vs BPC indicators | Tested | Root conftest `mock_blueprint_response` |
| ISK precision (billion-scale) | Tested via `approx_isk` | Root conftest |

**Missing Edge Cases:**
- No tests for ESI pagination (multi-page responses with `X-Pages` header)
- No tests for ESI error response bodies (HTML error pages, maintenance mode)
- No tests for concurrent singleton access (race conditions in reset)
- No tests for extremely large killmail attacker lists (100+ attackers)
- No tests for unicode system names (e.g., wormhole designations with special characters)

### 5.2 Temporal Edge Cases

| Edge Case | Coverage | Notes |
|-----------|----------|-------|
| Time freezing | `frozen_time` fixture via time-machine | Comprehensive |
| Cache staleness | `check_freshness` tested in `test_freshness.py` | Good |
| Token expiry boundary | `mock_credentials_data` has fixed expiry | Not boundary-tested |
| Midnight UTC rollover | `mock_kill_midnight` fixture exists | Signal tests only |
| DST transitions | Not tested | Low priority for UTC-only project |

### 5.3 Security Edge Cases

| Edge Case | Coverage | Notes |
|-----------|----------|-------|
| Path traversal | 10+ test cases | `test_path_security.py` |
| Absolute path injection | Tested (Unix + Windows) | Both `/etc/passwd` and `C:\` |
| Extension allowlist bypass | 7+ test cases | `.py`, `.sh`, `.exe`, no-extension |
| Break-glass mechanism | 7 test cases | Enable/disable, bypass validation |
| Pilot ID format injection | 8+ test cases | Special chars, path traversal, length |
| Symlink containment | 2 test cases | Escape detection, internal allowed |

---

## 6. Determinism Assessment

### 6.1 Time Determinism

**Strong.** Two complementary approaches:

1. `frozen_time` fixture (time-machine): Freezes all time sources to `2026-01-15T18:30:00Z`
2. `mock_utc_now` fixture: Patches only ARIA's `get_utc_now` function

The `normalize_volatile_fields()` function in skill tests strips 7 volatile keys before snapshot comparison.

### 6.2 Randomness Determinism

**Good.** `seeded_rng` provides an isolated `random.Random(42)` instance. `seed_global_random` is opt-in (not autouse) and restores original state after test.

**Risk**: Production code using `random.choice()` or `random.shuffle()` directly (not through the injected RNG) will be non-deterministic unless `seed_global_random` is explicitly requested.

### 6.3 Ordering Determinism

**Adequate.** pytest-xdist is available but not in `addopts` (parallel execution is opt-in via `-n auto`). Session-scoped fixtures (`sample_cache_data`, `sample_graph`, `real_universe`) are safe for parallel use since they're read-only.

**Risk**: The `reset_all_singletons` autouse fixture runs 30+ resets before and after every test. With xdist, different workers share the same process but different test order. The singleton reset pattern is correct for sequential execution but could mask ordering bugs that would surface in parallel.

### 6.4 Floating-Point Tolerance

**Good.** Domain-specific tolerance functions are defined and documented:
- `approx_sec(value, rel=1e-4)` for security status (4 decimal places in ESI)
- `approx_isk(value, rel=1e-6)` for ISK values (can reach billions)

**Missing**: No `approx_dps()` or `approx_resist()` helpers for fitting calculations. The fitting test fixtures use exact float comparisons via `MagicMock` return values, which sidesteps the issue but means real calculation tolerance is untested.

---

## 7. Fixture Generation Workflow

### 7.1 ESI Fixtures

The `tests/fixtures/esi/README.md` documents the capture-and-store workflow:

1. **Naming**: snake_case, include identifying info (`system_jita.json`)
2. **Format**: Valid JSON matching ESI response schemas
3. **IDs**: Standardized test IDs (character 12345678, Jita 30000142, etc.)
4. **Loading**: `load_esi_fixture("character/location.json")` helper function

**Current coverage**: 5 fixture files (character info, location, wallet, killmail, system).

**Gap**: No anonymization step is documented. The README says "use realistic test data (real type IDs, system IDs)" but doesn't address capturing from live ESI and sanitizing PII.

### 7.2 Skill Fixtures

The skill testing framework has a mature fixture pipeline:

1. **Schemas**: `tests/skills/schemas/*.schema.yaml` (21 schemas)
2. **Fixtures**: `tests/skills/fixtures/<skill>/*.yaml` (~70 fixtures across 17 skills)
3. **Ground Truth**: `tests/skills/ground_truth/` (gitkeep only -- placeholder)
4. **Evals**: `tests/skills/evals/*.eval.yaml` (2 G-Eval configs)
5. **Generation Scripts**: `tests/skills/scripts/generate_fixture.py`, `generate_schema.py`

Each fixture YAML file contains:
- `input`: The user request / parameters
- `mock_responses`: Expected MCP dispatcher responses
- `expected_output`: (structure layer) Schema-validated expected output
- `facts`: (structure layer) JSONPath-based assertions

### 7.3 Universe Fixtures

Session-scoped fixtures build test universes from inline data:
- `sample_cache_data`: 6-system universe with known security levels
- `sample_graph` / `sample_graph_path`: Built from cache, serialized to disk
- `create_mock_universe()`: Factory for custom topologies (igraph + numpy)
- `STANDARD_SYSTEMS` / `STANDARD_EDGES`: Reusable system/edge definitions

---

## 8. Coverage Analysis

### 8.1 Current State

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Line coverage (when tests pass) | ~59-60% | 80%+ | Below target |
| Coverage threshold (`fail_under`) | 59% | 80%+ | Configured low |
| Branch coverage | Enabled | 70%+ for dispatchers | Unknown per-module |
| MCP action coverage | Partial | 100% | Below target |
| ESI endpoint happy paths | ~30% externalized | 100% | Below target |

Note: The `--co -q` collection run showed 12.56% coverage because collection-only doesn't execute tests. The real coverage when tests pass is around 59% based on the `fail_under` threshold.

### 8.2 Coverage Gaps by Module

From the `pyproject.toml` comments:
- Core modules (auth, client, retry): 49-73% coverage
- Command modules: clones 72%, skills 89%, industry 72%, mining 76%, contracts 50%
- MCP tools: 71-100% coverage
- Overall project: ~60%

### 8.3 CI Coverage Integration

The main CI workflow (`ci.yml`) runs:
```bash
uv run pytest --cov --cov-report=xml --cov-report=term
```

Coverage XML is generated but not uploaded to any coverage service (no Codecov/Coveralls step). The `test-universe.yml` workflow explicitly uses `--no-cov` for focused test runs.

---

## 9. Findings

### 9.1 Strengths

1. **Comprehensive singleton reset** (`reset_all_singletons`): The autouse fixture resets 30+ module-level singletons, preventing cross-test contamination. Each reset is try/except-wrapped for resilience. This is above-average for Python projects.

2. **Domain-aware floating-point helpers**: `approx_sec()` and `approx_isk()` with documented precision rationale show mature understanding of the problem domain.

3. **Mock universe factory**: `create_mock_universe()` constructs real `UniverseGraph` instances from declarative system/edge lists, avoiding brittle mocking of the graph library. Standard test universes (6-system, 11-system, minimal, disconnected) cover common topologies.

4. **3-layer skill validation architecture**: Contract (Layer 1), Structure (Layer 2), and Semantic (Layer 3) testing with increasing cost and fidelity is well-designed. The schema + fixture + fact assertion system in `tests/skills/` is sophisticated.

5. **Security test depth**: `test_path_security.py` (60+ test cases) is thorough, covering path traversal, symlink escape, extension allowlists, pilot ID injection, and break-glass mechanisms.

6. **Multi-tier CI strategy**: Weekly Tier 2 API tests with cost estimates ($0.01/test), data health checks, and path-filtered universe tests show operational maturity.

7. **Session-scoped graph fixtures**: Building the test universe graph once per session (not per test) is the right trade-off for speed vs isolation.

### 9.2 Weaknesses

1. **Under-marked tests**: Only 190 of 6,288 tests are marked `@pytest.mark.unit`. The remaining ~6,000 are unmarked, making targeted layer execution unreliable. The `markers` configuration defines `unit`, `integration`, `contract`, `golden`, `structure`, `semantic`, etc. but they're sparsely applied.

2. **Coverage threshold too low**: The `fail_under = 59` is far below the 80% target. The comment explains the regression (archetype framework removal deleted well-tested code), but no recovery plan or per-module enforcement exists.

3. **No per-module coverage enforcement**: All coverage is measured globally. High-coverage modules (MCP tools at 100%) subsidize low-coverage modules (contracts at 50%, auth at 49%). Branch coverage is enabled but not reported per-module in CI.

4. **Duplicated mock data**: `MockProcessedKill` is defined 3 times across conftest files with slight variations. Notification test fixtures use factory functions returning `MagicMock` while interest engine tests use proper dataclasses. This inconsistency hinders maintenance.

5. **Thin ESI fixture externalization**: Only 5 ESI response files exist in `tests/fixtures/esi/`, but ESI responses are defined in at least 6 different conftest files as inline fixtures. The ESI fixture loading infrastructure is good but underutilized.

6. **Contract tests don't intercept real calls**: The contract test layer records calls to `MockMCPTracker` manually rather than intercepting actual skill-to-dispatcher invocations. This means contracts validate test expectations, not production behavior.

7. **No pytest-randomly or pytest-ordering**: Tests may have hidden ordering dependencies that are masked by the deterministic default collection order. The singleton reset fixture mitigates but doesn't eliminate this risk.

8. **Coverage not uploaded to external service**: The CI generates `--cov-report=xml` but doesn't upload to Codecov or similar. This means no PR-level coverage diff reporting.

9. **No `conftest.py` for top-level test files**: There are ~30 test files at the `tests/` root level (e.g., `test_auth.py`, `test_client.py`, `test_market_database.py`) that aren't organized into subdirectories. These appear to be older tests predating the directory structure.

### 9.3 Determinism Issues

1. **`datetime.now()` in notification fixtures**: `tests/services/redisq/notifications/conftest.py::make_processed_kill` uses `datetime.now(tz=timezone.utc)` as a default argument. This creates non-deterministic test data unless `frozen_time` is active for the calling test. Similarly, `tests/services/redisq/interest_v2/signals/conftest.py::MockProcessedKill.kill_time` uses `datetime.now(timezone.utc)` as a default factory.

2. **Corp jobs fixture uses real time**: `tests/commands/conftest.py::mock_corp_jobs_response` computes `future_end` using `datetime.now(timezone.utc) + timedelta(hours=2)`, creating non-reproducible fixture data.

3. **No seed for graph layout**: `igraph.Graph` layout operations (if used) may produce different results across platforms or library versions. The current tests use topology (connectivity) rather than layout, so this is low-risk.

### 9.4 Missing Coverage

1. **ESI pagination**: No tests for paginated ESI responses (multi-page with `X-Pages` header)
2. **ESI error bodies**: No tests for non-JSON error responses (HTML maintenance pages, rate limit bodies)
3. **Concurrent access**: No tests for thread-safety of singleton access patterns
4. **WebSocket/SSE**: If real-time features use streaming, no test infrastructure exists
5. **Large response handling**: No tests for very large killmail lists, order books, or asset inventories
6. **Database migration tests**: Killmail store has `test_migrations.py` but no similar tests for other SQLite stores
7. **Configuration validation**: No tests for invalid `userdata/config.json` structures (missing fields, wrong types)
8. **Persona loading regression**: No tests for the full persona loading pipeline (staleness check, compiled artifact loading, overlay resolution)

---

## 10. Actionable Recommendations

### 10.1 High Priority (Address in Next Sprint)

**R1. Fix non-deterministic fixtures**

Files to change:
- `/home/aurelien/git/aria/tests/services/redisq/notifications/conftest.py`: Replace `datetime.now()` default in `make_processed_kill` with a fixed datetime constant.
- `/home/aurelien/git/aria/tests/services/redisq/interest_v2/signals/conftest.py`: Replace `datetime.now()` default factory in `MockProcessedKill.kill_time` with a fixed value.
- `/home/aurelien/git/aria/tests/commands/conftest.py`: Replace `datetime.now()` in `mock_corp_jobs_response` with a fixed future datetime.

```python
# Instead of:
kill_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

# Use:
FIXED_KILL_TIME = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
kill_time: datetime = field(default_factory=lambda: FIXED_KILL_TIME)
```

**R2. Consolidate `MockProcessedKill` into a single shared module**

Create `/home/aurelien/git/aria/tests/services/redisq/_shared_fixtures.py` with a single canonical `MockProcessedKill` dataclass, then import it in the three conftest files that currently define it independently. The canonical version should include all fields (`hull_value`, `kill_time`) with the signals conftest's version as the base.

**R3. Raise coverage threshold with per-module enforcement**

Add module-specific coverage targets to `pyproject.toml`:
```toml
[tool.coverage.report]
fail_under = 65  # Raise incrementally toward 80%
```

And add a CI step that checks critical modules:
```bash
uv run pytest --cov=src/aria_esi/mcp --cov-fail-under=75
uv run pytest --cov=src/aria_esi/core --cov-fail-under=60
```

### 10.2 Medium Priority (Address in Next Milestone)

**R4. Add `pytest-randomly` for ordering detection**

Add to `[dependency-groups] dev`:
```toml
"pytest-randomly>=3.15.0",
```

This will randomize test order on each run, surfacing hidden ordering dependencies. The `--randomly-seed` flag ensures reproducibility when failures occur. The singleton reset fixture should handle most issues, but this validates the assumption.

**R5. Mark tests consistently**

Apply markers systematically:
- All tests in `tests/core/`, `tests/models/`, `tests/universe/`, and root-level test files should get `@pytest.mark.unit`
- All tests in `tests/mcp/` should get either `unit` or `integration` based on whether they use `mock_server` vs `integration_server`
- This can be done via `pytestmark` at the module level:
  ```python
  pytestmark = pytest.mark.unit
  ```

**R6. Centralize ESI fixture data**

Move inline ESI response fixtures from conftest files into `tests/fixtures/esi/`:
- `character/skills.json` (from `tests/fitting/conftest.py::mock_esi_skills_response`)
- `character/standings.json` (from `tests/commands/conftest.py::mock_standings_response`)
- `market/orders.json` (from `tests/commands/conftest.py::mock_orders_response`)
- `corporation/info.json` (from `tests/commands/conftest.py::mock_corporation_info`)
- `corporation/wallets.json`, `assets.json`, `blueprints.json`, `jobs.json`

Then update conftest fixtures to use `load_esi_fixture()`.

**R7. Add coverage upload to CI**

Add to `.github/workflows/ci.yml` after the test step:
```yaml
- name: Upload coverage
  uses: codecov/codecov-action@v4
  with:
    files: coverage.xml
    fail_ci_if_error: false
```

### 10.3 Low Priority (Backlog)

**R8. Add ESI pagination contract tests**

Create `tests/core/test_pagination.py` testing the client's handling of:
- `X-Pages: 1` (single page)
- `X-Pages: 5` (multi-page with sequential fetches)
- `X-Pages: 0` or missing header (edge case)

**R9. Add fitting tolerance helpers**

Add to root conftest:
```python
def approx_dps(value: float, rel: float = 1e-2) -> pytest.approx:
    """pytest.approx for DPS comparisons (2% tolerance for rounding)."""
    return pytest.approx(value, rel=rel)

def approx_resist(value: float, abs: float = 0.01) -> pytest.approx:
    """pytest.approx for resist percentages (1% absolute tolerance)."""
    return pytest.approx(value, abs=abs)
```

**R10. Add persona loading integration test**

Create `tests/integration/test_persona_loading.py` that exercises:
1. Profile with `persona_context.branch` matching `faction`
2. Profile with stale context (mismatch)
3. Missing compiled artifact fallback
4. Overlay resolution with fallback path

**R11. Organize root-level test files**

Move the ~30 root-level test files into appropriate subdirectories:
- `test_auth.py`, `test_core_auth.py`, `test_core_keyring.py` -> `tests/core/`
- `test_client.py`, `test_retry.py` -> `tests/core/`
- `test_market_*.py` -> `tests/mcp/market/` or `tests/services/market/`
- `test_formatters.py`, `test_constants.py` -> `tests/core/`

---

## 11. Proposed Test File Structure

The current structure is mostly well-organized. The primary proposed change is organizing root-level test files:

```
tests/
├── conftest.py                     # Root: shared fixtures (no changes needed)
├── fixtures/
│   └── esi/                        # Expand: add 10+ more ESI response files
├── core/                           # Move root-level core tests here
│   ├── test_auth.py                # <-- from tests/test_auth.py
│   ├── test_client.py              # <-- from tests/test_client.py
│   ├── test_config.py
│   ├── test_constants.py           # <-- from tests/test_constants.py
│   ├── test_data_integrity.py
│   ├── test_formatters.py          # <-- from tests/test_formatters.py
│   ├── test_freshness.py
│   ├── test_keyring_backend.py     # <-- from tests/test_keyring_backend.py
│   ├── test_logging.py
│   ├── test_path_security.py
│   └── test_retry.py
├── services/
│   ├── redisq/
│   │   ├── _shared_fixtures.py     # NEW: consolidated MockProcessedKill
│   │   ├── ...
│   └── market/                     # NEW: market-specific service tests
│       ├── test_cache.py           # <-- from tests/test_market_cache.py
│       ├── test_database.py        # <-- from tests/test_market_database.py
│       ├── test_clipboard.py       # <-- from tests/test_market_clipboard.py
│       └── test_nearby.py          # <-- from tests/test_market_nearby.py
├── skills/
│   ├── ground_truth/               # Populate with actual ground truth data
│   └── ...
└── integration/
    ├── test_persona_loading.py     # NEW: persona loading pipeline test
    └── ...
```

---

## 12. Verification Commands

```bash
# Run all default tests
uv run pytest -n auto

# Run specific layers
uv run pytest -m unit -n auto
uv run pytest -m integration
uv run pytest -m contract
uv run pytest -m golden
uv run pytest -m structure

# Run with coverage report
uv run pytest --cov --cov-report=html --cov-report=term-missing

# Run benchmarks (requires real universe graph)
uv run pytest -m benchmark --benchmark-enable --no-cov

# Run semantic tests (requires ANTHROPIC_API_KEY)
ANTHROPIC_API_KEY=sk-... uv run pytest -m semantic --no-cov

# Run tier 1 skill integration tests
uv run pytest tests/skills/test_integration.py -m tier1 -v --no-cov

# Run tier 2 skill integration tests (weekly CI)
ANTHROPIC_API_KEY=sk-... uv run pytest tests/skills/test_integration.py -m tier2 -v --no-cov

# Update snapshots
uv run pytest -m golden --snapshot-update

# Check fixture loading
uv run pytest tests/skills/test_structure.py -m structure -v --no-cov

# Lint and type check
uv run ruff check src .claude/scripts
uv run mypy

# Validate skill preflight
uv run python .claude/scripts/aria-skill-preflight.py --all
```

---

## 13. Summary Assessment

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Runner configuration | A | pytest + xdist + cov + asyncio + benchmark well-configured |
| Fixture system | A- | Excellent factories, good ESI loading, but thin externalized data |
| Mocking strategy | A- | Correct boundaries, domain-aware, but some duplication |
| Markers & selection | C+ | Markers defined but sparsely applied; layer execution unreliable |
| Snapshot/golden | B | Infrastructure exists (syrupy), but only 1 active snapshot |
| Coverage tooling | B- | Enabled with branch, but threshold too low, no per-module, no upload |
| Determinism | B | Time + RNG well-handled; 3 non-deterministic fixtures found |
| CI integration | A- | Multi-workflow, multi-Python, path-filtered; missing coverage upload |
| Edge case coverage | A- | Security and graph edge cases thorough; ESI edge cases thin |
| Skill testing framework | A | 3-layer architecture with schemas, fixtures, and G-Eval |

**Overall Grade: B+**

The testing harness is architecturally sound and demonstrates mature engineering practices (singleton reset, domain-aware tolerances, multi-tier skill validation). The primary gaps are operational: under-applied markers, low coverage thresholds, non-deterministic time defaults, and duplicated mock definitions. The recommended fixes are incremental and low-risk.
