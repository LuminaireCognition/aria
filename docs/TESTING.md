# Testing Guide

ARIA uses pytest with a tiered testing strategy to balance thoroughness with cost.

## Quick Start

```bash
# Run all tests (parallel execution)
uv run pytest -n auto

# Run unit tests only (fast, free)
uv run pytest -m unit

# Skip expensive tests
uv run pytest -m "not tier2 and not tier3"
```

## Test Tiers

| Tier | Marker | Cost | Speed | Description |
|------|--------|------|-------|-------------|
| Unit | `@pytest.mark.unit` | Free | Fast | No external dependencies |
| Integration | `@pytest.mark.integration` | Free | Medium | Uses mocks |
| Tier 1 | `@pytest.mark.tier1` | Free | Fast | MCP layer tests |
| Tier 2 | `@pytest.mark.tier2` | ~$0.01/test | Slow | API integration |
| Tier 3 | `@pytest.mark.tier3` | ~$0.03/test | Slow | CLI integration |
| Benchmark | `@pytest.mark.benchmark` | Free | Variable | Performance tests |

### When to Run Each Tier

| Context | Recommended Command |
|---------|-------------------|
| During development | `uv run pytest -m unit` |
| Before commit | `uv run pytest -m "not tier2 and not tier3"` |
| CI/CD (PR) | `uv run pytest -m "not tier3"` |
| CI/CD (merge) | `uv run pytest -n auto` |
| Weekly validation | `uv run pytest -n auto --run-tier3` |

## Running Specific Tests

### By Marker

```bash
# Unit tests only
uv run pytest -m unit

# Integration tests
uv run pytest -m integration

# Contract tests (Layer 1)
uv run pytest -m contract

# Golden/snapshot tests
uv run pytest -m golden

# Exclude benchmarks (default behavior)
uv run pytest -m "not benchmark"
```

### By Path

```bash
# Single test file
uv run pytest tests/services/test_asset_snapshots.py

# Single test function
uv run pytest tests/services/test_asset_snapshots.py::test_save_snapshot

# Test directory
uv run pytest tests/mcp/
```

### By Keyword

```bash
# Tests containing "market" in name
uv run pytest -k market

# Combine with markers
uv run pytest -m unit -k "price"
```

## Parallel Execution

Always use `-n auto` for parallel execution:

```bash
# Automatically detect CPU cores
uv run pytest -n auto

# Specify worker count
uv run pytest -n 4
```

**Note:** Some tests require sequential execution (database locks, etc.) and use `@pytest.mark.serial`.

## Coverage

### Generate Coverage Report

```bash
# Terminal report (default)
uv run pytest --cov=aria_esi --cov-report=term-missing

# HTML report
uv run pytest --cov=aria_esi --cov-report=html
open htmlcov/index.html

# Both
uv run pytest --cov=aria_esi --cov-report=term-missing --cov-report=html
```

### Coverage Targets

Current minimum: **54%** (enforced in CI)

| Module Category | Target | Current |
|-----------------|--------|---------|
| Core (auth, client) | 70%+ | ~55% |
| Commands | 70%+ | 50-89% |
| MCP Tools | 80%+ | 71-100% |
| Services | 70%+ | Variable |

## Test Fixtures

Common fixtures are in `tests/conftest.py`:

```python
@pytest.fixture
def mock_esi_client():
    """Mocked ESI client for unit tests."""
    ...

@pytest.fixture
def sample_assets():
    """Sample asset data for testing."""
    ...

@pytest.fixture
def temp_userdata(tmp_path):
    """Temporary userdata directory."""
    ...
```

## Writing Tests

### Unit Test Example

```python
import pytest

@pytest.mark.unit
def test_apply_me_efficiency():
    """ME 10 should reduce materials by 10%."""
    from aria_esi.services.industry_costs import apply_me

    result = apply_me(base_qty=1000, me_level=10)
    assert result == 900
```

### Integration Test Example

```python
import pytest

@pytest.mark.integration
@pytest.mark.httpx
def test_market_prices_fetch(httpx_mock):
    """Market prices should fetch from Fuzzwork."""
    httpx_mock.add_response(
        url="https://market.fuzzwork.co.uk/...",
        json={"12345": {"sell": {"min": 100}}}
    )

    result = fetch_prices([12345])
    assert result[12345] == 100
```

### Tier 2 Test Example

```python
import pytest

@pytest.mark.tier2
def test_live_esi_character():
    """Verify ESI character endpoint (costs API calls)."""
    # This test makes real API calls
    # Only run in CI or explicitly
    ...
```

## Snapshot Testing

ARIA uses [syrupy](https://github.com/tophat/syrupy) for golden/snapshot tests:

```python
@pytest.mark.golden
def test_skill_output_format(snapshot):
    """Skill output should match golden snapshot."""
    result = format_skill_plan(...)
    assert result == snapshot
```

Update snapshots:
```bash
uv run pytest --snapshot-update
```

## Benchmarks

Performance benchmarks require the universe graph:

```bash
# Run benchmarks
uv run pytest -m benchmark --benchmark-only

# Compare against baseline
uv run pytest -m benchmark --benchmark-compare
```

## Mocking External Services

### ESI API

```python
from unittest.mock import patch

@patch('aria_esi.core.client.ESIClient.get')
def test_assets_fetch(mock_get):
    mock_get.return_value = [{"item_id": 1, "type_id": 100}]
    ...
```

### Market API

```python
@pytest.mark.httpx
def test_market_fetch(httpx_mock):
    httpx_mock.add_response(url=..., json=...)
    ...
```

## CI/CD Integration

### GitHub Actions Markers

```yaml
- name: Run unit tests
  run: uv run pytest -m unit -n auto

- name: Run integration tests
  run: uv run pytest -m "not tier2 and not tier3" -n auto

- name: Run full test suite (weekly)
  if: github.event_name == 'schedule'
  run: uv run pytest -n auto
```

## Troubleshooting

### Test Isolation Issues

If tests pass individually but fail together:
```bash
# Run without parallel
uv run pytest -n 0

# Run with verbose isolation
uv run pytest -v --tb=long
```

### Flaky Tests

Mark known flaky tests:
```python
@pytest.mark.flaky(reruns=3)
def test_network_dependent():
    ...
```

### Slow Test Discovery

```bash
# Profile test collection
uv run pytest --collect-only -q
```

## Related Documentation

- [PYTHON_ENVIRONMENT.md](PYTHON_ENVIRONMENT.md) - Development setup
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
- [pyproject.toml](../pyproject.toml) - Test configuration (L72-99)
