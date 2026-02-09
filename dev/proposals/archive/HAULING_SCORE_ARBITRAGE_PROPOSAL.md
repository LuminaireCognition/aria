# Hauling Score Arbitrage Proposal

## Executive Summary

The current arbitrage scanner ranks opportunities by **profit percentage**, which produces misleading results for haulers. High-margin items like Tritanium appear at the top despite being impractical to transport due to low value density. Meanwhile, genuinely profitable hauling opportunities (high-value, compact items with good liquidity) are buried or excluded.

This proposal introduces a **Hauling Score** algorithm that ranks opportunities by **expected profit per m³ of transport capacity**, adjusted for market liquidity. The score answers the question every trader asks: *"What should I put in my cargo hold to maximize ISK earned this trip?"*

**Key Changes:**
1. Add `volume_m3` + `packaged_volume_m3` (prefer packaged volume where applicable)
2. Integrate `market_history` data for daily trade volume
3. Implement liquidity-adjusted scoring formula
4. New `cargo_capacity` parameter for hauler **cargo hold capacity**
   - **Note on specialized holds:** Only include fleet hangar or specialized holds if the item type can actually be stored there. Most trade goods (modules, ammo, charges) can only go in the main cargo hold. Ships can go in ship maintenance arrays. Ore/ice/gas require specialized holds. When in doubt, use only cargo hold capacity.
5. New sort modes: `margin`, `profit_density`, `hauling_score`

---

## Problem Statement

### Current Behavior

The V1 arbitrage scanner sorts by `profit_pct DESC`:

```sql
ORDER BY profit_pct DESC
```

This produces results like:

| Item | Margin | Volume/Unit | Available | Problem |
|------|--------|-------------|-----------|---------|
| Tritanium | 8.2% | 0.01 m³ | 50,000,000 | 8.2% of 5 ISK = 0.41 ISK/unit |
| Pyerite | 6.1% | 0.01 m³ | 12,000,000 | Low unit value |
| Mexallon | 5.8% | 0.01 m³ | 8,000,000 | Low unit value |
| PLEX | 2.1% | 0.01 m³ | 847 | Excellent: 2.1% of 5B = 105M/unit |

A hauler with 60,000 m³ transport capacity sees Tritanium as the "best" opportunity, but:
- 60,000 m³ of Tritanium = 6,000,000 units × 5 ISK × 8.2% = **2.46M ISK profit**
- 60,000 m³ of PLEX (if available) = 847 units × 5B ISK × 2.1% = **89B ISK profit**

The 2.1% margin item is **36,000x more profitable** for the same cargo space.

### The Core Issue

**Profit percentage ignores three critical factors:**

1. **Value Density** - ISK per m³ of the item
2. **Absolute Profit** - ISK earned per unit (not just percentage)
3. **Liquidity** - Can you actually sell this quantity?

### What Traders Actually Need

A trader with a specific ship (transport capacity = cargo + specialized holds) wants to know:
> "Which items give me the highest ISK per trip, given what I can carry and what will actually sell?"

---

## Proposed Algorithm: Hauling Score

### Core Formula

```
hauling_score = expected_profit / cargo_capacity_m3
```

Where:
- `expected_profit` = `net_profit_per_unit × safe_quantity`
- `cargo_used` = `safe_quantity × effective_volume`
- `packaged_volume_m3` = packaged volume when applicable (ships and modules that can be packaged)
- `effective_volume` = `packaged_volume_m3` if present/positive, else `volume_m3` if present/positive, else `DEFAULT_VOLUME_M3`
- `profit_density` = `net_profit_per_unit / effective_volume`
- `fill_ratio` = `cargo_used / cargo_capacity_m3`
- `hauling_score` = `profit_density × fill_ratio` (equivalently `expected_profit / cargo_capacity_m3`)
- `cargo_capacity_m3` = hauler's usable cargo capacity for this item type
  - **Warning:** Specialized holds (ore, fuel, fleet hangar) only accept specific item types. For most arbitrage items, use only the main cargo hold capacity. Including inapplicable holds will overestimate `safe_quantity` and `hauling_score`.
- `safe_quantity` = `min(max_by_cargo, max_by_liquidity, effective_buy, effective_sell)`

The buy/sell availability caps ensure we never plan to buy more than supply or sell more than demand. If only one side is available, proxy the missing side from the available side and record the source in `availability_source`.

### Liquidity Factor

The **10% rule**: Taking more than 10% of daily volume risks:
1. Moving the buy price against you (demand spike)
2. Crashing the sell price (supply flood)
3. Slow sales (inventory sitting)

```python
LIQUIDITY_FACTOR = 0.10  # Conservative: 10% of daily volume
```

For low-volume items, clamp the liquidity cap to at least 1 unit when `daily_volume > 0` to avoid excluding 1-unit trades.

**Proxy fallback:** When history data is missing but market availability exists, apply the same 10% factor to `market_available`. This maintains consistency: whether using history or proxy, liquidity is capped at 10% of the reference volume.

### Fee Calculation

**All profit figures are NET profit after fees.** The hauling score uses net profit to give traders accurate expectations.

**Understanding EVE Fee Mechanics:**

Broker fees are only charged when YOU place an order. Taking existing orders incurs no broker fee:
- Buying from sell orders (taker) → No broker fee for buyer
- Selling to buy orders (taker) → No broker fee for seller
- Sales tax always applies to the seller when the transaction completes

