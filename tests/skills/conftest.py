"""
Fixtures for skill golden tests.

Provides mock inputs and normalization utilities for snapshot testing,
contract validation, and structural validation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml


@pytest.fixture
def normalize_volatile_fields():
    """
    Return a function that normalizes volatile fields in skill output.

    Volatile fields that change between runs (timestamps, cache ages)
    are replaced with stable placeholders for snapshot comparison.
    """

    def _normalize(data: dict) -> dict:
        """Recursively normalize volatile fields."""
        if not isinstance(data, dict):
            return data

        result = {}
        volatile_keys = {
            "cache_age_seconds",
            "timestamp",
            "query_timestamp",
            "compiled_at",
            "fetched_at",
            "last_updated",
            "issued",  # Market order issue date
        }

        for key, value in data.items():
            if key in volatile_keys:
                # Replace with stable placeholder
                result[key] = "<NORMALIZED>"
            elif isinstance(value, dict):
                result[key] = _normalize(value)
            elif isinstance(value, list):
                result[key] = [
                    _normalize(item) if isinstance(item, dict) else item for item in value
                ]
            else:
                result[key] = value

        return result

    return _normalize


@pytest.fixture
def mock_route_input():
    """Standard route calculation input for testing."""
    return {
        "origin": "Jita",
        "destination": "Perimeter",
        "mode": "safe",
    }


@pytest.fixture
def mock_prices_input():
    """Standard price lookup input for testing."""
    return {
        "items": ["Tritanium", "Pyerite"],
        "region": "jita",
    }


@pytest.fixture
def mock_fitting_eft():
    """Standard EFT format input for testing."""
    return """[Venture, Basic Mining]

Mining Laser Upgrade I

1MN Afterburner I
Survey Scanner I

Miner I
Miner I

Small EM Shield Reinforcer I
Small EM Shield Reinforcer I
Small EM Shield Reinforcer I

Hobgoblin I x2"""


@pytest.fixture
def mock_system_activity_input():
    """Standard system activity input for testing."""
    return {
        "systems": ["Jita", "Amarr", "Dodixie"],
    }


# =============================================================================
# MCP Tool Call Tracking (Layer 1: Contract Validation)
# =============================================================================


@dataclass
class MCPCall:
    """Record of a single MCP tool call."""

    dispatcher: str
    action: str
    kwargs: dict[str, Any]


@dataclass
class MockMCPTracker:
    """
    Tracks MCP dispatcher calls for contract validation.

    Usage:
        mock_mcp = MockMCPTracker()
        # ... code that should call universe(action="route", ...)
        assert mock_mcp.was_called("universe", "route")
        assert mock_mcp.called_with("universe", "route", origin="Jita")
    """

    calls: list[MCPCall] = field(default_factory=list)
    responses: dict[tuple[str, str], Any] = field(default_factory=dict)

    def record_call(self, dispatcher: str, action: str, **kwargs: Any) -> Any:
        """Record a call and return configured response."""
        self.calls.append(MCPCall(dispatcher=dispatcher, action=action, kwargs=kwargs))
        key = (dispatcher, action)
        if key in self.responses:
            return self.responses[key]
        return {"status": "mocked", "dispatcher": dispatcher, "action": action}

    def was_called(self, dispatcher: str, action: str) -> bool:
        """Check if a specific dispatcher/action was called."""
        return any(c.dispatcher == dispatcher and c.action == action for c in self.calls)

    def called_with(self, dispatcher: str, action: str, **expected_kwargs: Any) -> bool:
        """Check if a call was made with specific parameters."""
        for call in self.calls:
            if call.dispatcher == dispatcher and call.action == action:
                for key, value in expected_kwargs.items():
                    if call.kwargs.get(key) != value:
                        break
                else:
                    return True
        return False

    def get_calls(self, dispatcher: str, action: str | None = None) -> list[MCPCall]:
        """Get all calls matching dispatcher and optionally action."""
        return [
            c
            for c in self.calls
            if c.dispatcher == dispatcher and (action is None or c.action == action)
        ]

    def set_response(self, dispatcher: str, action: str, response: Any) -> None:
        """Configure a response for a specific dispatcher/action."""
        self.responses[(dispatcher, action)] = response

    def reset(self) -> None:
        """Clear all recorded calls."""
        self.calls.clear()


@pytest.fixture
def mock_mcp():
    """
    Fixture that provides a mock MCP tracker for contract validation.

    Returns a MockMCPTracker instance that records all MCP calls.
    """
    return MockMCPTracker()


# =============================================================================
# JSON Extraction Utilities (Layer 2: Structural Validation)
# =============================================================================


def extract_json_from_response(response: str) -> dict[str, Any] | list[Any] | None:
    """
    Extract JSON data from an LLM response that may contain markdown or prose.

    Handles common patterns:
    - Raw JSON
    - JSON in ```json code blocks
    - JSON in ``` code blocks
    - JSON embedded in prose

    Args:
        response: Raw response text that may contain JSON

    Returns:
        Parsed JSON data or None if no valid JSON found
    """
    if not response:
        return None

    # Try direct parse first (response is pure JSON)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code blocks
    patterns = [
        r"```json\s*([\s\S]*?)\s*```",  # ```json ... ```
        r"```\s*([\s\S]*?)\s*```",  # ``` ... ```
        r"\{[\s\S]*\}",  # Bare object
        r"\[[\s\S]*\]",  # Bare array
    ]

    for pattern in patterns:
        matches = re.findall(pattern, response)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

    return None


@pytest.fixture
def extract_json():
    """Fixture that provides the JSON extraction function."""
    return extract_json_from_response


# =============================================================================
# Schema and Fixture Loading Utilities
# =============================================================================


def load_yaml_file(path: Path | str) -> dict[str, Any]:
    """Load a YAML file and return its contents."""
    with open(path) as f:
        return yaml.safe_load(f)


def get_schema_path(skill_name: str) -> Path:
    """Get the path to a skill's schema file."""
    return Path(__file__).parent / "schemas" / f"{skill_name}.schema.yaml"


