"""
Tests for Archetype Models.

Tests dataclasses, to_dict() methods, and ArchetypePath parsing.
"""

from __future__ import annotations

import pytest


# =============================================================================
# SlotLayout Tests
# =============================================================================


class TestSlotLayout:
    """Test SlotLayout dataclass."""

    def test_to_dict(self):
        """Converts to dictionary correctly."""
        from aria_esi.archetypes.models import SlotLayout

        layout = SlotLayout(high=6, mid=4, low=5, rig=3)
        result = layout.to_dict()

        assert result == {"high": 6, "mid": 4, "low": 5, "rig": 3}


# =============================================================================
# DroneCapacity Tests
# =============================================================================


class TestDroneCapacity:
    """Test DroneCapacity dataclass."""

    def test_to_dict(self):
        """Converts to dictionary correctly."""
        from aria_esi.archetypes.models import DroneCapacity

        capacity = DroneCapacity(bandwidth=50, bay=125)
        result = capacity.to_dict()

        assert result == {"bandwidth": 50, "bay": 125}


# =============================================================================
# EmptySlotConfig Tests
# =============================================================================


class TestEmptySlotConfig:
    """Test EmptySlotConfig dataclass."""

    def test_to_dict_empty(self):
        """Empty config returns empty dict."""
        from aria_esi.archetypes.models import EmptySlotConfig

        config = EmptySlotConfig()
        result = config.to_dict()

        assert result == {}

    def test_to_dict_with_slots(self):
        """Config with slots set returns correct dict."""
        from aria_esi.archetypes.models import EmptySlotConfig

        config = EmptySlotConfig(high=True, mid=True, low=False)
        result = config.to_dict()

        assert result == {"high": True, "mid": True}

    def test_to_dict_with_reason(self):
        """Config with reason includes it."""
        from aria_esi.archetypes.models import EmptySlotConfig

        config = EmptySlotConfig(high=True, reason="Utility high unused")
        result = config.to_dict()

        assert result == {"high": True, "reason": "Utility high unused"}


# =============================================================================
# WeaponConfig Tests
# =============================================================================


class TestWeaponConfig:
    """Test WeaponConfig dataclass."""

    def test_to_dict(self):
        """Converts to dictionary correctly."""
        from aria_esi.archetypes.models import WeaponConfig

        config = WeaponConfig(primary="drones", secondary="missiles")
        result = config.to_dict()

        assert result == {"primary": "drones", "secondary": "missiles"}

    def test_to_dict_no_secondary(self):
        """Works without secondary weapon."""
        from aria_esi.archetypes.models import WeaponConfig

        config = WeaponConfig(primary="turrets")
        result = config.to_dict()

        assert result == {"primary": "turrets", "secondary": None}


# =============================================================================
# FittingRules Tests
# =============================================================================


class TestFittingRules:
    """Test FittingRules dataclass."""

    def test_to_dict_minimal(self):
        """Minimal config converts correctly."""
        from aria_esi.archetypes.models import FittingRules

        rules = FittingRules(tank_type="armor_active")
        result = rules.to_dict()

        assert result == {"tank_type": "armor_active"}

    def test_to_dict_full(self):
        """Full config converts correctly."""
        from aria_esi.archetypes.models import (
            EmptySlotConfig,
            FittingRules,
            WeaponConfig,
        )

        rules = FittingRules(
            tank_type="shield_passive",
            empty_slots=EmptySlotConfig(low=True),
            weapons=WeaponConfig(primary="missiles"),
            notes=["Cap stable", "Omni tank"],
        )
        result = rules.to_dict()

        assert result["tank_type"] == "shield_passive"
        assert result["empty_slots"] == {"low": True}
        assert result["weapons"] == {"primary": "missiles", "secondary": None}
        assert result["notes"] == ["Cap stable", "Omni tank"]


# =============================================================================
# DroneConfig Tests
# =============================================================================


