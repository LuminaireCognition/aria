"""
Pilot Dispatcher for MCP Server.

Provides authenticated ESI access for character-specific data:
- mail_list: List mail headers
- mail_read: Read a specific mail body
- mining_ledger: View mining extraction history
- contracts: List personal contracts
- fittings_list: List saved ship fittings
- fittings_detail: Show fitting details with EFT export
- lp_balance: LP balances across all corporations
- lp_offers: Browse LP store offers for a corporation
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from ..context import log_context, wrap_output
from ..errors import InvalidParameterError
from ..policy import check_capability

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


PilotAction = Literal[
    "mail_list",
    "mail_read",
    "mining_ledger",
    "contracts",
    "fittings_list",
    "fittings_detail",
    "lp_balance",
    "lp_offers",
]

VALID_ACTIONS: set[str] = {
    "mail_list",
    "mail_read",
    "mining_ledger",
    "contracts",
    "fittings_list",
    "fittings_detail",
    "lp_balance",
    "lp_offers",
}


def register_pilot_dispatcher(server: FastMCP) -> None:
    """
    Register the pilot dispatcher with MCP server.

    Args:
        server: MCP Server instance
    """

    @server.tool()
    @log_context("pilot")
    async def pilot(
        action: str,
        # mail_list params
        unread_only: bool = False,
        limit: int = 50,
        # mail_read params
        mail_id: int | None = None,
        # mining_ledger params
        days: int = 30,
        system_filter: str | None = None,
        ore_filter: str | None = None,
        # contracts params
        status_filter: str | None = None,
        type_filter: str | None = None,
        issued: bool = True,
        received: bool = True,
        # fittings params
        ship_filter: str | None = None,
        fitting_id: int | None = None,
        eft: bool = False,
        # lp_offers params
        corporation_name: str | None = None,
        search: str | None = None,
        max_lp: int | None = None,
        affordable: bool = False,
    ) -> dict:
        """
        Unified pilot data interface for authenticated ESI endpoints.

        Actions:
        - mail_list: List mail headers with optional unread filter
        - mail_read: Read a specific mail body
        - mining_ledger: View mining extraction history
        - contracts: List personal contracts
        - fittings_list: List saved ship fittings
        - fittings_detail: Show fitting details with EFT export
        - lp_balance: LP balances across all corporations
        - lp_offers: Browse LP store offers for a corporation

        Args:
            action: The operation to perform

            Mail list params (action="mail_list"):
                unread_only: Show only unread mail (default False)
                limit: Max results (default 50)

            Mail read params (action="mail_read"):
                mail_id: Mail ID to read (required)

            Mining ledger params (action="mining_ledger"):
                days: Limit to last N days (default 30, max 30)
                system_filter: Filter by system name (partial match)
                ore_filter: Filter by ore type name (partial match)

            Contracts params (action="contracts"):
                status_filter: "active", "completed", or None for all
                type_filter: "item_exchange", "courier", "auction", or None
                issued: Include contracts you issued (default True)
                received: Include contracts assigned to you (default True)
                limit: Max results (default 50)

            Fittings list params (action="fittings_list"):
                ship_filter: Filter by ship hull name (partial match)

            Fittings detail params (action="fittings_detail"):
                fitting_id: Fitting ID to show (required)
                eft: Return EFT format only (default False)

            LP balance params (action="lp_balance"):
                (none)

            LP offers params (action="lp_offers"):
                corporation_name: Corporation name, ID, or shortcut (required)
                search: Filter offers by item name (partial match)
                max_lp: Maximum LP cost to show
                affordable: Only show offers you can afford (default False)

        Returns:
            For contracts:
            - contracts: List of contracts with type, status, price, counterparty
            - summary: {total_contracts, issued, received, outstanding, ...}

            For fittings_list:
            - fittings: List of saved fittings with name, ship, module count
            - summary: {total_fittings, unique_hulls}

            For fittings_detail:
            - fitting: {name, ship, slots, eft_format}

            For lp_balance:
            - balances: List of {corporation_name, loyalty_points}

            For lp_offers:
            - offers: List of LP store offers with costs and requirements

        Examples:
            pilot(action="contracts", status_filter="active")
            pilot(action="fittings_list", ship_filter="Vexor")
            pilot(action="fittings_detail", fitting_id=12345)
            pilot(action="lp_balance")
            pilot(action="lp_offers", corporation_name="Federation Navy")
        """
        if action not in VALID_ACTIONS:
            raise InvalidParameterError(
                "action",
                action,
                f"Must be one of: {', '.join(sorted(VALID_ACTIONS))}",
            )

        # Policy check
        check_capability("pilot", action)

        match action:
            case "mail_list":
                return await _mail_list(unread_only=unread_only, limit=limit)
            case "mail_read":
                return await _mail_read(mail_id=mail_id)
            case "mining_ledger":
                return await _mining_ledger(
                    days=days, system_filter=system_filter, ore_filter=ore_filter
                )
            case "contracts":
                return await _contracts(
                    status_filter=status_filter,
                    type_filter=type_filter,
                    issued=issued,
                    received=received,
                    limit=limit,
                )
            case "fittings_list":
                return await _fittings_list(ship_filter=ship_filter)
            case "fittings_detail":
                return await _fittings_detail(fitting_id=fitting_id, eft=eft)
            case "lp_balance":
                return await _lp_balance()
            case "lp_offers":
                return await _lp_offers(
                    corporation_name=corporation_name,
                    search=search,
                    max_lp=max_lp,
                    affordable=affordable,
                )
            case _:
                raise InvalidParameterError("action", action, "Unknown action")


# =============================================================================
# Helper Functions
# =============================================================================


def _strip_html(text: str) -> str:
    """Strip HTML tags from text."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = clean.replace("&nbsp;", " ")
    clean = clean.replace("&lt;", "<")
    clean = clean.replace("&gt;", ">")
    clean = clean.replace("&amp;", "&")
    clean = clean.replace("&quot;", '"')
    clean = clean.replace("&#39;", "'")
    return clean.strip()


