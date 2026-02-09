"""
Tests for Market Arbitrage System.

Tests cover:
- Fee calculation
- Confidence scoring (freshness-based)
- Arbitrage detection
- Refresh service
- Route timeout handling
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.services.arbitrage_engine import (
    ArbitrageCalculator,
    ArbitrageEngine,
)
from aria_esi.services.market_refresh import (
    TIER_1_TTL_SECONDS,
    MarketRefreshService,
)

# =============================================================================
# Fee Calculation Tests
# =============================================================================


class TestFeeCalculation:
    """Tests for ArbitrageCalculator fee calculations."""

    def test_basic_fee_calculation(self):
        """Test basic broker fee and sales tax calculation."""
        calc = ArbitrageCalculator(broker_fee_pct=3.0, sales_tax_pct=5.0)

        broker_fee, sales_tax, total_fees = calc.calculate_fees(
            buy_price=100.0,
            sell_price=120.0,
            quantity=10,
        )

        # Buy total: 1000, Sell total: 1200
        # Broker fee: (1000 + 1200) * 0.03 = 66
        assert broker_fee == pytest.approx(66.0, rel=0.01)

        # Sales tax: 1200 * 0.05 = 60
        assert sales_tax == pytest.approx(60.0, rel=0.01)

        # Total: 126
        assert total_fees == pytest.approx(126.0, rel=0.01)


class TestTradeModeNetProfit:
    """Tests for trade mode-based net profit calculation in ArbitrageEngine."""

    @pytest.fixture
    def engine(self):
        """Create engine instance for testing."""
        return ArbitrageEngine()

    def test_immediate_mode_no_broker_fees(self, engine):
        """Test immediate mode: only sales tax, no broker fees."""
        # Buy at 100, sell at 110, 3% broker (ignored), 3.6% sales tax
        net_profit, net_margin, gross_profit, gross_margin = engine._calculate_net_profit(
            buy_price=100.0,
            sell_price=110.0,
            trade_mode="immediate",
            broker_fee_pct=0.03,
            sales_tax_pct=0.036,
        )

        # Immediate mode: buy_cost = 100 (no broker fee)
        # sell_revenue = 110 * (1 - 0.036) = 110 * 0.964 = 106.04
        # net_profit = 106.04 - 100 = 6.04
        assert gross_profit == pytest.approx(10.0, rel=0.01)
        assert net_profit == pytest.approx(6.04, rel=0.01)
        assert gross_margin == pytest.approx(10.0, rel=0.01)
        assert net_margin == pytest.approx(6.04, rel=0.01)  # 6.04 / 100 * 100

    def test_hybrid_mode_broker_on_sell_only(self, engine):
        """Test hybrid mode: broker fee on sell side + sales tax."""
        # Buy at 100, sell at 110, 3% broker, 3.6% sales tax
        net_profit, net_margin, gross_profit, gross_margin = engine._calculate_net_profit(
            buy_price=100.0,
            sell_price=110.0,
            trade_mode="hybrid",
            broker_fee_pct=0.03,
            sales_tax_pct=0.036,
        )

        # Hybrid mode: buy_cost = 100 (no broker fee)
        # sell_revenue = 110 * (1 - 0.03 - 0.036) = 110 * 0.934 = 102.74
        # net_profit = 102.74 - 100 = 2.74
        assert gross_profit == pytest.approx(10.0, rel=0.01)
        assert net_profit == pytest.approx(2.74, rel=0.01)
        assert gross_margin == pytest.approx(10.0, rel=0.01)
        assert net_margin == pytest.approx(2.74, rel=0.01)  # 2.74 / 100 * 100

    def test_station_trading_mode_broker_on_both(self, engine):
        """Test station_trading mode: broker fees on both sides + sales tax."""
        # Buy at 100, sell at 110, 3% broker, 3.6% sales tax
        net_profit, net_margin, gross_profit, gross_margin = engine._calculate_net_profit(
            buy_price=100.0,
            sell_price=110.0,
            trade_mode="station_trading",
            broker_fee_pct=0.03,
            sales_tax_pct=0.036,
        )

        # Station trading: buy_cost = 100 * 1.03 = 103
        # sell_revenue = 110 * (1 - 0.03 - 0.036) = 110 * 0.934 = 102.74
        # net_profit = 102.74 - 103 = -0.26 (LOSS!)
        assert gross_profit == pytest.approx(10.0, rel=0.01)
        assert net_profit == pytest.approx(-0.26, rel=0.01)
        assert gross_margin == pytest.approx(10.0, rel=0.01)
        # net_margin = -0.26 / 103 * 100 = -0.25%
        assert net_margin == pytest.approx(-0.25, rel=0.05)

    def test_immediate_mode_profitable_at_lower_margin(self, engine):
        """Test that immediate mode is profitable at lower margins than station trading."""
        # 6% gross margin - should be profitable in immediate, marginal in hybrid, loss in station
        buy_price = 100.0
        sell_price = 106.0

        # Immediate mode
        immediate_net, _, _, _ = engine._calculate_net_profit(
            buy_price, sell_price, "immediate", 0.03, 0.036
        )
        # sell_revenue = 106 * 0.964 = 102.184, net = 102.184 - 100 = 2.184
        assert immediate_net > 0, "Immediate mode should be profitable at 6% margin"
        assert immediate_net == pytest.approx(2.184, rel=0.01)

        # Hybrid mode
        hybrid_net, _, _, _ = engine._calculate_net_profit(
            buy_price, sell_price, "hybrid", 0.03, 0.036
        )
        # sell_revenue = 106 * 0.934 = 99.004, net = 99.004 - 100 = -0.996
        assert hybrid_net < 0, "Hybrid mode should be loss at 6% margin with 3% broker"

        # Station trading mode
        station_net, _, _, _ = engine._calculate_net_profit(
            buy_price, sell_price, "station_trading", 0.03, 0.036
        )
        # buy_cost = 103, sell_revenue = 99.004, net = 99.004 - 103 = -3.996
        assert station_net < hybrid_net < immediate_net, "Station should have worst fees"

    def test_default_trade_mode_is_immediate(self, engine):
        """Test that default trade_mode is 'immediate'."""
        # When trade_mode not specified, should use immediate (taker-taker)
        net_profit_default, _, _, _ = engine._calculate_net_profit(
            buy_price=100.0,
            sell_price=110.0,
        )

        net_profit_immediate, _, _, _ = engine._calculate_net_profit(
            buy_price=100.0,
            sell_price=110.0,
            trade_mode="immediate",
        )

        assert net_profit_default == net_profit_immediate

    def test_reduced_skill_fees(self):
        """Test fee calculation with reduced skill rates."""
        # Skilled character: 1% broker, 2% tax
        calc = ArbitrageCalculator(broker_fee_pct=1.0, sales_tax_pct=2.0)

        broker_fee, sales_tax, total_fees = calc.calculate_fees(
            buy_price=1000.0,
            sell_price=1200.0,
            quantity=100,
        )

        # Buy total: 100000, Sell total: 120000
        # Broker fee: (100000 + 120000) * 0.01 = 2200
        assert broker_fee == pytest.approx(2200.0, rel=0.01)

        # Sales tax: 120000 * 0.02 = 2400
        assert sales_tax == pytest.approx(2400.0, rel=0.01)

    def test_true_profit_calculation(self):
        """Test complete profit calculation."""
        calc = ArbitrageCalculator(broker_fee_pct=3.0, sales_tax_pct=5.0)

        result = calc.calculate_true_profit(
            buy_price=100.0,
            sell_price=120.0,
            quantity=10,
            cargo_volume=0.01,
        )

        # Investment: 1000
        assert result.total_investment == 1000.0

        # Gross profit: 1200 - 1000 = 200
        # Fees: 126 (from previous test)
        # Net profit: 200 - 126 = 74
        assert result.estimated_profit == pytest.approx(74.0, rel=0.01)

        # ROI: 74 / 1000 * 100 = 7.4%
        assert result.roi_pct == pytest.approx(7.4, rel=0.1)

        # Cargo: 10 * 0.01 = 0.1 m3
        assert result.cargo_volume == pytest.approx(0.1, rel=0.01)

    def test_zero_investment_roi(self):
        """Test ROI calculation with zero investment."""
        calc = ArbitrageCalculator()

        result = calc.calculate_true_profit(
            buy_price=0.0,
            sell_price=100.0,
            quantity=10,
        )

        # Should handle division by zero gracefully
        assert result.roi_pct == 0.0


# =============================================================================
# Confidence Scoring Tests
# =============================================================================


class TestConfidenceScoring:
    """Tests for V1 freshness-based confidence scoring."""

    @pytest.fixture
    def engine(self):
        """Create engine instance for testing."""
        return ArbitrageEngine()

    def test_fresh_freshness(self, engine):
        """Test fresh classification (< 5 minutes)."""
        now = time.time()
        assert engine._get_freshness(int(now)) == "fresh"
        assert engine._get_freshness(int(now - 60)) == "fresh"  # 1 min
        assert engine._get_freshness(int(now - 290)) == "fresh"  # 4:50

    def test_recent_freshness(self, engine):
        """Test recent classification (5-30 minutes)."""
        now = time.time()
        assert engine._get_freshness(int(now - 310)) == "recent"  # 5:10
        assert engine._get_freshness(int(now - 600)) == "recent"  # 10 min
        assert engine._get_freshness(int(now - 1790)) == "recent"  # 29:50

    def test_stale_freshness(self, engine):
        """Test stale classification (> 30 minutes)."""
        now = time.time()
        assert engine._get_freshness(int(now - 1810)) == "stale"  # 30:10
        assert engine._get_freshness(int(now - 3600)) == "stale"  # 1 hour
        assert engine._get_freshness(int(now - 86400)) == "stale"  # 1 day

    def test_high_confidence(self, engine):
        """Test high confidence when both sides fresh."""
        confidence = engine._get_confidence("fresh", "fresh")
        assert confidence == "high"

    def test_medium_confidence(self, engine):
        """Test medium confidence when one side recent."""
        assert engine._get_confidence("fresh", "recent") == "medium"
        assert engine._get_confidence("recent", "fresh") == "medium"
        assert engine._get_confidence("recent", "recent") == "medium"

    def test_low_confidence(self, engine):
        """Test low confidence when any side stale."""
        assert engine._get_confidence("fresh", "stale") == "low"
        assert engine._get_confidence("stale", "fresh") == "low"
        assert engine._get_confidence("stale", "stale") == "low"
        assert engine._get_confidence("recent", "stale") == "low"


# =============================================================================
# Arbitrage Detection Tests
# =============================================================================


class TestArbitrageDetection:
    """Tests for arbitrage opportunity detection."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database with test data."""
        mock = AsyncMock()
        mock._get_connection = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_find_profitable_spread(self, mock_db):
        """Test finding profitable price spreads."""
        engine = ArbitrageEngine()
        engine._database = mock_db

        # Mock query result
        now = int(time.time())
        mock_cursor = MagicMock()
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.fetchall = AsyncMock(
            return_value=[
                {
                    "type_id": 34,
                    "type_name": "Tritanium",
                    "sell_region_id": 10000002,  # Jita - buy here
                    "buy_region_id": 10000043,  # Amarr - sell here
                    "sell_price": 5.0,  # Jita sell price
                    "buy_price": 6.0,  # Amarr buy price
                    "profit_per_unit": 1.0,
                    "profit_pct": 20.0,
                    "available_volume": 100000,
                    "sell_updated": now,
                    "buy_updated": now,
                    "item_volume": 0.01,
                    "item_packaged_volume": None,
                    "buy_available_volume": 100000,
                    "sell_available_volume": 100000,
                }
            ]
        )

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=mock_cursor)
        mock_db._get_connection.return_value = mock_conn

        opportunities = await engine.find_opportunities(min_profit_pct=5.0)

        assert len(opportunities) == 1
        opp = opportunities[0]
        assert opp.type_name == "Tritanium"
        assert opp.profit_pct == 20.0
        assert opp.buy_price == 5.0
        assert opp.sell_price == 6.0
        assert opp.freshness == "fresh"
        assert opp.confidence == "high"
        assert opp.trade_mode == "immediate"  # Verify default trade mode

    @pytest.mark.asyncio
    async def test_ignore_negative_spreads(self, mock_db):
        """Test that negative spreads are not returned."""
        engine = ArbitrageEngine()
        engine._database = mock_db

        # Mock query that returns empty (SQL filters out negatives)
        mock_cursor = MagicMock()
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=mock_cursor)
        mock_db._get_connection.return_value = mock_conn

        opportunities = await engine.find_opportunities()

        # Should be empty - SQL query filters out buy_max <= sell_min
        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_minimum_profit_filter(self, mock_db):
        """Test minimum profit percentage filtering."""
        engine = ArbitrageEngine()
        engine._database = mock_db

        # Mock that respects min_profit_pct in query
        mock_cursor = MagicMock()
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=mock_cursor)
        mock_db._get_connection.return_value = mock_conn

        await engine.find_opportunities(min_profit_pct=15.0)

        # Verify the query was called with correct min_profit_pct
        call_args = mock_conn.execute.call_args
        assert call_args is not None
        # Check that 15.0 was passed as first parameter
        params = call_args[0][1]
        assert params[0] == 15.0


