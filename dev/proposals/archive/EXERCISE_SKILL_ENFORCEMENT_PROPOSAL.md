# Exercise Run Skill Enforcement & MCP Fixes

**Status:** Proposed
**Date:** 2026-03-10
**Owner:** ARIA Development
**Scope:** `dev/scripts/`, `src/aria_esi/mcp/dispatchers/pilot.py`, `src/aria_esi/mcp/dispatchers/killmails.py`, `src/aria_esi/mcp/validation.py`
**Related:** `dev/reviews/exercise-outputs/20260310-185149/REPORT.md`, `dev/reviews/exercise-outputs/20260310-185149/RECOMMENDATIONS.md`

---

## Executive Summary

The 20260310-185149 exercise run (25 queries, 100% completion, 18 Good / 6 Fair / 1 Poor) surfaced a critical systemic issue: the Skill tool was never invoked in any of the 25 exercises despite explicit `/<skill>` prefixes. This means the entire skill loading chain — SKILL.md, prerequisite files, persona overlays — was bypassed, removing the primary guardrail against confabulation. Two additional code-level bugs were confirmed: the contracts MCP dispatcher fails all validation, and the killmails store path returns global data without scope metadata.

This proposal addresses five fixes spanning the exercise runner, MCP dispatchers, and validation layer.

| # | Fix | Layer | Severity | Effort |
|---|-----|-------|----------|--------|
| F1 | Enforce skill invocation via UserPromptSubmit hook | Exercise runner | Critical | Low |
| F2 | Fix contracts MCP dispatcher validation failure | MCP dispatcher | High | Medium |
| F3 | Add post-run quality gates to exercise runner | Exercise runner | High | Medium |
| F4 | Add data scope metadata to killmail store responses | MCP dispatcher | Medium (High ROI) | Low |
| F5 | Add PILOT_ACTION_PARAMS to validation framework | MCP validation | Medium (High ROI) | Low |

---

## F1: Enforce Skill Invocation via UserPromptSubmit Hook

### Problem

The exercise runner uses `--append-system-prompt` to instruct the model to invoke the Skill tool when it sees a `/<skill>` prefix. This instruction is appended after the full system prompt (CLAUDE.md, skill descriptions, MCP tool schemas) and is consistently ignored. The model sees MCP tools it can call directly and does so, treating the `/<skill>` prefix as a topic hint rather than a tool invocation command.

The result: 0/25 exercises invoked the Skill tool. No SKILL.md files loaded, no prerequisite files read, no persona overlays checked. Every response was generated without the confabulation guardrails that skills provide.

### Evidence

From all 25 tools.json files: zero `Skill` tool calls. The `Skill` tool IS in the `ALLOWED_TOOLS` list (`exercise-runner.py:52`). The `--append-system-prompt` instruction (`exercise-runner.py:288-291`) was correctly passed to `claude -p`.

### Root Cause

Per Claude Code's documentation on skills: "descriptions load at session start so Claude knows what's available, but full skill content only loads when invoked." In `-p` (non-interactive) mode, the model has access to both the Skill tool and MCP tools. When it sees `/<skill> query`, it recognizes the domain and calls MCP tools directly — a shorter path than invoking the Skill tool, waiting for SKILL.md to load, and then calling MCP tools.

The `--append-system-prompt` text competes with hundreds of lines of existing system context. It lacks the structural authority to override the model's tool-calling preferences.

### Proposed Fix

Replace the `--append-system-prompt` approach with a **`UserPromptSubmit` hook** that injects mandatory context alongside the prompt.

Per Claude Code's hooks documentation: "`UserPromptSubmit` fires when you submit a prompt, before Claude processes it" and supports `additionalContext` which adds text alongside the prompt and `transformedPrompt` which replaces the prompt entirely.

**Important:** Per the hooks docs, `PermissionRequest` hooks do not fire in non-interactive mode (`-p`), but `UserPromptSubmit` does fire since it's a prompt-level event that runs before tool selection.

**New file:** `dev/scripts/hooks/skill-enforcer.sh`

