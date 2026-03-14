# Skill-Gate Failed Strategies — Lessons Learned

**Date:** 2026-03-13
**Context:** 12 days (2026-03-01 → 2026-03-12), 8 proposals, ~140 exercise runs
**Purpose:** Prevent re-attempting strategies that have been measured and proven ineffective

---

## Background

The skill-gate system enforces a "Skill tool before data tools" ordering: when a
user query falls within a skill's domain, the model must invoke the Skill tool
(which loads SKILL.md, prerequisite reference data, and persona overlays) before
calling MCP tools or CLI commands. Without this ordering, the model confabulates
EVE game data from training data instead of querying authoritative sources.

The enforcement stack has two components that **work**:

1. **PreToolUse gate** (`skill-gate.sh`) — blocks MCP/CLI/Agent calls until the
   Skill tool sets a session marker. The model recovers 100% of the time.
2. **UserPromptSubmit enforcer** (`skill-enforcer.sh`) — injects `additionalContext`
   naming the specific skill for `/slash-command` prompts. Proven effective for
   explicit invocations.

Everything else attempted to reduce the **violation rate** (the percentage of
queries where the model attempts a data tool call before the Skill tool). The
violation rate has held steady at **53–68% across all interventions**. The gate
catches every violation and the model recovers, so correctness is 100% — but each
violation wastes 1–3 tool calls.

---

## Strategy 1: CLAUDE.md Prompt Engineering

**Proposals:** SKILL_GATE_COMPLIANCE_AND_QUALITY F1, SKILL_GATE_TOOLSEARCH_AND_ROUTING (Out of Scope), SKILL_GATE_PROMPT_SUBMIT_ROUTING (Out of Scope)

