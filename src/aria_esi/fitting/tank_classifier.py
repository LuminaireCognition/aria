"""
Tank Type Classifier for Ship Fittings.

Analyzes module loadout to determine tank type (active, buffer, passive)
and derives primary resist profiles from EOS data.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

from aria_esi.core.logging import get_logger

if TYPE_CHECKING:
    from aria_esi.models.fitting import ParsedFit

logger = get_logger(__name__)

TankType = Literal["active", "buffer", "passive"]

# =============================================================================
# Module Pattern Detection
# =============================================================================

# Active tank modules - repair HP over time
ACTIVE_TANK_PATTERNS = [
    # Armor
    r"armor repair",
    r"armor repairer",
    r"ancillary armor",
    # Shield
    r"shield booster",
    r"ancillary shield",
    r"shield boost amplifier",
]

# Buffer tank modules - increase raw HP
BUFFER_TANK_PATTERNS = [
    # Armor
    r"armor plate",
    r"reinforced bulkhead",
    r"armor layering",
    # Shield
    r"shield extender",
    r"shield amplifier",
]

# Passive shield tank modules - increase shield recharge
PASSIVE_TANK_PATTERNS = [
    r"shield power relay",
    r"shield flux coil",
    r"core defense field purifier",  # Rig
    r"shield recharger",
]

# Rig patterns for tank classification
ACTIVE_RIG_PATTERNS = [
    r"auxiliary nano pump",
    r"nanobot accelerator",
    r"capacitor control circuit",  # Supports active tank cap usage
]

BUFFER_RIG_PATTERNS = [
    r"trimark armor pump",
    r"core defense field extender",
]

PASSIVE_RIG_PATTERNS = [
    r"core defense field purifier",
]


def _matches_any_pattern(name: str, patterns: list[str]) -> bool:
    """Check if name matches any pattern (case-insensitive)."""
    name_lower = name.lower()
    for pattern in patterns:
        if re.search(pattern, name_lower):
            return True
    return False


# =============================================================================
# Tank Classification
# =============================================================================


def classify_tank(fit: ParsedFit) -> TankType:
    """
    Classify the tank type of a parsed fit.

    Tank types:
    - active: Uses armor repairers or shield boosters
    - buffer: Uses armor plates or shield extenders without active modules
    - passive: Uses shield power relays/purifiers for passive recharge

    Args:
        fit: ParsedFit from EFT parser

    Returns:
        TankType: "active", "buffer", or "passive"
    """
    # Collect all module names
    all_modules: list[str] = []

    for module in fit.low_slots + fit.mid_slots + fit.high_slots:
        all_modules.append(module.type_name)

    for rig in fit.rigs:
        all_modules.append(rig.type_name)

    # Count module types
    active_count = sum(1 for m in all_modules if _matches_any_pattern(m, ACTIVE_TANK_PATTERNS))
    buffer_count = sum(1 for m in all_modules if _matches_any_pattern(m, BUFFER_TANK_PATTERNS))
    passive_count = sum(1 for m in all_modules if _matches_any_pattern(m, PASSIVE_TANK_PATTERNS))

    # Check rigs for additional hints
    active_rigs = sum(1 for m in all_modules if _matches_any_pattern(m, ACTIVE_RIG_PATTERNS))
    buffer_rigs = sum(1 for m in all_modules if _matches_any_pattern(m, BUFFER_RIG_PATTERNS))
    passive_rigs = sum(1 for m in all_modules if _matches_any_pattern(m, PASSIVE_RIG_PATTERNS))

    # Classification priority:
    # 1. Active tank takes precedence (repairer/booster present)
    # 2. Passive shield tank (shield power relays without active/buffer)
    # 3. Buffer tank (plates/extenders)
    # 4. Default to buffer if no clear tank detected

    # Active tank if any active modules present
    if active_count > 0:
        logger.debug(
            "Fit '%s' classified as active tank (%d active modules, %d active rigs)",
            fit.fit_name,
            active_count,
            active_rigs,
        )
        return "active"

    # Passive shield tank - shield power relays without active modules
    if passive_count > 0 or passive_rigs > 0:
        # Only classify as passive if there are dedicated passive modules
        # and no active tank modules
        logger.debug(
            "Fit '%s' classified as passive tank (%d passive modules, %d passive rigs)",
            fit.fit_name,
            passive_count,
            passive_rigs,
        )
        return "passive"

    # Buffer tank - plates/extenders without active modules
    if buffer_count > 0 or buffer_rigs > 0:
        logger.debug(
            "Fit '%s' classified as buffer tank (%d buffer modules, %d buffer rigs)",
            fit.fit_name,
            buffer_count,
            buffer_rigs,
        )
        return "buffer"

    # Default to buffer if no clear tank type detected
    logger.debug("Fit '%s' defaulting to buffer tank (no clear tank modules)", fit.fit_name)
    return "buffer"


# =============================================================================
# Resist Profile Analysis
# =============================================================================


def derive_primary_resists(
    resists: dict[str, float],
    threshold: float = 60.0,
) -> list[str]:
    """
    Derive primary resist types from a resist profile.

    Args:
        resists: Dict mapping damage type to resist percentage
                 e.g., {"em": 75.0, "thermal": 65.0, "kinetic": 50.0, "explosive": 40.0}
        threshold: Minimum resist percentage to be considered "primary"

    Returns:
        List of damage types where resist >= threshold
        e.g., ["em", "thermal"]
    """
    primary = []
    for damage_type in ["em", "thermal", "kinetic", "explosive"]:
        resist = resists.get(damage_type, 0.0)
        if resist >= threshold:
            primary.append(damage_type)

    return primary


def derive_primary_damage(
    dps_by_type: dict[str, float],
    threshold_pct: float = 50.0,
) -> list[str]:
    """
    Derive primary damage types from DPS breakdown.

    Args:
        dps_by_type: Dict mapping damage type to DPS
                     e.g., {"em": 0, "thermal": 250, "kinetic": 50, "explosive": 0}
        threshold_pct: Minimum percentage of total DPS to be considered "primary"

    Returns:
        List of damage types that comprise >= threshold_pct of total DPS
    """
    total_dps = sum(dps_by_type.values())
    if total_dps <= 0:
        return []

    primary = []
    for damage_type in ["em", "thermal", "kinetic", "explosive"]:
        dps = dps_by_type.get(damage_type, 0.0)
        pct = (dps / total_dps) * 100
        if pct >= threshold_pct:
            primary.append(damage_type)

    # If no single type >= threshold, return the highest
    if not primary:
        max_type = max(dps_by_type.keys(), key=lambda k: dps_by_type.get(k, 0))
        if dps_by_type.get(max_type, 0) > 0:
            primary = [max_type]

    return primary


def calculate_tank_regen(
    tank_type: TankType,
    fit_stats: dict,
) -> float:
    """
    Calculate tank regeneration in EHP/s.

    For active tanks, this is the active repair rate.
    For buffer tanks, this is 0.
    For passive tanks, this is the shield recharge rate.

    Args:
        tank_type: The classified tank type
        fit_stats: Full fit statistics from EOS

    Returns:
        Tank regeneration in EHP/s
    """
    if tank_type == "buffer":
        return 0.0

    if tank_type == "passive":
        # Passive shield tank uses peak shield recharge
        # Peak recharge is at 25% shield, approximately 2.5x base rate
        capacitor = fit_stats.get("capacitor", {})
        recharge_rate = capacitor.get("recharge_rate", 0.0)
        # Note: This is a simplification. Real passive tank calculation
        # would need to account for shield HP and recharge time.
        return recharge_rate * 2.5

    # Active tank - use tank_sustained if available
    if "tank_sustained" in fit_stats.get("stats", {}):
        return fit_stats["stats"]["tank_sustained"]

    # Fallback: estimate from capacitor and rep cycle time
    # This is a rough approximation
    return 0.0


# =============================================================================
# Full Tank Analysis
# =============================================================================


def analyze_tank(fit: ParsedFit, fit_stats: dict | None = None) -> dict:
    """
    Perform full tank analysis on a fit.

    Args:
        fit: ParsedFit from EFT parser
        fit_stats: Optional full fit statistics from EOS

    Returns:
        Dict with tank analysis:
        - tank_type: "active", "buffer", or "passive"
        - tank_regen: EHP/s (0 for buffer)
        - primary_resists: List of damage types >= 60% resist
        - resists: Full resist profile (if fit_stats provided)
    """
    tank_type = classify_tank(fit)

    result: dict = {
        "tank_type": tank_type,
        "tank_regen": 0.0,
        "primary_resists": [],
    }

    if fit_stats:
        # Calculate tank regen
        result["tank_regen"] = calculate_tank_regen(tank_type, fit_stats)

        # Extract resist profile from fit stats
        tank_stats = fit_stats.get("tank", {})
        resists: dict[str, float] = {}

        # Use armor resists for armor tanks, shield for shield tanks
        # Determine which layer is primary based on EHP distribution
        armor = tank_stats.get("armor", {})
        shield = tank_stats.get("shield", {})

        armor_ehp = armor.get("ehp", 0)
        shield_ehp = shield.get("ehp", 0)

        if armor_ehp > shield_ehp:
            # Armor tank
            armor_resists = armor.get("resists", {})
            resists = {
                "em": armor_resists.get("em", 0),
                "thermal": armor_resists.get("thermal", 0),
                "kinetic": armor_resists.get("kinetic", 0),
                "explosive": armor_resists.get("explosive", 0),
            }
        else:
            # Shield tank
            shield_resists = shield.get("resists", {})
            resists = {
                "em": shield_resists.get("em", 0),
                "thermal": shield_resists.get("thermal", 0),
                "kinetic": shield_resists.get("kinetic", 0),
                "explosive": shield_resists.get("explosive", 0),
            }

        result["resists"] = resists
        result["primary_resists"] = derive_primary_resists(resists)

    return result
