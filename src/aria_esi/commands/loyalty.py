"""
ARIA ESI Loyalty Points Commands

LP balance tracking and LP store browsing.
"""

import argparse
from typing import Optional

from ..core import (
    CredentialsError,
    ESIClient,
    ESIError,
    get_authenticated_client,
    get_utc_timestamp,
)

# =============================================================================
# Well-Known Corporation IDs
# =============================================================================

# Common NPC corporations for LP farming - used for name shortcuts
KNOWN_LP_CORPS = {
    # Empire Navies
    "federation navy": 1000120,
    "fed navy": 1000120,
    "fednavy": 1000120,
    "caldari navy": 1000035,
    "cal navy": 1000035,
    "republic fleet": 1000182,
    "rep fleet": 1000182,
    "amarr navy": 1000003,
    "imperial navy": 1000003,
    # Sisters of EVE
    "sisters of eve": 1000130,
    "soe": 1000130,
    "sisters": 1000130,
    # Other common LP corps
    "thukker mix": 1000171,
    "thukker": 1000171,
    "mordu's legion": 1000139,
    "mordus legion": 1000139,
    "mordus": 1000139,
    "concord": 1000125,
    "drf": 1000148,  # Ducia Foundry
    # Federal Navy subdivisions
    "federal navy academy": 1000168,
    "fna": 1000168,
    # Gallente corps
    "federal intelligence office": 1000103,
    "fio": 1000103,
    "federal administration": 1000102,
    # Caldari corps
    "caldari provisions": 1000009,
    "state war academy": 1000167,
    # Minmatar corps
    "brutor tribe": 1000049,
    "republic university": 1000170,
    # Amarr corps
    "amarr certifications": 1000066,
    "ministry of war": 1000113,
}


def _resolve_corporation(client: ESIClient, query: str) -> tuple[Optional[int], Optional[str]]:
    """
    Resolve corporation query to ID and name.

    Supports:
    - Numeric IDs
    - Known shortcuts (e.g., "fed navy")
    - Partial name search

    Returns:
        Tuple of (corp_id, corp_name) or (None, None) if not found
    """
    # Check if numeric ID
    if query.isdigit():
        corp_id = int(query)
        corp_info = client.get_corporation_info(corp_id)
        if corp_info:
            return corp_id, corp_info.get("name")
        return corp_id, None

    # Check known shortcuts (case-insensitive)
    query_lower = query.lower().strip()
    if query_lower in KNOWN_LP_CORPS:
        corp_id = KNOWN_LP_CORPS[query_lower]
        corp_info = client.get_corporation_info(corp_id)
        if corp_info:
            return corp_id, corp_info.get("name")
        return corp_id, None

    # Try ESI name resolution
    resolved_corp_id, corp_name = client.resolve_corporation(query)
    return resolved_corp_id, corp_name


# =============================================================================
# LP Balance Command
# =============================================================================