**Trade Modes:**

| Mode | Buy Action | Sell Action | Applicable Fees |
|------|-----------|-------------|-----------------|
| `immediate` | Take sell orders | Take buy orders | Sales tax only |
| `hybrid` | Take sell orders | Place sell order | Broker fee on sell + Sales tax |
| `station_trading` | Place buy order | Place sell order | Broker fee on both + Sales tax |

For **hauling arbitrage**, the typical scenario is:
1. Travel to source region, buy items from existing sell orders (no broker fee)
2. Haul to destination region
3. Sell items - either immediately to buy orders (fastest) or via your own sell order (better price, slower)

The default mode is `immediate` (taker-taker) since haulers typically want fast turnaround.

**Fee components:**

| Fee | When Charged | Default | Notes |
|-----|--------------|---------|-------|
| Broker fee | When placing an order (maker) | 3.0% | Varies with standings (1.0% minimum) |
| Sales tax | When selling completes | 3.6% | Accounting V = 3.6%, IV = 4.0% |

**Net profit calculation by mode:**
```python
# Mode: immediate (taker-taker) - DEFAULT for hauling
# Buy from sell orders, sell to buy orders
buy_cost = buy_price                                  # No broker fee (taking order)
sell_revenue = sell_price * (1 - sales_tax_pct)       # Sales tax only
net_profit_per_unit = sell_revenue - buy_cost

# Example: Buy at 100 ISK, sell at 110 ISK, 3.6% sales tax
# buy_cost = 100 ISK
# sell_revenue = 110 * (1 - 0.036) = 110 * 0.964 = 106.04 ISK
# net_profit = 106.04 - 100 = 6.04 ISK (6.04% net margin)

# Mode: hybrid (taker-maker)
# Buy from sell orders, place your own sell order
buy_cost = buy_price                                  # No broker fee (taking order)
sell_revenue = sell_price * (1 - broker_fee_pct - sales_tax_pct)  # Broker + tax on sell
net_profit_per_unit = sell_revenue - buy_cost

# Example: Buy at 100 ISK, sell at 110 ISK, 3% broker, 3.6% sales tax
# buy_cost = 100 ISK
# sell_revenue = 110 * (1 - 0.03 - 0.036) = 110 * 0.934 = 102.74 ISK
# net_profit = 102.74 - 100 = 2.74 ISK (2.74% net margin)

# Mode: station_trading (maker-maker)
# Place buy order, place sell order (not typical for hauling)
buy_cost = buy_price * (1 + broker_fee_pct)           # Broker fee on buy
sell_revenue = sell_price * (1 - broker_fee_pct - sales_tax_pct)  # Broker + tax on sell
net_profit_per_unit = sell_revenue - buy_cost

# Example: Buy at 100 ISK, sell at 110 ISK, 3% broker, 3.6% sales tax
# buy_cost = 100 * 1.03 = 103 ISK
# sell_revenue = 110 * 0.934 = 102.74 ISK
# net_profit = 102.74 - 103 = -0.26 ISK (LOSS - need ~10% margin to break even)
```

**Important:** The trade mode dramatically affects profitability:
- `immediate` mode: ~6% gross margin → ~2.2% net profit (sales tax only)
- `hybrid` mode: ~6% gross margin → ~-1.0% net profit (LOSS - broker + tax on sell)
- `station_trading` mode: requires ~10% gross margin just to break even

**Fee impact by gross margin (with default 3% broker, 3.6% sales tax):**

| Gross Margin | Immediate Net | Hybrid Net | Station Trading Net |
|--------------|---------------|------------|---------------------|
| 5% | ~1.3% | ~-1.7% | ~-4.6% |
| 6% | ~2.2% | ~-1.0% | ~-3.8% |
| 8% | ~4.1% | ~+1.0% | ~-2.0% |
| 10% | ~6.0% | ~+2.9% | ~-0.1% |
| 12% | ~7.9% | ~+4.9% | ~+1.8% |

*Calculations use multiplicative fee math: immediate net = (1 + gross) × 0.964 - 1; hybrid net = (1 + gross) × 0.934 - 1; station_trading net = ((1 + gross) × 0.934 / 1.03) - 1. Linear approximation ("gross minus fees") overestimates net profit.*

The scanner should:
1. Default to `immediate` mode for hauling arbitrage
2. Calculate net profit based on the selected mode
3. Filter opportunities where `net_profit_per_unit <= 0`
4. Display both gross margin and net margin for transparency

**Fee parameters:** Allow users to specify their actual fee rates (based on standings and skills) and trade mode for accurate calculations. Default to `immediate` mode with 3.6% sales tax.

### Data Validation & Source Policy

This project does **not** accept model training data or memory as a source. All numeric inputs used in scoring must be grounded in authoritative sources and be locally cached where applicable:

- **Item volume** must come from SDE (`types.packaged_volume` preferred where applicable, else `types.volume`) or a local cache derived from SDE.
- **Market history (daily volume)** must come from ESI via `market_history` and be stored in `market_history_cache`.
- **Market availability** must come from aggregated market orders in our local database (sourced from ESI).
- **Fitting-based transport capacity** must come from EOS (`calculate_fit_stats`) or SDE base values when no fit is provided.

