"""
ARIA Killmail Analysis Command

Analyze individual killmails from zKillboard URLs or kill IDs.
Provides enriched tactical context including gatecamp detection.

This is separate from killmails.py which handles personal kill/loss history.
"""

from __future__ import annotations

import argparse
import re
from typing import Any

import httpx

from ..core import ESIClient, get_utc_timestamp
from ..core.logging import get_logger

logger = get_logger(__name__)


def parse_killmail_input(input_str: str) -> int | None:
    """
    Extract kill ID from various input formats.

    Accepts:
    - Full URL: https://zkillboard.com/kill/12345678/
    - Short URL: zkillboard.com/kill/12345678
    - Raw ID: 12345678

    Args:
        input_str: User input string

    Returns:
        Kill ID as integer, or None if not parseable
    """
    input_str = input_str.strip()

    # Try raw ID first
    if input_str.isdigit():
        return int(input_str)

    # Try URL patterns
    match = re.search(r"kill/(\d+)", input_str)
    if match:
        return int(match.group(1))

    return None


def fetch_from_zkillboard(kill_id: int) -> dict[str, Any] | None:
    """
    Fetch killmail data from zKillboard API.

    Returns dict with:
    - killmail_id
    - hash
    - zkb metadata (value, points, npc flag)
    - Full killmail if available

    Args:
        kill_id: The kill ID to fetch

    Returns:
        Dict with killmail data, or None if not found
    """
    url = f"https://zkillboard.com/api/killID/{kill_id}/"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                url,
                headers={
                    "User-Agent": "ARIA-ESI/1.0 (EVE Online Assistant)",
                    "Accept": "application/json",
                },
            )

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
            elif response.status_code == 404:
                return None

    except (httpx.RequestError, httpx.TimeoutException) as e:
        logger.warning("Failed to fetch from zKillboard: %s", e)

    return None


def fetch_esi_killmail(client: ESIClient, kill_id: int, kill_hash: str) -> dict[str, Any] | None:
    """
    Fetch full killmail from ESI.

    Args:
        client: ESI client
        kill_id: Kill ID
        kill_hash: Kill hash from zKillboard

    Returns:
        Full killmail dict, or None if not found
    """
    try:
        result = client.get(f"/killmails/{kill_id}/{kill_hash}/")
        return result if isinstance(result, dict) else None
    except Exception as e:
        logger.warning("Failed to fetch killmail from ESI: %s", e)
        return None


def get_threat_context(system_id: int) -> dict[str, Any] | None:
    """
    Get gatecamp and activity context from threat cache.

    Args:
        system_id: Solar system ID

    Returns:
        Dict with gatecamp_status and activity_summary, or None
    """
    try:
        from ..services.redisq.threat_cache import get_threat_cache

        cache = get_threat_cache()
        gatecamp = cache.get_gatecamp_status(system_id)
        activity = cache.get_activity_summary(system_id)

        return {
            "gatecamp": gatecamp.to_dict() if gatecamp else None,
            "activity": {
                "kills_10m": activity.kills_10m,
                "kills_1h": activity.kills_1h,
                "pod_kills_10m": activity.pod_kills_10m,
                "pod_kills_1h": activity.pod_kills_1h,
            }
            if activity
            else None,
        }
    except Exception as e:
        logger.debug("Threat cache unavailable: %s", e)
        return None


