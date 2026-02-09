"""
Tests for MCP Server and Tool Registration.

STP-004: MCP Server Core Tests
"""

from pathlib import Path
from unittest.mock import MagicMock

import igraph as ig
import numpy as np
import pytest

from aria_esi.mcp.errors import SystemNotFoundError
from aria_esi.mcp.server import DEFAULT_GRAPH_PATH, UniverseServer
from aria_esi.mcp.tools import (
    ResolvedSystem,
    _find_suggestions,
    collect_corrections,
    get_universe,
    register_tools,
    resolve_system_name,
)
from aria_esi.universe import UniverseBuildError, UniverseGraph
from aria_esi.universe.serialization import save_universe_graph

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_universe() -> UniverseGraph:
    """
    Create a minimal mock universe for testing.

    Graph structure:
        Jita (high-sec 0.95) -- Perimeter (high-sec 0.90)
             |                        |
        Maurasi (high-sec 0.65) -- Urlen (high-sec 0.85)
             |
        Sivala (low-sec 0.35)
             |
        Ala (null-sec -0.2)
    """
    g = ig.Graph(
        n=6,
        edges=[
            (0, 1),  # Jita -- Perimeter
            (0, 2),  # Jita -- Maurasi
            (1, 3),  # Perimeter -- Urlen
            (2, 3),  # Maurasi -- Urlen
            (2, 4),  # Maurasi -- Sivala
            (4, 5),  # Sivala -- Ala
        ],
        directed=False,
    )

    systems = [
        {"name": "Jita", "id": 30000142, "sec": 0.95, "const": 20000020, "region": 10000002},
        {"name": "Perimeter", "id": 30000144, "sec": 0.90, "const": 20000020, "region": 10000002},
        {"name": "Maurasi", "id": 30000140, "sec": 0.65, "const": 20000020, "region": 10000002},
        {"name": "Urlen", "id": 30000138, "sec": 0.85, "const": 20000020, "region": 10000002},
        {"name": "Sivala", "id": 30000160, "sec": 0.35, "const": 20000021, "region": 10000002},
        {"name": "Ala", "id": 30000161, "sec": -0.2, "const": 20000022, "region": 10000003},
    ]

    name_to_idx = {s["name"]: i for i, s in enumerate(systems)}
    idx_to_name = {i: s["name"] for i, s in enumerate(systems)}
    name_to_id = {s["name"]: s["id"] for s in systems}
    id_to_idx = {s["id"]: i for i, s in enumerate(systems)}
    name_lookup = {s["name"].lower(): s["name"] for s in systems}

    security = np.array([s["sec"] for s in systems], dtype=np.float32)
    system_ids = np.array([s["id"] for s in systems], dtype=np.int32)
    constellation_ids = np.array([s["const"] for s in systems], dtype=np.int32)
    region_ids = np.array([s["region"] for s in systems], dtype=np.int32)

    highsec = frozenset(i for i in range(6) if security[i] >= 0.45)
    lowsec = frozenset(i for i in range(6) if 0.0 < security[i] < 0.45)
    nullsec = frozenset(i for i in range(6) if security[i] <= 0.0)
    border = frozenset([2])

    region_systems = {
        10000002: [0, 1, 2, 3, 4],
        10000003: [5],
    }
    constellation_names = {
        20000020: "Kimotoro",
        20000021: "Otanuomi",
        20000022: "Somewhere",
    }
    region_names = {
        10000002: "The Forge",
        10000003: "Outer Region",
    }
    region_name_lookup = {name.lower(): rid for rid, name in region_names.items()}

    return UniverseGraph(
        graph=g,
        name_to_idx=name_to_idx,
        idx_to_name=idx_to_name,
        name_to_id=name_to_id,
        id_to_idx=id_to_idx,
        security=security,
        system_ids=system_ids,
        constellation_ids=constellation_ids,
        region_ids=region_ids,
        name_lookup=name_lookup,
        constellation_names=constellation_names,
        region_names=region_names,
        region_name_lookup=region_name_lookup,
        border_systems=border,
        region_systems=region_systems,
        highsec_systems=highsec,
        lowsec_systems=lowsec,
        nullsec_systems=nullsec,
        version="test-1.0",
        system_count=6,
        stargate_count=6,
    )


@pytest.fixture
def test_graph_path(tmp_path: Path, mock_universe: UniverseGraph) -> Path:
    """Create a .universe graph file for testing."""
    graph_path = tmp_path / "universe.universe"
    save_universe_graph(mock_universe, graph_path)
    return graph_path


# =============================================================================
# UniverseServer Tests
# =============================================================================


