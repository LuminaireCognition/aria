"""
Tool Registration Hub for SDE MCP Tools.

Coordinates registration of all SDE-related MCP tools
with the aria-universe server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from aria_esi.universe.graph import UniverseGraph


def register_sde_tools(server: FastMCP, universe: UniverseGraph | None = None) -> None:
    """
    Register all SDE tools with MCP server.

    Args:
        server: MCP Server instance
        universe: Loaded UniverseGraph (not used by SDE tools, but kept for consistency)
    """
    from .tools_activities import register_activity_tools
    from .tools_agents import register_agent_tools
    from .tools_blueprint import register_blueprint_tools
    from .tools_corporation import register_corporation_tools
    from .tools_easy80 import register_easy80_tools
    from .tools_item import register_item_tools
    from .tools_search import register_search_tools
    from .tools_skills import register_skill_tools

    # Register tool modules
    register_item_tools(server)
    register_blueprint_tools(server)
    register_search_tools(server)
    register_corporation_tools(server)
    register_skill_tools(server)
    register_easy80_tools(server)
    register_activity_tools(server)
    register_agent_tools(server)
