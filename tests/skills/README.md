# Skill Test Harness

This directory contains the test infrastructure for validating ARIA skill outputs. The harness uses a three-layer architecture with tiered integration testing to ensure skills produce correct, consistent results.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 1: Structure Tests                      │
│    test_structure.py - Schema validation, fact assertions        │
│    "Does the output have the right shape?"                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Layer 2: Integration Tests                      │
│    test_integration.py - MCP/ESI contract validation             │
│    "Does the skill call the right tools with right params?"      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 3: Tier Execution                       │
│    Tier 1: Mock dispatchers (free, fast)                         │
│    Tier 2: Anthropic API (weekly CI, ~$0.01/test)                │
│    Tier 3: Claude CLI (release/manual, ~$0.03/test)              │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
tests/skills/
├── README.md              # This file
├── conftest.py            # Shared pytest fixtures and utilities
├── test_structure.py      # Layer 1: Schema and fact validation
├── test_integration.py    # Layer 2: MCP/ESI contract tests
├── fixtures/              # Test fixtures organized by skill
│   ├── route/
│   │   ├── jita_amarr_safe.yaml
│   │   └── avoid_uedama.yaml
│   ├── assets/
│   │   └── valuation.yaml
│   └── ...
├── schemas/               # JSON Schema definitions for skill outputs
│   ├── route.schema.yaml
│   ├── assets.schema.yaml
│   └── ...
├── integration/           # Test infrastructure modules
│   ├── __init__.py
│   ├── mcp_mocker.py      # MockMCPServer for tool call simulation
│   ├── esi_mocker.py      # MockESIServer for ESI API simulation
│   ├── invokers.py        # Tier 1/2/3 invocation strategies
│   └── response_parser.py # JSON extraction from LLM responses
└── scripts/               # Fixture and schema generators
    ├── generate_fixture.py
    └── generate_schema.py
```

## Running Tests

```bash
# All structure tests (fast, no external deps)
uv run pytest tests/skills/test_structure.py -v

# All Tier 1 integration tests (mocked, free)
uv run pytest tests/skills/test_integration.py -m tier1 -v

# Tier 1 + Tier 2 (requires API key)
ANTHROPIC_API_KEY=sk-... uv run pytest tests/skills/test_integration.py -m "tier1 or tier2" -v

# Specific skill tests
uv run pytest tests/skills/ -k "route" -v
```

## Fixture Anatomy

A fixture file defines test scenarios for a skill. Here's the complete structure:

```yaml
# Test fixture: Descriptive name
# Brief description of what this tests

name: "Human-readable test name"
skill: route                    # Skill being tested
description: |
  Detailed description of the test scenario.
  What inputs are provided, what behavior is expected.

# Input parameters for the skill
input:
  origin: Jita
  destination: Amarr
  mode: safe

# Expected facts (assertions that must hold)
expected_facts:
  - path: "origin"
    equals: "Jita"

  - path: "total_jumps"
    range: [35, 55]

  - path: "route[*].security"
    all_satisfy: ">= 0.45"

# Optional: Full expected output (for snapshot testing)
expected_output:
  origin: "Jita"
  destination: "Amarr"
  total_jumps: 45
  # ...

# Mock MCP dispatcher responses (for MCP-dependent skills)
mock_responses:
  universe_route:
    origin: "Jita"
    destination: "Amarr"
    total_jumps: 45
    route:
      - system: "Jita"
        security: 0.95
      # ...

# Mock ESI API responses (for ESI-dependent skills)
esi_responses:
  assets:
    - item_id: 1234567890
      type_id: 17715
      location_id: 60003760
      quantity: 1
```

### Fact Assertion Types

| Type | Example | Description |
|------|---------|-------------|
| `equals` | `equals: "Jita"` | Exact value match |
| `range` | `range: [35, 55]` | Value within inclusive range |
| `contains` | `contains: "warning"` | String contains substring |
| `not_contains` | `not_contains: "error"` | String does not contain |
| `contains_all` | `contains_all: ["a", "b"]` | List contains all elements |
| `length` | `length: 5` | Collection has exact length |
| `all_satisfy` | `all_satisfy: ">= 0"` | All elements match condition |

### Path Expressions

Facts use JSONPath-like expressions:

```yaml
# Simple key
- path: "name"
  equals: "Jita"

# Nested key
- path: "summary.total_jumps"
  equals: 45

# Array index
- path: "route[0].system"
  equals: "Jita"

# Last element
- path: "route[-1].system"
  equals: "Amarr"