class TestUniverseServerInit:
    """Test UniverseServer initialization."""

    def test_default_graph_path(self):
        """Server uses default graph path."""
        server = UniverseServer()
        assert server.graph_path == DEFAULT_GRAPH_PATH

    def test_custom_graph_path(self, tmp_path: Path):
        """Server accepts custom graph path."""
        custom_path = tmp_path / "custom.universe"
        server = UniverseServer(graph_path=custom_path)
        assert server.graph_path == custom_path

    def test_initial_state(self):
        """Server initializes without loading graph."""
        server = UniverseServer()
        assert server.universe is None
        assert server._tools_registered is False

    def test_server_name(self):
        """Server has correct name."""
        server = UniverseServer()
        assert server.server.name == "aria-universe"


class TestUniverseServerEnvVar:
    """Test ARIA_UNIVERSE_GRAPH environment variable handling."""

    def test_env_var_overrides_default(self, tmp_path: Path, monkeypatch):
        """ARIA_UNIVERSE_GRAPH env var overrides default path."""
        custom_path = tmp_path / "custom_env.universe"
        monkeypatch.setenv("ARIA_UNIVERSE_GRAPH", str(custom_path))

        server = UniverseServer()
        assert server.graph_path == custom_path

    def test_explicit_path_overrides_env_var(self, tmp_path: Path, monkeypatch):
        """Explicit path parameter overrides env var."""
        env_path = tmp_path / "env.universe"
        explicit_path = tmp_path / "explicit.universe"
        monkeypatch.setenv("ARIA_UNIVERSE_GRAPH", str(env_path))

        server = UniverseServer(graph_path=explicit_path)
        assert server.graph_path == explicit_path


class TestUniverseServerLoadGraph:
    """Test graph loading."""

    def test_loads_graph_successfully(self, test_graph_path: Path):
        """Server loads graph from .universe."""
        server = UniverseServer(graph_path=test_graph_path)
        # skip_integrity_check=True for test-generated graphs that don't match manifest
        server.load_graph(skip_integrity_check=True)

        assert server.universe is not None
        assert server.universe.system_count > 0

    def test_load_sets_universe(self, test_graph_path: Path):
        """Loading graph sets universe attribute."""
        server = UniverseServer(graph_path=test_graph_path)
        assert server.universe is None

        # skip_integrity_check=True for test-generated graphs that don't match manifest
        server.load_graph(skip_integrity_check=True)
        assert server.universe is not None

    def test_load_missing_file_raises(self, tmp_path: Path):
        """Loading non-existent file raises UniverseBuildError."""
        missing_path = tmp_path / "missing.universe"
        server = UniverseServer(graph_path=missing_path)

        with pytest.raises(UniverseBuildError) as exc:
            server.load_graph()

        assert "Universe graph not found" in str(exc.value)


class TestUniverseServerRegisterTools:
    """Test tool registration."""

    def test_register_tools_requires_graph(self):
        """Tool registration requires loaded graph."""
        server = UniverseServer()

        with pytest.raises(RuntimeError, match="Graph must be loaded"):
            server.register_tools()

    def test_register_tools_after_load(self, test_graph_path: Path):
        """Tool registration succeeds after loading graph."""
        server = UniverseServer(graph_path=test_graph_path)
        # skip_integrity_check=True for test-generated graphs that don't match manifest
        server.load_graph(skip_integrity_check=True)
        server.register_tools()

        assert server._tools_registered is True

    def test_register_tools_idempotent(self, test_graph_path: Path):
        """Repeated registration is safe."""
        server = UniverseServer(graph_path=test_graph_path)
        # skip_integrity_check=True for test-generated graphs that don't match manifest
        server.load_graph(skip_integrity_check=True)

        server.register_tools()
        server.register_tools()  # Should not raise

        assert server._tools_registered is True


# =============================================================================
# Tool Registration Framework Tests
# =============================================================================


class TestGetUniverse:
    """Test get_universe function."""

    def test_raises_before_registration(self):
        """get_universe raises before tools registered."""
        # Reset global state
        import aria_esi.mcp.tools as tools_module

        original = tools_module._universe
        tools_module._universe = None

        try:
            with pytest.raises(RuntimeError, match="not loaded"):
                get_universe()
        finally:
            tools_module._universe = original

    def test_returns_universe_after_registration(self, mock_universe: UniverseGraph):
        """get_universe returns universe after registration."""
        mock_server = MagicMock()
        register_tools(mock_server, mock_universe)

        result = get_universe()
        assert result is mock_universe


