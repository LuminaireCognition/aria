---
name: orders
description: View active market orders and order history. Track buy/sell orders, escrow, and fill status.
model: haiku
category: financial
triggers:
  - "/orders"
  - "my market orders"
  - "active orders"
  - "sell orders"
  - "buy orders"
requires_pilot: true
esi_scopes:
  - esi-markets.read_character_orders.v1
---

# ARIA Market Orders Monitor

## Purpose

Query the capsuleer's market orders to display active buy/sell orders and order history. Essential for market traders and pilots monitoring their market activity.

## CRITICAL: Read-Only Limitation

**ESI market order endpoints are READ-ONLY.** ARIA can:
- View active buy and sell orders
- Display order history (expired/cancelled)
- Show escrow amounts and fill status

**ARIA CANNOT:**
- Place new orders
- Modify existing orders
- Cancel orders
- Interact with the EVE client in any way

**Always clarify this when showing order status.** If user asks to place or modify orders, explicitly state this requires in-game action (Market window).

## CRITICAL: Data Volatility

Market order data is **semi-stable** - orders update when filled or modified:

1. **Display query timestamp** - orders can change frequently
2. **Active orders cached 20 minutes** - may not reflect very recent fills
3. **Order history cached 1 hour** - historical data is stable
4. **Escrow amounts are locked** - shown for buy orders

## Trigger Phrases

- `/orders`
- "my market orders"
- "active orders"
- "sell orders"
- "buy orders"
- "order status"
- "what am I selling"
- "market activity"
- "order history"

## ESI Requirement

**Requires:** `esi-markets.read_character_orders.v1` scope

If scope is not authorized:
```
Market order access requires ESI authentication.

To enable: uv run python .claude/scripts/aria-oauth-setup.py
Select "esi-markets.read_character_orders.v1" during scope selection.
```

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi` commands - they will timeout
2. **RESPOND IMMEDIATELY** with:
   ```
   Market order monitoring requires live ESI data which is currently unavailable.

   Check this in-game: Alt+R (Market) → My Orders tab

   ESI usually recovers automatically.
   ```
3. **DO NOT** block waiting for ESI

### If ESI is AVAILABLE:

Proceed with normal orders queries.

## Implementation

Run the ESI wrapper commands:
```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi orders [options]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--buy` | Show only buy orders | - |
| `--sell` | Show only sell orders | - |
| `--active` | Show only active orders | (default) |
| `--history` | Include expired/cancelled orders | - |
| `--limit N` | Limit results | 50 |

### JSON Response Structure

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "semi_stable",
  "character_id": 2119654321,
  "summary": {
    "active_orders": 5,
    "buy_orders": 2,
    "sell_orders": 3,
    "total_escrow": 15000000,
    "total_sell_value": 85000000
  },
  "orders": [
    {
      "order_id": 6543210987,
      "type_id": 34,
      "type_name": "Tritanium",
      "is_buy_order": false,
      "location_id": 60003760,
      "location_name": "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
      "region_id": 10000002,
      "region_name": "The Forge",
      "price": 5.50,
      "volume_total": 1000000,
      "volume_remain": 750000,
      "fill_percent": 25.0,
      "issued": "2026-01-10T12:00:00Z",
      "duration": 90,
      "expires": "2026-04-10T12:00:00Z",
      "days_remaining": 85,
      "state": "active",
      "min_volume": 1,
      "range": "station",
      "escrow": null
    },
    {
      "order_id": 6543210988,
      "type_id": 35,
      "type_name": "Pyerite",
      "is_buy_order": true,
      "location_id": 60003760,
      "location_name": "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
      "region_id": 10000002,
      "region_name": "The Forge",
      "price": 8.00,
      "volume_total": 500000,
      "volume_remain": 500000,
      "fill_percent": 0.0,
      "issued": "2026-01-14T08:00:00Z",
      "duration": 30,
      "expires": "2026-02-13T08:00:00Z",
      "days_remaining": 29,
      "state": "active",
      "min_volume": 1,
      "range": "station",
      "escrow": 4000000
    }
  ]
}
```

### Order History Response (with --history)

Additional fields for completed orders:
```json
{
  "state": "expired",
  "completed": "2026-01-12T08:00:00Z"
}
```

States: `active`, `expired`, `cancelled`

### Empty Response

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "semi_stable",
  "character_id": 2119654321,
  "summary": {
    "active_orders": 0,
    "buy_orders": 0,
    "sell_orders": 0,
    "total_escrow": 0,
    "total_sell_value": 0
  },
  "orders": [],
  "message": "No active market orders"
}
```

## Order Range Values

| Range | Description |
|-------|-------------|
| `station` | Same station only |
| `solarsystem` | Same solar system |
| `1` - `40` | Jump range (1-40 jumps) |
| `region` | Entire region |

## Response Formats

### Standard Display (rp_level: off or lite)

```markdown
## Market Orders
*Query: 14:30 UTC*

