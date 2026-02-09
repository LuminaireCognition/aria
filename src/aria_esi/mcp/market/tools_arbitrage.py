"""
Arbitrage MCP Tools.

Provides market_arbitrage_scan and market_arbitrage_detail tools
for detecting and analyzing cross-region trading opportunities.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger
from aria_esi.models.market import TRADE_HUBS, TradeHubConfig
from aria_esi.services.arbitrage_engine import get_arbitrage_engine
from aria_esi.services.market_refresh import get_refresh_service

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_market.tools_arbitrage")

# Route calculation timeout
ROUTE_TIMEOUT_SECONDS = 3.0


# =============================================================================
# Implementation functions (called by both MCP tools and unified dispatcher)
# =============================================================================


async def _arbitrage_scan_impl(
    min_profit_pct: float = 5.0,
    min_volume: int = 10,
    max_results: int = 20,
    buy_from: list[str] | None = None,
    sell_to: list[str] | None = None,
    include_lowsec: bool = False,
    allow_stale: bool = False,
    force_refresh: bool = False,
    sort_by: str = "margin",
    trade_mode: str = "immediate",
    broker_fee_pct: float = 0.03,
    sales_tax_pct: float = 0.036,
    include_history: bool = False,
    cargo_capacity_m3: float | None = None,
    include_custom_scopes: bool = False,
    scopes: list[str] | None = None,
    scope_owner_id: int | None = None,
) -> dict:
    """Arbitrage scan implementation."""
    start_time = time.time()
    warnings: list[str] = []
    refresh_performed = False

    # Resolve region names to IDs
    buy_region_ids: list[int] | None = None
    sell_region_ids: list[int] | None = None

    if buy_from:
        buy_region_ids = []
        for name in buy_from:
            config = _resolve_region(name)
            if config:
                buy_region_ids.append(config["region_id"])
            else:
                return {
                    "error": {
                        "code": "INVALID_REGION",
                        "message": f"Unknown buy_from region: {name}",
                        "data": {"valid_regions": list(TRADE_HUBS.keys())},
                    }
                }

    if sell_to:
        sell_region_ids = []
        for name in sell_to:
            config = _resolve_region(name)
            if config:
                sell_region_ids.append(config["region_id"])
            else:
                return {
                    "error": {
                        "code": "INVALID_REGION",
                        "message": f"Unknown sell_to region: {name}",
                        "data": {"valid_regions": list(TRADE_HUBS.keys())},
                    }
                }

    # Get services
    refresh_service = await get_refresh_service()
    engine = await get_arbitrage_engine(allow_stale=allow_stale)

    # Check if refresh is needed
    if force_refresh or refresh_service.get_stale_regions():
        try:
            refresh_result = await refresh_service.ensure_fresh_data(force_refresh=force_refresh)
            refresh_performed = refresh_result.was_stale or force_refresh

            if refresh_result.errors:
                for error in refresh_result.errors[:3]:  # Limit error messages
                    warnings.append(f"Refresh warning: {error}")

        except Exception as e:
            logger.warning("Refresh failed: %s", e)
            warnings.append(f"Data refresh failed: {e}. Using cached data.")

    # Scan for opportunities
    try:
        result = await engine.get_scan_result(
            min_profit_pct=min_profit_pct,
            min_volume=min_volume,
            max_results=max_results,
            buy_regions=buy_region_ids,
            sell_regions=sell_region_ids,
            refresh_performed=refresh_performed,
            sort_by=sort_by,
            trade_mode=trade_mode,
            broker_fee_pct=broker_fee_pct,
            sales_tax_pct=sales_tax_pct,
            include_history=include_history,
            cargo_capacity_m3=cargo_capacity_m3,
            scopes=scopes if include_custom_scopes else None,
            scope_owner_id=scope_owner_id,
            include_custom_scopes=include_custom_scopes,
        )

        # Add route info if possible
        if result.opportunities:
            result = await _add_route_info(result, include_lowsec)

        # Add any warnings
        if warnings:
            result = result.model_copy(update={"warnings": list(result.warnings) + warnings})

        scan_time = int((time.time() - start_time) * 1000)
        logger.info(
            "Arbitrage scan found %d opportunities in %dms",
            len(result.opportunities),
            scan_time,
        )

        return result.model_dump()

    except Exception as e:
        logger.error("Arbitrage scan failed: %s", e)
        return {
            "error": {
                "code": "SCAN_FAILED",
                "message": f"Failed to scan for opportunities: {e}",
            }
        }


async def _arbitrage_detail_impl(
    type_name: str,
    buy_region: str,
    sell_region: str,
) -> dict:
    """Arbitrage detail implementation."""
    # Resolve regions
    buy_region_config = _resolve_region(buy_region)
    sell_region_config = _resolve_region(sell_region)

    if not buy_region_config:
        return {
            "error": {
                "code": "INVALID_REGION",
                "message": f"Unknown buy region: {buy_region}",
                "data": {"valid_regions": list(TRADE_HUBS.keys())},
            }
        }

    if not sell_region_config:
        return {
            "error": {
                "code": "INVALID_REGION",
                "message": f"Unknown sell region: {sell_region}",
                "data": {"valid_regions": list(TRADE_HUBS.keys())},
            }
        }

    # Resolve type name
    from aria_esi.mcp.market.database import get_market_database

    db = get_market_database()
    type_info = db.resolve_type_name(type_name)

    if not type_info:
        suggestions = db.find_type_suggestions(type_name, limit=5)
        return {
            "error": {
                "code": "ITEM_NOT_FOUND",
                "message": f"Could not find item: {type_name}",
                "data": {"suggestions": suggestions},
            }
        }

    # Get detailed analysis
    engine = await get_arbitrage_engine()
    result = await engine.get_detail(
        type_id=type_info.type_id,
        buy_region_id=buy_region_config["region_id"],
        sell_region_id=sell_region_config["region_id"],
    )

    if not result:
        return {
            "error": {
                "code": "NO_OPPORTUNITY",
                "message": f"No profitable opportunity found for {type_info.type_name} "
                f"from {buy_region_config['region_name']} to {sell_region_config['region_name']}",
            }
        }

    # Try to add route info
    result = await _add_detail_route_info(
        result,
        buy_region_config,
        sell_region_config,
    )

    return result.model_dump()


# =============================================================================
# MCP Tool Registration
# =============================================================================


def register_arbitrage_tools(server: FastMCP) -> None:
    """Register arbitrage tools with MCP server."""

    @server.tool()
    async def market_arbitrage_scan(
        min_profit_pct: float = 5.0,
        min_volume: int = 10,
        max_results: int = 20,
        buy_from: list[str] | None = None,
        sell_to: list[str] | None = None,
        include_lowsec: bool = False,
        allow_stale: bool = False,
        force_refresh: bool = False,
        sort_by: str = "margin",
        trade_mode: str = "immediate",
        broker_fee_pct: float = 0.03,
        sales_tax_pct: float = 0.036,
        include_history: bool = False,
        cargo_capacity_m3: float | None = None,
        scopes: list[str] | None = None,
        scope_owner_id: int | None = None,
        include_custom_scopes: bool = False,
    ) -> dict:
        """
        Scan for arbitrage opportunities across trade hubs.

        Finds items where buying in one region and selling in another
        yields profit after accounting for fees based on trade execution mode.

        All profit calculations use NET profit (after fees based on trade_mode).
        Opportunities with net_profit_per_unit <= 0 are automatically filtered.

        Args:
            min_profit_pct: Minimum gross profit percentage to include (default 5.0)
            min_volume: Minimum available volume (default 10)
            max_results: Maximum opportunities to return (default 20)
            buy_from: Trade hubs to buy FROM (source regions). Names like "jita", "dodixie".
                     If not specified, scans all 5 trade hubs.
                     Example: ["dodixie"] to only buy from Dodixie.
            sell_to: Trade hubs to sell TO (destination regions). Names like "amarr", "hek".
                    If not specified, scans all 5 trade hubs.
                    Example: ["hek"] to only sell in Hek.
                    Combine with buy_from to find specific routes:
                    buy_from=["dodixie"], sell_to=["hek"] finds Dodixie → Hek opportunities.
            include_lowsec: Include lowsec route warnings (default False)
            allow_stale: Allow stale data (>30 min old) in results (default False)
            force_refresh: Force data refresh before scanning (default False)
            sort_by: Ranking method (default "margin"):
                - "margin": Net profit percentage (uses net_margin_pct)
                - "profit_density": Net ISK profit per m³ of used cargo
                - "hauling_score": Best ISK per trip (requires cargo_capacity_m3)
            trade_mode: Trade execution mode affecting fee calculation (default "immediate"):
                - "immediate": Take sell orders → Take buy orders. Fees: sales tax only.
                  Best for haulers wanting fast turnaround.
                - "hybrid": Take sell orders → Place sell orders. Fees: broker + sales tax on sell.
                  Better price but requires waiting for order to fill.
                - "station_trading": Place buy/sell orders. Fees: broker on both + sales tax.
                  Not typical for hauling (waiting on both sides).
            broker_fee_pct: Broker fee rate (default 0.03 = 3%). Only applies in
                           hybrid/station_trading modes. Adjust based on standings/skills.
            sales_tax_pct: Sales tax rate (default 0.036 = 3.6% for Accounting IV).
                          Accounting V = 3.6%, IV = 4.0%, III = 4.4%.
            include_history: Fetch market history for daily volume estimation (slower).
                           Enables the daily_volume and daily_volume_source fields.
            cargo_capacity_m3: Ship cargo capacity in m³. When provided, calculates
                              hauling_score, safe_quantity, expected_profit, fill_ratio,
                              and limiting factors. Required for sort_by="hauling_score".
            scopes: List of ad-hoc scope names to include. Only used when
                   include_custom_scopes=True. Scopes must exist and have fresh data.
            scope_owner_id: Character ID for scope ownership resolution. Character
                           scopes with this owner take precedence over global scopes.
            include_custom_scopes: If True, include ad-hoc scope data in arbitrage scan.
                                  Default behavior (False) uses only trade hub data.

        Returns:
            ArbitrageScanResult with opportunities and metadata

        Examples:
            market_arbitrage_scan()
            market_arbitrage_scan(buy_from=["dodixie"], sell_to=["hek"])  # Dodixie → Hek only
            market_arbitrage_scan(buy_from=["jita"])  # Buy from Jita, sell anywhere
            market_arbitrage_scan(sell_to=["amarr", "jita"])  # Sell to Amarr or Jita
            market_arbitrage_scan(min_profit_pct=10, force_refresh=True)
            market_arbitrage_scan(trade_mode="hybrid")  # Place sell orders for better prices
            market_arbitrage_scan(sort_by="profit_density")
            market_arbitrage_scan(include_history=True)
            market_arbitrage_scan(cargo_capacity_m3=60000, sort_by="hauling_score", include_history=True)
            # Include ad-hoc scopes
            market_arbitrage_scan(include_custom_scopes=True, scopes=["Everyshore Minerals"])
        """
        return await _arbitrage_scan_impl(
            min_profit_pct=min_profit_pct,
            min_volume=min_volume,
            max_results=max_results,
            buy_from=buy_from,
            sell_to=sell_to,
            include_lowsec=include_lowsec,
            allow_stale=allow_stale,
            force_refresh=force_refresh,
            sort_by=sort_by,
            trade_mode=trade_mode,
            broker_fee_pct=broker_fee_pct,
            sales_tax_pct=sales_tax_pct,
            include_history=include_history,
            cargo_capacity_m3=cargo_capacity_m3,
            include_custom_scopes=include_custom_scopes,
            scopes=scopes,
            scope_owner_id=scope_owner_id,
        )

    @server.tool()
    async def market_arbitrage_detail(
        type_name: str,
        buy_region: str,
        sell_region: str,
    ) -> dict:
        """
        Get detailed analysis of a specific arbitrage opportunity.

        Provides fee breakdown, execution info, and route details
        for a specific item trade between two regions.

        Args:
            type_name: Item name to analyze
            buy_region: Region to buy from (trade hub name or region name)
            sell_region: Region to sell to (trade hub name or region name)

        Returns:
            ArbitrageDetailResult with detailed analysis

        Examples:
            market_arbitrage_detail("Caldari Navy Hookbill", "Jita", "Amarr")
            market_arbitrage_detail("PLEX", "dodixie", "rens")
        """
        return await _arbitrage_detail_impl(type_name, buy_region, sell_region)


async def _add_route_info(result, include_lowsec: bool):
    """
    Add route information to scan results.

    Uses MCP universe_route tool with timeout to prevent blocking.
    """
    from aria_esi.models.market import ArbitrageScanResult

    # Build system name lookup for route calculation
    hub_system_names = {
        10000002: "Jita",
        10000043: "Amarr",
        10000032: "Dodixie",
        10000030: "Rens",
        10000042: "Hek",
    }

    updated_opportunities = []

    for opp in result.opportunities:
        buy_system = hub_system_names.get(opp.buy_region_id)
        sell_system = hub_system_names.get(opp.sell_region_id)

        if buy_system and sell_system:
            try:
                route_result = await asyncio.wait_for(
                    _get_route(buy_system, sell_system),
                    timeout=ROUTE_TIMEOUT_SECONDS,
                )

                if route_result:
                    jumps, is_safe = route_result
                    opp = opp.model_copy(
                        update={
                            "route_jumps": jumps,
                            "route_safe": is_safe,
                        }
                    )

            except asyncio.TimeoutError:
                logger.debug(
                    "Route calculation timed out for %s -> %s",
                    buy_system,
                    sell_system,
                )
            except Exception as e:
                logger.debug("Route calculation failed: %s", e)

        # Filter out lowsec routes if not included
        if not include_lowsec and not opp.route_safe:
            continue

        updated_opportunities.append(opp)

    return ArbitrageScanResult(
        opportunities=updated_opportunities,
        total_found=result.total_found,  # Preserve original count before filtering
        regions_scanned=result.regions_scanned,
        scan_timestamp=result.scan_timestamp,
        data_freshness=result.data_freshness,
        stale_warning=result.stale_warning,
        refresh_performed=result.refresh_performed,
        warnings=list(result.warnings),
    )


async def _add_detail_route_info(result, buy_config: TradeHubConfig, sell_config: TradeHubConfig):
    """Add route information to detail result."""
    from aria_esi.models.market import ArbitrageDetailResult

    hub_system_names = {
        10000002: "Jita",
        10000043: "Amarr",
        10000032: "Dodixie",
        10000030: "Rens",
        10000042: "Hek",
    }

    buy_system = hub_system_names.get(buy_config["region_id"])
    sell_system = hub_system_names.get(sell_config["region_id"])

    if not buy_system or not sell_system:
        return result

    try:
        route_result = await asyncio.wait_for(
            _get_route_with_systems(buy_system, sell_system),
            timeout=ROUTE_TIMEOUT_SECONDS * 2,  # Double timeout for detail
        )

        if route_result:
            jumps, is_safe, systems = route_result

            # Update opportunity with route info
            updated_opp = result.opportunity.model_copy(
                update={
                    "route_jumps": jumps,
                    "route_safe": is_safe,
                }
            )

            return ArbitrageDetailResult(
                opportunity=updated_opp,
                execution=result.execution,
                buy_orders=result.buy_orders,
                sell_orders=result.sell_orders,
                route_systems=systems,
                warnings=list(result.warnings),
            )

    except asyncio.TimeoutError:
        logger.debug("Route calculation timed out for detail")
    except Exception as e:
        logger.debug("Route calculation failed for detail: %s", e)

    return result


async def _get_route(origin: str, destination: str) -> tuple[int, bool] | None:
    """
    Get route info using universe router asynchronously.

    Uses run_in_executor to avoid blocking the event loop since
    the router is synchronous.

    Returns:
        Tuple of (jumps, is_safe) or None if unavailable
    """
    loop = asyncio.get_running_loop()

    def _sync_route() -> tuple[int, bool] | None:
        try:
            from aria_esi.universe.router import route_systems

            result = route_systems(origin, destination, mode="safe")
            if result:
                jumps = len(result.systems) - 1
                is_safe = all(s.security >= 0.45 for s in result.systems)
                return jumps, is_safe
        except ImportError:
            pass
        except Exception as e:
            logger.debug("Route calculation failed: %s", e)
        return None

    try:
        return await loop.run_in_executor(None, _sync_route)
    except Exception as e:
        logger.debug("Route executor failed: %s", e)
        return None


async def _get_route_with_systems(
    origin: str,
    destination: str,
) -> tuple[int, bool, list[str]] | None:
    """
    Get route info with system names asynchronously.

    Uses run_in_executor to avoid blocking the event loop since
    the router is synchronous.

    Returns:
        Tuple of (jumps, is_safe, system_names) or None if unavailable
    """
    loop = asyncio.get_running_loop()

    def _sync_route() -> tuple[int, bool, list[str]] | None:
        try:
            from aria_esi.universe.router import route_systems

            result = route_systems(origin, destination, mode="safe")
            if result:
                jumps = len(result.systems) - 1
                is_safe = all(s.security >= 0.45 for s in result.systems)
                systems = [s.name for s in result.systems]
                return jumps, is_safe, systems
        except ImportError:
            pass
        except Exception as e:
            logger.debug("Route calculation failed: %s", e)
        return None

    try:
        return await loop.run_in_executor(None, _sync_route)
    except Exception as e:
        logger.debug("Route executor failed: %s", e)
        return None


def _resolve_region(name: str) -> TradeHubConfig | None:
    """Resolve region name to configuration."""
    name_lower = name.lower().strip()

    # Direct trade hub match
    if name_lower in TRADE_HUBS:
        return TRADE_HUBS[name_lower]

    # Partial match
    for hub_name, config in TRADE_HUBS.items():
        if hub_name.startswith(name_lower):
            return config

    # Region name match
    for config in TRADE_HUBS.values():
        if config["region_name"].lower() == name_lower:
            return config

    return None
