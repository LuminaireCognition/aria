# Exercise Run Remediation — 20260310-232643

**Status:** In Progress
**Date:** 2026-03-10
**Owner:** ARIA Development
**Scope:** `src/aria_esi/mcp/dispatchers/pilot.py`, `src/aria_esi/mcp/dispatchers/killmails.py`, `.claude/skills/sec-status/`, `.claude/skills/agents-research/`, `dev/scripts/exercise-runner.py`
**Related:** `dev/reviews/exercise-outputs/20260310-232643/REPORT.md`, `dev/reviews/exercise-outputs/20260310-232643/RECOMMENDATIONS.md`, `EXERCISE_SKILL_ENFORCEMENT_PROPOSAL.md`

---

## Executive Summary

The 20260310-232643 exercise run (25 queries across 15 ESI:LOW skills, 100% completion, 84% Good) represents a significant improvement over the previous run (20260310-185149) where the Skill tool was never invoked. This run achieved 72% skill invocation (18/25). The enforcement hook from F1 of `EXERCISE_SKILL_ENFORCEMENT_PROPOSAL.md` is working. The remaining issues fall into three categories:

1. **Two P0 code bugs** — contracts MCP still fails (persists from prior run), sec-status has no data source
2. **Residual skill bypass** — 5 exercises bypass the Skill tool despite the enforcement hook
3. **Data-layer friction** — standings CLI schema is opaque, killmails ESI fallback ignores character context

This proposal covers six fixes. Three are corrections to the RECOMMENDATIONS.md analysis where deeper investigation revealed different root causes than initially reported.

| # | Fix | Layer | Severity | Effort |
|---|-----|-------|----------|--------|
| F1 | Diagnose and fix contracts MCP failure | MCP dispatcher + ESI | P0 | Medium |
| F2 | Add sec-status data source to pilot dispatcher | MCP dispatcher + skill | P0 | Low |
| F3 | Strengthen skill invocation for tactical skills | Skill definitions + runner | P1 | Low |
| F4 | Pass character_id through killmails ESI fallback | MCP dispatcher | P1 | Low |
| F5 | Document standings CLI output schema in skills | Skill definitions | P2 | Trivial |
| F6 | Expand exercise runner to ESI:NONE category | Exercise runner | P2 | Low |

### Corrections to RECOMMENDATIONS.md

During proposal development, source-level investigation revealed that two RECOMMENDATIONS.md diagnoses were incorrect:

| Recommendation | Claimed Root Cause | Actual Root Cause |
|---|---|---|
| R1 (contracts) | "Parameter bleeding — all 16 params passed to validation" | Validation passes correctly. All non-contract params are None or match defaults. The error originates in `_contracts()` or the ESI client, not validation. |
| R5 (standings) | "CLI output uses opaque `from_id` without entity names" | CLI output includes a `name` field with resolved names (e.g., `"name": "CreoDron"`). The model assumed `.corporation_name` which doesn't exist, then spent 7 calls discovering the correct field `.name`. |

---

## F1: Diagnose and Fix Contracts MCP Failure

### Problem

All MCP calls to `pilot(action="contracts")` fail with `"Error executing tool pilot: validation failed"`. This persists from the 20260310-185149 run. CLI fallback (`uv run aria-esi contracts`) works correctly every time.

### Evidence

From `13-contracts-q1.tools.json`:
- `{"action": "contracts", "status_filter": "active"}` → `"Error executing tool pilot: validation failed"`
- `{"action": "contracts"}` → `"Error executing tool pilot: validation failed"`

Both calls include only valid parameters (or no parameters), so the parameter validation framework is not the cause.

### Root Cause Analysis

The RECOMMENDATIONS.md attributed this to "parameter bleeding" where all 16 function parameters are passed to `validate_action_params()`. This diagnosis is **incorrect**. Source analysis shows:

1. **Validation passes.** `PILOT_ACTION_PARAMS["contracts"]` accepts `{"status_filter", "type_filter", "issued", "received", "limit"}`. All other params in the unified signature either:
   - Are `None` (skipped by validation at `validation.py:379`)
   - Match their defaults in `get_default_values("pilot")` (skipped at `validation.py:383`)

   A bare `{"action": "contracts"}` call would produce zero validation warnings.

