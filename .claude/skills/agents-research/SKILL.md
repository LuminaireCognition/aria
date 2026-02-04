---
name: agents-research
description: Monitor research agent partnerships and accumulated research points. Track passive RP generation from R&D agents.
model: haiku
category: industry
triggers:
  - "/agents-research"
  - "my research agents"
  - "research points"
  - "RP status"
  - "datacores"
requires_pilot: true
esi_scopes:
  - esi-characters.read_agents_research.v1
---

# ARIA Research Agents Monitor

## Purpose

Query the capsuleer's active research agent partnerships to display accumulated research points (RP) and daily generation rates. Research agents provide passive RP accumulation for datacores used in invention.

## CRITICAL: Standings Freshness Check

**Before answering R&D agent eligibility questions**, this skill MUST query live standings data.

### When to Query Live Standings

| Question Type | Example | Action Required |
|---------------|---------|-----------------|
| Agent eligibility | "Can I use L2 R&D agents?" | **Query ESI standings first** |
| Corp access | "Do I have standing for CreoDron?" | **Query ESI standings first** |
| Agent recommendations | "Which R&D corps can I work with?" | **Query ESI standings first** |
| Current partnerships | "Show my research agents" | Profile data OK (no threshold) |

### Mandatory Query Sequence

For eligibility questions:

```bash
# 1. Check freshness (optional diagnostic)
uv run python .claude/scripts/aria-data-freshness.py standings

# 2. ALWAYS query live standings for eligibility decisions
uv run aria-esi standings
```

**Do NOT use profile.md standings for eligibility checks.** Profile data is a snapshot that may be days old. R&D agent access depends on current corporation standings which change with gameplay.

### R&D Agent Standing Requirements

| Agent Level | Corp Standing Required |
|-------------|------------------------|
| L1 | Any (no requirement) |
| L2 | **1.0** |
| L3 | **3.0** |
| L4 | **5.0** |
| L5 | **7.0** |

### Skill Requirements

R&D agents also require the corresponding science skill at the agent's level:
- Mechanical Engineering, Electronic Engineering, Graviton Physics, etc.
- Agent Level 2 → Skill at II minimum
- Agent Level 3 → Skill at III minimum

## CRITICAL: Read-Only Limitation

**ESI research agent endpoints are READ-ONLY.** ARIA can:
- View active research partnerships
- Display accumulated RP and daily rates
- Calculate current RP based on time elapsed

**ARIA CANNOT:**
- Start new research partnerships
- Cancel research agreements
- Collect datacores
- Interact with the EVE client in any way

**Always clarify this when showing research status.** If user asks to collect datacores, explicitly state this requires in-game action (visit agent in station).

## CRITICAL: Data Volatility

Research agent data is **stable** - RP accumulates on fixed timers:

1. **Display query timestamp** - RP is calculated from start date
2. **RP is deterministic** - based on skill levels and time elapsed
3. **Safe to cache** - partnerships rarely change
4. **Calculate current RP** - use formula: `remainder_points + (points_per_day * days_elapsed)`

## Trigger Phrases

- `/agents-research`
- "my research agents"
- "research points"
- "RP status"
- "datacores"
- "R&D agents"
- "how much RP do I have"
- "research agent status"

## ESI Requirement

**Requires:** `esi-characters.read_agents_research.v1` scope

If scope is not authorized:
```
Research agent monitoring requires ESI authentication.

To enable: uv run python .claude/scripts/aria-oauth-setup.py
Select "esi-characters.read_agents_research.v1" during scope selection.
```

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run research agent commands - they will timeout
2. **RESPOND IMMEDIATELY** with:
   ```
   Research agent monitoring requires live ESI data which is currently unavailable.

   Check this in-game:
   • Agent conversation → Research tab
   • Shows accumulated RP and collection options

   ESI usually recovers automatically.
   ```
3. **DO NOT** block waiting for ESI

### If ESI is AVAILABLE:

Proceed with normal research agent queries.

## Implementation

Run the ESI wrapper command:
```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi agents-research
```

### JSON Response Structure

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "stable",
  "character_id": 2119654321,
  "summary": {
    "total_agents": 2,
    "total_daily_rp": 95.5,
    "total_accumulated_rp": 15420
  },
  "agents": [
    {
      "agent_id": 3009841,
      "agent_name": "Tyren Aurilen",
      "agent_corp": "CreoDron",
      "skill_type_id": 11450,
      "skill_name": "Mechanical Engineering",
      "started_at": "2025-06-01T00:00:00Z",
      "points_per_day": 55.0,
      "remainder_points": 1250.5,
      "accumulated_rp": 12840,
      "days_active": 228
    },
    {
      "agent_id": 3009842,
      "agent_name": "Orie Midren",
      "agent_corp": "Duvolle Laboratories",
      "skill_type_id": 11446,
      "skill_name": "High Energy Physics",
      "started_at": "2025-09-15T00:00:00Z",
      "points_per_day": 40.5,
      "remainder_points": 500.0,
      "accumulated_rp": 2580,
      "days_active": 122
    }
  ]
}
```

### Empty Response

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "stable",
  "character_id": 2119654321,
  "summary": {
    "total_agents": 0,
    "total_daily_rp": 0,
    "total_accumulated_rp": 0
  },
  "agents": [],
  "message": "No active research agents"
}
```