```bash
#!/bin/bash
# Enforce Skill tool invocation for explicit /<skill> queries in exercise runs.
#
# UserPromptSubmit hook — fires before Claude processes the prompt.
# Detects /<skill> prefix and injects additionalContext requiring
# the model to invoke the Skill tool first.

INPUT=$(cat)
PROMPT=$(echo "$INPUT" | jq -r '.prompt // empty')

# Match /<skill-name> at start of prompt (lowercase, hyphens, digits)
if [[ "$PROMPT" =~ ^/([a-z][a-z0-9-]*)(\ |$) ]]; then
  SKILL="${BASH_REMATCH[1]}"
  ARGS="${PROMPT#/$SKILL}"
  ARGS="${ARGS# }"

  # Emit additionalContext that will appear alongside the prompt
  jq -n --arg skill "$SKILL" --arg args "$ARGS" '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: ("MANDATORY REQUIREMENT: You MUST use the Skill tool to invoke the skill named \"\(.skill)\" BEFORE using any other tool. The skill will load prerequisite files and reference data required for an accurate response. Pass the following as arguments to the Skill tool: \(.args)\n\nDo NOT skip this step. Do NOT call MCP tools or CLI commands until the Skill tool has been invoked and its content loaded into context.")
    }
  }'
fi

exit 0
```

**Integration:** The exercise runner registers this hook via a temporary settings file before launching `claude -p`:

**File:** `dev/scripts/exercise-runner.py` — add hook setup in `run_query()`:

```python
# Create temporary hooks configuration for exercise runs
hooks_config = {
    "hooks": {
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": str(HOOKS_DIR / "skill-enforcer.sh"),
                    }
                ]
            }
        ]
    }
}
```

The hooks config is written to a temporary `.claude/settings.local.json` during exercise runs and cleaned up afterward. This is the correct hook location per the docs: "Single project, No, gitignored."

**Why `additionalContext` over `transformedPrompt`:** The `additionalContext` field adds context without altering the original prompt, so the model still sees the user's query verbatim. `transformedPrompt` would replace the prompt entirely, which could confuse the model about what the user actually asked.

### Test

1. Run a single exercise with the hook active: `uv run python dev/scripts/exercise-runner.py --explicit --skills fittings --filter LOW`
2. Verify `Skill` appears in the tools.json output
3. Verify the SKILL.md file path appears in `Read` tool calls
4. Run the full ESI:LOW batch and compare Skill tool invocation rate

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hook adds latency | Negligible | `jq` on small JSON input completes in <10ms |
| Model ignores additionalContext | Medium | If this occurs, escalate to `transformedPrompt` which is more forceful |
| Hook regex mismatches skill names | Low | Regex matches the same pattern as the exercise runner's prefix logic |
| Settings conflict with existing hooks | Low | Uses `.claude/settings.local.json` which is gitignored and exercise-run scoped; runner saves/restores the file |

---

## F2: Fix Contracts MCP Dispatcher Validation Failure

### Problem

All MCP calls to `pilot(action="contracts")` fail with "validation failed." Five calls across exercises 13-14 failed with various parameter combinations, including a bare `{"action": "contracts"}` call. The CLI fallback (`aria-esi contracts`) works correctly.

Other pilot actions work fine in the same run: `fittings_list`, `fittings_detail`, `lp_balance`, `lp_offers`, `mining_ledger`, `mail_list` all succeed. The issue is specific to the `contracts` action path.

### Evidence

From `13-contracts-q1.tools.json`:
- `{"action": "contracts", "status_filter": "active"}` → "Error executing tool pilot: validation failed"
- `{"action": "contracts"}` → "Error executing tool pilot: validation failed"

From `14-contracts-q2.tools.json`:
- Three additional failed calls with various parameter combinations

### Root Cause Analysis

The error message format — `Error executing tool {name}: {e}` — originates from FastMCP's `tools/base.py:117` which catches all exceptions during tool execution and wraps them in `ToolError`. The "validation failed" substring is the exception message from the caught exception.

The execution flow for a pilot MCP call:
1. FastMCP validates parameters via pydantic (`func_metadata.py:87`: `self.arg_model.model_validate(...)`)
2. If valid, calls the function → enters `@log_context` wrapper → enters `pilot()`
3. Inside `pilot()`, `check_capability("pilot", action)` runs policy checks
4. Then the action-specific handler runs (e.g., `_contracts()`)

Since `{"action": "contracts"}` with no extra parameters fails, and `{"action": "fittings_list"}` with no extra parameters succeeds, the issue is NOT in FastMCP's pydantic schema (both would use the same generated model from the same function signature).

The issue is likely in **step 3 or 4** — something specific to the contracts action path that raises an exception whose message contains "validation." Candidates:
- The ESI scope check at `pilot.py:628-634`: `has_scope("esi-contracts.read_character_contracts.v1")` — but this returns a dict with `error: "scope_not_authorized"`, it doesn't raise
- The ESI client's `get_safe()` call for the contracts endpoint
- An authentication or credential validation step in the ESI client layer