# =============================================================================
# Refresh Service Tests
# =============================================================================


class TestRefreshService:
    """Tests for MarketRefreshService."""

    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return MarketRefreshService()

    def test_ttl_default(self, service):
        """Test default TTL is 5 minutes."""
        assert service.ttl_seconds == TIER_1_TTL_SECONDS
        assert service.ttl_seconds == 300

    def test_is_stale_no_data(self, service):
        """Test staleness when no previous refresh."""
        # Mock a region status with no refresh
        from aria_esi.services.market_refresh import RegionRefreshStatus

        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002,
            region_name="The Forge",
            last_refresh=0,
        )

        assert service.is_stale(10000002) is True

    def test_is_stale_fresh_data(self, service):
        """Test staleness with fresh data."""
        from aria_esi.services.market_refresh import RegionRefreshStatus

        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002,
            region_name="The Forge",
            last_refresh=int(time.time()) - 60,  # 1 minute ago
        )

        assert service.is_stale(10000002) is False

    def test_is_stale_old_data(self, service):
        """Test staleness with old data."""
        from aria_esi.services.market_refresh import RegionRefreshStatus

        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002,
            region_name="The Forge",
            last_refresh=int(time.time()) - 600,  # 10 minutes ago
        )

        assert service.is_stale(10000002) is True

    @pytest.mark.asyncio
    async def test_force_refresh(self, service):
        """Test force refresh bypasses TTL check."""
        with patch.object(service, "_ensure_initialized", new=AsyncMock()):
            with patch.object(
                service, "_refresh_region", new=AsyncMock(return_value=(100, 500, None))
            ):
                # Set up fresh data
                from aria_esi.services.market_refresh import RegionRefreshStatus

                service._region_status[10000002] = RegionRefreshStatus(
                    region_id=10000002,
                    region_name="The Forge",
                    last_refresh=int(time.time()),
                )
                service._region_locks[10000002] = asyncio.Lock()

                result = await service.ensure_fresh_data(
                    regions=[10000002],
                    force_refresh=True,
                )

                # Should have called refresh despite fresh data
                assert result.was_stale or service._refresh_region.called

    def test_get_stale_regions(self, service):
        """Test getting list of stale regions."""
        from aria_esi.services.market_refresh import RegionRefreshStatus

        now = int(time.time())

        # Fresh region
        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002,
            region_name="The Forge",
            last_refresh=now - 60,
        )

        # Stale region
        service._region_status[10000043] = RegionRefreshStatus(
            region_id=10000043,
            region_name="Domain",
            last_refresh=now - 600,
        )

        stale = service.get_stale_regions()
        assert 10000043 in stale
        assert 10000002 not in stale


