---
name: hunting-grounds
description: Hunting ground analysis for Eve Online. Analyze systems for target availability, traffic patterns, and competition.
model: haiku
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

## Required Tool Calls (MANDATORY)

Every activity metric in a hunting ground analysis MUST come from a tool call. Do NOT fabricate kill counts, jump counts, or system activity.

| Output Field | Tool Call |
|-------------|-----------|
| System name, security, kills, pods, NPC kills, jumps | `universe(action="activity", systems=[...], include_realtime=True)` |
| Top hunting grounds list | `universe(action="hotspots", origin="...", max_jumps=N, activity_type="kills")` |
| Sovereignty / alliance | `universe(action="systems", systems=[...])` |
| Coalition intel | `universe(action="territory_analysis", coalition="...")` |
| Viability / competition assessment | Derived from kill/jump metrics above |

**CRITICAL:** Systems outside the `max_jumps` search radius MUST NOT appear in results. If `hotspots` was called with `max_jumps=5`, do not present data for systems 9-10 jumps away. If `hotspots` returned 3 systems, present 3 systems — not 5.

**MCP failure:** If `activity` or `hotspots` calls fail entirely, report that hunting ground analysis requires live activity data and cannot proceed without it.

## Response Format

Present the top 5 systems maximum. If more match, summarize extras in a one-line-per-system table.

For each system present: system name, security, region, viability rating, live intel (kills/pods/NPC kills/jumps from last hour), mark availability assessment, competition assessment, and tactical notes.

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

## Anti-Patterns

❌ **WRONG:** Present activity data for Rancer (9j away) and Hevrice (10j away) when `hotspots` was called with `max_jumps=5`
✅ **RIGHT:** Only present systems that appear in the MCP response — respect the search radius

❌ **WRONG:** Show "Jumps: 1,247 | Kills: 47" for a system without calling `universe(action="activity")`
✅ **RIGHT:** Call `activity` or `hotspots` first, present only returned data

❌ **WRONG:** Claim "Known groups: Snuffed Out, locals" without any kill data showing those groups
✅ **RIGHT:** Group identity comes from killmail data. If no killmails were queried, you don't know who's active.

❌ **WRONG:** Present 8 systems with 10+ lines each (92-line response)
✅ **RIGHT:** Top 5 systems, concise per-system analysis. Extras in a summary table.
