"""
Skill-Aware Fit Selection Module.

Provides intelligent selection of archetype fits based on:
- Pilot skill levels
- Clone status (alpha/omega)
- Mission context (damage types, tank requirements)

Selection returns either a single recommended fit or
dual efficient/premium options when multiple fits qualify.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from aria_esi.core.logging import get_logger

from .loader import (
    ArchetypeLoader,
    find_hull_directory,
    load_yaml_file,
)
from .models import (
    Archetype,
    MissionContext,
    SkillTier,
)

if TYPE_CHECKING:
    from .tank_selection import TankSelectionResult

logger = get_logger(__name__)


# =============================================================================
# Selection Result
# =============================================================================


@dataclass
class FitCandidate:
    """A fit that passed initial filtering."""

    archetype: Archetype
    tier: SkillTier
    can_fly: bool
    missing_skills: list[dict] = field(default_factory=list)
    tank_adequate: bool = True
    damage_match: bool = True
    estimated_isk: int | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "tier": self.tier,
            "can_fly": self.can_fly,
            "missing_skills_count": len(self.missing_skills),
            "tank_adequate": self.tank_adequate,
            "damage_match": self.damage_match,
            "estimated_isk": self.estimated_isk,
            "archetype": self.archetype.to_dict() if self.archetype else None,
        }


@dataclass
class SelectionResult:
    """Result of fit selection."""

    # Primary recommendation
    recommended: FitCandidate | None = None

    # Alternative: efficient (lower cost) and premium (better stats)
    efficient: FitCandidate | None = None
    premium: FitCandidate | None = None

    # All candidates considered
    candidates: list[FitCandidate] = field(default_factory=list)

    # Selection metadata
    selection_mode: Literal["single", "dual", "none"] = "none"
    filters_applied: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Tank variant selection (if applicable)
    tank_selection: TankSelectionResult | None = None
    tank_variants_available: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "selection_mode": self.selection_mode,
            "filters_applied": self.filters_applied,
            "warnings": self.warnings,
            "candidates_count": len(self.candidates),
        }

        if self.recommended:
            result["recommended"] = self.recommended.to_dict()
        if self.efficient:
            result["efficient"] = self.efficient.to_dict()
        if self.premium:
            result["premium"] = self.premium.to_dict()
        if self.tank_selection:
            result["tank_selection"] = self.tank_selection.to_dict()
        if self.tank_variants_available:
            result["tank_variants_available"] = self.tank_variants_available

        return result


# =============================================================================
# Skill Requirement Checking
# =============================================================================


def _check_skill_requirements(
    archetype: Archetype,
    pilot_skills: dict[int, int],
) -> tuple[bool, list[dict]]:
    """
    Check if pilot meets skill requirements for an archetype.

    Args:
        archetype: The archetype to check
        pilot_skills: Dict mapping skill_id to trained level

    Returns:
        Tuple of (can_fly, missing_skills list)
    """
    from aria_esi.fitting import parse_eft
    from aria_esi.fitting.skills import _load_skill_requirements

    missing_skills: list[dict] = []

    # Load skill requirements database
    try:
        skill_reqs = _load_skill_requirements()
    except Exception as e:
        logger.warning("Could not load skill requirements: %s", e)
        return True, []  # Assume can fly if can't check

    # Parse EFT to get type IDs
    try:
        parsed_fit = parse_eft(archetype.eft)
    except Exception as e:
        logger.warning("Could not parse EFT for %s: %s", archetype.hull, e)
        return True, []  # Assume can fly if can't parse

    # Collect all type IDs
    type_ids: list[int] = [parsed_fit.ship_type_id]
    for module in parsed_fit.low_slots + parsed_fit.mid_slots + parsed_fit.high_slots:
        type_ids.append(module.type_id)
        if module.charge_type_id:
            type_ids.append(module.charge_type_id)
    for rig in parsed_fit.rigs:
        type_ids.append(rig.type_id)
    for drone in parsed_fit.drones:
        type_ids.append(drone.type_id)

    # Check each type
    checked: set[int] = set()
    for type_id in type_ids:
        reqs = skill_reqs.get(type_id, {})
        for skill_id, required_level in reqs.items():
            if skill_id in checked:
                continue
            checked.add(skill_id)

            current_level = pilot_skills.get(skill_id, 0)
            if current_level < required_level:
                missing_skills.append(
                    {
                        "skill_id": skill_id,
                        "required": required_level,
                        "current": current_level,
                    }
                )

    can_fly = len(missing_skills) == 0
    return can_fly, missing_skills


# =============================================================================
# Tank Adequacy Checking
# =============================================================================


def _check_tank_adequacy(
    archetype: Archetype,
    mission_context: MissionContext | None,
) -> bool:
    """
    Check if archetype's tank is adequate for the mission level.

    Args:
        archetype: The archetype to check
        mission_context: Optional mission context with level requirements

    Returns:
        True if tank is adequate
    """
    if not mission_context:
        return True

    stats = archetype.stats

    # Get tank type
    tank_type = stats.tank_type or "active"

    # Get threshold for this tank type and mission level
    threshold = mission_context.get_tank_threshold(tank_type)

    if tank_type == "buffer":
        # Buffer tank: compare EHP
        return stats.ehp >= threshold
    else:
        # Active/passive tank: compare EHP/s
        tank_regen = stats.tank_regen or stats.tank_sustained or 0
        return tank_regen >= threshold


# =============================================================================
# Damage Type Matching
# =============================================================================


def _check_damage_match(
    archetype: Archetype,
    mission_context: MissionContext | None,
) -> bool:
    """
    Check if archetype's damage type matches enemy weakness.

    Args:
        archetype: The archetype to check
        mission_context: Optional mission context with enemy weakness

    Returns:
        True if damage matches (or no context provided)
    """
    if not mission_context or not mission_context.enemy_weakness:
        return True

    stats = archetype.stats

    # Check primary damage types
    if stats.primary_damage:
        return mission_context.enemy_weakness in stats.primary_damage

    # Fallback: check damage_tuning default
    if archetype.damage_tuning:
        return archetype.damage_tuning.default_damage == mission_context.enemy_weakness

    return True  # Assume match if can't determine


# =============================================================================
# Tier Discovery
# =============================================================================

# Priority order for tier selection (best to worst)
TIER_PRIORITY: list[SkillTier] = ["t2_optimal", "t2_buffer", "t2_budget", "t2", "meta", "t1"]

# Legacy to new tier mapping for discovery
TIER_FILES: dict[str, list[str]] = {
    "t2_optimal": ["t2_optimal.yaml", "high.yaml"],
    "t2_buffer": ["t2_buffer.yaml"],
    "t2_budget": ["t2_budget.yaml"],
    "t2": ["t2.yaml"],
    "meta": ["meta.yaml", "medium.yaml"],
    "t1": ["t1.yaml", "low.yaml", "alpha.yaml"],
}


def _discover_tiers(archetype_base_path: str) -> list[tuple[SkillTier, Path]]:
    """
    Discover available tier files for an archetype path.

    Args:
        archetype_base_path: Path without tier suffix
                            e.g., "vexor/pve/missions/l2"

    Returns:
        List of (tier, file_path) tuples in priority order
    """
    # Parse path components
    parts = archetype_base_path.replace("\\", "/").split("/")
    if len(parts) < 3:
        logger.warning("Invalid archetype path: %s", archetype_base_path)
        return []

    hull = parts[0]
    activity_path = "/".join(parts[1:])

    # Find hull directory
    hull_dir = find_hull_directory(hull)
    if not hull_dir:
        logger.warning("Hull directory not found: %s", hull)
        return []

    # Check for each tier's possible file names
    found: list[tuple[SkillTier, Path]] = []

    for tier in TIER_PRIORITY:
        for filename in TIER_FILES.get(tier, []):
            file_path = hull_dir / activity_path / filename
            if file_path.exists():
                found.append((tier, file_path))
                break  # Only take first match per tier

    return found


def _discover_tank_variants(archetype_base_path: str) -> list[str]:
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


def _discover_tiers_with_variant(
    archetype_base_path: str,
    tank_variant: str | None = None,
) -> list[tuple[SkillTier, Path]]:
    """
    Discover available tier files, optionally within a tank variant subdirectory.

    Args:
        archetype_base_path: Path without tier suffix
                            e.g., "vexor/pve/missions/l3"
        tank_variant: Optional tank variant subdirectory ("armor" or "shield")

    Returns:
        List of (tier, file_path) tuples in priority order
    """
    # Parse path components
    parts = archetype_base_path.replace("\\", "/").split("/")
    if len(parts) < 3:
        logger.warning("Invalid archetype path: %s", archetype_base_path)
        return []

    hull = parts[0]
    activity_path = "/".join(parts[1:])

    # Find hull directory
    hull_dir = find_hull_directory(hull)
    if not hull_dir:
        logger.warning("Hull directory not found: %s", hull)
        return []

    # Build search path
    if tank_variant:
        search_dir = hull_dir / activity_path / tank_variant
    else:
        search_dir = hull_dir / activity_path

    if not search_dir.is_dir():
        logger.debug("Search directory not found: %s", search_dir)
        return []

    # Check for each tier's possible file names
    found: list[tuple[SkillTier, Path]] = []

    for tier in TIER_PRIORITY:
        for filename in TIER_FILES.get(tier, []):
            file_path = search_dir / filename
            if file_path.exists():
                found.append((tier, file_path))
                break  # Only take first match per tier

    return found


# =============================================================================
# Main Selection Algorithm
# =============================================================================


def select_fits(
    archetype_path: str,
    pilot_skills: dict[int, int],
    clone_status: Literal["alpha", "omega"] = "omega",
    mission_context: MissionContext | None = None,
    tank_override: str | None = None,
) -> SelectionResult:
    """
    Select appropriate fit(s) based on pilot capabilities.

    Selection algorithm:
    1. Check for tank variants and select if applicable
    2. Discover all available tiers for the archetype (in variant subdir if selected)
    3. Filter by omega_required (if alpha clone)
    4. Filter by skill requirements
    5. Optionally filter by mission context (tank, damage)
    6. Return single recommendation or dual efficient/premium

    Args:
        archetype_path: Base path without tier (e.g., "vexor/pve/missions/l2")
        pilot_skills: Dict mapping skill_id to trained level
        clone_status: "alpha" or "omega"
        mission_context: Optional mission filtering context
        tank_override: Optional explicit tank variant ("armor" or "shield")

    Returns:
        SelectionResult with recommended fit(s)
    """
    from .tank_selection import (
        TankSelectionResult,
        get_meta_yaml_path,
        load_tank_variant_config,
        select_tank_variant,
    )

    result = SelectionResult()
    loader = ArchetypeLoader()

    # Check for tank variants
    tank_variants = _discover_tank_variants(archetype_path)
    result.tank_variants_available = tank_variants

    selected_variant: str | None = None
    tank_selection: TankSelectionResult | None = None

    if tank_variants:
        # Load meta.yaml for variant configuration
        meta_path = get_meta_yaml_path(archetype_path)
        if meta_path:
            config = load_tank_variant_config(meta_path)
            if config:
                # Select tank variant based on skills or override
                tank_selection = select_tank_variant(
                    config,
                    pilot_skills,
                    tank_override,
                    available_variant_paths=tank_variants,
                )
                selected_variant = tank_selection.variant_path
                result.tank_selection = tank_selection
                result.filters_applied.append(
                    f"Tank variant: {selected_variant} ({tank_selection.selection_reason})"
                )
        elif tank_override:
            # No meta.yaml but explicit override - use it directly
            selected_variant = tank_override
            tank_selection = TankSelectionResult(
                variant=tank_override,
                variant_path=tank_override,
                selection_reason="override",
            )
            result.tank_selection = tank_selection
            result.filters_applied.append(f"Tank variant: {selected_variant} (override)")

    # Discover available tiers (with variant if selected)
    if selected_variant:
        tiers = _discover_tiers_with_variant(archetype_path, selected_variant)
    else:
        tiers = _discover_tiers(archetype_path)

    if not tiers:
        result.warnings.append(f"No archetype files found for: {archetype_path}")
        return result

    result.filters_applied.append(f"Found {len(tiers)} tier(s)")

    # Load and evaluate each tier
    flyable_candidates: list[FitCandidate] = []

    for tier, file_path in tiers:
        # Load archetype
        try:
            data = load_yaml_file(file_path)
            archetype_data = data.get("archetype", {})

            # Check omega_required
            omega_required = archetype_data.get("omega_required", True)
            if clone_status == "alpha" and omega_required:
                logger.debug("Skipping %s: omega required", tier)
                continue

            # Load full archetype
            # Include variant in path if applicable
            if selected_variant:
                tier_path = f"{archetype_path}/{selected_variant}/{tier}"
            else:
                tier_path = f"{archetype_path}/{tier}"

            archetype = loader.get_archetype(tier_path)
            if not archetype:
                # Try legacy tier name
                legacy_tier = file_path.stem
                if legacy_tier != tier:
                    if selected_variant:
                        tier_path = f"{archetype_path}/{selected_variant}/{legacy_tier}"
                    else:
                        tier_path = f"{archetype_path}/{legacy_tier}"
                    archetype = loader.get_archetype(tier_path)

            if not archetype:
                logger.warning("Could not load archetype: %s", tier_path)
                continue

            # Check skill requirements
            can_fly, missing_skills = _check_skill_requirements(archetype, pilot_skills)

            # Check tank adequacy
            tank_adequate = _check_tank_adequacy(archetype, mission_context)

            # Check damage match
            damage_match = _check_damage_match(archetype, mission_context)

            candidate = FitCandidate(
                archetype=archetype,
                tier=tier,
                can_fly=can_fly,
                missing_skills=missing_skills,
                tank_adequate=tank_adequate,
                damage_match=damage_match,
                estimated_isk=archetype.stats.estimated_isk,
            )

            result.candidates.append(candidate)

            if can_fly:
                flyable_candidates.append(candidate)

        except Exception as e:
            logger.warning("Error evaluating tier %s: %s", tier, e)
            continue

    # Filter for adequacy if mission context provided
    if mission_context:
        result.filters_applied.append("Mission context filtering")
        adequate_candidates = [c for c in flyable_candidates if c.tank_adequate and c.damage_match]
        if adequate_candidates:
            flyable_candidates = adequate_candidates
        else:
            result.warnings.append("No fits meet mission requirements; showing best available")

    # Select from flyable candidates
    if not flyable_candidates:
        result.selection_mode = "none"
        if result.candidates:
            # Show the closest candidate
            best = min(result.candidates, key=lambda c: len(c.missing_skills))
            result.recommended = best
            result.warnings.append(
                f"No flyable fits; showing {best.tier} (missing {len(best.missing_skills)} skills)"
            )
        return result

    if len(flyable_candidates) == 1:
        # Single option
        result.selection_mode = "single"
        result.recommended = flyable_candidates[0]
        result.filters_applied.append("Single fit available")
        return result

    # Multiple options: determine efficient vs premium
    # Sort by tier priority (higher tier = better stats typically)
    flyable_candidates.sort(
        key=lambda c: TIER_PRIORITY.index(c.tier) if c.tier in TIER_PRIORITY else 99
    )

    # Best stats (highest tier that's flyable)
    premium = flyable_candidates[0]

    # Most efficient (lowest tier that's flyable = cheapest)
    efficient = flyable_candidates[-1]

    if premium.tier == efficient.tier:
        # Same tier - single recommendation
        result.selection_mode = "single"
        result.recommended = premium
    else:
        # Different tiers - offer choice
        result.selection_mode = "dual"
        result.efficient = efficient
        result.premium = premium
        result.filters_applied.append("Dual efficient/premium options")

    return result


# =============================================================================
# Convenience Functions
# =============================================================================


def get_recommended_fit(
    archetype_path: str,
    pilot_skills: dict[int, int],
    clone_status: Literal["alpha", "omega"] = "omega",
) -> Archetype | None:
    """
    Get the single best recommended fit for a pilot.

    Convenience function that returns just the archetype without
    the full selection metadata.

    Args:
        archetype_path: Base path without tier
        pilot_skills: Dict mapping skill_id to level
        clone_status: "alpha" or "omega"

    Returns:
        Best fit Archetype or None if no suitable fit found
    """
    result = select_fits(archetype_path, pilot_skills, clone_status)

    if result.recommended:
        return result.recommended.archetype
    if result.efficient:
        return result.efficient.archetype
    if result.premium:
        return result.premium.archetype

    return None


def can_fly_archetype(
    archetype_path: str,
    pilot_skills: dict[int, int],
) -> tuple[bool, list[dict]]:
    """
    Check if pilot can fly a specific archetype.

    Args:
        archetype_path: Full path including tier (e.g., "vexor/pve/missions/l2/meta")
        pilot_skills: Dict mapping skill_id to level

    Returns:
        Tuple of (can_fly, missing_skills list)
    """
    loader = ArchetypeLoader()
    archetype = loader.get_archetype(archetype_path)

    if not archetype:
        return False, [{"error": f"Archetype not found: {archetype_path}"}]

    return _check_skill_requirements(archetype, pilot_skills)
