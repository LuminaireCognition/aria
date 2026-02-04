"""
Market MCP module for ARIA.

Provides market data tools backed by Fuzzwork API and local SQLite cache.
Integrates with aria-universe MCP server for unified tool registration.
"""

from aria_esi.mcp.market.cache import MarketCache, get_market_cache, reset_market_cache
from aria_esi.mcp.market.clients import FuzzworkClient, create_client
from aria_esi.mcp.market.database import MarketDatabase, get_market_database
from aria_esi.mcp.market.tools import register_market_tools

__all__ = [
    # Clients
    "FuzzworkClient",
    "create_client",
    # Database
    "MarketDatabase",
    "get_market_database",
    # Cache
    "MarketCache",
    "get_market_cache",
    "reset_market_cache",
    # Tools
    "register_market_tools",
]
