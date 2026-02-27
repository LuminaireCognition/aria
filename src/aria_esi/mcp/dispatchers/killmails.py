"""
Killmails Dispatcher for MCP Server.

Provides query and statistics access to the killmail store:
- query: Query killmails with filters
- stats: Get killmail statistics
- recent: Get most recent killmails
- analyze: Analyze individual killmail from zKillboard URL or kill ID
"""

from __future__ import annotations

import base64
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from ..context import log_context, wrap_output
from ..policy import check_capability

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


KillmailsAction = Literal["query", "stats", "recent", "analyze"]

VALID_ACTIONS: set[str] = {"query", "stats", "recent", "analyze"}


def _encode_cursor(kill_time: int, kill_id: int) -> str:
    """Encode pagination cursor."""
    data = json.dumps({"t": kill_time, "k": kill_id})
    return base64.urlsafe_b64encode(data.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[int, int] | None:
    """Decode pagination cursor."""
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return (data["t"], data["k"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _get_store():
    """Get the killmail store singleton."""
    from ...core.config import get_settings
    from ...services.killmail_store import SQLiteKillmailStore

    store_path = get_settings().killmail_db_path
    if not store_path.exists():
        return None
    return SQLiteKillmailStore(db_path=store_path, read_only=True)


def register_killmails_dispatcher(server: FastMCP) -> None:
    """
    Register the killmails dispatcher with MCP server.

    Args:
        server: MCP Server instance
    """

    @server.tool()
    @log_context("killmails")
    async def killmails(
        action: str,
        # query/recent params
        systems: list[str] | None = None,
        hours: int = 1,
        min_value: int | None = None,
        limit: int = 50,
        cursor: str | None = None,
        # stats params
        group_by: str | None = None,  # "system", "hour", "corporation"
        # analyze params
        killmail_input: str | None = None,
    ) -> dict:
        """
        Unified killmail query interface.

        Actions:
        - query: Query killmails with filters
        - stats: Get killmail statistics
        - recent: Get most recent killmails (shorthand for query with defaults)
        - analyze: Analyze individual killmail from zKillboard URL or kill ID

        Args:
            action: The operation to perform (see Actions above)

            Query params (action="query" or "recent"):
                systems: List of system names to filter by
                hours: Time window in hours (default 1, max 168/7 days)
                min_value: Minimum ISK value filter
                limit: Max results (default 50, max 100)
                cursor: Pagination cursor from previous response

            Stats params (action="stats"):
                systems: List of systems to include
                hours: Time window in hours
                group_by: Grouping mode - "system", "hour", or "corporation"

            Analyze params (action="analyze"):
                killmail_input: zKillboard URL, short URL, or raw kill ID
                    Examples: "https://zkillboard.com/kill/12345678/", "12345678"

        Returns:
            For query/recent:
            - kills: List of killmail records
            - count: Number of results
            - next_cursor: Cursor for pagination (null if no more results)
            - query: Echo of query parameters

            For stats:
            - total_kills: Total killmails in window
            - total_value: Total ISK destroyed
            - groups: Breakdown by group_by field
            - time_window: Query time window

            For analyze:
            - killmail_id, killmail_time, zkillboard_url
            - system: {id, name, security}
            - victim: {character, corporation, ship, damage}
            - attackers: {count, primary_group, ships, final_blow}
            - total_value, total_value_formatted

        Examples:
            killmails(action="query", systems=["Jita"], hours=1)
            killmails(action="recent", limit=10)
            killmails(action="stats", systems=["Uedama", "Niarja"], group_by="system")
            killmails(action="analyze", killmail_input="https://zkillboard.com/kill/12345678/")
        """
        # Policy check
        check_capability("killmails", action)

        if action not in VALID_ACTIONS:
            return {"error": f"Invalid action: {action}", "valid_actions": list(VALID_ACTIONS)}

        # Analyze action doesn't need the killmail store
        if action == "analyze":
            return await _handle_analyze(killmail_input)

        # Get store
        store = _get_store()
        if store is None:
            return {
                "error": "Killmail store not initialized",
                "hint": "Run the RedisQ poller to start collecting killmails",
            }

        try:
            await store.initialize()

            if action == "query" or action == "recent":
                return await _handle_query(
                    store=store,
                    systems=systems,
                    hours=hours,
                    min_value=min_value,
                    limit=limit,
                    cursor=cursor,
                )
            elif action == "stats":
                return await _handle_stats(
                    store=store,
                    systems=systems,
                    hours=hours,
                    group_by=group_by,
                )
            else:
                return {"error": f"Unknown action: {action}"}

        except Exception as e:
            logger.exception("Killmails dispatcher error")
            return {"error": str(e)}
        finally:
            await store.close()


async def _handle_query(
    store,
    systems: list[str] | None,
    hours: int,
    min_value: int | None,
    limit: int,
    cursor: str | None,
) -> dict:
    """Handle query/recent action."""
    # Resolve system names to IDs
    system_ids = None
    if systems:
        system_ids = await _resolve_systems(systems)
        if not system_ids:
            return {
                "error": "No valid systems found",
                "systems_requested": systems,
            }

    # Parse cursor
    cursor_tuple = None
    if cursor:
        cursor_tuple = _decode_cursor(cursor)
        if cursor_tuple is None:
            return {"error": "Invalid cursor format"}

    # Validate and clamp parameters
    hours = min(max(1, hours), 168)  # 1 hour to 7 days
    limit = min(max(1, limit), 100)

    # Calculate time window
    since = datetime.now(UTC) - timedelta(hours=hours)

    # Query store
    kills = await store.query_kills(
        systems=system_ids,
        since=since,
        min_value=min_value,
        limit=limit + 1,  # Fetch one extra to detect more results
        cursor=cursor_tuple,
    )

    # Check for more results
    has_more = len(kills) > limit
    if has_more:
        kills = kills[:limit]

    # Build next cursor
    next_cursor = None
    if has_more and kills:
        last = kills[-1]
        next_cursor = _encode_cursor(last.kill_time, last.kill_id)

    # Format results
    formatted_kills = [
        {
            "kill_id": k.kill_id,
            "kill_time": datetime.fromtimestamp(k.kill_time, tz=UTC).isoformat(),
            "system_id": k.solar_system_id,
            "value": k.zkb_total_value,
            "victim_ship_type_id": k.victim_ship_type_id,
            "victim_corporation_id": k.victim_corporation_id,
            "is_npc": k.zkb_is_npc,
            "is_solo": k.zkb_is_solo,
        }
        for k in kills
    ]

    return wrap_output(
        {
            "kills": formatted_kills,
            "count": len(formatted_kills),
            "next_cursor": next_cursor,
            "query": {
                "systems": systems,
                "hours": hours,
                "min_value": min_value,
                "limit": limit,
            },
        },
        items_key="kills",
        max_items=100,
    )


async def _handle_stats(
    store,
    systems: list[str] | None,
    hours: int,
    group_by: str | None,
) -> dict:
    """Handle stats action."""
    # Resolve system names to IDs
    system_ids = None
    if systems:
        system_ids = await _resolve_systems(systems)

    # Validate parameters
    hours = min(max(1, hours), 168)
    since = datetime.now(UTC) - timedelta(hours=hours)

    # Query all kills in window
    kills = await store.query_kills(
        systems=system_ids,
        since=since,
        limit=10000,  # Higher limit for stats
    )

    # Calculate aggregates
    total_kills = len(kills)
    total_value = sum(k.zkb_total_value or 0 for k in kills)

    # Group by
    groups = {}
    if group_by == "system":
        for k in kills:
            sid = k.solar_system_id
            if sid not in groups:
                groups[sid] = {"count": 0, "value": 0}
            groups[sid]["count"] += 1
            groups[sid]["value"] += k.zkb_total_value or 0
    elif group_by == "hour":
        for k in kills:
            hour = datetime.fromtimestamp(k.kill_time, tz=UTC).strftime("%Y-%m-%d %H:00")
            if hour not in groups:
                groups[hour] = {"count": 0, "value": 0}
            groups[hour]["count"] += 1
            groups[hour]["value"] += k.zkb_total_value or 0
    elif group_by == "corporation":
        for k in kills:
            cid = k.victim_corporation_id or 0
            if cid not in groups:
                groups[cid] = {"count": 0, "value": 0}
            groups[cid]["count"] += 1
            groups[cid]["value"] += k.zkb_total_value or 0

    return {
        "total_kills": total_kills,
        "total_value": total_value,
        "groups": groups if group_by else None,
        "time_window": {
            "hours": hours,
            "since": since.isoformat(),
        },
        "systems_queried": systems,
    }


async def _resolve_systems(system_names: list[str]) -> list[int] | None:
    """Resolve system names to IDs using universe graph."""
    try:
        from ..universe import get_universe

        graph = get_universe()
        if graph is None:
            return None

        system_ids = []
        for name in system_names:
            system = graph.get_system_by_name(name)
            if system:
                system_ids.append(system.system_id)

        return system_ids if system_ids else None
    except (ImportError, RuntimeError) as e:
        logger.warning("Failed to resolve system names: %s", e)
        return None


# =============================================================================
# Analyze Action
# =============================================================================


def _parse_killmail_input(input_str: str) -> int | None:
    """Extract kill ID from URL or raw ID string."""
    input_str = input_str.strip()
    if input_str.isdigit():
        return int(input_str)
    match = re.search(r"kill/(\d+)", input_str)
    if match:
        return int(match.group(1))
    return None


def _format_isk(value: float) -> str:
    """Format ISK value in human-readable format."""
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B ISK"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M ISK"
    elif value >= 1_000:
        return f"{value / 1_000:.1f}K ISK"
    else:
        return f"{value:.0f} ISK"


async def _handle_analyze(killmail_input: str | None) -> dict:
    """Analyze an individual killmail from zKillboard URL or kill ID."""
    if not killmail_input:
        return {
            "error": "missing_parameter",
            "message": "killmail_input is required for action='analyze'",
            "hint": "Use a zKillboard URL or numeric kill ID",
            "examples": [
                "https://zkillboard.com/kill/12345678/",
                "12345678",
            ],
        }

    kill_id = _parse_killmail_input(killmail_input)
    if not kill_id:
        return {
            "error": "invalid_input",
            "message": f"Could not parse kill ID from: {killmail_input}",
            "hint": "Use a zKillboard URL or numeric kill ID",
        }

    import httpx

    from aria_esi.store.esi_client import get_async_esi_client

    # Fetch from zKillboard API
    zkb_data = None
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"https://zkillboard.com/api/killID/{kill_id}/",
                headers={
                    "User-Agent": "ARIA-ESI/1.0 (EVE Online Assistant)",
                    "Accept": "application/json",
                },
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    zkb_data = data[0]
    except (httpx.RequestError, httpx.TimeoutException) as e:
        logger.warning("Failed to fetch from zKillboard: %s", e)

    if not zkb_data:
        return {
            "error": "kill_not_found",
            "message": f"Kill {kill_id} not found on zKillboard",
            "hints": [
                "Invalid kill ID",
                "Kill hasn't synced yet (wait a few minutes)",
            ],
        }

    zkb_meta = zkb_data.get("zkb", {})
    kill_hash = zkb_meta.get("hash", "")
    if not kill_hash:
        return {
            "error": "missing_hash",
            "message": f"Kill {kill_id} has no hash in zKillboard response",
        }

    # Fetch full killmail from ESI (public endpoint, no auth)
    esi_client = await get_async_esi_client()
    esi_data = await esi_client.get_safe(f"/killmails/{kill_id}/{kill_hash}/")

    if not esi_data or not isinstance(esi_data, dict):
        return {
            "error": "esi_fetch_failed",
            "message": f"Could not fetch killmail {kill_id} from ESI",
            "zkb_url": f"https://zkillboard.com/kill/{kill_id}/",
        }

    # Extract data
    victim = esi_data.get("victim", {})
    attackers = esi_data.get("attackers", [])
    system_id = esi_data.get("solar_system_id")
    kill_time = esi_data.get("killmail_time")

    # Collect IDs for name resolution
    type_ids: set[int] = set()
    char_ids: set[int] = set()
    corp_ids: set[int] = set()
    alliance_ids: set[int] = set()

    if victim.get("ship_type_id"):
        type_ids.add(victim["ship_type_id"])
    if victim.get("character_id"):
        char_ids.add(victim["character_id"])
    if victim.get("corporation_id"):
        corp_ids.add(victim["corporation_id"])
    if victim.get("alliance_id"):
        alliance_ids.add(victim["alliance_id"])

    for attacker in attackers:
        if attacker.get("ship_type_id"):
            type_ids.add(attacker["ship_type_id"])
        if attacker.get("weapon_type_id"):
            type_ids.add(attacker["weapon_type_id"])
        if attacker.get("character_id"):
            char_ids.add(attacker["character_id"])
        if attacker.get("corporation_id"):
            corp_ids.add(attacker["corporation_id"])
        if attacker.get("alliance_id"):
            alliance_ids.add(attacker["alliance_id"])

    # Resolve names via ESI
    names = await _resolve_names_async(esi_client, type_ids, char_ids, corp_ids, alliance_ids)

    # Get system info
    system_name = None
    system_security = None
    if system_id:
        sys_info = await esi_client.get_safe(f"/universe/systems/{system_id}/")
        if isinstance(sys_info, dict):
            system_name = sys_info.get("name")
            system_security = sys_info.get("security_status")

    # Analyze attackers
    attacker_analysis = _analyze_attackers(attackers, names)

    # Build victim info
    victim_char_id = victim.get("character_id")
    victim_corp_id = victim.get("corporation_id")
    victim_alliance_id = victim.get("alliance_id")
    victim_ship_id = victim.get("ship_type_id")
    victim_info = {
        "character_id": victim_char_id,
        "character_name": names["characters"].get(victim_char_id, "Unknown")
        if victim_char_id
        else "Unknown",
        "corporation_id": victim_corp_id,
        "corporation_name": names["corporations"].get(victim_corp_id, "Unknown")
        if victim_corp_id
        else "Unknown",
        "alliance_id": victim_alliance_id,
        "alliance_name": names["alliances"].get(victim_alliance_id) if victim_alliance_id else None,
        "ship_type_id": victim_ship_id,
        "ship_name": names["types"].get(victim_ship_id, "Unknown") if victim_ship_id else "Unknown",
        "damage_taken": victim.get("damage_taken", 0),
    }

    total_value = zkb_meta.get("totalValue", 0)

    return {
        "killmail_id": kill_id,
        "killmail_time": kill_time,
        "zkillboard_url": f"https://zkillboard.com/kill/{kill_id}/",
        "system": {
            "id": system_id,
            "name": system_name or f"System {system_id}",
            "security": round(float(system_security), 2) if system_security is not None else None,
        },
        "victim": victim_info,
        "total_value": total_value,
        "total_value_formatted": _format_isk(total_value),
        "is_npc_kill": zkb_meta.get("npc", False),
        "attackers": attacker_analysis,
    }


async def _resolve_names_async(
    client: Any,
    type_ids: set[int],
    char_ids: set[int],
    corp_ids: set[int],
    alliance_ids: set[int],
) -> dict[str, dict[int, str]]:
    """Resolve IDs to names via async ESI client."""
    result: dict[str, dict[int, str]] = {
        "types": {},
        "characters": {},
        "corporations": {},
        "alliances": {},
    }

    for tid in list(type_ids)[:100]:
        if tid:
            info = await client.get_safe(f"/universe/types/{tid}/")
            if isinstance(info, dict):
                result["types"][tid] = info.get("name", f"Unknown ({tid})")

    for cid in list(char_ids)[:50]:
        if cid:
            info = await client.get_safe(f"/characters/{cid}/")
            if isinstance(info, dict):
                result["characters"][cid] = info.get("name", f"Unknown ({cid})")

    for cid in list(corp_ids)[:50]:
        if cid:
            info = await client.get_safe(f"/corporations/{cid}/")
            if isinstance(info, dict):
                result["corporations"][cid] = info.get("name", f"Unknown ({cid})")

    for aid in list(alliance_ids)[:20]:
        if aid:
            info = await client.get_safe(f"/alliances/{aid}/")
            if isinstance(info, dict):
                result["alliances"][aid] = info.get("name", f"Unknown ({aid})")

    return result


def _analyze_attackers(attackers: list[dict], names: dict[str, dict[int, str]]) -> dict[str, Any]:
    """Analyze attacker composition."""
    corps: dict[int, int] = {}
    alliances: dict[int, int] = {}
    ships: dict[str, int] = {}
    final_blow: dict[str, Any] | None = None

    for attacker in attackers:
        corp_id = attacker.get("corporation_id")
        if corp_id:
            corps[corp_id] = corps.get(corp_id, 0) + 1

        alliance_id = attacker.get("alliance_id")
        if alliance_id:
            alliances[alliance_id] = alliances.get(alliance_id, 0) + 1

        ship_id = attacker.get("ship_type_id")
        if ship_id:
            ship_name = names["types"].get(ship_id, f"Unknown ({ship_id})")
            ships[ship_name] = ships.get(ship_name, 0) + 1

        if attacker.get("final_blow"):
            char_id = attacker.get("character_id")
            final_blow = {
                "character_id": char_id,
                "character_name": names["characters"].get(char_id, "Unknown")
                if char_id
                else "Unknown",
                "ship": names["types"].get(ship_id, "Unknown") if ship_id else "Unknown",
                "damage_done": attacker.get("damage_done", 0),
            }

    primary_corp = max(corps.items(), key=lambda x: x[1])[0] if corps else None
    primary_alliance = max(alliances.items(), key=lambda x: x[1])[0] if alliances else None

    primary_group = None
    primary_group_count = 0
    if primary_alliance:
        primary_group = names["alliances"].get(primary_alliance, f"Alliance {primary_alliance}")
        primary_group_count = alliances[primary_alliance]
    elif primary_corp:
        primary_group = names["corporations"].get(primary_corp, f"Corp {primary_corp}")
        primary_group_count = corps[primary_corp]

    return {
        "count": len(attackers),
        "primary_group": primary_group,
        "primary_group_count": primary_group_count,
        "ships": dict(sorted(ships.items(), key=lambda x: x[1], reverse=True)[:10]),
        "final_blow": final_blow,
    }
