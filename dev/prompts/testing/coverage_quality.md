<!-- owner: @anthropic/aria -->
<!-- last_reviewed: 2026-02-10T00:00:00Z -->
<!-- depends_on: [] -->
<!-- adjacent_prompts: ["testing/test_harness.md", "architecture/mcp_architecture.md"] -->

# Test Coverage Adequacy Review

Review this repository from the perspective of a **senior QA engineer** evaluating test coverage adequacy, gap analysis, and coverage tooling.

## Scope

**In-scope (coverage quality):**

* Line and branch coverage metrics and enforcement
* Coverage gap analysis: untested modules, functions, and branches
* Coverage tool configuration (`pyproject.toml`, CI integration)
* Test-to-source mapping: do tests exist for all production modules?
* Critical path coverage: are error paths, edge cases, and boundary conditions tested?
* Coverage trend: is coverage improving or regressing across recent changes?

**Out-of-scope:**

* Legal attribution and licensing text quality (see `security/supply_chain_and_dependencies.md`)
* Test harness infrastructure (see `testing/test_harness.md`)

## Adjacent Prompts

* `testing/test_harness.md` — test infrastructure and harness; this prompt evaluates coverage adequacy
* `architecture/mcp_architecture.md` — MCP contracts; this prompt checks if MCP paths are tested

## Deep-Dive Triggers

This prompt is selected for deep-dive when changes touch:

* `tests/**`
* `pyproject.toml`
* `.github/workflows/**`

## How to Run the Review

Examine test coverage:

* Map production modules under `src/` to corresponding test files under `tests/`
* Identify production modules with no corresponding tests
* Check coverage configuration and thresholds in `pyproject.toml`
* Evaluate whether CI enforces coverage gates
* Review recent changes for coverage regressions

## Deliverables

For each finding include:

* Severity (Critical / High / Medium / Low / Info)
* File path and line range
* What is wrong
* Why it matters
* Specific fix

Produce:

1. Coverage inventory (modules tested vs untested)
2. Coverage gap findings
3. Coverage tooling and enforcement assessment
4. Critical path coverage assessment
5. Actionable recommendations ranked by priority

## Output

Emit findings in `prompt_results.schema.v1`.