**Investigation plan:**

```bash
# Step 1: Reproduce locally
uv run python -c "
import asyncio
from aria_esi.mcp.dispatchers.pilot import register_pilot_dispatcher
# ... minimal reproduction
"

# Step 2: Enable debug logging and run a single contracts call
ARIA_LOG_LEVEL=DEBUG uv run python dev/scripts/exercise-runner.py \
  --explicit --skills contracts --filter LOW

# Step 3: Check ESI scope availability
uv run aria-esi contracts --active 2>&1
```

### Proposed Fix

**Phase 1: Diagnose** — Add structured error logging to the pilot dispatcher's contracts path:

**File:** `src/aria_esi/mcp/dispatchers/pilot.py`, in the `contracts` case branch:

```python
case "contracts":
    try:
        return await _contracts(
            status_filter=status_filter,
            type_filter=type_filter,
            issued=issued,
            received=received,
            limit=limit,
        )
    except Exception as e:
        logger.exception("Contracts action failed: %s", e)
        raise
```

This will capture the full traceback in the MCP server log, revealing the exact line that raises "validation failed."

**Phase 2: Fix** — Apply the appropriate fix based on Phase 1 findings. Most likely fixes:

- If the ESI client raises a validation error for the contracts endpoint: fix the endpoint URL or scope handling
- If an authentication step fails: ensure the contracts scope is requested during OAuth setup
- If pydantic model validation inside `_contracts()` fails: fix the type annotation or default value

**Phase 3: Validate** — Re-run exercises 13-14 and verify MCP calls succeed.

### Scope

- `src/aria_esi/mcp/dispatchers/pilot.py` — diagnostic logging (Phase 1), targeted fix (Phase 2)
- Potentially `src/aria_esi/store/esi_client.py` if the ESI layer is the source

---

## F3: Post-Run Quality Gates for Exercise Runner

### Problem

The exercise runner reports 25/25 "ok" status with no quality differentiation. Exercise 05 (killmails q1) showed completely wrong data — global kills presented as pilot losses — but received "ok" status because it completed without errors. The MANIFEST provides no signal about response quality.

### Evidence

From MANIFEST.md: all 25 entries show `ok` status. The only differentiation is duration and line count. Neither metric captures data correctness, skill invocation, or MCP failures.

### Proposed Fix

Add automated quality checks that run after each exercise completes, using the tools.json and response .md files.

**File:** `dev/scripts/exercise-runner.py` — add `quality_check()` function:

```python
def quality_check(
    result: dict,
    tools_path: Path,
    output_path: Path,
    explicit: bool,
) -> list[str]:
    """
    Run post-exercise quality checks.

    Returns a list of quality flag strings (empty = all clear).
    """
    flags = []
    tools_data = json.loads(tools_path.read_text()) if tools_path.exists() else []
    output_text = output_path.read_text() if output_path.exists() else ""

    # 1. Skill tool invocation (explicit mode only)
    if explicit:
        skill_calls = [t for t in tools_data if t.get("tool") == "Skill"]
        if not skill_calls:
            flags.append("no-skill")

    # 2. MCP validation failures
    mcp_failures = [
        t for t in tools_data
        if t.get("tool", "").startswith("mcp__")
        and "validation failed" in str(t.get("result", "")).lower()
    ]
    if mcp_failures:
        flags.append(f"mcp-fail({len(mcp_failures)})")

    # 3. Brevity compliance (count non-header, non-trace content lines)
    content_lines = [
        line for line in output_text.split("\n")
        if line.strip()
        and not line.startswith("# ")
        and not line.startswith("---")
        and "Tool Trace" not in line
    ]
    if len(content_lines) > 40:  # generous threshold
        flags.append(f"brevity-{len(content_lines)}")

    # 4. Data scope warnings for pilot-specific queries
    skill = result.get("skill", "")
    query = result.get("query_text", "").lower()
    if ("my " in query or "my\n" in query) and skill == "killmails":
        recent_calls = [
            t for t in tools_data
            if t.get("tool") == "mcp__aria-universe__killmails"
            and t.get("input", {}).get("action") == "recent"
            and t.get("input", {}).get("character_id") is None
        ]
        if recent_calls:
            flags.append("global-data")

    return flags
```

**MANIFEST format update** — add a `Quality` column:

