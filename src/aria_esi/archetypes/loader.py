"""
Archetype Loader Module.

Provides YAML loading and path resolution for archetype files.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from .models import (
    Archetype,
    ArchetypeHeader,
    ArchetypeNotes,
    ArchetypePath,
    DamageTuning,
    DroneCapacity,
    DroneConfig,
    EmptySlotConfig,
    FactionOverride,
    FittingRules,
    HullManifest,
    ModuleSubstitution,
    ModuleUpgrade,
    RigSubstitution,
    SkillRequirements,
    SlotLayout,
    Stats,
    UpgradePath,
    WeaponConfig,
)

if TYPE_CHECKING:
    pass

# =============================================================================
# Path Resolution
# =============================================================================

# Default archetypes directory relative to project root
_ARCHETYPES_DIR = "reference/archetypes"


def get_project_root() -> Path:
    """
    Get the project root directory.

    Walks up from this file's location to find the root.
    """
    current = Path(__file__).resolve()
    # Walk up to find the project root (contains reference/, src/, etc.)
    for parent in [current] + list(current.parents):
        if (parent / "reference").is_dir() and (parent / "src").is_dir():
            return parent
    # Fallback to current working directory
    return Path.cwd()


def get_archetypes_path() -> Path:
    """Get the absolute path to the archetypes directory."""
    return get_project_root() / _ARCHETYPES_DIR


def get_shared_path() -> Path:
    """Get the path to the _shared configuration directory."""
    return get_archetypes_path() / "_shared"


def get_hulls_path() -> Path:
    """Get the path to the hulls directory."""
    return get_archetypes_path() / "hulls"


# =============================================================================
# Ship Class Mapping
# =============================================================================

# Map hull names to their ship class directories
HULL_CLASS_MAP: dict[str, str] = {
    # Frigates
    "venture": "frigate",
    "heron": "frigate",
    "probe": "frigate",
    "magnate": "frigate",
    "imicus": "frigate",
    "tristan": "frigate",
    "kestrel": "frigate",
    "punisher": "frigate",
    "rifter": "frigate",
    "incursus": "frigate",
    "merlin": "frigate",
    # Destroyers
    "algos": "destroyer",
    "dragoon": "destroyer",
    "corax": "destroyer",
    "talwar": "destroyer",
    "catalyst": "destroyer",
    "thrasher": "destroyer",
    # Cruisers
    "vexor": "cruiser",
    "caracal": "cruiser",
    "omen": "cruiser",
    "stabber": "cruiser",
    "thorax": "cruiser",
    "moa": "cruiser",
    "maller": "cruiser",
    "rupture": "cruiser",
    "arbitrator": "cruiser",
    "blackbird": "cruiser",
    "celestis": "cruiser",
    "bellicose": "cruiser",
    "vexor_navy_issue": "cruiser",
    "caracal_navy_issue": "cruiser",
    "omen_navy_issue": "cruiser",
    "stabber_fleet_issue": "cruiser",
    "gnosis": "cruiser",
    # Battlecruisers
    "drake": "battlecruiser",
    "myrmidon": "battlecruiser",
    "harbinger": "battlecruiser",
    "hurricane": "battlecruiser",
    "brutix": "battlecruiser",
    "ferox": "battlecruiser",
    "prophecy": "battlecruiser",
    "cyclone": "battlecruiser",
    # Battleships
    "raven": "battleship",
    "dominix": "battleship",
    "apocalypse": "battleship",
    "typhoon": "battleship",
    "megathron": "battleship",
    "rokh": "battleship",
    "abaddon": "battleship",
    "maelstrom": "battleship",
    "praxis": "battleship",
}


def get_hull_class(hull: str) -> str | None:
    """
    Get the ship class for a hull name.

    Args:
        hull: Hull name (case insensitive)

    Returns:
        Ship class name or None if not found
    """
    return HULL_CLASS_MAP.get(hull.lower().replace(" ", "_"))


def find_hull_directory(hull: str) -> Path | None:
    """
    Find the directory for a hull by searching all class directories.

    Args:
        hull: Hull name to find

    Returns:
        Path to hull directory or None if not found
    """
    hulls_dir = get_hulls_path()
    hull_lower = hull.lower().replace(" ", "_")

    # Try known class first
    known_class = get_hull_class(hull)
    if known_class:
        hull_path = hulls_dir / known_class / hull_lower
        if hull_path.is_dir():
            return hull_path

    # Search all class directories
    if hulls_dir.exists():
        for class_dir in hulls_dir.iterdir():
            if class_dir.is_dir() and not class_dir.name.startswith("_"):
                hull_path = class_dir / hull_lower
                if hull_path.is_dir():
                    return hull_path

    return None


# =============================================================================
# YAML Loading Helpers
# =============================================================================


def load_yaml_file(path: Path) -> dict[str, Any]:
    """
    Load a YAML file and return its contents.

    Args:
        path: Path to YAML file

    Returns:
        Parsed YAML content as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        yaml.YAMLError: If YAML is invalid
    """
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# =============================================================================
# Shared Configuration Loading
# =============================================================================


def load_shared_config(name: str) -> dict[str, Any]:
    """
    Load a shared configuration file.

    Args:
        name: Config name (without .yaml extension)

    Returns:
        Parsed configuration dictionary

    Raises:
        FileNotFoundError: If config doesn't exist
    """
    config_path = get_shared_path() / f"{name}.yaml"
    return load_yaml_file(config_path)


def load_damage_profiles() -> dict[str, Any]:
    """Load faction damage profiles."""
    return load_shared_config("damage_profiles")


def load_faction_tuning() -> dict[str, Any]:
    """Load faction tuning rules."""
    return load_shared_config("faction_tuning")


def load_module_tiers() -> dict[str, Any]:
    """Load module upgrade paths."""
    return load_shared_config("module_tiers")


def load_skill_tiers() -> dict[str, Any]:
    """Load skill tier definitions."""
    return load_shared_config("skill_tiers")


def load_tank_archetypes() -> dict[str, Any]:
    """Load tank archetype definitions."""
    return load_shared_config("tank_archetypes")


# =============================================================================
# Hull Manifest Loading
# =============================================================================


def _parse_slot_layout(data: dict) -> SlotLayout:
    """Parse slot layout from YAML data."""
    return SlotLayout(
        high=data.get("high", 0),
        mid=data.get("mid", 0),
        low=data.get("low", 0),
        rig=data.get("rig", 0),
    )


def _parse_drone_capacity(data: dict | None) -> DroneCapacity | None:
    """Parse drone capacity from YAML data."""
    if not data:
        return None
    return DroneCapacity(
        bandwidth=data.get("bandwidth", 0),
        bay=data.get("bay", 0),
    )


def _parse_empty_slot_config(data: dict | None) -> EmptySlotConfig | None:
    """Parse empty slot configuration from YAML data."""
    if not data:
        return None
    return EmptySlotConfig(
        high=data.get("high", False),
        mid=data.get("mid", False),
        low=data.get("low", False),
        reason=data.get("reason"),
    )


def _parse_weapon_config(data: dict | None) -> WeaponConfig | None:
    """Parse weapon configuration from YAML data."""
    if not data:
        return None
    return WeaponConfig(
        primary=data.get("primary"),
        secondary=data.get("secondary"),
    )


def _parse_fitting_rules(data: dict) -> FittingRules:
    """Parse fitting rules from YAML data."""
    return FittingRules(
        tank_type=data.get("tank_type", "armor_active"),
        empty_slots=_parse_empty_slot_config(data.get("empty_slots")),
        weapons=_parse_weapon_config(data.get("weapons")),
        notes=data.get("notes", []),
    )


def _parse_drone_config(data: dict | None) -> DroneConfig | None:
    """Parse drone configuration from YAML data."""
    if not data:
        return None
    return DroneConfig(
        primary=data.get("primary"),
        anti_frigate=data.get("anti_frigate"),
        utility=data.get("utility"),
    )


def load_hull_manifest(hull: str) -> HullManifest | None:
    """
    Load hull manifest for a specific hull.

    Args:
        hull: Hull name (e.g., "vexor", "drake")

    Returns:
        HullManifest object or None if not found
    """
    hull_dir = find_hull_directory(hull)
    if not hull_dir:
        return None

    manifest_path = hull_dir / "manifest.yaml"
    if not manifest_path.exists():
        return None

    data = load_yaml_file(manifest_path)

    return HullManifest(
        hull=data.get("hull", hull.title()),
        ship_class=data.get("class", "cruiser"),
        faction=data.get("faction", "gallente"),
        tech_level=data.get("tech_level", 1),
        slots=_parse_slot_layout(data.get("slots", {})),
        drones=_parse_drone_capacity(data.get("drones")),
        bonuses=data.get("bonuses", []),
        roles=data.get("roles", []),
        fitting_rules=_parse_fitting_rules(data.get("fitting_rules", {})),
        drone_recommendations=_parse_drone_config(data.get("drone_recommendations")),
        capacitor_notes=data.get("capacitor", {}).get("notes")
        if isinstance(data.get("capacitor"), dict)
        else None,
        engagement_notes=data.get("engagement", {}).get("notes")
        if isinstance(data.get("engagement"), dict)
        else None,
    )


# =============================================================================
# Archetype Loading
# =============================================================================


def _parse_skill_requirements(data: dict | None) -> SkillRequirements:
    """Parse skill requirements from YAML data."""
    if not data:
        return SkillRequirements()
    return SkillRequirements(
        required=data.get("required", {}),
        recommended=data.get("recommended", {}),
    )


def _parse_stats(data: dict) -> Stats:
    """Parse stats from YAML data."""
    return Stats(
        dps=data.get("dps", 0),
        ehp=data.get("ehp", 0),
        tank_sustained=data.get("tank_sustained"),
        capacitor_stable=data.get("capacitor_stable"),
        align_time=data.get("align_time"),
        speed_mwd=data.get("speed_mwd"),
        speed_ab=data.get("speed_ab"),
        drone_control_range=data.get("drone_control_range"),
        missile_range=data.get("missile_range"),
        validated_date=data.get("validated_date"),
        # New fields for skill-aware selection
        tank_type=data.get("tank_type"),
        tank_regen=data.get("tank_regen"),
        primary_resists=data.get("primary_resists", []),
        primary_damage=data.get("primary_damage", []),
        dps_by_type=data.get("dps_by_type"),
        resists=data.get("resists"),
        estimated_isk=data.get("estimated_isk"),
        isk_updated=data.get("isk_updated"),
    )


def _parse_module_substitution(data: dict) -> ModuleSubstitution:
    """Parse module substitution from YAML data."""
    return ModuleSubstitution(
        from_module=data.get("from", ""),
        to_module=data.get("to", ""),
    )


def _parse_rig_substitution(data: dict) -> RigSubstitution:
    """Parse rig substitution from YAML data."""
    return RigSubstitution(
        from_rig=data.get("from", ""),
        to_rig=data.get("to", ""),
    )


def _parse_faction_override(data: dict) -> FactionOverride:
    """Parse faction override from YAML data."""
    modules = [_parse_module_substitution(m) for m in data.get("modules", [])]
    rigs = [_parse_rig_substitution(r) for r in data.get("rigs", [])]
    drones = _parse_drone_config(data.get("drones"))
    return FactionOverride(modules=modules, rigs=rigs, drones=drones)


def _parse_damage_tuning(data: dict | None) -> DamageTuning | None:
    """Parse damage tuning from YAML data."""
    if not data:
        return None
    overrides = {}
    for faction, override_data in data.get("overrides", {}).items():
        overrides[faction] = _parse_faction_override(override_data)
    return DamageTuning(
        default_damage=data.get("default_damage", "thermal"),
        tank_profile=data.get("tank_profile", "armor_active"),
        overrides=overrides,
    )


def _parse_module_upgrade(data: dict) -> ModuleUpgrade:
    """Parse module upgrade from YAML data."""
    return ModuleUpgrade(
        module=data.get("module", ""),
        upgrade_to=data.get("upgrade_to", ""),
        skill_required=data.get("skill_required"),
    )


def _parse_upgrade_path(data: dict | None) -> UpgradePath | None:
    """Parse upgrade path from YAML data."""
    if not data:
        return None
    key_upgrades = [_parse_module_upgrade(u) for u in data.get("key_upgrades", [])]
    return UpgradePath(
        next_tier=data.get("next_tier"),
        key_upgrades=key_upgrades,
    )


def _parse_notes(data: dict | None) -> ArchetypeNotes | None:
    """Parse archetype notes from YAML data."""
    if not data:
        return None
    return ArchetypeNotes(
        purpose=data.get("purpose", ""),
        engagement=data.get("engagement"),
        warnings=data.get("warnings", []),
    )


def load_archetype(path_or_str: str | ArchetypePath) -> Archetype | None:
    """
    Load an archetype from a path.

    Args:
        path_or_str: Either an ArchetypePath object or a path string like
                     "vexor/pve/missions/l2/medium"

    Returns:
        Archetype object or None if not found
    """
    if isinstance(path_or_str, str):
        try:
            arch_path = ArchetypePath.parse(path_or_str)
        except ValueError:
            return None
    else:
        arch_path = path_or_str

    # Find hull directory
    hull_dir = find_hull_directory(arch_path.hull)
    if not hull_dir:
        return None

    # Build full file path
    parts = [arch_path.activity_branch]
    if arch_path.activity:
        parts.append(arch_path.activity)
    if arch_path.level:
        parts.append(arch_path.level)
    if arch_path.variant:
        parts.append(arch_path.variant)
    parts.append(f"{arch_path.tier}.yaml")

    archetype_path = hull_dir / "/".join(parts)
    if not archetype_path.exists():
        return None

    data = load_yaml_file(archetype_path)

    # Parse archetype header
    header_data = data.get("archetype", {})
    header = ArchetypeHeader(
        hull=header_data.get("hull", arch_path.hull.title()),
        skill_tier=header_data.get("skill_tier", arch_path.tier),
        omega_required=header_data.get("omega_required", True),
    )

    return Archetype(
        archetype=header,
        eft=data.get("eft", ""),
        skill_requirements=_parse_skill_requirements(data.get("skill_requirements")),
        stats=_parse_stats(data.get("stats", {})),
        damage_tuning=_parse_damage_tuning(data.get("damage_tuning")),
        upgrade_path=_parse_upgrade_path(data.get("upgrade_path")),
        notes=_parse_notes(data.get("notes")),
        path=arch_path,
    )


# =============================================================================
# Archetype Discovery
# =============================================================================


def list_archetypes(hull: str | None = None) -> list[str]:
    """
    List available archetype paths.

    Args:
        hull: Optional hull name to filter by

    Returns:
        List of archetype path strings
    """
    archetypes = []
    hulls_dir = get_hulls_path()

    if not hulls_dir.exists():
        return archetypes

    # Determine directories to search
    if hull:
        hull_dir = find_hull_directory(hull)
        if hull_dir:
            search_dirs = [(hull.lower(), hull_dir)]
        else:
            return archetypes
    else:
        search_dirs = []
        for class_dir in hulls_dir.iterdir():
            if class_dir.is_dir() and not class_dir.name.startswith("_"):
                for h_dir in class_dir.iterdir():
                    if h_dir.is_dir():
                        search_dirs.append((h_dir.name, h_dir))

    # Find all archetype YAML files
    for hull_name, hull_dir in search_dirs:
        for yaml_file in hull_dir.rglob("*.yaml"):
            # Skip manifest, design docs, and tank variant meta files
            if yaml_file.name in ("manifest.yaml", "_design.md"):
                continue

            # Skip meta.yaml files that are tank variant config
            # (they have tank_variants section, not archetype fits)
            if yaml_file.name == "meta.yaml":
                # Check if parent directory has armor/shield subdirs
                parent = yaml_file.parent
                has_variant_subdirs = (
                    (parent / "armor").is_dir() or (parent / "shield").is_dir()
                )
                if has_variant_subdirs:
                    continue  # This is a variant config, not an archetype

            # Build relative path
            rel_path = yaml_file.relative_to(hull_dir)
            parts = list(rel_path.parts)

            # Remove .yaml extension from last part
            if parts[-1].endswith(".yaml"):
                parts[-1] = parts[-1][:-5]

            # Construct archetype path string
            arch_path = f"{hull_name}/{'/'.join(parts)}"
            archetypes.append(arch_path)

    return sorted(archetypes)


# =============================================================================
# Archetype Loader Class
# =============================================================================


class ArchetypeLoader:
    """
    High-level archetype loader with caching.
    """

    def __init__(self):
        self._manifest_cache: dict[str, HullManifest | None] = {}
        self._archetype_cache: dict[str, Archetype | None] = {}
        self._shared_cache: dict[str, dict] = {}

    def get_manifest(self, hull: str) -> HullManifest | None:
        """Get hull manifest with caching."""
        hull_lower = hull.lower()
        if hull_lower not in self._manifest_cache:
            self._manifest_cache[hull_lower] = load_hull_manifest(hull)
        return self._manifest_cache[hull_lower]

    def get_archetype(self, path: str) -> Archetype | None:
        """Get archetype with caching."""
        if path not in self._archetype_cache:
            self._archetype_cache[path] = load_archetype(path)
        return self._archetype_cache[path]

    def get_shared_config(self, name: str) -> dict:
        """Get shared configuration with caching."""
        if name not in self._shared_cache:
            try:
                self._shared_cache[name] = load_shared_config(name)
            except FileNotFoundError:
                self._shared_cache[name] = {}
        return self._shared_cache[name]

    def list_archetypes(self, hull: str | None = None) -> list[str]:
        """List available archetypes."""
        return list_archetypes(hull)

    def clear_cache(self):
        """Clear all caches."""
        self._manifest_cache.clear()
        self._archetype_cache.clear()
        self._shared_cache.clear()


# =============================================================================
# YAML Update Utilities
# =============================================================================


def _serialize_stats_for_yaml(stats: Stats) -> dict[str, Any]:
    """
    Convert Stats object to a dict suitable for YAML serialization.

    Only includes non-None fields to keep the YAML clean.
    """
    result: dict[str, Any] = {
        "dps": int(stats.dps) if stats.dps else 0,
        "ehp": int(stats.ehp) if stats.ehp else 0,
    }

    # Add optional legacy fields
    if stats.tank_sustained is not None:
        result["tank_sustained"] = round(stats.tank_sustained, 1)
    if stats.capacitor_stable is not None:
        result["capacitor_stable"] = stats.capacitor_stable
    if stats.align_time is not None:
        result["align_time"] = round(stats.align_time, 1)
    if stats.speed_mwd is not None:
        result["speed_mwd"] = int(stats.speed_mwd)
    if stats.speed_ab is not None:
        result["speed_ab"] = int(stats.speed_ab)
    if stats.drone_control_range is not None:
        result["drone_control_range"] = int(stats.drone_control_range)
    if stats.missile_range is not None:
        result["missile_range"] = int(stats.missile_range)

    # Add new skill-aware selection fields
    if stats.tank_type is not None:
        result["tank_type"] = stats.tank_type
    if stats.tank_regen is not None:
        result["tank_regen"] = round(stats.tank_regen, 1)
    if stats.primary_resists:
        result["primary_resists"] = stats.primary_resists
    if stats.primary_damage:
        result["primary_damage"] = stats.primary_damage
    if stats.dps_by_type is not None:
        result["dps_by_type"] = {
            k: round(v, 1) for k, v in stats.dps_by_type.items()
        }
    if stats.resists is not None:
        result["resists"] = {
            k: round(v, 1) for k, v in stats.resists.items()
        }
    if stats.estimated_isk is not None:
        result["estimated_isk"] = stats.estimated_isk
    if stats.isk_updated is not None:
        result["isk_updated"] = stats.isk_updated
    if stats.validated_date is not None:
        result["validated_date"] = stats.validated_date

    return result


def update_archetype_stats(yaml_path: Path, stats: Stats) -> None:
    """
    Update the stats section in an archetype YAML file.

    This function reads the existing file, replaces the stats section,
    and writes it back while preserving the overall structure.

    Args:
        yaml_path: Path to the archetype YAML file
        stats: Stats object with updated values

    Raises:
        FileNotFoundError: If the YAML file doesn't exist
        ValueError: If the file doesn't have a valid stats section
    """
    import re

    if not yaml_path.exists():
        raise FileNotFoundError(f"YAML file not found: {yaml_path}")

    # Read the original content
    with open(yaml_path, encoding="utf-8") as f:
        content = f.read()

    # Convert stats to YAML-ready dict
    stats_dict = _serialize_stats_for_yaml(stats)

    # Build the new stats section as YAML text
    stats_yaml = yaml.dump(
        {"stats": stats_dict},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    # Pattern to find the stats section:
    # Matches from "stats:" until the next top-level key or end of file
    # Top-level keys start at column 0 and have letters followed by colon
    stats_pattern = re.compile(
        r"^stats:\s*\n(?:(?:[ \t]+.*)?\n)*",
        re.MULTILINE,
    )

    # Find and replace the stats section
    match = stats_pattern.search(content)
    if match:
        # Replace existing stats section
        new_content = content[: match.start()] + stats_yaml + content[match.end() :]
    else:
        # No stats section found - append after eft section
        # Find where to insert (after skill_requirements or eft if no skill_requirements)
        insertion_patterns = [
            r"^skill_requirements:\s*\n(?:(?:[ \t]+.*)?\n)*",  # After skill_requirements
            r"^eft:\s*\|.*?\n(?:(?:[ \t]+.*)?\n)*",  # After eft (multiline)
        ]

        inserted = False
        for pattern in insertion_patterns:
            section_match = re.search(pattern, content, re.MULTILINE)
            if section_match:
                insert_pos = section_match.end()
                new_content = (
                    content[:insert_pos] + "\n" + stats_yaml + content[insert_pos:]
                )
                inserted = True
                break

        if not inserted:
            # Fallback: append at end
            new_content = content.rstrip() + "\n\n" + stats_yaml

    # Write back
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(new_content)


def get_archetype_yaml_path(archetype_path: str) -> Path | None:
    """
    Get the filesystem path to an archetype YAML file.

    Args:
        archetype_path: Path string like "vexor/pve/missions/l2/t1"
                       or "vexor/pve/missions/l3/armor/t2"

    Returns:
        Path to the YAML file, or None if not found
    """
    try:
        arch_path = ArchetypePath.parse(archetype_path)
    except ValueError:
        return None

    hull_dir = find_hull_directory(arch_path.hull)
    if not hull_dir:
        return None

    # Build full file path
    parts = [arch_path.activity_branch]
    if arch_path.activity:
        parts.append(arch_path.activity)
    if arch_path.level:
        parts.append(arch_path.level)
    if arch_path.variant:
        parts.append(arch_path.variant)
    parts.append(f"{arch_path.tier}.yaml")

    return hull_dir / "/".join(parts)
