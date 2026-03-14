# Exercise Sandbox Hardening & Skill Gate v4

**Status:** Proposed (revised 2026-03-12 — resolves readiness reviews 2026-03-11-2125, 2026-03-12-0052, 2026-03-12-0101, 2026-03-12-0111)
**Date:** 2026-03-11
**Owner:** ARIA Development
**Scope:** `dev/scripts/exercise-runner.py`, `dev/scripts/hooks/skill-gate.sh`, `CLAUDE.md`, `.claude/skills/{build-cost,orient,reactions,threat-assessment,exploration}/SKILL.md`
**Related:** `dev/reviews/exercise-outputs/20260311-192927/REPORT.md`, `dev/reviews/exercise-outputs/20260311-192927/RECOMMENDATIONS.md`, `SKILL_GATE_V3_AND_DB_RESILIENCE.md`, `SKILL_GATE_AND_EXERCISE_HARDENING.md`

---

## Executive Summary

The 20260311-192927 exercise run achieved 100% completion (47/47) and 100% data accuracy — a strong result. However, two critical failures reveal that the exercise sandbox is not airtight: the model **edited production source code** during a test query, and the **skill gate was bypassed in 15 of 47 queries** (68% compliance vs 100% target).

Both critical failures trace to the same root cause: the **Agent tool**. Subagents inherit the full tool set regardless of the parent session's `--allowedTools` restriction, and subagent tool calls don't fire the parent's `PreToolUse` hooks. The Agent tool is therefore a bypass vector for both the Edit/Write sandbox and the skill-gate enforcement.

This proposal covers six fixes across two categories:

**Category A — Exercise Sandbox Integrity**

| # | Fix | Layer | Severity | Effort |
|---|-----|-------|----------|--------|
| F1 | Block Agent tool in exercise runs | Exercise runner | Critical | Low |
| F2 | Assert clean git state around queries | Exercise runner | High | Low |

**Category B — Skill Gate Enforcement**

| # | Fix | Layer | Severity | Effort |
|---|-----|-------|----------|--------|
| F3 | Extend skill gate to cover Agent and Bash | Hook script | High | Medium |
| F4 | Add skill-first CLI fallback instruction | CLAUDE.md | High | Low |
| F5 | Cap tabular output in verbose skills | Skill definitions | Medium | Low |
| F6 | Add missing CLI fallbacks | CLI + docs | Medium | Medium |

The `{schema_version}` database bug (HIGH-1 from the report) is already patched in the working tree and is excluded from this proposal.

### Relationship to Prior Proposals

This is the fourth iteration of skill gate enforcement and the first to address exercise sandbox integrity as a distinct concern:

| Proposal | Key change | Skill compliance result |
|----------|-----------|------------------------|
| `EXERCISE_SKILL_ENFORCEMENT_PROPOSAL` | UserPromptSubmit hook (`skill-enforcer.sh`) | 0% → partial |
| `SKILL_GATE_AND_EXERCISE_HARDENING` | PreToolUse gate (`skill-gate.sh`), deny rules | partial → 26% |
| `SKILL_GATE_V3_AND_DB_RESILIENCE` | Proposed extending gate to all non-read tools | Not yet validated |
| **This proposal** | Block Agent in exercises, extend gate to Agent+Bash, git assertion | Target: >90% |

The v3 proposal identified the correct architectural gap (gate only intercepts MCP tools) but was written before the 20260311-192927 run confirmed the Agent bypass as the primary vector. This proposal supersedes v3's F2 (extended gate) with a more targeted approach that distinguishes exercise-time enforcement from production-time enforcement.

---

## F1: Block Agent Tool in Exercise Runs (Critical)

### Problem

The Agent tool is the root bypass vector for both critical issues in the report:

- **CRITICAL-1 (code mutation):** Query 43 (`build-cost-q1`) spawned an Agent subagent that invoked the Edit tool on `src/aria_esi/store/market/database.py`. The `--allowedTools` restriction on the parent session did not propagate to the subagent.
- **CRITICAL-2 (skill gate bypass):** 6 of 15 `no-skill` failures were caused by the model delegating MCP calls to Agent subagents, where the `PreToolUse` hook never fires.