class TestResolveSystemName:
    """Test resolve_system_name function."""

    def test_valid_name_resolves(self, mock_universe: UniverseGraph):
        """Valid system name resolves to ResolvedSystem."""
        mock_server = MagicMock()
        register_tools(mock_server, mock_universe)

        result = resolve_system_name("Jita")
        assert isinstance(result, ResolvedSystem)
        assert result.idx == 0
        assert result.canonical_name == "Jita"
        assert result.corrected_from is None
        assert not result.was_corrected

    def test_case_insensitive(self, mock_universe: UniverseGraph):
        """Name resolution is case-insensitive."""
        mock_server = MagicMock()
        register_tools(mock_server, mock_universe)

        assert resolve_system_name("jita").idx == 0
        assert resolve_system_name("JITA").idx == 0
        assert resolve_system_name("JiTa").idx == 0

    def test_auto_correct_typo(self, mock_universe: UniverseGraph):
        """Typo with single suggestion is auto-corrected."""
        mock_server = MagicMock()
        register_tools(mock_server, mock_universe)

        # "Juta" should auto-correct to "Jita" (single suggestion)
        result = resolve_system_name("Juta")
        assert result.idx == 0
        assert result.canonical_name == "Jita"
        assert result.corrected_from == "Juta"
        assert result.was_corrected

    def test_auto_correct_can_be_disabled(self, mock_universe: UniverseGraph):
        """Auto-correction can be disabled."""
        mock_server = MagicMock()
        register_tools(mock_server, mock_universe)

        # With auto_correct=False, should raise error instead
        with pytest.raises(SystemNotFoundError) as exc_info:
            resolve_system_name("Juta", auto_correct=False)

        assert exc_info.value.name == "Juta"
        assert "Jita" in exc_info.value.suggestions

    def test_unknown_name_raises_when_multiple_suggestions(self, mock_universe: UniverseGraph):
        """Unknown name with multiple suggestions raises SystemNotFoundError."""
        mock_server = MagicMock()
        register_tools(mock_server, mock_universe)

        # "a" matches multiple systems via substring, so should not auto-correct
        with pytest.raises(SystemNotFoundError) as exc_info:
            resolve_system_name("xyz123")

        assert exc_info.value.name == "xyz123"

    def test_unknown_name_includes_suggestions(self, mock_universe: UniverseGraph):
        """Unknown name error includes suggestions."""
        mock_server = MagicMock()
        register_tools(mock_server, mock_universe)

        with pytest.raises(SystemNotFoundError) as exc_info:
            resolve_system_name("Jit", auto_correct=False)

        # Should suggest "Jita" as it starts with "Jit"
        assert "Jita" in exc_info.value.suggestions


class TestCollectCorrections:
    """Test collect_corrections helper function."""

    def test_no_corrections(self, mock_universe: UniverseGraph):
        """No corrections when all systems resolve exactly."""
        mock_server = MagicMock()
        register_tools(mock_server, mock_universe)

        r1 = resolve_system_name("Jita")
        r2 = resolve_system_name("Perimeter")
        corrections = collect_corrections(r1, r2)
        assert corrections == {}

    def test_single_correction(self, mock_universe: UniverseGraph):
        """Single correction is collected."""
        mock_server = MagicMock()
        register_tools(mock_server, mock_universe)

        r1 = resolve_system_name("Juta")  # Auto-corrects to Jita
        r2 = resolve_system_name("Perimeter")  # Exact match
        corrections = collect_corrections(r1, r2)
        assert corrections == {"Juta": "Jita"}

    def test_multiple_corrections(self, mock_universe: UniverseGraph):
        """Multiple corrections are collected."""
        mock_server = MagicMock()
        register_tools(mock_server, mock_universe)

        r1 = resolve_system_name("Juta")  # Auto-corrects to Jita
        r2 = resolve_system_name("Sivalla")  # Auto-corrects to Sivala
        corrections = collect_corrections(r1, r2)
        assert corrections == {"Juta": "Jita", "Sivalla": "Sivala"}


