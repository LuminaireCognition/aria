# ARIA Market Data MCP Proposal

## Executive Summary

This proposal outlines a strategy for integrating up-to-date market data into ARIA via MCP tools. By combining bulk data downloads for seeding with API calls for incremental updates, we can provide fast, reliable price lookups while minimizing API load and enabling offline capability.

**Recommendation:** Extend the existing `aria-universe` MCP server with market tools backed by a local SQLite database that:
1. **Seeds** from Fuzzwork bulk CSV (~24MB, updated every 30 min)
2. **Updates** incrementally via Fuzzwork/ESI APIs on-demand (no background jobs)
3. **Resolves** item names locally using SDE type data (no API calls)
4. **Falls back** through multiple data sources when primary is unavailable

This hybrid approach provides instant cold-start (bulk load), offline capability, and minimal API usage.

---

## Data Sources Analysis

### ESI Market Endpoints

The official ESI provides three primary market endpoints:

| Endpoint | Auth | Cache | Use Case |
|----------|------|-------|----------|
| `GET /markets/prices/` | None | 1 hour | Global average/adjusted prices for all items |
| `GET /markets/{region_id}/orders/` | None | 5 min | Regional buy/sell orders (paginated) |
| `GET /markets/{region_id}/history/` | None | 1 hour | Daily historical data (30 days) |

**Strengths:**
- Official source, guaranteed accuracy
- Real-time order data (5 min cache)
- Free, no API key required

**Limitations:**
- `/markets/prices/` returns 15,000+ items in one response (~2MB)
- `/markets/{region_id}/orders/` requires pagination for liquid items
- No pre-aggregated metrics (must calculate min/max/spread client-side)
- Rate limited: ~100 errors per minute before throttling

### Fuzzwork Market API