**Why `--allowedTools` doesn't protect against this:**

The [subagents docs](https://code.claude.com/docs/en/sub-agents#available-tools) state: "By default, subagents inherit all tools from the main conversation, including MCP tools." The docs describe restricting subagent tools via the `tools` field (allowlist) or `disallowedTools` field (denylist) in the subagent definition — not via the parent's `--allowedTools` CLI flag. Empirically, query 43 confirmed this: the parent session's `--allowedTools` excluded Edit, yet the subagent used Edit successfully.

By contrast, `--disallowedTools` deny rules are authoritative across all levels. Per the [permissions docs](https://code.claude.com/docs/en/permissions#settings-precedence): "If a tool is denied at any level, no other level can allow it." Deny rules can also target specific subagent types using `Agent(name)` syntax ([permissions docs: Agent rules](https://code.claude.com/docs/en/permissions#agent-subagents)).

### Evidence

From `43-build-cost-q1.tools.json`:
- Index 0: `Agent` (spawned to call build-cost MCP)
- Indices 1–38: Bash, Read, Grep, Glob (subagent investigating the schema error)
- **Index 39: `Edit`** (subagent patching `database.py`)
- Indices 40–41: Bash (re-running CLI after patch)

### Proposed Fix

**File:** `dev/scripts/exercise-runner.py`

Add `Agent`, `Edit`, and `Write` to the `--disallowedTools` deny rules. The blanket `Edit` and `Write` denies are redundant with the `--allowedTools` allowlist but included because deny rules are the authoritative enforcement mechanism — per the [permissions docs](https://code.claude.com/docs/en/permissions#settings-precedence): "If a tool is denied at any level, no other level can allow it."

This block **replaces** the existing `deny_rules` list in `exercise-runner.py` (which currently contains only path-specific `Edit`/`Write` rules). The path-specific rules are retained as defense-in-depth in case the blanket denies are ever relaxed.

```python
deny_rules = [
    # Block subagent spawning — subagents bypass --allowedTools and
    # PreToolUse hooks, undermining both the edit sandbox and skill gate.
    "Agent",
    # Authoritative edit/write sandbox. Redundant with --allowedTools
    # allowlist, but deny rules take precedence across all levels including
    # subagents, so they are the reliable enforcement layer.
    "Edit",
    "Write",
    # Infrastructure protection (defense-in-depth against path-specific
    # bypass if the blanket deny is ever relaxed)
    "Edit(/.claude/settings*)",
    "Edit(/.claude/hooks/*)",
    "Write(/.claude/settings*)",
    "Write(/.claude/hooks/*)",
    "Edit(/dev/scripts/hooks/*)",
    "Write(/dev/scripts/hooks/*)",
]
```

### Why not also fix the hook?

The hook-based approach (F3) is valuable for production use but insufficient for exercise sandbox integrity:

1. Hooks are installed via `.claude/settings.local.json`, which could be overwritten by the model if Edit isn't denied
2. `SubagentStart` hooks ([hooks reference](https://code.claude.com/docs/en/hooks#subagentstart)) fire when a subagent spawns but "cannot block subagent creation" (can only return `additionalContext`). To prevent subagent creation, use either a `PreToolUse` hook on the parent's Agent invocation (exit 2 blocks the tool call) or a `--disallowedTools "Agent"` deny rule
3. The deny rule is simpler, more reliable, and directly addresses the root cause

### Verification

After applying F1, re-run query 43 and confirm:
- Agent tool is not in the tool trace
- Edit tool is not in the tool trace
- The model falls back to Skill → MCP or Skill → CLI without subagent delegation

---

## F2: Assert Clean Git State Around Queries (High)

### Problem

Even with F1 blocking Agent and Edit, defense-in-depth requires detecting any working tree mutation during an exercise run. The exercise runner currently has no git state assertion. The `--append-system-prompt` instruction telling the model git is up-to-date is informational, not enforced.

### Proposed Fix

**File:** `dev/scripts/exercise-runner.py`

Add pre-run baseline capture and per-query git state assertion:

```python
def _git_state_snapshot() -> str:
    """Capture git porcelain output for comparison.

    Raises subprocess.CalledProcessError on non-zero git exit to avoid
    masking failures as false-clean (empty stdout == empty baseline).
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, check=True, cwd=str(PROJECT_ROOT),
    )
    return result.stdout


def _check_git_state(label: str, baseline: str) -> str | None:
    """Return a quality flag if git state diverged from baseline."""
    current = _git_state_snapshot()
    if current != baseline:
        log.warning("git state changed after %s:\n%s", label, current)
        return "git-dirty"
    return None
```

Integrate into the run loop in `main()` (near line 783):

```python
    # -- just before the `if args.parallel <= 1:` branch (line 783) --
    baseline = _git_state_snapshot()

    # Run queries
    results = []
    if args.parallel <= 1:
        for seq, query in enumerate(filtered, 1):
            # ... existing print ...
            result = run_query(query, output_dir, seq, args.timeout, args.model, args.effort, args.explicit)
            git_flag = _check_git_state(f"{query['skill']}-q{query['query_num']}", baseline)
            if git_flag:
                result.setdefault("quality", []).append(git_flag)
            # ... existing print ...
            results.append(result)
    else:
        # Parallel execution
        # ... existing ThreadPoolExecutor setup ...
            for future in as_completed(futures):
                seq, query = futures[future]
                result = future.result()
                git_flag = _check_git_state(f"{query['skill']}-q{query['query_num']}", baseline)
                if git_flag:
                    result.setdefault("quality", []).append(git_flag)
                # ... existing print and append ...
```

Integration notes:
1. Capture `baseline = _git_state_snapshot()` once before the `if args.parallel <= 1:` branch (line 783)
2. After each query completes (both sequential and parallel paths), call `_check_git_state(query_label, baseline)`
3. If dirty, append `git-dirty` to the result's `quality` list for the **detecting query** (the query whose post-run check first observes the divergence). In parallel execution, this may not be the query that caused the mutation — but causal attribution would require per-query git snapshots (expensive) and is not worth the complexity. The detecting-query attribution is sufficient for post-hoc investigation: the MANIFEST timestamp plus `git log` identifies the actual mutation.
4. Do not abort — remaining queries should still run
5. Include the `git-dirty` flag in the MANIFEST quality column and the summary scorecard

### Why flag rather than abort?

The exercise runner runs 47+ queries in parallel. Aborting the entire run on the first mutation wastes the other workers' progress. Flagging allows post-hoc analysis: which query mutated state, what changed, and whether it affected subsequent queries.

### Unit Tests

Add tests to `tests/scripts/test_exercise_runner.py` (already exists as an untracked file):

- `test_git_state_snapshot_returns_porcelain`: mock `subprocess.run`, assert stdout returned verbatim
- `test_check_git_state_clean`: baseline == current → returns `None`
- `test_check_git_state_dirty`: baseline != current → returns `"git-dirty"`, logs warning with `label`
- `test_git_state_snapshot_git_failure`: `subprocess.run` returns non-zero → `CalledProcessError` raised (not masked as clean)
- `test_check_git_state_subprocess_error`: `subprocess.run` raises `OSError` → exception propagates (no silent swallow)

### Verification

Temporarily remove the `Agent` deny rule (F1), re-run query 43, and confirm the `git-dirty` flag appears in the MANIFEST.

---

## F3: Extend Skill Gate to Cover Agent and Bash (High)

### Problem

The current `skill-gate.sh` has a Phase 2 that unconditionally allows all non-MCP tools:

```bash
# Phase 2: Allow non-MCP tools unconditionally
if [[ "$TOOL_NAME" != mcp__* ]]; then
  exit 0
fi
```

This creates two bypass paths:

1. **Agent bypass (6 instances):** The model spawns an Agent to call MCP tools. The Agent tool passes through Phase 2 without restriction.
2. **Bash/CLI bypass (5 instances):** The model uses `aria-esi` CLI commands via Bash instead of MCP tools, skipping the gate entirely since Bash isn't MCP.

The hook matcher `"Skill|mcp__.*"` further limits the hook to only firing on Skill and MCP tools — Agent and Bash never even reach the script.

### Proposed Fix

**File:** `dev/scripts/hooks/skill-gate.sh` (replace the entire file contents with the following — the existing Phase 2 blanket allowance is superseded by the targeted allowlist below)

Replace Phase 2's blanket allowance with a targeted read-only allowlist:

```bash
#!/bin/bash
# PreToolUse hook: enforce skill-first access to data tools.
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

# Phase 2: Allow read-only and infrastructure tools unconditionally
case "$TOOL_NAME" in
  Read|Glob|Grep|ToolSearch|WebFetch|WebSearch) exit 0 ;;
esac

# Phase 3: Block data tools until Skill has been invoked
if [[ ! -f "$MARKER" ]]; then
  case "$TOOL_NAME" in
    Agent)
      echo "BLOCKED: Invoke the relevant skill via the Skill tool before delegating to an Agent. The skill loads prerequisite reference data." >&2
      exit 2
      ;;
    Bash)
      # Only gate aria-esi CLI calls, not arbitrary shell commands
      COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
      # Simple word-boundary match: if aria-esi appears anywhere in the
      # command, this is a data-tool call. echo pipes multi-line commands
      # as separate lines, and grep matches any line — so &&-chained,
      # semicolon-separated, newline-split, and $()-subshell invocations
      # all match without needing shell-operator anchors in the pattern.
      if echo "$COMMAND" | grep -qE '(uv run )?aria-esi\b'; then
        echo "BLOCKED: Invoke the relevant skill via the Skill tool before using aria-esi CLI commands. The skill loads prerequisite reference data." >&2
        exit 2
      fi
      # Allow non-aria-esi bash commands (git, ls, etc.)
      exit 0
      ;;
    mcp__*)
      echo "BLOCKED: Invoke the relevant skill via the Skill tool before calling MCP tools directly. The skill loads prerequisite reference data." >&2
      exit 2
      ;;
    *)
      # Allow other tools (Edit, Write, etc.) — gated by permissions, not skill gate
      exit 0
      ;;
  esac
fi

exit 0
```

**File:** `dev/scripts/exercise-runner.py` (hook registration)

Update the matcher to fire on all tools:

```python
merged["hooks"]["PreToolUse"] = [
    {
        # Empty matcher = fire on all tools. The script's Phase 2
        # allowlist handles read-only tools internally.
        "hooks": [
            {"type": "command", "command": gate_cmd},
        ],
    },
]
```

Per the [hooks reference: matcher patterns](https://code.claude.com/docs/en/hooks#matcher-patterns): 'Use `"*"`, `""`, or omit `matcher` entirely to match all occurrences.'

### Production vs Exercise Deployment

The extended gate is safe for production use with one adjustment: **don't block Agent in production**. The Agent tool is essential for normal Claude Code operation (research, parallel exploration, etc.). In production, gating MCP and `aria-esi` Bash calls is sufficient because:

- Production sessions have interactive approval, so Edit/Write are already user-gated
- The skill gate's purpose in production is prerequisite loading, not sandbox enforcement

For exercise runs, F1 (deny rule on Agent) provides the hard block. F3 provides the soft block via hook feedback, which is the appropriate enforcement level for production.

### Verification

Re-run the 15 `no-skill` queries from the report with the extended gate. Expected result:
- Agent-delegated MCP calls: blocked by Phase 3 (Agent case)
- CLI fallbacks without Skill: blocked by Phase 3 (Bash case for `aria-esi`)
- Hook-blocked MCP → CLI without Skill: blocked by Phase 3 (Bash case)

---

## F4: Add Skill-First CLI Fallback Instruction (High)

### Problem

When the skill-gate hook blocks an MCP call, the model correctly recognizes MCP is unavailable and falls back to CLI per `docs/MCP_FALLBACK.md`. However, it doesn't recognize that it should invoke the Skill tool first — the hook block looks like "MCP is down" rather than "invoke the skill first."

This is a prompt engineering fix that complements F3's hook enforcement. The [skills docs](https://code.claude.com/docs/en/skills#types-of-skill-content) note that skills can serve as reference content that Claude applies to current work. The skill-first instruction ensures prerequisite data is loaded regardless of which data path (MCP or CLI) is used.

### Proposed Fix

**File:** `CLAUDE.md`, append to the **Skill Loading** section (the section starting with "**Skills gate authoritative data.**", currently near line 97):

```markdown
**Skill-gate compliance:** When a hook blocks a direct MCP or `aria-esi` CLI
call, it means the Skill tool has not yet been invoked for this query. Invoke
the Skill tool first — this loads prerequisite files and persona overlays.
After the Skill tool runs, the gate marker is set and the MCP/CLI call will
succeed on retry. Do not fall back to CLI as a way to circumvent a blocked
MCP call — both paths require the skill to be invoked first.
```

### Why both instruction and hook?

Defense-in-depth. The CLAUDE.md instruction handles the common case (model reads the instruction and complies). The hook (F3) catches edge cases where the model ignores the instruction. Neither alone is sufficient:

- Instruction alone: model may still delegate to Agent or use CLI without Skill
- Hook alone: model may interpret hook blocks as infrastructure failure and attempt workarounds (the exact behavior observed in CRITICAL-1)

### Verification

Run a query that previously fell back to CLI without Skill (e.g., `hunting-grounds-q2`). Confirm the model invokes Skill before `aria-esi` CLI.

---

## F5: Cap Tabular Output in Verbose Skills (Medium)

### Problem

Eight queries exceeded the 30-line brevity protocol. The violations cluster in skills that produce tabular output:

| Query | Lines | Skill |
|-------|-------|-------|
| build-cost-q1 | 71 | build-cost |
| build-cost-q2 | 70 | build-cost |
| exploration-q1 | 56 | exploration |
| orient-q2 | 55 | orient |
| reactions-q1 | 48 | reactions |
| threat-assessment-q2 | 48 | threat-assessment |
| orient-q1 | 42 | orient |
| help-q1 | 60 | help |

The `build-cost` responses are worst because they include debugging traces (CLI error output, `git log` investigation) that should never appear in user-facing output.

### Proposed Fix

Add brevity constraints to skill definitions. The [skills docs](https://code.claude.com/docs/en/skills#types-of-skill-content) recommend keeping `SKILL.md` focused. Brevity rules belong in the skill's instructions since they're domain-specific:

**File:** `.claude/skills/build-cost/SKILL.md` — add:

```markdown
## Output format

- BOM table: top 5 materials by cost contribution, then "... and N more (X ISK total)"
- Never include CLI error traces, debugging output, or git investigation in responses
- Target: ≤30 lines
```

**File:** `.claude/skills/orient/SKILL.md` — add:

```markdown
## Output format

- System table: cap at 8 nearest systems, sort by jumps
- Target: ≤30 lines
```

**File:** `.claude/skills/reactions/SKILL.md` — add:

```markdown
## Output format

- Recipe table: cap at 5 reactions sorted by profit margin, then "... and N more reactions available"
- Show input/output volumes per run, not per-unit
- Target: ≤30 lines
```

**File:** `.claude/skills/threat-assessment/SKILL.md` — add:

```markdown
## Output format

- Activity table: cap at 6 systems, sorted by threat level (highest first)
- One-line verdict per system (sec status, NPC kills, pod kills, ship kills)
- Target: ≤30 lines
```

**File:** `.claude/skills/exploration/SKILL.md` — add:

```markdown
## Output format

- Site table: cap at 6 sites sorted by estimated value, then "... and N more sites in system"
- Loot breakdown: top 3 items by value only
- Target: ≤30 lines
```

**Exception:** `/help` lists available commands and legitimately needs more than 30 lines.

**Exemption handling in exercise runner:** Use a static allowlist in `exercise-runner.py`'s response post-processing (where brevity flags are assigned), not comment parsing. This avoids coupling the runner to skill file content.

**Integration with `quality_check()`:** `_check_brevity()` **replaces** the existing brevity check in `quality_check()` (lines 273–279). The changes are:

- **Threshold:** 40 → 30 (aligns with the `≤30 lines` target in CLAUDE.md's brevity protocol)
- **Flag format:** `"brevity-{N}"` → `"verbose"` (intentional simplification — the parametric line count added noise to MANIFEST summaries without actionable value; the MANIFEST normalization regex `re.sub(r"\(.*\)", "", f)` already stripped parens from other flags, and `"verbose"` is cleaner than relying on regex normalization)
- **Exemption:** New — skills in `BREVITY_EXEMPT_SKILLS` are not flagged regardless of line count

**Call-site:** `_check_brevity()` is called from within `quality_check()`, replacing the existing brevity block. The `query_label` parameter is constructed inside `quality_check()` from the `query` dict using `query["skill"]` and `query["query_num"]` (both always present — see line 329 where they're used for filenames). Specifically:

```python
# In quality_check(), replace lines 273-279 with:
query_label = f"{query['skill']}-q{query['query_num']}"
brevity_flag = _check_brevity(query_label, len(content_lines))
if brevity_flag:
    flags.append(brevity_flag)
```

The `content_lines` computation (lines 274–277) is preserved — only the threshold check and flag emission change.

```python
# Module-level constant, near other constants:
BREVITY_EXEMPT_SKILLS = {"help"}  # Skills with legitimately verbose output

def _check_brevity(query_label: str, response_lines: int) -> str | None:
    """Return 'verbose' flag if response exceeds brevity cap, unless exempt."""
    skill_name = query_label.rsplit("-q", 1)[0]  # "help-q1" → "help"
    if skill_name in BREVITY_EXEMPT_SKILLS:
        return None
    if response_lines > 30:
        return "verbose"
    return None
```

### Unit Tests

Add tests to `tests/scripts/test_exercise_runner.py`:

- `test_check_brevity_under_limit`: 25 lines, non-exempt skill → returns `None`
- `test_check_brevity_over_limit`: 35 lines, non-exempt skill → returns `"verbose"`
- `test_check_brevity_exempt_skill`: 60 lines, `"help"` skill → returns `None`
- `test_check_brevity_no_q_suffix`: label `"standalone"` (no `-q` suffix) → returns `"verbose"` if over 30 (not incorrectly exempt)
- `test_quality_check_brevity_integration`: pass a `query` dict with `skill="build-cost"` and `query_num=1` (producing label `"build-cost-q1"`) and a 35-line body to `quality_check()` → flags contain `"verbose"` (not `"brevity-35"`). This verifies the label construction and `_check_brevity` call-site wiring end-to-end.

### Verification

Re-run `build-cost-q1` and `orient-q2`. Confirm responses stay under 30 content lines.

---

## F6: Add Missing CLI Fallbacks (Medium)

### Problem

Two MCP actions have no CLI equivalent, causing incomplete data when MCP is unavailable:

| MCP Action | Affected Query | Current CLI |
|------------|---------------|-------------|
| `universe(action="territory_analysis")` | hunting-grounds-q3 (14) | None |
| `market(action="find_nearby")` proximity mode | find-q3 (32) | Partial (`aria-esi find` exists but lacks proximity sorting) |

Per `docs/MCP_FALLBACK.md`, every MCP action used by a skill should have a CLI fallback.

### Proposed Fix

1. **`aria-esi territory <system>`** — new CLI command in `src/aria_esi/commands/universe.py`, wrapping the territory analysis logic from `src/aria_esi/mcp/dispatchers/universe/_dispatcher.py`. Register by adding a `"territory"` subcommand in the existing `register_parsers()` function in `src/aria_esi/commands/universe.py` (the `universe` module is already in `_COMMAND_MODULES` at `src/aria_esi/__main__.py:450`). Follow the pattern of `src/aria_esi/commands/build_cost.py`: define `cmd_territory(args)` that calls the dispatcher's territory analysis function via `asyncio.run()`, and register with `subparsers.add_parser("territory", ...)`. Output format (text, one line per system):

   ```
   System          | Sov Holder    | Ship Kills | Pod Kills | NPC Kills | Jumps
   ----------------+---------------+------------+-----------+-----------+------
   <target>        | <alliance>    | 12         | 3         | 450       | 89
   <adjacent 1>    | ...           | ...        | ...       | ...       | ...
   ```

   Target system first, then adjacent systems sorted by total kill activity descending. JSON output via `--json` flag for programmatic use.

2. **`aria-esi find --proximity <system>`** — extend the existing `find` command with a `--proximity` flag that sorts results by jump distance from the reference system. The `<system>` argument is **required** when `--proximity` is used (error with usage hint if omitted). No current-location fallback — ESI location is volatile and the CLI should not implicitly depend on it.

3. **Update `docs/MCP_FALLBACK.md`** with the new mappings:

```markdown
| `/hunting-grounds` | `universe(action="territory_analysis", ...)` | `aria-esi territory` |
| `/find` (proximity) | `market(action="find_nearby", proximity=...)` | `aria-esi find --proximity` |
```

### Verification

Run `hunting-grounds-q3` and `find-q3` with MCP unavailable. Confirm CLI fallbacks return usable data.

---

## Implementation Order

Fixes are ordered by blast radius reduction — sandbox integrity first, then skill compliance, then polish:

```
F1 (Agent deny rule)     ← Critical: closes both code-mutation and gate-bypass vectors
  ↓
F2 (git state assertion) ← High: defense-in-depth detection layer
  ↓
F3 (extended gate)       ← High: closes remaining bypass paths for skill compliance
  ↓
F4 (CLAUDE.md instruction) ← High: complements F3, low-effort
  ↓
F5 (brevity caps)        ← Medium: skill definition polish
  ↓
F6 (CLI fallbacks)       ← Medium: new CLI commands, highest effort
```

F1+F2 can be implemented and validated independently of F3–F6. F3+F4 should ship together. F5 and F6 are independent of each other and of all prior fixes.

### Validation Run

After F1–F4 are applied, re-run the full 47-query ESI:NONE exercise. Success criteria:

| Metric | Target | Run 20260311-192927 |
|--------|--------|---------------------|
| Completion rate | 100% | 100% ✓ |
| Skill gate compliance | >90% | 68% ✗ |
| Brevity compliance | >90% | 83% ✗ |
| Data accuracy | 100% | 100% ✓ |
| No code mutation | YES | NO ✗ |
| No git-dirty flags | YES | N/A (new metric) |

---

## Deferred Items

The following items from the recommendations are deferred to separate proposals:

### Skill-Scoped Hooks (R7)

The [skills docs](https://code.claude.com/docs/en/skills#frontmatter-reference) support a `hooks` field in skill frontmatter. Per the [hooks reference: hooks in skills and agents](https://code.claude.com/docs/en/hooks#hooks-in-skills-and-agents), these hooks are "scoped to the component's lifecycle" and support `PreToolUse`, `PostToolUse`, and `Stop` events. This is a valid pattern for prerequisite validation *within* a skill (e.g., a `PreToolUse` hook on `mcp__*` that verifies `prerequisite_files` were loaded before MCP calls proceed). However, it cannot enforce the "invoke Skill first" gate — that's inherently a pre-skill concern handled by the global gate (F3).

This is an architectural improvement worth pursuing but not blocking for the current exercise compliance target.

### ESI-Dependent Coverage (R8)

42 of 89 queries require ESI credentials and were not exercised. Options include mock ESI via `PostToolUse` hooks ([hooks reference: PostToolUse decision control](https://code.claude.com/docs/en/hooks#posttooluse-decision-control) supports `updatedMCPToolOutput` for replacing MCP responses with canned data), dedicated test credentials, or a hybrid approach. This requires a separate design proposal.

---

## Readiness Review Resolution

### Review 1: `dev/reviews/2026-03-11-2125/exercise-sandbox-and-gate-v4-proposal-readiness.md`

| Item | Status | Resolution |
|------|--------|------------|
| **B1** — Output constraints missing for reactions, threat-assessment, exploration | Resolved | Added specific `## Output format` blocks with line caps and truncation rules for all three skills |
| **B2** — Exercise-runner exemption handling unresolved | Resolved | Chose static allowlist (`BREVITY_EXEMPT_SKILLS` set) in response post-processing; specified `_check_brevity()` implementation |
| **G1** — `_check_git_state` `label` parameter unused | Resolved | `label` used in `log.warning()` call for identifying which query caused mutation |
| **G2** — No unit test specification for F2 | Resolved | Added unit test matrix (4 cases) targeting `tests/scripts/test_exercise_runner.py` |
| F1 deny_rules — two code blocks, which is authoritative | Resolved | Consolidated to single block with Edit+Write included |
| F3 skill-gate.sh — net-new file confirmation | Resolved | Reframed as "replace the entire file contents" (corrected in review 3) |
| F4 CLAUDE.md target section | Resolved | Added line reference ("near line 97") |
| F3 regex correctness — pipe/newline bypass | Resolved | Extended regex to match `\|`, `\n`, `\$()` operators |

### Review 2: `dev/reviews/2026-03-12-0052/exercise-sandbox-and-gate-v4-proposal-readiness.md`

| Item | Status | Resolution |
|------|--------|------------|
| **B1** — F3 regex `\n`/`\$\(` in `echo \| grep -qE` is a no-op | Resolved | Simplified regex to `(uv run )?aria-esi\b` — shell-operator anchors unnecessary because echo pipes multi-line commands as separate lines and grep matches any line containing the pattern |
| **G1** — `_git_state_snapshot` silent on non-zero git exit | Resolved | Added `check=True` to `subprocess.run`; raises `CalledProcessError` instead of returning empty stdout. Added `test_git_state_snapshot_git_failure` to test matrix |
| **G2** — `aria-esi territory` output format unspecified | Resolved | Added output schema table (System, Sov Holder, Ship/Pod/NPC Kills, Jumps) with sort order and `--json` flag |
| **G3** — `--proximity <system>` argument cardinality | Resolved | `<system>` is required when `--proximity` is used; error with usage hint if omitted; no implicit current-location fallback |
| **G4** — `_check_brevity` has no test specification | Resolved | Added 4-case test matrix (under limit, over limit, exempt skill, no `-q` suffix) |

### Review 3: `dev/reviews/2026-03-12-0101/exercise-sandbox-and-gate-v4-proposal-readiness.md`

| Item | Status | Resolution |
|------|--------|------------|
| **B1** — F5: `_check_brevity()` conflicts with existing brevity in `quality_check()` | Resolved | `_check_brevity()` **replaces** the existing brevity block (lines 273–279). Threshold intentionally changed from 40→30. Flag format intentionally changed from `"brevity-N"` to `"verbose"` (simplification — parametric count added noise). Both changes documented with rationale. |
| **B2** — F3: skill-gate.sh framed as net-new but file exists | Resolved | Replaced "net-new file / no pre-existing file to preserve" with "replace the entire file contents" and noted the existing Phase 2 is superseded |
| **G1** — F5: `_check_brevity()` call-site integration unspecified | Resolved | Specified that `_check_brevity` is called from within `quality_check()`, replacing lines 273–279. `query_label` is constructed as `f"{query['skill']}-q{query['query_num']}"` (both keys always present). Added inline code block showing the replacement. |
| **G2** — F2: git-dirty flag attribution in parallel execution | Resolved | Stated that `git-dirty` is attached to the detecting query. Noted causal attribution would require per-query snapshots (expensive) and detecting-query attribution is sufficient for post-hoc investigation via MANIFEST timestamp + `git log`. |
| F1 deny_rules — replaces or merges with existing | Resolved | Added explicit note that the block replaces the existing `deny_rules` list; path-specific rules retained as defense-in-depth |
| F5 — integration test coverage gap | Resolved | Added `test_quality_check_brevity_integration` to test matrix: passes a `query` dict through `quality_check()` end-to-end, verifying label construction and `_check_brevity` wiring |

### Review 4: `dev/reviews/2026-03-12-0111/exercise-sandbox-and-gate-v4-proposal-readiness.md`

| Item | Status | Resolution |
|------|--------|------------|
| **G1** — F2: `baseline` capture and `_check_git_state()` call-site not shown in `main()` | Resolved | Added inline code stub showing `baseline = _git_state_snapshot()` placement before the parallel/sequential branch, and `_check_git_state()` calls in both execution paths with `result.setdefault("quality", []).append(git_flag)` wiring |
| **G2** — F6: Target module and CLI registration for `aria-esi territory` unspecified | Resolved | Target module is `src/aria_esi/commands/universe.py` (already in `_COMMAND_MODULES`). Register via `subparsers.add_parser("territory", ...)` in existing `register_parsers()`. Follow `build_cost.py` pattern: `cmd_territory(args)` calling dispatcher via `asyncio.run()` |
| **G3** — F5: Test spec `label="q1"` not a `quality_check()` parameter | Resolved | Corrected to `query_num=1` with note that it produces label `"build-cost-q1"` |
