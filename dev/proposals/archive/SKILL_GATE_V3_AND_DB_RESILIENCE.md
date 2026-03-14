# Skill Gate v3: Full-Spectrum Enforcement & Database Resilience

**Status:** Proposed
**Date:** 2026-03-11
**Owner:** ARIA Development
**Scope:** `dev/scripts/hooks/skill-gate.sh`, `dev/scripts/hooks/skill-enforcer.sh`, `dev/scripts/hooks/skill-gate-cleanup.sh`, `dev/scripts/hooks/skill-gate-cleanup-turn.sh`, `dev/scripts/exercise-runner.py`, `src/aria_esi/store/market/database.py`, `.claude/skills/` (4 skill files)
**Related:** `dev/reviews/exercise-outputs/20260311-164654/REPORT.md`, `dev/reviews/exercise-outputs/20260311-164654/RECOMMENDATIONS.md`, `SKILL_GATE_AND_EXERCISE_HARDENING.md`, `EXERCISE_SKILL_ENFORCEMENT_PROPOSAL.md`

---

## Executive Summary

The 20260311-164654 exercise run — the F5 validation run from `SKILL_GATE_AND_EXERCISE_HARDENING.md` — achieved 100% completion (47/47) and zero infrastructure crashes. The skill-gate `CLAUDE_ENV_FILE` bug is fixed, MCP fallback discipline is working, and deny rules correctly protect infrastructure files from Edit/Write. However, **skill invocation remains at 26%** (9/35 eligible queries), far below the 90% target. Three confabulation incidents and one complete query derailment confirm that the skill pipeline is still being bypassed at scale.

**Root cause:** The skill gate only intercepts MCP tool calls (`mcp__.*`), but MCP is unavailable in this exercise configuration. The model bypasses MCP entirely, going `ToolSearch → "not found" → Bash (CLI fallback)`. Since `Bash` and `ToolSearch` are allowed pre-skill by the gate's Phase 2, the gate never fires. Additionally, a `{schema_version}` format-string bug in the market database caused cascading SDE failures across 8+ queries and triggered the killmail #15 derailment.

This proposal addresses four fixes and one validation run:

| # | Fix | Layer | Severity | Effort |
|---|-----|-------|----------|--------|
| F1 | Harden `_get_schema_version()` against corrupt values | Database | Critical | Low |
| F2 | Extend skill gate to intercept all non-read tools | Hook script | Critical | Low |
| F3 | Add Bash command guardrails for exercise runs | Hook script | High | Low |
| F4 | Add brevity constraints to 4 verbose skills | Skill definitions | Medium | Low |
| F5 | Validation re-run | Validation | High | Low |

### Relationship to Prior Proposals

This is the third iteration of skill gate enforcement:

| Proposal | Fix | Result |
|----------|-----|--------|
| `EXERCISE_SKILL_ENFORCEMENT_PROPOSAL` (2026-03-10) | UserPromptSubmit hook (`skill-enforcer.sh`) | Skill invocation: 0% → partial |
| `SKILL_GATE_AND_EXERCISE_HARDENING` (2026-03-11) | PreToolUse gate (`skill-gate.sh`), MCP fallback discipline, deny rules | Skill invocation: partial → 26%. MCP blackout fixed. |
| **This proposal** | Extend gate to all non-read tools, database resilience, Bash guardrails | Target: >80% |

The UserPromptSubmit hook (skill-enforcer.sh) and PreToolUse gate (skill-gate.sh) are both deployed and functioning correctly — the enforcer injects context, the gate creates/checks markers. The structural gap is that the gate **only blocks MCP tools**, while the model **avoids MCP entirely** when the MCP server is unavailable, using CLI via Bash instead. F2 closes this gap.

---

## F1: Harden `_get_schema_version()` Against Corrupt Values (Critical)

### Problem

`database.py:396` contains `'{schema_version}'` as a format placeholder in the `SCHEMA_SQL` string. The `_initialize_schema` method at line 583 correctly calls `.format(schema_version=SCHEMA_VERSION)`, so new databases get the correct integer value. However, if the database was ever initialized during the window when the placeholder existed but `.format()` wasn't yet applied (an intermediate development state), the literal string `'{schema_version}'` was persisted to the metadata table.

