"""
Systems Tool Implementation for MCP Universe Server.

Provides the universe_systems tool for batch lookup of system information.
Enables efficient retrieval of detailed information for multiple systems
in a single call.

STP-006: Systems Tool (universe_systems)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import SystemInfo
from .tools import ResolvedSystem, get_universe, resolve_system_name
from .utils import build_system_info

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..universe.graph import UniverseGraph


def register_systems_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register system lookup tools with MCP server.

    Args:
        server: MCP Server instance
        universe: UniverseGraph for system lookups
    """

    @server.tool()
    async def universe_systems(systems: list[str]) -> dict:
        """
        Get detailed information for one or more systems.

        PREFER THIS TOOL over multiple individual system lookups or writing
        custom scripts to gather system data. Efficiently batches lookups.

        Args:
            systems: List of system names (case-insensitive)

        Returns:
            Dictionary containing:
            - systems: List of SystemInfo objects, preserving input order.
                      Unknown systems return null in their position.
            - found: Count of successfully resolved systems
            - not_found: Count of unresolved systems

        Example:
            universe_systems(["Jita", "Perimeter", "Unknown"])
            # Returns: {"systems": [SystemInfo, SystemInfo, null], "found": 2, "not_found": 1}
        """
        universe = get_universe()
        results: list[SystemInfo | None] = []
        corrections: dict[str, str] = {}

        for name in systems:
            # Try to resolve with auto-correction
            try:
                resolved: ResolvedSystem = resolve_system_name(name)
                results.append(build_system_info(universe, resolved.idx))
                if resolved.was_corrected and resolved.corrected_from:
                    corrections[resolved.corrected_from] = resolved.canonical_name
            except Exception:
                # If resolve_system_name raises (e.g., multiple suggestions), skip
                results.append(None)

        return {
            "systems": [s.model_dump() if s else None for s in results],
            "found": sum(1 for s in results if s is not None),
            "not_found": sum(1 for s in results if s is None),
            "corrections": corrections,
        }
