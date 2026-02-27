"""
Tests for Arbitrage Detection Engine.

Tests cover the ArbitrageEngine and ArbitrageCalculator for detecting
profitable cross-region trading opportunities:
- Fee calculation (broker fees, sales tax)
- Net profit calculation for different trade modes
- Freshness classification
- Confidence level determination
- Volume resolution (packaged vs regular)
- Opportunity detection and filtering
- Scope integration
- Sorting modes
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.models.market import DEFAULT_VOLUME_M3
from aria_esi.services.arbitrage_engine import (
    ArbitrageEngine,
    get_arbitrage_engine,
    reset_arbitrage_engine,
)
from aria_esi.services.arbitrage_fees import (
    DEFAULT_BROKER_FEE_PCT,
    DEFAULT_SALES_TAX_PCT,
    V2_BROKER_FEE_PCT,
    V2_SALES_TAX_PCT,
    ArbitrageCalculator,
)
from aria_esi.services.arbitrage_freshness import (
    FRESH_THRESHOLD,
    RECENT_THRESHOLD,
    SCOPE_FRESH_THRESHOLD,
    SCOPE_RECENT_THRESHOLD,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def calculator():
    """Create a fresh ArbitrageCalculator for each test."""
    return ArbitrageCalculator()


@pytest.fixture
def engine():
    """Create a fresh ArbitrageEngine for each test."""
    reset_arbitrage_engine()
    return ArbitrageEngine()


@pytest.fixture
def mock_async_db():
    """Create a mock async market database."""
    db = AsyncMock()
    db._get_connection = AsyncMock()
    db.get_scope_prices_for_arbitrage = AsyncMock(return_value=[])
    db.resolve_scopes = AsyncMock(return_value=[])
    return db


# =============================================================================
# Unit Tests: ArbitrageCalculator
# =============================================================================


class TestArbitrageCalculatorFees:
    """Tests for ArbitrageCalculator.calculate_fees()."""

    def test_calculate_fees_basic(self, calculator):
        """Test basic fee calculation."""
        broker_fee, sales_tax, total_fees = calculator.calculate_fees(
            buy_price=100.0, sell_price=110.0, quantity=10
        )

        # Total buy = 1000, Total sell = 1100
        # Broker fee = (1000 + 1100) * 0.03 = 63
        # Sales tax = 1100 * 0.05 = 55
        expected_broker = (100.0 * 10 + 110.0 * 10) * (DEFAULT_BROKER_FEE_PCT / 100)
        expected_sales_tax = (110.0 * 10) * (DEFAULT_SALES_TAX_PCT / 100)

        assert broker_fee == expected_broker
        assert sales_tax == expected_sales_tax
        assert total_fees == expected_broker + expected_sales_tax

    def test_calculate_fees_with_custom_rates(self):
        """Test fee calculation with custom broker/tax rates."""
        calculator = ArbitrageCalculator(broker_fee_pct=2.0, sales_tax_pct=3.6)

        broker_fee, sales_tax, total_fees = calculator.calculate_fees(
            buy_price=100.0, sell_price=120.0, quantity=5
        )

        # Total buy = 500, Total sell = 600
        # Broker fee = (500 + 600) * 0.02 = 22
        # Sales tax = 600 * 0.036 = 21.6
        expected_broker = (500 + 600) * (2.0 / 100)
        expected_sales_tax = 600 * (3.6 / 100)

        assert broker_fee == expected_broker
        assert sales_tax == expected_sales_tax

    def test_calculate_fees_zero_quantity(self, calculator):
        """Test fee calculation with zero quantity."""
        broker_fee, sales_tax, total_fees = calculator.calculate_fees(
            buy_price=100.0, sell_price=110.0, quantity=0
        )

        assert broker_fee == 0
        assert sales_tax == 0
        assert total_fees == 0

    def test_calculate_fees_large_quantity(self, calculator):
        """Test fee calculation with large quantity."""
        broker_fee, sales_tax, total_fees = calculator.calculate_fees(
            buy_price=1000000.0, sell_price=1100000.0, quantity=1000
        )

        # Should handle large numbers without overflow
        assert broker_fee > 0
        assert sales_tax > 0
        assert total_fees == broker_fee + sales_tax


class TestArbitrageCalculatorProfit:
    """Tests for ArbitrageCalculator.calculate_true_profit()."""

    def test_calculate_true_profit_basic(self, calculator):
        """Test basic profit calculation."""
        result = calculator.calculate_true_profit(
            buy_price=100.0, sell_price=120.0, quantity=10, cargo_volume=1.0
        )

        # Gross profit = (120 - 100) * 10 = 200
        # Fees need to be subtracted
        assert result.total_investment == 100.0 * 10
        assert result.cargo_volume == 10.0  # 1.0 * 10
        assert result.estimated_profit < 200  # Less than gross due to fees

    def test_calculate_true_profit_roi(self, calculator):
        """Test ROI calculation in profit result."""
        result = calculator.calculate_true_profit(
            buy_price=100.0, sell_price=150.0, quantity=10, cargo_volume=0.01
        )

        # ROI should be positive for profitable trade
        assert result.roi_pct > 0

    def test_calculate_true_profit_zero_investment(self):
        """Test ROI with zero investment (edge case)."""
        calculator = ArbitrageCalculator()
        result = calculator.calculate_true_profit(
            buy_price=0.0, sell_price=100.0, quantity=10, cargo_volume=1.0
        )

        # Should handle zero investment gracefully
        assert result.roi_pct == 0


# =============================================================================
# Unit Tests: Freshness Classification
# =============================================================================


class TestFreshnessClassification:
    """Tests for freshness classification methods."""

    def test_get_freshness_fresh(self, engine):
        """Test freshness classification for fresh data (<5 min)."""
        now = int(time.time())
        timestamp = now - 60  # 1 minute ago

        freshness = engine._get_freshness(timestamp)
        assert freshness == "fresh"

    def test_get_freshness_recent(self, engine):
        """Test freshness classification for recent data (5-30 min)."""
        now = int(time.time())
        timestamp = now - 600  # 10 minutes ago

        freshness = engine._get_freshness(timestamp)
        assert freshness == "recent"

    def test_get_freshness_stale(self, engine):
        """Test freshness classification for stale data (>30 min)."""
        now = int(time.time())
        timestamp = now - 3600  # 1 hour ago

        freshness = engine._get_freshness(timestamp)
        assert freshness == "stale"

    def test_get_scope_freshness_fresh(self, engine):
        """Test scope freshness for fresh data (<10 min)."""
        now = int(time.time())
        timestamp = now - 300  # 5 minutes ago

        freshness = engine._get_scope_freshness(timestamp)
        assert freshness == "fresh"

    def test_get_scope_freshness_recent(self, engine):
        """Test scope freshness for recent data (10-60 min)."""
        now = int(time.time())
        timestamp = now - 1800  # 30 minutes ago

        freshness = engine._get_scope_freshness(timestamp)
        assert freshness == "recent"

    def test_get_scope_freshness_stale(self, engine):
        """Test scope freshness for stale data (>60 min)."""
        now = int(time.time())
        timestamp = now - 7200  # 2 hours ago

        freshness = engine._get_scope_freshness(timestamp)
        assert freshness == "stale"


# =============================================================================
# Unit Tests: Confidence Level
# =============================================================================


class TestConfidenceLevel:
    """Tests for confidence level calculation."""

    def test_confidence_high_both_fresh(self, engine):
        """Test high confidence when both sides are fresh."""
        confidence = engine._get_confidence("fresh", "fresh")
        assert confidence == "high"

    def test_confidence_medium_one_recent(self, engine):
        """Test medium confidence when one side is recent."""
        confidence = engine._get_confidence("fresh", "recent")
        assert confidence == "medium"

        confidence = engine._get_confidence("recent", "fresh")
        assert confidence == "medium"

    def test_confidence_low_any_stale(self, engine):
        """Test low confidence when any side is stale."""
        confidence = engine._get_confidence("fresh", "stale")
        assert confidence == "low"

        confidence = engine._get_confidence("stale", "fresh")
        assert confidence == "low"

        confidence = engine._get_confidence("stale", "stale")
        assert confidence == "low"


# =============================================================================
# Unit Tests: Net Profit Calculation
# =============================================================================


class TestNetProfitCalculation:
    """Tests for _calculate_net_profit with different trade modes."""

    def test_immediate_mode_only_sales_tax(self, engine):
        """Test immediate mode: only sales tax, no broker fees."""
        net_profit, net_margin, gross_profit, gross_margin = engine._calculate_net_profit(
            buy_price=100.0,
            sell_price=120.0,
            trade_mode="immediate",
            broker_fee_pct=0.03,
            sales_tax_pct=0.036,
        )

        # Gross profit = 120 - 100 = 20
        assert gross_profit == 20.0

        # Net: buy_cost = 100, sell_revenue = 120 * (1 - 0.036) = 115.68
        # Net profit = 115.68 - 100 = 15.68
        expected_sell_revenue = 120.0 * (1 - 0.036)
        expected_net = expected_sell_revenue - 100.0

        assert abs(net_profit - expected_net) < 0.01

    def test_hybrid_mode_broker_on_sell(self, engine):
        """Test hybrid mode: broker fee on sell side only."""
        net_profit, net_margin, gross_profit, gross_margin = engine._calculate_net_profit(
            buy_price=100.0,
            sell_price=120.0,
            trade_mode="hybrid",
            broker_fee_pct=0.03,
            sales_tax_pct=0.036,
        )

        # Net: buy_cost = 100, sell_revenue = 120 * (1 - 0.03 - 0.036) = 112.08
        expected_sell_revenue = 120.0 * (1 - 0.03 - 0.036)
        expected_net = expected_sell_revenue - 100.0

        assert abs(net_profit - expected_net) < 0.01

    def test_station_trading_mode_broker_both_sides(self, engine):
        """Test station_trading mode: broker fees on both sides."""
        net_profit, net_margin, gross_profit, gross_margin = engine._calculate_net_profit(
            buy_price=100.0,
            sell_price=120.0,
            trade_mode="station_trading",
            broker_fee_pct=0.03,
            sales_tax_pct=0.036,
        )

        # Net: buy_cost = 100 * 1.03 = 103, sell_revenue = 120 * (1 - 0.03 - 0.036) = 112.08
        expected_buy_cost = 100.0 * 1.03
        expected_sell_revenue = 120.0 * (1 - 0.03 - 0.036)
        expected_net = expected_sell_revenue - expected_buy_cost

        assert abs(net_profit - expected_net) < 0.01

    def test_net_margin_calculation(self, engine):
        """Test that net margin is correctly calculated."""
        net_profit, net_margin, gross_profit, gross_margin = engine._calculate_net_profit(
            buy_price=100.0,
            sell_price=120.0,
            trade_mode="immediate",
        )

        # Net margin = (net_profit / buy_cost) * 100
        assert net_margin > 0
        assert gross_margin == 20.0  # (120 - 100) / 100 * 100

    def test_zero_buy_price_no_division_error(self, engine):
        """Test that zero buy price doesn't cause division error."""
        net_profit, net_margin, gross_profit, gross_margin = engine._calculate_net_profit(
            buy_price=0.0,
            sell_price=100.0,
            trade_mode="immediate",
        )

        # Should return 0 margins without error
        assert gross_margin == 0.0
        assert net_margin == 0.0


