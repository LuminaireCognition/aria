"""
ARIA ESI Killmail Commands

Kill and loss tracking for post-mortem analysis.
Learn from deaths to improve survivability.
"""

import argparse
import json
from pathlib import Path
from typing import Optional

from ..core import (
    CredentialsError,
    ESIClient,
    ESIError,
    get_authenticated_client,
    get_utc_timestamp,
)

# =============================================================================
# Damage Type Analysis
# =============================================================================


def _load_drone_damage_types() -> dict[str, list[str]]:
    """
    Load drone damage types from master reference file.

    Returns dict mapping drone name to list of damage types.
    Source: reference/mechanics/drones.json
    """
    # Navigate from src/aria_esi/commands/ to project root
    project_root = Path(__file__).parent.parent.parent.parent
    drone_data_path = project_root / "reference" / "mechanics" / "drones.json"

    try:
        with open(drone_data_path) as f:
            data = json.load(f)
        # Convert single damage type to list format for consistency
        return {name: [dtype] for name, dtype in data["damage_types"].items()}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # Fallback to empty dict if file not found - weapons still work
        return {}


# Weapon groups and their primary damage types
_WEAPON_DAMAGE_HINTS = {
    # Projectile weapons - usually explosive/kinetic
    "Autocannon": ["explosive", "kinetic"],
    "Artillery": ["explosive", "kinetic"],
    "Howitzer": ["explosive", "kinetic"],
    # Hybrid weapons - kinetic/thermal
    "Blaster": ["kinetic", "thermal"],
    "Railgun": ["kinetic", "thermal"],
    "Ion": ["kinetic", "thermal"],
    "Neutron": ["kinetic", "thermal"],
    "Electron": ["kinetic", "thermal"],
    # Laser weapons - EM/thermal
    "Laser": ["em", "thermal"],
    "Pulse": ["em", "thermal"],
    "Beam": ["em", "thermal"],
    "Tachyon": ["em", "thermal"],
    # Missiles - varies by type
    "Missile": ["varies"],
    "Rocket": ["varies"],
    "Torpedo": ["varies"],
}

# Combined hints: weapons + drones (drones loaded from master reference)
DAMAGE_TYPE_HINTS = {**_WEAPON_DAMAGE_HINTS, **_load_drone_damage_types()}

# NPC faction damage profiles
NPC_DAMAGE_PROFILES = {
    "Serpentis": {"deals": ["kinetic", "thermal"], "weak_to": ["thermal", "kinetic"]},
    "Angel Cartel": {"deals": ["explosive", "kinetic"], "weak_to": ["explosive", "kinetic"]},
    "Blood Raider": {"deals": ["em", "thermal"], "weak_to": ["em", "thermal"]},
    "Guristas": {"deals": ["kinetic", "thermal"], "weak_to": ["kinetic", "thermal"]},
    "Sansha": {"deals": ["em", "thermal"], "weak_to": ["em", "thermal"]},
    "Rogue Drone": {"deals": ["all"], "weak_to": ["em"]},
    "Mercenary": {"deals": ["all"], "weak_to": ["thermal", "kinetic"]},
    "CONCORD": {"deals": ["all"], "weak_to": ["none"]},
}


def _analyze_damage_types(attackers: list, type_cache: dict) -> dict:
    """
    Analyze damage types from attacker weapons.

    Returns breakdown of damage types dealt.
    """
    damage_by_type = {"em": 0, "thermal": 0, "kinetic": 0, "explosive": 0, "unknown": 0}

    total_damage = 0
    weapon_types = []

    for attacker in attackers:
        damage = attacker.get("damage_done", 0)
        total_damage += damage

        weapon_type_id = attacker.get("weapon_type_id")
        if weapon_type_id and weapon_type_id in type_cache:
            weapon_name = type_cache[weapon_type_id].get("name", "")
            weapon_types.append(weapon_name)

            # Try to infer damage type from weapon name
            damage_assigned = False
            for hint, types in DAMAGE_TYPE_HINTS.items():
                if hint.lower() in weapon_name.lower():
                    if "varies" not in types:
                        per_type = damage / len(types)
                        for t in types:
                            damage_by_type[t] += per_type
                        damage_assigned = True
                    break

            if not damage_assigned:
                damage_by_type["unknown"] += damage
        else:
            damage_by_type["unknown"] += damage

    # Calculate percentages
    result = {"total_damage": total_damage, "breakdown": {}}

    for dtype, amount in damage_by_type.items():
        if amount > 0:
            percentage = (amount / total_damage * 100) if total_damage > 0 else 0
            result["breakdown"][dtype] = {
                "damage": round(amount),
                "percentage": round(percentage, 1),
            }

    return result