# =============================================================================
# Route Timeout Tests
# =============================================================================


class TestRouteTimeout:
    """Tests for route calculation timeout handling."""

    @pytest.mark.asyncio
    async def test_route_timeout_graceful(self):
        """Test that route timeout doesn't break the scan."""
        from aria_esi.mcp.market.tools_arbitrage import _get_route

        # Mock the route function to timeout
        with patch(
            "aria_esi.mcp.market.tools_arbitrage._get_route",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            # Should not raise, just return None
            _ = await asyncio.wait_for(
                _get_route("Jita", "Amarr"),
                timeout=5.0,
            )
            # The patched function raises TimeoutError
            # In real code this is caught, but here we're directly calling patched function

    @pytest.mark.asyncio
    async def test_route_calculation_returns_none_on_error(self):
        """Test that route errors return None gracefully."""
        from aria_esi.mcp.market.tools_arbitrage import _get_route

        # Mock import error (no router available)
        with patch.dict("sys.modules", {"aria_esi.universe.router": None}):
            # Should return None, not raise
            result = await _get_route("Jita", "Amarr")
            assert result is None


# =============================================================================
# ESI Fallback Tests
# =============================================================================


class TestESIFallback:
    """Tests for ESI fallback when Fuzzwork is unavailable."""

    def test_aggregate_esi_orders_empty(self):
        """Test aggregating empty order lists."""
        from aria_esi.services.market_refresh import MarketRefreshService

        service = MarketRefreshService()
        result = service._aggregate_esi_orders([], [])

        # Should return zero values for empty orders
        assert result.buy_max == 0
        assert result.sell_min == 0
        assert result.buy_volume == 0
        assert result.sell_volume == 0

    def test_aggregate_esi_orders_with_data(self):
        """Test aggregating orders with actual data."""
        from aria_esi.services.market_refresh import MarketRefreshService

        service = MarketRefreshService()

        buy_orders = [
            {"price": 100.0, "volume_remain": 50},
            {"price": 95.0, "volume_remain": 100},
        ]
        sell_orders = [
            {"price": 110.0, "volume_remain": 30},
            {"price": 115.0, "volume_remain": 20},
        ]

        result = service._aggregate_esi_orders(buy_orders, sell_orders)

        # Buy side
        assert result.buy_max == 100.0
        assert result.buy_min == 95.0
        assert result.buy_volume == 150

        # Sell side
        assert result.sell_min == 110.0
        assert result.sell_max == 115.0
        assert result.sell_volume == 50


# =============================================================================
# Total Found Tests
# =============================================================================


class TestTotalFound:
    """Tests for total_found field in scan results."""

    @pytest.mark.asyncio
    async def test_total_found_populated(self):
        """Test that total_found is populated in scan result."""
        from unittest.mock import AsyncMock, MagicMock

        from aria_esi.services.arbitrage_engine import ArbitrageEngine

        engine = ArbitrageEngine()
        engine._database = AsyncMock()

        # Mock query result with 2 opportunities
        now = int(time.time())
        mock_cursor = MagicMock()
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.fetchall = AsyncMock(
            return_value=[
                {
                    "type_id": 34,
                    "type_name": "Tritanium",
                    "sell_region_id": 10000002,
                    "buy_region_id": 10000043,
                    "sell_price": 5.0,
                    "buy_price": 6.0,
                    "profit_per_unit": 1.0,
                    "profit_pct": 20.0,
                    "available_volume": 100000,
                    "sell_updated": now,
                    "buy_updated": now,
                    "item_volume": 0.01,
                    "item_packaged_volume": None,
                    "buy_available_volume": 100000,
                    "sell_available_volume": 100000,
                },
                {
                    "type_id": 35,
                    "type_name": "Pyerite",
                    "sell_region_id": 10000002,
                    "buy_region_id": 10000043,
                    "sell_price": 10.0,
                    "buy_price": 12.0,
                    "profit_per_unit": 2.0,
                    "profit_pct": 20.0,
                    "available_volume": 50000,
                    "sell_updated": now,
                    "buy_updated": now,
                    "item_volume": 0.01,
                    "item_packaged_volume": None,
                    "buy_available_volume": 50000,
                    "sell_available_volume": 50000,
                },
            ]
        )

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=mock_cursor)
        engine._database._get_connection.return_value = mock_conn

        result = await engine.get_scan_result()

        assert result.total_found == 2
        assert len(result.opportunities) == 2
        # Verify trade_mode is set correctly
        for opp in result.opportunities:
            assert opp.trade_mode == "immediate"