# =============================================================================
# Unit Tests: Effective Volume
# =============================================================================


class TestEffectiveVolume:
    """Tests for _get_effective_volume method."""

    def test_prefers_packaged_volume(self, engine):
        """Test that packaged volume is preferred over regular volume."""
        volume, source = engine._get_effective_volume(volume=100.0, packaged_volume=10.0)

        assert volume == 10.0
        assert source == "sde_packaged"

    def test_falls_back_to_regular_volume(self, engine):
        """Test fallback to regular volume when packaged is None."""
        volume, source = engine._get_effective_volume(volume=100.0, packaged_volume=None)

        assert volume == 100.0
        assert source == "sde_volume"

    def test_falls_back_to_default(self, engine):
        """Test fallback to default when both are None."""
        volume, source = engine._get_effective_volume(volume=None, packaged_volume=None)

        assert volume == DEFAULT_VOLUME_M3
        assert source == "fallback"

    def test_ignores_zero_packaged_volume(self, engine):
        """Test that zero packaged volume falls back to regular."""
        volume, source = engine._get_effective_volume(volume=50.0, packaged_volume=0.0)

        assert volume == 50.0
        assert source == "sde_volume"

    def test_ignores_zero_regular_volume(self, engine):
        """Test that zero regular volume falls back to default."""
        volume, source = engine._get_effective_volume(volume=0.0, packaged_volume=None)

        assert volume == DEFAULT_VOLUME_M3
        assert source == "fallback"