When `_get_schema_version()` reads this value, `int('{schema_version}')` raises `ValueError`, which is caught by the `sqlite3.OperationalError` handler and... isn't caught at all. `ValueError` is not `OperationalError`. The unhandled exception propagates up through every CLI command that touches the market database, causing cascading failures.

### Evidence

- 8+ queries failed with `invalid literal for int() with base 10: '{schema_version}'`
- Killmail #15 derailed entirely: the model diagnosed and attempted to fix `database.py` instead of analyzing the killmail
- Build-cost #43 ran a raw SQL `UPDATE` on the production database to patch the schema version
- The `git diff main` confirms the change from hardcoded `'8'` to `'{schema_version}'` (format placeholder) happened alongside the addition of `.format(schema_version=SCHEMA_VERSION)` in `_initialize_schema`

### Proposed Fix

**File:** `src/aria_esi/store/market/database.py`

Add `ValueError`/`TypeError` handling to `_get_schema_version()`:

```python
def _get_schema_version(self) -> int:
    """Get current schema version from metadata table."""
    conn = self._conn
    if conn is None:
        return 0

    try:
        row = conn.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            return 0
        try:
            return int(row["value"])
        except (ValueError, TypeError):
            # Corrupted value (e.g. unformatted template string '{schema_version}')
            logger.warning(
                "Invalid schema_version value %r in metadata; treating as 0",
                row["value"],
            )
            return 0
    except sqlite3.OperationalError:
        # metadata table doesn't exist yet
        return 0
```

Returning 0 triggers the full migration chain. This is safe because:
1. All migrations use `IF NOT EXISTS` guards for table/index creation
2. The `SCHEMA_SQL` executescript runs after migrations and overwrites the metadata row with the correct integer via `.format(schema_version=SCHEMA_VERSION)`
3. `_seed_core_scopes()` uses `INSERT OR IGNORE`, so re-seeding is idempotent

### Test

**File:** `tests/store/test_schema_version.py` (new)

```python
def test_get_schema_version_corrupt_string(tmp_path):
    """_get_schema_version returns 0 for non-integer stored values."""
    db = MarketDatabase(db_path=tmp_path / "test.db")
    db._conn.execute(
        "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)"
    )
    db._conn.execute(
        "INSERT INTO metadata (key, value) VALUES ('schema_version', '{schema_version}')"
    )
    db._conn.commit()
    assert db._get_schema_version() == 0


def test_get_schema_version_valid_integer(tmp_path):
    """_get_schema_version returns the stored integer value."""
    db = MarketDatabase(db_path=tmp_path / "test.db")
    db._conn.execute(
        "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)"
    )
    db._conn.execute(
        "INSERT INTO metadata (key, value) VALUES ('schema_version', '10')"
    )
    db._conn.commit()
    assert db._get_schema_version() == 10
```

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Returning 0 triggers unnecessary migration re-runs | Negligible | Migrations are idempotent. Re-running adds <100ms on startup. |
| Masking a real corruption issue | Low | The warning log entry flags the corrupt value for manual investigation. |

---

## F2: Extend Skill Gate to Intercept All Non-Read Tools (Critical)

### Problem

The current `skill-gate.sh` has a structural gap. Its Phase 2 allows all non-MCP tools unconditionally:

```bash
# Phase 2: Allow non-MCP tools unconditionally
if [[ "$TOOL_NAME" != mcp__* ]]; then
  exit 0
fi
```

When MCP is unavailable (as in the ESI:NONE exercise configuration), the model never calls MCP tools at all. It discovers MCP is unavailable via `ToolSearch`, then falls back to CLI via `Bash`. Both `ToolSearch` and `Bash` pass through Phase 2 unblocked. The gate never fires, and the Skill tool is never invoked.

This is confirmed by the tool traces: 26 queries show the pattern `ToolSearch("select:market") → "not found" → Bash("uv run aria-esi price ...")` with zero `Skill` tool calls.

