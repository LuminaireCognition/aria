"""
Ship Hull Price Lookup.

In-memory cache of ship hull prices from ESI adjusted prices.
Used to populate hull_value on ProcessedKill for hull-value-based
interest engine signals.
"""

from __future__ import annotations

import httpx

from ...core.logging import get_logger

logger = get_logger(__name__)

# ESI endpoint for market prices (public, no auth)
ESI_PRICES_URL = "https://esi.evetech.net/latest/markets/prices/"

# Ship category ID in SDE
SHIP_CATEGORY_ID = 6


class ShipPriceLookup:
    """
    In-memory cache of ship hull prices from ESI adjusted prices.

    Loaded once at poller startup. Provides O(1) lookup by type_id.
    """

    def __init__(self) -> None:
        self._prices: dict[int, float] = {}
        self._loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        """Whether prices have been loaded."""
        return self._loaded

    @property
    def ship_count(self) -> int:
        """Number of ship prices cached."""
        return len(self._prices)

    async def load(self) -> None:
        """
        Load ship hull prices from ESI adjusted prices.

        1. Query SDE types table for all ship type_ids (category_id=6)
        2. Fetch ESI /markets/prices/ (public, no auth)
        3. Filter to ship type_ids, store adjusted_price
        """
        # Step 1: Get ship type_ids from SDE
        ship_type_ids = self._get_ship_type_ids()
        if not ship_type_ids:
            logger.warning("No ship type_ids found in SDE, hull prices unavailable")
            self._loaded = True
            return

        # Step 2: Fetch ESI prices
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
                headers={
                    "User-Agent": "ARIA-ESI/1.0 (EVE Online Assistant)",
                    "Accept": "application/json",
                },
            ) as client:
                response = await client.get(ESI_PRICES_URL)
                if response.status_code != 200:
                    logger.warning(
                        "ESI /markets/prices/ returned %d, hull prices unavailable",
                        response.status_code,
                    )
                    self._loaded = True
                    return

                prices_data = response.json()
        except Exception as e:
            logger.warning("Failed to fetch ESI prices: %s", e)
            self._loaded = True
            return

        # Step 3: Filter to ships and store
        self._prices = {}
        for entry in prices_data:
            type_id = entry.get("type_id")
            adjusted_price = entry.get("adjusted_price")
            if type_id in ship_type_ids and adjusted_price is not None:
                self._prices[type_id] = float(adjusted_price)

        self._loaded = True
        logger.info("Loaded hull prices for %d ships", len(self._prices))

    def get_hull_value(self, type_id: int) -> float | None:
        """
        Get hull value for a ship type_id.

        Args:
            type_id: Ship type ID

        Returns:
            Adjusted price in ISK, or None if not a ship or price unknown
        """
        return self._prices.get(type_id)

    def _get_ship_type_ids(self) -> set[int]:
        """
        Get all ship type_ids from the SDE database.

        Returns:
            Set of type_ids for ships (category_id=6)
        """
        try:
            from ...mcp.market.database import get_market_database

            db = get_market_database()
            conn = db._get_connection()
            rows = conn.execute(
                "SELECT type_id FROM types WHERE category_id = ?",
                (SHIP_CATEGORY_ID,),
            ).fetchall()
            return {row[0] for row in rows}
        except Exception as e:
            logger.warning("Failed to query ship type_ids from SDE: %s", e)
            return set()


# =============================================================================
# Module-level singleton
# =============================================================================

_ship_price_lookup: ShipPriceLookup | None = None


def get_ship_price_lookup() -> ShipPriceLookup:
    """Get or create the ship price lookup singleton."""
    global _ship_price_lookup
    if _ship_price_lookup is None:
        _ship_price_lookup = ShipPriceLookup()
    return _ship_price_lookup


def reset_ship_price_lookup() -> None:
    """Reset the ship price lookup singleton (for testing)."""
    global _ship_price_lookup
    _ship_price_lookup = None