class TestDroneConfig:
    """Test DroneConfig dataclass."""

    def test_to_dict_empty(self):
        """Empty config returns empty dict."""
        from aria_esi.archetypes.models import DroneConfig

        config = DroneConfig()
        result = config.to_dict()

        assert result == {}

    def test_to_dict_full(self):
        """Full config converts correctly."""
        from aria_esi.archetypes.models import DroneConfig

        config = DroneConfig(
            primary="Hammerhead II",
            anti_frigate="Hobgoblin II",
            utility="Salvage Drone I",
        )
        result = config.to_dict()

        assert result == {
            "primary": "Hammerhead II",
            "anti_frigate": "Hobgoblin II",
            "utility": "Salvage Drone I",
        }


# =============================================================================
# HullManifest Tests
# =============================================================================


class TestHullManifest:
    """Test HullManifest dataclass."""

    def test_to_dict_minimal(self):
        """Minimal manifest converts correctly."""
        from aria_esi.archetypes.models import (
            FittingRules,
            HullManifest,
            SlotLayout,
        )

        manifest = HullManifest(
            hull="Vexor",
            ship_class="cruiser",
            faction="gallente",
            tech_level=1,
            slots=SlotLayout(high=4, mid=4, low=5, rig=3),
            drones=None,
            bonuses=["Drone damage", "Drone hitpoints"],
            roles=["Combat", "Ratting"],
            fitting_rules=FittingRules(tank_type="armor_active"),
        )
        result = manifest.to_dict()

        assert result["hull"] == "Vexor"
        assert result["class"] == "cruiser"
        assert result["faction"] == "gallente"
        assert result["tech_level"] == 1
        assert result["slots"] == {"high": 4, "mid": 4, "low": 5, "rig": 3}
        assert "drones" not in result

    def test_to_dict_full(self):
        """Full manifest converts correctly."""
        from aria_esi.archetypes.models import (
            DroneCapacity,
            DroneConfig,
            FittingRules,
            HullManifest,
            SlotLayout,
        )

        manifest = HullManifest(
            hull="Vexor Navy Issue",
            ship_class="cruiser",
            faction="gallente",
            tech_level=1,
            slots=SlotLayout(high=5, mid=4, low=6, rig=3),
            drones=DroneCapacity(bandwidth=125, bay=200),
            bonuses=["Drone damage"],
            roles=["Combat"],
            fitting_rules=FittingRules(tank_type="armor_active"),
            drone_recommendations=DroneConfig(primary="Ogre II"),
            capacitor_notes="Watch cap usage with MWD",
            engagement_notes="Kite at drone optimal",
        )
        result = manifest.to_dict()

        assert result["drones"] == {"bandwidth": 125, "bay": 200}
        assert result["drone_recommendations"] == {"primary": "Ogre II"}
        assert result["capacitor_notes"] == "Watch cap usage with MWD"
        assert result["engagement_notes"] == "Kite at drone optimal"


# =============================================================================
# SkillRequirements Tests
# =============================================================================


class TestSkillRequirements:
    """Test SkillRequirements dataclass."""

    def test_to_dict(self):
        """Converts to dictionary correctly."""
        from aria_esi.archetypes.models import SkillRequirements

        reqs = SkillRequirements(
            required={"Drones": 5, "Medium Drone Operation": 4},
            recommended={"Drone Interfacing": 4},
        )
        result = reqs.to_dict()

        assert result["required"] == {"Drones": 5, "Medium Drone Operation": 4}
        assert result["recommended"] == {"Drone Interfacing": 4}


# =============================================================================
# Stats Tests
# =============================================================================


