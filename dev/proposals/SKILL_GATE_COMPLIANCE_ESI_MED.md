# Proposal: Skill-Gate Compliance Hardening for ESI:MED Skills

**Date:** 2026-03-14
**Triggered by:** Exercise run `20260314-212723` — 6/14 skill-gate violations, 2 timeouts
**Report:** `dev/reviews/exercise-outputs/20260314-212723/REPORT.md`

---

## Problem Statement

ESI:MED skills (`fit-check`, `fit-budget`, `ship-next`, `isk-compare`) consistently fail skill-gate compliance. The model starts data gathering (CLI or MCP calls) *before* invoking the Skill tool, triggering `SKILL-GATE-BLOCK`. Recovery succeeds but wastes 30-60% of the time budget on blocked calls and duplicate re-fetching, causing 2 of 14 queries to timeout.

| Skill | Violations in run | Avg duration | Timed out? |
|-------|-------------------|-------------|------------|
| fit-check | 1/1 | 160s (timeout) | Yes |
| fit-budget | 1/2 | 160s (timeout) | Yes |
| ship-next | 2/2 | 136s | No |
| isk-compare | 2/2 | 104s | No |
| pilot | 0/2 | 16.7s | No |
| standings | 0/3 | 29.2s | No |
| clones | 0/2 | 13.2s | No |

Skills with clean invocations average **20s**. Skills with violations average **140s** — a 7x penalty.

### Root Cause Analysis

The model's pre-fetch impulse stems from two factors:

1. **No explicit routing hints** — The CLAUDE.md routing table only covers knowledge-only skills. ESI:MED skills with complex data needs aren't listed, so the model defaults to "gather data first, find the skill later."

2. **Opaque hook feedback** — The skill-gate hook's block message (`"Invoke the Skill tool for the relevant skill"`) doesn't name the skill. The model must infer the correct skill from context, costing an extra reasoning cycle.

---

## Proposed Changes

### Change 1: Expand CLAUDE.md routing hints table

**File:** `CLAUDE.md` (Routing Hints section)
**Mechanism:** Prompt-level routing (Claude Code built-in: skill descriptions loaded into context)
**Effort:** 5 minutes

Add ESI:MED skills that consistently violate the gate:

```markdown
### Routing Hints

Some queries map to knowledge-only skills that don't use MCP tools (so the skill-gate can't catch missed invocations). Always route these explicitly:

| User says | Invoke |
|-----------|--------|
| "what can you do", "help", "commands" | `/help` skill |
| "set up", "configure", "first time", "getting started" | `/first-run-setup` skill (alias: `/setup`) |
| "fit [ship] for abyssal", "abyssal fit" | `/abyssal` skill (not `/fitting`) |
| "watchlist", "war targets", "watch list" | No skill — use CLI directly |
| "brief me on [mission]", "what's the blitz for [mission]" | `/mission-brief` (intel-only default) |
| "fit for [mission]", "fitting for [mission]" | `/mission-brief --fit` or `/fitting` |
| "can I fly this fit", "check this fit", "fit requirements" | `/fit-check` |
| "budget fit", "make this cheaper", "downgrade fit" | `/fit-budget` |
| "what ship next", "upgrade path", "ship progression" | `/ship-next` |
| "best ISK", "ISK per hour", "compare money making" | `/isk-compare` |

Knowledge-only skills have no MCP calls to gate, so they rely on prompt-level routing rather than hook enforcement. ESI-dependent skills are also listed here because the skill-gate catches violations too late — after wasting time on blocked calls.
```

**Why this works:** The routing table is loaded at session start as part of CLAUDE.md. It gives the model explicit instructions before the first tool call, preventing the pre-fetch pattern entirely. This is the same mechanism that already works for `/help` and `/abyssal`.

### Change 2: Add skill-name hint to skill-gate block messages

**File:** `dev/scripts/hooks/skill-gate.sh`
**Mechanism:** PreToolUse hook with structured stderr (Claude Code: exit 2 stderr fed back to model)
**Effort:** 15 minutes

Currently the hook returns:
```
SKILL-GATE-BLOCK: Invoke the Skill tool for the relevant skill before calling mcp__aria-universe__fitting.
```

The model then has to infer which skill to invoke. Since the hook receives the full `tool_input` JSON, it can suggest specific skills based on MCP tool + action patterns:

