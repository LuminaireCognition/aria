"""
ARIA Industry Chain Resolution Service.

Resolves manufacturing chains recursively to show "build from scratch" costs
for items with manufactured components.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from aria_esi.core.logging import get_logger

logger = get_logger(__name__)

# Cache for terminal materials data
_terminal_data: Optional[dict[str, Any]] = None


def _load_terminal_materials() -> dict[str, Any]:
    """Load terminal materials configuration."""
    global _terminal_data
    if _terminal_data is not None:
        return _terminal_data

    ref_path = Path(__file__).parent.parent.parent / "reference" / "industry" / "terminal_materials.json"

    # Fallback path for installed package
    if not ref_path.exists():
        ref_path = Path("reference/industry/terminal_materials.json")

    if ref_path.exists():
        with open(ref_path) as f:
            _terminal_data = json.load(f)
    else:
        # Minimal default data
        _terminal_data = {
            "always_terminal": {
                "minerals": [
                    "Tritanium", "Pyerite", "Mexallon", "Isogen",
                    "Nocxium", "Zydrine", "Megacyte", "Morphite"
                ],
                "ice_products": [],
                "moon_materials": [],
                "pi_p0": [],
                "pi_p1": [],
                "salvage": [],
            },
            "chain_depth_limits": {"max_depth": 5},
        }

    return _terminal_data


def get_always_terminal_materials() -> set[str]:
    """
    Get the set of materials that can never be manufactured.

    These are raw materials that must be mined, extracted from planets,
    harvested from moons, or salvaged.

    Returns:
        Set of material names that are always terminal
    """
    data = _load_terminal_materials()
    always_terminal = data.get("always_terminal", {})

    terminal_set: set[str] = set()
    for category in always_terminal.values():
        if isinstance(category, list):
            terminal_set.update(category)

    return terminal_set


def get_max_chain_depth() -> int:
    """Get the maximum depth for chain resolution."""
    data = _load_terminal_materials()
    limits = data.get("chain_depth_limits", {})
    return limits.get("max_depth", 5)


@dataclass
class ChainNode:
    """A node in the manufacturing chain tree."""

    type_name: str
    type_id: int
    quantity: int
    is_terminal: bool
    terminal_reason: Optional[str] = None
    market_price: Optional[float] = None
    build_cost: Optional[float] = None
    blueprint_type_id: Optional[int] = None
    children: list["ChainNode"] = field(default_factory=list)
    depth: int = 0

    @property
    def total_market_cost(self) -> float:
        """Total cost if buying this and all children from market."""
        if self.market_price is not None:
            return self.market_price * self.quantity
        return sum(child.total_market_cost for child in self.children)

    @property
    def total_build_cost(self) -> float:
        """Total cost if building everything possible."""
        if self.is_terminal:
            # Terminal items must be bought
            return (self.market_price or 0) * self.quantity

        if not self.children:
            # No blueprint - must buy
            return (self.market_price or 0) * self.quantity

        # Sum children's build costs
        return sum(child.total_build_cost for child in self.children)

    @property
    def savings(self) -> float:
        """ISK saved by building vs buying."""
        return self.total_market_cost - self.total_build_cost

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type_name": self.type_name,
            "type_id": self.type_id,
            "quantity": self.quantity,
            "is_terminal": self.is_terminal,
            "terminal_reason": self.terminal_reason,
            "market_price": self.market_price,
            "build_cost": self.build_cost,
            "total_market_cost": self.total_market_cost,
            "total_build_cost": self.total_build_cost,
            "savings": self.savings,
            "depth": self.depth,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class ChainResolutionResult:
    """Result of chain resolution."""

    root: ChainNode
    total_market_cost: float
    total_build_cost: float
    savings: float
    max_depth_reached: int
    terminal_materials: list[dict[str, Any]]
    buildable_components: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "root": self.root.to_dict(),
            "total_market_cost": self.total_market_cost,
            "total_build_cost": self.total_build_cost,
            "savings": self.savings,
            "savings_percent": round(
                (self.savings / self.total_market_cost * 100)
                if self.total_market_cost > 0
                else 0,
                1,
            ),
            "max_depth_reached": self.max_depth_reached,
            "terminal_materials": self.terminal_materials,
            "buildable_components": self.buildable_components,
            "warnings": self.warnings,
        }


class ChainResolver:
    """
    Resolves manufacturing chains to find build-from-scratch costs.

    Uses SDE and market MCP tools to look up blueprints and prices.
    """

    def __init__(
        self,
        sde_lookup: callable,
        market_lookup: callable,
        me_level: int = 10,
        runs: int = 1,
    ):
        """
        Initialize the chain resolver.

        Args:
            sde_lookup: Function to look up blueprint info from SDE
                        Signature: (item_name) -> blueprint_info dict
            market_lookup: Function to look up market prices
                          Signature: (item_names) -> prices dict
            me_level: Material Efficiency level to apply (0-10)
            runs: Number of manufacturing runs
        """
        self.sde_lookup = sde_lookup
        self.market_lookup = market_lookup
        self.me_level = me_level
        self.runs = runs
        self._terminal_materials = get_always_terminal_materials()
        self._max_depth = get_max_chain_depth()
        self._seen: set[int] = set()  # Circular reference protection
        self._max_depth_reached = 0
        self._warnings: list[str] = []

    def resolve(self, product_name: str) -> ChainResolutionResult:
        """
        Resolve the full manufacturing chain for a product.

        Args:
            product_name: Name of the item to resolve

        Returns:
            ChainResolutionResult with full chain tree and cost analysis
        """
        self._seen.clear()
        self._max_depth_reached = 0
        self._warnings.clear()

        # Get blueprint info for the top-level product
        try:
            blueprint_info = self.sde_lookup(product_name)
        except Exception as e:
            logger.warning("Failed to look up blueprint for %s: %s", product_name, e)
            # Return a terminal node
            return self._make_terminal_result(product_name, f"No blueprint found: {e}")

        if not blueprint_info or "error" in blueprint_info:
            return self._make_terminal_result(
                product_name,
                blueprint_info.get("error", "No blueprint found")
            )

        # Build the chain tree
        root = self._resolve_node(
            type_name=blueprint_info.get("product", product_name),
            type_id=blueprint_info.get("product_type_id", 0),
            quantity=self.runs,
            blueprint_info=blueprint_info,
            depth=0,
        )

        # Collect terminal and buildable materials for summary
        terminal_materials: list[dict[str, Any]] = []
        buildable_components: list[dict[str, Any]] = []
        self._collect_materials(root, terminal_materials, buildable_components)

        return ChainResolutionResult(
            root=root,
            total_market_cost=root.total_market_cost,
            total_build_cost=root.total_build_cost,
            savings=root.savings,
            max_depth_reached=self._max_depth_reached,
            terminal_materials=terminal_materials,
            buildable_components=buildable_components,
            warnings=self._warnings,
        )

    def _resolve_node(
        self,
        type_name: str,
        type_id: int,
        quantity: int,
        blueprint_info: Optional[dict[str, Any]],
        depth: int,
    ) -> ChainNode:
        """Recursively resolve a single node in the chain."""
        self._max_depth_reached = max(self._max_depth_reached, depth)

        # Check for circular reference
        if type_id in self._seen:
            return ChainNode(
                type_name=type_name,
                type_id=type_id,
                quantity=quantity,
                is_terminal=True,
                terminal_reason="circular_reference",
                depth=depth,
            )
        self._seen.add(type_id)

        # Check depth limit
        if depth > self._max_depth:
            self._warnings.append(
                f"Max depth ({self._max_depth}) reached at {type_name}"
            )
            return ChainNode(
                type_name=type_name,
                type_id=type_id,
                quantity=quantity,
                is_terminal=True,
                terminal_reason="max_depth",
                depth=depth,
            )

        # Check if terminal material
        if type_name in self._terminal_materials:
            return ChainNode(
                type_name=type_name,
                type_id=type_id,
                quantity=quantity,
                is_terminal=True,
                terminal_reason="raw_material",
                depth=depth,
            )

        # If no blueprint info provided, try to look it up
        if blueprint_info is None:
            try:
                blueprint_info = self.sde_lookup(type_name)
            except Exception as e:
                logger.debug("No blueprint for %s: %s", type_name, e)
                blueprint_info = None

        # No blueprint = terminal
        if not blueprint_info or "error" in blueprint_info:
            return ChainNode(
                type_name=type_name,
                type_id=type_id,
                quantity=quantity,
                is_terminal=True,
                terminal_reason="no_blueprint",
                depth=depth,
            )

        # Get market price for this item
        market_price = self._get_price(type_name)

        # Create node with children from materials
        node = ChainNode(
            type_name=type_name,
            type_id=type_id,
            quantity=quantity,
            is_terminal=False,
            market_price=market_price,
            blueprint_type_id=blueprint_info.get("blueprint_type_id"),
            depth=depth,
        )

        # Resolve each material
        materials = blueprint_info.get("materials", [])
        for mat in materials:
            mat_name = mat.get("type_name", "Unknown")
            mat_id = mat.get("type_id", 0)
            base_qty = mat.get("quantity", 1)

            # Apply ME reduction
            adj_qty = self._apply_me(base_qty)
            # Scale by parent quantity
            total_qty = adj_qty * quantity

            child = self._resolve_node(
                type_name=mat_name,
                type_id=mat_id,
                quantity=total_qty,
                blueprint_info=None,  # Will be looked up
                depth=depth + 1,
            )
            node.children.append(child)

        # Remove from seen set to allow visiting from different paths
        self._seen.discard(type_id)

        return node

    def _apply_me(self, base_qty: int) -> int:
        """Apply Material Efficiency reduction."""
        import math
        reduction = 1 - (self.me_level * 0.01)
        return max(1, math.ceil(base_qty * reduction))

    def _get_price(self, type_name: str) -> Optional[float]:
        """Get market price for an item."""
        try:
            prices = self.market_lookup([type_name])
            if prices and "items" in prices:
                for item in prices["items"]:
                    if item.get("type_name") == type_name:
                        return item.get("sell_min") or item.get("sell_percentile")
        except Exception as e:
            logger.debug("Failed to get price for %s: %s", type_name, e)
        return None

    def _collect_materials(
        self,
        node: ChainNode,
        terminal: list[dict[str, Any]],
        buildable: list[dict[str, Any]],
    ) -> None:
        """Collect terminal and buildable materials from tree."""
        if node.is_terminal:
            # Check if already in list
            for item in terminal:
                if item["type_name"] == node.type_name:
                    item["quantity"] += node.quantity
                    return
            terminal.append({
                "type_name": node.type_name,
                "type_id": node.type_id,
                "quantity": node.quantity,
                "reason": node.terminal_reason,
                "market_price": node.market_price,
            })
        elif node.children:
            # This is buildable
            for item in buildable:
                if item["type_name"] == node.type_name:
                    item["quantity"] += node.quantity
                    return
            buildable.append({
                "type_name": node.type_name,
                "type_id": node.type_id,
                "quantity": node.quantity,
                "market_price": node.market_price,
                "has_blueprint": True,
            })

        # Recurse into children
        for child in node.children:
            self._collect_materials(child, terminal, buildable)

    def _make_terminal_result(
        self, product_name: str, reason: str
    ) -> ChainResolutionResult:
        """Create a result for an item that can't be resolved."""
        root = ChainNode(
            type_name=product_name,
            type_id=0,
            quantity=self.runs,
            is_terminal=True,
            terminal_reason=reason,
            depth=0,
        )
        return ChainResolutionResult(
            root=root,
            total_market_cost=0,
            total_build_cost=0,
            savings=0,
            max_depth_reached=0,
            terminal_materials=[],
            buildable_components=[],
            warnings=[reason],
        )


