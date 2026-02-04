"""
Golden tests for MCP dispatcher skill outputs.

Uses syrupy for snapshot testing to ensure output stability and quality.
These tests verify that skill outputs maintain consistent structure over time.

Run with: uv run pytest tests/skills/ -m golden
Update snapshots: uv run pytest tests/skills/ -m golden --snapshot-update
"""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.golden


# =============================================================================
# Status Output Golden Tests (enabled - mock subsystems)
# =============================================================================


@pytest.fixture
def mock_activity_cache():
    """Create a mock activity cache with stable test data."""
    cache = MagicMock()
    cache.get_cache_status.return_value = {
        "kills": {
            "cached_systems": 5000,
            "age_seconds": 120,
            "ttl_seconds": 3600,
            "stale": False,
        },
        "jumps": {
            "cached_systems": 5000,
            "age_seconds": 120,
            "ttl_seconds": 3600,
            "stale": False,
        },
        "fw": {
            "cached_systems": 200,
            "age_seconds": 300,
            "ttl_seconds": 3600,
            "stale": False,
        },
    }
    return cache


@pytest.fixture
def mock_market_cache():
    """Create a mock market cache with stable test data."""
    cache = MagicMock()
    cache.get_cache_status.return_value = {
        "fuzzwork": {
            "cached_types": 1000,
            "age_seconds": 500,
            "ttl_seconds": 900,
            "stale": False,
        },
        "esi_orders": {
            "cached_types": 50,
            "age_seconds": 100,
            "ttl_seconds": 300,
            "stale": False,
        },
    }
    return cache


@pytest.fixture
def mock_market_db():
    """Create a mock market database with stable test data."""
    db = MagicMock()
    db.get_stats.return_value = {
        "database_path": "/test/path/market.db",
        "database_size_mb": 150.5,
        "type_count": 45678,
    }
    return db


@pytest.fixture
def mock_eos_data_manager():
    """Create a mock EOS data manager with stable test data."""
    manager = MagicMock()
    validation = MagicMock()
    validation.is_valid = True
    validation.data_path = "/test/path/eos_data"
    validation.version = "2548611"
    validation.total_records = 45678
    validation.missing_files = []
    manager.validate.return_value = validation
    return manager


@pytest.fixture
def mock_notification_manager():
    """Create a mock notification manager with stable test data."""
    manager = MagicMock()
    manager.is_configured = True
    # Explicitly set _supervisor to None to prevent MagicMock leaking through
    manager._supervisor = None
    health = MagicMock()
    health.is_healthy = True
    health.is_paused = False
    health.is_quiet_hours = False
    health.success_rate = 1.0
    health.queue_depth = 0
    health.active_throttles = 0
    health.last_success = None
    health.next_active_time = None
    manager.get_health_status.return_value = health
    return manager