If a value is missing, **do not substitute a guessed number**. Use an explicit fallback (e.g., `DEFAULT_VOLUME_M3`) and label it as a fallback in results (see `daily_volume_source="market_proxy"`). For validation rules and source hierarchy, follow `docs/DATA_VERIFICATION.md` and `docs/DATA_SOURCES.md`.

### Complete Scoring Function

```python
# Default volume for items missing SDE data (prevents division-by-zero)
DEFAULT_VOLUME_M3 = 0.01

def calculate_hauling_score(
    net_profit_per_unit: float,   # sell_price - buy_price (NET, already fee-adjusted by caller)
    volume_m3: float | None,      # Unpacked item volume per unit (None if missing from SDE)
    packaged_volume_m3: float | None,  # Packaged volume per unit (None if not applicable)
    daily_volume: int | None,     # Average daily trade volume from history (None if missing)
    buy_available_volume: int | None,    # Units available to buy in source region (None proxies from sell)
    sell_available_volume: int | None,   # Units that can sell in destination region (None proxies from buy)
    cargo_capacity_m3: float,     # Hauler's cargo hold capacity (see note on specialized holds)
    liquidity_factor: float = 0.10,
    daily_volume_source: str = "none",  # "history" | "market_proxy" | "none"
) -> HaulingScore:
    """
    Calculate hauling score for an arbitrage opportunity.

    Returns score normalized to ISK per m³ of transport capacity,
    adjusted for market liquidity.

    Note: net_profit_per_unit should already be fee-adjusted by the caller
    (based on trade_mode: immediate, hybrid, or station_trading).
    This function does NOT apply fees - it only calculates the hauling score.
    """
    # Prefer packaged volume when available; fall back to unpacked volume, then default
    if packaged_volume_m3 and packaged_volume_m3 > 0:
        effective_volume = packaged_volume_m3
        volume_source = "sde_packaged"
    elif volume_m3 and volume_m3 > 0:
        effective_volume = volume_m3
        volume_source = "sde_volume"
    else:
        effective_volume = DEFAULT_VOLUME_M3
        volume_source = "fallback"

    # Handle None buy/sell availability with proxying
    # If one side is None, use the other as a proxy (market data may be incomplete)
    if buy_available_volume is None and sell_available_volume is None:
        # Both missing - cannot determine availability, use 0
        effective_buy = 0
        effective_sell = 0
        availability_source = "none"
    elif buy_available_volume is None:
        # Proxy buy from sell
        effective_buy = sell_available_volume
        effective_sell = sell_available_volume
        availability_source = "proxy_from_sell"
    elif sell_available_volume is None:
        # Proxy sell from buy
        effective_buy = buy_available_volume
        effective_sell = buy_available_volume
        availability_source = "proxy_from_buy"
    else:
        effective_buy = buy_available_volume
        effective_sell = sell_available_volume
        availability_source = "both_available"

    # Market availability across buy/sell regions
    market_available = min(effective_buy, effective_sell)

    # Maximum quantity limited by cargo space
    max_by_cargo = int(cargo_capacity_m3 / effective_volume)

    # Maximum quantity limited by liquidity (10% of daily volume)
    # Fallback when history is missing: use market availability as proxy (if available)
    if daily_volume is not None and daily_volume > 0:
        max_by_liquidity = max(1, int(daily_volume * liquidity_factor))
        if daily_volume_source == "none":
            daily_volume_source = "history"
    elif market_available > 0:
        # No history but we have market availability - use as proxy
        # Apply liquidity_factor for consistency with the 10% rule
        max_by_liquidity = max(1, int(market_available * liquidity_factor))
        daily_volume_source = "market_proxy"
    else:
        # Neither history nor availability - no data at all
        max_by_liquidity = 0
        daily_volume_source = "none"

    # Safe quantity is the most restrictive constraint
    # When we have data, ensure at least 1 unit; when no data, allow 0
    raw_safe_quantity = min(max_by_cargo, max_by_liquidity, effective_buy, effective_sell)
    if raw_safe_quantity <= 0:
        safe_quantity = 0
    else:
        safe_quantity = max(1, raw_safe_quantity)

    # Handle zero safe_quantity - distinguish "no data" from "no supply"
    if safe_quantity == 0:
        # "no_data" = both history and availability are missing (truly unknown)
        # "no_supply" = we have some data but market supply is zero
        if availability_source == "none" and daily_volume_source == "none":
            zero_factor = "no_data"
        else:
            zero_factor = "no_supply"

        return HaulingScore(
            score=0,
            safe_quantity=0,
            limiting_factor=zero_factor,
            limiting_factors=[zero_factor],
            daily_volume_source=daily_volume_source,
            availability_source=availability_source,
        )

    # Expected profit for this haul
    expected_profit = net_profit_per_unit * safe_quantity

    # Cargo space this quantity would use
    cargo_used = safe_quantity * effective_volume
    fill_ratio = cargo_used / cargo_capacity_m3 if cargo_capacity_m3 > 0 else 0

    # Hauling score: profit per m³ of transport capacity
    profit_density = net_profit_per_unit / effective_volume
    score = profit_density * fill_ratio

    # Identify ALL binding constraints (multiple can be equal)
    # Use effective values (after proxying) not raw parameters
    constraints = {
        "cargo": max_by_cargo,
        "liquidity": max_by_liquidity,
        "market_supply_buy": effective_buy,
        "market_supply_sell": effective_sell,
    }
    limiting_factors = [name for name, value in constraints.items() if value <= safe_quantity]

    # When proxying, only report the side that has actual data
    # (we don't know the proxied side's true availability)
    if availability_source == "proxy_from_sell" and "market_supply_buy" in limiting_factors:
        limiting_factors.remove("market_supply_buy")
    elif availability_source == "proxy_from_buy" and "market_supply_sell" in limiting_factors:
        limiting_factors.remove("market_supply_sell")

    # Primary limiting factor for simple display (most restrictive category)
    # Priority: market supply > liquidity > cargo (market supply is hardest to change)
    priority_order = ["market_supply_buy", "market_supply_sell", "liquidity", "cargo"]
    limiting_factor = "cargo"  # Default
    for factor in priority_order:
        if factor in limiting_factors:
            limiting_factor = factor
            break

    return HaulingScore(
        score=score,
        safe_quantity=safe_quantity,
        expected_profit=expected_profit,
        cargo_used=cargo_used,
        limiting_factor=limiting_factor,       # Primary factor for simple display
        limiting_factors=limiting_factors,     # All binding constraints (for detailed view)
        fill_ratio=fill_ratio,
        daily_volume_source=daily_volume_source,
        volume_source=volume_source,           # "sde_packaged" | "sde_volume" | "fallback"
        availability_source=availability_source,  # Proxy status if one side missing
    )
```

