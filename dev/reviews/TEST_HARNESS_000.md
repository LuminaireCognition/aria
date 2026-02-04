# ARIA Test Harness Review

**Date:** 2026-01-24
**Scope:** Testing infrastructure (harness), not business logic
**Status:** Initial assessment

---

## 1. Current Harness Inventory

### 1.1 Test Layout and Naming Conventions

**Directory Structure:**
```
tests/
├── conftest.py              # Root fixtures (740 lines)
├── benchmarks/              # Performance tests (excluded by default)
│   ├── conftest.py
│   └── bench_*.py
├── mcp/                     # MCP server and dispatcher tests
│   ├── conftest.py          # Mock universe factory
│   └── test_*.py            # 36+ test files
├── commands/                # CLI command tests
│   ├── conftest.py          # Mock ESI responses
│   └── test_*.py
├── fitting/                 # Ship fitting module tests
│   ├── conftest.py          # EOS mocking, parsed fit fixtures
│   └── test_*.py
├── skills/                  # Golden/snapshot tests
│   ├── conftest.py          # Volatile field normalization
│   ├── __snapshots__/       # Syrupy snapshot files
│   └── test_skill_outputs.py
├── integration/             # End-to-end tests
│   ├── conftest.py
│   └── test_*.py
├── core/                    # Core module tests
│   └── test_*.py
├── services/                # Service layer tests
│   └── test_*.py
├── universe/                # Graph and builder tests
│   └── test_*.py
└── test_*.py                # Root-level tests (30+)
```

**Naming Conventions:**
- Test files: `test_*.py`, `bench_*.py`
- Test classes: `Test*`
- Test functions: `test_*`
- Fixtures: lowercase with underscores, descriptive names

**Test Count:** ~1,104 tests (1,123 collected, 19 deselected by benchmark marker)

### 1.2 Fixture Location and Loading

**Root `conftest.py` (tests/conftest.py):**
- Path fixtures (`project_root`, `scripts_dir`, `test_data_dir`)
- Mock credentials (`mock_credentials_data`, `credentials_file`)
- Mock ESI responses (system, character, location, wallet, killmail)
- Mock ESI client
- Time fixtures (`fixed_datetime`, `mock_utc_now`)
- Argument namespace fixtures for CLI commands
- Universe fixtures (`sample_cache_data`, `sample_graph`, `mock_server`)
- **Singleton reset** (`reset_all_singletons`) - autouse fixture resetting 20+ singletons

**Domain-specific conftest files:**
- `tests/mcp/conftest.py`: `create_mock_universe()` factory, standard/extended/edge-case universes
- `tests/fitting/conftest.py`: `ParsedFit` fixtures, EFT strings, mock EOS module, market DB
- `tests/commands/conftest.py`: Mock authenticated clients, ESI response fixtures
- `tests/skills/conftest.py`: `normalize_volatile_fields()` for snapshot stability
- `tests/integration/conftest.py`: `integration_server` with full MCP stack

### 1.3 Time/Mocks/Random Handling

**Time Mocking:**
- `fixed_datetime` fixture: Returns `datetime(2026, 1, 15, 18, 30, 0, tzinfo=timezone.utc)`
- `mock_utc_now` fixture: Patches `aria_esi.core.formatters.get_utc_now`
- Ad-hoc patching: `patch("module.time.time", return_value=now)` in specific tests

**No global time-freezing library** (freezegun/time-machine) in use.

**Mocking Strategy:**
- `MagicMock` with `spec=` for type safety
- `AsyncMock` for async operations
- `patch()` context managers for runtime patching
- Factory functions for complex objects (`create_mock_universe`, `create_mock_fit`)

**Randomness:**
- **No seeded RNG fixture exists** - potential determinism gap

### 1.4 Markers and CI Selection

**Defined Markers (pyproject.toml):**
| Marker | Description | CI Behavior |
|--------|-------------|-------------|
| `unit` | Fast tests, no external dependencies | Included |
| `integration` | Tests that may require mocks | Included |
| `slow` | Network calls | Included (no exclusion) |
| `benchmark` | Performance benchmarks | **Excluded by default** (`-m not benchmark`) |
| `golden` | Snapshot tests via syrupy | Included |
| `httpx` | Tests requiring pytest-httpx | Included |

