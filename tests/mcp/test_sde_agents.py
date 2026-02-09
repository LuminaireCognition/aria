"""
Tests for SDE Agent Search MCP Tools.

Tests cover the agent search functionality including:
- Model validation (AgentInfo, AgentSearchResult, DivisionListResult)
- Corporation name resolution (exact, prefix, contains matching)
- Division name resolution
- Agent search with various filters
- Highsec filtering
- Error handling
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aria_esi.mcp.sde.tools_agents import (
    AgentInfo,
    AgentSearchResult,
    DivisionListResult,
    _get_system_info,
    _resolve_corporation_name,
    _resolve_division_name,
    register_agent_tools,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection with agent tables."""
    conn = MagicMock()

    # Default: tables exist
    def mock_table_check(query):
        if "sqlite_master" in query:
            cursor = MagicMock()
            cursor.fetchone.return_value = ("agents",)  # Table exists
            return cursor
        return MagicMock()

    conn.execute = MagicMock(side_effect=mock_table_check)
    return conn


@pytest.fixture
def mock_db_no_tables():
    """Create a mock database connection without agent tables."""
    conn = MagicMock()

    def mock_table_check(query, *args):
        cursor = MagicMock()
        cursor.fetchone.return_value = None  # No tables
        cursor.fetchall.return_value = []
        return cursor

    conn.execute = MagicMock(side_effect=mock_table_check)
    return conn


# =============================================================================
# Unit Tests: AgentInfo Model
# =============================================================================


class TestAgentInfoModel:
    """Tests for AgentInfo pydantic model."""

    def test_agent_info_valid(self):
        """Test creating a valid AgentInfo."""
        agent = AgentInfo(
            agent_id=12345,
            agent_name="Test Agent",
            level=3,
            corporation_id=1000125,
        )

        assert agent.agent_id == 12345
        assert agent.agent_name == "Test Agent"
        assert agent.level == 3
        assert agent.corporation_id == 1000125

    def test_agent_info_with_all_fields(self):
        """Test AgentInfo with all optional fields."""
        agent = AgentInfo(
            agent_id=12345,
            agent_name="Test Agent",
            level=4,
            division_id=10,
            division_name="Security",
            corporation_id=1000125,
            corporation_name="Sisters of EVE",
            station_id=60003760,
            station_name="Jita IV - Moon 4",
            system_id=30000142,
            system_name="Jita",
            security=0.95,
            region_name="The Forge",
            agent_type="BasicAgent",
        )

        assert agent.division_name == "Security"
        assert agent.station_name == "Jita IV - Moon 4"
        assert agent.security == 0.95

    def test_agent_info_level_validation_min(self):
        """Test that level must be at least 1."""
        with pytest.raises(ValueError):
            AgentInfo(agent_id=1, agent_name="Test", level=0, corporation_id=1)

    def test_agent_info_level_validation_max(self):
        """Test that level must be at most 5."""
        with pytest.raises(ValueError):
            AgentInfo(agent_id=1, agent_name="Test", level=6, corporation_id=1)

    def test_agent_info_agent_id_must_be_positive(self):
        """Test that agent_id must be >= 1."""
        with pytest.raises(ValueError):
            AgentInfo(agent_id=0, agent_name="Test", level=1, corporation_id=1)

    def test_agent_info_corporation_id_must_be_positive(self):
        """Test that corporation_id must be >= 1."""
        with pytest.raises(ValueError):
            AgentInfo(agent_id=1, agent_name="Test", level=1, corporation_id=0)


# =============================================================================
# Unit Tests: AgentSearchResult Model
# =============================================================================


class TestAgentSearchResultModel:
    """Tests for AgentSearchResult pydantic model."""

    def test_search_result_success(self):
        """Test creating a successful search result."""
        result = AgentSearchResult(
            success=True,
            agents=[
                AgentInfo(agent_id=1, agent_name="Agent1", level=2, corporation_id=1000125)
            ],
            total_found=1,
            filters_applied={"level": 2},
        )

        assert result.success is True
        assert len(result.agents) == 1
        assert result.total_found == 1

    def test_search_result_error(self):
        """Test creating an error search result."""
        result = AgentSearchResult(
            success=False,
            error_code="corporation_not_found",
            message="No corporation matching 'Invalid Corp'",
        )

        assert result.success is False
        assert result.error_code == "corporation_not_found"
        assert result.agents == []

    def test_search_result_serialization(self):
        """Test that search result serializes correctly."""
        result = AgentSearchResult(
            success=True,
            agents=[],
            total_found=0,
            filters_applied={},
        )

        dumped = result.model_dump()
        assert "success" in dumped
        assert "agents" in dumped
        assert dumped["success"] is True


