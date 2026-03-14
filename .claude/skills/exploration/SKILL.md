---
name: exploration
description: ARIA exploration and hacking guidance for Eve Online. Use for relic/data site analysis, hacking tips, or exploration loot identification.
model: sonnet
category: operations
triggers:
  - "/exploration"
  - "exploration analysis"
  - "I found a [site name]"
  - "hacking tips"
  - "what's this loot worth"
  - "relic site"
  - "data site"
requires_pilot: true
injected_prerequisites:
  - reference/mechanics/exploration_sites.md
  - reference/mechanics/hacking_guide.md
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/exploration.md
argument-hint: "[--system NAME|--region NAME]"
allowed-tools: [Read, Grep, Glob, "mcp__aria-universe__universe", "mcp__aria-universe__sde"]
preferred_max_lines: 45
---

# Exploration Analysis Module

```
/exploration <site_name>          # Site analysis (loot, containers, hacking)
/exploration hacking              # Hacking mechanics guide
/exploration loot <item_name>     # Loot identification and valuation
```

## Tool Calls

| Step | Call | Provides |
|------|------|----------|
| 1 | `market(action="prices", items=[...])` | Loot valuations (specific items only) |
| 2 | `sde(action="item_info", item="...")` | Individual loot item details |

Site and hacking reference data is injected below — do not re-read those files.

### Field → Source Mapping

| Output Field | Source |
|-------------|--------|
| Site classification (Relic/Data) | `exploration_sites.md` |
| Site prefix meaning (Ruined/Decayed/etc.) | `exploration_sites.md` |
| Security band for site type | `exploration_sites.md` |
| Container types and counts | `exploration_sites.md` |
| Probable loot categories | `exploration_sites.md` |
| Hacking mechanics (coherence, nodes) | `hacking_guide.md` |
| Hacking strategy | `hacking_guide.md` |
| Individual loot item details | `sde(action="item_info")` |
| Loot market value | `market(action="prices")` |

## Site Names vs SDE Items

Site names (e.g., "Serpentis Temple", "Ruined Sansha Monument") are cosmic signatures, not SDE items. Do not search SDE for site names — use `exploration_sites.md` instead.

Individual loot items (e.g., "Intact Armor Plates", "Emission Scope Sharpener") are SDE items — use `sde(action="item_info")`.

## Response Format

```
═══════════════════════════════════════════
EXPLORATION SITE ANALYSIS
───────────────────────────────────────────
SITE NAME: [Full site name]
CLASSIFICATION: [Relic/Data] Site ([Faction])
SECURITY ASSESSMENT: [Safe/Hostile presence expected]
───────────────────────────────────────────
EXPECTED CONTAINERS: [Number and types]

PROBABLE LOOT:
- [Item categories with brief descriptions]

HACKING ADVISORY:
[Strategy for this site type]

LORE CONTEXT:
[In-universe explanation of what this site represents]
═══════════════════════════════════════════
```

Quick site assessment first. Lore and full loot tables on request.

## Contextual Suggestions

After analysis, suggest ONE related command when relevant:

| Context | Suggest |
|---------|---------|
| Site in dangerous space | `/threat-assessment` |
| Needs exploration fit | `/fitting` |
| Notable loot discovered | `/journal exploration` |
| Site has hostile NPCs | `/mission-brief` |

## Output format

- Site table: cap at 6 sites sorted by estimated value, then "... and N more sites in system"
- Loot breakdown: top 3 items by value only
- Target: ≤30 lines

## Rules

- Every coherence value, node mechanic, and container type must come from the prerequisite files — quote exactly as written
- Do not cite "Rule of 6" or other numbered heuristics absent from `hacking_guide.md`
- Prefix/security mapping: Crumbling/Local = highsec; Decayed/Regional = lowsec; Ruined/Central = nullsec or WH C1-C3; Forgotten/Unsecured = WH C4+ Sleeper sites — flag mismatches between prefix and reported system security
- Regular sites allow retry on hack failure; only Ghost Sites are one-attempt — verify against `exploration_sites.md`
- The System Core is the hack objective, not a defensive tool
- Note items useful for self-sufficient gameplay
- Append a one-line `Sources:` footer listing MCP calls and prerequisite reference files consulted

## Injected Reference Data

### Reference: Exploration Sites (injected)
<!-- prerequisite: reference/mechanics/exploration_sites.md -->
!`cat reference/mechanics/exploration_sites.md`

### Reference: Hacking Guide (injected)
<!-- prerequisite: reference/mechanics/hacking_guide.md -->
!`cat reference/mechanics/hacking_guide.md`