### Root Cause

The gate was designed when MCP was expected to be the primary tool path. With MCP down, the entire enforcement mechanism is bypassed because the alternative path (CLI via Bash) is whitelisted.

### Proposed Fix

Replace the blanket non-MCP allowance with a targeted allowlist of tools required for the skill loading chain itself. Everything else is gated until the Skill marker exists.

**File:** `dev/scripts/hooks/skill-gate.sh`

```bash
#!/bin/bash
# PreToolUse hook: block tool calls until Skill tool has been invoked.
#
# Enforcement levels:
#   - "full": Block ALL non-read tools until Skill is invoked.
#             Set by skill-enforcer.sh when query matches a skill.
#   - unset:  No gating (non-skill queries, follow-up turns).
#
# Tools always allowed (needed for skill loading chain itself):
#   Read, Glob, Grep — file reading for SKILL.md and prerequisites
#
# Tools gated until Skill marker exists:
#   Bash, Agent, ToolSearch, mcp__*, WebFetch, WebSearch

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

# Validate session_id
if [[ -z "$SESSION_ID" || "$SESSION_ID" == "null" ]]; then
  exit 0
fi

MARKER="/tmp/claude-skill-gate-${SESSION_ID}"
LEVEL_FILE="/tmp/claude-skill-gate-level-${SESSION_ID}"

# Phase 1: Record Skill tool invocation
if [[ "$TOOL_NAME" == "Skill" ]]; then
  touch "$MARKER"
  exit 0
fi

# Phase 2: Always allow read-only tools (needed for skill loading)
case "$TOOL_NAME" in
  Read|Glob|Grep)
    exit 0
    ;;
esac

# Phase 3: If Skill has been invoked, allow everything
if [[ -f "$MARKER" ]]; then
  exit 0
fi

# Phase 4: Check gate level — only enforce when skill-enforcer set "full"
if [[ ! -f "$LEVEL_FILE" ]] || [[ "$(cat "$LEVEL_FILE")" != "full" ]]; then
  exit 0
fi

# Phase 5: Block — Skill tool has not been invoked for a skill-domain query
cat <<'REASON' >&2
BLOCKED: You MUST invoke the Skill tool before using other tools.

The user's query maps to a skill. Call the Skill tool first — it loads
SKILL.md, prerequisite reference data, and CLI fallback paths. Without it,
responses risk confabulation from training data.

Example: Skill(skill="price", args="How much is a Vexor?")

After the Skill tool completes, all tools (Bash, MCP, Agent, etc.) are
unblocked for this turn.
REASON
exit 2
```

The key change: Phase 2 now only allows `Read|Glob|Grep`. Phase 4 checks a gate level file written by `skill-enforcer.sh`. Phase 5 blocks with an actionable error message.

**File:** `dev/scripts/exercise-runner.py` — broaden PreToolUse matcher

The current exercise runner registers `skill-gate.sh` with matcher `"Skill|mcp__.*"` (line 400-402). This means the hook only fires for Skill and MCP tool calls — `Bash`, `Agent`, `ToolSearch`, and other tools never trigger the hook, so the new Phase 2-5 logic never executes for them. Per the Claude Code hooks reference, omitting the `matcher` field or using `""` matches all tool names.

Replace the PreToolUse registration block (lines 399-407):

```python
# Before:
gate_cmd = str(HOOKS_DIR / "skill-gate.sh")
merged["hooks"]["PreToolUse"] = [
    {
        "matcher": "Skill|mcp__.*",
        "hooks": [
            {"type": "command", "command": gate_cmd},
        ],
    },
]

# After:
gate_cmd = str(HOOKS_DIR / "skill-gate.sh")
merged["hooks"]["PreToolUse"] = [
    {
        "hooks": [
            {"type": "command", "command": gate_cmd},
        ],
    },
]
```

Removing the `matcher` field makes the gate fire for every tool call. The script's internal Phase 2 (`case` statement) handles the allowlist — `Read|Glob|Grep` pass through without hitting the filesystem for level/marker files.

**File:** `dev/scripts/hooks/skill-enforcer.sh` — add gate level persistence