### Score Interpretation

| Score Range (ISK per m³ of transport capacity) | Interpretation |
|-------------------------------------------|----------------|
| > 100,000 | Excellent opportunity (100K+ ISK per m³ of transport capacity) |
| 10,000 - 100,000 | Good opportunity |
| 1,000 - 10,000 | Marginal (consider if route is short) |
| < 1,000 | Poor (low-value bulk goods) |

### Example Calculations

**Scenario:** Hauler with 60,000 m³ transport capacity

> **Illustrative only:** The prices and daily volumes below are examples, not authoritative data. Runtime values must come from SDE/ESI (or local caches derived from them), never model memory.

| Item | Margin | Unit Price | Vol/Unit | Daily Vol | Safe Qty | Expected Profit | Score |
|------|--------|------------|----------|-----------|----------|-----------------|-------|
| PLEX | 2.1% | 5,000,000,000 | 0.01 | 847 | 84 | 8.8B | 147K/m³ |
| Skill Injector | 3.2% | 980,000,000 | 0.01 | 1,200 | 120 | 3.8B | 63K/m³ |
| Emergent Neurovisual | 4.9% | 8,200,000 | 1.0 | 2,400 | 240 | 96M | 1.6K/m³ |
| Tritanium | 8.2% | 5.10 | 0.01 | 50,000,000 | 5,000,000 | 2.46M | 42/m³ |

Despite having the highest margin (8.2%), Tritanium scores lowest because its value density is abysmal. PLEX scores highest due to extreme value density, even with a modest 2.1% margin.

---

## Data Requirements

### New Data: Effective Volume (Packaged vs Unpacked)

**Source:** `types` table already has `volume` column; prefer `packaged_volume` when present for items that can be packaged (ships and certain modules).

**Current query lacks volume:**
```sql
SELECT ... FROM region_prices sell
JOIN region_prices buy ON ...
LEFT JOIN types t ON t.type_id = sell.type_id
-- t.volume (and packaged volume if available) exist but are not used in scoring
```

**Enhancement:** Include `t.volume` and (if available in our SDE schema) `t.packaged_volume` in arbitrage queries and results. If `packaged_volume` is not currently stored, extend the `types` import to include it from SDE.

**Preference order:** `packaged_volume` → `volume` → `DEFAULT_VOLUME_M3`.

**Fallback:** If both SDE volumes are missing or zero, use `DEFAULT_VOLUME_M3` consistently for both `profit_density` and `cargo_used`.

### New Data: Buy/Sell Available Volume

**Source:** Market order aggregates per region (buy and sell sides)

Arbitrage spans two regions, so availability should be capped by both:
- `buy_available_volume`: units you can acquire in the source region
- `sell_available_volume`: units the destination region can absorb

**Derived field:** `available_volume = min(buy_available_volume, sell_available_volume)`

### New Data: Daily Trade Volume

**Source:** ESI market history endpoint via `market_history` MCP tool

**Current state:** History data is NOT used in arbitrage detection

**Required integration:**
1. Fetch history for items in arbitrage results
2. Calculate rolling average daily volume
3. Use for liquidity calculation

**Fallback when history is missing:**
- Use `available_volume` as a proxy for `daily_volume`
- Set `daily_volume_source = "market_proxy"` to make the fallback visible
 - Treat `market_proxy` as **non-authoritative** in UI/exports (label clearly)