class TestStats:
    """Test Stats dataclass."""

    def test_to_dict_minimal(self):
        """Minimal stats converts correctly."""
        from aria_esi.archetypes.models import Stats

        stats = Stats(dps=400.0, ehp=25000.0)
        result = stats.to_dict()

        assert result == {"dps": 400.0, "ehp": 25000.0}

    def test_to_dict_full(self):
        """Full stats converts correctly."""
        from aria_esi.archetypes.models import Stats

        stats = Stats(
            dps=500.0,
            ehp=30000.0,
            tank_sustained=150.0,
            capacitor_stable=True,
            align_time=8.5,
            speed_mwd=1500.0,
            speed_ab=400.0,
            drone_control_range=60000.0,
            missile_range=None,
            validated_date="2026-01-15",
            tank_type="active",
            tank_regen=200.0,
            primary_resists=["thermal", "kinetic"],
            primary_damage=["thermal"],
            dps_by_type={"thermal": 500.0},
            resists={"em": 0.5, "thermal": 0.7, "kinetic": 0.6, "explosive": 0.4},
            estimated_isk=50000000,
            isk_updated="2026-01-15",
        )
        result = stats.to_dict()

        assert result["dps"] == 500.0
        assert result["ehp"] == 30000.0
        assert result["tank_sustained"] == 150.0
        assert result["capacitor_stable"] is True
        assert result["align_time"] == 8.5
        assert result["speed_mwd"] == 1500.0
        assert result["speed_ab"] == 400.0
        assert result["drone_control_range"] == 60000.0
        assert result["validated_date"] == "2026-01-15"
        assert result["tank_type"] == "active"
        assert result["tank_regen"] == 200.0
        assert result["primary_resists"] == ["thermal", "kinetic"]
        assert result["primary_damage"] == ["thermal"]
        assert result["dps_by_type"] == {"thermal": 500.0}
        assert result["resists"] == {"em": 0.5, "thermal": 0.7, "kinetic": 0.6, "explosive": 0.4}
        assert result["estimated_isk"] == 50000000
        assert result["isk_updated"] == "2026-01-15"


# =============================================================================
# ModuleSubstitution Tests
# =============================================================================


class TestModuleSubstitution:
    """Test ModuleSubstitution dataclass."""

    def test_to_dict(self):
        """Converts to dictionary correctly."""
        from aria_esi.archetypes.models import ModuleSubstitution

        sub = ModuleSubstitution(
            from_module="Thermal Plating I",
            to_module="Kinetic Plating I",
        )
        result = sub.to_dict()

        assert result == {"from": "Thermal Plating I", "to": "Kinetic Plating I"}


# =============================================================================
# RigSubstitution Tests
# =============================================================================


class TestRigSubstitution:
    """Test RigSubstitution dataclass."""

    def test_to_dict(self):
        """Converts to dictionary correctly."""
        from aria_esi.archetypes.models import RigSubstitution

        sub = RigSubstitution(
            from_rig="Thermal Rig I",
            to_rig="Kinetic Rig I",
        )
        result = sub.to_dict()

        assert result == {"from": "Thermal Rig I", "to": "Kinetic Rig I"}


# =============================================================================
# FactionOverride Tests
# =============================================================================


class TestFactionOverride:
    """Test FactionOverride dataclass."""

    def test_to_dict_empty(self):
        """Empty override returns empty dict."""
        from aria_esi.archetypes.models import FactionOverride

        override = FactionOverride()
        result = override.to_dict()

        assert result == {}

    def test_to_dict_full(self):
        """Full override converts correctly."""
        from aria_esi.archetypes.models import (
            DroneConfig,
            FactionOverride,
            ModuleSubstitution,
            RigSubstitution,
        )

        override = FactionOverride(
            modules=[ModuleSubstitution("From Module", "To Module")],
            rigs=[RigSubstitution("From Rig", "To Rig")],
            drones=DroneConfig(primary="Vespa II"),
        )
        result = override.to_dict()

        assert result["modules"] == [{"from": "From Module", "to": "To Module"}]
        assert result["rigs"] == [{"from": "From Rig", "to": "To Rig"}]
        assert result["drones"] == {"primary": "Vespa II"}


# =============================================================================
# DamageTuning Tests
# =============================================================================


class TestDamageTuning:
    """Test DamageTuning dataclass."""

    def test_to_dict_minimal(self):
        """Minimal tuning converts correctly."""
        from aria_esi.archetypes.models import DamageTuning

        tuning = DamageTuning(
            default_damage="thermal",
            tank_profile="armor_active",
        )
        result = tuning.to_dict()

        assert result == {"default_damage": "thermal", "tank_profile": "armor_active"}

    def test_to_dict_with_overrides(self):
        """Tuning with overrides converts correctly."""
        from aria_esi.archetypes.models import (
            DamageTuning,
            FactionOverride,
            ModuleSubstitution,
        )

        tuning = DamageTuning(
            default_damage="kinetic",
            tank_profile="shield_passive",
            overrides={
                "serpentis": FactionOverride(
                    modules=[ModuleSubstitution("Old", "New")]
                )
            },
        )
        result = tuning.to_dict()

        assert result["default_damage"] == "kinetic"
        assert result["overrides"]["serpentis"]["modules"] == [{"from": "Old", "to": "New"}]