Insert the level file write inside the skill-match conditional, between the existing `rm -f` block and the `jq -n` output. Context from the current file (lines 30-35):

```bash
    # Clear stale marker so the Skill tool's PreToolUse re-creates it fresh
    if [[ -n "$session_id" && "$session_id" != "null" ]]; then
      rm -f "/tmp/claude-skill-gate-${session_id}"
+     echo "full" > "/tmp/claude-skill-gate-level-${session_id}"
    fi

    jq -n --arg skill "$skill_name" '{
```

The level file write goes inside the existing `session_id` guard (line 31), immediately after the `rm -f` (line 32). No new `if` block needed — the guard already validates `session_id`. This is inside the outer `if [[ "$prompt" =~ ^/([a-z][a-z0-9-]*) ]]` block (line 27), so the level file is only created for skill-prefixed prompts.

**File:** `dev/scripts/hooks/skill-gate-cleanup.sh` — add level file cleanup

Insert after the existing `rm -f` on line 6. Context from the current file (lines 5-8):

```bash
if [[ -n "$SESSION_ID" && "$SESSION_ID" != "null" ]]; then
  rm -f "/tmp/claude-skill-gate-${SESSION_ID}"
+ rm -f "/tmp/claude-skill-gate-level-${SESSION_ID}"
fi
```

**File:** `dev/scripts/hooks/skill-gate-cleanup-turn.sh` — add level file cleanup

Insert after the existing `rm -f` on line 7. Context from the current file (lines 6-8):

```bash
if [[ -n "$SID" && "$SID" != "null" ]]; then
  rm -f "/tmp/claude-skill-gate-${SID}"
+ rm -f "/tmp/claude-skill-gate-level-${SID}"
fi
```

Note: the variable is `$SID` in this file (not `$SESSION_ID`). The implementing agent must use `$SID` to match the existing code.

### Hook Ordering: UserPromptSubmit Registration

The exercise runner (lines 395-398) already registers `skill-gate-cleanup-turn.sh` before `skill-enforcer.sh` in the `UserPromptSubmit` array:

```python
merged["hooks"]["UserPromptSubmit"] = [
    {"hooks": [{"type": "command", "command": cleanup_cmd}]},  # cleanup first
    {"hooks": [{"type": "command", "command": hook_cmd}]},      # enforcer second
]
```

Per the Claude Code hooks reference, matcher groups under the same event fire in array order. This ordering is correct: cleanup clears stale state, then the enforcer sets the level file for the current turn. Do not reorder these entries.

### Why Gate Level Files Instead of Gating Everything

Gating all non-read tools unconditionally would break non-skill queries (e.g., general coding questions, git operations). The two-file approach lets the `UserPromptSubmit` hook (skill-enforcer.sh) signal to the `PreToolUse` hook (skill-gate.sh) that this particular query needs enforcement. Non-skill prompts don't create the level file, so the gate doesn't fire.

Per the Claude Code hooks reference, `UserPromptSubmit` fires before `PreToolUse`. This ordering is guaranteed: the prompt is submitted, the UserPromptSubmit hook writes the level file, then Claude processes the prompt, and each tool call triggers PreToolUse which reads the level file.

### Design Decision: File-Based State vs `CLAUDE_ENV_FILE`

The prior proposal (`SKILL_GATE_AND_EXERCISE_HARDENING.md`) documented that `CLAUDE_ENV_FILE` is unreliable in `-p` mode. The session-scoped marker file approach (using `session_id` from hook input JSON) was validated in the current run — the marker file mechanism works correctly. F2 extends this pattern with a second file for the gate level.

Per the Claude Code hooks reference, every hook receives `session_id` in its JSON input. This is documented, reliable, and unique per `claude -p` invocation. Parallel exercise runs use separate session IDs, so marker files don't collide.

### Test

1. Verify the generated `.claude/settings.local.json` has no `matcher` field on the PreToolUse entry (or uses `""`) — confirming the gate fires for all tools.
2. Run a single skill exercise:
   ```bash
   uv run python dev/scripts/exercise-runner.py --explicit --skills price --filter NONE --timeout 120
   ```