async def _resolve_sender_name(client: Any, sender_id: int) -> str:
    """Resolve a sender ID to a name (could be character, corp, or alliance)."""
    if not sender_id:
        return "Unknown"
    # Try character first
    info = await client.get_safe(f"/characters/{sender_id}/")
    if isinstance(info, dict) and "name" in info:
        return info["name"]
    # Try corporation
    info = await client.get_safe(f"/corporations/{sender_id}/")
    if isinstance(info, dict) and "name" in info:
        return info["name"]
    return f"Unknown-{sender_id}"


# =============================================================================
# Mail List Action
# =============================================================================


async def _mail_list(unread_only: bool, limit: int) -> dict:
    """List mail headers."""
    from aria_esi.store.esi_client import get_authenticated_async_esi_client

    auth_ctx = await get_authenticated_async_esi_client()
    client = auth_ctx.client
    char_id = auth_ctx.character_id

    # Check scope
    if not auth_ctx.creds.has_scope("esi-mail.read_mail.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-mail.read_mail.v1",
            "action": "Re-run OAuth setup to authorize mail access",
            "command": "uv run python .claude/scripts/aria-oauth-setup.py",
        }

    # Fetch mail headers
    mail_data = await client.get_safe(f"/characters/{char_id}/mail/", auth=True)
    if not isinstance(mail_data, list) or not mail_data:
        return {
            "character_id": char_id,
            "summary": {"total_shown": 0, "unread_count": 0},
            "mail": [],
            "message": "No mail found",
        }

    # Resolve sender names
    sender_ids = {m.get("from", 0) for m in mail_data if isinstance(m, dict)}
    sender_names: dict[int, str] = {}
    for sid in sender_ids:
        if sid:
            sender_names[sid] = await _resolve_sender_name(client, sid)

    # Process mail
    processed_mail = []
    unread_count = 0

    for mail in mail_data:
        is_read = mail.get("is_read", True)
        if unread_only and is_read:
            continue
        if not is_read:
            unread_count += 1

        from_id = mail.get("from", 0)
        processed_mail.append(
            {
                "mail_id": mail.get("mail_id"),
                "from_id": from_id,
                "from_name": sender_names.get(from_id, f"Unknown-{from_id}"),
                "subject": mail.get("subject", "(No Subject)"),
                "timestamp": mail.get("timestamp"),
                "is_read": is_read,
                "labels": mail.get("labels", []),
            }
        )

        if len(processed_mail) >= limit:
            break

    # Sort: unread first, then by timestamp
    processed_mail.sort(key=lambda m: (m["is_read"], m.get("timestamp", "") or ""), reverse=False)

    return wrap_output(
        {
            "character_id": char_id,
            "summary": {"total_shown": len(processed_mail), "unread_count": unread_count},
            "mail": processed_mail,
            "filters": {"unread_only": unread_only, "limit": limit},
        },
        items_key="mail",
        max_items=100,
    )


# =============================================================================
# Mail Read Action
# =============================================================================


