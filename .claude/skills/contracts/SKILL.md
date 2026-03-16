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
argument-hint: "[--type exchange|courier|auction]"
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot"]
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# ARIA Contracts Module

Contract actions (accept, create, cancel) require in-game action. ARIA monitors only.

> **HALLUCINATION GUARD:** Every contract, type, status, price, and counterparty in the response MUST come from a `pilot(action="contracts", ...)` MCP call or CLI call made in this session. If neither was called or returned an error, present only the error state. NEVER fill in contracts from training data.

**You MUST call the MCP tool or CLI command below before presenting any contract data.** Do not summarize, guess, or present contracts without executing the command first.

## Execution Rules

- **Always call the MCP tool.** Never infer contract status from context or prior
  queries. Contracts change in real-time — stale inference produces false negatives.
- If the MCP tool returns `scope_not_authorized`, report the specific missing scope
  and setup command. Do not suggest ESI is entirely unconfigured.

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
uv run aria-esi contracts [options]
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


### Field → Source Mapping

Every table column MUST map to the specific JSON field listed here. Do not swap, merge, or omit columns.

| Table Column | JSON Field | Notes |
|-------------|-----------|-------|
| Type | `type_display` | "Item Exchange", "Courier", "Auction" |
| Title | `title` | Contract title or type if no custom title |
| Price/Reward | `price_formatted` | For couriers, use `reward_formatted` |
| Collateral | `collateral_formatted` | Courier contracts only |
| Issued Date | `date_issued` | Format as YYYY-MM-DD |
| Expires | `date_expired` | Format as YYYY-MM-DD or "days remaining" |
| Status | `status_display` | "Outstanding", "In Progress", "Finished" |
| Issuer | `issuer_name` | The character who created the contract |
| Acceptor | `acceptor_name` | The character who accepted (if any) |

**Column discipline:** The Status value (`status_display`) MUST only appear in a Status column. Never place status in the Date column. If a table has no Status column, omit the value rather than misplace it.

**Direction clarity:** When showing contracts, indicate whether the authenticated pilot is the issuer or acceptor. For self-issued contracts, show the acceptor as the counterparty.

## Courier Contract Guidance

For courier contracts, assess route security via `universe(action="route")` and calculate ISK/jump ratio. Warn about gank risk on trade routes for freighter-sized volumes.

## Error Handling (Mandatory)

When the MCP tool returns an error response:

1. **Check `error` field value:**
   - If `"scope_not_authorized"` → Tell the user: "ESI is connected but the
     contracts scope (`esi-contracts.read_character_contracts.v1`) isn't authorized.
     Re-run OAuth setup to add it: `uv run aria-esi setup`"
   - If credentials RuntimeError / `"no_credentials"` → Tell the user: "ESI
     authentication isn't configured yet. Run `uv run aria-esi setup` to connect
     your character."

2. **Never say "ESI authentication isn't configured" when the error is
   `scope_not_authorized`.** Other ESI features work — the user just needs
   to add one scope.

3. **If the tool errors, report the error.** Do not fall back to "no contracts
   found" — that fabricates a successful result from a failed call.

   This applies equally to filtered queries. If the user asks about courier
   contracts specifically, you must still call the MCP tool — do not reason
   that "the general query failed, so a filtered query would also fail,
   so there must be no courier contracts." That logic fabricates data.
   Report the same error regardless of filter parameters.

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

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