def get_fixtures_for_skill(skill_name: str) -> list[Path]:
    """Get all fixture files for a given skill."""
    fixtures_dir = Path(__file__).parent / "fixtures" / skill_name
    if not fixtures_dir.exists():
        return []
    return sorted(fixtures_dir.glob("*.yaml"))


@pytest.fixture
def load_schema():
    """Fixture that loads a skill schema by name."""

    def _load(skill_name: str) -> dict[str, Any]:
        schema_path = get_schema_path(skill_name)
        if not schema_path.exists():
            pytest.skip(f"No schema for skill '{skill_name}'")
        return load_yaml_file(schema_path)

    return _load


@pytest.fixture
def load_fixture():
    """Fixture that loads a test fixture file."""

    def _load(fixture_path: Path | str) -> dict[str, Any]:
        return load_yaml_file(fixture_path)

    return _load


# =============================================================================
# Fact Assertion Utilities
# =============================================================================


def evaluate_path(data: Any, path: str) -> Any:
    """
    Evaluate a simple JSONPath-like expression against data.

    Supports:
    - Simple keys: "foo"
    - Nested keys: "foo.bar"
    - Array indices: "items[0]"
    - Last element: "items[-1]"
    - All elements: "items[*]"
    - Nested after wildcard: "items[*].name"

    Args:
        data: The data structure to query
        path: The path expression

    Returns:
        The value(s) at the path
    """
    if not path:
        return data

    parts = re.split(r"\.(?![^\[]*\])", path)  # Split on . but not inside []
    result = data
    is_wildcard_expansion = False

    for part in parts:
        if not part:
            continue

        # Handle array access
        match = re.match(r"(\w+)\[([^\]]+)\]", part)
        if match:
            key, index = match.groups()
            if key:
                if is_wildcard_expansion and isinstance(result, list):
                    result = [item[key] for item in result]
                else:
                    result = result[key]

            if index == "*":
                # Mark that we're now in wildcard expansion mode
                is_wildcard_expansion = True
                if isinstance(result, list):
                    # Continue with the list, subsequent paths apply to each element
                    pass
                else:
                    result = list(result.values()) if isinstance(result, dict) else [result]
            else:
                if is_wildcard_expansion and isinstance(result, list):
                    result = [item[int(index)] for item in result]
                else:
                    result = result[int(index)]
        else:
            # Simple key access
            if is_wildcard_expansion and isinstance(result, list):
                # Apply key to each element in the list
                result = [item[part] for item in result]
            else:
                result = result[part]

    return result


