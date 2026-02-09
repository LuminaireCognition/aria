"""
Easy 80% Skill Planning MCP Tools.

Implements the "Easy 80%" philosophy for skill planning:
- Cap most skills at Level IV (80% bonus for ~20% of total time)
- Only train to V when required for T2 modules/ships
- Identify multiplier skills with outsized impact
- Suggest meta module alternatives
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.database import get_market_database

from .queries import get_sde_query_service
from .tools_skills import (
    DEFAULT_ATTRIBUTES,
    calculate_sp_for_level,
    calculate_sp_per_minute,
    format_training_time,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_sde.tools_easy80")

# =============================================================================
# Constants
# =============================================================================

# Skills that are commonly required at Level V for T2 modules/ships
# These are exceptions to the "cap at IV" rule
SKILLS_REQUIRING_V = {
    # Required for T2 drones
    "Drones": ["T2 drones", "Drone Damage Amplifier II"],
    # Required for T2 armor reps
    "Mechanics": ["Armor Repairer II", "Damage Control II"],
    # Ship prerequisites often need V
    "Spaceship Command": ["Many T2 ships"],
    # T2 weapons often need support skills at V
    "Gunnery": ["Some T2 turrets", "Damage mods"],
    "Missile Launcher Operation": ["T2 launchers", "Ballistic Control II"],
    # Mining T2
    "Mining": ["Miner II", "Strip Miner II", "Mining Barge skill"],
}

# Multiplier skills - these have outsized impact on effectiveness
MULTIPLIER_SKILLS = {
    # Drone damage - 10% per level
    "Drone Interfacing": {
        "effect": "10% drone damage per level",
        "impact": "high",
        "priority": 1,
    },
    # Turret damage
    "Surgical Strike": {
        "effect": "3% turret damage per level",
        "impact": "medium",
        "priority": 2,
    },
    "Rapid Firing": {
        "effect": "4% turret rate of fire per level",
        "impact": "medium",
        "priority": 2,
    },
    # Missile damage
    "Warhead Upgrades": {
        "effect": "2% missile damage per level",
        "impact": "medium",
        "priority": 2,
    },
    "Rapid Launch": {
        "effect": "3% missile rate of fire per level",
        "impact": "medium",
        "priority": 2,
    },
    # Tank skills
    "Repair Systems": {
        "effect": "5% armor rep amount per level",
        "impact": "medium",
        "priority": 2,
    },
    "Shield Management": {
        "effect": "5% shield HP per level",
        "impact": "medium",
        "priority": 2,
    },
    # Mining
    "Astrogeology": {
        "effect": "5% mining yield per level",
        "impact": "high",
        "priority": 1,
    },
}

# Breakpoint skills are now loaded from reference/skills/breakpoint_skills.yaml
# to allow easier updates without code changes.

# Note: Ship group to role mapping is defined in reference/skills/ship_efficacy_rules.yaml
# rather than hardcoded here, to allow easier updates without code changes.

# =============================================================================
# YAML Data Loading (cached with mtime tracking)
# =============================================================================

# Cache structure: (data, mtime) tuples for automatic invalidation on file change
_efficacy_rules_cache: tuple[dict, float] | None = None
_meta_alternatives_cache: tuple[dict, float] | None = None
_breakpoint_skills_cache: tuple[dict, float] | None = None


def reset_easy80_caches() -> None:
    """
    Reset all Easy 80% YAML caches.

    Use for testing or to force reload of configuration files.
    """
    global _efficacy_rules_cache, _meta_alternatives_cache, _breakpoint_skills_cache
    _efficacy_rules_cache = None
    _meta_alternatives_cache = None
    _breakpoint_skills_cache = None


def _is_cache_stale(cache: tuple[dict, float] | None, file_path: Path) -> bool:
    """
    Check if a cache is stale based on file modification time.

    Args:
        cache: Tuple of (data, mtime) or None
        file_path: Path to the source file

    Returns:
        True if cache is None or file has been modified since caching
    """
    if cache is None:
        return True
    if not file_path.exists():
        return True
    cached_mtime = cache[1]
    current_mtime = file_path.stat().st_mtime
    return current_mtime > cached_mtime


def _get_project_root() -> Path:
    """Find project root by searching for pyproject.toml marker file."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError(f"Could not find project root (no pyproject.toml found above {__file__})")


def _get_reference_path() -> Path:
    """Get the path to the reference/skills directory."""
    return _get_project_root() / "reference" / "skills"