async def _mail_read(mail_id: int | None) -> dict:
    """Read a specific mail body."""
    if not mail_id:
        raise InvalidParameterError("mail_id", mail_id, "Required for action='mail_read'")

    from aria_esi.store.esi_client import get_authenticated_async_esi_client

    auth_ctx = await get_authenticated_async_esi_client()
    client = auth_ctx.client
    char_id = auth_ctx.character_id

    if not auth_ctx.creds.has_scope("esi-mail.read_mail.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-mail.read_mail.v1",
            "action": "Re-run OAuth setup to authorize mail access",
            "command": "uv run python .claude/scripts/aria-oauth-setup.py",
        }

    mail_data = await client.get_safe(f"/characters/{char_id}/mail/{mail_id}/", auth=True)
    if not isinstance(mail_data, dict):
        return {
            "error": "not_found",
            "message": f"Mail ID {mail_id} not found",
            "hint": "Use pilot(action='mail_list') to list available mail IDs",
        }

    # Resolve sender name
    from_id = mail_data.get("from", 0)
    from_name = await _resolve_sender_name(client, from_id)

    # Clean up body
    body = _strip_html(mail_data.get("body", ""))

    return {
        "mail": {
            "mail_id": mail_id,
            "from_id": from_id,
            "from_name": from_name,
            "subject": mail_data.get("subject", "(No Subject)"),
            "timestamp": mail_data.get("timestamp"),
            "body": body,
            "labels": mail_data.get("labels", []),
            "recipients": mail_data.get("recipients", []),
        },
    }


# =============================================================================
# Mining Ledger Action
# =============================================================================


async def _mining_ledger(days: int, system_filter: str | None, ore_filter: str | None) -> dict:
    """Fetch mining ledger entries."""
    from aria_esi.store.esi_client import get_async_esi_client, get_authenticated_async_esi_client

    auth_ctx = await get_authenticated_async_esi_client()
    client = auth_ctx.client
    char_id = auth_ctx.character_id

    if not auth_ctx.creds.has_scope("esi-industry.read_character_mining.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-industry.read_character_mining.v1",
            "action": "Re-run OAuth setup to authorize mining ledger access",
            "command": "uv run python .claude/scripts/aria-oauth-setup.py",
        }

    # Fetch mining ledger (paginated)
    all_entries: list[dict] = []
    page = 1
    while True:
        entries = await client.get_safe(
            f"/characters/{char_id}/mining/", auth=True, params={"page": page}
        )
        if not isinstance(entries, list) or not entries:
            break
        all_entries.extend(entries)
        page += 1
        if page > 20:
            break

    if not all_entries:
        return {
            "character_id": char_id,
            "summary": {
                "total_entries": 0,
                "total_quantity": 0,
                "unique_ores": 0,
                "unique_systems": 0,
                "days_covered": 0,
            },
            "entries": [],
            "message": "No mining activity in the last 30 days",
        }

    # Date filter
    days = min(max(1, days), 30)
    cutoff_date = None
    if days < 30:
        cutoff_date = (datetime.now(UTC) - timedelta(days=days)).date()

    # Collect IDs for resolution
    type_ids = {e.get("type_id", 0) for e in all_entries}
    system_ids = {e.get("solar_system_id", 0) for e in all_entries}

    # Use public client for name resolution
    pub_client = await get_async_esi_client()

    # Resolve type names
    type_names: dict[int, str] = {}
    for tid in type_ids:
        if tid:
            info = await pub_client.get_safe(f"/universe/types/{tid}/")
            if isinstance(info, dict) and "name" in info:
                type_names[tid] = info["name"]
            else:
                type_names[tid] = f"Unknown-{tid}"

    # Resolve system names and security
    system_info: dict[int, dict[str, Any]] = {}
    for sid in system_ids:
        if sid:
            info = await pub_client.get_safe(f"/universe/systems/{sid}/")
            if isinstance(info, dict):
                system_info[sid] = {
                    "name": info.get("name", f"System-{sid}"),
                    "security": round(info.get("security_status", 0.0), 1),
                }
            else:
                system_info[sid] = {"name": f"System-{sid}", "security": 0.0}

    # Process entries
    processed_entries = []
    total_quantity = 0
    unique_ores: set[int] = set()
    unique_systems: set[int] = set()
    dates_seen: set[str] = set()

    for entry in all_entries:
        entry_date = entry.get("date", "")
        type_id = entry.get("type_id", 0)
        system_id = entry.get("solar_system_id", 0)
        quantity = entry.get("quantity", 0)

        # Apply date filter
        if cutoff_date and entry_date:
            try:
                entry_date_obj = datetime.strptime(entry_date, "%Y-%m-%d").date()
                if entry_date_obj < cutoff_date:
                    continue
            except ValueError:
                pass

        type_name = type_names.get(type_id, f"Unknown-{type_id}")
        sys_data = system_info.get(system_id, {"name": "Unknown", "security": 0.0})

        # Apply system filter
        if system_filter and system_filter.lower() not in sys_data["name"].lower():
            continue

        # Apply ore filter
        if ore_filter and ore_filter.lower() not in type_name.lower():
            continue

        processed_entries.append(
            {
                "date": entry_date,
                "type_id": type_id,
                "type_name": type_name,
                "quantity": quantity,
                "solar_system_id": system_id,
                "solar_system_name": sys_data["name"],
                "security": sys_data["security"],
            }
        )

        total_quantity += quantity
        unique_ores.add(type_id)
        unique_systems.add(system_id)
        dates_seen.add(entry_date)

    # Sort by date descending
    processed_entries.sort(key=lambda e: (e["date"], e["type_name"]), reverse=True)

    return wrap_output(
        {
            "character_id": char_id,
            "summary": {
                "total_entries": len(processed_entries),
                "total_quantity": total_quantity,
                "unique_ores": len(unique_ores),
                "unique_systems": len(unique_systems),
                "days_covered": len(dates_seen),
            },
            "entries": processed_entries,
            "filters": {"days": days, "system": system_filter, "ore": ore_filter},
        },
        items_key="entries",
        max_items=200,
    )


