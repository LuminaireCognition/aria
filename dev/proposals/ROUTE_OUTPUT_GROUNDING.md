# Route Output Grounding: Eliminating Generated Tactical Commentary

**Status:** PROPOSED (2026-03-18)
**Related:** `docs/ROUTE_OUTPUT_SPEC.md` (new), `.claude/skills/route/SKILL.md`, `.claude/skills/escape-route/SKILL.md`, `.claude/skills/orient/SKILL.md`, `personas/paria/skill-overlays/route.md`, `CLAUDE.md` routing hints

---

## Executive Summary

Route-family skill outputs currently mix verified topology data with generated tactical commentary. The commentary is the only component that can be *dangerously wrong* — gate lists, security statuses, and activity numbers are sourced from MCP/SDE and can be stale but not fabricated. A reviewed `roam_route` output (2026-03-18, `dev/reviews/route.txt`) contained a critical error: CHA2-Q was recommended as an escape offering "alternate routing options deeper into Fountain" when it is in fact a 2-gate dead end. An FC following that advice under pressure would be trapped.

This proposal introduces two layers to eliminate generated tactical judgments from route outputs while preserving all grounded data:

1. **Constraint spec** (`docs/ROUTE_OUTPUT_SPEC.md`) — universal output rules for all route-producing skills, referenced from CLAUDE.md
2. **Skill-level output template changes** — structural modifications to route, escape-route, orient, and persona overlays that make compliance the path of least resistance

---

## Problem Statement

### The Error Taxonomy

Route outputs contain three categories of content with different error profiles:

| Category | Source | Can Be Wrong? | Example |
|----------|--------|--------------|---------|
| **Topology** | SDE (static) | No | "A-1CON has 2 gates: LIWW-P, YZ-LQL" |
| **Activity** | ESI (volatile) | Stale, not fabricated | "G95F-H: 1,036 NPC kills" |
| **Commentary** | Model generation | Yes, dangerously | "CHA2-Q offers alternate routing options" |

Every verified error in the reviewed output fell in category 3:

1. **CHA2-Q dead-end presented as escape** — model generated a plausible-sounding tactical narrative without verifying that CHA2-Q connects only to G95F-H and B32-14 (both already on the route)
2. **"Detour Option" described the main route** — model narrated strategy about a path already in the table, confusing the FC about what was primary vs. alternate
3. **Prescriptive advice** ("Stay aligned. Goons will form") — unfalsifiable but overstepping; FCs make these calls, not intel tools

### Why This Happens

The model's training data rewards helpful, complete-feeling responses. When presented with a route backbone and activity data, it fills silence with tactical interpretation. This is useful in conversational contexts but harmful in structured intel output where the FC is the tactician and the tool is the data source.

The existing hallucination guards in escape-route and orient (mandatory tool-call sourcing) prevent *system name* fabrication but do not address *strategic inference* fabrication. You can generate a dangerous escape recommendation using only real system names.

### Root Cause

No output rule in any route-family skill prohibits generated tactical commentary. The skills define what data to fetch and how to format tables, but the space between tables is unconstrained — the model fills it with plausible-sounding strategy.

---

## Proposed Changes

### Change 1: Create `docs/ROUTE_OUTPUT_SPEC.md` (Constraint Spec)

**Priority:** P0
**Effort:** Low
**Scope:** All route-producing outputs regardless of entry point

This document defines universal output rules for any response containing route data. It is referenced from CLAUDE.md so it loads into every session.

#### Content

The spec establishes four principles:

**Principle 1: Show topology, don't narrate it.**
Every named waypoint must include its full gate neighbor list with security status. Dead ends, pipe systems, and hub systems become self-evident from the data. The FC reads "CHA2-Q: gates to G95F-H (-0.68), B32-14 (-0.72)" and immediately sees a dead end — no commentary needed.

