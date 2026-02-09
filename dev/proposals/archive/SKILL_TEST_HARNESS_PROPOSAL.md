# Skill Test Harness Proposal

**Status:** ✅ COMPLETE (2026-02-02)
**Completed:** All 3 layers (contract validation, structural validation, semantic evals)

> **Validation (2026-02-02):** Layer 3 (semantic evals) is COMPLETE:
> - `invoke_skill()` implemented using Tier 2 API invoker with mock tool support
> - `get_active_persona()` reads pilot config/registry/profile for persona context
> - `load_skill_fixture_mocks()` loads mock tool responses from YAML fixtures
> - G-Eval infrastructure in `tests/skills/test_semantic.py` with weighted scoring
> - Eval config at `tests/skills/evals/mission_brief.eval.yaml`
> - Ground truth at `tests/skills/ground_truth/missions/the_blockade_l4.json`
> - Infrastructure tests pass: `TestSemanticInfrastructure` (4 tests)

---

## Executive Summary

This proposal establishes a comprehensive test harness for ARIA's 43 slash commands (skills). The harness validates skill outputs against known-correct answers using a three-layer approach: contract validation, structural validation, and semantic validation.

**Problem:** The skill activity heatmap shows 10 skills with minimal testing (1-2 commits), and 15 skills with only 3-4 commits. Skills added in the Jan 29 batch (`/pi`, `/abyssal`, `/standings`, `/build-cost`, `/assets`) have no functional tests. Current test infrastructure validates preflight prerequisites but not output correctness.

**Recommendation:** Implement a test harness that combines JSON Schema validation for structure, fact extraction for data-heavy skills, and optional LLM-as-judge evaluation for narrative quality.

---

## Problem Statement

### Current Test Coverage Gaps

From `dev/reviews/SKILL_ACTIVITY_HEATMAP.md`:

| Risk Level | Skills | Examples |
|------------|--------|----------|
| High (1-2 commits) | 10 | `/pi`, `/abyssal`, `/watchlist`, `/orient`, `/gatecamp` |
| Medium (3-4 commits) | 15 | `/skillplan`, `/arbitrage`, `/killmails`, `/orders` |
| Low (5+ commits) | 18 | `/mission-brief`, `/fitting`, `/route` |

### Existing Infrastructure

| Component | What It Tests | Gap |
|-----------|---------------|-----|
| `aria-skill-preflight.py` | Prerequisites (files, scopes, pilot) | Not output correctness |
| `test_skill_outputs.py` (syrupy) | Output stability via snapshots | Doesn't validate correctness |
| MCP mock fixtures | Tool call isolation | No ground truth comparison |

### Root Cause

1. **No formal output contracts** - Skill behavior documented in Markdown, not schemas
2. **No ground truth database** - No known-correct answers to compare against
3. **Snapshot drift** - Snapshots capture current behavior, not correct behavior
4. **LLM variability** - Natural language outputs vary between runs

### Impact

- Skills may produce incorrect data (wrong prices, bad routes, invalid fits)
- Regressions go undetected until user reports
- No confidence metric for skill reliability
- Cannot safely refactor skill implementations

---

## Proposed Solution

### Three-Layer Validation Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 3: Semantic Validation                                        │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ LLM-as-Judge (G-Eval pattern)                                   ││
│  │ • Factual accuracy against ground truth                         ││
│  │ • Response quality scoring (1-5 scale)                          ││
│  │ • Persona voice consistency (if rp_level != off)                ││
│  │ • Run: On release, weekly CI, or manual trigger                 ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 2: Structural Validation                                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ JSON Schema + Fact Assertions                                   ││
│  │ • Output matches documented format                              ││
│  │ • Required fields present with correct types                    ││
│  │ • Key facts extracted and asserted                              ││
│  │ • Run: Every PR, fast CI                                        ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: Contract Validation                                        │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Deterministic Checks                                            ││
│  │ • Correct MCP tool calls made                                   ││
│  │ • Parameters passed correctly                                   ││
│  │ • Data sources loaded                                           ││
│  │ • Run: Every commit, pre-commit hook                            ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### Layer 1: Contract Validation (Deterministic)

Validates that skills invoke the correct tools with correct parameters.

**Implementation:**

