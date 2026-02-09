---
name: mining
description: View mining ledger with ore extraction history. Track what you've mined, where, and when over the past 30 days.
model: haiku
category: operations
triggers:
  - "/mining"
  - "my mining ledger"
  - "what have I mined"
  - "mining history"
  - "mining stats"
requires_pilot: true
esi_scopes:
  - esi-industry.read_character_mining.v1
---

# ARIA Mining Ledger

## Purpose

Query the capsuleer's mining ledger to display ore extraction history. Shows what was mined, in which systems, and when. Essential for tracking mining operations and planning resource acquisition.

## CRITICAL: Read-Only Limitation

**ESI mining endpoints are READ-ONLY.** ARIA can:
- View mining history (past 30 days)
- Display ore quantities by type and system
- Aggregate mining data by date, ore, or location

**ARIA CANNOT:**
- Start or stop mining
- Jettison ore
- Control mining lasers
- Interact with the EVE client in any way

## CRITICAL: Data Retention

**Mining ledger only retains 30 days of data.** Older records are permanently deleted by the game server. If historical tracking is needed, export data periodically.

## CRITICAL: Data Volatility

Mining ledger data is **semi-stable** - updates as you mine:

1. **Display query timestamp** - data is aggregated by day
2. **Daily aggregation** - individual mining cycles are summed per day
3. **30-day window** - older data is purged automatically
4. **Safe to cache** - data only updates when actively mining

## Trigger Phrases

- `/mining`
- "my mining ledger"
- "what have I mined"
- "mining history"
- "ore extraction"
- "how much ore"
- "mining stats"
- "mining summary"

## ESI Requirement

**Requires:** `esi-industry.read_character_mining.v1` scope

This scope is included in ARIA's default scope set and should already be authorized.

If scope is not authorized:
```
Mining ledger access requires ESI authentication.

To enable: uv run python .claude/scripts/aria-oauth-setup.py
Select "esi-industry.read_character_mining.v1" during scope selection.
```

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run mining ledger commands - they will timeout
2. **RESPOND IMMEDIATELY** with:
   ```
   Mining ledger requires live ESI data which is currently unavailable.

   Check this in-game:
   • Industry window (Alt+S) → Mining Ledger tab
   • Shows ore extraction history for past 30 days

   ESI usually recovers automatically.
   ```
3. **DO NOT** block waiting for ESI

### If ESI is AVAILABLE:

Proceed with normal mining ledger queries.

## Implementation

Run the ESI wrapper commands:
```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi mining [options]
PYTHONPATH=.claude/scripts uv run python -m aria_esi mining-summary [options]
```

### Commands

| Command | Description |
|---------|-------------|
| `mining` | Detailed mining ledger (by date and ore) |
| `mining-summary` | Aggregate summary (totals by ore type) |

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--days N` | Limit to last N days | 30 (all available) |
| `--system <name>` | Filter by system name | - |
| `--ore <type>` | Filter by ore type | - |

### JSON Response Structure

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "semi_stable",
  "character_id": 2119654321,
  "summary": {
    "total_entries": 15,
    "total_quantity": 125000,
    "unique_ores": 4,
    "unique_systems": 2,
    "days_covered": 7
  },
  "entries": [
    {
      "date": "2026-01-15",
      "type_id": 1230,
      "type_name": "Veldspar",
      "quantity": 15000,
      "solar_system_id": 30002682,
      "solar_system_name": "Masalle",
      "security": 0.9
    },
    {
      "date": "2026-01-14",
      "type_id": 1228,
      "type_name": "Scordite",
      "quantity": 8500,
      "solar_system_id": 30002682,
      "solar_system_name": "Masalle",
      "security": 0.9
    }
  ]
}
```

### Mining Summary Response

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "semi_stable",
  "character_id": 2119654321,
  "summary": {
    "total_quantity": 125000,
    "unique_ores": 4,
    "days_covered": 7
  },
  "by_ore": [
    {
      "type_id": 1230,
      "type_name": "Veldspar",
      "total_quantity": 75000
    },
    {
      "type_id": 1228,
      "type_name": "Scordite",
      "total_quantity": 35000
    }
  ],
  "by_system": [
    {
      "solar_system_id": 30002682,
      "solar_system_name": "Masalle",
      "total_quantity": 100000
    }
  ]
}
```

### Empty Response

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "semi_stable",
  "character_id": 2119654321,
  "summary": {
    "total_entries": 0,
    "total_quantity": 0,
    "unique_ores": 0,
    "unique_systems": 0,
    "days_covered": 0
  },
  "entries": [],
  "message": "No mining activity in the last 30 days"
}
```

## Common Ore Types

