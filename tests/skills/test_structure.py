"""
Layer 2: Structural Validation Tests.

Validates skill outputs against JSON Schema and fact assertions.
These tests ensure outputs have correct structure and contain expected data.

Run with: uv run pytest tests/skills/test_structure.py -m structure
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    jsonschema = None  # type: ignore

from tests.skills.conftest import (
    assert_fact,
    evaluate_path,
    get_fixtures_for_skill,
    get_schema_path,
    load_yaml_file,
)

pytestmark = pytest.mark.structure


# =============================================================================
# Schema Validation Tests
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestRouteSchemaValidation:
    """Schema validation tests for route outputs."""

    @pytest.fixture
    def route_schema(self) -> dict[str, Any]:
        """Load route schema."""
        schema_path = get_schema_path("route")
        if not schema_path.exists():
            pytest.skip("Route schema not created yet")
        return load_yaml_file(schema_path)

    def test_valid_route_output(self, route_schema, mock_route_response):
        """Verify a valid route response passes schema validation."""
        jsonschema.validate(mock_route_response, route_schema)

    def test_route_missing_required_field_fails(self, route_schema):
        """Verify missing required field fails validation."""
        invalid_response = {
            "origin": "Jita",
            # Missing: destination, total_jumps, mode, route
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, route_schema)

    def test_route_invalid_security_fails(self, route_schema):
        """Verify invalid security values fail validation."""
        invalid_response = {
            "origin": "Jita",
            "destination": "Amarr",
            "total_jumps": 45,
            "mode": "safe",
            "route": [
                {"system": "Jita", "security": 2.0},  # Invalid: > 1.0
            ],
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, route_schema)


# =============================================================================
# Fact Assertion Tests
# =============================================================================


class TestFactAssertions:
    """Tests for fact assertion utilities."""

    def test_evaluate_path_simple_key(self):
        """Test simple key path evaluation."""
        data = {"name": "Jita", "security": 0.95}
        assert evaluate_path(data, "name") == "Jita"
        assert evaluate_path(data, "security") == 0.95

    def test_evaluate_path_nested_key(self):
        """Test nested key path evaluation."""
        data = {"summary": {"total_jumps": 45, "low_sec": 0}}
        assert evaluate_path(data, "summary.total_jumps") == 45

    def test_evaluate_path_array_index(self):
        """Test array index path evaluation."""
        data = {"route": [{"system": "Jita"}, {"system": "Amarr"}]}
        assert evaluate_path(data, "route[0]") == {"system": "Jita"}
        assert evaluate_path(data, "route[0].system") == "Jita"
        assert evaluate_path(data, "route[-1].system") == "Amarr"

    def test_evaluate_path_wildcard(self):
        """Test wildcard path evaluation."""
        data = {"route": [{"system": "Jita"}, {"system": "Amarr"}]}
        result = evaluate_path(data, "route[*]")
        assert len(result) == 2

    def test_assert_fact_equals(self):
        """Test equals assertion."""
        data = {"name": "Jita"}
        assert_fact(data, {"path": "name", "equals": "Jita"})

        with pytest.raises(AssertionError):
            assert_fact(data, {"path": "name", "equals": "Amarr"})

    def test_assert_fact_range(self):
        """Test range assertion."""
        data = {"jumps": 45}
        assert_fact(data, {"path": "jumps", "range": [40, 50]})

        with pytest.raises(AssertionError):
            assert_fact(data, {"path": "jumps", "range": [50, 60]})

    def test_assert_fact_contains(self):
        """Test contains assertion."""
        data = {"name": "Jita IV - Moon 4"}
        assert_fact(data, {"path": "name", "contains": "Jita"})

    def test_assert_fact_not_contains(self):
        """Test not_contains assertion."""
        data = {"systems": ["Jita", "Perimeter", "New Caldari"]}
        assert_fact(data, {"path": "systems", "not_contains": "Uedama"})

        with pytest.raises(AssertionError):
            assert_fact(data, {"path": "systems", "not_contains": "Jita"})

    def test_assert_fact_contains_all(self):
        """Test contains_all assertion."""
        data = {"systems": ["Jita", "Amarr", "Dodixie"]}
        assert_fact(data, {"path": "systems", "contains_all": ["Jita", "Amarr"]})

        with pytest.raises(AssertionError):
            assert_fact(data, {"path": "systems", "contains_all": ["Jita", "Rens"]})

    def test_assert_fact_length(self):
        """Test length assertion."""
        data = {"items": [1, 2, 3]}
        assert_fact(data, {"path": "items", "length": 3})

        with pytest.raises(AssertionError):
            assert_fact(data, {"path": "items", "length": 5})

    def test_assert_fact_all_satisfy(self):
        """Test all_satisfy assertion."""
        data = {"security": [0.95, 0.90, 0.85, 0.65]}
        assert_fact(data, {"path": "security", "all_satisfy": ">= 0.45"})

        data_with_lowsec = {"security": [0.95, 0.35, 0.85]}
        with pytest.raises(AssertionError):
            assert_fact(data_with_lowsec, {"path": "security", "all_satisfy": ">= 0.45"})


# =============================================================================
# Fixture-Based Validation Tests
# =============================================================================


def pytest_generate_tests(metafunc):
    """Dynamically generate tests for skill fixtures."""
    if "route_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("route")
        if fixtures:
            metafunc.parametrize("route_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "price_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("price")
        if fixtures:
            metafunc.parametrize("price_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "find_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("find")
        if fixtures:
            metafunc.parametrize("find_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "build_cost_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("build-cost")
        if fixtures:
            metafunc.parametrize("build_cost_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "arbitrage_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("arbitrage")
        if fixtures:
            metafunc.parametrize("arbitrage_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "skillplan_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("skillplan")
        if fixtures:
            metafunc.parametrize("skillplan_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "orient_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("orient")
        if fixtures:
            metafunc.parametrize("orient_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "fitting_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("fitting")
        if fixtures:
            metafunc.parametrize("fitting_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "threat_assessment_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("threat-assessment")
        if fixtures:
            metafunc.parametrize("threat_assessment_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "gatecamp_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("gatecamp")
        if fixtures:
            metafunc.parametrize("gatecamp_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "abyssal_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("abyssal")
        if fixtures:
            metafunc.parametrize("abyssal_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "pi_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("pi")
        if fixtures:
            metafunc.parametrize("pi_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "standings_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("standings")
        if fixtures:
            metafunc.parametrize("standings_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "watchlist_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("watchlist")
        if fixtures:
            metafunc.parametrize("watchlist_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "killmail_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("killmail")
        if fixtures:
            metafunc.parametrize("killmail_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "assets_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("assets")
        if fixtures:
            metafunc.parametrize("assets_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "pilot_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("pilot")
        if fixtures:
            metafunc.parametrize("pilot_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "skillqueue_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("skillqueue")
        if fixtures:
            metafunc.parametrize("skillqueue_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "clones_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("clones")
        if fixtures:
            metafunc.parametrize("clones_fixture_path", fixtures, ids=[f.stem for f in fixtures])

    if "wallet_journal_fixture_path" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("wallet-journal")
        if fixtures:
            metafunc.parametrize("wallet_journal_fixture_path", fixtures, ids=[f.stem for f in fixtures])


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestRouteFixtureValidation:
    """Run validation tests against route fixtures."""

    @pytest.fixture
    def route_schema(self) -> dict[str, Any]:
        """Load route schema."""
        schema_path = get_schema_path("route")
        if not schema_path.exists():
            pytest.skip("Route schema not created yet")
        return load_yaml_file(schema_path)

    def test_route_fixture_schema_validation(
        self,
        route_fixture_path: Path,
        route_schema: dict[str, Any],
        assert_facts,
    ):
        """
        Validate route outputs against fixtures.

        Each fixture contains:
        - input: Parameters to pass to the route skill
        - expected_output: Mock response to validate
        - expected_facts: Assertions to make about the output
        """
        fixture = load_yaml_file(route_fixture_path)

        # If fixture has expected_output, validate against schema
        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, route_schema)

            # Validate facts if present
            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Price Schema Validation Tests
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestPriceSchemaValidation:
    """Schema validation tests for price outputs."""

    @pytest.fixture
    def price_schema(self) -> dict[str, Any]:
        """Load price schema."""
        schema_path = get_schema_path("price")
        if not schema_path.exists():
            pytest.skip("Price schema not created yet")
        return load_yaml_file(schema_path)

    def test_valid_price_output(self, price_schema, mock_market_price_response):
        """Verify a valid price response passes schema validation."""
        jsonschema.validate(mock_market_price_response, price_schema)

    def test_price_missing_required_field_fails(self, price_schema):
        """Verify missing required field fails validation."""
        invalid_response = {
            "items": [],
            "region": "The Forge",
            # Missing: region_id, source, freshness
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, price_schema)

    def test_price_invalid_region_id_fails(self, price_schema):
        """Verify region_id outside valid range fails validation."""
        invalid_response = {
            "items": [],
            "region": "The Forge",
            "region_id": 99999999,  # Invalid: outside 10000000-12000000
            "source": "fuzzwork",
            "freshness": "fresh",
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, price_schema)

    def test_price_invalid_source_fails(self, price_schema):
        """Verify invalid source enum fails validation."""
        invalid_response = {
            "items": [],
            "region": "The Forge",
            "region_id": 10000002,
            "source": "invalid_source",  # Not in enum
            "freshness": "fresh",
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, price_schema)

    def test_price_item_missing_required_field_fails(self, price_schema):
        """Verify price item missing required field fails validation."""
        invalid_response = {
            "items": [
                {
                    "type_id": 34,
                    # Missing: type_name, buy, sell
                }
            ],
            "region": "The Forge",
            "region_id": 10000002,
            "source": "fuzzwork",
            "freshness": "fresh",
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, price_schema)

    def test_price_allows_null_prices(self, price_schema):
        """Verify null prices are allowed for items with no orders."""
        valid_response = {
            "items": [
                {
                    "type_id": 34,
                    "type_name": "Tritanium",
                    "buy": {
                        "order_count": 0,
                        "volume": 0,
                        "min_price": None,
                        "max_price": None,
                        "weighted_avg": None,
                        "median": None,
                        "percentile_5": None,
                        "stddev": None,
                    },
                    "sell": {
                        "order_count": 0,
                        "volume": 0,
                        "min_price": None,
                        "max_price": None,
                        "weighted_avg": None,
                        "median": None,
                        "percentile_5": None,
                        "stddev": None,
                    },
                    "spread": None,
                    "spread_percent": None,
                    "freshness": "fresh",
                }
            ],
            "region": "The Forge",
            "region_id": 10000002,
            "source": "fuzzwork",
            "freshness": "fresh",
        }

        # Should not raise
        jsonschema.validate(valid_response, price_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestPriceFixtureValidation:
    """Run validation tests against price fixtures."""

    @pytest.fixture
    def price_schema(self) -> dict[str, Any]:
        """Load price schema."""
        schema_path = get_schema_path("price")
        if not schema_path.exists():
            pytest.skip("Price schema not created yet")
        return load_yaml_file(schema_path)

    def test_price_fixture_schema_validation(
        self,
        price_fixture_path: Path,
        price_schema: dict[str, Any],
        assert_facts,
    ):
        """
        Validate price outputs against fixtures.

        Each fixture contains:
        - input: Parameters to pass to the price skill
        - expected_output: Mock response to validate
        - expected_facts: Assertions to make about the output
        """
        fixture = load_yaml_file(price_fixture_path)

        # If fixture has expected_output, validate against schema
        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, price_schema)

            # Validate facts if present
            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# JSON Extraction Tests
# =============================================================================


class TestJSONExtraction:
    """Tests for JSON extraction from LLM responses."""

    def test_extract_pure_json(self, extract_json):
        """Test extracting pure JSON response."""
        response = '{"name": "Jita", "jumps": 45}'
        result = extract_json(response)
        assert result == {"name": "Jita", "jumps": 45}

    def test_extract_from_code_block(self, extract_json):
        """Test extracting JSON from markdown code block."""
        response = """Here's the route:

```json
{"origin": "Jita", "destination": "Amarr"}
```

The route is safe."""
        result = extract_json(response)
        assert result == {"origin": "Jita", "destination": "Amarr"}

    def test_extract_from_bare_code_block(self, extract_json):
        """Test extracting JSON from bare code block."""
        response = """```
{"total_jumps": 45}
```"""
        result = extract_json(response)
        assert result == {"total_jumps": 45}

    def test_extract_array(self, extract_json):
        """Test extracting JSON array."""
        response = '[{"system": "Jita"}, {"system": "Amarr"}]'
        result = extract_json(response)
        assert len(result) == 2

    def test_extract_embedded_json(self, extract_json):
        """Test extracting JSON embedded in prose."""
        response = 'The result is {"status": "success"} as expected.'
        result = extract_json(response)
        assert result == {"status": "success"}

    def test_extract_returns_none_for_no_json(self, extract_json):
        """Test that non-JSON returns None."""
        response = "This is just plain text with no JSON."
        result = extract_json(response)
        assert result is None

    def test_extract_empty_response(self, extract_json):
        """Test that empty response returns None."""
        assert extract_json("") is None
        assert extract_json(None) is None


# =============================================================================
# Route Output Validation with Mock Data
# =============================================================================


class TestRouteOutputValidation:
    """Validate route outputs match expected structure."""

    def test_route_has_required_fields(self, mock_route_response):
        """Verify route response has all required fields."""
        required = ["origin", "destination", "total_jumps", "mode", "route"]
        for field in required:
            assert field in mock_route_response, f"Missing required field: {field}"

    def test_route_systems_have_required_fields(self, mock_route_response):
        """Verify each system in route has required fields."""
        for system in mock_route_response["route"]:
            assert "system" in system, "System missing 'system' field"
            assert "security" in system, "System missing 'security' field"

    def test_route_security_in_valid_range(self, mock_route_response):
        """Verify security values are in valid range [-1.0, 1.0]."""
        for system in mock_route_response["route"]:
            sec = system["security"]
            assert -1.0 <= sec <= 1.0, f"Invalid security: {sec}"

    def test_route_total_jumps_matches_route_length(self, mock_route_response):
        """Verify total_jumps matches route length minus 1."""
        # Route includes origin, so jumps = len(route) - 1
        expected_jumps = len(mock_route_response["route"]) - 1
        assert mock_route_response["total_jumps"] == expected_jumps


# =============================================================================
# Price Output Validation
# =============================================================================


class TestPriceOutputValidation:
    """Validate price skill output structure."""

    def test_price_has_required_fields(self, mock_market_price_response):
        """Verify price response has required fields."""
        required = ["items", "region", "region_id", "source", "freshness"]
        for field in required:
            assert field in mock_market_price_response, f"Missing required field: {field}"

    def test_price_items_have_required_fields(self, mock_market_price_response):
        """Verify each price item has required fields."""
        for item in mock_market_price_response["items"]:
            assert "type_id" in item, "Item missing 'type_id' field"
            assert "type_name" in item, "Item missing 'type_name' field"
            assert "buy" in item, "Item missing 'buy' field"
            assert "sell" in item, "Item missing 'sell' field"

    def test_price_order_stats_have_required_fields(self, mock_market_price_response):
        """Verify order stats (buy/sell) have required fields."""
        for item in mock_market_price_response["items"]:
            for side in ["buy", "sell"]:
                stats = item[side]
                assert "order_count" in stats, f"{side} missing 'order_count'"
                assert "volume" in stats, f"{side} missing 'volume'"

    def test_price_order_stats_have_price_fields(self, mock_market_price_response):
        """Verify order stats have price fields when orders exist."""
        for item in mock_market_price_response["items"]:
            for side in ["buy", "sell"]:
                stats = item[side]
                if stats["order_count"] > 0:
                    assert "min_price" in stats, f"{side} missing 'min_price'"
                    assert "max_price" in stats, f"{side} missing 'max_price'"
                    assert "weighted_avg" in stats, f"{side} missing 'weighted_avg'"
                    assert "median" in stats, f"{side} missing 'median'"

    def test_price_order_counts_non_negative(self, mock_market_price_response, assert_facts):
        """Verify order counts are non-negative."""
        assert_facts(
            mock_market_price_response,
            [
                {"path": "items[*].buy.order_count", "all_satisfy": ">= 0"},
                {"path": "items[*].sell.order_count", "all_satisfy": ">= 0"},
            ],
        )

    def test_price_volumes_non_negative(self, mock_market_price_response, assert_facts):
        """Verify volumes are non-negative."""
        assert_facts(
            mock_market_price_response,
            [
                {"path": "items[*].buy.volume", "all_satisfy": ">= 0"},
                {"path": "items[*].sell.volume", "all_satisfy": ">= 0"},
            ],
        )

    def test_price_region_id_in_valid_range(self, mock_market_price_response):
        """Verify region_id is in valid EVE range."""
        region_id = mock_market_price_response["region_id"]
        assert 10000000 <= region_id <= 12000000, f"Invalid region_id: {region_id}"

    def test_price_type_ids_positive(self, mock_market_price_response, assert_facts):
        """Verify type_ids are positive integers."""
        assert_facts(
            mock_market_price_response,
            [
                {"path": "items[*].type_id", "all_satisfy": ">= 1"},
            ],
        )

    def test_price_source_is_valid(self, mock_market_price_response):
        """Verify source is a known value."""
        valid_sources = {"fuzzwork", "esi", "esi_orders", "cache"}
        assert mock_market_price_response["source"] in valid_sources

    def test_price_freshness_is_valid(self, mock_market_price_response):
        """Verify freshness is a known value."""
        valid_freshness = {"fresh", "stale", "cached"}
        assert mock_market_price_response["freshness"] in valid_freshness


# =============================================================================
# Activity Output Validation
# =============================================================================


class TestActivityOutputValidation:
    """Validate activity skill output structure."""

    @pytest.fixture
    def mock_activity_response(self):
        """Mock activity response for testing."""
        return {
            "systems": {
                "Tama": {
                    "ship_kills": 15,
                    "pod_kills": 8,
                    "npc_kills": 120,
                    "jumps": 450,
                },
                "Amamake": {
                    "ship_kills": 25,
                    "pod_kills": 12,
                    "npc_kills": 80,
                    "jumps": 320,
                },
            },
            "data_period": "1 hour",
            "query_timestamp": "2024-01-15T12:00:00Z",
        }

    def test_activity_has_systems(self, mock_activity_response):
        """Verify activity response has systems data."""
        assert "systems" in mock_activity_response
        assert len(mock_activity_response["systems"]) > 0

    def test_activity_systems_have_stats(self, mock_activity_response):
        """Verify each system has activity statistics."""
        for _system_name, stats in mock_activity_response["systems"].items():
            assert "ship_kills" in stats or "kills" in stats
            assert "jumps" in stats


# =============================================================================
# Find Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestFindSchemaValidation:
    """Schema validation tests for /find skill outputs."""

    @pytest.fixture
    def find_schema(self) -> dict[str, Any]:
        """Load find schema."""
        schema_path = get_schema_path("find")
        if not schema_path.exists():
            pytest.skip("Find schema not created yet")
        return load_yaml_file(schema_path)

    def test_find_missing_required_field_fails(self, find_schema):
        """Verify missing required field fails validation."""
        invalid_response = {
            "type_id": 32880,
            "type_name": "Venture Blueprint",
            # Missing: origin_system, sources, total_found
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, find_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestFindFixtureValidation:
    """Run validation tests against find fixtures."""

    @pytest.fixture
    def find_schema(self) -> dict[str, Any]:
        """Load find schema."""
        schema_path = get_schema_path("find")
        if not schema_path.exists():
            pytest.skip("Find schema not created yet")
        return load_yaml_file(schema_path)

    def test_find_fixture_schema_validation(
        self,
        find_fixture_path: Path,
        find_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate find outputs against fixtures."""
        fixture = load_yaml_file(find_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, find_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Build Cost Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestBuildCostSchemaValidation:
    """Schema validation tests for /build-cost skill outputs."""

    @pytest.fixture
    def build_cost_schema(self) -> dict[str, Any]:
        """Load build-cost schema."""
        schema_path = get_schema_path("build-cost")
        if not schema_path.exists():
            pytest.skip("Build-cost schema not created yet")
        return load_yaml_file(schema_path)

    def test_build_cost_missing_required_field_fails(self, build_cost_schema):
        """Verify missing required field fails validation."""
        invalid_response = {
            "blueprint": {"type_id": 32880, "type_name": "Venture Blueprint"},
            # Missing: materials, total_material_cost, product_value
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, build_cost_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestBuildCostFixtureValidation:
    """Run validation tests against build-cost fixtures."""

    @pytest.fixture
    def build_cost_schema(self) -> dict[str, Any]:
        """Load build-cost schema."""
        schema_path = get_schema_path("build-cost")
        if not schema_path.exists():
            pytest.skip("Build-cost schema not created yet")
        return load_yaml_file(schema_path)

    def test_build_cost_fixture_schema_validation(
        self,
        build_cost_fixture_path: Path,
        build_cost_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate build-cost outputs against fixtures."""
        fixture = load_yaml_file(build_cost_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, build_cost_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Arbitrage Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestArbitrageSchemaValidation:
    """Schema validation tests for /arbitrage skill outputs."""

    @pytest.fixture
    def arbitrage_schema(self) -> dict[str, Any]:
        """Load arbitrage schema."""
        schema_path = get_schema_path("arbitrage")
        if not schema_path.exists():
            pytest.skip("Arbitrage schema not created yet")
        return load_yaml_file(schema_path)

    def test_arbitrage_missing_required_field_fails(self, arbitrage_schema):
        """Verify missing required field fails validation."""
        invalid_response = {
            "opportunities": [],
            # Missing: total_found, regions_scanned, scan_timestamp, data_freshness
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, arbitrage_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestArbitrageFixtureValidation:
    """Run validation tests against arbitrage fixtures."""

    @pytest.fixture
    def arbitrage_schema(self) -> dict[str, Any]:
        """Load arbitrage schema."""
        schema_path = get_schema_path("arbitrage")
        if not schema_path.exists():
            pytest.skip("Arbitrage schema not created yet")
        return load_yaml_file(schema_path)

    def test_arbitrage_fixture_schema_validation(
        self,
        arbitrage_fixture_path: Path,
        arbitrage_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate arbitrage outputs against fixtures."""
        fixture = load_yaml_file(arbitrage_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, arbitrage_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Skillplan Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestSkillplanSchemaValidation:
    """Schema validation tests for /skillplan skill outputs."""

    @pytest.fixture
    def skillplan_schema(self) -> dict[str, Any]:
        """Load skillplan schema."""
        schema_path = get_schema_path("skillplan")
        if not schema_path.exists():
            pytest.skip("Skillplan schema not created yet")
        return load_yaml_file(schema_path)

    def test_skillplan_missing_required_field_fails(self, skillplan_schema):
        """Verify missing required field fails validation."""
        invalid_response = {
            "item": "Vexor Navy Issue",
            # Missing: found
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, skillplan_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestSkillplanFixtureValidation:
    """Run validation tests against skillplan fixtures."""

    @pytest.fixture
    def skillplan_schema(self) -> dict[str, Any]:
        """Load skillplan schema."""
        schema_path = get_schema_path("skillplan")
        if not schema_path.exists():
            pytest.skip("Skillplan schema not created yet")
        return load_yaml_file(schema_path)

    def test_skillplan_fixture_schema_validation(
        self,
        skillplan_fixture_path: Path,
        skillplan_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate skillplan outputs against fixtures."""
        fixture = load_yaml_file(skillplan_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, skillplan_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Orient Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestOrientSchemaValidation:
    """Schema validation tests for /orient skill outputs."""

    @pytest.fixture
    def orient_schema(self) -> dict[str, Any]:
        """Load orient schema."""
        schema_path = get_schema_path("orient")
        if not schema_path.exists():
            pytest.skip("Orient schema not created yet")
        return load_yaml_file(schema_path)

    def test_orient_missing_required_field_fails(self, orient_schema):
        """Verify missing required field fails validation."""
        invalid_response = {
            "origin": "Tama",
            "origin_id": 30002813,
            # Missing: security, security_class, region, threat_summary
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, orient_schema)

    def test_orient_invalid_security_class_fails(self, orient_schema):
        """Verify invalid security_class fails validation."""
        invalid_response = {
            "origin": "Tama",
            "origin_id": 30002813,
            "security": 0.28,
            "security_class": "MEDIUM",  # Invalid: not HIGH, LOW, or NULL
            "region": "The Citadel",
            "threat_summary": {"level": "HIGH", "total_kills": 10},
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, orient_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestOrientFixtureValidation:
    """Run validation tests against orient fixtures."""

    @pytest.fixture
    def orient_schema(self) -> dict[str, Any]:
        """Load orient schema."""
        schema_path = get_schema_path("orient")
        if not schema_path.exists():
            pytest.skip("Orient schema not created yet")
        return load_yaml_file(schema_path)

    def test_orient_fixture_schema_validation(
        self,
        orient_fixture_path: Path,
        orient_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate orient outputs against fixtures."""
        fixture = load_yaml_file(orient_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, orient_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Fitting Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestFittingSchemaValidation:
    """Schema validation tests for /fitting skill outputs."""

    @pytest.fixture
    def fitting_schema(self) -> dict[str, Any]:
        """Load fitting schema."""
        schema_path = get_schema_path("fitting")
        if not schema_path.exists():
            pytest.skip("Fitting schema not created yet")
        return load_yaml_file(schema_path)

    def test_fitting_missing_required_field_fails(self, fitting_schema):
        """Verify missing required field fails validation."""
        invalid_response = {
            "ship": {"type_id": 32880, "type_name": "Venture", "fit_name": "Test"},
            # Missing: dps, tank, resources, capacitor, mobility, drones, slots, metadata
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, fitting_schema)

    def test_fitting_invalid_skill_mode_fails(self, fitting_schema):
        """Verify invalid skill_mode fails validation."""
        invalid_response = {
            "ship": {"type_id": 32880, "type_name": "Venture", "fit_name": "Test"},
            "dps": {"total": 0, "em": 0, "thermal": 0, "kinetic": 0, "explosive": 0},
            "tank": {
                "shield": {"hp": 400, "ehp": 480, "resists": {"em": 50, "thermal": 40, "kinetic": 40, "explosive": 50}},
                "armor": {"hp": 250, "ehp": 280, "resists": {"em": 50, "thermal": 45, "kinetic": 25, "explosive": 10}},
                "hull": {"hp": 350, "ehp": 350, "resists": {"em": 0, "thermal": 0, "kinetic": 0, "explosive": 0}},
                "total_hp": 1000,
                "total_ehp": 1110,
            },
            "resources": {
                "cpu": {"used": 0, "output": 130, "percent": 0, "remaining": 130, "overloaded": False},
                "powergrid": {"used": 0, "output": 25, "percent": 0, "remaining": 25, "overloaded": False},
                "calibration": {"used": 0, "output": 400, "percent": 0, "remaining": 400, "overloaded": False},
            },
            "capacitor": {"capacity": 250, "recharge_time": 125, "recharge_rate": 2, "peak_recharge_rate": 5},
            "mobility": {"max_velocity": 300, "agility": 3.5, "align_time": 4.5, "mass": 1200000, "warp_speed": 5},
            "drones": {"bandwidth": {"used": 0, "output": 10, "percent": 0}, "bay": {"used": 0, "output": 10}, "launched": 0, "max_active": 2},
            "slots": {"high": {"used": 0, "total": 2}, "mid": {"used": 0, "total": 2}, "low": {"used": 0, "total": 1}, "rig": {"used": 0, "total": 3}},
            "metadata": {"skill_mode": "invalid_mode", "validation_errors": [], "warnings": []},
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, fitting_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestFittingFixtureValidation:
    """Run validation tests against fitting fixtures."""

    @pytest.fixture
    def fitting_schema(self) -> dict[str, Any]:
        """Load fitting schema."""
        schema_path = get_schema_path("fitting")
        if not schema_path.exists():
            pytest.skip("Fitting schema not created yet")
        return load_yaml_file(schema_path)

    def test_fitting_fixture_schema_validation(
        self,
        fitting_fixture_path: Path,
        fitting_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate fitting outputs against fixtures."""
        fixture = load_yaml_file(fitting_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, fitting_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Threat Assessment Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestThreatAssessmentSchemaValidation:
    """Schema validation tests for /threat-assessment skill outputs."""

    @pytest.fixture
    def threat_assessment_schema(self) -> dict[str, Any]:
        """Load threat-assessment schema."""
        schema_path = get_schema_path("threat-assessment")
        if not schema_path.exists():
            pytest.skip("Threat-assessment schema not created yet")
        return load_yaml_file(schema_path)

    def test_threat_assessment_missing_required_field_fails(self, threat_assessment_schema):
        """Verify missing required field fails validation."""
        invalid_response = {
            "systems": [],
            # Missing: cache_age_seconds, data_period
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, threat_assessment_schema)

    def test_threat_assessment_invalid_security_class_fails(self, threat_assessment_schema):
        """Verify invalid security_class fails validation."""
        invalid_response = {
            "systems": [
                {
                    "name": "Tama",
                    "system_id": 30002813,
                    "security": 0.28,
                    "security_class": "MEDIUM",  # Invalid: not HIGH, LOW, or NULL
                }
            ],
            "cache_age_seconds": 180,
            "data_period": "last_hour",
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, threat_assessment_schema)

    def test_threat_assessment_invalid_activity_level_fails(self, threat_assessment_schema):
        """Verify invalid activity_level fails validation."""
        invalid_response = {
            "systems": [
                {
                    "name": "Tama",
                    "system_id": 30002813,
                    "security": 0.28,
                    "security_class": "LOW",
                    "activity_level": "super_extreme",  # Invalid
                }
            ],
            "cache_age_seconds": 180,
            "data_period": "last_hour",
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, threat_assessment_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestThreatAssessmentFixtureValidation:
    """Run validation tests against threat-assessment fixtures."""

    @pytest.fixture
    def threat_assessment_schema(self) -> dict[str, Any]:
        """Load threat-assessment schema."""
        schema_path = get_schema_path("threat-assessment")
        if not schema_path.exists():
            pytest.skip("Threat-assessment schema not created yet")
        return load_yaml_file(schema_path)

    def test_threat_assessment_fixture_schema_validation(
        self,
        threat_assessment_fixture_path: Path,
        threat_assessment_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate threat-assessment outputs against fixtures."""
        fixture = load_yaml_file(threat_assessment_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, threat_assessment_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Gatecamp Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestGatecampSchemaValidation:
    """Schema validation tests for /gatecamp skill outputs."""

    @pytest.fixture
    def gatecamp_schema(self) -> dict[str, Any]:
        """Load gatecamp schema."""
        schema_path = get_schema_path("gatecamp")
        if not schema_path.exists():
            pytest.skip("Gatecamp schema not created yet")
        return load_yaml_file(schema_path)

    def test_gatecamp_single_system_valid(self, gatecamp_schema):
        """Verify single system response passes validation."""
        valid_response = {
            "systems": [
                {
                    "name": "Niarja",
                    "system_id": 30003504,
                    "security": 0.50,
                    "security_class": "HIGH",
                    "ship_kills": 12,
                    "pod_kills": 8,
                    "npc_kills": 1,
                    "ship_jumps": 4200,
                    "activity_level": "high",
                }
            ],
            "cache_age_seconds": 60,
            "data_period": "last_hour",
        }
        jsonschema.validate(valid_response, gatecamp_schema)

    def test_gatecamp_route_analysis_valid(self, gatecamp_schema):
        """Verify route analysis response passes validation."""
        valid_response = {
            "origin": "Jita",
            "destination": "Amarr",
            "total_jumps": 45,
            "overall_risk": "high",
            "chokepoints": [
                {
                    "system": "Uedama",
                    "system_id": 30002768,
                    "security": 0.50,
                    "chokepoint_type": "pipe",
                    "recent_kills": 15,
                    "recent_pods": 10,
                    "risk_level": "extreme",
                    "warning": "Known gank pipe",
                }
            ],
            "high_risk_systems": ["Uedama"],
            "recommendation": "Scout ahead",
            "cache_age_seconds": 120,
        }
        jsonschema.validate(valid_response, gatecamp_schema)

    def test_gatecamp_invalid_risk_level_fails(self, gatecamp_schema):
        """Verify invalid risk_level fails validation."""
        invalid_response = {
            "origin": "Jita",
            "destination": "Amarr",
            "total_jumps": 45,
            "overall_risk": "super_dangerous",  # Invalid
            "chokepoints": [],
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, gatecamp_schema)

    def test_gatecamp_invalid_chokepoint_type_fails(self, gatecamp_schema):
        """Verify invalid chokepoint_type fails validation."""
        invalid_response = {
            "origin": "Jita",
            "destination": "Amarr",
            "total_jumps": 45,
            "overall_risk": "high",
            "chokepoints": [
                {
                    "system": "Uedama",
                    "system_id": 30002768,
                    "security": 0.50,
                    "chokepoint_type": "bottleneck",  # Invalid: not in enum
                    "recent_kills": 15,
                    "recent_pods": 10,
                    "risk_level": "extreme",
                }
            ],
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, gatecamp_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestGatecampFixtureValidation:
    """Run validation tests against gatecamp fixtures."""

    @pytest.fixture
    def gatecamp_schema(self) -> dict[str, Any]:
        """Load gatecamp schema."""
        schema_path = get_schema_path("gatecamp")
        if not schema_path.exists():
            pytest.skip("Gatecamp schema not created yet")
        return load_yaml_file(schema_path)

    def test_gatecamp_fixture_schema_validation(
        self,
        gatecamp_fixture_path: Path,
        gatecamp_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate gatecamp outputs against fixtures."""
        fixture = load_yaml_file(gatecamp_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, gatecamp_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Abyssal Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestAbyssalSchemaValidation:
    """Schema validation tests for /abyssal skill outputs."""

    @pytest.fixture
    def abyssal_schema(self) -> dict[str, Any]:
        """Load abyssal schema."""
        schema_path = get_schema_path("abyssal")
        if not schema_path.exists():
            pytest.skip("Abyssal schema not created yet")
        return load_yaml_file(schema_path)

    def test_abyssal_weather_response_valid(self, abyssal_schema):
        """Verify valid weather response passes validation."""
        valid_response = {
            "weather_type": "electrical",
            "filament_color": "blue",
            "effects": {
                "em_damage_modifier": 1.5,
                "capacitor_recharge_modifier": 0.5,
            },
            "npc_damage_profile": {"em": 50, "thermal": 30, "kinetic": 10, "explosive": 10},
            "recommended_resist": "EM",
        }
        jsonschema.validate(valid_response, abyssal_schema)

    def test_abyssal_tier_response_valid(self, abyssal_schema):
        """Verify valid tier response passes validation."""
        valid_response = {
            "tier": 4,
            "name": "Raging",
            "difficulty": "Very Hard",
            "ship_class": "Cruiser",
            "time_limit_seconds": 1200,
            "avg_loot_isk": 60000000,
        }
        jsonschema.validate(valid_response, abyssal_schema)

    def test_abyssal_ship_response_valid(self, abyssal_schema):
        """Verify valid ship response passes validation."""
        valid_response = {
            "hull": "Gila",
            "class": "Cruiser",
            "max_recommended_tier": 5,
            "strengths": ["Drone damage", "Passive shield tank"],
            "weaknesses": ["Expensive"],
            "preferred_weather": ["electrical", "exotic"],
        }
        jsonschema.validate(valid_response, abyssal_schema)

    def test_abyssal_npc_response_valid(self, abyssal_schema):
        """Verify valid NPC faction response passes validation."""
        valid_response = {
            "faction_name": "Triglavian Collective",
            "damage_dealt": {"em": 0, "thermal": 50, "kinetic": 0, "explosive": 50},
            "resist_profile": {
                "em": "high",
                "thermal": "low",
                "kinetic": "medium",
                "explosive": "low",
            },
            "recommended_damage": "Thermal/Explosive",
            "special_mechanics": ["Ramping damage"],
            "threat_priority": "High",
        }
        jsonschema.validate(valid_response, abyssal_schema)

    def test_abyssal_invalid_weather_type_fails(self, abyssal_schema):
        """Verify invalid weather type fails validation."""
        invalid_response = {
            "weather_type": "stormy",  # Invalid: not in enum
            "filament_color": "gray",
            "effects": {},
            "npc_damage_profile": {"em": 25, "thermal": 25, "kinetic": 25, "explosive": 25},
            "recommended_resist": "Omni",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, abyssal_schema)

    def test_abyssal_invalid_tier_fails(self, abyssal_schema):
        """Verify tier > 6 fails validation."""
        invalid_response = {
            "tier": 7,  # Invalid: max is 6
            "name": "Ultra",
            "difficulty": "Impossible",
            "ship_class": "Cruiser",
            "time_limit_seconds": 1200,
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, abyssal_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestAbyssalFixtureValidation:
    """Run validation tests against abyssal fixtures."""

    @pytest.fixture
    def abyssal_schema(self) -> dict[str, Any]:
        """Load abyssal schema."""
        schema_path = get_schema_path("abyssal")
        if not schema_path.exists():
            pytest.skip("Abyssal schema not created yet")
        return load_yaml_file(schema_path)

    def test_abyssal_fixture_schema_validation(
        self,
        abyssal_fixture_path: Path,
        abyssal_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate abyssal outputs against fixtures."""
        fixture = load_yaml_file(abyssal_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, abyssal_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# PI Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestPISchemaValidation:
    """Schema validation tests for /pi skill outputs."""

    @pytest.fixture
    def pi_schema(self) -> dict[str, Any]:
        """Load PI schema."""
        schema_path = get_schema_path("pi")
        if not schema_path.exists():
            pytest.skip("PI schema not created yet")
        return load_yaml_file(schema_path)

    def test_pi_production_chain_valid(self, pi_schema):
        """Verify valid production chain response passes validation."""
        valid_response = {
            "product_name": "Robotics",
            "product_tier": "P3",
            "inputs": [
                {"name": "Consumer Electronics", "quantity": 10, "tier": "P2"},
                {"name": "Mechanical Parts", "quantity": 10, "tier": "P2"},
            ],
            "raw_resources": ["Chiral Structures", "Toxic Metals"],
            "production_facility": "Advanced Industry Facility",
            "cycle_time_seconds": 3600,
            "output_quantity": 3,
        }
        jsonschema.validate(valid_response, pi_schema)

    def test_pi_planet_resource_valid(self, pi_schema):
        """Verify valid planet resource response passes validation."""
        valid_response = {
            "resource_name": "Reactive Gas",
            "planet_types": ["Gas", "Storm"],
            "produces_p1": "Oxidizing Compound",
            "p0_to_p1_ratio": "3000:20",
        }
        jsonschema.validate(valid_response, pi_schema)

    def test_pi_single_planet_valid(self, pi_schema):
        """Verify valid single planet P2 response passes validation."""
        valid_response = {
            "single_planet_products": {
                "Barren": ["Construction Blocks", "Nanites"],
                "Gas": ["Coolant", "Oxides"],
            },
            "best_planet_types": [
                {"planet_type": "Oceanic", "p2_count": 6},
            ],
        }
        jsonschema.validate(valid_response, pi_schema)

    def test_pi_skills_valid(self, pi_schema):
        """Verify valid skills response passes validation."""
        valid_response = {
            "skills": [
                {
                    "name": "Command Center Upgrades",
                    "rank": 4,
                    "recommended_level": 5,
                    "effect_per_level": "Increases CPU and powergrid capacity",
                },
            ],
            "recommended_priority": ["Command Center Upgrades"],
        }
        jsonschema.validate(valid_response, pi_schema)

    def test_pi_invalid_tier_fails(self, pi_schema):
        """Verify invalid product tier fails validation."""
        invalid_response = {
            "product_name": "Invalid",
            "product_tier": "P5",  # Invalid: not in enum
            "inputs": [{"name": "Test", "quantity": 1, "tier": "P1"}],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, pi_schema)

    def test_pi_invalid_planet_type_fails(self, pi_schema):
        """Verify invalid planet type fails validation."""
        invalid_response = {
            "resource_name": "Test Resource",
            "planet_types": ["Desert"],  # Invalid: not in enum
            "produces_p1": "Test P1",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, pi_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestPIFixtureValidation:
    """Run validation tests against PI fixtures."""

    @pytest.fixture
    def pi_schema(self) -> dict[str, Any]:
        """Load PI schema."""
        schema_path = get_schema_path("pi")
        if not schema_path.exists():
            pytest.skip("PI schema not created yet")
        return load_yaml_file(schema_path)

    def test_pi_fixture_schema_validation(
        self,
        pi_fixture_path: Path,
        pi_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate PI outputs against fixtures."""
        fixture = load_yaml_file(pi_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, pi_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Standings Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestStandingsSchemaValidation:
    """Schema validation tests for /standings skill outputs."""

    @pytest.fixture
    def standings_schema(self) -> dict[str, Any]:
        """Load standings schema."""
        schema_path = get_schema_path("standings")
        if not schema_path.exists():
            pytest.skip("Standings schema not created yet")
        return load_yaml_file(schema_path)

    def test_standings_overview_valid(self, standings_schema):
        """Verify valid overview response passes validation."""
        valid_response = {
            "pilot_name": "Test Pilot",
            "skills": {"connections": 5, "diplomacy": 3},
            "faction_standings": [
                {
                    "faction_id": 500004,
                    "faction_name": "Gallente Federation",
                    "raw_standing": 5.5,
                    "effective_standing": 6.4,
                    "status": "friendly",
                },
            ],
            "agent_access_summary": {
                "max_security_level": 4,
                "max_distribution_level": 4,
                "max_research_level": 3,
            },
        }
        jsonschema.validate(valid_response, standings_schema)

    def test_standings_agent_access_valid(self, standings_schema):
        """Verify valid agent access response passes validation."""
        valid_response = {
            "entity_name": "Gallente Federation",
            "entity_type": "faction",
            "raw_standing": 4.0,
            "effective_standing": 5.2,
            "required_level": 4,
            "required_standing": 5.0,
            "has_access": True,
            "calculation": {
                "formula": "effective = raw + (10 - raw) * connections_level * 0.04",
                "skill_name": "Connections",
                "skill_level": 5,
                "skill_bonus": 1.2,
            },
        }
        jsonschema.validate(valid_response, standings_schema)

    def test_standings_plan_valid(self, standings_schema):
        """Verify valid standing plan response passes validation."""
        valid_response = {
            "target_entity": "Caldari State",
            "target_standing": 5.0,
            "current_standing": 2.0,
            "effective_standing": 3.6,
            "gap": 1.4,
            "recommended_path": [
                {
                    "method": "storyline",
                    "description": "Run missions to trigger storylines",
                    "standing_gain": "~0.3-0.5",
                    "frequency": "Every 16 missions",
                    "priority": 1,
                },
            ],
            "estimated_missions": 48,
            "can_use_epic_arc": False,
        }
        jsonschema.validate(valid_response, standings_schema)

    def test_standings_repair_valid(self, standings_schema):
        """Verify valid repair strategy response passes validation."""
        valid_response = {
            "faction_name": "Gallente Federation",
            "current_standing": -3.5,
            "is_hostile": False,
            "navy_aggro_threshold": -5.0,
            "repair_strategies": [
                {
                    "method": "epic_arc",
                    "description": "Run Blood-Stained Stars",
                    "standing_gain": "~10%",
                    "cooldown": "90 days",
                    "requirements": "None",
                },
            ],
            "recommended_strategy": "epic_arc",
        }
        jsonschema.validate(valid_response, standings_schema)

    def test_standings_invalid_entity_type_fails(self, standings_schema):
        """Verify invalid entity type fails validation."""
        invalid_response = {
            "entity_name": "Test Corp",
            "entity_type": "alliance",  # Invalid: not in enum
            "raw_standing": 0.0,
            "effective_standing": 0.0,
            "has_access": False,
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, standings_schema)

    def test_standings_invalid_standing_range_fails(self, standings_schema):
        """Verify standing > 10.0 fails validation."""
        invalid_response = {
            "entity_name": "Test Faction",
            "entity_type": "faction",
            "raw_standing": 11.0,  # Invalid: max is 10.0
            "effective_standing": 11.0,
            "has_access": True,
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, standings_schema)

    def test_standings_invalid_repair_method_fails(self, standings_schema):
        """Verify invalid repair method fails validation."""
        invalid_response = {
            "faction_name": "Test Faction",
            "current_standing": -3.0,
            "repair_strategies": [
                {
                    "method": "bribery",  # Invalid: not in enum
                    "description": "Pay ISK for standing",
                },
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, standings_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestStandingsFixtureValidation:
    """Run validation tests against standings fixtures."""

    @pytest.fixture
    def standings_schema(self) -> dict[str, Any]:
        """Load standings schema."""
        schema_path = get_schema_path("standings")
        if not schema_path.exists():
            pytest.skip("Standings schema not created yet")
        return load_yaml_file(schema_path)

    def test_standings_fixture_schema_validation(
        self,
        standings_fixture_path: Path,
        standings_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate standings outputs against fixtures."""
        fixture = load_yaml_file(standings_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, standings_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Watchlist Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestWatchlistSchemaValidation:
    """Schema validation tests for /watchlist skill outputs."""

    @pytest.fixture
    def watchlist_schema(self) -> dict[str, Any]:
        """Load watchlist schema."""
        schema_path = get_schema_path("watchlist")
        if not schema_path.exists():
            pytest.skip("Watchlist schema not created yet")
        return load_yaml_file(schema_path)

    def test_watchlist_list_response_valid(self, watchlist_schema):
        """Verify valid list response passes validation."""
        valid_response = {
            "watchlists": [
                {
                    "name": "War Targets",
                    "type": "war_targets",
                    "entity_count": 3,
                    "last_sync": "2026-01-30T15:00:00Z",
                }
            ],
            "total_watchlists": 1,
            "total_entities": 3,
        }
        jsonschema.validate(valid_response, watchlist_schema)

    def test_watchlist_show_response_valid(self, watchlist_schema):
        """Verify valid show response passes validation."""
        valid_response = {
            "name": "War Targets",
            "type": "war_targets",
            "entity_count": 2,
            "corporations": [
                {
                    "entity_id": 98000001,
                    "entity_name": "CODE.",
                    "entity_type": "corporation",
                }
            ],
            "alliances": [
                {
                    "entity_id": 99000001,
                    "entity_name": "TEST Alliance",
                    "entity_type": "alliance",
                }
            ],
        }
        jsonschema.validate(valid_response, watchlist_schema)

    def test_watchlist_modify_response_valid(self, watchlist_schema):
        """Verify valid modify response passes validation."""
        valid_response = {
            "success": True,
            "action": "add",
            "watchlist_name": "Hostiles",
            "entity": {
                "entity_id": 98000001,
                "entity_type": "corporation",
            },
            "message": "Added entity",
        }
        jsonschema.validate(valid_response, watchlist_schema)

    def test_watchlist_invalid_type_fails(self, watchlist_schema):
        """Verify invalid watchlist type fails validation."""
        invalid_response = {
            "watchlists": [
                {
                    "name": "Test",
                    "type": "invalid_type",  # Invalid
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, watchlist_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestWatchlistFixtureValidation:
    """Run validation tests against watchlist fixtures."""

    @pytest.fixture
    def watchlist_schema(self) -> dict[str, Any]:
        """Load watchlist schema."""
        schema_path = get_schema_path("watchlist")
        if not schema_path.exists():
            pytest.skip("Watchlist schema not created yet")
        return load_yaml_file(schema_path)

    def test_watchlist_fixture_schema_validation(
        self,
        watchlist_fixture_path: Path,
        watchlist_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate watchlist outputs against fixtures."""
        fixture = load_yaml_file(watchlist_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, watchlist_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Killmail Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestKillmailSchemaValidation:
    """Schema validation tests for /killmail skill outputs."""

    @pytest.fixture
    def killmail_schema(self) -> dict[str, Any]:
        """Load killmail schema."""
        schema_path = get_schema_path("killmail")
        if not schema_path.exists():
            pytest.skip("Killmail schema not created yet")
        return load_yaml_file(schema_path)

    def test_killmail_analysis_response_valid(self, killmail_schema):
        """Verify valid analysis response passes validation."""
        valid_response = {
            "killmail_id": 12345678,
            "killmail_time": "2026-01-15T14:32:18Z",
            "system": {
                "system_id": 30002813,
                "system_name": "Tama",
                "security": 0.28,
            },
            "victim": {
                "ship_type_id": 29986,
                "ship_type_name": "Proteus",
            },
            "attackers": [
                {
                    "character_id": 90000001,
                    "damage_done": 45000,
                    "final_blow": True,
                }
            ],
        }
        jsonschema.validate(valid_response, killmail_schema)

    def test_killmail_error_response_valid(self, killmail_schema):
        """Verify valid error response passes validation."""
        valid_response = {
            "error": True,
            "error_type": "not_found",
            "error_message": "Kill not found",
        }
        jsonschema.validate(valid_response, killmail_schema)

    def test_killmail_invalid_error_type_fails(self, killmail_schema):
        """Verify invalid error type fails validation."""
        invalid_response = {
            "error": True,
            "error_type": "unknown_error",  # Invalid
            "error_message": "Something failed",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, killmail_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestKillmailFixtureValidation:
    """Run validation tests against killmail fixtures."""

    @pytest.fixture
    def killmail_schema(self) -> dict[str, Any]:
        """Load killmail schema."""
        schema_path = get_schema_path("killmail")
        if not schema_path.exists():
            pytest.skip("Killmail schema not created yet")
        return load_yaml_file(schema_path)

    def test_killmail_fixture_schema_validation(
        self,
        killmail_fixture_path: Path,
        killmail_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate killmail outputs against fixtures."""
        fixture = load_yaml_file(killmail_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, killmail_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Assets Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestAssetsSchemaValidation:
    """Schema validation tests for /assets skill outputs."""

    @pytest.fixture
    def assets_schema(self) -> dict[str, Any]:
        """Load assets schema."""
        schema_path = get_schema_path("assets")
        if not schema_path.exists():
            pytest.skip("Assets schema not created yet")
        return load_yaml_file(schema_path)

    def test_assets_overview_response_valid(self, assets_schema):
        """Verify valid overview response passes validation."""
        valid_response = {
            "total_unique_items": 847,
            "total_locations": 12,
            "locations": [
                {
                    "location_id": 60003760,
                    "item_count": 312,
                }
            ],
        }
        jsonschema.validate(valid_response, assets_schema)

    def test_assets_ships_response_valid(self, assets_schema):
        """Verify valid ships response passes validation."""
        valid_response = {
            "filter": "ships",
            "total_ships": 5,
            "ships": [
                {
                    "item_id": 1234567890,
                    "type_id": 17715,
                    "type_name": "Gila",
                    "is_singleton": True,
                }
            ],
        }
        jsonschema.validate(valid_response, assets_schema)

    def test_assets_valuation_response_valid(self, assets_schema):
        """Verify valid valuation response passes validation."""
        valid_response = {
            "filter": "value",
            "total_estimated_value": 1615000000,
            "price_source": "Jita sell orders",
        }
        jsonschema.validate(valid_response, assets_schema)

    def test_assets_negative_value_fails(self, assets_schema):
        """Verify negative value fails validation."""
        invalid_response = {
            "filter": "value",
            "total_estimated_value": -100,  # Invalid
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, assets_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestAssetsFixtureValidation:
    """Run validation tests against assets fixtures."""

    @pytest.fixture
    def assets_schema(self) -> dict[str, Any]:
        """Load assets schema."""
        schema_path = get_schema_path("assets")
        if not schema_path.exists():
            pytest.skip("Assets schema not created yet")
        return load_yaml_file(schema_path)

    def test_assets_fixture_schema_validation(
        self,
        assets_fixture_path: Path,
        assets_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate assets outputs against fixtures."""
        fixture = load_yaml_file(assets_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, assets_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Pilot Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestPilotSchemaValidation:
    """Schema validation tests for /pilot skill outputs."""

    @pytest.fixture
    def pilot_schema(self) -> dict[str, Any]:
        """Load pilot schema."""
        schema_path = get_schema_path("pilot")
        if not schema_path.exists():
            pytest.skip("Pilot schema not created yet")
        return load_yaml_file(schema_path)

    def test_pilot_self_response_valid(self, pilot_schema):
        """Verify valid self-query response passes validation."""
        valid_response = {
            "query_type": "self",
            "character_id": 2123984364,
            "character_name": "Test Pilot",
            "corporation_id": 98000001,
            "corporation_name": "Test Corp",
        }
        jsonschema.validate(valid_response, pilot_schema)

    def test_pilot_public_response_valid(self, pilot_schema):
        """Verify valid public lookup response passes validation."""
        valid_response = {
            "query_type": "public",
            "character_id": 123456789,
            "character_name": "Other Pilot",
            "corporation_id": 98000002,
            "corporation_name": "Other Corp",
            "note": "Public data only. Private data requires authentication.",
        }
        jsonschema.validate(valid_response, pilot_schema)

    def test_pilot_not_found_response_valid(self, pilot_schema):
        """Verify valid not-found response passes validation."""
        valid_response = {
            "query_type": "not_found",
            "error": "Character not found",
            "query": "NonExistentPilot",
            "suggestions": ["Check spelling"],
        }
        jsonschema.validate(valid_response, pilot_schema)

    def test_pilot_missing_required_field_fails(self, pilot_schema):
        """Verify missing required field fails validation."""
        invalid_response = {
            "query_type": "self",
            # Missing: character_id, character_name
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, pilot_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestPilotFixtureValidation:
    """Run validation tests against pilot fixtures."""

    @pytest.fixture
    def pilot_schema(self) -> dict[str, Any]:
        """Load pilot schema."""
        schema_path = get_schema_path("pilot")
        if not schema_path.exists():
            pytest.skip("Pilot schema not created yet")
        return load_yaml_file(schema_path)

    def test_pilot_fixture_schema_validation(
        self,
        pilot_fixture_path: Path,
        pilot_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate pilot outputs against fixtures."""
        fixture = load_yaml_file(pilot_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, pilot_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Skillqueue Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestSkillqueueSchemaValidation:
    """Schema validation tests for /skillqueue skill outputs."""

    @pytest.fixture
    def skillqueue_schema(self) -> dict[str, Any]:
        """Load skillqueue schema."""
        schema_path = get_schema_path("skillqueue")
        if not schema_path.exists():
            pytest.skip("Skillqueue schema not created yet")
        return load_yaml_file(schema_path)

    def test_skillqueue_active_response_valid(self, skillqueue_schema):
        """Verify valid active queue response passes validation."""
        valid_response = {
            "query_timestamp": "2026-01-31T12:30:00Z",
            "volatility": "volatile",
            "queue_status": "active",
            "queue_length": 3,
            "skills": [
                {
                    "queue_position": 0,
                    "skill_id": 3436,
                    "name": "Drones",
                    "target_level": 5,
                }
            ],
        }
        jsonschema.validate(valid_response, skillqueue_schema)

    def test_skillqueue_empty_response_valid(self, skillqueue_schema):
        """Verify valid empty queue response passes validation."""
        valid_response = {
            "query_timestamp": "2026-01-31T12:30:00Z",
            "volatility": "volatile",
            "queue_status": "empty",
            "queue_length": 0,
            "skills": [],
        }
        jsonschema.validate(valid_response, skillqueue_schema)

    def test_skillqueue_error_response_valid(self, skillqueue_schema):
        """Verify valid error response passes validation."""
        valid_response = {
            "error": "Scope not authorized",
            "error_type": "missing_scope",
        }
        jsonschema.validate(valid_response, skillqueue_schema)

    def test_skillqueue_invalid_queue_length_fails(self, skillqueue_schema):
        """Verify negative queue length fails validation."""
        invalid_response = {
            "query_timestamp": "2026-01-31T12:30:00Z",
            "volatility": "volatile",
            "queue_status": "active",
            "queue_length": -1,  # Invalid
            "skills": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, skillqueue_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestSkillqueueFixtureValidation:
    """Run validation tests against skillqueue fixtures."""

    @pytest.fixture
    def skillqueue_schema(self) -> dict[str, Any]:
        """Load skillqueue schema."""
        schema_path = get_schema_path("skillqueue")
        if not schema_path.exists():
            pytest.skip("Skillqueue schema not created yet")
        return load_yaml_file(schema_path)

    def test_skillqueue_fixture_schema_validation(
        self,
        skillqueue_fixture_path: Path,
        skillqueue_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate skillqueue outputs against fixtures."""
        fixture = load_yaml_file(skillqueue_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, skillqueue_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Clones Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestClonesSchemaValidation:
    """Schema validation tests for /clones skill outputs."""

    @pytest.fixture
    def clones_schema(self) -> dict[str, Any]:
        """Load clones schema."""
        schema_path = get_schema_path("clones")
        if not schema_path.exists():
            pytest.skip("Clones schema not created yet")
        return load_yaml_file(schema_path)

    def test_clones_full_status_response_valid(self, clones_schema):
        """Verify valid full clone status response passes validation."""
        valid_response = {
            "query_timestamp": "2026-01-31T12:30:00Z",
            "medical_clone": {
                "location_id": 60011866,
                "location_name": "Masalle Station",
            },
            "jump_clone_count": 2,
            "jump_clones": [],
        }
        jsonschema.validate(valid_response, clones_schema)

    def test_clones_implants_only_response_valid(self, clones_schema):
        """Verify valid implants-only response passes validation."""
        valid_response = {
            "query_timestamp": "2026-01-31T12:30:00Z",
            "response_type": "implants_only",
            "implant_count": 0,
            "implants": [],
        }
        jsonschema.validate(valid_response, clones_schema)

    def test_clones_error_response_valid(self, clones_schema):
        """Verify valid error response passes validation."""
        valid_response = {
            "error": "Clones scope not authorized",
            "error_type": "missing_scope",
        }
        jsonschema.validate(valid_response, clones_schema)

    def test_clones_invalid_implant_slot_fails(self, clones_schema):
        """Verify invalid implant slot fails validation."""
        invalid_response = {
            "query_timestamp": "2026-01-31T12:30:00Z",
            "response_type": "implants_only",
            "implant_count": 1,
            "implants": [
                {"slot": 15}  # Invalid: slot must be 1-10
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, clones_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestClonesFixtureValidation:
    """Run validation tests against clones fixtures."""

    @pytest.fixture
    def clones_schema(self) -> dict[str, Any]:
        """Load clones schema."""
        schema_path = get_schema_path("clones")
        if not schema_path.exists():
            pytest.skip("Clones schema not created yet")
        return load_yaml_file(schema_path)

    def test_clones_fixture_schema_validation(
        self,
        clones_fixture_path: Path,
        clones_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate clones outputs against fixtures."""
        fixture = load_yaml_file(clones_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, clones_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])


# =============================================================================
# Wallet-Journal Skill Schema and Fixture Validation
# =============================================================================


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestWalletJournalSchemaValidation:
    """Schema validation tests for /wallet-journal skill outputs."""

    @pytest.fixture
    def wallet_journal_schema(self) -> dict[str, Any]:
        """Load wallet-journal schema."""
        schema_path = get_schema_path("wallet-journal")
        if not schema_path.exists():
            pytest.skip("Wallet-journal schema not created yet")
        return load_yaml_file(schema_path)

    def test_wallet_journal_summary_response_valid(self, wallet_journal_schema):
        """Verify valid journal summary response passes validation."""
        valid_response = {
            "query_timestamp": "2026-01-31T12:30:00Z",
            "volatility": "semi_stable",
            "period_days": 7,
            "summary": {
                "total_income": 15000000,
                "total_expenses": 3000000,
                "net_change": 12000000,
            },
        }
        jsonschema.validate(valid_response, wallet_journal_schema)

    def test_wallet_journal_no_activity_response_valid(self, wallet_journal_schema):
        """Verify valid no-activity response passes validation."""
        valid_response = {
            "query_timestamp": "2026-01-31T12:30:00Z",
            "period_days": 7,
            "message": "No wallet activity found",
        }
        jsonschema.validate(valid_response, wallet_journal_schema)

    def test_wallet_journal_error_response_valid(self, wallet_journal_schema):
        """Verify valid error response passes validation."""
        valid_response = {
            "error": "Wallet scope not authorized",
            "error_type": "missing_scope",
        }
        jsonschema.validate(valid_response, wallet_journal_schema)

    def test_wallet_journal_invalid_period_fails(self, wallet_journal_schema):
        """Verify invalid period_days fails validation."""
        invalid_response = {
            "query_timestamp": "2026-01-31T12:30:00Z",
            "volatility": "semi_stable",
            "period_days": 0,  # Invalid: must be >= 1
            "summary": {
                "total_income": 0,
                "total_expenses": 0,
                "net_change": 0,
            },
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_response, wallet_journal_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestWalletJournalFixtureValidation:
    """Run validation tests against wallet-journal fixtures."""

    @pytest.fixture
    def wallet_journal_schema(self) -> dict[str, Any]:
        """Load wallet-journal schema."""
        schema_path = get_schema_path("wallet-journal")
        if not schema_path.exists():
            pytest.skip("Wallet-journal schema not created yet")
        return load_yaml_file(schema_path)

    def test_wallet_journal_fixture_schema_validation(
        self,
        wallet_journal_fixture_path: Path,
        wallet_journal_schema: dict[str, Any],
        assert_facts,
    ):
        """Validate wallet-journal outputs against fixtures."""
        fixture = load_yaml_file(wallet_journal_fixture_path)

        if "expected_output" in fixture:
            output = fixture["expected_output"]
            jsonschema.validate(output, wallet_journal_schema)

            if "expected_facts" in fixture:
                assert_facts(output, fixture["expected_facts"])