```python
# tests/skills/test_contracts.py

@pytest.mark.contract
def test_route_skill_calls_universe_route(mock_universe):
    """Verify /route skill invokes universe(action='route')."""
    result = invoke_skill("route", args={"origin": "Jita", "destination": "Amarr"})

    # Assert correct MCP call was made
    assert mock_universe.called_with(
        action="route",
        origin="Jita",
        destination="Amarr",
        mode="shortest"  # default
    )

@pytest.mark.contract
def test_price_skill_calls_market_prices(mock_market):
    """Verify /price skill invokes market(action='prices')."""
    result = invoke_skill("price", args={"items": ["Tritanium"]})

    assert mock_market.called_with(
        action="prices",
        items=["Tritanium"],
        region="jita"  # default
    )
```

**What it catches:**
- Wrong tool called
- Missing required parameters
- Incorrect parameter values
- Tool call ordering errors

### Layer 2: Structural Validation (JSON Schema + Facts)

Validates output structure and extracts key facts for assertion.

**Schema Definition Format:**

```yaml
# tests/skills/schemas/route.schema.yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
title: RouteSkillOutput
type: object
required:
  - route
  - summary
properties:
  route:
    type: array
    items:
      type: object
      required: [system, security]
      properties:
        system:
          type: string
        security:
          type: number
          minimum: -1.0
          maximum: 1.0
        kills_1h:
          type: integer
          minimum: 0
        jumps_1h:
          type: integer
          minimum: 0
  summary:
    type: object
    required: [total_jumps, low_sec_jumps]
    properties:
      total_jumps:
        type: integer
        minimum: 0
      low_sec_jumps:
        type: integer
        minimum: 0
```

**Fact Assertion Format:**

```yaml
# tests/skills/fixtures/route/jita_amarr_safe.yaml
name: "Jita to Amarr safe route"
skill: route
input:
  origin: Jita
  destination: Amarr
  mode: safe
expected_facts:
  - path: "route[0].system"
    equals: "Jita"
  - path: "route[-1].system"
    equals: "Amarr"
  - path: "summary.low_sec_jumps"
    equals: 0
  - path: "summary.total_jumps"
    range: [30, 50]  # Known range for safe route
  - path: "route[*].security"
    all_satisfy: ">= 0.45"  # All highsec
```

**Implementation:**

```python
# tests/skills/test_structure.py
import jsonschema
from yaml import safe_load

@pytest.mark.parametrize("fixture", glob("tests/skills/fixtures/route/*.yaml"))
def test_route_output_structure(fixture):
    """Validate route output against schema and facts."""
    case = safe_load(open(fixture))
    schema = safe_load(open("tests/skills/schemas/route.schema.yaml"))

    # Invoke skill with mock data
    result = invoke_skill(case["skill"], args=case["input"])
    output = extract_json(result)  # Parse JSON from response

    # Schema validation
    jsonschema.validate(output, schema)

    # Fact assertions
    for fact in case["expected_facts"]:
        actual = jsonpath(output, fact["path"])
        if "equals" in fact:
            assert actual == fact["equals"]
        elif "range" in fact:
            assert fact["range"][0] <= actual <= fact["range"][1]
        elif "all_satisfy" in fact:
            assert all(eval(f"x {fact['all_satisfy']}") for x in actual)
```

### Layer 3: Semantic Validation (LLM-as-Judge)

Evaluates response quality for natural language outputs.

**G-Eval Scorecard:**

```yaml
# tests/skills/evals/mission_brief.eval.yaml
skill: mission-brief
evaluator: g-eval
criteria:
  factual_accuracy:
    weight: 0.4
    prompt: |
      Score 1-5: Does the briefing accurately describe the mission?
      Ground truth: {ground_truth}
      Response: {response}

      5 = All facts correct, matches ground truth exactly
      3 = Minor inaccuracies, core facts correct
      1 = Major factual errors or hallucinations

  completeness:
    weight: 0.3
    prompt: |
      Score 1-5: Does the briefing cover all essential information?
      Required sections: enemy types, damage profile, recommended tank, triggers

      5 = All sections covered with detail
      3 = Most sections covered, some gaps
      1 = Missing critical information

  actionability:
    weight: 0.2
    prompt: |
      Score 1-5: Can a pilot act on this briefing?

      5 = Clear, specific guidance with fit recommendations
      3 = General guidance, pilot must fill gaps
      1 = Vague or confusing, not actionable

  persona_consistency:
    weight: 0.1
    prompt: |
      Score 1-5: Does the response match the expected persona voice?
      Expected: {persona_profile}

      5 = Perfect voice match
      3 = Mostly consistent with minor breaks
      1 = Wrong persona or no persona when expected

passing_threshold: 3.5  # Weighted average must exceed
```