# =============================================================================
# Contracts Action
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


def _format_isk(value: float) -> str:
    """Format ISK value with magnitude suffix."""
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B ISK"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M ISK"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K ISK"
    return f"{value:.0f} ISK"


def _calculate_days_remaining(expiry_str: str | None) -> int | None:
    """Calculate days remaining until expiry."""
    if not expiry_str:
        return None
    try:
        # ESI timestamps: "2024-01-15T12:00:00Z"
        expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        delta = expiry - datetime.now(UTC)
        return max(0, delta.days)
    except (ValueError, TypeError):
        return None


async def _resolve_names_batch(client: Any, ids: set[int]) -> dict[int, str]:
    """Resolve a batch of entity IDs (characters, corps) to names."""
    names: dict[int, str] = {}
    for eid in list(ids)[:30]:
        if not eid:
            continue
        info = await client.get_safe(f"/characters/{eid}/")
        if isinstance(info, dict) and "name" in info:
            names[eid] = info["name"]
            continue
        info = await client.get_safe(f"/corporations/{eid}/")
        if isinstance(info, dict) and "name" in info:
            names[eid] = info["name"]
            continue
        names[eid] = f"Unknown-{eid}"
    return names


async def _resolve_location_name_async(client: Any, location_id: int | None) -> str:
    """Resolve a location ID to a name."""
    if not location_id:
        return "Unknown Location"
    station = await client.get_safe(f"/universe/stations/{location_id}/")
    if isinstance(station, dict) and "name" in station:
        return station["name"]
    return f"Structure-{location_id}"


