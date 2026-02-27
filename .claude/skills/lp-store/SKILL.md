---
name: lp-store
description: Track LP balances and browse LP store offers. Essential for self-sufficient gameplay where LP store is the primary source of faction items.
model: haiku
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
---

# Loyalty Points Module

## Commands

### LP Balance Check

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi lp
```

### Browse LP Store

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi lp-offers "<corp>"
PYTHONPATH=.claude/scripts uv run python -m aria_esi lp-offers "<corp>" --search <term>
PYTHONPATH=.claude/scripts uv run python -m aria_esi lp-offers "<corp>" --max-lp <N>
PYTHONPATH=.claude/scripts uv run python -m aria_esi lp-offers "<corp>" --affordable
```

### Analyze for Self-Sufficiency

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi lp-analyze "<corp>"
```

Identifies offers requiring only LP + ISK (no market items needed).

## Data Locality

LP balance data is fetched live from ESI on every query — no local cache. LP store offers use the public ESI endpoint (no auth required).

Common corporation shortcuts (e.g., "fed navy", "soe", "cal navy") are supported by the CLI.

## Required Tool Calls (MANDATORY)

| Query Type | Required Call |
|------------|-------------|
| LP balance | `PYTHONPATH=.claude/scripts uv run python -m aria_esi lp` |
| LP store browse | `PYTHONPATH=.claude/scripts uv run python -m aria_esi lp-offers "<corp>"` |
| LP analysis | `PYTHONPATH=.claude/scripts uv run python -m aria_esi lp-analyze "<corp>"` |

**Corporation matching:** The corporation name MUST match the user's request exactly.

> **HALLUCINATION GUARD:** Every LP balance, store offer, item name, and cost in the response MUST come from a CLI call made in this session. If the CLI was not called or returned an error, present only the error state. NEVER fill in offers from training data — corporation LP stores change and training data may show items from the wrong corporation.

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