def format_chain_summary(result: ChainResolutionResult) -> str:
    """
    Format chain resolution result as a markdown summary.

    Args:
        result: ChainResolutionResult from resolver

    Returns:
        Formatted markdown string
    """
    from aria_esi.services.industry_costs import format_isk

    lines = []

    # Header
    root = result.root
    lines.append(f"## Build vs Buy Analysis: {root.type_name}")
    lines.append("")

    # Summary table
    lines.append("### Cost Comparison")
    lines.append("")
    lines.append("| Strategy | Total Cost |")
    lines.append("|----------|------------|")
    lines.append(f"| Buy from Market | {format_isk(result.total_market_cost)} |")
    lines.append(f"| Build Everything | {format_isk(result.total_build_cost)} |")

    if result.savings > 0:
        savings_pct = result.savings / result.total_market_cost * 100
        lines.append(f"| **Savings** | **{format_isk(result.savings)}** ({savings_pct:.1f}%) |")
    elif result.savings < 0:
        loss = abs(result.savings)
        loss_pct = loss / result.total_build_cost * 100
        lines.append(f"| **Loss if Building** | **{format_isk(loss)}** ({loss_pct:.1f}%) |")
    else:
        lines.append("| **Savings** | 0 ISK |")

    lines.append("")

    # Buildable components
    if result.buildable_components:
        lines.append("### Buildable Components")
        lines.append("")
        lines.append("| Component | Qty | Market Price | Build? |")
        lines.append("|-----------|-----|--------------|--------|")
        for comp in result.buildable_components:
            price = format_isk(comp["market_price"]) if comp["market_price"] else "N/A"
            lines.append(f"| {comp['type_name']} | {comp['quantity']:,} | {price} | Check BOM |")
        lines.append("")

    # Terminal materials (raw inputs)
    if result.terminal_materials:
        lines.append("### Raw Materials Required")
        lines.append("")
        lines.append("| Material | Qty | Source |")
        lines.append("|----------|-----|--------|")
        for mat in result.terminal_materials:
            reason = mat.get("reason", "unknown")
            source = {
                "raw_material": "Mining/PI/Moon",
                "no_blueprint": "Market only",
                "max_depth": "See subcomponents",
            }.get(reason, reason)
            lines.append(f"| {mat['type_name']} | {mat['quantity']:,} | {source} |")
        lines.append("")

    # Warnings
    if result.warnings:
        lines.append("### Notes")
        for warning in result.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines)