**CI Configuration (.github/workflows/ci.yml):**
- Multi-version matrix: Python 3.10, 3.11, 3.12, 3.13
- Dependencies: `uv sync --all-extras`
- Coverage: `pytest --cov --cov-report=xml`
- Upload to Codecov on Python 3.12

**Missing CI Selection:**
- No `@pytest.mark.unit` selective run
- No `@pytest.mark.integration` selective run
- All non-benchmark tests run together

---

## 2. Test Layer Classification

### 2.1 Unit Tests

**Current Status:** ✅ Supported

**Location:** Spread across `tests/`, `tests/core/`, `tests/commands/`, `tests/fitting/`

**Mock Boundaries:**
- ESI client: Mocked via `MagicMock(spec=ESIClient)`
- Filesystem: Uses `tmp_path` fixture
- Time: Patched via `mock_utc_now` fixture

**Gaps:**
- No explicit `@pytest.mark.unit` applied consistently
- Unit tests mixed with integration tests in same files

### 2.2 Integration Tests

**Current Status:** ⚠️ Partially Supported

**Location:** `tests/integration/`, `tests/mcp/`

**Mock Boundaries:**
- ESI responses mocked, dispatcher + validation real
- Full MCP server stack tested via `integration_server` fixture

**Gaps:**
- Integration tests not isolated with marker for selective runs
- No MCP dispatcher → ESI client chain end-to-end tests with HTTP mocking

### 2.3 Contract Tests

**Current Status:** ⚠️ Limited

**What Exists:**
- Pydantic model validation in `tests/mcp/test_models.py`
- Response schema validation happens implicitly via Pydantic

**Gaps:**
- No explicit ESI response schema drift detection
- No MCP tool schema contract tests
- No pinned ESI response examples compared against schema

### 2.4 Golden/Snapshot Tests

**Current Status:** ✅ Supported

**Location:** `tests/skills/`

**Infrastructure:**
- Syrupy 4.0+ via `pytest-syrupy`
- Snapshot files: `tests/skills/__snapshots__/test_skill_outputs.ambr`
- Normalization: `normalize_volatile_fields()` replaces timestamps with `<NORMALIZED>`

**Gaps:**
- Only one snapshot test file exists
- No route output snapshots
- No market report snapshots
- No explicit `@pytest.mark.golden` usage found in tests

---

## 3. Findings

### 3.1 Strengths

1. **Comprehensive singleton reset** - The `reset_all_singletons()` autouse fixture resets 20+ module-level singletons between tests, preventing cross-test contamination.

2. **Mock universe factory** - `create_mock_universe()` enables precise control over topology for testing edge cases (disconnected graphs, single-system universes, security boundaries).

3. **Fixture hierarchy** - Well-organized conftest files with domain-specific fixtures (fitting, MCP, commands).

4. **Coverage tooling** - Branch coverage enabled, 45% threshold enforced, Codecov integration.

5. **Syrupy snapshot infrastructure** - Modern snapshot testing with volatile field normalization.

6. **Type-safe mocks** - Consistent use of `MagicMock(spec=...)` for interface validation.

7. **Multi-Python version CI** - Tests run against 3.10, 3.11, 3.12, 3.13.

### 3.2 Weaknesses/Risks

1. **No `tests/fixtures/esi/` directory** - ESI fixtures are inline in conftest files, not centralized. This makes it harder to:
   - Share fixtures across tests
   - Document scenario coverage
   - Update fixtures when ESI changes

2. **No fixture capture workflow** - No tooling for capturing real ESI responses and anonymizing them.

3. **No time-freezing library** - Time mocking is inconsistent; some tests use `fixed_datetime` fixture, others use ad-hoc `patch()` calls.

4. **No randomness control** - No `seeded_rng` fixture; tests relying on random behavior may be non-deterministic.

5. **Optional dependency errors** - 7 test files fail to collect when `mcp` module is not installed, despite being in `[project.optional-dependencies]`.

6. **Marker inconsistency** - Markers like `unit`, `integration`, `slow` are defined but rarely applied to tests.

7. **No floating-point tolerance helpers** - Security status comparisons (0.45 threshold) could fail due to float precision.

8. **Coverage threshold too low** - 45% is below the 80% target specified in the review prompt.

### 3.3 Determinism Issues