```
| # | Skill | Query | ESI | Status | Duration | Quality |
|---|-------|-------|-----|--------|----------|---------|
| 05 | killmails | Show my recent losses | LOW | ok | 17.1s | no-skill,global-data |
| 13 | contracts | Show me my active contracts | LOW | ok | 19.4s | no-skill,mcp-fail(2) |
| 18 | fittings | Show my saved fittings | LOW | ok | 11.2s | no-skill |
```

**Summary statistics** in MANIFEST footer:

```
Quality flags: 25 no-skill, 2 mcp-fail, 1 global-data, 3 brevity
```

### Scope

- `dev/scripts/exercise-runner.py` — add `quality_check()`, update `write_manifest()`, update result dict
- No test changes (exercise runner is a dev tool, not production code)

---

## F4: Add Data Scope Metadata to Killmail Store Responses

### Problem

The killmails MCP dispatcher's `recent` and `query` actions return data from the RedisQ store (a global kill feed) when the store is active, or from ESI (pilot-specific) when the store is down. The response includes a `source` field (`"store"` or `"esi_fallback"`) but no indication of whether the data is global or filtered to the authenticated pilot.

When the model calls `killmails(action="recent", limit=50)` for "show my recent losses," the store returns 50 random universe kills. Without scope metadata, the model has no signal that this data is global — especially when the Skill tool is bypassed and SKILL.md guidance isn't loaded.

### Evidence

From `05-killmails-q1.tools.json`: 50 kills returned with `system_id: null`, `victim_ship_type_id: null`, all within a few seconds of each other. The model presented these as "Available data from last hour (50 kills)" without caveat.

Note: The SKILL.md correctly maps "recent kills/losses" to `killmails(action="recent")` and documents how to use `character_id` for filtering. The real issue is the skill wasn't loaded. This fix is defense-in-depth.

### Proposed Fix

**File:** `src/aria_esi/mcp/dispatchers/killmails.py`

In `_handle_query()` (store path), add scope metadata to the response:

```python
# After line 320 (result dict construction)
result["scope"] = "character" if character_id else "global"
if not character_id:
    result["scope_note"] = (
        "Data from global killmail feed (all pilots). "
        "Pass character_id to filter to a specific pilot's kills."
    )
```

In `_handle_esi_fallback()` (ESI fallback path):

```python
result["scope"] = "character"
```

In `_handle_esi_history()`:

```python
result["scope"] = "character"
```

The `scope_note` field provides guidance that the model can use even without the SKILL.md loaded.

### Test

Add test cases in `tests/mcp/dispatchers/test_killmails.py`:
- `test_recent_store_global_scope`: verify `scope="global"` when no `character_id`
- `test_recent_store_character_scope`: verify `scope="character"` when `character_id` is set
- `test_esi_fallback_character_scope`: verify `scope="character"` in fallback path

### Scope

- `src/aria_esi/mcp/dispatchers/killmails.py` — add `scope` and `scope_note` fields to 3 response paths
- `tests/mcp/dispatchers/test_killmails.py` — 3 new test cases

---

## F5: Add PILOT_ACTION_PARAMS to Validation Framework

### Problem

The MCP parameter validation framework (`validation.py`) defines action-parameter schemas for universe, market, sde, skills, and fitting dispatchers — but not for the pilot dispatcher. The pilot dispatcher also does not call `validate_action_params()`, unlike all other dispatchers.

While this isn't the root cause of the contracts validation failure (F2), it means the pilot dispatcher lacks the parameter-hallucination guardrails that other dispatchers have. The model can pass irrelevant parameters (e.g., `ship_filter` to a `contracts` action) without warning.

### Evidence

- `validation.py` defines 5 `*_ACTION_PARAMS` schemas — no `PILOT_ACTION_PARAMS`
- All other dispatchers call `validate_action_params()` — pilot does not
- The `get_default_values()` function has no `"pilot"` branch

### Proposed Fix

**File:** `src/aria_esi/mcp/validation.py`

Add the pilot schema:

```python
# =============================================================================
# Pilot Dispatcher Parameter Schema
# =============================================================================

PILOT_ACTION_PARAMS: dict[str, set[str]] = {
    "mail_list": {"unread_only", "limit"},
    "mail_read": {"mail_id"},
    "mining_ledger": {"days", "system_filter", "ore_filter"},
    "contracts": {"status_filter", "type_filter", "issued", "received", "limit"},
    "fittings_list": {"ship_filter", "limit"},
    "fittings_detail": {"fitting_id", "eft"},
    "lp_balance": set(),
    "lp_offers": {"corporation_name", "search", "max_lp", "affordable", "limit"},
}
```