async def _contracts(
    status_filter: str | None,
    type_filter: str | None,
    issued: bool,
    received: bool,
    limit: int,
) -> dict:
    """List personal contracts."""
    from aria_esi.store.esi_client import get_async_esi_client, get_authenticated_async_esi_client

    auth_ctx = await get_authenticated_async_esi_client()
    client = auth_ctx.client
    char_id = auth_ctx.character_id

    if not auth_ctx.creds.has_scope("esi-contracts.read_character_contracts.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-contracts.read_character_contracts.v1",
            "action": "Re-run OAuth setup to authorize contracts access",
            "command": "uv run python .claude/scripts/aria-oauth-setup.py",
        }

    contracts_data = await client.get_safe(f"/characters/{char_id}/contracts/", auth=True)
    if not isinstance(contracts_data, list) or not contracts_data:
        return {
            "character_id": char_id,
            "summary": {"total_contracts": 0, "issued": 0, "received": 0},
            "contracts": [],
            "message": "No contracts found",
        }

    # Collect IDs for batch resolution
    char_ids: set[int] = set()
    location_ids: set[int] = set()
    for c in contracts_data:
        if not isinstance(c, dict):
            continue
        for key in ("issuer_id", "acceptor_id", "assignee_id"):
            if c.get(key):
                char_ids.add(c[key])
        for key in ("start_location_id", "end_location_id"):
            if c.get(key):
                location_ids.add(c[key])

    # Resolve names using public client
    pub_client = await get_async_esi_client()
    char_names = await _resolve_names_batch(pub_client, char_ids)
    location_names: dict[int, str] = {}
    for lid in list(location_ids)[:20]:
        location_names[lid] = await _resolve_location_name_async(pub_client, lid)

    # Process contracts
    processed = []
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
        if not isinstance(contract, dict):
            continue

        c_type = contract.get("type", "unknown")
        c_status = contract.get("status", "unknown")
        issuer_id = contract.get("issuer_id")
        acceptor_id = contract.get("acceptor_id")

        is_issuer = issuer_id == char_id

        # Direction filters
        if not issued and is_issuer:
            continue
        if not received and not is_issuer:
            continue

        # Status filter
        if status_filter == "active" and c_status not in ACTIVE_STATUSES:
            continue
        if status_filter == "completed" and c_status not in COMPLETED_STATUSES:
            continue

        # Type filter
        if type_filter and c_type != type_filter:
            continue

        # Update summary
        summary["total_contracts"] += 1
        if is_issuer:
            summary["issued"] += 1
        else:
            summary["received"] += 1
        if c_status == "outstanding":
            summary["outstanding"] += 1
        elif c_status == "in_progress":
            summary["in_progress"] += 1
        elif c_status in COMPLETED_STATUSES:
            summary["completed"] += 1
        if c_type in summary["by_type"]:
            summary["by_type"][c_type] += 1

        days_remaining = _calculate_days_remaining(contract.get("date_expired"))

        entry: dict[str, Any] = {
            "contract_id": contract.get("contract_id"),
            "type": c_type,
            "type_display": CONTRACT_TYPES.get(c_type, c_type),
            "status": c_status,
            "status_display": CONTRACT_STATUSES.get(c_status, c_status),
            "title": contract.get("title") or CONTRACT_TYPES.get(c_type, "Contract"),
            "availability": contract.get("availability", "unknown"),
            "is_issuer": is_issuer,
            "issuer_name": char_names.get(issuer_id, f"Character-{issuer_id}")
            if issuer_id
            else "Unknown",
            "date_issued": contract.get("date_issued"),
            "date_expired": contract.get("date_expired"),
            "days_remaining": days_remaining,
        }

        if acceptor_id:
            entry["acceptor_name"] = char_names.get(acceptor_id)

        # Type-specific fields
        if c_type == "item_exchange":
            entry["price"] = contract.get("price", 0)
            entry["price_formatted"] = _format_isk(contract.get("price", 0))
        elif c_type == "auction":
            entry["price"] = contract.get("price", 0)
            entry["price_formatted"] = _format_isk(contract.get("price", 0))
            buyout = contract.get("buyout")
            if buyout:
                entry["buyout"] = buyout
                entry["buyout_formatted"] = _format_isk(buyout)
        elif c_type == "courier":
            entry["reward"] = contract.get("reward", 0)
            entry["reward_formatted"] = _format_isk(contract.get("reward", 0))
            entry["collateral"] = contract.get("collateral", 0)
            entry["collateral_formatted"] = _format_isk(contract.get("collateral", 0))
            entry["volume"] = contract.get("volume", 0)
            entry["days_to_complete"] = contract.get("days_to_complete", 0)
            start_loc = contract.get("start_location_id")
            end_loc = contract.get("end_location_id")
            if start_loc:
                entry["start_location"] = location_names.get(start_loc, f"Location-{start_loc}")
            if end_loc:
                entry["end_location"] = location_names.get(end_loc, f"Location-{end_loc}")

        processed.append(entry)

    # Sort: outstanding first, then in_progress, then by date
    def sort_key(c: dict) -> tuple:
        status_order = {"outstanding": 0, "in_progress": 1}
        order = status_order.get(c["status"], 2 if c["status"] in COMPLETED_STATUSES else 3)
        date_key = c.get("date_expired") or c.get("date_issued") or "9999"
        return (order, date_key)

    processed.sort(key=sort_key)

    return wrap_output(
        {
            "character_id": char_id,
            "summary": summary,
            "contracts": processed,
            "filters": {
                "status": status_filter,
                "type": type_filter,
                "issued": issued,
                "received": received,
                "limit": limit,
            },
        },
        items_key="contracts",
        max_items=limit,
    )


# =============================================================================
# Fittings Actions
# =============================================================================

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

    for slot_key in ("high", "medium", "low", "rig", "subsystem"):
        for item in slots.get(slot_key, []):
            name = type_names.get(item["type_id"], f"Unknown-{item['type_id']}")
            for _ in range(item.get("quantity", 1)):
                lines.append(name)
        lines.append("")

    for slot_key in ("drone", "cargo"):
        for item in slots.get(slot_key, []):
            name = type_names.get(item["type_id"], f"Unknown-{item['type_id']}")
            qty = item.get("quantity", 1)
            lines.append(f"{name} x{qty}" if qty > 1 else name)

    return "\n".join(lines).strip()