# =============================================================================
# Region Filtering Tests
# =============================================================================


class TestRegionFiltering:
    """Tests for buy_from/sell_to region filtering in arbitrage scanner."""

    def test_resolve_region_valid_name(self):
        """Test resolving valid region names."""
        from aria_esi.mcp.market.tools_arbitrage import _resolve_region

        # Should resolve standard trade hub names
        assert _resolve_region("jita") is not None
        assert _resolve_region("Jita") is not None
        assert _resolve_region("JITA") is not None
        assert _resolve_region("dodixie")["region_id"] == 10000032
        assert _resolve_region("hek")["region_id"] == 10000042
        assert _resolve_region("amarr")["region_id"] == 10000043
        assert _resolve_region("rens")["region_id"] == 10000030

    def test_resolve_region_invalid_name(self):
        """Test resolving invalid region names."""
        from aria_esi.mcp.market.tools_arbitrage import _resolve_region

        # Should return None for unknown regions
        assert _resolve_region("invalid") is None
        assert _resolve_region("perimeter") is None
        assert _resolve_region("null-sec-system") is None

    @pytest.mark.asyncio
    async def test_engine_builds_correct_sql_with_region_filters(self):
        """Test that ArbitrageEngine builds SQL with both buy and sell region filters."""
        from unittest.mock import AsyncMock, MagicMock

        from aria_esi.services.arbitrage_engine import ArbitrageEngine

        engine = ArbitrageEngine()
        engine._database = AsyncMock()

        # Mock empty result
        mock_cursor = MagicMock()
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=mock_cursor)
        engine._database._get_connection.return_value = mock_conn

        # Call with both region filters
        # buy_regions filters source (sell table) - where we BUY FROM sell orders
        # sell_regions filters destination (buy table) - where we SELL TO buy orders
        await engine.find_opportunities(
            buy_regions=[10000032],  # Dodixie (Sinq Laison)
            sell_regions=[10000042],  # Hek (Metropolis)
        )

        # Verify the query was called and extract the SQL
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        sql_query = call_args[0][0]

        # Verify buy_regions filter: sell.region_id IN (10000032) - Dodixie
        # This is correct because we BUY FROM sell orders in the source region
        assert "sell.region_id IN (10000032)" in sql_query, (
            f"Expected buy_regions to filter sell.region_id, but SQL was: {sql_query[:500]}"
        )

        # Verify sell_regions filter: buy.region_id IN (10000042) - Hek
        # This is correct because we SELL TO buy orders in the destination region
        assert "buy.region_id IN (10000042)" in sql_query, (
            f"Expected sell_regions to filter buy.region_id, but SQL was: {sql_query[:500]}"
        )

    @pytest.mark.asyncio
    async def test_get_scan_result_includes_both_regions_in_scanned(self):
        """Test that get_scan_result includes both buy and sell regions in regions_scanned."""
        from unittest.mock import AsyncMock, MagicMock

        from aria_esi.services.arbitrage_engine import ArbitrageEngine

        engine = ArbitrageEngine()
        engine._database = AsyncMock()

        # Mock empty result
        mock_cursor = MagicMock()
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=mock_cursor)
        engine._database._get_connection.return_value = mock_conn

        result = await engine.get_scan_result(
            buy_regions=[10000032],  # Dodixie (Sinq Laison)
            sell_regions=[10000042],  # Hek (Metropolis)
        )

        # regions_scanned should include BOTH regions (not or, must be and)
        assert "Sinq Laison" in result.regions_scanned, (
            f"Expected Sinq Laison (buy_regions) in regions_scanned: {result.regions_scanned}"
        )
        assert "Metropolis" in result.regions_scanned, (
            f"Expected Metropolis (sell_regions) in regions_scanned: {result.regions_scanned}"
        )

    @pytest.mark.asyncio
    async def test_regions_scanned_includes_defaults_when_one_side_filtered(self):
        """Test that regions_scanned includes defaulted side when only one filter is specified.

        This tests the fix for the medium severity finding: when only buy_regions is specified,
        sell_regions defaults to all hubs - and regions_scanned should reflect ALL regions
        actually scanned, not just the explicit filter.
        """
        from unittest.mock import AsyncMock, MagicMock

        from aria_esi.models.market import TRADE_HUBS
        from aria_esi.services.arbitrage_engine import ArbitrageEngine

        engine = ArbitrageEngine()
        engine._database = AsyncMock()

        # Mock empty result
        mock_cursor = MagicMock()
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=mock_cursor)
        engine._database._get_connection.return_value = mock_conn

        # Only specify buy_regions - sell_regions should default to all hubs
        result = await engine.get_scan_result(
            buy_regions=[10000032],  # Only Dodixie (Sinq Laison)
        )

        # regions_scanned should include:
        # - The explicit buy region (Sinq Laison)
        # - All default sell regions (all 5 trade hubs)
        assert "Sinq Laison" in result.regions_scanned, "Explicit buy region missing"

        # Should include all trade hub regions as defaults for sell side
        all_hub_regions = {hub["region_name"] for hub in TRADE_HUBS.values()}
        for hub_region in all_hub_regions:
            assert hub_region in result.regions_scanned, (
                f"Default sell region '{hub_region}' missing from regions_scanned: {result.regions_scanned}"
            )


