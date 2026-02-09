"""
ARIA Services.

Business logic services for market operations, arbitrage detection,
real-time intelligence, navigation, loop planning, and other higher-level operations.
"""

from __future__ import annotations

__all__ = [
    "MarketRefreshService",
    "ArbitrageEngine",
    "ArbitrageCalculator",
    # Freshness utilities
    "get_freshness",
    "get_scope_freshness",
    "get_confidence",
    "get_combined_freshness",
    "get_effective_volume",
    # Fee calculation
    "calculate_net_profit",
    # RedisQ real-time intel
    "redisq",
    # Navigation service
    "NavigationService",
    "navigation",
    # Loop planning service
    "LoopPlanningService",
    "loop_planning",
]


def __getattr__(name: str):
    """Lazy import services to avoid circular imports."""
    if name == "MarketRefreshService":
        from .market_refresh import MarketRefreshService

        return MarketRefreshService
    if name == "ArbitrageEngine":
        from .arbitrage_engine import ArbitrageEngine

        return ArbitrageEngine
    if name == "ArbitrageCalculator":
        from .arbitrage_fees import ArbitrageCalculator

        return ArbitrageCalculator
    if name in (
        "get_freshness",
        "get_scope_freshness",
        "get_confidence",
        "get_combined_freshness",
        "get_effective_volume",
    ):
        from . import arbitrage_freshness

        return getattr(arbitrage_freshness, name)
    if name == "calculate_net_profit":
        from .arbitrage_fees import calculate_net_profit

        return calculate_net_profit
    if name == "redisq":
        from . import redisq

        return redisq
    if name == "NavigationService":
        from .navigation import NavigationService

        return NavigationService
    if name == "navigation":
        from . import navigation

        return navigation
    if name == "LoopPlanningService":
        from .loop_planning import LoopPlanningService

        return LoopPlanningService
    if name == "loop_planning":
        from . import loop_planning

        return loop_planning
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