1. **Time-dependent tests** - Some tests use `time.time()` instead of patched time, making them sensitive to execution timing.

2. **Dict ordering** - Python 3.7+ guarantees dict ordering, but comparison of large structures may differ if constructed differently.

3. **No stable sort enforcement** - Output comparisons may fail if iteration order varies.

4. **Cache age calculations** - Tests comparing cache ages may be flaky if executed slowly.

### 3.4 Missing Edge Case Support

**Data Edge Cases:**
- ❌ Empty results (no orders/kills) - limited fixture support
- ❌ Maximum results & pagination - not tested
- ✅ Unicode names - not explicitly tested but Pydantic handles
- ⚠️ Null/optional fields - covered in some response mocks

**Temporal Edge Cases:**
- ❌ Cache expiry during request
- ⚠️ Skill queue states (empty/paused/active) - partially covered
- ❌ Market orders expiring between fetch/display

**Security/System Edge Cases:**
- ⚠️ 0.0 vs -0.0 vs -1.0 security - `nullsec_systems` set exists
- ❌ Wormholes (no security) - not modeled
- ❌ Thera / special systems - not in test universes

---

## 4. Domain-Aware Harness Checklist

### 4.1 ESI Integration

| Capability | Status | Notes |
|------------|--------|-------|
| Token refresh simulation | ❌ | No fixtures for refresh flows |
| Rate limit handling (420/backoff) | ⚠️ | `pytest-httpx` available but no 420 tests |
| Expired/revoked token handling | ❌ | No auth failure fixtures |
| Schema drift detection | ❌ | No contract tests against ESI schemas |

### 4.2 MCP Dispatchers

| Capability | Status | Notes |
|------------|--------|-------|
| Action routing correctness | ✅ | Table-driven tests in `test_dispatchers.py` |
| Parameter validation before ESI | ⚠️ | Tested but not with call ordering assertions |
| Response truncation/limit logic | ⚠️ | Some tests exist |
| Error propagation | ✅ | `InvalidParameterError` tests exist |

### 4.3 EVE Mechanics (Harness Requirements)

| Capability | Status | Notes |
|------------|--------|-------|
| Floating-point tolerance patterns | ❌ | No reusable helpers |
| Deterministic SDE calculations | ✅ | Real SDE data used |

### 4.4 Persona/Skills

| Capability | Status | Notes |
|------------|--------|-------|
| Missing overlay/persona file simulation | ❌ | No `tmp_persona_fs` fixture |
| Context staleness detection | ❌ | Not tested |
| Skill preflight validation | ❌ | Not mocked for testing |

---

## 5. Actionable Recommendations

### 5.1 High Priority

#### R1: Create `tests/fixtures/esi/` Directory Structure

```
tests/fixtures/esi/
├── README.md                    # Documents each fixture's scenario
├── character/
│   ├── location.json            # Character location response
│   ├── skills.json              # Skills endpoint response
│   └── wallet.json              # Wallet balance
├── market/
│   ├── orders_empty.json        # Empty market response
│   ├── orders_paginated.json    # Full page requiring pagination
│   └── prices.json              # Fuzzwork prices response
├── killmails/
│   └── recent_loss.json         # Recent loss mail
└── universe/
    └── system_jita.json         # System info response
```

**Fixture loader helper (add to `tests/conftest.py`):**
```python
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "esi"

def load_esi_fixture(path: str) -> dict:
    """Load ESI fixture from tests/fixtures/esi/."""
    fixture_path = FIXTURES_DIR / path
    if not fixture_path.exists():
        raise FileNotFoundError(f"ESI fixture not found: {path}")
    return json.loads(fixture_path.read_text())
```

#### R2: Add Global Time-Freezing Fixture

**Install `time-machine` (lighter than freezegun):**
```toml
# pyproject.toml [project.optional-dependencies.dev]
"time-machine>=2.10.0",
```

**Create fixture:**
```python
# tests/conftest.py
import time_machine

@pytest.fixture
def frozen_time():
    """
    Freeze time globally to 2026-01-15 18:30:00 UTC.

    Usage:
        def test_something(frozen_time):
            assert datetime.now(timezone.utc) == frozen_time
    """
    freeze_at = datetime(2026, 1, 15, 18, 30, 0, tzinfo=timezone.utc)
    with time_machine.travel(freeze_at, tick=False):
        yield freeze_at
```