**Implementation:**

```python
# tests/skills/test_semantic.py
from deepeval import evaluate
from deepeval.metrics import GEval

@pytest.mark.semantic
@pytest.mark.slow  # Exclude from fast CI
def test_mission_brief_quality():
    """Evaluate mission brief quality via LLM-as-judge."""
    eval_config = safe_load(open("tests/skills/evals/mission_brief.eval.yaml"))

    # Invoke skill
    result = invoke_skill("mission-brief", args={"mission": "The Blockade", "level": 4})

    # Load ground truth
    ground_truth = load_ground_truth("the_blockade_l4")

    # Build G-Eval metrics
    metrics = []
    for name, criterion in eval_config["criteria"].items():
        metrics.append(GEval(
            name=name,
            criteria=criterion["prompt"].format(
                ground_truth=ground_truth,
                response=result,
                persona_profile=get_active_persona()
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT]
        ))

    # Run evaluation
    scores = evaluate(result, metrics)

    # Calculate weighted average
    weighted_score = sum(
        scores[m.name] * eval_config["criteria"][m.name]["weight"]
        for m in metrics
    )

    assert weighted_score >= eval_config["passing_threshold"]
```

---

## Test Case Repository

### Directory Structure

```
tests/
├── skills/
│   ├── conftest.py              # Existing fixtures
│   ├── test_contracts.py        # Layer 1: Tool call validation
│   ├── test_structure.py        # Layer 2: Schema + fact validation
│   ├── test_semantic.py         # Layer 3: LLM-as-judge
│   ├── schemas/                  # JSON Schema definitions
│   │   ├── route.schema.yaml
│   │   ├── price.schema.yaml
│   │   ├── fitting.schema.yaml
│   │   └── ...
│   ├── fixtures/                 # Test inputs and expected facts
│   │   ├── route/
│   │   │   ├── jita_amarr_safe.yaml
│   │   │   ├── jita_amarr_shortest.yaml
│   │   │   └── nullsec_transit.yaml
│   │   ├── price/
│   │   │   ├── tritanium_jita.yaml
│   │   │   └── plex_all_hubs.yaml
│   │   └── ...
│   ├── evals/                    # G-Eval configurations
│   │   ├── mission_brief.eval.yaml
│   │   ├── fitting.eval.yaml
│   │   └── ...
│   └── ground_truth/             # Known-correct reference data
│       ├── missions/
│       │   ├── the_blockade_l4.json
│       │   └── ...
│       ├── routes/
│       │   └── jita_amarr.json
│       └── ...
```

### Ground Truth Sources

| Data Type | Source | Update Frequency |
|-----------|--------|------------------|
| Route topology | `aria-universe` MCP | Static (game patches) |
| Mission intel | EVE University Wiki | Monthly review |
| Item prices | Fuzzwork snapshot | Test-time mock |
| Fit stats | EOS calculation | Test-time calculation |
| Skill requirements | SDE | Static (game patches) |

---

## Test Runner Integration

### pytest Markers

```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
markers = [
    "contract: Layer 1 - tool call contract validation",
    "structure: Layer 2 - JSON schema and fact assertions",
    "semantic: Layer 3 - LLM-as-judge evaluation (slow)",
    "golden: Snapshot comparison tests",
    "slow: Tests that take >10s",
]
```

### CI Configuration

```yaml
# .github/workflows/skill-tests.yml
name: Skill Test Harness

on:
  push:
    paths:
      - '.claude/skills/**'
      - 'tests/skills/**'
  pull_request:
  schedule:
    - cron: '0 6 * * 0'  # Weekly semantic tests

jobs:
  fast-tests:
    name: Contract + Structure (Fast)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: uv sync
      - run: uv run pytest tests/skills -m "contract or structure" --tb=short

  semantic-tests:
    name: Semantic Evaluation (Weekly)
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    steps:
      - uses: actions/checkout@v4
      - run: uv sync
      - run: uv run pytest tests/skills -m semantic --tb=short
    env:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

### Coverage Tracking

```python
# tests/skills/coverage_report.py
"""Generate skill test coverage report."""

from aria_skill_index import load_index

