"""
Shared fixtures for MCP dispatcher tests.

Provides mock dispatchers, activity cache mocks, and other shared test infrastructure.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.mcp.activity import ActivityData
from aria_esi.universe import UniverseGraph


# =============================================================================
# Dispatcher Factory Fixtures
# =============================================================================


def create_dispatcher(
    register_func,
    universe: UniverseGraph | None = None,
    additional_setup: callable | None = None,
):
    """
    Factory to create a captured dispatcher function for testing.

    Args:
        register_func: The registration function (e.g., register_universe_dispatcher)
        universe: Optional UniverseGraph instance
        additional_setup: Optional callback for additional mock setup

    Returns:
        The captured async tool function
    """
    mock_server = MagicMock()
    captured_func = None

    def mock_tool():
        def decorator(func):
            nonlocal captured_func
            captured_func = func
            return func
        return decorator

    mock_server.tool = mock_tool

    if additional_setup:
        additional_setup(mock_server)

    if universe is not None:
        register_func(mock_server, universe)
    else:
        register_func(mock_server)

    return captured_func


@pytest.fixture
def universe_dispatcher(standard_universe):
    """Create universe dispatcher with mock server."""
    from aria_esi.mcp.dispatchers.universe import register_universe_dispatcher
    from aria_esi.mcp.tools import register_tools

    mock_server = MagicMock()

    def mock_tool():
        def decorator(func):
            return func
        return decorator

    mock_server.tool = mock_tool

    # Register universe tools first (needed for resolution)
    register_tools(mock_server, standard_universe)

    # Capture the dispatcher
    captured_func = None

    def capture_tool():
        def decorator(func):
            nonlocal captured_func
            captured_func = func
            return func
        return decorator

    mock_server.tool = capture_tool
    register_universe_dispatcher(mock_server, standard_universe)
    return captured_func


@pytest.fixture
def market_dispatcher(standard_universe):
    """Create market dispatcher with mock server."""
    from aria_esi.mcp.dispatchers.market import register_market_dispatcher

    return create_dispatcher(register_market_dispatcher, standard_universe)


@pytest.fixture
def sde_dispatcher(standard_universe):
    """Create SDE dispatcher with mock server."""
    from aria_esi.mcp.dispatchers.sde import register_sde_dispatcher

    return create_dispatcher(register_sde_dispatcher, standard_universe)


@pytest.fixture
def skills_dispatcher(standard_universe):
    """Create skills dispatcher with mock server."""
    from aria_esi.mcp.dispatchers.skills import register_skills_dispatcher

    return create_dispatcher(register_skills_dispatcher, standard_universe)


@pytest.fixture
def fitting_dispatcher(standard_universe):
    """Create fitting dispatcher with mock server."""
    from aria_esi.mcp.dispatchers.fitting import register_fitting_dispatcher
    from aria_esi.mcp.policy import PolicyEngine

    # Reset policy singleton
    PolicyEngine.reset_instance()

    dispatcher = create_dispatcher(register_fitting_dispatcher, standard_universe)
    yield dispatcher

    # Cleanup
    PolicyEngine.reset_instance()


@pytest.fixture
def status_tool():
    """Create status tool with mock server."""
    from aria_esi.mcp.dispatchers.status import register_status_tool

    return create_dispatcher(register_status_tool)


# =============================================================================
# Activity Cache Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_activity_cache():
    """
    Create a mock activity cache with configurable data.

    Returns a mock that can be patched into get_activity_cache().
    """
    cache = MagicMock()

    # Default activity data (zeros)
    default_activity = ActivityData(
        system_id=0,
        ship_kills=0,
        pod_kills=0,
        npc_kills=0,
        ship_jumps=0,
    )

    async def get_activity(system_id: int) -> ActivityData:
        return default_activity

    cache.get_activity = AsyncMock(side_effect=get_activity)
    cache.get_kills_cache_age.return_value = 60
    cache.get_all_activity = AsyncMock(return_value={})
    cache.get_all_fw = AsyncMock(return_value={})

    return cache


@pytest.fixture
def mock_activity_with_data():
    """
    Create a mock activity cache factory with preset activity data.

    Returns a factory function that creates mocks with specified activity levels.
    """

    def _create_cache(activity_map: dict[int, dict]) -> MagicMock:
        """
        Create mock cache with specific activity data.

        Args:
            activity_map: Dict mapping system_id to activity dict
                         e.g., {30000142: {"ship_kills": 5, "pod_kills": 2}}
        """
        cache = MagicMock()

        async def get_activity(system_id: int) -> ActivityData:
            data = activity_map.get(system_id, {})
            return ActivityData(
                system_id=system_id,
                ship_kills=data.get("ship_kills", 0),
                pod_kills=data.get("pod_kills", 0),
                npc_kills=data.get("npc_kills", 0),
                ship_jumps=data.get("ship_jumps", 0),
            )

        async def get_all_activity() -> dict[int, ActivityData]:
            result = {}
            for system_id, data in activity_map.items():
                result[system_id] = ActivityData(
                    system_id=system_id,
                    ship_kills=data.get("ship_kills", 0),
                    pod_kills=data.get("pod_kills", 0),
                    npc_kills=data.get("npc_kills", 0),
                    ship_jumps=data.get("ship_jumps", 0),
                )
            return result

        cache.get_activity = AsyncMock(side_effect=get_activity)
        cache.get_all_activity = AsyncMock(side_effect=get_all_activity)
        cache.get_kills_cache_age.return_value = 60
        cache.get_all_fw = AsyncMock(return_value={})

        return cache

    return _create_cache


# =============================================================================
# Market Database Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_market_db():
    """Create a mock market database."""
    db = MagicMock()

    # Type resolution mock
    def resolve_type_name(name: str):
        type_map = {
            "tritanium": MagicMock(type_id=34, type_name="Tritanium"),
            "pyerite": MagicMock(type_id=35, type_name="Pyerite"),
            "mexallon": MagicMock(type_id=36, type_name="Mexallon"),
            "isogen": MagicMock(type_id=37, type_name="Isogen"),
            "plex": MagicMock(type_id=44992, type_name="PLEX"),
            "venture": MagicMock(type_id=32880, type_name="Venture"),
            "vexor": MagicMock(type_id=626, type_name="Vexor"),
        }
        return type_map.get(name.lower())

    db.resolve_type_name = MagicMock(side_effect=resolve_type_name)
    db.find_type_suggestions = MagicMock(return_value=["Tritanium", "Pyerite"])
    db.get_stats = MagicMock(return_value={
        "database_path": "/tmp/test.db",
        "database_size_mb": 10.5,
        "type_count": 45000,
    })

    return db


@pytest.fixture
def mock_market_cache():
    """Create a mock market cache."""
    cache = MagicMock()

    async def get_prices(type_ids, type_names):
        from aria_esi.models.market import PriceAggregate, PriceResult

        results = []
        for type_id in type_ids:
            results.append(PriceResult(
                type_id=type_id,
                type_name=type_names.get(type_id, f"Type {type_id}"),
                sell=PriceAggregate(
                    min_price=100.0,
                    max_price=150.0,
                    avg_price=125.0,
                    volume=1000000,
                    order_count=100,
                ),
                buy=PriceAggregate(
                    min_price=80.0,
                    max_price=95.0,
                    avg_price=87.5,
                    volume=500000,
                    order_count=50,
                ),
                freshness="fresh",
            ))
        return results

    cache.get_prices = AsyncMock(side_effect=get_prices)
    cache.get_cache_status = MagicMock(return_value={
        "fuzzwork": {"age_seconds": 30, "ttl_seconds": 900, "stale": False},
    })

    return cache


# =============================================================================
# SDE Query Service Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_sde_service():
    """Create a mock SDE query service."""
    service = MagicMock()

    service.get_skill_prerequisites = MagicMock(return_value=[])
    service.get_type_skill_requirements = MagicMock(return_value=[])
    service.get_full_skill_tree = MagicMock(return_value=[])
    service.get_skill_attributes = MagicMock(return_value=None)
    service.get_meta_variants = MagicMock(return_value=[])
    service._get_parent_type_id = MagicMock(return_value=None)

    return service


# =============================================================================
# Async Run Helper
# =============================================================================


def run_async(coro):
    """Helper to run async functions in tests."""
    return asyncio.run(coro)
