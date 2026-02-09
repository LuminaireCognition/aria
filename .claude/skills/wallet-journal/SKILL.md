---
name: wallet-journal
description: View wallet transaction history and ISK flow analysis. Use for financial tracking, profit/loss analysis, or identifying income sources.
model: haiku
category: financial
triggers:
  - "/wallet-journal"
  - "where did my ISK go"
  - "ISK history"
  - "transaction history"
  - "wallet transactions"
  - "income breakdown"
  - "show me my finances"
  - "profit and loss"
requires_pilot: true
esi_scopes:
  - esi-wallet.read_character_wallet.v1
---

# ARIA Financial Intelligence Module (Wallet Journal)

## Purpose
Query wallet journal and transactions to provide detailed ISK flow analysis. Essential for self-sufficient pilots tracking manufacturing profit margins, bounty income, mission rewards, and identifying where ISK comes from and goes.

## CRITICAL: Data Volatility

Wallet journal data is **semi-stable** - new transactions appear continuously but historical data is fixed:

1. **Display query timestamp** - shows data freshness
2. **No staleness warning needed** - historical transactions don't change
3. **Can cache results** - useful for trend analysis
4. **Recent entries may update** - very recent transactions might still be processing

## Trigger Phrases

- `/wallet-journal`
- "where did my ISK go"
- "ISK history" / "transaction history"
- "wallet transactions"
- "income breakdown"
- "show me my finances"
- "money coming in"
- "profit and loss"
- "what am I earning from"

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi` commands - they will timeout
2. **RESPOND IMMEDIATELY** with:
   ```
   Wallet journal requires live ESI data which is currently unavailable.

   Check this in-game: Alt+W (Wallet) → Journal tab

   ESI usually recovers automatically.
   ```
3. **DO NOT** block waiting for ESI

### If ESI is AVAILABLE:

Proceed with normal wallet journal queries.

## ESI Endpoints Used

| Endpoint | Scope | Purpose |
|----------|-------|---------|
| `/characters/{id}/wallet/journal/` | `esi-wallet.read_character_wallet.v1` | Transaction journal with ref types |
| `/characters/{id}/wallet/transactions/` | `esi-wallet.read_character_wallet.v1` | Market transactions (buy/sell) |

**Scope already requested** - no new authentication needed.

## Implementation

Run the ESI wrapper command:
```bash
uv run aria-esi wallet-journal [--days N] [--type TYPE]
```

### Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--days N` | Limit to last N days | 7 |
| `--type TYPE` | Filter by ref_type category | all |

### Type Categories

| Category | Ref Types Included | Description |
|----------|-------------------|-------------|
| `bounty` | bounty_prizes, agent_mission_reward, agent_mission_time_bonus_reward | Combat earnings |
| `market` | market_transaction, market_escrow | Buy/sell orders |
| `industry` | industry_job_tax, manufacturing | Production costs |
| `insurance` | insurance | Ship insurance payouts |
| `transfer` | player_donation, corporation_account_withdrawal | ISK movements |
| `tax` | transaction_tax, brokers_fee | Market fees |

### JSON Response Structure

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "semi_stable",
  "period_days": 7,
  "summary": {
    "total_income": 15234567.89,
    "total_expenses": 3456789.12,
    "net_change": 11777778.77,
    "income_breakdown": {
      "bounty_prizes": 8500000.00,
      "agent_mission_reward": 4200000.00,
      "market_transaction": 2534567.89
    },
    "expense_breakdown": {
      "market_transaction": 2100000.00,
      "transaction_tax": 856789.12,
      "brokers_fee": 500000.00
    }
  },
  "journal": [
    {
      "date": "2026-01-15T12:30:00Z",
      "ref_type": "bounty_prizes",
      "amount": 125000.00,
      "balance": 15234567.89,
      "description": "For killing pirates in Essence"
    }
  ],
  "transactions": [
    {
      "date": "2026-01-14T18:00:00Z",
      "type_name": "Hammerhead I",
      "quantity": 5,
      "unit_price": 425000.00,
      "is_buy": true,
      "location_name": "Dodixie IX - Moon 20"
    }
  ]
}
```

## Response Formats

### Standard Format (rp_level: off or lite)

```markdown
## Wallet Journal (Last 7 Days)
*Query: 14:30 UTC*

### Summary
| | ISK |
|---|---:|
| Income | +15,234,567 |
| Expenses | -3,456,789 |
| **Net** | **+11,777,778** |

### Income Sources
| Source | Amount | % |
|--------|-------:|--:|
| Bounties | 8,500,000 | 56% |
| Mission Rewards | 4,200,000 | 28% |
| Market Sales | 2,534,567 | 16% |

