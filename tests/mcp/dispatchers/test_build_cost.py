"""
Tests for market build_cost action.

Integration tests with mocked SDE and market data to verify
server-side computation correctness.
"""

from __future__ import annotations

import asyncio
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.models.market import (
    BuildCostBlueprint,
    BuildCostCategorySubtotal,
    BuildCostMaterial,
    BuildCostProfitability,
    BuildCostResult,
)
from aria_esi.services.industry_costs import apply_facility_me, apply_me, format_isk


# =============================================================================
# Test Fixtures
# =============================================================================


def _make_bp_result(
    product_name: str = "Venture",
    blueprint_name: str = "Venture Blueprint",
    product_type_id: int = 32880,
    blueprint_type_id: int = 32881,
    product_quantity: int = 1,
    manufacturing_time: int = 3600,
    materials: list[dict] | None = None,
) -> dict:
    """Create a mock blueprint_info_impl result."""
    if materials is None:
        materials = [
            {"type_id": 34, "type_name": "Tritanium", "quantity": 22000},
            {"type_id": 35, "type_name": "Pyerite", "quantity": 5500},
            {"type_id": 36, "type_name": "Mexallon", "quantity": 3333},
        ]

    return {
        "found": True,
        "query": product_name,
        "searched_as": "product",
        "suggestions": [],
        "warnings": [],
        "blueprint": {
            "blueprint_type_id": blueprint_type_id,
            "blueprint_name": blueprint_name,
            "product_type_id": product_type_id,
            "product_name": product_name,
            "product_quantity": product_quantity,
            "manufacturing_time": manufacturing_time,
            "copying_time": 1800,
            "research_me_time": 600,
            "research_te_time": 600,
            "invention_time": None,
            "max_production_limit": 10,
            "materials": materials,
            "sources": [],
        },
    }


def _make_price(type_id: int, type_name: str, sell_min: float, sell_avg: float = None):
    """Create a mock ItemPrice-like object."""
    if sell_avg is None:
        sell_avg = sell_min * 1.05

    price = MagicMock()
    price.type_id = type_id
    price.type_name = type_name
    price.sell = MagicMock()
    price.sell.min_price = sell_min
    price.sell.weighted_avg = sell_avg
    price.sell.max_price = sell_min * 1.2
    price.sell.order_count = 100
    price.sell.volume = 1000000
    price.buy = MagicMock()
    price.buy.max_price = sell_min * 0.9
    price.freshness = "fresh"
    return price


def _make_type_info(type_id: int, type_name: str):
    """Create a mock type info object."""
    info = MagicMock()
    info.type_id = type_id
    info.type_name = type_name
    return info


# Standard type map for test fixtures
STANDARD_TYPES = {
    "tritanium": (34, "Tritanium"),
    "pyerite": (35, "Pyerite"),
    "mexallon": (36, "Mexallon"),
    "venture": (32880, "Venture"),
}

# Standard prices
STANDARD_PRICES = {
    34: ("Tritanium", 4.32),
    35: ("Pyerite", 9.80),
    36: ("Mexallon", 55.20),
    32880: ("Venture", 500000.0),
}


@pytest.fixture
def mock_deps():
    """Set up all mocks for _build_cost."""
    # Mock blueprint info
    bp_mock = AsyncMock(return_value=_make_bp_result())

    # Mock market database type resolution
    db_mock = MagicMock()

    def resolve_type(name):
        key = name.lower()
        if key in STANDARD_TYPES:
            tid, tname = STANDARD_TYPES[key]
            return _make_type_info(tid, tname)
        return None

    db_mock.resolve_type_name = MagicMock(side_effect=resolve_type)

    # Mock market cache
    cache_mock = MagicMock()

    async def get_prices(type_ids, type_names):
        results = []
        for tid in type_ids:
            if tid in STANDARD_PRICES:
                tname, price = STANDARD_PRICES[tid]
                results.append(_make_price(tid, tname, price))
        return results

    cache_mock.get_prices = AsyncMock(side_effect=get_prices)
    cache_class_mock = MagicMock(return_value=cache_mock)

    patches = {
        "bp": patch(
            "aria_esi.mcp.sde.tools_blueprint._blueprint_info_impl",
            bp_mock,
        ),
        "db": patch(
            "aria_esi.store.market.database.get_market_database",
            return_value=db_mock,
        ),
        "cache": patch(
            "aria_esi.store.market.cache.MarketCache",
            cache_class_mock,
        ),
    }

    return {
        "bp_mock": bp_mock,
        "db_mock": db_mock,
        "cache_mock": cache_mock,
        "cache_class_mock": cache_class_mock,
        "patches": patches,
    }