def _resolve_type_ids_sync(type_ids: set[int]) -> dict[int, str]:
    """Resolve type IDs to names using SDE (sync, fast local lookup)."""
    from aria_esi.commands._resolution import resolve_type_ids

    type_ids.discard(0)
    if not type_ids:
        return {}
    info = resolve_type_ids(type_ids)
    return {tid: data["name"] for tid, data in info.items()}


async def _fittings_list(ship_filter: str | None) -> dict:
    """List saved ship fittings."""
    from aria_esi.store.esi_client import get_authenticated_async_esi_client

    auth_ctx = await get_authenticated_async_esi_client()
    client = auth_ctx.client
    char_id = auth_ctx.character_id

    if not auth_ctx.creds.has_scope("esi-fittings.read_fittings.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-fittings.read_fittings.v1",
            "action": "Re-run OAuth setup to authorize saved fittings access",
            "command": "uv run python .claude/scripts/aria-oauth-setup.py",
        }

    fittings_data = await client.get_safe(f"/characters/{char_id}/fittings/", auth=True)
    if not isinstance(fittings_data, list) or not fittings_data:
        return {
            "character_id": char_id,
            "summary": {"total_fittings": 0, "unique_hulls": 0},
            "fittings": [],
            "message": "No saved fittings found",
        }

    # Collect ship type IDs and resolve via SDE
    ship_type_ids = {f.get("ship_type_id", 0) for f in fittings_data if isinstance(f, dict)}
    ship_names = _resolve_type_ids_sync(ship_type_ids)

    # Process fittings
    processed_fittings = []
    unique_hulls: set[int] = set()

    for fit in fittings_data:
        if not isinstance(fit, dict):
            continue
        ship_type_id = fit.get("ship_type_id", 0)
        ship_name = ship_names.get(ship_type_id, f"Unknown-{ship_type_id}")

        if ship_filter and ship_filter.lower() not in ship_name.lower():
            continue

        items = fit.get("items", [])
        module_count = sum(item.get("quantity", 1) for item in items)

        processed_fittings.append(
            {
                "fitting_id": fit.get("fitting_id"),
                "name": fit.get("name", "Unnamed"),
                "description": fit.get("description", ""),
                "ship_type_id": ship_type_id,
                "ship_type_name": ship_name,
                "module_count": module_count,
            }
        )
        unique_hulls.add(ship_type_id)

    processed_fittings.sort(key=lambda f: f["name"].lower())

    return wrap_output(
        {
            "character_id": char_id,
            "summary": {
                "total_fittings": len(processed_fittings),
                "unique_hulls": len(unique_hulls),
            },
            "fittings": processed_fittings,
            "filters": {"ship": ship_filter},
        },
        items_key="fittings",
        max_items=100,
    )


async def _fittings_detail(fitting_id: int | None, eft: bool) -> dict:
    """Show fitting details with slot breakdown and optional EFT export."""
    if not fitting_id:
        raise InvalidParameterError(
            "fitting_id", fitting_id, "Required for action='fittings_detail'"
        )

    from aria_esi.store.esi_client import get_authenticated_async_esi_client

    auth_ctx = await get_authenticated_async_esi_client()
    client = auth_ctx.client
    char_id = auth_ctx.character_id

    if not auth_ctx.creds.has_scope("esi-fittings.read_fittings.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-fittings.read_fittings.v1",
            "action": "Re-run OAuth setup to authorize saved fittings access",
            "command": "uv run python .claude/scripts/aria-oauth-setup.py",
        }

    fittings_data = await client.get_safe(f"/characters/{char_id}/fittings/", auth=True)
    if not isinstance(fittings_data, list):
        fittings_data = []

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
            "hint": "Use pilot(action='fittings_list') to list available fitting IDs",
        }

    # Collect all type IDs (ship + modules)
    type_ids: set[int] = {target_fit.get("ship_type_id", 0)}
    for item in target_fit.get("items", []):
        if isinstance(item, dict):
            type_ids.add(item.get("type_id", 0))

    type_names = _resolve_type_ids_sync(type_ids)

    # Organize items by slot category
    slots: dict[str, list] = defaultdict(list)
    for item in target_fit.get("items", []):
        if not isinstance(item, dict):
            continue
        flag = item.get("flag", "")
        category = _categorize_flag(flag)
        slots[category].append(
            {
                "type_id": item.get("type_id"),
                "type_name": type_names.get(
                    item.get("type_id", 0), f"Unknown-{item.get('type_id')}"
                ),
                "quantity": item.get("quantity", 1),
                "flag": flag,
            }
        )

    ship_type_id = target_fit.get("ship_type_id", 0)
    ship_name = type_names.get(ship_type_id, f"Unknown-{ship_type_id}")
    fitting_name = target_fit.get("name", "Unnamed")

    eft_format = _generate_eft(ship_name, fitting_name, dict(slots), type_names)

    if eft:
        return {
            "fitting_id": fitting_id,
            "name": fitting_name,
            "eft_format": eft_format,
        }

    return {
        "character_id": char_id,
        "fitting": {
            "fitting_id": fitting_id,
            "name": fitting_name,
            "description": target_fit.get("description", ""),
            "ship_type_id": ship_type_id,
            "ship_type_name": ship_name,
            "slots": {
                key: slots.get(key, [])
                for key in (
                    "high",
                    "medium",
                    "low",
                    "rig",
                    "subsystem",
                    "drone",
                    "fighter",
                    "cargo",
                    "service",
                )
            },
            "eft_format": eft_format,
        },
    }


