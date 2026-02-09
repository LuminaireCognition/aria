# Test Infrastructure & Quality Assurance Review

**Reviewer:** Gemini 3 Pro
**Date:** 2026-01-31
**Scope:** `tests/`, `conftest.py`, `pyproject.toml`

## Executive Summary

The ARIA test infrastructure is robust, well-organized, and utilizes modern Python testing tools (`pytest`, `time-machine`, `syrupy`). The separation of unit and integration tests is clear. The fixture strategy in `conftest.py` is comprehensive, particularly for mocking external ESI data and handling time-dependent logic.

However, the testing strategy relies heavily on a "global reset" pattern to manage singletons, which poses a maintenance risk. Additionally, the baseline coverage target (54%) leaves significant room for improvement before a public release.

## Strengths (Brief)

*   **Fixture Architecture:** `tests/conftest.py` provides excellent centralized fixtures for ESI data (`esi_fixture_loader`), time freezing (`frozen_time`), and reproducible RNG (`seeded_rng`).
*   **Integration Testing:** The `integration_server` fixture allows for realistic testing of the MCP server lifecycle against a sample universe graph.
*   **Tooling:** proper configuration of `ruff`, `mypy` (with a phased adoption plan), and `pytest-cov` in `pyproject.toml`.

## Critical Findings & Recommendations

### 1. Singleton State Management
**Risk:** High
**Observation:** The `reset_all_singletons` fixture in `conftest.py` manually resets over 15 different modules/services. This "God fixture" approach is fragile; if a developer adds a new singleton state but forgets to add it to this reset list, tests will silently leak state, leading to flaky "heisenbugs."
**Recommendation:**
*   **Refactor to Dependency Injection:** Where possible, move away from global singletons to instance-based services passed via context.
*   **Registry Pattern:** If singletons are necessary, implement a centralized registry that tracks them and provides a unified `reset_all()` method, rather than hardcoding imports in `conftest.py`.

### 2. Test Coverage & Safety
**Risk:** Medium
**Observation:** The `fail_under` setting in `pyproject.toml` is 54%. While `mcp` tools have higher coverage, core modules (`auth`, `client`) are listed as having lower coverage.
**Recommendation:**
*   **Targeted Increase:** Raise the minimum coverage threshold for critical paths (especially `aria_esi.core` and `aria_esi.services`) to at least 80% before release.
*   **Network Isolation:** Ensure `pytest-socket` or similar is used to strictly forbid network requests in unit tests, preventing accidental API hits.

### 3. Database Testing Strategy
**Risk:** Low
**Observation:** `test_threat_cache.py` creates a temporary SQLite file for testing. While functional, ensuring these are cleaned up (via `tempfile.TemporaryDirectory`) is critical to avoid disk clutter on CI. The current implementation uses `tempfile`, which is correct.
**Recommendation:**
*   **In-Memory DB:** Consider using `:memory:` SQLite databases for unit tests where persistence isn't explicitly being tested, to speed up execution.

### 4. Legacy Artifacts
**Risk:** Low
**Observation:** `conftest.py` and `server.py` contain fallback logic for `universe.pkl` (legacy) vs `universe.universe`.
**Recommendation:**
*   **Deprecate:** Explicitly mark the pickle support for removal in the next minor version to clean up the codebase.

## Action Plan
1.  **Audit Singletons:** Review the codebase for any singletons missing from `reset_all_singletons`.
2.  **Increase Core Coverage:** Prioritize writing unit tests for `aria_esi.core.auth` and `aria_esi.core.client`.
3.  **Strict Network Blocking:** specific configuration to fail tests that attempt real network connections.
