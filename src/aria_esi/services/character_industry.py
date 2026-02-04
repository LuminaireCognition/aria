"""
ARIA Character Industry Service.

Fetches character blueprint and skill data from ESI for
personalized manufacturing cost calculations.
"""

from __future__ import annotations

from typing import Any, Optional

# Industry-relevant skill IDs
INDUSTRY_SKILL_IDS = {
    # Manufacturing
    "Industry": 3380,
    "Advanced Industry": 3388,
    "Mass Production": 3387,
    "Advanced Mass Production": 24625,

    # Science/Invention
    "Science": 3402,
    "Laboratory Operation": 3406,
    "Advanced Laboratory Operation": 24624,

    # Encryption methods
    "Amarr Encryption Methods": 23087,
    "Caldari Encryption Methods": 21790,
    "Gallente Encryption Methods": 23121,
    "Minmatar Encryption Methods": 21791,

    # Science skills for invention
    "Amarrian Starship Engineering": 11454,
    "Caldari Starship Engineering": 11453,
    "Gallentean Starship Engineering": 11450,
    "Minmatar Starship Engineering": 11452,
    "Electromagnetic Physics": 11433,
    "Electronic Engineering": 11443,
    "Graviton Physics": 11446,
    "High Energy Physics": 11441,
    "Hydromagnetic Physics": 11445,
    "Laser Physics": 11444,
    "Mechanical Engineering": 11442,
    "Molecular Engineering": 11448,
    "Nanite Engineering": 11449,
    "Nuclear Physics": 11447,
    "Plasma Physics": 11451,
    "Quantum Physics": 11440,
    "Rocket Science": 11529,
}

# Reverse lookup: skill_id -> skill_name
SKILL_ID_TO_NAME = {v: k for k, v in INDUSTRY_SKILL_IDS.items()}


def get_character_blueprints(
    character_id: int,
    esi_client: Any,
) -> list[dict[str, Any]]:
    """
    Fetch character's blueprints with research levels.

    Args:
        character_id: Character ID
        esi_client: Authenticated ESI client

    Returns:
        List of blueprint dicts:
        [
            {
                "type_id": int,
                "item_id": int,
                "location_id": int,
                "material_efficiency": int (0-10),
                "time_efficiency": int (0-20),
                "runs": int (-1 for BPO, >0 for BPC),
                "is_bpo": bool,
                "is_bpc": bool,
            }
        ]
    """
    try:
        blueprints = esi_client.get(f"/characters/{character_id}/blueprints/", auth=True)
    except Exception:
        return []

    if not isinstance(blueprints, list):
        return []

    result = []
    for bp in blueprints:
        quantity = bp.get("quantity", 0)

        result.append({
            "type_id": bp["type_id"],
            "item_id": bp["item_id"],
            "location_id": bp["location_id"],
            "material_efficiency": bp.get("material_efficiency", 0),
            "time_efficiency": bp.get("time_efficiency", 0),
            "runs": bp.get("runs", 0),
            "is_bpo": quantity == -1,
            "is_bpc": quantity == -2 or bp.get("runs", 0) > 0,
        })

    return result


def find_blueprint_for_item(
    blueprints: list[dict[str, Any]],
    target_type_id: int,
    prefer_bpo: bool = True,
) -> Optional[dict[str, Any]]:
    """
    Find the best blueprint for manufacturing an item.

    Args:
        blueprints: List of character blueprints
        target_type_id: Type ID of the item to manufacture
        prefer_bpo: If True, prefer BPOs over BPCs

    Returns:
        Best matching blueprint or None
    """
    # Blueprint type ID is different from product type ID
    # For most items, blueprint type_id = item type_id + some offset
    # This is a simplification - proper lookup would use SDE

    matches = []
    for bp in blueprints:
        # Direct match (for T1 items, blueprint type_id often matches)
        # Or blueprint name matches (would need type resolution)
        if bp["type_id"] == target_type_id:
            matches.append(bp)

    if not matches:
        return None

    # Sort by preference
    if prefer_bpo:
        # BPOs first, then by ME (higher is better)
        matches.sort(
            key=lambda x: (not x["is_bpo"], -x["material_efficiency"]),
        )
    else:
        # BPCs first (might have more runs), then by ME
        matches.sort(
            key=lambda x: (x["is_bpo"], -x["material_efficiency"]),
        )

    return matches[0]


def get_character_industry_skills(
    character_id: int,
    esi_client: Any,
) -> dict[str, int]:
    """
    Fetch character's industry-relevant skills.

    Args:
        character_id: Character ID
        esi_client: Authenticated ESI client

    Returns:
        Dict mapping skill name to trained level:
        {
            "Industry": 5,
            "Advanced Industry": 4,
            "Mechanical Engineering": 4,
            ...
        }
    """
    try:
        skills_data = esi_client.get(f"/characters/{character_id}/skills/", auth=True)
    except Exception:
        return {}

    if not skills_data or "skills" not in skills_data:
        return {}

    # Build skill_id -> level mapping
    skill_levels = {}
    for skill in skills_data["skills"]:
        skill_id = skill.get("skill_id")
        level = skill.get("trained_skill_level", 0)

        if skill_id in SKILL_ID_TO_NAME:
            skill_name = SKILL_ID_TO_NAME[skill_id]
            skill_levels[skill_name] = level

    return skill_levels


