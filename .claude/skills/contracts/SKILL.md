---
name: contracts
description: Personal contract management. View item exchange, courier, and auction contracts - both issued and received.
model: haiku
category: financial
triggers:
  - "/contracts"
  - "my contracts"
  - "show contracts"
  - "contract status"
  - "courier contracts"
requires_pilot: true
esi_scopes:
  - esi-contracts.read_character_contracts.v1
---

# ARIA Contracts Module

## Purpose

Monitor personal contracts in EVE Online. View item exchanges, courier contracts, and auctions that you've issued or received. Essential for tracking trades, deliveries, and transactions outside the market system.

## CRITICAL: Read-Only Limitation

**ESI contract endpoints are READ-ONLY.** ARIA can:
- View all your personal contracts (issued and received)
- See contract items, status, and expiration
- Track courier contract progress
- View auction bids

**ARIA CANNOT:**
- Accept or reject contracts
- Create new contracts
- Cancel existing contracts
- Deliver courier packages
- Place auction bids
- Interact with the EVE client in any way

**Always clarify this when showing contract data.** If contracts need action, explicitly state this requires in-game action.

## Why This Matters

For self-sufficient pilots, contracts are often essential:
- **Item Exchange:** Trade items outside the market (faction gear from LP stores, etc.)
- **Courier:** Move goods between stations without market fees
- **Auction:** Sell unique or valuable items to the highest bidder

Without market trading, contracts become a key transaction method.

## Contract Types

| Type | Purpose | Key Fields |
|------|---------|------------|
| `item_exchange` | Trade items for ISK | price, items |
| `courier` | Deliver items between locations | reward, collateral, volume |
| `auction` | Sell to highest bidder | price (min), buyout, bids |
| `loan` | Item lending (rare) | collateral, duration |

## Contract Statuses

| Status | Meaning |
|--------|---------|
| `outstanding` | Active, awaiting acceptance |
| `in_progress` | Courier being delivered |
| `finished_issuer` | Completed, awaiting issuer action |
| `finished_contractor` | Completed, awaiting contractor action |
| `finished` | Fully completed |
| `cancelled` | Cancelled by issuer |
| `rejected` | Rejected by assignee |
| `failed` | Courier failed (expired/items lost) |
| `deleted` | Removed from system |
| `reversed` | Transaction reversed |

## Trigger Phrases

- `/contracts`
- "my contracts"
- "show contracts"
- "contract status"
- "check contracts"
- "pending contracts"
- "courier contracts"
- "auction status"
- "what contracts do I have"

## ESI Requirement

**Requires:** `esi-contracts.read_character_contracts.v1` scope

This scope provides access to personal contracts. If not authorized:
```
Contract access requires ESI authentication.

To enable: uv run python .claude/scripts/aria-oauth-setup.py
The contracts scope will be included automatically.
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
   Contract monitoring requires live ESI data which is currently unavailable.

   Check this in-game: Alt+C (Contracts) → My Contracts

   ESI usually recovers automatically.
   ```
3. **DO NOT** block waiting for ESI

### If ESI is AVAILABLE:

Proceed with normal contract queries.

## Implementation

Run the ESI wrapper command:
```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi contracts [options]
```

### Commands

| Command | Description |
|---------|-------------|
| `contracts` | List all personal contracts |
| `contracts --issued` | Show only contracts you created |
| `contracts --received` | Show only contracts assigned to you |
| `contracts --type courier` | Filter by contract type |
| `contracts --active` | Show only outstanding/in_progress |
| `contracts --completed` | Show completed contracts |
| `contract <id>` | Detailed view of specific contract |

### Options

| Option | Description |
|--------|-------------|
| `--issued` | Show only contracts you issued |
| `--received` | Show only contracts assigned to you |
| `--type <type>` | Filter by type: item_exchange, courier, auction |
| `--active` | Show only active contracts (outstanding/in_progress) |
| `--completed` | Show completed contracts |
| `--limit N` | Maximum contracts to display (default: 20) |

## JSON Response Structure

