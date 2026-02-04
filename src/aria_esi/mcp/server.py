"""
MCP Server Entry Point for ARIA Universe Server.

Provides the UniverseServer class with lifecycle management and stdio transport.

STP-004: MCP Server Core
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

from ..core.config import get_settings
from ..core.logging import get_logger
from ..universe.builder import load_universe_graph

if TYPE_CHECKING:
    from ..universe.graph import UniverseGraph

# Configure module logger
logger = get_logger("aria_universe")

# Default to new safe format, with env var override
DEFAULT_GRAPH_PATH = Path(__file__).parent.parent / "data" / "universe.universe"
LEGACY_GRAPH_PATH = Path(__file__).parent.parent / "data" / "universe.pkl"


class UniverseServer:
    """
    MCP server for EVE Online universe queries.

    Provides graph loading, tool registration, and stdio transport.
    """

    def __init__(self, graph_path: Path | None = None):
        """
        Initialize server with graph path.

        Args:
            graph_path: Path to universe graph. Defaults to package data directory.
                       Supports both .universe (safe) and .pkl (legacy) formats.
                       Can be overridden with ARIA_UNIVERSE_GRAPH env var.
        """
        settings = get_settings()
        if graph_path:
            self.graph_path = graph_path
        elif settings.universe_graph:
            self.graph_path = settings.universe_graph
        elif DEFAULT_GRAPH_PATH.exists():
            self.graph_path = DEFAULT_GRAPH_PATH
        elif LEGACY_GRAPH_PATH.exists():
            self.graph_path = LEGACY_GRAPH_PATH
        else:
            self.graph_path = DEFAULT_GRAPH_PATH  # Will fail with helpful message
        self.universe: UniverseGraph | None = None
        self.server = FastMCP("aria-universe")
        self._tools_registered = False

    def load_graph(self, *, skip_integrity_check: bool = False) -> None:
        """
        Load pre-built universe graph from pickle.

        Args:
            skip_integrity_check: Skip checksum verification (for testing only)
        """
        logger.info("Loading universe graph from %s", self.graph_path)
        start = time.perf_counter()
        self.universe = load_universe_graph(
            self.graph_path, skip_integrity_check=skip_integrity_check
        )
        elapsed = time.perf_counter() - start
        logger.info(
            "Universe graph loaded: %d systems, %d stargates (%.2fms)",
            self.universe.system_count,
            self.universe.stargate_count,
            elapsed * 1000,
        )

    def register_tools(self) -> None:
        """Register all MCP tools with the server."""
        if self._tools_registered:
            return
        if self.universe is None:
            raise RuntimeError("Graph must be loaded before registering tools")

        from .tools import register_tools

        logger.debug("Registering MCP tools")
        register_tools(self.server, self.universe)
        self._tools_registered = True
        logger.info("MCP tools registered successfully")

    def warm_sde_caches(self) -> None:
        """Warm SDE query caches at startup."""
        try:
            from .sde.queries import get_sde_query_service

            service = get_sde_query_service()
            stats = service.warm_caches()

            if stats["corporations"] > 0:
                logger.info(
                    "SDE caches warmed: %d corporations, %d categories",
                    stats["corporations"],
                    stats["categories"],
                )
            # If nothing warmed, SDE probably not seeded - that's fine

        except Exception as e:
            # Don't fail server startup due to cache warming issues
            logger.debug("SDE cache warming skipped (non-fatal): %s", e)

    def run(self) -> None:
        """Start MCP server with stdio transport."""
        logger.info("Starting ARIA Universe MCP Server")
        self.load_graph()
        self.register_tools()
        self.warm_sde_caches()

        # FastMCP.run() is synchronous - it handles its own event loop via anyio
        logger.info("Server ready, starting stdio transport")
        self.server.run()


def main() -> None:
    """Entry point for MCP server."""
    settings = get_settings()
    log_level = settings.universe_log_level

    # Configure logging with timestamp and module info
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.debug("Log level set to %s", log_level)

    server = UniverseServer()
    server.run()


if __name__ == "__main__":
    main()
