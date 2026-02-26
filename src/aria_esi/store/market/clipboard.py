"""
EVE Online Clipboard Parser.

Parses various clipboard formats from EVE Online into item/quantity pairs.
Supports:
- Tab-separated: "Item Name\tQuantity"
- Inventory window: "Item Name    Quantity: 1,000"
- Multi-buy format: "Item Name x100"
- Contract format: "Item Name 100 unit(s)"
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParsedItem:
    """Parsed item from clipboard."""

    name: str
    quantity: int


def parse_clipboard(text: str) -> list[ParsedItem]:
    """
    Parse EVE Online clipboard text into item/quantity pairs.

    Automatically detects format and parses accordingly.

    Args:
        text: Raw clipboard text

    Returns:
        List of ParsedItem with name and quantity
    """
    if not text or not text.strip():
        return []

    lines = text.strip().split("\n")
    items: list[ParsedItem] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        parsed = _parse_line(line)
        if parsed:
            items.append(parsed)

    return items


def _parse_line(line: str) -> ParsedItem | None:
    """
    Parse a single line using multiple format patterns.

    Tries patterns in order of specificity.
    """
    # Pattern 1: Tab-separated (most common from inventory copy)
    # "Item Name\t1,000"
    if "\t" in line:
        parts = line.split("\t")
        if len(parts) >= 2:
            name = parts[0].strip()
            qty_str = parts[1].strip()
            qty = _parse_quantity(qty_str)
            if name and qty > 0:
                return ParsedItem(name=name, quantity=qty)

    # Pattern 2: Inventory window format
    # "Item Name    Quantity: 1,000"
    match = re.match(r"^(.+?)\s+Quantity:\s*([\d,]+)", line, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        qty = _parse_quantity(match.group(2))
        if name and qty > 0:
            return ParsedItem(name=name, quantity=qty)

    # Pattern 3: Multi-buy format
    # "Item Name x100" or "Item Name x 100"
    match = re.match(r"^(.+?)\s*[xX]\s*([\d,]+)$", line)
    if match:
        name = match.group(1).strip()
        qty = _parse_quantity(match.group(2))
        if name and qty > 0:
            return ParsedItem(name=name, quantity=qty)

    # Pattern 4: Contract format
    # "Item Name 100 unit(s)"
    match = re.match(r"^(.+?)\s+([\d,]+)\s*unit", line, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        qty = _parse_quantity(match.group(2))
        if name and qty > 0:
            return ParsedItem(name=name, quantity=qty)

    # Pattern 5: Simple "Item Name quantity" (space-separated, quantity at end)
    # Only if quantity is a pure number
    match = re.match(r"^(.+?)\s+([\d,]+)$", line)
    if match:
        name = match.group(1).strip()
        qty_str = match.group(2)
        # Only accept if it looks like a quantity (not part of name)
        if qty_str.isdigit() or re.match(r"^[\d,]+$", qty_str):
            qty = _parse_quantity(qty_str)
            if name and qty > 0 and not name[-1].isdigit():
                return ParsedItem(name=name, quantity=qty)

    # Pattern 6: Just item name (quantity = 1)
    # Only if line doesn't contain obvious quantity indicators
    if not re.search(r"\d", line) or (len(line) > 3 and not line[-1].isdigit()):
        name = line.strip()
        if name and len(name) > 2:
            return ParsedItem(name=name, quantity=1)

    return None


def _parse_quantity(qty_str: str) -> int:
    """Parse quantity string, handling commas and formatting."""
    if not qty_str:
        return 0

    # Remove commas and whitespace
    cleaned = qty_str.replace(",", "").replace(" ", "").strip()

    # Handle 'k' suffix (1k = 1000)
    if cleaned.lower().endswith("k"):
        try:
            return int(float(cleaned[:-1]) * 1000)
        except ValueError:
            return 0

    # Handle 'm' suffix (1m = 1000000)
    if cleaned.lower().endswith("m"):
        try:
            return int(float(cleaned[:-1]) * 1_000_000)
        except ValueError:
            return 0

    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def items_to_dict(items: list[ParsedItem]) -> list[dict]:
    """
    Convert parsed items to dict format for API consumption.

    Args:
        items: List of ParsedItem

    Returns:
        List of {"name": str, "quantity": int} dicts
    """
    return [{"name": item.name, "quantity": item.quantity} for item in items]


def parse_clipboard_to_dict(text: str) -> list[dict]:
    """
    Parse clipboard text directly to dict format.

    Convenience function combining parse_clipboard and items_to_dict.

    Args:
        text: Raw clipboard text

    Returns:
        List of {"name": str, "quantity": int} dicts
    """
    items = parse_clipboard(text)
    return items_to_dict(items)