def _categorize_attackers(
    attackers: list, char_id: int, type_cache: dict, char_cache: dict
) -> dict:
    """
    Categorize attackers into NPCs, players, and structures.
    """
    players = []
    npcs = []
    structures = []
    final_blow = None

    for attacker in attackers:
        attacker_char_id = attacker.get("character_id")
        attacker.get("corporation_id")
        ship_type_id = attacker.get("ship_type_id")
        weapon_type_id = attacker.get("weapon_type_id")
        damage = attacker.get("damage_done", 0)
        is_final = attacker.get("final_blow", False)

        # Get names from cache
        ship_name = type_cache.get(ship_type_id, {}).get("name", "Unknown")
        weapon_name = type_cache.get(weapon_type_id, {}).get("name", "Unknown")
        char_name = char_cache.get(attacker_char_id, {}).get("name") if attacker_char_id else None

        entry = {
            "damage_done": damage,
            "ship": ship_name,
            "weapon": weapon_name,
            "final_blow": is_final,
        }

        if is_final:
            final_blow = entry.copy()

        if attacker_char_id:
            # Player attacker
            entry["character_id"] = attacker_char_id
            entry["character_name"] = char_name or "Unknown Player"
            players.append(entry)
        elif attacker.get("faction_id"):
            # NPC faction attacker
            entry["faction_id"] = attacker.get("faction_id")
            npcs.append(entry)
        else:
            # Structure or other
            structures.append(entry)

    return {
        "players": sorted(players, key=lambda x: x["damage_done"], reverse=True),
        "npcs": sorted(npcs, key=lambda x: x["damage_done"], reverse=True),
        "structures": structures,
        "final_blow": final_blow,
        "player_count": len(players),
        "npc_count": len(npcs),
    }


def _get_killmail_details(
    client: ESIClient, killmail_id: int, killmail_hash: str
) -> Optional[dict]:
    """
    Fetch full killmail details from public endpoint.
    """
    try:
        result = client.get(f"/killmails/{killmail_id}/{killmail_hash}/")
        return result if isinstance(result, dict) else None
    except ESIError:
        return None


# =============================================================================
# Killmails Command (List Recent)
# =============================================================================