Add pilot defaults to `get_default_values()`:

```python
elif dispatcher == "pilot":
    return {
        "unread_only": False,
        "limit": 50,
        "days": 30,
        "issued": True,
        "received": True,
        "eft": False,
        "affordable": False,
    }
```

**File:** `src/aria_esi/mcp/dispatchers/pilot.py`

Add validation call after action dispatch (matching the pattern in other dispatchers):

```python
from ..validation import validate_action_params

# Inside pilot(), before the match statement:
warnings = validate_action_params("pilot", action, {
    k: v for k, v in {
        "unread_only": unread_only, "limit": limit, "mail_id": mail_id,
        "days": days, "system_filter": system_filter, "ore_filter": ore_filter,
        "status_filter": status_filter, "type_filter": type_filter,
        "issued": issued, "received": received, "ship_filter": ship_filter,
        "fitting_id": fitting_id, "eft": eft, "corporation_name": corporation_name,
        "search": search, "max_lp": max_lp, "affordable": affordable,
    }.items() if v is not None
})
```

### Test

Add test cases in `tests/mcp/test_validation.py`:
- `test_pilot_contracts_valid_params`: `validate_action_params("pilot", "contracts", {"status_filter": "active"})` returns no warnings
- `test_pilot_contracts_irrelevant_params`: `validate_action_params("pilot", "contracts", {"ship_filter": "Vexor"})` returns a warning about `ship_filter`
- `test_pilot_lp_balance_no_params`: `validate_action_params("pilot", "lp_balance", {})` returns no warnings

### Scope

- `src/aria_esi/mcp/validation.py` — add `PILOT_ACTION_PARAMS`, update `get_default_values()`
- `src/aria_esi/mcp/dispatchers/pilot.py` — add `validate_action_params()` call
- `tests/mcp/test_validation.py` — 3 new test cases

---

## Implementation Plan

F1, F3, F4, and F5 are independent. F2 has a diagnostic phase before the fix can be specified.

```
Week 1:
  F1: Hook script + exercise runner integration     [Low effort]
  F4: Killmail scope metadata                       [Low effort]
  F5: Pilot validation schema                       [Low effort]
  F2 Phase 1: Diagnostic logging + reproduction     [Low effort]

Week 2:
  F2 Phase 2-3: Fix + validate                      [Medium effort, depends on Phase 1]
  F3: Quality gates in exercise runner              [Medium effort]

Validation:
  Re-run ESI:LOW batch with F1 active               [After F1 lands]
  Re-run contracts exercises after F2 fix            [After F2 lands]
```

### Recommended Priority Order

F1 → F4 → F5 → F2 (Phase 1) → F3 → F2 (Phase 2-3)

F1 is the highest-impact fix — once skills load, many secondary issues (confabulation, tag costs, data scope guidance) should self-resolve. F4 and F5 are quick wins. F2 requires investigation before a fix can be specified. F3 is the most effort but provides ongoing value for all future exercise runs.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| F1: `UserPromptSubmit` hook doesn't fire in `-p` mode | Critical | Verify with a single test exercise before full batch. If it doesn't fire, fall back to `--system-prompt` (full override, not append) |
| F1: Model still ignores `additionalContext` | Medium | Escalate to `transformedPrompt` which replaces the prompt entirely. Add a `PreToolUse` hook that blocks MCP calls until Skill has been called |
| F2: Root cause is in ESI client, not dispatcher | Medium | The diagnostic logging (Phase 1) will reveal the exact exception chain |
| F3: Quality gates produce false positives | Low | Flags are advisory, not blocking. Review first few runs and tune thresholds |
| F4: `scope_note` text consumes context tokens | Negligible | ~25 tokens per response; omit when `scope="character"` |
| F5: Validation warnings for pilot actions may confuse model | Low | Warnings are appended to `_meta`, not the main response body |

---

## Out of Scope

- **Subagent architecture for exercise runs** (R6 from RECOMMENDATIONS.md): architecturally sound but high effort. Evaluate after F1's effectiveness is measured.
- **Escape-route confabulation fix**: symptom of skill bypass; expected to self-resolve with F1.
- **sec-status tag cost calculation**: symptom of skill bypass; expected to self-resolve with F1.
- **Brevity protocol enforcement**: tracked as a quality flag (F3) rather than a code fix. Brevity is a prompt-level concern better addressed in SKILL.md files.
- **Exercise runner parallelization improvements**: operational optimization, not a correctness fix.