Fuzzwork (https://market.fuzzwork.co.uk/api/) provides pre-aggregated market data:

| Endpoint | Purpose |
|----------|---------|
| `/aggregates/?region={id}&types={ids}` | Aggregated buy/sell metrics |
| `/aggregates/?station={id}&types={ids}` | Station-specific aggregates |
| `/api/orderset` | Current orderset ID (snapshot version) |

**Response structure per item:**
```json
{
  "34": {
    "buy": {
      "weightedAverage": 3.95,
      "max": 4.00,
      "min": 3.50,
      "stddev": 0.12,
      "median": 3.97,
      "volume": 50000000000,
      "orderCount": 1542,
      "percentile": 3.98
    },
    "sell": {
      "weightedAverage": 4.10,
      "min": 4.05,
      "max": 5.00,
      "stddev": 0.15,
      "median": 4.12,
      "volume": 12000000000,
      "orderCount": 892,
      "percentile": 4.08
    }
  }
}
```

**Strengths:**
- Batch queries: 100+ items in single request
- Pre-aggregated: weighted average, percentile, volume, spread
- Station-specific filtering (Jita 4-4 only, etc.)
- Designed for bulk lookups

**Limitations:**
- Third-party service (availability not guaranteed)
- Aggregates only (no individual order details)
- Update frequency unclear (~15-30 minutes typical)

### EVE Ref Market Data (Secondary Fallback)

EVE Ref (https://docs.everef.net/datasets/) provides bulk market snapshots:

| Dataset | Update Freq | Size | Contents |
|---------|-------------|------|----------|
| `market-orders/` | 2x hourly | ~500MB | Full order snapshots |
| `market-history/` | Daily | Varies | Historical price data |

**Use as fallback when:**
- Fuzzwork API is unavailable
- Need to compute aggregates from raw orders
- Historical analysis requires full order book

---

## Recommended Architecture

### Integrated Server Approach

Rather than creating a separate `aria-market` MCP server, extend the existing `aria-universe` server with market tools. This provides:

- Single MCP connection to manage
- Shared state (system/region name resolution from universe graph)
- Simpler `.mcp.json` configuration
- Cross-domain queries (e.g., route + cargo value)

```
                    ┌─────────────────────────────┐
                    │      aria-universe          │
                    │        MCP Server           │
                    │  ┌───────────┬────────────┐ │
                    │  │ Universe  │   Market   │ │
                    │  │   Tools   │   Tools    │ │
                    │  └─────┬─────┴──────┬─────┘ │
                    └────────┼────────────┼───────┘
                             │            │
              ┌──────────────┤            ├──────────────┐
              │              │            │              │
              ▼              ▼            ▼              ▼
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │ UniverseGraph│ │ MarketCache  │ │  OrderCache  │ │ HistoryCache │
      │   (static)   │ │  (Fuzzwork)  │ │    (ESI)     │ │    (ESI)     │
      │              │ │  TTL: 15min  │ │  TTL: 5min   │ │  TTL: 1hour  │
      └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

### Data Source Fallback Chain

```
Primary          Secondary         Tertiary
┌─────────┐      ┌─────────┐      ┌─────────┐
│Fuzzwork │ ──▶  │ESI Rgn  │ ──▶  │ESI Glbl │
│Aggregate│      │Orders   │      │Prices   │
└─────────┘      └─────────┘      └─────────┘
     │                │                │
     │ Unavailable    │ Unavailable    │ Unavailable
     ▼                ▼                ▼
   Try next        Try next       Return stale
   source          source         + warning
```

### Why Hybrid Sources?

| Query Type | Best Source | Reason |
|------------|-------------|--------|
| "What's Tritanium worth?" | Fuzzwork | Pre-aggregated, fast |
| "Price check 50 salvage items" | Fuzzwork | Batch query support |
| "Show me top 10 buy orders" | ESI | Order details needed |
| "Price trend for PLEX" | ESI | Historical data required |
| "Spread analysis for T2 mods" | Fuzzwork | Aggregates include spread |

### Package Structure

```
aria_esi/
├── mcp/
│   ├── server.py                 # Extended to load market tools
│   ├── tools.py                  # Universe tool registration
│   └── market/
│       ├── __init__.py
│       ├── cache.py              # MarketCache (on-demand refresh)
│       ├── clients.py            # Fuzzwork + ESI clients
│       ├── database.py           # SQLite seeding/queries
│       ├── tools.py              # Tool registration
│       ├── tools_prices.py       # Price lookup tools
│       ├── tools_orders.py       # Regional order tools
│       ├── tools_history.py      # Historical data tools
│       └── tools_analysis.py     # Spread/trend analysis
└── models/
    └── market.py                 # Shared Pydantic models (CLI + MCP)
```

### Configuration (.mcp.json)

No change required - market tools are registered in the existing server:

```json
{
  "mcpServers": {
    "aria-universe": {
      "command": "uv",
      "args": ["run", "python", "-m", "aria_esi.mcp.server"],
      "cwd": ".claude/scripts"
    }
  }
}
```

---

## Shared Response Models

Unified Pydantic models for use across CLI and MCP:

```python
# aria_esi/models/market.py
from pydantic import BaseModel
from typing import Literal

class PriceAggregate(BaseModel):
    """Aggregated price metrics for one side of the market."""
    min: float
    max: float
    weighted_avg: float
    median: float
    stddev: float
    volume: int
    order_count: int
    percentile: float  # 5th percentile for sells, 95th for buys

class ItemPrice(BaseModel):
    """Complete price data for a single item."""
    type_id: int
    name: str
    buy: PriceAggregate
    sell: PriceAggregate
    spread_isk: float      # sell.min - buy.max
    spread_percent: float  # spread / sell.min * 100

class MarketPricesResult(BaseModel):
    """Result from market_prices tool."""
    items: list[ItemPrice]
    region: str
    station: str | None
    source: Literal["fuzzwork", "esi_orders", "esi_global", "local_cache"]
    cache_age_seconds: int
    warnings: list[str] = []

class MarketOrder(BaseModel):
    """Individual market order."""
    order_id: int
    price: float
    volume_remain: int
    volume_total: int
    location_id: int
    location_name: str
    is_buy_order: bool
    min_volume: int
    range: str
    duration: int
    issued: str

class MarketOrdersResult(BaseModel):
    """Result from market_orders tool."""
    type_id: int
    name: str
    region: str
    buy_orders: list[MarketOrder]
    sell_orders: list[MarketOrder]
    best_buy: float | None
    best_sell: float | None
    spread_isk: float | None
    spread_percent: float | None
    cache_age_seconds: int

class ValuationItem(BaseModel):
    """Single item in a valuation request."""
    name: str
    quantity: int
    type_id: int | None = None  # Resolved during processing

class ValuationResult(BaseModel):
    """Result from market_valuation tool."""
    items: list[dict]  # Per-item breakdown
    total_value: float
    price_type: Literal["buy", "sell"]
    region: str
    confidence: Literal["high", "medium", "low"]
    warnings: list[str] = []
```

---

## Proposed MCP Tools

### Core Price Tools

#### `market_prices`
Quick price lookups using Fuzzwork aggregates.

```python
@server.tool()
async def market_prices(
    items: list[str],           # Item names or type IDs
    region: str = "jita",       # Trade hub or region name
    station_only: bool = True   # Filter to hub station only
) -> MarketPricesResult:
    """
    Get aggregated market prices for multiple items.

    Uses Fuzzwork pre-aggregated data for fast batch lookups.
    Falls back to ESI regional orders if Fuzzwork unavailable.
    Returns buy/sell prices with volume, spread, and order counts.

    Args:
        items: Item names to look up (max 100)
        region: Trade hub name (jita, amarr, dodixie, rens, hek) or region ID
        station_only: If true, filter to main station (e.g., Jita 4-4)

    Returns:
        MarketPricesResult with per-item buy/sell aggregates

    Example:
        market_prices(["Tritanium", "Pyerite", "Mexallon"], region="jita")
    """
```

#### `market_orders`
Detailed order book from ESI.

```python
@server.tool()
async def market_orders(
    item: str,                  # Item name or type ID
    region: str = "jita",       # Trade hub or region
    order_type: str = "all",    # "buy", "sell", or "all"
    limit: int = 10             # Orders to return per side
) -> MarketOrdersResult:
    """
    Get detailed market orders for an item.

    Uses ESI for real-time order data (5 min cache).
    Shows individual orders with price, volume, and location.

    Args:
        item: Item name to look up
        region: Trade hub or region
        order_type: Filter to buy, sell, or all orders
        limit: Max orders to return per side (default: 10, max: 50)

    Returns:
        MarketOrdersResult with buy/sell order lists
    """
```

#### `market_cache_status`
Diagnostic tool for cache state.

```python
@server.tool()
async def market_cache_status() -> dict:
    """
    Return diagnostic information about market cache layers.

    Useful for debugging cache behavior, checking data freshness,
    and verifying API connectivity.

    Returns:
        Cache status for aggregates, orders, history, and types
    """
```

**Response:**
```json
{
  "aggregates": {
    "source": "fuzzwork_bulk",
    "age_seconds": 847,
    "rows": 1250000,
    "stale": false
  },
  "orders": {
    "cached_items": 42,
    "oldest_seconds": 290,
    "newest_seconds": 15
  },
  "types": {
    "loaded": true,
    "count": 47000,
    "sde_version": "Equinox_1.0"
  },
  "api_health": {
    "fuzzwork": "ok",
    "esi": "ok",
    "last_fuzzwork_error": null,
    "last_esi_error": null
  }
}
```

### Analysis Tools

#### `market_spread`
Compare prices across regions.

```python
@server.tool()
async def market_spread(
    items: list[str],
    regions: list[str] = ["jita", "amarr", "dodixie", "rens", "hek"]
) -> MarketSpreadResult:
    """
    Compare item prices across multiple regions.

    Identifies arbitrage opportunities and regional price differences.
    Uses Fuzzwork for efficient multi-region lookups.

    Returns:
        Per-item comparison showing best buy/sell regions and profit margins
    """
```

#### `market_history`
Historical price trends.

```python
@server.tool()
async def market_history(
    item: str,
    region: str = "jita",
    days: int = 30
) -> MarketHistoryResult:
    """
    Get historical price data for an item.

    Uses ESI historical endpoint (1 hour cache).
    Returns daily average, low, high, volume, and order count.

    Args:
        item: Item name
        region: Region for history
        days: Number of days (max 365)

    Returns:
        Daily price points with trend analysis
    """
```

#### `market_valuation`
Batch valuation for inventories with EVE clipboard support.

```python
@server.tool()
async def market_valuation(
    items: list[dict] | str,    # List of {name, quantity} OR raw clipboard text
    price_type: str = "sell",   # "buy" (instant sell) or "sell" (instant buy)
    region: str = "jita"
) -> MarketValuationResult:
    """
    Calculate total value of an item list.

    Useful for loot valuation, cargo appraisal, and inventory pricing.
    Uses Fuzzwork aggregates for fast batch pricing.

    Supports multiple input formats:
    - List of dicts: [{"name": "Tritanium", "quantity": 1000000}]
    - EVE clipboard (tab-separated): "Tritanium\t1000000\nPyerite\t500000"
    - EVE inventory format: "Tritanium    Quantity: 1,000,000"

    Args:
        items: Item list or clipboard text
        price_type: "buy" for instant sell value, "sell" for instant buy cost
        region: Trade hub for pricing

    Returns:
        Per-item values and total with confidence estimate
    """
```

**EVE Clipboard Parsing:**
```python
def parse_eve_clipboard(text: str) -> list[ValuationItem]:
    """
    Parse EVE Online clipboard formats.

    Supports:
    - Tab-separated: "Item Name\tQuantity"
    - Inventory window: "Item Name    Quantity: 1,000"
    - Asset list: "Item Name (packaged)    Quantity: 1,000"
    - Multi-buy: "Item Name x100"
    """
    items = []
    for line in text.strip().split('\n'):
        # Try tab-separated first
        if '\t' in line:
            parts = line.split('\t')
            name = parts[0].strip()
            qty = parse_quantity(parts[1]) if len(parts) > 1 else 1
        # Try "Quantity: X" format
        elif 'Quantity:' in line:
            match = re.match(r'(.+?)\s+Quantity:\s*([\d,]+)', line)
            if match:
                name = match.group(1).strip().rstrip('(packaged)')
                qty = parse_quantity(match.group(2))
        # Try "x100" format
        elif re.search(r'\sx\d+$', line):
            match = re.match(r'(.+?)\s+x(\d+)$', line)
            if match:
                name = match.group(1).strip()
                qty = int(match.group(2))
        else:
            name = line.strip()
            qty = 1

        if name:
            items.append(ValuationItem(name=name, quantity=qty))

    return items
```

---

## On-Demand Refresh Strategy

Following the `ActivityCache` pattern, market data refreshes on-demand rather than via background jobs. This approach:

- Avoids resource consumption when idle
- Simplifies state management
- Aligns with MCP's request-driven model
- Works with Claude Code's process lifecycle

### MarketCache Implementation

```python
class MarketCache:
    """
    Multi-layer cache for market data with on-demand refresh.

    Follows ActivityCache pattern: refresh on first stale query,
    not proactively. Uses asyncio.Lock to prevent duplicate fetches.

    - Fuzzwork prices: 15 minute TTL (pre-aggregated, low cost)
    - ESI orders: 5 minute TTL (matches ESI cache headers)
    - ESI history: 1 hour TTL (daily data, slow changing)
    """

    def __init__(
        self,
        fuzzwork_ttl: int = 900,    # 15 minutes
        orders_ttl: int = 300,       # 5 minutes
        history_ttl: int = 3600      # 1 hour
    ):
        self._fuzzwork_prices: dict[str, dict[int, ItemPrice]] = {}
        self._esi_orders: dict[tuple[int, int], list[MarketOrder]] = {}
        self._esi_history: dict[tuple[int, int], list[HistoryPoint]] = {}

        # Per-key timestamps for granular TTL
        self._fuzzwork_timestamps: dict[str, float] = {}
        self._orders_timestamps: dict[tuple[int, int], float] = {}
        self._history_timestamps: dict[tuple[int, int], float] = {}

        # Locks prevent duplicate fetches (one per cache layer)
        self._fuzzwork_lock = asyncio.Lock()
        self._orders_lock = asyncio.Lock()
        self._history_lock = asyncio.Lock()

        # Clients
        self._fuzzwork: FuzzworkClient | None = None
        self._esi: ESIClient | None = None

    async def get_prices(
        self,
        type_ids: list[int],
        region_id: int
    ) -> dict[int, ItemPrice]:
        """
        Get prices with automatic freshness management.

        1. Check in-memory cache
        2. If fresh (<15 min), return cached
        3. If stale, fetch from Fuzzwork and update cache
        4. If Fuzzwork fails, try ESI regional orders
        5. If ESI fails, return stale data with warning
        """
        cache_key = f"{region_id}"

        # Check if we have fresh data
        if self._is_fuzzwork_fresh(cache_key, type_ids):
            return self._get_cached_prices(cache_key, type_ids)

        # Need to refresh - acquire lock to prevent duplicate fetches
        async with self._fuzzwork_lock:
            # Double-check after acquiring lock
            if self._is_fuzzwork_fresh(cache_key, type_ids):
                return self._get_cached_prices(cache_key, type_ids)

            return await self._refresh_prices(type_ids, region_id)

    async def _refresh_prices(
        self,
        type_ids: list[int],
        region_id: int
    ) -> dict[int, ItemPrice]:
        """Refresh prices with fallback chain."""
        cache_key = f"{region_id}"
        warnings = []

        # Try Fuzzwork first
        try:
            client = self._get_fuzzwork_client()
            # Run sync HTTP in executor (matches ActivityCache pattern)
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(
                None,
                client.get_aggregates,
                type_ids,
                region_id
            )
            self._update_fuzzwork_cache(cache_key, data)
            logger.debug("Refreshed %d prices from Fuzzwork", len(data))
            return data
        except FuzzworkError as e:
            logger.warning("Fuzzwork unavailable: %s", e)
            warnings.append(f"fuzzwork_error: {e}")

        # Fallback: ESI regional orders
        try:
            client = self._get_esi_client()
            data = await self._aggregate_from_esi_orders(type_ids, region_id)
            self._update_fuzzwork_cache(cache_key, data)  # Cache as if from Fuzzwork
            logger.debug("Computed %d prices from ESI orders", len(data))
            return data
        except ESIError as e:
            logger.warning("ESI orders unavailable: %s", e)
            warnings.append(f"esi_error: {e}")

        # Last resort: return stale data if available
        stale = self._get_cached_prices(cache_key, type_ids, allow_stale=True)
        if stale:
            for item in stale.values():
                item.warnings = warnings + ["stale_data"]
            return stale

        raise MarketDataUnavailable("All data sources failed", warnings=warnings)
```

### SQLite Async Handling

Following the existing pattern in `activity.py`, SQLite operations run in an executor:

```python
async def _query_local_db(self, type_ids: list[int], region_id: int) -> dict:
    """Query local SQLite database via executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        self._sync_query_db,
        type_ids,
        region_id
    )

def _sync_query_db(self, type_ids: list[int], region_id: int) -> dict:
    """Synchronous SQLite query."""
    conn = sqlite3.connect(self.db_path)
    try:
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(type_ids))
        cursor.execute(f'''
            SELECT type_id, is_buy, weighted_avg, min_price, max_price,
                   stddev, median, volume, order_count, percentile
            FROM aggregates
            WHERE region_id = ? AND type_id IN ({placeholders})
        ''', [region_id] + type_ids)
        return {row[0]: self._row_to_price(row) for row in cursor.fetchall()}
    finally:
        conn.close()
```

---

## Bulk Data Seeding Strategy

### Available Bulk Data Sources

| Source | URL | Update Freq | Size | Contents |
|--------|-----|-------------|------|----------|
| Fuzzwork Aggregates | `market.fuzzwork.co.uk/aggregatecsv.csv.gz` | ~30 min | ~24MB | All market aggregates |
| EVE Ref Orders | `data.everef.net/market-orders/` | 2x hourly | ~500MB | Full order snapshots |
| EVE Ref History | `data.everef.net/market-history/` | Daily | Varies | Historical price data |
| Fuzzwork SDE | `fuzzwork.co.uk/dump/latest/` | Per patch | ~100MB | Type IDs, stations, regions |

### Explicit Seeding (User-Initiated)

Database seeding is an explicit CLI command, not automatic. This avoids surprise downloads on first use:

```bash
# Initial seed (user runs explicitly)
uv run aria-esi market-seed

# Force refresh from bulk sources
uv run aria-esi market-seed --force

# Check database status
uv run aria-esi market-status

# Seed types only (smaller download)
uv run aria-esi market-seed --types-only
```

### Database Schema

```sql
-- Price aggregates (bulk seeded from Fuzzwork CSV)
CREATE TABLE aggregates (
    region_id INTEGER,
    type_id INTEGER,
    is_buy INTEGER,  -- 0=sell, 1=buy
    weighted_avg REAL,
    min_price REAL,
    max_price REAL,
    stddev REAL,
    median REAL,
    volume INTEGER,
    order_count INTEGER,
    percentile REAL,
    updated_at TEXT,
    PRIMARY KEY (region_id, type_id, is_buy)
);

-- Type ID lookup (seeded from SDE)
CREATE TABLE types (
    type_id INTEGER PRIMARY KEY,
    name TEXT,
    name_lower TEXT,  -- For case-insensitive lookup
    group_id INTEGER,
    market_group_id INTEGER
);
CREATE INDEX idx_types_name ON types(name_lower);

-- Common items for cache pre-warming
CREATE TABLE common_items (
    type_id INTEGER PRIMARY KEY,
    category TEXT  -- 'mineral', 'salvage', 'pi', 'fuel', etc.
);

-- Metadata for staleness tracking
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);
```

### Storage Requirements

| Data | Estimated Size | Notes |
|------|----------------|-------|
| Aggregates (all regions) | ~50MB | Refreshed on-demand |
| Type IDs (SDE) | ~10MB | Updated per game patch |
| Common items | ~1KB | Pre-populated list |
| **Total (minimal)** | ~60MB | Aggregates + types |

---

## Rate Limiting Strategy

### Fuzzwork Client

```python
class FuzzworkClient:
    """
    Async client for Fuzzwork Market API with rate limiting.
    """

    BASE_URL = "https://market.fuzzwork.co.uk"

    # Rate limits (conservative, per Fuzzwork's "reasonable usage" request)
    MAX_REQUESTS_PER_MINUTE = 30
    MAX_TYPES_PER_REQUEST = 100
    MIN_REQUEST_INTERVAL = 2.0  # seconds

    def __init__(self):
        self._last_request_time = 0
        self._request_count = 0
        self._minute_start = 0

    async def get_aggregates(
        self,
        type_ids: list[int],
        region_id: int | None = None,
        station_id: int | None = None
    ) -> dict[int, ItemAggregate]:
        """
        Fetch aggregated prices with rate limiting.

        Args:
            type_ids: List of type IDs (will be chunked if > MAX_TYPES_PER_REQUEST)
            region_id: Region to query (e.g., 10000002 for The Forge)
            station_id: Station to query (e.g., 60003760 for Jita 4-4)

        Returns:
            Dict mapping type_id to buy/sell aggregates
        """
        await self._enforce_rate_limit()

        # Chunk large requests
        if len(type_ids) > self.MAX_TYPES_PER_REQUEST:
            results = {}
            for chunk in self._chunk(type_ids, self.MAX_TYPES_PER_REQUEST):
                chunk_result = await self._fetch_aggregates(chunk, region_id, station_id)
                results.update(chunk_result)
                await self._enforce_rate_limit()
            return results

        return await self._fetch_aggregates(type_ids, region_id, station_id)

    async def _enforce_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        now = time.time()

        # Reset counter each minute
        if now - self._minute_start > 60:
            self._request_count = 0
            self._minute_start = now

        # Check per-minute limit
        if self._request_count >= self.MAX_REQUESTS_PER_MINUTE:
            sleep_time = 60 - (now - self._minute_start)
            logger.debug("Rate limit reached, sleeping %.1fs", sleep_time)
            await asyncio.sleep(sleep_time)
            self._request_count = 0
            self._minute_start = time.time()

        # Enforce minimum interval
        elapsed = now - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            await asyncio.sleep(self.MIN_REQUEST_INTERVAL - elapsed)

        self._last_request_time = time.time()
        self._request_count += 1
```

---

## Error Classification

### Error Types

```python
from enum import Enum

class ErrorType(Enum):
    TRANSIENT = "transient"    # Retry after delay
    PERMANENT = "permanent"    # Fail fast, don't retry
    DEGRADED = "degraded"      # Return stale data with warning

class MarketError(Exception):
    """Base class for market errors."""
    def __init__(self, message: str, error_type: ErrorType, retryable: bool = False):
        self.message = message
        self.error_type = error_type
        self.retryable = retryable
        super().__init__(message)

class FuzzworkError(MarketError):
    """Fuzzwork API error."""
    pass

class ESIError(MarketError):
    """ESI API error."""
    pass

class TypeNotFoundError(MarketError):
    """Item type could not be resolved."""
    def __init__(self, name: str, suggestions: list[str] = None):
        super().__init__(
            f"Could not find item: {name}",
            ErrorType.PERMANENT,
            retryable=False
        )
        self.suggestions = suggestions or []
```

### Error Handling Matrix

| Error | Classification | Action |
|-------|----------------|--------|
| Fuzzwork timeout | TRANSIENT | Retry once, then fall back to ESI |
| Fuzzwork 5xx | TRANSIENT | Fall back to ESI immediately |
| Fuzzwork 4xx | PERMANENT | Log error, fall back to ESI |
| ESI timeout | TRANSIENT | Retry with exponential backoff |
| ESI 5xx | TRANSIENT | Retry once, then return stale |
| ESI 420 (rate limited) | TRANSIENT | Wait and retry |
| Type ID not found | PERMANENT | Return error with suggestions |
| Region not found | PERMANENT | Default to Jita with warning |
| All sources failed | DEGRADED | Return stale data if available |

---

## Logging & Monitoring

### Logging Strategy

```python
import logging
import time
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger("aria_market")

@dataclass
class MarketMetrics:
    """Metrics for market data operations."""
    cache_hits: int = 0
    cache_misses: int = 0
    fuzzwork_requests: int = 0
    fuzzwork_errors: int = 0
    esi_requests: int = 0
    esi_errors: int = 0
    total_items_priced: int = 0
    avg_response_time_ms: float = 0

# Module-level metrics singleton
_metrics = MarketMetrics()

def log_request(
    source: Literal["fuzzwork", "esi", "cache"],
    operation: str,
    duration_ms: float,
    item_count: int,
    success: bool,
    error: str | None = None
):
    """Log market data request with metrics."""
    global _metrics

    if source == "cache":
        if success:
            _metrics.cache_hits += item_count
        else:
            _metrics.cache_misses += item_count
    elif source == "fuzzwork":
        _metrics.fuzzwork_requests += 1
        if not success:
            _metrics.fuzzwork_errors += 1
    elif source == "esi":
        _metrics.esi_requests += 1
        if not success:
            _metrics.esi_errors += 1

    if success:
        _metrics.total_items_priced += item_count

    # Log at appropriate level
    if success:
        logger.debug(
            "%s %s: %d items in %.1fms",
            source, operation, item_count, duration_ms
        )
    else:
        logger.warning(
            "%s %s failed: %s (%.1fms)",
            source, operation, error, duration_ms
        )

def get_metrics() -> MarketMetrics:
    """Get current metrics for diagnostics."""
    return _metrics
```

### Log Output Examples

```
DEBUG aria_market: cache get_prices: 5 items in 0.3ms
DEBUG aria_market: fuzzwork get_aggregates: 50 items in 245.2ms
WARNING aria_market: fuzzwork get_aggregates failed: timeout (5001.2ms)
DEBUG aria_market: esi get_orders fallback: 50 items in 1823.5ms
INFO aria_market: Bulk seed complete: 1,250,000 rows in 4.2s
```

---

## Integration with Existing Skills

### Updated `/price` Skill

The `/price` skill uses MCP tools when available:

```markdown
## Tool Selection

When MCP market tools are available, prefer them:

1. **Single item, quick lookup**: Use `market_prices(["Tritanium"], region="jita")`
2. **Multiple items**: Use `market_prices(items, region="jita")` (batch)
3. **Need order details**: Use `market_orders(item, region="jita")`
4. **Historical trend**: Use `market_history(item, region="jita")`

When MCP unavailable, fall back to CLI:
```bash
uv run aria-esi price "Tritanium" --jita
```
```

### `/lp-store` Integration

The `/lp-store` skill can use market prices for ISK/LP calculations:

```python
# In lp-store skill implementation
async def calculate_isk_per_lp(offer: LPOffer, region: str = "jita") -> float:
    """
    Calculate ISK/LP ratio for an LP store offer.

    Uses market_prices to get current sell price, then:
    ISK/LP = (sell_price - isk_cost) / lp_cost
    """
    prices = await market_prices([offer.item_name], region=region)
    if not prices.items:
        return 0.0

    sell_price = prices.items[0].sell.min
    profit = sell_price - offer.isk_cost
    return profit / offer.lp_cost if offer.lp_cost > 0 else 0.0
```

### New Skills

| Skill | MCP Tool | Purpose |
|-------|----------|---------|
| `/price` | `market_prices` | Quick price lookups (existing, enhanced) |
| `/appraise` | `market_valuation` | Inventory/loot valuation (EVE clipboard support) |
| `/market-compare` | `market_spread` | Cross-region price comparison |
| `/market-trend` | `market_history` | Price trend analysis |

### Route Value Integration (Future)

Consider a `market_route_value` tool for gank risk assessment:

```python
@server.tool()
async def market_route_value(
    items: list[dict],          # Cargo items
    route: list[str],           # System names
    price_type: str = "sell"
) -> RouteValueResult:
    """
    Estimate cargo value along a route.

    Useful for:
    - Gank risk assessment (high-value cargo through Uedama)
    - Insurance decisions
    - Route security planning

    Returns:
        Total value and per-system risk assessment
    """
```

---

## Trade Hub Constants

Pre-configured trade hub mappings:

```python
TRADE_HUBS = {
    "jita": {
        "region_id": 10000002,
        "region_name": "The Forge",
        "station_id": 60003760,
        "station_name": "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
        "system_id": 30000142
    },
    "amarr": {
        "region_id": 10000043,
        "region_name": "Domain",
        "station_id": 60008494,
        "station_name": "Amarr VIII (Oris) - Emperor Family Academy",
        "system_id": 30002187
    },
    "dodixie": {
        "region_id": 10000032,
        "region_name": "Sinq Laison",
        "station_id": 60011866,
        "station_name": "Dodixie IX - Moon 20 - Federation Navy Assembly Plant",
        "system_id": 30002659
    },
    "rens": {
        "region_id": 10000030,
        "region_name": "Heimatar",
        "station_id": 60004588,
        "station_name": "Rens VI - Moon 8 - Brutor Tribe Treasury",
        "system_id": 30002510
    },
    "hek": {
        "region_id": 10000042,
        "region_name": "Metropolis",
        "station_id": 60005686,
        "station_name": "Hek VIII - Moon 12 - Boundless Creation Factory",
        "system_id": 30002053
    }
}
```

---

## Type ID Resolution

### Hybrid Strategy (Recommended)

```python
class TypeResolver:
    """
    Resolve item names to type IDs with local cache + ESI fallback.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._memory_cache: dict[str, int] = {}

    async def resolve(self, name: str) -> tuple[int | None, str | None]:
        """
        Resolve item name to type ID.

        Returns:
            (type_id, canonical_name) or (None, None) if not found
        """
        name_lower = name.lower().strip()

        # 1. Check memory cache
        if name_lower in self._memory_cache:
            return self._memory_cache[name_lower], name

        # 2. Check local database
        type_id, canonical = await self._query_local(name_lower)
        if type_id:
            self._memory_cache[name_lower] = type_id
            return type_id, canonical

        # 3. Fall back to ESI
        type_id, canonical = await self._query_esi(name)
        if type_id:
            self._memory_cache[name_lower] = type_id
            # Learn into local database for next time
            await self._insert_type(type_id, canonical)
            return type_id, canonical

        return None, None

    async def resolve_batch(self, names: list[str]) -> dict[str, int]:
        """Resolve multiple names efficiently."""
        results = {}
        missing = []

        # Check cache first
        for name in names:
            name_lower = name.lower().strip()
            if name_lower in self._memory_cache:
                results[name] = self._memory_cache[name_lower]
            else:
                missing.append(name)

        # Batch query local DB for missing
        if missing:
            local_results = await self._query_local_batch(missing)
            results.update(local_results)
            missing = [n for n in missing if n not in local_results]

        # ESI fallback for still-missing
        if missing:
            esi_results = await self._query_esi_batch(missing)
            results.update(esi_results)

        return results
```

### Pre-warming Common Items

On database seed, pre-warm the type cache with frequently-queried items:

```python
COMMON_ITEMS = {
    "minerals": ["Tritanium", "Pyerite", "Mexallon", "Isogen", "Nocxium", "Zydrine", "Megacyte", "Morphite"],
    "ice": ["Heavy Water", "Liquid Ozone", "Strontium Clathrates", "Helium Isotopes"],
    "pi_p1": ["Bacteria", "Biofuels", "Biomass", "Chiral Structures"],
    "salvage": ["Alloyed Tritanium Bar", "Armor Plates", "Broken Drone Transceiver"],
    "fuel": ["Nitrogen Fuel Block", "Hydrogen Fuel Block", "Helium Fuel Block", "Oxygen Fuel Block"],
}
```

---

## Implementation Phases

### Phase 1: CLI Foundation (Validate Approach)

Build CLI commands first to validate Fuzzwork integration before MCP:

1. Implement `FuzzworkClient` with rate limiting
2. Implement `MarketDatabase` with SQLite backend
3. Add CLI: `uv run aria-esi market-seed`
4. Add CLI: `uv run aria-esi market-status`
5. Add CLI: `uv run aria-esi price-batch items.txt`
6. Create shared Pydantic models in `aria_esi/models/market.py`

**Deliverables:**
```bash
# Seed database
uv run aria-esi market-seed
> Downloading Fuzzwork aggregates... 24.2MB
> Importing 1,250,000 rows... done (4.2s)
> Downloading SDE types... 8.1MB
> Importing 47,000 types... done (1.1s)

# Check status
uv run aria-esi market-status
> Aggregates: 1,250,000 rows, 15m old
> Types: 47,000 items loaded
> Cache: 0 items in memory

# Batch price check
uv run aria-esi price-batch minerals.txt --jita
> Tritanium: 4.10 sell / 3.95 buy (3.8% spread)
> Pyerite: 8.20 sell / 7.85 buy (4.5% spread)
> ...
```

### Phase 2: MCP Integration

Add market tools to existing `aria-universe` server:

1. Create `aria_esi/mcp/market/` package
2. Implement `MarketCache` with on-demand refresh
3. Implement `market_prices` tool
4. Implement `market_orders` tool
5. Register tools in `aria_esi/mcp/server.py`
6. Implement `market_cache_status` diagnostic tool

### Phase 3: Analysis Tools

1. Implement `market_spread` for cross-region comparison
2. Implement `market_valuation` with EVE clipboard parsing
3. Implement `market_history` (ESI historical endpoint)
4. Add trend analysis helpers

### Phase 4: Skill Integration

1. Update `/price` skill to prefer MCP tools
2. Create `/appraise` skill with clipboard support
3. Create `/market-compare` skill for arbitrage
4. Integrate with `/lp-store` for ISK/LP calculations
5. Document MCP fallback behavior in CLAUDE.md

### Phase 5: Polish & Optimization

1. Add fuzzy name matching for item lookups
2. Pre-warm cache with common items on startup
3. Performance testing and tuning
4. Add route value integration (optional)

---

## Testing Strategy

### Unit Tests

```python
# test_market_cache.py
async def test_cache_ttl_expiration():
    """Cache returns stale after TTL expires."""
    cache = MarketCache(fuzzwork_ttl=1)  # 1 second TTL
    await cache.set_prices("jita", {34: mock_price})
    await asyncio.sleep(1.1)
    assert cache.is_stale("jita", [34])

async def test_fallback_chain():
    """Falls back through sources on failure."""
    cache = MarketCache()
    cache._fuzzwork_client = MockFuzzwork(fail=True)
    cache._esi_client = MockESI(fail=False)

    result = await cache.get_prices([34], 10000002)
    assert result[34].source == "esi_orders"

async def test_rate_limiting():
    """Respects rate limits."""
    client = FuzzworkClient()
    start = time.time()
    for _ in range(5):
        await client._enforce_rate_limit()
    elapsed = time.time() - start
    assert elapsed >= 4 * client.MIN_REQUEST_INTERVAL
```

### Integration Tests

```python
# test_market_integration.py
@pytest.mark.integration
async def test_real_fuzzwork_aggregates():
    """Fetch real data from Fuzzwork."""
    client = FuzzworkClient()
    result = await client.get_aggregates([34, 35], region_id=10000002)
    assert 34 in result
    assert result[34].buy.max > 0
    assert result[34].sell.min > 0

@pytest.mark.integration
async def test_type_resolution_esi():
    """Resolve type via ESI."""
    resolver = TypeResolver("test.db")
    type_id, name = await resolver.resolve("Tritanium")
    assert type_id == 34
    assert name == "Tritanium"
```

### Load Tests

- 100-item batch pricing
- Concurrent tool invocations
- Cache effectiveness under load

---

## Security Considerations

- No authentication required (public market data)
- No user secrets stored or transmitted
- Rate limit tracking prevents API abuse
- Fuzzwork TOS compliance (conservative rate limits)
- Local database contains only public data

---

## Appendix: API Reference

### ESI Market Endpoints

| Endpoint | Parameters | Cache | Notes |
|----------|------------|-------|-------|
| `GET /markets/prices/` | - | 3600s | All items, ~2MB response |
| `GET /markets/{region_id}/orders/` | type_id, order_type, page | 300s | Paginated |
| `GET /markets/{region_id}/history/` | type_id | 3600s | 30 days daily data |
| `GET /markets/groups/` | - | 86400s | Market tree structure |
| `GET /markets/groups/{market_group_id}/` | - | 86400s | Single group details |
| `GET /markets/{region_id}/types/` | page | 86400s | Type IDs with orders |

### Fuzzwork Endpoints

| Endpoint | Parameters | Notes |
|----------|------------|-------|
| `/aggregates/` | region, station, types | Pre-aggregated buy/sell |
| `/api/orderset` | - | Current snapshot version |

---

## Accepted Review Recommendations

The following changes are incorporated based on architectural review:

### 1. Add `aiosqlite` to Dependencies

Add `aiosqlite>=0.20.0` to the `universe` optional-dependencies in `pyproject.toml`:

```toml
universe = [
    "igraph>=0.11.0",
    "numpy>=1.24.0",
    "pydantic>=2.0.0",
    "mcp>=1.0.0",
    "aiosqlite>=0.20.0",  # Added for market cache
]
```

This enables native async SQLite operations without thread pool overhead, replacing the executor pattern:

```python
# Instead of run_in_executor:
import aiosqlite
async with aiosqlite.connect(self.db_path) as db:
    async with db.execute(query, params) as cursor:
        return {row[0]: self._row_to_price(row) async for row in cursor}
```

### 2. Revised Phase Sequencing

**Phase 3** now includes `market_valuation` (moved from Phase 4) as it's a core use case for inventory/loot appraisal.

**Phase 4** now includes `market_route_value` (moved from "Future") to support ARIA's safety-first directive with cargo value + gatecamp risk integration.

Updated phase summary:

| Phase | Focus | Key Deliverables |
|-------|-------|------------------|
| 1 | CLI Foundation | `market-seed`, `market-status`, `price-batch`, Fuzzwork client |
| 2 | MCP Integration | `market_prices`, `market_orders`, `market_cache_status` |
| 3 | Valuation & Analysis | `market_valuation` (EVE clipboard), `market_spread` |
| 4 | Route Integration | `market_route_value`, `/lp-store` ISK/LP calculations |
| 5 | Polish | `market_history`, fuzzy matching, pre-warming, performance tuning |

### 3. Add Explicit Freshness Field

All price response models include a `freshness` field alongside `cache_age_seconds`:

```python
class MarketPricesResult(BaseModel):
    """Result from market_prices tool."""
    items: list[ItemPrice]
    region: str
    station: str | None
    source: Literal["fuzzwork", "esi_orders", "esi_global", "local_cache"]
    cache_age_seconds: int
    freshness: Literal["fresh", "recent", "stale"]  # Added
    warnings: list[str] = []
```

Freshness thresholds:

| Freshness | Fuzzwork Age | ESI Orders Age | Description |
|-----------|--------------|----------------|-------------|
| `fresh` | < 5 min | < 2 min | Data within normal update window |
| `recent` | 5-15 min | 2-5 min | Usable but approaching staleness |
| `stale` | > 15 min | > 5 min | May not reflect current market |

Implementation:

```python
def compute_freshness(cache_age: int, source: str) -> str:
    """Compute freshness level based on source and age."""
    if source == "fuzzwork":
        if cache_age < 300:
            return "fresh"
        elif cache_age < 900:
            return "recent"
        return "stale"
    elif source == "esi_orders":
        if cache_age < 120:
            return "fresh"
        elif cache_age < 300:
            return "recent"
        return "stale"
    return "stale"  # Unknown source treated as stale
```

### 4. Pre-Seeded Database for Cold Start

Consider shipping a minimal pre-seeded SQLite database with the package to eliminate cold-start latency for common queries.

**Contents (~2MB compressed):**

| Data | Items | Purpose |
|------|-------|---------|
| Type IDs | ~5,000 | Common tradeable items only |
| Jita aggregates | ~5,000 | Most-traded items in primary hub |
| Trade hub metadata | 5 | Station/region constants |

**Pre-seed categories:**

```python
PRESEED_CATEGORIES = [
    "minerals",      # Tritanium through Morphite
    "ice_products",  # Fuel components
    "pi_p1_p4",      # Planetary materials
    "fuel_blocks",   # Starbase/structure fuel
    "common_salvage", # High-volume salvage
    "plex_injectors", # PLEX, skill injectors
    "t2_components",  # Common manufacturing inputs
]
```

**Implementation approach:**

1. Generate `market_seed.db` during release build
2. Ship as package data in `aria_esi/data/market_seed.db`
3. On first run, copy to user data directory if no existing database
4. `market-seed` command refreshes/replaces with full dataset

**User experience:**

```bash
# First run (pre-seeded):
$ uv run aria-esi price Tritanium --jita
Tritanium: 4.10 sell / 3.95 buy (Jita)
Source: pre-seeded (7 days old) - run 'aria-esi market-seed' for fresh data

# After seeding:
$ uv run aria-esi market-seed
Downloading Fuzzwork aggregates... 24.2MB
Importing 1,250,000 rows... done (4.2s)

$ uv run aria-esi price Tritanium --jita
Tritanium: 4.12 sell / 3.98 buy (Jita)
Source: fuzzwork (2 min old)
```

---

## References

### Official Sources
- [ESI Introduction](https://docs.esi.evetech.net/docs/esi_introduction.html)
- [ESI Interactive Explorer](https://esi.evetech.net/ui/)
- [EVE Developer Portal](https://developers.eveonline.com/docs/services/esi/overview/)

### Third-Party Data Sources
- [Fuzzwork Market API](https://market.fuzzwork.co.uk/api/) - Aggregated market data
- [Fuzzwork SDE Dumps](https://www.fuzzwork.co.uk/dump/) - Static data exports (SQLite, CSV, SQL)
- [EVE Ref Datasets](https://docs.everef.net/datasets/) - Market orders, history, killmails
- [EVE Ref Market Orders](https://docs.everef.net/datasets/market-orders.html) - Twice-hourly snapshots
- [EVE Ref Market History](https://docs.everef.net/datasets/market-history.html) - Daily archives

### Bulk Download URLs
- Fuzzwork Aggregates: `https://market.fuzzwork.co.uk/aggregatecsv.csv.gz`
- Fuzzwork Type IDs: `https://www.fuzzwork.co.uk/dump/latest/invTypes.csv.bz2`
- EVE Ref Orders: `https://data.everef.net/market-orders/`
- EVE Ref History: `https://data.everef.net/market-history/`