### Major Expenses
| Expense | Amount |
|---------|-------:|
| Market Purchases | 2,100,000 |
| Transaction Tax | 856,789 |
| Broker Fees | 500,000 |

### Recent Transactions
| Date | Type | Amount | Balance |
|------|------|-------:|--------:|
| Jan 15 12:30 | Bounty | +125,000 | 15.2M |
| Jan 14 18:00 | Market Buy | -2,125,000 | 15.1M |
...
```

### Formatted Version (rp_level: moderate or full)

```
═══════════════════════════════════════════════════════════════════
ARIA FINANCIAL INTELLIGENCE REPORT
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC | Period: 7 days
───────────────────────────────────────────────────────────────────
ISK FLOW SUMMARY
───────────────────────────────────────────────────────────────────
  Income:     +15,234,567.89 ISK
  Expenses:    -3,456,789.12 ISK
  ─────────────────────────────
  Net Change: +11,777,778.77 ISK
───────────────────────────────────────────────────────────────────
INCOME BREAKDOWN
───────────────────────────────────────────────────────────────────
  Bounty Prizes ................ 8,500,000 ISK  (56%)
  Mission Rewards .............. 4,200,000 ISK  (28%)
  Market Sales ................. 2,534,567 ISK  (16%)
───────────────────────────────────────────────────────────────────
EXPENSE ANALYSIS
───────────────────────────────────────────────────────────────────
  Market Purchases ............. 2,100,000 ISK
  Transaction Tax ................. 856,789 ISK
  Broker Fees ..................... 500,000 ISK
═══════════════════════════════════════════════════════════════════
```

### Compact Format

For quick checks:
```
Wallet (7d): +11.8M net | Income: 15.2M | Expenses: 3.5M
Top income: Bounties (56%), Missions (28%), Sales (16%)
```

## Error Handling

### ESI Not Configured

```
═══════════════════════════════════════════════════════════════════
ARIA FINANCIAL INTELLIGENCE
───────────────────────────────────────────────────────────────────
Wallet journal access requires ESI authentication.

ARIA works fully without ESI - you can track finances manually
in your operations log or notes.

OPTIONAL: Enable live tracking (~5 min setup)
  → uv run python .claude/scripts/aria-oauth-setup.py
═══════════════════════════════════════════════════════════════════
```

### No Transactions in Period

```
No wallet activity found in the last [N] days.

Possible reasons:
• Account is new or inactive
• Transactions are older than query period
• Try: /wallet-journal --days 30
```

## Self-Sufficiency Context

For pilots with `market_trading: false` in their profile, the wallet journal helps track:
- Manufacturing input costs (minerals bought before restriction)
- Mission and bounty income efficiency
- Insurance payouts vs ship losses
- Which activities generate the most ISK per hour

**Never suggest selling items** to these pilots when analyzing their finances.

## Contextual Suggestions

After displaying wallet journal, suggest ONE related command when relevant:

| Context | Suggest |
|---------|---------|
| High mission income | "For mission optimization, try `/mission-brief`" |
| Manufacturing costs visible | "Check material costs with `/price <item>`" |
| Low income period | "Try `/mining-advisory` for passive income options" |
| Insurance payouts | "Review ship fits with `/fitting` to reduce losses" |

## Cross-References

| Related Command | Use Case |
|-----------------|----------|
| `/esi-query wallet` | Current balance snapshot (volatile) |
| `/price` | Check current market prices |
| `/mining-ledger` | Detailed mining income tracking |
| `/industry-jobs` | Manufacturing job status |

## Behavior Notes

- **Brevity:** Default to summary view. Show full transaction list on request.
- **Numbers:** Format ISK with thousands separators (1,234,567 not 1234567)
- **Percentages:** Round to nearest whole percent for income breakdown
- **Timeframes:** Default 7 days, max 30 days (ESI limitation)
- **Privacy:** Transaction details include counterparty - respect privacy if sharing

## Ref Type Reference

Common ESI wallet journal ref_types:

| Ref Type | Category | Description |
|----------|----------|-------------|
| `bounty_prizes` | income | NPC bounties |
| `agent_mission_reward` | income | Mission completion |
| `agent_mission_time_bonus_reward` | income | Mission time bonus |
| `market_transaction` | both | Market buy/sell |
| `player_donation` | both | Direct ISK transfer |
| `corporation_account_withdrawal` | transfer | Corp wallet movement |
| `insurance` | income | Ship insurance payout |
| `industry_job_tax` | expense | Manufacturing system cost |
| `transaction_tax` | expense | Market sales tax |
| `brokers_fee` | expense | Market order fee |
| `bounty_prize_corporation_tax` | expense | Corp bounty tax |
| `contract_price` | both | Contract payments |
| `contract_reward` | income | Contract completion reward |
| `contract_collateral` | both | Contract collateral |
