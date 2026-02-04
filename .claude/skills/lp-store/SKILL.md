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

# ARIA Loyalty Points Module

## Purpose

Track Loyalty Points (LP) earned from mission running and browse LP store offers. For self-sufficient pilots, the LP store is the **primary way to acquire faction modules, implants, and special items** without using the player market.

## Trigger Phrases

- "check my LP" / "LP balance"
- "how much LP do I have"
- "what can I buy with LP"
- "LP store" / "loyalty store"
- "Federation Navy LP store"
- `/lp-store`

## Commands

### LP Balance Check

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi lp
```

Shows LP balances across all corporations where you have earned loyalty points.

### Browse LP Store

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi lp-offers "Federation Navy"
PYTHONPATH=.claude/scripts uv run python -m aria_esi lp-offers fed\ navy --search implant
PYTHONPATH=.claude/scripts uv run python -m aria_esi lp-offers 1000120 --max-lp 5000
PYTHONPATH=.claude/scripts uv run python -m aria_esi lp-offers "Federation Navy" --affordable
```

Options:
- `--search <term>` - Filter by item name
- `--max-lp <N>` - Only show offers costing N LP or less
- `--affordable` - Only show offers you can currently afford (requires auth)

### Analyze for Self-Sufficiency

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi lp-analyze "Federation Navy"
```

Identifies offers that require **only LP + ISK** (no market items needed) - ideal for self-sufficient gameplay.

## Corporation Shortcuts

Common corporation names have shortcuts for convenience:

| Shortcut | Corporation | Corp ID |
|----------|-------------|---------|
| `fed navy`, `federation navy` | Federation Navy | 1000120 |
| `cal navy`, `caldari navy` | Caldari Navy | 1000035 |
| `rep fleet`, `republic fleet` | Republic Fleet | 1000182 |
| `amarr navy`, `imperial navy` | Amarr Navy | 1000003 |
| `soe`, `sisters` | Sisters of EVE | 1000130 |
| `mordus`, `mordus legion` | Mordu's Legion | 1000139 |
| `concord` | CONCORD | 1000125 |
| `thukker` | Thukker Mix | 1000171 |

## Response Format

### LP Balance Report

```
═══════════════════════════════════════════════════════════════════
ARIA LOYALTY POINTS SUMMARY
───────────────────────────────────────────────────────────────────
Total LP: [sum] across [N] corporations
───────────────────────────────────────────────────────────────────
BALANCES:
• Federation Navy: 45,230 LP
• Federal Navy Academy: 12,100 LP
• [etc.]
───────────────────────────────────────────────────────────────────
Use `/lp-store <corp>` to browse available offers.
═══════════════════════════════════════════════════════════════════
```

### LP Store Browse

```
═══════════════════════════════════════════════════════════════════
ARIA LP STORE - Federation Navy
───────────────────────────────────────────────────────────────────
Your Balance: 45,230 LP (if authenticated)
Offers Shown: 25 of 342 (filtered)
───────────────────────────────────────────────────────────────────
AVAILABLE OFFERS:

Federation Navy Hammerhead (5x)
  Cost: 2,500 LP + 250,000 ISK
  Requires: 5x Hammerhead I

Federation Navy Magnetic Field Stabilizer
  Cost: 15,000 LP + 15,000,000 ISK
  ✓ No items required (LP + ISK only)

[etc.]
───────────────────────────────────────────────────────────────────
Tip: Use --search <term> to filter, --affordable to show buyable items
═══════════════════════════════════════════════════════════════════
```

### Self-Sufficiency Analysis

```
═══════════════════════════════════════════════════════════════════
ARIA LP STORE ANALYSIS - Federation Navy
───────────────────────────────────────────────────────────────────
Total Offers: 342
LP + ISK Only: 87 (self-sufficient friendly)
Requires Items: 255 (need market/loot)
───────────────────────────────────────────────────────────────────
SELF-SUFFICIENT OFFERS (sample):

Hardwiring - Zainou 'Gnome' Shield Management SM-70
  Cost: 15,000 LP + 15,000,000 ISK
  Type: Implant (slot 7)

