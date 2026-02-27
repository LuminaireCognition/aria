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

Contract actions (accept, create, cancel) require in-game action. ARIA monitors only.

## Contract Types

Item exchange, courier, auction, loan. The CLI output includes type and status fields for each contract.

## Implementation

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

## Response Format

Present contracts organized by status (Outstanding, In Progress, Completed). Include:

```
## Personal Contracts
*Query: [timestamp]*

### Outstanding (N)
| Type | Title | Price/Reward | Expires |
|------|-------|--------------|---------|
| ... | ... | ... | ... |

### In Progress (N)
- **Courier** to [dest] - [reward], [collateral] collateral - [days] left

*ARIA monitors contracts but cannot accept, create, or modify them.*
```

For no contracts: "No active contracts found."

## Courier Contract Guidance

For courier contracts, assess route security via `universe(action="route")` and calculate ISK/jump ratio. Warn about gank risk on trade routes for freighter-sized volumes.

## Error Handling

- **ESI not configured:** "Contract monitoring requires ESI authentication. Run `uv run python .claude/scripts/aria-oauth-setup.py` to enable."
- **Missing scope:** "ESI is configured but contracts scope is missing. Re-run OAuth setup and select `esi-contracts.read_character_contracts.v1`."

## Contextual Suggestions

After displaying contracts, suggest ONE related action when relevant:

| Context | Suggest |
|---------|---------|
| Courier in progress | "Track route security with `/threat-assessment`" |
| Auction with bids | "Monitor for outbids - check back before expiry" |
| Item exchange pending | "Check market prices with `/price <item>`" |
| No contracts | "Consider selling LP store items via contract" |

## Behavior Notes

- **Brevity:** Default to summary view unless detail requested
- **Expiration:** Highlight contracts expiring within 24 hours
- **In Progress:** Always show courier collateral at risk
- **Location Resolution:** Convert station IDs to readable names
- **ISK Formatting:** Use standard ISK format (e.g., "50M ISK")
- **Privacy:** Don't expose counterparty details unnecessarily