3. Verify in `tools.json`: `Skill` call appears BEFORE any `Bash` or `ToolSearch` call
4. Verify the response contains price data (not "invoke skill first" error text)
5. Run a non-skill query to verify the gate doesn't fire:
   ```bash
   echo "What is 2+2?" | claude -p
   ```

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Broadened matcher causes gate to fire on every tool call | Low | Phase 2 (`case` statement) exits immediately for `Read\|Glob\|Grep` without filesystem checks. Phase 1 handles `Skill`. All other tools hit Phase 3-5 which read two small files — negligible latency. |
| Gate blocks legitimate tool calls | Medium | Only fires when level file contains "full", which is only written for `/skill` prefixed prompts. Non-skill prompts unaffected. |
| Model loops on the block message | Low | Block message includes an explicit example of the correct Skill tool call. The skill-enforcer's `additionalContext` provides the same guidance pre-emptively. |
| Read/Glob/Grep allowlist too narrow | Low | These are the only tools needed for skill loading (reading SKILL.md and prerequisite files). If a skill's loading chain needs other tools, add them to the Phase 2 case statement. |
| Level file race between UserPromptSubmit and PreToolUse | None | UserPromptSubmit fires before Claude processes the prompt. PreToolUse fires during processing. The level file is always written before it's read. |
| UserPromptSubmit hook ordering (cleanup vs enforcer) | None | Exercise runner registers cleanup-turn before enforcer in the array (lines 396-397). Per hooks reference, matcher groups fire in array order. |

---

## F3: Add Bash Command Guardrails for Exercise Runs (High)

### Problem

The exercise runner's deny rules (from `SKILL_GATE_AND_EXERCISE_HARDENING.md` F3) correctly block `Edit` and `Write` to infrastructure files. However, build-cost #43 bypassed this by running ad-hoc Python via `Bash` to execute a raw SQL `UPDATE` on the production database:

```bash
uv run python -c "
import sqlite3
...
conn.execute(\"UPDATE metadata SET value = '10' WHERE key = 'schema_version'\")
"
```

Killmail #15 similarly attempted to edit `database.py` via `Edit` (which was blocked), then spent its remaining tool budget on diagnosis. While F1 fixes the root cause (the `{schema_version}` bug), a guardrail is still needed to prevent the model from modifying persistent state during exercise runs.

### Evidence

From `43-build-cost-q1.tools.json`: the model ran 6 `Read` calls on `database.py`, 1 `Edit` (blocked), then a `Bash` command with inline Python that modified the production SQLite database. The subsequent `aria-esi build-cost` call succeeded because the schema version was now correct — but the database was modified as a side effect of an exercise query.

### Proposed Fix

Add a `PreToolUse` hook on `Bash` that blocks dangerous command patterns during exercise runs.

**File:** `dev/scripts/hooks/exercise-bash-guard.sh` (new)

```bash
#!/bin/bash
# PreToolUse hook (Bash matcher): block dangerous commands during exercise runs.
#
# Blocks:
# - sqlite3 commands (direct database modification)
# - python -c with sqlite/aria_esi imports (ad-hoc database access)
# - Direct file writes to src/ or .claude/ via shell (echo >>, tee, etc.)
#
# Allows:
# - uv run aria-esi ... (CLI fallback commands)
# - uv run python dev/scripts/... (exercise infrastructure)
# - All other safe commands

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Block direct sqlite3 invocations
if echo "$COMMAND" | grep -qE '^\s*sqlite3\b'; then
  echo "Exercise mode: direct sqlite3 access is not permitted. Use CLI commands (aria-esi ...) for data queries." >&2
  exit 2
fi

# Block inline Python that imports sqlite3 or aria_esi modules
if echo "$COMMAND" | grep -qE 'python3?\s+-c' && \
   echo "$COMMAND" | grep -qE '(import\s+sqlite3|from\s+aria_esi|\.execute\()'; then
  echo "Exercise mode: ad-hoc Python with database access is not permitted. Use CLI commands (aria-esi ...) for data queries." >&2
  exit 2
fi

# Block shell writes to source or config directories
if echo "$COMMAND" | grep -qE '(>\s*|tee\s+)(src/|\.claude/)'; then
  echo "Exercise mode: writing to source or config files is not permitted." >&2
  exit 2
fi

exit 0
```