def resolve_names(
    client: ESIClient,
    type_ids: set[int],
    char_ids: set[int],
    corp_ids: set[int],
    alliance_ids: set[int],
) -> dict[str, dict[int, str]]:
    """
    Resolve IDs to names via ESI.

    Returns:
        Dict with 'types', 'characters', 'corporations', 'alliances' name mappings
    """
    result: dict[str, dict[int, str]] = {
        "types": {},
        "characters": {},
        "corporations": {},
        "alliances": {},
    }

    # Resolve type names (ships, modules)
    for tid in list(type_ids)[:100]:
        if tid:
            info = client.get_safe(f"/universe/types/{tid}/")
            if info and isinstance(info, dict):
                result["types"][tid] = info.get("name", f"Unknown ({tid})")

    # Resolve character names
    for cid in list(char_ids)[:50]:
        if cid:
            info = client.get_safe(f"/characters/{cid}/")
            if info and isinstance(info, dict):
                result["characters"][cid] = info.get("name", f"Unknown ({cid})")

    # Resolve corporation names
    for cid in list(corp_ids)[:50]:
        if cid:
            info = client.get_safe(f"/corporations/{cid}/")
            if info and isinstance(info, dict):
                result["corporations"][cid] = info.get("name", f"Unknown ({cid})")

    # Resolve alliance names
    for aid in list(alliance_ids)[:20]:
        if aid:
            info = client.get_safe(f"/alliances/{aid}/")
            if info and isinstance(info, dict):
                result["alliances"][aid] = info.get("name", f"Unknown ({aid})")

    return result


def analyze_attackers(attackers: list[dict], names: dict[str, dict[int, str]]) -> dict[str, Any]:
    """
    Analyze attacker composition.

    Returns:
        Analysis dict with counts, ships, corps, primary group
    """
    corps: dict[int, int] = {}
    alliances: dict[int, int] = {}
    ships: dict[str, int] = {}
    final_blow: dict[str, Any] | None = None

    for attacker in attackers:
        # Count corporations
        corp_id = attacker.get("corporation_id")
        if corp_id:
            corps[corp_id] = corps.get(corp_id, 0) + 1

        # Count alliances
        alliance_id = attacker.get("alliance_id")
        if alliance_id:
            alliances[alliance_id] = alliances.get(alliance_id, 0) + 1

        # Count ships
        ship_id = attacker.get("ship_type_id")
        if ship_id:
            ship_name = names["types"].get(ship_id, f"Unknown ({ship_id})")
            ships[ship_name] = ships.get(ship_name, 0) + 1

        # Track final blow
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

    # Find primary group
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


def cmd_killmail_analyze(args: argparse.Namespace) -> dict[str, Any]:
    """
    Analyze a killmail from zKillboard URL or kill ID.

    Provides enriched analysis with:
    - Victim details and fitting type
    - Attacker composition
    - Gatecamp context from threat cache
    - System activity
    """
    query_ts = get_utc_timestamp()
    input_str = getattr(args, "killmail_input", "")

    # Parse input
    kill_id = parse_killmail_input(input_str)
    if not kill_id:
        return {
            "error": "invalid_input",
            "message": f"Could not parse kill ID from: {input_str}",
            "hint": "Use a zKillboard URL or numeric kill ID",
            "examples": [
                "https://zkillboard.com/kill/12345678/",
                "zkillboard.com/kill/12345678",
                "12345678",
            ],
            "query_timestamp": query_ts,
        }

    # Fetch from zKillboard
    zkb_data = fetch_from_zkillboard(kill_id)
    if not zkb_data:
        return {
            "error": "kill_not_found",
            "message": f"Kill {kill_id} not found on zKillboard",
            "hints": [
                "Invalid kill ID",
                "Kill hasn't synced yet (wait a few minutes)",
                "Kill may be very old (zKillboard prunes old data)",
            ],
            "query_timestamp": query_ts,
        }

    # Extract hash and zkb metadata
    zkb_meta = zkb_data.get("zkb", {})
    kill_hash = zkb_meta.get("hash", "")

    if not kill_hash:
        return {
            "error": "missing_hash",
            "message": f"Kill {kill_id} has no hash in zKillboard response",
            "query_timestamp": query_ts,
        }

    # Fetch full killmail from ESI
    esi_client = ESIClient()
    esi_data = fetch_esi_killmail(esi_client, kill_id, kill_hash)

    if not esi_data:
        return {
            "error": "esi_fetch_failed",
            "message": f"Could not fetch killmail {kill_id} from ESI",
            "zkb_url": f"https://zkillboard.com/kill/{kill_id}/",
            "query_timestamp": query_ts,
        }

    # Extract data
    victim = esi_data.get("victim", {})
    attackers = esi_data.get("attackers", [])
    system_id = esi_data.get("solar_system_id")
    kill_time = esi_data.get("killmail_time")

    # Collect IDs for resolution
    type_ids: set[int] = set()
    char_ids: set[int] = set()
    corp_ids: set[int] = set()
    alliance_ids: set[int] = set()

    # Victim IDs
    if victim.get("ship_type_id"):
        type_ids.add(victim["ship_type_id"])
    if victim.get("character_id"):
        char_ids.add(victim["character_id"])
    if victim.get("corporation_id"):
        corp_ids.add(victim["corporation_id"])
    if victim.get("alliance_id"):
        alliance_ids.add(victim["alliance_id"])

    # Attacker IDs
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

    # Resolve names
    names = resolve_names(esi_client, type_ids, char_ids, corp_ids, alliance_ids)

    # Get system info
    system_info = esi_client.get_safe(f"/universe/systems/{system_id}/") if system_id else None
    system_name = system_info.get("name") if isinstance(system_info, dict) else None
    system_security = system_info.get("security_status") if isinstance(system_info, dict) else None

    # Analyze attackers
    attacker_analysis = analyze_attackers(attackers, names)

    # Get threat context
    threat_context = get_threat_context(system_id) if system_id else None

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

    # Calculate ISK value
    total_value = zkb_meta.get("totalValue", 0)
    is_npc = zkb_meta.get("npc", False)

    return {
        "query_timestamp": query_ts,
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
        "is_npc_kill": is_npc,
        "attackers": attacker_analysis,
        "threat_context": threat_context,
    }


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