**Schema addition to `ArbitrageOpportunity`:**
```python
@dataclass
class ArbitrageOpportunity:
    # ... existing fields ...

    # New fields for hauling score
    item_volume_m3: float = 0.01       # Effective volume per unit (packaged preferred)
    item_packaged_volume_m3: float | None = None  # Packaged volume per unit (if applicable)
    volume_source: str | None = None   # "sde_packaged" | "sde_volume" | "fallback" (data quality visibility)
    daily_volume: int | None = None    # Avg daily trade volume (history if available)
    daily_volume_source: str | None = None  # "history" | "market_proxy"
    buy_available_volume: int | None = None   # Supply in source region
    sell_available_volume: int | None = None  # Demand in destination region
    availability_source: str | None = None    # "both_available" | "proxy_from_buy" | "proxy_from_sell" | "none"
    hauling_score: float | None = None # Calculated score (if transport capacity provided)
    safe_quantity: int | None = None   # Liquidity-adjusted quantity
    fill_ratio: float | None = None    # cargo_used / cargo_capacity_m3
    limiting_factor: str | None = None # Primary: "cargo" | "liquidity" | "market_supply_buy" | "market_supply_sell" | "no_data" | "no_supply"
    limiting_factors: list[str] | None = None  # All binding constraints (for detailed view)

    # Fee-adjusted profit fields
    gross_profit_per_unit: float | None = None  # sell_price - buy_price (before fees)
    net_profit_per_unit: float | None = None    # After broker fees and sales tax
    gross_margin_pct: float | None = None       # gross_profit / buy_price * 100
    net_margin_pct: float | None = None         # net_profit / buy_cost * 100
    broker_fee_pct: float = 0.03                # Assumed broker fee rate
    sales_tax_pct: float = 0.036                # Assumed sales tax rate
```

### History Data Caching Strategy

**Problem:** Fetching history for 50+ items is slow (50 API calls)

**Solution:** Lightweight history cache table

```sql
CREATE TABLE market_history_cache (
    type_id INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    avg_daily_volume INTEGER,
    avg_daily_isk REAL,
    volatility_pct REAL,        -- Price volatility (std dev / mean)
    updated_at INTEGER,
    PRIMARY KEY (type_id, region_id)
);
```

