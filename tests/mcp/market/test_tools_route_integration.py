"""
Tests for Market Route MCP Tools (integration-style).

Tests gank threshold lookup, risk classification, cargo value
calculation, route validation, and clipboard input parsing for
the market_route_value tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.mcp.market.tools_route import (
    GANK_THRESHOLDS,
    KNOWN_GANK_SYSTEMS,
    classify_risk,
    get_gank_threshold,
    register_route_tools,
)
from aria_esi.models.market import (
    ItemPrice,
    PriceAggregate,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@dataclass
class TypeInfo:
    """Mock type info returned by resolve_type_name."""

    type_id: int
    type_name: str


def _make_price(
    type_id: int,
    type_name: str,
    sell_min: float = 100.0,
    buy_max: float = 90.0,
) -> ItemPrice:
    """Factory for creating ItemPrice objects."""
    return ItemPrice(
        type_id=type_id,
        type_name=type_name,
        buy=PriceAggregate(
            order_count=10,
            volume=1000,
            min_price=buy_max * 0.9 if buy_max else None,
            max_price=buy_max,
            weighted_avg=buy_max * 0.95 if buy_max else None,
        ),
        sell=PriceAggregate(
            order_count=20,
            volume=2000,
            min_price=sell_min,
            max_price=sell_min * 1.1 if sell_min else None,
            weighted_avg=sell_min * 1.05 if sell_min else None,
        ),
        freshness="fresh",
    )


@pytest.fixture
def route_tools():
    """Register route tools and yield tools dict with mocks."""
    server = MagicMock()
    tools = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    server.tool = tool_decorator

    with (
        patch("aria_esi.mcp.market.tools_route.get_market_database") as mock_db_fn,
        patch("aria_esi.mcp.market.tools_route.MarketCache") as mock_cache_cls,
    ):
        register_route_tools(server)
        yield tools, mock_db_fn, mock_cache_cls


# =============================================================================
# get_gank_threshold Tests
# =============================================================================


class TestGetGankThreshold:
    """Tests for security-based gank threshold lookup."""

    def test_high_security_1_0(self):
        """Security >= 0.95 returns 1.0 threshold."""
        assert get_gank_threshold(1.0) == GANK_THRESHOLDS["1.0"]
        assert get_gank_threshold(0.95) == GANK_THRESHOLDS["1.0"]

    def test_high_security_0_9(self):
        """Security 0.85-0.94 returns 0.9 threshold."""
        assert get_gank_threshold(0.9) == GANK_THRESHOLDS["0.9"]
        assert get_gank_threshold(0.85) == GANK_THRESHOLDS["0.9"]

    def test_high_security_0_8(self):
        """Security 0.75-0.84 returns 0.8 threshold."""
        assert get_gank_threshold(0.8) == GANK_THRESHOLDS["0.8"]

    def test_high_security_0_7(self):
        """Security 0.65-0.74 returns 0.7 threshold."""
        assert get_gank_threshold(0.7) == GANK_THRESHOLDS["0.7"]

    def test_high_security_0_6(self):
        """Security 0.55-0.64 returns 0.6 threshold."""
        assert get_gank_threshold(0.6) == GANK_THRESHOLDS["0.6"]

    def test_high_security_0_5(self):
        """Security 0.45-0.54 returns 0.5 threshold."""
        assert get_gank_threshold(0.5) == GANK_THRESHOLDS["0.5"]

    def test_low_security(self):
        """Security 0.0-0.44 returns low-sec threshold."""
        assert get_gank_threshold(0.4) == GANK_THRESHOLDS["low"]
        assert get_gank_threshold(0.0) == GANK_THRESHOLDS["low"]

    def test_null_security(self):
        """Negative security returns null-sec threshold."""
        assert get_gank_threshold(-0.5) == GANK_THRESHOLDS["null"]
        assert get_gank_threshold(-1.0) == GANK_THRESHOLDS["null"]

    def test_boundary_0_45(self):
        """Security exactly 0.45 returns 0.5 threshold (high-sec border)."""
        assert get_gank_threshold(0.45) == GANK_THRESHOLDS["0.5"]

    def test_boundary_0_44(self):
        """Security 0.44 returns low-sec threshold."""
        assert get_gank_threshold(0.44) == GANK_THRESHOLDS["low"]


# =============================================================================
# classify_risk Tests
# =============================================================================


class TestClassifyRisk:
    """Tests for risk level classification."""

    def test_known_gank_system_high_value_escalates_to_extreme(self):
        """Uedama with high-value cargo escalates to extreme."""
        threshold = GANK_THRESHOLDS["0.5"]
        cargo_value = threshold * 0.6  # Above 0.5 * threshold
        result = classify_risk(cargo_value, threshold, 0.5, "Uedama")
        assert result == "extreme"

    def test_known_gank_system_medium_risk_escalates(self):
        """Known medium-risk system escalates with valuable cargo."""
        threshold = GANK_THRESHOLDS["0.6"]
        cargo_value = threshold * 0.6  # Above 0.5 * threshold
        result = classify_risk(cargo_value, threshold, 0.6, "Madirmilire")
        assert result == "high"

    def test_known_gank_system_moderate_value(self):
        """Known gank system with moderate cargo value."""
        threshold = GANK_THRESHOLDS["0.5"]
        cargo_value = threshold * 0.25  # Above 0.2 but below 0.5
        result = classify_risk(cargo_value, threshold, 0.5, "Uedama")
        assert result == "high"

    def test_low_sec_always_at_least_medium(self):
        """Low-sec systems are always at least medium risk."""
        threshold = GANK_THRESHOLDS["low"]
        cargo_value = 1.0  # Minimal cargo
        result = classify_risk(cargo_value, threshold, 0.3, "SomeLowsecSystem")
        assert result == "medium"

    def test_low_sec_extreme_with_high_cargo(self):
        """Low-sec with cargo exceeding threshold is extreme."""
        threshold = GANK_THRESHOLDS["low"]
        cargo_value = threshold * 2.0
        result = classify_risk(cargo_value, threshold, 0.3, "SomeLowsecSystem")
        assert result == "extreme"

    def test_low_sec_high_risk(self):
        """Low-sec with cargo above half threshold is high risk."""
        threshold = GANK_THRESHOLDS["low"]
        cargo_value = threshold * 0.7
        result = classify_risk(cargo_value, threshold, 0.3, "SomeLowsecSystem")
        assert result == "high"

    def test_high_sec_extreme_ratio(self):
        """High-sec with cargo > 2x threshold is extreme."""
        threshold = GANK_THRESHOLDS["0.8"]
        cargo_value = threshold * 2.5
        result = classify_risk(cargo_value, threshold, 0.8, "SafeSystem")
        assert result == "extreme"

    def test_high_sec_high_ratio(self):
        """High-sec with cargo between 1-2x threshold is high."""
        threshold = GANK_THRESHOLDS["0.8"]
        cargo_value = threshold * 1.5
        result = classify_risk(cargo_value, threshold, 0.8, "SafeSystem")
        assert result == "high"

    def test_high_sec_medium_ratio(self):
        """High-sec with cargo between 0.5-1x threshold is medium."""
        threshold = GANK_THRESHOLDS["0.8"]
        cargo_value = threshold * 0.7
        result = classify_risk(cargo_value, threshold, 0.8, "SafeSystem")
        assert result == "medium"

    def test_high_sec_low_ratio(self):
        """High-sec with cargo between 0.1-0.5x threshold is low."""
        threshold = GANK_THRESHOLDS["0.8"]
        cargo_value = threshold * 0.2
        result = classify_risk(cargo_value, threshold, 0.8, "SafeSystem")
        assert result == "low"

    def test_high_sec_safe(self):
        """High-sec with cargo < 0.1x threshold is safe."""
        threshold = GANK_THRESHOLDS["0.8"]
        cargo_value = threshold * 0.05
        result = classify_risk(cargo_value, threshold, 0.8, "SafeSystem")
        assert result == "safe"

    def test_zero_cargo_is_safe(self):
        """Zero cargo value is safe."""
        threshold = GANK_THRESHOLDS["0.8"]
        result = classify_risk(0.0, threshold, 0.8, "SafeSystem")
        assert result == "safe"


# =============================================================================
# market_route_value Tool Tests
# =============================================================================


class TestMarketRouteValue:
    """Tests for the market_route_value tool."""

    @pytest.mark.asyncio
    async def test_no_items_returns_error(self, route_tools):
        """Empty items list returns NO_ITEMS error."""
        tools, _, _ = route_tools

        result = await tools["market_route_value"](
            items=[], route=["Jita", "Perimeter"]
        )

        assert result["error"]["code"] == "NO_ITEMS"

    @pytest.mark.asyncio
    async def test_invalid_route_returns_error(self, route_tools):
        """Route with fewer than 2 systems returns INVALID_ROUTE."""
        tools, _, _ = route_tools

        result = await tools["market_route_value"](
            items=[{"name": "PLEX", "quantity": 1}], route=["Jita"]
        )

        assert result["error"]["code"] == "INVALID_ROUTE"

    @pytest.mark.asyncio
    async def test_no_items_resolved_returns_error(self, route_tools):
        """All items failing resolution returns NO_ITEMS_RESOLVED."""
        tools, mock_db_fn, mock_cache_cls = route_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = None

        result = await tools["market_route_value"](
            items=[{"name": "FakeItem", "quantity": 1}],
            route=["Jita", "Perimeter"],
        )

        assert result["error"]["code"] == "NO_ITEMS_RESOLVED"

    @pytest.mark.asyncio
    async def test_happy_path_with_universe(self, route_tools):
        """Full route value calculation with universe data."""
        tools, mock_db_fn, mock_cache_cls = route_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(44992, "PLEX")

        cache = MagicMock()
        mock_cache_cls.return_value = cache
        cache.get_prices = AsyncMock(
            return_value=[_make_price(44992, "PLEX", sell_min=3_500_000.0, buy_max=3_400_000.0)]
        )

        # Mock universe
        mock_universe = MagicMock()
        mock_universe.resolve_name.side_effect = lambda n: {"Jita": 0, "Perimeter": 1}.get(n)
        mock_universe.security = [0.95, 0.93]
        mock_universe.system_ids = [30000142, 30000144]
        mock_universe.idx_to_name = {0: "Jita", 1: "Perimeter"}

        with patch("aria_esi.mcp.tools.get_universe", return_value=mock_universe):
            # Also mock get_activity_cache to avoid import errors
            with patch("aria_esi.mcp.activity.get_activity_cache", side_effect=ImportError):
                result = await tools["market_route_value"](
                    items=[{"name": "PLEX", "quantity": 10}],
                    route=["Jita", "Perimeter"],
                )

        assert result["total_value"] > 0
        assert result["item_count"] == 10
        assert len(result["route_systems"]) == 2
        assert result["route_systems"][0]["system"] == "Jita"
        assert result["overall_risk"] in ("safe", "low", "medium", "high", "extreme")
        assert result["recommendation"] != ""

    @pytest.mark.asyncio
    async def test_clipboard_string_input_parsing(self, route_tools):
        """String input is parsed via clipboard parser."""
        tools, mock_db_fn, mock_cache_cls = route_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        cache = MagicMock()
        mock_cache_cls.return_value = cache
        cache.get_prices = AsyncMock(
            return_value=[_make_price(34, "Tritanium", sell_min=6.5)]
        )

        mock_universe = MagicMock()
        mock_universe.resolve_name.side_effect = lambda n: {"Jita": 0, "Amarr": 1}.get(n)
        mock_universe.security = [0.95, 1.0]
        mock_universe.system_ids = [30000142, 30002187]
        mock_universe.idx_to_name = {0: "Jita", 1: "Amarr"}

        with patch("aria_esi.mcp.tools.get_universe", return_value=mock_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", side_effect=ImportError):
                result = await tools["market_route_value"](
                    items="Tritanium\t1000000",
                    route=["Jita", "Amarr"],
                )

        assert result["total_value"] > 0
        assert result["item_count"] == 1000000

    @pytest.mark.asyncio
    async def test_universe_unavailable_produces_warning(self, route_tools):
        """Universe graph failure produces warning, not crash."""
        tools, mock_db_fn, mock_cache_cls = route_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        cache = MagicMock()
        mock_cache_cls.return_value = cache
        cache.get_prices = AsyncMock(
            return_value=[_make_price(34, "Tritanium")]
        )

        with patch(
            "aria_esi.mcp.tools.get_universe",
            side_effect=RuntimeError("Universe not loaded"),
        ):
            result = await tools["market_route_value"](
                items=[{"name": "Tritanium", "quantity": 100}],
                route=["Jita", "Perimeter"],
            )

        assert len(result["warnings"]) >= 1
        assert "universe graph unavailable" in result["warnings"][0].lower()

    @pytest.mark.asyncio
    async def test_unknown_route_system_produces_warning(self, route_tools):
        """Unknown systems in route produce warnings."""
        tools, mock_db_fn, mock_cache_cls = route_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        cache = MagicMock()
        mock_cache_cls.return_value = cache
        cache.get_prices = AsyncMock(
            return_value=[_make_price(34, "Tritanium")]
        )

        mock_universe = MagicMock()
        mock_universe.resolve_name.side_effect = lambda n: {"Jita": 0}.get(n)
        mock_universe.security = [0.95]
        mock_universe.system_ids = [30000142]
        mock_universe.idx_to_name = {0: "Jita"}

        with patch("aria_esi.mcp.tools.get_universe", return_value=mock_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", side_effect=ImportError):
                result = await tools["market_route_value"](
                    items=[{"name": "Tritanium", "quantity": 100}],
                    route=["Jita", "NonexistentSystem"],
                )

        assert any("Unknown system" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_invalid_price_type_defaults_to_sell(self, route_tools):
        """Invalid price_type defaults to sell."""
        tools, mock_db_fn, mock_cache_cls = route_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        cache = MagicMock()
        mock_cache_cls.return_value = cache
        cache.get_prices = AsyncMock(
            return_value=[_make_price(34, "Tritanium", sell_min=6.5)]
        )

        mock_universe = MagicMock()
        mock_universe.resolve_name.return_value = 0
        mock_universe.security = [0.95]
        mock_universe.system_ids = [30000142]
        mock_universe.idx_to_name = {0: "Jita"}

        with patch("aria_esi.mcp.tools.get_universe", return_value=mock_universe):
            with patch("aria_esi.mcp.activity.get_activity_cache", side_effect=ImportError):
                result = await tools["market_route_value"](
                    items=[{"name": "Tritanium", "quantity": 100}],
                    route=["Jita", "Jita"],
                    price_type="invalid",
                )

        # Should not crash; price_type corrected internally to "sell"
        assert result["total_value"] > 0
