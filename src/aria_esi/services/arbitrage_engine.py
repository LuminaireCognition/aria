"""
Arbitrage Detection Engine.

Identifies profitable cross-region trading opportunities by comparing
prices across trade hubs. Includes fee calculation for accurate
profit estimation.

V1 Implementation:
- Simple detection query across region_prices table
- Basic broker fee / sales tax calculation
- Freshness-based confidence scoring
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

from aria_esi.mcp.market.database_async import AsyncMarketDatabase, get_async_market_database
from aria_esi.models.market import (
    TRADE_HUBS,
    ArbitrageDetailResult,
    ArbitrageOpportunity,
    ArbitrageScanResult,
    ConfidenceLevel,
    FreshnessLevel,
)

# Import from extracted modules
from aria_esi.services.arbitrage_fees import (
    V2_BROKER_FEE_PCT,
    V2_SALES_TAX_PCT,
    ArbitrageCalculator,
    calculate_net_profit,
)
from aria_esi.services.arbitrage_freshness import (
    RECENT_THRESHOLD,
    SCOPE_RECENT_THRESHOLD,
    get_confidence,
    get_effective_volume,
    get_freshness,
    get_scope_freshness,
)

logger = get_logger("aria_market.arbitrage")

# =============================================================================
# Constants
# =============================================================================

# Region ID to name mapping (reverse lookup)
REGION_ID_TO_NAME: dict[int, str] = {
    config["region_id"]: config["region_name"] for config in TRADE_HUBS.values()
}

# Region ID to hub name mapping
REGION_ID_TO_HUB: dict[int, str] = {
    config["region_id"]: hub_name for hub_name, config in TRADE_HUBS.items()
}


# =============================================================================
# Arbitrage Engine
# =============================================================================


@dataclass
class ArbitrageEngine:
    """
    Engine for detecting and analyzing arbitrage opportunities.

    Queries the region_prices table to find profitable cross-region
    trades and calculates accurate profit after fees.

    Attributes:
        calculator: Fee calculator instance
        allow_stale: Whether to include stale data in results
    """

    calculator: ArbitrageCalculator = field(default_factory=ArbitrageCalculator)
    allow_stale: bool = False
    _database: AsyncMarketDatabase | None = field(default=None, repr=False)

    async def _get_database(self) -> AsyncMarketDatabase:
        """Get database connection."""
        if self._database is None:
            self._database = await get_async_market_database()
        return self._database

    # Delegate to module-level functions for freshness/confidence
    def _get_freshness(self, timestamp: int) -> FreshnessLevel:
        """Classify freshness based on timestamp (hub data thresholds)."""
        return get_freshness(timestamp)

    def _get_scope_freshness(self, timestamp: int) -> FreshnessLevel:
        """Classify freshness based on timestamp (scope data - more lenient)."""
        return get_scope_freshness(timestamp)

    def _get_confidence(
        self,
        buy_freshness: FreshnessLevel,
        sell_freshness: FreshnessLevel,
    ) -> ConfidenceLevel:
        """Calculate V1 confidence level based on data freshness."""
        return get_confidence(buy_freshness, sell_freshness)

    def _calculate_net_profit(
        self,
        buy_price: float,
        sell_price: float,
        trade_mode: str = "immediate",
        broker_fee_pct: float = V2_BROKER_FEE_PCT,
        sales_tax_pct: float = V2_SALES_TAX_PCT,
    ) -> tuple[float, float, float, float]:
        """Calculate fee-adjusted net profit per unit based on trade mode."""
        return calculate_net_profit(
            buy_price, sell_price, trade_mode, broker_fee_pct, sales_tax_pct
        )

    def _get_effective_volume(
        self,
        volume: float | None,
        packaged_volume: float | None,
    ) -> tuple[float, str]:
        """Get effective item volume, preferring packaged volume."""
        return get_effective_volume(volume, packaged_volume)

    async def _find_scope_opportunities(
        self,
        scope_ids: list[int],
        scope_metadata: dict[int, dict],
        min_profit_pct: float = 5.0,
        min_volume: int = 10,
        trade_mode: str = "immediate",
        broker_fee_pct: float = V2_BROKER_FEE_PCT,
        sales_tax_pct: float = V2_SALES_TAX_PCT,
    ) -> list[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities involving ad-hoc scopes.

        Queries scope prices and finds profitable pairs between scopes
        or between scopes and hub regions.

        Args:
            scope_ids: List of scope IDs to include
            scope_metadata: Dict mapping scope_id -> {scope_name, scope_type, region_id, ...}
            min_profit_pct: Minimum gross profit percentage
            min_volume: Minimum available volume
            trade_mode: Trade execution mode
            broker_fee_pct: Broker fee rate
            sales_tax_pct: Sales tax rate

        Returns:
            List of ArbitrageOpportunity objects from scope data
        """
        if not scope_ids:
            return []

        db = await self._get_database()
        now = int(time.time())

        # Get scope prices with metadata
        scope_prices = await db.get_scope_prices_for_arbitrage(
            scope_ids,
            max_age_seconds=SCOPE_RECENT_THRESHOLD,
        )

        if not scope_prices:
            return []

        # Build price lookup: (type_id, scope_id) -> price_row
        price_lookup: dict[tuple[int, int], dict] = {}
        for row in scope_prices:
            key = (row["type_id"], row["scope_id"])
            price_lookup[key] = row

        # Group prices by type_id for cross-scope comparison
        prices_by_type: dict[int, list[dict]] = {}
        for row in scope_prices:
            type_id = row["type_id"]
            if type_id not in prices_by_type:
                prices_by_type[type_id] = []
            prices_by_type[type_id].append(row)

        opportunities = []

        # Find profitable pairs: buy from one scope, sell to another
        for type_id, type_prices in prices_by_type.items():
            if len(type_prices) < 2:
                continue

            # Find best buy (lowest sell_min) and best sell (highest buy_max)
            for buy_row in type_prices:
                buy_price = buy_row.get("sell_min")
                if buy_price is None or buy_price <= 0:
                    continue

                for sell_row in type_prices:
                    if sell_row["scope_id"] == buy_row["scope_id"]:
                        continue  # Skip same scope

                    sell_price = sell_row.get("buy_max")
                    if sell_price is None or sell_price <= buy_price:
                        continue

                    # Calculate gross profit
                    gross_profit = sell_price - buy_price
                    gross_margin = (gross_profit / buy_price) * 100

                    if gross_margin < min_profit_pct:
                        continue

                    # Check volume
                    available_volume = min(
                        buy_row.get("sell_volume") or 0,
                        sell_row.get("buy_volume") or 0,
                    )
                    if available_volume < min_volume:
                        continue

                    # Calculate net profit
                    net_profit, net_margin, _, _ = self._calculate_net_profit(
                        buy_price, sell_price, trade_mode, broker_fee_pct, sales_tax_pct
                    )

                    if net_profit <= 0:
                        continue

                    # Get metadata
                    buy_scope = scope_metadata.get(buy_row["scope_id"], {})
                    sell_scope = scope_metadata.get(sell_row["scope_id"], {})

                    # Get effective volume
                    effective_volume, volume_source = self._get_effective_volume(
                        buy_row.get("volume"), buy_row.get("packaged_volume")
                    )
                    profit_density = net_profit / effective_volume

                    # Calculate freshness from scope data
                    buy_freshness = self._get_scope_freshness(buy_row["updated_at"])
                    sell_freshness = self._get_scope_freshness(sell_row["updated_at"])

                    if buy_freshness == "stale" or sell_freshness == "stale":
                        freshness: FreshnessLevel = "stale"
                    elif buy_freshness == "recent" or sell_freshness == "recent":
                        freshness = "recent"
                    else:
                        freshness = "fresh"

                    # Determine truncation status
                    is_truncated = (
                        buy_row.get("fetch_status") != "complete"
                        or sell_row.get("fetch_status") != "complete"
                    )

                    # Calculate data age from http_last_modified
                    buy_http_modified = buy_row.get("http_last_modified")
                    sell_http_modified = sell_row.get("http_last_modified")
                    data_age = None
                    if buy_http_modified and sell_http_modified:
                        oldest_modified = min(buy_http_modified, sell_http_modified)
                        data_age = now - oldest_modified
                    elif buy_http_modified:
                        data_age = now - buy_http_modified
                    elif sell_http_modified:
                        data_age = now - sell_http_modified

                    # Calculate last_checked from updated_at
                    oldest_updated = min(buy_row["updated_at"], sell_row["updated_at"])
                    last_checked = now - oldest_updated

                    opportunities.append(
                        ArbitrageOpportunity(
                            type_id=type_id,
                            type_name=buy_row["type_name"],
                            buy_region=buy_scope.get("scope_name", f"Scope {buy_row['scope_id']}"),
                            buy_region_id=buy_scope.get("region_id")
                            or buy_row.get("scope_region_id")
                            or 0,
                            sell_region=sell_scope.get(
                                "scope_name", f"Scope {sell_row['scope_id']}"
                            ),
                            sell_region_id=sell_scope.get("region_id")
                            or sell_row.get("scope_region_id")
                            or 0,
                            buy_price=round(buy_price, 2),
                            sell_price=round(sell_price, 2),
                            profit_per_unit=round(gross_profit, 2),
                            profit_pct=round(gross_margin, 2),
                            available_volume=available_volume,
                            freshness=freshness,
                            confidence=self._get_confidence(buy_freshness, sell_freshness),
                            # V2 fields
                            item_volume_m3=effective_volume,
                            item_packaged_volume_m3=buy_row.get("packaged_volume"),
                            volume_source=volume_source,
                            profit_density=round(profit_density, 2),
                            buy_available_volume=buy_row.get("sell_volume") or 0,
                            sell_available_volume=sell_row.get("buy_volume") or 0,
                            gross_profit_per_unit=round(gross_profit, 2),
                            net_profit_per_unit=round(net_profit, 2),
                            gross_margin_pct=round(gross_margin, 2),
                            net_margin_pct=round(net_margin, 2),
                            trade_mode=trade_mode,
                            broker_fee_pct=broker_fee_pct,
                            sales_tax_pct=sales_tax_pct,
                            # Phase 4 fields
                            buy_scope_name=buy_scope.get("scope_name"),
                            sell_scope_name=sell_scope.get("scope_name"),
                            data_age=data_age,
                            last_checked=last_checked,
                            is_truncated=is_truncated,
                            source_type="esi",
                        )
                    )

        return opportunities

    def _merge_opportunities(
        self,
        hub_opps: list[ArbitrageOpportunity],
        scope_opps: list[ArbitrageOpportunity],
    ) -> list[ArbitrageOpportunity]:
        """
        Merge hub and scope opportunities with deduplication.

        When the same opportunity (type_id, buy_region_id, sell_region_id) exists
        in both lists, prefer hub data as it's typically fresher and more reliable.

        Args:
            hub_opps: Opportunities from hub data (Fuzzwork)
            scope_opps: Opportunities from scope data (ESI)

        Returns:
            Merged list with duplicates removed (hub preferred)
        """
        # Build a set of hub opportunity keys for deduplication
        hub_keys: set[tuple[int, int, int]] = {
            (opp.type_id, opp.buy_region_id, opp.sell_region_id) for opp in hub_opps
        }

        # Start with all hub opportunities
        merged = list(hub_opps)

        # Add scope opportunities that don't conflict with hub data
        for opp in scope_opps:
            key = (opp.type_id, opp.buy_region_id, opp.sell_region_id)
            if key not in hub_keys:
                merged.append(opp)

        return merged

    async def find_opportunities(
        self,
        min_profit_pct: float = 5.0,
        min_volume: int = 10,
        max_results: int = 50,
        regions: Sequence[int] | None = None,
        buy_regions: Sequence[int] | None = None,
        sell_regions: Sequence[int] | None = None,
        sort_by: str = "margin",
        trade_mode: str = "immediate",
        broker_fee_pct: float = V2_BROKER_FEE_PCT,
        sales_tax_pct: float = V2_SALES_TAX_PCT,
        include_history: bool = False,
        cargo_capacity_m3: float | None = None,
        scopes: list[str] | None = None,
        scope_owner_id: int | None = None,
        include_custom_scopes: bool = False,
    ) -> list[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities across trade hubs.

        All profit calculations use NET profit (after fees based on trade_mode).
        Opportunities with net_profit_per_unit <= 0 are automatically filtered.

        Args:
            min_profit_pct: Minimum gross profit percentage to include (initial filter)
            min_volume: Minimum available volume
            max_results: Maximum opportunities to return
            regions: Region IDs to include for both buy and sell (default: all trade hubs)
                     Deprecated: Use buy_regions/sell_regions for finer control
            buy_regions: Region IDs to buy FROM (source regions). If specified, overrides
                        regions for the buy side. Use with sell_regions to filter specific
                        trade routes (e.g., Dodixie → Hek only).
            sell_regions: Region IDs to sell TO (destination regions). If specified,
                         overrides regions for the sell side.
            sort_by: Ranking method:
                - "margin": Net profit percentage (default, uses net_margin_pct)
                - "profit_density": Net ISK profit per m³ of used cargo
                - "hauling_score": Best ISK per trip (requires cargo_capacity_m3)
            trade_mode: Trade execution mode affecting fee calculation:
                - "immediate": Take sell orders → Take buy orders. Fees: sales tax only.
                - "hybrid": Take sell orders → Place sell orders. Fees: broker + sales tax on sell.
                - "station_trading": Place buy/sell orders. Fees: broker on both + sales tax.
            broker_fee_pct: Broker fee rate (decimal, default 0.03 = 3%)
            sales_tax_pct: Sales tax rate (decimal, default 0.036 = 3.6%)
            include_history: Fetch market history for daily volume data (slower)
            cargo_capacity_m3: Ship cargo capacity in m³ (required for hauling_score)
            scopes: List of scope names to include (requires include_custom_scopes=True)
            scope_owner_id: Character ID for scope ownership resolution
            include_custom_scopes: If True, include ad-hoc scope data in arbitrage scan

        Returns:
            List of ArbitrageOpportunity sorted by specified sort mode

        Raises:
            ValueError: If sort_by="hauling_score" but cargo_capacity_m3 is not provided
        """
        # Validate hauling_score requirements
        if sort_by == "hauling_score" and cargo_capacity_m3 is None:
            raise ValueError("sort_by='hauling_score' requires cargo_capacity_m3 to be specified")
        db = await self._get_database()
        conn = await db._get_connection()

        # Build region filter
        # Priority: buy_regions/sell_regions > regions > all trade hubs
        hub_ids = [config["region_id"] for config in TRADE_HUBS.values()]

        # Determine buy-side filter (source regions where we buy from sell orders)
        if buy_regions:
            buy_region_ids = list(buy_regions)
        elif regions:
            buy_region_ids = list(regions)
        else:
            buy_region_ids = hub_ids

        # Determine sell-side filter (destination regions where we sell to buy orders)
        if sell_regions:
            sell_region_ids = list(sell_regions)
        elif regions:
            sell_region_ids = list(regions)
        else:
            sell_region_ids = hub_ids

        # Build the SQL filter clause
        # Note: In the query, "sell" alias = source (where we buy from sell orders)
        #       and "buy" alias = destination (where we sell to buy orders)
        buy_filter = f"sell.region_id IN ({','.join(str(r) for r in buy_region_ids)})"
        sell_filter = f"buy.region_id IN ({','.join(str(r) for r in sell_region_ids)})"
        region_filter = f"AND {buy_filter} AND {sell_filter}"

        # Staleness filter
        if not self.allow_stale:
            # Only include data less than 30 minutes old
            stale_cutoff = int(time.time()) - RECENT_THRESHOLD
            stale_filter = (
                f"AND sell.updated_at > {stale_cutoff} AND buy.updated_at > {stale_cutoff}"
            )
        else:
            stale_filter = ""

        # V2 query with volume columns
        query = f"""
        SELECT
            buy.type_id,
            COALESCE(t.type_name, 'Type ' || buy.type_id) as type_name,
            t.volume as item_volume,
            t.packaged_volume as item_packaged_volume,
            sell.region_id AS sell_region_id,
            buy.region_id AS buy_region_id,
            sell.sell_min AS sell_price,
            buy.buy_max AS buy_price,
            sell.sell_volume AS sell_available_volume,
            buy.buy_volume AS buy_available_volume,
            (buy.buy_max - sell.sell_min) AS profit_per_unit,
            ROUND(((buy.buy_max - sell.sell_min) / sell.sell_min) * 100, 2) AS profit_pct,
            MIN(sell.sell_volume, buy.buy_volume) AS available_volume,
            sell.updated_at AS sell_updated,
            buy.updated_at AS buy_updated
        FROM region_prices sell
        JOIN region_prices buy ON sell.type_id = buy.type_id
            AND sell.region_id != buy.region_id
        LEFT JOIN types t ON t.type_id = sell.type_id
        WHERE
            sell.sell_min IS NOT NULL
            AND buy.buy_max IS NOT NULL
            AND sell.sell_min > 0
            AND buy.buy_max > sell.sell_min
            AND ((buy.buy_max - sell.sell_min) / sell.sell_min) * 100 >= ?
            AND MIN(sell.sell_volume, buy.buy_volume) >= ?
            {region_filter}
            {stale_filter}
        ORDER BY profit_pct DESC
        LIMIT ?
        """

        # Fetch more than max_results since we'll filter by net profit
        fetch_limit = max_results * 3

        async with conn.execute(query, (min_profit_pct, min_volume, fetch_limit)) as cursor:
            rows = await cursor.fetchall()

        # Fetch history data if requested
        history_data: dict[int, tuple[int | None, str]] = {}  # type_id -> (daily_volume, source)
        if include_history and rows:
            try:
                from aria_esi.services.history_cache import get_history_cache_service

                history_service = await get_history_cache_service()
                # Build batch request: use sell region (where we buy)
                history_items = [
                    (row["type_id"], row["sell_region_id"], row["available_volume"]) for row in rows
                ]
                history_results = await history_service.get_daily_volumes_batch(history_items)
                for type_id, result in history_results.items():
                    history_data[type_id] = (result.daily_volume, result.source)
            except Exception as e:
                logger.warning("Failed to fetch history data: %s", e)

        opportunities = []
        for row in rows:
            buy_price = row["sell_price"]
            sell_price = row["buy_price"]

            # Calculate net profit after fees based on trade mode
            net_profit, net_margin, gross_profit, gross_margin = self._calculate_net_profit(
                buy_price, sell_price, trade_mode, broker_fee_pct, sales_tax_pct
            )

            # Filter out negative net profit opportunities
            if net_profit <= 0:
                continue

            # Get effective volume for density calculation
            effective_volume, volume_source = self._get_effective_volume(
                row["item_volume"], row["item_packaged_volume"]
            )

            # Calculate profit density (net profit per m³)
            profit_density = net_profit / effective_volume

            sell_freshness = self._get_freshness(row["sell_updated"])
            buy_freshness = self._get_freshness(row["buy_updated"])

            # Overall freshness is the worse of the two
            if sell_freshness == "stale" or buy_freshness == "stale":
                freshness: FreshnessLevel = "stale"
            elif sell_freshness == "recent" or buy_freshness == "recent":
                freshness = "recent"
            else:
                freshness = "fresh"

            # Get history data for this type
            daily_volume = None
            daily_volume_source = None
            if row["type_id"] in history_data:
                daily_volume, daily_volume_source = history_data[row["type_id"]]

            opportunities.append(
                ArbitrageOpportunity(
                    type_id=row["type_id"],
                    type_name=row["type_name"],
                    buy_region=REGION_ID_TO_NAME.get(
                        row["sell_region_id"], f"Region {row['sell_region_id']}"
                    ),
                    buy_region_id=row["sell_region_id"],
                    sell_region=REGION_ID_TO_NAME.get(
                        row["buy_region_id"], f"Region {row['buy_region_id']}"
                    ),
                    sell_region_id=row["buy_region_id"],
                    buy_price=round(buy_price, 2),
                    sell_price=round(sell_price, 2),
                    profit_per_unit=round(row["profit_per_unit"], 2),
                    profit_pct=row["profit_pct"],
                    available_volume=row["available_volume"],
                    freshness=freshness,
                    confidence=self._get_confidence(buy_freshness, sell_freshness),
                    # V2 fields
                    item_volume_m3=effective_volume,
                    item_packaged_volume_m3=row["item_packaged_volume"],
                    volume_source=volume_source,
                    profit_density=round(profit_density, 2),
                    buy_available_volume=row["buy_available_volume"],
                    sell_available_volume=row["sell_available_volume"],
                    gross_profit_per_unit=round(gross_profit, 2),
                    net_profit_per_unit=round(net_profit, 2),
                    gross_margin_pct=round(gross_margin, 2),
                    net_margin_pct=round(net_margin, 2),
                    trade_mode=trade_mode,
                    broker_fee_pct=broker_fee_pct,
                    sales_tax_pct=sales_tax_pct,
                    # History fields
                    daily_volume=daily_volume,
                    daily_volume_source=daily_volume_source,
                )
            )

        # Process custom scopes if enabled
        if include_custom_scopes and scopes:
            try:
                # Resolve scope names to scope objects
                resolved_scopes = await db.resolve_scopes(
                    scopes,
                    owner_character_id=scope_owner_id,
                    include_core=False,  # Only ad-hoc scopes
                )

                if resolved_scopes:
                    # Build scope metadata dict
                    scope_ids = [s.scope_id for s in resolved_scopes]
                    scope_metadata = {
                        s.scope_id: {
                            "scope_name": s.scope_name,
                            "scope_type": s.scope_type,
                            "region_id": s.region_id,
                            "is_core": s.is_core,
                        }
                        for s in resolved_scopes
                    }

                    # Find scope opportunities
                    scope_opps = await self._find_scope_opportunities(
                        scope_ids=scope_ids,
                        scope_metadata=scope_metadata,
                        min_profit_pct=min_profit_pct,
                        min_volume=min_volume,
                        trade_mode=trade_mode,
                        broker_fee_pct=broker_fee_pct,
                        sales_tax_pct=sales_tax_pct,
                    )

                    # Merge with hub opportunities (hub data preferred for duplicates)
                    opportunities = self._merge_opportunities(opportunities, scope_opps)

                    logger.info(
                        "Scope arbitrage: found %d scope opportunities from %d scopes",
                        len(scope_opps),
                        len(resolved_scopes),
                    )

            except Exception as e:
                logger.warning("Failed to process scope opportunities: %s", e)

        # Calculate hauling scores if cargo capacity is provided
        if cargo_capacity_m3 is not None:
            from aria_esi.services.hauling_score import calculate_hauling_score

            updated_opportunities = []
            for opp in opportunities:
                hs_result = calculate_hauling_score(
                    net_profit_per_unit=opp.net_profit_per_unit or 0,
                    volume_m3=opp.item_volume_m3,
                    packaged_volume_m3=opp.item_packaged_volume_m3,
                    daily_volume=opp.daily_volume,
                    buy_available_volume=opp.buy_available_volume,
                    sell_available_volume=opp.sell_available_volume,
                    cargo_capacity_m3=cargo_capacity_m3,
                    daily_volume_source=opp.daily_volume_source or "none",
                )
                # Update opportunity with hauling score fields
                updated_opportunities.append(
                    opp.model_copy(
                        update={
                            "hauling_score": hs_result.score,
                            "safe_quantity": hs_result.safe_quantity,
                            "expected_profit": hs_result.expected_profit,
                            "fill_ratio": hs_result.fill_ratio,
                            "limiting_factor": hs_result.limiting_factor,
                            "limiting_factors": hs_result.limiting_factors,
                            "availability_source": hs_result.availability_source,
                        }
                    )
                )
            opportunities = updated_opportunities

        # Sort by specified mode
        if sort_by == "hauling_score":
            opportunities.sort(key=lambda o: o.hauling_score or 0, reverse=True)
        elif sort_by == "profit_density":
            opportunities.sort(key=lambda o: o.profit_density or 0, reverse=True)
        else:
            # Default: sort by net_margin_pct (descending)
            opportunities.sort(key=lambda o: o.net_margin_pct or 0, reverse=True)

        # Limit to requested max_results
        return opportunities[:max_results]

    async def get_scan_result(
        self,
        min_profit_pct: float = 5.0,
        min_volume: int = 10,
        max_results: int = 20,
        regions: Sequence[int] | None = None,
        buy_regions: Sequence[int] | None = None,
        sell_regions: Sequence[int] | None = None,
        refresh_performed: bool = False,
        sort_by: str = "margin",
        trade_mode: str = "immediate",
        broker_fee_pct: float = V2_BROKER_FEE_PCT,
        sales_tax_pct: float = V2_SALES_TAX_PCT,
        include_history: bool = False,
        cargo_capacity_m3: float | None = None,
        scopes: list[str] | None = None,
        scope_owner_id: int | None = None,
        include_custom_scopes: bool = False,
    ) -> ArbitrageScanResult:
        """
        Get a complete scan result with metadata.

        Args:
            min_profit_pct: Minimum profit percentage
            min_volume: Minimum available volume
            max_results: Maximum opportunities
            regions: Region IDs to include (both buy and sell)
            buy_regions: Region IDs to buy FROM (overrides regions for buy side)
            sell_regions: Region IDs to sell TO (overrides regions for sell side)
            refresh_performed: Whether a refresh was just performed
            sort_by: Ranking method ("margin", "profit_density", or "hauling_score")
            trade_mode: Trade execution mode ("immediate", "hybrid", "station_trading")
            broker_fee_pct: Broker fee rate for net profit calculation
            sales_tax_pct: Sales tax rate for net profit calculation
            include_history: Fetch market history for daily volume data
            cargo_capacity_m3: Ship cargo capacity (required for hauling_score)
            scopes: List of scope names to include (requires include_custom_scopes=True)
            scope_owner_id: Character ID for scope ownership resolution
            include_custom_scopes: If True, include ad-hoc scope data in arbitrage scan

        Returns:
            ArbitrageScanResult with opportunities and metadata
        """
        opportunities = await self.find_opportunities(
            min_profit_pct=min_profit_pct,
            min_volume=min_volume,
            max_results=max_results,
            regions=regions,
            buy_regions=buy_regions,
            sell_regions=sell_regions,
            sort_by=sort_by,
            trade_mode=trade_mode,
            broker_fee_pct=broker_fee_pct,
            sales_tax_pct=sales_tax_pct,
            include_history=include_history,
            cargo_capacity_m3=cargo_capacity_m3,
            scopes=scopes,
            scope_owner_id=scope_owner_id,
            include_custom_scopes=include_custom_scopes,
        )

        # Determine overall freshness
        if not opportunities:
            freshness: FreshnessLevel = "fresh"
        else:
            stale_count = sum(1 for o in opportunities if o.freshness == "stale")
            recent_count = sum(1 for o in opportunities if o.freshness == "recent")
            if stale_count > 0:
                freshness = "stale"
            elif recent_count > 0:
                freshness = "recent"
            else:
                freshness = "fresh"

        # Build stale warning
        stale_warning = None
        if freshness == "stale" and not self.allow_stale:
            stale_warning = "Some data is stale (>30 min old). Consider using force_refresh=True for accurate results."

        # Get regions scanned - must reflect what was actually scanned
        # This mirrors the logic in find_opportunities: unspecified side defaults to all hubs
        hub_ids = [config["region_id"] for config in TRADE_HUBS.values()]
        if buy_regions or sell_regions:
            # Specific buy/sell regions were specified
            # Include both explicit filters AND defaulted side
            all_region_ids = set()
            all_region_ids.update(buy_regions if buy_regions else hub_ids)
            all_region_ids.update(sell_regions if sell_regions else hub_ids)
            regions_scanned = [REGION_ID_TO_NAME.get(r, f"Region {r}") for r in all_region_ids]
        elif regions:
            regions_scanned = [REGION_ID_TO_NAME.get(r, f"Region {r}") for r in regions]
        else:
            regions_scanned = list(REGION_ID_TO_NAME.values())

        # Add scope names from opportunities that came from scopes
        if include_custom_scopes:
            scope_names_from_results: set[str] = set()
            for opp in opportunities:
                if opp.buy_scope_name:
                    scope_names_from_results.add(opp.buy_scope_name)
                if opp.sell_scope_name:
                    scope_names_from_results.add(opp.sell_scope_name)
            # Append unique scope names that aren't already in regions_scanned
            for scope_name in scope_names_from_results:
                if scope_name not in regions_scanned:
                    regions_scanned.append(scope_name)

        return ArbitrageScanResult(
            opportunities=opportunities,
            total_found=len(opportunities),
            regions_scanned=regions_scanned,
            scan_timestamp=int(time.time()),
            data_freshness=freshness,
            stale_warning=stale_warning,
            refresh_performed=refresh_performed,
        )

    async def get_detail(
        self,
        type_id: int,
        buy_region_id: int,
        sell_region_id: int,
    ) -> ArbitrageDetailResult | None:
        """
        Get detailed analysis of a specific arbitrage opportunity.

        Fetches live order data and calculates execution info.

        Args:
            type_id: Item type ID
            buy_region_id: Region to buy from
            sell_region_id: Region to sell to

        Returns:
            ArbitrageDetailResult or None if opportunity no longer exists
        """
        db = await self._get_database()
        conn = await db._get_connection()

        # Get current prices from region_prices
        async with conn.execute(
            """
            SELECT
                sell.sell_min AS buy_price,
                buy.buy_max AS sell_price,
                sell.sell_volume AS buy_volume,
                buy.buy_volume AS sell_volume,
                sell.updated_at AS sell_updated,
                buy.updated_at AS buy_updated,
                COALESCE(t.type_name, 'Type ' || sell.type_id) as type_name,
                t.volume as item_volume
            FROM region_prices sell
            JOIN region_prices buy ON sell.type_id = buy.type_id
            LEFT JOIN types t ON t.type_id = sell.type_id
            WHERE sell.type_id = ?
                AND sell.region_id = ?
                AND buy.region_id = ?
                AND sell.sell_min IS NOT NULL
                AND buy.buy_max IS NOT NULL
                AND sell.sell_min > 0
            """,
            (type_id, buy_region_id, sell_region_id),
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return None

        buy_price = row["buy_price"]
        sell_price = row["sell_price"]

        # Check if still profitable
        if sell_price <= buy_price:
            return None

        available_volume = min(row["buy_volume"], row["sell_volume"])
        profit_per_unit = sell_price - buy_price
        profit_pct = (profit_per_unit / buy_price) * 100

        # Get freshness
        sell_freshness = self._get_freshness(row["sell_updated"])
        buy_freshness = self._get_freshness(row["buy_updated"])

        if sell_freshness == "stale" or buy_freshness == "stale":
            freshness: FreshnessLevel = "stale"
        elif sell_freshness == "recent" or buy_freshness == "recent":
            freshness = "recent"
        else:
            freshness = "fresh"

        opportunity = ArbitrageOpportunity(
            type_id=type_id,
            type_name=row["type_name"],
            buy_region=REGION_ID_TO_NAME.get(buy_region_id, f"Region {buy_region_id}"),
            buy_region_id=buy_region_id,
            sell_region=REGION_ID_TO_NAME.get(sell_region_id, f"Region {sell_region_id}"),
            sell_region_id=sell_region_id,
            buy_price=round(buy_price, 2),
            sell_price=round(sell_price, 2),
            profit_per_unit=round(profit_per_unit, 2),
            profit_pct=round(profit_pct, 2),
            available_volume=available_volume,
            freshness=freshness,
            confidence=self._get_confidence(buy_freshness, sell_freshness),
        )

        # Calculate execution info
        item_volume = row["item_volume"] or 0.01  # Default to 0.01 m3 if unknown
        execution = self.calculator.calculate_true_profit(
            buy_price=buy_price,
            sell_price=sell_price,
            quantity=available_volume,
            cargo_volume=item_volume,
        )

        return ArbitrageDetailResult(
            opportunity=opportunity,
            execution=execution,
            buy_orders=[],  # V1: Don't fetch live orders
            sell_orders=[],
            route_systems=[],  # V1: Don't calculate route
        )


# =============================================================================
# Module-level Singleton
# =============================================================================

_arbitrage_engine: ArbitrageEngine | None = None


async def get_arbitrage_engine(allow_stale: bool = False) -> ArbitrageEngine:
    """Get or create the arbitrage engine singleton."""
    global _arbitrage_engine
    if _arbitrage_engine is None:
        _arbitrage_engine = ArbitrageEngine(allow_stale=allow_stale)
    elif _arbitrage_engine.allow_stale != allow_stale:
        # Update stale setting
        _arbitrage_engine.allow_stale = allow_stale
    return _arbitrage_engine


def reset_arbitrage_engine() -> None:
    """Reset the arbitrage engine singleton (mainly for testing)."""
    global _arbitrage_engine
    _arbitrage_engine = None
