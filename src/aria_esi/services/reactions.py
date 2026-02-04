"""
ARIA Reactions Service.

Calculates costs and profitability for moon goo reactions and fuel blocks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from aria_esi.core.logging import get_logger

logger = get_logger(__name__)

# Cache for fuel block data
_fuel_block_data: Optional[dict[str, Any]] = None


def _load_fuel_block_data() -> dict[str, Any]:
    """Load fuel block reference data."""
    global _fuel_block_data
    if _fuel_block_data is not None:
        return _fuel_block_data

    ref_path = Path(__file__).parent.parent.parent / "reference" / "industry" / "fuel_blocks.json"

    # Fallback path for installed package
    if not ref_path.exists():
        ref_path = Path("reference/industry/fuel_blocks.json")

    if ref_path.exists():
        with open(ref_path) as f:
            _fuel_block_data = json.load(f)
    else:
        # Minimal default data
        _fuel_block_data = {
            "fuel_blocks": {},
            "reaction_time_modifiers": {
                "per_level_reduction": 0.04,
                "max_level": 5,
            },
            "refinery_bonuses": {},
        }

    return _fuel_block_data


def get_fuel_block_info(fuel_block_name: str) -> Optional[dict[str, Any]]:
    """
    Get fuel block recipe information.

    Args:
        fuel_block_name: Name of fuel block (e.g., "Nitrogen Fuel Block")

    Returns:
        Dict with inputs, output_quantity, cycle_time_seconds, faction, isotope
        or None if not found
    """
    data = _load_fuel_block_data()
    fuel_blocks = data.get("fuel_blocks", {})

    # Case-insensitive lookup
    for name, info in fuel_blocks.items():
        if name.lower() == fuel_block_name.lower():
            return {"name": name, **info}

    # Try partial match
    name_lower = fuel_block_name.lower()
    for name, info in fuel_blocks.items():
        if name_lower in name.lower():
            return {"name": name, **info}

    return None


def list_fuel_blocks() -> list[dict[str, Any]]:
    """
    List all fuel block types.

    Returns:
        List of fuel block info dicts
    """
    data = _load_fuel_block_data()
    fuel_blocks = data.get("fuel_blocks", {})

    result = []
    for name, info in fuel_blocks.items():
        result.append({"name": name, **info})

    return sorted(result, key=lambda x: x["name"])


def get_refinery_info(refinery_name: str) -> dict[str, Any]:
    """
    Get refinery bonus information.

    Args:
        refinery_name: Name of refinery (Athanor or Tatara)

    Returns:
        Dict with reaction_time_bonus, reaction_slots, description
    """
    data = _load_fuel_block_data()
    refineries = data.get("refinery_bonuses", {})

    # Case-insensitive lookup
    for name, info in refineries.items():
        if name.lower() == refinery_name.lower():
            return {"name": name, **info}

    # Default to Athanor if not found
    return {
        "name": "Athanor",
        "description": "Medium refinery (default)",
        "reaction_time_bonus": 0,
        "reaction_slots": 3,
    }


def calculate_reaction_time(
    base_cycle_seconds: int,
    reactions_skill: int = 0,
    refinery_name: str = "Athanor",
    runs: int = 1,
) -> dict[str, Any]:
    """
    Calculate effective reaction time with skills and bonuses.

    Reactions skill reduces cycle time by 4% per level.
    Tatara refinery provides additional 25% reduction.

    Formula: effective_time = base_time * (1 - skill * 0.04) * (1 - refinery_bonus)

    Args:
        base_cycle_seconds: Base cycle time from reaction formula
        reactions_skill: Reactions skill level (0-5)
        refinery_name: Refinery type (Athanor or Tatara)
        runs: Number of reaction runs

    Returns:
        Dict with effective_time_seconds, time_per_run, total_runs_time,
        skill_reduction_percent, refinery_reduction_percent
    """
    data = _load_fuel_block_data()
    modifiers = data.get("reaction_time_modifiers", {})

    # Clamp skill to valid range
    reactions_skill = max(0, min(5, reactions_skill))

    # Skill reduction
    per_level = modifiers.get("per_level_reduction", 0.04)
    skill_reduction = reactions_skill * per_level

    # Refinery bonus
    refinery = get_refinery_info(refinery_name)
    refinery_bonus = refinery.get("reaction_time_bonus", 0)

    # Calculate effective time
    # Bonuses are multiplicative
    skill_factor = 1 - skill_reduction
    refinery_factor = 1 - refinery_bonus

    effective_cycle = base_cycle_seconds * skill_factor * refinery_factor
    total_time = effective_cycle * runs

    return {
        "base_cycle_seconds": base_cycle_seconds,
        "effective_cycle_seconds": round(effective_cycle),
        "total_time_seconds": round(total_time),
        "total_time_hours": round(total_time / 3600, 2),
        "runs": runs,
        "skill_reduction_percent": round(skill_reduction * 100, 1),
        "refinery_reduction_percent": round(refinery_bonus * 100, 1),
        "total_reduction_percent": round((1 - skill_factor * refinery_factor) * 100, 1),
        "refinery": refinery["name"],
    }


def calculate_fuel_block_cost(
    fuel_block_name: str,
    material_prices: dict[str, float],
    reactions_skill: int = 0,
    refinery_name: str = "Athanor",
    runs: int = 1,
) -> dict[str, Any]:
    """
    Calculate fuel block production cost.

    Args:
        fuel_block_name: Name of fuel block
        material_prices: Dict mapping material name to unit price
        reactions_skill: Reactions skill level (0-5)
        refinery_name: Refinery type
        runs: Number of reaction runs

    Returns:
        Dict with cost breakdown, production time, cost per unit
    """
    fb_info = get_fuel_block_info(fuel_block_name)
    if not fb_info:
        return {"error": f"Unknown fuel block: {fuel_block_name}"}

    inputs = fb_info.get("inputs", {})
    output_qty = fb_info.get("output_quantity", 40)
    cycle_time = fb_info.get("cycle_time_seconds", 900)

    # Calculate input costs
    material_costs = []
    total_input_cost = 0.0
    missing_prices = []

    for material, quantity in inputs.items():
        total_qty = quantity * runs
        unit_price = material_prices.get(material)

        if unit_price is not None:
            cost = unit_price * total_qty
            total_input_cost += cost
            material_costs.append({
                "material": material,
                "quantity_per_run": quantity,
                "total_quantity": total_qty,
                "unit_price": unit_price,
                "total_cost": round(cost, 2),
            })
        else:
            missing_prices.append(material)
            material_costs.append({
                "material": material,
                "quantity_per_run": quantity,
                "total_quantity": total_qty,
                "unit_price": None,
                "total_cost": None,
            })

    # Calculate production time
    time_result = calculate_reaction_time(
        base_cycle_seconds=cycle_time,
        reactions_skill=reactions_skill,
        refinery_name=refinery_name,
        runs=runs,
    )

    # Calculate outputs
    total_output = output_qty * runs
    cost_per_unit = total_input_cost / total_output if total_output > 0 else 0

    return {
        "fuel_block": fb_info["name"],
        "faction": fb_info.get("faction"),
        "isotope": fb_info.get("isotope"),
        "runs": runs,
        "output_per_run": output_qty,
        "total_output": total_output,
        "material_costs": material_costs,
        "total_input_cost": round(total_input_cost, 2),
        "cost_per_unit": round(cost_per_unit, 2),
        "production_time": time_result,
        "missing_prices": missing_prices,
        "is_complete": len(missing_prices) == 0,
    }


def calculate_fuel_block_profit(
    fuel_block_name: str,
    material_prices: dict[str, float],
    fuel_block_price: float,
    reactions_skill: int = 0,
    refinery_name: str = "Athanor",
    runs: int = 1,
) -> dict[str, Any]:
    """
    Calculate fuel block production profit.

    Args:
        fuel_block_name: Name of fuel block
        material_prices: Dict mapping material name to unit price
        fuel_block_price: Market price per fuel block
        reactions_skill: Reactions skill level (0-5)
        refinery_name: Refinery type
        runs: Number of reaction runs

    Returns:
        Dict with cost, revenue, profit, profit per hour
    """
    cost_result = calculate_fuel_block_cost(
        fuel_block_name=fuel_block_name,
        material_prices=material_prices,
        reactions_skill=reactions_skill,
        refinery_name=refinery_name,
        runs=runs,
    )

    if "error" in cost_result:
        return cost_result

    total_output = cost_result["total_output"]
    total_cost = cost_result["total_input_cost"]
    revenue = fuel_block_price * total_output
    gross_profit = revenue - total_cost
    margin = (gross_profit / revenue * 100) if revenue > 0 else 0

    # Profit per hour
    total_hours = cost_result["production_time"]["total_time_hours"]
    profit_per_hour = gross_profit / total_hours if total_hours > 0 else 0

    return {
        **cost_result,
        "fuel_block_price": fuel_block_price,
        "revenue": round(revenue, 2),
        "gross_profit": round(gross_profit, 2),
        "margin_percent": round(margin, 1),
        "profit_per_hour": round(profit_per_hour, 2),
    }


def format_fuel_block_summary(result: dict[str, Any]) -> str:
    """
    Format fuel block calculation result as markdown.

    Args:
        result: Result from calculate_fuel_block_cost or calculate_fuel_block_profit

    Returns:
        Formatted markdown string
    """
    from aria_esi.services.industry_costs import format_isk, format_time_duration

    lines = []

    if "error" in result:
        return f"**Error:** {result['error']}"

    # Header
    lines.append(f"## Fuel Block Production: {result['fuel_block']}")
    lines.append("")
    lines.append(f"**Faction:** {result.get('faction', 'Unknown')}")
    lines.append(f"**Isotope:** {result.get('isotope', 'Unknown')}")
    lines.append(f"**Runs:** {result['runs']} (Output: {result['total_output']:,} blocks)")
    lines.append("")

    # Materials table
    lines.append("### Input Materials")
    lines.append("")
    lines.append("| Material | Per Run | Total | Price | Cost |")
    lines.append("|----------|---------|-------|-------|------|")

    for mat in result["material_costs"]:
        price_str = format_isk(mat["unit_price"]) if mat["unit_price"] else "N/A"
        cost_str = format_isk(mat["total_cost"]) if mat["total_cost"] else "N/A"
        lines.append(
            f"| {mat['material']} | {mat['quantity_per_run']:,} | "
            f"{mat['total_quantity']:,} | {price_str} | {cost_str} |"
        )

    lines.append("")
    lines.append(f"**Total Input Cost:** {format_isk(result['total_input_cost'])}")
    lines.append(f"**Cost Per Block:** {format_isk(result['cost_per_unit'])}")
    lines.append("")

    # Production time
    time_info = result["production_time"]
    lines.append("### Production Time")
    lines.append("")
    lines.append(f"| Setting | Value |")
    lines.append(f"|---------|-------|")
    lines.append(f"| Base Cycle | {format_time_duration(time_info['base_cycle_seconds'])} |")
    lines.append(f"| Reactions Skill | -{time_info['skill_reduction_percent']}% |")
    lines.append(f"| Refinery ({time_info['refinery']}) | -{time_info['refinery_reduction_percent']}% |")
    lines.append(f"| Effective Cycle | {format_time_duration(time_info['effective_cycle_seconds'])} |")
    lines.append(f"| **Total Time** | **{time_info['total_time_hours']}h** |")
    lines.append("")

    # Profitability (if available)
    if "gross_profit" in result:
        lines.append("### Profitability")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Cost | {format_isk(result['total_input_cost'])} |")
        lines.append(f"| Revenue | {format_isk(result['revenue'])} |")
        lines.append(f"| **Gross Profit** | **{format_isk(result['gross_profit'])}** |")
        lines.append(f"| **Margin** | **{result['margin_percent']}%** |")
        lines.append(f"| **Profit/Hour** | **{format_isk(result['profit_per_hour'])}/hr** |")
        lines.append("")

    # Warnings
    if result.get("missing_prices"):
        lines.append("### Warnings")
        lines.append("")
        lines.append("Missing prices for:")
        for mat in result["missing_prices"]:
            lines.append(f"- {mat}")
        lines.append("")
        lines.append("*Cost calculation is incomplete.*")
        lines.append("")

    return "\n".join(lines)


def get_material_sources() -> dict[str, str]:
    """
    Get acquisition sources for fuel block materials.

    Returns:
        Dict mapping material name to acquisition method
    """
    data = _load_fuel_block_data()

    sources = {}

    # PI materials
    pi_sources = data.get("pi_material_sources", {})
    sources.update(pi_sources)

    # Ice materials
    ice_sources = data.get("ice_material_sources", {})
    sources.update(ice_sources)

    return sources