#### R3: Add Seeded RNG Fixture

```python
# tests/conftest.py
import random

@pytest.fixture
def seeded_rng():
    """
    Provide a seeded random generator for deterministic tests.

    Returns:
        random.Random instance seeded to 42
    """
    rng = random.Random(42)
    return rng

@pytest.fixture(autouse=True)
def seed_global_random():
    """Seed global random for test determinism."""
    random.seed(42)
    yield
    # No need to reset - next test will re-seed
```

#### R4: Add Floating-Point Tolerance Helpers

```python
# tests/conftest.py
from typing import Any
import math

def approx_sec(value: float, rel: float = 1e-4) -> Any:
    """
    Approximate equality for security status values.

    EVE security status is displayed to 2 decimal places.
    """
    return pytest.approx(value, rel=rel)

def assert_highsec(sec: float) -> None:
    """Assert system is highsec (>= 0.45)."""
    assert sec >= 0.45 - 1e-6, f"Expected highsec, got {sec}"

def assert_lowsec(sec: float) -> None:
    """Assert system is lowsec (0.0 < sec < 0.45)."""
    assert 0.0 < sec < 0.45, f"Expected lowsec, got {sec}"
```

### 5.2 Medium Priority

#### R5: Apply Markers Consistently

**Create marker application script (`.claude/scripts/apply_test_markers.py`):**

```python
#!/usr/bin/env python3
"""Apply appropriate markers to test files based on location."""

MARKER_RULES = {
    "tests/unit/": "unit",
    "tests/integration/": "integration",
    "tests/benchmarks/": "benchmark",
    "tests/skills/": "golden",
}

# Apply @pytest.mark.<marker> to test files in each directory
```

**Target directory structure migration:**
```
tests/
├── unit/           # @pytest.mark.unit
├── integration/    # @pytest.mark.integration
├── contract/       # @pytest.mark.contract (new)
├── golden/         # @pytest.mark.golden
└── benchmarks/     # @pytest.mark.benchmark
```

#### R6: Add Contract Test Infrastructure

**Create `tests/contract/` with:**

```python
# tests/contract/test_esi_schemas.py
"""Contract tests for ESI response schemas."""

import pytest
from pydantic import ValidationError

from aria_esi.models.esi import CharacterLocation, CharacterSkills

class TestESIContracts:
    """Verify ESI response fixtures match expected schemas."""

    def test_location_response_schema(self, load_esi_fixture):
        """Verify location response matches CharacterLocation model."""
        data = load_esi_fixture("character/location.json")
        # Should not raise ValidationError
        location = CharacterLocation(**data)
        assert location.solar_system_id > 0

    def test_skills_response_schema(self, load_esi_fixture):
        """Verify skills response matches CharacterSkills model."""
        data = load_esi_fixture("character/skills.json")
        skills = CharacterSkills(**data)
        assert skills.total_sp >= 0
```

#### R7: Raise Coverage Threshold Incrementally

**Modify `pyproject.toml` with roadmap:**
```toml
[tool.coverage.report]
# Coverage roadmap:
# Phase 1 (current): 45% baseline
# Phase 2: 55% after unit test expansion
# Phase 3: 65% after integration tests
# Phase 4: 75% after contract tests
# Target: 80%+ with exclusions for CLI shims
fail_under = 45
```

### 5.3 Low Priority

#### R8: Handle Optional Dependency Test Isolation

**Add pytest skip for optional dependencies:**
```python
# tests/mcp/conftest.py
import pytest

try:
    import mcp
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

collect_ignore = []
if not HAS_MCP:
    collect_ignore.extend([
        "test_tools_route.py",
        "test_dispatchers.py",
        # ... other MCP-dependent tests
    ])
```

#### R9: Add ESI Fixture Capture Tool

**Create `scripts/capture_esi_fixture.py`:**
```python
#!/usr/bin/env python3
"""
Capture ESI response and anonymize for fixtures.

Usage:
    uv run python scripts/capture_esi_fixture.py character/location
"""

import sys
import json
import re

def anonymize(data: dict) -> dict:
    """Replace character/corp IDs with stable test values."""
    text = json.dumps(data)
    # Replace character IDs with test ID
    text = re.sub(r'"character_id":\s*\d+', '"character_id": 12345678', text)
    text = re.sub(r'"corporation_id":\s*\d+', '"corporation_id": 98000001', text)
    return json.loads(text)

if __name__ == "__main__":
    # Implementation: call aria-esi --debug, capture, anonymize, save
    pass
```

