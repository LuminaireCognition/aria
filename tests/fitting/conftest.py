"""
Shared Test Fixtures for Fitting Module Tests.

Provides:
- ParsedFit fixtures
- EFT string fixtures
- Mock market database
- Mock ESI responses
- Mock EOS data manager
- Mock EOS module
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock

import pytest

from aria_esi.models.fitting import (
    CapacitorStats,
    DPSBreakdown,
    DroneStats,
    FitStatsResult,
    LayerStats,
    MobilityStats,
    ParsedDrone,
    ParsedFit,
    ParsedModule,
    ResistProfile,
    ResourceUsage,
    SlotUsage,
    TankStats,
)

# =============================================================================
# Type Resolution Helper
# =============================================================================


class TypeInfo(NamedTuple):
    """Simple type info for testing."""

    type_id: int
    type_name: str


# =============================================================================
# Parsed Fit Fixtures
# =============================================================================


@pytest.fixture
def vexor_parsed_fit() -> ParsedFit:
    """
    A standard Vexor fit with DDAs, AB, and drones.

    Modules:
    - 3x Drone Damage Amplifier II (low)
    - 1x 10MN Afterburner II (mid)
    - 1x Drone Link Augmentor I (high)

    Rigs:
    - 3x Medium Auxiliary Nano Pump I

    Drones:
    - 5x Hammerhead II
    - 5x Hobgoblin II
    """
    return ParsedFit(
        ship_type_id=626,
        ship_type_name="Vexor",
        fit_name="My PvE Fit",
        low_slots=[
            ParsedModule(type_id=4405, type_name="Drone Damage Amplifier II"),
            ParsedModule(type_id=4405, type_name="Drone Damage Amplifier II"),
            ParsedModule(type_id=4405, type_name="Drone Damage Amplifier II"),
        ],
        mid_slots=[
            ParsedModule(type_id=12058, type_name="10MN Afterburner II"),
        ],
        high_slots=[
            ParsedModule(type_id=4393, type_name="Drone Link Augmentor I"),
        ],
        rigs=[
            ParsedModule(type_id=31718, type_name="Medium Auxiliary Nano Pump I"),
            ParsedModule(type_id=31718, type_name="Medium Auxiliary Nano Pump I"),
            ParsedModule(type_id=31718, type_name="Medium Auxiliary Nano Pump I"),
        ],
        drones=[
            ParsedDrone(type_id=2185, type_name="Hammerhead II", quantity=5),
            ParsedDrone(type_id=2456, type_name="Hobgoblin II", quantity=5),
        ],
    )


@pytest.fixture
def fit_with_offline_module() -> ParsedFit:
    """Fit with an offline module."""
    return ParsedFit(
        ship_type_id=626,
        ship_type_name="Vexor",
        fit_name="Offline Test",
        low_slots=[
            ParsedModule(type_id=4405, type_name="Drone Damage Amplifier II", is_offline=True),
        ],
    )


@pytest.fixture
def fit_with_charges() -> ParsedFit:
    """Fit with modules that have charges loaded."""
    return ParsedFit(
        ship_type_id=621,
        ship_type_name="Caracal",
        fit_name="Missile Test",
        high_slots=[
            ParsedModule(
                type_id=19739,
                type_name="Rapid Light Missile Launcher II",
                charge_type_id=27361,
                charge_name="Scourge Fury Light Missile",
            ),
        ],
    )


@pytest.fixture
def minimal_fit() -> ParsedFit:
    """Minimal fit with just ship, no modules."""
    return ParsedFit(
        ship_type_id=626,
        ship_type_name="Vexor",
        fit_name="Empty Vexor",
    )


@pytest.fixture
def t3_fit_with_subsystems() -> ParsedFit:
    """T3 Cruiser fit with subsystems."""
    return ParsedFit(
        ship_type_id=29984,
        ship_type_name="Tengu",
        fit_name="T3 Test",
        subsystems=[
            ParsedModule(type_id=30118, type_name="Tengu Defensive - Amplification Node"),
            ParsedModule(type_id=30119, type_name="Tengu Offensive - Accelerated Ejection Bay"),
            ParsedModule(type_id=30120, type_name="Tengu Propulsion - Chassis Optimization"),
            ParsedModule(type_id=30121, type_name="Tengu Core - Augmented Graviton Reactor"),
        ],
    )


# =============================================================================
# EFT String Fixtures
# =============================================================================


@pytest.fixture
def eft_vexor_string() -> str:
    """Standard Vexor fit in EFT format."""
    return """[Vexor, My PvE Fit]
