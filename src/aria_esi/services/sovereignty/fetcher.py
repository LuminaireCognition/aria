"""
Sovereignty ESI Fetcher.

Fetches sovereignty data from ESI endpoints:
- GET /sovereignty/map/ - Current sovereignty map (public, no auth)
- GET /alliances/{id}/ - Alliance info for name resolution
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from ...core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger(__name__)

# ESI endpoints
ESI_BASE_URL = "https://esi.evetech.net/latest"
SOV_MAP_ENDPOINT = "/sovereignty/map/"
ALLIANCE_ENDPOINT = "/alliances/{alliance_id}/"

# Rate limiting
ALLIANCE_BATCH_SIZE = 50  # ESI allows ~150 concurrent requests, be conservative
ALLIANCE_BATCH_DELAY = 0.5  # Delay between batches


async def fetch_sovereignty_map() -> list[dict]:
    """
    Fetch current sovereignty map from ESI.

    ESI GET /sovereignty/map/ returns a list of:
    {
        "system_id": int,
        "alliance_id": int (optional),
        "corporation_id": int (optional),
        "faction_id": int (optional)
    }

    Returns:
        List of sovereignty entries from ESI
    """
    import httpx

    url = f"{ESI_BASE_URL}{SOV_MAP_ENDPOINT}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.info("Fetching sovereignty map from ESI")
        response = await client.get(
            url,
            params={"datasource": "tranquility"},
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()

        data = response.json()
        logger.info("Fetched %d sovereignty entries", len(data))
        return data


async def fetch_alliance_info(alliance_id: int) -> dict | None:
    """
    Fetch alliance information from ESI.

    ESI GET /alliances/{alliance_id}/ returns:
    {
        "name": str,
        "ticker": str,
        "creator_corporation_id": int,
        "creator_id": int,
        "date_founded": str,
        "executor_corporation_id": int (optional),
        "faction_id": int (optional)
    }

    Args:
        alliance_id: Alliance ID to fetch

    Returns:
        Alliance data dict or None if not found
    """
    import httpx

    url = f"{ESI_BASE_URL}{ALLIANCE_ENDPOINT.format(alliance_id=alliance_id)}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                params={"datasource": "tranquility"},
                headers={"Accept": "application/json"},
            )

            if response.status_code == 404:
                logger.warning("Alliance %d not found", alliance_id)
                return None

            response.raise_for_status()
            return response.json()

    except Exception as e:
        logger.error("Failed to fetch alliance %d: %s", alliance_id, e)
        return None


async def fetch_alliances_batch(alliance_ids: Sequence[int]) -> dict[int, dict]:
    """
    Fetch multiple alliances with rate limiting.

    Args:
        alliance_ids: Alliance IDs to fetch

    Returns:
        Dict mapping alliance_id to alliance data
    """
    results: dict[int, dict] = {}
    unique_ids = list(set(alliance_ids))

    logger.info("Fetching %d unique alliances", len(unique_ids))

    # Process in batches
    for i in range(0, len(unique_ids), ALLIANCE_BATCH_SIZE):
        batch = unique_ids[i : i + ALLIANCE_BATCH_SIZE]

        # Fetch batch concurrently
        tasks = [fetch_alliance_info(aid) for aid in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for alliance_id, result in zip(batch, batch_results):
            if isinstance(result, dict):
                results[alliance_id] = result
            elif isinstance(result, Exception):
                logger.error("Error fetching alliance %d: %s", alliance_id, result)

        # Rate limit between batches
        if i + ALLIANCE_BATCH_SIZE < len(unique_ids):
            await asyncio.sleep(ALLIANCE_BATCH_DELAY)

        logger.debug(
            "Fetched %d/%d alliances", min(i + ALLIANCE_BATCH_SIZE, len(unique_ids)), len(unique_ids)
        )

    logger.info("Fetched %d alliances successfully", len(results))
    return results


def fetch_sovereignty_map_sync() -> list[dict]:
    """Synchronous wrapper for fetch_sovereignty_map."""
    return asyncio.run(fetch_sovereignty_map())


def fetch_alliances_batch_sync(alliance_ids: Sequence[int]) -> dict[int, dict]:
    """Synchronous wrapper for fetch_alliances_batch."""
    return asyncio.run(fetch_alliances_batch(alliance_ids))