# =============================================================================
# LP Balance and Offers Actions
# =============================================================================

# Common NPC corporations for LP farming - used for name shortcuts
KNOWN_LP_CORPS: dict[str, int] = {
    "federation navy": 1000120,
    "fed navy": 1000120,
    "fednavy": 1000120,
    "caldari navy": 1000035,
    "cal navy": 1000035,
    "republic fleet": 1000182,
    "rep fleet": 1000182,
    "amarr navy": 1000003,
    "imperial navy": 1000003,
    "sisters of eve": 1000130,
    "soe": 1000130,
    "sisters": 1000130,
    "thukker mix": 1000171,
    "thukker": 1000171,
    "mordu's legion": 1000139,
    "mordus legion": 1000139,
    "mordus": 1000139,
    "concord": 1000125,
    "federal intelligence office": 1000103,
    "fio": 1000103,
    "ministry of war": 1000113,
}


async def _resolve_corporation_async(client: Any, query: str) -> tuple[int | None, str | None]:
    """Resolve corporation query to (corp_id, corp_name)."""
    # Numeric ID
    if query.strip().isdigit():
        corp_id = int(query.strip())
        info = await client.get_safe(f"/corporations/{corp_id}/")
        name = info.get("name") if isinstance(info, dict) else None
        return corp_id, name

    # Known shortcuts
    query_lower = query.lower().strip()
    if query_lower in KNOWN_LP_CORPS:
        corp_id = KNOWN_LP_CORPS[query_lower]
        info = await client.get_safe(f"/corporations/{corp_id}/")
        name = info.get("name") if isinstance(info, dict) else None
        return corp_id, name

    # ESI search via POST /universe/ids/
    try:
        resolved = await client.post("/universe/ids/", data=[query])
        if isinstance(resolved, dict):
            corps = resolved.get("corporations", [])
            if corps:
                return corps[0]["id"], corps[0]["name"]
    except Exception:  # noqa: BLE001
        pass

    return None, None


async def _lp_balance() -> dict:
    """Fetch LP balances across all corporations."""
    from aria_esi.store.esi_client import get_async_esi_client, get_authenticated_async_esi_client

    auth_ctx = await get_authenticated_async_esi_client()
    client = auth_ctx.client
    char_id = auth_ctx.character_id

    if not auth_ctx.creds.has_scope("esi-characters.read_loyalty.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-characters.read_loyalty.v1",
            "action": "Re-run OAuth setup to authorize LP access",
            "command": "uv run python .claude/scripts/aria-oauth-setup.py",
        }

    lp_data = await client.get_safe(f"/characters/{char_id}/loyalty/points/", auth=True)
    if not isinstance(lp_data, list) or not lp_data:
        return {
            "character_id": char_id,
            "total_lp": 0,
            "corporation_count": 0,
            "balances": [],
            "message": "No LP balances found. Run missions to earn loyalty points!",
        }

    pub_client = await get_async_esi_client()

    balances = []
    total_lp = 0

    for entry in lp_data:
        corp_id = entry.get("corporation_id")
        lp_amount = entry.get("loyalty_points", 0)
        if lp_amount <= 0:
            continue

        total_lp += lp_amount

        corp_name = "Unknown Corporation"
        info = await pub_client.get_safe(f"/corporations/{corp_id}/")
        if isinstance(info, dict) and "name" in info:
            corp_name = info["name"]

        balances.append(
            {
                "corporation_id": corp_id,
                "corporation_name": corp_name,
                "loyalty_points": lp_amount,
            }
        )

    balances.sort(key=lambda x: x["loyalty_points"], reverse=True)

    return wrap_output(
        {
            "character_id": char_id,
            "total_lp": total_lp,
            "corporation_count": len(balances),
            "balances": balances,
        },
        items_key="balances",
        max_items=50,
    )


