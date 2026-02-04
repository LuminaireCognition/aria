"""
Fuzzwork Market API Client.

Provides aggregated market data from Fuzzwork's EVE Market Data service.
Supports both individual queries and bulk CSV downloads for database seeding.

API Documentation: https://market.fuzzwork.co.uk/
Rate Limits: ~30 requests/minute, 100 types per request
"""

from __future__ import annotations

import asyncio
import gzip
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx

from ...core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

FUZZWORK_BASE_URL = "https://market.fuzzwork.co.uk"
FUZZWORK_AGGREGATES_ENDPOINT = "/aggregates/"
FUZZWORK_BULK_CSV_URL = "https://market.fuzzwork.co.uk/aggregatecsv.csv.gz"

# Rate limiting
MAX_TYPES_PER_REQUEST = 100
MIN_REQUEST_INTERVAL_SECONDS = 2.0  # ~30 req/min = 2 seconds between requests
DEFAULT_TIMEOUT_SECONDS = 30

# Default location (Jita 4-4)
DEFAULT_REGION_ID = 10000002  # The Forge
DEFAULT_STATION_ID = 60003760  # Jita 4-4


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True)
class FuzzworkAggregate:
    """
    Aggregated price data from Fuzzwork API.

    Contains buy and sell statistics for a single type ID.
    """

    type_id: int
    buy_weighted_average: float
    buy_max: float
    buy_min: float
    buy_stddev: float
    buy_median: float
    buy_volume: int
    buy_order_count: int
    buy_percentile: float  # 5th percentile
    sell_weighted_average: float
    sell_max: float
    sell_min: float
    sell_stddev: float
    sell_median: float
    sell_volume: int
    sell_order_count: int
    sell_percentile: float  # 5th percentile

    @classmethod
    def from_api_response(cls, type_id: int, data: dict) -> FuzzworkAggregate:
        """
        Parse Fuzzwork API response into aggregate data.

        Args:
            type_id: The type ID this data is for
            data: Raw API response dict for this type

        Returns:
            Parsed FuzzworkAggregate
        """
        buy = data.get("buy", {})
        sell = data.get("sell", {})

        return cls(
            type_id=type_id,
            buy_weighted_average=float(buy.get("weightedAverage", 0)),
            buy_max=float(buy.get("max", 0)),
            buy_min=float(buy.get("min", 0)),
            buy_stddev=float(buy.get("stddev", 0)),
            buy_median=float(buy.get("median", 0)),
            buy_volume=int(float(buy.get("volume", 0))),
            buy_order_count=int(buy.get("orderCount", 0)),
            buy_percentile=float(buy.get("percentile", 0)),
            sell_weighted_average=float(sell.get("weightedAverage", 0)),
            sell_max=float(sell.get("max", 0)),
            sell_min=float(sell.get("min", 0)),
            sell_stddev=float(sell.get("stddev", 0)),
            sell_median=float(sell.get("median", 0)),
            sell_volume=int(float(sell.get("volume", 0))),
            sell_order_count=int(sell.get("orderCount", 0)),
            sell_percentile=float(sell.get("percentile", 0)),
        )


