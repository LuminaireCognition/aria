---
name: journal
description: Log mission completions and exploration discoveries to operational records.
model: haiku
category: operations
triggers:
  - "/journal"
  - "/journal mission"
  - "/journal exploration"
  - "log mission"
  - "log site"
  - "record that mission"
  - "log this run"
requires_pilot: true
has_persona_overlay: true
data_sources:
  - userdata/pilots/{active_pilot}/missions.md
  - userdata/pilots/{active_pilot}/exploration.md
---

# Operations Journal

## Entry Types

### 1. Mission Entry
**Target File:** `userdata/pilots/{active_pilot}/missions.md`
**Insert After:** `## Recent Completions` header

### 2. Exploration Entry
**Target File:** `userdata/pilots/{active_pilot}/exploration.md`
**Insert After:** `## Recent Discoveries` header

On first use, replace the placeholder template entry under the header.

## Response Flow

1. **Determine entry type** - If not specified, ask: "Mission or exploration entry?"
2. **Collect required fields** (see below)
3. **Preview the entry** using the format templates below, then ask for confirmation
4. **Write entry** using Edit tool to insert after the appropriate section header
5. **Statistics prompt** (exploration only) - Offer: "Update site statistics?"

### Required Fields

**Missions:** Mission name, agent name (default from pilot profile faction), target faction, outcome, notable events (optional), standing change (optional)

**Exploration:** Site name, type (Relic/Data), system and security level, containers found/hacked, notable loot, observations (optional)

## Entry Format Templates

### Mission Entry
```markdown
### YYYY-MM-DD
**Mission:** [Mission Name]
**Agent:** [Agent Name] ([Corporation])
**Target:** [Faction]
**Outcome:** Success
**Notes:** [Notable events, close calls, loot drops]
**Standing Change:** +X.XX
```

### Exploration Entry
```markdown
### YYYY-MM-DD - [Site Name]
- **Type:** Relic/Data
- **System:** [System Name] ([Security])
- **Containers:** X found, Y successfully hacked
- **Notable Loot:**
  - [Item Name] x [quantity]
- **Notes:** [Interesting observations, difficulty, special circumstances]
```

## Inline Argument Parsing

Support quick entries: `/journal mission "Gone Berserk" Serpentis success +0.15` or `/journal exploration "Crumbling Serpentis..." Relic Masalle 0.6 3/3`. If arguments incomplete, prompt for remaining fields.

## Statistics Updates

After exploration entries, increment the relevant counters (Total Sites Run, Relic/Data Sites) at the top of the exploration catalog. Update "Best Single Haul" if applicable.

## Error Handling

- **File not found:** Offer to create the log file structure.
- **Write failure:** Display the formatted entry for manual copy.

## Behavior Notes

- **Brevity:** Keep prompts minimal. Pilot is likely mid-session.
- **Defaults:** Default agent corporation from pilot profile faction, not hardcoded.
- **Date Format:** Use YYYY-MM-DD (today's date by default).
- **No Duplication:** Check if an identical entry exists before writing.
- **Batch Mode:** If pilot says "log 3 missions" or similar, process sequentially.

## Cross-References

After logging, offer relevant follow-ups: update faction notes for new factions, update loot inventory for notable exploration loot, or check standings with `/esi-query standings`.