Drone Damage Amplifier II
Drone Damage Amplifier II
Drone Damage Amplifier II

10MN Afterburner II

Drone Link Augmentor I

Medium Auxiliary Nano Pump I
Medium Auxiliary Nano Pump I
Medium Auxiliary Nano Pump I

Hammerhead II x5
Hobgoblin II x5
"""


@pytest.fixture
def eft_with_offline_module() -> str:
    """EFT fit with offline module."""
    return """[Vexor, Offline Test]
Drone Damage Amplifier II /OFFLINE
"""


@pytest.fixture
def eft_with_charge() -> str:
    """EFT fit with module and charge."""
    # EFT format: low -> mid -> high (separated by blank lines)
    # Need [empty slot] markers to start sections before blank lines advance them
    return """[Caracal, Missile Test]
[empty low slot]

[empty med slot]

Rapid Light Missile Launcher II, Scourge Fury Light Missile
"""


@pytest.fixture
def eft_with_empty_slots() -> str:
    """EFT fit with empty slot markers."""
    return """[Vexor, Empty Slots]
Drone Damage Amplifier II
[empty low slot]
[empty low slot]

[empty med slot]

[empty high slot]
"""


@pytest.fixture
def eft_invalid_no_header() -> str:
    """Invalid EFT - missing header."""
    return """Drone Damage Amplifier II
10MN Afterburner II
"""


@pytest.fixture
def eft_malformed_header() -> str:
    """Invalid EFT - malformed header."""
    return """[Vexor My Fit]
