"""
ARIA ESI Corporation Commands

Corporation management: info, status, wallet, assets, blueprints, jobs.
Most commands require authentication and CEO/Director role.
"""

import argparse
from datetime import datetime, timezone
from typing import Optional

from ..core import (
    ACTIVITY_TYPES,
    PLAYER_CORP_MIN_ID,
    SHIP_GROUP_IDS,
    Credentials,
    CredentialsError,
    ESIClient,
    ESIError,
    format_duration,
    get_authenticated_client,
    get_utc_timestamp,
    parse_datetime,
)


def _get_character_corp_id(client: ESIClient, char_id: int) -> Optional[int]:
    """Get corporation ID from character public info."""
    char_info = client.get_dict_safe(f"/characters/{char_id}/")
    return char_info.get("corporation_id") if char_info else None


def _require_corp_scope(creds: Credentials, scope: str, query_ts: str) -> Optional[dict]:
    """
    Check if credentials have a required scope.
    Returns error dict if missing, None if scope is present.
    """
    if not creds.has_scope(scope):
        return {
            "error": "scope_not_authorized",
            "message": f"Missing required scope: {scope}",
            "action": "Re-run OAuth setup with corporation scopes",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }
    return None


# =============================================================================
# Corp Info Command (Public - no auth required for lookup)
# =============================================================================


def cmd_corp_info(args: argparse.Namespace) -> dict:
    """
    Fetch corporation public information.

    Works for any corporation - no authentication required for lookup.
    Use 'my' or no argument to look up own corporation (requires auth).
    """
    query_ts = get_utc_timestamp()
    target = getattr(args, "target", "my") or "my"
    public_client = ESIClient()

    corp_id = None

    if target.lower() in ("my", "self", ""):
        # Get own corporation - requires auth
        try:
            client, creds = get_authenticated_client()
            corp_id = _get_character_corp_id(public_client, creds.character_id)
        except CredentialsError as e:
            return e.to_dict() | {"query_timestamp": query_ts}
    elif target.isdigit():
        # Direct corporation ID
        corp_id = int(target)
    else:
        # Search by name using POST /universe/ids/
        try:
            result = public_client.post("/universe/ids/", [target])
            if result and isinstance(result, dict):
                corps = result.get("corporations", [])
                if corps:
                    corp_id = corps[0].get("id")
        except ESIError:
            pass

        if not corp_id:
            return {
                "error": "not_found",
                "message": f"No corporation found matching: {target}",
                "query_timestamp": query_ts,
            }

    # Get corporation public info
    corp = public_client.get_dict_safe(f"/corporations/{corp_id}/")
    if not corp:
        return {
            "error": "not_found",
            "message": f"Corporation {corp_id} not found",
            "query_timestamp": query_ts,
        }

    # Resolve CEO name
    ceo_name = "Unknown"
    if corp.get("ceo_id"):
        ceo_info = public_client.get_dict_safe(f"/characters/{corp['ceo_id']}/")
        if ceo_info:
            ceo_name = ceo_info.get("name", "Unknown")

    # Resolve alliance if any
    alliance_name = None
    if corp.get("alliance_id"):
        alliance_info = public_client.get_dict_safe(f"/alliances/{corp['alliance_id']}/")
        if alliance_info:
            alliance_name = alliance_info.get("name")

    # Resolve home station if any
    home_station = None
    if corp.get("home_station_id"):
        station_info = public_client.get_dict_safe(f"/universe/stations/{corp['home_station_id']}/")
        if station_info:
            home_station = station_info.get("name")

    return {
        "query_timestamp": query_ts,
        "volatility": "stable",
        "corporation_id": corp_id,
        "name": corp.get("name"),
        "ticker": corp.get("ticker"),
        "member_count": corp.get("member_count"),
        "ceo_id": corp.get("ceo_id"),
        "ceo_name": ceo_name,
        "tax_rate": round(corp.get("tax_rate", 0) * 100, 1),
        "date_founded": corp.get("date_founded"),
        "alliance_id": corp.get("alliance_id"),
        "alliance_name": alliance_name,
        "home_station": home_station,
        "description": (corp.get("description", "") or "")[:500],
        "is_player_corp": corp_id >= PLAYER_CORP_MIN_ID,
    }