# All elements (wildcard)
- path: "route[*].security"
  all_satisfy: ">= 0.45"
```

## MCP vs ESI Mocking

Skills fall into two categories based on their data sources:

### MCP-Dependent Skills

These skills call MCP dispatchers (universe, market, sde, fitting, skills):

| Skill | MCP Dispatchers |
|-------|-----------------|
| `/route` | `universe(action="route")` |
| `/price` | `market(action="prices")` |
| `/build-cost` | `sde(action="blueprint_info")`, `market(action="prices")` |
| `/fitting` | `fitting(action="calculate_stats")` |
| `/orient` | `universe(action="local_area")` |
| `/gatecamp` | `universe(action="gatecamp_risk")` |
| `/skillplan` | `sde(action="skill_requirements")`, `skills(action="easy_80_plan")` |

**Use `mock_responses` section:**
```yaml
mock_responses:
  universe_route:     # Format: {dispatcher}_{action}
    origin: "Jita"
    # ...
  market_prices:
    items: [...]
```

### ESI-Dependent Skills

These skills call EVE ESI API endpoints for character data:

| Skill | ESI Endpoints |
|-------|---------------|
| `/assets` | `characters/{id}/assets` |
| `/skillqueue` | `characters/{id}/skillqueue` |
| `/clones` | `characters/{id}/clones`, `characters/{id}/implants` |
| `/wallet-journal` | `characters/{id}/wallet/journal` |
| `/pilot` | `characters/{id}/` (public info) |
| `/standings` | `characters/{id}/standings` |

**Use `esi_responses` section:**
```yaml
esi_responses:
  assets:          # Short key maps to full endpoint
    - item_id: 1234567890
      type_id: 17715
      # ...
  skillqueue:
    - skill_id: 3436
      finished_level: 5
      # ...
```

Short key mappings:
- `skills` → `characters/{character_id}/skills`
- `skillqueue` → `characters/{character_id}/skillqueue`
- `clones` → `characters/{character_id}/clones`
- `implants` → `characters/{character_id}/implants`
- `assets` → `characters/{character_id}/assets`
- `wallet` → `characters/{character_id}/wallet`
- `wallet_journal` → `characters/{character_id}/wallet/journal`
- `standings` → `characters/{character_id}/standings`

### Hybrid Skills

Some skills use both MCP and ESI. Include both sections:

```yaml
# /assets with valuation uses ESI for inventory + MCP for prices
esi_responses:
  assets:
    - item_id: 123
      type_id: 17715
      # ...

mock_responses:
  market_valuation:
    total_value: 1615000000
    # ...
```

## Adding Tests for a New Skill

### Step 1: Create the Schema

Create `schemas/{skill-name}.schema.yaml`:

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
title: SkillNameOutput
description: Output schema for the /skill-name skill
type: object

required:
  - field1
  - field2

properties:
  field1:
    type: string
    description: Description of field1

  field2:
    type: integer
    minimum: 0

$defs:
  NestedObject:
    type: object
    properties:
      # ...
```

### Step 2: Create Fixtures

Create fixtures in `fixtures/{skill-name}/`:

```bash
# Using the generator (recommended)
uv run python tests/skills/scripts/generate_fixture.py \
    --skill route \
    --input '{"origin": "Jita", "destination": "Amarr", "mode": "safe"}' \
    --name "jita_amarr_safe" \
    --description "Safe route between major trade hubs"

# Or create manually
```

Create at least:
1. A "happy path" fixture with typical input
2. An edge case (empty result, error condition, etc.)
3. Boundary conditions if applicable

### Step 3: Add Test Parametrization

In `test_structure.py`, add to `pytest_generate_tests`:

```python
if "newskill_fixture_path" in metafunc.fixturenames:
    fixtures = get_fixtures_for_skill("newskill")
    if fixtures:
        metafunc.parametrize("newskill_fixture_path", fixtures, ids=[f.stem for f in fixtures])
```

In `test_integration.py`, add similar parametrization for the fixture type (use `_get_skill_fixtures_with_mocks` for MCP skills, `_get_skill_fixtures_with_any_mocks` for ESI skills).

### Step 4: Add Test Classes

In `test_structure.py`:

