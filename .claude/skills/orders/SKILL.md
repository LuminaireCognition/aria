---
name: orders
description: View active market orders and order history. Track buy/sell orders, escrow, and fill status.
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
argument-hint: "[--buy|--sell|--history]"
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot"]
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# ARIA Market Orders Monitor

If the user asks to place or modify orders, explain this requires the Market window (Alt+R) in the EVE client.

> **HALLUCINATION GUARD:** Present only data returned by the CLI. If the command fails or returns empty, say so — do not fabricate order details.

**Note:** This skill uses CLI (`uv run aria-esi orders`) rather than the market MCP dispatcher because personal orders require authenticated ESI access.

## Implementation

Run the ESI wrapper command:
```bash
uv run aria-esi orders [options]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--buy` | Show only buy orders | - |
| `--sell` | Show only sell orders | - |
| `--history` | Include expired/cancelled orders | - |
| `--limit N` | Limit results | 50 |

> Active orders are shown by default. Use `--history` to include expired/cancelled orders.

### Key Response Fields

The CLI returns JSON with order details: type name, price, volume total/remaining, fill percent, location, expiry/days remaining, escrow (for buy orders), and state (active/expired/cancelled).

Summary block includes `active_orders`, `buy_orders`, `sell_orders`, `total_escrow`, `total_sell_value`.

Empty response returns `"orders": []` with a message.

## Response Format

Present orders in a markdown table with query timestamp:

```markdown
## Market Orders
*Query: {timestamp}*

### Active Orders ({count})

**Sell Orders ({count})**
| Item | Price | Qty | Filled | Location |
|------|-------|-----|--------|----------|
| {type_name} | {price} | {volume} | {fill_pct}% | {location} |

**Buy Orders ({count})**
| Item | Price | Qty | Escrow | Location |
|------|-------|-----|--------|----------|
| {type_name} | {price} | {volume} | {escrow} | {location} |

**Totals:** {escrow} escrow locked | {sell_value} sell value pending
```

If no orders: state that no active market orders exist and note that orders are placed via Market window (Alt+R).

If ESI is not configured or scope is missing: state the limitation and provide the setup command (`uv run python .claude/scripts/aria-oauth-setup.py`).

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

## Behavior Notes

- **Sorting:** Active orders first, then by expiration date
- **Fill Status:** Show percentage filled for partially completed orders
- **Escrow:** Always show escrow amounts for buy orders
- **Duration:** Show days remaining until expiration
- **Location:** Abbreviate long station names

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
