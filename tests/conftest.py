"""
ARIA Test Suite - Shared Fixtures and Configuration

This module sets up the Python path to import aria_esi from .claude/scripts/
and provides shared fixtures for all tests.

STP-012: Testing & Deployment
"""

# CRITICAL: Disable keyring BEFORE any imports that might trigger it.
# On Linux, the keyring module tries to contact Secret Service via D-Bus
# at import time. If D-Bus is unavailable or the keyring is locked,
# this call hangs indefinitely, causing the test suite to freeze.
import os
os.environ.setdefault("ARIA_NO_KEYRING", "1")

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add aria_esi package to path
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / ".claude" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# ESI fixture directory for externalized test data
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "esi"


def load_esi_fixture(path: str) -> dict:
    """
    Load a JSON fixture from the ESI fixtures directory.

    Args:
        path: Relative path within tests/fixtures/esi/, e.g., "character/location.json"

    Returns:
        Parsed JSON data as a dictionary

    Raises:
        FileNotFoundError: If fixture file doesn't exist
        json.JSONDecodeError: If fixture contains invalid JSON
    """
    fixture_path = FIXTURES_DIR / path
    return json.loads(fixture_path.read_text())


@pytest.fixture
def esi_fixture_loader():
    """
    Fixture providing the load_esi_fixture function for tests.

    Usage:
        def test_something(esi_fixture_loader):
            location = esi_fixture_loader("character/location.json")
    """
    return load_esi_fixture


# =============================================================================
# Integrity Check Fixtures
# =============================================================================


@pytest.fixture
def skip_integrity_check(monkeypatch):
    """
    Disable universe graph integrity checks for tests using temporary graphs.

    Tests that create temporary test graphs will have different checksums than
    the production graph pinned in data-sources.json. This fixture enables the
    break-glass mode that bypasses checksum verification.
    """
    monkeypatch.setenv("ARIA_ALLOW_UNPINNED", "1")


# =============================================================================
# Path Fixtures
# =============================================================================


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def scripts_dir() -> Path:
    """Return the scripts directory containing aria_esi."""
    return SCRIPTS_DIR


