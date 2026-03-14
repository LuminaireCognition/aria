# Skill-Gate Compliance & Quality Hardening

**Status:** Proposed
**Date:** 2026-03-12
**Owner:** ARIA Development
**Scope:** `CLAUDE.md`, `dev/scripts/hooks/skill-gate.sh`, `.claude/skills/{watchlist,journal,first-run-setup,build-cost,mission-brief}/SKILL.md`
**Related:** `dev/reviews/exercise-outputs/20260312-021631/REPORT.md`, `dev/reviews/exercise-outputs/20260312-021631/RECOMMENDATIONS.md`, `SKILL_GATE_AND_EXERCISE_HARDENING.md` (predecessor — implemented F1-F4)

---

## Executive Summary

The 20260312-021631 exercise run (47 queries, 100% completion, 0 errors) is the first clean baseline run since the skill-gate infrastructure was deployed. The gate works — MCP calls are correctly blocked until the Skill tool is invoked, and the model correctly retries after invocation. However, the run reveals **behavioral inefficiency** and **two deadlock patterns** that were not visible in prior runs where the gate was broken.

**Key findings:**

1. **53% of queries pay a double MCP call tax** — the model tries MCP first, gets blocked, invokes Skill, then retries. The gate's prompting teaches *recovery* but not *prevention*.
2. **`disable-model-invocation` skills deadlock with the gate** — watchlist and journal have `disable-model-invocation: true`, making the Skill tool unavailable. The gate requires the Skill tool. Neither constraint can yield. 4 queries affected, 1 surfaced internal implementation details to the user.
3. **Verbosity flags are mostly false positives** — 15 responses were flagged against the global 30-line limit, but skills declare `preferred_max_lines` (45-50 for complex skills) with a 50% soft overshoot allowance per `.claude/rules/skills.md`. Most flagged responses are within their per-skill budgets.

This proposal covers five fixes. Two corrections to RECOMMENDATIONS.md analysis are noted where deeper investigation revealed different causes.

| # | Fix | Layer | Severity | Effort |
|---|-----|-------|----------|--------|
| F1 | Proactive skill-gate prompting in CLAUDE.md | Prompt instructions | High | Low |
| F2 | Resolve `disable-model-invocation` gate deadlock | Hook script + skill frontmatter | Critical | Low |
| F3 | Build-cost classification gate conflict | Skill definition | Medium | Trivial |
| F4 | Mission-brief archetype tier validation | Skill definition | Medium | Low |
| F5 | Journal tool selection fix | Skill frontmatter | Low | Trivial |

### Corrections to RECOMMENDATIONS.md

| Recommendation | Claimed Issue | Actual Finding |
|---|---|---|
| Verbosity (32%) | 15 responses exceed 30-line global limit | Skills declare `preferred_max_lines` (40-50) with 50% soft overshoot per `.claude/rules/skills.md`. **All 15 are within the soft ceiling.** The report compared against the wrong baseline. |
| Build-cost q44 "gave up" | Skill lacks invention handling | Skill already has decryptor lookup at line 122. But the Classification Gate at line 39 preempts it. The model followed the gate correctly. The fix is a gate clarification, not a new reference file. |
| first-run-setup "no-skill" | Model bypassed skill system | `disable-model-invocation: true` means description is not in context (skills.md line 274). Working as designed; exercise query mismatches the skill's invocation model. |
| Watchlist deadlock | Marker not set | Marker IS set when the Skill tool is attempted. But the model makes parallel tool calls (Skill + Bash simultaneously), so the Bash PreToolUse fires before the Skill PreToolUse creates the marker. The deadlock is a **parallel execution race**, not a missing marker. |

### Relationship to Prior Proposals

`SKILL_GATE_AND_EXERCISE_HARDENING.md` (2026-03-11) deployed the current skill-gate mechanism (F1: marker-file approach, F2: MCP fallback discipline, F3: infrastructure protection, F4: no-skill-ok quality flag). All four fixes are confirmed working. This proposal addresses behavioral patterns that became visible only after the infrastructure was stable.

---

## F1: Proactive Skill-Gate Prompting (High)

### Problem

25 of 47 queries (~53%) follow this wasteful pattern:

