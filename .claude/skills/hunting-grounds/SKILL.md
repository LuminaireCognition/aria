---
name: hunting-grounds
description: Hunting ground analysis for Eve Online. Analyze systems for target availability, traffic patterns, and competition.
model: sonnet
category: tactical
triggers:
  - "/hunting-grounds"
  - "hunting grounds"
  - "where should I hunt"
  - "good systems for piracy"
  - "find targets"
  - "busy systems"
requires_pilot: true
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
---

# Hunting Grounds Module

## Query Triage (FIRST STEP)

Classify the query before any tool calls:

| Query Type | Example | Tool Sequence |
|-----------|---------|---------------|
| **System-specific** | "analyze hunting grounds in Rancer" | Phase 1a → Phase 1b → Phase 2 |
| **Discovery** | "where should I hunt near Tama?" | Phase 1b → Phase 2 |
| **Territory** | "hunting viability for Imperium renter space" | Phase 0 → Phase 1b → Phase 2 |

## Phased Execution Protocol

### Phase 0 — Territory Resolution (territory queries only)

Call `universe(action="territory_analysis", coalition="...")` to identify actual systems/regions. Use a representative system from the result as `origin` for Phase 1b. If the tool returns no data, report that territory intel is unavailable — do NOT substitute systems from training data.

### Phase 1a — Subject System Activity (system-specific queries only)

**MANDATORY when the user names a specific system.** Call:
```
universe(action="activity", systems=["<named_system>"], include_realtime=True)
```
Present this system FIRST in the output, regardless of its activity level. If it's quiet, say so — that IS the intel. A hunter asking about Rancer needs Rancer's data, not a redirect to Amamake.

### Phase 1b — Nearby Hotspots

Call:
```
universe(action="hotspots", origin="<system>", max_jumps=15, activity_type="kills")
```
The `origin` comes from: the named system (system-specific), the user's reference system (discovery), or Phase 0 output (territory).

### Phase 2 — Format and Present

Build the output table using ONLY data from Phase 1a/1b responses. For each system in the output:

| Output Column | Source Field |
|--------------|-------------|
| System | `hotspots[].name` or `activity[].name` |
| Sec | `hotspots[].security` or `activity[].security_class` |
| Region | `hotspots[].region` |
| Kills (1h) | `hotspots[].activity_value` or `activity[].ship_kills` |
| Pods (1h) | `activity[].pod_kills` (only if Phase 1a was called) |
| NPC Kills | `activity[].npc_kills` (only if Phase 1a was called) |
| Jumps (1h) | `activity[].ship_jumps` (only if Phase 1a was called) |
| Distance | `hotspots[].jumps_from_origin` |

**Mandatory table template** — use this exact column order, never reorder columns:

```
| System | Sec | Region | Kills (1h) | Activity | Distance |
|--------|-----|--------|----------:|----------|----------|
```

**If a field has no source (no tool call returned it), leave it blank or omit the column.** Never fill gaps with estimates.

### Output Constraints

- Systems outside the `max_jumps` search radius MUST NOT appear in results.
- If `hotspots` returned 3 systems, present 3 — not 5.
- If the subject system (Phase 1a) is also in the hotspots list, merge the rows — don't duplicate.
- Narrative sections (analysis, recommendations, viability breakdowns) MUST NOT introduce systems absent from the tool response. If a system was not returned by `hotspots` or `activity`, it does not exist for this analysis.

**MCP failure:** If `activity` or `hotspots` calls fail entirely, report that hunting ground analysis requires live activity data and cannot proceed without it.

## Response Format

**Subject system** (if Phase 1a): Present first with full activity breakdown.
**Nearby hotspots**: Top 5 systems maximum from Phase 1b. Extras in a one-line summary table.

For each system: system name, security, region, viability rating, live intel (from tool data only), mark availability assessment, competition assessment, and tactical notes.

**Closing (rp_level: on or full only):** End with "Your call, Captain." At rp_level: off, omit the closing line.

## Hunting Ground Metrics

### Traffic Analysis

| Jumps (last hour) | Assessment |
|-------------------|------------|
| <50 | Dead - not worth the trip |
| 50-200 | Quiet - patient hunting |
| 200-500 | Moderate - steady traffic |
| 500-1000 | Busy - good mark flow |
| 1000+ | Hot - marks and competition |

### Mark Availability Indicators

| Indicator | Meaning |
|-----------|---------|
| High NPC kills | Ratters/mission runners in space |
| Low ship kills + high jumps | Marks passing through, not hunted |
| Mining anomalies | Potential mining barges |
| Mission agents in system | Mission runner traffic |

### Competition Assessment

| Ship Kills (last hour) | Assessment |
|------------------------|------------|
| 0 | Unclaimed territory |
| 1-10 | Light activity - room for more |
| 10-30 | Active hunting - competition |
| 30+ | Crowded - consider elsewhere |

## Worked Example: "Analyze hunting grounds in Rancer"

1. **Triage:** System-specific (user named "Rancer") → Phase 1a + 1b + 2
2. **Phase 1a:** `universe(action="activity", systems=["Rancer"], include_realtime=True)` → returns `{ship_kills: 1, pod_kills: 1, npc_kills: 0, ship_jumps: 83}`
3. **Phase 1b:** `universe(action="hotspots", origin="Rancer", max_jumps=15, activity_type="kills")` → returns e.g. `[{name: "Jita", activity_value: 82, ...}, {name: "Dal", activity_value: 42, ...}, ...]`
4. **Phase 2:** Present Rancer first (quiet: 1 kill, 83 jumps — patient hunting only), then top hotspots from the tool response with their actual numbers.

**Key:** Rancer is quiet → say so. Don't substitute a different system as if it were the answer.

## Anti-Patterns

❌ **WRONG:** User asks about Rancer → skip Phase 1a, present Amamake instead with fabricated numbers
✅ **RIGHT:** Query Rancer's activity first (Phase 1a), present it as the subject, then show nearby alternatives from hotspots

❌ **WRONG:** Show "Jumps: 1,247 | Kills: 47" for a system without calling `universe(action="activity")`
✅ **RIGHT:** Every number in the output traces to a field in a tool response

❌ **WRONG:** "Show me hunting viability for Imperium renter space" → present Amamake/Heimatar lowsec
✅ **RIGHT:** Call `territory_analysis(coalition="imperium")` first to find actual Imperium systems, use one as hotspot origin

❌ **WRONG:** Claim "Known groups: Snuffed Out, locals" without any kill data showing those groups
✅ **RIGHT:** Group identity comes from killmail data. If no killmails were queried, you don't know who's active.

❌ **WRONG:** Present 8 systems with 10+ lines each (92-line response)
✅ **RIGHT:** Top 5 systems, concise per-system analysis. Extras in a summary table.

❌ **WRONG:** Tool returns 5 systems → add a "Viability by Distance" section with Ahbazon and Uedama (not in tool output)
✅ **RIGHT:** Analysis and narrative sections reference ONLY systems present in the tool-sourced table
