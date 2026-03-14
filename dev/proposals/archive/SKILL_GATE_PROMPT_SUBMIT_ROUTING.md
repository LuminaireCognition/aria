# Skill-Gate Prompt-Submit Routing

**Status:** Proposed
**Date:** 2026-03-12
**Owner:** ARIA Development
**Scope:** `dev/scripts/hooks/skill-enforcer.sh`, `.claude/settings.json`
**Related:** `dev/reviews/exercise-outputs/20260312-163457/REPORT.md`, `SKILL_GATE_TOOLSEARCH_AND_ROUTING.md` (predecessor — implemented F1-F3), `SKILL_GATE_COMPLIANCE_AND_QUALITY.md` (predecessor — implemented F1-F5)

---

## Executive Summary

The 20260312-163457 exercise run (47 queries, 100% completion, 0 errors) is the third clean baseline since skill-gate deployment. The violation rate has remained flat across three rounds of fixes: 53% → 66% → 68%. Two distinct strategies have been tried and measured:

1. **Prompt engineering** (CLAUDE.md Prime Directive #8, Skill Loading section) — 53% → 66%. Additional prompt emphasis had no measurable effect; the second proposal concluded "prompt-level approaches have reached their ceiling."
2. **ToolSearch gating** (PreToolUse blocks `ToolSearch(mcp__*)` before Skill marker) — 66% → 68%. The violation is caught one step earlier (fewer wasted calls per violation), but the violation *rate* did not decrease. The model still defaults to ToolSearch-first.

Both approaches operate at the wrong point in the model's decision cycle:

- **CLAUDE.md** instructions are loaded at session start and fade after compaction. They are hundreds of lines away from the user's prompt when the model formulates its tool plan.
- **PreToolUse hooks** fire *after* the model has already committed to a tool call. They can block and force recovery, but cannot influence the initial planning decision.

The SKILLSSKILLS documentation describes a mechanism that operates at the right point: **UserPromptSubmit hooks** inject `additionalContext` alongside the user's prompt, *before* the model begins processing. This context appears adjacent to the prompt — where recency and proximity effects make it most likely to influence tool-ordering decisions.

**Key finding:** The existing `skill-enforcer.sh` (UserPromptSubmit hook) already uses this mechanism — but only for explicit `/skill-name` prompts. For natural language queries (100% of exercise run prompts), the hook returns `{}` and the model gets no per-prompt routing signal. This is the gap.

| # | Fix | Layer | Severity | Effort |
|---|-----|-------|----------|--------|
| F1 | Extend UserPromptSubmit skill-first routing to natural language queries | Hook script | Critical | Low |
| F2 | Add SessionStart `compact` re-injection for post-compaction resilience | Settings + hook script | Medium | Low |

### Why This Is Different from Prior Prompt Engineering

The prior proposals' prompt engineering modified **static system instructions** (CLAUDE.md). This proposal uses a **per-prompt hook mechanism** from the SKILLSSKILLS docs that injects context at decision time. The distinction:

| Approach | When context appears | Proximity to prompt | Survives compaction | Tested |
|----------|---------------------|--------------------|--------------------|--------|
| CLAUDE.md rewrite | Session start | Far (hundreds of lines away) | Summarized | Yes — no effect (3 iterations) |
| UserPromptSubmit `additionalContext` | Every prompt | Adjacent (injected alongside prompt) | N/A (injected fresh) | Partially — works for `/` commands, untested for natural language |

The existing `skill-enforcer.sh` proves the mechanism works: when it fires (for `/` prefixed prompts), the model receives `additionalContext` saying "You MUST call the Skill tool BEFORE using any other tool" and follows it. The gap is that it only fires for slash commands. Extending it to natural language queries fills this gap using the same proven mechanism.

### Corrections to REPORT.md Recommendations

| Report Recommendation | Issue | Correction |
|---|---|---|
| C1: "Strengthen Prime Directive #8 phrasing — current language may be too buried" | Conflates content with timing | The phrasing is adequate. Three iterations of strengthening produced no improvement (53% → 66% → 68%). The issue is not what the instruction says but *when* the model sees it relative to its tool-planning phase. CLAUDE.md instructions are processed at session start; tool planning happens per-prompt. |
| C1: "Evaluate whether the skill name could be injected earlier (e.g., in the query metadata)" | Correct diagnosis, wrong mechanism | The report correctly identifies that earlier injection would help. The mechanism is `UserPromptSubmit` `additionalContext` per hooks-reference.md, not "query metadata" (which is not a documented mechanism). |

### Relationship to Prior Proposals

| Proposal | What It Fixed | Effect on Violation Rate |
|---|---|---|
| `SKILL_GATE_AND_EXERCISE_HARDENING` | Deployed skill-gate, marker mechanism | Baseline: 53% |
| `SKILL_GATE_COMPLIANCE_AND_QUALITY` F1 | CLAUDE.md proactive "Skill First" rewrite | 53% → 66% (no improvement) |
| `SKILL_GATE_TOOLSEARCH_AND_ROUTING` F1 | Gated `ToolSearch(mcp__*)` before Skill marker | 66% → 68% (no improvement in rate; fewer wasted calls per violation) |
| **This proposal** F1 | Per-prompt `additionalContext` via UserPromptSubmit | Target: <30% |

Each prior proposal addressed a layer of the problem. This proposal addresses the layer that has been missing: **per-prompt context injection at decision time**.

---

## F1: Extend UserPromptSubmit Skill-First Routing to Natural Language Queries (Critical)

### Problem

32 of 47 queries (68%) follow this pattern:

```
ToolSearch(select:mcp__*) → BLOCKED → Skill → ToolSearch(retry) → MCP → success
```

The model's default behavior is to resolve tool schemas before invoking skills. Three rounds of fixes targeting static instructions (CLAUDE.md) and reactive enforcement (PreToolUse gating) have not reduced the violation rate.

### Root Cause

The existing `skill-enforcer.sh` (UserPromptSubmit hook) injects `additionalContext` only for slash-command prompts:

```bash
if [[ "$prompt" =~ ^/([a-z][a-z0-9-]*) ]]; then
    # Injects: "SKILL ENFORCEMENT: ... You MUST call the Skill tool ..."
else
    echo '{}'  # ← No-op for natural language queries
fi
```

All 47 exercise queries are natural language (e.g., "fit my Vexor for missions", "is Uedama safe"). The `else` branch returns empty JSON — the model receives no per-prompt skill-first signal and falls back to its default tool-ordering behavior.

### Evidence

**The mechanism works when it fires.** The slash-command path injects `additionalContext` with "You MUST call the Skill tool with skill=X BEFORE using any other tool." When the exercise runner tests `/` prefixed queries (not in the current suite, but validated during enforcer development), the model follows the instruction. The gap is that the mechanism doesn't fire for natural language queries.

**Per-prompt context outweighs static instructions.** CLAUDE.md Prime Directive #8 says "invoke the Skill tool BEFORE calling any MCP tools." The model has this instruction in its context window but ignores it 68% of the time. Per the SKILLSSKILLS docs, `additionalContext` is "added to Claude's context alongside the prompt" (hooks-reference.md §UserPromptSubmit decision control). This places the instruction adjacent to the user's query — where it competes with, and plausibly outweighs, the model's default tool-ordering instincts.

### Proposed Fix

**File:** `dev/scripts/hooks/skill-enforcer.sh`

Extend the `else` branch to inject a generic skill-first reminder for non-slash prompts:

```bash
#!/usr/bin/env bash
# skill-enforcer.sh — UserPromptSubmit hook
#
# For /skill-name prompts: clears stale marker, injects skill-specific enforcement.
# For natural language prompts: injects generic skill-first routing reminder.
# The generic reminder fills the gap that causes 68% violation rates on
# natural language queries where no per-prompt routing signal is provided.

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
    # Generic skill-first reminder for natural language queries.
    # The model has skill descriptions in context and can identify which
    # skill applies. The problem is ordering, not identification — so the
    # reminder is generic rather than skill-specific.
    cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "SKILL-FIRST: If this query falls within a skill's domain, invoke the Skill tool for that skill BEFORE calling ToolSearch for mcp__ tools or any mcp__ tools directly. Flow: Skill tool \u2192 ToolSearch \u2192 MCP calls \u2192 response."
  }
}
JSON
fi
```

#### Why Generic Instead of Skill-Specific

The slash-command path can inject the specific skill name because it's in the prompt (e.g., `/fitting`). For natural language, identifying the skill would require keyword matching in bash — fragile, slow, and redundant. The model already has skill descriptions in context and reliably identifies the correct skill (the 68% violation is about *ordering*, not *routing*). A generic reminder to check skill descriptions first is sufficient.

#### Why Unconditional (No Keyword Filtering)

ARIA is an EVE Online assistant. Virtually every user query maps to a skill domain. Filtering on game-related keywords would add complexity with marginal benefit:

- The injected context is ~35 tokens — negligible context cost
- For non-skill queries (development tasks, meta questions), the reminder says "IF this query falls within a skill's domain" — the model can evaluate this condition and skip Skill invocation when no skill applies
- Keyword filtering would require a maintained list that drifts from the actual skill set

#### Production Registration

The exercise runner already registers `skill-enforcer.sh` as a UserPromptSubmit hook (exercise-runner.py lines 484-487). For production use (non-exercise ARIA sessions), register the hook in `.claude/settings.json`.

**File:** `.claude/settings.json` — add to existing `hooks` object:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/dev/scripts/hooks/skill-gate-cleanup-turn.sh"
          }
        ]
      },
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/dev/scripts/hooks/skill-enforcer.sh"
          }
        ]
      }
    ]
  }
}
```

**Note:** The exercise runner replaces the `UserPromptSubmit` key in its merged settings (exercise-runner.py line 485), so this production registration does not affect exercise runs. The exercise runner will continue to use its own absolute-path references. The production registration ensures the skill-first routing also applies to interactive ARIA sessions.

### How This Fits the Defense-in-Depth Stack

| Layer | Hook Event | When | Mechanism | What It Does |
|-------|-----------|------|-----------|-------------|
| **1. Proactive routing** (this fix) | UserPromptSubmit | Before model plans | `additionalContext` | Tells model to invoke Skill first |
| 2. Static instructions | CLAUDE.md (loaded at start) | Session start | System prompt | Documents the rule |
| 3. ToolSearch gate | PreToolUse | After model calls ToolSearch(mcp__*) | Exit 2 block | Catches layer 1 failures early |
| 4. MCP gate | PreToolUse | After model calls mcp__* | Exit 2 block | Catches layer 3 bypasses |
| 5. Post-compaction | SessionStart `compact` (F2) | After compaction | Stdout to context | Restores layer 2 after context loss |

Layers 2-4 exist today. This proposal adds layers 1 and 5.

### SKILLSSKILLS Documentation Basis

| Claim | Reference | Status |
|---|---|---|
| UserPromptSubmit fires before Claude processes the prompt | hooks-reference.md §UserPromptSubmit: "When you submit a prompt, before Claude processes it" | Correct |
| `additionalContext` is added alongside the prompt | hooks-reference.md §UserPromptSubmit decision control: "Text added to Claude's context alongside the prompt" | Correct |
| UserPromptSubmit supports command hooks | hooks-reference.md §Prompt-based hooks: lists UserPromptSubmit in supported events | Correct |
| Hook returns structured JSON on stdout | hooks-reference.md §JSON output: "When a hook exits 0, Claude Code tries to parse stdout as JSON" | Correct |
| `hookSpecificOutput` with `hookEventName` wraps decision control | hooks-reference.md §PreToolUse decision control (same pattern used for UserPromptSubmit) | Correct |

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Model ignores `additionalContext` like it ignores CLAUDE.md | Medium | `additionalContext` appears adjacent to the prompt (recency/proximity effect), unlike CLAUDE.md which is hundreds of lines away. The slash-command path proves the mechanism works when it fires. |
| Unconditional injection adds noise for non-skill queries | Low | ~35 tokens per prompt; conditional phrasing ("IF this query falls within a skill's domain") lets the model self-filter |
| Python subprocess in hook adds latency | Low | The existing slash-command path already uses python3 for JSON parsing; no additional subprocess. Total hook execution: ~50ms |
| Exercise runner overrides production registration | None | Exercise runner replaces `UserPromptSubmit` with its own absolute-path hooks (exercise-runner.py line 485). Both paths reference the same script. |

---

## F2: SessionStart Compact Re-Injection (Medium)

### Problem

After context compaction, CLAUDE.md instructions are summarized. The skill-first rule in Prime Directive #8 may lose prominence in the compacted summary. Subsequent prompts see the compacted context but no fresh skill-first instruction (layer 1 fires per-prompt, but the static layer 2 is degraded).

This is a defense-in-depth fix. F1's per-prompt injection should be sufficient regardless of compaction. F2 ensures that even if F1's injected context is somehow insufficient, the model has a fresh reminder of the skill-first rule after compaction.

### Root Cause

Per the SKILLSSKILLS docs, `SessionStart` with matcher `compact` fires "when a session begins or resumes" (hooks-reference.md §SessionStart). Stdout from SessionStart hooks is "added to Claude's context" (hooks-reference.md §SessionStart input). This is the documented mechanism for re-injecting critical instructions after compaction.

The current `.claude/settings.json` has two `SessionStart` hooks (aria-boot.sh and skill-listing), neither of which addresses skill-first routing.

### Proposed Fix

**File:** `.claude/settings.json` — add a third SessionStart matcher group:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/aria-boot.sh",
            "timeout": 15
          }
        ]
      },
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 -c \"...\""
          }
        ]
      },
      {
        "matcher": "compact",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'POST-COMPACTION REMINDER: Always invoke the Skill tool for the relevant skill BEFORE calling ToolSearch for mcp__ tools or any mcp__ tools directly. Flow: identify skill → Skill tool → data calls → response. This rule is documented in Prime Directive #8.'"
          }
        ]
      }
    ]
  }
}
```