@pytest.fixture
def test_data_dir(tmp_path: Path) -> Path:
    """Create and return a temporary test data directory."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    return data_dir


# =============================================================================
# Mock Credentials Fixtures
# =============================================================================

@pytest.fixture
def mock_credentials_data() -> dict:
    """Return sample credentials data."""
    return {
        "character_id": 12345678,
        "access_token": "test_access_token_abc123",
        "refresh_token": "test_refresh_token_xyz789",
        "token_expiry": "2026-01-15T20:00:00Z",
        "scopes": [
            "esi-location.read_location.v1",
            "esi-wallet.read_character_wallet.v1",
            "esi-skills.read_skills.v1",
            "esi-killmails.read_killmails.v1",
        ]
    }


@pytest.fixture
def credentials_file(tmp_path: Path, mock_credentials_data: dict) -> Path:
    """Create a temporary credentials file and return its path."""
    creds_dir = tmp_path / "userdata" / "credentials"
    creds_dir.mkdir(parents=True)
    creds_file = creds_dir / "12345678.json"
    creds_file.write_text(json.dumps(mock_credentials_data))
    return creds_file


@pytest.fixture
def mock_project_with_credentials(tmp_path: Path, mock_credentials_data: dict) -> Path:
    """Create a mock project directory with credentials and config."""
    # Create directory structure
    userdata = tmp_path / "userdata"
    userdata.mkdir()
    (userdata / "credentials").mkdir()
    (userdata / "pilots").mkdir()

    # Write credentials
    creds_file = userdata / "credentials" / "12345678.json"
    creds_file.write_text(json.dumps(mock_credentials_data))

    # Write config
    config = {
        "version": "2.0",
        "active_pilot": "12345678"
    }
    config_file = userdata / "config.json"
    config_file.write_text(json.dumps(config))

    return tmp_path


# =============================================================================
# Mock ESI Response Fixtures
# =============================================================================

@pytest.fixture
def mock_system_response() -> dict:
    """Return a mock ESI system response (Jita)."""
    return {
        "constellation_id": 20000020,
        "name": "Jita",
        "planets": [],
        "position": {"x": 0, "y": 0, "z": 0},
        "security_class": "B",
        "security_status": 0.9459131360054016,
        "star_id": 40009081,
        "stargates": [50001248, 50001249],
        "system_id": 30000142
    }


@pytest.fixture
def mock_character_response() -> dict:
    """Return a mock ESI character response."""
    return {
        "alliance_id": None,
        "birthday": "2025-12-01T00:00:00Z",
        "bloodline_id": 1,
        "corporation_id": 1000125,
        "description": "Test character",
        "gender": "male",
        "name": "Test Pilot",
        "race_id": 1,
        "security_status": 1.5
    }


@pytest.fixture
def mock_location_response() -> dict:
    """Return a mock ESI location response."""
    return {
        "solar_system_id": 30000142,
        "station_id": 60003760
    }


@pytest.fixture
def mock_wallet_response() -> float:
    """Return a mock ESI wallet balance."""
    return 15000000.50


@pytest.fixture
def mock_type_response() -> dict:
    """Return a mock ESI type (item) response."""
    return {
        "capacity": 0,
        "description": "A small combat drone.",
        "group_id": 100,
        "icon_id": 21,
        "market_group_id": 837,
        "mass": 5000,
        "name": "Hobgoblin I",
        "packaged_volume": 5,
        "portion_size": 1,
        "published": True,
        "radius": 2,
        "type_id": 2454,
        "volume": 5
    }


@pytest.fixture
def mock_killmail_response() -> dict:
    """Return a mock ESI killmail response."""
    return {
        "attackers": [
            {
                "character_id": 99999999,
                "corporation_id": 1000001,
                "damage_done": 5000,
                "final_blow": True,
                "security_status": 0.5,
                "ship_type_id": 24690,
                "weapon_type_id": 3170
            }
        ],
        "killmail_id": 123456789,
        "killmail_time": "2026-01-15T18:00:00Z",
        "solar_system_id": 30002187,
        "victim": {
            "character_id": 12345678,
            "corporation_id": 1000125,
            "damage_taken": 5000,
            "items": [],
            "position": {"x": 0, "y": 0, "z": 0},
            "ship_type_id": 587
        }
    }


# =============================================================================
# Mock Client Fixtures
# =============================================================================

@pytest.fixture
def mock_esi_client():
    """Create a mock ESI client with common methods stubbed."""
    from aria_esi.core import ESIClient

    client = MagicMock(spec=ESIClient)
    client.token = None
    client.timeout = 30
    client.base_url = "https://esi.evetech.net/latest"
    client.datasource = "tranquility"

    return client


# =============================================================================
# Time Fixtures
# =============================================================================

@pytest.fixture
def fixed_datetime() -> datetime:
    """Return a fixed datetime for consistent testing."""
    return datetime(2026, 1, 15, 18, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def mock_utc_now(fixed_datetime: datetime):
    """Patch get_utc_now to return a fixed datetime."""
    with patch('aria_esi.core.formatters.get_utc_now', return_value=fixed_datetime):
        yield fixed_datetime


# Conditional import for time-machine (optional dependency)
try:
    import time_machine
    HAS_TIME_MACHINE = True
except ImportError:
    time_machine = None  # type: ignore[assignment]
    HAS_TIME_MACHINE = False


@pytest.fixture
def frozen_time(fixed_datetime: datetime):
    """
    Freeze time using time-machine for deterministic time-dependent tests.

    This provides more comprehensive time freezing than mock_utc_now, as it
    affects all time sources (datetime.now, time.time, etc.) rather than
    just the ARIA-specific get_utc_now function.

    Requires: time-machine>=2.10.0 (optional dev dependency)

    Example:
        def test_time_sensitive(frozen_time):
            # All time sources return 2026-01-15 18:30:00 UTC
            assert datetime.now(timezone.utc) == frozen_time
    """
    if not HAS_TIME_MACHINE:
        pytest.skip("time-machine not installed")

    with time_machine.travel(fixed_datetime, tick=False):
        yield fixed_datetime


# =============================================================================
# RNG Fixtures
# =============================================================================


@pytest.fixture
def seeded_rng() -> random.Random:
    """
    Return a seeded Random instance for deterministic randomness in tests.

    This provides an isolated random number generator that won't affect
    global state. Use this when you need reproducible random values.

    Example:
        def test_random_selection(seeded_rng):
            items = ["a", "b", "c"]
            selected = seeded_rng.choice(items)
            assert selected == "c"  # Deterministic with seed 42
    """
    return random.Random(42)


@pytest.fixture(autouse=False)
def seed_global_random():
    """
    Seed the global random module for test determinism.

    This is NOT autouse by default - only enable for tests that specifically
    need global random determinism. Most tests should use seeded_rng instead.

    Warning: This affects global state and may cause test interdependencies
    if used carelessly.

    Example:
        @pytest.mark.usefixtures("seed_global_random")
        def test_uses_global_random():
            assert random.randint(1, 100) == 82  # Deterministic
    """
    original_state = random.getstate()
    random.seed(42)
    yield
    random.setstate(original_state)


# =============================================================================
# Floating-Point Tolerance Helpers
# =============================================================================


def approx_sec(value: float, rel: float = 1e-4) -> pytest.approx:
    """
    Return pytest.approx configured for security status comparisons.

    Security status values have 4 decimal places of precision in ESI.

    Example:
        assert system["security"] == approx_sec(0.9459)
    """
    return pytest.approx(value, rel=rel)


def approx_isk(value: float, rel: float = 1e-6) -> pytest.approx:
    """
    Return pytest.approx configured for ISK value comparisons.

    ISK values can be large (billions) so we use tighter relative tolerance.

    Example:
        assert wallet_balance == approx_isk(15_000_000.50)
    """
    return pytest.approx(value, rel=rel)


def assert_highsec(sec: float) -> None:
    """
    Assert that a security status represents high-sec space.

    High-sec is >= 0.45 (rounds to 0.5+).

    Raises:
        AssertionError: If sec < 0.45
    """
    assert sec >= 0.45, f"Expected highsec (>=0.45), got {sec}"


def assert_lowsec(sec: float) -> None:
    """
    Assert that a security status represents low-sec space.

    Low-sec is > 0.0 and < 0.45.

    Raises:
        AssertionError: If not in lowsec range
    """
    assert 0.0 < sec < 0.45, f"Expected lowsec (0.0 < sec < 0.45), got {sec}"


def assert_nullsec(sec: float) -> None:
    """
    Assert that a security status represents null-sec space.

    Null-sec is <= 0.0.

    Raises:
        AssertionError: If sec > 0.0
    """
    assert sec <= 0.0, f"Expected nullsec (<=0.0), got {sec}"


# =============================================================================
# Argument Namespace Fixtures
# =============================================================================

@pytest.fixture
def empty_args():
    """Create an empty argparse.Namespace for command testing."""
    import argparse
    return argparse.Namespace()


@pytest.fixture
def route_args():
    """Create args for route command."""
    import argparse
    args = argparse.Namespace()
    args.origin = "Dodixie"
    args.destination = "Jita"
    args.route_flag = "shortest"
    return args


@pytest.fixture
def killmails_args():
    """Create args for killmails command."""
    import argparse
    args = argparse.Namespace()
    args.limit = 10
    args.losses = False
    args.kills = False
    return args


# =============================================================================
# Universe MCP Server Fixtures (STP-012)
# =============================================================================

@pytest.fixture(scope="session")
def sample_cache_data() -> dict:
    """
    Minimal universe cache for fast tests.

    Contains 6 systems with varying security levels:
    - Jita (0.95, highsec, The Forge)
    - Perimeter (0.90, highsec, The Forge)
    - Urlen (0.65, highsec, The Forge)
    - Sivala (0.50, highsec border, The Forge) - borders lowsec
    - Aufay (0.35, lowsec, The Forge)
    - Ala (0.20, lowsec, The Forge)
    """
    return {
        "systems": {
            "30000142": {
                "system_id": 30000142,
                "name": "Jita",
                "security": 0.9459,
                "constellation_id": 20000020,
                "stargates": [50001248]
            },
            "30000144": {
                "system_id": 30000144,
                "name": "Perimeter",
                "security": 0.9072,
                "constellation_id": 20000020,
                "stargates": [50001250, 50001251]
            },
            "30000139": {
                "system_id": 30000139,
                "name": "Urlen",
                "security": 0.6500,
                "constellation_id": 20000020,
                "stargates": [50001252, 50001253]
            },
            "30000138": {
                "system_id": 30000138,
                "name": "Sivala",
                "security": 0.5000,
                "constellation_id": 20000020,
                "stargates": [50001254, 50001255]
            },
            "30000137": {
                "system_id": 30000137,
                "name": "Aufay",
                "security": 0.3500,
                "constellation_id": 20000021,
                "stargates": [50001256]
            },
            "30000136": {
                "system_id": 30000136,
                "name": "Ala",
                "security": 0.2000,
                "constellation_id": 20000021,
                "stargates": [50001257]
            }
        },
        "stargates": {
            "50001248": {"destination_system_id": 30000144},  # Jita -> Perimeter
            "50001250": {"destination_system_id": 30000142},  # Perimeter -> Jita
            "50001251": {"destination_system_id": 30000139},  # Perimeter -> Urlen
            "50001252": {"destination_system_id": 30000144},  # Urlen -> Perimeter
            "50001253": {"destination_system_id": 30000138},  # Urlen -> Sivala
            "50001254": {"destination_system_id": 30000139},  # Sivala -> Urlen
            "50001255": {"destination_system_id": 30000137},  # Sivala -> Aufay
            "50001256": {"destination_system_id": 30000138},  # Aufay -> Sivala
            "50001257": {"destination_system_id": 30000137}   # Ala -> Aufay (dead end)
        },
        "constellations": {
            "20000020": {"name": "Kimotoro", "region_id": 10000002},
            "20000021": {"name": "Okkelen", "region_id": 10000002}
        },
        "regions": {
            "10000002": {"name": "The Forge"}
        },
        "generated": "test-1.0"
    }


@pytest.fixture(scope="session")
def sample_cache_path(tmp_path_factory, sample_cache_data) -> Path:
    """Create minimal universe cache JSON for fast tests."""
    path = tmp_path_factory.mktemp("data") / "universe_cache.json"
    path.write_text(json.dumps(sample_cache_data))
    return path


@pytest.fixture(scope="session")
def sample_graph(sample_cache_path, tmp_path_factory):
    """Build sample graph from cache for testing."""
    from aria_esi.universe.builder import build_universe_graph

    output = tmp_path_factory.mktemp("data") / "universe.universe"
    return build_universe_graph(sample_cache_path, output)


@pytest.fixture(scope="session")
def sample_graph_path(sample_graph, tmp_path_factory) -> Path:
    """Path to sample graph in safe format."""
    from aria_esi.universe.serialization import save_universe_graph

    path = tmp_path_factory.mktemp("graphs") / "universe.universe"
    save_universe_graph(sample_graph, path)
    return path


@pytest.fixture
def mock_server(sample_graph_path):
    """Create mock server with sample graph."""
    from aria_esi.mcp.server import UniverseServer

    server = UniverseServer(graph_path=sample_graph_path)
    server.load_graph(skip_integrity_check=True)
    server.register_tools()
    return server


@pytest.fixture(scope="session")
def real_graph_path() -> Path | None:
    """Path to real universe graph if available."""
    # Data directory is in src/aria_esi/data
    data_dir = PROJECT_ROOT / "src" / "aria_esi" / "data"

    new_path = data_dir / "universe.universe"
    if new_path.exists():
        return new_path
    return None


@pytest.fixture(scope="session")
def real_universe(real_graph_path):
    """Load real universe graph if available."""
    if real_graph_path is None:
        pytest.skip("Real universe graph not available")
    from aria_esi.universe.builder import load_universe_graph
    return load_universe_graph(real_graph_path)


# =============================================================================
# Singleton Reset Fixtures
# =============================================================================

# =============================================================================
# ESI Command Test Fixtures
# =============================================================================


@pytest.fixture
def mock_blueprint_response():
    """Sample blueprint data with BPO and BPC."""
    return [
        {
            "item_id": 1001,
            "type_id": 687,  # Rifter Blueprint
            "quantity": -1,  # BPO indicator
            "material_efficiency": 10,
            "time_efficiency": 20,
            "runs": -1,
            "location_id": 60003760,
            "location_flag": "Hangar",
        },
        {
            "item_id": 1002,
            "type_id": 688,  # Slasher Blueprint
            "quantity": -2,  # BPC indicator
            "material_efficiency": 0,
            "time_efficiency": 0,
            "runs": 10,
            "location_id": 60003760,
            "location_flag": "Hangar",
        },
    ]


@pytest.fixture
def mock_fitting_assets_response():
    """Fitted ship with modules and drones."""
    return [
        # Ship in hangar
        {
            "item_id": 1001,
            "type_id": 587,  # Rifter
            "location_id": 60003760,
            "location_type": "station",
            "location_flag": "Hangar",
            "is_singleton": True,
            "quantity": 1,
        },
        # Low slot module fitted to ship
        {
            "item_id": 1002,
            "type_id": 2046,  # Damage Control
            "location_id": 1001,  # Located in ship
            "location_type": "item",
            "location_flag": "LoSlot0",
            "is_singleton": True,
            "quantity": 1,
        },
        # Med slot module
        {
            "item_id": 1003,
            "type_id": 527,  # 1MN Afterburner
            "location_id": 1001,
            "location_type": "item",
            "location_flag": "MedSlot0",
            "is_singleton": True,
            "quantity": 1,
        },
        # High slot module
        {
            "item_id": 1004,
            "type_id": 2881,  # 150mm Autocannon
            "location_id": 1001,
            "location_type": "item",
            "location_flag": "HiSlot0",
            "is_singleton": True,
            "quantity": 1,
        },
        # Rig slot
        {
            "item_id": 1005,
            "type_id": 31117,  # Small Projectile Burst Aerator I
            "location_id": 1001,
            "location_type": "item",
            "location_flag": "RigSlot0",
            "is_singleton": True,
            "quantity": 1,
        },
        # Drones in drone bay
        {
            "item_id": 1006,
            "type_id": 2454,  # Hobgoblin I
            "location_id": 1001,
            "location_type": "item",
            "location_flag": "DroneBay",
            "is_singleton": False,
            "quantity": 5,
        },
        # Cargo item
        {
            "item_id": 1007,
            "type_id": 34,  # Tritanium
            "location_id": 1001,
            "location_type": "item",
            "location_flag": "Cargo",
            "is_singleton": False,
            "quantity": 100,
        },
    ]


@pytest.fixture
def mock_contract_items_response():
    """Contract items payload."""
    return [
        {"type_id": 34, "quantity": 1000, "is_included": True, "is_singleton": False},
        {"type_id": 35, "quantity": 500, "is_included": True, "is_singleton": False},
    ]


@pytest.fixture
def mock_contract_bids_response():
    """Contract bid history for auctions."""
    return [
        {
            "bid_id": 1,
            "bidder_id": 98765432,
            "amount": 5000000,
            "date_bid": "2026-01-20T12:00:00Z",
        },
        {
            "bid_id": 2,
            "bidder_id": 87654321,
            "amount": 3000000,
            "date_bid": "2026-01-19T12:00:00Z",
        },
    ]


@pytest.fixture(autouse=True)
def reset_all_singletons():
    """
    Reset all module-level singletons between tests.

    This fixture runs automatically before and after each test to ensure
    clean state and prevent cross-test contamination. It resets:

    Core services:
    - Settings cache (MUST be first - other modules read from settings)
    - Market database connections (sync and async)
    - Market cache and refresh service
    - YAML configuration caches (Easy 80%, activities)
    - Skill requirements cache
    - EOS data manager
    - Universe graph reference
    - Activity caches (MCP and navigation)
    - Arbitrage engine
    - History cache service
    - SDE query service
    - Keyring credential store
    - Context budget
    - Async ESI client

    RedisQ services:
    - Name resolver
    - War context provider
    - Realtime database
    - Interest providers registry
    - Preset loader
    - Threat cache
    - Notification manager
    - NPC faction mapper
    - Persona loader
    - Entity watchlist manager
    - Fetch queue
    - Poller
    - Entity filter

    MCP services:
    - Trace context

    Note: Some imports may fail if optional dependencies aren't installed.
    Each reset is wrapped in a try/except to allow partial resets.
    """
    def do_reset():
        # Settings cache (MUST be first - other modules read from settings)
        try:
            from aria_esi.core.config import reset_settings
            reset_settings()
        except ImportError:
            pass

        # Logging state (reset early - affects propagation for caplog)
        try:
            from aria_esi.core.logging import reset_logging
            reset_logging()
        except ImportError:
            pass

        # Market database
        try:
            from aria_esi.mcp.market.database import reset_market_database
            reset_market_database()
        except ImportError:
            pass

        # Async market database (sync reset for non-async context)
        try:
            from aria_esi.mcp.market.database_async import reset_async_market_database_sync
            reset_async_market_database_sync()
        except ImportError:
            pass

        # Market cache
        try:
            from aria_esi.mcp.market.cache import reset_market_cache
            reset_market_cache()
        except ImportError:
            pass

        # Market refresh service
        try:
            from aria_esi.services.market_refresh import reset_refresh_service
            reset_refresh_service()
        except ImportError:
            pass

        # Easy 80% YAML caches
        try:
            from aria_esi.mcp.sde.tools_easy80 import reset_easy80_caches
            reset_easy80_caches()
        except ImportError:
            pass

        # Activities cache
        try:
            from aria_esi.mcp.sde.tools_activities import reset_activities_cache
            reset_activities_cache()
        except ImportError:
            pass

        # Skill requirements cache
        try:
            from aria_esi.fitting.skills import reset_skill_requirements
            reset_skill_requirements()
        except ImportError:
            pass

        # EOS data manager
        try:
            from aria_esi.fitting.eos_data import reset_eos_data_manager
            reset_eos_data_manager()
        except ImportError:
            pass

        # Universe graph
        try:
            from aria_esi.mcp.tools import reset_universe
            reset_universe()
        except ImportError:
            pass

        # MCP activity cache
        try:
            from aria_esi.mcp.activity import reset_activity_cache
            reset_activity_cache()
        except ImportError:
            pass

        # Navigation activity cache
        try:
            from aria_esi.commands.navigation import reset_navigation_activity_cache
            reset_navigation_activity_cache()
        except ImportError:
            pass

        # Arbitrage engine
        try:
            from aria_esi.services.arbitrage_engine import reset_arbitrage_engine
            reset_arbitrage_engine()
        except ImportError:
            pass

        # History cache service
        try:
            from aria_esi.services.history_cache import reset_history_cache_service
            reset_history_cache_service()
        except ImportError:
            pass

        # SDE query service
        try:
            from aria_esi.mcp.sde.queries import reset_sde_query_service
            reset_sde_query_service()
        except ImportError:
            pass

        # Keyring credential store
        try:
            from aria_esi.core.keyring_backend import reset_keyring_store
            reset_keyring_store()
        except ImportError:
            pass

        # Universe JSON cache
        try:
            from aria_esi.cache import clear_cache
            clear_cache()
        except ImportError:
            pass

        # Context budget
        try:
            from aria_esi.mcp.context_budget import reset_context_budget
            reset_context_budget()
        except ImportError:
            pass

        # Async ESI client singleton
        try:
            from aria_esi.mcp.esi_client import reset_async_esi_client
            reset_async_esi_client()
        except ImportError:
            pass

        # RedisQ - Name resolver
        try:
            from aria_esi.services.redisq.name_resolver import reset_name_resolver
            reset_name_resolver()
        except ImportError:
            pass

        # RedisQ - War context provider
        try:
            from aria_esi.services.redisq.war_context import reset_war_context_provider
            reset_war_context_provider()
        except ImportError:
            pass

        # RedisQ - Realtime database
        try:
            from aria_esi.services.redisq.database import reset_realtime_database
            reset_realtime_database()
        except ImportError:
            pass

        # RedisQ - Interest providers registry
        try:
            from aria_esi.services.redisq.interest_v2.providers.registry import reset_registry
            reset_registry()
        except ImportError:
            pass

        # RedisQ - Preset loader
        try:
            from aria_esi.services.redisq.interest_v2.presets.loader import reset_preset_loader
            reset_preset_loader()
        except ImportError:
            pass

        # RedisQ - Threat cache
        try:
            from aria_esi.services.redisq.threat_cache import reset_threat_cache
            reset_threat_cache()
        except ImportError:
            pass

        # RedisQ - Notification manager
        try:
            from aria_esi.services.redisq.notifications.manager import reset_notification_manager
            reset_notification_manager()
        except ImportError:
            pass

        # RedisQ - NPC faction mapper
        try:
            from aria_esi.services.redisq.notifications.npc_factions import reset_npc_faction_mapper
            reset_npc_faction_mapper()
        except ImportError:
            pass

        # RedisQ - Persona loader
        try:
            from aria_esi.services.redisq.notifications.persona import reset_persona_loader
            reset_persona_loader()
        except ImportError:
            pass

        # RedisQ - Entity watchlist manager
        try:
            from aria_esi.services.redisq.entity_watchlist import reset_entity_watchlist_manager
            reset_entity_watchlist_manager()
        except ImportError:
            pass

        # RedisQ - Fetch queue
        try:
            from aria_esi.services.redisq.fetch_queue import reset_fetch_queue
            reset_fetch_queue()
        except ImportError:
            pass

        # RedisQ - Poller
        try:
            from aria_esi.services.redisq.poller import reset_poller
            reset_poller()
        except ImportError:
            pass

        # RedisQ - Entity filter
        try:
            from aria_esi.services.redisq.entity_filter import reset_entity_filter
            reset_entity_filter()
        except ImportError:
            pass

        # MCP - Trace context
        try:
            from aria_esi.mcp.context import reset_trace_context
            reset_trace_context()
        except ImportError:
            pass

    # Reset before test
    do_reset()

    yield

    # Reset after test
    do_reset()