### Contract List
```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "semi_stable",
  "character_id": 2119654321,
  "summary": {
    "total_contracts": 5,
    "issued": 2,
    "received": 3,
    "outstanding": 3,
    "in_progress": 1,
    "completed": 1
  },
  "contracts": [
    {
      "contract_id": 123456789,
      "type": "item_exchange",
      "status": "outstanding",
      "title": "Federation Navy Hammerhead x5",
      "issuer_name": "Federation Navy Suwayyah",
      "assignee_name": null,
      "availability": "public",
      "price": 50000000.0,
      "reward": 0.0,
      "collateral": 0.0,
      "volume": 50.0,
      "date_issued": "2026-01-14T10:00:00Z",
      "date_expired": "2026-01-28T10:00:00Z",
      "days_remaining": 13,
      "is_issuer": true,
      "location": "Dodixie IX - Moon 20 - Federation Navy Assembly Plant"
    },
    {
      "contract_id": 123456790,
      "type": "courier",
      "status": "in_progress",
      "title": "Minerals to Jita",
      "issuer_name": "Some Trader",
      "assignee_name": "Federation Navy Suwayyah",
      "acceptor_name": "Federation Navy Suwayyah",
      "availability": "private",
      "reward": 5000000.0,
      "collateral": 100000000.0,
      "volume": 50000.0,
      "start_location": "Dodixie IX - Moon 20",
      "end_location": "Jita IV - Moon 4",
      "days_to_complete": 7,
      "date_accepted": "2026-01-14T12:00:00Z",
      "date_expired": "2026-01-21T12:00:00Z",
      "is_issuer": false,
      "is_acceptor": true
    }
  ]
}
```

### Contract Detail
```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "stable",
  "contract_id": 123456789,
  "type": "item_exchange",
  "status": "outstanding",
  "title": "Federation Navy Hammerhead x5",
  "issuer": {
    "character_id": 2119654321,
    "name": "Federation Navy Suwayyah"
  },
  "availability": "public",
  "price": 50000000.0,
  "date_issued": "2026-01-14T10:00:00Z",
  "date_expired": "2026-01-28T10:00:00Z",
  "location": "Dodixie IX - Moon 20 - Federation Navy Assembly Plant",
  "items": [
    {
      "type_name": "Federation Navy Hammerhead",
      "quantity": 5,
      "is_included": true
    }
  ],
  "bids": []
}
```

## Response Formats

### Standard Display (rp_level: off or lite)

```markdown
## Personal Contracts
*Query: 14:30 UTC*

### Outstanding (3)
| Type | Title | Price/Reward | Expires |
|------|-------|--------------|---------|
| Item Exchange | Fed Navy Hammerhead x5 | 50M ISK | 13 days |
| Courier | Minerals to Jita | 5M reward | 6 days |
| Auction | Rare Blueprint | 100M+ | 2 days |

### In Progress (1)
- **Courier** to Jita - 5M reward, 100M collateral - 6 days left

*ARIA monitors contracts but cannot accept, create, or modify them.*
```

### Formatted Version (rp_level: moderate or full)

```
═══════════════════════════════════════════════════════════════════
ARIA CONTRACT MONITOR
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC
───────────────────────────────────────────────────────────────────
CONTRACTS SUMMARY: 5 total (3 active)
  Issued by you:    2
  Assigned to you:  3
───────────────────────────────────────────────────────────────────
OUTSTANDING CONTRACTS:

  [Item Exchange] Federation Navy Hammerhead x5
  Status:   Outstanding (PUBLIC)
  Price:    50,000,000 ISK
  Location: Dodixie IX - Moon 20
  Expires:  13 days

  [Auction] Rare BPC Collection
  Status:   Outstanding (PUBLIC)
  Min Bid:  100,000,000 ISK
  Buyout:   500,000,000 ISK
  Bids:     3 (current: 250M)
  Expires:  2 days

───────────────────────────────────────────────────────────────────
IN PROGRESS:

  [Courier] Minerals to Jita
  From:       Dodixie IX - Moon 20
  To:         Jita IV - Moon 4
  Reward:     5,000,000 ISK
  Collateral: 100,000,000 ISK (at risk)
  Volume:     50,000 m³
  Deadline:   6 days remaining

───────────────────────────────────────────────────────────────────
IN-GAME ACTION: Contracts window → My Contracts
ARIA monitors only - cannot create, accept, or modify contracts.
═══════════════════════════════════════════════════════════════════
```

