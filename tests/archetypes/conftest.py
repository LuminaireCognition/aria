"""
Pytest fixtures for archetypes module tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def mock_archetypes_root(tmp_path: Path) -> Path:
    """Create a mock archetypes directory structure."""
    archetypes = tmp_path / "reference" / "archetypes"
    archetypes.mkdir(parents=True)

    # Create _shared directory
    shared = archetypes / "_shared"
    shared.mkdir()

    # Create hulls directory structure
    hulls = archetypes / "hulls"
    hulls.mkdir()

    return archetypes


@pytest.fixture
def sample_hull_manifest_data() -> dict[str, Any]:
    """Sample hull manifest data."""
    return {
        "hull": "Vexor",
        "class": "cruiser",
        "faction": "gallente",
        "tech_level": 1,
        "slots": {
            "high": 4,
            "mid": 4,
            "low": 5,
            "rig": 3,
        },
        "drones": {
            "bandwidth": 75,
            "bay": 125,
        },
        "bonuses": [
            "50% bonus to Drone damage and hitpoints",
            "10% bonus to Drone tracking and optimal range",
        ],
        "roles": ["combat", "pve", "missions"],
        "fitting_rules": {
            "tank_type": "armor_active",
            "weapons": {
                "primary": "drones",
                "secondary": "turrets",
            },
            "notes": ["Primary drone boat", "Use armor tank"],
        },
        "drone_recommendations": {
            "primary": "Hammerhead II",
            "anti_frigate": "Hobgoblin II",
            "utility": "Salvage Drone I",
        },
        "capacitor": {
            "notes": "Cap stable with proper skills",
        },
        "engagement": {
            "notes": "Keep at range, let drones do damage",
        },
    }


@pytest.fixture
def sample_archetype_data() -> dict[str, Any]:
    """Sample archetype data."""
    return {
        "archetype": {
            "hull": "Vexor",
            "skill_tier": "t1",
            "omega_required": False,
        },
        "eft": """[Vexor, PvE L2 T1]

Drone Damage Amplifier I
Drone Damage Amplifier I
Armor Repairer I
Armor Hardener I
Armor Hardener I

10MN Afterburner I
Cap Recharger I
Cap Recharger I
Cap Recharger I

[Empty High slot]
[Empty High slot]
[Empty High slot]
[Empty High slot]

Medium Capacitor Control Circuit I
Medium Capacitor Control Circuit I
Medium Capacitor Control Circuit I

Hobgoblin I x5
Hammerhead I x5
""",
        "skill_requirements": {
            "required": {
                "Gallente Cruiser": 1,
                "Drones": 5,
            },
            "recommended": {
                "Medium Drone Operation": 3,
                "Drone Interfacing": 3,
            },
        },
        "stats": {
            "dps": 280,
            "ehp": 18000,
            "tank_sustained": 120,
            "capacitor_stable": True,
            "align_time": 9.5,
        },
        "notes": {
            "purpose": "Level 2 missions on minimal skills",
            "engagement": "Keep at 20-30km, launch drones on hostiles",
            "warnings": ["Limited tank", "Needs cap skills for stability"],
        },
    }


@pytest.fixture
def sample_damage_profiles_data() -> dict[str, Any]:
    """Sample damage profiles config data."""
    return {
        "blood_raiders": {
            "deal": {"em": 50, "thermal": 50, "kinetic": 0, "explosive": 0},
            "weak": {"em": 0, "thermal": 100, "kinetic": 0, "explosive": 0},
        },
        "serpentis": {
            "deal": {"em": 0, "thermal": 50, "kinetic": 50, "explosive": 0},
            "weak": {"em": 0, "thermal": 60, "kinetic": 40, "explosive": 0},
        },
    }


@pytest.fixture
def sample_eft_string() -> str:
    """Sample EFT string for pricing and tuning tests."""
    return """[Vexor, Test Fit]

Drone Damage Amplifier II
Drone Damage Amplifier II
Medium Armor Repairer II
Reactive Armor Hardener
Energized Adaptive Nano Membrane II

10MN Afterburner II
Cap Recharger II
Cap Recharger II
Cap Recharger II

[Empty High slot]
[Empty High slot]
[Empty High slot]
[Empty High slot]

Medium Auxiliary Nano Pump I
Medium Capacitor Control Circuit I
Medium Capacitor Control Circuit I

Hobgoblin II x5
Hammerhead II x5
"""


@pytest.fixture
def sample_eft_with_charges() -> str:
    """Sample EFT string with module charges."""
    return """[Vexor, Mission Runner]

