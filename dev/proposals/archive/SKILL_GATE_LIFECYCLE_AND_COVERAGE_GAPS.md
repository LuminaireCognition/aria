# Skill Gate Lifecycle Fix & Coverage Gap Remediation

**Status:** Proposed
**Date:** 2026-03-11
**Owner:** ARIA Development
**Scope:** `dev/scripts/hooks/`, `dev/scripts/exercise-runner.py`, `.claude/settings.local.json`, `src/aria_esi/store/market/database.py`, `docs/MCP_FALLBACK.md`, `.claude/skills/_index.json`
**Related:** `dev/reviews/exercise-outputs/20260311-134340/RECOMMENDATIONS.md`, `SKILL_GATE_AND_EXERCISE_HARDENING.md`

---

## Executive Summary

The 20260311-134340 exercise run (47 queries, 100% completion) validated all fixes from `SKILL_GATE_AND_EXERCISE_HARDENING.md` — the `CLAUDE_ENV_FILE` bug is resolved, MCP fallback discipline is clean, and infrastructure files are protected. The remaining systemic issue is **skill invocation non-determinism: 21% of queries (10/47) bypassed skill loading** despite the skill-gate hook being active.

Root cause: the skill-gate marker is **session-scoped**, so once any Skill tool call creates the marker, all subsequent MCP calls in the session pass through unchecked — even when they belong to a different query that never invoked a skill. Three secondary issues compound this: build-cost has no CLI fallback (3/3 queries failed), a watchlist schema version mismatch causes data corruption, and several skill descriptions lack the natural-language keywords needed for auto-invocation.

| # | Fix | Severity | Effort | Layer |
|---|-----|----------|--------|-------|
| F1 | Per-turn skill gate lifecycle | Critical | Low | Hook script |
| F2 | Deploy skill gate to production | High | Low | Settings |
| F3 | Build-cost CLI fallback | High | Medium | CLI + docs |
| F4 | Watchlist schema version fix | Medium | Low | Database |
| F5 | Skill description keyword audit | Medium | Low | Skill index |
| F6 | Per-skill brevity targets | Low | Low | Skill definitions |

### Relationship to Prior Proposals

`SKILL_GATE_AND_EXERCISE_HARDENING.md` (F1-F4 all confirmed working) fixed the catastrophic MCP blackout from run 20260311-105805. This proposal addresses the next layer: the gate's per-session design flaw (F1), production deployment (F2), and coverage gaps exposed now that the gate itself is functional (F3-F6).

R7 from the recommendations (skill-enforcer timing gap) requires no action — it is fully addressed by F1. R8 (watchlist entity resolution) is deferred to a follow-up as low-impact.

---

## F1: Per-Turn Skill Gate Lifecycle (Critical)

### Problem

The current `skill-gate.sh` uses a **session-scoped** marker file at `/tmp/claude-skill-gate-${SESSION_ID}`. Once any Skill tool call creates this marker, it persists for the entire session. Subsequent queries in the same session bypass the gate entirely:

1. Query 1: user asks about routes → `/route` Skill invoked → marker created → MCP calls pass ✓
2. Query 2: user asks a price question → no Skill invoked → **marker still exists** → MCP calls pass ✗
3. Query 3: user asks about orientation → no Skill invoked → **marker still exists** → MCP calls pass ✗

**Evidence:** In the exercise run, queries 12 (hunting-grounds q1) and 14 (hunting-grounds q3) both invoked the Skill tool, but query 13 (hunting-grounds q2) did not — yet all three produced MCP-backed output because the marker from q1 carried across. The 10 `no-skill` cases cluster after successful skill invocations, confirming the marker leak.

### Proposed Fix

Add a **`UserPromptSubmit` hook** that deletes the marker file before each new prompt. This resets the gate per-turn so each query must independently invoke the Skill tool before MCP calls are allowed.

