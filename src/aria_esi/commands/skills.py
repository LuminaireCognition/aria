"""
ARIA ESI Skills Commands

Character skill information: trained skills, skill queue.
All commands require authentication.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ..core import (
    CredentialsError,
    ESIClient,
    ESIError,
    format_duration,
    get_authenticated_client,
    get_pilot_directory,
    get_utc_timestamp,
    parse_datetime,
    to_roman,
)

# =============================================================================
# Skill Cache Functions
# =============================================================================


def load_cached_skills(pilot_dir: Path | None = None) -> dict[int, int] | None:
    """
    Load skills from local cache.

    Args:
        pilot_dir: Pilot directory path. If None, resolves from config.

    Returns:
        Dict mapping skill_id to level, or None if cache not found.
    """
    if pilot_dir is None:
        pilot_dir = get_pilot_directory()
    if not pilot_dir:
        return None

    cache_path = pilot_dir / "skills.json"
    if not cache_path.exists():
        return None

    try:
        data = json.loads(cache_path.read_text())
        return {int(k): v for k, v in data.get("skills", {}).items()}
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def is_skills_cache_stale(pilot_dir: Path | None = None, ttl_hours: int = 12) -> bool:
    """
    Check if skill cache is older than TTL.

    Args:
        pilot_dir: Pilot directory path. If None, resolves from config.
        ttl_hours: Cache TTL in hours (default 12).

    Returns:
        True if cache is stale or missing, False if fresh.
    """
    if pilot_dir is None:
        pilot_dir = get_pilot_directory()
    if not pilot_dir:
        return True

    cache_path = pilot_dir / "skills.json"
    if not cache_path.exists():
        return True

    try:
        data = json.loads(cache_path.read_text())
        meta = data.get("_meta", {})
        synced_at = meta.get("synced_at")
        if not synced_at:
            return True

        # Parse ISO timestamp
        sync_time = datetime.fromisoformat(synced_at.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - sync_time).total_seconds() / 3600
        return age_hours > ttl_hours
    except (json.JSONDecodeError, KeyError, ValueError):
        return True


def get_skills_cache_info(pilot_dir: Path | None = None) -> dict | None:
    """
    Get metadata about the skills cache.

    Args:
        pilot_dir: Pilot directory path. If None, resolves from config.

    Returns:
        Dict with cache metadata, or None if not cached.
    """
    if pilot_dir is None:
        pilot_dir = get_pilot_directory()
    if not pilot_dir:
        return None

    cache_path = pilot_dir / "skills.json"
    if not cache_path.exists():
        return None

    try:
        data = json.loads(cache_path.read_text())
        return data.get("_meta")
    except (json.JSONDecodeError, KeyError):
        return None


# =============================================================================
# Sync Skills Command
# =============================================================================


def cmd_sync_skills(args: argparse.Namespace) -> dict:
    """
    Sync skills from ESI to local cache.

    Fetches all trained skills and saves them to userdata/pilots/{dir}/skills.json
    for use by fitting calculations.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id

    # Resolve pilot directory
    pilot_dir = get_pilot_directory()
    if not pilot_dir:
        return {
            "error": "pilot_directory_not_found",
            "message": "Could not find pilot directory",
            "hint": "Ensure userdata/pilots/ contains a directory for this pilot",
            "query_timestamp": query_ts,
        }

    # Fetch skills from ESI
    try:
        skills_data = client.get(f"/characters/{char_id}/skills/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch skills: {e.message}",
            "query_timestamp": query_ts,
        }

    if not isinstance(skills_data, dict):
        return {
            "error": "invalid_response",
            "message": "Invalid skills response from ESI",
            "query_timestamp": query_ts,
        }

    total_sp = skills_data.get("total_sp", 0)
    unallocated_sp = skills_data.get("unallocated_sp", 0)
    skills = skills_data.get("skills", [])

    # Build skill_id -> level mapping
    skill_levels: dict[str, int] = {}
    for skill in skills:
        skill_id = skill.get("skill_id")
        trained_level = skill.get("trained_skill_level", 0)
        if skill_id and trained_level > 0:
            # Store as string keys for JSON serialization
            skill_levels[str(skill_id)] = trained_level

    # Build cache file
    cache_data = {
        "_meta": {
            "character_id": char_id,
            "synced_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "total_sp": total_sp,
            "unallocated_sp": unallocated_sp,
            "skill_count": len(skill_levels),
        },
        "skills": skill_levels,
    }

    # Write cache file
    cache_path = pilot_dir / "skills.json"
    try:
        cache_path.write_text(json.dumps(cache_data, indent=2))
    except OSError as e:
        return {
            "error": "write_error",
            "message": f"Could not write cache file: {e}",
            "cache_path": str(cache_path),
            "query_timestamp": query_ts,
        }

    return {
        "query_timestamp": query_ts,
        "status": "success",
        "message": "Skills synced to local cache",
        "cache_path": str(cache_path),
        "character_id": char_id,
        "total_sp": total_sp,
        "skill_count": len(skill_levels),
    }


# =============================================================================
# Skills Command
# =============================================================================