**File:** `dev/scripts/exercise-runner.py` — register the hook

In the hook setup block (around line 399), add after the existing `PreToolUse` entry:

```python
# Add Bash guard for exercise safety
bash_guard_cmd = str(HOOKS_DIR / "exercise-bash-guard.sh")
merged["hooks"]["PreToolUse"].append(
    {
        "matcher": "Bash",
        "hooks": [
            {"type": "command", "command": bash_guard_cmd},
        ],
    },
)
```

Per the Claude Code hooks reference, multiple matcher groups under the same event fire independently. A `Bash` matcher and a `Skill|mcp__.*` matcher coexist without interference. Each matcher evaluates its own hook handler.

### Why Not Remove Bash from ALLOWED_TOOLS

Removing `Bash` entirely would break CLI fallback (`uv run aria-esi route ...`), which is the primary data path when MCP is unavailable. The guardrail approach preserves CLI access while blocking the specific dangerous patterns observed in the exercise run.

### Test

1. `chmod +x dev/scripts/hooks/exercise-bash-guard.sh`
2. Simulate a blocked command:
   ```bash
   echo '{"tool_input":{"command":"python3 -c \"import sqlite3; ...\""}}'  | dev/scripts/hooks/exercise-bash-guard.sh
   # Should exit 2 with error message
   ```
3. Simulate an allowed command:
   ```bash
   echo '{"tool_input":{"command":"uv run aria-esi price Vexor"}}' | dev/scripts/hooks/exercise-bash-guard.sh
   # Should exit 0
   ```

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Regex false positives on legitimate commands | Low | Patterns are specific: `sqlite3` binary, `python -c` with `import sqlite3`, shell redirects to `src/` or `.claude/`. Normal CLI commands don't match. |
| Model circumvents via alternative command syntax | Low | F1 fixes the root cause (`{schema_version}` bug). Without the cascading SDE failures, the model has no motivation to patch the database. The guardrail is defense-in-depth. |
| Hook only active during exercise runs | By design | Registered via `.claude/settings.local.json` which is managed by the exercise runner and cleaned up afterward. |

---

## F4: Add Brevity Constraints to Verbose Skills (Medium)

### Problem

6 of 47 queries exceeded the 30-line brevity limit (per the `Brevity Protocol` in CLAUDE.md and `.claude/rules/skills.md`). The worst offenders:

| # | Skill | Lines | Over by | Root cause |
|---|-------|-------|---------|------------|
| 01 | help | 64 | 34 | Full command table with description column |
| 36 | exploration | 58 | 28 | Unnecessary "LORE CONTEXT" section |
| 08 | fitting | 52 | 22 | EFT + tactical notes + upgrade path |
| 43 | build-cost | 49 | 19 | Per-material BOM table + profitability |
| 25 | threat-assessment | 45 | 15 | Boxed assessment with mitigations |
| 21 | orient | 43 | 13 | Three-table display (borderline) |

Per `.claude/rules/skills.md`, skills can declare `preferred_max_lines` in frontmatter to override the global 30-line default, with up to 50% overage for complex queries. The `help` skill declares `preferred_max_lines: 80` which is too generous — the model treats it as a ceiling, not a target. The other three offenders do not declare this field, so the 30-line default applies with a soft ceiling of 45 lines.

### Proposed Fix

Add output format constraints and `preferred_max_lines` to the 4 worst offenders. #25 and #21 are borderline (within the 50% overage for complex queries) and don't need changes.

**Skill: `help`** — `.claude/skills/help/SKILL.md`

The skill already has category-based grouping, "Target ~25 lines" in the output constraints, and `preferred_max_lines: 80`. The 64-line output in the exercise run indicates the model ignored the existing "~25 lines" target because the `preferred_max_lines` ceiling of 80 provided too much headroom. Fix: lower the ceiling to align with the existing target.

