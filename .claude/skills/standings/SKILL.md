---
name: standings
description: Standings tracker and progression planner for agent access, faction requirements, and standing repair strategies.
model: haiku
category: identity
triggers:
  - "/standings"
  - "my standings"
  - "can I use L[N] agents"
  - "standing requirements"
  - "how to fix standings"
  - "agent access"
  - "faction standing"
  - "how to get L4 agents"
  - "path to 5.0 standing"
  - "how long to reach L4"
  - "standings grind"
  - "standing requirements for L[N]"
  - "fastest way to raise standings"
requires_pilot: true
esi_scopes:
  - esi-characters.read_standings.v1
  - esi-skills.read_skills.v1
data_sources:
  - reference/mechanics/standings_thresholds.json
  - reference/mechanics/epic_arcs.json
external_sources: []
argument-hint: "[--faction NAME|--corp NAME]"
allowed-tools: [Read, Grep, Glob, "mcp__aria-universe__pilot", "mcp__aria-universe__sde"]
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# ARIA Standings Module

## Command Syntax

```
/standings                     # Overview of all standings
/standings <faction/corp>      # Standing with specific entity
/standings agents <corp>       # What agent levels you can access
/standings plan <faction> <N>  # How to reach standing N
/standings repair <faction>    # Strategies to repair negative standing
```

## Data Sources

- **ESI:** Live standings via `uv run aria-esi standings`
- **Reference:** Read `reference/mechanics/standings_thresholds.json` for agent level thresholds, derived standing formulas, standing gain estimates, and repair strategies.
- **Reference:** Read `reference/mechanics/epic_arcs.json` for epic arc details, faction choices, and cooldowns.

**CRITICAL:** Always ensure fresh standings data before answering eligibility questions. Use the freshness gate below.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `sde(action="agent_search")` | Find agents for standings grinding |
| `sde(action="corporation_info")` | Get corp faction relationships |
| `skills(action="training_time")` | Calculate Social skill training |

## Freshness Gate (before eligibility checks)

**Every standings query that involves eligibility ("Can I use L3 agents?", "Do I qualify?") must run this first:**

```bash
uv run aria-esi ensure-fresh standings
```

This single call checks cache age, syncs from ESI if stale and available, and returns a result you can branch on:

| `fresh` | `esi_available` | Action |
|---------|-----------------|--------|
| `true`  | —               | Use data confidently |
| `false` | `false`         | Use cached data + **strong staleness warning**. Refuse definitive eligibility claims if `age_hours > 168` (7 days). |
| `false` | `true` (sync failed) | Warn about sync failure and use cached data |

**For non-eligibility queries** (general overview, progression planning): use profile data directly without the freshness gate.

### Profile Standings Format

The profile contains pre-formatted standings:
```markdown
| Corporation | Standing | Access |
|-------------|----------|--------|
| Federation Navy | 4.59 | **L3 Missions** (L4 @ 5.0) |
```

This already includes access level calculations - use directly for quick answers.

## Response Patterns

### Overview Query

When asked for general standings ("/standings"):

1. Query ESI: `uv run aria-esi standings`
2. Read `standings_thresholds.json` for threshold context
3. Query skills for Connections/Diplomacy levels
4. Present organized by faction and corporation

**Example Response:**

```
## Current Standings

**Connections V active** (+20% effective on positive standings)

### Empire Factions
| Faction | Raw | Effective | L4 Access? |
|---------|-----|-----------|------------|
| Gallente Federation | 4.2 | 5.36 | Yes |
| Caldari State | 2.1 | 3.68 | No (need 5.0) |

### Key Corporations
| Corporation | Raw | Effective | Notes |
|-------------|-----|-----------|-------|
| Federation Navy | 5.1 | 6.08 | L4 access |

*Effective standing includes Connections V bonus.*
```

### Agent Access Query

When asked about agent access:

1. Query ESI for current standings
2. Query skills for Connections level
3. Calculate effective standing using formula from `standings_thresholds.json`
4. Compare to threshold from reference data
5. Use `sde(action="agent_search")` to find nearest agents

### Research Agent Query

When asked about R&D / research agents:

1. **Verify corporation faction** via `sde(action="corporation_info")`. Never guess faction from training data.
2. Query standings and calculate effective standing with Connections bonus.
3. Look up R&D agents via `sde(action="agent_search", corporation="...", level=4, division="R&D", limit=100)`.
4. Route to nearest agents via `universe(action="route", ...)`.

**Faction verification warning:** If unsure which faction a corporation belongs to, always call `sde(action="corporation_info")` first.

### Standing Plan Query

When asked how to reach a standing (e.g., "/standings plan Caldari 5.0"):

1. Query current standing from ESI
2. Calculate gap to target using formulas from `standings_thresholds.json`
3. Read `standings_thresholds.json` for progression strategies and `epic_arcs.json` for arc-based repair options
4. Present: Current Status / Agent Access / Progression Path / Accelerators / Skill Recommendations

### Standing Repair Query

When asked about repairing negative standings:

1. Query current standing
2. Read `epic_arcs.json` for repair strategies
3. Read `standings_thresholds.json` for Diplomacy skill effects and repair strategies
4. Present strategies in order of effectiveness

## Derived Standing Calculation

Read `standings_thresholds.json → derived_standings_formula` for the Connections/Diplomacy formulas. **Always show both raw and effective standings in output.**

## Standings CLI Output Schema

The `uv run aria-esi standings` command returns:
```json
{
  "standings": [
    {"from_id": 1000101, "from_type": "npc_corp", "name": "CreoDron", "standing": 3.73},
    {"from_id": 3009895, "from_type": "agent", "name": "Agent Name", "standing": 7.99}
  ]
}
```

Filter by name: `jq '.standings[] | select(.name == "CreoDron")'`
Filter by type: `jq '.standings[] | select(.from_type == "npc_corp")'`

Field reference:
- `from_id`: Entity ID (NPC corp, faction, or agent)
- `from_type`: `"npc_corp"`, `"faction"`, or `"agent"`
- `name`: Resolved entity name
- `standing`: Standing value (-10.0 to +10.0)

Agent standing requirements: L1=any, L2=1.0, L3=3.0, L4=5.0, L5=7.0

## ESI Query Pattern

```bash
# Get current standings (run in parallel with skills)
uv run aria-esi standings
uv run aria-esi skills
```

## Integration with Other Skills

| Context | Action |
|---------|--------|
| Finding agents | Use `sde(action="agent_search", ...)` |
| Route to agent | Use `universe(action="route", ...)` |
| Mission preparation | Suggest `/mission-brief` |
| LP conversion | Suggest `/lp-store` |

## Error Handling

| Scenario | Response |
|----------|----------|
| No standing data | "Cannot fetch standings. Ensure ESI is connected." |
| Unknown corp/faction | "Entity not found. Try the full name (e.g., 'Federation Navy')." |
| Already at target | "Good news! You already meet the requirement for [target]." |
| Negative standing repair | Prioritize epic arc strategy |

## DO NOT

- **DO NOT** make definitive eligibility claims on stale data (age > 7 days) -- use the freshness gate
- **DO NOT** recommend killing friendly faction NPCs
- **DO NOT** suggest COSMOS missions without warning they're one-time only
- **DO NOT** forget to factor in Connections/Diplomacy skills

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