**Principle 2: No prescriptive language.**
Route outputs may contain system names, security statuses, constellation names, gate neighbors, sovereignty, and timestamped activity numbers. They may not contain verbs that prescribe FC behavior: "burn through," "stay aligned," "take the X gate," "push deeper," "expect caps." The one permitted imperative is safety-critical warnings derived from data (e.g., "pipe system" for 2-gate systems, "ACTIVE CAMP" from real-time detection).

**Principle 3: Timestamp volatile data.**
Every activity figure (NPC kills, ship kills, jumps, gatecamp detections) must include a staleness indicator. Current-hour data shows as-is. Data older than 1 hour shows `(>1h)`. This lets the FC discount stale intel without the model needing to editorialize about freshness.

**Principle 4: Gate topology appendix for routes >5 jumps.**
Any route-producing output with more than 5 waypoints must include a gate topology block listing full gate neighbors (with security status) for the terminus system, dead ends, pipes, and decision points (3+ gates). This applies to all entry points: `/route`, `roam_route`, `/orient` escape routes, and `/escape-route`. Annotation rules: `[dead end]` for <=2 gates with all neighbors on-route, `[pipe]` for exactly 2 gates both on-route, `[hub]` for 5+ gates. These are structural facts, not tactical advice.

#### Banned Patterns (explicit list for the spec)

| Pattern | Why Banned | Replace With |
|---------|-----------|--------------|
| "offers alternate routing options" | Unverified strategic claim | Show gate neighbors; FC decides |
| "burn through" / "don't linger" | Prescriptive FC advice | "pipe (2 gates)" in Notes column |
| "expect caps/supers" | Speculation from NPC kill volume | Show NPC kill count; FC interprets |
| "Goons will form" / "[group] will respond" | Speculation about player behavior | Show sovereignty; FC knows their opponents |
| "good d-scan checkpoint" | Subjective tactical value | Show gate count; FC decides utility |
| "stay aligned" | Basic piloting advice | Omit — FC knows |
| "your fastest exit is X" | Route claim without explicit verification | Show escape routes from tool calls only |
| "push deeper after terminus" | Strategic suggestion | Show neighbor topology of terminus system |
| "Snuffed Out works that pipe" | Entity claim from training data | Show sovereignty from sov data; omit entity names not in MCP response |
| "Known camp spot: X gate in Y" | Unverified camp claim | Show real-time gatecamp detection data if available; otherwise omit |

#### Integration Point

Add to CLAUDE.md under Reference Documentation:

```markdown
| Route output formatting | `docs/ROUTE_OUTPUT_SPEC.md` |
```

And add a one-line reference in the Prime Directives or Skill Loading section:

```markdown
**Route output constraint:** All route-producing skills must comply with `docs/ROUTE_OUTPUT_SPEC.md`. See that document for banned commentary patterns and mandatory topology display rules.
```

---

### Change 2: Add mandatory gate-neighbor display to route SKILL.md

**Priority:** P0
**Effort:** Low
**Files:** `.claude/skills/route/SKILL.md`

#### Modification: Response Format table schema

Current:
```
| System | Sec | Ships | Pods | Jumps | Notes |
```

Proposed:
```
| # | System | Sec | Gates | Ships | Pods | Jumps | Notes |
```

Where `Gates` contains the count and neighbor names: `3: A, B, C` for systems with <=4 gates, or just the count `6` for hub systems (neighbor names in appendix).

#### Modification: Add gate-neighbor appendix requirement

For routes >5 jumps, append a gate topology block after the main table:

```
GATE TOPOLOGY (terminus + decision points)
  C1XD-X (-0.45): 00GD-D (-0.20), G95F-H (-0.68), B32-14 (-0.72)
  B32-14 (-0.72): C1XD-X (-0.45), G95F-H (-0.68), CHA2-Q (-0.85)
  CHA2-Q (-0.85): G95F-H (-0.68), B32-14 (-0.72) [dead end]
```