# =============================================================================
# ModuleUpgrade Tests
# =============================================================================


class TestModuleUpgrade:
    """Test ModuleUpgrade dataclass."""

    def test_to_dict_minimal(self):
        """Minimal upgrade converts correctly."""
        from aria_esi.archetypes.models import ModuleUpgrade

        upgrade = ModuleUpgrade(module="Armor Repairer I", upgrade_to="Armor Repairer II")
        result = upgrade.to_dict()

        assert result == {"module": "Armor Repairer I", "upgrade_to": "Armor Repairer II"}

    def test_to_dict_with_skill(self):
        """Upgrade with skill requirement converts correctly."""
        from aria_esi.archetypes.models import ModuleUpgrade

        upgrade = ModuleUpgrade(
            module="Armor Repairer I",
            upgrade_to="Armor Repairer II",
            skill_required="Repair Systems V",
        )
        result = upgrade.to_dict()

        assert result["skill_required"] == "Repair Systems V"


# =============================================================================
# UpgradePath Tests
# =============================================================================


class TestUpgradePath:
    """Test UpgradePath dataclass."""

    def test_to_dict_empty(self):
        """Empty path returns empty dict."""
        from aria_esi.archetypes.models import UpgradePath

        path = UpgradePath(next_tier=None)
        result = path.to_dict()

        assert result == {}

    def test_to_dict_full(self):
        """Full path converts correctly."""
        from aria_esi.archetypes.models import ModuleUpgrade, UpgradePath

        path = UpgradePath(
            next_tier="t2_optimal",
            key_upgrades=[
                ModuleUpgrade("Module I", "Module II", "Skill V")
            ],
        )
        result = path.to_dict()

        assert result["next_tier"] == "t2_optimal"
        assert len(result["key_upgrades"]) == 1


# =============================================================================
# ArchetypeNotes Tests
# =============================================================================


class TestArchetypeNotes:
    """Test ArchetypeNotes dataclass."""

    def test_to_dict_minimal(self):
        """Minimal notes converts correctly."""
        from aria_esi.archetypes.models import ArchetypeNotes

        notes = ArchetypeNotes(purpose="L2 mission running")
        result = notes.to_dict()

        assert result == {"purpose": "L2 mission running"}

    def test_to_dict_full(self):
        """Full notes converts correctly."""
        from aria_esi.archetypes.models import ArchetypeNotes

        notes = ArchetypeNotes(
            purpose="L2 mission running",
            engagement="Orbit at 30km",
            warnings=["Watch out for neuts", "Keep transversal up"],
        )
        result = notes.to_dict()

        assert result["purpose"] == "L2 mission running"
        assert result["engagement"] == "Orbit at 30km"
        assert result["warnings"] == ["Watch out for neuts", "Keep transversal up"]


# =============================================================================
# ArchetypePath Tests
# =============================================================================