---

## 6. Proposed Test File Structure

**Target structure mirroring `src/aria_esi/`:**

```
tests/
├── conftest.py                  # Shared fixtures, singleton reset
├── fixtures/
│   ├── esi/                     # ESI response fixtures (R1)
│   │   └── README.md
│   └── sde/                     # SDE query result fixtures
│
├── unit/                        # @pytest.mark.unit
│   ├── core/
│   │   ├── test_auth.py
│   │   ├── test_client.py
│   │   └── test_formatters.py
│   ├── commands/
│   │   └── test_*.py
│   ├── fitting/
│   │   └── test_*.py
│   └── services/
│       └── test_*.py
│
├── integration/                 # @pytest.mark.integration
│   ├── conftest.py
│   ├── test_mcp_protocol.py
│   ├── test_dispatcher_chain.py
│   └── test_end_to_end.py
│
├── contract/                    # @pytest.mark.contract (new)
│   ├── test_esi_schemas.py
│   └── test_mcp_tool_schemas.py
│
├── golden/                      # @pytest.mark.golden
│   ├── conftest.py              # Volatile normalization
│   ├── __snapshots__/
│   ├── test_route_outputs.py
│   ├── test_skill_outputs.py
│   └── test_market_reports.py
│
└── benchmarks/                  # @pytest.mark.benchmark
    ├── conftest.py
    └── bench_*.py
```

---

## 7. Recommended Standard Fixtures

### 7.1 `frozen_time`

```python
@pytest.fixture
def frozen_time():
    """Freeze all time sources to 2026-01-15 18:30:00 UTC."""
    # See R2 implementation
```

### 7.2 `esi_fixture_loader`

```python
@pytest.fixture
def esi_fixture_loader():
    """Load ESI fixtures from tests/fixtures/esi/."""
    def _load(path: str) -> dict:
        return load_esi_fixture(path)
    return _load
```

### 7.3 `seeded_rng`

```python
@pytest.fixture
def seeded_rng():
    """Provide deterministic random.Random(42)."""
    # See R3 implementation
```

### 7.4 `tmp_persona_fs`

```python
@pytest.fixture
def tmp_persona_fs(tmp_path: Path):
    """
    Create a mock persona filesystem for overlay testing.

    Structure:
        tmp_path/
        ├── userdata/
        │   ├── config.json
        │   └── pilots/
        │       └── 12345678/
        │           └── profile.md
        └── personas/
            └── aria/
                └── skill-overlays/
    """
    # Create directories
    userdata = tmp_path / "userdata"
    userdata.mkdir()
    (userdata / "config.json").write_text('{"active_pilot": "12345678"}')

    pilots = userdata / "pilots" / "12345678"
    pilots.mkdir(parents=True)
    (pilots / "profile.md").write_text("# Test Pilot\n")

    personas = tmp_path / "personas" / "aria" / "skill-overlays"
    personas.mkdir(parents=True)

    return tmp_path
```

---

## 8. Marker Taxonomy and CI Selection

### 8.1 Marker Definitions

```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "unit: Fast isolated tests (<100ms), no I/O, mock all boundaries",
    "integration: Tests with real dispatcher chains, mock ESI only",
    "contract: Schema validation tests for ESI and MCP interfaces",
    "golden: Snapshot/output format tests using syrupy",
    "slow: Tests that take >1s (network, large data)",
    "benchmark: Performance tests (excluded by default)",
    "httpx: Tests requiring pytest-httpx HTTP mocking",
    "network: Tests that require real network (skip in CI)",
]
```

### 8.2 CI Selection Commands

```yaml
# .github/workflows/ci.yml
jobs:
  unit-tests:
    steps:
      - run: uv run pytest -m "unit" --cov

  integration-tests:
    steps:
      - run: uv run pytest -m "integration" --cov

  contract-tests:
    steps:
      - run: uv run pytest -m "contract"

  golden-tests:
    steps:
      - run: uv run pytest -m "golden"

  all-tests:
    steps:
      - run: uv run pytest -m "not benchmark and not network"
```

