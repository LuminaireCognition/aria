"""
MCP Protocol Integration Tests

Tests the full MCP server lifecycle and tool execution through the protocol.

STP-012: Testing & Deployment
"""

import pytest


@pytest.mark.integration
class TestServerLifecycle:
    """Test MCP server initialization and lifecycle."""

    def test_server_initialization(self, sample_graph_path):
        """Server initializes correctly with graph path."""
        from aria_esi.mcp.server import UniverseServer

        server = UniverseServer(graph_path=sample_graph_path)
        assert server.graph_path == sample_graph_path
        assert server.universe is None
        assert server._tools_registered is False

    def test_graph_loading(self, sample_graph_path):
        """Graph loads correctly from pickle."""
        from aria_esi.mcp.server import UniverseServer

        server = UniverseServer(graph_path=sample_graph_path)
        server.load_graph(skip_integrity_check=True)

        assert server.universe is not None
        assert server.universe.system_count > 0

    def test_tool_registration(self, sample_graph_path):
        """Tools register correctly after graph load."""
        from aria_esi.mcp.server import UniverseServer

        server = UniverseServer(graph_path=sample_graph_path)
        server.load_graph(skip_integrity_check=True)
        server.register_tools()

        assert server._tools_registered is True

    def test_tool_registration_requires_graph(self, sample_graph_path):
        """Tool registration fails without loaded graph."""
        from aria_esi.mcp.server import UniverseServer

        server = UniverseServer(graph_path=sample_graph_path)

        with pytest.raises(RuntimeError, match="Graph must be loaded"):
            server.register_tools()


@pytest.mark.integration
class TestRouteToolIntegration:
    """Integration tests for universe_route tool."""

    @pytest.mark.asyncio
    async def test_route_shortest(self, integration_server, sample_graph):
        """Route tool returns valid response for shortest mode."""
        # Get the tool function from the server
        from aria_esi.mcp.tools import get_universe
        from aria_esi.mcp.tools_route import _calculate_route

        universe = get_universe()

        # Calculate route directly using internal functions
        origin_idx = universe.resolve_name("Jita")
        dest_idx = universe.resolve_name("Perimeter")

        assert origin_idx is not None
        assert dest_idx is not None

        path = _calculate_route(universe, origin_idx, dest_idx, "shortest")

        assert len(path) > 0
        assert path[0] == origin_idx
        assert path[-1] == dest_idx

    @pytest.mark.asyncio
    async def test_route_result_structure(self, integration_server, sample_graph):
        """Route result has correct structure."""
        from aria_esi.mcp.tools import get_universe
        from aria_esi.mcp.tools_route import _build_route_result, _calculate_route

        universe = get_universe()

        origin_idx = universe.resolve_name("Jita")
        dest_idx = universe.resolve_name("Sivala")

        path = _calculate_route(universe, origin_idx, dest_idx, "shortest")
        result = _build_route_result(universe, path, "Jita", "Sivala", "shortest")

        assert result.origin == "Jita"
        assert result.destination == "Sivala"
        assert result.mode == "shortest"
        assert result.jumps == len(path) - 1
        assert len(result.systems) == len(path)
        assert result.security_summary is not None


@pytest.mark.integration
class TestSystemsToolIntegration:
    """Integration tests for universe_systems tool."""

    def test_system_lookup(self, integration_server):
        """System lookup returns correct information."""
        from aria_esi.mcp.tools import get_universe
        from aria_esi.mcp.utils import build_system_info

        universe = get_universe()

        jita_idx = universe.resolve_name("Jita")
        assert jita_idx is not None

        info = build_system_info(universe, jita_idx)

        assert info.name == "Jita"
        assert info.security > 0.9
        assert info.security_class == "HIGH"
        assert info.region == "The Forge"

    def test_border_system_detection(self, integration_server):
        """Border systems correctly identified."""
        from aria_esi.mcp.tools import get_universe
        from aria_esi.mcp.utils import build_system_info

        universe = get_universe()

        sivala_idx = universe.resolve_name("Sivala")
        assert sivala_idx is not None

        info = build_system_info(universe, sivala_idx)

        # Sivala should be a border system (adjacent to Aufay which is lowsec)
        assert info.is_border is True
        assert len(info.adjacent_lowsec) > 0


@pytest.mark.integration
class TestBordersToolIntegration:
    """Integration tests for universe_borders tool."""

    def test_border_search_from_jita(self, integration_server):
        """Border search finds nearby border systems."""
        from aria_esi.mcp.tools import get_universe
        from aria_esi.mcp.tools_borders import _find_border_systems

        universe = get_universe()

        jita_idx = universe.resolve_name("Jita")
        assert jita_idx is not None

        borders = _find_border_systems(universe, jita_idx, limit=5, max_jumps=10)

        # Should find Sivala which is a border system
        border_names = [b.name for b in borders]
        assert "Sivala" in border_names


@pytest.mark.integration
class TestSearchToolIntegration:
    """Integration tests for universe_search tool."""

    def test_search_lowsec(self, integration_server):
        """Search finds low-sec systems correctly."""
        from aria_esi.mcp.tools import get_universe
        from aria_esi.mcp.tools_search import _search_systems

        universe = get_universe()

        results = _search_systems(
            universe,
            origin_idx=None,
            max_jumps=None,
            security_min=0.1,
            security_max=0.4,
            region_id=None,
            is_border=None,
            limit=20,
        )

        # Should find Aufay (0.35) and Ala (0.20)
        names = [r.name for r in results]
        assert "Aufay" in names
        assert "Ala" in names


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling through the protocol."""

    def test_unknown_system_error(self, integration_server):
        """Unknown system raises appropriate error."""
        from aria_esi.mcp.errors import SystemNotFoundError
        from aria_esi.mcp.tools import resolve_system_name

        with pytest.raises(SystemNotFoundError) as exc_info:
            resolve_system_name("NonexistentSystem123")

        assert "NonexistentSystem123" in str(exc_info.value)

    def test_system_not_found_suggestions(self, integration_server):
        """SystemNotFoundError includes suggestions when auto_correct disabled."""
        from aria_esi.mcp.errors import SystemNotFoundError
        from aria_esi.mcp.tools import resolve_system_name

        # With auto_correct=False, partial match raises error with suggestions
        with pytest.raises(SystemNotFoundError) as exc_info:
            resolve_system_name("Jit", auto_correct=False)

        # Should suggest "Jita"
        assert "Jita" in exc_info.value.suggestions

    def test_system_auto_correct_single_match(self, integration_server):
        """Auto-correct resolves single-match typos without raising."""
        from aria_esi.mcp.tools import resolve_system_name

        # "Jit" should auto-correct to "Jita" with default auto_correct=True
        result = resolve_system_name("Jit")
        assert result.canonical_name == "Jita"
        assert result.corrected_from == "Jit"
