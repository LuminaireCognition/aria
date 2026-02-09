# Testing Prompt: Review & Improve the Testing Harness for ARIA

## Scope

You are reviewing **the project’s testing harness** (not the business logic). The goal is to assess whether the test infrastructure reliably supports **unit, integration, contract, and golden** tests for an ARIA-style project (Python + MCP + ESI fixtures + static SDE data).

**In-scope (harness):**

* Test runner configuration (pytest/uv/nox/tox), `pyproject.toml`, `pytest.ini`, `conftest.py`
* Fixtures system (directory layout, fixture factories, ESI fixture loading helpers)
* Mocking/time-freezing strategy
* Markers, xfail/skip policies, and test selection strategy
* Snapshot/golden infrastructure (if present)
* Coverage tooling + thresholds + CI integration
* Determinism controls (ordering, randomness, floating-point tolerance)

**Out-of-scope:**

* Implementing new production features
* Rewriting the core route/pathfinding algorithms
* Replacing Pydantic models with mocks

## Layer Definition & Boundaries (must classify)

Classify the existing tests and harness capabilities into these layers, and identify gaps:

* **Unit:** Functions/classes isolated from I/O

  * Mock boundaries: Mock ESI client, current time, filesystem where needed
* **Integration:** MCP dispatcher → ESI client chain

  * Mock boundaries: Mock ESI responses only; keep dispatcher + validation real
* **Contract:** ESI response schemas + MCP tool schemas

  * Use real schemas; synthetic/fixture data; verify compatibility
* **Golden:** Output format/snapshots for routes/reports

  * Snapshot comparison with stable ordering and tolerances

For each layer, explain whether the harness supports it cleanly and how tests are selected (markers, folder structure, CI jobs).

## Domain-Aware Harness Checklist (mandatory review)

Evaluate whether the harness makes it easy to test ARIA-specific concerns:

### ESI Integration

* Token refresh support for long operations (test harness can simulate refresh flows)
* Rate limit handling (420/backoff) (harness has backoff control and deterministic waits)
* Expired/revoked token handling (fixtures or helpers for auth failure cases)
* Schema drift detection (contract tests pin expected response shapes)

### MCP Dispatchers

* Action routing correctness (table-driven tests and action coverage)
* Parameter validation happens before ESI calls (tests can assert call ordering)
* Response truncation/limit logic (tests cover large datasets deterministically)
* Error propagation to the model/client (structured errors preserved)

### EVE Mechanics (as harness requirements)

* Floating-point tolerance patterns exist (e.g., security status display)
* Ability to run deterministic calculations with real SDE data

### Persona/Skills

* Harness can simulate missing overlay/persona files (filesystem mocking)
* Harness can detect and test context staleness rules
* Skill preflight validation flows testable without network

## Mock Strategy Specification (verify adherence)

Confirm the harness enforces (or at least enables) the following:

### What to mock

* **ESI API responses** using fixtures from `tests/fixtures/esi/`
* **Current time** (for skill training, market age, cache expiry)
* **File system** (persona loading, overlay files)
* **Randomness** (seeded or injected RNG)

### What NOT to mock

* **SDE data**: use real static data
* **Route algorithms**: test actual pathfinding
* **Pydantic validation**: validate real schemas

If the harness currently violates these (e.g., mocking Pydantic or algorithms), propose concrete refactors.

## Edge Case Coverage Requirements (harness must support)

Assess whether the harness provides easy patterns for these edge cases:

### Data edge cases

* Empty results (no orders/kills)
* Maximum results & pagination
* Unicode names
* Null/optional fields

### Temporal edge cases

* Cache expiry during request
* Skill queue: empty vs paused vs active
* Market orders expiring between fetch and display

### Security/system edge cases

* 0.0 vs -0.0 vs -1.0
* Wormholes (no security)
* Thera / special systems

If missing, recommend fixture patterns and helper utilities.

## Determinism Requirements (must be enforceable)

Verify and/or implement harness-level determinism controls:

* **Freeze time**: all tests use fixed timestamps via a single fixture
* **Seed randomness**: global seed fixture and/or dependency injection
* **Stable ordering**: normalize/sort outputs before snapshot/compare
* **Tolerance bands**: reusable assertion helpers for floats

The review must identify non-deterministic tests and propose fixes.

## Fixture Generation Guidance (validate workflow)

Confirm the harness supports this workflow and document it:

1. Capture real ESI responses via `uv run aria-esi --debug`
2. Anonymize character/corp IDs
3. Store in `tests/fixtures/esi/{endpoint_name}.json`
4. Document scenario each fixture represents (README or inline docstrings)

If a tool/script is missing for anonymization or fixture capture, recommend minimal additions.

## Coverage Targets (evaluate tooling and enforcement)

Check the coverage tool configuration and how it is enforced locally + CI.

Targets:

* **Line coverage:** 80%+ for `src/aria_esi/` (exclude CLI entry shims)
* **Branch coverage:** 70%+ for dispatchers
* **MCP action coverage:** 100% (every action has ≥1 test)
* **ESI endpoint coverage:** all used endpoints at least happy path

Deliver a short gap analysis: what’s currently measured vs what should be measured.

## Output Format Requirements (deliverables)

Your output must be a structured report with:

1. **Current harness inventory**

   * Test layout and naming conventions
   * Where fixtures live; how they are loaded
   * How time/mocks/random are handled
   * Markers + CI selection

2. **Findings** (bullet list)

   * Strengths
   * Weaknesses/risks
   * Determinism issues
   * Missing edge cases and missing layer support

3. **Actionable recommendations**

   * Concrete file-level changes (e.g., `tests/conftest.py`, `pytest.ini`, helper modules)
   * Suggested fixture additions and test templates
   * Marker strategy (e.g., `@pytest.mark.integration`, `@pytest.mark.contract`, `@pytest.mark.golden`, `@pytest.mark.slow`, `@pytest.mark.network`)

4. **Proposed test file structure** that mirrors `src/` layout

5. **Verification commands**

   * `uv run pytest tests/...`
   * coverage command(s) used in the repo

## Deliverables Checklist

* [ ] Written review of the test harness with gap analysis
* [ ] Suggested directory/file structure for tests and fixtures
* [ ] Recommended standard fixtures: `frozen_time`, `esi_fixture_loader`, `seeded_rng`, `tmp_persona_fs`
* [ ] Marker taxonomy and CI selection guidance
* [ ] Coverage configuration recommendations aligned to targets
* [ ] Determinism plan (time, randomness, ordering, tolerances)

## Notes to Codex

* Prefer minimal, incremental improvements.
* Keep SDE and Pydantic validation real.
* Avoid adding new dependencies unless justified; if adding, specify why and how.
* Any recommended changes must be runnable in this repo with the existing tooling (`uv`, `pytest`).