def cmd_killmails(args: argparse.Namespace) -> dict:
    """
    Fetch recent kills and losses.

    Shows summary of recent combat activity.
    """
    query_ts = get_utc_timestamp()
    limit = getattr(args, "limit", 10)
    losses_only = getattr(args, "losses", False)
    kills_only = getattr(args, "kills", False)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Check for required scope
    if not creds.has_scope("esi-killmails.read_killmails.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-killmails.read_killmails.v1",
            "action": "Re-run OAuth setup to authorize killmail access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    # Fetch recent killmails
    try:
        killmail_refs = client.get(f"/characters/{char_id}/killmails/recent/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch killmails: {e.message}",
            "query_timestamp": query_ts,
        }

    if not isinstance(killmail_refs, list):
        killmail_refs = []

    if not killmail_refs:
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "total_count": 0,
            "kills": [],
            "losses": [],
            "message": "No recent killmails found",
        }

    # Fetch details for each killmail (up to limit)
    kills = []
    losses = []
    type_ids_to_resolve = set()
    char_ids_to_resolve = set()

    for ref in killmail_refs[: limit * 2]:  # Fetch extra to account for filtering
        km_id = ref.get("killmail_id")
        km_hash = ref.get("killmail_hash")

        if not km_id or not km_hash:
            continue

        km_data = _get_killmail_details(public_client, km_id, km_hash)
        if not km_data:
            continue

        victim = km_data.get("victim", {})
        victim_char_id = victim.get("character_id")
        victim_ship_type_id = victim.get("ship_type_id")

        # Collect IDs for resolution
        if victim_ship_type_id:
            type_ids_to_resolve.add(victim_ship_type_id)
        if victim_char_id:
            char_ids_to_resolve.add(victim_char_id)

        # Determine if this is a kill or loss
        is_loss = victim_char_id == char_id

        if losses_only and not is_loss:
            continue
        if kills_only and is_loss:
            continue

        entry = {
            "killmail_id": km_id,
            "killmail_hash": km_hash,
            "killmail_time": km_data.get("killmail_time"),
            "solar_system_id": km_data.get("solar_system_id"),
            "victim_ship_type_id": victim_ship_type_id,
            "attacker_count": len(km_data.get("attackers", [])),
            "is_loss": is_loss,
            "damage_taken": victim.get("damage_taken", 0),
        }

        if is_loss:
            losses.append(entry)
        else:
            kills.append(entry)

        if len(kills) + len(losses) >= limit:
            break

    # Resolve type names
    type_cache: dict[int, dict[str, str]] = {}
    for tid in list(type_ids_to_resolve)[:50]:
        info = public_client.get_safe(f"/universe/types/{tid}/")
        if info and isinstance(info, dict):
            type_cache[tid] = {"name": info.get("name", f"Unknown ({tid})")}

    # Resolve system names
    system_ids = set()
    for entry in kills + losses:
        if entry.get("solar_system_id"):
            system_ids.add(entry["solar_system_id"])

    system_cache: dict[int, dict[str, str | float]] = {}
    for sid in list(system_ids)[:20]:
        info = public_client.get_safe(f"/universe/systems/{sid}/")
        if info and isinstance(info, dict):
            system_cache[sid] = {
                "name": info.get("name", f"System {sid}"),
                "security_status": info.get("security_status", 0),
            }

    # Enhance entries with resolved names
    for entry in kills + losses:
        ship_tid = entry.get("victim_ship_type_id")
        if ship_tid and ship_tid in type_cache:
            entry["victim_ship"] = type_cache[ship_tid]["name"]
        else:
            entry["victim_ship"] = "Unknown Ship"

        sys_id = entry.get("solar_system_id")
        if sys_id and sys_id in system_cache:
            entry["system"] = system_cache[sys_id]["name"]
            sec_status = system_cache[sys_id]["security_status"]
            entry["security"] = round(float(sec_status), 1) if sec_status is not None else 0.0
        else:
            entry["system"] = "Unknown System"

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "character_id": char_id,
        "kill_count": len(kills),
        "loss_count": len(losses),
        "kills": kills[:limit] if not losses_only else [],
        "losses": losses[:limit] if not kills_only else [],
        "filters": {"losses_only": losses_only, "kills_only": kills_only, "limit": limit},
    }


# =============================================================================
# Killmail Detail Command
# =============================================================================