## Research Skills Reference

| Skill | Datacore Type | Common Uses |
|-------|---------------|-------------|
| Mechanical Engineering | Mechanical Engineering | Armor, rigs, structures |
| Electronic Engineering | Electronic Engineering | EWAR, shield modules |
| Graviton Physics | Graviton Physics | Warp drives, propulsion |
| High Energy Physics | High Energy Physics | Lasers, capacitor |
| Hydromagnetic Physics | Hydromagnetic Physics | Shield systems |
| Laser Physics | Laser Physics | Laser weapons |
| Molecular Engineering | Molecular Engineering | Nanite repair, hull |
| Nanite Engineering | Nanite Engineering | Armor repair |
| Nuclear Physics | Nuclear Physics | Missiles, bombs |
| Plasma Physics | Plasma Physics | Blasters, plasma |
| Quantum Physics | Quantum Physics | Cloaking, cyno |
| Rocket Science | Rocket Science | Missiles, propulsion |

## Response Formats

### Standard Display (rp_level: off or lite)

```markdown
## Research Agents
*Query: 14:30 UTC*

| Agent | Corp | Skill | Daily RP | Accumulated |
|-------|------|-------|----------|-------------|
| Tyren Aurilen | CreoDron | Mechanical Eng | 55.0 | 12,840 |
| Orie Midren | Duvolle Labs | High Energy Phys | 40.5 | 2,580 |

**Total:** 95.5 RP/day | 15,420 accumulated

*Visit agents in-station to collect datacores.*
```

### Formatted Version (rp_level: moderate or full)

```
═══════════════════════════════════════════════════════════════════
ARIA RESEARCH AGENT MONITOR
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC
───────────────────────────────────────────────────────────────────
ACTIVE PARTNERSHIPS: 2 agents
───────────────────────────────────────────────────────────────────
  Tyren Aurilen (CreoDron)
  Skill:       Mechanical Engineering
  Daily RP:    55.0
  Active:      228 days
  Accumulated: 12,840 RP

  Orie Midren (Duvolle Laboratories)
  Skill:       High Energy Physics
  Daily RP:    40.5
  Active:      122 days
  Accumulated: 2,580 RP
───────────────────────────────────────────────────────────────────
TOTALS: 95.5 RP/day | 15,420 accumulated RP
───────────────────────────────────────────────────────────────────
Visit agents in-station to exchange RP for datacores.
═══════════════════════════════════════════════════════════════════
```

### No Agents Display

```
═══════════════════════════════════════════════════════════════════
ARIA RESEARCH AGENT MONITOR
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC
───────────────────────────────────────────────────────────────────
No active research agent partnerships.

To start R&D research:
1. Train a research skill (e.g., Mechanical Engineering)
2. Find an R&D agent at a corporation you have standings with
3. Start a research partnership through the agent conversation
═══════════════════════════════════════════════════════════════════
```

## Error Handling

### ESI Not Configured

```
═══════════════════════════════════════════════════════════════════
ARIA RESEARCH AGENT MONITOR
───────────────────────────────────────────────────────────────────
Research agent monitoring requires ESI authentication.

ARIA works fully without ESI - you can manually track
your research agents if needed.

OPTIONAL: Enable live tracking (~5 min setup)
  uv run python .claude/scripts/aria-oauth-setup.py
═══════════════════════════════════════════════════════════════════
```

### Missing Scope

```
═══════════════════════════════════════════════════════════════════
ARIA RESEARCH AGENT MONITOR - SCOPE NOT AUTHORIZED
───────────────────────────────────────────────────────────────────
ESI is configured but research agents scope is missing.

To enable:
  uv run python .claude/scripts/aria-oauth-setup.py

Select "esi-characters.read_agents_research.v1" during setup.
═══════════════════════════════════════════════════════════════════
```

## Contextual Suggestions

| Context | Suggest |
|---------|---------|
| Has accumulated RP | "Visit agent stations to collect datacores" |
| No research agents | "Consider starting R&D partnerships for passive datacore income" |
| Discussing invention | "Check accumulated RP with `/agents-research`" |

## Cross-References

| Related Command | Use Case |
|-----------------|----------|
| `/industry-jobs` | Check invention jobs using datacores |
| `/esi-query skills` | View research skill levels |
| `/price` | Check datacore market prices |

## Self-Sufficiency Context

For pilots with `market_trading: false`:
- Datacores from research agents are essential for self-sufficient invention
- Emphasize datacore accumulation for T2 production
- Note which skills/agents produce needed datacores

## Behavior Notes

- **Brevity:** Default to table format unless RP mode requests formatted boxes
- **Calculation:** Always calculate current RP from start date and elapsed time
- **Sorting:** Sort agents by accumulated RP (highest first)
- **Rounding:** Display RP values to 1 decimal place
- **Age:** Show days active for context on partnership duration