#### How This Works

Per hooks-reference.md §SessionStart:

- The `matcher` field filters on session start source: `startup`, `resume`, `clear`, `compact`
- Matcher `compact` fires only after context compaction — not on initial startup or resume
- Stdout from the hook is "added to Claude's context" as a system message

The hook is a simple `echo` — no script file needed, ~1ms execution time. The output appears in the compacted context as a system-level message, re-establishing the skill-first rule that may have been summarized away.

### SKILLSSKILLS Documentation Basis

| Claim | Reference | Status |
|---|---|---|
| SessionStart fires after compaction | hooks-reference.md §SessionStart: matches on source including `compact` | Correct |
| SessionStart stdout added to context | hooks-reference.md §SessionStart: "Stdout from SessionStart hooks is added to Claude's context" | Correct |
| Matcher `compact` filters to compaction events only | hooks-guide.md §Re-inject context after compaction: example uses `"matcher": "compact"` | Correct |

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Re-injection insufficient to override compacted priorities | Low | This is defense-in-depth; F1's per-prompt injection is the primary mechanism |
| SessionStart `compact` doesn't fire in exercise runs | Medium | Exercise runs are single-turn (`-p` mode) — no compaction occurs. This fix targets multi-turn production sessions, not exercise runs |

---

## Out of Scope

