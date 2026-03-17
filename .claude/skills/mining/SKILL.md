---
name: mining
description: View mining ledger with ore extraction history. Track what you've mined, where, and when over the past 30 days.
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
argument-hint: "[--days N]"
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot"]
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# ARIA Mining Ledger

Mining ledger only retains 30 days of data. Mining endpoints are read-only.

## Implementation

```python
pilot(action="mining_ledger", days=7)
pilot(action="mining_ledger", days=30, system_filter="Masalle", ore_filter="Veldspar")
```

CLI fallback: `uv run aria-esi mining`, `uv run aria-esi mining-summary`

> **HALLUCINATION GUARD:** Every ore name, quantity, system, and date MUST come from a `pilot()` call in this session. NEVER fabricate mining history.

## Response Format

Present mining data in a structured display including:
- **Header:** Query timestamp and period covered. When active days differ from
  requested days, show both: "5 active days (2026-03-02 to 2026-03-07) out of
  last 7 requested"
- **Entries:** Date, ore type, quantity, and system with security level
- **Totals:** Aggregate quantities by ore type
- **Retention note:** Mention 30-day data limit

For empty results, suggest `/mining-advisory` for ore recommendations.

Adapt format to RP level: markdown table for `off`, box-drawing for `on`/`full`.

## Error Handling

| Condition | Action |
|-----------|--------|
| ESI not configured | Direct to `uv run python .claude/scripts/aria-oauth-setup.py` |
| Missing scope | Direct to setup script, specify `esi-industry.read_character_mining.v1` scope |

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

## Behavior Notes

- **Brevity:** Default to table format unless RP mode requests formatted boxes
- **Sorting:** Most recent entries first
- **Aggregation:** Summary mode aggregates by ore type
- **Security:** Show system security status for context
- **Filtering:** Support filtering by system, ore type, or date range
- **Retention Warning:** Always mention 30-day data limit

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