# =============================================================================
# Corp Status Command (Dashboard)
# =============================================================================


def cmd_corp_status(args: argparse.Namespace) -> dict:
    """
    Fetch corporation dashboard with summary of all corp data.

    Requires CEO/Director role for detailed information.
    Only works for player corporations.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    public_client = ESIClient()
    char_id = creds.character_id

    # Get corporation ID
    corp_id = _get_character_corp_id(public_client, char_id)
    if not corp_id:
        return {
            "error": "corp_not_found",
            "message": "Could not determine corporation ID",
            "query_timestamp": query_ts,
        }

    # Check if player corp
    if corp_id < PLAYER_CORP_MIN_ID:
        return {
            "error": "npc_corporation",
            "message": "Corporation dashboard only works for player corporations",
            "corporation_id": corp_id,
            "suggestion": "Use 'corp info' for public corporation lookup",
            "query_timestamp": query_ts,
        }

    # Get public corporation info
    corp = public_client.get_dict_safe(f"/corporations/{corp_id}/")
    if not corp:
        return {
            "error": "corp_not_found",
            "message": f"Could not retrieve corporation {corp_id}",
            "query_timestamp": query_ts,
        }

    # Resolve CEO name
    ceo_name = "Unknown"
    if corp.get("ceo_id"):
        ceo_info = public_client.get_dict_safe(f"/characters/{corp['ceo_id']}/")
        if ceo_info and "name" in ceo_info:
            ceo_name = ceo_info["name"]

    # Build output
    output = {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "corporation": {
            "id": corp_id,
            "name": corp.get("name"),
            "ticker": corp.get("ticker"),
            "member_count": corp.get("member_count"),
            "ceo_name": ceo_name,
            "tax_rate": round(corp.get("tax_rate", 0) * 100, 1),
            "date_founded": corp.get("date_founded"),
        },
    }

    # Try to get wallet balances if scope available
    if creds.has_scope("esi-wallet.read_corporation_wallets.v1"):
        try:
            wallets = client.get(f"/corporations/{corp_id}/wallets/", auth=True)
            if wallets and isinstance(wallets, list):
                total_balance = sum(w.get("balance", 0) for w in wallets)
                output["financial"] = {
                    "total_balance": total_balance,
                    "division_count": len(wallets),
                }
        except ESIError:
            output["financial"] = {"status": "access_denied"}
    else:
        output["financial"] = {"status": "scope_not_authorized"}

    # Try to get asset counts if scope available
    if creds.has_scope("esi-assets.read_corporation_assets.v1"):
        try:
            assets = client.get(f"/corporations/{corp_id}/assets/", auth=True)
            if assets and isinstance(assets, list):
                locations = set()
                ship_count = 0
                for a in assets:
                    if a.get("location_type") == "station":
                        locations.add(a.get("location_id"))
                    if a.get("is_singleton") and a.get("location_flag") in ("CorpSAG1", "Hangar"):
                        ship_count += 1
                output["assets"] = {
                    "total_items": len(assets),
                    "locations": len(locations),
                    "ships": ship_count,
                }
        except ESIError:
            output["assets"] = {"status": "access_denied"}
    else:
        output["assets"] = {"status": "scope_not_authorized"}

    # Try to get blueprint counts if scope available
    if creds.has_scope("esi-corporations.read_blueprints.v1"):
        try:
            blueprints = client.get(f"/corporations/{corp_id}/blueprints/", auth=True)
            if blueprints and isinstance(blueprints, list):
                bpo_count = sum(1 for b in blueprints if b.get("quantity") == -1)
                bpc_count = len(blueprints) - bpo_count
                output["blueprints"] = {"bpo_count": bpo_count, "bpc_count": bpc_count}
        except ESIError:
            output["blueprints"] = {"status": "access_denied"}
    else:
        output["blueprints"] = {"status": "scope_not_authorized"}

    # Try to get industry job counts if scope available
    if creds.has_scope("esi-industry.read_corporation_jobs.v1"):
        try:
            jobs = client.get(f"/corporations/{corp_id}/industry/jobs/", auth=True)
            if jobs and isinstance(jobs, list):
                active_jobs = [j for j in jobs if j.get("status") == "active"]
                output["industry"] = {"active_jobs": len(active_jobs), "total_jobs": len(jobs)}
        except ESIError:
            output["industry"] = {"status": "access_denied"}
    else:
        output["industry"] = {"status": "scope_not_authorized"}

    output["available_subcommands"] = ["info", "wallet", "assets", "blueprints", "jobs", "help"]

    return output


# =============================================================================
# Corp Wallet Command
# =============================================================================


def cmd_corp_wallet(args: argparse.Namespace) -> dict:
    """
    Fetch corporation wallet balances and optional journal.

    Requires esi-wallet.read_corporation_wallets.v1 scope.
    """
    query_ts = get_utc_timestamp()
    show_journal = getattr(args, "journal", False)
    division = getattr(args, "division", 1)
    limit = getattr(args, "limit", 25)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    # Check scope
    scope_error = _require_corp_scope(creds, "esi-wallet.read_corporation_wallets.v1", query_ts)
    if scope_error:
        return scope_error

    public_client = ESIClient()
    char_id = creds.character_id
    corp_id = _get_character_corp_id(public_client, char_id)

    if not corp_id:
        return {
            "error": "corp_not_found",
            "message": "Could not determine corporation ID",
            "query_timestamp": query_ts,
        }

    # Get wallet balances
    try:
        wallets = client.get(f"/corporations/{corp_id}/wallets/", auth=True)
    except ESIError as e:
        return {
            "error": "wallet_access_denied",
            "message": f"Could not access corporation wallets: {e.message}",
            "hint": "You may need CEO/Director role",
            "query_timestamp": query_ts,
        }

    if not wallets or not isinstance(wallets, list):
        return {
            "error": "wallet_access_denied",
            "message": "Could not access corporation wallets. You may need CEO/Director role.",
            "query_timestamp": query_ts,
        }

    # Get division names (if available)
    div_names = {}
    try:
        divisions = client.get(f"/corporations/{corp_id}/divisions/", auth=True)
        if divisions and isinstance(divisions, dict):
            wallet_divs = divisions.get("wallet", [])
            for d in wallet_divs:
                div_names[d.get("division")] = d.get("name", f"Division {d.get('division')}")
    except ESIError:
        pass

    # Build wallet summary
    wallet_summary = []
    total_balance = 0
    for w in wallets:
        div_num = w.get("division", 1)
        balance = w.get("balance", 0)
        total_balance += balance
        wallet_summary.append(
            {
                "division": div_num,
                "name": div_names.get(
                    div_num, "Master Wallet" if div_num == 1 else f"Division {div_num}"
                ),
                "balance": balance,
            }
        )

    output = {
        "query_timestamp": query_ts,
        "volatility": "volatile",
        "corporation_id": corp_id,
        "total_balance": total_balance,
        "wallets": wallet_summary,
    }

    # Get journal if requested
    if show_journal:
        try:
            journal = client.get(f"/corporations/{corp_id}/wallets/{division}/journal/", auth=True)
            if journal and isinstance(journal, list):
                # Sort by date descending and limit
                journal.sort(key=lambda x: x.get("date", ""), reverse=True)
                journal = journal[:limit]

                journal_entries = []
                for entry in journal:
                    journal_entries.append(
                        {
                            "id": entry.get("id"),
                            "date": entry.get("date"),
                            "amount": entry.get("amount"),
                            "balance": entry.get("balance"),
                            "ref_type": entry.get("ref_type"),
                            "description": (entry.get("description", "") or "")[:100],
                        }
                    )
                output["journal"] = {"division": division, "entries": journal_entries}
        except ESIError:
            output["journal"] = {"error": "Could not fetch journal"}

    return output


# =============================================================================
# Corp Assets Command
# =============================================================================


def cmd_corp_assets(args: argparse.Namespace) -> dict:
    """
    Fetch corporation asset inventory.

    Supports --ships filter, --location filter, --type filter.
    Requires esi-assets.read_corporation_assets.v1 scope.
    """
    query_ts = get_utc_timestamp()
    show_ships = getattr(args, "ships", False)
    filter_location = getattr(args, "location_filter", None)
    filter_type = getattr(args, "type_filter", None)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    # Check scope
    scope_error = _require_corp_scope(creds, "esi-assets.read_corporation_assets.v1", query_ts)
    if scope_error:
        return scope_error

    public_client = ESIClient()
    char_id = creds.character_id
    corp_id = _get_character_corp_id(public_client, char_id)

    if not corp_id:
        return {
            "error": "corp_not_found",
            "message": "Could not determine corporation ID",
            "query_timestamp": query_ts,
        }

    # Get corporation assets
    try:
        assets = client.get(f"/corporations/{corp_id}/assets/", auth=True)
    except ESIError as e:
        return {
            "error": "asset_access_denied",
            "message": f"Could not access corporation assets: {e.message}",
            "hint": "You may need CEO/Director role",
            "query_timestamp": query_ts,
        }

    if not assets or not isinstance(assets, list):
        return {
            "error": "asset_access_denied",
            "message": "Could not access corporation assets. You may need CEO/Director role.",
            "query_timestamp": query_ts,
        }

    # Collect type and location IDs for resolution (limit to avoid too many requests)
    type_ids = set(a["type_id"] for a in assets)
    location_ids = set(a["location_id"] for a in assets if a.get("location_type") == "station")

    # Resolve type names (limit to first 100)
    type_info = {}
    for tid in list(type_ids)[:100]:
        info = public_client.get_dict_safe(f"/universe/types/{tid}/")
        if info and "name" in info:
            type_info[tid] = {"name": info["name"], "group_id": info.get("group_id", 0)}

    # Resolve station names (limit to first 50)
    station_names = {}
    for lid in list(location_ids)[:50]:
        info = public_client.get_dict_safe(f"/universe/stations/{lid}/")
        if info and "name" in info:
            station_names[lid] = info["name"]

    # Group assets by location
    assets_by_location = {}
    ships = []

    for a in assets:
        tid = a["type_id"]
        tinfo = type_info.get(tid, {"name": f"Type-{tid}", "group_id": 0})
        name = tinfo["name"]
        group_id = tinfo["group_id"]

        loc_id = a["location_id"]
        if a.get("location_type") == "station":
            location = station_names.get(loc_id, f"Station-{loc_id}")
        else:
            location = f"Location-{loc_id}"

        # Apply filters
        if filter_location and filter_location.lower() not in location.lower():
            continue
        if filter_type and filter_type.lower() not in name.lower():
            continue

        # Check if ship
        if show_ships:
            if group_id in SHIP_GROUP_IDS and a.get("is_singleton"):
                ships.append(
                    {
                        "item_id": a["item_id"],
                        "type_name": name,
                        "location": location,
                        "location_flag": a.get("location_flag", ""),
                    }
                )
            continue

        # Group by location
        if location not in assets_by_location:
            assets_by_location[location] = []
        assets_by_location[location].append(
            {
                "name": name,
                "quantity": a.get("quantity", 1),
                "location_flag": a.get("location_flag", ""),
                "is_singleton": a.get("is_singleton", False),
            }
        )

    if show_ships:
        ships.sort(key=lambda x: x["type_name"])
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "corporation_id": corp_id,
            "ship_count": len(ships),
            "ships": ships,
        }
    else:
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "corporation_id": corp_id,
            "total_items": len(assets),
            "locations": len(assets_by_location),
            "assets_by_location": assets_by_location,
            "filters_applied": {
                "location": filter_location if filter_location else None,
                "type": filter_type if filter_type else None,
            },
        }


# =============================================================================
# Corp Blueprints Command
# =============================================================================


def cmd_corp_blueprints(args: argparse.Namespace) -> dict:
    """
    Fetch corporation blueprint library.

    Supports --filter, --bpos, --bpcs flags.
    Requires esi-corporations.read_blueprints.v1 scope.
    """
    query_ts = get_utc_timestamp()
    filter_name = getattr(args, "filter", None)
    show_bpos_only = getattr(args, "bpos", False)
    show_bpcs_only = getattr(args, "bpcs", False)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    # Check scope
    scope_error = _require_corp_scope(creds, "esi-corporations.read_blueprints.v1", query_ts)
    if scope_error:
        return scope_error

    public_client = ESIClient()
    char_id = creds.character_id
    corp_id = _get_character_corp_id(public_client, char_id)

    if not corp_id:
        return {
            "error": "corp_not_found",
            "message": "Could not determine corporation ID",
            "query_timestamp": query_ts,
        }

    # Get corporation blueprints
    try:
        blueprints = client.get(f"/corporations/{corp_id}/blueprints/", auth=True)
    except ESIError as e:
        return {
            "error": "blueprint_access_denied",
            "message": f"Could not access corporation blueprints: {e.message}",
            "hint": "You may need CEO/Director role",
            "query_timestamp": query_ts,
        }

    if not blueprints or not isinstance(blueprints, list):
        return {
            "error": "blueprint_access_denied",
            "message": "Could not access corporation blueprints. You may need CEO/Director role.",
            "query_timestamp": query_ts,
        }

    # Collect type IDs for resolution (limit to first 100)
    type_ids = set(bp["type_id"] for bp in blueprints)

    # Resolve type names
    type_names = {}
    for tid in list(type_ids)[:100]:
        info = public_client.get_dict_safe(f"/universe/types/{tid}/")
        if info and "name" in info:
            type_names[tid] = info["name"]

    # Process blueprints
    bpos = []
    bpcs = []

    for bp in blueprints:
        tid = bp["type_id"]
        name = type_names.get(tid, f"Blueprint-{tid}")

        # Apply filter
        if filter_name and filter_name.lower() not in name.lower():
            continue

        entry = {
            "type_id": tid,
            "name": name,
            "material_efficiency": bp.get("material_efficiency", 0),
            "time_efficiency": bp.get("time_efficiency", 0),
            "location_flag": bp.get("location_flag", ""),
        }

        if bp.get("quantity") == -1:
            # BPO
            entry["type"] = "BPO"
            bpos.append(entry)
        else:
            # BPC
            entry["type"] = "BPC"
            entry["runs"] = bp.get("runs", 0)
            bpcs.append(entry)

    # Sort by name
    bpos.sort(key=lambda x: x["name"])
    bpcs.sort(key=lambda x: x["name"])

    # Filter output based on flags
    if show_bpos_only:
        output_bpos = bpos
        output_bpcs = []
    elif show_bpcs_only:
        output_bpos = []
        output_bpcs = bpcs
    else:
        output_bpos = bpos
        output_bpcs = bpcs

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "corporation_id": corp_id,
        "bpo_count": len(output_bpos),
        "bpc_count": len(output_bpcs),
        "bpos": output_bpos,
        "bpcs": output_bpcs,
        "filter_applied": filter_name if filter_name else None,
    }


# =============================================================================
# Corp Jobs Command
# =============================================================================


def cmd_corp_jobs(args: argparse.Namespace) -> dict:
    """
    Fetch corporation industry jobs.

    Supports --active, --completed, --history flags.
    Requires esi-industry.read_corporation_jobs.v1 scope.
    """
    query_ts = get_utc_timestamp()
    show_active_only = getattr(args, "active", False)
    show_completed = getattr(args, "completed", False)
    show_history = getattr(args, "history", False)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    # Check scope
    scope_error = _require_corp_scope(creds, "esi-industry.read_corporation_jobs.v1", query_ts)
    if scope_error:
        return scope_error

    public_client = ESIClient()
    char_id = creds.character_id
    corp_id = _get_character_corp_id(public_client, char_id)

    if not corp_id:
        return {
            "error": "corp_not_found",
            "message": "Could not determine corporation ID",
            "query_timestamp": query_ts,
        }

    # Get corporation industry jobs
    params = {"include_completed": "true"} if (show_completed or show_history) else {}
    try:
        jobs = client.get(f"/corporations/{corp_id}/industry/jobs/", auth=True, params=params)
    except ESIError as e:
        return {
            "error": "jobs_access_denied",
            "message": f"Could not access corporation industry jobs: {e.message}",
            "hint": "You may need CEO/Director role",
            "query_timestamp": query_ts,
        }

    if not jobs or not isinstance(jobs, list):
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "corporation_id": corp_id,
            "active_count": 0,
            "active_jobs": [],
            "recently_completed": [],
            "message": "No industry jobs found or access denied",
        }

    # Collect type and character IDs for resolution
    product_ids = set(j.get("product_type_id") or j.get("blueprint_type_id") for j in jobs)
    installer_ids = set(j.get("installer_id") for j in jobs)

    # Resolve product names (limit to 50)
    product_names = {}
    for tid in list(product_ids)[:50]:
        if tid:
            info = public_client.get_dict_safe(f"/universe/types/{tid}/")
            if info and "name" in info:
                product_names[tid] = info["name"]

    # Resolve installer names (limit to 20)
    installer_names = {}
    for cid in list(installer_ids)[:20]:
        if cid:
            info = public_client.get_dict_safe(f"/characters/{cid}/")
            if info and "name" in info:
                installer_names[cid] = info["name"]

    # Process jobs
    active_jobs = []
    completed_jobs = []
    now = datetime.now(timezone.utc)

    for job in jobs:
        activity_id = job.get("activity_id", 0)
        activity_key, activity_display = ACTIVITY_TYPES.get(activity_id, ("unknown", "Unknown"))
        product_id = job.get("product_type_id") or job.get("blueprint_type_id")
        product = product_names.get(product_id, f"Product-{product_id}")
        installer = installer_names.get(job.get("installer_id"), "Unknown")

        entry = {
            "job_id": job.get("job_id"),
            "activity": activity_display,
            "product": product,
            "runs": job.get("runs", 1),
            "installer": installer,
            "start_date": job.get("start_date"),
            "end_date": job.get("end_date"),
            "status": job.get("status"),
        }

        # Calculate time remaining for active jobs
        if job.get("status") == "active" and job.get("end_date"):
            end_date = parse_datetime(job["end_date"])
            if end_date:
                delta = (end_date - now).total_seconds()
                if delta > 0:
                    entry["time_remaining"] = format_duration(delta)
                else:
                    entry["time_remaining"] = "Ready for delivery"

        if job.get("status") == "active":
            active_jobs.append(entry)
        else:
            completed_jobs.append(entry)

    # Sort by end date
    active_jobs.sort(key=lambda x: x.get("end_date", ""))
    completed_jobs.sort(key=lambda x: x.get("end_date", ""), reverse=True)

    # Apply filters
    if show_active_only:
        output_active = active_jobs
        output_completed = []
    elif show_completed or show_history:
        output_active = []
        output_completed = completed_jobs[: 50 if show_history else 10]
    else:
        output_active = active_jobs
        output_completed = completed_jobs[:5]  # Recent completed

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "corporation_id": corp_id,
        "active_count": len(active_jobs),
        "active_jobs": output_active,
        "recently_completed": output_completed,
    }


# =============================================================================
# Corp Help Command
# =============================================================================


def cmd_corp_help(args: argparse.Namespace) -> dict:
    """Display help for corporation commands."""
    return {
        "command": "aria-esi corp",
        "description": "Corporation management and queries",
        "subcommands": {
            "status": "Corporation dashboard - overview of all corp data (default)",
            "info": "Public corporation lookup (works for any corp, no auth required)",
            "wallet": "Wallet balances and transaction journal",
            "assets": "Corporation hangar inventory",
            "blueprints": "BPO/BPC library",
            "jobs": "Manufacturing and research status",
            "help": "This help message",
        },
        "examples": [
            "aria-esi corp                      # Status dashboard",
            "aria-esi corp info                 # Own corp public info",
            "aria-esi corp info 98000001        # EVE University by ID",
            'aria-esi corp info "Pandemic"      # Search by name',
            "aria-esi corp wallet               # Wallet summary",
            "aria-esi corp wallet --journal     # Transaction history",
            "aria-esi corp assets               # Full inventory",
            "aria-esi corp assets --ships       # Corp ships only",
            "aria-esi corp blueprints           # Blueprint library",
            "aria-esi corp blueprints --bpos    # BPOs only",
            "aria-esi corp jobs                 # Industry status",
            "aria-esi corp jobs --active        # Active jobs only",
        ],
        "authentication": {
            "info": "No authentication required (public endpoint)",
            "other": "Requires CEO/Director role and corporation ESI scopes",
        },
        "setup": "python3 .claude/scripts/aria-oauth-setup.py (select corp scopes)",
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register corporation command parsers."""

    # Main corp command with subparsers
    corp_parser = subparsers.add_parser("corp", help="Corporation management and queries")
    corp_subparsers = corp_parser.add_subparsers(dest="corp_subcommand", help="Corp subcommands")

    # corp status (default)
    status_parser = corp_subparsers.add_parser(
        "status", help="Corporation dashboard - overview of all corp data"
    )
    status_parser.set_defaults(func=cmd_corp_status)

    # corp info
    info_parser = corp_subparsers.add_parser("info", help="Public corporation lookup")
    info_parser.add_argument(
        "target",
        nargs="?",
        default="my",
        help="Corporation name, ID, or 'my' for own corp (default: my)",
    )
    info_parser.set_defaults(func=cmd_corp_info)

    # corp wallet
    wallet_parser = corp_subparsers.add_parser(
        "wallet", help="Corporation wallet balances and journal"
    )
    wallet_parser.add_argument("--journal", action="store_true", help="Include transaction journal")
    wallet_parser.add_argument(
        "--div",
        dest="division",
        type=int,
        default=1,
        help="Wallet division for journal (default: 1)",
    )
    wallet_parser.add_argument(
        "--limit", type=int, default=25, help="Maximum journal entries (default: 25)"
    )
    wallet_parser.set_defaults(func=cmd_corp_wallet)

    # corp assets
    assets_parser = corp_subparsers.add_parser("assets", help="Corporation asset inventory")
    assets_parser.add_argument("--ships", action="store_true", help="Show only assembled ships")
    assets_parser.add_argument(
        "--location", dest="location_filter", metavar="NAME", help="Filter by location name"
    )
    assets_parser.add_argument(
        "--type", dest="type_filter", metavar="NAME", help="Filter by item type name"
    )
    assets_parser.set_defaults(func=cmd_corp_assets)

    # corp blueprints
    blueprints_parser = corp_subparsers.add_parser(
        "blueprints", help="Corporation blueprint library"
    )
    blueprints_parser.add_argument(
        "--filter", dest="filter", metavar="NAME", help="Filter by blueprint name"
    )
    blueprints_parser.add_argument("--bpos", action="store_true", help="Show only BPOs")
    blueprints_parser.add_argument("--bpcs", action="store_true", help="Show only BPCs")
    blueprints_parser.set_defaults(func=cmd_corp_blueprints)

    # corp jobs
    jobs_parser = corp_subparsers.add_parser("jobs", help="Corporation industry jobs")
    jobs_group = jobs_parser.add_mutually_exclusive_group()
    jobs_group.add_argument("--active", action="store_true", help="Show only active jobs")
    jobs_group.add_argument("--completed", action="store_true", help="Show recently completed jobs")
    jobs_group.add_argument("--history", action="store_true", help="Show extended job history")
    jobs_parser.set_defaults(func=cmd_corp_jobs)

    # corp help
    help_parser = corp_subparsers.add_parser("help", help="Show corporation command help")
    help_parser.set_defaults(func=cmd_corp_help)

    # Default to status if no subcommand
    corp_parser.set_defaults(func=cmd_corp_status)