# =============================================================================
# Unit Tests: Merge Opportunities
# =============================================================================


class TestMergeOpportunities:
    """Tests for _merge_opportunities method."""

    def test_merge_prefers_hub_data(self, engine):
        """Test that hub opportunities are preferred over scope duplicates."""
        # Create mock opportunities
        hub_opp = MagicMock()
        hub_opp.type_id = 34
        hub_opp.buy_region_id = 10000002
        hub_opp.sell_region_id = 10000043

        scope_opp = MagicMock()
        scope_opp.type_id = 34  # Same type
        scope_opp.buy_region_id = 10000002  # Same route
        scope_opp.sell_region_id = 10000043

        result = engine._merge_opportunities([hub_opp], [scope_opp])

        # Should only contain hub opportunity
        assert len(result) == 1
        assert result[0] is hub_opp

    def test_merge_includes_unique_scope_opps(self, engine):
        """Test that unique scope opportunities are included."""
        hub_opp = MagicMock()
        hub_opp.type_id = 34
        hub_opp.buy_region_id = 10000002
        hub_opp.sell_region_id = 10000043

        scope_opp = MagicMock()
        scope_opp.type_id = 35  # Different type
        scope_opp.buy_region_id = 10000002
        scope_opp.sell_region_id = 10000043

        result = engine._merge_opportunities([hub_opp], [scope_opp])

        # Should contain both
        assert len(result) == 2

    def test_merge_empty_lists(self, engine):
        """Test merging with empty lists."""
        result = engine._merge_opportunities([], [])
        assert result == []

        result = engine._merge_opportunities([MagicMock(type_id=34, buy_region_id=1, sell_region_id=2)], [])
        assert len(result) == 1


