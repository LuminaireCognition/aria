"""
MCP (Model Context Protocol) module for ARIA Universe Server.

This module provides the MCP server implementation for EVE Online
universe queries, including routing, system info, and border analysis.
"""

from aria_esi.mcp.errors import (
    InsufficientBordersError,
    InvalidParameterError,
    RouteNotFoundError,
    SystemNotFoundError,
    UniverseError,
)
from aria_esi.mcp.models import (
    BorderSearchResult,
    BorderSystem,
    DangerZone,
    LoopResult,
    MCPModel,
    NeighborInfo,
    RouteAnalysis,
    RouteResult,
    SecuritySummary,
    SystemInfo,
    SystemSearchResult,
)
from aria_esi.mcp.server import UniverseServer, main

__all__ = [
    # Server
    "UniverseServer",
    "main",
    # Errors
    "UniverseError",
    "SystemNotFoundError",
    "RouteNotFoundError",
    "InvalidParameterError",
    "InsufficientBordersError",
    # Models
    "MCPModel",
    "NeighborInfo",
    "SystemInfo",
    "SecuritySummary",
    "RouteResult",
    "BorderSystem",
    "LoopResult",
    "DangerZone",
    "RouteAnalysis",
    "SystemSearchResult",
    "BorderSearchResult",
]
