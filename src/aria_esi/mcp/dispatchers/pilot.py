"""
Pilot Dispatcher for MCP Server.

Provides authenticated ESI access for character-specific data:
- mail_list: List mail headers
- mail_read: Read a specific mail body
- mining_ledger: View mining extraction history
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from ..context import log_context, wrap_output
from ..errors import InvalidParameterError
from ..policy import check_capability

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


PilotAction = Literal["mail_list", "mail_read", "mining_ledger"]

VALID_ACTIONS: set[str] = {"mail_list", "mail_read", "mining_ledger"}


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
    ) -> dict:
        """
        Unified pilot data interface for authenticated ESI endpoints.

        Actions:
        - mail_list: List mail headers with optional unread filter
        - mail_read: Read a specific mail body
        - mining_ledger: View mining extraction history

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

        Returns:
            For mail_list:
            - mail: List of mail headers with sender, subject, timestamp
            - summary: {total_shown, unread_count}

            For mail_read:
            - mail: {mail_id, from_name, subject, body, timestamp, recipients}

            For mining_ledger:
            - entries: List of mining entries with ore name, quantity, system
            - summary: {total_entries, total_quantity, unique_ores, unique_systems}

        Examples:
            pilot(action="mail_list", unread_only=True)
            pilot(action="mail_read", mail_id=12345)
            pilot(action="mining_ledger", days=7, ore_filter="Veldspar")
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
    from ..esi_client import get_authenticated_async_esi_client

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

    from ..esi_client import get_authenticated_async_esi_client

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
    from ..esi_client import get_async_esi_client, get_authenticated_async_esi_client

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