# =============================================================================
# Unit Tests: Find Opportunities
# =============================================================================


class TestFindOpportunities:
    """Tests for find_opportunities method."""

    @pytest.mark.asyncio
    async def test_hauling_score_requires_cargo_capacity(self, engine, mock_async_db):
        """Test that hauling_score sort requires cargo_capacity_m3."""
        with patch.object(engine, "_get_database", return_value=mock_async_db):
            with pytest.raises(ValueError, match="cargo_capacity_m3"):
                await engine.find_opportunities(sort_by="hauling_score", cargo_capacity_m3=None)

    @pytest.mark.asyncio
    async def test_find_opportunities_empty_results(self, engine, mock_async_db):
        """Test that empty query results return empty list."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])

        # Create object that works as async context manager
        class MockCursorCM:
            async def __aenter__(self):
                return mock_cursor

            async def __aexit__(self, *args):
                return None

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=MockCursorCM())
        mock_async_db._get_connection = AsyncMock(return_value=mock_conn)

        with patch.object(engine, "_get_database", return_value=mock_async_db):
            result = await engine.find_opportunities()

        assert len(result) == 0


# =============================================================================
# Unit Tests: Get Scan Result
# =============================================================================


class TestGetScanResult:
    """Tests for get_scan_result method."""

    @pytest.mark.asyncio
    async def test_scan_result_aggregates_freshness(self, engine, mock_async_db):
        """Test that scan result correctly aggregates freshness."""
        with patch.object(
            engine, "find_opportunities", new_callable=AsyncMock, return_value=[]
        ):
            result = await engine.get_scan_result()

        assert result.data_freshness == "fresh"  # No opportunities = default fresh
        assert result.total_found == 0

    @pytest.mark.asyncio
    async def test_scan_result_includes_stale_warning(self, engine, mock_async_db):
        """Test that stale warning is included when data is stale."""
        from aria_esi.models.market import ArbitrageOpportunity

        stale_opp = ArbitrageOpportunity(
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
            available_volume=100,
            freshness="stale",
            confidence="low",
        )

        engine.allow_stale = False

        with patch.object(
            engine, "find_opportunities", new_callable=AsyncMock, return_value=[stale_opp]
        ):
            result = await engine.get_scan_result()

        assert result.data_freshness == "stale"
        assert result.stale_warning is not None
        assert "stale" in result.stale_warning.lower()


# =============================================================================
# Unit Tests: Singleton Management
# =============================================================================


class TestSingletonManagement:
    """Tests for singleton engine management."""

    @pytest.mark.asyncio
    async def test_get_arbitrage_engine_returns_singleton(self):
        """Test that get_arbitrage_engine returns the same instance."""
        reset_arbitrage_engine()

        engine1 = await get_arbitrage_engine()
        engine2 = await get_arbitrage_engine()

        assert engine1 is engine2

    @pytest.mark.asyncio
    async def test_get_arbitrage_engine_updates_stale_setting(self):
        """Test that allow_stale setting can be updated."""
        reset_arbitrage_engine()

        engine1 = await get_arbitrage_engine(allow_stale=False)
        assert engine1.allow_stale is False

        engine2 = await get_arbitrage_engine(allow_stale=True)
        assert engine2.allow_stale is True
        assert engine1 is engine2  # Same instance, updated setting

    def test_reset_clears_singleton(self):
        """Test that reset clears the singleton."""
        reset_arbitrage_engine()
        # Should not raise
        reset_arbitrage_engine()


# =============================================================================
# Unit Tests: Constants
# =============================================================================


class TestConstants:
    """Tests to verify constants are correctly defined."""

    def test_fresh_threshold_is_5_minutes(self):
        """Test that fresh threshold is 5 minutes (300 seconds)."""
        assert FRESH_THRESHOLD == 300

    def test_recent_threshold_is_30_minutes(self):
        """Test that recent threshold is 30 minutes (1800 seconds)."""
        assert RECENT_THRESHOLD == 1800

    def test_scope_fresh_threshold_is_10_minutes(self):
        """Test that scope fresh threshold is 10 minutes (600 seconds)."""
        assert SCOPE_FRESH_THRESHOLD == 600

    def test_scope_recent_threshold_is_1_hour(self):
        """Test that scope recent threshold is 1 hour (3600 seconds)."""
        assert SCOPE_RECENT_THRESHOLD == 3600

    def test_default_broker_fee(self):
        """Test default broker fee percentage."""
        assert DEFAULT_BROKER_FEE_PCT == 3.0

    def test_default_sales_tax(self):
        """Test default sales tax percentage."""
        assert DEFAULT_SALES_TAX_PCT == 5.0

    def test_v2_broker_fee(self):
        """Test V2 broker fee rate (decimal)."""
        assert V2_BROKER_FEE_PCT == 0.03

    def test_v2_sales_tax(self):
        """Test V2 sales tax rate (decimal)."""
        assert V2_SALES_TAX_PCT == 0.036


# =============================================================================
# Unit Tests: Get Detail
# =============================================================================


class TestGetDetail:
    """Tests for get_detail method."""

    @pytest.mark.asyncio
    async def test_get_detail_returns_none_when_no_opportunity(self, engine, mock_async_db):
        """Test that get_detail returns None when opportunity doesn't exist."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        # Create object that works as async context manager
        class MockCursorCM:
            async def __aenter__(self):
                return mock_cursor

            async def __aexit__(self, *args):
                return None

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=MockCursorCM())
        mock_async_db._get_connection = AsyncMock(return_value=mock_conn)

        with patch.object(engine, "_get_database", return_value=mock_async_db):
            result = await engine.get_detail(
                type_id=34, buy_region_id=10000002, sell_region_id=10000043
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_detail_returns_none_when_no_longer_profitable(self, engine, mock_async_db):
        """Test that get_detail returns None when trade is no longer profitable."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(
            return_value={
                "buy_price": 100.0,
                "sell_price": 90.0,  # Sell price < buy price = not profitable
                "buy_volume": 100,
                "sell_volume": 100,
                "sell_updated": int(time.time()),
                "buy_updated": int(time.time()),
                "type_name": "Tritanium",
                "item_volume": 0.01,
            }
        )

        class MockCursorCM:
            async def __aenter__(self):
                return mock_cursor

            async def __aexit__(self, *args):
                return None

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=MockCursorCM())
        mock_async_db._get_connection = AsyncMock(return_value=mock_conn)

        with patch.object(engine, "_get_database", return_value=mock_async_db):
            result = await engine.get_detail(
                type_id=34, buy_region_id=10000002, sell_region_id=10000043
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_detail_returns_result_for_profitable_trade(self, engine, mock_async_db):
        """Test that get_detail returns result for profitable trade."""
        now = int(time.time())
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(
            return_value={
                "buy_price": 100.0,
                "sell_price": 120.0,
                "buy_volume": 100,
                "sell_volume": 100,
                "sell_updated": now,
                "buy_updated": now,
                "type_name": "Tritanium",
                "item_volume": 0.01,
            }
        )

        class MockCursorCM:
            async def __aenter__(self):
                return mock_cursor

            async def __aexit__(self, *args):
                return None

        mock_conn = AsyncMock()
        mock_conn.execute = MagicMock(return_value=MockCursorCM())
        mock_async_db._get_connection = AsyncMock(return_value=mock_conn)

        with patch.object(engine, "_get_database", return_value=mock_async_db):
            result = await engine.get_detail(
                type_id=34, buy_region_id=10000002, sell_region_id=10000043
            )

        assert result is not None
        assert result.opportunity.type_id == 34
        assert result.opportunity.profit_per_unit == 20.0