| Ore | Type ID | Primary Mineral | Where Found |
|-----|---------|-----------------|-------------|
| Veldspar | 1230 | Tritanium | High-sec |
| Scordite | 1228 | Pyerite, Tritanium | High-sec |
| Pyroxeres | 1224 | Pyerite, Nocxium | High-sec |
| Plagioclase | 1222 | Mexallon, Pyerite | High-sec |
| Omber | 1227 | Isogen, Pyerite | Low-sec, null |
| Kernite | 1226 | Mexallon, Isogen | Low-sec |
| Jaspet | 1223 | Mexallon, Nocxium | Low-sec |
| Hemorphite | 1231 | Isogen, Nocxium | Low-sec |
| Hedbergite | 1232 | Isogen, Nocxium | Low-sec |
| Gneiss | 1229 | Mexallon, Isogen | Null-sec |
| Dark Ochre | 1232 | Nocxium, Isogen | Null-sec |
| Spodumain | 1233 | Tritanium, Pyerite | Null-sec |
| Crokite | 1225 | Nocxium, Zydrine | Null-sec |
| Bistot | 1223 | Pyerite, Zydrine | Null-sec |
| Arkonor | 1221 | Tritanium, Megacyte | Null-sec |
| Mercoxit | 11396 | Morphite | Null-sec |

Note: Compressed ore variants have different type IDs.

## Response Formats

### Standard Display (rp_level: off or lite)

```markdown
## Mining Ledger (Last 7 days)
*Query: 14:30 UTC*

| Date | Ore | Quantity | System |
|------|-----|----------|--------|
| Jan 15 | Veldspar | 15,000 | Masalle (0.9) |
| Jan 15 | Scordite | 8,500 | Masalle (0.9) |
| Jan 14 | Veldspar | 12,000 | Masalle (0.9) |

**Total:** 35,500 units across 2 ore types

*Mining ledger retains 30 days of history.*
```

### Formatted Version (rp_level: moderate or full)

```
═══════════════════════════════════════════════════════════════════
ARIA MINING LEDGER
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC | Period: Last 7 days
───────────────────────────────────────────────────────────────────
EXTRACTION RECORD
───────────────────────────────────────────────────────────────────
  2026-01-15 | Masalle (0.9)
    Veldspar          15,000 units
    Scordite           8,500 units

  2026-01-14 | Masalle (0.9)
    Veldspar          12,000 units
───────────────────────────────────────────────────────────────────
TOTALS
───────────────────────────────────────────────────────────────────
  Veldspar:           27,000 units
  Scordite:            8,500 units
  ────────────────────────────────
  Total:              35,500 units
───────────────────────────────────────────────────────────────────
Data retention: 30 days (older records purged automatically)
═══════════════════════════════════════════════════════════════════
```

### No Activity Display

```
═══════════════════════════════════════════════════════════════════
ARIA MINING LEDGER
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC
───────────────────────────────────────────────────────────────────
No mining activity recorded in the last 30 days.

Mining operations are tracked automatically when you:
• Extract ore using mining lasers
• Harvest ice
• Mine gas clouds

Get started with `/mining-advisory` for ore recommendations.
═══════════════════════════════════════════════════════════════════
```

## Error Handling

### ESI Not Configured

```
═══════════════════════════════════════════════════════════════════
ARIA MINING LEDGER
───────────────────────────────────────────────────────────────────
Mining ledger access requires ESI authentication.

ARIA works fully without ESI - you can manually track
your mining operations if needed.

OPTIONAL: Enable live tracking (~5 min setup)
  uv run python .claude/scripts/aria-oauth-setup.py
═══════════════════════════════════════════════════════════════════
```

### Missing Scope

```
═══════════════════════════════════════════════════════════════════
ARIA MINING LEDGER - SCOPE NOT AUTHORIZED
───────────────────────────────────────────────────────────────────
ESI is configured but mining ledger scope is missing.

To enable:
  uv run python .claude/scripts/aria-oauth-setup.py

Select "esi-industry.read_character_mining.v1" during setup.
═══════════════════════════════════════════════════════════════════
```

## Contextual Suggestions

| Context | Suggest |
|---------|---------|
| Has mining data | "Check ore prices with `/price <ore>`" |
| Mining in dangerous space | "Assess system security with `/threat-assessment`" |
| No mining activity | "Get ore recommendations with `/mining-advisory`" |

## Cross-References

| Related Command | Use Case |
|-----------------|----------|
| `/mining-advisory` | Get ore recommendations based on your skills |
| `/price` | Check market prices for mined ores |
| `/threat-assessment` | Assess safety of mining systems |
| `/industry-jobs` | Check if ore is being processed |

## Self-Sufficiency Context

For pilots with `market_trading: false`:
- Mining is a primary resource acquisition method
- Track ore extraction for manufacturing planning
- Correlate with `/industry-jobs` for material requirements
- No market sales means all ore is for personal use

## Behavior Notes

- **Brevity:** Default to table format unless RP mode requests formatted boxes
- **Sorting:** Most recent entries first
- **Aggregation:** Summary mode aggregates by ore type
- **Security:** Show system security status for context
- **Filtering:** Support filtering by system, ore type, or date range
- **Retention Warning:** Always mention 30-day data limit