Per the [hooks reference](https://code.claude.com/docs/en/hooks), `UserPromptSubmit` fires "when you submit a prompt, before Claude processes it" and supports `type: "command"` handlers. `UserPromptSubmit` does not support matchers — it always fires on every occurrence. This is the correct lifecycle point for resetting per-turn state — it fires before the model plans any tool calls.

**New file:** `dev/scripts/hooks/skill-gate-cleanup-turn.sh`

```bash
#!/bin/bash
# UserPromptSubmit hook: reset the skill-gate marker at the start of each turn.
#
# This ensures each user prompt requires its own Skill tool invocation
# before MCP tools are allowed. Without this, the marker persists from
# a prior turn and subsequent queries bypass the gate.
INPUT=$(cat)
SID=$(echo "$INPUT" | jq -r '.session_id // empty')
if [[ -n "$SID" && "$SID" != "null" ]]; then
  rm -f "/tmp/claude-skill-gate-${SID}"
fi
exit 0
```

**Hook ordering:** The existing `skill-enforcer.sh` also occupies `UserPromptSubmit`. Per the [hooks reference](https://code.claude.com/docs/en/hooks), multiple matcher groups under the same event execute in array order. The cleanup must run **first** (before the enforcer emits `additionalContext`), so it appears earlier in the array:

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

### Why Not Skill-Scoped Hooks

The [hooks reference](https://code.claude.com/docs/en/hooks) documents that skills can define hooks in their YAML frontmatter, scoped to the skill's lifecycle (`hooks` field in frontmatter). This would be more architecturally clean (each skill manages its own MCP gate) but:

1. Requires modifying all ~50 skill definitions
2. Does not address the core problem — queries where the model calls MCP tools *without* invoking any skill. The gate must operate at the session level, not the skill level.

Skill-scoped hooks remain a valid defense-in-depth pattern for future consideration.

### Scope

- `dev/scripts/hooks/skill-gate-cleanup-turn.sh` — new file
- `dev/scripts/exercise-runner.py` — add the cleanup hook to the `UserPromptSubmit` array injected at line 390, inserting it **before** the existing `skill-enforcer.sh` entry. The runner currently replaces the `UserPromptSubmit` key entirely (line 390: `merged["hooks"]["UserPromptSubmit"] = [...]`), so the new hook is simply prepended to the array literal.

### Test

1. Re-run the exercise suite with `--explicit` — the runner's hook injection now includes `skill-gate-cleanup-turn.sh` before `skill-enforcer.sh`
2. Run 3 sequential queries in a single session: `/route Jita to Amarr`, then `How much is a Vexor?`, then `/orient in Tama`
3. Verify: query 1 invokes Skill + MCP passes; query 2 must invoke Skill independently (marker was cleared); query 3 must invoke Skill independently

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Marker deletion races with parallel tool planning | Low | `UserPromptSubmit` fires before the model generates any response. The marker cannot exist yet for the current turn. |
| `jq` unavailable on target system | Low | Same dependency as `skill-gate.sh` which is already deployed. |
| Cleanup hook breaks non-skill queries | None | If no marker exists, `rm -f` is a no-op. Non-skill queries never create markers. |

---

## F2: Deploy Skill Gate Hooks to Production (High)

### Problem

The skill-gate infrastructure (`skill-gate.sh`, `skill-enforcer.sh`, `skill-gate-cleanup.sh`, and the new `skill-gate-cleanup-turn.sh`) only runs during exercise runs. The exercise runner dynamically injects these hooks into `.claude/settings.local.json`, then removes them afterward. **Production interactive sessions have zero skill enforcement.**

The `CLAUDE.md` directive ("Skills gate authoritative data. If a query falls within a skill's domain, invoke the skill") is prompt-only. The exercise run proves this is insufficient — 21% bypass rate even with the reinforcement of `additionalContext` injection from `skill-enforcer.sh`.

### Proposed Fix

Register the hooks permanently in `.claude/settings.local.json`. Per the [hooks guide](https://code.claude.com/docs/en/hooks-guide), this is the correct location for project-local, non-shareable hooks — it is gitignored and scoped to this project only.

**File:** `.claude/settings.local.json`

Use `$CLAUDE_PROJECT_DIR` for portable paths per the [hooks reference security best practices](https://code.claude.com/docs/en/hooks):

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
    ],
    "PreToolUse": [
      {
        "matcher": "Skill|mcp__.*",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/dev/scripts/hooks/skill-gate.sh"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/dev/scripts/hooks/skill-gate-cleanup.sh"
          }
        ]
      }
    ]
  }
}
```

**Note on `UserPromptSubmit`:** Per the [hooks reference](https://code.claude.com/docs/en/hooks), `UserPromptSubmit` does not support matchers — it always fires on every occurrence. Matcher groups under this event omit the `matcher` field entirely.

**Matcher design:** The PreToolUse matcher `"Skill|mcp__.*"` fires for both the Skill tool (to record invocation) and all MCP tools (to check the gate). Per the [hooks reference](https://code.claude.com/docs/en/hooks), matchers use regex patterns against `tool_name`. Non-MCP, non-Skill tools (Read, Edit, Bash, etc.) pass through unconditionally — the matcher avoids invoking `skill-gate.sh` for those tools entirely, and the script's own line 26 check (`[[ "$TOOL_NAME" != mcp__* ]]`) provides defense-in-depth.

**Exercise runner merge:** The runner currently **replaces** each hook event key in `settings.local.json` (lines 390-412 of `exercise-runner.py`). After F2 deploys production hooks, the runner must preserve them. Update the runner's hook injection to **skip-if-present** by command path. Specifically:

1. Read existing `merged["hooks"].get("UserPromptSubmit", [])` before overwriting
2. For each hook the runner wants to inject, check if a matcher group with the same `command` path already exists in the array. **Skip** if present; append only if absent.
3. Apply the same skip-if-present logic to `PreToolUse` and `SessionEnd`
4. On cleanup (lines 539-555), restore the original entries rather than removing the keys entirely — this is already handled by the `saved_settings` restore path

This prevents double-registration when production hooks from F2 overlap with exercise runner hooks. During the run, each hook executes exactly once; on cleanup, `saved_settings` restore returns `.claude/settings.local.json` to its pre-run state.

### Scope

- `.claude/settings.local.json` — permanent hook registration
- `dev/scripts/exercise-runner.py` — update hook injection (lines 390-412) to merge with existing settings instead of replacing

### Dependency

**Requires F1.** Without per-turn marker reset, production sessions would allow all MCP calls after the first Skill invocation, providing minimal value.

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Gate blocks legitimate MCP calls for non-skill queries | Medium | The gate's defensive fallback (allow if `session_id` is missing) and `skill-enforcer.sh` `additionalContext` injection handle edge cases. Monitor for false positives. |
| `$CLAUDE_PROJECT_DIR` not set | Low | `$CLAUDE_PROJECT_DIR` is always set by Claude Code per the [hooks reference](https://code.claude.com/docs/en/hooks). Falls back to cwd if absent. |
| Exercise runner overwrites production hooks | Low | Addressed in F2 Scope: runner uses skip-if-present logic to avoid double-registration. Restore path handles cleanup via `saved_settings`. |

### Rollback

Delete `.claude/settings.local.json` or remove the `hooks` key. Immediate effect — no restart needed since hooks are read per-invocation.

---

## F3: Build-Cost CLI Fallback (High)

### Problem

3/3 build-cost queries failed completely. The MCP `market(action="build_cost")` action was blocked by the skill gate, and no CLI fallback exists. The model correctly followed MCP fallback discipline (no infrastructure diagnosis) but had nothing to fall back to, so it redirected users to external websites — a 100% failure rate for this skill category.

**Validated:**
- `build_cost` is implemented as an MCP-only action in `src/aria_esi/mcp/dispatchers/market.py` (lines 47, 73, 409)
- The service layer exists at `src/aria_esi/services/industry_costs.py`
- `uv run aria-esi --help` does not list a `build-cost` command
- `docs/MCP_FALLBACK.md` has no entry for build-cost

### Proposed Fix

#### Step 1: Add `aria-esi build-cost` CLI Command

Create a thin CLI entry point wrapping the existing `IndustryCostService`. The service layer already handles all the computation — the CLI command just provides input parsing and output formatting.

**File:** `src/aria_esi/cli/commands/build_cost.py` (new)

The command should accept:
- `item_name` (positional) — item to cost (string, resolved via SDE name lookup)
- `--me` (optional, default 0) — material efficiency level (0-10)
- `--runs` (optional, default 1) — number of runs
- `--system` (optional) — manufacturing system name (string, resolved to system ID via SDE). Used for system cost index lookup.
- `--format` (optional, `table`/`json`) — output format

**Table output columns:** item name, material name, quantity (adjusted for ME), unit price, line total. Footer: total material cost, installation cost (if `--system`), total cost per run.

**Service interface (confirmed):** The CLI delegates to functions in `src/aria_esi/services/industry_costs.py`, which is a standalone module with no MCP imports. Key functions:
- `estimate_total_build_cost(material_cost, estimated_item_value, system_cost_index, facility_name, facility_tax)` → dict with `material_cost`, `job_cost`, `total_cost`, `cost_breakdown`
- `calculate_job_cost(estimated_item_value, system_cost_index, facility_name, facility_tax)` → dict with fee components

Material costs and item resolution come from the SDE/market layers, not this service. The CLI must resolve `item_name` → blueprint → materials via SDE before calling `estimate_total_build_cost`.

#### Step 2: Register in MCP Fallback Table

**File:** `docs/MCP_FALLBACK.md`

Add row:

```
| `/build-cost` | `market(action="build_cost", ...)` | `aria-esi build-cost` |
```

#### Step 3: Ensure Skill Gate Compatibility

When the `/build-cost` skill is invoked via the Skill tool, the marker is created and subsequent `market(action="build_cost")` MCP calls pass through. This is the expected flow — the CLI fallback is only needed when MCP is unavailable for non-gate reasons (connection failure, server down).

### Scope

- `src/aria_esi/cli/commands/build_cost.py` — new file, thin CLI wrapper
- `src/aria_esi/cli/main.py` — register command
- `docs/MCP_FALLBACK.md` — add entry

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| CLI output format differs from MCP response | Low | The model adapts to different formats. CLI and MCP need not be identical. |
| Service layer has MCP-specific dependencies | None | Confirmed: `industry_costs.py` imports only `json`, `math`, `pathlib`, `typing`. No MCP types. |

---

## F4: Watchlist Schema Version Fix (Medium)

### Problem

The exercise run exposed functional bugs in watchlist operations:
- `sync-wars`: `UNIQUE constraint failed: entity_watchlists.name, entity_watchlists.owner_character_id`
- `watchlist-show`: `Watchlist 'Default' not found`

### Root Cause (Confirmed)

In `src/aria_esi/store/market/database.py`:

| Location | Value | Expected |
|----------|-------|----------|
| Line 31: `SCHEMA_VERSION` | `10` | `10` (correct) |
| Line 396: SQL `INSERT` | `'8'` | `'10'` |

The `SCHEMA_SQL` block (used for fresh database creation) hardcodes `schema_version = '8'` in its metadata INSERT, even though the DDL includes v10 features (COLLATE NOCASE). On first startup:

1. Fresh database created with DDL that includes v10 schema features
2. Metadata row records `schema_version = '8'`
3. On next startup, `_get_schema_version()` returns 8
4. Migrations 8→9 and 9→10 run against a database that already has v10 schema
5. Migration 9→10 attempts to deduplicate and recreate watchlists, potentially corrupting data or hitting UNIQUE constraints

### Proposed Fix

**File:** `src/aria_esi/store/market/database.py`

1. **Line 396:** Replace the hardcoded `'8'` with a format placeholder. `SCHEMA_SQL` contains no other `{}` characters (verified — SQL DDL uses only parentheses), so `.format()` is safe.

```python
# In SCHEMA_SQL (line 396), replace the hardcoded value with a placeholder:
INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '{schema_version}');