def load_breakpoint_skills() -> dict:
    """
    Load breakpoint skills from YAML file.

    Returns cached result on subsequent calls. Automatically reloads
    if the file has been modified since caching.

    Raises:
        FileNotFoundError: If breakpoint_skills.yaml is missing.
    """
    global _breakpoint_skills_cache

    bp_path = _get_reference_path() / "breakpoint_skills.yaml"

    if not _is_cache_stale(_breakpoint_skills_cache, bp_path):
        return _breakpoint_skills_cache[0]

    if not bp_path.exists():
        raise FileNotFoundError(
            f"Required configuration file not found: {bp_path}. "
            "Ensure the reference/skills directory is present in the project root."
        )

    with open(bp_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    _breakpoint_skills_cache = (data, bp_path.stat().st_mtime)
    return data


def load_efficacy_rules() -> dict:
    """
    Load ship efficacy rules from YAML file.

    Returns cached result on subsequent calls. Automatically reloads
    if the file has been modified since caching.

    Raises:
        FileNotFoundError: If ship_efficacy_rules.yaml is missing.
    """
    global _efficacy_rules_cache

    rules_path = _get_reference_path() / "ship_efficacy_rules.yaml"

    if not _is_cache_stale(_efficacy_rules_cache, rules_path):
        return _efficacy_rules_cache[0]

    if not rules_path.exists():
        raise FileNotFoundError(
            f"Required configuration file not found: {rules_path}. "
            "Ensure the reference/skills directory is present in the project root."
        )

    with open(rules_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    _efficacy_rules_cache = (data, rules_path.stat().st_mtime)
    return data


def load_meta_alternatives() -> dict:
    """
    Load meta module alternatives from YAML file.

    Returns cached result on subsequent calls. Automatically reloads
    if the file has been modified since caching.

    Raises:
        FileNotFoundError: If meta_module_alternatives.yaml is missing.
    """
    global _meta_alternatives_cache

    alt_path = _get_reference_path() / "meta_module_alternatives.yaml"

    if not _is_cache_stale(_meta_alternatives_cache, alt_path):
        return _meta_alternatives_cache[0]

    if not alt_path.exists():
        raise FileNotFoundError(
            f"Required configuration file not found: {alt_path}. "
            "Ensure the reference/skills directory is present in the project root."
        )

    with open(alt_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    _meta_alternatives_cache = (data, alt_path.stat().st_mtime)
    return data


def detect_ship_roles(group_name: str | None, type_name: str | None) -> list[str]:
    """
    Detect ship roles from group name and type name.

    Args:
        group_name: Ship group (e.g., "Cruiser", "Frigate")
        type_name: Ship type name (e.g., "Vexor Navy Issue")

    Returns:
        List of detected role names (e.g., ["drone_boat", "armor_tank"])
    """
    if not group_name:
        return []

    rules = load_efficacy_rules()
    ship_roles = rules.get("ship_roles", {})

    roles = []
    group_lower = group_name.lower()
    type_lower = (type_name or "").lower()

    # Check for explicit ship mentions in example_ships
    for role_name, role_data in ship_roles.items():
        example_ships = role_data.get("example_ships", [])
        for example in example_ships:
            if example.lower() in type_lower or type_lower in example.lower():
                if role_name not in roles:
                    roles.append(role_name)

    # =========================================================================
    # Drone Boats
    # =========================================================================
    if "vexor" in type_lower or "myrmidon" in type_lower or "dominix" in type_lower:
        if "drone_boat" not in roles:
            roles.append("drone_boat")
    elif "gila" in type_lower or "ishtar" in type_lower or "rattlesnake" in type_lower:
        if "drone_boat" not in roles:
            roles.append("drone_boat")

    # =========================================================================
    # Mining Ships
    # =========================================================================
    if "venture" in type_lower or "procurer" in type_lower or "retriever" in type_lower:
        if "miner" not in roles:
            roles.append("miner")
    elif "covetor" in type_lower or "skiff" in type_lower or "mackinaw" in type_lower:
        if "miner" not in roles:
            roles.append("miner")
    elif "hulk" in type_lower or "rorqual" in type_lower:
        if "miner" not in roles:
            roles.append("miner")
    elif "barge" in group_lower or "exhumer" in group_lower:
        if "miner" not in roles:
            roles.append("miner")

    # Prospect is a gas mining ship
    if "prospect" in type_lower:
        if "miner" not in roles:
            roles.append("miner")
        if "gas_miner" not in roles:
            roles.append("gas_miner")
        if "stealth_ship" not in roles:
            roles.append("stealth_ship")  # Prospect has covert cloak

    # Endurance is an ice mining ship
    if "endurance" in type_lower:
        if "miner" not in roles:
            roles.append("miner")
        if "ice_miner" not in roles:
            roles.append("ice_miner")

    # =========================================================================
    # Exploration Ships
    # =========================================================================
    exploration_t1 = ["heron", "imicus", "probe", "magnate"]
    exploration_covops = ["helios", "anathema", "buzzard", "cheetah"]

    for ship in exploration_t1:
        if ship in type_lower:
            if "explorer" not in roles:
                roles.append("explorer")
            break

    for ship in exploration_covops:
        if ship in type_lower:
            if "explorer" not in roles:
                roles.append("explorer")
            if "stealth_ship" not in roles:
                roles.append("stealth_ship")
            break

    # Astero and Stratios are exploration + stealth
    if "astero" in type_lower or "stratios" in type_lower:
        if "explorer" not in roles:
            roles.append("explorer")
        if "stealth_ship" not in roles:
            roles.append("stealth_ship")
        if "drone_boat" not in roles:
            roles.append("drone_boat")

    # =========================================================================
    # Stealth/Covert Ops Ships
    # =========================================================================
    # Stealth Bombers
    stealth_bombers = ["hound", "nemesis", "manticore", "purifier"]
    for ship in stealth_bombers:
        if ship in type_lower:
            if "stealth_ship" not in roles:
                roles.append("stealth_ship")
            break

    # Force Recons (combat recons don't have covert cloak)
    force_recons = ["arazu", "rapier", "falcon", "pilgrim"]
    for ship in force_recons:
        if ship in type_lower:
            if "stealth_ship" not in roles:
                roles.append("stealth_ship")
            break

    # Black Ops battleships
    black_ops = ["sin", "widow", "panther", "redeemer", "marshal"]
    for ship in black_ops:
        if ship in type_lower:
            if "stealth_ship" not in roles:
                roles.append("stealth_ship")
            if "jump_capable" not in roles:
                roles.append("jump_capable")
            break

    # Group-based detection for covert ops
    if "covert ops" in group_lower or "stealth bomber" in group_lower:
        if "stealth_ship" not in roles:
            roles.append("stealth_ship")

    if "black ops" in group_lower:
        if "stealth_ship" not in roles:
            roles.append("stealth_ship")
        if "jump_capable" not in roles:
            roles.append("jump_capable")

    # =========================================================================
    # Logistics Ships
    # =========================================================================
    # T1 Logistics Cruisers
    t1_logi = ["scythe", "osprey", "augoror", "exequror"]
    for ship in t1_logi:
        if ship in type_lower:
            if "logi" not in roles:
                roles.append("logi")
            break

    # T2 Logistics Cruisers
    t2_logi = ["scimitar", "basilisk", "guardian", "oneiros"]
    for ship in t2_logi:
        if ship in type_lower:
            if "logi" not in roles:
                roles.append("logi")
            break

    # Logistics Frigates
    logi_frigs = [
        "bantam",
        "burst",
        "inquisitor",
        "navitas",
        "deacon",
        "kirin",
        "thalia",
        "scalpel",
    ]
    for ship in logi_frigs:
        if ship in type_lower:
            if "logi" not in roles:
                roles.append("logi")
            break

    # Group-based detection
    if "logistics" in group_lower:
        if "logi" not in roles:
            roles.append("logi")

    # =========================================================================
    # Capital Ships / Jump Capable
    # =========================================================================
    capital_groups = ["carrier", "dreadnought", "force auxiliary", "supercarrier", "titan"]
    for cap_group in capital_groups:
        if cap_group in group_lower:
            if "jump_capable" not in roles:
                roles.append("jump_capable")
            break

    # Jump Freighters
    jump_freighters = ["rhea", "anshar", "ark", "nomad"]
    for ship in jump_freighters:
        if ship in type_lower:
            if "jump_capable" not in roles:
                roles.append("jump_capable")
            break

    if "jump freighter" in group_lower:
        if "jump_capable" not in roles:
            roles.append("jump_capable")

    # =========================================================================
    # Active Tank Detection (ships commonly active-tanked)
    # =========================================================================
    active_tank_ships = [
        "vexor navy issue",
        "myrmidon",
        "dominix",  # Gallente active armor
        "gila",
        "rattlesnake",  # Shield boosted
        "sacrilege",
        "zealot",  # Amarr HACs
        "deimos",
        "ishtar",  # Gallente HACs
        "kronos",
        "paladin",
        "vargur",
        "golem",  # Marauders
    ]
    for ship in active_tank_ships:
        if ship in type_lower:
            if "active_tank" not in roles:
                roles.append("active_tank")
            break

    # Marauders are always active tanked
    if "marauder" in group_lower:
        if "active_tank" not in roles:
            roles.append("active_tank")

    # =========================================================================
    # Armor vs Shield Tank (Gallente/Amarr = armor, Caldari/Minmatar = shield)
    # =========================================================================
    # Gallente ships (typically armor)
    gallente_indicators = [
        "vexor",
        "thorax",
        "brutix",
        "myrmidon",
        "dominix",
        "megathron",
        "hyperion",
        "hecate",
        "ishtar",
        "deimos",
    ]
    for ship in gallente_indicators:
        if ship in type_lower:
            if "armor_tank" not in roles:
                roles.append("armor_tank")
            break

    # Amarr ships (typically armor)
    amarr_indicators = [
        "omen",
        "maller",
        "harbinger",
        "prophecy",
        "armageddon",
        "apocalypse",
        "abaddon",
        "zealot",
        "sacrilege",
        "confessor",
    ]
    for ship in amarr_indicators:
        if ship in type_lower:
            if "armor_tank" not in roles:
                roles.append("armor_tank")
            break

    # Caldari ships (typically shield)
    caldari_indicators = [
        "caracal",
        "moa",
        "drake",
        "ferox",
        "raven",
        "scorpion",
        "rokh",
        "cerberus",
        "eagle",
        "jackdaw",
    ]
    for ship in caldari_indicators:
        if ship in type_lower:
            if "shield_tank" not in roles:
                roles.append("shield_tank")
            break

    # Minmatar ships (typically shield, some armor)
    minmatar_indicators = [
        "stabber",
        "rupture",
        "hurricane",
        "cyclone",
        "typhoon",
        "tempest",
        "maelstrom",
        "vagabond",
        "muninn",
    ]
    for ship in minmatar_indicators:
        if ship in type_lower:
            if "shield_tank" not in roles:
                roles.append("shield_tank")
            break

    return roles


def get_support_skills_for_roles(roles: list[str], existing_skill_names: set[str]) -> list[dict]:
    """
    Get support skills for detected roles from efficacy rules.

    Args:
        roles: List of role names (e.g., ["drone_boat", "armor_tank"])
        existing_skill_names: Set of skill names already in the prerequisite tree

    Returns:
        List of support skill dicts with required_level based on easy_80_plan.required_5
    """
    rules = load_efficacy_rules()
    ship_roles = rules.get("ship_roles", {})

    support_skills = []
    seen_skills = set(existing_skill_names)
    required_5_skills: set[str] = set()  # Track skills that need V from easy_80_plan

    # First pass: collect all required_5 skills from easy_80_plan
    for role in roles:
        role_data = ship_roles.get(role, {})
        easy_80_plan = role_data.get("easy_80_plan", {})
        for skill_name in easy_80_plan.get("required_5", []):
            required_5_skills.add(skill_name)

    # Second pass: build support skill list
    for role in roles:
        role_data = ship_roles.get(role, {})
        skills_list = role_data.get("skills", [])

        for skill_info in skills_list:
            skill_name = skill_info.get("skill")
            if skill_name and skill_name not in seen_skills:
                seen_skills.add(skill_name)
                # Check if this skill is in required_5
                req_level = 5 if skill_name in required_5_skills else 0
                support_skills.append(
                    {
                        "skill_name": skill_name,
                        "required_level": req_level,
                        "rank": 1,  # Default, will be updated if found in SDE
                        "is_support": True,
                        "role": role,
                        "effect": skill_info.get("effect", ""),
                    }
                )

    return support_skills


# =============================================================================
# Easy 80% Calculation Functions
# =============================================================================


def calculate_efficacy(
    skills_at_level: dict[str, int],
    target_levels: dict[str, int],
    role: str | None = None,
) -> float:
    """
    Calculate approximate effectiveness percentage with role-aware weighting.

    Uses a weighted average approach that better reflects actual in-game
    effectiveness compared to pure multiplicative calculation.

    For multiplicative skills (damage mods), uses weighted average of ratios.
    Multiplier skills get higher weight than support skills.

    Args:
        skills_at_level: Current skill levels {"Drone Interfacing": 4}
        target_levels: Target levels for 100% {"Drone Interfacing": 5}
        role: Optional ship role for role-specific weighting

    Returns:
        Efficacy as percentage (0-100)
    """
    if not skills_at_level or not target_levels:
        return 100.0

    rules = load_efficacy_rules()
    ship_roles = rules.get("ship_roles", {})
    role_data = ship_roles.get(role, {}) if role else {}
    role_skills = {s.get("skill"): s for s in role_data.get("skills", [])}

    weighted_sum = 0.0
    total_weight = 0.0

    for skill, target in target_levels.items():
        current = skills_at_level.get(skill, 0)
        if target <= 0:
            continue

        ratio = current / target

        # Determine weight based on skill importance
        if skill in MULTIPLIER_SKILLS:
            # Multiplier skills have high weight
            weight = 3.0
        elif skill in role_skills:
            # Role-relevant skills from efficacy rules
            skill_info = role_skills[skill]
            per_level = skill_info.get("per_level", 5)
            # Higher per-level bonus = more important
            weight = 1.0 + (per_level / 10.0)
        else:
            # Standard prerequisite skills
            weight = 1.0

        weighted_sum += ratio * weight
        total_weight += weight

    if total_weight == 0:
        return 100.0

    efficacy = (weighted_sum / total_weight) * 100
    return round(efficacy, 1)


def generate_easy_80_plan(
    full_tree: list[dict],
    item_category: str | None = None,
    detected_roles: list[str] | None = None,
) -> dict:
    """
    Generate an Easy 80% skill plan from a full prerequisite tree.

    Rules:
    1. Prerequisites required for the item stay at their required levels
    2. Support skills (required_level=0) cap at Level IV
    3. Skills in SKILLS_REQUIRING_V at level V go to train_to_5
    4. Multiplier skills are flagged and go to cap_at_4
    5. Breakpoint skills for detected roles go to train_to_5 with breakpoint_info

    Args:
        full_tree: List of skill requirements from sde_skill_requirements
        item_category: Category of the item (Ship, Module, etc.)
        detected_roles: List of detected ship roles (e.g., ["drone_boat"])

    Returns:
        Easy 80% plan with skill groupings and time estimates
    """
    required_at_level = []  # Must be at this exact level
    cap_at_4 = []  # Can be capped at IV for Easy 80%
    train_to_5 = []  # Should train to V (T2 reqs at V or breakpoint)
    optional = []  # Nice to have but not critical
    detected_roles = detected_roles or []

    # Determine which breakpoint skills apply to detected roles
    applicable_breakpoints: dict[str, dict] = {}
    breakpoint_skills = load_breakpoint_skills()
    for skill_name, bp_info in breakpoint_skills.items():
        applies_to = bp_info.get("applies_to_roles")
        # None means applies to all combat roles
        if applies_to is None or any(role in applies_to for role in detected_roles):
            applicable_breakpoints[skill_name] = bp_info

    for skill in full_tree:
        skill_name = skill.get("skill_name", "")
        required_level = skill.get("required_level", 1)
        rank = skill.get("rank", 1)

        skill_entry = {
            "skill_name": skill_name,
            "required_level": required_level,
            "easy_80_level": required_level,  # Start at required
            "rank": rank,
            "is_multiplier": skill_name in MULTIPLIER_SKILLS,
            "is_breakpoint": skill_name in applicable_breakpoints,
            "requires_v_for_t2": skill_name in SKILLS_REQUIRING_V,
        }

        # Add multiplier info if applicable
        if skill_name in MULTIPLIER_SKILLS:
            skill_entry["multiplier_info"] = MULTIPLIER_SKILLS[skill_name]

        # Add breakpoint info if applicable
        if skill_name in applicable_breakpoints:
            skill_entry["breakpoint_info"] = applicable_breakpoints[skill_name]

        # Categorize skills - check breakpoints first (highest priority for roles)
        if skill_name in applicable_breakpoints:
            # Breakpoint skill - train to breakpoint level (usually V)
            bp_level = applicable_breakpoints[skill_name]["breakpoint_level"]
            skill_entry["easy_80_level"] = bp_level
            skill_entry["reason"] = [applicable_breakpoints[skill_name]["reason"]]
            # Also include T2 reasons if applicable
            if skill_name in SKILLS_REQUIRING_V:
                skill_entry["reason"].extend(SKILLS_REQUIRING_V[skill_name])
            train_to_5.append(skill_entry)
        elif required_level >= 5 and skill_name in SKILLS_REQUIRING_V:
            # T2 skill required at V - goes to train_to_5
            skill_entry["easy_80_level"] = 5
            skill_entry["reason"] = SKILLS_REQUIRING_V[skill_name]
            train_to_5.append(skill_entry)
        elif skill_name in MULTIPLIER_SKILLS:
            # Multiplier skill - recommend at least IV, respect if required higher
            skill_entry["easy_80_level"] = max(required_level, 4) if required_level > 0 else 4
            cap_at_4.append(skill_entry)
        elif required_level >= 1:
            # Standard prerequisite - keep at required level
            skill_entry["easy_80_level"] = required_level
            required_at_level.append(skill_entry)
        else:
            # Support skill (required_level = 0) - cap at IV
            skill_entry["easy_80_level"] = 4
            cap_at_4.append(skill_entry)

    return {
        "required_at_level": required_at_level,
        "cap_at_4": cap_at_4,
        "train_to_5": train_to_5,
        "optional": optional,
    }


def calculate_plan_training_time(
    plan: dict,
    from_levels: dict[str, int] | None = None,
    attributes: dict[str, int] | None = None,
) -> dict:
    """
    Calculate total training time for an Easy 80% plan.

    Args:
        plan: Easy 80% plan from generate_easy_80_plan
        from_levels: Current skill levels (default: all at 0)
        attributes: Character attributes (default: balanced)

    Returns:
        Training time breakdown and totals, including any skipped skills
    """
    from_levels = from_levels or {}
    attrs = attributes or DEFAULT_ATTRIBUTES

    db = get_market_database()
    conn = db._get_connection()
    query_service = get_sde_query_service()

    total_sp = 0
    total_seconds = 0
    skill_times = []
    skipped_skills = []
    warnings = []

    all_skills = (
        plan.get("required_at_level", []) + plan.get("cap_at_4", []) + plan.get("train_to_5", [])
    )

    for skill_entry in all_skills:
        skill_name = skill_entry["skill_name"]
        target_level = skill_entry.get("easy_80_level", 4)
        from_level = from_levels.get(skill_name, 0)

        if from_level >= target_level:
            continue  # Already trained

        # Look up skill for attributes
        cursor = conn.execute(
            """
            SELECT type_id FROM types
            WHERE type_name_lower = ?
            AND category_id = 16
            LIMIT 1
            """,
            (skill_name.lower(),),
        )
        row = cursor.fetchone()
        if not row:
            skipped_skills.append(skill_name)
            continue

        skill_id = row[0]
        skill_attrs = query_service.get_skill_attributes(skill_id)
        if not skill_attrs:
            skipped_skills.append(skill_name)
            continue

        rank = skill_attrs.rank

        # Calculate SP needed
        sp_at_from = calculate_sp_for_level(rank, from_level) if from_level > 0 else 0
        sp_at_to = calculate_sp_for_level(rank, target_level)
        sp_needed = sp_at_to - sp_at_from

        # Calculate training time
        sp_per_min = calculate_sp_per_minute(
            skill_attrs.primary_attribute,
            skill_attrs.secondary_attribute,
            attrs,
        )
        training_seconds = int(math.ceil((sp_needed / sp_per_min) * 60))

        total_sp += sp_needed
        total_seconds += training_seconds

        skill_times.append(
            {
                "skill_name": skill_name,
                "from_level": from_level,
                "to_level": target_level,
                "sp_needed": sp_needed,
                "training_seconds": training_seconds,
                "training_formatted": format_training_time(training_seconds),
            }
        )

    # Add warning if skills were skipped
    if skipped_skills:
        warnings.append(f"Skills not found in SDE: {', '.join(skipped_skills)}")

    return {
        "skills": skill_times,
        "total_sp": total_sp,
        "total_seconds": total_seconds,
        "total_formatted": format_training_time(total_seconds),
        "skipped_skills": skipped_skills,
        "warnings": warnings,
    }


# =============================================================================
# Standalone Implementation Functions (for dispatcher imports)
# =============================================================================


async def _easy_80_plan_impl(
    item: str,
    current_skills: dict | None = None,
    attributes: dict | None = None,
) -> dict:
    """
    Generate an Easy 80% skill plan for an item.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        item: Item name (ship, module, or skill) - case-insensitive
        current_skills: Optional dict of current skill levels
        attributes: Optional character attributes for time calculation

    Returns:
        Easy80PlanResult with categorized skill plan and time estimates
    """
    db = get_market_database()
    conn = db._get_connection()
    query_service = get_sde_query_service()

    # Normalize query
    query = item.strip()
    query_lower = query.lower()

    # Look up item (include group_name for ship role detection)
    cursor = conn.execute(
        """
        SELECT t.type_id, t.type_name, c.category_name, t.category_id, g.group_name
        FROM types t
        LEFT JOIN categories c ON t.category_id = c.category_id
        LEFT JOIN groups g ON t.group_id = g.group_id
        WHERE t.type_name_lower = ?
        LIMIT 1
        """,
        (query_lower,),
    )
    row = cursor.fetchone()

    if not row:
        # Try fuzzy match
        cursor = conn.execute(
            """
            SELECT t.type_id, t.type_name, c.category_name, t.category_id, g.group_name
            FROM types t
            LEFT JOIN categories c ON t.category_id = c.category_id
            LEFT JOIN groups g ON t.group_id = g.group_id
            WHERE t.type_name_lower LIKE ?
            AND t.published = 1
            ORDER BY length(t.type_name)
            LIMIT 1
            """,
            (f"{query_lower}%",),
        )
        row = cursor.fetchone()

    if not row:
        return {
            "item": query,
            "found": False,
            "error": f"Item '{query}' not found in SDE.",
        }

    type_id, type_name, category_name, category_id, group_name = row
    warnings: list[str] = []
    detected_roles: list[str] = []

    # Get full prerequisite tree
    tree_data = query_service.get_full_skill_tree(type_id)
    full_tree = []

    for skill_id, skill_name, level, rank in tree_data:
        attrs = query_service.get_skill_attributes(skill_id)
        full_tree.append(
            {
                "skill_id": skill_id,
                "skill_name": skill_name,
                "required_level": level,
                "rank": rank,
                "primary_attribute": attrs.primary_attribute if attrs else None,
                "secondary_attribute": attrs.secondary_attribute if attrs else None,
            }
        )

    # Check for empty skill data
    if not tree_data:
        # Check if skill tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='skill_attributes'"
        )
        tables_exist = cursor.fetchone() is not None

        if not tables_exist:
            warnings.append(
                "Skill data tables not found. Run 'aria-esi sde-seed' to import skill data."
            )
        else:
            # Tables exist but no tree data - might be an item without skill requirements
            direct_reqs = query_service.get_type_skill_requirements(type_id)
            if direct_reqs:
                warnings.append(
                    "Skill prerequisite data may be incomplete. "
                    "Run 'aria-esi sde-seed' to update SDE skill tables."
                )

    # For ships, detect roles and add support skills
    if category_name == "Ship":
        detected_roles = detect_ship_roles(group_name, type_name)
        if detected_roles:
            existing_skill_names: set[str] = {str(s["skill_name"]) for s in full_tree}
            support_skills = get_support_skills_for_roles(detected_roles, existing_skill_names)

            # Look up actual skill attributes for support skills
            for support_skill in support_skills:
                skill_name_lower = support_skill["skill_name"].lower()
                cursor = conn.execute(
                    """
                    SELECT type_id FROM types
                    WHERE type_name_lower = ?
                    AND category_id = 16
                    LIMIT 1
                    """,
                    (skill_name_lower,),
                )
                skill_row = cursor.fetchone()
                if skill_row:
                    skill_id = skill_row[0]
                    attrs = query_service.get_skill_attributes(skill_id)
                    if attrs:
                        support_skill["skill_id"] = skill_id
                        support_skill["rank"] = attrs.rank
                        support_skill["primary_attribute"] = attrs.primary_attribute
                        support_skill["secondary_attribute"] = attrs.secondary_attribute
                    full_tree.append(support_skill)

    # Generate Easy 80% plan
    plan = generate_easy_80_plan(full_tree, category_name, detected_roles)

    # Calculate training times
    current = current_skills or {}
    time_estimate = calculate_plan_training_time(plan, current, attributes)

    # Merge any warnings from training time calculation
    warnings.extend(time_estimate.get("warnings", []))

    # Calculate full training time for comparison
    full_time_seconds = 0
    for skill in full_tree:
        skill_name = str(skill["skill_name"])
        target = 5  # Full mastery
        from_level = current.get(skill_name, 0)
        if from_level >= target:
            continue
        rank = int(skill.get("rank", 1))
        sp_at_from = calculate_sp_for_level(rank, from_level) if from_level > 0 else 0
        sp_at_to = calculate_sp_for_level(rank, target)
        sp_needed = sp_at_to - sp_at_from
        primary_attr = skill.get("primary_attribute")
        secondary_attr = skill.get("secondary_attribute")
        sp_per_min = calculate_sp_per_minute(
            str(primary_attr) if primary_attr else None,
            str(secondary_attr) if secondary_attr else None,
            attributes or DEFAULT_ATTRIBUTES,
        )
        full_time_seconds += int(math.ceil((sp_needed / sp_per_min) * 60))

    # Calculate efficacy estimate
    easy_80_levels = {}
    full_levels = {}
    for skill in full_tree:
        skill_name = str(skill["skill_name"])
        # Find the easy 80 level for this skill
        for category in ["required_at_level", "cap_at_4", "train_to_5"]:
            for s in plan.get(category, []):
                if s["skill_name"] == skill_name:
                    easy_80_levels[skill_name] = s.get("easy_80_level", 4)
                    break
        full_levels[skill_name] = 5

    # Use first detected role for efficacy calculation weighting
    primary_role = detected_roles[0] if detected_roles else None
    efficacy = calculate_efficacy(easy_80_levels, full_levels, role=primary_role)

    # Determine item role for meta suggestions using YAML data
    meta_suggestions = []
    meta_alternatives = load_meta_alternatives()

    if category_name == "Module":
        # Check if any required skills need V
        # Search both required_at_level AND train_to_5 since V-level skills
        # in SKILLS_REQUIRING_V are categorized into train_to_5
        for category in ["required_at_level", "train_to_5"]:
            for skill in plan.get(category, []):
                if skill["required_level"] == 5 and skill["skill_name"] in SKILLS_REQUIRING_V:
                    # Look for specific meta alternative for this module
                    suggestion_text = "Consider meta 4 alternative module"

                    # Search for the module in meta_alternatives YAML
                    for category_data in meta_alternatives.values():
                        if isinstance(category_data, dict) and type_name in category_data:
                            module_data = category_data[type_name]
                            if isinstance(module_data, dict):
                                meta_alt = module_data.get("meta_alternative", {})
                                if meta_alt and meta_alt.get("name"):
                                    eff = meta_alt.get("effectiveness", "")
                                    eff_str = f" ({eff}% effectiveness)" if eff else ""
                                    suggestion_text = f"Consider {meta_alt['name']}{eff_str}"
                            break

                    meta_suggestions.append(
                        {
                            "skill": skill["skill_name"],
                            "reason": f"Required at V for {type_name}",
                            "suggestion": suggestion_text,
                        }
                    )

    return {
        "item": type_name,
        "item_category": category_name,
        "found": True,
        "easy_80_plan": {
            "required_at_level": plan.get("required_at_level", []),
            "cap_at_4": plan.get("cap_at_4", []),
            "train_to_5": plan.get("train_to_5", []),
        },
        "easy_80_time": {
            "total_seconds": time_estimate["total_seconds"],
            "total_formatted": time_estimate["total_formatted"],
            "skills": time_estimate["skills"],
        },
        "full_mastery_time": {
            "total_seconds": full_time_seconds,
            "total_formatted": format_training_time(full_time_seconds),
        },
        "time_savings": {
            "seconds_saved": full_time_seconds - time_estimate["total_seconds"],
            "formatted_saved": format_training_time(
                full_time_seconds - time_estimate["total_seconds"]
            ),
            "percentage_saved": round(
                (1 - time_estimate["total_seconds"] / max(full_time_seconds, 1)) * 100, 1
            ),
        },
        "efficacy_estimate": efficacy,
        "meta_suggestions": meta_suggestions,
        "multiplier_skills": [s for s in plan.get("cap_at_4", []) if s.get("is_multiplier")],
        "breakpoint_skills": [s for s in plan.get("train_to_5", []) if s.get("is_breakpoint")],
        "detected_roles": detected_roles,
        "warnings": warnings,
    }


async def _get_multipliers_impl(role: str | None = None) -> dict:
    """
    Get high-impact "multiplier" skills for a role.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        role: Optional role filter

    Returns:
        List of multiplier skills with their effects and priority
    """
    role_filters = {
        # Combat roles
        "drone_boat": ["Drone Interfacing"],
        "drones": ["Drone Interfacing"],
        "turret_boat": ["Surgical Strike", "Rapid Firing"],
        "turret": ["Surgical Strike", "Rapid Firing"],
        "turrets": ["Surgical Strike", "Rapid Firing"],
        "missile_boat": ["Warhead Upgrades", "Rapid Launch"],
        "missile": ["Warhead Upgrades", "Rapid Launch"],
        "missiles": ["Warhead Upgrades", "Rapid Launch"],
        # Tank roles
        "tank": ["Repair Systems", "Shield Management"],
        "armor_tank": ["Repair Systems"],
        "armor": ["Repair Systems"],
        "shield_tank": ["Shield Management"],
        "shield": ["Shield Management"],
        "active_tank": ["Repair Systems", "Shield Management"],
        # Industrial roles
        "mining": ["Astrogeology"],
        "miner": ["Astrogeology"],
    }

    if role:
        role_lower = role.lower()
        if role_lower in role_filters:
            filtered = {k: v for k, v in MULTIPLIER_SKILLS.items() if k in role_filters[role_lower]}
            return {
                "role": role,
                "multiplier_skills": [{"skill_name": k, **v} for k, v in filtered.items()],
            }

    # Deduplicate role names for display (prefer canonical names)
    canonical_roles = [
        "drone_boat",
        "turret_boat",
        "missile_boat",
        "armor_tank",
        "shield_tank",
        "active_tank",
        "miner",
    ]
    return {
        "role": "all",
        "multiplier_skills": [{"skill_name": k, **v} for k, v in MULTIPLIER_SKILLS.items()],
        "available_roles": canonical_roles,
    }


async def _get_breakpoints_impl(
    role: str | None = None,
    category_filter: str | None = None,
) -> dict:
    """
    Get breakpoint skills where specific levels unlock non-linear gameplay effects.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        role: Optional role filter
        category_filter: Optional category filter

    Returns:
        List of breakpoint skills with their effects and applicable roles
    """
    filtered = {}
    breakpoint_skills = load_breakpoint_skills()

    for skill_name, bp_info in breakpoint_skills.items():
        applies_to = bp_info.get("applies_to_roles")
        bp_category = bp_info.get("category", "universal")

        # Role filter
        role_match = True
        if role:
            role_lower = role.lower()
            # None means universal (matches all), otherwise check role match
            if applies_to is not None and role_lower not in applies_to:
                role_match = False

        # Category filter
        category_match = True
        if category_filter:
            category_lower = category_filter.lower()
            if bp_category.lower() != category_lower:
                category_match = False

        if role_match and category_match:
            filtered[skill_name] = bp_info

    if role or category_filter:
        return {
            "role": role or "all",
            "category": category_filter or "all",
            "breakpoint_skills": [{"skill_name": k, **v} for k, v in filtered.items()],
        }

    # All breakpoint skills with their applicable roles and categories
    all_roles = set()
    all_categories = set()
    for bp_info in breakpoint_skills.values():
        applies_to = bp_info.get("applies_to_roles")
        if applies_to:
            all_roles.update(applies_to)
        bp_category = bp_info.get("category")
        if bp_category:
            all_categories.add(bp_category)

    return {
        "role": "all",
        "category": "all",
        "breakpoint_skills": [{"skill_name": k, **v} for k, v in breakpoint_skills.items()],
        "available_roles": sorted(all_roles),
        "available_categories": sorted(all_categories),
    }


async def _t2_requirements_impl(item: str) -> dict:
    """
    Check what Level V skills are required for a T2 item.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        item: T2 item name (module, ship, drone)

    Returns:
        List of skills requiring V and possible alternatives
    """
    db = get_market_database()
    conn = db._get_connection()
    query_service = get_sde_query_service()

    # Normalize query
    query = item.strip()
    query_lower = query.lower()

    # Look up item
    cursor = conn.execute(
        """
        SELECT t.type_id, t.type_name, c.category_name, g.group_name
        FROM types t
        LEFT JOIN categories c ON t.category_id = c.category_id
        LEFT JOIN groups g ON t.group_id = g.group_id
        WHERE t.type_name_lower = ?
        LIMIT 1
        """,
        (query_lower,),
    )
    row = cursor.fetchone()

    if not row:
        return {
            "item": query,
            "found": False,
            "error": f"Item '{query}' not found.",
        }

    type_id, type_name, category_name, group_name = row

    # Check if it's T2 (name ends in II or contains "II")
    is_t2 = " II" in type_name or type_name.endswith(" II")

    # Get skill requirements
    reqs = query_service.get_type_skill_requirements(type_id)

    skills_at_v = []
    skills_below_v = []
    meta_alternatives = []

    for req in reqs:
        if req.required_level == 5:
            skills_at_v.append(
                {
                    "skill_name": req.skill_name,
                    "skill_id": req.skill_id,
                    "level": 5,
                    "unlocks": SKILLS_REQUIRING_V.get(req.skill_name, []),
                }
            )
            # Suggest alternative
            if req.skill_name in SKILLS_REQUIRING_V:
                meta_alternatives.append(
                    {
                        "skill": req.skill_name,
                        "suggestion": f"Consider meta 4 or T1 version of {type_name}",
                    }
                )
        else:
            skills_below_v.append(
                {
                    "skill_name": req.skill_name,
                    "skill_id": req.skill_id,
                    "level": req.required_level,
                }
            )

    return {
        "item": type_name,
        "category": category_name,
        "group": group_name,
        "is_t2": is_t2,
        "found": True,
        "skills_requiring_v": skills_at_v,
        "skills_below_v": skills_below_v,
        "total_v_requirements": len(skills_at_v),
        "meta_alternatives": meta_alternatives,
        "easy_80_verdict": (
            "Achievable at Easy 80%"
            if len(skills_at_v) == 0
            else f"Requires {len(skills_at_v)} skill(s) at V - consider alternatives"
        ),
    }


# =============================================================================
# MCP Tool Registration
# =============================================================================


def register_easy80_tools(server: FastMCP) -> None:
    """Register Easy 80% MCP tools with the server."""

    @server.tool()
    async def skill_easy_80_plan(
        item: str,
        current_skills: dict | None = None,
        attributes: dict | None = None,
    ) -> dict:
        """
        Generate an Easy 80% skill plan for an item.

        The Easy 80% philosophy caps most skills at Level IV, achieving
        ~80% effectiveness with ~20% of the training time. Only trains
        to Level V when required for T2 modules or ships.

        Args:
            item: Item name (ship, module, or skill) - case-insensitive
            current_skills: Optional dict of current skill levels
                           {"Drones": 4, "Drone Interfacing": 3}
            attributes: Optional character attributes for time calculation

        Returns:
            Easy80PlanResult with categorized skill plan and time estimates

        Examples:
            skill_easy_80_plan("Vexor Navy Issue")
            skill_easy_80_plan("Medium Armor Repairer II")
            skill_easy_80_plan("Vexor", current_skills={"Gallente Cruiser": 3})
        """
        return await _easy_80_plan_impl(item, current_skills, attributes)

    @server.tool()
    async def skill_get_multipliers(
        role: str | None = None,
    ) -> dict:
        """
        Get high-impact "multiplier" skills for a role.

        Multiplier skills have outsized impact on effectiveness and
        should be prioritized in training plans.

        Args:
            role: Optional role filter. Available roles:
                  Combat: drone_boat, turret_boat, missile_boat
                  Tank: armor_tank, shield_tank, active_tank
                  Industrial: miner
                 If not specified, returns all multiplier skills.

        Returns:
            List of multiplier skills with their effects and priority

        Examples:
            skill_get_multipliers()  # All multipliers
            skill_get_multipliers("drone_boat")  # Drone-specific
        """
        return await _get_multipliers_impl(role)

    @server.tool()
    async def skill_get_breakpoints(
        role: str | None = None,
        category: str | None = None,
    ) -> dict:
        """
        Get breakpoint skills where specific levels unlock non-linear gameplay effects.

        Unlike multiplier skills (percentage bonuses per level), breakpoint skills
        unlock discrete capabilities at specific levels that dramatically change
        effectiveness. These override the "cap at IV" Easy 80% rule.

        Args:
            role: Optional role filter. Available roles:
                  Combat: drone_boat, turret_boat, missile_boat
                  Tank: armor_tank, active_tank
                  Stealth: stealth_ship, explorer
                  Industrial: miner, gas_miner, ice_miner
                  Capital: jump_capable, capital_support
                  Logistics: logi
                  If not specified, returns all breakpoint skills.
            category: Optional category filter. Available categories:
                      combat, tank, stealth, industrial, exploration, capital, logi, universal
                      If not specified, returns all categories.

        Returns:
            List of breakpoint skills with their effects and applicable roles

        Examples:
            skill_get_breakpoints()  # All breakpoints
            skill_get_breakpoints("drone_boat")  # Drone-specific (Drones V)
            skill_get_breakpoints(category="stealth")  # All stealth breakpoints
            skill_get_breakpoints("explorer", "exploration")  # Explorer + exploration category
        """
        return await _get_breakpoints_impl(role, category)

    @server.tool()
    async def skill_t2_requirements(
        item: str,
    ) -> dict:
        """
        Check what Level V skills are required for a T2 item.

        T2 modules and ships often require specific skills at Level V.
        This tool identifies those requirements and suggests alternatives.

        Args:
            item: T2 item name (module, ship, drone)

        Returns:
            List of skills requiring V and possible alternatives

        Examples:
            skill_t2_requirements("Medium Armor Repairer II")
            skill_t2_requirements("Hammerhead II")
        """
        return await _t2_requirements_impl(item)