def assert_fact(data: Any, fact: dict[str, Any]) -> None:
    """
    Assert a fact about extracted data.

    Fact types:
    - equals: Exact match
    - range: Value within [min, max]
    - contains: Value contains substring or list contains element
    - not_contains: Value does not contain substring or list does not contain element
    - contains_all: List contains all specified elements
    - length: Collection has specified length
    - all_satisfy: All elements satisfy condition (e.g., ">= 0")

    Args:
        data: The data structure to check
        fact: Fact definition with 'path' and assertion type
    """
    path = fact.get("path", "")
    actual = evaluate_path(data, path)

    if "equals" in fact:
        assert actual == fact["equals"], f"Path '{path}': expected {fact['equals']}, got {actual}"

    elif "range" in fact:
        min_val, max_val = fact["range"]
        assert (
            min_val <= actual <= max_val
        ), f"Path '{path}': expected {actual} in range [{min_val}, {max_val}]"

    elif "contains" in fact:
        expected = fact["contains"]
        assert expected in actual, f"Path '{path}': expected {actual} to contain {expected}"

    elif "not_contains" in fact:
        excluded = fact["not_contains"]
        assert excluded not in actual, f"Path '{path}': expected {actual} to NOT contain {excluded}"

    elif "contains_all" in fact:
        expected = set(fact["contains_all"])
        actual_set = set(actual) if isinstance(actual, list) else {actual}
        missing = expected - actual_set
        assert not missing, f"Path '{path}': missing elements {missing}"

    elif "length" in fact:
        expected_len = fact["length"]
        actual_len = len(actual)
        assert actual_len == expected_len, f"Path '{path}': expected length {expected_len}, got {actual_len}"

    elif "all_satisfy" in fact:
        condition = fact["all_satisfy"]
        if not isinstance(actual, list):
            actual = [actual]
        for i, val in enumerate(actual):
            # Safe evaluation of simple conditions like ">= 0", "< 1.0", etc.
            if not _evaluate_condition(val, condition):
                raise AssertionError(
                    f"Path '{path}[{i}]': value {val} does not satisfy '{condition}'"
                )


def _evaluate_condition(value: Any, condition: str) -> bool:
    """
    Safely evaluate a simple condition against a value.

    Supports: >, <, >=, <=, ==, !=
    Example: _evaluate_condition(0.5, ">= 0.45") -> True
    """
    match = re.match(r"([><=!]+)\s*(-?\d+\.?\d*)", condition)
    if not match:
        raise ValueError(f"Invalid condition format: {condition}")

    op, threshold = match.groups()
    threshold = float(threshold)

    ops = {
        ">": lambda x, y: x > y,
        "<": lambda x, y: x < y,
        ">=": lambda x, y: x >= y,
        "<=": lambda x, y: x <= y,
        "==": lambda x, y: x == y,
        "!=": lambda x, y: x != y,
    }

    if op not in ops:
        raise ValueError(f"Unknown operator: {op}")

    return ops[op](value, threshold)


@pytest.fixture
def assert_facts():
    """
    Fixture that returns a function to assert multiple facts about data.

    Usage:
        assert_facts(data, [
            {"path": "route[0].system", "equals": "Jita"},
            {"path": "summary.total_jumps", "range": [30, 50]},
        ])
    """

    def _assert(data: Any, facts: list[dict[str, Any]]) -> None:
        for fact in facts:
            assert_fact(data, fact)

    return _assert


# =============================================================================
# Mock Universe Data for Route Testing
# =============================================================================


@pytest.fixture
def mock_route_response():
    """Standard mock response for universe route action."""
    return {
        "origin": "Jita",
        "destination": "Perimeter",
        "total_jumps": 1,
        "mode": "safe",
        "route": [
            {"system": "Jita", "security": 0.95, "system_id": 30000142},
            {"system": "Perimeter", "security": 0.90, "system_id": 30000144},
        ],
        "security_profile": {
            "highsec_jumps": 1,
            "lowsec_jumps": 0,
            "nullsec_jumps": 0,
        },
    }


