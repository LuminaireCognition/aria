"""
ARIA ESI Contracts Commands

Personal contract management: item exchange, courier, and auction contracts.
All commands require authentication.
"""

import argparse
from datetime import datetime, timezone
from typing import Optional

from ..core import (
    CredentialsError,
    ESIClient,
    ESIError,
    format_isk,
    get_authenticated_client,
    get_utc_timestamp,
    parse_datetime,
)

# =============================================================================
# Contract Type and Status Mappings
# =============================================================================

CONTRACT_TYPES = {
    "unknown": "Unknown",
    "item_exchange": "Item Exchange",
    "auction": "Auction",
    "courier": "Courier",
    "loan": "Loan",
}

CONTRACT_STATUSES = {
    "outstanding": "Outstanding",
    "in_progress": "In Progress",
    "finished_issuer": "Finished (Issuer)",
    "finished_contractor": "Finished (Contractor)",
    "finished": "Finished",
    "cancelled": "Cancelled",
    "rejected": "Rejected",
    "failed": "Failed",
    "deleted": "Deleted",
    "reversed": "Reversed",
}

ACTIVE_STATUSES = {"outstanding", "in_progress"}
COMPLETED_STATUSES = {"finished_issuer", "finished_contractor", "finished"}
TERMINAL_STATUSES = {"cancelled", "rejected", "failed", "deleted", "reversed"}


# =============================================================================
# Helper Functions
# =============================================================================


def _resolve_location_name(client: ESIClient, location_id: Optional[int]) -> str:
    """Resolve a location ID to a name."""
    if not location_id:
        return "Unknown Location"

    # Try station first (NPC stations)
    station = client.get_safe(f"/universe/stations/{location_id}/")
    if station and "name" in station:
        return station["name"]

    # Could be a structure - requires separate handling
    # For now, return a generic name
    return f"Structure-{location_id}"


def _resolve_character_name(client: ESIClient, char_id: Optional[int]) -> Optional[str]:
    """Resolve a character ID to a name."""
    if not char_id:
        return None

    char_info = client.get_safe(f"/characters/{char_id}/")
    if char_info and "name" in char_info:
        return char_info["name"]
    return f"Character-{char_id}"


def _resolve_corporation_name(client: ESIClient, corp_id: Optional[int]) -> Optional[str]:
    """Resolve a corporation ID to a name."""
    if not corp_id:
        return None

    corp_info = client.get_safe(f"/corporations/{corp_id}/")
    if corp_info and "name" in corp_info:
        return corp_info["name"]
    return f"Corporation-{corp_id}"


def _calculate_days_remaining(expiry_str: Optional[str]) -> Optional[int]:
    """Calculate days remaining until expiry."""
    if not expiry_str:
        return None

    expiry = parse_datetime(expiry_str)
    if not expiry:
        return None

    now = datetime.now(timezone.utc)
    delta = expiry - now
    return max(0, delta.days)


# =============================================================================
# Contracts List Command
# =============================================================================