def generate_coverage_report():
    index = load_index()
    test_fixtures = glob("tests/skills/fixtures/**/*.yaml")

    coverage = {}
    for skill in index["skills"]:
        name = skill["name"]
        fixtures = [f for f in test_fixtures if f"/{name}/" in f]
        schemas = Path(f"tests/skills/schemas/{name}.schema.yaml").exists()
        evals = Path(f"tests/skills/evals/{name}.eval.yaml").exists()

        coverage[name] = {
            "test_cases": len(fixtures),
            "has_schema": schemas,
            "has_semantic_eval": evals,
            "commit_count": get_commit_count(skill),  # From heatmap
            "coverage_score": calculate_score(fixtures, schemas, evals)
        }

    return coverage
```

**Coverage Score Formula:**

```
coverage_score = (
    0.3 * min(test_cases / 5, 1.0) +    # Up to 5 test cases
    0.3 * has_schema +                    # Schema exists
    0.2 * has_semantic_eval +             # G-Eval exists
    0.2 * min(commit_count / 10, 1.0)     # Development maturity
)
```

---

## Implementation Checklist

### Phase 1: Infrastructure (Week 1)

- [ ] Create `tests/skills/schemas/` directory structure
- [ ] Create `tests/skills/fixtures/` directory structure
- [ ] Create `tests/skills/evals/` directory structure
- [ ] Implement `invoke_skill()` test helper
- [ ] Implement `extract_json()` response parser
- [ ] Add pytest markers to `pyproject.toml`

### Phase 2: High-Priority Skill Tests (Week 2)

Target: Skills from heatmap with high activity but no formal tests.

- [ ] `/route` - Schema + 5 fixtures + ground truth
- [ ] `/price` - Schema + 3 fixtures
- [ ] `/fitting` - Schema + 3 fixtures + G-Eval
- [ ] `/threat-assessment` - Schema + 3 fixtures
- [ ] `/mission-brief` - Schema + G-Eval (complex output)

### Phase 3: Medium-Priority Skills (Week 3)

Target: Skills with 5-9 commits.

- [ ] `/skillqueue` - Schema + 2 fixtures
- [ ] `/pilot` - Schema + 2 fixtures
- [ ] `/mining-advisory` - Schema + 2 fixtures
- [ ] `/exploration` - Schema + G-Eval
- [ ] `/arbitrage` - Schema + 3 fixtures

### Phase 4: Low-Activity Skills (Week 4)

Target: Skills with 1-4 commits (highest risk).

- [ ] `/pi` - Schema + 2 fixtures
- [ ] `/abyssal` - Schema + G-Eval
- [ ] `/standings` - Schema + 2 fixtures
- [ ] `/build-cost` - Schema + 2 fixtures
- [ ] `/assets` - Schema + 2 fixtures
- [ ] `/gatecamp` - Schema + 2 fixtures
- [ ] `/orient` - Schema + 2 fixtures
- [ ] `/watchlist` - Schema + 2 fixtures

### Phase 5: CI Integration (Week 5)

- [ ] Add GitHub Actions workflow
- [ ] Configure semantic tests as weekly scheduled job
- [ ] Implement coverage report generation
- [ ] Add coverage badge to README

### Phase 6: Coverage Dashboard (Week 6)

- [ ] Build coverage report script
- [ ] Generate coverage heatmap (extends activity heatmap)
- [ ] Document coverage requirements for new skills
- [ ] Add pre-commit hook for schema validation

---

## Framework Comparison

| Framework | Pros | Cons | Recommendation |
|-----------|------|------|----------------|
| **DeepEval** | Purpose-built for LLM testing, G-Eval built-in | Adds dependency, learning curve | Use for Layer 3 |
| **pytest + jsonschema** | No new dependencies, fast | Manual fact extraction | Use for Layers 1-2 |
| **Promptfoo** | YAML-based, good CLI | Separate tool, less pytest integration | Consider for evals |
| **LangSmith** | Great tracing, hosted | Requires account, cost | Future integration |

**Recommendation:** Start with pytest + jsonschema for Layers 1-2, add DeepEval for Layer 3 semantic tests.

```toml
# pyproject.toml additions
[project.optional-dependencies]
test-harness = [
    "jsonschema>=4.20.0",
    "jsonpath-ng>=1.6.0",
    "deepeval>=0.21.0",
]
```

---

## Example Test Cases

### Layer 1: Contract Test

```python
@pytest.mark.contract
def test_price_calls_market_dispatcher(mock_mcp):
    """Verify /price invokes market(action='prices')."""
    invoke_skill("price", {"items": ["Tritanium", "Pyerite"]})

    mock_mcp.assert_called_with(
        "market",
        action="prices",
        items=["Tritanium", "Pyerite"],
        region="jita"
    )
