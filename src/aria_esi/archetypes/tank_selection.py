"""
Tank Variant Selection Module.

Provides skill-based selection between armor and shield tank variants
for archetypes that support multiple tank configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aria_esi.core.logging import get_logger

from .loader import find_hull_directory, load_yaml_file

logger = get_logger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class TankVariantConfig:
    """Configuration for tank variant selection from meta.yaml."""

    available: list[str] = field(default_factory=list)  # ["armor_active", "shield_buffer"]
    default: str = "armor_active"
    selection_strategy: str = "skill_based"
    skill_comparison: dict[str, Any] = field(default_factory=dict)
    tie_breaker: str = "armor"

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> TankVariantConfig:
        """Parse from YAML tank_variants section."""
        tank_variants = data.get("tank_variants", {})
        skill_comparison = data.get("skill_comparison", {})

        return cls(
            available=tank_variants.get("available", []),
            default=tank_variants.get("default", "armor_active"),
            selection_strategy=tank_variants.get("selection_strategy", "skill_based"),
            skill_comparison=skill_comparison,
            tie_breaker=skill_comparison.get("tie_breaker", "armor"),
        )


@dataclass
class TankSelectionResult:
    """Result of tank variant selection."""

    variant: str  # "armor_active" or "shield_buffer"
    variant_path: str  # "armor" or "shield" (subdirectory name)
    armor_score: float = 0.0
    shield_score: float = 0.0
    selection_reason: str = ""  # "armor_skills_higher", "shield_skills_higher", "tie_breaker", "default", "override"
    skill_details: dict[str, Any] = field(default_factory=dict)  # Detailed skill breakdown

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "variant": self.variant,
            "variant_path": self.variant_path,
            "armor_score": self.armor_score,
            "shield_score": self.shield_score,
            "selection_reason": self.selection_reason,
            "skill_details": self.skill_details,
        }


# =============================================================================
# Skill Resolution
# =============================================================================

# Common tank skill name to ID mapping
# These are the standard tank skills used for selection
TANK_SKILL_IDS: dict[str, int] = {
    # Armor skills
    "Hull Upgrades": 3393,
    "Mechanics": 3392,
    "Repair Systems": 3394,
    "Armor Rigging": 26252,
    # Shield skills
    "Shield Management": 3416,
    "Shield Operation": 3419,
    "Shield Upgrades": 21059,
    "Tactical Shield Manipulation": 3420,
}


def resolve_skill_name_to_id(skill_name: str) -> int | None:
    """
    Resolve a skill name to its type ID.

    First checks the hardcoded mapping for common tank skills,
    then falls back to database lookup if available.

    Args:
        skill_name: Skill name (e.g., "Hull Upgrades")

    Returns:
        Skill type ID or None if not found
    """
    # Check hardcoded mapping first
    if skill_name in TANK_SKILL_IDS:
        return TANK_SKILL_IDS[skill_name]

    # Try database lookup
    try:
        from aria_esi.mcp.market.database import MarketDatabase

        db = MarketDatabase()
        type_info = db.resolve_type_name(skill_name)
        if type_info:
            return type_info.type_id
    except Exception as e:
        logger.debug("Could not resolve skill name via database: %s", e)

    return None


def resolve_skill_names_to_ids(skill_names: list[str]) -> dict[str, int]:
    """
    Resolve a list of skill names to their type IDs.

    Args:
        skill_names: List of skill names

    Returns:
        Dict mapping skill name to type ID (only includes resolved names)
    """
    result: dict[str, int] = {}
    for name in skill_names:
        skill_id = resolve_skill_name_to_id(name)
        if skill_id:
            result[name] = skill_id
        else:
            logger.warning("Could not resolve skill name: %s", name)
    return result


# =============================================================================
# Score Calculation
# =============================================================================


def calculate_tank_score(
    skill_names: list[str],
    pilot_skills: dict[int, int],
    weight: float = 1.0,
) -> tuple[float, dict[str, int]]:
    """
    Calculate tank proficiency score based on pilot skills.

    Args:
        skill_names: List of skill names to check
        pilot_skills: Dict mapping skill_id to trained level
        weight: Multiplier for the final score

    Returns:
        Tuple of (score, skill_levels dict)
    """
    skill_levels: dict[str, int] = {}
    total_score = 0.0

    for skill_name in skill_names:
        skill_id = resolve_skill_name_to_id(skill_name)
        if skill_id:
            level = pilot_skills.get(skill_id, 0)
            skill_levels[skill_name] = level
            total_score += level
        else:
            skill_levels[skill_name] = 0

    return total_score * weight, skill_levels


# =============================================================================
# Variant Selection
# =============================================================================


def load_tank_variant_config(meta_path: Path) -> TankVariantConfig | None:
    """
    Load tank variant configuration from a meta.yaml file.

    Args:
        meta_path: Path to the meta.yaml file

    Returns:
        TankVariantConfig or None if file doesn't exist or has no variants
    """
    if not meta_path.exists():
        return None

    try:
        data = load_yaml_file(meta_path)
    except Exception as e:
        logger.warning("Failed to load meta.yaml: %s", e)
        return None

    config = TankVariantConfig.from_yaml(data)

    # Return None if no variants available
    if not config.available:
        return None

    return config


def select_tank_variant(
    config: TankVariantConfig,
    pilot_skills: dict[int, int],
    override: str | None = None,
) -> TankSelectionResult:
    """
    Select appropriate tank variant based on pilot skills.

    Selection algorithm:
    1. If override specified, use that directly
    2. Otherwise, calculate armor and shield scores
    3. Compare scores and select higher
    4. Use tie_breaker if scores are equal

    Args:
        config: Tank variant configuration from meta.yaml
        pilot_skills: Dict mapping skill_id to trained level
        override: Optional explicit variant ("armor" or "shield")

    Returns:
        TankSelectionResult with selected variant
    """
    # Handle explicit override
    if override:
        variant_path = override.lower()
        # Map override to variant name
        variant_name = _map_path_to_variant(variant_path, config.available)
        return TankSelectionResult(
            variant=variant_name,
            variant_path=variant_path,
            selection_reason="override",
        )

    # Get skill lists from config
    armor_config = config.skill_comparison.get("armor", {})
    shield_config = config.skill_comparison.get("shield", {})

    armor_skills = armor_config.get("skills", [])
    shield_skills = shield_config.get("skills", [])

    armor_weight = armor_config.get("weight", 1.0)
    shield_weight = shield_config.get("weight", 1.0)

    # Calculate scores
    armor_score, armor_levels = calculate_tank_score(armor_skills, pilot_skills, armor_weight)
    shield_score, shield_levels = calculate_tank_score(shield_skills, pilot_skills, shield_weight)

    # Determine selection
    if armor_score > shield_score:
        variant_path = "armor"
        selection_reason = "armor_skills_higher"
    elif shield_score > armor_score:
        variant_path = "shield"
        selection_reason = "shield_skills_higher"
    else:
        # Tie - use tie_breaker
        variant_path = config.tie_breaker
        selection_reason = "tie_breaker"

    # Map path to variant name
    variant_name = _map_path_to_variant(variant_path, config.available)

    return TankSelectionResult(
        variant=variant_name,
        variant_path=variant_path,
        armor_score=armor_score,
        shield_score=shield_score,
        selection_reason=selection_reason,
        skill_details={
            "armor": armor_levels,
            "shield": shield_levels,
        },
    )


def _map_path_to_variant(path: str, available_variants: list[str]) -> str:
    """
    Map a variant path (armor/shield) to the full variant name.

    Args:
        path: "armor" or "shield"
        available_variants: List of available variant names

    Returns:
        Full variant name (e.g., "armor_active", "shield_buffer")
    """
    for variant in available_variants:
        if variant.startswith(path):
            return variant

    # Fallback to path as variant name
    return path


# =============================================================================
# Discovery Functions
# =============================================================================


def discover_tank_variants(archetype_base_path: str) -> list[str]:
    """
    Discover available tank variant subdirectories for an archetype path.

    Args:
        archetype_base_path: Path without tier suffix
                            e.g., "vexor/pve/missions/l3"

    Returns:
        List of variant subdirectory names (e.g., ["armor", "shield"])
    """
    # Parse path components
    parts = archetype_base_path.replace("\\", "/").split("/")
    if len(parts) < 3:
        return []

    hull = parts[0]
    activity_path = "/".join(parts[1:])

    # Find hull directory
    hull_dir = find_hull_directory(hull)
    if not hull_dir:
        return []

    base_dir = hull_dir / activity_path
    if not base_dir.is_dir():
        return []

    # Check for variant subdirectories
    variants = []
    for subdir in base_dir.iterdir():
        if subdir.is_dir() and subdir.name in ("armor", "shield"):
            variants.append(subdir.name)

    return sorted(variants)


def get_meta_yaml_path(archetype_base_path: str) -> Path | None:
    """
    Get the path to meta.yaml for an archetype base path.

    Args:
        archetype_base_path: Path without tier suffix
                            e.g., "vexor/pve/missions/l3"

    Returns:
        Path to meta.yaml or None if not found
    """
    parts = archetype_base_path.replace("\\", "/").split("/")
    if len(parts) < 3:
        return None

    hull = parts[0]
    activity_path = "/".join(parts[1:])

    hull_dir = find_hull_directory(hull)
    if not hull_dir:
        return None

    meta_path = hull_dir / activity_path / "meta.yaml"
    if meta_path.exists():
        return meta_path

    return None