def cmd_contracts(args: argparse.Namespace) -> dict:
    """
    Fetch personal contracts.

    Shows item exchange, courier, and auction contracts.
    """
    query_ts = get_utc_timestamp()

    # Parse filter options
    issued_only = getattr(args, "issued", False)
    received_only = getattr(args, "received", False)
    contract_type = getattr(args, "type", None)
    active_only = getattr(args, "active", False)
    completed_only = getattr(args, "completed", False)
    limit = getattr(args, "limit", 20)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Check for required scope
    if not creds.has_scope("esi-contracts.read_character_contracts.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-contracts.read_character_contracts.v1",
            "action": "Re-run OAuth setup to authorize contracts access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    # Fetch contracts
    try:
        contracts_data = client.get(f"/characters/{char_id}/contracts/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch contracts: {e.message}",
            "hint": "Ensure esi-contracts.read_character_contracts.v1 scope is authorized",
            "query_timestamp": query_ts,
        }

    if not isinstance(contracts_data, list):
        contracts_data = []

    if not contracts_data:
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "character_id": char_id,
            "summary": {"total_contracts": 0, "issued": 0, "received": 0},
            "contracts": [],
            "message": "No contracts found",
        }

    # Collect IDs for name resolution
    char_ids_to_resolve = set()
    corp_ids_to_resolve = set()
    location_ids_to_resolve = set()

    for contract in contracts_data:
        if contract.get("issuer_id"):
            char_ids_to_resolve.add(contract["issuer_id"])
        if contract.get("acceptor_id"):
            char_ids_to_resolve.add(contract["acceptor_id"])
        if contract.get("assignee_id"):
            # Could be character, corp, or alliance - try as character first
            char_ids_to_resolve.add(contract["assignee_id"])
        if contract.get("issuer_corporation_id"):
            corp_ids_to_resolve.add(contract["issuer_corporation_id"])
        if contract.get("start_location_id"):
            location_ids_to_resolve.add(contract["start_location_id"])
        if contract.get("end_location_id"):
            location_ids_to_resolve.add(contract["end_location_id"])

    # Resolve names (batch for efficiency, limit to reasonable count)
    char_names = {}
    for cid in list(char_ids_to_resolve)[:30]:
        name = _resolve_character_name(public_client, cid)
        if name:
            char_names[cid] = name

    location_names = {}
    for lid in list(location_ids_to_resolve)[:20]:
        name = _resolve_location_name(public_client, lid)
        if name:
            location_names[lid] = name

    # Process contracts
    datetime.now(timezone.utc)
    processed_contracts = []
    summary = {
        "total_contracts": 0,
        "issued": 0,
        "received": 0,
        "outstanding": 0,
        "in_progress": 0,
        "completed": 0,
        "by_type": {"item_exchange": 0, "courier": 0, "auction": 0, "loan": 0, "unknown": 0},
    }

    for contract in contracts_data:
        contract_id = contract.get("contract_id")
        c_type = contract.get("type", "unknown")
        c_status = contract.get("status", "unknown")
        issuer_id = contract.get("issuer_id")
        acceptor_id = contract.get("acceptor_id")
        assignee_id = contract.get("assignee_id")

        # Determine relationship to character
        is_issuer = issuer_id == char_id
        is_acceptor = acceptor_id == char_id
        is_assignee = assignee_id == char_id

        # Filter: issued only
        if issued_only and not is_issuer:
            continue

        # Filter: received only (assigned to character or accepted by character)
        if received_only and is_issuer and not is_acceptor:
            continue

        # Filter: by type
        if contract_type and c_type != contract_type:
            continue

        # Filter: active only
        if active_only and c_status not in ACTIVE_STATUSES:
            continue

        # Filter: completed only
        if completed_only and c_status not in COMPLETED_STATUSES:
            continue

        # Update summary
        summary["total_contracts"] += 1
        if is_issuer:
            summary["issued"] += 1
        else:
            summary["received"] += 1

        if c_status in ACTIVE_STATUSES:
            if c_status == "outstanding":
                summary["outstanding"] += 1
            else:
                summary["in_progress"] += 1
        elif c_status in COMPLETED_STATUSES:
            summary["completed"] += 1

        if c_type in summary["by_type"]:
            summary["by_type"][c_type] += 1

        # Calculate days remaining
        days_remaining = _calculate_days_remaining(contract.get("date_expired"))

        # Build processed contract
        processed = {
            "contract_id": contract_id,
            "type": c_type,
            "type_display": CONTRACT_TYPES.get(c_type, c_type),
            "status": c_status,
            "status_display": CONTRACT_STATUSES.get(c_status, c_status),
            "title": contract.get("title") or f"{CONTRACT_TYPES.get(c_type, 'Contract')}",
            "availability": contract.get("availability", "unknown"),
            "for_corporation": contract.get("for_corporation", False),
            "is_issuer": is_issuer,
            "is_acceptor": is_acceptor,
            "is_assignee": is_assignee,
            "issuer_id": issuer_id,
            "issuer_name": char_names.get(issuer_id, f"Character-{issuer_id}"),
            "date_issued": contract.get("date_issued"),
            "date_expired": contract.get("date_expired"),
            "days_remaining": days_remaining,
        }

        # Add acceptor info if present
        if acceptor_id:
            processed["acceptor_id"] = acceptor_id
            processed["acceptor_name"] = char_names.get(acceptor_id)
            processed["date_accepted"] = contract.get("date_accepted")

        # Add assignee info if present
        if assignee_id and assignee_id != 0:
            processed["assignee_id"] = assignee_id
            processed["assignee_name"] = char_names.get(assignee_id)

        # Type-specific fields
        if c_type == "item_exchange":
            processed["price"] = contract.get("price", 0)
            processed["price_formatted"] = format_isk(contract.get("price", 0))

        elif c_type == "auction":
            processed["price"] = contract.get("price", 0)  # Starting/current bid
            processed["price_formatted"] = format_isk(contract.get("price", 0))
            processed["buyout"] = contract.get("buyout")
            if processed["buyout"]:
                processed["buyout_formatted"] = format_isk(processed["buyout"])

        elif c_type == "courier":
            processed["reward"] = contract.get("reward", 0)
            processed["reward_formatted"] = format_isk(contract.get("reward", 0))
            processed["collateral"] = contract.get("collateral", 0)
            processed["collateral_formatted"] = format_isk(contract.get("collateral", 0))
            processed["volume"] = contract.get("volume", 0)
            processed["days_to_complete"] = contract.get("days_to_complete", 0)

            start_loc = contract.get("start_location_id")
            end_loc = contract.get("end_location_id")
            processed["start_location_id"] = start_loc
            processed["end_location_id"] = end_loc
            processed["start_location"] = location_names.get(start_loc, f"Location-{start_loc}")
            processed["end_location"] = location_names.get(end_loc, f"Location-{end_loc}")

        processed_contracts.append(processed)

    # Sort: outstanding first, then in_progress, then by date
    def sort_key(c):
        status_order = {
            "outstanding": 0,
            "in_progress": 1,
            "finished_issuer": 2,
            "finished_contractor": 2,
            "finished": 3,
        }
        order = status_order.get(c["status"], 4)
        # Sort by expiry date for active, by date_issued for others
        date_key = c.get("date_expired") or c.get("date_issued") or "9999"
        return (order, date_key)

    processed_contracts.sort(key=sort_key)

    # Apply limit
    processed_contracts = processed_contracts[:limit]

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "character_id": char_id,
        "summary": summary,
        "contracts": processed_contracts,
        "filters": {
            "issued_only": issued_only,
            "received_only": received_only,
            "type": contract_type,
            "active_only": active_only,
            "completed_only": completed_only,
            "limit": limit,
        },
    }


