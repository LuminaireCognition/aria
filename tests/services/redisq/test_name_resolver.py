"""
Tests for Kill Notification Name Resolution.

Tests NameResolver class for system and type name resolution.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# NameResolver Tests
# =============================================================================


class TestNameResolverInit:
    """Test NameResolver initialization."""

    def test_init_without_graph(self):
        """Initialize without pre-loaded graph."""
        from aria_esi.services.redisq.name_resolver import NameResolver

        resolver = NameResolver()

        assert resolver._graph is None
        assert resolver._graph_loaded is False

    def test_init_with_graph(self):
        """Initialize with pre-loaded graph."""
        from aria_esi.services.redisq.name_resolver import NameResolver

        mock_graph = MagicMock()
        resolver = NameResolver(graph=mock_graph)

        assert resolver._graph is mock_graph
        assert resolver._graph_loaded is True


class TestEnsureGraph:
    """Test lazy graph loading."""

    def test_lazy_load_success(self):
        """Graph loads successfully on first use."""
        from aria_esi.services.redisq.name_resolver import NameResolver

        mock_graph = MagicMock()

        with patch(
            "aria_esi.universe.load_universe_graph",
            return_value=mock_graph,
        ):
            resolver = NameResolver()
            result = resolver._ensure_graph()

            assert result is mock_graph
            assert resolver._graph_loaded is True

    def test_lazy_load_failure_sets_flag(self):
        """Graph load failure sets flag to prevent retry."""
        from aria_esi.services.redisq.name_resolver import NameResolver

        with patch(
            "aria_esi.universe.load_universe_graph",
            side_effect=Exception("Load failed"),
        ):
            resolver = NameResolver()
            result = resolver._ensure_graph()

            assert result is None
            assert resolver._graph_loaded is True  # Flag set to prevent retry

    def test_skips_load_if_already_loaded(self):
        """Does not reload if already loaded."""
        from aria_esi.services.redisq.name_resolver import NameResolver

        mock_graph = MagicMock()
        resolver = NameResolver(graph=mock_graph)

        # Should return existing graph without trying to load
        result = resolver._ensure_graph()

        assert result is mock_graph


class TestResolveSystemName:
    """Test system name resolution."""

    def test_resolve_known_system(self):
        """Resolves known system ID to name."""
        from aria_esi.services.redisq.name_resolver import NameResolver

        mock_graph = MagicMock()
        mock_graph.id_to_idx = {30000142: 0}
        mock_graph.idx_to_name = {0: "Jita"}

        resolver = NameResolver(graph=mock_graph)
        result = resolver.resolve_system_name(30000142)

        assert result == "Jita"

    def test_resolve_unknown_system(self):
        """Returns None for unknown system ID."""
        from aria_esi.services.redisq.name_resolver import NameResolver

        mock_graph = MagicMock()
        mock_graph.id_to_idx = {}

        resolver = NameResolver(graph=mock_graph)
        result = resolver.resolve_system_name(99999999)

        assert result is None

    def test_resolve_without_graph(self):
        """Returns None when graph unavailable."""
        from aria_esi.services.redisq.name_resolver import NameResolver

        with patch(
            "aria_esi.universe.load_universe_graph",
            side_effect=Exception("No graph"),
        ):
            resolver = NameResolver()
            result = resolver.resolve_system_name(30000142)

            assert result is None


class TestResolveSystemWithFallback:
    """Test system resolution with fallback."""

    def test_returns_name_when_found(self):
        """Returns system name when found."""
        from aria_esi.services.redisq.name_resolver import NameResolver

        mock_graph = MagicMock()
        mock_graph.id_to_idx = {30000142: 0}
        mock_graph.idx_to_name = {0: "Jita"}

        resolver = NameResolver(graph=mock_graph)
        result = resolver.resolve_system_with_fallback(30000142)

        assert result == "Jita"

    def test_returns_fallback_when_not_found(self):
        """Returns 'System {id}' fallback when not found."""
        from aria_esi.services.redisq.name_resolver import NameResolver

        mock_graph = MagicMock()
        mock_graph.id_to_idx = {}

        resolver = NameResolver(graph=mock_graph)
        result = resolver.resolve_system_with_fallback(99999999)

        assert result == "System 99999999"


class TestResolveTypeWithFallback:
    """Test type resolution with fallback."""

    def test_returns_unknown_for_none(self):
        """Returns 'Unknown' for None type ID."""
        from aria_esi.services.redisq.name_resolver import NameResolver

        resolver = NameResolver()
        result = resolver.resolve_type_with_fallback(None)

        assert result == "Unknown"

    def test_returns_fallback_when_not_found(self):
        """Returns 'Ship {id}' fallback when type not found."""
        from aria_esi.services.redisq.name_resolver import NameResolver

        with patch(
            "aria_esi.services.redisq.name_resolver._resolve_type_name_cached",
            return_value=None,
        ):
            resolver = NameResolver()
            result = resolver.resolve_type_with_fallback(12345)

            assert result == "Ship 12345"

    def test_returns_name_when_found(self):
        """Returns type name when found."""
        from aria_esi.services.redisq.name_resolver import NameResolver

        with patch(
            "aria_esi.services.redisq.name_resolver._resolve_type_name_cached",
            return_value="Vexor",
        ):
            resolver = NameResolver()
            result = resolver.resolve_type_with_fallback(626)

            assert result == "Vexor"


# =============================================================================
# Singleton Tests
# =============================================================================


class TestGetNameResolver:
    """Test singleton accessor."""

    def test_returns_resolver(self):
        """get_name_resolver returns a NameResolver."""
        from aria_esi.services.redisq.name_resolver import (
            NameResolver,
            get_name_resolver,
            reset_name_resolver,
        )

        reset_name_resolver()
        resolver = get_name_resolver()

        assert isinstance(resolver, NameResolver)

    def test_returns_same_instance(self):
        """get_name_resolver returns cached instance."""
        from aria_esi.services.redisq.name_resolver import (
            get_name_resolver,
            reset_name_resolver,
        )

        reset_name_resolver()
        resolver1 = get_name_resolver()
        resolver2 = get_name_resolver()

        assert resolver1 is resolver2


class TestResetNameResolver:
    """Test singleton reset."""

    def test_reset_clears_singleton(self):
        """reset_name_resolver clears the singleton."""
        from aria_esi.services.redisq.name_resolver import (
            get_name_resolver,
            reset_name_resolver,
        )

        resolver1 = get_name_resolver()
        reset_name_resolver()
        resolver2 = get_name_resolver()

        assert resolver1 is not resolver2