class TestArchetypePath:
    """Test ArchetypePath dataclass and parse method."""

    def test_relative_path_short(self):
        """Short path generates correct relative path."""
        from aria_esi.archetypes.models import ArchetypePath

        path = ArchetypePath(
            hull="heron",
            activity_branch="exploration",
            activity=None,
            level=None,
            tier="t1",
        )
        assert path.relative_path == "heron/exploration/t1.yaml"

    def test_relative_path_medium(self):
        """Medium path generates correct relative path."""
        from aria_esi.archetypes.models import ArchetypePath

        path = ArchetypePath(
            hull="vexor",
            activity_branch="pve",
            activity="missions",
            level=None,
            tier="meta",
        )
        assert path.relative_path == "vexor/pve/missions/meta.yaml"

    def test_relative_path_full(self):
        """Full path generates correct relative path."""
        from aria_esi.archetypes.models import ArchetypePath

        path = ArchetypePath(
            hull="vexor",
            activity_branch="pve",
            activity="missions",
            level="l2",
            tier="t2_optimal",
        )
        assert path.relative_path == "vexor/pve/missions/l2/t2_optimal.yaml"

    def test_parse_short_format(self):
        """Parses short format correctly."""
        from aria_esi.archetypes.models import ArchetypePath

        path = ArchetypePath.parse("heron/exploration/t1")

        assert path.hull == "heron"
        assert path.activity_branch == "exploration"
        assert path.activity is None
        assert path.level is None
        assert path.tier == "t1"

    def test_parse_medium_format(self):
        """Parses medium format correctly."""
        from aria_esi.archetypes.models import ArchetypePath

        path = ArchetypePath.parse("vexor/pve/missions/meta")

        assert path.hull == "vexor"
        assert path.activity_branch == "pve"
        assert path.activity == "missions"
        assert path.level is None
        assert path.tier == "meta"

    def test_parse_full_format(self):
        """Parses full format correctly."""
        from aria_esi.archetypes.models import ArchetypePath

        path = ArchetypePath.parse("vexor/pve/missions/l2/t2_optimal")

        assert path.hull == "vexor"
        assert path.activity_branch == "pve"
        assert path.activity == "missions"
        assert path.level == "l2"
        assert path.tier == "t2_optimal"

    def test_parse_with_yaml_extension(self):
        """Parses path with .yaml extension."""
        from aria_esi.archetypes.models import ArchetypePath

        path = ArchetypePath.parse("heron/exploration/t1.yaml")

        assert path.hull == "heron"
        assert path.tier == "t1"

    def test_parse_with_hulls_prefix(self):
        """Parses path with hulls/{class}/ prefix."""
        from aria_esi.archetypes.models import ArchetypePath

        path = ArchetypePath.parse("hulls/cruiser/vexor/pve/missions/l2/meta.yaml")

        assert path.hull == "vexor"
        assert path.activity_branch == "pve"
        assert path.activity == "missions"
        assert path.level == "l2"
        assert path.tier == "meta"

    def test_parse_invalid_too_short(self):
        """Raises error for too short path."""
        from aria_esi.archetypes.models import ArchetypePath

        with pytest.raises(ValueError) as exc_info:
            ArchetypePath.parse("heron/exploration")

        assert "Invalid archetype path" in str(exc_info.value)

    def test_parse_invalid_tier(self):
        """Raises error for invalid tier."""
        from aria_esi.archetypes.models import ArchetypePath

        with pytest.raises(ValueError) as exc_info:
            ArchetypePath.parse("heron/exploration/invalid_tier")

        assert "Invalid skill tier" in str(exc_info.value)

    def test_parse_normalizes_backslashes(self):
        """Normalizes Windows-style backslashes."""
        from aria_esi.archetypes.models import ArchetypePath

        path = ArchetypePath.parse("heron\\exploration\\t1")

        assert path.hull == "heron"
        assert path.tier == "t1"

    def test_to_dict(self):
        """Converts to dictionary correctly."""
        from aria_esi.archetypes.models import ArchetypePath

        path = ArchetypePath(
            hull="vexor",
            activity_branch="pve",
            activity="missions",
            level="l2",
            tier="t1",
        )
        result = path.to_dict()

        assert result["hull"] == "vexor"
        assert result["activity_branch"] == "pve"
        assert result["activity"] == "missions"
        assert result["level"] == "l2"
        assert result["tier"] == "t1"
        assert result["relative_path"] == "vexor/pve/missions/l2/t1.yaml"


# =============================================================================
# ArchetypeHeader Tests
# =============================================================================


class TestArchetypeHeader:
    """Test ArchetypeHeader dataclass."""

    def test_to_dict(self):
        """Converts to dictionary correctly."""
        from aria_esi.archetypes.models import ArchetypeHeader

        header = ArchetypeHeader(hull="Vexor", skill_tier="t1", omega_required=False)
        result = header.to_dict()

        assert result == {"hull": "Vexor", "skill_tier": "t1", "omega_required": False}


# =============================================================================
# Archetype Tests
# =============================================================================