Change frontmatter:

```yaml
# Before:
preferred_max_lines: 80

# After:
preferred_max_lines: 30
```

No other changes to `help/SKILL.md` — the existing "Command Listing Format" section already specifies category headers with short descriptions, which is the correct compact format. The `skill-listing.md` prerequisite file is injected via `!`command`` syntax and is compatible with the lower line budget.

**Skill: `exploration`** — `.claude/skills/exploration/SKILL.md`

Add to the existing instructions:

```markdown
Do NOT include lore, background, or flavor text. Focus exclusively on:
- Container types and hack difficulty
- Expected loot and ISK estimate
- Hacking tactics (utility node priority, target nodes)
- Threats and safety notes

"LORE CONTEXT" sections have zero tactical value and waste response space.
```

And add frontmatter:

```yaml
preferred_max_lines: 35
```

**Skill: `fitting`** — `.claude/skills/fitting/SKILL.md`

Add to the output format section:

```markdown
Default response: EFT block + 3-5 lines of tactical notes.
Do NOT include upgrade paths, training recommendations, or alternative fits unless explicitly requested.
```

And add frontmatter:

```yaml
preferred_max_lines: 35
```

**Skill: `build-cost`** — `.claude/skills/build-cost/SKILL.md`

Add to the output format section:

```markdown
Default response: summarize BOM as category totals (Minerals, Components, etc.), not per-material rows.
Only show per-material breakdown when the user explicitly requests "full BOM", "detailed materials", or similar.
Include profitability summary (cost, sell price, margin) in 3-4 lines.
```

And add frontmatter:

```yaml
preferred_max_lines: 30
```

### Why Skill-Level Constraints Instead of Global Enforcement

The brevity protocol in CLAUDE.md sets a global 30-line target. The `.claude/rules/skills.md` adds `preferred_max_lines` as a per-skill override mechanism. The problem isn't that the model doesn't know about brevity — it's that specific skills produce inherently data-dense output (BOM tables, command listings, site analysis) where the model defaults to maximum detail. Skill-level constraints tell the model *how* to be brief for each output format.

Per the Claude Code skills documentation, skill content is "instructions Claude follows when the skill is invoked." Output format constraints in SKILL.md are the correct place for this guidance — they load when the skill is invoked and apply only to that skill's output.

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Constraints too restrictive for complex queries | Low | `preferred_max_lines` is a soft target per `.claude/rules/skills.md` (up to 50% overage allowed). Complex queries like multi-item BOM or multi-system route can exceed. |
| Model ignores the constraints | Medium | This is the same prompt-following challenge as all SKILL.md instructions. The constraints are clear and specific. If still violated, consider a PostToolUse hook that counts lines. |

---

## F5: Validation Re-Run (High)

### Prerequisite

F1 (database resilience) and F2 (gate extension) must be deployed. F3 is recommended but not blocking.

### Purpose

Establish a clean baseline with the extended skill gate:
1. Confirm skill invocation rate exceeds 80% (up from 26%)
2. Confirm `{schema_version}` errors are eliminated
3. Verify Bash guardrails prevent database modification
4. Measure brevity compliance improvement from F4

### Configuration

```bash
uv run python dev/scripts/exercise-runner.py \
  --explicit \
  --filter NONE \
  --parallel 5 \
  --timeout 920
```

Same configuration as the 20260311-164654 run for comparison.

### Success Criteria

