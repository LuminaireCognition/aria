# Skill-Gate ToolSearch Gating & Skill Routing Fixes

**Status:** Proposed
**Date:** 2026-03-12
**Owner:** ARIA Development
**Scope:** `dev/scripts/hooks/skill-gate.sh`, `.claude/skills/abyssal/SKILL.md`, `CLAUDE.md`
**Related:** `dev/reviews/exercise-outputs/20260312-154601/REPORT.md`, `SKILL_GATE_COMPLIANCE_AND_QUALITY.md` (predecessor — implemented F1-F5)

---

## Executive Summary

The 20260312-154601 exercise run (47 queries, 30 skills, 100% completion, 0 errors) is the second clean baseline run since skill-gate deployment. The gate continues to work — all MCP calls are correctly blocked until the Skill tool is invoked, and the model correctly retries after invocation. However, the **violation rate increased from 53% to 66%** despite the proactive prompting fix applied in the prior proposal. The prompt-level approach has reached its ceiling.

**Key findings:**

1. **66% of queries follow the ToolSearch → MCP → BLOCKED → Skill → retry pattern.** The prior proposal's proactive "Skill First" prompting (Prime Directive #8, Skill Loading section) did not reduce violations — the rate increased from 25/47 (53%) to 31/47 (66%). Three iterations of prompt-level fixes have produced no measurable improvement. The model's natural behavior — resolve data tools first — overrides prompt instructions.

2. **The root cause is structural, not prompt-level.** The skill-gate exempts `ToolSearch` (skill-gate.sh line 21), allowing the model to fetch MCP tool schemas before Skill invocation. Once the model has a resolved MCP schema, it calls the MCP tool — which IS gated. The exemption creates a "one free step" that reliably leads to the blocked call.

3. **Three queries never invoked a skill** (first-run-setup, watchlist ×2). Two are the `disable-model-invocation` deadlock pattern already addressed in the prior proposal. The first-run-setup case is an exercise query mismatch, not a code defect.

4. **One query took 253s/23 tool calls** because "fit a Stormbringer for abyssal" routed to the fitting skill instead of the abyssal skill. The abyssal skill has injected prerequisite data for weather types and NPC threats; the fitting skill doesn't.

This proposal covers three fixes. One is a structural hook change that addresses the dominant 66% violation pattern. The other two are skill routing corrections. No prompt-level changes are proposed — the prior three iterations demonstrate that additional prompt changes have negligible impact.

### Corrections to REPORT.md Recommendations

| Report Recommendation | Issue | Correction |
|---|---|---|
| H1: Pre-load MCP tool schemas | Contradicts deferred-loading architecture | Per features-overview.md, tool search loads MCP tools up to 10% of context and defers the rest. Pre-loading all 8 MCP schemas defeats this budget. The fix is the opposite: make MCP schemas *harder* to access before Skill invocation (F1). |
| H2: Auto-invoke skills from gate hook | Not supported by hooks API | Per hooks-reference.md, PreToolUse can return `permissionDecision: "allow"\|"deny"\|"ask"`. There is no mechanism for a hook to auto-invoke the Skill tool. The current block-and-recover pattern is the maximum the hooks API supports. |
| H4: Add triggers to `_index.json` | ARIA-specific, not standard skill mechanism | Per skills.md, skill routing uses the `description` field in SKILL.md frontmatter: "Claude uses this to decide when to apply the skill." The `_index.json` file is an ARIA extension. Route via description keywords and CLAUDE.md routing hints. |
| C1.2: ToolSearch removal | Conflates ordering with overhead | ToolSearch is not wasted — it is the designed mechanism for deferred tool loading. The waste is the *ordering* (ToolSearch before Skill). Fixing the ordering (F1) eliminates the waste without removing ToolSearch. |

### Relationship to Prior Proposals

`SKILL_GATE_COMPLIANCE_AND_QUALITY.md` (2026-03-12) applied proactive "Skill First" prompting to CLAUDE.md and resolved the `disable-model-invocation` deadlock. All five fixes are confirmed working. The violation rate remained high (66% vs. 53%), demonstrating that prompt-level changes have reached diminishing returns. This proposal shifts to structural enforcement.

---

## F1: Gate MCP-Bound ToolSearch Calls (Critical)

### Problem

31 of 47 queries (66%) follow this pattern:

```
ToolSearch(select:mcp__*) → MCP tool (BLOCKED) → Skill → MCP tool (retry → success)
```

The prior proposal added proactive prompting: "invoke the Skill tool BEFORE calling any MCP tools, CLI commands, or ToolSearch for data tools" (CLAUDE.md Prime Directive #8). Three iterations of prompt-level fixes have not reduced the violation rate. The model's natural behavior — resolve tool schemas first, then call tools — consistently overrides prompt instructions.

### Root Cause

The skill-gate hook (`skill-gate.sh` line 21) explicitly exempts `ToolSearch`:

```bash
case "$TOOL_NAME" in
  Read|Glob|Grep|ToolSearch|WebFetch|WebSearch) exit 0 ;;
esac
```

This allows the model to call `ToolSearch(select:mcp__aria-universe__market)` *before* Skill invocation. The call succeeds, resolving the MCP tool schema. The model now has a callable MCP tool and naturally calls it — which IS gated. The exemption creates a reliable pathway to the blocked-call pattern.

### Evidence

From `10-gatecamp-q1.tools.json` (representative of 31/47 queries):

| Step | Tool Call | Result |
|------|-----------|--------|
| 1 | `ToolSearch(select:mcp__aria-universe__universe)` | **Success** (not gated) |
| 2 | `mcp__aria-universe__universe(activity, ...)` | **BLOCKED** by skill-gate |
| 3 | `Skill("gatecamp")` | Success — sets marker |
| 4 | `mcp__aria-universe__universe(activity, ...)` | **Success** |

From `08-fitting-q1.tools.json` (clean execution — correct flow):

| Step | Tool Call | Result |
|------|-----------|--------|
| 1 | `Skill("fitting")` | Success — sets marker |
| 2-5 | `Read(...)` | Profile, archetype, etc. |
| 6 | `ToolSearch(select:mcp__aria-universe__sde)` | Success (marker exists) |
| 7+ | `mcp__aria-universe__sde(...)` | Success |

The clean execution shows that when Skill is invoked first, ToolSearch naturally follows. The model doesn't need ToolSearch to *decide* which skill to invoke — it needs it to *resolve* MCP schemas for data calls. Gating MCP-bound ToolSearch before Skill invocation breaks the violation chain at step 1.

### Proposed Fix

**File:** `dev/scripts/hooks/skill-gate.sh`

Replace the blanket ToolSearch exemption (line 21) with MCP-aware gating:

```bash
# Phase 2: Allow read-only and infrastructure tools unconditionally
case "$TOOL_NAME" in
  Read|Glob|Grep|WebFetch|WebSearch) exit 0 ;;
  ToolSearch)
    # Allow ToolSearch for non-MCP tools (Read, Edit, etc.)
    # Gate ToolSearch for MCP tools until Skill has been invoked
    if [[ ! -f "$MARKER" ]]; then
      QUERY=$(echo "$INPUT" | jq -r '.tool_input.query // empty')
      if echo "$QUERY" | grep -q 'mcp__'; then
        echo "SKILL-GATE-BLOCK: ToolSearch for MCP tools blocked — no skill invoked yet. Action: invoke the Skill tool for the relevant skill first. After Skill invocation, MCP tool schemas can be resolved." >&2
        exit 2
      fi
    fi
    exit 0
    ;;
esac
```

#### How This Works Per the Hooks API

Per hooks-reference.md:

- **PreToolUse** fires before any tool call executes (line 506-508). The hook receives `tool_name` and `tool_input` as JSON on stdin.
- **Exit code 2** blocks the tool call and feeds stderr back to Claude (line 371). Claude sees the `SKILL-GATE-BLOCK` message and follows the recovery path (invoke Skill, then retry).
- **`tool_input`** contains the ToolSearch query (e.g., `{"query": "select:mcp__aria-universe__market"}`), which we inspect to distinguish MCP-bound from non-MCP ToolSearch calls.

This is the same mechanism already used for MCP tool gating (skill-gate.sh lines 48-58). We extend it to ToolSearch calls whose query targets MCP tools.

#### What Changes for the Model

| Before (current) | After (proposed) |
|---|---|
| ToolSearch(mcp__*) → succeeds → MCP → BLOCKED → Skill → retry | ToolSearch(mcp__*) → BLOCKED → Skill → ToolSearch(mcp__*) → succeeds → MCP → succeeds |

The model still calls ToolSearch first (its natural behavior). But now ToolSearch is also gated for MCP queries, so the block happens one step earlier — before the model has a resolved MCP schema. The block message says to invoke Skill first. After Skill invocation, both ToolSearch and MCP calls succeed.

**Net change:** The violation pattern shifts from 4 tool calls (ToolSearch + blocked MCP + Skill + retried MCP) to 3 tool calls (blocked ToolSearch + Skill + ToolSearch + MCP). This saves **1 tool call per violation** (~31 calls in this run). More importantly, the model never reaches the "I have a schema, let me call MCP" state that leads to the blocked MCP call, which reduces confusion and latency.

#### What ToolSearch Calls Are NOT Gated

- `ToolSearch(select:Read,Edit)` — non-MCP, always allowed
- `ToolSearch("notebook jupyter")` — keyword search, not MCP-bound
- Any ToolSearch call after Skill invocation (marker exists) — always allowed

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Non-MCP queries that happen to mention "mcp__" in search terms | Negligible | ToolSearch queries use `select:tool_name` format; false positives require the user to literally type "mcp__" as a keyword |
| Model calls CLI (`aria-esi`) instead of ToolSearch after block | Low | CLI calls are already gated by the Bash case (skill-gate.sh lines 32-44) |
| ToolSearch-for-MCP after Skill invocation adds a step | None | Marker exists; ToolSearch passes immediately |

---

## F2: Abyssal-Fitting Skill Routing (Medium)

### Problem

Query 07 ("How should I fit a Stormbringer for abyssal deadspace?") took 253s with 23 tool calls. The model routed to the `/fitting` skill instead of `/abyssal`. The abyssal skill has injected prerequisite data (via `!`command`` dynamic context injection per skills.md §Inject dynamic context) covering weather types, tier difficulty, and NPC threats. The fitting skill has no abyssal context, so the model had to improvise via iterative SDE lookups.

### Root Cause

The fitting skill's description matches "fit" + ship name strongly. The abyssal skill's description matches "abyssal deadspace" strongly. When both keywords are present ("fit Stormbringer for abyssal"), the model resolves to fitting because the action word "fit" has higher salience than the context word "abyssal."

Per skills.md §Skill not triggering: "Check the description includes keywords users would naturally say." The abyssal skill description lacks fitting-related trigger phrases.

### Proposed Fix

**Two complementary changes:**

**A. Add fitting-for-abyssal routing to the abyssal skill description.**

**File:** `.claude/skills/abyssal/SKILL.md` frontmatter

Amend the `description` to include fitting context:

```yaml
description: >
  Abyssal Deadspace guide for weather types, tiers, ship fits, and NPC threats.
  Use when capsuleer asks about fitting ships for abyssal deadspace, abyssal
  filaments, or abyssal weather/NPC encounters. This skill provides weather and
  NPC reference data that the fitting skill does not have.
```

Per skills.md: "Skill descriptions are loaded into context so Claude knows what's available" (line 277). Adding "fitting ships for abyssal" to the description gives Claude the signal to prefer abyssal over fitting for combined queries.

**B. Add a routing hint to CLAUDE.md.**

**File:** `CLAUDE.md`, Routing Hints table

Add:

```markdown
| "fit [ship] for abyssal", "abyssal fit" | `/abyssal` skill (not `/fitting`) |
```

Per CLAUDE.md §Routing Hints: "Some queries map to knowledge-only skills that don't use MCP tools (so the skill-gate can't catch missed invocations). Always route these explicitly." While abyssal does use MCP tools, the routing ambiguity with fitting makes an explicit hint valuable.

### Why Not `context: fork`

The report's H3 suggested using `context: fork` (per skills.md §Run skills in a subagent) to have abyssal delegate to fitting in a forked subagent. This is architecturally sound but over-engineered for this case:

1. The abyssal skill already has fitting guidance in its injected prerequisites
2. Forking adds a subagent round-trip (~15-30s) per sub-agents.md
3. The problem is routing (wrong skill invoked), not isolation

If future exercise runs show that abyssal-fitting queries consistently need the fitting skill's EOS validation, `context: fork` delegation can be reconsidered.

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Broader abyssal description triggers on non-abyssal fitting queries | Low | "abyssal deadspace" is a distinctive phrase; generic "fit my Vexor" won't match |
| Routing hint table grows unwieldy | Low | Table currently has 2 entries; adding 1 is fine |

---

## F3: Watchlist Routing Gap (Low)

### Problem

Two watchlist queries (26, 27) never invoked a skill. The report notes: "There is no `watchlist` skill in the Skill tool's available skills list." The watchlist functionality exists only as CLI commands (`aria-esi watchlist-*`).

The prior proposal resolved the `disable-model-invocation` deadlock by exempting watchlist CLI commands from the gate (skill-gate.sh lines 38-41). This means watchlist queries bypass skill loading entirely — no prerequisite data, no formatting rules, no persona overlay.

### Root Cause

Per skills.md, "skill descriptions are loaded into context so Claude knows what's available" (line 277). Without a registered skill, Claude has no description to match against, and the skill-gate has nothing to enforce. The watchlist exemption in skill-gate.sh was the correct deadlock fix but leaves a routing gap.

### Proposed Fix

**Add a routing hint to CLAUDE.md** for watchlist queries.

**File:** `CLAUDE.md`, Routing Hints table

```markdown
| "watchlist", "war targets", "watch list" | No skill — use CLI directly: `uv run aria-esi watchlist-list`, `watchlist-add`, `watchlist-remove` |
```

Per CLAUDE.md §Routing Hints: "Knowledge-only skills have no MCP calls to gate, so they rely on prompt-level routing rather than hook enforcement." Watchlist is CLI-only, so it falls in the same category.

### Why Not Register a Watchlist Skill

Per skills.md, a skill with `disable-model-invocation: true` has its "description not in context" (line 274). The Skill tool cannot invoke it. The prior proposal confirmed: the Skill tool rejects `disable-model-invocation` skills with an error. Creating a skill that can't be invoked via the Skill tool doesn't solve the routing problem — it just adds a file.

A skill WITHOUT `disable-model-invocation` would work, but watchlist commands modify state (add/remove entities). Per skills.md §Control who invokes a skill: "Use [disable-model-invocation] for workflows with side effects or that you want to control timing... You don't want Claude deciding to [act] because [the data] looks ready." A user-invocable watchlist skill risks Claude autonomously modifying the watchlist.

The routing hint provides the routing signal without the invocation risk.

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Routing hint doesn't prevent ToolSearch-first pattern | None | Watchlist uses CLI, not MCP — not affected by the ToolSearch gate |
| Model attempts watchlist modification without user intent | Avoided | No skill registered; routing hint points to CLI commands that require explicit user action |

---

## Out of Scope

### Dropped Report Recommendations (with documentation justification)

| Recommendation | Why Dropped | Reference |
|---|---|---|
| **H1: Pre-load MCP tool schemas** | Contradicts deferred-loading architecture. Per features-overview.md §Context cost by feature: "Tool search (enabled by default) loads MCP tools up to 10% of context and defers the rest until needed." Pre-loading all 8 schemas defeats this budget and increases per-request context cost. | features-overview.md line 218 |
| **H2: Auto-invoke skills from gate hook** | Not possible with current hooks API. Per hooks-reference.md §PreToolUse decision control: hooks can return `permissionDecision` of `"allow"`, `"deny"`, or `"ask"`. No fourth option exists for "invoke a different tool." The block-and-recover pattern is the maximum the PreToolUse hook supports. | hooks-reference.md lines 530-532 |
| **C1.1: Stronger prompt positioning** | Three iterations of prompt changes (recovery-focused → proactive → negative examples) have not reduced the violation rate. The 53% → 66% increase demonstrates that additional prompt changes in CLAUDE.md have negligible impact on the model's tool-ordering behavior. F1 addresses the root cause structurally. | Prior proposals: SKILL_GATE_AND_EXERCISE_HARDENING F1, SKILL_GATE_COMPLIANCE_AND_QUALITY F1 |
| **C1.3: Negative examples in CLAUDE.md** | Same as C1.1 — prompt-level approach has reached its ceiling. Adding "DO NOT" examples to CLAUDE.md would increase context cost without demonstrated benefit. | — |

### Other Items Not Addressed

- **first-run-setup (query 03):** The prior proposal classified this as an exercise query mismatch: "the exercise query should be changed to `/first-run-setup`, not the skill's invocation model." The skill has `disable-model-invocation: true`, which is correct per skills.md — it writes to profile files. Natural language queries cannot trigger it. No code change needed.
- **Prompt-level "Skill First" text:** The existing text in CLAUDE.md (Prime Directive #8, Skill Loading section) is retained. It provides correct guidance for cases where the structural gate doesn't apply (e.g., knowledge-only skills). No changes proposed.
- **`disable-model-invocation` evaluation:** The report could have recommended evaluating which skills should be `disable-model-invocation: true` per skills.md line 274. This is deferred — the current set (watchlist, journal, first-run-setup) is correct.

---

## Implementation Plan

F1 is independent. F2 and F3 are independent of each other and of F1.

```
Phase 1:
  F1: Gate MCP-bound ToolSearch in skill-gate.sh    [Low effort, ~10 lines]

Phase 2 (parallel):
  F2: Amend abyssal skill description + routing hint  [Trivial, ~3 lines]
  F3: Add watchlist routing hint to CLAUDE.md          [Trivial, ~1 line]

Phase 3 (validation):
  Re-run exercise suite with same config:
  --explicit --filter NONE --parallel 5 --timeout 920
```

### Success Criteria

| Metric | Current (20260312-154601) | Target |
|--------|--------------------------|--------|
| Skill-gate violations (ToolSearch → MCP → BLOCKED) | 31/47 (66%) | <15% |
| Total wasted tool calls from violations | ~62 | <15 |
| Abyssal-fitting routing to wrong skill | 1 query (253s) | 0 |
| Watchlist queries with no routing signal | 2 queries | 0 |
| Net correctness | 47/47 (100%) | 47/47 (100%) — no regression |

**Note on the violation target:** Gating MCP-bound ToolSearch shifts the violation from 4 wasted calls to 1 (blocked ToolSearch). Some violations will persist — the model may still attempt ToolSearch(mcp__*) before Skill. But each violation now costs 1 tool call instead of 2, and the model receives the block message earlier in its planning, before it has committed to an MCP-first approach.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| F1: Model finds alternative path to MCP schemas after ToolSearch block | Low | MCP tool calls are also gated (existing behavior); any path to MCP still requires Skill marker |
| F1: ToolSearch block message confuses model | Low | Message uses same `SKILL-GATE-BLOCK` prefix the model already recovers from reliably (100% recovery rate in current run) |
| F1: False positive on ToolSearch query containing "mcp__" | Negligible | ToolSearch queries use `select:tool_name` format; accidental matches require deliberate use of the internal prefix |
| F2: Abyssal description too broad | Low | "abyssal deadspace" is highly distinctive in EVE context |
| F3: Routing hint insufficient for watchlist discovery | Low | Watchlist users already know the functionality; hint ensures correct CLI path |

---

## SKILLSSKILLS Documentation Adherence

| Proposal Claim | Reference | Status |
|---|---|---|
| PreToolUse exit 2 blocks tool calls | hooks-reference.md §Exit code 2 behavior per event (line 371): "Blocks the tool call" | Correct — used in F1 |
| PreToolUse receives `tool_input` with call parameters | hooks-reference.md §PreToolUse input (lines 510-524): JSON includes `tool_input` object | Correct — F1 inspects `tool_input.query` |
| Deferred tools load on demand via ToolSearch | features-overview.md §MCP servers (line 218): "Tool search loads MCP tools up to 10% of context and defers the rest" | Correct — justifies NOT pre-loading (drops H1) |
| PreToolUse can only allow/deny/ask | hooks-reference.md §PreToolUse decision control (lines 528-532): `permissionDecision` field accepts three values | Correct — justifies dropping H2 |
| Skill descriptions loaded at session start | skills.md line 277: "Skill descriptions are loaded into context so Claude knows what's available" | Correct — used in F2 |
| `disable-model-invocation` removes description from context | skills.md line 274: "Description not in context, full skill loads when you invoke" | Correct — justifies F3's routing hint over skill registration |
| `disable-model-invocation` for side-effect skills | skills.md §Control who invokes a skill: "Use for workflows with side effects" | Correct — justifies not registering watchlist as model-invocable |
| `!`command`` injects dynamic context at skill load time | skills.md §Inject dynamic context (lines 343-373): "command output replaces the placeholder" | Correct — referenced in F2 for abyssal injected prerequisites |
| Hook execution order across scopes not guaranteed | hooks-reference.md: no specification of cross-scope ordering | Absence confirmed — inherited from prior proposal |