```
ToolSearch -> MCP (BLOCKED by gate) -> Skill tool (gate satisfied) -> MCP (retry -> success)
```

Confirmed in tool traces for mark-assessment, ransom-calc, orient, route, build-cost, killmail, threat-assessment, and others. Each affected query pays ~1-2 extra tool calls and ~15-30s additional latency.

### Root Cause

CLAUDE.md's "Skill-gate compliance" section describes the recovery path:

> When a hook blocks a direct MCP or `aria-esi` CLI call, it means the Skill tool has not yet been invoked for this query. Invoke the Skill tool first...

This teaches the model what to do *after* a block, but doesn't establish a prevention rule. The model's natural flow — resolve data first, invoke skills as needed — leads to the block-then-retry pattern.

### Evidence

From `16-mark-assessment-q1.tools.json`:
```
ToolSearch -> fitting (resolve)
fitting(hull_stats) -> BLOCKED
market(prices) -> BLOCKED
Skill(mark-assessment) -> gate satisfied
fitting(hull_stats) -> success
market(prices) -> success
```

6 tool calls where 4 would suffice.

### Proposed Fix

Replace the current "Skill-gate compliance" paragraph in CLAUDE.md with a proactive rule:

**File:** `CLAUDE.md`, "Skill Loading" section (lines 168-173)

Replace:

```markdown
**Skill-gate compliance:** When a hook blocks a direct MCP or `aria-esi` CLI
call, it means the Skill tool has not yet been invoked for this query. Invoke
the Skill tool first — this loads prerequisite files and persona overlays.
After the Skill tool runs, the gate marker is set and the MCP/CLI call will
succeed on retry. Do not fall back to CLI as a way to circumvent a blocked
MCP call — both paths require the skill to be invoked first.
```

With:

```markdown
**Skill-gate order of operations:** When a query falls within a skill's
domain, invoke the Skill tool BEFORE making any MCP or `aria-esi` CLI calls.
The skill-gate hook blocks data tool calls until the Skill tool has been
invoked — calling MCP first wastes a tool call on the block and forces a
retry.

Flow: identify skill -> Skill tool -> MCP/CLI calls -> response.

If a data tool call is blocked by the gate, invoke the Skill tool and retry.
Do not diagnose the blocker or fall back to CLI as a way to circumvent a
blocked MCP call — both paths require the skill to be invoked first.
```

### Why This Works

Per the Claude Code skills documentation, skill descriptions are "loaded into context so Claude knows what's available" (line 277). The model can identify which skill domain a query falls into before making tool calls. The current instruction tells the model how to recover; the replacement tells it how to avoid needing recovery.

The recovery instruction is preserved as the final sentence for defense-in-depth.

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Model still tries MCP first despite instruction | Medium | Recovery path preserved; this is a latency optimization, not a correctness fix |
| Instruction too aggressive — model invokes Skill for non-skill queries | Low | Instruction scopes to "when a query falls within a skill's domain" |

---

## F2: Resolve `disable-model-invocation` Gate Deadlock (Critical)

### Problem

Skills with `disable-model-invocation: true` (watchlist, journal, first-run-setup) cannot satisfy the skill-gate because:

1. The user invokes the skill via `/watchlist` (command expansion, not Skill tool)
2. The model tries to call MCP or Bash -> **blocked** by gate (no Skill marker)
3. The model tries `Skill("watchlist")` -> **rejected** (`disable-model-invocation`)
4. The model tries Bash again -> **still blocked** (marker never created)
5. Deadlock

### Evidence

Query 27 (`/watchlist "Sync my war targets"`):
- `Bash(watchlist-list)` -> BLOCKED by gate
- `Skill(watchlist)` -> "cannot be used with Skill tool due to disable-model-invocation"
- `Bash(watchlist-list)` -> BLOCKED by gate (still no marker)

Query 27 response surfaced internal details ("skill-gate hook", "dev/scripts/hooks/skill-gate.sh") to the user, violating the MCP Fallback Discipline directive.

### Root Cause

The deadlock was initially attributed to a missing marker. Deeper investigation reveals a **parallel execution race**: when the model calls Skill and Bash simultaneously, both PreToolUse hooks fire in parallel. The Bash hook checks for the marker before the Skill hook creates it.

