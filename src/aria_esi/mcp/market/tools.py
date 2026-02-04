"""
Tool Registration Hub for Market MCP Tools.

Coordinates registration of all market-related MCP tools
with the aria-universe server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from aria_esi.universe.graph import UniverseGraph


def register_market_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register all market tools with MCP server.

    Args:
        server: MCP Server instance
        universe: Loaded UniverseGraph (for system resolution if needed)
    """
    from .tools_analysis import register_analysis_tools
    from .tools_arbitrage import register_arbitrage_tools
    from .tools_history import register_history_tools
    from .tools_management import register_management_tools
    from .tools_nearby import register_nearby_tools
    from .tools_npc import register_npc_tools
    from .tools_orders import register_order_tools
    from .tools_prices import register_price_tools
    from .tools_route import register_route_tools
    from .tools_scope_refresh import register_scope_refresh_tools
    from .tools_valuation import register_valuation_tools

    # Register tool modules
    register_price_tools(server)
    register_order_tools(server)
    register_valuation_tools(server)
    register_analysis_tools(server)
    register_route_tools(server)
    register_history_tools(server)
    register_npc_tools(server)
    register_arbitrage_tools(server)
    register_nearby_tools(server, universe)
    register_management_tools(server)
    register_scope_refresh_tools(server)