def cmd_test_webhook(args: argparse.Namespace) -> dict[str, Any]:
    """
    Test Discord webhook configuration.

    Sends a test message to verify webhook is working.

    DEPRECATED: Use 'notifications test <profile-name>' instead.
    This command uses the legacy config.json format.
    """
    import asyncio
    import sys

    # Print deprecation warning to stderr
    print(
        "DEPRECATED: 'test-webhook' uses legacy config.json format.",
        file=sys.stderr,
    )
    print(
        "Use 'uv run aria-esi notifications test <profile-name>' instead.",
        file=sys.stderr,
    )
    print(file=sys.stderr)

    query_ts = get_utc_timestamp()

    try:
        from ..services.redisq.notifications import get_notification_manager

        manager = get_notification_manager()

        if not manager or not manager.is_configured:
            return {
                "error": "not_configured",
                "message": "Discord webhook not configured",
                "hint": "Add discord_webhook_url to userdata/config.json under redisq.notifications",
                "query_timestamp": query_ts,
            }

        # Run async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success, message = loop.run_until_complete(manager.test_webhook())
        finally:
            loop.close()

        return {
            "success": success,
            "message": message,
            "query_timestamp": query_ts,
        }

    except Exception as e:
        return {
            "error": "test_failed",
            "message": str(e),
            "query_timestamp": query_ts,
        }


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register killmail analysis command parsers."""

    # Analyze killmail from URL/ID
    analyze_parser = subparsers.add_parser(
        "analyze-killmail",
        help="Analyze a killmail from zKillboard URL or ID",
        aliases=["akm"],
    )
    analyze_parser.add_argument(
        "killmail_input",
        help="zKillboard URL or kill ID (e.g., https://zkillboard.com/kill/12345678/ or 12345678)",
    )
    analyze_parser.set_defaults(func=cmd_killmail_analyze)

    # Test webhook
    test_webhook_parser = subparsers.add_parser(
        "test-webhook",
        help="Test Discord webhook configuration",
    )
    test_webhook_parser.set_defaults(func=cmd_test_webhook)