def cmd_killmail_detail(args: argparse.Namespace) -> dict:
    """
    Fetch detailed analysis of a specific killmail.

    Provides comprehensive breakdown of what happened.
    """
    query_ts = get_utc_timestamp()
    killmail_id = getattr(args, "killmail_id", None)
    killmail_hash = getattr(args, "killmail_hash", None)

    # If no ID provided, try to get most recent loss
    if not killmail_id:
        return cmd_killmail_last(args)

    public_client = ESIClient()

    # If we have an ID but no hash, we need to fetch from character's killmails
    if not killmail_hash:
        try:
            client, creds = get_authenticated_client()
            char_id = creds.character_id

            # Check scope
            if not creds.has_scope("esi-killmails.read_killmails.v1"):
                return {
                    "error": "scope_not_authorized",
                    "message": "Missing required scope for killmail lookup",
                    "hint": "Provide both killmail_id and killmail_hash, or re-authorize",
                    "query_timestamp": query_ts,
                }

            # Find the hash in recent killmails
            killmail_refs = client.get(f"/characters/{char_id}/killmails/recent/", auth=True)
            if isinstance(killmail_refs, list):
                for ref in killmail_refs:
                    if ref.get("killmail_id") == killmail_id:
                        killmail_hash = ref.get("killmail_hash")
                        break

            if not killmail_hash:
                return {
                    "error": "killmail_not_found",
                    "message": f"Killmail {killmail_id} not found in recent history",
                    "hint": "Provide the killmail_hash if you have it",
                    "query_timestamp": query_ts,
                }

        except CredentialsError:
            return {
                "error": "auth_required",
                "message": "Authentication required to look up killmail hash",
                "hint": "Provide both killmail_id and killmail_hash",
                "query_timestamp": query_ts,
            }

    # Fetch the killmail details
    km_data = _get_killmail_details(public_client, killmail_id, killmail_hash)
    if not km_data:
        return {
            "error": "killmail_not_found",
            "message": f"Could not fetch killmail {killmail_id}",
            "query_timestamp": query_ts,
        }

    # Extract victim info
    victim = km_data.get("victim", {})
    attackers = km_data.get("attackers", [])
    items = victim.get("items", [])

    # Collect type IDs to resolve
    type_ids = set()
    type_ids.add(victim.get("ship_type_id"))
    for attacker in attackers:
        if attacker.get("ship_type_id"):
            type_ids.add(attacker["ship_type_id"])
        if attacker.get("weapon_type_id"):
            type_ids.add(attacker["weapon_type_id"])
    for item in items:
        if item.get("item_type_id"):
            type_ids.add(item["item_type_id"])

    # Resolve type names
    type_cache: dict[int, dict[str, str | int]] = {}
    for tid in list(type_ids)[:100]:
        if tid:
            info = public_client.get_safe(f"/universe/types/{tid}/")
            if info and isinstance(info, dict):
                type_cache[tid] = {
                    "name": info.get("name", f"Unknown ({tid})"),
                    "group_id": info.get("group_id", 0),
                }

    # Collect character IDs to resolve
    char_ids = set()
    if victim.get("character_id"):
        char_ids.add(victim["character_id"])
    for attacker in attackers:
        if attacker.get("character_id"):
            char_ids.add(attacker["character_id"])

    # Resolve character names
    char_cache: dict[int, dict[str, str]] = {}
    for cid in list(char_ids)[:30]:
        if cid:
            info = public_client.get_safe(f"/characters/{cid}/")
            if info and isinstance(info, dict):
                char_cache[cid] = {"name": info.get("name", f"Unknown ({cid})")}

    # Resolve system
    system_id = km_data.get("solar_system_id")
    system_info_raw = (
        public_client.get_safe(f"/universe/systems/{system_id}/") if system_id else None
    )
    # Type guard: ensure we have a dict response
    system_info = system_info_raw if isinstance(system_info_raw, dict) else None

    # Analyze attackers
    attacker_analysis = _categorize_attackers(
        attackers, victim.get("character_id", 0), type_cache, char_cache
    )

    # Analyze damage types
    damage_analysis = _analyze_damage_types(attackers, type_cache)

    # Process items lost/dropped
    items_destroyed = []
    items_dropped = []
    for item in items:
        item_tid = item.get("item_type_id")
        item_name = type_cache.get(item_tid, {}).get("name", f"Unknown ({item_tid})")

        item_entry = {
            "name": item_name,
            "quantity_destroyed": item.get("quantity_destroyed", 0),
            "quantity_dropped": item.get("quantity_dropped", 0),
            "flag": item.get("flag", 0),
        }

        if item.get("quantity_destroyed", 0) > 0:
            items_destroyed.append(item_entry)
        if item.get("quantity_dropped", 0) > 0:
            items_dropped.append(item_entry)

    # Build output
    victim_ship_name = type_cache.get(victim.get("ship_type_id"), {}).get("name", "Unknown Ship")
    victim_char_name = char_cache.get(victim.get("character_id"), {}).get("name", "Unknown Pilot")

    output = {
        "query_timestamp": query_ts,
        "volatility": "stable",
        "killmail_id": killmail_id,
        "killmail_time": km_data.get("killmail_time"),
        "system": {
            "id": system_id,
            "name": system_info.get("name") if system_info else "Unknown",
            "security": round(system_info.get("security_status", 0), 1) if system_info else None,
        },
        "victim": {
            "character_id": victim.get("character_id"),
            "character_name": victim_char_name,
            "ship_type_id": victim.get("ship_type_id"),
            "ship": victim_ship_name,
            "damage_taken": victim.get("damage_taken", 0),
        },
        "attackers": attacker_analysis,
        "damage_analysis": damage_analysis,
        "items": {
            "destroyed_count": len(items_destroyed),
            "dropped_count": len(items_dropped),
            "destroyed": items_destroyed[:20],
            "dropped": items_dropped[:20],
        },
    }

    return output