2. **The error message `"validation failed"` does not originate from `validate_action_params()`.** That function returns a list of warning strings or raises `InvalidParameterError` (with `strict=True`, which is not used by the pilot dispatcher). The error wrapping format `"Error executing tool {name}: {message}"` comes from FastMCP's `ToolError` handler in `tools/base.py`.

3. **Other pilot actions work.** `fittings_list`, `fittings_detail`, `lp_balance`, `lp_offers`, `mining_ledger`, `mail_list` all succeed in the same run with the same function signature and validation path.

4. **Diagnostic logging was added** (pilot.py:222-224, from the prior proposal) but hasn't been exercised in a debug run.

The error is in `_contracts()` (pilot.py:649-728) or below — likely in:
- `get_authenticated_async_esi_client()` if the contracts scope check fails differently than expected
- `client.get_safe("/characters/{char_id}/contracts/", auth=True)` if the ESI endpoint returns an unexpected structure
- The `has_scope()` check at pilot.py:663 if it raises instead of returning False

### Proposed Fix

**Phase 1: Reproduce and diagnose**

Run a targeted debug exercise to capture the full exception traceback:

```bash
ARIA_LOG_LEVEL=DEBUG uv run python dev/scripts/exercise-runner.py \
  --explicit --skills contracts --filter LOW 2>&1 | tee /tmp/contracts-debug.log
```

The diagnostic `logger.exception()` at pilot.py:222-224 will capture the traceback. If the exception occurs before entering `_contracts()` (e.g., in FastMCP parameter marshalling), run a direct MCP client test:

```bash
uv run python -c "
import asyncio
from aria_esi.mcp.dispatchers.pilot import _contracts
asyncio.run(_contracts(status_filter='active', type_filter=None, issued=True, received=True, limit=50))
"
```

**Phase 2: Fix** — Apply targeted fix based on Phase 1 findings. Most likely scenarios:

| Scenario | Fix |
|---|---|
| ESI scope `has_scope()` raises an exception | Guard with try/except, return scope error dict |
| `get_authenticated_async_esi_client()` fails when called from contracts | Check credential state; may need scope refresh |
| FastMCP pydantic validation rejects parameter types | Fix type annotations on `_contracts()` parameters |
| ESI endpoint returns error structure parsed as validation failure | Add response type checking before processing |

**Phase 3: Validate** — Re-run exercises 13-14 and confirm MCP calls succeed.

### Scope

- `src/aria_esi/mcp/dispatchers/pilot.py` — diagnostic run (Phase 1), targeted fix (Phase 2)
- Potentially `src/aria_esi/store/esi_client.py` if ESI layer is the source

---

## F2: Add Security Status Data Source

### Problem

The `/sec-status` skill's core function — querying the pilot's current security status — doesn't work. The model correctly invokes the skill and reads `reference/mechanics/security_status.json`, but cannot fetch the pilot's actual sec status value. It asks the user to provide it manually, defeating the skill's purpose.

### Evidence

From `01-sec-status-q1.tools.json`: only 2 tool calls — `Skill("sec-status")` and `Read(security_status.json)`. No MCP or CLI call to fetch pilot data. The response says "The available tools don't include direct security status querying."

From `sec-status/SKILL.md` (line 41): the flow says "Get current sec status from ESI (or ask pilot if unavailable)." The skill lists `mcp__aria-universe__pilot` in `allowed-tools`, but the pilot dispatcher's `PilotAction` literal has no `sec_status` or `character_sheet` action.

### Root Cause

The pilot dispatcher exposes 8 actions (`mail_list`, `mail_read`, `mining_ledger`, `contracts`, `fittings_list`, `fittings_detail`, `lp_balance`, `lp_offers`). None return security status. The ESI endpoint that provides security status is `GET /characters/{character_id}/` which returns a `security_status` float field — but no dispatcher action exposes it.

The skill's ESI failure handling clause ("ask pilot if unavailable") triggers because the model correctly determines it has no tool path to the data.

### Proposed Fix

**Option A (recommended): CLI-based approach in the skill**

The fastest path is to document the existing CLI command in the skill definition. The `uv run aria-esi pilot` command returns character data including security status.

**File:** `.claude/skills/sec-status/SKILL.md`, update the execution flow:

```markdown
## Execution Flow

1. **Get current sec status** via CLI:
   ```bash
   uv run aria-esi pilot
   ```
   Extract the `security_status` field from the response.
   If ESI is unavailable or the field is missing, ask the pilot for their
   current security status and note "Based on self-reported value."
```

