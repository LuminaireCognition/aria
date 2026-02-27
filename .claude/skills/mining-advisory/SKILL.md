---
name: mining-advisory
description: ARIA mining operations guidance for Eve Online. Use for ore recommendations, belt intel, Venture fitting, or mining optimization.
model: haiku
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

# ARIA Mining Operations Module

## Purpose
Provide mining guidance optimized for self-sufficient gameplay, including ore prioritization, belt selection, and Venture optimization.

## Trigger Phrases
- "mining advisory"
- "what should I mine"
- "ore recommendations"
- "belt intel"
- "mining optimization"

## Required Tool Calls (MANDATORY)

Before presenting any mining advisory, the following MUST happen:

| Step | Call | Required For |
|------|------|-------------|
| 1 | Read `reference/mechanics/ore_database.md` | Ore types, security bands, mineral yields |
| 2 | `universe(action="systems", systems=["..."])` | System security status verification |
| 3 | `market(action="prices", items=[...])` | Current ore/mineral prices (if ISK comparison needed) |

**Step 1 is a `data_source` for this skill and MUST be read before responding.** The ore database contains verified security band data. Do NOT rely on training data for which ores spawn in which security levels.

> **⚠️ HALLUCINATION GUARD:** Every ore name, security band, and mineral yield in the response MUST come from `ore_database.md` or an MCP tool call in this session. Training data about ore availability by security level is frequently wrong. Read the reference file FIRST, respond SECOND.

### Field → Source Mapping

| Output Field | Required Source | Source |
|-------------|----------------|--------|
| Ore names available in system | `ore_database.md` | Prerequisite file (read before output) |
| Ore security bands (min sec to spawn) | `ore_database.md` | Prerequisite file |
| Mineral yields per ore | `ore_database.md` | Prerequisite file |
| System security status | Universe dispatcher | `universe(action="systems", systems=["..."])` |
| Current ore/mineral prices | Market dispatcher | `market(action="prices", items=[...])` |
| ISK/m³ rankings | Derived | Calculate from `ore_database.md` yields × market prices |
| Pilot ship/skills context | Pilot profile | `data_sources` pilot files |

## Response Format

```
═══════════════════════════════════════════
ARIA MINING OPERATIONS ADVISORY
───────────────────────────────────────────
LOCATION: [System if known]
SECURITY: [Sec level]
PILOT VESSEL: Venture-class Mining Frigate
───────────────────────────────────────────
ORE PRIORITY (for self-sufficient operations):

HIGH PRIORITY:
• [Ores with minerals needed for manufacturing]

MODERATE PRIORITY:
• [Secondary ores]

EFFICIENCY NOTES:
[Venture-specific considerations]

SAFETY ADVISORY:
[Security-appropriate warnings]
═══════════════════════════════════════════
```

## Ore Reference (Gallente High-Sec)

### Manufacturing Priority Ores
| Ore | Primary Minerals | Notes |
|-----|------------------|-------|
| Plagioclase | Tritanium, Mexallon | Best Mexallon source in high-sec |
| Pyroxeres | Tritanium, Pyerite, Mexallon | Good all-rounder |
| Kernite | Tritanium, Mexallon, Isogen | Isogen source |
| Omber | Tritanium, Pyerite, Isogen | Dense, good for Venture |
| Hemorphite | Tritanium, Isogen, Nocxium, Zydrine | Rare in high-sec (0.5 only) |
| Jaspet | Mexallon, Nocxium, Zydrine | Rare in high-sec (0.5 only) |

### Avoid for Venture
| Ore | Reason |
|-----|--------|
| Veldspar | Bulk ore, fills hold fast with low value |
| Scordite | Similar issue, better alternatives |

## Venture Optimization Tips
- Fit Mining Laser Upgrade in low slot
- Use the Venture's built-in +2 warp core stabilization — no WCS module needed
- Keep ore hold under 5000 m3 focus on dense ores
- Align while mining in lower security
- Use Survey Scanner to find best rocks

## Anti-Patterns

❌ **WRONG:** Claim "Kernite is available in 0.7 systems" from training data
✅ **RIGHT:** Read `ore_database.md` for verified security bands per ore type

❌ **WRONG:** Present ore ISK/m³ rankings without querying current market prices
✅ **RIGHT:** Call `market(action="prices")` for current mineral prices, then calculate

❌ **WRONG:** State mineral yields per ore unit from memory
✅ **RIGHT:** Read `ore_database.md` for exact reprocessing outputs

## Behavior
- Account for pilot's self-sufficient status - prioritize manufacturing utility over ISK/hour
- Consider mineral needs for ships/modules pilot might want to build
- Always include safety reminders for non-1.0 systems
- Reference reprocessing skills if discussing yield
- **Intelligence Framing:** Follow the Intelligence Sourcing Protocol in CLAUDE.md. Present ore data as live survey scans and current belt analysis, not static reference data. Use phrases like "Belt survey indicates..." or "Current extraction analysis shows..." rather than archival language.
- **Brevity:** Lead with top 2-3 ore recommendations. Full mineral breakdown on request.

## Contextual Suggestions

After providing mining advice, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Mining in lower security space | "Check `/threat-assessment` for safety intel" |
| Capsuleer needs a mining fit | "Try `/fitting` for an optimized Venture build" |
| Discussing what to build with ore | "I can help with manufacturing plans" |
| After a successful mining session | "Log notable hauls with `/journal`" |

Don't add suggestions to every advisory - only when clearly helpful.