# At execution time (where SCHEMA_SQL is passed to conn.executescript),
# apply: SCHEMA_SQL.format(schema_version=SCHEMA_VERSION)
```

This keeps `SCHEMA_SQL` as a plain string template and ensures `SCHEMA_VERSION` (line 31) is the single source of truth.

2. **Update test fixture** in `tests/services/redisq/test_entity_watchlist.py` (confirmed path) line 37 to add `COLLATE NOCASE` on the `name` column, matching production schema.

3. **Add a regression test:**

```python
def test_schema_sql_version_matches_constant():
    """Ensure SCHEMA_SQL metadata version stays in sync with SCHEMA_VERSION."""
    assert f"'{SCHEMA_VERSION}'" in SCHEMA_SQL or str(SCHEMA_VERSION) in SCHEMA_SQL
```

### Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Existing databases already have version 8 in metadata | None | They already ran migrations 8→9→10 on first upgrade. This fix only affects fresh databases. |
| String formatting in SQL introduces injection risk | None | `SCHEMA_VERSION` is a module-level integer constant, not user input. |

---

## F5: Skill Description Keyword Audit (Medium)

### Problem

The skill invocation system relies on Claude matching natural language queries to skill descriptions. Per the [skills documentation](https://code.claude.com/docs/en/skills):

> Claude uses [the description] to decide when to apply the skill.

And from the troubleshooting section:

> If Claude doesn't use your skill when expected: Check the description includes keywords users would naturally say

The 10 no-skill cases include queries where the natural language didn't trigger the expected skill. Some are explained by the session-scoped marker leak (F1), but others suggest description gaps:

| Skill | Current Description | Missed Query | Missing Keywords |
|-------|-------------------|--------------|------------------|
| `build-cost` | "Manufacturing cost calculator. Calculates material costs, profit margins, and ME efficiency." | "What's the cost to build a Dominix..." | "cost to build", "profitable to build" |
| `price` | "EVE Online market price lookups. Use for item valuation, buy/sell spreads, or market analysis." | "How much is a Vexor Navy Issue..." | "how much is", "selling for" |

Note: the `_index.json` already has a `trigger_phrases` field with good coverage (e.g., `"cost to build [item]"`, `"how much is [item] worth"` are listed). But per the [skills documentation](https://code.claude.com/docs/en/skills), it's the **description** field that Claude uses for invocation decisions — `trigger_phrases` is an ARIA-specific index field used by the exercise runner, not by Claude's skill matching.

### Proposed Fix

Revise descriptions to embed the natural-language phrases users actually say. Per the [skills documentation](https://code.claude.com/docs/en/skills), descriptions are loaded into context so Claude knows what's available, so they should be concise:

| Skill | Current | Proposed |
|-------|---------|----------|
| `build-cost` | "Manufacturing cost calculator. Calculates material costs, profit margins, and ME efficiency." | "Manufacturing cost calculator. Use for 'cost to build', profit margins, build-vs-buy, and ME efficiency." |
| `price` | "EVE Online market price lookups. Use for item valuation, buy/sell spreads, or market analysis." | "Market price lookups. Use for 'how much is [item]', price checks, buy/sell spreads, or item valuation." |

Update both the SKILL.md frontmatter `description` field and the corresponding entry in `_index.json`.

### Impact

Improves auto-invocation rates without any hook or infrastructure changes. Complementary to F1/F2 — better descriptions reduce reliance on enforcement hooks. Even with perfect gate enforcement, better descriptions mean the model invokes the *right* skill rather than requiring the gate to block a wrong-skill MCP call.

---

## F6: Per-Skill Brevity Targets (Low)

### Problem

7/47 responses (15%) exceeded the 30-line brevity limit in `CLAUDE.md`. The worst offender (exploration-q1) hit 70 lines. All 7 are tactical or structured skills that produce tabular data, multi-section intelligence reports, or EFT-format fittings.

The 30-line global target makes sense for conversational responses but creates tension with structured output. A threat assessment with system activity tables, engagement notes, and recommendations is inherently longer than a chat reply.

### Proposed Fix

Don't change the global brevity target. Instead, add `preferred_max_lines` to the SKILL.md frontmatter for skills that need it. Per `.claude/rules/skills.md`, this is the documented mechanism:

> If a skill declares `preferred_max_lines` in its frontmatter, target that line count instead of the global 30-line default. This is a soft target, not a hard ceiling — complex or wide-scope queries may exceed it by up to 50%.

This approach serves both runtime behavior (Claude reads the frontmatter and adjusts output length) and exercise runner scoring (the runner can read `preferred_max_lines` to apply per-skill thresholds instead of the global 30-line default).

**Example frontmatter addition:**

```yaml
---
name: threat-assessment
description: ...
preferred_max_lines: 45
---
```

Skills to update:
- `exploration` (70 lines → `preferred_max_lines: 45`)
- `mission-brief` (52 lines → `preferred_max_lines: 45`)
- `orient` (50 lines → `preferred_max_lines: 45`)
- `threat-assessment` (50 lines → `preferred_max_lines: 45`)
- `ransom-calc` (48 lines → `preferred_max_lines: 40`)
- `fitting` (44 lines → `preferred_max_lines: 45`)
- `mark-assessment` (41 lines → `preferred_max_lines: 40`)

---

## Implementation Plan

```
Phase 1 — Gate lifecycle (F1 depends on nothing; F2 depends on F1):
  F1: Create skill-gate-cleanup-turn.sh
  F1: Add cleanup hook to exercise-runner.py UserPromptSubmit array (before enforcer)
  F1: Re-run exercise suite to measure improvement
  F2: Deploy hooks to .claude/settings.local.json (after F1 validates)
  F2: Update exercise-runner.py hook injection to merge (not replace) existing entries