This is a skill-prompt-only change — no code modification needed.

**Option B (future): Add pilot dispatcher action**

Add a `character_info` action to the pilot dispatcher that fetches `GET /characters/{character_id}/` and returns:
- `security_status` (float)
- `name` (string)
- `corporation_id` (int)
- `birthday` (string)

This is a cleaner long-term solution but requires code changes + tests. Implement this when other skills also need character sheet data.

### Verification

Check whether the `pilot` CLI subcommand actually returns security status:

```bash
uv run aria-esi pilot | jq '.security_status'
```

If it doesn't, Option A requires adding `security_status` to the CLI output first. In that case, prioritize Option B.

### Risk

| Risk | Impact | Mitigation |
|---|---|---|
| CLI `pilot` command doesn't include `security_status` | Medium | Verify before implementing; fall back to Option B |
| Model fails to parse sec status from CLI output | Low | The CLI returns structured JSON; model reliably parses similar outputs from other exercises |

### Scope

- `.claude/skills/sec-status/SKILL.md` — update execution flow (Option A)
- Or `src/aria_esi/mcp/dispatchers/pilot.py` + tests (Option B)

---

## F3: Strengthen Skill Invocation for Tactical Skills

### Problem

Five exercises bypassed the Skill tool despite the enforcement hook from the prior proposal: escape-route (2x), fitting (1x), skillplan (2x). These skills have `injected_prerequisites` containing authoritative reference data (skill plans, ship efficacy rules, EFT format, drone stats) that is embedded into the skill prompt via `!`command`` syntax at load time. Bypassing the Skill tool means this injected content is never loaded, risking confabulation.

> **Note:** These skills use `injected_prerequisites` (pre-loaded via shell injection), not `prerequisite_files` (read at runtime). Both mechanisms gate authoritative data behind the Skill tool — the distinction is *when* content is resolved, not *whether* bypassing the skill loses it.

### Evidence

From MANIFEST.md: exercises 02, 03, 04, 07, 08 flagged `no-skill`. All five went directly to MCP tools or CLI without invoking the Skill tool.

The skill definitions for all three skills have strong descriptions and trigger patterns that should match the exercise queries:
- `escape-route`: triggers on "escape route", "get me out", "nearest safe"
- `skillplan`: triggers on "what skills for [ship]", "skills needed for [item]"
- `fitting`: triggers on "fit my [ship]", "export fitting", "EFT format"

The issue is NOT weak skill metadata.

### Root Cause

Investigation reveals a pattern: the 5 bypassed exercises all involve skills with high MCP tool affinity. The model sees that MCP tools directly answer the query (universe for routes, skills/sde for skill plans, pilot/fitting for fits) and calls them without the skill invocation step. The enforcement hook (`UserPromptSubmit`) injects context telling the model to invoke the skill first, but for these tool-direct queries, the model treats the MCP path as more efficient.

The exercises that DO invoke skills correctly (assets, contracts, fittings, mail, mining, orders, etc.) tend to have skill prompts that add substantial workflow logic beyond a single tool call. The bypassed skills appear "tool-shaped" to the model — their primary value is reference data loading, which the model doesn't perceive as necessary.

### Proposed Fix

**Two complementary approaches:**

**A. Add skill-invocation validation to the exercise runner (deterministic)**