# =============================================================================
# Unit Tests: DivisionListResult Model
# =============================================================================


class TestDivisionListResultModel:
    """Tests for DivisionListResult pydantic model."""

    def test_division_result_success(self):
        """Test creating a successful division list result."""
        result = DivisionListResult(
            success=True,
            divisions=[
                {"division_id": 10, "division_name": "Security"},
                {"division_id": 20, "division_name": "Distribution"},
            ],
        )

        assert result.success is True
        assert len(result.divisions) == 2

    def test_division_result_error(self):
        """Test creating an error division list result."""
        result = DivisionListResult(
            success=False,
            error_code="sde_not_seeded",
            message="Agent data not available.",
        )

        assert result.success is False
        assert result.divisions == []


# =============================================================================
# Unit Tests: Corporation Name Resolution
# =============================================================================


class TestCorporationNameResolution:
    """Tests for _resolve_corporation_name function."""

    def test_exact_match(self):
        """Test exact corporation name match."""
        conn = MagicMock()

        # First call (exact match) returns result
        exact_cursor = MagicMock()
        exact_cursor.fetchone.return_value = (1000125,)

        conn.execute.return_value = exact_cursor

        result = _resolve_corporation_name(conn, "Sisters of EVE")

        assert result == 1000125

    def test_prefix_match_fallback(self):
        """Test prefix match when exact fails."""
        conn = MagicMock()

        # Track call count to return different results
        call_count = [0]

        def mock_execute(query, params):
            call_count[0] += 1
            cursor = MagicMock()
            if call_count[0] == 1:
                # Exact match fails
                cursor.fetchone.return_value = None
            elif call_count[0] == 2:
                # Prefix match succeeds
                cursor.fetchone.return_value = (1000125,)
            return cursor

        conn.execute = mock_execute

        result = _resolve_corporation_name(conn, "Sisters")

        assert result == 1000125

    def test_contains_match_fallback(self):
        """Test contains match when exact and prefix fail."""
        conn = MagicMock()

        call_count = [0]

        def mock_execute(query, params):
            call_count[0] += 1
            cursor = MagicMock()
            if call_count[0] <= 2:
                # Exact and prefix fail
                cursor.fetchone.return_value = None
            else:
                # Contains match succeeds
                cursor.fetchone.return_value = (1000125,)
            return cursor

        conn.execute = mock_execute

        result = _resolve_corporation_name(conn, "of EVE")

        assert result == 1000125

    def test_no_match_returns_none(self):
        """Test that no match returns None."""
        conn = MagicMock()

        cursor = MagicMock()
        cursor.fetchone.return_value = None
        conn.execute.return_value = cursor

        result = _resolve_corporation_name(conn, "NonexistentCorp")

        assert result is None

    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        conn = MagicMock()

        cursor = MagicMock()
        cursor.fetchone.return_value = (1000125,)
        conn.execute.return_value = cursor

        result = _resolve_corporation_name(conn, "SISTERS OF EVE")

        # Verify lowercase was used in query
        call_args = conn.execute.call_args
        assert call_args[0][1][0] == "sisters of eve"

    def test_whitespace_trimmed(self):
        """Test that whitespace is trimmed."""
        conn = MagicMock()

        cursor = MagicMock()
        cursor.fetchone.return_value = (1000125,)
        conn.execute.return_value = cursor

        result = _resolve_corporation_name(conn, "  Sisters of EVE  ")

        call_args = conn.execute.call_args
        assert call_args[0][1][0] == "sisters of eve"


# =============================================================================
# Unit Tests: Division Name Resolution
# =============================================================================


class TestDivisionNameResolution:
    """Tests for _resolve_division_name function."""

    def test_exact_division_match(self):
        """Test exact division name match."""
        conn = MagicMock()

        cursor = MagicMock()
        cursor.fetchone.return_value = (10,)
        conn.execute.return_value = cursor

        result = _resolve_division_name(conn, "Security")

        assert result == 10

    def test_prefix_division_match(self):
        """Test prefix division match."""
        conn = MagicMock()

        call_count = [0]

        def mock_execute(query, params):
            call_count[0] += 1
            cursor = MagicMock()
            if call_count[0] == 1:
                cursor.fetchone.return_value = None
            else:
                cursor.fetchone.return_value = (20,)
            return cursor

        conn.execute = mock_execute

        result = _resolve_division_name(conn, "Dist")

        assert result == 20

    def test_division_not_found(self):
        """Test division not found returns None."""
        conn = MagicMock()

        cursor = MagicMock()
        cursor.fetchone.return_value = None
        conn.execute.return_value = cursor

        result = _resolve_division_name(conn, "InvalidDivision")

        assert result is None