### Approaches Considered and Rejected

| Approach | Why Rejected | Reference |
|---|---|---|
| **Prompt-based PreToolUse hook** (`type: "prompt"`) to evaluate each tool call with an LLM | Adds ~2-3s latency per tool call (Haiku inference). The current command hook achieves the same blocking in ~10ms. The cost exceeds the benefit given that F1 should reduce the number of violations reaching the PreToolUse layer. | hooks-reference.md §Prompt-based hooks |
| **Skill-scoped hooks** (`hooks:` in SKILL.md frontmatter) | Hook execution ordering across scopes is not guaranteed (confirmed in prior proposals). A skill-scoped PreToolUse hook and the global skill-gate.sh fire for the same event with non-deterministic ordering. | hooks-reference.md §Hooks in skills and agents; prior proposal F2 investigation |
| **InstructionsLoaded `transformedContent`** to rewrite CLAUDE.md at load time | The instruction content is adequate — the problem is timing (when the model sees it relative to tool planning), not content. Rewriting CLAUDE.md doesn't change when it's processed. | hooks-reference.md §InstructionsLoaded |
| **Stop hook** for retroactive correction | Fires after Claude finishes responding — too late to prevent violations within a turn. | hooks-reference.md §Stop |
| **`transformedPrompt`** to prefix every user prompt | Modifies the user's actual prompt text. This is invasive and could interfere with the model's understanding of the query. `additionalContext` is the correct mechanism — it adds context alongside the prompt without modifying it. | hooks-reference.md §UserPromptSubmit decision control |
| **Keyword-based skill routing** in UserPromptSubmit | Fragile (keyword list drifts from skill set), slow (pattern matching ~50 skills), and redundant (model already has skill descriptions in context). The problem is ordering, not identification. | — |
| **Additional CLAUDE.md prompt changes** | Three iterations of prompt-level changes produced no measurable improvement (53% → 66% → 68%). The prior proposal concluded: "prompt-level approaches have reached their ceiling." | SKILL_GATE_TOOLSEARCH_AND_ROUTING.md §Executive Summary |

