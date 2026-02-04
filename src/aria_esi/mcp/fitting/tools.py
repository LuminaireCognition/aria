"""
Tool Registration Hub for Fitting MCP Tools.

Coordinates registration of all fitting-related MCP tools
with the aria-universe server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from aria_esi.universe.graph import UniverseGraph


def register_fitting_tools(server: FastMCP, universe: UniverseGraph | None = None) -> None:
    """
    Register all fitting tools with MCP server.

    Args:
        server: MCP Server instance
        universe: Loaded UniverseGraph (not used by fitting tools, but kept for consistency)
    """
    from .tools_stats import register_stats_tools
    from .tools_status import register_status_tools

    # Register tool modules
    register_stats_tools(server)
    register_status_tools(server)
