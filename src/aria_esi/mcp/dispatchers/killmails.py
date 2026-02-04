"""
Killmails Dispatcher for MCP Server.

Provides query and statistics access to the killmail store:
- query: Query killmails with filters
- stats: Get killmail statistics
- recent: Get most recent killmails
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal

from ..context import log_context, wrap_output
from ..policy import check_capability

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


KillmailsAction = Literal["query", "stats", "recent"]

VALID_ACTIONS: set[str] = {"query", "stats", "recent"}


def _encode_cursor(kill_time: int, kill_id: int) -> str:
    """Encode pagination cursor."""
    data = json.dumps({"t": kill_time, "k": kill_id})
    return base64.urlsafe_b64encode(data.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[int, int] | None:
    """Decode pagination cursor."""
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return (data["t"], data["k"])
    except Exception:
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
    ) -> dict:
        """
        Unified killmail query interface.

        Actions:
        - query: Query killmails with filters
        - stats: Get killmail statistics
        - recent: Get most recent killmails (shorthand for query with defaults)

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

        Examples:
            killmails(action="query", systems=["Jita"], hours=1)
            killmails(action="recent", limit=10)
            killmails(action="stats", systems=["Uedama", "Niarja"], group_by="system")
        """
        # Policy check
        check_capability("killmails", action)

        if action not in VALID_ACTIONS:
            return {"error": f"Invalid action: {action}", "valid_actions": list(VALID_ACTIONS)}

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
    since = datetime.utcnow() - timedelta(hours=hours)

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
            "kill_time": datetime.fromtimestamp(k.kill_time).isoformat(),
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
    since = datetime.utcnow() - timedelta(hours=hours)

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
            hour = datetime.fromtimestamp(k.kill_time).strftime("%Y-%m-%d %H:00")
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
    except Exception as e:
        logger.warning("Failed to resolve system names: %s", e)
        return None