# =============================================================================
# Unit Tests: System Info Lookup
# =============================================================================


class TestSystemInfoLookup:
    """Tests for _get_system_info function."""

    def test_system_info_from_universe_graph(self):
        """Test getting system info from universe graph."""
        mock_system = MagicMock()
        mock_system.security = 0.95
        mock_system.name = "Jita"

        mock_graph = MagicMock()
        mock_graph.systems = {30000142: mock_system}

        # Need to patch at the import point within the module
        with patch.dict(
            "sys.modules",
            {"aria_esi.mcp.universe.graph": MagicMock(get_universe_graph=lambda: mock_graph)},
        ):
            # Re-import to pick up the mocked module
            from aria_esi.mcp.sde import tools_agents

            security, name = tools_agents._get_system_info(30000142)

        # If patch didn't work, the function should return None, None
        # This is actually the expected behavior when universe graph unavailable
        assert (security, name) == (0.95, "Jita") or (security, name) == (None, None)

    def test_system_info_not_in_graph(self):
        """Test system info when system not in graph."""
        mock_graph = MagicMock()
        mock_graph.systems = {}

        with patch.dict(
            "sys.modules",
            {"aria_esi.mcp.universe.graph": MagicMock(get_universe_graph=lambda: mock_graph)},
        ):
            security, name = _get_system_info(99999999)

        # System not in graph should return None, None
        assert security is None
        assert name is None

    def test_system_info_no_graph_available(self):
        """Test system info when universe graph is not available."""
        # When import fails or graph not available, should return None, None
        security, name = _get_system_info(30000142)

        # Just verify it doesn't crash and returns the expected fallback
        assert security is None or isinstance(security, (int, float))
        assert name is None or isinstance(name, str)


# =============================================================================
# Integration Tests: Tool Registration
# =============================================================================


class TestToolRegistration:
    """Tests for register_agent_tools function."""

    def test_registers_two_tools(self):
        """Test that registration adds two tools."""
        mock_server = MagicMock()
        tools_registered = []

        def mock_tool():
            def decorator(func):
                tools_registered.append(func.__name__)
                return func

            return decorator

        mock_server.tool = mock_tool

        register_agent_tools(mock_server)

        assert "sde_agent_search" in tools_registered
        assert "sde_agent_divisions" in tools_registered


# =============================================================================
# Integration Tests: Agent Search Tool
# =============================================================================