But even without parallel execution, the Skill tool fails for `disable-model-invocation` skills. The fundamental conflict is that two constraints — `disable-model-invocation` (skill can't be loaded via Skill tool) and skill-gate (Skill tool must be called to set marker) — are mutually exclusive.

### Proposed Fix

**Modify `skill-gate.sh` to exempt `disable-model-invocation` skills.**

These skills load inline via `<command-name>` expansion when the user types `/watchlist`. The skill content (including prerequisite data, formatting rules, and persona overlays) is already in context. The gate's purpose — ensuring prerequisite data is loaded — is satisfied by the inline loading path.

**File:** `dev/scripts/hooks/skill-gate.sh`

Add an exemption list in the Bash gating section (after the `aria-esi` grep):

```bash
# Exempt CLI commands for disable-model-invocation skills.
# These skills load inline via /command — the gate's prerequisite-loading
# purpose is satisfied by that path. The Skill tool cannot be used for them.
EXEMPT_PATTERNS="watchlist-|journal"
if echo "$COMMAND" | grep -qE "$EXEMPT_PATTERNS"; then
  exit 0
fi
```

For MCP calls, add a skill-agnostic exemption for `resolve_names` in the `mcp__*` block. This exemption is **intentionally not scoped to watchlist** — `resolve_names` is a read-only SDE name resolution call that returns static data (type IDs to names). It carries no confabulation risk regardless of which skill triggers it, and the hook has no access to calling-skill context. Scoping it would require plumbing that adds complexity without safety benefit.

```bash
mcp__*)
  # Exempt SDE resolve_names — read-only name resolution, safe regardless of
  # calling skill. Intentionally skill-agnostic: the hook has no calling-skill
  # context, and resolve_names returns static SDE data with no confabulation risk.
  # See: .claude/skills/{watchlist,journal,first-run-setup}/SKILL.md
  TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input // empty')
  if echo "$TOOL_INPUT" | grep -q '"resolve_names"'; then
    exit 0
  fi
  echo "BLOCKED: ..." >&2
  exit 2
  ;;
```

### Why Not Skill-Scoped Hooks

The RECOMMENDATIONS.md proposed skill-scoped `hooks` in frontmatter to set the gate marker. Per the Claude Code hooks reference, skills can define hooks scoped to their lifecycle (line 102). However:

1. **Hook ordering is not guaranteed** across scopes. A skill-scoped PreToolUse hook and the global `skill-gate.sh` PreToolUse hook fire for the same event. If the global hook fires first, it blocks before the skill hook creates the marker.
2. **The `once: true` field** (hooks-reference.md line 194) removes the hook after first execution, but doesn't address execution ordering.
3. **`${CLAUDE_SESSION_ID}`** is documented for string substitution in skill *content* (skills.md line 204), not as an environment variable in hook command contexts.

The exemption-list approach is simpler, testable, and doesn't depend on hook execution ordering.

### Affected Skills

| Skill | `disable-model-invocation` | CLI Commands to Exempt | MCP Actions to Exempt |
|-------|---------------------------|------------------------|----------------------|
| watchlist | `true` | `watchlist-*` | `sde(resolve_names)` |
| journal | `true` | (none — uses Write tool) | (none) |
| first-run-setup | `true` | (none — reads profile only) | (none) |

Journal and first-run-setup don't make gated tool calls, so they're not affected by the deadlock in practice. The exemption for watchlist CLI commands resolves the functional issue.

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Exemption list becomes stale as skills change | Low | Only 3 skills have `disable-model-invocation`; comment in hook links to skills |
| Exempted CLI commands bypass prerequisite loading | None | These skills load inline via `<command-name>` — prerequisite data is already in context |
| `resolve_names` exemption too broad | Low | Intentionally skill-agnostic: returns static SDE data, no confabulation risk. Hook lacks calling-skill context, so scoping would require plumbing with no safety benefit. |

---

## F3: Build-Cost Classification Gate Conflict (Medium)

### Problem

Query 44 ("Is it profitable to build Hammerhead II with the Attainment decryptor?") followed the Out-of-Scope Template verbatim and gave up without making any tool call.

### Root Cause

The build-cost SKILL.md has a conflict between two sections:

**Classification Gate (line 39):**
> "Is it profitable to build [T2 item]?" requires invention economics -> out of scope.

**T2 Items section (line 122):**
> If the user names a decryptor, look up its ME modifier via `sde(action="item_info")` and use that ME value.

The Classification Gate catches the query first and routes it to the Out-of-Scope Template. The model never reaches the decryptor handling.

The Out-of-Scope Template is correct for open-ended T2 profitability questions. But when a decryptor is named, the user has already made the invention decision — they want manufacturing-step cost at that decryptor's ME level.

### Proposed Fix

**File:** `.claude/skills/build-cost/SKILL.md`

Amend the Classification Gate (around line 35-39) to add a decryptor exception:

```markdown
- **Fully out-of-scope** (invention ROI, datacores, BPC acquisition, success rate analysis) -> Out-of-Scope Template, then stop

**Exception:** If the user names a specific decryptor (e.g., "with the Attainment
decryptor"), the query is **partially in-scope**: look up the decryptor's ME modifier
per the T2 Items section, run `build_cost` at that ME level, and present the result
with the T2 scope notice. The user has already made the invention decision — they
want manufacturing-step cost.
```

No new reference files needed. The decryptor ME lookup uses `sde(item_info)` which returns the ME modifier from the game database.

### Implementation Prerequisite

Before applying this fix, the implementer MUST verify that `sde(action="item_info", item="Attainment Decryptor")` returns the ME modifier attribute. If the SDE dispatcher does not return decryptor attributes, this fix is **blocked** pending a SDE dispatcher addition (out of scope for this proposal). The classification gate change without a working ME lookup would route queries to the T2 section where they'd fail silently.

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Model misclassifies general T2 profitability as decryptor-named | Low | Gate distinction is clear |
| `sde(item_info)` doesn't return decryptor ME modifier | Medium | **Implementation prerequisite** — verify before applying; blocks this fix if absent |

---

## F4: Mission-Brief Archetype Tier Validation (Medium)

### Problem

Query 19 ("Prepare for Gone Berserk level 3") loaded `reference/archetypes/hulls/cruiser/vexor/pve/missions/l2/meta.yaml` — an L2 archetype for an L3 mission. The resulting fit used T1 modules (Armor Repairer I, Kinetic Armor Hardener I) appropriate for L2 but under-specced for L3. The response warned "will be tight for L3" but the fit itself was a direct L2 template.

### Root Cause

The archetype directory has L2 but no L3 for the Vexor. The mission-brief skill doesn't validate that the archetype tier matches the requested mission level — it finds the nearest available archetype and uses it silently.

### Proposed Fix

**File:** `.claude/skills/mission-brief/SKILL.md`

Add an archetype selection rule:

```markdown
## Archetype Selection

When selecting a fit archetype for a mission:

1. Check for exact tier match: `archetypes/{hull}/pve/missions/l{level}/`
2. If no match exists, check one tier below: `l{level-1}/`
3. **If using a lower-tier archetype, explicitly state this** in the response:
   "No L{level} archetype for {hull}. Adapting L{level-1} template."
4. When adapting upward, upgrade modules where pilot skills allow:
   - T1 -> compact meta (always available)
   - T1 -> T2 (check via `fitting(check_requirements)`)
   - Add rigs if slots are empty
5. If no archetype exists within 1 tier, recommend a more appropriate hull
   from the pilot's ship roster instead of using a 2+ tier mismatch.
```

### Validation

The exercise runner does not currently check archetype tier vs. requested mission level, so the success criterion ("0 silent mismatches") cannot be verified automatically. **Manual inspection** of a post-implementation mission-brief response is the accepted validation path for the initial implementation.

Future hardening (out of scope): add an exercise query like `"Prepare for Gone Berserk level 3"` with a quality check that greps the response for "Adapting L{n} template" or confirms T2/meta module presence when the archetype tier doesn't match the mission level.

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Module upgrades produce an unflyable fit | Low | `fitting(check_requirements)` validates prerequisites |
| Archetype directory structure changes | Low | Path pattern is stable |

---

## F5: Journal Tool Selection Fix (Low)

### Problem

Query 39 (exploration journal logging) attempted three write operations, all failed:
1. `NotebookEdit` on a `.md` file -> error (NotebookEdit is for `.ipynb` only)
2. `Bash` heredoc -> blocked by security hook (`#`-prefixed line in heredoc)
3. `Bash` Python heredoc -> blocked by security hook (consecutive quote characters)

### Root Cause

The journal skill has `disable-model-invocation: true` but does NOT declare `allowed-tools`. Without explicit tool guidance, the model chose `NotebookEdit` (wrong tool for `.md` files) and then fell back to Bash workarounds that triggered unrelated security hooks.

Per the Claude Code skills documentation, `allowed-tools` "grants Claude access to those tools without per-use approval when the skill is active" (line 189). It also signals to the model which tools are appropriate for the skill's task.

### Proposed Fix

**File:** `.claude/skills/journal/SKILL.md`

Add `allowed-tools` to the frontmatter:

```yaml
---
name: journal
description: Log mission completions and exploration discoveries to operational records.
model: haiku
category: operations
disable-model-invocation: true
preferred_max_lines: 15
allowed-tools: Read, Write, Grep, Glob
---
```

Write is the correct tool for creating/replacing `.md` file content. Declaring it in `allowed-tools` provides both permission and a signal about intended tool selection.

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Write tool permissions not granted in exercise runner | Low | Write is a standard tool; runner allows it for non-infrastructure paths |

---

## Verbosity Assessment: No Action Required

### Analysis

The RECOMMENDATIONS.md flagged 15 responses (32%) as exceeding the 30-line brevity protocol. However, this comparison uses the wrong baseline:

- `.claude/rules/skills.md` (line 21-23) states: "If a skill declares `preferred_max_lines` in its frontmatter, target that line count instead of the global 30-line default. This is a soft target, not a hard ceiling — complex or wide-scope queries may exceed it by up to 50%."

All flagged skills declare their own `preferred_max_lines`:

| Skill | Actual Lines | `preferred_max_lines` | Soft Ceiling (x1.5) | Status |
|-------|-------------|----------------------|---------------------|--------|
| route | 42 | 45 | 67 | **Within budget** |
| orient | 53 | 45 | 67 | **Within budget** |
| threat-assessment | 44 | 45 | 67 | **Within budget** |
| mark-assessment | 44 | 40 | 60 | **Within budget** |
| ransom-calc | 55 | 40 | 60 | **Within budget** |
| build-cost | 58 | 50 | 75 | **Within budget** |
| find | 29 | (none) | 45 (global) | **Within budget** |

**All 15 flagged responses are within their per-skill soft ceilings.** No line budget changes are needed.

### Exercise Runner Fix

The exercise runner's brevity check should compare against `preferred_max_lines` from the skill frontmatter, not the global 30-line default. This is a runner bug, not a response quality issue.

**File:** `dev/scripts/exercise-runner.py`, `quality_check()` function

`parse_yaml_frontmatter()` does not exist in `exercise-runner.py` and must be written. The runner already imports `re` but not `yaml`. Use a regex approach to avoid adding a new dependency:

```python
def parse_yaml_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter as a dict using regex (no yaml dependency)."""
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            value = value.strip()
            # Coerce numeric values
            try:
                value = int(value)
            except ValueError:
                pass
            result[key.strip()] = value
    return result
```

Then in `_check_brevity()`:

```python
def _check_brevity(query_label: str, response_lines: int) -> str | None:
    """Return 'verbose' flag if response exceeds brevity cap, unless exempt."""
    skill_name = query_label.rsplit("-q", 1)[0]
    if skill_name in BREVITY_EXEMPT_SKILLS:
        return None
    # Read per-skill preferred_max_lines from SKILL.md frontmatter
    index_path = PROJECT_ROOT / ".claude" / "skills" / skill_name / "SKILL.md"
    max_lines = 30  # global default
    if index_path.exists():
        frontmatter = parse_yaml_frontmatter(index_path.read_text())
        max_lines = frontmatter.get("preferred_max_lines", 30)
    soft_ceiling = int(max_lines * 1.5)
    if response_lines > soft_ceiling:
        return "verbose"
    return None
```

---

## Implementation Plan

F1 and F2 are independent. F3-F5 are independent of each other and of F1/F2.

**Implementer note:** Before applying F2, read `dev/scripts/hooks/skill-gate.sh` in full to verify exemption insertion points match the described structure (Bash gating section and `mcp__*` block).

```
Phase 1 (parallel):
  F1: Replace CLAUDE.md skill-gate compliance text     [Low effort, ~10 lines]
  F2: Add exemption list to skill-gate.sh              [Low effort, ~10 lines]

Phase 2 (parallel):
  F3: Amend build-cost Classification Gate              [Trivial, ~5 lines in SKILL.md]
  F4: Add archetype tier validation to mission-brief    [Low effort, ~15 lines in SKILL.md]
  F5: Add allowed-tools to journal SKILL.md             [Trivial, 1 line]

Phase 3 (validation):
  Re-run exercise suite with same config:
  --explicit --filter NONE --parallel 5 --timeout 920
```

### Success Criteria

| Metric | Current (20260312) | Target |
|--------|-------------------|--------|
| Double MCP call rate | 53% (25/47) | <20% |
| `disable-model-invocation` deadlocks | 2 queries | 0 |
| Internal details surfaced to user | 1 query | 0 |
| Build-cost "gave up" on named decryptor | 1 query | 0 |
| Archetype tier mismatch (silent) | 1 query | 0 |
| Journal write failures | 3 attempts | 0 |
| False verbose flags in MANIFEST | 15 | <3 |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| F1: Model still tries MCP first despite stronger prompting | Medium | Recovery path preserved; latency optimization, not correctness |
| F2: Exemption list becomes stale | Low | Only 3 skills have `disable-model-invocation`; comment in hook links to skills |
| F2: Exemption bypasses prerequisite loading | None | `disable-model-invocation` skills load inline via `<command-name>` |
| F3: Model misclassifies general T2 query as decryptor-named | Low | Gate distinction is explicit |
| F4: Module upgrades produce unflyable fit | Low | `fitting(check_requirements)` validates prerequisites |

---

## Out of Scope

- **Per-skill line budget reductions**: All responses are within per-skill soft ceilings. The `preferred_max_lines` values are appropriate. No changes needed.
- **Decryptor reference file**: RECOMMENDATIONS.md proposed `reference/industry/decryptors.md`. The `sde(item_info)` tool already returns decryptor attributes. A static reference file would be a second source of truth that drifts from SDE.
- **first-run-setup natural language invocation**: `disable-model-invocation: true` is correct for this skill (it writes to profile files). The exercise query should be changed to `/first-run-setup`, not the skill's invocation model.
- **No-skill-ok verification pass**: All 9 `no-skill-ok` responses were correct. Automated verification adds complexity with no demonstrated quality improvement.
- **Skill-scoped hooks for gate marker**: Investigated as an alternative to F2. Hook execution ordering across scopes is not guaranteed per the hooks reference, making this approach unreliable.

---

## SKILLSSKILLS Documentation Adherence

| Proposal Claim | Reference | Status |
|---|---|---|
| `disable-model-invocation: true` removes description from context | skills.md line 274: "Description not in context, full skill loads when you invoke" | Correct — validates first-run-setup reclassification |
| `allowed-tools` signals correct tool selection | skills.md line 189: "Tools Claude can use without asking permission when this skill is active" | Correct — used in F5 |
| `preferred_max_lines` overrides global 30-line default | `.claude/rules/skills.md` line 21-23 | Correct — validates verbosity reclassification |
| Skill-scoped hooks fire for matching events during skill lifecycle | hooks-reference.md line 102: "Hooks can be defined in skills... Scoped to the component's lifecycle" | Correct — investigated for F2, rejected due to ordering concerns |
| PreToolUse exit 2 blocks tool calls | hooks-reference.md line 371: "Exit 2: Blocks the tool call" | Correct — gate mechanism |
| `once: true` runs hook once then removes it | hooks-reference.md line 194: "runs only once per session then is removed. Skills only" | Correct — considered for F2 |
| Hook execution order across scopes | Not specified in hooks-reference.md | Absence confirmed — justifies exemption approach over skill-scoped hooks |
