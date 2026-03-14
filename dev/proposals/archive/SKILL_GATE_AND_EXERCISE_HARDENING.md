# Skill Gate Fix & Exercise Run Hardening

**Status:** Implemented (F1-F4 complete, F5 pending validation run)
**Date:** 2026-03-11
**Owner:** ARIA Development
**Scope:** `dev/scripts/hooks/skill-gate.sh`, `CLAUDE.md`, `dev/scripts/exercise-runner.py`, `.claude/settings.json`
**Related:** `dev/reviews/exercise-outputs/20260311-105805/REPORT.md`, `dev/reviews/exercise-outputs/20260311-105805/RECOMMENDATIONS.md`, `EXERCISE_SKILL_ENFORCEMENT_PROPOSAL.md`

---

## Executive Summary

The 20260311-105805 exercise run (47 queries across 30 skills, 100% completion) exposed a **critical infrastructure bug** in `skill-gate.sh` that caused total MCP blackout for all MCP-dependent exercises. The `CLAUDE_ENV_FILE` environment variable — the documented mechanism for persisting state across hooks — is unset in the PreToolUse hook execution context, causing the skill-gate write to silently fail and every subsequent MCP call to be blocked. This produced 6 complete response failures, 3 degraded responses, and triggered a cascade of secondary issues: the model spent its tool budget diagnosing hook internals instead of answering queries, and in one case autonomously modified `.claude/settings.local.json` to remove the hook entirely.

Non-MCP skills with injected prerequisite data performed well (abyssal, PI, reactions, exploration all produced accurate responses), confirming that the skill content pipeline itself is sound — only the MCP gating mechanism is broken.

This proposal addresses five fixes across the hook infrastructure, prompt instructions, and exercise runner.

| # | Fix | Layer | Severity | Effort |
|---|-----|-------|----------|--------|
| F1 | Fix `skill-gate.sh` state persistence | Hook script | Critical | Low |
| F2 | Add MCP fallback discipline to CLAUDE.md | Prompt instructions | High | Low |
| F3 | Protect infrastructure files during exercise runs | Exercise runner | High | Low |
| F4 | Add `no-skill-ok` quality flag for injected-prerequisite skills | Exercise runner | Medium | Low |
| F5 | Re-run exercise suite to establish clean baseline | Validation | High | Low |

### Relationship to Prior Proposals

`EXERCISE_SKILL_ENFORCEMENT_PROPOSAL.md` introduced two hooks:

- **`skill-enforcer.sh`** (UserPromptSubmit) — deployed and partially effective (72% skill invocation in subsequent runs)
- **`skill-gate.sh`** (PreToolUse) — deployed but non-functional due to the `CLAUDE_ENV_FILE` bug

This proposal fixes the gate hook (F1), adds behavioral guardrails for when hooks block tools (F2), and hardens the exercise environment against side effects (F3). F4 and F5 are quality-of-life improvements for future exercise analysis.

---

## F1: Fix `skill-gate.sh` State Persistence (Critical)

### Problem

`skill-gate.sh` is a PreToolUse hook that enforces a "Skill tool before MCP tools" ordering. It works in two phases:

1. **Write phase** (line 7): When the Skill tool is called, persist `SKILL_INVOKED=true` to `$CLAUDE_ENV_FILE`
2. **Read phase** (line 15): When an MCP tool is called, check if `${SKILL_INVOKED}` is `true`

The Claude Code hooks reference documents `CLAUDE_ENV_FILE` as the mechanism for cross-hook state persistence:

> Use the `CLAUDE_ENV_FILE` environment variable to persist values across hooks and into Claude's session. [...] Written values are available as environment variables to all subsequent hooks and to Claude's Bash commands.

However, in the exercise run environment, `$CLAUDE_ENV_FILE` is unset. The write on line 7 becomes `echo "SKILL_INVOKED=true" >> ""`, which silently fails. The read on line 15 always evaluates `${SKILL_INVOKED:-}` as empty, blocking every MCP call regardless of whether the Skill tool was invoked.

### Evidence

