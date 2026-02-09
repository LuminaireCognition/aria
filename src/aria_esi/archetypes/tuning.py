"""
Faction Tuning Module.

Applies faction-specific module and drone substitutions to archetypes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .loader import load_faction_tuning, load_shared_config
from .models import (
    Archetype,
    DamageType,
    FactionOverride,
    RigSubstitution,
    SkillTier,
    TankProfile,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Tuning Result
# =============================================================================


@dataclass
class TuningResult:
    """
    Result of faction tuning application.
    """

    original_eft: str
    tuned_eft: str
    faction: str
    tank_profile: TankProfile
    substitutions: list[dict] = field(default_factory=list)
    drone_changes: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "faction": self.faction,
            "tank_profile": self.tank_profile,
            "substitutions": self.substitutions,
            "drone_changes": self.drone_changes,
            "warnings": self.warnings,
        }


# =============================================================================
# EFT Parsing Helpers
# =============================================================================


def _parse_eft_header(eft: str) -> tuple[str, str]:
    """
    Parse the EFT header to get ship and fit name.

    Returns:
        Tuple of (ship_name, fit_name)
    """
    lines = eft.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("[") and "]" in line:
            # Format: [Ship, Fit Name]
            content = line[1:].split("]")[0]
            parts = content.split(",", 1)
            ship = parts[0].strip()
            fit_name = parts[1].strip() if len(parts) > 1 else ""
            return ship, fit_name
    return "", ""


def _modify_eft_header(eft: str, new_suffix: str) -> str:
    """
    Modify the EFT header to add a suffix to the fit name.

    Args:
        eft: Original EFT string
        new_suffix: Suffix to add (e.g., "Anti-Serpentis")

    Returns:
        EFT with modified header
    """
    lines = eft.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and "]" in stripped:
            # Parse existing header
            content = stripped[1:].split("]")[0]
            parts = content.split(",", 1)
            ship = parts[0].strip()
            fit_name = parts[1].strip() if len(parts) > 1 else ""

            # Build new header
            if fit_name:
                new_fit_name = f"{fit_name} - {new_suffix}"
            else:
                new_fit_name = new_suffix

            lines[i] = f"[{ship}, {new_fit_name}]"
            break

    return "\n".join(lines)


def _substitute_module(eft: str, from_module: str, to_module: str) -> tuple[str, bool]:
    """
    Substitute a module in the EFT string.

    Args:
        eft: EFT string
        from_module: Module to replace
        to_module: Replacement module

    Returns:
        Tuple of (modified_eft, was_substituted)
    """
    # Handle single substitution (exact line match)
    lines = eft.split("\n")
    modified = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match module line (may have charge after comma)
        if stripped == from_module or stripped.startswith(f"{from_module},"):
            lines[i] = line.replace(from_module, to_module, 1)
            modified = True
            break

    return "\n".join(lines), modified


def _substitute_drone(
    eft: str,
    from_damage: DamageType,
    to_damage: DamageType,
    drone_size: str,
    skill_tier: SkillTier,
) -> tuple[str, bool]:
    """
    Substitute drones by damage type.

    Args:
        eft: EFT string
        from_damage: Original damage type
        to_damage: New damage type
        drone_size: "light", "medium", or "heavy"
        skill_tier: Skill tier for T1/T2 selection

    Returns:
        Tuple of (modified_eft, was_substituted)
    """
    # Load drone type mappings
    try:
        tuning_config = load_faction_tuning()
        drone_types = tuning_config.get("drone_types", {})
        tech_suffix = tuning_config.get("drone_tech_suffix", {})
    except FileNotFoundError:
        return eft, False

    # Get source and target drone names
    from_drone_base = drone_types.get(from_damage, {}).get(drone_size)
    to_drone_base = drone_types.get(to_damage, {}).get(drone_size)

    if not from_drone_base or not to_drone_base:
        return eft, False

    # Get tech level suffix
    suffix = tech_suffix.get(skill_tier, " I")

    from_drone = f"{from_drone_base}{suffix}"
    to_drone = f"{to_drone_base}{suffix}"

    # Find and replace drone lines
    lines = eft.split("\n")
    modified = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match drone line: "Hammerhead I x5" or just "Hammerhead I"
        if stripped.startswith(from_drone):
            lines[i] = line.replace(from_drone, to_drone)
            modified = True

    return "\n".join(lines), modified


# =============================================================================
# Main Tuning Function
# =============================================================================


def apply_faction_tuning(
    archetype: Archetype,
    faction: str,
) -> TuningResult:
    """
    Apply faction-specific tuning to an archetype.

    Args:
        archetype: The base archetype to tune
        faction: Target faction (e.g., "serpentis", "guristas")

    Returns:
        TuningResult with the tuned fit
    """
    result = TuningResult(
        original_eft=archetype.eft,
        tuned_eft=archetype.eft,
        faction=faction,
        tank_profile=archetype.damage_tuning.tank_profile
        if archetype.damage_tuning
        else "armor_active",
    )

    if not archetype.damage_tuning:
        result.warnings.append("Archetype has no damage_tuning configuration")
        return result

    tank_profile = archetype.damage_tuning.tank_profile
    default_damage = archetype.damage_tuning.default_damage

    # Load faction tuning configuration
    try:
        tuning_config = load_faction_tuning()
    except FileNotFoundError:
        result.warnings.append("Faction tuning configuration not found")
        return result

    # Get tuning rules for this tank profile and faction
    profile_rules = tuning_config.get(tank_profile, {})
    faction_rules = profile_rules.get(faction.lower())

    # Handle inheritance
    if faction_rules and faction_rules.get("inherit"):
        inherited_faction = faction_rules["inherit"]
        faction_rules = profile_rules.get(inherited_faction, {})
        result.warnings.append(f"Using inherited rules from {inherited_faction}")

    if not faction_rules:
        result.warnings.append(f"No tuning rules for {faction} with {tank_profile}")
        return result

    # Start with the original EFT
    tuned_eft = archetype.eft

    # Check for archetype-specific overrides first
    archetype_overrides: FactionOverride | None = archetype.damage_tuning.overrides.get(
        faction.lower()
    )

    # Apply module substitutions from overrides
    if archetype_overrides and archetype_overrides.modules:
        for sub in archetype_overrides.modules:
            new_eft, was_sub = _substitute_module(tuned_eft, sub.from_module, sub.to_module)
            if was_sub:
                tuned_eft = new_eft
                result.substitutions.append(
                    {
                        "type": "module_override",
                        "from": sub.from_module,
                        "to": sub.to_module,
                    }
                )

    # Apply rig substitutions from overrides
    if archetype_overrides and archetype_overrides.rigs:
        rig_sub: RigSubstitution
        for rig_sub in archetype_overrides.rigs:
            new_eft, was_sub = _substitute_module(tuned_eft, rig_sub.from_rig, rig_sub.to_rig)
            if was_sub:
                tuned_eft = new_eft
                result.substitutions.append(
                    {
                        "type": "rig_override",
                        "from": rig_sub.from_rig,
                        "to": rig_sub.to_rig,
                    }
                )

    # Get module substitutions from shared rules
    module_rules = faction_rules.get("modules", [])
    for rule in module_rules:
        slot = rule.get("slot")
        to_modules = rule.get("to", [])

        if slot == "resist" and to_modules:
            # For resist slots, we need to find and replace adaptive modules
            # This is a simplified approach - real implementation would be smarter
            adaptive_modules = [
                "Energized Adaptive Nano Membrane I",
                "Energized Adaptive Nano Membrane II",
                "Compact Energized Adaptive Nano Membrane",
                "Reactive Armor Hardener",
                "Adaptive Invulnerability Field I",
                "Adaptive Invulnerability Field II",
                "Multispectrum Shield Hardener I",
                "Multispectrum Shield Hardener II",
            ]

            to_idx = 0
            for adaptive in adaptive_modules:
                if to_idx < len(to_modules):
                    new_eft, was_sub = _substitute_module(tuned_eft, adaptive, to_modules[to_idx])
                    if was_sub:
                        tuned_eft = new_eft
                        result.substitutions.append(
                            {
                                "type": "resist_module",
                                "from": adaptive,
                                "to": to_modules[to_idx],
                            }
                        )
                        to_idx += 1

    # Apply drone changes
    drone_rules = faction_rules.get("drones", {})
    if drone_rules:
        primary_damage = drone_rules.get("primary")
        anti_frigate_damage = drone_rules.get("anti_frigate")

        skill_tier = archetype.archetype.skill_tier

        # Change primary (medium) drones if different from default
        if primary_damage and primary_damage != default_damage:
            new_eft, was_sub = _substitute_drone(
                tuned_eft, default_damage, primary_damage, "medium", skill_tier
            )
            if was_sub:
                tuned_eft = new_eft
                result.drone_changes.append(
                    {
                        "role": "primary",
                        "from_damage": default_damage,
                        "to_damage": primary_damage,
                    }
                )

        # Change anti-frigate (light) drones if different from default
        if anti_frigate_damage and anti_frigate_damage != default_damage:
            new_eft, was_sub = _substitute_drone(
                tuned_eft, default_damage, anti_frigate_damage, "light", skill_tier
            )
            if was_sub:
                tuned_eft = new_eft
                result.drone_changes.append(
                    {
                        "role": "anti_frigate",
                        "from_damage": default_damage,
                        "to_damage": anti_frigate_damage,
                    }
                )

    # Modify the fit name to indicate tuning
    faction_title = faction.replace("_", " ").title()
    tuned_eft = _modify_eft_header(tuned_eft, f"Anti-{faction_title}")

    result.tuned_eft = tuned_eft
    return result


# =============================================================================
# Utility Functions
# =============================================================================


def get_faction_damage_profile(faction: str) -> dict | None:
    """
    Get the damage profile for a faction.

    Args:
        faction: Faction name (e.g., "serpentis")

    Returns:
        Damage profile dict or None if not found
    """
    try:
        damage_config = load_shared_config("damage_profiles")
        factions = damage_config.get("factions", {})
        return factions.get(faction.lower())
    except FileNotFoundError:
        return None


def list_supported_factions() -> list[str]:
    """
    List all factions with tuning support.

    Returns:
        List of faction names
    """
    try:
        damage_config = load_shared_config("damage_profiles")
        factions = damage_config.get("factions", {})
        return sorted(factions.keys())
    except FileNotFoundError:
        return []


def get_recommended_damage_type(faction: str) -> DamageType | None:
    """
    Get the recommended damage type to deal against a faction.

    Args:
        faction: Faction name

    Returns:
        Damage type string or None
    """
    profile = get_faction_damage_profile(faction)
    if profile:
        return profile.get("weakness")
    return None