```python
@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestNewSkillSchemaValidation:
    """Schema validation tests for /newskill outputs."""

    @pytest.fixture
    def newskill_schema(self) -> dict[str, Any]:
        schema_path = get_schema_path("newskill")
        if not schema_path.exists():
            pytest.skip("Schema not created yet")
        return load_yaml_file(schema_path)

    def test_valid_response(self, newskill_schema):
        """Verify valid response passes schema validation."""
        valid = {"field1": "value", "field2": 42}
        jsonschema.validate(valid, newskill_schema)


class TestNewSkillFixtureValidation:
    """Fixture validation tests for /newskill."""

    def test_fixture_schema_validation(self, newskill_fixture_path, newskill_schema):
        fixture = load_yaml_file(newskill_fixture_path)
        if "expected_output" in fixture:
            jsonschema.validate(fixture["expected_output"], newskill_schema)

    def test_fixture_fact_assertions(self, newskill_fixture_path):
        fixture = load_yaml_file(newskill_fixture_path)
        if "expected_output" in fixture and "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                assert_fact(fixture["expected_output"], fact)
```

In `test_integration.py`:

```python
@pytest.mark.tier1
class TestNewSkillMCPContract:
    """Tier 1: Verify /newskill MCP calls match fixtures."""

    def test_has_mock_responses(self, newskill_fixture: Path):
        fixture = load_fixture(newskill_fixture)
        assert "mock_responses" in fixture

    def test_fact_assertions(self, newskill_fixture: Path):
        fixture = load_fixture(newskill_fixture)
        if "expected_output" in fixture and "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                assert_fact(fixture["expected_output"], fact)
```

## Test Tiers Explained

### Tier 1: Mock Dispatchers (Default)

- **Cost:** Free
- **Speed:** Fast (~10ms per test)
- **When:** Every PR, local development
- **What:** Validates that fixtures are internally consistent

```bash
uv run pytest tests/skills/test_integration.py -m tier1 -v
```

### Tier 2: Anthropic API

- **Cost:** ~$0.01 per test
- **Speed:** Moderate (~2-5s per test)
- **When:** Weekly CI, pre-release
- **What:** Validates LLM produces outputs matching fixture structure

```bash
ANTHROPIC_API_KEY=sk-... uv run pytest tests/skills/test_integration.py -m tier2 -v
```

### Tier 3: Full CLI

- **Cost:** ~$0.03 per test
- **Speed:** Slow (~10-30s per test)
- **When:** Release validation, manual
- **What:** End-to-end validation through Claude Code CLI

```bash
uv run pytest tests/skills/test_integration.py -m tier3 -v
```

## Troubleshooting

### Test Not Discovering Fixtures

Ensure your fixture has the required section:
- MCP skills: `mock_responses` section
- ESI skills: `esi_responses` section
- Hybrid: Either or both

### Schema Validation Failures

```bash
# Validate schema syntax
uv run python -c "import yaml; yaml.safe_load(open('tests/skills/schemas/route.schema.yaml'))"

# Test specific fixture against schema
uv run pytest tests/skills/test_structure.py -k "route and schema" -v
```

### Fact Assertion Failures

Check path syntax:
- Use `.` for nested keys: `summary.total_jumps`
- Use `[n]` for array indices: `route[0]`
- Use `[*]` for wildcards: `route[*].security`

## Coverage Status

| Skill | Fixtures | Schema | MCP Mock | ESI Mock |
|-------|----------|--------|----------|----------|
| route | ✓ | ✓ | ✓ | - |
| price | ✓ | ✓ | ✓ | - |
| build-cost | ✓ | ✓ | ✓ | - |
| fitting | ✓ | ✓ | ✓ | - |
| gatecamp | ✓ | ✓ | ✓ | - |
| orient | ✓ | ✓ | ✓ | - |
| skillplan | ✓ | ✓ | ✓ | - |
| threat-assessment | ✓ | ✓ | ✓ | - |
| assets | ✓ | ✓ | ✓ | ✓ |
| clones | ✓ | ✓ | - | ✓ |
| killmail | ✓ | ✓ | - | - |
| pilot | ✓ | ✓ | - | ✓ |
| skillqueue | ✓ | ✓ | - | ✓ |
| wallet-journal | ✓ | ✓ | - | ✓ |
| watchlist | ✓ | ✓ | ✓ | - |
| abyssal | ✓ | ✓ | - | - |
| pi | ✓ | ✓ | - | - |
| standings | ✓ | ✓ | - | - |
| arbitrage | ✓ | ✓ | ✓ | - |
| find | ✓ | ✓ | ✓ | - |

Skills without coverage: agents-research, aria-status, contracts, corp, escape-route, esi-query, exploration, first-run-setup, fittings, help, hunting-grounds, industry-jobs, journal, killmails, lp-store, mail, mining, mining-advisory, mission-brief, orders, ransom-calc, sec-status