def cmd_skills(args: argparse.Namespace) -> dict:
    """
    Fetch trained skill levels.

    Optionally filter by skill name.
    """
    query_ts = get_utc_timestamp()
    skill_filter = getattr(args, "filter", None)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Fetch skills
    try:
        skills_data = client.get(f"/characters/{char_id}/skills/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch skills: {e.message}",
            "query_timestamp": query_ts,
        }

    if not isinstance(skills_data, dict):
        return {
            "error": "invalid_response",
            "message": "Invalid skills response from ESI",
            "query_timestamp": query_ts,
        }

    total_sp = skills_data.get("total_sp", 0)
    unallocated_sp = skills_data.get("unallocated_sp", 0)
    skills = skills_data.get("skills", [])

    # Resolve skill names
    type_ids = [s["skill_id"] for s in skills]
    skill_names = {}
    skill_groups = {}

    for tid in type_ids:
        info = public_client.get_dict_safe(f"/universe/types/{tid}/")
        if info and "name" in info:
            skill_names[tid] = info["name"]
            skill_groups[tid] = info.get("group_id", 0)

    # Build skill list with names
    skill_list = []
    for s in skills:
        sid = s["skill_id"]
        name = skill_names.get(sid, f"Unknown-{sid}")

        # Apply filter if specified
        if skill_filter and skill_filter.lower() not in name.lower():
            continue

        skill_list.append(
            {
                "skill_id": sid,
                "name": name,
                "trained_level": s["trained_skill_level"],
                "active_level": s["active_skill_level"],
                "skillpoints": s["skillpoints_in_skill"],
                "level_display": to_roman(s["trained_skill_level"]),
            }
        )

    # Sort by name
    skill_list.sort(key=lambda x: x["name"])

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "total_sp": total_sp,
        "unallocated_sp": unallocated_sp,
        "skill_count": len(skill_list),
        "filter_applied": skill_filter if skill_filter else None,
        "skills": skill_list,
    }


# =============================================================================
# Skillqueue Command
# =============================================================================


def cmd_skillqueue(args: argparse.Namespace) -> dict:
    """
    Fetch skill training queue with ETA.

    Shows currently training skill and queue completion time.
    This data is VOLATILE - queue can change at any time.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Fetch skill queue
    try:
        queue_data = client.get_list(f"/characters/{char_id}/skillqueue/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch skill queue: {e.message}",
            "hint": "Ensure esi-skills.read_skillqueue.v1 scope is authorized",
            "query_timestamp": query_ts,
        }

    # Empty queue check
    if not queue_data:
        return {
            "query_timestamp": query_ts,
            "volatility": "volatile",
            "queue_status": "empty",
            "message": "Skill queue is empty - no skills training!",
            "queue_length": 0,
            "skills": [],
        }

    # Collect skill IDs for name resolution
    skill_ids = set(s["skill_id"] for s in queue_data if isinstance(s, dict) and "skill_id" in s)
    skill_names = {}

    for sid in skill_ids:
        info = public_client.get_dict_safe(f"/universe/types/{sid}/")
        if info and "name" in info:
            skill_names[sid] = info["name"]

    now = datetime.now(timezone.utc)
    queue_items = []
    currently_training = None
    queue_completion = None

    for idx, skill in enumerate(queue_data):
        sid = skill["skill_id"]
        name = skill_names.get(sid, f"Unknown-{sid}")
        target_level = skill["finished_level"]

        start_date = parse_datetime(skill.get("start_date"))
        finish_date = parse_datetime(skill.get("finish_date"))

        # Calculate progress and time remaining
        progress = 0
        time_remaining = None
        time_remaining_str = ""
        status = "queued"

        if finish_date:
            remaining_seconds = (finish_date - now).total_seconds()
            time_remaining = max(0, remaining_seconds)
            time_remaining_str = format_duration(time_remaining)

            # Track queue completion (last skill's finish_date)
            if not queue_completion or finish_date > queue_completion:
                queue_completion = finish_date

            # Calculate progress for currently training skill
            if start_date and skill.get("queue_position", idx) == 0:
                total_seconds = (finish_date - start_date).total_seconds()
                elapsed_seconds = (now - start_date).total_seconds()
                if total_seconds > 0:
                    progress = int(min(100, max(0, (elapsed_seconds / total_seconds) * 100)))
                status = "training"
                currently_training = {
                    "name": name,
                    "level": target_level,
                    "level_display": to_roman(target_level),
                    "progress": round(progress, 1),
                    "time_remaining": time_remaining_str,
                    "finish_date": finish_date.isoformat(),
                }

        item = {
            "queue_position": skill.get("queue_position", idx),
            "skill_id": sid,
            "name": name,
            "target_level": target_level,
            "level_display": to_roman(target_level),
            "status": status,
            "time_remaining": time_remaining_str if time_remaining_str else None,
            "finish_date": finish_date.isoformat() if finish_date else None,
        }

        if status == "training":
            item["progress_percent"] = round(progress, 1)

        queue_items.append(item)

    # Calculate total queue time
    total_queue_time = ""
    if queue_completion:
        total_seconds = (queue_completion - now).total_seconds()
        total_queue_time = format_duration(max(0, total_seconds))

    return {
        "query_timestamp": query_ts,
        "volatility": "volatile",
        "queue_status": "active",
        "queue_length": len(queue_items),
        "total_queue_time": total_queue_time,
        "queue_completion": queue_completion.isoformat() if queue_completion else None,
        "currently_training": currently_training,
        "skills": queue_items,
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register skills command parsers."""

    # Skills command
    skills_parser = subparsers.add_parser("skills", help="Fetch trained skill levels")
    skills_parser.add_argument("filter", nargs="?", help="Filter skills by name (optional)")
    skills_parser.set_defaults(func=cmd_skills)

    # Skillqueue command
    queue_parser = subparsers.add_parser(
        "skillqueue", help="Fetch skill training queue with ETA (volatile)"
    )
    queue_parser.set_defaults(func=cmd_skillqueue)

    # Sync-skills command
    sync_parser = subparsers.add_parser(
        "sync-skills", help="Cache skills locally for fitting calculations"
    )
    sync_parser.set_defaults(func=cmd_sync_skills)