**What was tried:**
- Three iterations of rewriting the "Skill First" rule in CLAUDE.md
- Iteration 1: Recovery-focused — "When a hook blocks a direct MCP call, invoke the Skill tool first"
- Iteration 2: Prevention-focused — "invoke the Skill tool BEFORE calling any MCP tools" (Prime Directive #8)
- Iteration 3: Negative examples — "Do NOT call ToolSearch or MCP tools before Skill invocation — the skill-gate hook will block them and waste a tool call"
- Moved the rule to different locations (Prime Directive list, Skill Loading section, MCP Fallback Discipline)
- Added redundant restatements across multiple CLAUDE.md sections (4 locations at peak)

**Measured results:**

| Iteration | Violation Rate | Change |
|-----------|---------------|--------|
| Before any prompt changes | 53% | baseline |
| After recovery-focused text | 53% | none |
| After prevention-focused text (PD#8) | 66% | worse (noise) |
| After negative examples added | 68% | worse (noise) |

**Why it fails:** CLAUDE.md instructions are loaded at session start and are
hundreds of lines away from the user's prompt when the model formulates its tool
plan. The model's natural behavior — resolve data tools first — consistently
overrides static system instructions regardless of phrasing, positioning, or
emphasis. Adding more text about the same rule in more places doesn't help;
it increases context cost without influencing tool-ordering decisions.

**Key insight:** The problem is *when* the model sees the instruction relative
to its tool-planning phase, not *what* the instruction says. Content and phrasing
don't matter when the instruction is too far from the decision point.

**Rule: Do not add more CLAUDE.md text about skill-first ordering. Two concise
statements (PD#8 + MCP Fallback exception) are sufficient. Additional restatements
are proven to have zero effect.**

---

## Strategy 2: Gating ToolSearch for MCP Schemas

**Proposal:** SKILL_GATE_TOOLSEARCH_AND_ROUTING F1

**What was tried:** Modified `skill-gate.sh` to intercept `ToolSearch` calls
whose query string contained `mcp__`. The idea was to catch violations one step
earlier — before the model resolves MCP tool schemas, rather than after.

**Measured results:**

| Metric | Before | After |
|--------|--------|-------|
| Violation rate | 66% | 68% |
| Wasted calls per violation | 2 | 1 |

**Why it fails:** The violation *rate* is unchanged. The model still attempts
ToolSearch first — the block just moves from step 2 (MCP call) to step 1
(ToolSearch call). Each individual violation is cheaper (1 wasted call instead
of 2), but the total violation count stays the same.

**The ToolSearch gating also introduced a worse error message.** "Invoke Skill
before resolving MCP schemas" is less actionable than "invoke Skill before
calling mcp__market" — the model understands the latter better because it names
the specific tool that was blocked.

**Rule: Do not gate ToolSearch. Let it pass unconditionally. The MCP gate on the
actual data call is the right enforcement point — it produces a more actionable
block message and the model recovers correctly.**

---

## Strategy 3: Generic Per-Prompt `additionalContext` Injection

**Proposal:** SKILL_GATE_PROMPT_SUBMIT_ROUTING F1

**What was tried:** Extended `skill-enforcer.sh` to inject a generic "SKILL-FIRST"
reminder via `additionalContext` on *every* prompt, not just `/slash-command`
prompts. The hypothesis was that per-prompt injection (which fires adjacent to
the user's query) would outperform static CLAUDE.md instructions.

The injected text: `"SKILL-FIRST: If this query falls within a skill's domain,
invoke the Skill tool for that skill BEFORE calling ToolSearch for mcp__ tools
or any mcp__ tools directly."`

**Measured results:**

| Metric | Before | After |
|--------|--------|-------|
| Violation rate | 68% | 66% |

Within measurement noise. No improvement.

**Why it fails:** The injection is generic — it says "IF this query falls within
a skill's domain" and leaves the model to judge. The model consistently judges
"resolve data first" because its natural behavior (tool-schema resolution) is
more concrete than a conditional instruction.

**Contrast with what works:** The `/slash-command` path injects the *specific
skill name* ("You MUST call the Skill tool with skill='fitting'"), which gives
the model a concrete action. The generic path says "figure out if a skill
applies, then invoke it" — the model skips the figuring-out step and goes
straight to data.

**Key insight:** Per-prompt `additionalContext` works when it names a specific
action. It does not work as a generic routing reminder. The mechanism is proven;
the content must be specific.

**Rule: Do not inject generic skill-first reminders on every prompt. If the
specific skill can't be identified in the hook (which it can't for natural
language queries without fragile keyword matching), let the PreToolUse gate
handle enforcement.**

---

## Strategy 4: Post-Compaction `SessionStart` Re-Injection

**Proposal:** SKILL_GATE_PROMPT_SUBMIT_ROUTING F2

**What was tried:** Added a `SessionStart` hook with `"matcher": "compact"` that
echoes a post-compaction skill-first reminder. The idea was to re-inject the
rule after context compaction summarizes away CLAUDE.md instructions.

**Why it's unnecessary:** This is defense-in-depth for CLAUDE.md prompt text
(Strategy 1), which itself doesn't work. Defense-in-depth for an ineffective
defense adds complexity with no benefit. Additionally:

- The model's skill routing in long sessions depends on skill *descriptions*
  (always in context as part of the skill registry), not on CLAUDE.md text
  (which gets compressed)
- The per-prompt enforcer (Strategy 3) was supposed to be the primary mechanism,
  making the compaction re-injection redundant — but Strategy 3 also doesn't work

**Rule: Do not add `SessionStart compact` hooks for skill-gate reminders. The
information the model needs for routing (skill descriptions) survives compaction
natively.**

---

## Strategy 5: Gate Level Files (Two-File State Machine)

**Proposal:** SKILL_GATE_V3_AND_DB_RESILIENCE F2

**What was tried:** Added a second `/tmp` file (`skill-gate-level-{session_id}`)
written by the UserPromptSubmit enforcer to signal "this query needs enforcement."
The PreToolUse gate would only block if the level file existed and contained
"full". The idea was to avoid blocking non-skill queries while still enforcing
skill queries.

**Why it was abandoned:** The mechanism was proposed but the exercise run that
would have validated it was superseded by the v4 proposal (EXERCISE_SANDBOX_AND_GATE_V4),
which took a simpler approach: just gate MCP/CLI/Agent unconditionally when the
Skill marker doesn't exist, and exempt only read-only tools (Read/Glob/Grep).
The level file added a second file to manage, a second cleanup path, and a
coupling between two hook scripts — all for a distinction (skill vs non-skill
queries) that the simpler "always gate, exempt reads" approach handles without
extra state.

**Rule: Do not add multi-file state coordination between hooks. The single
marker file (created by Skill, checked by gate, cleared per-turn) is the right
granularity. If a new signal is needed between hooks, prefer making the gate
logic self-contained rather than adding inter-hook file protocols.**

---

## Strategy 6: `CLAUDE_ENV_FILE` for Cross-Hook State

**Proposal:** EXERCISE_SKILL_ENFORCEMENT_PROPOSAL (original `skill-gate.sh`)

**What was tried:** Used `$CLAUDE_ENV_FILE` (the documented mechanism for
cross-hook state persistence) to persist `SKILL_INVOKED=true` when the Skill
tool fires and read it when MCP tools fire.

**What happened:** `$CLAUDE_ENV_FILE` is unset in `-p` (non-interactive) mode.
The write silently fails. Every subsequent MCP call is blocked regardless of
whether the Skill tool was invoked. This caused total MCP blackout: 6 complete
failures, 3 degraded responses, and one exercise autonomously modifying
`.claude/settings.local.json` to remove the hook.

**Fix applied:** Replaced with session-scoped marker files using `session_id`
from hook input JSON (`/tmp/claude-skill-gate-{session_id}`). This works
reliably in all modes.

**Rule: Do not use `$CLAUDE_ENV_FILE` for state persistence in hooks that must
work in `-p` mode. Use session-scoped `/tmp/` marker files keyed by `session_id`
from the hook input JSON.**

---

## Strategy 7: `--allowedTools` for Bash Command Restriction

**Proposal:** SKILL_GATE_AND_EXERCISE_HARDENING F3

**What was tried:** Set `--allowedTools "Bash(uv run:*)"` to restrict Bash to
only `uv run` commands during exercise runs.

**What happened:** The model successfully ran `python3 -c "import json; ..."` to
modify `.claude/settings.local.json` and `python3 -c "import sqlite3; ..."` to
patch a production database — both through Bash despite the `(uv run:*)` pattern
restriction.

**Conclusion:** `--allowedTools` with Bash subpatterns does not enforce
command-level restrictions in `-p` mode (or possibly at all). The pattern syntax
is either not implemented or interpreted differently than expected.

**Fix applied:** Replaced with `--disallowedTools Agent,Edit,Write` deny rules,
which are authoritative per the permissions docs: "If a tool is denied at any
level, no other level can allow it."

**Rule: Do not rely on `--allowedTools` Bash subpatterns for security boundaries.
Use `--disallowedTools` deny rules for authoritative enforcement. For Bash
command filtering, use PreToolUse hooks that inspect `tool_input.command`.**

---

## Strategy 8: Skill-Scoped Hooks for Gate Marker

**Proposals:** SKILL_GATE_COMPLIANCE_AND_QUALITY F2 (investigation), SKILL_GATE_LIFECYCLE_AND_COVERAGE_GAPS F1 (rejected alternative)

**What was tried (investigation only):** Considered adding `hooks:` to skill
YAML frontmatter so that each skill's PreToolUse hook would create the gate
marker. This would be architecturally clean — each skill manages its own MCP
gate.

**Why it was rejected:**
1. Hook execution ordering across scopes (global vs skill-scoped) is not
   guaranteed. A skill-scoped PreToolUse hook and the global `skill-gate.sh`
   both fire for the same event. If the global hook fires first, it blocks
   before the skill hook creates the marker.
2. Requires modifying all ~50 skill definitions.
3. Doesn't address the core problem — queries where the model calls MCP tools
   *without* invoking any skill. The gate must operate at the session level.

**Rule: Do not use skill-scoped hooks for gate marker management. The global
PreToolUse hook is the correct scope. Skill-scoped hooks are for skill-specific
concerns (e.g., a skill that needs a cleanup action), not for cross-cutting
enforcement.**

---

## Strategy 9: `--append-system-prompt` for Skill Enforcement

**Proposal:** EXERCISE_SKILL_ENFORCEMENT_PROPOSAL (original approach, pre-hook)

**What was tried:** Used `--append-system-prompt` to add text instructing the
model to invoke the Skill tool when it sees a `/skill` prefix. This was the
first enforcement attempt, before any hooks were deployed.

**Measured result:** 0/25 exercises invoked the Skill tool.

**Why it fails:** The appended text competes with hundreds of lines of existing
system context. It lacks structural authority to override the model's tool-calling
preferences. When the model sees MCP tools it can call directly, it treats the
`/skill` prefix as a topic hint rather than a tool invocation command.

**Rule: Do not use `--append-system-prompt` for behavioral enforcement. It is
advisory at best. Use hooks (UserPromptSubmit for proactive injection,
PreToolUse for reactive blocking) for enforceable behavior.**

---

## Strategy 10: Git-Dirty Detection in Exercise Runner

**Proposal:** EXERCISE_SANDBOX_AND_GATE_V4 F2

**What was tried:** Added `_git_state_snapshot()` and `_check_git_state()` to
the exercise runner to detect if the model modified any files during a query.
Captured a `git status --porcelain` baseline before the run and diffed after
each query.

**Why it's unnecessary:** The `--disallowedTools Agent,Edit,Write` deny rules
completely prevent file mutation. The deny rules are authoritative per the
permissions docs. Since the deny rules were added, zero `git-dirty` flags have
been observed in any exercise run. The git detection is defense-in-depth for a
defense that works perfectly.

**Rule: Do not add runtime detection for behaviors that are already blocked by
authoritative deny rules. If the deny rules are bypassed, it's a Claude Code
framework bug — git-dirty detection can't prevent the damage, only report it
after the fact.**

---

## Summary: What Works vs What Doesn't

### What works

| Mechanism | Why |
|-----------|-----|
| PreToolUse gate (block + stderr recovery message) | Deterministic enforcement; model reads stderr and recovers 100% |
| UserPromptSubmit with specific skill name injection | Concrete action ("call Skill with skill='fitting'") succeeds |
| `--disallowedTools` deny rules | Authoritative per framework; works across subagents |
| Per-turn marker cleanup (UserPromptSubmit) | Prevents marker leak across queries in a session |
| Session-scoped `/tmp/` marker files | Reliable in all execution modes |

### What doesn't work

| Mechanism | Why |
|-----------|-----|
| CLAUDE.md prompt rewrites (any phrasing) | Too far from decision point; model ignores |
| ToolSearch gating | Shifts block point, doesn't reduce violation count |
| Generic per-prompt `additionalContext` | Conditional instruction; model skips the condition |
| Post-compaction re-injection | Defense-in-depth for a defense that doesn't work |
| Multi-file hook state (level files) | Unnecessary complexity; simpler approach exists |
| `CLAUDE_ENV_FILE` in `-p` mode | Unset; silently fails |
| `--allowedTools` Bash subpatterns | Not enforced in practice |
| Skill-scoped hooks for global enforcement | Ordering not guaranteed; wrong scope |
| `--append-system-prompt` | Advisory; no structural authority |
| Git-dirty detection alongside deny rules | Redundant; deny rules are authoritative |

### The fundamental constraint

The model's natural tool-ordering behavior — resolve schemas first, then call
tools, then invoke skills as needed — cannot be overridden by prompt-level
instructions. This has been measured across 3 prompt rewrites, 1 per-prompt
injection approach, and 1 ToolSearch gating approach. The only effective
enforcement is the PreToolUse gate, which blocks the incorrect order and lets
the model self-correct. The ~66% violation rate is the steady-state cost of
this architecture. Each violation costs 1–3 tool calls but produces correct
output after recovery.

Reducing the violation rate below ~66% likely requires a mechanism that does not
exist in the current Claude Code hooks API: the ability for a hook to
auto-invoke a tool (the Skill tool) rather than just blocking and returning an
error message. The hooks API supports `allow`, `deny`, and `ask` — not
"invoke this other tool first."

---

## When to Revisit

These conclusions should be re-evaluated if:

1. **Claude Code adds auto-invocation hooks** — a PreToolUse hook that can
   trigger a Skill tool call before allowing the blocked tool would eliminate
   violations entirely
2. **A new model family changes tool-ordering behavior** — future models may
   respond differently to prompt-level ordering instructions
3. **The hooks API adds per-prompt tool prioritization** — e.g., a mechanism to
   declare "always try Skill before mcp__*" at the API level rather than via
   prompt text