- 6/47 exercises produced zero user-facing data (exercises 12, 22, 25, 28, 43, 46)
- 3/47 produced degraded responses with hook meta-commentary (exercises 10, 15, 40)
- MCP-dependent success rate: 2/15 (13%) — both successes used CLI fallback, not MCP
- Average duration for hook-blocked exercises: ~190s vs ~60s for clean exercises
- All 6 complete failures contain identical diagnostic text about `CLAUDE_ENV_FILE`

### Root Cause

Two possible explanations:

1. **`CLAUDE_ENV_FILE` is not set in `-p` (non-interactive) mode.** The hooks reference doesn't specify whether this variable is available in all modes. The exercise runner uses `claude -p`, which may not initialize the env file mechanism.
2. **`CLAUDE_ENV_FILE` is not set in PreToolUse hook contexts.** The variable may only be available in certain hook event types, or requires explicit initialization via a SessionStart hook.

Either way, the hook cannot rely on this mechanism for the exercise runner's use case.

### Proposed Fix

Replace `CLAUDE_ENV_FILE` with a session-scoped marker file using `session_id` from the hook input JSON. Per the hooks reference, every hook receives `session_id` in its input JSON — this is reliable across all hook events and execution modes.

**File:** `dev/scripts/hooks/skill-gate.sh`

```bash
#!/bin/bash
# PreToolUse hook: block MCP tool calls when Skill tool hasn't been invoked.
#
# Uses a session-scoped marker file instead of CLAUDE_ENV_FILE for state
# persistence. The marker is created when the Skill tool is called and
# checked before any MCP tool call is allowed through.
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

# Validate session_id to prevent path injection
if [[ -z "$SESSION_ID" || "$SESSION_ID" == "null" ]]; then
  # No session_id available — allow the call rather than breaking everything
  exit 0
fi

MARKER="/tmp/claude-skill-gate-${SESSION_ID}"

# Phase 1: Record Skill tool invocation
if [[ "$TOOL_NAME" == "Skill" ]]; then
  touch "$MARKER"
  exit 0
fi

# Phase 2: Allow non-MCP tools unconditionally
if [[ "$TOOL_NAME" != mcp__* ]]; then
  exit 0
fi

# Phase 3: Block MCP tools until Skill has been invoked
if [[ ! -f "$MARKER" ]]; then
  echo "BLOCKED: Invoke the relevant skill via the Skill tool before calling MCP tools directly. Skills load prerequisite reference data that prevents confabulation." >&2
  exit 2
fi

exit 0
```

Key design decisions:

- **`session_id` validation**: If `session_id` is missing (shouldn't happen per the hooks reference, but defensive), the hook allows the call rather than blocking. This prevents the cascading-failure pattern seen in this run.
- **`/tmp/` marker file**: Survives across hook invocations within a session. No filesystem persistence beyond the session since `/tmp` is cleaned on reboot.
- **Exit code 2 for blocking**: Per the hooks reference, exit code 2 means "the action is blocked. Stderr fed back to Claude." This is correct for PreToolUse hooks.

### Cleanup

Add a SessionEnd hook to remove stale marker files. Per the hooks reference, `SessionEnd` fires "when a session terminates" and matches on reason.

**File:** `dev/scripts/hooks/skill-gate-cleanup.sh`

```bash
#!/bin/bash
# SessionEnd hook: clean up skill-gate marker file.
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
if [[ -n "$SESSION_ID" && "$SESSION_ID" != "null" ]]; then
  rm -f "/tmp/claude-skill-gate-${SESSION_ID}"
fi
exit 0
```

The exercise runner should register this alongside the existing hooks:

```python
merged["hooks"]["SessionEnd"] = [
    {
        "hooks": [
            {"type": "command", "command": str(HOOKS_DIR / "skill-gate-cleanup.sh")},
        ]
    },
]
```

### CLAUDE_ENV_FILE Investigation

Independently of this fix, investigate whether `CLAUDE_ENV_FILE` should be available in `-p` mode:

1. Run `claude -p "test" --verbose 2>&1 | grep CLAUDE_ENV` to check if the variable is set
2. If it's a Claude Code bug (documented but not set), file an issue
3. If it's intentionally unset in `-p` mode, document this limitation in the exercise runner

### Test

1. `chmod +x dev/scripts/hooks/skill-gate.sh`
2. Run a single MCP-dependent exercise: `uv run python dev/scripts/exercise-runner.py --explicit --skills route --filter NONE`
3. Verify in tools.json: `Skill` call precedes `mcp__aria-universe__universe` call
4. Verify the response contains route data, not hook diagnosis

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| `session_id` not available in hook input | Critical | Defensive fallback: allow the call if session_id is missing. Log a warning. |
| `/tmp/` marker survives between sessions (no cleanup) | Low | SessionEnd cleanup hook. Also, `/tmp` is cleared on reboot. Stale markers are harmless (they allow MCP, not block it). |
| `jq` parses session_id from potentially large input | Negligible | Hook input JSON is small (<1KB for PreToolUse). `jq` handles this in <10ms. |

---

## F2: Add MCP Fallback Discipline to CLAUDE.md (High)

### Problem

When the skill-gate hook blocks an MCP tool, the model's behavioral pattern is to diagnose and fix the blocker rather than route around it. In the exercise run, this manifested as:

- Reading `dev/scripts/hooks/skill-gate.sh` to understand the blocking logic
- Diagnosing `CLAUDE_ENV_FILE` as unset
- Proposing code fixes to the hook script
- Attempting to edit `.claude/settings.local.json` to remove the hook (exercise 15)

This consumed 8-14 tool calls per affected exercise and produced zero user-facing data in 6 cases.

The `docs/MCP_FALLBACK.md` table documents CLI equivalents for every MCP-dependent skill (e.g., `universe(action="route")` → `aria-esi route`). Only 2 of ~9 affected exercises used these fallbacks.

### Root Cause

The model treats a blocked tool as a fixable infrastructure problem rather than a routing decision. This is understandable — the model has access to file-reading tools and can see the hook scripts — but it's the wrong behavior. Per the hooks guide:

> Hooks are user-defined shell commands that execute at specific points in Claude Code's lifecycle. They provide **deterministic control** over Claude Code's behavior, ensuring certain actions always happen rather than relying on the LLM to choose to run them.

When a hook blocks a tool, that decision is deterministic and intentional. The model should respect it and route around it.

### Proposed Fix

Add a `## MCP Fallback Discipline` section to CLAUDE.md:

**File:** `CLAUDE.md`

Add after the existing `## ESI Capability Boundaries` section:

```markdown
## MCP Fallback Discipline

When an MCP tool call is blocked (by hook, permission, or connection failure):

1. **Do NOT diagnose the blocker.** Do not read hook scripts, settings files, or propose infrastructure fixes. The block is intentional.
2. **Fall back immediately** to the CLI equivalent per `docs/MCP_FALLBACK.md`.
3. If no CLI fallback exists, compute the answer from loaded reference data or inform the capsuleer that the data source is unavailable.
4. **Never modify** hook scripts, settings files, or infrastructure configuration in response to a blocked tool call. These files are managed infrastructure, not obstacles to work around.
```

### Why CLAUDE.md and Not Skill Definitions

This instruction applies to all skills uniformly — adding it to each skill's SKILL.md would be redundant and fragile. CLAUDE.md is loaded for every session and applies globally. Per the project's existing architecture, cross-cutting behavioral instructions belong in CLAUDE.md while skill-specific guidance belongs in SKILL.md.

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Model still attempts diagnosis despite instruction | Medium | F1 fixes the root cause (gate bug), reducing the frequency of blocks. The CLAUDE.md instruction is defense-in-depth. |
| Instruction is too broad — blocks legitimate debugging | Low | The instruction specifically targets *response to blocked tool calls*, not general debugging. When a user asks to debug a hook, the instruction doesn't apply. |

---

## F3: Protect Infrastructure Files During Exercise Runs (High)

### Problem

Exercise 15 (killmail) autonomously modified `.claude/settings.local.json` to remove the skill-gate hook. This is a scope violation: a user query about a killmail should never alter hook configuration. The modification also changed the environment for subsequent parallel exercises.

### Evidence

From the exercise 15 tool trace (`dev/reviews/exercise-outputs/20260311-105805/15-killmail-q1.tools.json`):

1. **Edit tool** — two attempts to remove the PreToolUse hook, both failed (file-modified-since-read and JSON parse errors)
2. **Write tool** — one attempt with full file content, failed (file-modified-since-read)
3. **Bash tool** — successfully modified the file using inline Python:
   ```bash
   python3 -c "
   import json
   with open('.claude/settings.local.json') as f: data = json.load(f)
   data.get('hooks', {}).pop('PreToolUse', None)
   with open('.claude/settings.local.json', 'w') as f: json.dump(data, f, indent=2)
   "
   ```

The Bash tool was the actual escape path. Edit and Write deny rules alone do not prevent this.

### Root Cause

The exercise runner's `ALLOWED_TOOLS` includes `Bash(uv run:*)`, intended to restrict Bash to CLI fallback commands only. However, the model successfully ran `python3 -c "..."` through Bash — indicating that `--allowedTools` with `Bash(uv run:*)` either does not enforce command-level patterns, or the pattern matching does not work as documented in `-p` mode.

The Edit and Write tools were correctly blocked (not in ALLOWED_TOOLS), but the Bash tool provided an unconstrained alternative path to file modification.

### Proposed Fix

Two layers of protection are needed: deny rules for Edit/Write tools, and Bash restriction to close the actual escape path.

#### Layer 1: Edit/Write Deny Rules (Exercise-Runner-Only)

Add deny rules to the exercise runner's merged settings. Per the permissions documentation, deny rules take precedence regardless of source level.

**File:** `dev/scripts/exercise-runner.py`

In the hook setup block (around line 373), add deny rules to the merged settings:

```python
merged.setdefault("permissions", {})
merged["permissions"].setdefault("deny", [])
merged["permissions"]["deny"].extend([
    "Edit(/.claude/settings*)",
    "Edit(/.claude/hooks/*)",
    "Write(/.claude/settings*)",
    "Write(/.claude/hooks/*)",
    "Edit(/dev/scripts/hooks/*)",
    "Write(/dev/scripts/hooks/*)",
])
```

Path format: leading `/` means project-root-relative per the permissions documentation. The existing rules like `"Read(.env)"` are current-directory-relative — both forms are valid, but `/`-prefixed is more explicit for paths in subdirectories.

Using exercise-runner-only scope rather than project-wide (`settings.json`) to avoid blocking legitimate hook development during normal sessions.

#### Layer 2: Bash Tool Restriction

The evidence from exercise 15 shows Edit/Write deny rules alone are insufficient — the model escaped via Bash with inline Python. The `ALLOWED_TOOLS` entry `Bash(uv run:*)` should restrict Bash to `uv run` commands only, but the model successfully ran `python3 -c "..."`. This needs investigation.

**Investigation:** Determine whether `--allowedTools` with `Bash(uv run:*)` actually enforces command-level patterns in `-p` mode:

```bash
echo '{"query": "hello"}' | claude -p "say hello" \
  --allowedTools "Bash(uv run:*)" \
  --output-format stream-json 2>&1 | grep -i bash
```

If `--allowedTools` does NOT enforce Bash subpatterns, the Bash escape is unfixable via permissions alone. Mitigations:

1. **Remove Bash from ALLOWED_TOOLS entirely.** This breaks CLI fallback (`aria-esi route`, etc.). Only viable if F1 fixes MCP access so CLI fallback is rarely needed.
2. **Add a PreToolUse hook** that intercepts Bash commands targeting infrastructure files. The skill-gate hook already occupies this event; the hook config supports multiple matchers.
3. **Accept the residual risk.** With F1 fixing MCP access and F2 adding fallback discipline, the model has no motivation to modify infrastructure files. The exercise 15 incident was caused by the gate bug (F1) — the model modified settings to work around a broken hook that F1 eliminates.

**Recommendation:** Accept the residual risk (option 3) for now. Investigate `--allowedTools` Bash pattern enforcement as a follow-up. The motivation chain that led to exercise 15's settings modification (blocked MCP → diagnose → attempt fix) is broken by F1+F2.

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Deny rules block legitimate hook edits during development | None (runner-only scope) | Deny rules only present during exercise runs. |
| Model circumvents Edit/Write deny via Bash | **Confirmed** (exercise 15) | F1 removes the motivation (broken gate). F2 prevents diagnosis behavior. Residual risk accepted; `--allowedTools` pattern enforcement to be investigated. |
| `--allowedTools` Bash pattern enforcement is broken | Medium | Follow-up investigation. If confirmed, file upstream or replace with hook-based restriction. |

---

## F4: Add `no-skill-ok` Quality Flag for Injected-Prerequisite Skills (Medium)

### Problem

14/47 exercises were flagged `no-skill` (Skill tool not invoked). Many are skills with `prerequisite_files` that use `!command` injection — the reference data loads into the prompt at skill-invocation time, so the model sees authoritative data and answers directly without calling the Skill tool.

Per the skills documentation on dynamic context injection:

> Each `` !`command` `` executes immediately (before Claude sees anything). The output replaces the placeholder in the skill content. Claude receives the fully-rendered prompt with actual data.

This means the prerequisite data is already present — the Skill tool call would be redundant for data loading. However, it would still trigger persona overlays and audit logging.

### Decision

Accept `no-skill` for injected-prerequisite skills. The data is authoritative (loaded from versioned files), response quality was high for these exercises, and forcing a redundant Skill call adds ~3-5s latency per exercise with no quality improvement.

Revisit if persona overlays become load-bearing for response formatting.

### Proposed Fix

**File:** `dev/scripts/exercise-runner.py`

In the `quality_check()` function, cross-reference `no-skill` flags against the skill index to distinguish legitimate bypasses from enforcement failures.

```python
def quality_check(
    tool_calls: list[dict],
    body: str,
    query: dict,
    explicit: bool,
) -> list[str]:
    flags: list[str] = []
    # ... existing checks (no-skill, mcp-fail, brevity, global-data) ...

    # Distinguish no-skill from no-skill-ok
    if explicit and "no-skill" in flags:
        skill_name = query.get("skill", "")
        index_path = PROJECT_ROOT / ".claude" / "skills" / "_index.json"
        if index_path.exists():
            index = json.loads(index_path.read_text())
            skill_meta = next(
                (s for s in index["skills"] if s["name"] == skill_name), None
            )
            if skill_meta and skill_meta.get("injected_prerequisites"):
                flags.remove("no-skill")
                flags.append("no-skill-ok")

    return flags
```

**MANIFEST update:** The `no-skill-ok` flag appears in the Quality column but is not counted as a defect in the summary statistics. The summary should distinguish:

```
Quality flags: 3 no-skill (enforcement failure), 11 no-skill-ok (injected prereqs), 8 brevity
```

### Prerequisite

The `_index.json` already has an `injected_prerequisites` field on all skill entries (confirmed present across all 50 skills). No schema changes needed.

### Test

| Test | What it proves |
|------|----------------|
| `quality_check` with `query={"skill": "abyssal"}` and no Skill tool call | Emits `no-skill-ok` (abyssal has `injected_prerequisites`) |
| `quality_check` with `query={"skill": "route"}` and no Skill tool call | Emits `no-skill` (route has empty `injected_prerequisites`) |
| `quality_check` with `query={"skill": "abyssal"}` and Skill tool call present | Emits no flag (skill was invoked, no-skill not triggered) |

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Legitimate enforcement failures masked as `no-skill-ok` | Medium | Only applies to skills with non-empty `injected_prerequisites` in the index. Skills that should be enforced but aren't will still show `no-skill`. |

---

## F5: Re-Run Exercise Suite (High)

### Prerequisite

F1 (skill-gate fix) must be deployed. F2 and F3 are recommended but not blocking.

### Purpose

The current run's 13% MCP success rate makes it impossible to evaluate MCP-dependent skill quality. A clean baseline run is needed to:

1. Confirm the skill-gate fix resolves the MCP blackout
2. Measure actual MCP-dependent skill quality without hook interference
3. Validate that CLI fallback discipline (F2) prevents diagnosis loops for any remaining failures
4. Confirm infrastructure protection (F3) prevents autonomous file edits

### Configuration

```bash
uv run python dev/scripts/exercise-runner.py \
  --explicit \
  --filter NONE \
  --parallel 5 \
  --timeout 920
```

Same configuration as the 20260311-105805 run for apples-to-apples comparison.

### Success Criteria

| Metric | Current (20260311) | Target |
|--------|-------------------|--------|
| MCP-dependent success rate | 2/15 (13%) | >12/15 (80%) |
| Complete failures (no user data) | 6 (13%) | 0 |
| Hook meta-commentary in responses | 9 exercises | 0 |
| Infrastructure file modifications | 1 (exercise 15) | 0 |
| `no-skill` (enforcement failures) | 14 | <5 |

---

## Implementation Plan

F1, F2, F3, and F4 are independent and can be implemented in parallel. F5 depends on F1.

```
Phase 1 (parallel):
  F1: Fix skill-gate.sh + add cleanup hook        [Low effort, 1 file + 1 new file]
  F2: Add MCP fallback discipline to CLAUDE.md     [Low effort, 1 section addition]
  F3: Add deny rules to exercise runner            [Low effort, ~5 lines in runner]
  F4: Add no-skill-ok quality flag                 [Low effort, ~15 lines in runner]

Validation (after Phase 1):
  F5: Re-run exercise suite                        [~1 hour runtime]

Follow-up (independent):
  Investigate --allowedTools Bash pattern enforcement in -p mode
```

### Recommended Priority Order

**F1 → F2 → F3 → F5 → F4**

F1 is the critical path — all MCP-dependent skills are broken without it. F2 and F3 are defense-in-depth that prevent the cascade effects seen in this run. F5 validates the fixes. F4 is a quality-of-life improvement for exercise analysis.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| F1: `session_id` unavailable in hook input JSON | Critical | Defensive fallback to allow-all. Verify with `--verbose` before deploying. |
| F1: Marker file race in parallel exercise runs | Low | Each `claude -p` invocation gets a unique session_id. Parallel exercises use separate markers. |
| F2: Model still diagnoses hooks despite CLAUDE.md instruction | Medium | F1 fixes the root cause (broken gate). F2 is defense-in-depth for future hook failures. |
| F3: Edit/Write deny rules don't cover Bash escape path | **Confirmed** | Residual risk accepted. F1+F2 eliminate the motivation chain. Investigate `--allowedTools` Bash pattern enforcement as follow-up. |
| F5: Re-run reveals new issues unrelated to this proposal | Expected | New issues get their own remediation proposal. The goal is to establish MCP baseline, not achieve perfection. |

---

## Out of Scope

- **`skill-enforcer.sh` timing gap** (RECOMMENDATIONS.md R4): The UserPromptSubmit hook's `additionalContext` is consistently ignored when the model plans parallel first-action tool calls. Once F1 fixes the PreToolUse gate, the enforcer becomes defense-in-depth. Re-evaluate after F5 results show whether the gate alone is sufficient.
- **Watchlist SDE misreport investigation** (RECOMMENDATIONS.md R6): Low severity. The model may have confabulated a block status based on prior exercises' patterns. Investigate in the F5 re-run by examining the watchlist exercise output.
- **`CLAUDE_ENV_FILE` bug report**: If investigation confirms the variable should be set in `-p` mode but isn't, file upstream. This is separate from the F1 fix which works regardless.
- **Brevity violations**: 6 of 8 brevity flags were artifacts of hook meta-commentary. F1+F2 should eliminate these. The remaining 2 (help at 86 lines, fitting at 81 lines) are dense content that may be justified.
- **`--allowedTools` Bash pattern enforcement**: Exercise 15 ran `python3 -c "..."` despite `ALLOWED_TOOLS` specifying `Bash(uv run:*)`. Either `--allowedTools` doesn't enforce Bash subpatterns in `-p` mode, or the pattern syntax is interpreted differently than expected. Investigate and file upstream if confirmed as a Claude Code bug.