Per the [Claude Code hooks reference](https://code.claude.com/docs/en/hooks-reference), a `PreToolUse` hook can block tool calls before they execute. Add a hook that blocks MCP calls when the Skill tool hasn't been invoked yet in the current turn.

**File:** `dev/scripts/hooks/skill-gate.sh`

```bash
#!/bin/bash
# PreToolUse hook: block MCP tool calls when Skill tool hasn't been invoked.
# Uses CLAUDE_ENV_FILE to track whether the Skill tool was called.
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

# Allow Skill tool calls and non-MCP tools
if [[ "$TOOL_NAME" == "Skill" ]]; then
  echo "SKILL_INVOKED=true" >> "$CLAUDE_ENV_FILE"
  exit 0
fi

# Allow non-MCP tools (Read, Bash, etc.)
if [[ "$TOOL_NAME" != mcp__* ]]; then
  exit 0
fi

# Block MCP calls if Skill hasn't been invoked
if [[ "${SKILL_INVOKED:-}" != "true" ]]; then
  echo "BLOCKED: Invoke the relevant skill via the Skill tool before calling MCP tools directly. Skills load prerequisite reference data that prevents confabulation." >&2
  exit 2
fi

exit 0
```

This uses `CLAUDE_ENV_FILE` to persist state across hook invocations within a turn, as documented in the [hooks reference](https://code.claude.com/docs/en/hooks-reference#persist-environment-variables). The hook fires on every `PreToolUse` event. Once the Skill tool is called, `SKILL_INVOKED=true` is written to the env file and subsequent MCP calls proceed.

**Important:** This hook should ONLY be active during exercise runs — not in normal interactive sessions where the user may legitimately bypass skills. Register it via the exercise runner's temporary `.claude/settings.local.json`.

**B. Add "invoke me" guidance to tactical skill descriptions**

For the three affected skills, append explicit guidance that reinforces the skill framework's role:

```yaml
# In SKILL.md frontmatter description:
description: >
  ARIA ship fitting assistance for Eve Online.
  IMPORTANT: Always invoke this skill before calling fitting or pilot MCP tools.
  This skill loads reference data (EFT format, module names, drone stats) required
  for accurate responses.
```

This approach works within the existing skill description mechanism — per the [skills documentation](https://code.claude.com/docs/en/skills), "descriptions load at session start so Claude knows what's available" and "Claude uses this to decide when to apply the skill."

### Risk

| Risk | Impact | Mitigation |
|---|---|---|
| PreToolUse hook blocks legitimate MCP calls in non-exercise contexts | High | Hook is exercise-runner-scoped only (temporary settings.local.json) |
| Model works around the block by calling CLI instead of MCP | Medium | Monitor tool traces for Bash calls to `aria-esi` as first call |
| `CLAUDE_ENV_FILE` unavailable | Low | Check for env var existence before writing; fail open (allow call) |

### Scope

- `dev/scripts/hooks/skill-gate.sh` — new hook script
- `dev/scripts/exercise-runner.py` — register PreToolUse hook in exercise runs
- `.claude/skills/escape-route/SKILL.md` — add invocation guidance to description
- `.claude/skills/skillplan/SKILL.md` — same
- `.claude/skills/fitting/SKILL.md` — same

---

## F4: Fix Killmails ESI Fallback Character Context

### Problem

The killmails dispatcher's ESI fallback path (`_handle_esi_fallback`) does not accept a `character_id` parameter and hardcodes `scope: "character"` in the response, even though it inherently returns the authenticated character's kills via `_fetch_esi_killmail_refs()`.

The store-backed path was already fixed (scope metadata added at killmails.py:313-330, from prior proposal F4). The ESI fallback has two issues:

1. If a caller passes `character_id`, it's silently dropped at line 179 — the fallback function signature doesn't include it
2. The fallback response claims `scope: "character"` which is correct (ESI returns auth'd char's kills) but provides no `scope_note` guidance, unlike the store path

### Evidence

From the store path (lines 313-330): correctly sets `scope = "character" if character_id else "global"` and adds `scope_note` for global queries.

From the fallback path (lines 615-676): function signature `_handle_esi_fallback(hours, limit)` — no `character_id`. Response hardcodes `scope: "character"` at line 671.

The exercise run's killmails issue (#05, #06) was caused by the STORE path returning global data without `character_id` — which is now handled by the scope metadata. This fix addresses the remaining gap in the fallback path.

### Proposed Fix

**File:** `src/aria_esi/mcp/dispatchers/killmails.py`

**Step 1:** Add `character_id` to the fallback call site (line 179):

```python
if action in ("query", "recent"):
    return await _handle_esi_fallback(
        hours=hours,
        limit=limit,
        character_id=character_id,
    )
```

**Step 2:** Update the fallback function signature (line 615):

```python
async def _handle_esi_fallback(
    hours: int,
    limit: int,
    character_id: int | None = None,
) -> dict:
```

**Step 3:** Add scope handling to the fallback response (after line 670):

```python
result: dict[str, Any] = {
    "kills": filtered,
    "count": len(filtered),
    "next_cursor": None,
    "query": {
        "systems": None,
        "hours": hours,
        "min_value": None,
        "limit": limit,
    },
    "source": "esi_fallback",
    "scope": "character",
    "scope_note": (
        "ESI fallback returns authenticated character's killmails only. "
        "The character_id parameter has no effect in this mode."
    ) if character_id and character_id != char_id else None,
}
```

Note: ESI fallback always returns the authenticated character's kills (via OAuth token). If a different `character_id` is requested, the response should note this limitation rather than silently ignoring it.

### Test

Add to `tests/mcp/dispatchers/test_killmails_actions.py`:
- `test_esi_fallback_scope_metadata`: verify fallback includes `scope: "character"`
- `test_esi_fallback_mismatched_character_id`: verify `scope_note` appears when `character_id` doesn't match authenticated char

### Scope

- `src/aria_esi/mcp/dispatchers/killmails.py` — 3 changes (call site, function signature, response metadata)
- `tests/mcp/dispatchers/test_killmails_actions.py` — 2 new test cases

---

## F5: Document Standings CLI Schema in Skills

### Problem

Exercise #23 (agents-research q2) used 10 tool calls — 7 of them trial-and-error Bash commands — to look up CreoDron standing. The model assumed the standings CLI output had a `corporation_name` field; it doesn't. The actual field is `name`.

### Evidence

From `23-agents-research-q2.tools.json`:

| Call | Command | Result |
|------|---------|--------|
| 2 | `jq '.standings[] \| select(.corporation_name == "CreoDron")'` | Empty (field doesn't exist) |
| 3 | `jq '.standings[] \| .corporation_name' \| sort` | 64 nulls |
| 4 | `jq '.standings[0]'` | `{"from_id": 3009895, "from_type": "agent", "name": "Agent 3009895", "standing": 7.99}` |
| 5-9 | Discovery of SDE corporation_info, cross-reference | Eventually found `from_id == 1000101` |

The standings CLI output includes `from_id`, `from_type`, `name`, and `standing`. The `name` field IS present and correctly resolved. The model simply assumed the wrong field name on its first attempt.

### Proposed Fix

Add CLI output schema documentation to the two skills that use standings data.

**File:** `.claude/skills/agents-research/SKILL.md`

Add after the execution flow section:

```markdown
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

Agent standing requirements: L1=any, L2=1.0, L3=3.0, L4=5.0, L5=7.0
```

**File:** `.claude/skills/standings/SKILL.md` — add the same reference section.

### Why Not Code Changes

The CLI output already includes resolved names. The problem was entirely model-side: it guessed `corporation_name` instead of checking the actual schema. Documenting the schema in skills that consume standings data is the minimal, correct fix. A `pilot(action="standings")` MCP action would be cleaner long-term but is overengineered for this issue.

### Scope

- `.claude/skills/agents-research/SKILL.md` — add standings CLI reference
- `.claude/skills/standings/SKILL.md` — add standings CLI reference

---

## F6: Expand Exercise Runner to ESI:NONE Skills

### Problem

This run covered 15 ESI:LOW skills (25 queries). The ESI:NONE category contains 24 skills with 42 queries, including the skills most dependent on `prerequisite_files` for correctness: `abyssal`, `mission-brief`, `route`, `threat-assessment`, `price`, `reactions`, `exploration`, `pi`.

These skills are where skill bypass would cause the most confabulation — their prerequisite files contain EVE game data (NPC damage types, abyssal weather effects, reaction recipes, fuel block factions) that changes across patches and cannot be reliably stated from training data alone.

### Proposed Fix

No code changes needed. This is an operational action:

1. **Run ESI:NONE batch** after F3 lands (skill enforcement improvements):
   ```bash
   uv run python dev/scripts/exercise-runner.py --explicit --filter NONE
   ```

2. **Key metrics to watch:**
   - Skill invocation rate (target: >90% with F3 enforcement hook)
   - `prerequisite_files` read rate (every declared prerequisite should appear in tool trace)
   - Confabulation incidents in EVE game data (incorrect damage types, wrong fuel block recipes, etc.)

3. **High-value exercises to monitor:**
   - `mission-brief` — relies heavily on `reference/missions/` cache and NPC damage data
   - `reactions` — fuel block recipes change; prerequisite data is the only reliable source
   - `abyssal` — weather effects, tiers, and NPC types from reference files
   - `route` / `threat-assessment` — security status thresholds from reference data

### Scope

- No code changes
- Operational: 1 exercise run + review

---

## Implementation Plan

F1 and F2 are P0 blockers. F3 and F4 are independent P1 improvements. F5 is trivial. F6 depends on F3.

```
Phase 1 — Immediate (P0):
  F1: Diagnostic run for contracts bug             [1 debug run]
  F2: sec-status skill update (Option A)           [Trivial]

Phase 2 — After F1 diagnosis:
  F1: Targeted fix for contracts MCP failure       [Depends on Phase 1]
  F3: Skill enforcement hook + description updates [Low effort]
  F4: Killmails ESI fallback character_id          [Low effort]

Phase 3 — Polish:
  F5: Standings schema in skill definitions        [Trivial]

Phase 4 — Validation:
  F6: ESI:NONE exercise run                        [After F3 lands]
  Re-run ESI:LOW exercises                         [After F1, F2, F3 land]
```

**Recommended execution order:** F2 → F1 (Phase 1) → F5 → F3 → F4 → F1 (Phase 2) → F6

F2 is the quickest P0 fix (skill-prompt edit). F1 Phase 1 is a diagnostic run. F5 is trivial. F3 and F4 are independent. F1 Phase 2 depends on diagnostic results.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| F1: Root cause is in ESI auth layer, not the dispatcher | Medium | Diagnostic logging at pilot.py:222-224 captures full traceback |
| F2: CLI `pilot` command may not include `security_status` | Medium | Verify before implementing; fall back to new MCP action (Option B) |
| F3: PreToolUse hook too aggressive in exercise context | Medium | Hook only blocks MCP calls; allows Read, Bash, Grep. Only active during exercise runs |
| F3: Model works around PreToolUse block by using CLI | Low | Monitor for CLI-first patterns in tool traces |
| F4: `scope_note` text consumes context tokens | Negligible | ~25 tokens; only appears in fallback with mismatched character_id |
| F6: ESI:NONE run reveals many new issues | Expected | This is the purpose — better to find confabulation in exercises than in user sessions |

---

## Out of Scope

- **Full pilot dispatcher restructuring into per-action functions**: architecturally cleaner than the unified signature but disproportionate effort for the current bugs.
- **MCP `pilot(action="standings")` action**: the CLI already returns resolved names. Skill documentation (F5) is sufficient. Revisit if multiple skills need standings via MCP.
- **MCP `pilot(action="sec_status")` action**: Option B in F2. Implement when other skills also need character sheet fields.
- **Automated quality gate enforcement** (blocking exercise runs on quality failures): proposed in prior proposal F3 as advisory flags. Quality flags are now appearing in MANIFEST.md. Enforcement should wait until the flag detection is tuned.
- **CLI invocation standardization** (RECOMMENDATIONS.md R7): low priority; the model already uses `uv run aria-esi` correctly in 23/25 exercises.

---

## Relationship to Prior Proposals

| Prior Proposal Item | Status | This Proposal |
|---|---|---|
| F1: Skill enforcement hook | **Implemented** — 72% invocation rate (up from 0%) | F3 strengthens for remaining 28% |
| F2: Contracts MCP failure | **Unresolved** — diagnostic logging added, bug persists | F1 continues investigation with corrected root cause analysis |
| F3: Quality gates in runner | **Partially implemented** — MANIFEST shows quality flags | Not revisited (working adequately) |
| F4: Killmail scope metadata | **Implemented** — store path has scope + scope_note | F4 extends to ESI fallback path |
| F5: Pilot validation schema | **Implemented** — PILOT_ACTION_PARAMS in validation.py | Not revisited (working correctly) |

---

## Proposal Validation Record

**Validated:** 2026-03-11
**Method:** Source code analysis against proposal claims + adherence check against Claude Code documentation ([SKILLSSKILLS/docs](../../../SKILLSSKILLS/docs/))

### Findings

| Fix | Verdict | Details |
|-----|---------|---------|
| F1 | **Verified** | All claims accurate. Validation does skip None/default params (validation.py:379-383). Error format matches FastMCP, not `validate_action_params()`. Diagnostic logging confirmed at pilot.py:222-224. Correction to RECOMMENDATIONS.md R1 is warranted. |
| F2 | **Verified** | `PilotAction` literal has exactly 8 actions, no `sec_status`. SKILL.md line 41 matches quoted text. CLI `aria-esi pilot` returns `security_status` field (commands/pilot.py:76-82). Option A is viable. |
| F3 | **Verified with correction** | Hook mechanism is sound per [hooks-reference](https://code.claude.com/docs/en/hooks): `CLAUDE_ENV_FILE` persists env vars across hooks (hooks-reference §Persist environment variables), exit code 2 blocks PreToolUse (hooks-reference §Exit code 2 behavior per event). Session-scope concern does not apply — exercise runner spawns separate `claude -p` subprocesses per exercise. **Corrected:** proposal originally said `prerequisite_files` but the three skills use `injected_prerequisites` (content injected via `!`command`` at skill load time). Same risk profile — bypassing Skill = bypassing the injected data — but the terminology was wrong. |
| F4 | **Verified** | `_handle_esi_fallback` signature confirmed as `(hours, limit)` with no `character_id`. Call site confirmed at line 179. Store path scope metadata at lines 313-330 confirmed. |
| F5 | **Verified** | Standings CLI output includes `from_id`, `from_type`, `name`, `standing` (commands/character.py:197-203). Names are resolved via faction/corp ESI lookups. Neither `agents-research/SKILL.md` nor `standings/SKILL.md` currently documents this schema. |
| F6 | **N/A** | Operational action, no claims to verify. |

### SKILLSSKILLS Documentation Adherence

| Proposal Claim | SKILLSSKILLS Reference | Status |
|---|---|---|
| `CLAUDE_ENV_FILE` persists across hooks | hooks-reference.md §Persist environment variables (lines 414-423) | Correct |
| PreToolUse exit 2 blocks tool calls | hooks-reference.md §Exit code 2 behavior per event (line 371) | Correct |
| Skill descriptions used for auto-invocation | skills.md line 186: "Claude uses this to decide when to apply the skill" | Correct |
| Hook in `.claude/settings.local.json` is project-scoped, not committed | hooks-reference.md §Hook locations (line 99) | Correct |
| `disable-model-invocation` prevents auto-load | skills.md line 274: "Description not in context" | Not used (proposal uses description guidance instead) |

---

## Outstanding Items

Items below track implementation progress. Updated as work lands.

### Completed

| ID | Item | Fix | Completed | Notes |
|----|------|-----|-----------|-------|
| O1 | Update sec-status skill with CLI path | F2 | 2026-03-10 | Added `uv run aria-esi pilot` CLI path to `sec-status/SKILL.md` execution flow |
| O2 | Add standings CLI schema to agents-research + standings skills | F5 | 2026-03-10 | Schema reference added to both `agents-research/SKILL.md` and `standings/SKILL.md` |
| O3 | Create `skill-gate.sh` hook for exercise runs | F3 | 2026-03-11 | `dev/scripts/hooks/skill-gate.sh` created; registered as `PreToolUse` hook in exercise-runner.py with cleanup on exit |
| O4 | Add invocation guidance to escape-route, skillplan, fitting descriptions | F3 | 2026-03-11 | Appended `IMPORTANT: Always invoke this skill before calling ... MCP tools` to `description` in both SKILL.md frontmatter and `_index.json` for all three skills |
| O5 | Pass `character_id` through killmails ESI fallback + add scope_note | F4 | 2026-03-11 | Added `character_id` param to `_handle_esi_fallback()`, pass-through from call site, `scope_note` on mismatch. 2 new tests in `TestScopeMetadata` (40/40 pass) |

### Requires Investigation

| ID | Item | Fix | Blocker | Next Step |
|----|------|-----|---------|-----------|
| O6 | Diagnose contracts MCP failure root cause | F1 Phase 1 | Unknown exception source | Run `ARIA_LOG_LEVEL=DEBUG` exercise targeting contracts; capture traceback from pilot.py:222-224 |
| O7 | Fix contracts MCP failure | F1 Phase 2 | Depends on O6 diagnosis | Apply targeted fix per scenario table in F1 |

### Validation Runs (Post-Fix)

| ID | Item | Fix | Dependency | Status |
|----|------|-----|------------|--------|
| O8 | Re-run ESI:LOW exercises after O1, O3, O6/O7 land | F1/F2/F3 | O1 + O3 + O7 | Blocked on O6/O7 (contracts). O1+O3 done. |
| O9 | Run ESI:NONE exercise batch | F6 | O3 (skill enforcement hook) | Unblocked — O3 complete. Ready to run. |

### Execution Status

```
O1 (trivial)  ✓ done
O2 (trivial)  ✓ done
O4 (trivial)  ✓ done
O5 (low)      ✓ done
O3 (low)      ✓ done
O6 (diagnostic) — next: requires live debug run
O7 (depends on O6) — blocked
O8 (validation) — blocked on O7
O9 (validation) — ready to run
```
