"""
Pilot Skill Integration for Fitting Calculations.

Provides methods to fetch pilot skills from ESI for accurate fitting
calculations. Skills affect many aspects of ship performance including
DPS, tank, capacitor, and mobility.

Two skill modes are supported:
1. All V (default): Assumes all skills at level 5 for maximum potential stats
2. Pilot Skills: Fetches actual trained skill levels from ESI

Note: Using pilot skills requires valid ESI authentication.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger

if TYPE_CHECKING:
    from aria_esi.core.auth import Credentials
    from aria_esi.models.fitting import ParsedFit

logger = get_logger(__name__)


# =============================================================================
# Skill Requirements Cache
# =============================================================================

_skill_requirements: dict[int, dict[int, int]] | None = None


def reset_skill_requirements() -> None:
    """
    Reset the skill requirements cache.

    Use for testing or to force reload from EOS data files.
    """
    global _skill_requirements
    _skill_requirements = None


def _load_skill_requirements() -> dict[int, dict[int, int]]:
    """Load skill requirements from EOS data files."""
    global _skill_requirements
    if _skill_requirements is not None:
        return _skill_requirements

    from aria_esi.fitting.eos_data import get_eos_data_manager

    data_manager = get_eos_data_manager()
    req_file = data_manager.fsd_built_path / "requiredskillsfortypes.json"

    if not req_file.exists():
        logger.warning("Skill requirements file not found: %s", req_file)
        _skill_requirements = {}
        return _skill_requirements

    with open(req_file, encoding="utf-8") as f:
        raw_data = json.load(f)

    # Convert string keys to integers
    _skill_requirements = {}
    for type_id_str, skills in raw_data.items():
        type_id = int(type_id_str)
        _skill_requirements[type_id] = {int(skill_id): level for skill_id, level in skills.items()}

    logger.debug("Loaded skill requirements for %d types", len(_skill_requirements))
    return _skill_requirements


# =============================================================================
# Exceptions
# =============================================================================


class SkillFetchError(Exception):
    """Raised when skill fetching fails."""

    def __init__(self, message: str, is_auth_error: bool = False):
        super().__init__(message)
        self.is_auth_error = is_auth_error


# =============================================================================
# Skill Fetching
# =============================================================================


class SkillFetchResult:
    """Result from fetch_pilot_skills with source tracking."""

    def __init__(self, skills: dict[int, int], source: str):
        """
        Args:
            skills: Dict mapping skill_id to level
            source: Where skills came from - "cache", "esi", or "all_v"
        """
        self.skills = skills
        self.source = source

    def __len__(self) -> int:
        return len(self.skills)


def fetch_pilot_skills(
    creds: Credentials | None = None,
    use_cache: bool = True,
    cache_ttl_hours: int = 12,
) -> SkillFetchResult:
    """
    Fetch trained skill levels, preferring cached data.

    Args:
        creds: Optional Credentials. If None, attempts to resolve from config.
        use_cache: If True, check local cache first (default True)
        cache_ttl_hours: Cache TTL in hours (default 12)

    Returns:
        SkillFetchResult with skills dict and source indicator

    Raises:
        SkillFetchError: If skill fetching fails
    """
    from aria_esi.core import (
        CredentialsError,
        ESIClient,
        ESIError,
        get_authenticated_client,
    )

    # 1. Try cache first
    if use_cache:
        from aria_esi.commands.skills import is_skills_cache_stale, load_cached_skills

        cached = load_cached_skills()
        if cached and not is_skills_cache_stale(ttl_hours=cache_ttl_hours):
            logger.info("Using cached skills (%d skills)", len(cached))
            return SkillFetchResult(cached, source="cache")
        elif cached:
            logger.debug("Cache exists but is stale, falling through to ESI")

    # 2. Fall through to ESI fetch
    try:
        if creds is None:
            client, creds = get_authenticated_client()
        else:
            client = ESIClient(token=creds.access_token)
    except CredentialsError as e:
        raise SkillFetchError(str(e), is_auth_error=True) from e

    char_id = creds.character_id

    try:
        skills_data = client.get(f"/characters/{char_id}/skills/", auth=True)
    except ESIError as e:
        raise SkillFetchError(f"Failed to fetch skills from ESI: {e.message}") from e

    if not isinstance(skills_data, dict):
        raise SkillFetchError("Invalid skills response from ESI")

    skills = skills_data.get("skills", [])

    # Build skill_id -> level mapping
    skill_levels: dict[int, int] = {}
    for skill in skills:
        skill_id = skill.get("skill_id")
        trained_level = skill.get("trained_skill_level", 0)
        if skill_id and trained_level > 0:
            skill_levels[skill_id] = trained_level

    logger.info("Fetched %d trained skills for character %d from ESI", len(skill_levels), char_id)
    return SkillFetchResult(skill_levels, source="esi")


def get_all_v_skills() -> dict[int, int] | None:
    """
    Return None to indicate all skills at level 5.

    The EOS bridge interprets None as "use all skills at level 5".
    This is useful when you want maximum potential stats without
    needing to specify individual skill levels.

    Returns:
        None (interpreted as all skills at level 5)
    """
    return None


# =============================================================================
# Common Skill Sets
# =============================================================================

# Core fitting skills that affect CPU/PG
FITTING_SKILL_IDS = [
    3318,  # Weapon Upgrades (CPU)
    3426,  # Capacitor Systems Operation (cap recharge)
    3424,  # Capacitor Management (cap capacity)
    3319,  # Advanced Weapon Upgrades (PG)
    3421,  # Capacitor Emission Systems (cap transfer)
]

# Drone skills
DRONE_SKILL_IDS = [
    3436,  # Drones
    33699,  # Medium Drone Operation
    12486,  # Drone Avionics
    3442,  # Drone Navigation
    3441,  # Drone Durability
    3443,  # Drone Interfacing
    12487,  # Heavy Drone Operation
    33697,  # Light Drone Operation
    24241,  # Drone Sharpshooting
]

# Tank skills
TANK_SKILL_IDS = [
    3392,  # Mechanics (hull HP)
    3393,  # Hull Upgrades (armor HP)
    3394,  # Shield Operation (shield HP)
    3416,  # Shield Management (shield capacity)
    3419,  # Shield Compensation (resistance)
    21059,  # Shield Upgrades (modules)
    3419,  # Armor Rigging
    26260,  # Shield Rigging
]

# Navigation skills
NAVIGATION_SKILL_IDS = [
    3449,  # Navigation
    3450,  # Afterburner
    3451,  # Warp Drive Operation
    3453,  # Evasive Maneuvering
    3454,  # Fuel Conservation
    3456,  # Acceleration Control
]


def get_relevant_skills_for_fit(fit_type: str = "generic") -> list[int]:
    """
    Get a list of skill IDs relevant for a particular fit type.

    Args:
        fit_type: Type of fit - "drone_boat", "armor_tank", "shield_tank", "generic"

    Returns:
        List of relevant skill IDs
    """
    # Start with common skills
    skills = list(FITTING_SKILL_IDS)

    if fit_type == "drone_boat":
        skills.extend(DRONE_SKILL_IDS)
    elif fit_type == "armor_tank":
        skills.extend(TANK_SKILL_IDS)
    elif fit_type == "shield_tank":
        skills.extend(TANK_SKILL_IDS)

    # Always include navigation
    skills.extend(NAVIGATION_SKILL_IDS)

    return list(set(skills))  # Remove duplicates


# =============================================================================
# Dynamic Skill Extraction
# =============================================================================

# Bonus skills that provide important effects but may not be required
# These are added at level 5 for "all V" calculations
BONUS_SKILL_IDS = {
    # Drone bonus skills
    3443: "Drone Interfacing",  # +10% drone damage per level
    24241: "Drone Sharpshooting",  # +5% drone optimal per level
    3442: "Drone Navigation",  # +5% drone MWD velocity per level
    3441: "Drone Durability",  # +5% drone shield/armor/hull per level
    # Fitting skills
    3318: "Weapon Upgrades",  # -5% CPU for weapons per level
    3319: "Advanced Weapon Upgrades",  # -2% PG for weapons per level
    # Capacitor skills
    3426: "Capacitor Systems Operation",  # -5% cap recharge time per level
    3424: "Capacitor Management",  # +5% cap capacity per level
    # Tank skills
    3392: "Mechanics",  # +5% hull HP per level
    3393: "Hull Upgrades",  # +5% armor HP per level
    3394: "Shield Operation",  # -5% shield recharge time per level
    3416: "Shield Management",  # +5% shield capacity per level
    # Navigation skills
    3449: "Navigation",  # +5% sub-warp velocity per level
    3453: "Evasive Maneuvering",  # +5% agility per level
    3456: "Acceleration Control",  # +5% AB/MWD speed boost per level
    # Engineering skills
    3413: "Power Grid Management",  # +5% powergrid per level
}


def _get_direct_requirements(type_id: int) -> dict[int, int]:
    """Get direct skill requirements for a type ID."""
    skill_reqs = _load_skill_requirements()
    return skill_reqs.get(type_id, {})


def _resolve_prerequisites(
    skill_id: int,
    resolved: dict[int, int],
    visited: set[int],
) -> None:
    """
    Recursively resolve skill prerequisites.

    Args:
        skill_id: Skill to resolve prerequisites for
        resolved: Dict to accumulate skill_id -> level mappings
        visited: Set of already visited skill IDs (cycle detection)
    """
    if skill_id in visited:
        return
    visited.add(skill_id)

    # Get prerequisites for this skill (skills are also types)
    prereqs = _get_direct_requirements(skill_id)

    for prereq_id, _required_level in prereqs.items():
        # Recursively resolve the prerequisite's prerequisites
        _resolve_prerequisites(prereq_id, resolved, visited)
        # Add prerequisite at level 5 (for all V mode)
        if prereq_id not in resolved:
            resolved[prereq_id] = 5


def extract_skills_for_fit(parsed_fit: ParsedFit, level: int = 5) -> dict[int, int]:
    """
    Extract all required and bonus skills for a parsed fit.

    Analyzes the ship, modules, rigs, subsystems, and drones to determine
    which skills are needed. Recursively resolves prerequisite skills.
    Also includes bonus skills that provide important stat bonuses.

    Args:
        parsed_fit: Parsed fit from EFT parser
        level: Skill level to set (default 5 for "all V" mode)

    Returns:
        Dict mapping skill_id to level
    """
    skills: dict[int, int] = {}
    visited: set[int] = set()

    # Collect all type IDs from the fit
    type_ids: list[int] = [parsed_fit.ship_type_id]

    # Add modules
    for module in parsed_fit.low_slots:
        type_ids.append(module.type_id)
        if module.charge_type_id:
            type_ids.append(module.charge_type_id)

    for module in parsed_fit.mid_slots:
        type_ids.append(module.type_id)
        if module.charge_type_id:
            type_ids.append(module.charge_type_id)

    for module in parsed_fit.high_slots:
        type_ids.append(module.type_id)
        if module.charge_type_id:
            type_ids.append(module.charge_type_id)

    # Add rigs
    for rig in parsed_fit.rigs:
        type_ids.append(rig.type_id)

    # Add subsystems
    for subsystem in parsed_fit.subsystems:
        type_ids.append(subsystem.type_id)

    # Add drones
    for drone in parsed_fit.drones:
        type_ids.append(drone.type_id)

    # Extract direct requirements for each type
    for type_id in type_ids:
        direct_reqs = _get_direct_requirements(type_id)
        for skill_id, _req_level in direct_reqs.items():
            # Add the required skill at the specified level
            if skill_id not in skills:
                skills[skill_id] = level

            # Resolve prerequisites for this skill
            _resolve_prerequisites(skill_id, skills, visited)

    # Add bonus skills that provide important effects
    # Only add if relevant to the fit
    has_drones = len(parsed_fit.drones) > 0

    if has_drones:
        # Add drone bonus skills
        for skill_id in [3443, 24241, 3442, 3441]:  # Drone Interfacing, etc.
            if skill_id not in skills:
                skills[skill_id] = level

    # Always add core fitting/tank/nav skills
    core_skills = [
        3318,  # Weapon Upgrades
        3426,  # Capacitor Systems Operation
        3424,  # Capacitor Management
        3392,  # Mechanics
        3393,  # Hull Upgrades
        3449,  # Navigation
        3453,  # Evasive Maneuvering
    ]

    for skill_id in core_skills:
        if skill_id not in skills:
            skills[skill_id] = level

    logger.debug(
        "Extracted %d skills for fit '%s' (ship: %s)",
        len(skills),
        parsed_fit.fit_name,
        parsed_fit.ship_type_name,
    )

    return skills