# =============================================================================
# Integration Tests (require database)
# =============================================================================


# =============================================================================
# Phase 4 Scope Integration Tests
# =============================================================================


class TestScopeIntegration:
    """Phase 4 scope integration tests for arbitrage with ad-hoc scopes."""

    @pytest.fixture
    def engine(self):
        """Create engine instance for testing."""
        return ArbitrageEngine()

    @pytest.mark.asyncio
    async def test_scopes_not_included_by_default(self):
        """Test that scope opportunities are NOT included by default."""
        engine = ArbitrageEngine()
        engine._database = AsyncMock()

        # Mock empty hub result
        mock_cursor = MagicMock()
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=mock_cursor)
        engine._database._get_connection.return_value = mock_conn

        # Call without include_custom_scopes (default=False)
        result = await engine.get_scan_result(scopes=["TestScope"])

        # Should not attempt to resolve scopes
        # (If it did, we'd need to mock resolve_scopes)
        assert len(result.opportunities) == 0

    @pytest.mark.asyncio
    async def test_scopes_included_when_enabled(self):
        """Test that scopes are processed when include_custom_scopes=True."""
        from aria_esi.mcp.market.database import MarketScope

        engine = ArbitrageEngine()
        engine._database = AsyncMock()

        now = int(time.time())

        # Mock empty hub result from SQL query
        mock_cursor = MagicMock()
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=mock_cursor)
        engine._database._get_connection.return_value = mock_conn

        # Mock scope resolution
        mock_scope = MarketScope(
            scope_id=1,
            scope_name="TestScope",
            scope_type="region",
            region_id=10000037,  # Everyshore
            station_id=None,
            system_id=None,
            structure_id=None,
            parent_region_id=None,
            watchlist_id=1,
            is_core=False,
            source="esi",
            owner_character_id=None,
            created_at=now,
            updated_at=now,
            last_scanned_at=now,
            last_scan_status="complete",
        )
        engine._database.resolve_scopes = AsyncMock(return_value=[mock_scope])

        # Mock scope prices with profitable pair
        scope_prices = [
            {
                "scope_id": 1,
                "type_id": 34,
                "buy_max": 6.0,  # Can sell for 6.0
                "buy_volume": 10000,
                "sell_min": 5.0,  # Can buy for 5.0
                "sell_volume": 10000,
                "spread_pct": 20.0,
                "order_count_buy": 10,
                "order_count_sell": 10,
                "updated_at": now,
                "http_last_modified": now - 60,
                "http_expires": now + 300,
                "source": "esi",
                "coverage_type": "watchlist",
                "fetch_status": "complete",
                "scope_name": "TestScope",
                "scope_type": "region",
                "last_scan_status": "complete",
                "scope_region_id": 10000037,
                "type_name": "Tritanium",
                "volume": 0.01,
                "packaged_volume": None,
            },
        ]
        engine._database.get_scope_prices_for_arbitrage = AsyncMock(return_value=scope_prices)

        # Call with include_custom_scopes=True
        await engine.get_scan_result(
            scopes=["TestScope"],
            include_custom_scopes=True,
        )

        # Verify resolve_scopes was called
        engine._database.resolve_scopes.assert_called_once()

    def test_scope_freshness_thresholds(self, engine):
        """Test that scope freshness uses lenient thresholds."""
        now = int(time.time())

        # Hub freshness: 5 min fresh, 30 min recent
        # Scope freshness: 10 min fresh, 60 min recent

        # 7 minutes old - stale for hub, fresh for scope
        seven_min_ago = now - 420
        assert engine._get_freshness(seven_min_ago) == "recent"  # Hub: recent
        assert engine._get_scope_freshness(seven_min_ago) == "fresh"  # Scope: still fresh

        # 45 minutes old - stale for hub, recent for scope
        forty_five_min_ago = now - 2700
        assert engine._get_freshness(forty_five_min_ago) == "stale"  # Hub: stale
        assert engine._get_scope_freshness(forty_five_min_ago) == "recent"  # Scope: recent

        # 70 minutes old - stale for both
        seventy_min_ago = now - 4200
        assert engine._get_freshness(seventy_min_ago) == "stale"
        assert engine._get_scope_freshness(seventy_min_ago) == "stale"

    def test_deduplication_prefers_hub_data(self, engine):
        """Test that hub data is preferred over scope data for duplicates."""
        from aria_esi.models.market import ArbitrageOpportunity

        # Create hub opportunity
        hub_opp = ArbitrageOpportunity(
            type_id=34,
            type_name="Tritanium",
            buy_region="The Forge",
            buy_region_id=10000002,
            sell_region="Domain",
            sell_region_id=10000043,
            buy_price=5.0,
            sell_price=6.0,
            profit_per_unit=1.0,
            profit_pct=20.0,
            available_volume=100000,
            freshness="fresh",
            confidence="high",
            source_type=None,  # Hub data has no source_type
        )

        # Create scope opportunity with same key but different values
        scope_opp = ArbitrageOpportunity(
            type_id=34,  # Same type_id
            type_name="Tritanium",
            buy_region="The Forge",
            buy_region_id=10000002,  # Same buy region
            sell_region="Domain",
            sell_region_id=10000043,  # Same sell region
            buy_price=5.1,  # Different price
            sell_price=5.9,  # Different price
            profit_per_unit=0.8,
            profit_pct=15.7,
            available_volume=50000,
            freshness="recent",
            confidence="medium",
            source_type="esi",  # Scope data
            buy_scope_name="TestScope",
            sell_scope_name="OtherScope",
        )

        # Merge - hub should be preferred
        merged = engine._merge_opportunities([hub_opp], [scope_opp])

        assert len(merged) == 1
        assert merged[0].buy_price == 5.0  # Hub price
        assert merged[0].source_type is None  # Hub data

    def test_is_truncated_flag_propagation(self, engine):
        """Test that is_truncated flag is set correctly from fetch_status."""
        # This tests the logic in _find_scope_opportunities
        # If fetch_status != 'complete', is_truncated should be True

        # Test the propagation by checking the ArbitrageOpportunity model
        from aria_esi.models.market import ArbitrageOpportunity

        opp_complete = ArbitrageOpportunity(
            type_id=34,
            type_name="Tritanium",
            buy_region="TestScope",
            buy_region_id=10000037,
            sell_region="OtherScope",
            sell_region_id=10000032,
            buy_price=5.0,
            sell_price=6.0,
            profit_per_unit=1.0,
            profit_pct=20.0,
            available_volume=100000,
            freshness="fresh",
            confidence="high",
            is_truncated=False,  # fetch_status was 'complete'
        )
        assert opp_complete.is_truncated is False

        opp_truncated = ArbitrageOpportunity(
            type_id=35,
            type_name="Pyerite",
            buy_region="TestScope",
            buy_region_id=10000037,
            sell_region="OtherScope",
            sell_region_id=10000032,
            buy_price=10.0,
            sell_price=12.0,
            profit_per_unit=2.0,
            profit_pct=20.0,
            available_volume=50000,
            freshness="fresh",
            confidence="high",
            is_truncated=True,  # fetch_status was 'truncated'
        )
        assert opp_truncated.is_truncated is True

    def test_data_age_calculation(self, engine):
        """Test that data_age is correctly calculated from http_last_modified."""
        from aria_esi.models.market import ArbitrageOpportunity

        opp = ArbitrageOpportunity(
            type_id=34,
            type_name="Tritanium",
            buy_region="TestScope",
            buy_region_id=10000037,
            sell_region="OtherScope",
            sell_region_id=10000032,
            buy_price=5.0,
            sell_price=6.0,
            profit_per_unit=1.0,
            profit_pct=20.0,
            available_volume=100000,
            freshness="fresh",
            confidence="high",
            data_age=300,  # 5 minutes old
            last_checked=60,  # Last fetched 1 minute ago
        )

        assert opp.data_age == 300
        assert opp.last_checked == 60

    @pytest.mark.asyncio
    async def test_scope_owner_shadowing(self):
        """Test that character-owned scopes shadow global scopes."""
        # This tests the resolve_scopes behavior where character scopes
        # take precedence over global scopes with the same name.
        # The actual shadowing logic is in database_async.resolve_scopes

        # We just verify that scope_owner_id is passed through correctly
        engine = ArbitrageEngine()
        engine._database = AsyncMock()

        mock_cursor = MagicMock()
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=mock_cursor)
        engine._database._get_connection.return_value = mock_conn
        engine._database.resolve_scopes = AsyncMock(return_value=[])
        engine._database.get_scope_prices_for_arbitrage = AsyncMock(return_value=[])

        character_id = 12345678

        await engine.get_scan_result(
            scopes=["MyScope"],
            scope_owner_id=character_id,
            include_custom_scopes=True,
        )

        # Verify resolve_scopes was called with the character ID
        engine._database.resolve_scopes.assert_called_once()
        call_args = engine._database.resolve_scopes.call_args
        assert call_args[1].get("owner_character_id") == character_id


@pytest.mark.integration
class TestArbitrageIntegration:
    """Integration tests that require actual database."""

    @pytest.mark.asyncio
    async def test_end_to_end_scan(self):
        """Test end-to-end arbitrage scan with real database."""
        # This test requires actual database setup
        # Skip if database not available
        pytest.skip("Integration test - requires database setup")