### No Contracts Display

```
═══════════════════════════════════════════════════════════════════
ARIA CONTRACT MONITOR
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC
───────────────────────────────────────────────────────────────────
No active contracts found.

You have no outstanding item exchanges, courier jobs, or auctions.
Create contracts in-game: Inventory → Right-click item → Create Contract
═══════════════════════════════════════════════════════════════════
```

## Courier Contract Guidance

For self-sufficient pilots, courier contracts may be the primary way to:
- Move items from LP stores to your base
- Transport manufactured goods
- Relocate assets without personal travel

### Courier Risk Assessment

```
COURIER CONTRACT ANALYSIS
───────────────────────────────────────────────────────────────────
Route:      Dodixie → Jita (11 jumps via high-sec)
Volume:     50,000 m³ (requires Freighter or multiple trips)
Reward:     5,000,000 ISK
Collateral: 100,000,000 ISK

RISK ASSESSMENT:
  Route Security: High-sec only ✓
  Gank Risk:      Moderate (trade route, Freighter required)
  ISK/Jump:       454,545 ISK/jump

RECOMMENDATION: Acceptable for experienced hauler. New pilots
consider smaller loads or hiring a service.
───────────────────────────────────────────────────────────────────
```

## Auction Monitoring

For auction contracts you've issued:

```
AUCTION STATUS
───────────────────────────────────────────────────────────────────
Item:       Rare Blueprint Collection
Min Bid:    100,000,000 ISK
Buyout:     500,000,000 ISK
Status:     3 bids received

Current Bid: 250,000,000 ISK (by Bidder Name)
Time Left:   2 days 4 hours

Bid History:
  • 250M - Bidder Name (current)
  • 175M - Another Bidder
  • 100M - First Bidder
───────────────────────────────────────────────────────────────────
```

## Error Handling

### ESI Not Configured

```
═══════════════════════════════════════════════════════════════════
ARIA CONTRACT MONITOR
───────────────────────────────────────────────────────────────────
Contract monitoring requires ESI authentication.

ARIA works fully without ESI - you can tell me about contracts
and I'll help analyze them manually.

OPTIONAL: Enable live tracking (~5 min setup)
  → uv run python .claude/scripts/aria-oauth-setup.py
═══════════════════════════════════════════════════════════════════
```

### Missing Scope

```
═══════════════════════════════════════════════════════════════════
ARIA CONTRACT MONITOR - SCOPE NOT AUTHORIZED
───────────────────────────────────────────────────────────────────
ESI is configured but contracts scope is missing.

To enable contract monitoring:
  uv run python .claude/scripts/aria-oauth-setup.py

Select "esi-contracts.read_character_contracts.v1" during setup.
═══════════════════════════════════════════════════════════════════
```

## Contextual Suggestions

After displaying contracts, suggest ONE related action when relevant:

| Context | Suggest |
|---------|---------|
| Courier in progress | "Track route security with `/threat-assessment`" |
| Auction with bids | "Monitor for outbids - check back before expiry" |
| Item exchange pending | "Check market prices with `/price <item>`" |
| No contracts | "Consider selling LP store items via contract" |

## Cross-References

| Related Command | Use Case |
|-----------------|----------|
| `/lp-store` | LP items you might want to sell via contract |
| `/price` | Compare contract prices to market |
| `/threat-assessment` | Evaluate courier route safety |
| `/wallet-journal` | Track contract income |

## Self-Sufficiency Context

For pilots with `market_trading: false`:
- Contracts become the primary trade mechanism
- Item exchange contracts let you sell LP store items directly
- Courier contracts let you hire others to move goods
- Emphasize contract-based trading over market orders

## Behavior Notes

- **Brevity:** Default to summary view unless detail requested
- **Expiration:** Highlight contracts expiring within 24 hours
- **In Progress:** Always show courier collateral at risk
- **Location Resolution:** Convert station IDs to readable names
- **ISK Formatting:** Use standard ISK format (e.g., "50M ISK")
- **Privacy:** Don't expose counterparty details unnecessarily