### Items Deferred

- **Exercise runner registration of production hooks**: The exercise runner currently replaces hook events with absolute-path equivalents (exercise-runner.py lines 480-506). A future proposal could refactor the runner to merge production hooks rather than replace them, ensuring parity between exercise and production environments. Not blocking — the same scripts are used in both paths.
- **Violation rate below 15%**: The target for this proposal is <30%. Achieving <15% may require mechanisms beyond what the current SKILLSSKILLS hooks API supports (e.g., auto-invocation of the Skill tool from a hook, which is not possible per hooks-reference.md §PreToolUse decision control).

---

## Implementation Plan

F1 and F2 are independent.

```
Phase 1 (parallel):
  F1: Modify skill-enforcer.sh else branch              [Low effort, ~10 lines]
  F2: Add SessionStart compact hook to settings.json     [Low effort, ~5 lines]

Phase 2:
  F1-production: Register UserPromptSubmit hooks in      [Low effort, ~10 lines]
    .claude/settings.json for non-exercise sessions

Phase 3 (validation):
  Re-run exercise suite with same config:
  --explicit --filter NONE --parallel 5 --timeout 920
```

### Success Criteria

| Metric | Current (20260312-163457) | Target |
|--------|--------------------------|--------|
| Skill-gate violations | 32/47 (68%) | <14/47 (<30%) |
| Queries with 2+ blocked calls before recovery | ~5 (killmail-q1 etc.) | 0 |
| Mean duration | 52.8s | <45s |
| Total wasted tool calls from violations | ~40-50 | <15 |
| Net correctness | 47/47 (100%) | 47/47 (100%) — no regression |

