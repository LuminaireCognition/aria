"""
Killmails Dispatcher for MCP Server.

Provides query and statistics access to the killmail store:
- query: Query killmails with filters (auto-falls back to ESI when store unavailable)
- stats: Get killmail statistics
- recent: Get most recent killmails (auto-falls back to ESI when store unavailable)
- analyze: Analyze individual killmail from zKillboard URL or kill ID
- esi_history: Fetch killmail history directly from authenticated ESI (no time cap)
"""

from __future__ import annotations

import asyncio
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


KillmailsAction = Literal["query", "stats", "recent", "analyze", "esi_history"]

VALID_ACTIONS: set[str] = {"query", "stats", "recent", "analyze", "esi_history"}


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


async def _resolve_character_id() -> int | None:
    """Resolve character_id from ESI credentials. Returns None if unavailable."""
    try:
        from ...store.esi_client import get_authenticated_async_esi_client

        auth_ctx = await get_authenticated_async_esi_client()
        return auth_ctx.character_id
    except (RuntimeError, ImportError):
        return None


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
        character_id: int | None = None,
        # stats params
        group_by: str | None = None,  # "system", "hour", "corporation"
        # analyze params
        killmail_input: str | None = None,
    ) -> dict:
        """
        Unified killmail query interface.

        Actions:
        - query: Query killmails with filters (auto-falls back to ESI if store unavailable)
        - stats: Get killmail statistics (requires store)
        - recent: Get most recent killmails (auto-falls back to ESI if store unavailable)
        - analyze: Analyze individual killmail from zKillboard URL or kill ID
        - esi_history: Fetch killmail history from authenticated ESI (no 7-day cap)

        Args:
            action: The operation to perform (see Actions above)

            Query params (action="query" or "recent"):
                systems: List of system names to filter by
                hours: Time window in hours (default 1, max 168/7 days)
                min_value: Minimum ISK value filter
                limit: Max results (default 50, max 100)
                cursor: Pagination cursor from previous response
                character_id: Filter to kills involving this character (as victim)

            Stats params (action="stats"):
                systems: List of systems to include
                hours: Time window in hours
                group_by: Grouping mode - "system", "hour", or "corporation"
                character_id: Filter to kills involving this character (as victim)

            Analyze params (action="analyze"):
                killmail_input: zKillboard URL, short URL, or raw kill ID
                    Examples: "https://zkillboard.com/kill/12345678/", "12345678"

            ESI history params (action="esi_history"):
                hours: Time window in hours (no cap, default 168)
                limit: Max results (default 50, max 100)
                cursor: Pagination cursor (before_kill_id) from previous response

        Returns:
            For query/recent:
            - kills: List of killmail records
            - count: Number of results
            - next_cursor: Cursor for pagination (null if no more results)
            - query: Echo of query parameters
            - source: "store", "esi_fallback" (when store unavailable)

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

            For esi_history:
            - kills: List of enriched killmail records (value=null, no zkb metadata)
            - count: Number of results
            - next_cursor: Cursor for next page (null if no more)
            - query: Echo of query parameters
            - source: "esi_direct"

        Examples:
            killmails(action="query", systems=["Jita"], hours=1)
            killmails(action="recent", limit=10)
            killmails(action="stats", systems=["Uedama", "Niarja"], group_by="system")
            killmails(action="analyze", killmail_input="https://zkillboard.com/kill/12345678/")
            killmails(action="esi_history", hours=2160, limit=50)
        """
        # Policy check
        check_capability("killmails", action)

        if action not in VALID_ACTIONS:
            return {"error": f"Invalid action: {action}", "valid_actions": list(VALID_ACTIONS)}

        # Actions that don't need the killmail store
        if action == "analyze":
            return await _handle_analyze(killmail_input)

        if action == "esi_history":
            return await _handle_esi_history(
                hours=hours,
                limit=limit,
                cursor=cursor,
            )

        # Auto-resolve character_id from ESI credentials for query/recent
        if action in ("query", "recent") and character_id is None:
            character_id = await _resolve_character_id()

        # Get store
        store = _get_store()
        if store is None:
            # Fallback to ESI for query/recent when store is unavailable
            if action in ("query", "recent"):
                return await _handle_esi_fallback(
                    hours=hours,
                    limit=limit,
                    character_id=character_id,
                )
            return {
                "error": "Killmail store not initialized",
                "hint": "Run the RedisQ poller to start collecting killmails. "
                "For kill history without the store, use action='esi_history'.",
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
                    character_id=character_id,
                )
            elif action == "stats":
                return await _handle_stats(
                    store=store,
                    systems=systems,
                    hours=hours,
                    group_by=group_by,
                    character_id=character_id,
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
    character_id: int | None = None,
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
        character_id=character_id,
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

    # Batch-fetch ESI details for enrichment (graceful degradation)
    esi_details: dict = {}
    try:
        kill_ids = [k.kill_id for k in kills]
        if kill_ids:
            esi_details = await store.get_esi_details_batch(kill_ids)
    except Exception:  # noqa: BLE001 – graceful degradation, any failure is non-fatal
        logger.debug("ESI details batch fetch failed, using denormalized data")

    # Format results with ESI enrichment
    formatted_kills = []
    for k in kills:
        esi = esi_details.get(k.kill_id)
        entry: dict[str, Any] = {
            "kill_id": k.kill_id,
            "kill_time": datetime.fromtimestamp(k.kill_time, tz=UTC).isoformat(),
            "system_id": k.solar_system_id if k.solar_system_id != 0 else None,
            "value": k.zkb_total_value,
            "victim_ship_type_id": (
                esi.victim_ship_type_id
                if esi and esi.victim_ship_type_id
                else k.victim_ship_type_id
            ),
            "victim_corporation_id": (
                esi.victim_corporation_id
                if esi and esi.victim_corporation_id
                else k.victim_corporation_id
            ),
            "is_npc": k.zkb_is_npc,
            "is_solo": k.zkb_is_solo,
            "has_esi_details": esi is not None,
        }
        if esi:
            entry["victim_character_id"] = esi.victim_character_id
            entry["victim_damage_taken"] = esi.victim_damage_taken
            entry["attacker_count"] = esi.attacker_count
        formatted_kills.append(entry)

    scope = "character" if character_id else "global"
    result_dict: dict[str, Any] = {
        "kills": formatted_kills,
        "count": len(formatted_kills),
        "next_cursor": next_cursor,
        "query": {
            "systems": systems,
            "hours": hours,
            "min_value": min_value,
            "limit": limit,
        },
        "scope": scope,
    }
    if scope == "global":
        result_dict["scope_note"] = (
            "No ESI credentials available — showing global killmail feed. "
            "Authenticate with ESI to auto-scope to your character."
        )

    return wrap_output(
        result_dict,
        items_key="kills",
        max_items=100,
    )


async def _handle_stats(
    store,
    systems: list[str] | None,
    hours: int,
    group_by: str | None,
    character_id: int | None = None,
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
        character_id=character_id,
    )

    # Calculate aggregates
    total_kills = len(kills)
    total_value = sum(k.zkb_total_value or 0 for k in kills)

    # Group by
    groups = {}
    if group_by == "system":
        for k in kills:
            sid = k.solar_system_id or None  # 0 sentinel → None for "unknown"
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
# ESI Direct / Fallback Actions
# =============================================================================

_KILLMAIL_SCOPE = "esi-killmails.read_killmails.v1"


async def _fetch_esi_killmail_refs(
    before_kill_id: int | None = None,
) -> tuple[list[dict[str, Any]], int, str | None]:
    """
    Fetch killmail refs from authenticated ESI.

    Returns:
        (refs_list, character_id, error_or_none)
        Each ref has {killmail_id, killmail_hash}.
    """
    from aria_esi.store.esi_client import get_authenticated_async_esi_client

    try:
        auth_ctx = await get_authenticated_async_esi_client()
    except RuntimeError as e:
        return [], 0, f"No ESI credentials: {e}"

    if not auth_ctx.creds.has_scope(_KILLMAIL_SCOPE):
        return (
            [],
            auth_ctx.character_id,
            (
                f"scope_not_authorized: Missing {_KILLMAIL_SCOPE}. "
                "Run 'uv run aria-esi setup' to authorize."
            ),
        )

    char_id = auth_ctx.character_id
    client = auth_ctx.client

    params: dict[str, Any] = {}
    if before_kill_id is not None:
        params["before_kill_id"] = before_kill_id

    data = await client.get_safe(
        f"/characters/{char_id}/killmails/recent/",
        params=params if params else None,
        auth=True,
    )

    if not isinstance(data, list):
        return [], char_id, "ESI returned unexpected response for killmail refs"

    refs = [
        {"killmail_id": r["killmail_id"], "killmail_hash": r["killmail_hash"]}
        for r in data
        if isinstance(r, dict) and "killmail_id" in r and "killmail_hash" in r
    ]

    return refs, char_id, None


async def _enrich_killmail_refs(
    refs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """
    Enrich killmail refs by fetching full data from public ESI.

    Returns:
        (enriched_kills, enrichment_error_count)
    """
    from aria_esi.store.esi_client import get_async_esi_client

    esi_client = await get_async_esi_client()
    sem = asyncio.Semaphore(10)

    async def fetch_one(ref: dict[str, Any]) -> dict[str, Any] | None:
        async with sem:
            kill_id = ref["killmail_id"]
            kill_hash = ref["killmail_hash"]
            data = await esi_client.get_safe(f"/killmails/{kill_id}/{kill_hash}/")
            if not isinstance(data, dict):
                return None
            victim = data.get("victim", {})
            attackers = data.get("attackers", [])
            kill_time_str = data.get("killmail_time")
            return {
                "kill_id": kill_id,
                "kill_time": kill_time_str,
                "system_id": data.get("solar_system_id"),
                "value": None,  # zkb metadata unavailable via ESI
                "victim_ship_type_id": victim.get("ship_type_id"),
                "victim_character_id": victim.get("character_id"),
                "victim_corporation_id": victim.get("corporation_id"),
                "victim_damage_taken": victim.get("damage_taken"),
                "attacker_count": len(attackers),
                "is_npc": None,
                "is_solo": None,
                "has_esi_details": True,
            }

    tasks = [fetch_one(ref) for ref in refs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    enriched = []
    errors = 0
    for r in results:
        if isinstance(r, dict):
            enriched.append(r)
        else:
            errors += 1

    return enriched, errors


async def _handle_esi_history(
    hours: int,
    limit: int,
    cursor: str | None,
) -> dict:
    """Handle esi_history action — fetch kill history directly from ESI."""
    # No hour clamping for esi_history (the whole point)
    hours = max(1, hours)
    limit = min(max(1, limit), 100)

    # Decode cursor as before_kill_id
    before_kill_id = None
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded is None:
            return {"error": "Invalid cursor format"}
        # Use kill_id from cursor as before_kill_id
        before_kill_id = decoded[1]

    refs, char_id, error = await _fetch_esi_killmail_refs(before_kill_id)
    if error:
        return {"error": error}

    if not refs:
        return wrap_output(
            {
                "kills": [],
                "count": 0,
                "next_cursor": None,
                "query": {"hours": hours, "limit": limit, "source": "esi_direct"},
                "source": "esi_direct",
                "scope": "character",
            },
            items_key="kills",
            max_items=100,
        )

    # Enrich refs
    enriched, enrichment_errors = await _enrich_killmail_refs(refs)

    # Filter by time window if hours specified
    since = datetime.now(UTC) - timedelta(hours=hours)
    filtered = []
    for kill in enriched:
        if kill["kill_time"]:
            try:
                kt = datetime.fromisoformat(kill["kill_time"].replace("Z", "+00:00"))
                if kt >= since:
                    filtered.append(kill)
            except (ValueError, AttributeError):
                filtered.append(kill)  # Keep if we can't parse
        else:
            filtered.append(kill)

    # Apply limit
    has_more = len(filtered) > limit
    filtered = filtered[:limit]

    # Build next cursor from last ref (not last filtered kill) for pagination
    next_cursor = None
    if has_more or len(refs) >= 50:  # ESI returns up to 50 per page
        last_ref = refs[-1]
        next_cursor = _encode_cursor(0, last_ref["killmail_id"])

    result: dict[str, Any] = {
        "kills": filtered,
        "count": len(filtered),
        "next_cursor": next_cursor,
        "query": {"hours": hours, "limit": limit, "source": "esi_direct"},
        "source": "esi_direct",
        "scope": "character",
    }
    if enrichment_errors > 0:
        result["enrichment_errors"] = enrichment_errors

    return wrap_output(result, items_key="kills", max_items=100)


async def _handle_esi_fallback(
    hours: int,
    limit: int,
    character_id: int | None = None,
) -> dict:
    """Fallback for query/recent when store is unavailable."""
    # Keep the same clamping as store-based queries for consistency
    hours = min(max(1, hours), 168)
    limit = min(max(1, limit), 100)

    refs, char_id, error = await _fetch_esi_killmail_refs()
    if error:
        return {"error": error}

    # Compute scope note for mismatched character_id
    scope_note = None
    if character_id and char_id and character_id != char_id:
        scope_note = (
            f"Requested character_id={character_id} differs from authenticated "
            f"character ({char_id}). ESI fallback returns data for the "
            f"authenticated character only."
        )

    if not refs:
        empty_result: dict[str, Any] = {
            "kills": [],
            "count": 0,
            "next_cursor": None,
            "query": {"hours": hours, "limit": limit, "source": "esi_fallback"},
            "source": "esi_fallback",
            "scope": "character",
        }
        if scope_note:
            empty_result["scope_note"] = scope_note
        return wrap_output(
            empty_result,
            items_key="kills",
            max_items=100,
        )

    enriched, enrichment_errors = await _enrich_killmail_refs(refs)

    # Filter by time window
    since = datetime.now(UTC) - timedelta(hours=hours)
    filtered = []
    for kill in enriched:
        if kill["kill_time"]:
            try:
                kt = datetime.fromisoformat(kill["kill_time"].replace("Z", "+00:00"))
                if kt >= since:
                    filtered.append(kill)
            except (ValueError, AttributeError):
                filtered.append(kill)
        else:
            filtered.append(kill)

    filtered = filtered[:limit]

    result: dict[str, Any] = {
        "kills": filtered,
        "count": len(filtered),
        "next_cursor": None,
        "query": {
            "systems": None,
            "hours": hours,
            "min_value": None,
            "limit": limit,
        },
        "source": "esi_fallback",
        "scope": "character",
    }
    if scope_note:
        result["scope_note"] = scope_note
    if enrichment_errors > 0:
        result["enrichment_errors"] = enrichment_errors

    return wrap_output(result, items_key="kills", max_items=100)


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
