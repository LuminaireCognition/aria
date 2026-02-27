---
name: exploration
description: ARIA exploration and hacking guidance for Eve Online. Use for relic/data site analysis, hacking tips, or exploration loot identification.
model: haiku
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
prerequisite_files:
  - reference/mechanics/exploration_sites.md
  - reference/mechanics/hacking_guide.md
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/exploration.md
---

# ARIA Exploration Analysis Module

## Purpose
Provide exploration site analysis, hacking strategies, and loot identification with appropriate lore context.

## Trigger Phrases
- "exploration analysis"
- "I found a [site name]"
- "hacking tips"
- "what's this loot worth"
- "relic site" / "data site"

## Required Tool Calls (MANDATORY)

Before presenting any exploration analysis, the following MUST happen:

| Step | Call | Required For |
|------|------|-------------|
| 1 | Read `reference/mechanics/exploration_sites.md` | Site classification, loot tables, container types |
| 2 | Read `reference/mechanics/hacking_guide.md` | Hacking mechanics, coherence rules, strategies |
| 3 | `market(action="prices", items=[...])` | Loot valuations (only for specific items) |
| 4 | `sde(action="item_info", item="...")` | Individual loot item details (NOT site names) |

**Steps 1-2 are the `data_sources` for this skill and MUST be read before responding.** These files contain verified game mechanics. Do NOT rely on training data for hacking mechanics, container types, site prefixes, or loot tables.

> **⚠️ HALLUCINATION GUARD:** Every mechanic, container name, loot table, and hacking strategy in the response MUST come from the reference files read in this session. Training data knowledge about EVE exploration is frequently wrong (e.g., coherence mechanics, site prefix meanings, container behaviors). Read the reference files FIRST, respond SECOND.

### Field → Source Mapping

| Output Field | Required Source | Source |
|-------------|----------------|--------|
| Site classification (Relic/Data) | `exploration_sites.md` | Prerequisite file (read before output) |
| Site prefix meaning (Ruined/Decayed/etc.) | `exploration_sites.md` | Prerequisite file |
| Security band for site type | `exploration_sites.md` | Prerequisite file |
| Container types and counts | `exploration_sites.md` | Prerequisite file |
| Probable loot categories | `exploration_sites.md` | Prerequisite file |
| Hacking mechanics (coherence, nodes) | `hacking_guide.md` | Prerequisite file (read before output) |
| Hacking strategy | `hacking_guide.md` | Prerequisite file |
| Individual loot item details | SDE | `sde(action="item_info", item="...")` |
| Loot market value | Market dispatcher | `market(action="prices", items=[...])` |

## Response Format

```
═══════════════════════════════════════════
ARIA EXPLORATION SITE ANALYSIS
───────────────────────────────────────────
SITE NAME: [Full site name]
CLASSIFICATION: [Relic/Data] Site ([Faction])
SECURITY ASSESSMENT: [Safe/Hostile presence expected]
───────────────────────────────────────────
EXPECTED CONTAINERS: [Number and types]

PROBABLE LOOT:
• [Item categories with brief descriptions]

HACKING ADVISORY:
[Strategy for this site type]

LORE CONTEXT:
[In-universe explanation of what this site represents]
═══════════════════════════════════════════
```

## Site Classification Reference

> **Full Reference:** `reference/mechanics/exploration_sites.md` contains complete site types, ISK estimates, and loot tables.

### Relic Sites (Archaeology)
| Prefix | Faction | Danger | Loot Quality |
|--------|---------|--------|--------------|
| Ruined | Various | None | Standard |
| Crumbling | Various | None | Low |
| Decayed | Sleeper | WH only | High |

### Data Sites (Hacking)
| Prefix | Faction | Danger | Loot Quality |
|--------|---------|--------|--------------|
| Local | Various | None | Low |
| Regional | Various | None | Standard |
| Central | Various | Possible | Higher |

### Faction-Specific Notes

**Serpentis Sites:** Neural booster research facilities. May contain booster BPCs and data.

**Angel Cartel Sites:** Smuggling caches. Ship component blueprints common.

**Blood Raider Sites:** Biotech research. Often contaminated nanite compounds.

**Guristas Sites:** Stolen technology. Electronics and decryptors.

**Sansha Sites:** Slave processing/cybernetics. Intact armor plates common.

## Hacking Strategy
1. **Identify the System Core** - Eliminates defensive subsystems when destroyed
2. **Preserve Utility Subsystems** - Repair and secondary vectors are valuable
3. **Manage Coherence** - Plan your route, don't brute force
4. **Use Data Analyzers for Data, Relic for Relic** - T1 is fine for high-sec

## Valuable Loot Categories
- **Intact Armor Plates** - High value, low volume
- **Decryptors** - Invention materials (valuable even for self-sufficient)
- **Faction BPCs** - Can be manufactured without market
- **Datacores** - Research materials

## Anti-Patterns

❌ **WRONG:** State "Coherence depletes with each probe attempt" from training data
✅ **RIGHT:** Read `hacking_guide.md` — coherence is HP lost when defensive nodes attack you

❌ **WRONG:** Claim "System Core eliminates dangerous subsystems"
✅ **RIGHT:** Read `hacking_guide.md` — the Core is the objective you destroy to win the hack

❌ **WRONG:** State "One attempt per container" for regular data sites
✅ **RIGHT:** Only true for Ghost Sites. Regular sites allow retries. Read `exploration_sites.md`.

❌ **WRONG:** Accept "Ruined Serpentis Temple" in high-sec without questioning
✅ **RIGHT:** "Ruined" prefix = nullsec/WH sites. High-sec uses "Decayed" prefix. Read `exploration_sites.md`.

## Important: Site Names vs Items

Exploration site names (e.g., "Serpentis Temple", "Ruined Sansha Monument", "Local Guristas Shattered Life-Support Unit") are **cosmic signature names**, NOT SDE items. Do NOT search SDE for site names — `sde(action="item_info", item="Serpentis Temple")` will fail or return wrong results.

- **Site information:** Use the `data_sources` reference files listed in this skill's `_index.json`
- **Individual loot items:** These ARE SDE items — use `sde(action="item_info")` for specific loot like "Intact Armor Plates" or "Emission Scope Sharpener"

## Behavior
- **Intelligence Framing:** Follow the Intelligence Sourcing Protocol in CLAUDE.md. For exploration sites, frame data as live archaeological surveys and faction intelligence assessments. Use phrases like "Site signature analysis indicates..." or "DED classification identifies this as..." rather than archival language.
- Provide lore context as active intelligence on discovered sites
- Note items particularly useful for self-sufficient gameplay
- Warn about hostile site variants
- Celebrate notable discoveries appropriately (in character)
- **Brevity:** Quick site assessment first. Lore and full loot tables on request.

## Contextual Suggestions

After providing exploration analysis, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Site is in dangerous space | "Check `/threat-assessment` for local intel" |
| Capsuleer needs exploration fit | "Try `/fitting` for an optimized scanning build" |
| After discovering notable loot | "Log it with `/journal exploration`" |
| Site has hostile NPCs | "Run `/mission-brief` for enemy damage profiles" |

Don't add suggestions to every analysis - only when clearly helpful.