# =============================================================================
# Contract Detail Command
# =============================================================================


def cmd_contract_detail(args: argparse.Namespace) -> dict:
    """
    Fetch detailed information about a specific contract.

    Shows items in the contract and bid history for auctions.
    """
    query_ts = get_utc_timestamp()
    contract_id = getattr(args, "contract_id", None)

    if not contract_id:
        return {
            "error": "missing_argument",
            "message": "Contract ID is required",
            "usage": "python3 -m aria_esi contract <contract_id>",
            "query_timestamp": query_ts,
        }

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Check scope
    if not creds.has_scope("esi-contracts.read_character_contracts.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-contracts.read_character_contracts.v1",
            "query_timestamp": query_ts,
        }

    # Find the contract in the character's contracts
    try:
        contracts_data = client.get(f"/characters/{char_id}/contracts/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch contracts: {e.message}",
            "query_timestamp": query_ts,
        }

    if not isinstance(contracts_data, list):
        contracts_data = []

    # Find the specific contract
    contract = None
    for c in contracts_data:
        if c.get("contract_id") == contract_id:
            contract = c
            break

    if not contract:
        return {
            "error": "contract_not_found",
            "message": f"Contract {contract_id} not found in your contracts",
            "hint": "You can only view details of contracts you're involved with",
            "query_timestamp": query_ts,
        }

    c_type = contract.get("type", "unknown")
    c_status = contract.get("status", "unknown")
    issuer_id = contract.get("issuer_id")
    acceptor_id = contract.get("acceptor_id")

    # Resolve names
    issuer_name = _resolve_character_name(public_client, issuer_id)
    acceptor_name = _resolve_character_name(public_client, acceptor_id) if acceptor_id else None

    # Fetch contract items
    items = []
    try:
        items_data = client.get(f"/characters/{char_id}/contracts/{contract_id}/items/", auth=True)
        if isinstance(items_data, list):
            # Resolve item type names
            type_ids = set(item.get("type_id") for item in items_data if item.get("type_id"))
            type_names = {}
            for tid in list(type_ids)[:50]:
                info = public_client.get_safe(f"/universe/types/{tid}/")
                if info and "name" in info:
                    type_names[tid] = info["name"]

            for item in items_data:
                tid = item.get("type_id")
                items.append(
                    {
                        "type_id": tid,
                        "type_name": type_names.get(tid, f"Unknown ({tid})"),
                        "quantity": item.get("quantity", 1),
                        "is_included": item.get("is_included", True),
                        "is_singleton": item.get("is_singleton", False),
                    }
                )
    except ESIError:
        pass  # Items may not be accessible for all contracts

    # Fetch bids for auction contracts
    bids = []
    if c_type == "auction":
        try:
            bids_data = client.get(
                f"/characters/{char_id}/contracts/{contract_id}/bids/", auth=True
            )
            if isinstance(bids_data, list):
                # Resolve bidder names
                bidder_ids = set(b.get("bidder_id") for b in bids_data if b.get("bidder_id"))
                bidder_names = {}
                for bid in list(bidder_ids)[:10]:
                    name = _resolve_character_name(public_client, bid)
                    if name:
                        bidder_names[bid] = name

                for bid in bids_data:
                    bidder_id = bid.get("bidder_id")
                    bids.append(
                        {
                            "bid_id": bid.get("bid_id"),
                            "bidder_id": bidder_id,
                            "bidder_name": bidder_names.get(bidder_id, f"Bidder-{bidder_id}"),
                            "amount": bid.get("amount", 0),
                            "amount_formatted": format_isk(bid.get("amount", 0)),
                            "date_bid": bid.get("date_bid"),
                        }
                    )
                # Sort by amount descending
                bids.sort(key=lambda b: b.get("amount", 0), reverse=True)
        except ESIError:
            pass

    # Resolve locations for courier contracts
    start_location = None
    end_location = None
    if c_type == "courier":
        start_loc_id = contract.get("start_location_id")
        end_loc_id = contract.get("end_location_id")
        if start_loc_id:
            start_location = _resolve_location_name(public_client, start_loc_id)
        if end_loc_id:
            end_location = _resolve_location_name(public_client, end_loc_id)

    # Build response
    is_issuer = issuer_id == char_id
    days_remaining = _calculate_days_remaining(contract.get("date_expired"))

    result = {
        "query_timestamp": query_ts,
        "volatility": "stable",
        "contract_id": contract_id,
        "type": c_type,
        "type_display": CONTRACT_TYPES.get(c_type, c_type),
        "status": c_status,
        "status_display": CONTRACT_STATUSES.get(c_status, c_status),
        "title": contract.get("title") or f"{CONTRACT_TYPES.get(c_type, 'Contract')}",
        "availability": contract.get("availability"),
        "is_issuer": is_issuer,
        "issuer": {"character_id": issuer_id, "name": issuer_name},
        "date_issued": contract.get("date_issued"),
        "date_expired": contract.get("date_expired"),
        "days_remaining": days_remaining,
        "items": items,
        "items_count": len(items),
    }

    if acceptor_id:
        result["acceptor"] = {"character_id": acceptor_id, "name": acceptor_name}
        result["date_accepted"] = contract.get("date_accepted")

    # Type-specific fields
    if c_type == "item_exchange":
        result["price"] = contract.get("price", 0)
        result["price_formatted"] = format_isk(contract.get("price", 0))

    elif c_type == "auction":
        result["price"] = contract.get("price", 0)
        result["price_formatted"] = format_isk(contract.get("price", 0))
        result["buyout"] = contract.get("buyout")
        if result["buyout"]:
            result["buyout_formatted"] = format_isk(result["buyout"])
        result["bids"] = bids
        result["bid_count"] = len(bids)
        if bids:
            result["current_bid"] = bids[0]["amount"]
            result["current_bid_formatted"] = bids[0]["amount_formatted"]

    elif c_type == "courier":
        result["reward"] = contract.get("reward", 0)
        result["reward_formatted"] = format_isk(contract.get("reward", 0))
        result["collateral"] = contract.get("collateral", 0)
        result["collateral_formatted"] = format_isk(contract.get("collateral", 0))
        result["volume"] = contract.get("volume", 0)
        result["days_to_complete"] = contract.get("days_to_complete", 0)
        result["start_location"] = start_location
        result["end_location"] = end_location

    return result


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register contracts command parsers."""

    # Contracts list command
    list_parser = subparsers.add_parser(
        "contracts", help="List personal contracts (item exchange, courier, auction)"
    )
    list_parser.add_argument("--issued", action="store_true", help="Show only contracts you issued")
    list_parser.add_argument(
        "--received", action="store_true", help="Show only contracts assigned to you"
    )
    list_parser.add_argument(
        "--type",
        "-t",
        choices=["item_exchange", "courier", "auction", "loan"],
        help="Filter by contract type",
    )
    list_parser.add_argument(
        "--active", action="store_true", help="Show only active contracts (outstanding/in_progress)"
    )
    list_parser.add_argument(
        "--completed", action="store_true", help="Show only completed contracts"
    )
    list_parser.add_argument(
        "--limit", "-n", type=int, default=20, help="Maximum contracts to show (default: 20)"
    )
    list_parser.set_defaults(func=cmd_contracts)

    # Contract detail command
    detail_parser = subparsers.add_parser("contract", help="Detailed view of a specific contract")
    detail_parser.add_argument("contract_id", type=int, help="Contract ID to view")
    detail_parser.set_defaults(func=cmd_contract_detail)