@pytest.fixture
def mock_market_price_response():
    """Standard mock response for market prices action."""
    return {
        "items": [
            {
                "type_id": 34,
                "type_name": "Tritanium",
                "buy": {
                    "order_count": 57,
                    "volume": 12467603788,
                    "min_price": 0.02,
                    "max_price": 4.35,
                    "weighted_avg": 2.76,
                    "median": 3.55,
                    "percentile_5": 4.07,
                    "stddev": 1.07,
                },
                "sell": {
                    "order_count": 85,
                    "volume": 12277199377,
                    "min_price": 4.0,
                    "max_price": 119000.0,
                    "weighted_avg": 4.57,
                    "median": 4.73,
                    "percentile_5": 4.12,
                    "stddev": 14096.25,
                },
                "spread": -0.35,
                "spread_percent": -8.75,
                "freshness": "fresh",
            },
            {
                "type_id": 35,
                "type_name": "Pyerite",
                "buy": {
                    "order_count": 45,
                    "volume": 2497405877,
                    "min_price": 0.03,
                    "max_price": 22.01,
                    "weighted_avg": 16.91,
                    "median": 19.29,
                    "percentile_5": 20.69,
                    "stddev": 5.55,
                },
                "sell": {
                    "order_count": 189,
                    "volume": 6385258186,
                    "min_price": 21.3,
                    "max_price": 268200.0,
                    "weighted_avg": 24.01,
                    "median": 24.68,
                    "percentile_5": 21.66,
                    "stddev": 20440.82,
                },
                "spread": -0.71,
                "spread_percent": -3.33,
                "freshness": "fresh",
            },
        ],
        "region": "The Forge",
        "region_id": 10000002,
        "station": "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
        "station_id": 60003760,
        "source": "fuzzwork",
        "freshness": "fresh",
        "cache_age_seconds": 0,
        "unresolved_items": [],
        "warnings": [],
        "_meta": {
            "count": 2,
            "timestamp": "2024-01-15T12:00:00+00:00",
        },
    }


# =============================================================================
# Integration Test Tier Configuration
# =============================================================================


@pytest.fixture
def integration_tier():
    """
    Return the integration test tier based on environment.

    Tiers:
    - 1: Mock MCP (always available)
    - 2: Anthropic API (requires ANTHROPIC_API_KEY)
    - 3: Claude CLI (requires 'claude' in PATH)
    """
    import os
    import shutil

    tiers_available = [1]  # Tier 1 always available

    if os.environ.get("ANTHROPIC_API_KEY"):
        tiers_available.append(2)

    if shutil.which("claude"):
        tiers_available.append(3)

    return max(tiers_available)


@pytest.fixture
def skip_if_no_api_key():
    """Skip test if ANTHROPIC_API_KEY is not set."""
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")


@pytest.fixture
def skip_if_no_cli():
    """Skip test if Claude CLI is not installed."""
    import shutil

    if not shutil.which("claude"):
        pytest.skip("Claude CLI not installed")


# =============================================================================
# Integration Test Fixture Helpers
# =============================================================================


def get_integration_fixtures(skill_name: str) -> list[Path]:
    """
    Get fixtures for a skill that have mock_responses section.

    Args:
        skill_name: Name of the skill (e.g., "build-cost", "route")

    Returns:
        List of fixture paths with mock_responses
    """
    fixtures = get_fixtures_for_skill(skill_name)
    result = []
    for path in fixtures:
        fixture = load_yaml_file(path)
        if "mock_responses" in fixture:
            result.append(path)
    return result


@pytest.fixture
def integration_fixture_loader():
    """
    Fixture that provides a function to load integration fixtures.

    Returns a function that loads a fixture and its mock_responses.
    """

    def _load(fixture_path: Path | str) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Load fixture and extract mock_responses.

        Args:
            fixture_path: Path to the YAML fixture

        Returns:
            Tuple of (fixture_data, mock_responses)
        """
        fixture = load_yaml_file(fixture_path)
        mock_responses = fixture.get("mock_responses", {})
        return fixture, mock_responses

    return _load
