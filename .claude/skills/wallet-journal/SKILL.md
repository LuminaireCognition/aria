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
argument-hint: "[--days N] [--type TYPE]"
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot"]
preferred_max_lines: 20
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# Wallet Journal

## Command Syntax

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

> **HALLUCINATION GUARD:** Every ISK amount, transaction, and breakdown in the response MUST come from the CLI call made in this session. NEVER fabricate wallet data from training data. If the CLI was not called or returned an error, present only the error state.

## Response Format

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

### Compact Format

For quick checks:
```
Wallet (7d): +11.8M net | Income: 15.2M | Expenses: 3.5M
Top income: Bounties (56%), Missions (28%), Sales (16%)
```

## Error Handling

### No Transactions in Period

```
No wallet activity found in the last [N] days.

Possible reasons:
• Account is new or inactive
• Transactions are older than query period
• Try: /wallet-journal --days 30
```

## Behavior Notes

- If profile has `market_trading: false`, never suggest selling items.
- **Brevity:** Default to summary view. Show full transaction list on request.
- **Numbers:** Format ISK with thousands separators (1,234,567 not 1234567)
- **Percentages:** Round to nearest whole percent for income breakdown
- **Timeframes:** Default 7 days, max 30 days (ESI limitation)
- **Privacy:** Transaction details include counterparty - respect privacy if sharing

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
