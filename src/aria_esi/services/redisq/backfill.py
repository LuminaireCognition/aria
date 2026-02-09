"""
Gap Recovery and Backfill from zKillboard API.

When the poller has been offline, backfills missed kills
from zKillboard's REST API.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import httpx

from ...core.logging import get_logger
from .database import get_realtime_database
from .processor import parse_esi_killmail

if TYPE_CHECKING:
    from .models import ProcessedKill, RedisQConfig

logger = get_logger(__name__)

# zKillboard API endpoints
ZKB_API_BASE = "https://zkillboard.com/api"
ZKB_REGION_KILLS_URL = ZKB_API_BASE + "/kills/regionID/{region_id}/"
ZKB_ALL_KILLS_URL = ZKB_API_BASE + "/kills/"

# ESI endpoint
ESI_KILLMAIL_URL = "https://esi.evetech.net/latest/killmails/{kill_id}/{hash}/"

# Rate limits
ZKB_RATE_LIMIT = 10  # requests per second
ESI_RATE_LIMIT = 20  # requests per second


async def backfill_from_zkillboard(
    regions: list[int] | None = None,
    since: datetime | None = None,
    max_kills: int = 500,
) -> list[ProcessedKill]:
    """
    Backfill kills from zKillboard API.

    Fetches recent kills from zKillboard (which provides kill ID + hash),
    then fetches full killmail data from ESI.

    Args:
        regions: Region IDs to backfill (None = all regions)
        since: Only backfill kills after this time
        max_kills: Maximum kills to fetch

    Returns:
        List of ProcessedKill objects fetched and processed
    """
    if since is None:
        since = datetime.utcnow() - timedelta(hours=1)

    db = get_realtime_database()
    processed_kills: list[ProcessedKill] = []

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "ARIA-ESI/1.0 (EVE Online Assistant)",
            "Accept": "application/json",
        },
        timeout=30.0,
    ) as client:
        # Fetch kills from zKillboard
        zkb_kills = await _fetch_zkb_kills(client, regions, max_kills)

        if not zkb_kills:
            logger.info("No kills found on zKillboard for backfill")
            return []

        logger.info("Fetched %d kills from zKillboard for backfill", len(zkb_kills))

        # Filter to kills after 'since' and not in database
        new_kills = []
        for kill in zkb_kills:
            kill_id = kill.get("killmail_id")
            kill_time_str = kill.get("killmail_time", "")

            if not kill_id:
                continue

            # Parse kill time
            try:
                kill_time = datetime.fromisoformat(kill_time_str.replace("Z", "+00:00"))
                kill_time = kill_time.replace(tzinfo=None)
            except (ValueError, AttributeError):
                continue

            # Filter by time
            if kill_time < since:
                continue

            # Skip if already in database
            if db.kill_exists(kill_id):
                continue

            new_kills.append(kill)

        if not new_kills:
            logger.info("All backfill kills already in database")
            return []

        logger.info("Processing %d new kills for backfill", len(new_kills))

        # Fetch full killmail data from ESI
        for kill in new_kills:
            kill_id = kill.get("killmail_id")
            zkb_data = kill.get("zkb", {})
            kill_hash = zkb_data.get("hash")

            if not kill_id or not kill_hash:
                continue

            # Fetch from ESI
            esi_data = await _fetch_esi_killmail(client, kill_id, kill_hash)

            if esi_data:
                try:
                    processed = parse_esi_killmail(esi_data, zkb_data)
                    db.save_kill(processed)
                    processed_kills.append(processed)
                except Exception as e:
                    logger.warning("Failed to parse kill %d: %s", kill_id, e)

            # Rate limiting
            await asyncio.sleep(1.0 / ESI_RATE_LIMIT)

    logger.info("Backfill complete: %d kills processed", len(processed_kills))
    return processed_kills


async def _fetch_zkb_kills(
    client: httpx.AsyncClient,
    regions: list[int] | None,
    max_kills: int,
) -> list[dict]:
    """
    Fetch kills from zKillboard API.

    Args:
        client: HTTP client
        regions: Region IDs to fetch (None = all)
        max_kills: Maximum kills to fetch

    Returns:
        List of kill dicts from zKillboard
    """
    all_kills: list[dict] = []

    if regions:
        # Fetch kills per region
        for region_id in regions:
            url = ZKB_REGION_KILLS_URL.format(region_id=region_id)
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    kills = response.json()
                    all_kills.extend(kills)

                    if len(all_kills) >= max_kills:
                        break

                # Rate limiting
                await asyncio.sleep(1.0 / ZKB_RATE_LIMIT)

            except Exception as e:
                logger.warning("Failed to fetch region %d: %s", region_id, e)
                continue
    else:
        # Fetch all recent kills
        try:
            response = await client.get(ZKB_ALL_KILLS_URL)
            if response.status_code == 200:
                all_kills = response.json()
        except Exception as e:
            logger.warning("Failed to fetch all kills: %s", e)

    return all_kills[:max_kills]


async def _fetch_esi_killmail(
    client: httpx.AsyncClient,
    kill_id: int,
    kill_hash: str,
) -> dict | None:
    """
    Fetch full killmail from ESI.

    Args:
        client: HTTP client
        kill_id: Killmail ID
        kill_hash: Killmail hash

    Returns:
        ESI killmail data or None on error
    """
    url = ESI_KILLMAIL_URL.format(kill_id=kill_id, hash=kill_hash)

    try:
        response = await client.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            logger.debug("ESI returned %d for kill %d", response.status_code, kill_id)
            return None
    except Exception as e:
        logger.debug("ESI fetch failed for kill %d: %s", kill_id, e)
        return None


async def startup_recovery(config: RedisQConfig) -> dict:
    """
    Perform startup recovery if there's a gap in data.

    Checks the last poll time and backfills if there's a significant gap.

    Args:
        config: RedisQ configuration

    Returns:
        Dict with recovery results
    """
    db = get_realtime_database()

    # Check last poll time
    last_poll = db.get_last_poll_time()
    if last_poll is None:
        # First run, no recovery needed
        return {
            "recovery_needed": False,
            "reason": "first_run",
            "kills_recovered": 0,
        }

    # Calculate gap
    now = datetime.utcnow()
    gap = now - last_poll

    # Only recover if gap > 10 minutes
    if gap.total_seconds() < 600:
        return {
            "recovery_needed": False,
            "reason": "gap_too_small",
            "gap_seconds": gap.total_seconds(),
            "kills_recovered": 0,
        }

    # Limit recovery to last 2 hours
    recovery_since = max(last_poll, now - timedelta(hours=2))

    logger.info(
        "Gap detected: %d minutes. Starting recovery from %s",
        gap.total_seconds() / 60,
        recovery_since.isoformat(),
    )

    # Perform backfill
    regions = config.filter_regions if config.filter_regions else None
    kills = await backfill_from_zkillboard(
        regions=regions,
        since=recovery_since,
        max_kills=500,
    )

    return {
        "recovery_needed": True,
        "reason": "gap_detected",
        "gap_seconds": gap.total_seconds(),
        "recovery_since": recovery_since.isoformat(),
        "kills_recovered": len(kills),
    }
