"""
Pydantic Models for Archetype Fittings Library.

Defines the data structures for hull manifests, archetypes, and related
configuration used in the archetype fitting system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# =============================================================================
# Type Aliases
# =============================================================================

SkillTier = Literal["t1", "meta", "t2", "t2_budget", "t2_buffer", "t2_optimal"]
"""
Skill tier for archetype variants.

- t1: Basic T1/Meta 0 modules, minimal skills
- meta: Meta/Compact modules, moderate skills
- t2: Standard T2 modules
- t2_budget: Mix of T1/T2, good skills
- t2_buffer: T2 buffer tank (shield or armor)
- t2_optimal: Full T2, maxed relevant skills
"""

# Legacy tier names for migration compatibility
LegacySkillTier = Literal["low", "medium", "high", "alpha"]
"""Legacy skill tier names (deprecated, use SkillTier instead)."""

# Mapping from legacy to new tier names
TIER_MIGRATION_MAP: dict[str, str] = {
    "low": "t1",
    "medium": "meta",
    "high": "t2_optimal",
    "alpha": "t1",  # Alpha fits become t1 with omega_required=False
}

TankProfile = Literal["armor_active", "armor_passive", "shield_active", "shield_passive"]
"""Tank philosophy classification."""

DamageType = Literal["em", "thermal", "kinetic", "explosive"]
"""EVE Online damage types."""

ShipClass = Literal[
    "frigate",
    "destroyer",
    "cruiser",
    "battlecruiser",
    "battleship",
    "industrial",
    "mining_barge",
    "capital",
]
"""Ship class classifications."""

Faction = Literal["amarr", "caldari", "gallente", "minmatar", "sisters", "ore"]
"""Ship faction identifiers."""


# =============================================================================
# Slot Configuration Models
# =============================================================================


@dataclass
class SlotLayout:
    """
    Ship slot layout from SDE.
    """

    high: int
    mid: int
    low: int
    rig: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "high": self.high,
            "mid": self.mid,
            "low": self.low,
            "rig": self.rig,
        }


@dataclass
class DroneCapacity:
    """
    Drone bay and bandwidth capacity.
    """

    bandwidth: int
    bay: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "bandwidth": self.bandwidth,
            "bay": self.bay,
        }


# =============================================================================
# Fitting Rules Models
# =============================================================================


@dataclass
class EmptySlotConfig:
    """
    Configuration for intentionally empty slots.
    """

    high: bool = False
    mid: bool = False
    low: bool = False
    reason: str | None = None

    def to_dict(self) -> dict[str, bool | str]:
        """Convert to dictionary."""
        result: dict[str, bool | str] = {}
        if self.high:
            result["high"] = True
        if self.mid:
            result["mid"] = True
        if self.low:
            result["low"] = True
        if self.reason:
            result["reason"] = self.reason
        return result


@dataclass
class WeaponConfig:
    """
    Weapon system configuration.
    """

    primary: str | None  # e.g., "drones", "missiles", "turrets"
    secondary: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "primary": self.primary,
            "secondary": self.secondary,
        }


@dataclass
class FittingRules:
    """
    Hull-specific fitting rules and preferences.
    """

    tank_type: TankProfile
    empty_slots: EmptySlotConfig | None = None
    weapons: WeaponConfig | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result: dict = {"tank_type": self.tank_type}
        if self.empty_slots:
            result["empty_slots"] = self.empty_slots.to_dict()
        if self.weapons:
            result["weapons"] = self.weapons.to_dict()
        if self.notes:
            result["notes"] = self.notes
        return result


# =============================================================================
# Drone Recommendations
# =============================================================================


@dataclass
class DroneConfig:
    """
    Recommended drone loadout configuration.
    """

    primary: str | None = None  # e.g., "Hammerhead I"
    anti_frigate: str | None = None  # e.g., "Hobgoblin I"
    utility: str | None = None  # e.g., "Salvage Drone I"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {}
        if self.primary:
            result["primary"] = self.primary
        if self.anti_frigate:
            result["anti_frigate"] = self.anti_frigate
        if self.utility:
            result["utility"] = self.utility
        return result


# =============================================================================
# Hull Manifest Model
# =============================================================================


@dataclass
class HullManifest:
    """
    Hull metadata and fitting rules.

    Located at: reference/archetypes/hulls/{class}/{hull}/manifest.yaml
    """

    hull: str
    ship_class: ShipClass
    faction: Faction
    tech_level: int
    slots: SlotLayout
    drones: DroneCapacity | None
    bonuses: list[str]
    roles: list[str]
    fitting_rules: FittingRules
    drone_recommendations: DroneConfig | None = None
    capacitor_notes: str | None = None
    engagement_notes: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "hull": self.hull,
            "class": self.ship_class,
            "faction": self.faction,
            "tech_level": self.tech_level,
            "slots": self.slots.to_dict(),
            "bonuses": self.bonuses,
            "roles": self.roles,
            "fitting_rules": self.fitting_rules.to_dict(),
        }
        if self.drones:
            result["drones"] = self.drones.to_dict()
        if self.drone_recommendations:
            result["drone_recommendations"] = self.drone_recommendations.to_dict()
        if self.capacitor_notes:
            result["capacitor_notes"] = self.capacitor_notes
        if self.engagement_notes:
            result["engagement_notes"] = self.engagement_notes
        return result


# =============================================================================
# Archetype Skill Requirements
# =============================================================================


@dataclass
class SkillRequirements:
    """
    Skill requirements for an archetype variant.
    """

    required: dict[str, int] = field(default_factory=dict)
    recommended: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "required": self.required,
            "recommended": self.recommended,
        }


# =============================================================================
# Archetype Stats
# =============================================================================


@dataclass
class Stats:
    """
    Expected performance statistics for an archetype.

    Values are EOS-validated baselines.
    """

    dps: float
    ehp: float
    tank_sustained: float | None = None  # HP/s for active tanks (legacy)
    capacitor_stable: bool | None = None
    align_time: float | None = None
    speed_mwd: float | None = None
    speed_ab: float | None = None
    drone_control_range: float | None = None
    missile_range: float | None = None
    validated_date: str | None = None

    # New fields for skill-aware selection
    tank_type: TankType | None = None  # active, buffer, or passive
    tank_regen: float | None = None  # EHP/s (0 for buffer tanks)
    primary_resists: list[str] = field(default_factory=list)  # Damage types >= 60%
    primary_damage: list[str] = field(default_factory=list)  # DPS types >= 50%
    dps_by_type: dict[str, float] | None = None  # Full DPS breakdown
    resists: dict[str, float] | None = None  # Full resist profile
    estimated_isk: int | None = None  # Estimated fit cost
    isk_updated: str | None = None  # ISO date of price update

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result: dict = {
            "dps": self.dps,
            "ehp": self.ehp,
        }
        if self.tank_sustained is not None:
            result["tank_sustained"] = self.tank_sustained
        if self.capacitor_stable is not None:
            result["capacitor_stable"] = self.capacitor_stable
        if self.align_time is not None:
            result["align_time"] = self.align_time
        if self.speed_mwd is not None:
            result["speed_mwd"] = self.speed_mwd
        if self.speed_ab is not None:
            result["speed_ab"] = self.speed_ab
        if self.drone_control_range is not None:
            result["drone_control_range"] = self.drone_control_range
        if self.missile_range is not None:
            result["missile_range"] = self.missile_range
        if self.validated_date is not None:
            result["validated_date"] = self.validated_date
        # New fields
        if self.tank_type is not None:
            result["tank_type"] = self.tank_type
        if self.tank_regen is not None:
            result["tank_regen"] = self.tank_regen
        if self.primary_resists:
            result["primary_resists"] = self.primary_resists
        if self.primary_damage:
            result["primary_damage"] = self.primary_damage
        if self.dps_by_type is not None:
            result["dps_by_type"] = self.dps_by_type
        if self.resists is not None:
            result["resists"] = self.resists
        if self.estimated_isk is not None:
            result["estimated_isk"] = self.estimated_isk
        if self.isk_updated is not None:
            result["isk_updated"] = self.isk_updated
        return result


# =============================================================================
# Damage Tuning
# =============================================================================


@dataclass
class ModuleSubstitution:
    """
    Module substitution rule for faction tuning.
    """

    from_module: str
    to_module: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "from": self.from_module,
            "to": self.to_module,
        }


@dataclass
class RigSubstitution:
    """
    Rig substitution rule for faction overrides.
    """

    from_rig: str
    to_rig: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "from": self.from_rig,
            "to": self.to_rig,
        }


@dataclass
class FactionOverride:
    """
    Faction-specific override for an archetype.
    """

    modules: list[ModuleSubstitution] = field(default_factory=list)
    rigs: list[RigSubstitution] = field(default_factory=list)
    drones: DroneConfig | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result: dict = {}
        if self.modules:
            result["modules"] = [m.to_dict() for m in self.modules]
        if self.rigs:
            result["rigs"] = [r.to_dict() for r in self.rigs]
        if self.drones:
            result["drones"] = self.drones.to_dict()
        return result


@dataclass
class DamageTuning:
    """
    Damage tuning configuration for an archetype.
    """

    default_damage: DamageType
    tank_profile: TankProfile
    overrides: dict[str, FactionOverride] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result: dict = {
            "default_damage": self.default_damage,
            "tank_profile": self.tank_profile,
        }
        if self.overrides:
            result["overrides"] = {k: v.to_dict() for k, v in self.overrides.items()}
        return result


# =============================================================================
# Upgrade Path
# =============================================================================


@dataclass
class ModuleUpgrade:
    """
    A single module upgrade step.
    """

    module: str
    upgrade_to: str
    skill_required: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "module": self.module,
            "upgrade_to": self.upgrade_to,
        }
        if self.skill_required:
            result["skill_required"] = self.skill_required
        return result


@dataclass
class UpgradePath:
    """
    Upgrade path to higher skill tier variants.
    """

    next_tier: SkillTier | None
    key_upgrades: list[ModuleUpgrade] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result: dict = {}
        if self.next_tier:
            result["next_tier"] = self.next_tier
        if self.key_upgrades:
            result["key_upgrades"] = [u.to_dict() for u in self.key_upgrades]
        return result


# =============================================================================
# Archetype Notes
# =============================================================================


@dataclass
class ArchetypeNotes:
    """
    Documentation and guidance for an archetype.
    """

    purpose: str
    engagement: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result: dict = {"purpose": self.purpose}
        if self.engagement:
            result["engagement"] = self.engagement
        if self.warnings:
            result["warnings"] = self.warnings
        return result


# =============================================================================
# Archetype Path
# =============================================================================


@dataclass
class ArchetypePath:
    """
    Parsed archetype path components.

    Path formats:
      - Short: {hull}/{activity_branch}/{tier} (e.g., heron/exploration/t1)
      - Full: {hull}/{activity_branch}/{activity}/{level}/{tier} (e.g., vexor/pve/missions/l2/t1)
      - Variant: {hull}/{activity_branch}/{activity}/{level}/{variant}/{tier} (e.g., vexor/pve/missions/l3/armor/t2)
    """

    hull: str
    activity_branch: str  # e.g., "pve", "pvp", "mining", "exploration"
    activity: str | None  # e.g., "missions", "anomalies", "belt" (optional for simple activities)
    level: str | None  # e.g., "l2", "t1-electrical" (optional)
    tier: SkillTier
    variant: str | None = None  # e.g., "armor", "shield" (optional tank variant)

    @property
    def relative_path(self) -> str:
        """Get the relative path string."""
        parts = [self.hull, self.activity_branch]
        if self.activity:
            parts.append(self.activity)
        if self.level:
            parts.append(self.level)
        if self.variant:
            parts.append(self.variant)
        parts.append(f"{self.tier}.yaml")
        return "/".join(parts)

    @classmethod
    def parse(cls, path_str: str) -> ArchetypePath:
        """
        Parse a path string into components.

        Accepts:
          - heron/exploration/t1 (short format)
          - vexor/pve/missions/l2/medium (full format)
          - hulls/cruiser/vexor/pve/missions/l2/medium.yaml
        """
        # Normalize path
        path_str = path_str.replace("\\", "/")

        # Remove .yaml extension if present
        if path_str.endswith(".yaml"):
            path_str = path_str[:-5]

        # Split into parts
        parts = [p for p in path_str.split("/") if p]

        # Handle full path starting with hulls/{class}/
        if len(parts) >= 2 and parts[0] == "hulls":
            # Skip "hulls" and ship class
            parts = parts[2:]

        # Valid tiers for checking
        valid_tiers: set[str] = {
            # New tier names
            "t1",
            "meta",
            "t2",
            "t2_budget",
            "t2_buffer",
            "t2_optimal",
            # Legacy tier names (for backward compatibility)
            "low",
            "medium",
            "high",
            "alpha",
        }

        # Valid tank variants
        valid_variants: set[str] = {"armor", "shield"}

        # Minimum: hull/activity_branch/tier (3 parts)
        if len(parts) < 3:
            raise ValueError(
                f"Invalid archetype path: {path_str}. "
                "Expected format: hull/activity_branch/[activity/][level/][variant/]tier"
            )

        hull = parts[0]
        activity_branch = parts[1]
        variant = None

        # Determine format based on number of parts
        if len(parts) == 3:
            # Short format: hull/activity_branch/tier
            activity = None
            level = None
            tier_str = parts[2]
        elif len(parts) == 4:
            # Medium format: hull/activity_branch/activity/tier
            activity = parts[2]
            level = None
            tier_str = parts[3]
        elif len(parts) == 5:
            # Full format: hull/activity_branch/activity/level/tier
            activity = parts[2]
            level = parts[3]
            tier_str = parts[4]
        else:
            # Variant format: hull/activity_branch/activity/level/variant/tier
            activity = parts[2]
            level = parts[3]
            # Check if parts[4] is a variant or part of level
            if parts[4] in valid_variants:
                variant = parts[4]
                tier_str = parts[5]
            else:
                # Extended level (e.g., l3/something/tier)
                level = f"{parts[3]}/{parts[4]}"
                tier_str = parts[5]

        if tier_str not in valid_tiers:
            raise ValueError(f"Invalid skill tier: {tier_str}. Expected one of: {valid_tiers}")

        return cls(
            hull=hull,
            activity_branch=activity_branch,
            activity=activity,
            level=level,
            variant=variant,
            tier=tier_str,  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "hull": self.hull,
            "activity_branch": self.activity_branch,
            "activity": self.activity,
            "level": self.level,
            "variant": self.variant,
            "tier": self.tier,
            "relative_path": self.relative_path,
        }


# =============================================================================
# Main Archetype Model
# =============================================================================


TankType = Literal["active", "buffer", "passive"]
"""Tank type classification for EHP/s thresholds."""


@dataclass
class ArchetypeHeader:
    """
    Archetype identification header.
    """

    hull: str
    skill_tier: SkillTier
    omega_required: bool = True  # False for alpha-flyable fits

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "hull": self.hull,
            "skill_tier": self.skill_tier,
            "omega_required": self.omega_required,
        }


@dataclass
class Archetype:
    """
    Complete archetype fit definition.

    Located at: reference/archetypes/hulls/{class}/{hull}/{activity}/{tier}.yaml
    """

    # Header
    archetype: ArchetypeHeader

    # The actual fit in EFT format
    eft: str

    # Requirements and performance
    skill_requirements: SkillRequirements
    stats: Stats

    # Optional sections
    damage_tuning: DamageTuning | None = None
    upgrade_path: UpgradePath | None = None
    notes: ArchetypeNotes | None = None

    # Path information (set by loader)
    path: ArchetypePath | None = None

    @property
    def hull(self) -> str:
        """Get hull name."""
        return self.archetype.hull

    @property
    def skill_tier(self) -> SkillTier:
        """Get skill tier."""
        return self.archetype.skill_tier

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result: dict = {
            "archetype": self.archetype.to_dict(),
            "eft": self.eft,
            "skill_requirements": self.skill_requirements.to_dict(),
            "stats": self.stats.to_dict(),
        }
        if self.damage_tuning:
            result["damage_tuning"] = self.damage_tuning.to_dict()
        if self.upgrade_path:
            result["upgrade_path"] = self.upgrade_path.to_dict()
        if self.notes:
            result["notes"] = self.notes.to_dict()
        if self.path:
            result["path"] = self.path.to_dict()
        return result


# =============================================================================
# Shared Configuration Models
# =============================================================================


@dataclass
class FactionDamageProfile:
    """
    Faction damage dealt and weakness.
    """

    damage_dealt: dict[str, int]  # e.g., {"thermal": 55, "kinetic": 45}
    weakness: DamageType
    ewar: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result: dict = {
            "damage_dealt": self.damage_dealt,
            "weakness": self.weakness,
        }
        if self.ewar:
            result["ewar"] = self.ewar
        if self.notes:
            result["notes"] = self.notes
        return result


@dataclass
class FactionTuningRule:
    """
    Faction-specific module/drone tuning rule.
    """

    modules: list[dict] = field(default_factory=list)  # slot -> to mappings
    drones: dict[str, str] = field(default_factory=dict)  # role -> damage type
    rigs: list[dict] = field(default_factory=list)  # optional rig swaps
    inherit: str | None = None  # inherit from another faction

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result: dict = {}
        if self.inherit:
            result["inherit"] = self.inherit
        if self.modules:
            result["modules"] = self.modules
        if self.drones:
            result["drones"] = self.drones
        if self.rigs:
            result["rigs"] = self.rigs
        return result


@dataclass
class SkillTierDefinition:
    """
    Definition of a skill tier.
    """

    description: str
    typical_sp: str | None = None
    core_skills: int | None = None
    weapon_skills: int | None = None
    ship_skills: int | None = None
    module_restriction: str | None = None
    max_skill_level: int | None = None
    notes: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result: dict = {"description": self.description}
        if self.typical_sp:
            result["typical_sp"] = self.typical_sp
        if self.core_skills is not None:
            result["core_skills"] = self.core_skills
        if self.weapon_skills is not None:
            result["weapon_skills"] = self.weapon_skills
        if self.ship_skills is not None:
            result["ship_skills"] = self.ship_skills
        if self.module_restriction:
            result["module_restriction"] = self.module_restriction
        if self.max_skill_level is not None:
            result["max_skill_level"] = self.max_skill_level
        if self.notes:
            result["notes"] = self.notes
        return result


@dataclass
class DroneTypeMapping:
    """
    Drone type resolution by damage type and size.
    """

    light: str
    medium: str
    heavy: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "light": self.light,
            "medium": self.medium,
            "heavy": self.heavy,
        }


# =============================================================================
# Mission Context for Fit Selection
# =============================================================================


@dataclass
class MissionContext:
    """
    Context for mission-aware fit selection.

    Used to filter fits based on mission requirements like damage types,
    tank requirements, and EWAR considerations.
    """

    mission_level: int  # 1-4
    enemy_faction: str | None = None  # e.g., "serpentis", "guristas"
    enemy_damage_types: list[str] = field(default_factory=list)  # What they deal
    enemy_weakness: str | None = None  # Primary weakness
    ewar_types: list[str] = field(default_factory=list)  # neuts, damps, etc.
    mission_name: str | None = None  # For logging/debugging

    # Tank requirements by mission level (EHP/s for active, EHP for buffer)
    TANK_THRESHOLDS: dict[int, dict[str, float]] = field(
        default_factory=lambda: {
            1: {"active": 15.0, "buffer": 8000.0, "passive": 15.0},
            2: {"active": 50.0, "buffer": 20000.0, "passive": 50.0},
            3: {"active": 150.0, "buffer": 45000.0, "passive": 150.0},
            4: {"active": 300.0, "buffer": 80000.0, "passive": 300.0},
        },
        init=False,
    )

    def get_tank_threshold(self, tank_type: str) -> float:
        """Get minimum tank requirement for this mission level."""
        level_thresholds = self.TANK_THRESHOLDS.get(self.mission_level, self.TANK_THRESHOLDS[4])
        return level_thresholds.get(tank_type, 0.0)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result: dict = {
            "mission_level": self.mission_level,
        }
        if self.enemy_faction:
            result["enemy_faction"] = self.enemy_faction
        if self.enemy_damage_types:
            result["enemy_damage_types"] = self.enemy_damage_types
        if self.enemy_weakness:
            result["enemy_weakness"] = self.enemy_weakness
        if self.ewar_types:
            result["ewar_types"] = self.ewar_types
        if self.mission_name:
            result["mission_name"] = self.mission_name
        return result
