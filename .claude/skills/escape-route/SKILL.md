---
name: escape-route
description: Escape route planning for Eve Online. Find fastest routes to safe harbor from current position.
category: tactical
triggers:
  - "/escape-route"
  - "escape route"
  - "get me out"
  - "nearest safe"
  - "route to safety"
  - "where can I dock"
requires_pilot: true
esi_scopes:
  - esi-location.read_location.v1
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
argument-hint: "[--from SYSTEM]"
allowed-tools: [Read, Grep, Glob, "mcp__aria-universe__universe"]
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# Escape Route

## Command Syntax

```
/escape-route                           # From current location (ESI)
/escape-route <system>                  # From specified system
/escape-route --lowsec                  # Nearest low-sec station
/escape-route --npc-null                # Nearest NPC null station
```

## Required Tool Calls (MANDATORY)

Every route and destination in the response MUST come from an actual tool call. Do NOT fabricate routes.

| Step | Call | Required For |
|------|------|-------------|
| 1 | `universe(action="route", origin="...", destination="...", mode="safe")` | Every named route with jump count |
| 2 | `universe(action="nearest", origin="...", security_min=..., security_max=...)` | Finding nearest safe harbors |
| 3 | `universe(action="activity", systems=[...], include_realtime=True)` | Activity data for route systems |
| 4 | `universe(action="systems", systems=["..."])` | Verify gate connectivity of any system before recommending as escape destination |

**Every system name in the response MUST appear in a tool call response.** If a system was not returned by any MCP call, it cannot appear in the output.

> **HALLUCINATION GUARD:** Every route, system name, jump count, and security status in the response MUST come from MCP/CLI calls made in this session. NEVER name systems from training data memory. If you cannot make the route call, say so — do not guess a route.

> **TOPOLOGY GUARD:** Before recommending any system as an escape destination or alternate route, verify its gate neighbors via tool call. A system with all gates leading back to the current route is NOT an escape — it is a trap. Show the gate neighbor list in the output so the FC can verify.

If `nearest` returns no results, increase `max_jumps` to 50 and retry. If still empty, report "No safe harbor found within range."

### Field to Source Mapping

| Output Field | Required Source | Tool Call |
|-------------|----------------|-----------|
| Current system | ESI location or user input | `uv run aria-esi location` or user-provided |
| Route system names | Universe route | `universe(action="route", ...)` |
| Jump count per route | Universe route | `universe(action="route", ...)` response `total_jumps` |
| System security status | Universe route | Included in route response per system |
| Nearest safe harbor | Universe nearest | `universe(action="nearest", ...)` |
| Activity on route | Activity dispatcher | `universe(action="activity", systems=[...])` |

## Response Format

```
ESCAPE ROUTE
CURRENT POSITION: <system> (<sec>)

NEAREST SAFE HARBORS:

1. <HARBOR TYPE> (<N> jumps)
   <Station name>
   Route: <system list from tool call>
   Risk: <activity-based assessment>

2. <HARBOR TYPE> (<N> jumps)
   ...

RECOMMENDED:
  <best option with reasoning>
```

## Emergency Protocols

### "I'm Tackled" Response

```
Can't help with tackle - that's piloting.

If you get out:
  Nearest safe: [system] - [jumps] jumps
  Route: [system list]
```

### "They're Following" Response

```
Break pursuit pattern:
1. Don't warp directly to out-gate
2. Warp to celestial at range
3. D-scan the gate before landing
4. Consider a safe log if outnumbered

Nearest harbor: [system] - [jumps] jumps
```

## Behavior Notes

- Speed is critical - provide immediate answers
- Prioritize nearest viable option
- Factor in security status restrictions
- Don't moralize - just get the pilot out

## Anti-Patterns

- **WRONG:** Present a route without calling `universe(action="route")`
- **RIGHT:** Call `universe(action="route", origin="...", destination="...", mode="safe")` and present the returned path
- **WRONG:** Name systems that appear in no MCP response (fabricated from training data)
- **RIGHT:** Every system name must trace to a tool call response in this session

## DO NOT

- **DO NOT** lecture about how they got into this situation
- **DO NOT** delay with unnecessary information
- **DO NOT** assume high-sec is always an option
- **DO NOT** forget security status restrictions

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