**Refresh strategy:**
- Market history updates once daily after downtime, so refresh logic should align to that boundary.
- Cache TTL: 24 hours (history doesn't change rapidly)
- Downtime-aware refresh: If `updated_at` is **before** the most recent daily downtime and `now` is **after** downtime, treat the cache as stale even if TTL hasn't elapsed. Use a configured DT window or ESI status metadata. This avoids showing 2-day-old history right before the daily update.
- Lazy refresh: Update when queried if stale
- Batch refresh: Background job for known trade items
 - Only cache **ESI-derived** history; no manual or heuristic inserts

---

## API Changes

### Enhanced `market_arbitrage_scan`

```python
@server.tool()
async def market_arbitrage_scan(
    # Existing parameters
    min_profit_pct: float = 5.0,
    min_volume: int = 10,
    max_results: int = 20,
    include_lowsec: bool = False,
    allow_stale: bool = False,
    force_refresh: bool = False,

    # New parameters
    cargo_capacity_m3: float | None = None,  # Hauler's total transport capacity (cargo + fleet hangar/specialized holds)
    sort_by: str = "margin",                  # "margin" | "profit_density" | "hauling_score"
    min_daily_volume: int | None = None,      # Filter illiquid items (history or proxy)
    include_history: bool = False,            # Fetch history data (slower)

    # Fee parameters (for accurate net profit calculation)
    trade_mode: str = "immediate",            # "immediate" | "hybrid" | "station_trading"
    broker_fee_pct: float = 0.03,             # Broker fee (default 3%, only used in hybrid/station_trading)
    sales_tax_pct: float = 0.036,             # Sales tax (default 3.6% for Accounting IV)
) -> ArbitrageScanResult:
    """
    Scan for arbitrage opportunities.

    All profit calculations use NET profit (after fees based on trade_mode).
    Opportunities with net_profit_per_unit <= 0 are automatically filtered.

    Args:
        cargo_capacity_m3: If provided, calculates hauling_score for each
                          opportunity based on your total transport capacity.
        sort_by: Ranking method:
                 - "margin": Net profit percentage (default, uses net_margin_pct)
                 - "profit_density": Net ISK profit per m³ of used cargo (ignores liquidity)
                 - "hauling_score": Full algorithm with liquidity + fill ratio
        min_daily_volume: Exclude items trading less than N units/day (history or proxy)
        include_history: Fetch market history for volume data (slower but accurate)
        trade_mode: How orders are executed (affects fee calculation):
                   - "immediate": Take sell orders → Take buy orders. Fees: sales tax only.
                     Best for haulers wanting fast turnaround.
                   - "hybrid": Take sell orders → Place sell orders. Fees: broker + sales tax on sell.
                     Better price but requires waiting for order to fill.
                   - "station_trading": Place buy orders → Place sell orders. Fees: broker on both + sales tax.
                     Not typical for hauling (waiting on both sides).
        broker_fee_pct: Broker fee rate (default 3%, only applies in hybrid/station_trading modes).
                       Adjust based on your faction standings and skills.
                       Minimum possible is 1% with max standings + skills.
        sales_tax_pct: Sales tax rate (default 3.6% for Accounting IV).
                      Accounting V = 3.6%, IV = 4.0%, III = 4.4%.

    Note: sort_by="hauling_score" requires cargo_capacity_m3.
          If history data is unavailable, daily_volume falls back to available_volume
          (market proxy) and daily_volume_source="market_proxy".
          min_daily_volume applies to the same source unless we add a strict-history flag.
    """
```

### New Response Fields

```python
@dataclass
class ArbitrageOpportunity:
    # Existing fields
    type_id: int
    type_name: str
    buy_region: str
    sell_region: str
    buy_price: float
    sell_price: float
    profit_per_unit: float             # DEPRECATED: Use net_profit_per_unit instead
    profit_pct: float                  # DEPRECATED: Use net_margin_pct instead
    available_volume: int              # min(buy_available_volume, sell_available_volume)
    freshness: FreshnessLevel
    confidence: ConfidenceLevel

    # New fields (V2) - Volume & Density
    item_volume_m3: float              # Effective volume per unit in m³ (packaged preferred)
    item_packaged_volume_m3: float | None  # Packaged volume per unit (if applicable)
    volume_source: str | None          # "sde_packaged" | "sde_volume" | "fallback" (data quality visibility)
    profit_density: float              # net_profit_per_unit / effective_volume

    # New fields (V2) - Fee-adjusted Profit
    gross_profit_per_unit: float       # sell_price - buy_price (before fees)
    net_profit_per_unit: float         # After fees (varies by trade_mode)
    gross_margin_pct: float            # gross_profit / buy_price * 100
    net_margin_pct: float              # net_profit / buy_cost * 100
    trade_mode: str                    # "immediate" | "hybrid" | "station_trading"
    broker_fee_pct: float              # Fee rate used (only applies in hybrid/station_trading)
    sales_tax_pct: float               # Tax rate used in calculation (default 3.6%)

    # New fields (V2) - Liquidity
    daily_volume: int | None           # From history (if available)
    daily_volume_source: str | None    # "history" | "market_proxy"
    buy_available_volume: int | None   # Supply in source region
    sell_available_volume: int | None  # Demand in destination region
    availability_source: str | None    # "both_available" | "proxy_from_buy" | "proxy_from_sell" | "none"

    # New fields (V2) - Hauling Score
    hauling_score: float | None        # If transport capacity provided
    safe_quantity: int | None          # Liquidity-adjusted quantity
    expected_profit: float | None      # net_profit_per_unit × safe_quantity
    fill_ratio: float | None           # cargo_used / cargo_capacity_m3
    limiting_factor: str | None        # Primary: "cargo" | "liquidity" | "market_supply_buy" | "market_supply_sell" | "no_data" | "no_supply"
    limiting_factors: list[str] | None # All binding constraints (for detailed view)
```

### Sort Mode Behavior

| Mode | Formula | Use Case |
|------|---------|----------|
| `margin` | `net_margin_pct DESC` | Station traders (uses net profit after fees) |
| `profit_density` | `net_profit_per_unit / effective_volume DESC` | Quick estimate without history |
| `hauling_score` | `expected_profit / cargo_capacity_m3` | Haulers with transport constraint |

**Note:** All modes use net profit (after fees). The deprecated `profit_pct` field still contains gross margin for backward compatibility but should not be used for sorting.

---

## Integration Points

### 1. Arbitrage Engine Enhancement

**File:** `src/aria_esi/services/arbitrage_engine.py`

**Changes:**
- Add `item_volume_m3` to query (prefer `types.packaged_volume`, fall back to `types.volume`)
- Add `item_packaged_volume_m3` to response for transparency (raw packaged volume)
- Add `buy_available_volume` and `sell_available_volume` (derive `available_volume = min(...)`)
- Add `profit_density` calculation using effective volume default
- Add optional history integration with `daily_volume_source` fallback
- Add `calculate_hauling_score()` method
- Support multiple sort modes

### 2. History Cache Integration

**File:** `src/aria_esi/mcp/market/database.py`

**Additions to `MarketDatabase`:**
- Add `market_history_cache` table to schema
- Add `get_history_cache()` and `save_history_cache()` methods
- Add `get_history_batch()` for bulk lookups during arbitrage scans

### 3. MCP Tool Updates

**File:** `src/aria_esi/mcp/market/tools_arbitrage.py`

**Changes:**
- Add new parameters to `market_arbitrage_scan`
- Serialize new fields in response
- Add history fetching (optional, behind flag) and daily_volume_source fallback

### 4. Skill Updates

**File:** `.claude/skills/arbitrage/SKILL.md`

**Changes:**
- Accept transport capacity parameter (cargo + fleet hangar/specialized holds)
- Display hauling score in results
- Show limiting factor (cargo vs liquidity vs market_supply)

---

## Display Format

### Standard Output (with hauling score)

```
## Arbitrage Opportunities (60,000 m³ transport capacity)
## Trade mode: immediate (sales tax only: 3.6%)

| Item | Buy→Sell | Gross | Net | Score | Safe Qty | Expected | Limit |
|------|----------|-------|-----|-------|----------|----------|-------|
| Skill Injector | Amarr→Jita | 8.2% | 4.3% | 63K/m³ | 120 | 5.0B | liquidity |
| Neurovisual | Jita→Amarr | 11.9% | 7.8% | 6.4K/m³ | 240 | 154M | liquidity |
| Tritanium | Jita→Dodixie | 6.0% | 2.2% | 42/m³ | 6M | 660K | cargo |

Legend:
  Gross = (sell - buy) / buy × 100 (before fees)
  Net = profit after fees (mode-dependent: immediate = sales tax only)
  Score = Net ISK profit per m³ of transport capacity
  Limit = binding constraint (cargo | liquidity | market_supply)

Note: Items with net_profit <= 0 are automatically filtered from results.
```

### Comparison View (showing why gross margin is misleading)

```
## Why Gross Margin ≠ Profit (Comparing Trade Modes)

PLEX Example: 2.1% gross margin (Buy: 5.0B, Sell: 5.105B)

  IMMEDIATE mode (taker-taker, recommended for hauling):
    → No broker fees (taking existing orders)
    → Sales tax: 5.105B × 3.6% = 184M ISK
    → Net profit: 105M - 184M = -79M ISK (LOSS)
    → Net margin: -1.6%
    → Verdict: Still unprofitable, filtered from results

  STATION TRADING mode (maker-maker, NOT typical for hauling):
    → Buy broker fee (3%): 150M ISK
    → Sell broker fee (3%): 153M ISK
    → Sales tax (3.6%): 184M ISK
    → Total fees: 487M ISK
    → Net profit: 105M - 487M = -382M ISK (LOSS)
    → Net margin: -7.6%
    → Verdict: Much worse - needs ~10% gross to break even

Skill Injector: 8.2% gross margin (Buy: 980M, Sell: 1.06B)

  IMMEDIATE mode:
    → Sales tax: 1.06B × 3.6% = 38M ISK
    → Gross profit: 80M ISK
    → Net profit: 80M - 38M = 42M ISK per unit
    → Net margin: 4.3%
    → With 120 safe quantity: 5.0B expected profit

Tritanium: 8.2% gross margin vs Skill Injector (same margin, different value density)

  → Same gross margin (8.2%), same net margin (4.3%)
  → But unit value is 5 ISK vs 980M ISK
  → Tritanium net profit: 0.22 ISK per unit
  → 60,000 m³ = 6M units × 0.22 ISK = 1.3M ISK total
  → Score: 22 ISK/m³ (terrible vs Skill Injector's 63K/m³)
```

---

## Implementation Phases

### Phase 1: Foundation (Volume & Density)

**Goal:** Add item volume and profit density to existing arbitrage results

**Deliverables:**
- [ ] Include `types.volume` in arbitrage SQL query
- [ ] Add `item_volume_m3` and `profit_density` (using effective volume default)
- [ ] Add buy/sell availability and derive `available_volume = min(...)`
- [ ] Add `sort_by` parameter with "margin" and "profit_density" modes
- [ ] Update skill display to show profit density

**No history integration yet** - uses available_volume as liquidity proxy (daily_volume_source="market_proxy").

**Estimated complexity:** Low (query and model changes only)

### Phase 2: History Integration

**Goal:** Add market history for accurate daily volume

**Deliverables:**
- [ ] Create `market_history_cache` table
- [ ] Add history cache methods to `MarketDatabase` with lazy refresh
- [ ] Add `include_history` parameter to scan
- [ ] Populate `daily_volume` field from cache
- [ ] Set `daily_volume_source` to "history" or "market_proxy"

**Estimated complexity:** Medium (new table, caching logic, ESI history fetching)

### Phase 3: Full Hauling Score

**Goal:** Complete algorithm with transport capacity

**Deliverables:**
- [ ] Add `cargo_capacity_m3` parameter (total transport capacity)
- [ ] Implement `calculate_hauling_score()` function
- [ ] Add `hauling_score`, `safe_quantity`, `expected_profit`, `fill_ratio`, `limiting_factor` fields
- [ ] Add "hauling_score" sort mode
- [ ] Update skill to accept transport capacity

**Estimated complexity:** Low (algorithm is straightforward once data exists)

### Phase 4: Polish & Optimization

**Goal:** Performance and UX improvements

**Deliverables:**
- [ ] Background history refresh for common items
- [ ] Ship transport capacity presets (e.g., "freighter", "blockade runner", DST fleet hangar)
- [ ] Route cost integration (jump fuel)
- [ ] Combined "best routes" view (cargo + route efficiency)

**Estimated complexity:** Medium (optimization, UX research)

---

## Validation & Testing

**Focus areas:**

### Volume & Density
- Default volume fallback: `volume_m3` is `None` or `0` uses `DEFAULT_VOLUME_M3` for both `profit_density` and `cargo_used`
- Packaged volume preference: when `packaged_volume_m3 > 0`, use it over `volume_m3`

### Liquidity
- History fallback: `daily_volume=None` uses market proxy and sets `daily_volume_source="market_proxy"`
- Low-volume rounding: `daily_volume < 10` still allows 1-unit trades (`max_by_liquidity >= 1`)
- Buy/sell availability cap: `available_volume = min(buy_available_volume, sell_available_volume)`

### Limiting Factors
- Single constraint: when only one limit is binding, `limiting_factor` matches and `limiting_factors` has one element
- Multiple constraints: when `safe_quantity` equals multiple limits, `limiting_factors` contains all of them
- Priority ordering: `limiting_factor` follows priority (market_supply > liquidity > cargo) when multiple bind

### Fee Calculation
- Net profit calculation: `net_profit = sell_revenue - buy_cost` where costs include broker fees
- Break-even threshold: 10% gross margin ≈ 3.4% net profit with default fees (verify math)
- Negative profit filtering: opportunities with `net_profit_per_unit <= 0` are excluded from results
- Custom fee rates: user-provided `broker_fee_pct` and `sales_tax_pct` override defaults
- Edge case: 0% broker fee (e.g., citadel with 0% fee) produces higher net margins

### Sorting
- Sorting stability: `margin`, `profit_density`, and `hauling_score` produce distinct orderings
- Margin sort uses `net_margin_pct` (not deprecated `profit_pct`)
- Profit density uses `net_profit_per_unit / effective_volume`

### Integration
- Expected profit: `expected_profit = net_profit_per_unit × safe_quantity` (not gross)
- Hauling score: uses net profit, not gross profit

---

## Alternatives Considered

### Alternative 1: ROI per Hour

**Formula:** `(profit / investment) / (route_time_hours)`

**Pros:** Accounts for time value of money

**Cons:**
- Requires route time estimation (variable)
- Assumes continuous trading (not realistic for casual)
- Overcomplicates the model

**Decision:** Rejected. Hauling score is simpler and covers 90% of use cases.

### Alternative 2: Kelly Criterion Sizing

**Formula:** `f* = (p × b - q) / b` where p=win prob, b=odds, q=loss prob

**Pros:** Optimal bankroll management

**Cons:**
- Requires win/loss probability estimation
- Overkill for EVE trading (no true "loss" in arbitrage)
- Confusing for users

**Decision:** Rejected. Liquidity factor is simpler and more intuitive.

### Alternative 3: Multi-Trip Optimization

**Formula:** Optimize for multiple round trips, batch orders

**Pros:** Higher theoretical efficiency

**Cons:**
- Dramatically more complex
- Requires order book depth analysis
- Diminishing returns vs. simple single-trip model

**Decision:** Deferred to V3. Single-trip model is sufficient for V2.

---

## Open Questions

1. **Default transport capacity?**
   - Option A: Require explicit input (current recommendation)
   - Option B: Default to common ship (e.g., 5,000 m³ for T1 industrial)
   - Option C: Profile-based (read from `operations.md`)

2. **History data TTL?**
   - Recommendation: 24 hours, **but downtime-aware** (force refresh after daily history update)
   - Alternative: 6 hours (more responsive to market shifts)

3. **Liquidity factor default?**
   - Recommendation: 10% (conservative, avoids market impact)
   - Alternative: 5% (very conservative) or 20% (aggressive)

4. **Should we warn on low-liquidity items?**
   - Yes: Flag items where `safe_quantity < available_volume / 2`
   - This indicates liquidity is the binding constraint

---

## Future Considerations

The following enhancements are worth considering but require additional design work:

### Ship Cargo Presets via EOS

Instead of requiring manual transport capacity input for every scan, derive values from practical fits using the EOS fitting engine. This ensures accuracy with expanders, rigs, and skill effects (and fleet hangars where applicable).

**Approach:**
1. Store reference hauling fits in `userdata/fits/haulers/` (EFT format)
2. On `--ship` flag, load the fit and call `calculate_fit_stats()` to get actual transport capacity
3. Cache computed cargo values to avoid repeated EOS calls

```bash
# Proposed CLI usage
market_arbitrage_scan --ship "Prowler - Max Cargo"    # Loads fit, computes cargo via EOS
market_arbitrage_scan --ship prowler                   # Shorthand for default Prowler fit

# If no cargo specified and no fit provided
DEFAULT_CARGO_M3 = 5_000  # Placeholder fallback; replace with SDE/EOS-derived values
```

**Reference fits to include (verify with SDE/EOS):**
- T1 Industrials (Nereus, Tayra, Badger, etc.) - verify base + fit cargo via EOS
- Blockade Runners (Prowler, Crane, etc.) - verify fit cargo via EOS
- Deep Space Transports - verify fleet hangar capacity via EOS/SDE
- Freighters - verify fit cargo via EOS/SDE

**Why EOS over static presets:**
- Accounts for cargo expanders, rigs, and implants
- Reflects pilot skill levels (if `use_pilot_skills=True`)
- Single source of truth for ship stats
- Fits can be updated without code changes

### Database Integration Pattern

The `market_history_cache` table should be added to the existing `MarketDatabase` class (in `src/aria_esi/mcp/market/database.py`) following the established pattern:

```python
# Add to SCHEMA_SQL constant
"""
CREATE TABLE IF NOT EXISTS market_history_cache (
    type_id INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    avg_daily_volume INTEGER,
    avg_daily_isk REAL,
    volatility_pct REAL,
    updated_at INTEGER,
    PRIMARY KEY (type_id, region_id)
);
"""
```

This follows the existing pattern where `MarketDatabase` manages all market-related tables (`types`, `aggregates`, `common_items`). History cache data shares the same keys (`type_id`, `region_id`) and serves the same domain.

---

## Summary

| Aspect | Current (V1) | Proposed (V2) |
|--------|--------------|---------------|
| **Profit calculation** | Gross (ignores fees) | Net (after broker fees + sales tax) |
| **Fee handling** | None | Configurable broker_fee_pct and sales_tax_pct |
| **Ranking** | Gross profit % only | Hauling score (net ISK/m³ adjusted for liquidity) |
| **Volume data** | Ignored | Item volume from SDE (packaged preferred) |
| **History data** | Not used | Daily volume for liquidity calculation |
| **Transport awareness** | None | Explicit cargo_capacity parameter (transport capacity) |
| **Liquidity model** | None | 10% of daily volume cap |
| **Sort modes** | 1 (margin) | 3 (margin, profit_density, hauling_score) |
| **Limiting factors** | Not tracked | Primary + full list of binding constraints |

The hauling score algorithm transforms arbitrage scanning from "what has the best margin" to "what should I actually haul" - a fundamentally more useful question for traders. The switch to net profit after fees eliminates the common trap where high gross margin items become losses after transaction costs.