Phase 2 — Coverage gaps (all independent, parallel with Phase 1):
  F4: Fix database.py schema version + add regression test
  F5: Audit and update skill descriptions
  F6: Add brevity targets to tactical SKILL.md files

Phase 3 — CLI (independent):
  F3: Implement aria-esi build-cost CLI command
  F3: Register in MCP_FALLBACK.md
  F3: Re-run build-cost exercises to validate

Validation:
  Re-run full exercise suite after F1+F2 deployed
  Target: no-skill rate < 5% (down from 21%)
```

### Recommended Execution Order

**F1 → F4 → F5 → F2 → F3 → F6**

F1 is the critical path — fixes the structural cause of 21% skill bypass. F4 is a straightforward confirmed bug fix. F5 is a quick audit pass. F2 deploys enforcement to production once F1 is validated. F3 requires new CLI implementation (medium effort). F6 is lowest priority (cosmetic quality improvement).

---

## Success Criteria

| Metric | Current (20260311-134340) | Target (post-fix) |
|--------|--------------------------|-------------------|
| Skill bypass rate (no-skill) | 10/47 (21%) | < 3/47 (< 5%) |
| Build-cost success rate | 0/3 (0%) | 3/3 (100%) |
| Watchlist operations | 1/2 failed | 2/2 pass |
| Brevity violations (>30 lines) | 7/47 (15%) | < 3/47 (tactical skills use per-skill targets) |
| Infrastructure file modifications | 0 | 0 (maintained) |
| MCP fallback discipline violations | 0 | 0 (maintained) |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| F1: Marker deletion races with first-turn tool planning | Low | `UserPromptSubmit` fires before the model generates any response. Race window is zero. |
| F2: Gate blocks legitimate non-skill MCP queries in production | Medium | Monitor for false positives. Gate allows all calls if `session_id` is missing. Users can remove hooks from `settings.local.json` to disable. |
| F2: Exercise runner overwrites production hooks | Medium | Addressed in F2 Scope: runner uses skip-if-present deduplication by command path. |
| F3: Service layer has MCP-specific dependencies | None | Confirmed: `industry_costs.py` has no MCP imports. |
| F5: Description changes cause over-triggering | Low | Each description stays within ~100 chars. Monitor for false-positive skill invocations in next exercise run. |

---

## Out of Scope

- **skill-enforcer.sh timing gap (R7):** The `additionalContext` injection is advisory and the model ignores it in 10/47 cases. Once F1 makes the PreToolUse gate per-turn, the enforcer becomes defense-in-depth. No changes needed.
- **Watchlist entity resolution fallback (R8):** Low impact (1 query affected). Adding `resolve_names` to the watchlist skill's `allowed-tools` or implementing a CLI `aria-esi resolve-name` command are both viable but deferred.
- **`--allowedTools` Bash pattern enforcement investigation:** Exercise 15 from the prior run showed the model bypassing `Bash(uv run:*)` restrictions. This is an upstream Claude Code behavior question, not actionable in this proposal. Tracked as a follow-up.
- **ESI-gated skill coverage:** 20 skills requiring ESI authentication were excluded from this run. A follow-up exercise run with ESI:LOW and ESI:MED filters is needed.