@pytest.mark.asyncio
class TestStatusOutputGolden:
    """Golden tests for status tool output."""

    async def test_status_output_structure(
        self,
        snapshot,
        normalize_volatile_fields,
        mock_activity_cache,
        mock_market_cache,
        mock_market_db,
        mock_eos_data_manager,
        mock_notification_manager,
    ):
        """Verify status output maintains consistent structure."""
        # Mock the killmail store path to not exist
        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with patch(
            "aria_esi.mcp.activity.get_activity_cache",
            return_value=mock_activity_cache,
        ):
            with patch(
                "aria_esi.mcp.market.cache.get_market_cache",
                return_value=mock_market_cache,
            ):
                with patch(
                    "aria_esi.mcp.market.database.get_market_database",
                    return_value=mock_market_db,
                ):
                    with patch(
                        "aria_esi.fitting.get_eos_data_manager",
                        return_value=mock_eos_data_manager,
                    ):
                        with patch(
                            "aria_esi.mcp.policy.check_capability"
                        ):
                            with patch(
                                "aria_esi.services.redisq.notifications.get_notification_manager",
                                return_value=mock_notification_manager,
                            ):
                                with patch(
                                    "pathlib.Path.home"
                                ) as mock_home:
                                    mock_home.return_value.__truediv__ = (
                                        lambda self, x: mock_path
                                    )
                                    mock_path.__truediv__ = lambda self, x: mock_path

                                    # Import the actual status function
                                    from aria_esi.mcp.dispatchers.status import (
                                        register_status_tool,
                                    )

                                    # Create mock server and capture the registered function
                                    mock_server = MagicMock()
                                    status_func = None

                                    def capture_tool():
                                        def decorator(func):
                                            nonlocal status_func
                                            status_func = func
                                            return func

                                        return decorator

                                    mock_server.tool = capture_tool

                                    register_status_tool(mock_server)

                                    result = await status_func()
                                    normalized = normalize_volatile_fields(result)

                                    assert normalized == snapshot

    async def test_status_output_fields(
        self,
        mock_activity_cache,
        mock_market_cache,
        mock_market_db,
        mock_eos_data_manager,
        mock_notification_manager,
    ):
        """Verify status output contains required fields."""
        with patch(
            "aria_esi.mcp.activity.get_activity_cache",
            return_value=mock_activity_cache,
        ):
            with patch(
                "aria_esi.mcp.market.cache.get_market_cache",
                return_value=mock_market_cache,
            ):
                with patch(
                    "aria_esi.mcp.market.database.get_market_database",
                    return_value=mock_market_db,
                ):
                    with patch(
                        "aria_esi.fitting.get_eos_data_manager",
                        return_value=mock_eos_data_manager,
                    ):
                        with patch(
                            "aria_esi.mcp.policy.check_capability"
                        ):
                            with patch(
                                "aria_esi.services.redisq.notifications.get_notification_manager",
                                return_value=mock_notification_manager,
                            ):
                                from aria_esi.mcp.dispatchers.status import (
                                    register_status_tool,
                                )

                                mock_server = MagicMock()
                                status_func = None

                                def capture_tool():
                                    def decorator(func):
                                        nonlocal status_func
                                        status_func = func
                                        return func

                                    return decorator

                                mock_server.tool = capture_tool

                                register_status_tool(mock_server)

                                result = await status_func()

                                # Required top-level sections
                                assert "activity" in result
                                assert "market" in result
                                assert "sde" in result
                                assert "fitting" in result
                                assert "summary" in result

                                # Activity subsections
                                assert "kills" in result["activity"]
                                assert "jumps" in result["activity"]
                                assert "fw" in result["activity"]

                                # Summary fields
                                assert "all_healthy" in result["summary"]
                                assert "issues" in result["summary"]

    async def test_status_healthy_system(
        self,
        mock_activity_cache,
        mock_market_cache,
        mock_market_db,
        mock_eos_data_manager,
        mock_notification_manager,
    ):
        """Verify status reports healthy when all systems are working."""
        with patch(
            "aria_esi.mcp.activity.get_activity_cache",
            return_value=mock_activity_cache,
        ):
            with patch(
                "aria_esi.mcp.market.cache.get_market_cache",
                return_value=mock_market_cache,
            ):
                with patch(
                    "aria_esi.mcp.market.database.get_market_database",
                    return_value=mock_market_db,
                ):
                    with patch(
                        "aria_esi.fitting.get_eos_data_manager",
                        return_value=mock_eos_data_manager,
                    ):
                        with patch(
                            "aria_esi.mcp.policy.check_capability"
                        ):
                            with patch(
                                "aria_esi.services.redisq.notifications.get_notification_manager",
                                return_value=mock_notification_manager,
                            ):
                                from aria_esi.mcp.dispatchers.status import (
                                    register_status_tool,
                                )

                                mock_server = MagicMock()
                                status_func = None

                                def capture_tool():
                                    def decorator(func):
                                        nonlocal status_func
                                        status_func = func
                                        return func

                                    return decorator

                                mock_server.tool = capture_tool

                                register_status_tool(mock_server)

                                result = await status_func()

                                assert result["summary"]["all_healthy"] is True
                                assert len(result["summary"]["issues"]) == 0


@pytest.mark.asyncio
class TestRouteOutputGolden:
    """Golden tests for universe route action outputs."""

    @pytest.mark.skipif(
        True, reason="Requires mock universe graph - placeholder for implementation"
    )
    async def test_route_output_structure(
        self, snapshot, normalize_volatile_fields, mock_route_input
    ):
        """Verify route output maintains consistent structure."""
        # Import here to avoid loading universe graph unless test runs
        from aria_esi.mcp.dispatchers.universe import _route

        result = await _route(
            origin=mock_route_input["origin"],
            destination=mock_route_input["destination"],
            mode=mock_route_input["mode"],
            avoid_systems=None,
        )
        normalized = normalize_volatile_fields(result)

        # Snapshot assertion - structure should match previous runs
        assert normalized == snapshot

    @pytest.mark.skipif(
        True, reason="Requires mock universe graph - placeholder for implementation"
    )
    async def test_route_output_fields(self, mock_route_input):
        """Verify route output contains required fields."""
        from aria_esi.mcp.dispatchers.universe import _route

        result = await _route(
            origin=mock_route_input["origin"],
            destination=mock_route_input["destination"],
            mode=mock_route_input["mode"],
            avoid_systems=None,
        )

        # Required fields for route output
        assert "origin" in result
        assert "destination" in result
        assert "total_jumps" in result
        assert "mode" in result


@pytest.mark.asyncio
class TestMarketOutputGolden:
    """Golden tests for market dispatcher outputs."""

    @pytest.mark.skipif(
        True, reason="Requires mock market cache - placeholder for implementation"
    )
    async def test_prices_output_structure(
        self, snapshot, normalize_volatile_fields, mock_prices_input
    ):
        """Verify prices output maintains consistent structure."""
        from aria_esi.mcp.dispatchers.market import _prices

        result = await _prices(
            items=mock_prices_input["items"],
            region=mock_prices_input["region"],
            station_only=True,
        )
        normalized = normalize_volatile_fields(result)

        assert normalized == snapshot

    @pytest.mark.skipif(
        True, reason="Requires mock market cache - placeholder for implementation"
    )
    async def test_prices_output_fields(self, mock_prices_input):
        """Verify prices output contains required fields."""
        from aria_esi.mcp.dispatchers.market import _prices

        result = await _prices(
            items=mock_prices_input["items"],
            region=mock_prices_input["region"],
            station_only=True,
        )

        # Required fields for prices output
        assert "items" in result
        assert "region" in result
        assert "freshness" in result


