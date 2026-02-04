"""
Pydantic models for Market MCP tools.

These models define the data structures for market price queries,
valuation, and order book operations. Used by both CLI commands
and MCP tools.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Type Aliases
# =============================================================================

PriceType = Literal["buy", "sell"]
"""Price type for valuation: buy (instant sell) or sell (instant buy)."""

FreshnessLevel = Literal["fresh", "recent", "stale"]
"""
Data freshness classification:
- fresh: < 5 minutes old
- recent: 5-30 minutes old
- stale: > 30 minutes old
"""

OrderType = Literal["buy", "sell", "all"]
"""Order type filter for market queries."""

# =============================================================================
# Ad-hoc Market Scope Types (Hub-Centric Engine)
# =============================================================================

ScopeType = Literal["hub_region", "region", "station", "system", "structure"]
"""
Market scope type for ad-hoc markets:
- hub_region: Core trade hub regions (Fuzzwork source)
- region: Ad-hoc region scope (ESI source)
- station: Ad-hoc station scope (ESI source, filtered from region)
- system: Ad-hoc system scope (ESI source, filtered from region)
- structure: Ad-hoc structure scope (ESI source, full order fetch)
"""

ScanStatus = Literal["new", "complete", "truncated", "error"]
"""
Market scope scan status:
- new: Scope created, never scanned
- complete: Last scan completed successfully
- truncated: Last scan hit pagination limits (structure scopes)
- error: Last scan encountered an error
"""

FetchStatus = Literal["complete", "truncated", "skipped_truncation"]
"""
Price row fetch status:
- complete: Price data successfully fetched
- truncated: Scope was truncated, price may be incomplete
- skipped_truncation: Item was in watchlist but not found due to truncation
"""

ScopeSource = Literal["fuzzwork", "esi"]
"""
Data source for a market scope:
- fuzzwork: Aggregated data from Fuzzwork (core hubs only)
- esi: Direct ESI orders (ad-hoc scopes)
"""

TradeMode = Literal["immediate", "hybrid", "station_trading"]
"""
Trade execution mode affecting fee calculation:
- immediate: Take sell orders → Take buy orders. Fees: sales tax only.
- hybrid: Take sell orders → Place sell orders. Fees: broker + sales tax on sell.
- station_trading: Place buy orders → Place sell orders. Fees: broker on both + sales tax.
"""

# Default volume for items missing SDE data (prevents division-by-zero)
DEFAULT_VOLUME_M3 = 0.01


# =============================================================================
# Base Model
# =============================================================================


class MarketModel(BaseModel):
    """
    Base model for market data with MCP-friendly serialization.

    Configuration:
    - frozen: Prevents accidental mutation, enables hashing
    - extra="forbid": Catches typos in field names during construction
    - ser_json_inf_nan="constants": Serializes inf/nan as JSON constants
    """

    model_config = ConfigDict(frozen=True, extra="forbid", ser_json_inf_nan="constants")


# =============================================================================
# Price Aggregate Models
# =============================================================================


class PriceAggregate(MarketModel):
    """
    Aggregated price metrics for buy or sell side.

    Contains min, max, weighted average, and volume data
    from Fuzzwork or ESI aggregation.
    """

    order_count: int = Field(ge=0, description="Number of orders")
    volume: int = Field(ge=0, description="Total units available")
    min_price: float | None = Field(default=None, ge=0, description="Lowest price")
    max_price: float | None = Field(default=None, ge=0, description="Highest price")
    weighted_avg: float | None = Field(
        default=None, ge=0, description="Volume-weighted average price"
    )
    median: float | None = Field(default=None, ge=0, description="Median price")
    percentile_5: float | None = Field(default=None, ge=0, description="5th percentile price")
    stddev: float | None = Field(default=None, ge=0, description="Price standard deviation")


class ItemPrice(MarketModel):
    """
    Complete price data for a single item.

    Includes buy and sell aggregates, spread calculation,
    and type metadata.
    """

    type_id: int = Field(ge=1, description="EVE type ID")
    type_name: str = Field(description="Item name")
    buy: PriceAggregate = Field(description="Buy order aggregates (instant sell)")
    sell: PriceAggregate = Field(description="Sell order aggregates (instant buy)")
    spread: float | None = Field(
        default=None,
        description="Spread (sell.min - buy.max, can be negative)",
    )
    spread_percent: float | None = Field(
        default=None,
        description="Spread as percentage of sell price",
    )
    freshness: FreshnessLevel = Field(default="fresh", description="Data age classification")


class MarketPricesResult(MarketModel):
    """
    Result from market_prices tool.

    Contains batch price data with source info and warnings.
    """

    items: list[ItemPrice] = Field(default_factory=list, description="Price data per item")
    region: str = Field(description="Region name (e.g., 'The Forge')")
    region_id: int = Field(ge=1, description="Region ID")
    station: str | None = Field(default=None, description="Station name if station-filtered")
    station_id: int | None = Field(default=None, ge=1, description="Station ID if filtered")
    source: str = Field(
        default="fuzzwork",
        description="Data source (fuzzwork, esi, cache)",
    )
    freshness: FreshnessLevel = Field(default="fresh", description="Overall data freshness")
    cache_age_seconds: int | None = Field(
        default=None, ge=0, description="Age of cached data in seconds"
    )
    unresolved_items: list[str] = Field(
        default_factory=list,
        description="Item names that could not be resolved to type IDs",
    )
    warnings: list[str] = Field(default_factory=list, description="Any warnings or notes")


# =============================================================================
# Market Order Models
# =============================================================================


class MarketOrder(MarketModel):
    """
    Individual market order from ESI.
    """

    order_id: int = Field(ge=1, description="Unique order ID")
    type_id: int = Field(ge=1, description="Item type ID")
    is_buy_order: bool = Field(description="True for buy orders")
    price: float = Field(ge=0, description="Order price per unit")
    volume_remain: int = Field(ge=0, description="Remaining volume")
    volume_total: int = Field(ge=0, description="Original volume")
    location_id: int = Field(ge=1, description="Station or structure ID")
    location_name: str | None = Field(default=None, description="Station/structure name")
    system_id: int = Field(ge=1, description="Solar system ID")
    system_name: str | None = Field(default=None, description="Solar system name")
    range: str = Field(description="Order range (station, solarsystem, region, etc.)")
    min_volume: int = Field(default=1, ge=1, description="Minimum purchase volume")
    duration: int = Field(ge=0, description="Days until expiry")
    issued: str = Field(description="ISO timestamp when order was placed")


class MarketOrdersResult(MarketModel):
    """
    Result from market_orders tool.

    Contains detailed order book with station info.
    """

    type_id: int = Field(ge=1, description="Item type ID")
    type_name: str = Field(description="Item name")
    region: str = Field(description="Region name")
    region_id: int = Field(ge=1, description="Region ID")
    buy_orders: list[MarketOrder] = Field(default_factory=list)
    sell_orders: list[MarketOrder] = Field(default_factory=list)
    total_buy_orders: int = Field(default=0, ge=0, description="Total buy orders in region")
    total_sell_orders: int = Field(default=0, ge=0, description="Total sell orders in region")
    best_buy: float | None = Field(default=None, ge=0, description="Highest buy price")
    best_sell: float | None = Field(default=None, ge=0, description="Lowest sell price")
    spread: float | None = Field(default=None, description="Spread (can be negative if buy > sell)")
    spread_percent: float | None = Field(default=None, description="Spread percentage")
    freshness: FreshnessLevel = Field(default="fresh")
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Valuation Models
# =============================================================================


class ValuationItem(MarketModel):
    """
    Single item in a valuation calculation.
    """

    type_id: int | None = Field(default=None, ge=1, description="Type ID if resolved")
    type_name: str = Field(description="Item name (input or resolved)")
    quantity: int = Field(ge=0, description="Number of units")
    unit_price: float | None = Field(default=None, ge=0, description="Price per unit")
    total_value: float | None = Field(default=None, ge=0, description="quantity * unit_price")
    resolved: bool = Field(default=True, description="False if item couldn't be found")
    warning: str | None = Field(default=None, description="Warning if any issue")


class ValuationResult(MarketModel):
    """
    Result from market_valuation tool.

    Contains itemized breakdown and total value.
    """

    items: list[ValuationItem] = Field(default_factory=list)
    total_value: float = Field(ge=0, description="Sum of all resolved item values")
    total_quantity: int = Field(ge=0, description="Sum of all quantities")
    resolved_count: int = Field(ge=0, description="Number of successfully resolved items")
    unresolved_count: int = Field(ge=0, description="Number of unresolved items")
    price_type: PriceType = Field(description="Price type used (buy or sell)")
    region: str = Field(description="Region used for pricing")
    region_id: int = Field(ge=1)
    freshness: FreshnessLevel = Field(default="fresh")
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Market Analysis Models
# =============================================================================


class RegionPrice(MarketModel):
    """
    Price data for a single region in spread analysis.
    """

    region: str = Field(description="Region name")
    region_id: int = Field(ge=1)
    buy_price: float | None = Field(default=None, ge=0, description="Best buy price")
    sell_price: float | None = Field(default=None, ge=0, description="Best sell price")
    buy_volume: int = Field(default=0, ge=0)
    sell_volume: int = Field(default=0, ge=0)


class ItemSpread(MarketModel):
    """
    Cross-region price analysis for a single item.
    """

    type_id: int = Field(ge=1)
    type_name: str
    regions: list[RegionPrice] = Field(default_factory=list)
    best_buy_region: str | None = Field(default=None, description="Region with highest buy price")
    best_sell_region: str | None = Field(default=None, description="Region with lowest sell price")
    arbitrage_profit: float | None = Field(
        default=None,
        description="Potential profit: best_buy - best_sell (per unit)",
    )
    arbitrage_percent: float | None = Field(default=None, ge=0)


class MarketSpreadResult(MarketModel):
    """
    Result from market_spread tool.

    Cross-region price comparison for arbitrage analysis.
    """

    items: list[ItemSpread] = Field(default_factory=list)
    regions_queried: list[str] = Field(default_factory=list)
    freshness: FreshnessLevel = Field(default="fresh")
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Route Value Models
# =============================================================================


class SystemRisk(MarketModel):
    """
    Gank risk assessment for a single system.
    """

    system: str = Field(description="System name")
    system_id: int = Field(ge=1)
    security: float = Field(ge=-1.0, le=1.0)
    cargo_value: float = Field(ge=0, description="Cargo value at this point")
    gank_threshold: float = Field(
        ge=0,
        description="Estimated ISK threshold for profitable gank",
    )
    risk_level: Literal["safe", "low", "medium", "high", "extreme"] = Field(
        description="Risk classification based on cargo value vs threshold"
    )
    recent_kills: int | None = Field(default=None, ge=0, description="Recent gank kills")


class RouteValueResult(MarketModel):
    """
    Result from market_route_value tool.

    Cargo value with per-system gank risk.
    """

    total_value: float = Field(ge=0, description="Total cargo value")
    item_count: int = Field(ge=0)
    route_systems: list[SystemRisk] = Field(default_factory=list)
    highest_risk_system: str | None = Field(default=None)
    overall_risk: Literal["safe", "low", "medium", "high", "extreme"]
    recommendation: str = Field(description="Safety recommendation")
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Market History Models
# =============================================================================


class DailyPrice(MarketModel):
    """
    Single day of price history.
    """

    date: str = Field(description="ISO date (YYYY-MM-DD)")
    average: float = Field(ge=0)
    highest: float = Field(ge=0)
    lowest: float = Field(ge=0)
    volume: int = Field(ge=0)
    order_count: int = Field(ge=0)


class MarketHistoryResult(MarketModel):
    """
    Result from market_history tool.

    Historical price data with trend analysis.
    """

    type_id: int = Field(ge=1)
    type_name: str
    region: str
    region_id: int = Field(ge=1)
    history: list[DailyPrice] = Field(default_factory=list)
    days_requested: int = Field(ge=1)
    days_returned: int = Field(ge=0)
    price_trend: Literal["rising", "falling", "stable", "volatile"] = Field(
        default="stable",
        description="Price trend over period",
    )
    volume_trend: Literal["increasing", "decreasing", "stable"] = Field(
        default="stable",
        description="Volume trend over period",
    )
    avg_price: float | None = Field(default=None, ge=0, description="Period average price")
    avg_volume: int | None = Field(default=None, ge=0, description="Period average volume")
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Cache Status Models
# =============================================================================


class MarketCacheLayerStatus(MarketModel):
    """
    Status of a single market cache layer.
    """

    name: str = Field(description="Cache layer name (fuzzwork, esi_orders, esi_history)")
    cached_types: int = Field(default=0, ge=0, description="Number of cached type IDs")
    age_seconds: int | None = Field(default=None, description="Age of oldest data")
    ttl_seconds: int = Field(ge=0, description="Time-to-live setting")
    stale: bool = Field(description="True if cache has expired")
    last_error: str | None = Field(default=None, description="Last error if any")


class MarketCacheStatusResult(MarketModel):
    """
    Result from market_cache_status tool.

    Diagnostic information about market cache layers.
    """

    fuzzwork: MarketCacheLayerStatus
    esi_orders: MarketCacheLayerStatus
    esi_history: MarketCacheLayerStatus
    database_path: str | None = Field(default=None, description="SQLite database path")
    database_size_mb: float | None = Field(default=None, ge=0)
    type_count: int = Field(default=0, ge=0, description="Known type IDs in database")
    common_items_cached: int = Field(default=0, ge=0, description="Pre-warmed common items")


# =============================================================================
# Trade Hub Constants
# =============================================================================


class TradeHubConfig(TypedDict):
    """Configuration for a trade hub location."""

    region_id: int
    region_name: str
    station_id: int
    station_name: str
    system_id: int


class RegionConfig(TypedDict):
    """Configuration for any region (trade hub or otherwise).

    For trade hubs, station_id/station_name/system_id are populated.
    For non-trade-hub regions, they are None.
    """

    region_id: int
    region_name: str
    station_id: int | None
    station_name: str | None
    system_id: int | None


TRADE_HUBS: dict[str, TradeHubConfig] = {
    "jita": {
        "region_id": 10000002,
        "region_name": "The Forge",
        "station_id": 60003760,
        "station_name": "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
        "system_id": 30000142,
    },
    "amarr": {
        "region_id": 10000043,
        "region_name": "Domain",
        "station_id": 60008494,
        "station_name": "Amarr VIII (Oris) - Emperor Family Academy",
        "system_id": 30002187,
    },
    "dodixie": {
        "region_id": 10000032,
        "region_name": "Sinq Laison",
        "station_id": 60011866,
        "station_name": "Dodixie IX - Moon 20 - Federation Navy Assembly Plant",
        "system_id": 30002659,
    },
    "rens": {
        "region_id": 10000030,
        "region_name": "Heimatar",
        "station_id": 60004588,
        "station_name": "Rens VI - Moon 8 - Brutor Tribe Treasury",
        "system_id": 30002510,
    },
    "hek": {
        "region_id": 10000042,
        "region_name": "Metropolis",
        "station_id": 60005686,
        "station_name": "Hek VIII - Moon 12 - Boundless Creation Factory",
        "system_id": 30002053,
    },
}
"""
Major trade hub configuration.

