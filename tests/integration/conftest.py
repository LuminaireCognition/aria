"""
Integration Test Fixtures

Provides fixtures for full MCP protocol integration tests.

STP-012: Testing & Deployment
"""

import pytest


@pytest.fixture
def integration_server(sample_graph_path):
    """
    Create fully initialized server for integration tests.

    Uses sample graph for fast, reproducible tests.
    Skips integrity check since test graphs have different checksums.
    """
    from aria_esi.mcp.server import UniverseServer

    server = UniverseServer(graph_path=sample_graph_path)
    server.load_graph(skip_integrity_check=True)
    server.register_tools()
    return server
