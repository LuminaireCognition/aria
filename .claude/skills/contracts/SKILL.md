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

> **HALLUCINATION GUARD:** Every contract, type, status, price, and counterparty in the response MUST come from a `pilot(action="contracts", ...)` MCP call or CLI call made in this session. If neither was called or returned an error, present only the error state. NEVER fill in contracts from training data.

**You MUST call the MCP tool or CLI command below before presenting any contract data.** Do not summarize, guess, or present contracts without executing the command first.

## Contract Types

Item exchange, courier, auction, loan. The output includes type and status fields for each contract.

## Implementation

### MCP (preferred)

```
pilot(action="contracts")
pilot(action="contracts", status_filter="active")
pilot(action="contracts", type_filter="courier")
pilot(action="contracts", issued=True, received=False)
pilot(action="contracts", status_filter="completed", limit=10)
```

**Parameters:**
| Parameter | Description | Default |
|-----------|-------------|---------|
| `status_filter` | `"active"`, `"completed"`, or omit for all | None |
| `type_filter` | `"item_exchange"`, `"courier"`, `"auction"` | None |
| `issued` | Include contracts you issued | True |
| `received` | Include contracts assigned to you | True |
| `limit` | Maximum contracts to display | 50 |

### CLI (fallback)

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi contracts [options]
```

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