This is sourced from the `neighbors` field already present in `universe(action="route")` and `universe(action="systems")` responses. No additional MCP calls needed.

**Annotation rules for the appendix:**
- Systems with exactly 1 non-route neighbor: no annotation
- Systems with 0 non-route neighbors and <=2 total gates: `[dead end]`
- Systems with exactly 2 gates where both are on the route: `[pipe]`
- Systems with 5+ gates: `[hub]`

These annotations are structural facts derived from gate count, not tactical advice.

#### Modification: Add to DO NOT section

```markdown
- **DO NOT** generate tactical commentary, strategic advice, or prescriptive language — see `docs/ROUTE_OUTPUT_SPEC.md`
- **DO NOT** recommend escape routes without verifying terminus system gate connectivity against actual neighbor data
- **DO NOT** describe a system as offering "alternate routing" or "deeper options" without showing its gate neighbors
```

---

### Change 3: Add topology verification gate to escape-route SKILL.md

**Priority:** P0
**Effort:** Trivial
**Files:** `.claude/skills/escape-route/SKILL.md`

#### Modification: Add verification requirement

In the "Required Tool Calls (MANDATORY)" section, add:

```markdown
| 4 | `universe(action="systems", systems=["..."])` | Verify gate connectivity of any system recommended as escape destination |
```

And add to the hallucination guard:

```markdown
> **TOPOLOGY GUARD:** Before recommending any system as an escape destination or alternate route, verify its gate neighbors via tool call. A system with all gates leading back to the current route is NOT an escape — it is a trap. Show the gate neighbor list in the output so the FC can verify.
```

This directly prevents the CHA2-Q class of error.

---

### Change 4: Add commentary prohibition to orient SKILL.md

**Priority:** P1
**Effort:** Trivial
**Files:** `.claude/skills/orient/SKILL.md`

Orient already has strong hallucination guards for data sourcing. Add a parallel guard for commentary:

```markdown
> **COMMENTARY GUARD:** Orientation output presents data for FC decision-making. Do not generate strategic advice ("expect organized response," "you should leave," "good place to set up"). Show sovereignty, activity numbers, and gate topology. The FC interprets.
```

The existing "Threat Implications by Territory Type" table (lines 117-124) contains generated inferences ("Organized standing fleets, rapid response," "Variable response capability") that violate the commentary guard being added in the same change. **Decision: Remove the Implication column entirely.** The territory type categories (Major Coalition, Smaller Alliance, NPC Null-sec, Unclaimed) are useful structural labels derivable from sov data, but the implications are speculation.

Replace the table with:

```markdown
### Territory Type Labels

Derive territory type from sovereignty data returned by `local_area` or `systems`:

| Sov Data | Territory Label |
|----------|----------------|
| Alliance in known coalition (`sovereignty.coalition_name` present) | Show: `[TICKER] Alliance — Coalition Name` |
| Alliance without coalition | Show: `[TICKER] Alliance` |
| No sovereignty holder | `NPC Null-sec` |
| No holder + recent sov changes in constellation | `Contested` |

Do not generate behavioral predictions from territory type. The FC knows their opponents.
```

---

### Change 5: Update PARIA route overlay for grounding compliance

**Priority:** P1
**Effort:** Medium
**Files:** `personas/paria/skill-overlays/route.md`

The PARIA overlay currently adds persona-flavored *commentary* — "hunting grounds," "your call, Captain," "crash their party." This is the persona's voice and adds character, but it needs to operate within the grounding constraint.

#### Approach: Persona voice in framing, not in fabrication

The overlay should:
- **Keep:** Terminology translations (safe→quiet, dangerous→hunting grounds, threat→opportunity) — these are label changes, not data fabrication
- **Keep:** "Your call, Captain" — this is the opposite of prescriptive; it defers to the FC
- **Keep:** Box-drawing format, section naming conventions
- **Remove:** "Known camp spot: Old Man Star gate in Villore" (unless from real-time data)
- **Remove:** "Snuffed Out and locals work that pipe" (entity claims from training data)
- **Modify:** "HUNTING OPPORTUNITIES" section should show high-activity systems from data, not generated camp-spot recommendations
- **Add:** Gate topology appendix (same as base skill, persona-styled header)