class TestFindSuggestions:
    """Test _find_suggestions function."""

    def test_prefix_match(self, mock_universe: UniverseGraph):
        """Prefix matches are found."""
        suggestions = _find_suggestions("Per", mock_universe)
        assert "Perimeter" in suggestions

    def test_substring_match(self, mock_universe: UniverseGraph):
        """Substring matches are found."""
        suggestions = _find_suggestions("imeter", mock_universe)
        assert "Perimeter" in suggestions

    def test_case_insensitive(self, mock_universe: UniverseGraph):
        """Matching is case-insensitive."""
        suggestions = _find_suggestions("JITA", mock_universe)
        assert "Jita" in suggestions

    def test_respects_limit(self, mock_universe: UniverseGraph):
        """Results respect limit parameter."""
        suggestions = _find_suggestions("a", mock_universe, limit=2)
        assert len(suggestions) <= 2

    def test_empty_input(self, mock_universe: UniverseGraph):
        """Empty input returns many matches."""
        suggestions = _find_suggestions("", mock_universe, limit=3)
        # Empty string is substring of everything
        assert len(suggestions) == 3

    def test_no_matches(self, mock_universe: UniverseGraph):
        """No matches returns empty list."""
        suggestions = _find_suggestions("xyz123", mock_universe)
        assert suggestions == []

    def test_fuzzy_match_typo(self, mock_universe: UniverseGraph):
        """Fuzzy matching catches single-character typos."""
        # "Juta" should match "Jita" via Levenshtein (edit distance 1)
        suggestions = _find_suggestions("Juta", mock_universe)
        assert "Jita" in suggestions

    def test_fuzzy_match_transposition(self, mock_universe: UniverseGraph):
        """Fuzzy matching catches character transpositions."""
        # "Jiat" should match "Jita" via Levenshtein (edit distance 2)
        suggestions = _find_suggestions("Jiat", mock_universe)
        assert "Jita" in suggestions

    def test_fuzzy_match_extra_char(self, mock_universe: UniverseGraph):
        """Fuzzy matching catches extra characters."""
        # "Sivalla" should match "Sivala" (edit distance 1)
        suggestions = _find_suggestions("Sivalla", mock_universe)
        assert "Sivala" in suggestions

    def test_fuzzy_match_missing_char(self, mock_universe: UniverseGraph):
        """Fuzzy matching catches missing characters."""
        # "Ulen" should match "Urlen" (edit distance 1)
        suggestions = _find_suggestions("Ulen", mock_universe)
        assert "Urlen" in suggestions

    def test_fuzzy_sorted_by_distance(self, mock_universe: UniverseGraph):
        """Fuzzy matches are sorted by edit distance."""
        # "Jita" with typo "Juta" (distance 1) vs "Ala" (distance 3)
        # Should prefer closer match
        suggestions = _find_suggestions("Juta", mock_universe)
        # First suggestion should be Jita (distance 1)
        assert suggestions[0] == "Jita"

    def test_prefix_takes_priority_over_fuzzy(self, mock_universe: UniverseGraph):
        """Prefix matches are returned before fuzzy search runs."""
        # "Ji" matches "Jita" via prefix - no fuzzy needed
        suggestions = _find_suggestions("Ji", mock_universe)
        assert "Jita" in suggestions


class TestLevenshteinDistance:
    """Test _levenshtein_distance function."""

    def test_identical_strings(self):
        """Identical strings have distance 0."""
        from aria_esi.mcp.tools import _levenshtein_distance

        assert _levenshtein_distance("test", "test") == 0

    def test_single_insertion(self):
        """Single character insertion has distance 1."""
        from aria_esi.mcp.tools import _levenshtein_distance

        assert _levenshtein_distance("test", "tests") == 1

    def test_single_deletion(self):
        """Single character deletion has distance 1."""
        from aria_esi.mcp.tools import _levenshtein_distance

        assert _levenshtein_distance("tests", "test") == 1

    def test_single_substitution(self):
        """Single character substitution has distance 1."""
        from aria_esi.mcp.tools import _levenshtein_distance

        assert _levenshtein_distance("test", "tast") == 1

    def test_transposition(self):
        """Character transposition has distance 2."""
        from aria_esi.mcp.tools import _levenshtein_distance

        # "ab" -> "ba" requires delete+insert = 2
        assert _levenshtein_distance("ab", "ba") == 2

    def test_empty_strings(self):
        """Empty string distance equals other string length."""
        from aria_esi.mcp.tools import _levenshtein_distance

        assert _levenshtein_distance("", "test") == 4
        assert _levenshtein_distance("test", "") == 4

    def test_case_sensitive(self):
        """Distance is case-sensitive."""
        from aria_esi.mcp.tools import _levenshtein_distance

        assert _levenshtein_distance("Test", "test") == 1

    def test_kisago_kisogo(self):
        """Real-world typo: Kisago vs Kisogo."""
        from aria_esi.mcp.tools import _levenshtein_distance

        # "Kisago" -> "Kisogo" = 1 substitution (a->o)
        assert _levenshtein_distance("kisago", "kisogo") == 1


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestModuleExports:
    """Test that server components are exported correctly."""

    def test_universe_server_exported(self):
        """UniverseServer is exported from mcp module."""
        from aria_esi.mcp import UniverseServer

        assert UniverseServer is not None

    def test_main_exported(self):
        """main function is exported from mcp module."""
        from aria_esi.mcp import main

        assert main is not None
        assert callable(main)