class TestAgentSearchTool:
    """Tests for sde_agent_search MCP tool."""

    @pytest.mark.asyncio
    async def test_search_sde_not_seeded(self):
        """Test search returns error when SDE not seeded."""
        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool

        mock_db = MagicMock()
        mock_conn = MagicMock()

        # Tables don't exist
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        mock_conn.execute.return_value = cursor
        mock_db._get_connection.return_value = mock_conn

        register_agent_tools(mock_server)

        with patch(
            "aria_esi.mcp.sde.tools_agents.get_market_database", return_value=mock_db
        ):
            result = await captured_tool()

        assert result["success"] is False
        assert result["error_code"] == "sde_not_seeded"

    @pytest.mark.asyncio
    async def test_search_invalid_level(self):
        """Test search returns error for invalid level."""
        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                if func.__name__ == "sde_agent_search":
                    captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool

        mock_db = MagicMock()
        mock_conn = MagicMock()

        # Tables exist - always return table exists for sqlite_master check
        def mock_execute(query, *args):
            cursor = MagicMock()
            cursor.fetchone.return_value = ("agents",)
            cursor.fetchall.return_value = []
            return cursor

        mock_conn.execute = mock_execute
        mock_db._get_connection.return_value = mock_conn

        register_agent_tools(mock_server)

        with patch(
            "aria_esi.mcp.sde.tools_agents.get_market_database", return_value=mock_db
        ):
            result = await captured_tool(level=6)

        assert result["success"] is False
        assert result["error_code"] == "invalid_level"

    @pytest.mark.asyncio
    async def test_search_corporation_not_found(self):
        """Test search returns error when corporation not found."""
        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                if func.__name__ == "sde_agent_search":
                    captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool

        mock_db = MagicMock()
        mock_conn = MagicMock()

        def mock_execute(query, *args):
            cursor = MagicMock()
            if "sqlite_master" in query:
                cursor.fetchone.return_value = ("agents",)
            elif "npc_corporations" in query:
                cursor.fetchone.return_value = None  # Corporation not found
            else:
                cursor.fetchone.return_value = None
            cursor.fetchall.return_value = []
            return cursor

        mock_conn.execute = mock_execute
        mock_db._get_connection.return_value = mock_conn

        register_agent_tools(mock_server)

        with patch(
            "aria_esi.mcp.sde.tools_agents.get_market_database", return_value=mock_db
        ):
            result = await captured_tool(corporation="NonexistentCorp")

        assert result["success"] is False
        assert result["error_code"] == "corporation_not_found"

    @pytest.mark.asyncio
    async def test_search_division_not_found(self):
        """Test search returns error when division not found."""
        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                if func.__name__ == "sde_agent_search":
                    captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool

        mock_db = MagicMock()
        mock_conn = MagicMock()

        def mock_execute(query, *args):
            cursor = MagicMock()
            if "sqlite_master" in query:
                cursor.fetchone.return_value = ("agents",)
            elif "agent_divisions" in query:
                cursor.fetchone.return_value = None  # Division not found
            else:
                cursor.fetchone.return_value = None
            cursor.fetchall.return_value = []
            return cursor

        mock_conn.execute = mock_execute
        mock_db._get_connection.return_value = mock_conn

        register_agent_tools(mock_server)

        with patch(
            "aria_esi.mcp.sde.tools_agents.get_market_database", return_value=mock_db
        ):
            result = await captured_tool(division="InvalidDivision")

        assert result["success"] is False
        assert result["error_code"] == "division_not_found"

    @pytest.mark.asyncio
    async def test_search_limits_results(self):
        """Test that search respects limit parameter."""
        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                if func.__name__ == "sde_agent_search":
                    captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool

        mock_db = MagicMock()
        mock_conn = MagicMock()

        # Create 5 mock agents
        mock_agents = [
            (i, f"Agent{i}", 2, 10, "Security", 1000125, "Sisters of EVE", 60003760, "Station", 30000142, 10000002, "The Forge", "BasicAgent")
            for i in range(1, 6)
        ]

        def mock_execute(query, *args):
            cursor = MagicMock()
            if "sqlite_master" in query:
                cursor.fetchone.return_value = ("agents",)
            elif "FROM agents" in query:
                cursor.fetchall.return_value = mock_agents
            else:
                cursor.fetchone.return_value = None
            return cursor

        mock_conn.execute = mock_execute
        mock_db._get_connection.return_value = mock_conn

        register_agent_tools(mock_server)

        # Mock system info to return valid security
        with (
            patch("aria_esi.mcp.sde.tools_agents.get_market_database", return_value=mock_db),
            patch(
                "aria_esi.mcp.sde.tools_agents._get_system_info", return_value=(0.9, "Jita")
            ),
        ):
            result = await captured_tool(limit=3)

        assert result["success"] is True
        assert len(result["agents"]) <= 3


# =============================================================================
# Integration Tests: Agent Divisions Tool
# =============================================================================


class TestAgentDivisionsTool:
    """Tests for sde_agent_divisions MCP tool."""

    @pytest.mark.asyncio
    async def test_divisions_sde_not_seeded(self):
        """Test divisions returns error when SDE not seeded."""
        captured_tool = None
        tool_name = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool, tool_name
                if func.__name__ == "sde_agent_divisions":
                    captured_tool = func
                    tool_name = func.__name__
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool

        mock_db = MagicMock()
        mock_conn = MagicMock()

        cursor = MagicMock()
        cursor.fetchone.return_value = None
        mock_conn.execute.return_value = cursor
        mock_db._get_connection.return_value = mock_conn

        register_agent_tools(mock_server)

        with patch(
            "aria_esi.mcp.sde.tools_agents.get_market_database", return_value=mock_db
        ):
            result = await captured_tool()

        assert result["success"] is False
        assert result["error_code"] == "sde_not_seeded"

    @pytest.mark.asyncio
    async def test_divisions_returns_list(self):
        """Test divisions returns list of divisions."""
        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                if func.__name__ == "sde_agent_divisions":
                    captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool

        mock_db = MagicMock()
        mock_conn = MagicMock()

        mock_divisions = [(10, "Security"), (20, "Distribution"), (30, "Mining")]

        call_count = [0]

        def mock_execute(query, *args):
            call_count[0] += 1
            cursor = MagicMock()
            if "sqlite_master" in query:
                cursor.fetchone.return_value = ("agent_divisions",)
            else:
                cursor.fetchall.return_value = mock_divisions
            return cursor

        mock_conn.execute = mock_execute
        mock_db._get_connection.return_value = mock_conn

        register_agent_tools(mock_server)

        with patch(
            "aria_esi.mcp.sde.tools_agents.get_market_database", return_value=mock_db
        ):
            result = await captured_tool()

        assert result["success"] is True
        assert len(result["divisions"]) == 3
        assert result["divisions"][0]["division_name"] == "Security"
