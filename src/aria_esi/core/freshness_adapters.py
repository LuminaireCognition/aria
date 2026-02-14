"""
ARIA Freshness Sync Adapters

Adapter functions that bridge the freshness library to existing sync commands.
Each adapter has signature (pilot_dir: Path) -> None and raises on failure.
"""

import argparse
import os
from pathlib import Path


def sync_standings(pilot_dir: Path) -> None:
    """
    Sync standings from ESI to profile.md.

    Sets ARIA_PILOT env var so get_settings() resolves the correct pilot,
    then calls the existing sync_profile() function.
    """
    from .config import reset_settings

    pilot_id = pilot_dir.name.split("_", 1)[0]
    old_pilot = os.environ.get("ARIA_PILOT")

    try:
        os.environ["ARIA_PILOT"] = pilot_id
        reset_settings()

        from ..commands.sync_profile import sync_profile

        result = sync_profile()
        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(result.get("message", result["error"]))
    finally:
        if old_pilot is not None:
            os.environ["ARIA_PILOT"] = old_pilot
        else:
            os.environ.pop("ARIA_PILOT", None)
        reset_settings()


def sync_skills(pilot_dir: Path) -> None:
    """
    Sync skills from ESI to skills.json.

    Sets ARIA_PILOT env var so get_settings() resolves the correct pilot,
    then calls the existing cmd_sync_skills() function.
    """
    from .config import reset_settings

    pilot_id = pilot_dir.name.split("_", 1)[0]
    old_pilot = os.environ.get("ARIA_PILOT")

    try:
        os.environ["ARIA_PILOT"] = pilot_id
        reset_settings()

        from ..commands.skills import cmd_sync_skills

        result = cmd_sync_skills(argparse.Namespace())
        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(result.get("message", result["error"]))
    finally:
        if old_pilot is not None:
            os.environ["ARIA_PILOT"] = old_pilot
        else:
            os.environ.pop("ARIA_PILOT", None)
        reset_settings()