# =============================================================================
# Last Loss Command
# =============================================================================


def cmd_killmail_last(args: argparse.Namespace) -> dict:
    """
    Fetch and analyze the most recent loss.

    Quick access to post-mortem on your last death.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Check scope
    if not creds.has_scope("esi-killmails.read_killmails.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-killmails.read_killmails.v1",
            "action": "Re-run OAuth setup to authorize killmail access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    # Fetch recent killmails
    try:
        killmail_refs = client.get(f"/characters/{char_id}/killmails/recent/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch killmails: {e.message}",
            "query_timestamp": query_ts,
        }

    if not isinstance(killmail_refs, list) or not killmail_refs:
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "message": "No recent killmails found",
        }

    # Find the most recent loss
    for ref in killmail_refs:
        km_id = ref.get("killmail_id")
        km_hash = ref.get("killmail_hash")

        if not km_id or not km_hash:
            continue

        km_data = _get_killmail_details(public_client, km_id, km_hash)
        if not km_data:
            continue

        victim = km_data.get("victim", {})
        if victim.get("character_id") == char_id:
            # Found the most recent loss - delegate to detail command
            args.killmail_id = km_id
            args.killmail_hash = km_hash
            return cmd_killmail_detail(args)

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "message": "No recent losses found - you haven't lost any ships recently!",
        "note": "This only checks recent killmails (last 90 days)",
    }


# =============================================================================
# Loss Analysis Command
# =============================================================================


def cmd_loss_analysis(args: argparse.Namespace) -> dict:
    """
    Analyze patterns across multiple losses.

    Identifies common causes of death and areas for improvement.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Check scope
    if not creds.has_scope("esi-killmails.read_killmails.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-killmails.read_killmails.v1",
            "action": "Re-run OAuth setup",
            "query_timestamp": query_ts,
        }

    # Fetch recent killmails
    try:
        killmail_refs = client.get(f"/characters/{char_id}/killmails/recent/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch killmails: {e.message}",
            "query_timestamp": query_ts,
        }

    if not isinstance(killmail_refs, list):
        killmail_refs = []

    # Analyze losses
    losses = []
    ship_losses = {}
    system_losses = {}
    pvp_losses = 0
    pve_losses = 0

    type_cache = {}

    for ref in killmail_refs[:50]:  # Analyze up to 50 recent
        km_id = ref.get("killmail_id")
        km_hash = ref.get("killmail_hash")

        if not km_id or not km_hash:
            continue

        km_data = _get_killmail_details(public_client, km_id, km_hash)
        if not km_data:
            continue

        victim = km_data.get("victim", {})
        if victim.get("character_id") != char_id:
            continue  # Not a loss

        attackers = km_data.get("attackers", [])
        ship_tid = victim.get("ship_type_id")
        system_id = km_data.get("solar_system_id")

        # Get ship name
        if ship_tid and ship_tid not in type_cache:
            info = public_client.get_safe(f"/universe/types/{ship_tid}/")
            if info and isinstance(info, dict):
                type_cache[ship_tid] = info.get("name", f"Unknown ({ship_tid})")

        ship_name = type_cache.get(ship_tid, "Unknown")
        ship_losses[ship_name] = ship_losses.get(ship_name, 0) + 1

        # Get system name
        if system_id:
            sys_info = public_client.get_safe(f"/universe/systems/{system_id}/")
            if sys_info and isinstance(sys_info, dict):
                sys_name = sys_info.get("name", "Unknown")
                system_losses[sys_name] = system_losses.get(sys_name, 0) + 1

        # Analyze attackers
        has_player = any(a.get("character_id") for a in attackers)
        if has_player:
            pvp_losses += 1
        else:
            pve_losses += 1

        losses.append(
            {
                "killmail_id": km_id,
                "ship": ship_name,
                "damage_taken": victim.get("damage_taken", 0),
                "attacker_count": len(attackers),
                "pvp": has_player,
                "time": km_data.get("killmail_time"),
            }
        )

    if not losses:
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "message": "No recent losses found to analyze",
            "note": "This is a good thing!",
        }

    # Sort ship losses by count
    top_ships = sorted(ship_losses.items(), key=lambda x: x[1], reverse=True)[:5]
    top_systems = sorted(system_losses.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "analysis_period": "Last 90 days",
        "total_losses": len(losses),
        "pvp_losses": pvp_losses,
        "pve_losses": pve_losses,
        "ships_lost": {
            "unique_types": len(ship_losses),
            "most_lost": [{"ship": s, "count": c} for s, c in top_ships],
        },
        "dangerous_systems": [{"system": s, "losses": c} for s, c in top_systems],
        "recommendations": _generate_recommendations(losses, pvp_losses, pve_losses, top_ships),
    }