@pytest.mark.asyncio
class TestFittingOutputGolden:
    """Golden tests for fitting dispatcher outputs."""

    @pytest.mark.skipif(
        True, reason="Requires EOS data - placeholder for implementation"
    )
    async def test_fitting_output_structure(
        self, snapshot, normalize_volatile_fields, mock_fitting_eft
    ):
        """Verify fitting output maintains consistent structure."""
        from aria_esi.mcp.dispatchers.fitting import _calculate_stats

        result = await _calculate_stats(
            eft=mock_fitting_eft,
            damage_profile=None,
            use_pilot_skills=False,
        )
        normalized = normalize_volatile_fields(result)

        assert normalized == snapshot

    @pytest.mark.skipif(
        True, reason="Requires EOS data - placeholder for implementation"
    )
    async def test_fitting_output_sections(self, mock_fitting_eft):
        """Verify fitting output contains required sections."""
        from aria_esi.mcp.dispatchers.fitting import _calculate_stats

        result = await _calculate_stats(
            eft=mock_fitting_eft,
            damage_profile=None,
            use_pilot_skills=False,
        )

        # Check for error or expected sections
        if "error" not in result:
            # Required sections for successful fit calculation
            assert "ship" in result
            assert "dps" in result or "tank" in result


@pytest.mark.asyncio
class TestSDEOutputGolden:
    """Golden tests for SDE dispatcher outputs."""

    @pytest.mark.skipif(
        True, reason="Requires SDE database - placeholder for implementation"
    )
    async def test_item_info_output_structure(self, snapshot, normalize_volatile_fields):
        """Verify item_info output maintains consistent structure."""
        from aria_esi.mcp.dispatchers.sde import _item_info

        result = await _item_info(item="Tritanium")
        normalized = normalize_volatile_fields(result)

        assert normalized == snapshot

    @pytest.mark.skipif(
        True, reason="Requires SDE database - placeholder for implementation"
    )
    async def test_item_info_output_fields(self):
        """Verify item_info output contains required fields."""
        from aria_esi.mcp.dispatchers.sde import _item_info

        result = await _item_info(item="Tritanium")

        # Required fields for item_info output
        assert "found" in result
        assert "query" in result
        if result.get("found"):
            assert "item" in result
            assert result["item"].get("type_id") is not None
            assert result["item"].get("type_name") is not None


@pytest.mark.asyncio
class TestActivityOutputGolden:
    """Golden tests for universe activity action outputs."""

    @pytest.mark.skipif(
        True, reason="Requires activity cache - placeholder for implementation"
    )
    async def test_activity_output_structure(
        self, snapshot, normalize_volatile_fields, mock_system_activity_input
    ):
        """Verify activity output maintains consistent structure."""
        from aria_esi.mcp.dispatchers.universe import _activity

        result = await _activity(systems=mock_system_activity_input["systems"])
        normalized = normalize_volatile_fields(result)

        assert normalized == snapshot

    @pytest.mark.skipif(
        True, reason="Requires activity cache - placeholder for implementation"
    )
    async def test_activity_output_fields(self, mock_system_activity_input):
        """Verify activity output contains required fields."""
        from aria_esi.mcp.dispatchers.universe import _activity

        result = await _activity(systems=mock_system_activity_input["systems"])

        # Required fields for activity output
        assert "systems" in result
        assert "data_period" in result


# =============================================================================
# Output Quality Validation Tests
# =============================================================================


class TestOutputQuality:
    """Tests for output quality standards (non-snapshot)."""

    def test_normalize_volatile_fields_removes_timestamps(self, normalize_volatile_fields):
        """Verify normalizer removes volatile timestamps."""
        input_data = {
            "result": "success",
            "cache_age_seconds": 123,
            "timestamp": "2024-01-01T00:00:00Z",
            "nested": {"issued": "2024-01-01"},
        }

        normalized = normalize_volatile_fields(input_data)

        assert normalized["cache_age_seconds"] == "<NORMALIZED>"
        assert normalized["timestamp"] == "<NORMALIZED>"
        assert normalized["nested"]["issued"] == "<NORMALIZED>"
        assert normalized["result"] == "success"

    def test_normalize_volatile_fields_preserves_structure(self, normalize_volatile_fields):
        """Verify normalizer preserves non-volatile data structure."""
        input_data = {
            "items": [
                {"name": "Tritanium", "price": 5.5},
                {"name": "Pyerite", "price": 10.0},
            ],
            "total": 2,
        }

        normalized = normalize_volatile_fields(input_data)

        assert normalized == input_data  # Should be unchanged