def cmd_lp(args: argparse.Namespace) -> dict:
    """
    Fetch LP balances across all corporations.

    Shows loyalty points earned from each corporation the character
    has a positive balance with.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Fetch LP balances
    try:
        lp_data = client.get(f"/characters/{char_id}/loyalty/points/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch LP balances: {e.message}",
            "hint": "Ensure esi-characters.read_loyalty.v1 scope is authorized",
            "query_timestamp": query_ts,
        }

    if not isinstance(lp_data, list):
        lp_data = []

    if not lp_data:
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "total_lp": 0,
            "corporation_count": 0,
            "balances": [],
            "message": "No LP balances found. Run missions to earn loyalty points!",
        }

    # Resolve corporation names
    balances = []
    total_lp = 0

    for entry in lp_data:
        corp_id = entry.get("corporation_id")
        lp_amount = entry.get("loyalty_points", 0)

        if lp_amount <= 0:
            continue

        total_lp += lp_amount

        # Get corporation name
        corp_name = "Unknown Corporation"
        corp_info = public_client.get_corporation_info(corp_id)
        if corp_info:
            corp_name = corp_info.get("name", f"Corporation {corp_id}")

        balances.append(
            {"corporation_id": corp_id, "corporation_name": corp_name, "loyalty_points": lp_amount}
        )

    # Sort by LP amount (highest first)
    balances.sort(key=lambda x: x["loyalty_points"], reverse=True)

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "total_lp": total_lp,
        "corporation_count": len(balances),
        "balances": balances,
    }


# =============================================================================
# LP Store Offers Command
# =============================================================================


def cmd_lp_offers(args: argparse.Namespace) -> dict:
    """
    Browse LP store offers for a corporation.

    This is a PUBLIC endpoint - no authentication required.
    Shows what items are available in the LP store and their costs.
    """
    query_ts = get_utc_timestamp()
    corp_query = getattr(args, "corporation", None)
    search_term = getattr(args, "search", None)
    show_affordable = getattr(args, "affordable", False)
    max_lp = getattr(args, "max_lp", None)

    if not corp_query:
        return {
            "error": "missing_argument",
            "message": "Corporation name or ID required",
            "hint": "Example: aria-esi lp-offers 'Federation Navy'",
            "shortcuts": list(set(KNOWN_LP_CORPS.values()))[:10],
            "query_timestamp": query_ts,
        }

    public_client = ESIClient()

    # Resolve corporation
    corp_id, corp_name = _resolve_corporation(public_client, corp_query)

    if not corp_id:
        return {
            "error": "corporation_not_found",
            "message": f"Could not find corporation: {corp_query}",
            "hint": "Try a corporation ID or known name like 'Federation Navy'",
            "query_timestamp": query_ts,
        }

    if not corp_name:
        corp_info = public_client.get_corporation_info(corp_id)
        corp_name = (
            corp_info.get("name", f"Corporation {corp_id}")
            if corp_info
            else f"Corporation {corp_id}"
        )

    # Fetch LP store offers (public endpoint)
    try:
        offers = public_client.get(f"/loyalty/stores/{corp_id}/offers/")
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch LP store: {e.message}",
            "hint": "This corporation may not have an LP store",
            "query_timestamp": query_ts,
        }

    if not isinstance(offers, list):
        offers = []

    if not offers:
        return {
            "query_timestamp": query_ts,
            "volatility": "stable",
            "corporation_id": corp_id,
            "corporation_name": corp_name,
            "offer_count": 0,
            "offers": [],
            "message": "No LP store offers found for this corporation",
        }

    # Get current LP balance if checking affordability
    current_lp = None
    current_isk = None

    if show_affordable:
        try:
            client, creds = get_authenticated_client()
            char_id = creds.character_id

            # Get LP balance for this corp
            lp_data = client.get(f"/characters/{char_id}/loyalty/points/", auth=True)
            if isinstance(lp_data, list):
                for entry in lp_data:
                    if entry.get("corporation_id") == corp_id:
                        current_lp = entry.get("loyalty_points", 0)
                        break

            # Get ISK balance
            isk_balance = client.get(f"/characters/{char_id}/wallet/", auth=True)
            if isinstance(isk_balance, (int, float)):
                current_isk = isk_balance

        except (CredentialsError, ESIError):
            # Fall back to no affordability filter
            show_affordable = False

    # Collect unique type IDs for name resolution
    type_ids = set()
    for offer in offers:
        type_ids.add(offer.get("type_id"))
        for req in offer.get("required_items", []):
            type_ids.add(req.get("type_id"))

    # Resolve type names (batch, limit to avoid too many requests)
    type_names = {}
    for tid in list(type_ids)[:200]:
        if tid:
            info = public_client.get_dict_safe(f"/universe/types/{tid}/")
            if info and "name" in info:
                type_names[tid] = info["name"]

    # Process offers
    processed_offers = []

    for offer in offers:
        offer_id = offer.get("offer_id")
        type_id = offer.get("type_id")
        quantity = offer.get("quantity", 1)
        lp_cost = offer.get("lp_cost", 0)
        isk_cost = offer.get("isk_cost", 0)
        ak_cost = offer.get("ak_cost", 0)  # Analysis Kredits
        required_items = offer.get("required_items", [])

        item_name = type_names.get(type_id, f"Unknown Item ({type_id})")

        # Apply search filter
        if search_term:
            if search_term.lower() not in item_name.lower():
                continue

        # Apply LP cost filter
        if max_lp is not None and lp_cost > max_lp:
            continue

        # Apply affordability filter
        if show_affordable:
            if current_lp is not None and lp_cost > current_lp:
                continue
            if current_isk is not None and isk_cost > current_isk:
                continue

        # Process required items
        required = []
        for req in required_items:
            req_type_id = req.get("type_id")
            req_qty = req.get("quantity", 1)
            req_name = type_names.get(req_type_id, f"Unknown ({req_type_id})")
            required.append({"type_id": req_type_id, "name": req_name, "quantity": req_qty})

        processed_offer = {
            "offer_id": offer_id,
            "type_id": type_id,
            "name": item_name,
            "quantity": quantity,
            "lp_cost": lp_cost,
            "isk_cost": isk_cost,
        }

        if ak_cost > 0:
            processed_offer["ak_cost"] = ak_cost

        if required:
            processed_offer["required_items"] = required

        # Calculate LP-to-ISK ratio if we have market data hints
        # (Simple metric: ISK cost per LP spent, lower is "better value")
        if lp_cost > 0:
            processed_offer["isk_per_lp"] = round(isk_cost / lp_cost, 2)

        processed_offers.append(processed_offer)

    # Sort by LP cost (lowest first for accessibility)
    processed_offers.sort(key=lambda x: x["lp_cost"])

    # Limit output
    total_matches = len(processed_offers)
    truncated = total_matches > 50
    processed_offers = processed_offers[:50]

    result = {
        "query_timestamp": query_ts,
        "volatility": "stable",
        "corporation_id": corp_id,
        "corporation_name": corp_name,
        "total_offers": len(offers),
        "filtered_count": total_matches,
        "offers": processed_offers,
        "truncated": truncated,
        "filters_applied": {
            "search": search_term if search_term else None,
            "max_lp": max_lp if max_lp else None,
            "affordable_only": show_affordable,
        },
    }

    if show_affordable and current_lp is not None:
        result["current_lp"] = current_lp
        result["current_isk"] = current_isk

    return result


# =============================================================================
# LP Store Analysis Command
# =============================================================================


def cmd_lp_analyze(args: argparse.Namespace) -> dict:
    """
    Analyze LP store for self-sufficient items.

    Identifies items that:
    - Require only LP + ISK (no market items)
    - Are useful for self-sufficient gameplay (modules, implants, etc.)
    """
    query_ts = get_utc_timestamp()
    corp_query = getattr(args, "corporation", None)

    if not corp_query:
        return {
            "error": "missing_argument",
            "message": "Corporation name or ID required",
            "hint": "Example: aria-esi lp-analyze 'Federation Navy'",
            "query_timestamp": query_ts,
        }

    public_client = ESIClient()

    # Resolve corporation
    corp_id, corp_name = _resolve_corporation(public_client, corp_query)

    if not corp_id:
        return {
            "error": "corporation_not_found",
            "message": f"Could not find corporation: {corp_query}",
            "query_timestamp": query_ts,
        }

    if not corp_name:
        corp_info = public_client.get_corporation_info(corp_id)
        corp_name = (
            corp_info.get("name", f"Corporation {corp_id}")
            if corp_info
            else f"Corporation {corp_id}"
        )

    # Fetch LP store offers
    try:
        offers = public_client.get(f"/loyalty/stores/{corp_id}/offers/")
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch LP store: {e.message}",
            "query_timestamp": query_ts,
        }

    if not isinstance(offers, list):
        offers = []

    # Collect type IDs for resolution
    type_ids = set()
    for offer in offers:
        type_ids.add(offer.get("type_id"))

    # Resolve type names
    type_info = {}
    for tid in list(type_ids)[:200]:
        if tid:
            info = public_client.get_dict_safe(f"/universe/types/{tid}/")
            if info:
                type_info[tid] = {
                    "name": info.get("name", f"Unknown ({tid})"),
                    "group_id": info.get("group_id", 0),
                    "market_group_id": info.get("market_group_id"),
                }

    # Categorize offers
    no_items_required = []  # LP + ISK only
    items_required = []  # Need additional items

    for offer in offers:
        type_id = offer.get("type_id")
        required_items = offer.get("required_items", [])
        info = type_info.get(type_id, {"name": f"Unknown ({type_id})"})

        offer_data = {
            "type_id": type_id,
            "name": info["name"],
            "quantity": offer.get("quantity", 1),
            "lp_cost": offer.get("lp_cost", 0),
            "isk_cost": offer.get("isk_cost", 0),
        }

        if not required_items:
            no_items_required.append(offer_data)
        else:
            # Track what items are needed
            req_names = []
            for req in required_items:
                req_info = type_info.get(req.get("type_id"), {})
                req_names.append(f"{req.get('quantity', 1)}x {req_info.get('name', 'Unknown')}")
            offer_data["requires"] = req_names
            items_required.append(offer_data)

    # Sort by LP cost
    no_items_required.sort(key=lambda x: x["lp_cost"])
    items_required.sort(key=lambda x: x["lp_cost"])

    return {
        "query_timestamp": query_ts,
        "volatility": "stable",
        "corporation_id": corp_id,
        "corporation_name": corp_name,
        "analysis": {
            "total_offers": len(offers),
            "lp_isk_only": len(no_items_required),
            "requires_items": len(items_required),
        },
        "self_sufficient_offers": no_items_required[:30],
        "requires_items": items_required[:20],
        "note": "Self-sufficient offers require only LP + ISK, no additional items",
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register loyalty command parsers."""

    # LP balance command
    lp_parser = subparsers.add_parser("lp", help="Fetch LP balances across all corporations")
    lp_parser.set_defaults(func=cmd_lp)

    # LP store offers command
    offers_parser = subparsers.add_parser(
        "lp-offers", help="Browse LP store offers for a corporation"
    )
    offers_parser.add_argument(
        "corporation",
        nargs="?",
        help="Corporation name, ID, or shortcut (e.g., 'Federation Navy', 'fed navy', 1000120)",
    )
    offers_parser.add_argument(
        "--search", "-s", dest="search", metavar="TERM", help="Filter offers by item name"
    )
    offers_parser.add_argument(
        "--max-lp", dest="max_lp", type=int, metavar="LP", help="Maximum LP cost to show"
    )
    offers_parser.add_argument(
        "--affordable", action="store_true", help="Only show offers you can afford (requires auth)"
    )
    offers_parser.set_defaults(func=cmd_lp_offers)

    # LP analyze command
    analyze_parser = subparsers.add_parser(
        "lp-analyze", help="Analyze LP store for self-sufficient items"
    )
    analyze_parser.add_argument("corporation", nargs="?", help="Corporation name or ID")
    analyze_parser.set_defaults(func=cmd_lp_analyze)