class TestArchetype:
    """Test Archetype dataclass."""

    def test_hull_property(self):
        """Hull property returns archetype hull."""
        from aria_esi.archetypes.models import (
            Archetype,
            ArchetypeHeader,
            SkillRequirements,
            Stats,
        )

        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=300, ehp=20000),
        )

        assert archetype.hull == "Vexor"

    def test_skill_tier_property(self):
        """Skill tier property returns archetype tier."""
        from aria_esi.archetypes.models import (
            Archetype,
            ArchetypeHeader,
            SkillRequirements,
            Stats,
        )

        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="meta"),
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=300, ehp=20000),
        )

        assert archetype.skill_tier == "meta"

    def test_to_dict_minimal(self):
        """Minimal archetype converts correctly."""
        from aria_esi.archetypes.models import (
            Archetype,
            ArchetypeHeader,
            SkillRequirements,
            Stats,
        )

        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="[Vexor, Test]\nDrone Damage Amplifier II",
            skill_requirements=SkillRequirements(required={"Drones": 5}),
            stats=Stats(dps=400, ehp=25000),
        )
        result = archetype.to_dict()

        assert result["archetype"]["hull"] == "Vexor"
        assert result["eft"] == "[Vexor, Test]\nDrone Damage Amplifier II"
        assert result["skill_requirements"]["required"] == {"Drones": 5}
        assert result["stats"]["dps"] == 400

    def test_to_dict_full(self):
        """Full archetype converts correctly."""
        from aria_esi.archetypes.models import (
            Archetype,
            ArchetypeHeader,
            ArchetypeNotes,
            ArchetypePath,
            DamageTuning,
            ModuleUpgrade,
            SkillRequirements,
            Stats,
            UpgradePath,
        )

        archetype = Archetype(
            archetype=ArchetypeHeader(hull="Vexor", skill_tier="t1"),
            eft="[Vexor, Test]",
            skill_requirements=SkillRequirements(),
            stats=Stats(dps=400, ehp=25000),
            damage_tuning=DamageTuning(default_damage="thermal", tank_profile="armor_active"),
            upgrade_path=UpgradePath(
                next_tier="meta",
                key_upgrades=[ModuleUpgrade("DDA I", "DDA II")],
            ),
            notes=ArchetypeNotes(purpose="L2 missions"),
            path=ArchetypePath(
                hull="vexor",
                activity_branch="pve",
                activity="missions",
                level="l2",
                tier="t1",
            ),
        )
        result = archetype.to_dict()

        assert "damage_tuning" in result
        assert "upgrade_path" in result
        assert "notes" in result
        assert "path" in result


# =============================================================================
# FactionDamageProfile Tests
# =============================================================================


class TestFactionDamageProfile:
    """Test FactionDamageProfile dataclass."""

    def test_to_dict_minimal(self):
        """Minimal profile converts correctly."""
        from aria_esi.archetypes.models import FactionDamageProfile

        profile = FactionDamageProfile(
            damage_dealt={"thermal": 55, "kinetic": 45},
            weakness="thermal",
        )
        result = profile.to_dict()

        assert result == {
            "damage_dealt": {"thermal": 55, "kinetic": 45},
            "weakness": "thermal",
        }

    def test_to_dict_full(self):
        """Full profile converts correctly."""
        from aria_esi.archetypes.models import FactionDamageProfile

        profile = FactionDamageProfile(
            damage_dealt={"thermal": 55, "kinetic": 45},
            weakness="thermal",
            ewar="Sensor Dampening",
            notes="Uses tracking disruptors",
        )
        result = profile.to_dict()

        assert result["ewar"] == "Sensor Dampening"
        assert result["notes"] == "Uses tracking disruptors"


# =============================================================================
# FactionTuningRule Tests
# =============================================================================


class TestFactionTuningRule:
    """Test FactionTuningRule dataclass."""

    def test_to_dict_empty(self):
        """Empty rule returns empty dict."""
        from aria_esi.archetypes.models import FactionTuningRule

        rule = FactionTuningRule()
        result = rule.to_dict()

        assert result == {}

    def test_to_dict_full(self):
        """Full rule converts correctly."""
        from aria_esi.archetypes.models import FactionTuningRule

        rule = FactionTuningRule(
            modules=[{"slot": "low1", "to": "Kinetic Plating II"}],
            drones={"primary": "kinetic"},
            rigs=[{"slot": "rig1", "to": "Kinetic Rig I"}],
            inherit="serpentis",
        )
        result = rule.to_dict()

        assert result["inherit"] == "serpentis"
        assert result["modules"] == [{"slot": "low1", "to": "Kinetic Plating II"}]
        assert result["drones"] == {"primary": "kinetic"}
        assert result["rigs"] == [{"slot": "rig1", "to": "Kinetic Rig I"}]


