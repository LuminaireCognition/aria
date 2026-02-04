"""
Market History MCP Tools.

Provides market_history tool for historical price trend analysis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.database import get_market_database
from aria_esi.models.market import (
    TRADE_HUBS,
    DailyPrice,
    MarketHistoryResult,
    resolve_trade_hub,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_market.tools_history")

# =============================================================================
# Trend Analysis
# =============================================================================


def analyze_price_trend(
    history: list[DailyPrice],
) -> Literal["rising", "falling", "stable", "volatile"]:
    """
    Analyze price trend from historical data.

    Uses simple linear regression slope and volatility to classify trend.
    """
    if len(history) < 3:
        return "stable"

    prices = [h.average for h in history]
    n = len(prices)

    # Calculate simple moving averages for first and last thirds
    third = max(1, n // 3)
    early_avg = sum(prices[:third]) / third
    late_avg = sum(prices[-third:]) / third

    # Calculate volatility (coefficient of variation)
    mean_price = sum(prices) / n
    if mean_price == 0:
        return "stable"

    variance = sum((p - mean_price) ** 2 for p in prices) / n
    stddev = variance**0.5
    cv = stddev / mean_price  # Coefficient of variation

    # High volatility threshold
    if cv > 0.15:  # >15% CV indicates high volatility
        return "volatile"

    # Trend detection based on price change
    change_percent = (late_avg - early_avg) / early_avg if early_avg > 0 else 0

    if change_percent > 0.05:  # >5% increase
        return "rising"
    elif change_percent < -0.05:  # >5% decrease
        return "falling"

    return "stable"


def analyze_volume_trend(
    history: list[DailyPrice],
) -> Literal["increasing", "decreasing", "stable"]:
    """
    Analyze volume trend from historical data.
    """
    if len(history) < 3:
        return "stable"

    volumes = [h.volume for h in history]
    n = len(volumes)

    # Compare first and last thirds
    third = max(1, n // 3)
    early_avg = sum(volumes[:third]) / third
    late_avg = sum(volumes[-third:]) / third

    if early_avg == 0:
        return "stable"

    change_percent = (late_avg - early_avg) / early_avg

    if change_percent > 0.2:  # >20% increase
        return "increasing"
    elif change_percent < -0.2:  # >20% decrease
        return "decreasing"

    return "stable"


# =============================================================================
# Tool Registration
# =============================================================================


async def _get_history_impl(
    item: str,
    region: str = "jita",
    days: int = 30,
) -> dict:
    """
    Implementation for history action.

    Get historical price data for an item.
    """
    # Resolve trade hub
    hub = resolve_trade_hub(region)
    if not hub:
        hub = TRADE_HUBS["jita"]

    # Clamp days
    days = max(1, min(365, days))

    # Resolve item name
    db = get_market_database()
    type_info = db.resolve_type_name(item)

    if not type_info:
        suggestions = db.find_type_suggestions(item)
        return {
            "error": {
                "code": "TYPE_NOT_FOUND",
                "message": f"Unknown item: {item}",
                "data": {"suggestions": suggestions},
            }
        }

    type_id = type_info.type_id
    type_name = type_info.type_name
    region_id = hub["region_id"]

    # Fetch history from ESI
    warnings: list[str] = []
    history_data: list[dict] = []

    try:
        from aria_esi.mcp.esi_client import get_async_esi_client

        client = await get_async_esi_client()

        data = await client.get(
            f"/markets/{region_id}/history/",
            params={"type_id": str(type_id)},
        )

        if isinstance(data, list):
            history_data = data

    except Exception as e:
        logger.warning("Failed to fetch market history: %s", e)
        warnings.append(f"ESI error: {e}")

    if not history_data:
        return {
            "error": {
                "code": "NO_HISTORY",
                "message": f"No market history available for {type_name} in {hub['region_name']}",
                "data": {"type_id": type_id, "region_id": region_id},
            }
        }

    # Sort by date (newest first for slicing, then reverse for output)
    history_data.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Limit to requested days
    history_data = history_data[:days]

    # Reverse to chronological order (oldest first)
    history_data.reverse()

    # Convert to model objects
    daily_prices: list[DailyPrice] = []
    for entry in history_data:
        try:
            daily_prices.append(
                DailyPrice(
                    date=entry.get("date", ""),
                    average=round(entry.get("average", 0), 2),
                    highest=round(entry.get("highest", 0), 2),
                    lowest=round(entry.get("lowest", 0), 2),
                    volume=int(entry.get("volume", 0)),
                    order_count=int(entry.get("order_count", 0)),
                )
            )
        except Exception as e:
            logger.warning("Failed to parse history entry: %s", e)
            continue

    if not daily_prices:
        return {
            "error": {
                "code": "PARSE_ERROR",
                "message": "Failed to parse market history data",
            }
        }

    # Analyze trends
    price_trend = analyze_price_trend(daily_prices)
    volume_trend = analyze_volume_trend(daily_prices)

    # Calculate averages
    avg_price = sum(d.average for d in daily_prices) / len(daily_prices)
    avg_volume = sum(d.volume for d in daily_prices) // len(daily_prices)

    result = MarketHistoryResult(
        type_id=type_id,
        type_name=type_name,
        region=hub["region_name"],
        region_id=region_id,
        history=daily_prices,
        days_requested=days,
        days_returned=len(daily_prices),
        price_trend=price_trend,
        volume_trend=volume_trend,
        avg_price=round(avg_price, 2),
        avg_volume=avg_volume,
        warnings=warnings,
    )

    return result.model_dump()


def register_history_tools(server: FastMCP) -> None:
    """Register market history tools with MCP server."""

    @server.tool()
    async def market_history(
        item: str,
        region: str = "jita",
        days: int = 30,
    ) -> dict:
        """
        Get historical price data for an item.

        Fetches daily price history from ESI including average, high, low,
        volume, and order count. Includes trend analysis.

        Args:
            item: Item name to look up (case-insensitive)
            region: Trade hub name (jita, amarr, dodixie, rens, hek)
            days: Number of days of history (default 30, max 365)

        Returns:
            MarketHistoryResult with daily prices and trend analysis

        Examples:
            market_history("Tritanium")
            market_history("PLEX", region="amarr", days=90)
            market_history("Veldspar", days=7)
        """
        return await _get_history_impl(item, region, days)
