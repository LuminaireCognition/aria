"""
Centralized context policy limits for MCP tool outputs.

This module defines domain-specific output limits using frozen dataclasses.
All dispatchers and tool modules should import limits from here rather than
defining them inline, ensuring consistent context management across ARIA.

Usage:
    from aria_esi.mcp.context_policy import UNIVERSE, MARKET, SDE, SKILLS

    # Use in validation
    if limit > UNIVERSE.SEARCH_MAX_LIMIT:
        raise InvalidParameterError("limit", limit, f"Max is {UNIVERSE.SEARCH_MAX_LIMIT}")

    # Use in wrap_output
    result = wrap_output(data, "systems", max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UniverseLimits:
    """
    Limits for universe navigation tools.

    Input limits control what users can request.
    Output limits control truncation for context management.
    """

    # Search tool limits
    SEARCH_MAX_LIMIT: int = 100  # Max systems user can request
    SEARCH_MAX_JUMPS: int = 50  # Max search radius

    # Borders tool limits
    BORDERS_MAX_LIMIT: int = 50  # Max border systems to return
    BORDERS_MAX_JUMPS: int = 30  # Max search radius for borders

    # Nearest tool limits
    NEAREST_MAX_LIMIT: int = 50  # Max nearest systems to return
    NEAREST_MAX_JUMPS: int = 50  # Max search radius for nearest

    # Waypoints tool limits
    WAYPOINTS_MIN_COUNT: int = 2  # Minimum waypoints for optimization
    WAYPOINTS_MAX_COUNT: int = 50  # Maximum waypoints for optimization

    # Loop tool limits
    LOOP_MIN_TARGET_JUMPS: int = 10  # Minimum loop size
    LOOP_MAX_TARGET_JUMPS: int = 100  # Maximum loop size
    LOOP_MIN_BORDERS: int = 2  # Minimum borders for loop
    LOOP_MAX_BORDERS: int = 10  # User-configurable max borders
    LOOP_MAX_BORDERS_CAP: int = 15  # Absolute max for internal calculations
    LOOP_SEARCH_RADIUS_DIVISOR: int = 3  # target_jumps / divisor = search radius

    # Hotspots tool limits
    HOTSPOTS_MAX_JUMPS: int = 30  # Max search radius for hotspots
    HOTSPOTS_MAX_LIMIT: int = 50  # Max hotspots to return

    # Output limits for wrap_output
    OUTPUT_MAX_ROUTE: int = 100  # Max route systems in output
    OUTPUT_MAX_SYSTEMS: int = 50  # Max systems in search/borders/nearest
    OUTPUT_MAX_HOTSPOTS: int = 50  # Max hotspots in output
    OUTPUT_MAX_CHOKEPOINTS: int = 50  # Max chokepoints in gatecamp_risk
    OUTPUT_MAX_FW_SYSTEMS: int = 50  # Max FW systems per category

    # Route summarization thresholds
    ROUTE_SUMMARIZE_THRESHOLD: int = 20  # Routes longer than this get summarized
    ROUTE_SHOW_HEAD: int = 5  # Systems to show at start
    ROUTE_SHOW_TAIL: int = 5  # Systems to show at end


@dataclass(frozen=True)
class MarketLimits:
    """
    Limits for market tools.

    Controls order book depth, arbitrage results, and proximity searches.
    """

    # Orders tool limits
    ORDERS_MAX_LIMIT: int = 50  # Max orders per side (buy/sell)
    ORDERS_DEFAULT_LIMIT: int = 10  # Default orders per side

    # Nearby tool limits
    NEARBY_MAX_JUMPS: int = 50  # Max search radius
    NEARBY_MAX_REGIONS: int = 10  # Max regions to search
    NEARBY_MAX_LIMIT: int = 50  # Max sources to return
    NEARBY_DEFAULT_LIMIT: int = 10  # Default sources to return

    # Arbitrage tool limits
    ARBITRAGE_MAX_RESULTS: int = 50  # Max arbitrage opportunities
    ARBITRAGE_DEFAULT_RESULTS: int = 20  # Default arbitrage results

    # NPC sources limits
    NPC_MAX_LIMIT: int = 50  # Max NPC sources to return
    NPC_DEFAULT_LIMIT: int = 10  # Default NPC sources

    # History limits
    HISTORY_MAX_DAYS: int = 365  # Max days of history
    HISTORY_DEFAULT_DAYS: int = 30  # Default days of history

    # Output limits for wrap_output
    OUTPUT_MAX_ITEMS: int = 50  # Max items in prices/spread
    OUTPUT_MAX_ORDERS: int = 20  # Max orders per side in output
    OUTPUT_MAX_HISTORY: int = 30  # Max history data points
    OUTPUT_MAX_SOURCES: int = 50  # Max sources in find_nearby
    OUTPUT_MAX_ARBITRAGE: int = 20  # Max arbitrage opportunities


@dataclass(frozen=True)
class SDELimits:
    """
    Limits for SDE (Static Data Export) tools.

    Controls search results, agent lookups, and skill trees.
    """

    # Search tool limits
    SEARCH_MAX_LIMIT: int = 50  # Max search results
    SEARCH_DEFAULT_LIMIT: int = 10  # Default search results

    # Agent search limits
    AGENTS_MAX_LIMIT: int = 100  # Max agents to return
    AGENTS_DEFAULT_LIMIT: int = 20  # Default agents to return

    # Skill requirements limits
    SKILLS_MAX_TREE_DEPTH: int = 30  # Max skills in prerequisite tree

    # Output limits for wrap_output
    OUTPUT_MAX_SEARCH_ITEMS: int = 20  # Max items in search output
    OUTPUT_MAX_AGENTS: int = 30  # Max agents in output
    OUTPUT_MAX_SKILL_TREE: int = 30  # Max skills in tree output


@dataclass(frozen=True)
class SkillsLimits:
    """
    Limits for skill planning tools.

    Controls skill plan sizes and training time calculations.
    """

    # Training time limits
    TRAINING_MAX_SKILLS: int = 50  # Max skills per calculation

    # Easy 80 plan limits
    EASY80_MAX_SKILLS: int = 30  # Max skills in Easy 80 plan

    # Activity plan limits
    ACTIVITY_MAX_SKILLS: int = 50  # Max skills in activity plan

    # Output limits for wrap_output
    OUTPUT_MAX_SKILLS: int = 30  # Max skills in output
    OUTPUT_MAX_ACTIVITIES: int = 50  # Max activities in list


@dataclass(frozen=True)
class FittingLimits:
    """
    Limits for fitting calculation tools.

    Controls EFT parsing and stat output sizes.
    """

    # Input limits
    MAX_EFT_LENGTH: int = 10000  # Max EFT string length
    MAX_MODULES: int = 100  # Max modules in a fit

    # Output limits
    OUTPUT_MAX_WARNINGS: int = 10  # Max warnings in output


# Singleton instances - import these directly
UNIVERSE = UniverseLimits()
MARKET = MarketLimits()
SDE = SDELimits()
SKILLS = SkillsLimits()
FITTING = FittingLimits()


# Global context limits (for total output management)
@dataclass(frozen=True)
class GlobalLimits:
    """
    Global context limits across all tool outputs.
    """

    # Per-tool output size limits (bytes)
    MAX_OUTPUT_SIZE_BYTES: int = 10240  # 10 KB soft limit per tool
    MAX_TOTAL_OUTPUT_BYTES: int = 51200  # 50 KB soft limit per turn
    HARD_LIMIT_BYTES: int = 102400  # 100 KB hard limit

    # Error message truncation
    MAX_ERROR_MESSAGE_LENGTH: int = 500


GLOBAL = GlobalLimits()