async def _lp_offers(
    corporation_name: str | None,
    search: str | None,
    max_lp: int | None,
    affordable: bool,
) -> dict:
    """Browse LP store offers for a corporation."""
    if not corporation_name:
        raise InvalidParameterError(
            "corporation_name",
            corporation_name,
            "Required for action='lp_offers'. Example: 'Federation Navy'",
        )

    from aria_esi.store.esi_client import get_async_esi_client, get_authenticated_async_esi_client

    pub_client = await get_async_esi_client()

    # Resolve corporation
    corp_id, corp_name = await _resolve_corporation_async(pub_client, corporation_name)
    if not corp_id:
        return {
            "error": "corporation_not_found",
            "message": f"Could not find corporation: {corporation_name}",
            "hint": "Try a corporation ID or known name like 'Federation Navy'",
        }
    if not corp_name:
        corp_name = f"Corporation {corp_id}"

    # Fetch LP store offers (public endpoint)
    offers = await pub_client.get_safe(f"/loyalty/stores/{corp_id}/offers/")
    if not isinstance(offers, list) or not offers:
        return {
            "corporation_id": corp_id,
            "corporation_name": corp_name,
            "offer_count": 0,
            "offers": [],
            "message": "No LP store offers found for this corporation",
        }

    # Get current LP/ISK balance if checking affordability
    current_lp = None
    current_isk = None
    if affordable:
        try:
            auth_ctx = await get_authenticated_async_esi_client()
            auth_client = auth_ctx.client
            a_char_id = auth_ctx.character_id

            lp_data = await auth_client.get_safe(
                f"/characters/{a_char_id}/loyalty/points/", auth=True
            )
            if isinstance(lp_data, list):
                for entry in lp_data:
                    if entry.get("corporation_id") == corp_id:
                        current_lp = entry.get("loyalty_points", 0)
                        break

            isk_balance = await auth_client.get_safe(f"/characters/{a_char_id}/wallet/", auth=True)
            if isinstance(isk_balance, (int, float)):
                current_isk = isk_balance
        except Exception:  # noqa: BLE001
            affordable = False

    # Resolve type names via SDE
    type_ids: set[int] = set()
    for offer in offers:
        if offer.get("type_id"):
            type_ids.add(offer["type_id"])
        for req in offer.get("required_items", []):
            if req.get("type_id"):
                type_ids.add(req["type_id"])

    type_names = _resolve_type_ids_sync(type_ids)

    # Process offers
    processed_offers = []
    for offer in offers:
        type_id = offer.get("type_id")
        lp_cost = offer.get("lp_cost", 0)
        isk_cost = offer.get("isk_cost", 0)
        item_name = type_names.get(type_id, f"Unknown Item ({type_id})")

        # Apply search filter
        if search and search.lower() not in item_name.lower():
            continue

        # Apply LP cost filter
        if max_lp is not None and lp_cost > max_lp:
            continue

        # Apply affordability filter
        if affordable:
            if current_lp is not None and lp_cost > current_lp:
                continue
            if current_isk is not None and isk_cost > current_isk:
                continue

        # Process required items
        required = []
        for req in offer.get("required_items", []):
            req_type_id = req.get("type_id")
            req_name = type_names.get(req_type_id, f"Unknown ({req_type_id})")
            required.append(
                {
                    "type_id": req_type_id,
                    "name": req_name,
                    "quantity": req.get("quantity", 1),
                }
            )

        processed_offer: dict[str, Any] = {
            "offer_id": offer.get("offer_id"),
            "type_id": type_id,
            "name": item_name,
            "quantity": offer.get("quantity", 1),
            "lp_cost": lp_cost,
            "isk_cost": isk_cost,
        }

        ak_cost = offer.get("ak_cost", 0)
        if ak_cost > 0:
            processed_offer["ak_cost"] = ak_cost

        if required:
            processed_offer["required_items"] = required

        if lp_cost > 0:
            processed_offer["isk_per_lp"] = round(isk_cost / lp_cost, 2)

        processed_offers.append(processed_offer)

    processed_offers.sort(key=lambda x: x["lp_cost"])

    result: dict[str, Any] = {
        "corporation_id": corp_id,
        "corporation_name": corp_name,
        "total_offers": len(offers),
        "filtered_count": len(processed_offers),
        "offers": processed_offers,
        "filters_applied": {
            "search": search,
            "max_lp": max_lp,
            "affordable_only": affordable,
        },
    }

    if affordable and current_lp is not None:
        result["current_lp"] = current_lp
        result["current_isk"] = current_isk

    return wrap_output(result, items_key="offers", max_items=50)