```bash
# Phase 4: Block data tools — Skill not yet invoked
case "$TOOL_NAME" in
  Bash)
    COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
    if echo "$COMMAND" | grep -qE '(uv run )?aria-esi\b'; then
      if echo "$COMMAND" | grep -qE 'watchlist-|journal|sync-wars'; then
        exit 0
      fi
      # Suggest skill based on CLI subcommand
      SKILL_HINT=""
      if echo "$COMMAND" | grep -qE '\bskills\b'; then
        SKILL_HINT=" (try: /skillqueue, /fit-check, /ship-next, or /isk-compare)"
      elif echo "$COMMAND" | grep -qE '\bstandings\b'; then
        SKILL_HINT=" (try: /standings)"
      elif echo "$COMMAND" | grep -qE '\bwallet\b'; then
        SKILL_HINT=" (try: /fit-check, /fit-budget, or /ship-next)"
      elif echo "$COMMAND" | grep -qE '\bclones\b'; then
        SKILL_HINT=" (try: /clones)"
      fi
      echo "SKILL-GATE-BLOCK: Invoke the Skill tool for the relevant skill before using CLI.${SKILL_HINT}" >&2
      exit 2
    fi
    exit 0
    ;;
  mcp__aria-universe__fitting)
    echo "SKILL-GATE-BLOCK: Invoke the Skill tool for /fit-check or /fit-budget before calling fitting MCP." >&2
    exit 2
    ;;
  mcp__aria-universe__skills)
    echo "SKILL-GATE-BLOCK: Invoke the Skill tool for /skillqueue, /ship-next, or /isk-compare before calling skills MCP." >&2
    exit 2
    ;;
  mcp__aria-universe__market)
    echo "SKILL-GATE-BLOCK: Invoke the Skill tool for the relevant skill (/fit-check, /fit-budget, /price, /build-cost) before calling market MCP." >&2
    exit 2
    ;;
  mcp__*)
    # Generic MCP block for other tools
    echo "SKILL-GATE-BLOCK: Invoke the Skill tool for the relevant skill before calling ${TOOL_NAME}." >&2
    exit 2
    ;;
```

**Why this works:** The model receives specific skill names in the error message, reducing the inference step. Per Claude Code docs, exit code 2 stderr is "fed back to Claude" — so the model sees the suggestion directly. This doesn't prevent the violation (Change 1 does that) but accelerates recovery when it occurs.

### Change 3: Add `pilot_skills: "auto"` sentinel to fitting MCP tool

**File:** `src/aria_esi/commands/skills.py` (or the MCP fitting handler)
**Mechanism:** Server-side skill cache lookup
**Effort:** 30 minutes

The model passed `pilot_skills: "cached"` to `fitting(check_requirements)` and got a parse error. This is a reasonable expectation — the MCP server already has cached skills from `ensure-fresh`. Add support for sentinel values:

- `"auto"` — Look up cached skills from the most recent `ensure-fresh skills` run
- `"cached"` — Alias for `"auto"`

When `pilot_skills` is `"auto"`, the fitting tool reads from the local skills cache file, constructs the skill dict internally, and proceeds as if it were passed inline. This eliminates one round-trip per fit-check call.

**Why this works:** The fitting MCP tool already has access to the local filesystem. The skills cache is written by `ensure-fresh skills`. Reading it server-side avoids the model needing to fetch skills via CLI, parse the output, and pass it as a giant JSON blob.

---

## Changes NOT Proposed

### UserPromptSubmit hook for skill routing

A `UserPromptSubmit` hook could analyze the user's prompt and inject `additionalContext` like "This query maps to /fit-check. Invoke the Skill tool first." However:

- The Claude Code docs show `UserPromptSubmit` hook input contains the `prompt` field but no tool calling context
- A prompt-type hook would add latency to every user message, not just skill-relevant ones
- The routing hints table (Change 1) achieves the same effect with zero runtime cost

### Skill-scoped hooks via frontmatter

Claude Code supports `hooks:` in skill frontmatter, scoped to the skill's lifecycle. This doesn't help because the problem is that the skill hasn't been invoked yet — lifecycle-scoped hooks only run while the skill is active.

### Increasing exercise runner timeout

Increasing timeout from 160s to 240s for fitting skills would mask the root cause. The 7x duration penalty (20s clean vs 140s violated) shows the real fix is preventing violations, not tolerating them. After Changes 1-2 land, re-evaluate whether the base timeout needs adjustment.

---

## Validation Plan

1. **Re-run the same 14 queries** from `SKILL_EXERCISE_QUERIES.md` with the ESI:MED filter after applying Changes 1-3
2. **Success criteria:**
   - Skill-gate violations: 0/14 (currently 6/14)
   - Timeouts: 0/14 (currently 2/14)
   - Avg duration for fit-check/fit-budget: under 60s (currently timeout at 160s)
3. **Track regression:** pilot, standings, clones should remain clean (currently 0 violations)

---

## Implementation Order

| Priority | Change | Effort | Expected Impact |
|----------|--------|--------|-----------------|
| 1 | Routing hints expansion (Change 1) | 5 min | Prevents 6/6 violations |
| 2 | Hook hint messages (Change 2) | 15 min | Accelerates recovery if violations still occur |
| 3 | `pilot_skills: "auto"` (Change 3) | 30 min | Eliminates 1 error cycle per fit-check call |

Changes 1-2 are prompt/hook only — no Python code changes, no test changes needed. Change 3 touches the MCP handler and needs a unit test for the sentinel parsing.

---

## Appendix: Claude Code Mechanisms Referenced

| Mechanism | Documentation | How Used |
|-----------|--------------|----------|
| Routing hints in CLAUDE.md | Skills docs: "Description always in context" | Change 1: explicit routing before first tool call |
| PreToolUse exit 2 stderr | Hooks ref: "Exit 2: blocking error. Stderr fed back to Claude" | Change 2: include skill name in block message |
| Skill descriptions budget | Skills docs: "2% of context window" | Existing: descriptions for 50 skills fit within budget |
| Matcher patterns for MCP | Hooks ref: "`mcp__memory__.*` matches all tools from the memory server" | Change 2: MCP-tool-specific skill suggestions |
