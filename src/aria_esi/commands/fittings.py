"""
ARIA ESI Saved Fittings Commands

View saved ship fittings from ESI.
All commands require authentication.
"""

import argparse
from collections import defaultdict

from ..core import (
    CredentialsError,
    ESIClient,
    ESIError,
    get_authenticated_client,
    get_utc_timestamp,
)

# Slot flag to category mapping
SLOT_CATEGORIES = {
    "HiSlot": "high",
    "MedSlot": "medium",
    "LoSlot": "low",
    "RigSlot": "rig",
    "SubSystemSlot": "subsystem",
    "DroneBay": "drone",
    "FighterBay": "fighter",
    "Cargo": "cargo",
    "ServiceSlot": "service",
}


def _categorize_flag(flag: str) -> str:
    """Categorize a slot flag into a slot category."""
    for prefix, category in SLOT_CATEGORIES.items():
        if flag.startswith(prefix):
            return category
    return "other"


def _generate_eft(ship_name: str, fitting_name: str, slots: dict, type_names: dict) -> str:
    """Generate EFT format string from fitting data."""
    lines = [f"[{ship_name}, {fitting_name}]", ""]

    # High slots
    for item in slots.get("high", []):
        name = type_names.get(item["type_id"], f"Unknown-{item['type_id']}")
        for _ in range(item.get("quantity", 1)):
            lines.append(name)
    lines.append("")

    # Medium slots
    for item in slots.get("medium", []):
        name = type_names.get(item["type_id"], f"Unknown-{item['type_id']}")
        for _ in range(item.get("quantity", 1)):
            lines.append(name)
    lines.append("")

    # Low slots
    for item in slots.get("low", []):
        name = type_names.get(item["type_id"], f"Unknown-{item['type_id']}")
        for _ in range(item.get("quantity", 1)):
            lines.append(name)
    lines.append("")

    # Rig slots
    for item in slots.get("rig", []):
        name = type_names.get(item["type_id"], f"Unknown-{item['type_id']}")
        for _ in range(item.get("quantity", 1)):
            lines.append(name)
    lines.append("")

    # Subsystems (T3)
    for item in slots.get("subsystem", []):
        name = type_names.get(item["type_id"], f"Unknown-{item['type_id']}")
        for _ in range(item.get("quantity", 1)):
            lines.append(name)
    if slots.get("subsystem"):
        lines.append("")

    # Drones
    for item in slots.get("drone", []):
        name = type_names.get(item["type_id"], f"Unknown-{item['type_id']}")
        qty = item.get("quantity", 1)
        if qty > 1:
            lines.append(f"{name} x{qty}")
        else:
            lines.append(name)

    # Cargo
    for item in slots.get("cargo", []):
        name = type_names.get(item["type_id"], f"Unknown-{item['type_id']}")
        qty = item.get("quantity", 1)
        if qty > 1:
            lines.append(f"{name} x{qty}")
        else:
            lines.append(name)

    return "\n".join(lines).strip()


# =============================================================================
# List Fittings Command
# =============================================================================


