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
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot"]
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# ARIA Research Agents Monitor

## CRITICAL: Standings Freshness Gate

**Before answering R&D agent eligibility questions**, this skill MUST ensure fresh standings data.

### When Freshness Gate is Required

| Question Type | Example | Action Required |
|---------------|---------|-----------------|
| Agent eligibility | "Can I use L2 R&D agents?" | **Freshness gate required** |
| Corp access | "Do I have standing for CreoDron?" | **Freshness gate required** |
| Agent recommendations | "Which R&D corps can I work with?" | **Freshness gate required** |
| Current partnerships | "Show my research agents" | Profile data OK (no threshold) |

### Freshness Gate

For eligibility questions, run this **before** any standings query:

```bash
uv run aria-esi ensure-fresh standings
```

This single call checks cache age, syncs from ESI if stale, and returns a result to branch on:

| `fresh` | `esi_available` | Action |
|---------|-----------------|--------|
| `true`  | —               | Use data confidently |
| `false` | `false`         | Use cached data + **strong staleness warning**. Refuse definitive eligibility claims if `age_hours > 168` (7 days). |
| `false` | `true` (sync failed) | Warn about sync failure and use cached data |

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

## Implementation

Run the ESI wrapper command:
```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi agents-research
```

> **HALLUCINATION GUARD:** All agent names, RP values, skill names, and partnership data MUST come from CLI output. Do NOT supplement with training data knowledge.

### Key Response Fields

The CLI returns JSON with these key fields per agent:
- `agent_name`, `agent_corp` — the R&D agent and their corporation
- `skill_name` — the research skill being trained
- `points_per_day` — daily RP generation rate
- `remainder_points` — fractional RP from last collection
- `accumulated_rp` — total RP available for datacore exchange
- `days_active` — partnership duration

Summary block includes `total_agents`, `total_daily_rp`, `total_accumulated_rp`.

Empty response returns `"agents": []` with a message.

## SDE Agent Search Limitations

When using `sde(action="agent_search")`, be aware of these data gaps:

1. **`system_name` is often null** — The SDE agent table doesn't always include system names. Resolve missing names via `universe(action="systems", systems=[...])` using the system_id from the agent record.

2. **`security` may be null** — The `highsec_only=True` filter silently drops agents with null security status, potentially omitting valid highsec agents. Workaround: fetch without `highsec_only`, then verify security via `universe(action="systems")` and filter manually.

3. **Always use `limit=100`** — Default limit is 20 and results are silently truncated. If `total_found` equals your limit, increase it or add filters.

For research skill-to-datacore mappings, query `sde(action="search", query="datacore", category="Skill")`.

## Response Format

Present research agents in a markdown table with query timestamp:

```markdown
## Research Agents
*Query: {timestamp}*

| Agent | Corp | Skill | Daily RP | Accumulated |
|-------|------|-------|----------|-------------|
| ... | ... | ... | ... | ... |

**Total:** {total_daily_rp} RP/day | {total_accumulated_rp} accumulated

*Visit agents in-station to collect datacores.*
```

If no agents: state that no active partnerships exist and suggest how to start R&D (train a research skill, find an R&D agent, start partnership through agent conversation).

If ESI is not configured or scope is missing: state the limitation and provide the setup command (`uv run python .claude/scripts/aria-oauth-setup.py`).

## Contextual Suggestions

| Context | Suggest |
|---------|---------|
| Has accumulated RP | "Visit agent stations to collect datacores" |
| No research agents | "Consider starting R&D partnerships for passive datacore income" |
| Discussing invention | "Check accumulated RP with `/agents-research`" |

## Standings CLI Reference

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

## Cross-References

| Related Command | Use Case |
|-----------------|----------|
| `/industry-jobs` | Check invention jobs using datacores |
| `/esi-query skills` | View research skill levels |
| `/price` | Check datacore market prices |

## Behavior Notes

- **Calculation:** Always calculate current RP from start date and elapsed time
- **Sorting:** Sort agents by accumulated RP (highest first)
- **Rounding:** Display RP values to 1 decimal place
- **Age:** Show days active for context on partnership duration

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
