# Skill-Gate Simplification: Strip Proven-Ineffective Complexity

**Status:** Proposed
**Date:** 2026-03-12
**Owner:** ARIA Development
**Scope:** `dev/scripts/hooks/`, `.claude/settings.json`, `CLAUDE.md`, `dev/scripts/exercise-runner.py`

---

## Executive Summary

Over 12 days and 8 proposals, the skill-gate enforcement system grew from a simple concept (invoke the Skill tool before MCP calls) into a multi-layered stack of 4 hook scripts, 3 hook events, 6 CLAUDE.md paragraphs, a `SessionStart compact` re-injection, deny rules, git-dirty detection, and extensive exercise-runner integration. The violation rate across the last 4 measured runs: **53% → 66% → 68% → 66%**. None of the layers added after the initial gate produced measurable improvement in violation *rate*.

What **does** work:
1. The `PreToolUse` gate (`skill-gate.sh`) — blocks MCP/CLI calls until Skill is invoked, model recovers 100% of the time
2. The `UserPromptSubmit` enforcer (`skill-enforcer.sh`) — injects `additionalContext` for `/` commands, proven effective for explicit invocations

What **does not** work (proven by data):
1. CLAUDE.md prompt rewrites (3 iterations, no improvement)
2. ToolSearch gating (shifts block point earlier, no rate change)
3. Generic per-prompt `additionalContext` for natural language queries (no rate change)
4. `SessionStart compact` re-injection (defense-in-depth for a defense that doesn't work)
5. Multi-file gate level tracking (`/tmp/claude-skill-gate-level-*`)

This proposal strips the system back to the two components that work, removes the CLAUDE.md bloat, and archives the dead proposals.

---

## Inventory: What Exists Today

### Hook Scripts (4 files)

| File | Event | Purpose | Keep? |
|------|-------|---------|-------|
| `skill-gate.sh` | PreToolUse | Blocks MCP/CLI/ToolSearch/Agent before Skill marker | **Yes — simplify** |
| `skill-enforcer.sh` | UserPromptSubmit | Injects `additionalContext` for `/` and natural language | **Yes — simplify** |
| `skill-gate-cleanup-turn.sh` | UserPromptSubmit | Clears marker per-turn | **Yes** (essential) |
| `skill-gate-cleanup.sh` | SessionEnd | Clears marker on session end | **Yes** (essential) |

### .claude/settings.json Hooks (3 events, 5 entries)

| Entry | Purpose | Keep? |
|-------|---------|-------|
| `SessionStart` — aria-boot.sh | Boot context | **Yes** (unrelated) |
| `SessionStart` — skill-listing python | Generate help listing | **Yes** (unrelated) |
| `SessionStart compact` — echo reminder | Post-compaction skill-first reminder | **Remove** — defense-in-depth for a defense (CLAUDE.md text) that doesn't work |
| `UserPromptSubmit` — cleanup-turn.sh | Per-turn marker reset | **Yes** |
| `UserPromptSubmit` — skill-enforcer.sh | Skill-first injection | **Yes — simplify** |

### CLAUDE.md Sections

| Section | Lines | Purpose | Keep? |
|---------|-------|---------|-------|
| MCP Fallback Discipline (item 2) | 1 | `SKILL-GATE-BLOCK` exception handling | **Yes — simplify** |
| Prime Directive #8 | 1 | "Skill First, Data Second" | **Yes — simplify** |
| Routing Hints table | 7 | Knowledge-only skill routing | **Yes** |
| "Knowledge-only skills have no MCP calls..." | 1 | Routing hint context | **Yes** |
| Skill Loading §1 "CRITICAL: Invoke..." | 1 | Redundant restatement of PD#8 | **Remove** |
| Skill Loading §2 "Skills gate authoritative..." | 3 | Explains *why* skills matter | **Keep** (motivation) |
| Skill Loading §skill-gate order of ops | 1 | Redundant: recovery instructions | **Remove** — the gate's stderr message already tells the model what to do |

### Exercise Runner Integration

| Feature | Lines (approx) | Purpose | Keep? |
|---------|----------------|---------|-------|
| Hook setup (cleanup-turn, enforcer, gate, session-cleanup) | ~40 | Install hooks for exercise | **Yes** |
| Deny rules (Agent, Edit, Write, infra paths) | ~20 | Exercise sandbox | **Yes** |
| `_git_state_snapshot` / `_check_git_state` | ~20 | Git-dirty detection | **Remove** — defense-in-depth for Agent/Edit/Write deny rules that already work. Never triggered in any run after deny rules were added. |
| `_check_brevity` / `BREVITY_EXEMPT_SKILLS` | ~15 | Per-skill line budgets | **Keep** (useful quality signal) |
| `quality_check` `no-skill-ok` logic | ~15 | Distinguish injected-prereq skills | **Keep** |
| `quality_check` `skill-gate-violation` logic | ~15 | Track violation pattern | **Keep** (diagnostic value) |

---

## Changes

### R1: Simplify `skill-gate.sh` — Remove ToolSearch Gating

**Current state:** The gate intercepts ToolSearch calls containing `mcp__` in the query string (lines 27-35). This was added in `SKILL_GATE_TOOLSEARCH_AND_ROUTING.md` to catch violations one step earlier.

**Evidence it doesn't help:** The violation rate was 66% before ToolSearch gating and 68% after. The model still attempts ToolSearch first — the block just shifts from step 2 to step 1. Each violation saves 1 tool call but the *rate* is unchanged.

**Proposed change:** Remove the ToolSearch case from Phase 3. Let ToolSearch pass unconditionally (move it back to Phase 2 allowlist). The MCP gate at Phase 3 `mcp__*` already catches the actual data call.

**Why this is better:** Simpler script, fewer jq parses per tool call, and the gate error message on the actual MCP call is more actionable ("invoke Skill before calling mcp__market") than the ToolSearch one ("invoke Skill before resolving MCP schemas").

**File:** `dev/scripts/hooks/skill-gate.sh`

```bash
#!/bin/bash
# PreToolUse hook: block data tool calls until the Skill tool has been invoked.
#
# Marker: /tmp/claude-skill-gate-{session_id}
#   Created by Phase 1 when the Skill tool fires.
#   Cleared per-turn by skill-gate-cleanup-turn.sh (UserPromptSubmit).
#   Cleared on exit by skill-gate-cleanup.sh (SessionEnd).
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

if [[ -z "$SESSION_ID" || "$SESSION_ID" == "null" ]]; then
  exit 0
fi

MARKER="/tmp/claude-skill-gate-${SESSION_ID}"

# Phase 1: Record Skill tool invocation
if [[ "$TOOL_NAME" == "Skill" ]]; then
  touch "$MARKER"
  exit 0
fi

# Phase 2: Always allow read-only and schema-resolution tools
case "$TOOL_NAME" in
  Read|Glob|Grep|ToolSearch|WebFetch|WebSearch) exit 0 ;;
esac

# Phase 3: If Skill marker exists, allow everything
if [[ -f "$MARKER" ]]; then
  exit 0
fi

# Phase 4: Block data tools — Skill not yet invoked
case "$TOOL_NAME" in
  Bash)
    COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
    if echo "$COMMAND" | grep -qE '(uv run )?aria-esi\b'; then
      # Exempt disable-model-invocation skills (load inline via /command)
      if echo "$COMMAND" | grep -qE 'watchlist-|journal|sync-wars'; then
        exit 0
      fi
      echo "SKILL-GATE-BLOCK: Invoke the Skill tool for the relevant skill before using aria-esi CLI." >&2
      exit 2
    fi
    exit 0
    ;;
  mcp__*)
    # Exempt resolve_names — read-only SDE name lookup, no confabulation risk
    if echo "$INPUT" | jq -r '.tool_input // empty' | grep -q '"resolve_names"'; then
      exit 0
    fi
    echo "SKILL-GATE-BLOCK: Invoke the Skill tool for the relevant skill before calling ${TOOL_NAME}." >&2
    exit 2
    ;;
  Agent)
    echo "SKILL-GATE-BLOCK: Invoke the Skill tool for the relevant skill before delegating to an Agent." >&2
    exit 2
    ;;
  *)
    exit 0
    ;;
esac
```

**Net change:** Removed ToolSearch gating (7 lines). Consolidated block messages (shorter, still contain `SKILL-GATE-BLOCK` for CLAUDE.md exception routing). Moved ToolSearch back to Phase 2 allowlist. Removed "This is NOT an MCP failure" phrasing — the `SKILL-GATE-BLOCK` prefix already triggers the CLAUDE.md exception path.

---

### R2: Simplify `skill-enforcer.sh` — Remove Natural Language Branch

**Current state:** The `else` branch injects a generic "SKILL-FIRST" reminder for every non-slash prompt. This was added in `SKILL_GATE_PROMPT_SUBMIT_ROUTING.md`.

**Evidence it doesn't help:** The violation rate was 68% before the generic reminder and 66% after. Within measurement noise. The prior proposal itself acknowledged: "the model's natural behavior — resolve data tools first — overrides prompt instructions."

**The slash-command branch works** because it names the specific skill. The generic branch doesn't because it says "IF this query falls within a skill's domain" — the model must make a judgment call, and it consistently judges "resolve data first."

**Proposed change:** Remove the `else` branch. Return `{}` for non-slash prompts (the original behavior before the generic injection was added).

**File:** `dev/scripts/hooks/skill-enforcer.sh`

```bash
#!/usr/bin/env bash
# skill-enforcer.sh — UserPromptSubmit hook
#
# When a prompt starts with /<skill-name>, clears the stale skill-gate
# marker and injects additionalContext requiring the Skill tool first.
# Non-slash prompts: no-op. The PreToolUse gate handles enforcement.

set -euo pipefail

input="$(cat)"

read -r prompt session_id < <(echo "$input" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('prompt', ''), data.get('session_id', ''))
")

if [[ "$prompt" =~ ^/([a-z][a-z0-9-]*) ]]; then
    skill_name="${BASH_REMATCH[1]}"

    # Clear stale marker so the Skill tool's PreToolUse re-creates it fresh
    if [[ -n "$session_id" && "$session_id" != "null" ]]; then
      rm -f "/tmp/claude-skill-gate-${session_id}"
    fi

    jq -n --arg skill "$skill_name" '{
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext: ("SKILL ENFORCEMENT: The user invoked /\($skill). You MUST call the Skill tool with skill=\"\($skill)\" BEFORE using any other tool (Read, Glob, Grep, MCP, etc). Do NOT bypass the Skill tool by reading skill files directly. This is a blocking requirement from the skill-enforcer hook.")
      }
    }'
else
    echo '{}'
fi
```

**Net change:** Removed 8 lines (generic SKILL-FIRST heredoc). Comment updated. Behavior for `/` commands unchanged.

---

### R3: Remove `SessionStart compact` Hook

**Current state:** `.claude/settings.json` has a `SessionStart` entry with `"matcher": "compact"` that echoes a post-compaction skill-first reminder.

**Evidence it doesn't help:** This was added in `SKILL_GATE_PROMPT_SUBMIT_ROUTING.md` as "defense-in-depth" for the CLAUDE.md skill-first instruction. But the CLAUDE.md instruction itself doesn't work (3 iterations, no improvement). Defense-in-depth for an ineffective defense adds complexity with no benefit.

**Proposed change:** Remove the compact matcher group from `SessionStart` in `.claude/settings.json`.

**File:** `.claude/settings.json` — remove lines 29-36 (the compact matcher group).

---

### R4: Trim CLAUDE.md Skill-Gate Text

**Current state:** CLAUDE.md has ~15 lines devoted to skill-gate instructions across 4 locations: MCP Fallback Discipline item 2, Prime Directive #8, Skill Loading §1 ("CRITICAL: Invoke the Skill tool FIRST"), and Skill Loading §skill-gate order of ops.

**Evidence of redundancy:**
- PD#8 and Skill Loading §1 say the same thing
- Skill Loading §skill-gate says "If a data tool call returns a `SKILL-GATE-BLOCK` message, invoke the Skill tool and retry" — but the gate's stderr already says this
- Three iterations of strengthening this text produced no improvement

**Proposed changes:**

1. **Keep** PD#8 as the single statement of the rule, but shorten it:

   ```
   8. **Skill First, Data Second:** When a query falls within a skill's domain,
      invoke the Skill tool BEFORE calling any MCP tools (`mcp__*`) or CLI commands.
      Flow: identify skill → Skill tool → data calls → response.
   ```

   Remove the sentence "Do NOT call ToolSearch or MCP tools before Skill invocation — the skill-gate hook will block them and waste a tool call." This is implementation detail that leaks the gate mechanism into the prompt without improving compliance.

2. **Keep** MCP Fallback Discipline item 2 (`SKILL-GATE-BLOCK` exception), but simplify:

   ```
   2. **Exception — skill-gate blocks:** If a block message contains
      `SKILL-GATE-BLOCK`, invoke the Skill tool for the relevant skill,
      then retry. See Prime Directive #8.
   ```

   Remove "this is NOT an MCP failure. Do not fall back to CLI" — redundant with the block message itself.

3. **Remove** Skill Loading §1 ("CRITICAL: Invoke the Skill tool FIRST. Do not call MCP tools, ToolSearch, or CLI before Skill invocation. See Prime Directive #8.") — Pure restatement of PD#8.

4. **Remove** Skill Loading §skill-gate ("Skill-gate order of operations: See Prime Directive #8. If a data tool call returns a `SKILL-GATE-BLOCK` message, invoke the Skill tool and retry...") — The gate's stderr already tells the model what to do. Documenting the recovery path in CLAUDE.md proved ineffective (the model reads the stderr, not the CLAUDE.md, when deciding how to recover).

**Net savings:** ~8 lines of CLAUDE.md context. More importantly, reduces the number of competing instructions about the same topic from 4 to 2.

---

### R5: Remove `_git_state_snapshot` / `_check_git_state` from Exercise Runner

**Current state:** The exercise runner captures a git porcelain baseline before the run and checks for mutations after each query. Added in `EXERCISE_SANDBOX_AND_GATE_V4.md` F2.

**Evidence it's unnecessary:** The `--disallowedTools Agent,Edit,Write` deny rules (same proposal, F1) completely prevent code mutation. The deny rules are authoritative per the permissions docs: "If a tool is denied at any level, no other level can allow it." Since the deny rules were added, zero `git-dirty` flags have been observed in any exercise run. The git-dirty detection is defense-in-depth for a defense (deny rules) that works perfectly.

**Proposed change:** Remove `_git_state_snapshot()`, `_check_git_state()`, and their call sites in `main()` (lines 880, 890, 909).

**Net savings:** ~25 lines.

---

### R6: Archive Dead Proposals

The following proposals have been fully superseded or describe approaches proven ineffective. Move them to `dev/proposals/archive/`:

| Proposal | Reason |
|----------|--------|
| `EXERCISE_SKILL_ENFORCEMENT_PROPOSAL.md` | Superseded by all subsequent gate proposals |
| `SKILL_GATE_AND_EXERCISE_HARDENING.md` | F1-F4 implemented; superseded by v3/v4 |
| `SKILL_GATE_V3_AND_DB_RESILIENCE.md` | Superseded by `EXERCISE_SANDBOX_AND_GATE_V4.md` |
| `SKILL_GATE_LIFECYCLE_AND_COVERAGE_GAPS.md` | F1-F2 implemented; F3-F6 either done or superseded |
| `SKILL_GATE_COMPLIANCE_AND_QUALITY.md` | All fixes implemented; prompt approach proven ineffective |
| `SKILL_GATE_TOOLSEARCH_AND_ROUTING.md` | F1 proven ineffective (this proposal removes it); F2-F3 implemented |
| `SKILL_GATE_PROMPT_SUBMIT_ROUTING.md` | F1 proven ineffective (this proposal removes it); F2 removed |

**Keep in `dev/proposals/`:**

| Proposal | Reason |
|----------|--------|
| `EXERCISE_SANDBOX_AND_GATE_V4.md` | Contains the current gate architecture (deny rules, extended gate) — still the reference design |

---

## What Remains After Simplification

### Hook Scripts (4 files, simplified)

| File | Lines | Purpose |
|------|-------|---------|
| `skill-gate.sh` | ~55 | PreToolUse: block MCP/CLI/Agent until Skill marker exists |
| `skill-enforcer.sh` | ~30 | UserPromptSubmit: inject specific skill name for `/` commands |
| `skill-gate-cleanup-turn.sh` | ~9 | UserPromptSubmit: clear marker per-turn |
| `skill-gate-cleanup.sh` | ~8 | SessionEnd: clear marker on exit |

### .claude/settings.json Hooks

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [{ "type": "command", "command": "...aria-boot.sh", "timeout": 15 }] },
      { "hooks": [{ "type": "command", "command": "python3 -c \"...skill-listing...\"" }] }
    ],
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [{ "type": "command", "command": "...protect-credentials.sh" }] }
    ],
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "...skill-gate-cleanup-turn.sh" }] },
      { "hooks": [{ "type": "command", "command": "...skill-enforcer.sh" }] }
    ]
  }
}
```

Note: The production `PreToolUse` no longer registers `skill-gate.sh`. The gate runs only during exercise runs (via the exercise runner's hook injection). In production interactive sessions, the `UserPromptSubmit` enforcer provides the specific-skill injection for `/` commands, and natural language queries rely on the model's own skill descriptions for routing — which works well enough given that production sessions have interactive oversight.

### CLAUDE.md Skill-Gate Footprint

~6 lines total:
- PD#8 (2 lines)
- MCP Fallback Discipline item 2 (2 lines)
- Skill Loading §2 "Skills gate authoritative data" (2 lines, explains *why*)

### Exercise Runner

- Hook installation: same 4 scripts, same events
- Deny rules: `Agent, Edit, Write` + infrastructure paths (unchanged)
- Quality checks: `no-skill-ok`, `skill-gate-violation`, `_check_brevity` (unchanged)
- Removed: `_git_state_snapshot`, `_check_git_state` (~25 lines)

---

## What This Does NOT Change

1. **The gate mechanism itself** — PreToolUse blocking with session-scoped markers works and stays.
2. **Per-turn marker cleanup** — Essential for multi-query sessions, stays.
3. **Exercise deny rules** — Agent/Edit/Write blocking works perfectly, stays.
4. **Skill descriptions and routing hints** — These are the model's actual routing mechanism, stay.
5. **Quality checks in exercise runner** — Diagnostic value, stay.
6. **`disable-model-invocation` exemptions** — Watchlist/journal CLI exemptions in the gate, stay.

---

## Expected Impact

| Metric | Before | After | Why |
|--------|--------|-------|-----|
| Violation rate | ~66% | ~66% | Removed layers had no measurable effect |
| Recovery rate | 100% | 100% | Gate mechanism unchanged |
| Correctness | 100% | 100% | Gate mechanism unchanged |
| Hook scripts total lines | ~102 | ~102 | Simplified but same count (ToolSearch logic replaced by comments) |
| CLAUDE.md skill-gate lines | ~15 | ~6 | 60% reduction |
| Exercise runner lines | ~130 | ~105 | Removed git-dirty detection |
| settings.json hook entries | 5 | 4 | Removed compact re-injection |
| `/tmp` files per session | 1 marker | 1 marker | Removed level file (was proposed but never implemented) |
| Proposals in dev/proposals/ | 8 skill-gate | 1 + 7 archived | Cleaner directory |

**The system does the same thing with less code, less configuration, and less CLAUDE.md context.** The violation rate stays at ~66% because the removed layers never affected it. What matters — the gate blocks, the model recovers, the output is correct — is preserved.

---

## Implementation Plan

All changes are independent. Apply in any order.

```
R1: Simplify skill-gate.sh                     [Edit 1 file, net -7 lines]
R2: Simplify skill-enforcer.sh                 [Edit 1 file, net -8 lines]
R3: Remove SessionStart compact hook           [Edit .claude/settings.json, -8 lines]
R4: Trim CLAUDE.md                             [Edit CLAUDE.md, net -8 lines]
R5: Remove git-dirty detection                 [Edit exercise-runner.py, -25 lines]
R6: Archive proposals                          [mv 7 files to archive/]
```

### Validation

After applying R1-R5, run one exercise suite to confirm no regression:

```bash
uv run python dev/scripts/exercise-runner.py \
  --explicit --filter NONE --parallel 5 --timeout 920
```

**Success criteria:** Same or better than the 20260312-174408 baseline (47/47 ok, 0 errors, ~66% violation rate, 100% recovery).

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Removing ToolSearch gate causes extra blocked MCP call per violation | Low | Each violation adds 1 tool call (~3s). Net effect: ~31 extra calls/run. But ToolSearch gating also added 1 call per violation (blocked ToolSearch), so net change is zero. |
| Removing generic additionalContext reduces compliance for some edge case | Negligible | 3 exercise runs showed no improvement from generic injection. If a regression appears, re-add with 2 lines. |
| Removing compact re-injection hurts long sessions | Low | The model's skill routing in long sessions depends on skill descriptions (always in context), not on CLAUDE.md text (compressed away). |
| Removing git-dirty detection misses a future mutation | Low | Deny rules are authoritative. If they're bypassed, it's a Claude Code bug, not something git-dirty detection would prevent. |
