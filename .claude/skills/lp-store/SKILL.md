---
name: lp-store
description: Track LP balances and browse LP store offers. Essential for self-sufficient gameplay where LP store is the primary source of faction items.
category: financial
triggers:
  - "/lp-store"
  - "check my LP"
  - "LP balance"
  - "what can I buy with LP"
  - "LP store offers"
requires_pilot: true
esi_scopes:
  - esi-characters.read_loyalty.v1
argument-hint: "[--corp NAME|--item NAME]"
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot", "mcp__aria-universe__market"]
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# Loyalty Points Module

## Required Tool Calls (MANDATORY)

| Query Type | MCP Call (preferred) | CLI Fallback |
|------------|---------------------|--------------|
| LP balance | `pilot(action="lp_balance")` | `uv run aria-esi lp` |
| LP store browse | `pilot(action="lp_offers", corporation_name="<corp>")` | `uv run aria-esi lp-offers "<corp>"` |
| LP analysis | `pilot(action="lp_offers", corporation_name="<corp>")` | `uv run aria-esi lp-analyze "<corp>"` |

**Corporation matching:** The corporation name MUST match the user's request exactly.

> **HALLUCINATION GUARD:** Every LP balance, store offer, item name, and cost in the response MUST come from a `pilot(action="lp_balance")` or `pilot(action="lp_offers", ...)` MCP call, or a CLI call made in this session. If neither was called or returned an error, present only the error state. NEVER fill in offers from training data — corporation LP stores change and training data may show items from the wrong corporation.

## Commands

### MCP (preferred)

```
pilot(action="lp_balance")
pilot(action="lp_offers", corporation_name="Federation Navy")
pilot(action="lp_offers", corporation_name="Federation Navy", search="implant")
pilot(action="lp_offers", corporation_name="Federation Navy", max_lp=5000)
pilot(action="lp_offers", corporation_name="Federation Navy", affordable=True)
```

**Parameters:**

| Action | Parameter | Description | Default |
|--------|-----------|-------------|---------|
| `lp_balance` | *(none)* | Lists LP per corporation | - |
| `lp_offers` | `corporation_name` | Corp name, ID, or shortcut (required) | - |
| `lp_offers` | `search` | Filter offers by item name | None |
| `lp_offers` | `max_lp` | Maximum LP cost to show | None |
| `lp_offers` | `affordable` | Only show offers you can afford | False |

### CLI (fallback)

```bash
uv run aria-esi lp
uv run aria-esi lp-offers "<corp>" [--search <term>] [--max-lp <N>] [--affordable]
uv run aria-esi lp-analyze "<corp>"
```

## Data Locality

LP balance data is fetched live from ESI on every query — no local cache. LP store offers use the public ESI endpoint (no auth required).

Common corporation shortcuts (e.g., "fed navy", "soe", "cal navy") are supported by the CLI.

## Response Format

```
LP STORE - <Corporation>
Your Balance: <N> LP (if authenticated)
Offers Shown: <N> of <total> (filtered)

AVAILABLE OFFERS:

<Item Name> (<quantity>)
  Cost: <N> LP + <N> ISK
  Requires: <item> (or "✓ No items required")

...

Tip: Use --search <term> to filter, --affordable to show buyable items
```

**Variants:**
- Balance-only: List LP per corporation with total.
- Self-sufficiency analysis: Show total offers vs LP+ISK-only count, then list self-sufficient offers.

For self-sufficient pilots (`market_trading: false`), highlight offers requiring only LP + ISK.

## Experience-Based Adaptation

- **New players:** Explain LP concept briefly (earned from missions, spent at LP store).
- **Intermediate:** Show offers directly with LP+ISK-only markers.
- **Veteran:** Terse summary with counts.

## Contextual Suggestions

After providing LP information, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Low LP balance | "Run `/mission-brief` to prepare for LP farming" |
| Looking at implants | "Check `/clones` for current implant slots" |
| Expensive offers | "Use `/wallet-journal` to track ISK income" |
| After mission completion | "Log with `/journal mission` to track progress" |

## Error Handling

### No LP Balance
```
No LP balances found. LP is earned by completing missions for NPC corporations.
Run missions to build your balance, then return to browse offers.
```

### Corporation Not Found
```
Could not find corporation: [query]
Try the full name ("Federation Navy"), a shortcut ("fed navy"), or corp ID (1000120).
Use `/lp-store` with no arguments to see your LP balances.
```

### No LP Store for Corporation
```
[Corporation] does not have an LP store.
Not all corporations offer loyalty rewards. Mission-giving NPC corps have LP stores.
```

## Anti-Patterns

- **WRONG:** Present Caldari Navy items when user asked for Federation Navy LP store
- **RIGHT:** Call `lp-offers "Federation Navy"` — match the exact corporation requested

- **WRONG:** Show LP store offers without making any `lp-offers` CLI call
- **RIGHT:** Call the CLI, present only what it returns

- **WRONG:** Say "you can afford N offers" based only on LP balance without checking ISK cost
- **RIGHT:** Either cross-check wallet balance, or qualify: "N offers within your LP budget (ISK cost not verified)"

- **WRONG:** Dump hundreds of offers as a prose list when user asks "what can I buy"
- **RIGHT:** Use `affordable=True` or `max_lp=<balance>` to filter, then show top 10–15 actionable offers sorted by value. Mention total count and suggest `--search` for specific items.

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
