"""
Archetype Fit Pricing Module.

Estimates ISK cost of fits using market data from the MCP market dispatcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from aria_esi.core.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Pricing Result
# =============================================================================


@dataclass
class ItemPrice:
    """Price information for a single item."""

    type_name: str
    quantity: int
    unit_price: float
    total_price: float
    price_source: str = "jita"  # Trade hub used


@dataclass
class FitPriceEstimate:
    """Complete price estimate for a fit."""

    total_isk: int
    breakdown: list[ItemPrice] = field(default_factory=list)
    ship_price: float = 0.0
    modules_price: float = 0.0
    rigs_price: float = 0.0
    drones_price: float = 0.0
    charges_price: float = 0.0
    price_source: str = "jita"
    updated: str = ""  # ISO timestamp
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_isk": self.total_isk,
            "ship_price": round(self.ship_price, 2),
            "modules_price": round(self.modules_price, 2),
            "rigs_price": round(self.rigs_price, 2),
            "drones_price": round(self.drones_price, 2),
            "charges_price": round(self.charges_price, 2),
            "price_source": self.price_source,
            "updated": self.updated,
            "breakdown_count": len(self.breakdown),
            "warnings": self.warnings,
        }


# =============================================================================
# EFT Parsing for Pricing
# =============================================================================


def _parse_eft_for_pricing(eft: str) -> dict[str, Any]:
    """
    Parse EFT string to extract items and quantities for pricing.

    Returns dict with:
    - ship: ship type name
    - modules: list of (name, quantity) tuples
    - rigs: list of (name, quantity) tuples
    - drones: list of (name, quantity) tuples
    - charges: list of (name, quantity) tuples (from module loadouts)
    """
    result: dict[str, Any] = {
        "ship": None,
        "modules": [],
        "rigs": [],
        "drones": [],
        "charges": [],
    }

    lines = eft.strip().split("\n")
    if not lines:
        return result

    # Parse header
    header = lines[0].strip()
    if header.startswith("[") and "]" in header:
        content = header[1:].split("]")[0]
        ship_name = content.split(",")[0].strip()
        result["ship"] = ship_name

    # Track modules for quantity counting
    module_counts: dict[str, int] = {}
    rig_counts: dict[str, int] = {}
    drone_counts: dict[str, int] = {}
    charge_counts: dict[str, int] = {}

    for line in lines[1:]:
        line = line.strip()

        if not line:
            # Empty line might indicate section change
            continue

        # Skip empty slot markers
        if line.lower().startswith("[empty"):
            continue

        # Check for drone/cargo quantity format: "Item x5"
        if " x" in line:
            parts = line.rsplit(" x", 1)
            if len(parts) == 2:
                name = parts[0].strip()
                try:
                    qty = int(parts[1].strip())
                    drone_counts[name] = drone_counts.get(name, 0) + qty
                    continue
                except ValueError:
                    pass

        # Check for charge in module: "Module, Charge"
        if "," in line and not line.startswith("["):
            parts = line.split(",", 1)
            module_name = parts[0].strip()
            charge_name = parts[1].strip()

            # Remove offline marker
            if "/" in module_name:
                module_name = module_name.split("/")[0].strip()
            if "/" in charge_name:
                charge_name = charge_name.split("/")[0].strip()

            module_counts[module_name] = module_counts.get(module_name, 0) + 1
            if charge_name:
                charge_counts[charge_name] = charge_counts.get(charge_name, 0) + 1
            continue

        # Regular module/rig line
        name = line
        if "/" in name:  # Remove offline marker
            name = name.split("/")[0].strip()

        # Determine if rig based on name patterns
        is_rig = any(
            pattern in name.lower()
            for pattern in ["pump", "purifier", "trimark", "rig", "field extender"]
        )

        if is_rig:
            rig_counts[name] = rig_counts.get(name, 0) + 1
        else:
            module_counts[name] = module_counts.get(name, 0) + 1

    # Convert to tuples
    result["modules"] = list(module_counts.items())
    result["rigs"] = list(rig_counts.items())
    result["drones"] = list(drone_counts.items())
    result["charges"] = list(charge_counts.items())

    return result


# =============================================================================
# Price Fetching
# =============================================================================


def _fetch_prices_from_market(
    items: list[str],
    region: str = "jita",
) -> dict[str, float]:
    """
    Fetch prices from market database cache.

    Args:
        items: List of item names
        region: Trade hub to query

    Returns:
        Dict mapping item name to sell price
    """
    try:
        from aria_esi.mcp.market.database import get_market_database
        from aria_esi.models.market import TRADE_HUBS, resolve_trade_hub

        db = get_market_database()
        prices: dict[str, float] = {}

        # Resolve region to get region_id
        hub = resolve_trade_hub(region)
        if not hub:
            hub = TRADE_HUBS["jita"]
        region_id = hub["region_id"]

        for item_name in items:
            try:
                # Resolve item name to type ID
                type_info = db.resolve_type_name(item_name)
                if type_info:
                    # Try to get cached aggregate price
                    aggregate = db.get_aggregate(type_info.type_id, region_id)
                    if aggregate:
                        # Use sell_min (what you'd pay to buy)
                        if aggregate.sell_min and aggregate.sell_min > 0:
                            prices[item_name] = aggregate.sell_min
                            continue

                        # Fallback to weighted average
                        if aggregate.sell_weighted_avg and aggregate.sell_weighted_avg > 0:
                            prices[item_name] = aggregate.sell_weighted_avg
                            continue

                    # No cached data - item might be rare/unavailable
                    logger.debug("No cached price for: %s", item_name)

            except Exception as e:
                logger.debug("Error fetching price for %s: %s", item_name, e)

        return prices

    except Exception as e:
        logger.warning("Could not access market database: %s", e)
        return {}


# =============================================================================
# Main Pricing Function
# =============================================================================


def estimate_fit_price(
    eft: str,
    region: str = "jita",
) -> FitPriceEstimate:
    """
    Estimate the ISK cost of a ship fitting.

    Args:
        eft: Ship fitting in EFT format
        region: Trade hub for price lookup (default: jita)

    Returns:
        FitPriceEstimate with total and breakdown
    """
    result = FitPriceEstimate(
        total_isk=0,
        price_source=region,
        updated=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )

    # Parse EFT
    parsed = _parse_eft_for_pricing(eft)

    if not parsed["ship"]:
        result.warnings.append("Could not parse ship from EFT")
        return result

    # Collect all items to price
    all_items: list[str] = []

    if parsed["ship"]:
        all_items.append(parsed["ship"])

    for name, _qty in parsed["modules"]:
        if name not in all_items:
            all_items.append(name)

    for name, _qty in parsed["rigs"]:
        if name not in all_items:
            all_items.append(name)

    for name, _qty in parsed["drones"]:
        if name not in all_items:
            all_items.append(name)

    for name, _qty in parsed["charges"]:
        if name not in all_items:
            all_items.append(name)

    # Fetch prices
    prices = _fetch_prices_from_market(all_items, region)

    # Calculate totals
    total = 0.0

    # Ship price
    if parsed["ship"]:
        ship_price = prices.get(parsed["ship"], 0)
        result.ship_price = ship_price
        total += ship_price
        if ship_price == 0:
            result.warnings.append(f"No price found for ship: {parsed['ship']}")

    # Module prices
    for name, qty in parsed["modules"]:
        unit_price = prices.get(name, 0)
        item_total = unit_price * qty
        result.modules_price += item_total
        total += item_total

        result.breakdown.append(
            ItemPrice(
                type_name=name,
                quantity=qty,
                unit_price=unit_price,
                total_price=item_total,
                price_source=region,
            )
        )

        if unit_price == 0:
            result.warnings.append(f"No price found for module: {name}")

    # Rig prices
    for name, qty in parsed["rigs"]:
        unit_price = prices.get(name, 0)
        item_total = unit_price * qty
        result.rigs_price += item_total
        total += item_total

        result.breakdown.append(
            ItemPrice(
                type_name=name,
                quantity=qty,
                unit_price=unit_price,
                total_price=item_total,
                price_source=region,
            )
        )

        if unit_price == 0:
            result.warnings.append(f"No price found for rig: {name}")

    # Drone prices
    for name, qty in parsed["drones"]:
        unit_price = prices.get(name, 0)
        item_total = unit_price * qty
        result.drones_price += item_total
        total += item_total

        result.breakdown.append(
            ItemPrice(
                type_name=name,
                quantity=qty,
                unit_price=unit_price,
                total_price=item_total,
                price_source=region,
            )
        )

        if unit_price == 0:
            result.warnings.append(f"No price found for drone: {name}")

    # Charge prices (not included in total - consumable)
    for name, qty in parsed["charges"]:
        unit_price = prices.get(name, 0)
        item_total = unit_price * qty
        result.charges_price += item_total
        # Note: charges not added to total

        result.breakdown.append(
            ItemPrice(
                type_name=name,
                quantity=qty,
                unit_price=unit_price,
                total_price=item_total,
                price_source=region,
            )
        )

    result.total_isk = int(total)

    return result


# =============================================================================
# Archetype Price Update
# =============================================================================


def update_archetype_price(
    archetype_path: str,
    region: str = "jita",
) -> dict:
    """
    Update the estimated_isk and isk_updated fields in an archetype file.

    Args:
        archetype_path: Path to archetype (e.g., "vexor/pve/missions/l2/medium")
        region: Trade hub for price lookup

    Returns:
        Dict with update status
    """
    from .loader import ArchetypeLoader

    loader = ArchetypeLoader()
    archetype = loader.get_archetype(archetype_path)

    if not archetype:
        return {
            "error": "not_found",
            "message": f"Archetype not found: {archetype_path}",
        }

    # Estimate price
    estimate = estimate_fit_price(archetype.eft, region)

    if estimate.total_isk == 0:
        return {
            "error": "price_unavailable",
            "message": "Could not determine price",
            "warnings": estimate.warnings,
        }

    return {
        "archetype_path": archetype_path,
        "estimated_isk": estimate.total_isk,
        "isk_updated": estimate.updated,
        "breakdown": estimate.to_dict(),
        "status": "calculated",
    }