def cmd_fittings(args: argparse.Namespace) -> dict:
    """
    List saved fittings.

    Shows all saved ship fittings with optional hull filter.
    """
    query_ts = get_utc_timestamp()
    ship_filter = getattr(args, "ship", None)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id

    # Check scope
    if not creds.has_scope("esi-fittings.read_fittings.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-fittings.read_fittings.v1",
            "action": "Re-run OAuth setup to authorize saved fittings access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    public_client = ESIClient()

    # Fetch fittings
    try:
        fittings_data = client.get_list(f"/characters/{char_id}/fittings/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch saved fittings: {e.message}",
            "hint": "Ensure esi-fittings.read_fittings.v1 scope is authorized",
            "query_timestamp": query_ts,
        }

    # Empty check
    if not fittings_data:
        return {
            "query_timestamp": query_ts,
            "volatility": "stable",
            "character_id": char_id,
            "summary": {"total_fittings": 0, "unique_hulls": 0},
            "fittings": [],
            "message": "No saved fittings found",
        }

    # Collect ship type IDs
    ship_type_ids = set()
    for fit in fittings_data:
        if isinstance(fit, dict):
            ship_type_ids.add(fit.get("ship_type_id", 0))

    # Resolve ship names
    ship_names = {}
    for tid in ship_type_ids:
        if tid:
            info = public_client.get_dict_safe(f"/universe/types/{tid}/")
            if info and "name" in info:
                ship_names[tid] = info["name"]
            else:
                ship_names[tid] = f"Unknown-{tid}"

    # Process fittings
    processed_fittings = []
    unique_hulls = set()

    for fit in fittings_data:
        if not isinstance(fit, dict):
            continue
        ship_type_id = fit.get("ship_type_id", 0)
        ship_name = ship_names.get(ship_type_id, f"Unknown-{ship_type_id}")

        # Apply ship filter
        if ship_filter:
            if ship_filter.lower() not in ship_name.lower():
                continue

        items = fit.get("items", [])
        module_count = sum(item.get("quantity", 1) for item in items)

        processed_fit = {
            "fitting_id": fit.get("fitting_id"),
            "name": fit.get("name", "Unnamed"),
            "description": fit.get("description", ""),
            "ship_type_id": ship_type_id,
            "ship_type_name": ship_name,
            "module_count": module_count,
        }

        processed_fittings.append(processed_fit)
        unique_hulls.add(ship_type_id)

    # Sort alphabetically by name
    processed_fittings.sort(key=lambda f: f["name"].lower())

    return {
        "query_timestamp": query_ts,
        "volatility": "stable",
        "character_id": char_id,
        "summary": {"total_fittings": len(processed_fittings), "unique_hulls": len(unique_hulls)},
        "fittings": processed_fittings,
        "filters": {"ship": ship_filter},
    }


# =============================================================================
# Fitting Detail Command
# =============================================================================


def cmd_fittings_detail(args: argparse.Namespace) -> dict:
    """
    Show fitting details with slot breakdown and optional EFT export.
    """
    query_ts = get_utc_timestamp()
    fitting_id = getattr(args, "fitting_id", None)
    eft_only = getattr(args, "eft", False)

    if not fitting_id:
        return {
            "error": "missing_argument",
            "message": "Fitting ID is required",
            "usage": "python3 -m aria_esi fittings-detail <fitting_id>",
            "query_timestamp": query_ts,
        }

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id

    # Check scope
    if not creds.has_scope("esi-fittings.read_fittings.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-fittings.read_fittings.v1",
            "action": "Re-run OAuth setup to authorize saved fittings access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    public_client = ESIClient()

    # Fetch all fittings (ESI doesn't have single-fitting endpoint)
    try:
        fittings_data = client.get_list(f"/characters/{char_id}/fittings/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch saved fittings: {e.message}",
            "query_timestamp": query_ts,
        }

    # Find the requested fitting
    target_fit = None
    for fit in fittings_data:
        if isinstance(fit, dict) and fit.get("fitting_id") == fitting_id:
            target_fit = fit
            break

    if not target_fit:
        return {
            "error": "not_found",
            "message": f"Fitting ID {fitting_id} not found",
            "hint": "Use `fittings` to list available fitting IDs",
            "query_timestamp": query_ts,
        }

    # Collect type IDs for resolution
    type_ids = set()
    type_ids.add(target_fit.get("ship_type_id", 0))
    for item in target_fit.get("items", []):
        if isinstance(item, dict):
            type_ids.add(item.get("type_id", 0))

    # Resolve type names
    type_names = {}
    for tid in type_ids:
        if tid:
            info = public_client.get_dict_safe(f"/universe/types/{tid}/")
            if info and "name" in info:
                type_names[tid] = info["name"]
            else:
                type_names[tid] = f"Unknown-{tid}"

    # Organize items by slot category
    slots = defaultdict(list)
    for item in target_fit.get("items", []):
        flag = item.get("flag", "")
        category = _categorize_flag(flag)
        slots[category].append(
            {
                "type_id": item.get("type_id"),
                "type_name": type_names.get(item.get("type_id"), f"Unknown-{item.get('type_id')}"),
                "quantity": item.get("quantity", 1),
                "flag": flag,
            }
        )

    ship_type_id = target_fit.get("ship_type_id", 0)
    ship_name = type_names.get(ship_type_id, f"Unknown-{ship_type_id}")
    fitting_name = target_fit.get("name", "Unnamed")

    # Generate EFT format
    eft_format = _generate_eft(ship_name, fitting_name, dict(slots), type_names)

    # If EFT only, return just the EFT string
    if eft_only:
        return {
            "query_timestamp": query_ts,
            "volatility": "stable",
            "fitting_id": fitting_id,
            "name": fitting_name,
            "eft_format": eft_format,
        }

    return {
        "query_timestamp": query_ts,
        "volatility": "stable",
        "character_id": char_id,
        "fitting": {
            "fitting_id": fitting_id,
            "name": fitting_name,
            "description": target_fit.get("description", ""),
            "ship_type_id": ship_type_id,
            "ship_type_name": ship_name,
            "slots": {
                "high": slots.get("high", []),
                "medium": slots.get("medium", []),
                "low": slots.get("low", []),
                "rig": slots.get("rig", []),
                "subsystem": slots.get("subsystem", []),
                "drone": slots.get("drone", []),
                "fighter": slots.get("fighter", []),
                "cargo": slots.get("cargo", []),
                "service": slots.get("service", []),
            },
            "eft_format": eft_format,
        },
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register saved fittings command parsers."""

    # List fittings command
    list_parser = subparsers.add_parser("fittings", help="List saved ship fittings")
    list_parser.add_argument("--ship", "-s", type=str, help="Filter by ship hull name")
    list_parser.set_defaults(func=cmd_fittings)

    # Fitting detail command
    detail_parser = subparsers.add_parser(
        "fittings-detail", help="Show fitting details with EFT export"
    )
    detail_parser.add_argument("fitting_id", type=int, help="Fitting ID to show")
    detail_parser.add_argument("--eft", action="store_true", help="Output EFT format only")
    detail_parser.set_defaults(func=cmd_fittings_detail)