### Active Orders (5)

**Sell Orders (3)**
| Item | Price | Qty | Filled | Location |
|------|-------|-----|--------|----------|
| Tritanium | 5.50 | 1M | 25% | Jita 4-4 |
| Pyerite | 9.20 | 500K | 0% | Jita 4-4 |
| Mexallon | 45.00 | 100K | 50% | Dodixie |

**Buy Orders (2)**
| Item | Price | Qty | Escrow | Location |
|------|-------|-----|--------|----------|
| Pyerite | 8.00 | 500K | 4M | Jita 4-4 |
| Isogen | 50.00 | 50K | 2.5M | Jita 4-4 |

**Totals:** 6.5M escrow locked | 85M sell value pending
```

### Formatted Version (rp_level: moderate or full)

```
═══════════════════════════════════════════════════════════════════
ARIA MARKET ORDER STATUS
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC
───────────────────────────────────────────────────────────────────
ACTIVE ORDERS: 5 (3 sell, 2 buy)
───────────────────────────────────────────────────────────────────
SELL ORDERS
  Tritanium         5.50 ISK x 1,000,000  (25% filled)
  Location: Jita IV - Moon 4 - CNP | Expires: 85 days

  Pyerite           9.20 ISK x 500,000    (0% filled)
  Location: Jita IV - Moon 4 - CNP | Expires: 28 days
───────────────────────────────────────────────────────────────────
BUY ORDERS
  Pyerite           8.00 ISK x 500,000    (0% filled)
  Location: Jita IV - Moon 4 - CNP | Escrow: 4,000,000 ISK

  Isogen           50.00 ISK x 50,000     (0% filled)
  Location: Jita IV - Moon 4 - CNP | Escrow: 2,500,000 ISK
───────────────────────────────────────────────────────────────────
ESCROW LOCKED:    6,500,000 ISK
SELL VALUE:      85,000,000 ISK (pending)
───────────────────────────────────────────────────────────────────
Orders managed via Market window (Alt+R) in EVE client.
═══════════════════════════════════════════════════════════════════
```

### No Orders Display

```
═══════════════════════════════════════════════════════════════════
ARIA MARKET ORDER STATUS
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC
───────────────────────────────────────────────────────────────────
No active market orders.

To place orders, use the Market window (Alt+R) in the EVE client.
═══════════════════════════════════════════════════════════════════
```

## Error Handling

### ESI Not Configured

```
═══════════════════════════════════════════════════════════════════
ARIA MARKET ORDER STATUS
───────────────────────────────────────────────────────────────────
Market order monitoring requires ESI authentication.

ARIA works fully without ESI - you can manually track
your orders or check the Market window.

OPTIONAL: Enable live tracking (~5 min setup)
  uv run python .claude/scripts/aria-oauth-setup.py
═══════════════════════════════════════════════════════════════════
```

### Missing Scope

```
═══════════════════════════════════════════════════════════════════
ARIA MARKET ORDER STATUS - SCOPE NOT AUTHORIZED
───────────────────────────────────────────────────────────────────
ESI is configured but market orders scope is missing.

To enable:
  uv run python .claude/scripts/aria-oauth-setup.py

Select "esi-markets.read_character_orders.v1" during setup.
═══════════════════════════════════════════════════════════════════
```

## Contextual Suggestions

| Context | Suggest |
|---------|---------|
| Has sell orders | "Check market prices with `/price <item>`" |
| Orders expiring soon | "Consider updating orders before expiry" |
| High escrow locked | "Buy order escrow is locked until filled or cancelled" |

## Cross-References

| Related Command | Use Case |
|-----------------|----------|
| `/price` | Check current market prices |
| `/wallet-journal` | Track market transaction income |
| `/assets` | View items available to sell |

## Self-Sufficiency Context

For pilots with `market_trading: false`:
- Market orders may still be used for personal purchasing
- Sell orders would be atypical - flag if unexpected
- Focus on buy orders for resource acquisition

## Behavior Notes

- **Brevity:** Default to table format unless RP mode requests formatted boxes
- **Sorting:** Active orders first, then by expiration date
- **Fill Status:** Show percentage filled for partially completed orders
- **Escrow:** Always show escrow amounts for buy orders
- **Duration:** Show days remaining until expiration
- **Location:** Abbreviate long station names