**Note on the violation target:** Some violations will persist. The model may still attempt ToolSearch before Skill even with the per-prompt reminder — `additionalContext` influences but does not deterministically control tool ordering. The target of <30% reflects the expectation that per-prompt injection at decision time will significantly outperform static instructions, but will not eliminate violations entirely. Eliminating violations would require a mechanism to auto-invoke the Skill tool from a hook, which the SKILLSSKILLS hooks API does not support.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| F1: Model ignores per-prompt `additionalContext` | Medium | The slash-command path (same mechanism, same script) is proven effective. The risk is that generic reminders are less effective than skill-specific ones. Fallback: layers 3-4 (ToolSearch/MCP gating) still catch violations. |
| F1: Unconditional injection creates context noise | Low | ~35 tokens per prompt; conditional phrasing allows self-filtering; ARIA sessions are predominantly skill-domain queries |
| F1: Hook adds latency to every prompt | Low | ~50ms total (python3 JSON parse + jq output). The existing slash-command path has identical cost. |
| F2: Compaction reminder conflicts with other SessionStart hooks | None | Different matcher group (`compact` vs. unmatched). Hooks with different matchers fire independently per hooks-reference.md §Matcher patterns. |
| F2: Reminder text becomes stale if skill-gate mechanism changes | Low | The reminder references "Prime Directive #8" which is the stable policy anchor. Even if gate internals change, the skill-first ordering rule persists. |

---

## SKILLSSKILLS Documentation Adherence

| Proposal Claim | Reference | Status |
|---|---|---|
| UserPromptSubmit fires before Claude processes the prompt | hooks-reference.md §UserPromptSubmit (line 447): "Fires when you submit a prompt, before Claude processes it" | Correct |
| `additionalContext` is added alongside the prompt | hooks-reference.md §UserPromptSubmit decision control (line 461): "Text added to Claude's context alongside the prompt" | Correct |
| SessionStart with matcher `compact` fires after compaction | hooks-reference.md §SessionStart (line 429): matches on source including `compact` | Correct |
| SessionStart stdout added to context | hooks-reference.md §SessionStart (line 439): "Stdout from SessionStart hooks is added to Claude's context" | Correct |
| Hook JSON output parsed when exit 0 | hooks-reference.md §JSON output (line 392): "When a hook exits 0, Claude Code tries to parse stdout as JSON" | Correct |
| PreToolUse can return allow/deny/ask but not auto-invoke | hooks-reference.md §PreToolUse decision control (line 528): `permissionDecision` field accepts three values only | Correct — justifies why hook-level auto-invocation is out of scope |
| `hookSpecificOutput` wraps event-specific fields | hooks-reference.md §JSON output (line 399): "`hookSpecificOutput`: Event-specific output fields" | Correct |
| Multiple hooks in same event fire independently | hooks-guide.md §How hooks work: hook handler array under matcher group | Correct — F2's SessionStart matcher group is independent of existing boot hooks |