@dataclass
class FuzzworkClient:
    """
    Client for Fuzzwork Market API.

    Handles rate limiting, request batching, and error recovery.
    Designed for async usage via run_in_executor pattern.
    """

    region_id: int = DEFAULT_REGION_ID
    station_id: int | None = DEFAULT_STATION_ID
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    _last_request_time: float = field(default=0.0, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            sleep_time = MIN_REQUEST_INTERVAL_SECONDS - elapsed
            logger.debug("Rate limiting: sleeping %.2fs", sleep_time)
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _build_url(self, type_ids: Sequence[int]) -> str:
        """
        Build Fuzzwork API URL for given type IDs.

        Args:
            type_ids: Type IDs to query (max 100)

        Returns:
            Full URL with query parameters
        """
        types_param = ",".join(str(t) for t in type_ids)
        url = f"{FUZZWORK_BASE_URL}{FUZZWORK_AGGREGATES_ENDPOINT}"
        url += f"?region={self.region_id}&types={types_param}"

        if self.station_id:
            url += f"&station={self.station_id}"

        return url

    def get_aggregates_sync(
        self,
        type_ids: Sequence[int],
    ) -> dict[int, FuzzworkAggregate]:
        """
        Synchronous fetch of aggregated prices.

        Args:
            type_ids: Type IDs to fetch (will be chunked if > 100)

        Returns:
            Dict mapping type_id to FuzzworkAggregate
        """
        if not type_ids:
            return {}

        results: dict[int, FuzzworkAggregate] = {}

        # Chunk into batches of MAX_TYPES_PER_REQUEST
        chunks = [
            type_ids[i : i + MAX_TYPES_PER_REQUEST]
            for i in range(0, len(type_ids), MAX_TYPES_PER_REQUEST)
        ]

        for chunk in chunks:
            self._rate_limit()
            url = self._build_url(chunk)

            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url)
                    response.raise_for_status()
                    data = response.json()

                    for type_id_str, type_data in data.items():
                        try:
                            type_id = int(type_id_str)
                            results[type_id] = FuzzworkAggregate.from_api_response(
                                type_id, type_data
                            )
                        except (ValueError, KeyError) as e:
                            logger.warning("Failed to parse type %s: %s", type_id_str, e)

            except httpx.TimeoutException:
                logger.error("Fuzzwork request timed out for %d types", len(chunk))
                raise
            except httpx.HTTPStatusError as e:
                logger.error("Fuzzwork HTTP error %d: %s", e.response.status_code, e)
                raise
            except Exception as e:
                logger.error("Fuzzwork request failed: %s", e)
                raise

        return results

    async def get_aggregates(
        self,
        type_ids: Sequence[int],
    ) -> dict[int, FuzzworkAggregate]:
        """
        Async fetch of aggregated prices.

        Runs sync HTTP in executor to avoid blocking the event loop.
        Uses lock to prevent concurrent requests (rate limiting).

        Args:
            type_ids: Type IDs to fetch

        Returns:
            Dict mapping type_id to FuzzworkAggregate
        """
        async with self._lock:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                self.get_aggregates_sync,
                type_ids,
            )

    def download_bulk_csv_sync(self) -> bytes:
        """
        Download bulk CSV data for all items.

        Downloads gzipped CSV from Fuzzwork and decompresses it.
        Contains aggregated prices for all market items.

        Returns:
            Raw CSV bytes (decompressed)
        """
        self._rate_limit()

        with httpx.Client(timeout=120) as client:  # Longer timeout for bulk
            response = client.get(FUZZWORK_BULK_CSV_URL)
            response.raise_for_status()
            # Decompress gzip data
            return gzip.decompress(response.content)

    async def download_bulk_csv(self) -> bytes:
        """Async wrapper for bulk CSV download."""
        async with self._lock:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self.download_bulk_csv_sync)


# =============================================================================
# Helper Functions
# =============================================================================


def create_client(
    region: str = "jita",
    station_only: bool = True,
) -> FuzzworkClient:
    """
    Create a Fuzzwork client for the specified trade hub.

    Args:
        region: Trade hub name (jita, amarr, dodixie, rens, hek)
        station_only: If True, filter to station orders only

    Returns:
        Configured FuzzworkClient
    """
    from aria_esi.models.market import resolve_trade_hub

    hub = resolve_trade_hub(region)
    if not hub:
        # Default to Jita if unknown
        logger.warning("Unknown trade hub '%s', defaulting to Jita", region)
        hub = resolve_trade_hub("jita")

    return FuzzworkClient(
        region_id=hub["region_id"],
        station_id=hub["station_id"] if station_only else None,
    )