async def _run_build_cost(mock_deps, **kwargs):
    """Run _build_cost with all mocks applied."""
    from aria_esi.mcp.dispatchers.market import _build_cost

    defaults = {
        "item": "Venture",
        "me_level": 0,
        "runs": 1,
        "facility": None,
        "region": "jita",
    }
    defaults.update(kwargs)

    with (
        mock_deps["patches"]["bp"],
        mock_deps["patches"]["db"],
        mock_deps["patches"]["cache"],
    ):
        return await _build_cost(**defaults)


# =============================================================================
# Happy Path Tests
# =============================================================================


class TestBuildCostHappyPath:
    """Tests for successful build cost calculations."""

    def test_basic_venture_build(self, mock_deps):
        """Basic Venture build with 3 minerals, ME 0."""
        result = asyncio.run(_run_build_cost(mock_deps))

        assert result["blueprint"]["product_name"] == "Venture"
        assert result["blueprint"]["me_level"] == 0
        assert result["blueprint"]["runs"] == 1
        assert result["is_complete"] is True
        assert result["materials_priced"] == 3
        assert result["materials_missing"] == 0
        assert result["complexity"] == "simple"
        assert result["region"] == "The Forge"

        # Verify material costs computed correctly
        mats = {m["type_name"]: m for m in result["materials"]}

        # Tritanium: 22000 * 4.32 = 95,040
        assert mats["Tritanium"]["base_qty"] == 22000
        assert mats["Tritanium"]["me_qty"] == 22000  # ME 0
        assert mats["Tritanium"]["total_qty"] == 22000
        assert mats["Tritanium"]["unit_price"] == 4.32
        assert abs(mats["Tritanium"]["total_cost"] - 95040.0) < 0.01

        # Pyerite: 5500 * 9.80 = 53,900
        assert abs(mats["Pyerite"]["total_cost"] - 53900.0) < 0.01

        # Mexallon: 3333 * 55.20 = 183,981.6
        assert abs(mats["Mexallon"]["total_cost"] - 183981.6) < 0.01

        # Total should be sum of all
        expected_total = 95040.0 + 53900.0 + 183981.6
        assert abs(result["total_material_cost"] - expected_total) < 0.01

        # Formatted strings should exist
        assert "ISK" in result["total_material_cost_formatted"]

    def test_me10_reduces_quantities(self, mock_deps):
        """ME 10 reduces material quantities by 10%."""
        result = asyncio.run(_run_build_cost(mock_deps, me_level=10))

        mats = {m["type_name"]: m for m in result["materials"]}

        # Tritanium: ceil(22000 * 0.90) = 19800
        assert mats["Tritanium"]["me_qty"] == math.ceil(22000 * 0.90)
        # Pyerite: ceil(5500 * 0.90) = 4950
        assert mats["Pyerite"]["me_qty"] == math.ceil(5500 * 0.90)
        # Mexallon: ceil(3333 * 0.90) = 3000
        assert mats["Mexallon"]["me_qty"] == math.ceil(3333 * 0.90)

        assert result["blueprint"]["me_level"] == 10

    def test_multi_run(self, mock_deps):
        """Multiple runs multiply total_qty."""
        result = asyncio.run(_run_build_cost(mock_deps, runs=5))

        mats = {m["type_name"]: m for m in result["materials"]}
        assert mats["Tritanium"]["total_qty"] == 22000 * 5
        assert result["blueprint"]["runs"] == 5

    def test_facility_me_bonus(self, mock_deps):
        """Azbel facility applies 1% ME bonus on top of blueprint ME."""
        result = asyncio.run(_run_build_cost(mock_deps, me_level=10, facility="Azbel"))

        mats = {m["type_name"]: m for m in result["materials"]}

        # Tritanium: apply_me(22000, 10) = 19800, then apply_facility(19800, 1) = ceil(19800 * 0.99) = 19602
        bp_me = apply_me(22000, 10)
        expected = apply_facility_me(bp_me, 1)
        assert mats["Tritanium"]["me_qty"] == expected

        assert result["blueprint"]["facility"] is not None
        assert result["blueprint"]["facility_me_bonus"] == 1.0

    def test_profitability_calculated(self, mock_deps):
        """Profitability is computed when product price available."""
        result = asyncio.run(_run_build_cost(mock_deps))

        prof = result["profitability"]
        assert prof is not None
        assert prof["product_sell_price"] == 500000.0
        assert prof["product_total_value"] == 500000.0  # 1 run, 1 qty
        assert prof["gross_profit"] == 500000.0 - result["total_material_cost"]
        assert prof["profitable"] is True
        assert "ISK" in prof["product_sell_formatted"]
        assert "ISK" in prof["gross_profit_formatted"]

    def test_formatted_strings_present(self, mock_deps):
        """All formatted strings are populated."""
        result = asyncio.run(_run_build_cost(mock_deps))

        # Material formatted strings
        for mat in result["materials"]:
            assert "ISK" in mat["unit_price_formatted"] or mat["unit_price_formatted"] == "N/A"
            assert "ISK" in mat["total_cost_formatted"] or mat["total_cost_formatted"] == "N/A"

        # Category subtotals
        for sub in result["category_subtotals"]:
            assert "ISK" in sub["total_cost_formatted"]

        # Blueprint time
        assert result["blueprint"]["manufacturing_time_formatted"] is not None

    def test_category_subtotals(self, mock_deps):
        """Category subtotals sum material costs correctly."""
        result = asyncio.run(_run_build_cost(mock_deps))

        # All 3 materials are minerals
        subtotals = result["category_subtotals"]
        assert len(subtotals) == 1
        assert subtotals[0]["category"] == "minerals"
        assert subtotals[0]["item_count"] == 3
        assert abs(subtotals[0]["total_cost"] - result["total_material_cost"]) < 0.01


