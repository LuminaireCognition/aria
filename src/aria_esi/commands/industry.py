"""
ARIA ESI Industry Commands

Manufacturing and research: industry jobs.
All commands require authentication.
"""

import argparse
from datetime import datetime, timezone

from ..core import (
    ACTIVITY_TYPES,
    CredentialsError,
    ESIClient,
    ESIError,
    format_duration,
    get_authenticated_client,
    get_utc_timestamp,
    parse_datetime,
)

# =============================================================================
# Industry Jobs Command
# =============================================================================


def cmd_industry_jobs(args: argparse.Namespace) -> dict:
    """
    Fetch personal manufacturing and research jobs.

    Shows active jobs, completion times, and optionally recent history.
    """
    query_ts = get_utc_timestamp()
    filter_mode = getattr(args, "filter_mode", None)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Determine if we need completed jobs
    include_completed = filter_mode in ("history", "all", "completed")

    # Fetch industry jobs
    try:
        params = {"include_completed": "true"} if include_completed else {}
        jobs_data = client.get_list(
            f"/characters/{char_id}/industry/jobs/", auth=True, params=params
        )
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch industry jobs: {e.message}",
            "hint": "Ensure esi-industry.read_character_jobs.v1 scope is authorized",
            "query_timestamp": query_ts,
        }

    # Empty jobs check
    if not jobs_data:
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "character_id": char_id,
            "summary": {"active_jobs": 0, "completed_awaiting_delivery": 0},
            "jobs": [],
            "message": "No industry jobs found",
        }

    # Collect type IDs for name resolution
    type_ids = set()
    for job in jobs_data:
        if isinstance(job, dict):
            type_ids.add(job.get("blueprint_type_id", 0))
            if job.get("product_type_id"):
                type_ids.add(job["product_type_id"])

    # Resolve type names
    type_names = {}
    for tid in type_ids:
        if tid:
            info = public_client.get_dict_safe(f"/universe/types/{tid}/")
            if info and "name" in info:
                type_names[tid] = info["name"]

    # Resolve station/structure names
    location_ids = set(job.get("facility_id", 0) for job in jobs_data if isinstance(job, dict))
    location_names = {}
    for lid in location_ids:
        if lid:
            station = public_client.get_dict_safe(f"/universe/stations/{lid}/")
            if station and "name" in station:
                location_names[lid] = station["name"]
            else:
                location_names[lid] = f"Structure-{lid}"

    now = datetime.now(timezone.utc)
    processed_jobs = []
    summary = {
        "active_jobs": 0,
        "completed_awaiting_delivery": 0,
        "manufacturing": 0,
        "research_me": 0,
        "research_te": 0,
        "copying": 0,
        "invention": 0,
        "reactions": 0,
    }

    for job in jobs_data:
        activity_id = job.get("activity_id", 0)
        activity_key, activity_display = ACTIVITY_TYPES.get(activity_id, ("unknown", "Unknown"))

        blueprint_tid = job.get("blueprint_type_id", 0)
        product_tid = job.get("product_type_id")

        blueprint_name = type_names.get(blueprint_tid, f"Unknown-{blueprint_tid}")
        product_name = type_names.get(product_tid) if product_tid else None

        start_date = parse_datetime(job.get("start_date"))
        end_date = parse_datetime(job.get("end_date"))

        # Determine status
        job_status = job.get("status", "active")

        # Calculate progress and time remaining
        progress = 0
        time_remaining_str = ""

        if end_date:
            remaining_seconds = (end_date - now).total_seconds()

            if job_status == "active":
                if remaining_seconds <= 0:
                    # Job completed but not yet delivered
                    job_status = "ready"
                    progress = 100
                    time_remaining_str = "0m"
                else:
                    time_remaining_str = format_duration(remaining_seconds)

                    # Calculate progress
                    if start_date:
                        total_seconds = (end_date - start_date).total_seconds()
                        elapsed = (now - start_date).total_seconds()
                        if total_seconds > 0:
                            progress = int(min(100, max(0, (elapsed / total_seconds) * 100)))
            elif job_status == "delivered":
                progress = 100
                time_remaining_str = "Delivered"
            elif job_status == "cancelled":
                time_remaining_str = "Cancelled"
            elif job_status == "reverted":
                time_remaining_str = "Reverted"

        # Update summary
        if job_status == "active":
            summary["active_jobs"] += 1
            if activity_key in summary:
                summary[activity_key] += 1
        elif job_status == "ready":
            summary["completed_awaiting_delivery"] += 1

        # Filter logic
        if filter_mode == "active" and job_status not in ["active"]:
            continue
        if filter_mode == "completed" and job_status != "ready":
            continue
        if filter_mode == "history" and job_status not in [
            "delivered",
            "cancelled",
            "reverted",
            "active",
            "ready",
        ]:
            continue

        processed_job = {
            "job_id": job.get("job_id"),
            "activity": activity_key,
            "activity_id": activity_id,
            "activity_display": activity_display,
            "blueprint_name": blueprint_name,
            "product_name": product_name,
            "runs": job.get("runs", 1),
            "status": job_status,
            "facility_name": location_names.get(job.get("facility_id", 0), "Unknown"),
            "start_date": job.get("start_date"),
            "end_date": job.get("end_date"),
            "time_remaining": time_remaining_str,
            "progress_percent": round(progress, 1),
            "cost": job.get("cost", 0),
        }

        # Add specific fields for certain activities
        if activity_id == 5:  # Copying
            processed_job["licensed_runs"] = job.get("licensed_runs")
        if activity_id == 8:  # Invention
            processed_job["probability"] = job.get("probability")

        processed_jobs.append(processed_job)

    # Sort: active first by end_date, then ready, then completed
    def sort_key(j):
        status_order = {"active": 0, "ready": 1, "delivered": 2, "cancelled": 3, "reverted": 4}
        order = status_order.get(j["status"], 5)
        end = j.get("end_date") or "9999"
        return (order, end)

    processed_jobs.sort(key=sort_key)

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "character_id": char_id,
        "summary": summary,
        "jobs": processed_jobs,
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register industry command parsers."""

    # Industry jobs command
    jobs_parser = subparsers.add_parser(
        "industry-jobs", help="Fetch personal manufacturing and research jobs"
    )
    jobs_parser.add_argument(
        "--active",
        action="store_const",
        const="active",
        dest="filter_mode",
        help="Show only active jobs (default)",
    )
    jobs_parser.add_argument(
        "--completed",
        action="store_const",
        const="completed",
        dest="filter_mode",
        help="Show jobs ready for delivery",
    )
    jobs_parser.add_argument(
        "--history",
        action="store_const",
        const="history",
        dest="filter_mode",
        help="Include recently completed jobs",
    )
    jobs_parser.add_argument(
        "--all",
        action="store_const",
        const="all",
        dest="filter_mode",
        help="Show all jobs including history",
    )
    jobs_parser.set_defaults(func=cmd_industry_jobs)
