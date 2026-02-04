"""
Market Route Integration MCP Tools.

Provides market_route_value tool for cargo value and gank risk assessment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.cache import MarketCache
from aria_esi.mcp.market.clipboard import parse_clipboard_to_dict
from aria_esi.mcp.market.database import get_market_database
from aria_esi.models.market import (
    RouteValueResult,
    SystemRisk,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_market.tools_route")

# Type alias for risk levels
RiskLevel = Literal["safe", "low", "medium", "high", "extreme"]

# =============================================================================
# Gank Threshold Constants
# =============================================================================

# Base gank threshold by security status (in millions ISK)
# These represent the approximate value where ganking becomes profitable
GANK_THRESHOLDS = {
    "1.0": 1000_000_000,  # Very high - rarely worth ganking
    "0.9": 500_000_000,
    "0.8": 300_000_000,
    "0.7": 200_000_000,
    "0.6": 100_000_000,
    "0.5": 50_000_000,  # Low-sec border - ganks common
    "low": 10_000_000,  # Low-sec - any valuable cargo at risk
    "null": 1_000_000,  # Null - everything at risk
}

# Known high-risk gank systems
KNOWN_GANK_SYSTEMS = {
    "Uedama": "high",  # Famous gank pipe
    "Sivala": "high",
    "Niarja": "high",
    "Madirmilire": "medium",
    "Aufay": "medium",
    "Balle": "medium",
}


def get_gank_threshold(security: float) -> float:
    """Get gank threshold for a security status."""
    if security >= 0.95:
        return GANK_THRESHOLDS["1.0"]
    elif security >= 0.85:
        return GANK_THRESHOLDS["0.9"]
    elif security >= 0.75:
        return GANK_THRESHOLDS["0.8"]
    elif security >= 0.65:
        return GANK_THRESHOLDS["0.7"]
    elif security >= 0.55:
        return GANK_THRESHOLDS["0.6"]
    elif security >= 0.45:
        return GANK_THRESHOLDS["0.5"]
    elif security >= 0.0:
        return GANK_THRESHOLDS["low"]
    else:
        return GANK_THRESHOLDS["null"]


def classify_risk(
    cargo_value: float,
    threshold: float,
    security: float,
    system_name: str,
) -> Literal["safe", "low", "medium", "high", "extreme"]:
    """Classify risk level based on cargo value vs threshold."""
    # Check if system is a known gank hotspot
    if system_name in KNOWN_GANK_SYSTEMS:
        base_risk = KNOWN_GANK_SYSTEMS[system_name]
        # Escalate risk for high-value cargo in known gank systems
        if cargo_value > threshold * 0.5:
            if base_risk == "high":
                return "extreme"
            else:
                return "high"
        elif cargo_value > threshold * 0.2:
            return "high" if base_risk == "high" else "medium"

    # Low-sec is always at least medium risk
    if security < 0.45:
        if cargo_value > threshold:
            return "extreme"
        elif cargo_value > threshold * 0.5:
            return "high"
        return "medium"

    # High-sec risk classification
    ratio = cargo_value / threshold if threshold > 0 else 0
    if ratio > 2.0:
        return "extreme"
    elif ratio > 1.0:
        return "high"
    elif ratio > 0.5:
        return "medium"
    elif ratio > 0.1:
        return "low"
    return "safe"


def register_route_tools(server: FastMCP) -> None:
    """Register market route tools with MCP server."""

    @server.tool()
    async def market_route_value(
        items: list[dict] | str,
        route: list[str],
        price_type: str = "sell",
    ) -> dict:
        """
        Estimate cargo value and per-system gank risk along a route.

        Combines market valuation with route security analysis to
        provide hauling risk assessment.

        Args:
            items: List of {"name": str, "quantity": int} OR raw clipboard text
            route: List of system names in order (from universe_route)
            price_type: "sell" (instant buy) or "buy" (instant sell)

        Returns:
            RouteValueResult with total value and per-system risk

        Examples:
            market_route_value(
                [{"name": "PLEX", "quantity": 10}],
                ["Jita", "Perimeter", "Urlen", "Sivala", "Uedama"]
            )
        """
        # Parse clipboard if string input
        if isinstance(items, str):
            items = parse_clipboard_to_dict(items)

        if not items:
            return {
                "error": {
                    "code": "NO_ITEMS",
                    "message": "No items provided or parsed",
                }
            }

        if not route or len(route) < 2:
            return {
                "error": {
                    "code": "INVALID_ROUTE",
                    "message": "Route must contain at least 2 systems",
                }
            }

        # Validate price_type
        if price_type not in ("buy", "sell"):
            price_type = "sell"

        # Resolve item names and calculate total value
        db = get_market_database()
        cache = MarketCache(region="jita", station_only=True)

        type_ids: list[int] = []
        type_names: dict[int, str] = {}
        quantities: dict[int, int] = {}

        for item in items:
            name = item.get("name", "")
            qty = item.get("quantity", 1)

            type_info = db.resolve_type_name(name)
            if type_info:
                type_id = type_info.type_id
                type_ids.append(type_id)
                type_names[type_id] = type_info.type_name
                quantities[type_id] = quantities.get(type_id, 0) + qty

        if not type_ids:
            return {
                "error": {
                    "code": "NO_ITEMS_RESOLVED",
                    "message": "Could not resolve any item names",
                }
            }

        # Get prices
        prices = await cache.get_prices(type_ids, type_names)
        price_map = {p.type_id: p for p in prices}

        # Calculate total cargo value
        total_value = 0.0
        item_count = 0

        for type_id, qty in quantities.items():
            price_data = price_map.get(type_id)
            if price_data:
                if price_type == "sell":
                    unit_price = price_data.sell.min_price
                else:
                    unit_price = price_data.buy.max_price

                if unit_price:
                    total_value += unit_price * qty
                    item_count += qty

        # Get system information from universe tools
        # We need to resolve system names to get security status
        system_risks: list[SystemRisk] = []
        highest_risk_system = None
        highest_risk_level: RiskLevel = "safe"
        warnings: list[str] = []

        # Try to get system info from universe graph
        try:
            from aria_esi.mcp.tools import get_universe

            universe = get_universe()

            for system_name in route:
                idx = universe.resolve_name(system_name)
                if idx is not None:
                    security = universe.security[idx]
                    system_id = universe.system_ids[idx]
                    canonical_name = universe.idx_to_name[idx]

                    threshold = get_gank_threshold(security)
                    risk_level = classify_risk(total_value, threshold, security, canonical_name)

                    # Get recent kills if activity cache is available
                    recent_kills = None
                    try:
                        from aria_esi.mcp.activity import get_activity_cache

                        activity_cache = get_activity_cache()
                        # Note: This is sync call, but we're in async context
                        # Activity cache is pre-loaded, so this should be fast
                        kills_data = activity_cache._kills_data.get(system_id)
                        if kills_data:
                            recent_kills = kills_data.ship_kills + kills_data.pod_kills
                    except Exception:
                        pass

                    system_risks.append(
                        SystemRisk(
                            system=canonical_name,
                            system_id=system_id,
                            security=round(security, 2),
                            cargo_value=round(total_value, 2),
                            gank_threshold=round(threshold, 2),
                            risk_level=risk_level,
                            recent_kills=recent_kills,
                        )
                    )

                    # Track highest risk
                    risk_order = ["safe", "low", "medium", "high", "extreme"]
                    if risk_order.index(risk_level) > risk_order.index(highest_risk_level):
                        highest_risk_level = risk_level
                        highest_risk_system = canonical_name

                else:
                    warnings.append(f"Unknown system: {system_name}")

        except Exception as e:
            logger.warning("Failed to get universe data: %s", e)
            warnings.append("Could not resolve route systems - universe graph unavailable")

        # Generate recommendation
        if highest_risk_level == "extreme":
            recommendation = (
                "DANGER: Cargo value exceeds gank threshold. Use scout, web alt, or split cargo."
            )
        elif highest_risk_level == "high":
            recommendation = (
                "HIGH RISK: Consider using a tanky hauler, webbing alt, or splitting cargo."
            )
        elif highest_risk_level == "medium":
            recommendation = "CAUTION: Stay aligned, watch local, consider off-peak travel."
        elif highest_risk_level == "low":
            recommendation = "LOW RISK: Standard precautions advised. Watch for war targets."
        else:
            recommendation = "SAFE: Cargo value below gank threshold for this route."

        result = RouteValueResult(
            total_value=round(total_value, 2),
            item_count=item_count,
            route_systems=system_risks,
            highest_risk_system=highest_risk_system,
            overall_risk=highest_risk_level,
            recommendation=recommendation,
            warnings=warnings,
        )

        return result.model_dump()