# =============================================================================
# Missing Price Tests
# =============================================================================


class TestBuildCostMissingPrices:
    """Tests for handling missing market data."""

    def test_missing_material_price(self, mock_deps):
        """Material with no price is flagged."""
        # Add an unknown material to the blueprint
        mock_deps["bp_mock"].return_value = _make_bp_result(
            materials=[
                {"type_id": 34, "type_name": "Tritanium", "quantity": 22000},
                {"type_id": 99999, "type_name": "Unobtanium", "quantity": 100},
            ]
        )

        result = asyncio.run(_run_build_cost(mock_deps))

        assert result["is_complete"] is False
        assert result["materials_missing"] == 1
        assert result["materials_priced"] == 1
        assert len(result["warnings"]) > 0
        assert "Unobtanium" in result["warnings"][0]

        # Find the missing material
        mats = {m["type_name"]: m for m in result["materials"]}
        assert mats["Unobtanium"]["price_missing"] is True
        assert mats["Unobtanium"]["total_cost_formatted"] == "N/A"

    def test_product_price_missing_no_profitability(self, mock_deps):
        """No profitability when product price unavailable."""
        # Use a product that's not in our price map
        mock_deps["bp_mock"].return_value = _make_bp_result(
            product_name="Unknown Ship",
            product_type_id=88888,
        )

        result = asyncio.run(_run_build_cost(mock_deps))

        assert result["profitability"] is None


# =============================================================================
# Blueprint Not Found Tests
# =============================================================================


class TestBuildCostNotFound:
    """Tests for blueprint-not-found cases."""

    def test_blueprint_not_found(self, mock_deps):
        """Returns suggestions when blueprint not found."""
        mock_deps["bp_mock"].return_value = {
            "found": False,
            "query": "Nonexistent Ship",
            "searched_as": "product",
            "suggestions": ["Venture", "Vexor"],
            "warnings": [],
            "blueprint": None,
        }

        result = asyncio.run(_run_build_cost(mock_deps))

        assert result["found"] is False
        assert "Venture" in result["suggestions"]
        assert len(result["warnings"]) > 0


# =============================================================================
# Complexity Tests
# =============================================================================


class TestBuildCostComplexity:
    """Tests for complexity classification."""

    def test_minerals_only_is_simple(self, mock_deps):
        """All-mineral blueprints are simple."""
        result = asyncio.run(_run_build_cost(mock_deps))
        assert result["complexity"] == "simple"

    def test_pi_material_is_moderate(self, mock_deps):
        """PI materials bump complexity to moderate."""
        mock_deps["bp_mock"].return_value = _make_bp_result(
            materials=[
                {"type_id": 34, "type_name": "Tritanium", "quantity": 22000},
                {"type_id": 99001, "type_name": "Coolant", "quantity": 50},
            ]
        )

        # Add Coolant to type resolution and prices
        orig_resolve = mock_deps["db_mock"].resolve_type_name.side_effect

        def resolve_with_coolant(name):
            if name.lower() == "coolant":
                return _make_type_info(99001, "Coolant")
            return orig_resolve(name)

        mock_deps["db_mock"].resolve_type_name.side_effect = resolve_with_coolant

        orig_prices = mock_deps["cache_mock"].get_prices.side_effect
        prices_with_coolant = dict(STANDARD_PRICES)
        prices_with_coolant[99001] = ("Coolant", 8000.0)

        async def get_prices_extended(type_ids, type_names):
            results = []
            for tid in type_ids:
                if tid in prices_with_coolant:
                    tname, price = prices_with_coolant[tid]
                    results.append(_make_price(tid, tname, price))
            return results

        mock_deps["cache_mock"].get_prices.side_effect = get_prices_extended

        result = asyncio.run(_run_build_cost(mock_deps))
        assert result["complexity"] == "moderate"


