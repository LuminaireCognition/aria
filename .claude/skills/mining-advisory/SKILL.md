---
name: mining-advisory
description: ARIA mining operations guidance for Eve Online. Use for ore recommendations, belt intel, Venture fitting, or mining optimization.
model: sonnet
category: operations
triggers:
  - "/mining-advisory"
  - "mining advisory"
  - "what should I mine"
  - "ore recommendations"
  - "belt intel"
  - "mining optimization"
requires_pilot: true
prerequisite_files:
  - reference/mechanics/ore_database.md
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/ships.md
---

# Mining Operations Module

```
/mining-advisory                      # General ore recommendations for current location
/mining-advisory <system>             # Ore recommendations for a specific system
/mining-advisory --isk                # Rank ores by ISK/m3 (requires market lookup)
```

## Tool Calls

| Step | Call | Provides |
|------|------|----------|
| 1 | Read `reference/mechanics/ore_database.md` | Ore types, security bands, mineral yields |
| 2 | `universe(action="systems", systems=["..."])` | System security status |
| 3 | `market(action="prices", items=[...])` | Current ore/mineral prices (if ISK comparison needed) |

Step 1 must complete before any output. If market prices are unavailable, recommend by mineral utility without ISK rankings. If system security lookup fails, ask the user to confirm.

### Field → Source Mapping

| Output Field | Source |
|-------------|--------|
| Ore names available in system | `ore_database.md` |
| Ore security bands (min sec to spawn) | `ore_database.md` |
| Mineral yields per ore | `ore_database.md` |
| System security status | `universe(action="systems")` |
| Current ore/mineral prices | `market(action="prices")` |
| ISK/m3 rankings | Derived: `ore_database.md` yields x market prices |
| Pilot ship/skills context | `data_sources` pilot files |

## Response Format

```
MINING OPERATIONS ADVISORY
───────────────────────────────────────────
LOCATION: [System if known]
SECURITY: [Sec level]
PILOT VESSEL: [Ship if known]
───────────────────────────────────────────
ORE PRIORITY:

HIGH PRIORITY:
- [Ores with minerals needed for manufacturing]

MODERATE PRIORITY:
- [Secondary ores]

EFFICIENCY NOTES:
[Ship-specific considerations]

SAFETY ADVISORY:
[Security-appropriate warnings]
```

Lead with top 2–3 ore recommendations. Full mineral breakdown on request.

## Contextual Suggestions

After advisory, suggest ONE related command when relevant:

| Context | Suggest |
|---------|---------|
| Mining in lower security | `/threat-assessment` |
| Needs a mining fit | `/fitting` |
| Discussing what to build | `/build-cost` |
| After a successful session | `/journal` |

## Rules

- Every ore name, security band, and mineral yield must come from `ore_database.md` — training data about ore availability by security level is frequently wrong
- Do not present ISK/m3 rankings without a `market(action="prices")` call in this session
- Prioritize manufacturing utility over ISK/hour for self-sufficient pilots
- Include safety reminders for non-1.0 systems
- Align while mining in lower security; use Survey Scanner to find best rocks