# =============================================================================
# SkillTierDefinition Tests
# =============================================================================


class TestSkillTierDefinition:
    """Test SkillTierDefinition dataclass."""

    def test_to_dict_minimal(self):
        """Minimal definition converts correctly."""
        from aria_esi.archetypes.models import SkillTierDefinition

        definition = SkillTierDefinition(description="Basic T1 modules")
        result = definition.to_dict()

        assert result == {"description": "Basic T1 modules"}

    def test_to_dict_full(self):
        """Full definition converts correctly."""
        from aria_esi.archetypes.models import SkillTierDefinition

        definition = SkillTierDefinition(
            description="Full T2 modules",
            typical_sp="5-10M SP",
            core_skills=4,
            weapon_skills=4,
            ship_skills=4,
            module_restriction="T2 only",
            max_skill_level=5,
            notes="For experienced pilots",
        )
        result = definition.to_dict()

        assert result["description"] == "Full T2 modules"
        assert result["typical_sp"] == "5-10M SP"
        assert result["core_skills"] == 4
        assert result["weapon_skills"] == 4
        assert result["ship_skills"] == 4
        assert result["module_restriction"] == "T2 only"
        assert result["max_skill_level"] == 5
        assert result["notes"] == "For experienced pilots"


# =============================================================================
# DroneTypeMapping Tests
# =============================================================================


class TestDroneTypeMapping:
    """Test DroneTypeMapping dataclass."""

    def test_to_dict(self):
        """Converts to dictionary correctly."""
        from aria_esi.archetypes.models import DroneTypeMapping

        mapping = DroneTypeMapping(
            light="Hobgoblin II",
            medium="Hammerhead II",
            heavy="Ogre II",
        )
        result = mapping.to_dict()

        assert result == {
            "light": "Hobgoblin II",
            "medium": "Hammerhead II",
            "heavy": "Ogre II",
        }


# =============================================================================
# MissionContext Tests
# =============================================================================


class TestMissionContext:
    """Test MissionContext dataclass."""

    def test_get_tank_threshold_level_1(self):
        """Returns correct threshold for L1."""
        from aria_esi.archetypes.models import MissionContext

        context = MissionContext(mission_level=1)

        assert context.get_tank_threshold("active") == 15.0
        assert context.get_tank_threshold("buffer") == 8000.0
        assert context.get_tank_threshold("passive") == 15.0

    def test_get_tank_threshold_level_4(self):
        """Returns correct threshold for L4."""
        from aria_esi.archetypes.models import MissionContext

        context = MissionContext(mission_level=4)

        assert context.get_tank_threshold("active") == 300.0
        assert context.get_tank_threshold("buffer") == 80000.0
        assert context.get_tank_threshold("passive") == 300.0

    def test_get_tank_threshold_unknown_level(self):
        """Returns L4 threshold for unknown level."""
        from aria_esi.archetypes.models import MissionContext

        context = MissionContext(mission_level=99)

        # Falls back to L4 thresholds
        assert context.get_tank_threshold("active") == 300.0

    def test_get_tank_threshold_unknown_type(self):
        """Returns 0 for unknown tank type."""
        from aria_esi.archetypes.models import MissionContext

        context = MissionContext(mission_level=2)

        assert context.get_tank_threshold("unknown") == 0.0

    def test_to_dict_minimal(self):
        """Minimal context converts correctly."""
        from aria_esi.archetypes.models import MissionContext

        context = MissionContext(mission_level=2)
        result = context.to_dict()

        assert result == {"mission_level": 2}

    def test_to_dict_full(self):
        """Full context converts correctly."""
        from aria_esi.archetypes.models import MissionContext

        context = MissionContext(
            mission_level=3,
            enemy_faction="serpentis",
            enemy_damage_types=["thermal", "kinetic"],
            enemy_weakness="thermal",
            ewar_types=["damps"],
            mission_name="Enemies Abound",
        )
        result = context.to_dict()

        assert result["mission_level"] == 3
        assert result["enemy_faction"] == "serpentis"
        assert result["enemy_damage_types"] == ["thermal", "kinetic"]
        assert result["enemy_weakness"] == "thermal"
        assert result["ewar_types"] == ["damps"]
        assert result["mission_name"] == "Enemies Abound"