#### Specific Changes

**Section 1 — "PARIA-Specific Route Analysis" (lines 57-74): Replace entirely.**

The current section contains ungrounded camp-spot recommendations and escape route claims without tool-call verification. Replace with:

```markdown
### PARIA-Specific Data Presentation

For pirate pilots, the same grounded data is presented with operational framing:

1. **Low-sec segments** labeled as "Operating Space" (not "Dangerous")
2. **Pipe systems** (2 gates) flagged as "Chokepoint" in Notes
3. **High-traffic systems** labeled as "Active" with jump counts
4. **Gate topology appendix** uses header "TACTICAL TOPOLOGY" instead of "GATE TOPOLOGY"

All data comes from MCP calls. Persona changes labels, not facts.
```

This removes the "Escape Route Planning" sub-section (lines 72-74) which recommends "Nearest NPC null station" and "Alternate routes if primary is camped" without mandating tool-call verification. Those capabilities belong to `/escape-route`, not to route commentary.

**Section 2 — "PARIA Response Format" example (lines 30-54): Update for compliance.**

The example output block contains two banned patterns:
- `Known camp spot: Old Man Star gate in Villore` — unverified camp-spot claim from training data
- `HUNTING OPPORTUNITIES` section with generated intel

Replace lines 45-52 of the example with:

```
───────────────────────────────────────────────────────────────────
ACTIVITY:
  Villore: 892 jumps, 2 ships, 1 pod (border system)
  Old Man Star: 234 jumps, 5 ships, 3 pods

TACTICAL TOPOLOGY (decision points)
  Villore (0.54): Old Man Star (0.30), ... [border]
  Old Man Star (0.30): Villore (0.54), Heydieles (0.30), ...
───────────────────────────────────────────────────────────────────
Your call, Captain.
```

**Section 3 — "PARIA Route with Competition" example (lines 101-127): Update entity claim.**

Line 114 reads `Competition: CODE. (Tornado fleet)` — this is a training-data entity claim. The real-time gatecamp detection response provides attacker ship types and kill counts, but not corporation identification by name from training data.

Replace lines 111-115 with:

```
🎯 COMPETITION WORKING THIS ROUTE
  System: Niarja (0.5)
  Recent kills: 5 in last 10 minutes
  Attacker ships: Tornado x3 (from real-time data)
  Options: Wait them out, detour via Dodixie, or crash their party
```

The attacker ship types come from the real-time kill data fields. The corporation/alliance name may appear in the kill data — if present, show it. If not, omit rather than guess.

**Section 4 — "Example: Same Route, Different Personas" (lines 143-149): Replace PARIA example.**

The current PARIA example contains entity claims (`"Snuffed Out and locals work that pipe"`) and unverified camp-spot recommendations (`"The Villore gate is a known camp spot if you want to set up"`). Replace lines 148-149 with:

```markdown
**PARIA (Pirate pilot, Jita -> Old Man Star):**
> "12 jumps, enters low-sec at Villore. Old Man Star — 5 ships, 3 pods last hour, active hunting ground. Villore gate is the chokepoint (2 gates on route). High-sec portion is 8 jumps of nothing. Your call, Captain."
```

This preserves the persona voice (dismissive of high-sec, framing activity as opportunity) while grounding every claim in data fields.

---

### Change 6: Add `has_persona_overlay: true` verification note to `_index.json` affected skills

**Priority:** P2
**Effort:** Trivial

Verify that route, escape-route, and orient all have `has_persona_overlay: true` if overlays exist or are planned. Currently only route has PARIA overlay. If escape-route or orient gain overlays that implement persona-voiced grounding, their index entries need updating.