def get_invention_skills_for_item(
    item_name: str,
    faction: str = "Gallente",
) -> dict[str, str]:
    """
    Get the relevant invention skills for an item.

    Args:
        item_name: Item name (for determining required skills)
        faction: Item faction (Amarr, Caldari, Gallente, Minmatar)

    Returns:
        Dict with:
        - encryption_skill: Name of encryption skill
        - science_skill_1: First science skill name
        - science_skill_2: Second science skill name (may be same as first)
    """
    # Encryption skill by faction
    encryption_skills = {
        "Amarr": "Amarr Encryption Methods",
        "Caldari": "Caldari Encryption Methods",
        "Gallente": "Gallente Encryption Methods",
        "Minmatar": "Minmatar Encryption Methods",
    }

    # Default science skills (would need item-specific lookup for accuracy)
    # Ships use faction starship engineering + mechanical engineering
    # Modules vary by type

    result = {
        "encryption_skill": encryption_skills.get(faction, "Gallente Encryption Methods"),
        "science_skill_1": f"{faction}an Starship Engineering" if faction != "Minmatar" else "Minmatar Starship Engineering",
        "science_skill_2": "Mechanical Engineering",
    }

    # Adjust for known module types
    item_lower = item_name.lower()
    if any(x in item_lower for x in ["shield", "extender", "booster"]):
        result["science_skill_1"] = "Electromagnetic Physics"
        result["science_skill_2"] = "Graviton Physics"
    elif any(x in item_lower for x in ["armor", "plate", "repair"]):
        result["science_skill_1"] = "Mechanical Engineering"
        result["science_skill_2"] = "Nanite Engineering"
    elif any(x in item_lower for x in ["drone", "sentry", "hammerhead", "hobgoblin", "warrior", "acolyte"]):
        result["science_skill_1"] = "Mechanical Engineering"
        result["science_skill_2"] = "Electronic Engineering"

    return result


def calculate_character_invention_bonus(
    character_skills: dict[str, int],
    encryption_skill: str,
    science_skill_1: str,
    science_skill_2: str,
) -> float:
    """
    Calculate invention success rate bonus from character skills.

    Args:
        character_skills: Dict of skill name -> level
        encryption_skill: Name of encryption skill
        science_skill_1: Name of first science skill
        science_skill_2: Name of second science skill

    Returns:
        Skill bonus as decimal (e.g., 0.12 for 12%)
    """
    enc_level = character_skills.get(encryption_skill, 0)
    sci1_level = character_skills.get(science_skill_1, 0)
    sci2_level = character_skills.get(science_skill_2, 0)

    # Each level gives +1%
    return (enc_level + sci1_level + sci2_level) * 0.01


def summarize_industry_capabilities(
    character_skills: dict[str, int],
) -> dict[str, Any]:
    """
    Summarize character's industry capabilities.

    Args:
        character_skills: Dict of skill name -> level

    Returns:
        Summary of capabilities
    """
    # Manufacturing slots
    mass_prod = character_skills.get("Mass Production", 0)
    adv_mass_prod = character_skills.get("Advanced Mass Production", 0)
    manufacturing_slots = 1 + mass_prod + adv_mass_prod

    # Science slots
    lab_op = character_skills.get("Laboratory Operation", 0)
    adv_lab_op = character_skills.get("Advanced Laboratory Operation", 0)
    science_slots = 1 + lab_op + adv_lab_op

    # Job time reduction from Advanced Industry
    adv_industry = character_skills.get("Advanced Industry", 0)
    time_reduction = adv_industry * 0.03  # 3% per level

    # Invention bonuses by faction
    # Skill names: Amarrian, Caldari, Gallentean, Minmatar
    faction_skill_names = {
        "Amarr": "Amarrian Starship Engineering",
        "Caldari": "Caldari Starship Engineering",
        "Gallente": "Gallentean Starship Engineering",
        "Minmatar": "Minmatar Starship Engineering",
    }
    invention_bonuses = {}
    for faction in ["Amarr", "Caldari", "Gallente", "Minmatar"]:
        enc_skill = f"{faction} Encryption Methods"
        ship_skill = faction_skill_names[faction]

        enc_level = character_skills.get(enc_skill, 0)
        ship_level = character_skills.get(ship_skill, 0)

        invention_bonuses[faction] = {
            "encryption_level": enc_level,
            "starship_engineering_level": ship_level,
            "base_bonus_percent": (enc_level + ship_level) * 1,
        }

    return {
        "manufacturing_slots": manufacturing_slots,
        "science_slots": science_slots,
        "time_reduction_percent": round(time_reduction * 100, 1),
        "invention_bonuses": invention_bonuses,
        "skills": character_skills,
    }