# =============================================================================
# Model Serialization Tests
# =============================================================================


class TestBuildCostModels:
    """Tests for Pydantic model construction and serialization."""

    def test_build_cost_result_serializes(self):
        """BuildCostResult can be constructed and serialized."""
        result = BuildCostResult(
            blueprint=BuildCostBlueprint(
                blueprint_type_id=32881,
                blueprint_name="Venture Blueprint",
                product_type_id=32880,
                product_name="Venture",
                product_quantity=1,
                manufacturing_time=3600,
                manufacturing_time_formatted="1h",
                me_level=10,
                runs=1,
                facility="Azbel",
                facility_me_bonus=1.0,
            ),
            materials=[
                BuildCostMaterial(
                    type_id=34,
                    type_name="Tritanium",
                    category="minerals",
                    base_qty=22000,
                    me_qty=19800,
                    total_qty=19800,
                    unit_price=4.32,
                    unit_price_formatted="4 ISK",
                    total_cost=85536.0,
                    total_cost_formatted="85.5K ISK",
                    price_missing=False,
                )
            ],
            category_subtotals=[
                BuildCostCategorySubtotal(
                    category="minerals",
                    category_label="Minerals",
                    item_count=1,
                    total_cost=85536.0,
                    total_cost_formatted="85.5K ISK",
                )
            ],
            total_material_cost=85536.0,
            total_material_cost_formatted="85.5K ISK",
            complexity="simple",
            profitability=BuildCostProfitability(
                product_sell_price=500000.0,
                product_sell_formatted="500.0K ISK",
                product_total_value=500000.0,
                product_total_formatted="500.0K ISK",
                gross_profit=414464.0,
                gross_profit_formatted="414.5K ISK",
                margin_pct=82.9,
                profitable=True,
            ),
            region="The Forge",
            materials_priced=1,
            materials_missing=0,
            is_complete=True,
            warnings=[],
        )

        dumped = result.model_dump()
        assert dumped["blueprint"]["product_name"] == "Venture"
        assert dumped["total_material_cost"] == 85536.0
        assert dumped["is_complete"] is True

    def test_build_cost_result_no_profitability(self):
        """BuildCostResult with profitability=None serializes."""
        result = BuildCostResult(
            blueprint=BuildCostBlueprint(
                blueprint_type_id=1,
                blueprint_name="Test BP",
                product_type_id=2,
                product_name="Test Product",
                product_quantity=1,
                me_level=0,
                runs=1,
                facility_me_bonus=0.0,
            ),
            materials=[],
            category_subtotals=[],
            total_material_cost=0.0,
            total_material_cost_formatted="0 ISK",
            complexity="simple",
            profitability=None,
            region="The Forge",
            materials_priced=0,
            materials_missing=0,
            is_complete=True,
        )

        dumped = result.model_dump()
        assert dumped["profitability"] is None


# =============================================================================
# Format Verification Tests
# =============================================================================


class TestFormatIsk:
    """Tests for format_isk producing expected strings."""

    def test_small_amount(self):
        assert format_isk(4.32) == "4 ISK"

    def test_thousands(self):
        assert format_isk(95040.0) == "95.0K ISK"

    def test_millions(self):
        assert format_isk(137000000.0) == "137.0M ISK"

    def test_billions(self):
        assert format_isk(1500000000.0) == "1.5B ISK"


# =============================================================================
# ME Application Tests
# =============================================================================


class TestMEApplication:
    """Tests for ME formula correctness."""

    def test_me0_no_change(self):
        assert apply_me(22000, 0) == 22000

    def test_me10_reduces_by_10pct(self):
        assert apply_me(22000, 10) == math.ceil(22000 * 0.90)

    def test_me5_reduces_by_5pct(self):
        assert apply_me(22000, 5) == math.ceil(22000 * 0.95)

    def test_me_ceil_rounding(self):
        # 3333 * 0.90 = 2999.7 -> ceil = 3000
        assert apply_me(3333, 10) == 3000

    def test_facility_me_bonus(self):
        # 19800 * 0.99 = 19602.0 -> ceil = 19602
        assert apply_facility_me(19800, 1) == 19602
