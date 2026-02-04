"""
ARIA Industry Cost Service.

Calculates manufacturing job costs including system cost indices,
facility bonuses, and tax components.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Optional

# Facility data loaded from reference file
_facility_data: Optional[dict[str, Any]] = None


def _load_facility_data() -> dict[str, Any]:
    """Load facility bonus data from reference file."""
    global _facility_data
    if _facility_data is not None:
        return _facility_data

    ref_path = Path(__file__).parent.parent.parent.parent / "reference" / "industry" / "facility_bonuses.json"

    # Fallback path for installed package
    if not ref_path.exists():
        ref_path = Path("reference/industry/facility_bonuses.json")

    if ref_path.exists():
        with open(ref_path) as f:
            _facility_data = json.load(f)
    else:
        # Default data if file not found
        _facility_data = {
            "facilities": {
                "NPC Station": {"me_bonus": 0, "te_bonus": 0},
                "Raitaru": {"me_bonus": 1, "te_bonus": 15},
                "Azbel": {"me_bonus": 1, "te_bonus": 20},
                "Sotiyo": {"me_bonus": 1, "te_bonus": 30},
            },
            "taxes": {
                "scc_surcharge": {"rate": 0.04},
                "npc_facility_tax": {"rate": 0.0025},
            },
        }

    return _facility_data


def get_facility_info(facility_name: str) -> dict[str, Any]:
    """
    Get facility bonus information.

    Args:
        facility_name: Name of facility (NPC Station, Raitaru, Azbel, Sotiyo)

    Returns:
        Dict with me_bonus, te_bonus, description, notes
    """
    data = _load_facility_data()
    facilities = data.get("facilities", {})

    # Case-insensitive lookup
    for name, info in facilities.items():
        if name.lower() == facility_name.lower():
            return {"name": name, **info}

    # Default to NPC Station if not found
    return {
        "name": "NPC Station",
        "me_bonus": 0,
        "te_bonus": 0,
        "description": "Standard NPC-owned station (default)",
    }


def list_facilities() -> list[dict[str, Any]]:
    """
    List all known facilities and their bonuses.

    Returns:
        List of facility info dicts
    """
    data = _load_facility_data()
    facilities = data.get("facilities", {})

    result = []
    for name, info in facilities.items():
        result.append({"name": name, **info})

    return result


def apply_me(base_qty: int, me_level: int) -> int:
    """
    Apply Material Efficiency reduction to quantity.

    Args:
        base_qty: Base material quantity from blueprint
        me_level: ME research level (0-10)

    Returns:
        Adjusted quantity after ME reduction (ceil applied)
    """
    if me_level < 0:
        me_level = 0
    if me_level > 10:
        me_level = 10

    reduction = 1 - (me_level * 0.01)
    return math.ceil(base_qty * reduction)


def apply_facility_me(qty: int, facility_me_bonus: float) -> int:
    """
    Apply facility ME bonus to quantity.

    Args:
        qty: Material quantity after blueprint ME
        facility_me_bonus: Facility ME bonus percentage (e.g., 1 for 1%)

    Returns:
        Adjusted quantity after facility bonus
    """
    if facility_me_bonus <= 0:
        return qty

    reduction = 1 - (facility_me_bonus / 100)
    return math.ceil(qty * reduction)


def calculate_job_cost(
    estimated_item_value: float,
    system_cost_index: float,
    facility_name: str = "NPC Station",
    facility_tax: float = 0.0,
    include_scc: bool = True,
) -> dict[str, float]:
    """
    Calculate manufacturing job installation cost.

    Args:
        estimated_item_value: EIV from blueprint (sum of adjusted prices)
        system_cost_index: System manufacturing index (0.0 to 1.0, e.g., 0.05 = 5%)
        facility_name: Facility type for bonuses
        facility_tax: Structure owner's tax rate (0.0 to 0.5)
        include_scc: Include SCC surcharge (default True)

    Returns:
        Dict with cost breakdown:
        - base_cost: EIV × system_index
        - scc_surcharge: 4% of EIV
        - facility_tax: Structure tax amount
        - npc_tax: NPC facility tax (if applicable)
        - total: Sum of all components
    """
    data = _load_facility_data()
    taxes = data.get("taxes", {})

    # Get SCC surcharge rate
    scc_rate = taxes.get("scc_surcharge", {}).get("rate", 0.04)
    npc_tax_rate = taxes.get("npc_facility_tax", {}).get("rate", 0.0025)

    # Get facility info
    facility = get_facility_info(facility_name)

    # Base job cost (EIV × system index)
    # Note: Facility bonuses typically reduce this, but the formula
    # from CCP is complex. Simplified here.
    base_cost = estimated_item_value * system_cost_index

    # SCC surcharge (always 4%)
    scc_surcharge = estimated_item_value * scc_rate if include_scc else 0.0

    # Facility tax
    # NPC stations use fixed low rate, player structures use owner rate
    is_npc = facility.get("availability") != "player_structure"
    if is_npc or facility_name.lower() == "npc station":
        npc_tax = estimated_item_value * npc_tax_rate
        structure_tax = 0.0
    else:
        npc_tax = 0.0
        structure_tax = estimated_item_value * facility_tax

    total = base_cost + scc_surcharge + npc_tax + structure_tax

    return {
        "estimated_item_value": estimated_item_value,
        "system_cost_index": system_cost_index,
        "facility": facility_name,
        "base_cost": round(base_cost, 2),
        "scc_surcharge": round(scc_surcharge, 2),
        "npc_tax": round(npc_tax, 2),
        "structure_tax": round(structure_tax, 2),
        "total": round(total, 2),
    }


def estimate_total_build_cost(
    material_cost: float,
    estimated_item_value: float,
    system_cost_index: float = 0.02,
    facility_name: str = "Raitaru",
    facility_tax: float = 0.05,
) -> dict[str, Any]:
    """
    Estimate total manufacturing cost including materials and job fees.

    Args:
        material_cost: Total cost of input materials
        estimated_item_value: EIV for job cost calculation
        system_cost_index: System manufacturing index
        facility_name: Facility type
        facility_tax: Structure tax rate

    Returns:
        Dict with:
        - material_cost: Input material cost
        - job_cost: Job installation fees
        - total_cost: Sum of materials + job fees
        - cost_breakdown: Detailed job cost breakdown
    """
    job_costs = calculate_job_cost(
        estimated_item_value=estimated_item_value,
        system_cost_index=system_cost_index,
        facility_name=facility_name,
        facility_tax=facility_tax,
    )

    total = material_cost + job_costs["total"]

    return {
        "material_cost": material_cost,
        "job_cost": job_costs["total"],
        "total_cost": round(total, 2),
        "cost_breakdown": job_costs,
    }


def get_typical_system_index(system_name: str) -> float:
    """
    Get typical manufacturing cost index for a system.

    Note: This returns estimated typical values. Actual indices
    change hourly based on manufacturing activity.

    Args:
        system_name: System name

    Returns:
        Typical system cost index (0.0 to 1.0)
    """
    data = _load_facility_data()
    examples = data.get("system_cost_index_examples", {})

    # Check for known system
    for name, info in examples.items():
        if name.lower() == system_name.lower():
            typical = info.get("typical_range", [0.01, 0.02])
            return (typical[0] + typical[1]) / 2

    # Default for unknown highsec
    return 0.01


# =============================================================================
# Invention Cost Calculations
# =============================================================================

# Invention reference data cache
_invention_data: Optional[dict[str, Any]] = None


def _load_invention_data() -> dict[str, Any]:
    """Load invention reference data."""
    global _invention_data
    if _invention_data is not None:
        return _invention_data

    ref_path = Path(__file__).parent.parent.parent.parent / "reference" / "industry" / "invention_materials.json"

    # Fallback path for installed package
    if not ref_path.exists():
        ref_path = Path("reference/industry/invention_materials.json")

    if ref_path.exists():
        with open(ref_path) as f:
            _invention_data = json.load(f)
    else:
        # Minimal default data
        _invention_data = {
            "base_success_rates": {"default": 0.26},
            "decryptors": {},
            "datacore_type_ids": {},
        }

    return _invention_data


def get_decryptor_info(decryptor_name: Optional[str] = None) -> Optional[dict[str, Any]]:
    """
    Get decryptor information.

    Args:
        decryptor_name: Name of decryptor or None for no decryptor

    Returns:
        Dict with success_modifier, me_modifier, te_modifier, runs_modifier
        or None if no decryptor specified
    """
    if not decryptor_name:
        return None

    data = _load_invention_data()
    decryptors = data.get("decryptors", {})

    # Case-insensitive lookup
    for name, info in decryptors.items():
        if name.lower() == decryptor_name.lower():
            return {"name": name, **info}

    return None


def list_decryptors() -> list[dict[str, Any]]:
    """
    List all available decryptors and their effects.

    Returns:
        List of decryptor info dicts
    """
    data = _load_invention_data()
    decryptors = data.get("decryptors", {})

    result = []
    for name, info in decryptors.items():
        result.append({"name": name, **info})

    return sorted(result, key=lambda x: x.get("success_modifier", 1.0), reverse=True)


def calculate_invention_success_rate(
    base_rate: float = 0.26,
    encryption_skill: int = 0,
    science_skill_1: int = 0,
    science_skill_2: int = 0,
    decryptor: Optional[str] = None,
) -> dict[str, Any]:
    """
    Calculate invention success rate with skills and decryptor.

    Formula: base_rate × (1 + (skill_bonus)) × decryptor_modifier

    Args:
        base_rate: Base success rate (typically 0.26 for T2)
        encryption_skill: Encryption Methods skill level (0-5)
        science_skill_1: First science skill level (0-5)
        science_skill_2: Second science skill level (0-5)
        decryptor: Optional decryptor name

    Returns:
        Dict with:
        - base_rate: Starting rate
        - skill_bonus: Total skill modifier
        - decryptor_modifier: Decryptor multiplier
        - final_rate: Calculated success rate
        - expected_attempts: Average attempts needed (1/rate)
    """
    # Skill bonus: +1% per level of each skill
    skill_bonus = (encryption_skill + science_skill_1 + science_skill_2) * 0.01

    # Decryptor modifier
    decryptor_info = get_decryptor_info(decryptor)
    decryptor_modifier = decryptor_info.get("success_modifier", 1.0) if decryptor_info else 1.0

    # Calculate final rate
    # Rate cannot exceed 1.0 (100%)
    final_rate = min(base_rate * (1 + skill_bonus) * decryptor_modifier, 1.0)

    # Expected attempts = 1 / success_rate
    expected_attempts = 1 / final_rate if final_rate > 0 else float('inf')

    return {
        "base_rate": base_rate,
        "skill_bonus": round(skill_bonus, 3),
        "decryptor_modifier": decryptor_modifier,
        "decryptor_name": decryptor_info.get("name") if decryptor_info else None,
        "final_rate": round(final_rate, 4),
        "final_rate_percent": round(final_rate * 100, 2),
        "expected_attempts": round(expected_attempts, 2),
    }


def calculate_invention_cost(
    datacore_costs: dict[str, float],
    datacore_quantities: dict[str, int],
    t1_bpc_cost: float = 0.0,
    decryptor: Optional[str] = None,
    decryptor_cost: float = 0.0,
    success_rate: float = 0.26,
) -> dict[str, Any]:
    """
    Calculate expected invention cost per successful run.

    Args:
        datacore_costs: Dict mapping datacore name to unit price
        datacore_quantities: Dict mapping datacore name to quantity required
        t1_bpc_cost: Cost of T1 BPC (copying cost or market value)
        decryptor: Optional decryptor name
        decryptor_cost: Market price of decryptor (if used)
        success_rate: Invention success rate (after skills/decryptor)

    Returns:
        Dict with:
        - per_attempt_cost: Materials consumed per attempt
        - expected_cost: Average total cost for one success
        - cost_breakdown: Itemized costs
    """
    # Calculate datacore costs
    datacore_total = 0.0
    datacore_breakdown = []

    for name, qty in datacore_quantities.items():
        unit_cost = datacore_costs.get(name, 0.0)
        total = unit_cost * qty
        datacore_total += total
        datacore_breakdown.append({
            "name": name,
            "quantity": qty,
            "unit_cost": unit_cost,
            "total_cost": round(total, 2),
        })

    # Per-attempt cost
    per_attempt = datacore_total + t1_bpc_cost
    if decryptor:
        per_attempt += decryptor_cost

    # Expected cost = per_attempt / success_rate
    expected_attempts = 1 / success_rate if success_rate > 0 else float('inf')
    expected_cost = per_attempt * expected_attempts

    return {
        "per_attempt_cost": round(per_attempt, 2),
        "expected_attempts": round(expected_attempts, 2),
        "expected_cost": round(expected_cost, 2),
        "success_rate": success_rate,
        "datacore_cost": round(datacore_total, 2),
        "t1_bpc_cost": t1_bpc_cost,
        "decryptor_cost": decryptor_cost if decryptor else 0.0,
        "decryptor_name": decryptor,
        "cost_breakdown": datacore_breakdown,
    }


def calculate_t2_bpc_stats(
    base_runs: int = 10,
    decryptor: Optional[str] = None,
) -> dict[str, int]:
    """
    Calculate T2 BPC stats from invention.

    Args:
        base_runs: Base runs for the item type (ships=1, modules=10, etc.)
        decryptor: Optional decryptor name

    Returns:
        Dict with:
        - runs: Total runs on T2 BPC
        - me: Material efficiency (typically -2 + modifier)
        - te: Time efficiency (typically 0 + modifier)
    """
    decryptor_info = get_decryptor_info(decryptor)

    # Base T2 BPC values
    base_me = -2
    base_te = 0

    if decryptor_info:
        runs = base_runs + decryptor_info.get("runs_modifier", 0)
        me = base_me + decryptor_info.get("me_modifier", 0)
        te = base_te + decryptor_info.get("te_modifier", 0)
    else:
        runs = base_runs
        me = base_me
        te = base_te

    # ME can't exceed 10, runs can't be less than 1
    runs = max(1, runs)
    me = min(10, me)

    return {
        "runs": runs,
        "me": me,
        "te": te,
        "decryptor": decryptor_info.get("name") if decryptor_info else None,
    }


def estimate_t2_production_cost(
    invention_cost: float,
    t2_material_cost: float,
    t2_job_cost: float,
    t2_bpc_runs: int,
) -> dict[str, Any]:
    """
    Estimate total T2 production cost including invention.

    Args:
        invention_cost: Expected invention cost for one T2 BPC
        t2_material_cost: Material cost for one T2 unit
        t2_job_cost: Job installation cost for T2 manufacturing
        t2_bpc_runs: Number of runs on the T2 BPC

    Returns:
        Dict with:
        - invention_cost_per_unit: Amortized invention cost
        - material_cost_per_unit: T2 materials per unit
        - job_cost_per_unit: Amortized job cost
        - total_cost_per_unit: Total cost per T2 unit
        - total_batch_cost: Cost for entire BPC batch
    """
    # Amortize invention cost across all runs
    invention_per_unit = invention_cost / t2_bpc_runs

    # Job cost is typically per run, but some is fixed
    job_per_unit = t2_job_cost / t2_bpc_runs

    # Total per unit
    total_per_unit = invention_per_unit + t2_material_cost + job_per_unit

    # Total for batch
    total_batch = invention_cost + (t2_material_cost * t2_bpc_runs) + t2_job_cost

    return {
        "invention_cost_per_unit": round(invention_per_unit, 2),
        "material_cost_per_unit": round(t2_material_cost, 2),
        "job_cost_per_unit": round(job_per_unit, 2),
        "total_cost_per_unit": round(total_per_unit, 2),
        "t2_bpc_runs": t2_bpc_runs,
        "total_batch_cost": round(total_batch, 2),
    }


def get_datacore_type_id(datacore_name: str) -> Optional[int]:
    """
    Get type ID for a datacore by name.

    Args:
        datacore_name: Datacore name (e.g., "Datacore - Mechanical Engineering")

    Returns:
        Type ID or None if not found
    """
    data = _load_invention_data()
    type_ids = data.get("datacore_type_ids", {})
    return type_ids.get(datacore_name)


# =============================================================================
# Profit Per Hour Calculations
# =============================================================================


def calculate_profit_per_hour(
    gross_profit: float,
    manufacturing_time_seconds: int,
    runs: int = 1,
    te_level: int = 0,
    facility_te_bonus: float = 0.0,
) -> dict[str, Any]:
    """
    Calculate profit per hour for manufacturing.

    TE (Time Efficiency) reduces manufacturing time:
    - Blueprint TE: 0-20% reduction (0-20 levels, 1% per level)
    - Facility TE: Structure-specific bonus (e.g., Raitaru 15%, Azbel 20%)

    Formula: effective_time = base_time * (1 - te_level * 0.01) * (1 - facility_te/100)

    Args:
        gross_profit: Total profit for all runs (sell price - material cost)
        manufacturing_time_seconds: Base manufacturing time per run from blueprint
        runs: Number of manufacturing runs
        te_level: Blueprint TE research level (0-20)
        facility_te_bonus: Facility TE bonus percentage (e.g., 15 for Raitaru)

    Returns:
        Dict with:
        - profit_per_hour: ISK earned per hour of manufacturing
        - effective_time_hours: Total manufacturing time after TE reductions
        - time_per_run_seconds: Effective time per single run
        - te_savings_percent: Total time reduction from TE
    """
    # Clamp TE to valid range
    te_level = max(0, min(20, te_level))
    facility_te_bonus = max(0.0, facility_te_bonus)

    # Calculate time reduction factors
    # Blueprint TE: 1% per level (max 20%)
    te_reduction = 1 - (te_level * 0.01)
    # Facility TE: direct percentage
    facility_reduction = 1 - (facility_te_bonus / 100)

    # Total effective time for all runs
    effective_time_seconds = manufacturing_time_seconds * te_reduction * facility_reduction * runs

    # Convert to hours
    effective_hours = effective_time_seconds / 3600

    # Calculate profit per hour
    if effective_hours > 0:
        profit_per_hour = gross_profit / effective_hours
    else:
        profit_per_hour = 0.0

    # Calculate total TE savings
    total_te_savings = (1 - (te_reduction * facility_reduction)) * 100

    return {
        "profit_per_hour": round(profit_per_hour, 2),
        "effective_time_hours": round(effective_hours, 2),
        "time_per_run_seconds": round(effective_time_seconds / runs, 0) if runs > 0 else 0,
        "te_savings_percent": round(total_te_savings, 1),
    }


def format_time_duration(seconds: float) -> str:
    """
    Format seconds into human-readable duration.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "4h 30m" or "2d 6h"
    """
    if seconds <= 0:
        return "0m"

    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 and days == 0:  # Only show minutes if less than a day
        parts.append(f"{minutes}m")

    return " ".join(parts) if parts else "< 1m"


def format_isk(amount: float, precision: int = 1) -> str:
    """
    Format ISK amount with appropriate suffix.

    Args:
        amount: ISK amount
        precision: Decimal places for display

    Returns:
        Formatted string like "4.1M ISK/hr" or "250K ISK"
    """
    if abs(amount) >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.{precision}f}B ISK"
    elif abs(amount) >= 1_000_000:
        return f"{amount / 1_000_000:.{precision}f}M ISK"
    elif abs(amount) >= 1_000:
        return f"{amount / 1_000:.{precision}f}K ISK"
    else:
        return f"{amount:.0f} ISK"