Drone Damage Amplifier II
"""


# =============================================================================
# Mock Market Database
# =============================================================================


@pytest.fixture
def mock_market_db():
    """
    Mock MarketDatabase for type name resolution.

    Supports basic type lookups without requiring actual database.
    """
    # Type data for common items
    type_data = {
        "vexor": TypeInfo(626, "Vexor"),
        "caracal": TypeInfo(621, "Caracal"),
        "tengu": TypeInfo(29984, "Tengu"),
        "drone damage amplifier ii": TypeInfo(4405, "Drone Damage Amplifier II"),
        "10mn afterburner ii": TypeInfo(12058, "10MN Afterburner II"),
        "drone link augmentor i": TypeInfo(4393, "Drone Link Augmentor I"),
        "medium auxiliary nano pump i": TypeInfo(31718, "Medium Auxiliary Nano Pump I"),
        "hammerhead ii": TypeInfo(2185, "Hammerhead II"),
        "hobgoblin ii": TypeInfo(2456, "Hobgoblin II"),
        "rapid light missile launcher ii": TypeInfo(19739, "Rapid Light Missile Launcher II"),
        "scourge fury light missile": TypeInfo(27361, "Scourge Fury Light Missile"),
        "tengu defensive - amplification node": TypeInfo(30118, "Tengu Defensive - Amplification Node"),
        "tengu offensive - accelerated ejection bay": TypeInfo(
            30119, "Tengu Offensive - Accelerated Ejection Bay"
        ),
        "tengu propulsion - chassis optimization": TypeInfo(
            30120, "Tengu Propulsion - Chassis Optimization"
        ),
        "tengu core - augmented graviton reactor": TypeInfo(
            30121, "Tengu Core - Augmented Graviton Reactor"
        ),
    }

    mock_db = MagicMock()

    def resolve_type_name(name: str) -> TypeInfo | None:
        return type_data.get(name.lower())

    def find_type_suggestions(name: str) -> list[str]:
        # Return similar names for fuzzy matching
        suggestions = []
        name_lower = name.lower()
        for key, info in type_data.items():
            if name_lower in key or key in name_lower:
                suggestions.append(info.type_name)
        return suggestions[:5]

    mock_db.resolve_type_name = resolve_type_name
    mock_db.find_type_suggestions = find_type_suggestions

    return mock_db


@pytest.fixture
def in_memory_market_db(tmp_path: Path):
    """
    Create an in-memory SQLite database with type data.

    For tests that need actual database queries.
    """
    db_path = tmp_path / "market.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create types table
    cursor.execute("""
        CREATE TABLE types (
            type_id INTEGER PRIMARY KEY,
            type_name TEXT NOT NULL,
            group_id INTEGER,
            category_id INTEGER,
            market_group_id INTEGER,
            volume REAL,
            is_blueprint INTEGER DEFAULT 0
        )
    """)

    # Insert test types
    types = [
        (626, "Vexor", 26, 6, 602, 10000),
        (621, "Caracal", 26, 6, 601, 10000),
        (4405, "Drone Damage Amplifier II", 645, 7, 935, 5),
        (12058, "10MN Afterburner II", 46, 7, 133, 5),
        (4393, "Drone Link Augmentor I", 646, 7, 939, 5),
        (31718, "Medium Auxiliary Nano Pump I", 787, 7, 1037, 20),
        (2185, "Hammerhead II", 1023, 18, 838, 10),
        (2456, "Hobgoblin II", 1023, 18, 837, 5),
    ]

    cursor.executemany(
        "INSERT INTO types (type_id, type_name, group_id, category_id, market_group_id, volume) VALUES (?, ?, ?, ?, ?, ?)",
        types,
    )

    conn.commit()
    conn.close()

    return db_path


# =============================================================================
# Mock ESI Responses
# =============================================================================


@pytest.fixture
def mock_esi_skills_response() -> dict:
    """
    Mock ESI skills endpoint response.

    Contains a subset of common skills for testing.
    """
    return {
        "skills": [
            {"skill_id": 3332, "trained_skill_level": 5},  # Gallente Cruiser
            {"skill_id": 3436, "trained_skill_level": 5},  # Drones
            {"skill_id": 3442, "trained_skill_level": 4},  # Drone Navigation
            {"skill_id": 3443, "trained_skill_level": 3},  # Drone Interfacing
            {"skill_id": 33699, "trained_skill_level": 5},  # Medium Drone Operation
            {"skill_id": 3392, "trained_skill_level": 5},  # Mechanics
            {"skill_id": 3393, "trained_skill_level": 4},  # Hull Upgrades
            {"skill_id": 3318, "trained_skill_level": 5},  # Weapon Upgrades
            {"skill_id": 3426, "trained_skill_level": 4},  # Capacitor Systems Operation
            {"skill_id": 3449, "trained_skill_level": 5},  # Navigation
        ],
        "total_sp": 5000000,
        "unallocated_sp": 0,
    }


@pytest.fixture
def mock_empty_skills_response() -> dict:
    """Mock ESI response for character with no skills."""
    return {
        "skills": [],
        "total_sp": 0,
        "unallocated_sp": 0,
    }


# =============================================================================
# Mock EOS Data Manager
# =============================================================================


@pytest.fixture
def mock_eos_data_path(tmp_path: Path) -> Path:
    """
    Create a mock EOS data directory structure.

    Creates the expected directory layout with minimal placeholder files.
    """
    data_path = tmp_path / "eos-data"
    data_path.mkdir()

    # Create subdirectories
    fsd_built = data_path / "fsd_built"
    fsd_built.mkdir()

    fsd_lite = data_path / "fsd_lite"
    fsd_lite.mkdir()

    phobos = data_path / "phobos"
    phobos.mkdir()

    # Create required fsd_built files
    (fsd_built / "types.json").write_text("{}")
    (fsd_built / "groups.json").write_text("{}")
    (fsd_built / "categories.json").write_text("{}")
    (fsd_built / "dogmaattributes.json").write_text("{}")
    (fsd_built / "dogmaeffects.json").write_text("{}")
    (fsd_built / "typedogma.json").write_text("{}")

    # Create optional fsd_built files
    (fsd_built / "requiredskillsfortypes.json").write_text("{}")

    # Create required fsd_lite files
    (fsd_lite / "fighterabilitiesbytype.json").write_text("{}")

    # Create phobos metadata
    metadata = [
        {"field_name": "client_build", "field_value": 2564511}
    ]
    (phobos / "metadata.json").write_text(json.dumps(metadata))

    return data_path


@pytest.fixture
def incomplete_eos_data_path(tmp_path: Path) -> Path:
    """
    Create an incomplete EOS data directory (missing required files).
    """
    data_path = tmp_path / "eos-data-incomplete"
    data_path.mkdir()

    fsd_built = data_path / "fsd_built"
    fsd_built.mkdir()

    # Only create some files (missing types.json, dogmaeffects.json)
    (fsd_built / "groups.json").write_text("{}")
    (fsd_built / "categories.json").write_text("{}")

    return data_path


# =============================================================================
# Mock EOS Module
# =============================================================================


@pytest.fixture
def mock_eos_module():
    """
    Full mock of the EOS library for tests without EOS installed.

    Provides:
    - State enum (online, offline, active)
    - Fit class with mock stats
    - Ship, Skill, Module*, Drone, Rig, Subsystem classes
    - SourceManager
    - DmgProfile
    """
    mock_eos = MagicMock()

    # State enum
    mock_eos.State = MagicMock()
    mock_eos.State.online = "online"
    mock_eos.State.offline = "offline"
    mock_eos.State.active = "active"

    # Restriction enum
    mock_eos.Restriction = MagicMock()
    mock_eos.Restriction.skill_requirement = "skill_requirement"
    mock_eos.Restriction.launched_drone = "launched_drone"

    # DmgProfile
    mock_eos.DmgProfile = MagicMock()

    def create_mock_fit():
        """Create a mock Fit object with stats."""
        fit = MagicMock()

        # Ship with attrs that return numeric values
        mock_ship = MagicMock()
        # Resist attribute IDs and slot attribute IDs need actual numeric values
        # From eos_bridge.py constants:
        # Armor: 267-270, Shield: 271-274, Hull: 974-977
        # Use a real dict for attrs to ensure .get() returns proper values
        mock_ship.attrs = {
            # Armor resist attributes (267-270)
            267: 0.5,   # ATTR_ARMOR_EM_RESIST
            268: 0.35,  # ATTR_ARMOR_THERMAL_RESIST
            269: 0.25,  # ATTR_ARMOR_KINETIC_RESIST
            270: 0.1,   # ATTR_ARMOR_EXPLOSIVE_RESIST
            # Shield resist attributes (271-274)
            271: 0.0,   # ATTR_SHIELD_EM_RESIST
            272: 0.2,   # ATTR_SHIELD_THERMAL_RESIST
            273: 0.4,   # ATTR_SHIELD_KINETIC_RESIST
            274: 0.5,   # ATTR_SHIELD_EXPLOSIVE_RESIST
            # Hull resist attributes (974-977)
            974: 0.33,  # ATTR_HULL_EM_RESIST
            975: 0.33,  # ATTR_HULL_THERMAL_RESIST
            976: 0.33,  # ATTR_HULL_KINETIC_RESIST
            977: 0.33,  # ATTR_HULL_EXPLOSIVE_RESIST
            # Slot counts
            12: 5,  # lowSlots
            13: 4,  # medSlots
            14: 4,  # hiSlots
            1137: 3,  # rigSlots
            # Capacitor
            482: 1500.0,  # capacitorCapacity
            55: 300000.0,  # rechargeRate (ms)
            # Mobility
            37: 200.0,  # maxVelocity
            4: 10000000.0,  # mass
            600: 4.5,  # warpSpeedMultiplier
        }
        mock_ship.type_id = 626  # Vexor
        fit.ship = mock_ship

        # Skills
        fit.skills = MagicMock()
        fit.skills.add = MagicMock()

        # Modules
        fit.modules = MagicMock()
        fit.modules.low = MagicMock()
        fit.modules.mid = MagicMock()
        fit.modules.high = MagicMock()
        fit.modules.low.equip = MagicMock()
        fit.modules.mid.equip = MagicMock()
        fit.modules.high.equip = MagicMock()
        fit.modules.low.__iter__ = lambda self: iter([])
        fit.modules.mid.__iter__ = lambda self: iter([])
        fit.modules.high.__iter__ = lambda self: iter([])

        # Rigs and subsystems
        fit.rigs = MagicMock()
        fit.rigs.add = MagicMock()
        fit.rigs.__iter__ = lambda self: iter([])

        fit.subsystems = MagicMock()
        fit.subsystems.add = MagicMock()

        # Drones
        fit.drones = MagicMock()
        fit.drones.add = MagicMock()

        # Validate
        fit.validate = MagicMock()

        # Stats
        stats = MagicMock()

        # DPS
        dps_result = MagicMock()
        dps_result.total = 500.0
        dps_result.em = 0.0
        dps_result.thermal = 500.0
        dps_result.kinetic = 0.0
        dps_result.explosive = 0.0
        stats.get_dps = MagicMock(return_value=dps_result)

        # HP
        hp_result = MagicMock()
        hp_result.shield = 1000.0
        hp_result.armor = 2000.0
        hp_result.hull = 2000.0
        hp_result.total = 5000.0
        stats.hp = hp_result

        # EHP
        ehp_result = MagicMock()
        ehp_result.shield = 1500.0
        ehp_result.armor = 3000.0
        ehp_result.hull = 3500.0
        ehp_result.total = 8000.0
        stats.get_ehp = MagicMock(return_value=ehp_result)

        # Resources
        cpu_result = MagicMock()
        cpu_result.used = 200.0
        cpu_result.output = 375.0
        stats.cpu = cpu_result

        pg_result = MagicMock()
        pg_result.used = 250.0
        pg_result.output = 700.0
        stats.powergrid = pg_result

        cal_result = MagicMock()
        cal_result.used = 300.0
        cal_result.output = 400.0
        stats.calibration = cal_result

        # Drones
        drone_bw = MagicMock()
        drone_bw.used = 50.0
        drone_bw.output = 75.0
        stats.drone_bandwidth = drone_bw

        drone_bay = MagicMock()
        drone_bay.used = 75.0
        drone_bay.output = 125.0
        stats.dronebay = drone_bay

        launched = MagicMock()
        launched.used = 5
        launched.total = 5
        stats.launched_drones = launched

        # Mobility
        stats.agility_factor = 0.5
        stats.align_time = 7.5

        fit.stats = stats

        return fit

    # Fit factory
    mock_eos.Fit = MagicMock(side_effect=create_mock_fit)

    # Ship class - returns ship with proper attrs dict for JSON serialization
    def create_mock_ship(type_id):
        """Create a mock Ship with proper attrs."""
        ship = MagicMock()
        ship.type_id = type_id
        # Use a real dict for attrs to ensure .get() returns proper values
        ship.attrs = {
            # Armor resist attributes (267-270)
            267: 0.5,   # ATTR_ARMOR_EM_RESIST
            268: 0.35,  # ATTR_ARMOR_THERMAL_RESIST
            269: 0.25,  # ATTR_ARMOR_KINETIC_RESIST
            270: 0.1,   # ATTR_ARMOR_EXPLOSIVE_RESIST
            # Shield resist attributes (271-274)
            271: 0.0,   # ATTR_SHIELD_EM_RESIST
            272: 0.2,   # ATTR_SHIELD_THERMAL_RESIST
            273: 0.4,   # ATTR_SHIELD_KINETIC_RESIST
            274: 0.5,   # ATTR_SHIELD_EXPLOSIVE_RESIST
            # Hull resist attributes (974-977)
            974: 0.33,  # ATTR_HULL_EM_RESIST
            975: 0.33,  # ATTR_HULL_THERMAL_RESIST
            976: 0.33,  # ATTR_HULL_KINETIC_RESIST
            977: 0.33,  # ATTR_HULL_EXPLOSIVE_RESIST
            # Slot counts
            12: 5,  # lowSlots
            13: 4,  # medSlots
            14: 4,  # hiSlots
            1137: 3,  # rigSlots
            # Capacitor
            482: 1500.0,  # capacitorCapacity
            55: 300000.0,  # rechargeRate (ms)
            # Mobility
            37: 200.0,  # maxVelocity
            4: 10000000.0,  # mass
            600: 4.5,  # warpSpeedMultiplier
        }
        return ship

    mock_eos.Ship = MagicMock(side_effect=create_mock_ship)
    mock_eos.Skill = MagicMock()
    mock_eos.ModuleLow = MagicMock()
    mock_eos.ModuleMid = MagicMock()
    mock_eos.ModuleHigh = MagicMock()
    mock_eos.Drone = MagicMock()
    mock_eos.Rig = MagicMock()
    mock_eos.Subsystem = MagicMock()

    # SourceManager
    mock_eos.SourceManager = MagicMock()
    mock_eos.SourceManager.add = MagicMock()
    mock_eos.SourceManager.remove = MagicMock()
    mock_eos.SourceManager.list = MagicMock(return_value=[])

    # Data handlers
    mock_eos.JsonDataHandler = MagicMock()
    mock_eos.JsonCacheHandler = MagicMock()

    return mock_eos


# =============================================================================
# Mock Credentials
# =============================================================================


@pytest.fixture
def mock_credentials():
    """Mock ESI credentials for skill fetching tests."""
    creds = MagicMock()
    creds.character_id = 12345678
    creds.access_token = "test_access_token"
    return creds


# =============================================================================
# Mock ESI Client
# =============================================================================


@pytest.fixture
def mock_esi_client():
    """Mock ESI client for skill fetching tests."""
    from aria_esi.core import ESIClient

    client = MagicMock(spec=ESIClient)
    client.token = "test_token"
    client.get = MagicMock()
    return client


# =============================================================================
# Fit Stats Result Fixtures
# =============================================================================


@pytest.fixture
def sample_fit_stats_result() -> FitStatsResult:
    """Sample complete FitStatsResult for comparison tests."""
    return FitStatsResult(
        ship_type_id=626,
        ship_type_name="Vexor",
        fit_name="Test Fit",
        dps=DPSBreakdown(total=500.0, thermal=500.0),
        tank=TankStats(
            shield=LayerStats(hp=1000.0, ehp=1500.0, resists=ResistProfile()),
            armor=LayerStats(hp=2000.0, ehp=3000.0, resists=ResistProfile()),
            hull=LayerStats(hp=2000.0, ehp=3500.0, resists=ResistProfile()),
            total_hp=5000.0,
            total_ehp=8000.0,
        ),
        cpu=ResourceUsage(used=200.0, output=375.0),
        powergrid=ResourceUsage(used=250.0, output=700.0),
        calibration=ResourceUsage(used=300.0, output=400.0),
        capacitor=CapacitorStats(capacity=1500.0, recharge_time=300.0, recharge_rate=5.0),
        mobility=MobilityStats(
            max_velocity=200.0, agility=0.5, align_time=7.5, mass=10000000.0, warp_speed=4.5
        ),
        drones=DroneStats(
            bandwidth_used=50.0,
            bandwidth_output=75.0,
            bay_used=75.0,
            bay_output=125.0,
            drones_launched=5,
            drones_max=5,
        ),
        slots=SlotUsage(
            high_used=1,
            high_total=4,
            mid_used=1,
            mid_total=4,
            low_used=3,
            low_total=5,
            rig_used=3,
            rig_total=3,
        ),
        skill_mode="all_v",
    )


# =============================================================================
# Skill Requirements Fixtures
# =============================================================================


@pytest.fixture
def mock_skill_requirements_data() -> dict[str, dict[str, int]]:
    """
    Mock skill requirements data (requiredskillsfortypes.json format).

    Maps type_id -> {skill_id: required_level}
    """
    return {
        # Vexor requires Gallente Cruiser III and Spaceship Command III
        "626": {"3332": 3, "3327": 3},
        # Gallente Cruiser requires Gallente Frigate IV and Spaceship Command II
        "3332": {"3328": 4, "3327": 2},
        # Gallente Frigate requires Spaceship Command I
        "3328": {"3327": 1},
        # Drone Damage Amplifier II requires Drones V
        "4405": {"3436": 5},
        # Hammerhead II requires Medium Drone Operation V and Drones V
        "2185": {"33699": 5, "3436": 5},
        # Medium Drone Operation requires Drones III
        "33699": {"3436": 3},
    }