def _generate_recommendations(losses: list, pvp: int, pve: int, top_ships: list) -> list:
    """Generate improvement recommendations based on loss patterns."""
    recommendations = []

    total = len(losses)
    if total == 0:
        return ["No losses to analyze - keep up the good work!"]

    # PvP vs PvE balance
    if pvp > pve and pvp > 3:
        recommendations.append(
            f"Most losses ({pvp}/{total}) are to players. Consider: "
            "D-scan vigilance, safer travel routes, or PvP-fit ships."
        )
    elif pve > pvp and pve > 3:
        recommendations.append(
            f"Most losses ({pve}/{total}) are to NPCs. Consider: "
            "Better tanking for your ship class, or lower-level content."
        )

    # Ship type analysis
    if top_ships:
        most_lost_ship, count = top_ships[0]
        if count >= 3:
            recommendations.append(
                f"You've lost {count} {most_lost_ship}(s). Consider: "
                "Reviewing your fit, or trying a different hull."
            )

    # General recommendations
    if total >= 5:
        recommendations.append(
            "Review individual losses with 'aria-esi killmail <id>' for detailed analysis."
        )

    if not recommendations:
        recommendations.append(
            "Loss patterns look normal. Review individual killmails for specific lessons."
        )

    return recommendations


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register killmail command parsers."""

    # Recent killmails list
    list_parser = subparsers.add_parser("killmails", help="List recent kills and losses")
    list_parser.add_argument(
        "--limit", "-n", type=int, default=10, help="Maximum entries to show (default: 10)"
    )
    list_parser.add_argument("--losses", action="store_true", help="Show only losses")
    list_parser.add_argument("--kills", action="store_true", help="Show only kills")
    list_parser.set_defaults(func=cmd_killmails)

    # Specific killmail detail
    detail_parser = subparsers.add_parser(
        "killmail", help="Detailed analysis of a specific killmail"
    )
    detail_parser.add_argument(
        "killmail_id", type=int, nargs="?", help="Killmail ID (omit for most recent loss)"
    )
    detail_parser.add_argument(
        "killmail_hash", nargs="?", help="Killmail hash (optional if ID is in your history)"
    )
    detail_parser.set_defaults(func=cmd_killmail_detail)

    # Last loss shortcut
    last_parser = subparsers.add_parser("last-loss", help="Analyze your most recent ship loss")
    last_parser.set_defaults(func=cmd_killmail_last)

    # Loss pattern analysis
    analyze_parser = subparsers.add_parser(
        "loss-analysis", help="Analyze patterns across recent losses"
    )
    analyze_parser.set_defaults(func=cmd_loss_analysis)