Drone Damage Amplifier II
Drone Damage Amplifier II
Medium Armor Repairer II, Nanite Repair Paste
Reactive Armor Hardener
Energized Adaptive Nano Membrane II

10MN Afterburner II
Cap Recharger II
Cap Recharger II
Cap Recharger II

Drone Link Augmentor I
[Empty High slot]
[Empty High slot]
[Empty High slot]

Medium Auxiliary Nano Pump I
Medium Capacitor Control Circuit I
Medium Capacitor Control Circuit I

Hobgoblin II x5
Hammerhead II x5
"""


@pytest.fixture
def sample_alpha_eft() -> str:
    """Sample EFT string for alpha clone (no T2)."""
    return """[Vexor, Alpha Fit]

Drone Damage Amplifier I
Drone Damage Amplifier I
Medium Armor Repairer I
Armor Hardener I
Armor Hardener I

10MN Afterburner I
Cap Recharger I
Cap Recharger I
Cap Recharger I

[Empty High slot]
[Empty High slot]
[Empty High slot]
[Empty High slot]

Medium Capacitor Control Circuit I
Medium Capacitor Control Circuit I
Medium Capacitor Control Circuit I

Hobgoblin I x5
Hammerhead I x5
"""


@pytest.fixture
def mock_pilot_skills() -> dict[int, int]:
    """Sample pilot skills for selection tests (skill_id -> level)."""
    return {
        3336: 5,  # Drones V
        3426: 4,  # Medium Drone Operation IV
        33699: 3,  # Gallente Cruiser III
        3392: 3,  # Drone Interfacing III
        3442: 3,  # Armor Honeycombing III
        3394: 3,  # Mechanics III
    }


@pytest.fixture
def mock_empty_skills() -> dict[int, int]:
    """Empty pilot skills for testing missing requirements."""
    return {}


@pytest.fixture
def mock_mission_context():
    """Sample mission context for selection tests."""
    from aria_esi.archetypes.models import MissionContext
    return MissionContext(
        mission_level=2,
        enemy_faction="serpentis",
        enemy_weakness="thermal",
        enemy_damage_types=["kinetic", "thermal"],
    )


@pytest.fixture
def mock_market_prices() -> dict[str, float]:
    """Mocked market prices for pricing tests."""
    return {
        "Vexor": 15_000_000.0,
        "Drone Damage Amplifier II": 1_500_000.0,
        "Drone Damage Amplifier I": 50_000.0,
        "Medium Armor Repairer II": 1_200_000.0,
        "Medium Armor Repairer I": 25_000.0,
        "Reactive Armor Hardener": 500_000.0,
        "Energized Adaptive Nano Membrane II": 1_800_000.0,
        "10MN Afterburner II": 800_000.0,
        "10MN Afterburner I": 30_000.0,
        "Cap Recharger II": 200_000.0,
        "Cap Recharger I": 5_000.0,
        "Medium Auxiliary Nano Pump I": 500_000.0,
        "Medium Capacitor Control Circuit I": 400_000.0,
        "Hobgoblin II": 150_000.0,
        "Hobgoblin I": 10_000.0,
        "Hammerhead II": 300_000.0,
        "Hammerhead I": 25_000.0,
    }


@pytest.fixture
def populated_archetypes(
    mock_archetypes_root: Path,
    sample_hull_manifest_data: dict[str, Any],
    sample_archetype_data: dict[str, Any],
    sample_damage_profiles_data: dict[str, Any],
) -> Path:
    """Create a populated archetypes structure with sample data."""
    import yaml

    # Create hull directory structure
    cruiser_dir = mock_archetypes_root / "hulls" / "cruiser" / "vexor"
    cruiser_dir.mkdir(parents=True)

    # Write manifest
    manifest_path = cruiser_dir / "manifest.yaml"
    with open(manifest_path, "w") as f:
        yaml.dump(sample_hull_manifest_data, f)

    # Create archetype directory structure
    pve_dir = cruiser_dir / "pve" / "missions" / "l2"
    pve_dir.mkdir(parents=True)

    # Write archetype
    archetype_path = pve_dir / "t1.yaml"
    with open(archetype_path, "w") as f:
        yaml.dump(sample_archetype_data, f)

    # Write shared config
    shared_dir = mock_archetypes_root / "_shared"
    damage_profiles_path = shared_dir / "damage_profiles.yaml"
    with open(damage_profiles_path, "w") as f:
        yaml.dump(sample_damage_profiles_data, f)

    return mock_archetypes_root