Keys are lowercase aliases used in tool parameters.
Values contain region, station, and system IDs for ESI queries.
"""


def resolve_trade_hub(name: str) -> TradeHubConfig | None:
    """
    Resolve trade hub name to configuration.

    Args:
        name: Hub name (case-insensitive, partial match supported)

    Returns:
        Hub configuration TypedDict or None if not found
    """
    name_lower = name.lower().strip()

    # Direct match
    if name_lower in TRADE_HUBS:
        return TRADE_HUBS[name_lower]

    # Partial match (e.g., "jit" matches "jita")
    for hub_name, config in TRADE_HUBS.items():
        if hub_name.startswith(name_lower):
            return config

    return None


def resolve_region(name: str) -> RegionConfig | None:
    """
    Resolve region name to configuration.

    Checks trade hubs first (which have station info), then falls back
    to SDE region lookup for arbitrary regions like Everyshore.

    Args:
        name: Region or hub name (case-insensitive)

    Returns:
        Region configuration with at minimum:
        - region_id: int
        - region_name: str
        Trade hubs also include station_id, station_name, system_id.
        Returns None if region not found.
    """
    # First check trade hubs (they have more complete data)
    hub = resolve_trade_hub(name)
    if hub:
        # TradeHubConfig is compatible with RegionConfig (int is subtype of int | None)
        return RegionConfig(
            region_id=hub["region_id"],
            region_name=hub["region_name"],
            station_id=hub["station_id"],
            station_name=hub["station_name"],
            system_id=hub["system_id"],
        )

    # Check if it's a numeric region ID
    try:
        region_id_val = int(name)
        return RegionConfig(
            region_id=region_id_val,
            region_name=f"Region {region_id_val}",
            station_id=None,
            station_name=None,
            system_id=None,
        )
    except ValueError:
        pass

    # Fall back to SDE region lookup
    try:
        from aria_esi.mcp.market.database import get_market_database

        db = get_market_database()
        region_info = db.resolve_region_name(name)
        if region_info:
            return RegionConfig(
                region_id=region_info["region_id"],
                region_name=region_info["region_name"],
                station_id=None,  # Non-trade-hub regions don't have a default station
                station_name=None,
                system_id=None,
            )
    except ImportError:
        pass

    return None


# =============================================================================
# Arbitrage Models
# =============================================================================


ConfidenceLevel = Literal["high", "medium", "low"]
"""
V1 Confidence level based on data freshness:
- high: All data < 5 minutes old
- medium: Some data 5-30 minutes old
- low: Some data > 30 minutes old
"""


class ArbitrageOpportunity(MarketModel):
    """
    Single arbitrage opportunity between two regions.

    Represents a profitable trade route: buy at sell_region, sell at buy_region.
    """

    type_id: int = Field(ge=1, description="Item type ID")
    type_name: str = Field(description="Item name")
    buy_region: str = Field(description="Region to buy from (lower price)")
    buy_region_id: int = Field(ge=1)
    sell_region: str = Field(description="Region to sell to (higher price)")
    sell_region_id: int = Field(ge=1)
    buy_price: float = Field(ge=0, description="Sell order price at buy region")
    sell_price: float = Field(ge=0, description="Buy order price at sell region")
    profit_per_unit: float = Field(description="Gross profit per unit (sell - buy)")
    profit_pct: float = Field(description="Profit percentage before fees")
    available_volume: int = Field(ge=0, description="Min of buy/sell volume")
    route_jumps: int | None = Field(default=None, ge=0, description="Jumps between hubs")
    route_safe: bool = Field(default=True, description="Route is high-sec only")
    freshness: FreshnessLevel = Field(default="fresh", description="Data freshness")
    confidence: ConfidenceLevel = Field(default="high", description="V1 confidence level")

    # V2 Fields: Volume & Density
    item_volume_m3: float = Field(
        default=0.01,
        ge=0,
        description="Effective volume per unit in m³ (packaged preferred)",
    )
    item_packaged_volume_m3: float | None = Field(
        default=None, description="Packaged volume per unit (if applicable)"
    )
    volume_source: str | None = Field(
        default=None,
        description="Source of volume data: 'sde_packaged' | 'sde_volume' | 'fallback'",
    )
    profit_density: float | None = Field(
        default=None, description="Net profit per m³ (net_profit_per_unit / effective_volume)"
    )

    # V2 Fields: Buy/Sell Availability (separate)
    buy_available_volume: int | None = Field(
        default=None, ge=0, description="Units available to buy in source region"
    )
    sell_available_volume: int | None = Field(
        default=None, ge=0, description="Units that can sell in destination region"
    )
    availability_source: str | None = Field(
        default=None,
        description="Availability data source: 'both_available' | 'proxy_from_buy' | 'proxy_from_sell' | 'none'",
    )

    # V2 Fields: Fee-adjusted Profit
    gross_profit_per_unit: float | None = Field(
        default=None, description="sell_price - buy_price (before fees)"
    )
    net_profit_per_unit: float | None = Field(
        default=None, description="Profit after fees (varies by trade_mode)"
    )
    gross_margin_pct: float | None = Field(
        default=None, description="Gross profit / buy_price * 100"
    )
    net_margin_pct: float | None = Field(default=None, description="Net profit / buy_cost * 100")
    trade_mode: str = Field(
        default="immediate",
        description="Trade mode: 'immediate' | 'hybrid' | 'station_trading'",
    )
    broker_fee_pct: float = Field(
        default=0.03, description="Broker fee rate (only applies in hybrid/station_trading)"
    )
    sales_tax_pct: float = Field(default=0.036, description="Sales tax rate used (default 3.6%)")

    # V2 Fields: Liquidity (from market history)
    daily_volume: int | None = Field(
        default=None, ge=0, description="Average daily trade volume from history"
    )
    daily_volume_source: str | None = Field(
        default=None, description="Source: 'history' or 'market_proxy'"
    )

    # V2 Fields: Hauling Score
    hauling_score: float | None = Field(
        default=None, description="ISK profit per m³ of transport capacity"
    )
    safe_quantity: int | None = Field(
        default=None, ge=0, description="Liquidity-adjusted quantity to trade"
    )
    expected_profit: float | None = Field(
        default=None, description="net_profit_per_unit × safe_quantity"
    )
    fill_ratio: float | None = Field(
        default=None, ge=0, le=1, description="cargo_used / cargo_capacity_m3"
    )
    limiting_factor: str | None = Field(
        default=None,
        description="Primary constraint: 'cargo' | 'liquidity' | 'market_supply_buy' | 'market_supply_sell'",
    )
    limiting_factors: list[str] | None = Field(default=None, description="All binding constraints")

    # Phase 4 Fields: Ad-hoc Scope Data Provenance
    buy_scope_name: str | None = Field(default=None, description="Scope name for buy side")
    sell_scope_name: str | None = Field(default=None, description="Scope name for sell side")
    data_age: int | None = Field(
        default=None, ge=0, description="Age of CCP data (now - http_last_modified)"
    )
    last_checked: int | None = Field(
        default=None, ge=0, description="Seconds since last fetch (now - updated_at)"
    )
    is_truncated: bool = Field(default=False, description="True if fetch_status != 'complete'")
    source_type: str | None = Field(default=None, description="'fuzzwork' (hub) or 'esi' (scope)")


class BasicExecutionInfo(MarketModel):
    """
    V1 execution info for an arbitrage opportunity.

    Provides basic logistics calculation without advanced features
    like slippage estimation or ship recommendations.
    """

    cargo_volume: float = Field(ge=0, description="Total cargo volume in m3")
    estimated_profit: float = Field(description="Estimated profit after fees")
    broker_fee: float = Field(ge=0, description="Estimated broker fee")
    sales_tax: float = Field(ge=0, description="Estimated sales tax")
    total_investment: float = Field(ge=0, description="ISK needed to buy goods")
    roi_pct: float = Field(description="Return on investment percentage")


class ArbitrageScanResult(MarketModel):
    """
    Result from market_arbitrage_scan tool.

    Contains list of opportunities with metadata about the scan.
    """

    opportunities: list[ArbitrageOpportunity] = Field(default_factory=list)
    total_found: int = Field(
        default=0, ge=0, description="Total opportunities found before filtering"
    )
    regions_scanned: list[str] = Field(default_factory=list)
    scan_timestamp: int = Field(description="Unix timestamp of scan")
    data_freshness: FreshnessLevel = Field(default="fresh", description="Overall freshness")
    stale_warning: str | None = Field(
        default=None,
        description="Warning if data is stale",
    )
    refresh_performed: bool = Field(default=False, description="Whether refresh was triggered")
    warnings: list[str] = Field(default_factory=list)


class ArbitrageDetailResult(MarketModel):
    """
    Result from market_arbitrage_detail tool.

    Detailed analysis of a specific arbitrage opportunity with
    live order book data and execution planning.
    """

    opportunity: ArbitrageOpportunity
    execution: BasicExecutionInfo
    buy_orders: list[MarketOrder] = Field(
        default_factory=list,
        description="Live sell orders at buy region",
    )
    sell_orders: list[MarketOrder] = Field(
        default_factory=list,
        description="Live buy orders at sell region",
    )
    route_systems: list[str] = Field(default_factory=list, description="Route system names")
    warnings: list[str] = Field(default_factory=list)


class RefreshResult(MarketModel):
    """
    Result from a market data refresh operation.
    """

    regions_refreshed: list[str] = Field(default_factory=list)
    items_updated: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)
    was_stale: bool = Field(default=False, description="True if refresh was needed")


class RegionPriceSnapshot(MarketModel):
    """
    Price snapshot for a single item in a single region.

    Used internally for cross-region comparison.
    """

    type_id: int = Field(ge=1)
    region_id: int = Field(ge=1)
    region_name: str
    buy_max: float | None = Field(default=None, ge=0)
    buy_volume: int = Field(default=0, ge=0)
    sell_min: float | None = Field(default=None, ge=0)
    sell_volume: int = Field(default=0, ge=0)
    spread_pct: float | None = Field(default=None)
    updated_at: int = Field(description="Unix timestamp")
    freshness: FreshnessLevel = Field(default="fresh")


# =============================================================================
# Nearby Market Search Models
# =============================================================================

SourceFilter = Literal["all", "npc", "player"]
"""Filter for market source type: all, npc (364+ day orders), or player."""

RouteSecurityLevel = Literal["high", "low", "mixed-low", "mixed-null", "null"]
"""Security classification for a route to a market source."""


class NearbyMarketSource(MarketModel):
    """
    A nearby market source for an item.

    Contains location, pricing, distance, and order classification info.
    """

    order_id: int = Field(ge=1, description="ESI order ID")
    price: float = Field(ge=0, description="Price per unit")
    volume_remain: int = Field(ge=0, description="Remaining volume")
    volume_total: int = Field(ge=0, description="Original volume")

    # Location details
    station_id: int = Field(ge=1, description="Station or structure ID")
    station_name: str | None = Field(
        default=None,
        description="Station name (None for player structures)",
    )
    system_id: int = Field(ge=1, description="Solar system ID")
    system_name: str = Field(description="Solar system name")
    security: float = Field(ge=-1.0, le=1.0, description="System security status")
    region_id: int = Field(ge=1, description="Region ID")
    region_name: str = Field(description="Region name")

    # Distance and routing
    jumps_from_origin: int = Field(ge=0, description="Jump count from origin")
    route_security: RouteSecurityLevel | None = Field(
        default=None,
        description="Route security classification (computed for top results only)",
    )

    # Order classification
    duration: int = Field(ge=0, description="Order duration in days")
    is_npc: bool = Field(description="True if duration >= 364 (NPC order heuristic)")
    issued: str = Field(description="ISO timestamp when order was placed")

    # Derived metrics
    price_per_jump: float | None = Field(
        default=None,
        description="Price divided by jumps (None if 0 jumps)",
    )

    # Anomaly flags
    price_flags: list[str] = Field(
        default_factory=list,
        description="Warning flags for suspicious pricing",
    )


class MarketFindNearbyResult(MarketModel):
    """
    Result from market_find_nearby tool.

    Contains nearby market sources sorted by distance with summary stats.
    """

    # Query info
    type_id: int = Field(ge=1, description="Resolved type ID")
    type_name: str = Field(description="Resolved item name")
    category_id: int | None = Field(default=None, description="Item category ID")
    category_name: str | None = Field(default=None, description="Item category name")
    origin_system: str = Field(description="Origin system name")
    origin_region: str = Field(description="Origin region name")

    # Results
    sources: list[NearbyMarketSource] = Field(
        default_factory=list,
        description="Market sources sorted by distance",
    )
    total_found: int = Field(ge=0, description="Total orders found before limit")

    # Search metadata
    regions_searched: list[str] = Field(
        default_factory=list,
        description="Regions queried for orders",
    )
    source_filter_applied: SourceFilter = Field(
        description="Source filter actually used",
    )
    source_filter_suggested: SourceFilter = Field(
        description="Suggested filter based on item category",
    )

    # Summary stats
    nearest_source: NearbyMarketSource | None = Field(
        default=None,
        description="Closest source by jumps",
    )
    cheapest_source: NearbyMarketSource | None = Field(
        default=None,
        description="Lowest price source",
    )
    best_value: NearbyMarketSource | None = Field(
        default=None,
        description="Best balance of price and distance",
    )

    # Reference price for anomaly detection
    jita_reference_price: float | None = Field(
        default=None,
        ge=0,
        description="Jita sell price for comparison",
    )

    # Warnings
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Watchlist and Scope Management Models
# =============================================================================


class WatchlistInfo(MarketModel):
    """Watchlist information for API responses."""

    watchlist_id: int = Field(ge=1, description="Unique watchlist ID")
    name: str = Field(description="Watchlist name")
    owner_character_id: int | None = Field(
        default=None, description="Character ID for ownership (None = global)"
    )
    item_count: int = Field(ge=0, description="Number of items in watchlist")
    created_at: int = Field(ge=0, description="Unix timestamp of creation")


class WatchlistItemInfo(MarketModel):
    """Watchlist item with resolved type name."""

    type_id: int = Field(ge=1, description="EVE type ID")
    type_name: str = Field(description="Item name (resolved from SDE)")
    added_at: int = Field(ge=0, description="Unix timestamp when added")


class WatchlistDetail(MarketModel):
    """Detailed watchlist with items."""

    watchlist_id: int = Field(ge=1, description="Unique watchlist ID")
    name: str = Field(description="Watchlist name")
    owner_character_id: int | None = Field(
        default=None, description="Character ID for ownership (None = global)"
    )
    items: list[WatchlistItemInfo] = Field(
        default_factory=list, description="Items in the watchlist"
    )
    created_at: int = Field(ge=0, description="Unix timestamp of creation")


class MarketScopeInfo(MarketModel):
    """Market scope information for API responses."""

    scope_id: int = Field(ge=1, description="Unique scope ID")
    scope_name: str = Field(description="Scope name")
    scope_type: str = Field(
        description="Scope type: hub_region, region, station, system, structure"
    )
    location_id: int = Field(ge=1, description="Relevant location ID for the scope type")
    location_name: str | None = Field(
        default=None, description="Resolved location name if available"
    )
    parent_region_id: int | None = Field(
        default=None, description="Parent region ID for station/system/structure scopes"
    )
    watchlist_name: str | None = Field(
        default=None, description="Resolved watchlist name (None for core hubs)"
    )
    is_core: bool = Field(description="True for core trade hub scopes")
    source: str = Field(description="Data source: fuzzwork or esi")
    owner_character_id: int | None = Field(default=None, description="Scope owner (None = global)")
    last_scan_status: str = Field(
        default="new", description="Scan status: new, complete, truncated, error"
    )
    last_scanned_at: int | None = Field(default=None, description="Unix timestamp of last scan")


class WatchlistCreateResult(MarketModel):
    """Result of watchlist creation."""

    watchlist: WatchlistInfo = Field(description="Created watchlist info")
    items_added: int = Field(ge=0, description="Number of items successfully added")
    unresolved_items: list[str] = Field(
        default_factory=list, description="Item names that could not be resolved"
    )


class WatchlistAddItemResult(MarketModel):
    """Result of adding an item to a watchlist."""

    item: WatchlistItemInfo = Field(description="Added item info")
    watchlist_name: str = Field(description="Name of the watchlist")


class WatchlistDeleteResult(MarketModel):
    """Result of watchlist deletion."""

    deleted: bool = Field(description="True if watchlist was deleted")
    watchlist_name: str = Field(description="Name of the deleted watchlist")
    items_deleted: int = Field(ge=0, description="Number of items that were in the list")


class ScopeCreateResult(MarketModel):
    """Result of scope creation."""

    scope: MarketScopeInfo = Field(description="Created scope info")


class ScopeDeleteResult(MarketModel):
    """Result of scope deletion."""

    deleted: bool = Field(description="True if scope was deleted")
    scope_name: str = Field(description="Name of the deleted scope")


class ScopePriceRefreshInfo(MarketModel):
    """Per-type refresh status from a scope refresh operation."""

    type_id: int = Field(ge=1, description="EVE type ID")
    type_name: str = Field(description="Item name")
    fetch_status: str = Field(description="Fetch status: complete | truncated | skipped_truncation")
    order_count_buy: int = Field(ge=0, description="Number of buy orders found")
    order_count_sell: int = Field(ge=0, description="Number of sell orders found")
    buy_max: float | None = Field(default=None, ge=0, description="Highest buy price")
    sell_min: float | None = Field(default=None, ge=0, description="Lowest sell price")


class ScopeRefreshResult(MarketModel):
    """
    Result from market_scope_refresh tool.

    Contains detailed information about a scope refresh operation,
    including per-item price data and metadata about the fetch.
    """

    scope_id: int = Field(ge=1, description="Scope ID")
    scope_name: str = Field(description="Scope name")
    scope_type: str = Field(description="Scope type: region | station | system | structure")
    items_refreshed: int = Field(
        ge=0, description="Number of watchlist items successfully refreshed"
    )
    items_skipped: int = Field(
        ge=0, description="Number of items skipped (e.g., due to truncation)"
    )
    items_with_orders: int = Field(ge=0, description="Number of items that had at least one order")
    items_without_orders: int = Field(ge=0, description="Number of items with zero orders")
    refresh_duration_ms: int = Field(ge=0, description="Total refresh time in milliseconds")
    http_last_modified: int | None = Field(
        default=None, description="ESI Last-Modified timestamp (Unix)"
    )
    http_expires: int | None = Field(default=None, description="ESI Expires timestamp (Unix)")
    scan_status: str = Field(description="Overall scan status: complete | truncated | error")
    was_conditional: bool = Field(
        default=False, description="True if ESI returned 304 Not Modified"
    )
    pages_fetched: int | None = Field(
        default=None, description="Pages fetched (structure scopes only)"
    )
    pages_truncated: bool = Field(default=False, description="True if pagination was truncated")
    prices: list[ScopePriceRefreshInfo] = Field(
        default_factory=list, description="Per-item price refresh results"
    )
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
    errors: list[str] = Field(default_factory=list, description="Error messages")


class WatchlistListResult(MarketModel):
    """Result of listing watchlists."""

    watchlists: list[WatchlistInfo] = Field(default_factory=list, description="Watchlist summaries")
    total: int = Field(ge=0, description="Total number of watchlists")


class ScopeListResult(MarketModel):
    """Result of listing scopes."""

    scopes: list[MarketScopeInfo] = Field(default_factory=list, description="Scope summaries")
    core_count: int = Field(ge=0, description="Number of core hub scopes")
    adhoc_count: int = Field(ge=0, description="Number of ad-hoc scopes")


class ManagementError(MarketModel):
    """Error response for management operations."""

    code: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    suggestions: list[str] = Field(default_factory=list, description="Suggested corrections")