---

## 9. Coverage Configuration Recommendations

### 9.1 Aligned Targets

```toml
[tool.coverage.report]
# Target: 80% line coverage for src/aria_esi/ (excluding CLI shims)
# Current: 45% (baseline)
fail_under = 45

# Exclude unreachable code
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "@overload",
    "assert False",
    "raise AssertionError",
]

# Per-module targets (future)
# core/: 70%
# commands/: 60%
# mcp/: 75%
# fitting/: 65%
```

### 9.2 Branch Coverage Configuration

```toml
[tool.coverage.run]
branch = true

[tool.coverage.report]
# Branch coverage target: 70% for dispatchers
# Measure with: uv run pytest --cov --cov-branch
```

---

## 10. Determinism Plan

### 10.1 Time

- **Fixture:** `frozen_time` using `time-machine`
- **Scope:** Function-level (each test gets fresh freeze)
- **Standard time:** `2026-01-15T18:30:00Z`

### 10.2 Randomness

- **Fixture:** `seeded_rng` returning `random.Random(42)`
- **Autouse:** `seed_global_random()` seeds `random.seed(42)` per test
- **Policy:** Tests needing randomness must use `seeded_rng` fixture

### 10.3 Ordering

- **Dicts:** Stable in Python 3.7+; no action needed
- **Sets:** Convert to sorted lists before comparison
- **API responses:** Sort by primary key before snapshot
- **Helper:** `normalize_for_snapshot(data)` function

### 10.4 Tolerances

- **Security status:** `pytest.approx(value, rel=1e-4)`
- **ISK values:** `pytest.approx(value, rel=1e-6)`
- **Helper functions:** `approx_sec()`, `approx_isk()`

---

## 11. Verification Commands

### 11.1 Run All Tests

```bash
# Standard test run (excludes benchmarks)
uv run pytest

# Verbose with coverage
uv run pytest -v --cov --cov-report=term-missing

# Parallel execution
uv run pytest -n auto
```

### 11.2 Run by Marker

```bash
# Unit tests only
uv run pytest -m unit

# Integration tests
uv run pytest -m integration

# Golden/snapshot tests
uv run pytest -m golden

# Update snapshots
uv run pytest -m golden --snapshot-update
```

### 11.3 Coverage Reports

```bash
# HTML coverage report
uv run pytest --cov --cov-report=html
open htmlcov/index.html

# XML for CI upload
uv run pytest --cov --cov-report=xml

# Branch coverage
uv run pytest --cov --cov-branch --cov-report=term-missing
```

### 11.4 Benchmarks

```bash
# Run benchmarks (excluded by default)
uv run pytest -m benchmark --benchmark-only

# Compare benchmark results
uv run pytest -m benchmark --benchmark-compare
```

---

## 12. Deliverables Checklist

- [x] Written review of test harness with gap analysis
- [x] Suggested directory/file structure for tests and fixtures
- [x] Recommended standard fixtures: `frozen_time`, `esi_fixture_loader`, `seeded_rng`, `tmp_persona_fs`
- [x] Marker taxonomy and CI selection guidance
- [x] Coverage configuration recommendations aligned to targets
- [x] Determinism plan (time, randomness, ordering, tolerances)

---

## Appendix A: Quick Wins

**Immediate actions requiring minimal effort:**

1. **Add `time-machine` to dev dependencies** - 5 min
2. **Create `tests/fixtures/esi/` directory with README** - 10 min
3. **Add `seeded_rng` fixture to root conftest** - 5 min
4. **Add `approx_sec()` helper to conftest** - 5 min
5. **Document marker usage in pyproject.toml** - 10 min

## Appendix B: Test File Migration Priority

| Current Location | Target Location | Priority |
|------------------|-----------------|----------|
| `tests/test_formatters.py` | `tests/unit/core/test_formatters.py` | Medium |
| `tests/test_client.py` | `tests/unit/core/test_client.py` | Medium |
| `tests/mcp/test_*.py` | Keep (well-organized) | Low |
| `tests/skills/test_skill_outputs.py` | `tests/golden/test_skill_outputs.py` | Low |
| `tests/test_commands_esi.py` | `tests/integration/test_commands_esi.py` | Medium |