```

### Layer 2: Structure Test

```yaml
# tests/skills/fixtures/price/minerals_jita.yaml
name: "Mineral prices in Jita"
skill: price
input:
  items: ["Tritanium", "Pyerite", "Mexallon"]
  region: jita
expected_facts:
  - path: "prices"
    length: 3
  - path: "prices[*].item_name"
    contains_all: ["Tritanium", "Pyerite", "Mexallon"]
  - path: "prices[*].sell_price"
    all_satisfy: "> 0"
  - path: "prices[*].buy_price"
    all_satisfy: "> 0"
  - path: "prices[*].spread_pct"
    all_satisfy: ">= 0"
```

### Layer 3: Semantic Eval

```yaml
# tests/skills/evals/fitting.eval.yaml
skill: fitting
evaluator: g-eval
test_cases:
  - name: "Vexor PvE fit recommendation"
    input:
      ship: Vexor
      purpose: "Level 3 missions"
    ground_truth: |
      - Should recommend drone damage amplifiers
      - Should have active armor tank (repper)
      - Should include propulsion (AB or MWD)
      - DPS should be 200-400 range
      - Should be cap stable or near-stable

criteria:
  fit_validity:
    weight: 0.4
    prompt: |
      Does the fit pass EOS validation? Is it importable to EVE?
      A valid fit has no slot errors and doesn't exceed CPU/PG.

  purpose_match:
    weight: 0.3
    prompt: |
      Is this fit appropriate for the stated purpose (Level 3 missions)?
      Consider: tank type, DPS, utility slots, drone choice.

  explanation_quality:
    weight: 0.3
    prompt: |
      Does the explanation help the pilot understand the fit choices?
      Good explanations cover: why each module, how to fly it, upgrade path.
```

---

## Open Questions

1. **How to handle MCP unavailability in tests?**
   - Option A: Mock all MCP calls (current approach)
   - Option B: Integration tests with live MCP server
   - **Recommendation:** Mock for CI, optional live tests locally

2. **Should semantic tests block PRs?**
   - Option A: Yes, require passing score
   - Option B: No, advisory only
   - **Recommendation:** Advisory for now, blocking after baseline established

3. **How to version ground truth data?**
   - Option A: Git-tracked JSON files
   - Option B: Separate ground-truth repository
   - **Recommendation:** Git-tracked in `tests/skills/ground_truth/`

4. **Cost management for LLM-as-judge?**
   - Estimated cost: ~$0.10 per semantic test (Claude Haiku)
   - Weekly CI run with 50 tests: ~$5/week
   - **Recommendation:** Use Haiku for evals, budget $20/month

5. **How to handle persona-exclusive skills?**
   - PARIA skills require pirate persona context
   - **Recommendation:** Separate test fixtures per persona

---

## Success Metrics

| Metric | Current | Target (Phase 6) |
|--------|---------|------------------|
| Skills with schema | 0 | 43 (100%) |
| Skills with test fixtures | ~5 | 43 (100%) |
| Skills with semantic eval | 0 | 15 (narrative skills) |
| Average test cases per skill | <1 | 3+ |
| CI test runtime | N/A | <5 min (fast), <30 min (full) |
| Coverage score (high-activity) | Unknown | >0.8 |
| Coverage score (low-activity) | Unknown | >0.6 |

---

## Summary

| Aspect | Current State | Proposed State |
|--------|---------------|----------------|
| Output contracts | Markdown docs only | JSON Schema per skill |
| Correctness testing | None | Fact assertions + ground truth |
| Semantic quality | None | G-Eval scoring for narrative skills |
| CI integration | Preflight + snapshots | Three-layer validation pipeline |
| Coverage tracking | Commit-based heatmap | Test-based coverage scores |
| New skill requirements | None | Schema + 2 fixtures minimum |

This test harness transforms skill quality from "it ran without crashing" to "it produced correct, well-structured, high-quality output."

---

## References

- [DeepEval - LLM Evaluation Framework](https://github.com/confident-ai/deepeval)
- [G-Eval: NLG Evaluation Using GPT-4](https://arxiv.org/abs/2303.16634)
- [Building an LLM evaluation framework | Datadog](https://www.datadoghq.com/blog/llm-evaluation-framework-best-practices/)
- [LLM Testing Guide 2025](https://www.uprootsecurity.com/blog/llm-testing-guide-methods-frameworks)
- `dev/reviews/SKILL_ACTIVITY_HEATMAP.md` - Current skill coverage analysis