No changes needed now — this is a reminder for when overlays are created for other skills.

---

## Implementation Order

| Phase | Changes | Validates |
|-------|---------|-----------|
| **1. Spec + route skill** | #1 (spec), #2 (route SKILL.md) | Run `/route` and `roam_route` queries against live data, verify no commentary in output, verify gate topology appendix appears |
| **2. Safety-critical skills** | #3 (escape-route) | Run `/escape-route` from dead-end systems, verify tool-call verification of escape destinations |
| **3. Orient + overlay** | #4 (orient), #5 (PARIA overlay) | Run `/orient` in null-sec, verify no strategic inference; run PARIA `/route`, verify persona voice without fabrication |
| **4. Index hygiene** | #6 (_index.json) | Verify overlay loading works for modified skills |

---

## Testing Strategy

### Test 1: CHA2-Q Dead-End Detection

```
/route C1XD-X B32-14
```

Expected: Gate topology appendix shows CHA2-Q with `[dead end]` annotation. No mention of CHA2-Q as escape or alternate routing option.

### Test 2: Prescriptive Language Elimination

```
Roaming route from 7BIX-A through Fountain ratting systems, 20 jumps
```

Expected: Route table with gates column, activity data with timestamps, gate topology appendix for terminus and decision points. No "burn through," "stay aligned," "expect caps," or strategic advice.

### Test 3: Escape Route Topology Verification

```
/escape-route --from CHA2-Q
```

Expected: Tool calls verify CHA2-Q neighbors before recommending escape. Output shows CHA2-Q's 2 gates explicitly. Does not recommend "deeper into Fountain" as an option.

### Test 4: PARIA Persona Compliance

```
[With PARIA active]
/route Jita Old Man Star
```

Expected: Persona voice in labels and framing ("hunting grounds," "competition"), but no unverified entity claims ("Snuffed Out works this pipe"), no camp-spot recommendations without real-time data, gate topology appendix present.

### Test 5: Orient Commentary Guard

```
/orient 7BIX-A
```

Expected: Threat level, sovereignty, activity tables, escape routes — all from `local_area` response. No "expect organized response" or "rapid response capability" unless tied to specific data field.

---

## Success Criteria

- [ ] `docs/ROUTE_OUTPUT_SPEC.md` exists and is referenced from CLAUDE.md
- [ ] Route outputs include gate neighbor data for all named waypoints
- [ ] No route-family output contains prescriptive verbs (burn, align, push, expect, avoid-as-imperative)
- [ ] Dead-end systems are annotated `[dead end]` in gate topology, never recommended as escapes
- [ ] Escape route skill verifies terminus gate connectivity via tool call before recommending
- [ ] PARIA overlay passes grounding compliance (persona voice, no fabricated entities or unverified camp spots)
- [ ] Activity data includes staleness indicator
- [ ] An FC receiving route output can identify dead ends, pipes, hubs, and decision points from the data alone without reading any generated prose

---

## Summary

| # | Change | Priority | Effort | Files |
|---|--------|----------|--------|-------|
| 1 | Route output constraint spec | P0 | Low | `docs/ROUTE_OUTPUT_SPEC.md`, `CLAUDE.md` |
| 2 | Gate topology in route skill | P0 | Low | `.claude/skills/route/SKILL.md` |
| 3 | Escape topology verification | P0 | Trivial | `.claude/skills/escape-route/SKILL.md` |
| 4 | Orient commentary guard | P1 | Trivial | `.claude/skills/orient/SKILL.md` |
| 5 | PARIA overlay grounding | P1 | Medium | `personas/paria/skill-overlays/route.md` |
| 6 | Index hygiene | P2 | Trivial | `.claude/skills/_index.json` |

**Core principle:** If the output can't be wrong, it doesn't need review. Gate topology can't be wrong (SDE). Activity numbers can be stale but not invented. The only things that can be dangerously wrong are generated tactical judgments — so eliminate them structurally.