| Metric | Current (20260311-164654) | Target |
|--------|--------------------------|--------|
| Skill invocation rate | 9/35 (26%) | >28/35 (80%) |
| `{schema_version}` errors | 8+ queries | 0 |
| Query derailments (no user data) | 1 (#15) | 0 |
| Database modifications | 1 (#43) | 0 |
| Brevity compliance | 41/47 (87%) | >44/47 (94%) |
| Confabulation incidents | 3 | 0-1 |

---

## Implementation Plan

F1, F3, and F4 are independent. F2 depends on understanding the hook file interaction but is otherwise independent. F5 depends on F1 and F2.

```
Phase 1 (parallel):
  F1: Harden _get_schema_version()                    [1 file + 1 test file]
  F2: Extend skill-gate.sh + update enforcer/cleanup   [4 hook files + exercise-runner.py matcher]
  F3: Add exercise-bash-guard.sh + register in runner  [1 new file + ~5 lines in runner]
  F4: Add brevity constraints to 4 SKILL.md files      [4 skill files]

Validation (after Phase 1):
  F5: Re-run exercise suite                            [~1 hour runtime]
```

### Recommended Priority Order

**F1 → F2 → F3 → F4 → F5**

F1 is the only code change to production source (store/market/database.py). F2 is the highest-impact exercise improvement. F3 is defense-in-depth. F4 is low-risk, low-effort. F5 validates all of them.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| F2: Gate blocks Skill tool's own Read calls | None | Read/Glob/Grep are in the Phase 2 allowlist. The Skill tool triggers Read calls for SKILL.md and prerequisites — these are allowed. |
| F2: Gate level file persists across parallel exercises | None | Each `claude -p` invocation has a unique `session_id`. Level files are session-scoped (`/tmp/claude-skill-gate-level-{session_id}`). |
| F2: Broadened matcher adds latency to every tool call | Negligible | Phase 2 case statement exits immediately for read tools. Phases 3-5 stat two small `/tmp` files — sub-millisecond. |
| F2: Model fails to invoke Skill even after explicit block message | Medium | The block message includes a concrete example. The skill-enforcer's `additionalContext` provides a second instruction. If both fail, the query produces a blocked response rather than a confabulated one — a safer failure mode. |
| F3: Regex false positive blocks a legitimate CLI command | Low | The patterns target `sqlite3`, `python -c` with `import sqlite3`, and shell redirects to `src/` or `.claude/`. Normal `uv run aria-esi ...` commands don't match. |
| F4: Brevity constraints make responses too sparse for complex queries | Low | `preferred_max_lines` is a soft target with documented 50% overage allowance. Skills like `build-cost` that produce inherently tabular data will naturally exceed for multi-component items. |
| F1: Returning 0 triggers unnecessary migration re-runs | Negligible | Migrations are idempotent. Re-running adds <100ms. The warning log flags the issue for investigation. |

---

## Out of Scope

- **Confabulation regression tests** (R6 from RECOMMENDATIONS.md): Post-run quality gate that cross-references tool traces against output claims. Medium effort, deferred until F5 results show whether F2's skill enforcement reduces confabulation to acceptable levels.
- **Stop hook for derailment prevention** (R7 from RECOMMENDATIONS.md): Prompt-based Stop hook that validates response relevance. Adds latency and cost. Deferred until F2+F3 are validated — the gate (F2) prevents the derailment pattern by forcing Skill invocation, and the Bash guardrail (F3) prevents database modification. If derailments persist after F5, revisit.
- **Prerequisite injection expansion** (R4 from RECOMMENDATIONS.md): Adding `!`command`` CLI syntax hints to skills without injected prerequisites. This is a valid optimization for eliminating the Agent bounce pattern but is orthogonal to the skill gate fix. The gate (F2) forces Skill invocation, which loads the SKILL.md including any CLI guidance. Injection expansion would be valuable for non-explicit (implicit/natural-language) queries where the Skill tool might not fire. Revisit after F5 shows implicit-mode results.
- **`no-skill-ok` classification accuracy**: The current `no-skill-ok` flag assumes that skills with `injected_prerequisites` produce acceptable output without Skill invocation. This is overly generous — `!`command`` injection only runs when the Skill tool is invoked. The 12 `no-skill-ok` exercises likely answered from training data, not from injected reference files. However, since F2 should increase invocation rate to >80%, the `no-skill-ok` population will shrink and the accuracy question becomes less important.
- **`--allowedTools` Bash pattern enforcement investigation**: Exercise 15 in the prior run executed `python3 -c "..."` despite `ALLOWED_TOOLS` specifying `Bash(uv run:*)`. Whether `--allowedTools` enforces Bash subpatterns in `-p` mode remains unresolved. F3's hook-based Bash guardrail makes this investigation lower priority.