Navy Cap Booster 400 (100x)
  Cost: 500 LP + 50,000 ISK
  Type: Charges

[etc.]
───────────────────────────────────────────────────────────────────
These offers require only LP + ISK, no additional items.
═══════════════════════════════════════════════════════════════════
```

## Self-Sufficiency Context

**CRITICAL:** For self-sufficient pilots (market_trading: false), LP stores are the **primary acquisition method** for:

1. **Faction Modules** - Navy damage mods, tank mods, etc.
2. **Implants** - Hardwirings and attribute implants
3. **Faction Ammo** - Navy charges and missiles
4. **Blueprints** - Some faction BPCs available

### Offer Types by Accessibility

| Type | Self-Sufficient | Notes |
|------|-----------------|-------|
| LP + ISK only | **YES** | Fully accessible |
| LP + ISK + Tags | **Maybe** | Tags drop from missions |
| LP + ISK + Base Item | **Maybe** | If item is lootable/manufacturable |
| LP + ISK + Market Item | **NO** | Requires player market |

### Recommended Workflow

1. **Check LP balance** after mission sessions
2. **Browse affordable offers** to plan LP spending
3. **Use lp-analyze** to find self-sufficient options
4. **Prioritize implants** (permanent value) over consumables

## Behavior

- **Intelligence Framing:** Present LP data as "accessing GalNet loyalty databases" or "querying faction reward systems"
- Always show which items require additional materials vs LP+ISK only
- Highlight self-sufficient options when pilot has market restrictions
- Note when offers provide good value for the LP spent
- Suggest browsing specific categories (implants, modules) based on pilot goals

## Experience-Based Adaptation

### LP Store Explanation

**new:**
```
WHAT IS THE LP STORE?
LP (Loyalty Points) are earned by completing missions for NPC corporations.
You can spend LP + ISK at the LP Store to buy special items that are often
better than standard market items. Each corporation has different offers.

To buy: Open the station services panel, click "Loyalty Point Store"
```

**intermediate:**
```
LP Store offers for Federation Navy. Faction modules require base item + LP + ISK.
Items marked "No items required" can be purchased with just LP + ISK.
```

**veteran:**
```
Fed Navy LP store. 87 LP+ISK only offers. Hardwirings at standard rates.
```

## Contextual Suggestions

After providing LP information, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Low LP balance | "Run `/mission-brief` to prepare for LP farming" |
| Looking at implants | "Check `/clones` for current implant slots" (when implemented) |
| Expensive offers | "Use `/wallet-journal` to track ISK income" |
| After mission completion | "Log with `/journal mission` to track progress" |

## Error Handling

### No LP Balance

```
No LP balances found. Loyalty Points are earned by completing missions
for NPC corporations like Federation Navy, Sisters of EVE, etc.

Run missions to build your LP balance, then return to browse offers.
```

### Corporation Not Found

```
Could not find corporation: [query]

Try:
• Full name: "Federation Navy"
• Shortcut: "fed navy"
• Corp ID: 1000120

Use `/lp-store` with no arguments to see your LP balances and which
corporations you've earned LP with.
```

### No LP Store for Corporation

```
[Corporation] does not have an LP store.

Not all corporations offer loyalty rewards. Mission-giving NPC corps
(Federation Navy, Sisters of EVE, etc.) have LP stores.
```

## Scopes Required

- `esi-characters.read_loyalty.v1` - Required for LP balance
- LP store offers endpoint is **public** (no auth required)

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run LP balance commands - they will timeout
2. **LP store offers still work** - the offers endpoint is public
3. **RESPOND IMMEDIATELY** with:
   ```
   LP balance query requires live ESI data which is currently unavailable.

   Check your LP balances in-game:
   • Station services → Loyalty Point Store
   • Your balance is shown at the top

   Note: LP store browsing still works - use '/lp-store <corp>' to view offers.

   ESI usually recovers automatically.
   ```
4. **DO NOT** block waiting for ESI

### If ESI is AVAILABLE:

Proceed with normal LP queries.
