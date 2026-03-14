# Exercise Run Remediation — 20260310-153119

**Status:** Proposed
**Date:** 2026-03-10
**Owner:** ARIA Development
**Scope:** `src/aria_esi/services/navigation/`, `src/aria_esi/store/market/`, `src/aria_esi/mcp/dispatchers/market.py`, `.claude/skills/journal/`, `.claude/skills/help/`
**Related:** `dev/reviews/exercise-outputs/20260310-153119/REPORT.md`, `PREREQ_PATH_DISAMBIGUATION.md`, `CONTEXT_EFFICIENCY_PROPOSAL.md`

---

## Executive Summary

The 20260310-153119 exercise run (47 queries, 100% completion, 9.0/10 average quality) surfaced five issues across the MCP tool layer, data store, and skill prompts. Validation determined that none are critical — the highest-severity item (route safe+avoid) is correct behavior with a poor error message, not a pathfinding bug. All five fixes are low-effort and independent.

| # | Issue | Layer | Validated Severity | Effort |
|---|-------|-------|--------------------|--------|
| R1 | Route safe+avoid returns bare "no route" error | MCP service | Medium | Low |
| R2 | Watchlist case-sensitive name collision | Data store | Low | Low |
| R3 | Journal asks for agent instead of cross-referencing records | Skill prompt | Low | Trivial |
| R4 | Help skill excessive file reads (42.8s) | Skill prompt | Low | Trivial |
| R5 | Market tool unused parameter warnings | MCP dispatcher | Cosmetic | Trivial |

---

## R1: Route Safe+Avoid Error Message

### Problem

`universe(route, mode="safe", avoid_systems=["Uedama"])` from Dodixie to Jita returns `"No route from Dodixie to Jita"` — a generic error that implies the tool is broken.

The report classified this as a HIGH priority pathfinding bug. Validation determined it is **correct behavior**: there is no highsec-only route between Dodixie and Jita that avoids Uedama. The Niarja crossing was removed by Triglavians (Pochven), leaving the Tama lowsec corridor as the only alternative. Safe mode correctly rejects that path at the post-validation gate (`router.py:100-101`).

The issue is UX: the error message gives no indication of *why* the route failed.

### Evidence

From `22-route-q1.tools.json`:
- Call 1: `mode="safe", avoid_systems=["Uedama"]` → `"Error: No route from Dodixie to Jita"`
- Call 2: `mode="shortest", avoid_systems=["Uedama"]` → 12-jump route through Tama (lowsec)

The response recovered by falling back to shortest mode with a manual threat overlay — the user got a complete answer, but at the cost of an extra tool call and model-side reasoning that should have been unnecessary.

### Proposed Fix

Add a `reason` string when safe-mode post-validation rejects a path.

**File:** `src/aria_esi/services/navigation/router.py` (lines 98-101)

```python
# Before:
if path and any(self.universe.security[idx] < HIGHSEC_THRESHOLD for idx in path):
    return []

# After:
if path and any(self.universe.security[idx] < HIGHSEC_THRESHOLD for idx in path):
    from .errors import RouteNotFoundError
    raise RouteNotFoundError(
        origin=self.universe.system_name(origin_idx),
        destination=self.universe.system_name(dest_idx),
        reason="all paths avoiding specified systems traverse lowsec; try mode='shortest' with avoid_systems for a threat-annotated alternative",
    )
```

The `RouteNotFoundError` class already supports `reason` (`errors.py:22-28`) — it is simply never populated by callers. The MCP layer at `_actions_navigation.py:110` catches empty paths and raises its own `RouteNotFoundError`; we move the raise into the router so it carries the reason.

**Caller update** — `_actions_navigation.py:109-110`: let the service-level exception propagate instead of checking for empty path:

```python
# Before:
if not path:
    raise RouteNotFoundError(origin_resolved.canonical_name, dest_resolved.canonical_name)

# After:
# RouteNotFoundError now raised by the router with reason when safe-mode
# post-validation fails; empty path (disconnected graph) still caught here
if not path:
    raise RouteNotFoundError(origin_resolved.canonical_name, dest_resolved.canonical_name)
```

No change needed to the MCP-layer catch — it already surfaces the full error message.

### Test

Add a test case in `tests/services/navigation/test_router.py` where the only path between two systems traverses lowsec, and verify that `mode="safe"` raises `RouteNotFoundError` with a non-None `reason`.

---

## R2: Watchlist Case-Sensitive Name Collision

### Problem

The watchlist system allows both "Default" and "default" to coexist as separate watchlists. The `entity_watchlists` table in `store/market/database.py:353-356` uses UNIQUE indexes on `name` without `COLLATE NOCASE`. The service layer (`services/redisq/entity_watchlist.py:197-203`) performs case-sensitive lookups. This can cause:

1. Silent duplicate watchlists created by different code paths using different casing
2. UNIQUE constraint violations when adding entities to the "wrong" case variant
3. Ambiguous behavior when the CLI resolves a watchlist name

### Evidence

From `26-watchlist-q1.md`: `watchlist-list` returned three watchlists including both "Default" and "default". Adding CODE. to "Default" surfaced a UNIQUE constraint error.

### Proposed Fix

Normalize via index rebuild, inline migration, and application-level normalization.

**Phase 1: Schema definition** — `store/market/database.py`

Add `COLLATE NOCASE` to the `name` column definition in `entity_watchlists`:

```sql
CREATE TABLE IF NOT EXISTS entity_watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE,
    ...
)
```

This applies to **new installs only**. SQLite does not support `ALTER COLUMN`, and `CREATE TABLE IF NOT EXISTS` is a no-op on existing databases. For existing installs, the index rebuild (Phase 2) and application normalization (Phase 3) are sufficient — the column-level collation is defense-in-depth for fresh databases.

**Phase 2: Inline versioned migration (v9→v10)** — `store/market/database.py`

Add a v10 migration block in `_run_migrations()` and bump `SCHEMA_VERSION` to 10. The migration performs two steps in order:

Step 1 — **Dedup merge.** Items live in `entity_watchlist_items` (FK: `watchlist_id → entity_watchlists(watchlist_id)`, `ON DELETE CASCADE`). The migration must:

1. Identify groups of watchlists whose names differ only by case (`GROUP BY name COLLATE NOCASE HAVING COUNT(*) > 1`)
2. For each group, pick the lowest-`watchlist_id` row as the survivor
3. Re-point `entity_watchlist_items` rows from duplicate watchlists to the survivor, using `INSERT OR IGNORE` to handle items that already exist in both (composite PK: `watchlist_id, entity_id, entity_type`)
4. Delete the duplicate `entity_watchlists` rows (CASCADE will clean up any remaining orphaned items)

Step 2 — **Index rebuild with `COLLATE NOCASE`:**

```sql
DROP INDEX IF EXISTS idx_entity_watchlists_global;
DROP INDEX IF EXISTS idx_entity_watchlists_owner;

CREATE UNIQUE INDEX idx_entity_watchlists_global
    ON entity_watchlists(name COLLATE NOCASE)
    WHERE owner_character_id IS NULL;

CREATE UNIQUE INDEX idx_entity_watchlists_owner
    ON entity_watchlists(name COLLATE NOCASE, owner_character_id)
    WHERE owner_character_id IS NOT NULL;
```

The dedup must run before the index rebuild — creating a `COLLATE NOCASE` UNIQUE index will fail if case-variant duplicates still exist.

**Phase 3: Application-level normalization** — in `entity_watchlist.py`, normalize input names to lowercase in `create_watchlist()` and `get_watchlist()` for defense-in-depth:

```python
name = name.strip().lower()
```

### Test

| Test | What it proves |
|------|----------------|
| `test_v10_migration_merges_case_duplicates` | Two watchlists ("Default", "default") with overlapping items are merged into one; items from both survive; duplicate watchlist row is deleted |
| `test_case_insensitive_uniqueness_after_migration` | After v10 migration, `INSERT INTO entity_watchlists` with a name differing only by case from an existing row raises `IntegrityError` |
| Existing watchlist tests pass | Regression gate |

### Scope

- `store/market/database.py` — schema definition (`COLLATE NOCASE` in `CREATE TABLE`) + v10 migration block in `_run_migrations()` + bump `SCHEMA_VERSION` to 10
- `services/redisq/entity_watchlist.py` — input normalization
- `commands/redisq.py` — no change needed (inherits from service layer)

---

## R3: Journal Auto-Resolve From Existing Records

### Problem

The journal skill asked an open-ended question ("Who was the agent?") when the user logged "Gone Berserk against Equilibrium of Mankind", despite having two existing records showing Gone Berserk consistently logged under Federation Navy. The pilot profile also declares `Mission Provider: Federation Navy`.

The skill behaved correctly (it doesn't assume), but the UX is suboptimal. When existing records provide a strong signal, the skill should suggest rather than ask.

### Evidence

From `38-journal-q1.tools.json`: the skill read `missions.md` (which contains two Gone Berserk entries under Federation Navy) and `profile.md` (which declares Federation Navy as mission provider), then asked for agent clarification anyway.

### Proposed Fix

Add a cross-reference step to the journal skill prompt.

**File:** `.claude/skills/journal/SKILL.md`

Add after the current mission-parsing step:

```markdown
### Cross-Reference Check

Before asking the user for missing fields (agent, level, etc.):

1. Read the pilot's `missions.md` for prior entries of the same mission name
2. Check the pilot's `profile.md` for `Mission Provider`
3. If existing records consistently show the same agent for this mission,
   **suggest rather than ask**: "Your records show Gone Berserk is from
   Federation Navy — logging under that agent. Correct?"
4. Only ask an open-ended question when records are ambiguous (multiple
   agents for the same mission) or no prior entries exist
```

This is a skill-prompt-only change. No code modification needed. Per the Claude Code skills architecture, skills are markdown instructions that guide the model's behavior — adding a cross-reference step to the prompt directly addresses the issue.

### Risk

Low. The change is additive (new step in an existing workflow). The "suggest rather than ask" pattern preserves user override capability while reducing friction.

---

## R4: Help Skill Efficiency

### Problem

The help skill took 42.8s to generate a command listing. The tool trace shows:
- 4 attempted reads of `_index.json` (70KB, triggered persisted-output handling each time)
- 1 denied `jq` Bash command
- 1 spawned general-purpose Agent subagent (which itself read the file again)
- Multiple redundant file reads of the same content

The skill listing is static between deploys — it changes only when skills are added or modified.

### Evidence

From `01-help-q1.tools.json`: 7 tool calls for what should be a single file read and format operation. Compare with `47-reactions-q2` at 8.5s for a complex multi-tool query.

### Proposed Fix

**Option A (recommended): Dynamic context injection**

Use the `` !`command` `` syntax (per Claude Code skills documentation, "Inject dynamic context") to pre-render the help listing before the skill prompt reaches the model. This eliminates all runtime file reads.

**File:** `.claude/skills/help/SKILL.md`

Replace the current "read `_index.json` and format" instruction with a pre-computed injection:

```yaml
---
name: help
description: Display available ARIA commands and capabilities
---

## Available Commands

!`jq -r '.skills[] | select(.name != "aria-review") | "- /\(.name): \(.description)"' .claude/skills/_index.json`

## Usage

Type `/<command>` to invoke any skill, or describe what you need in natural language.
```

The `` !`jq ...` `` command executes at skill-load time (preprocessing, not model execution) and injects the formatted listing directly into the prompt. The model receives the final text with no file reads needed.

This aligns with the Claude Code skills guidance: "Each `` !`command` `` executes immediately (before Claude sees anything). The output replaces the placeholder in the skill content. Claude receives the fully-rendered prompt with actual data."

**Option B (alternative): Precomputed help index**

Generate a `help_listing.md` file as a build artifact (similar to `_index.json` generation), read it as a single small file.

Option A is preferred because it requires no build step and stays automatically up-to-date.

### Scope

- `.claude/skills/help/SKILL.md` — rewrite with dynamic injection
- No supporting code changes

---

## R5: Market Tool Unused Parameter Warnings

### Problem

The market MCP dispatcher (`dispatchers/market.py`) accepts 50+ parameters for all 18 actions in a single function signature. Invention-specific parameters (`encryption_skill=4`, `science_skill_1=4`, `science_skill_2=4`) have non-None defaults, so the validator flags them as "not used by action 'find_nearby'" on every non-invention query.

### Evidence

From `30-find-q1.tools.json` and `31-find-q2.tools.json`: tool responses include 3 warnings each about unused invention parameters.

### Proposed Fix

Add the missing invention-parameter defaults to the existing `get_default_values()` helper.

`validate_action_params()` already filters out parameters whose value matches their dispatcher default via the `get_default_values(dispatcher)` function (`validation.py:233-294`). The invention parameters are simply missing from the market defaults dict. No signature change or `inspect.signature()` introspection needed.

**File:** `src/aria_esi/mcp/validation.py`, in `get_default_values()`, market section

Add the three missing defaults:

```python
"encryption_skill": 4,
"science_skill_1": 4,
"science_skill_2": 4,
```

### Scope

- `src/aria_esi/mcp/validation.py` — add three entries to `get_default_values("market")`
- `tests/mcp/test_validation.py` — add test: `validate_action_params("market", "find_nearby", {"encryption_skill": 4, ...})` returns no warnings for these parameters

---

## Implementation Plan

All five fixes are independent and can be implemented in any order or in parallel.

| Fix | Phase | Effort | Test Impact |
|-----|-------|--------|-------------|
| R1: Route error message | Single PR | Low | 1 new test case |
| R2: Watchlist case normalization | Single PR (schema + v10 migration + service) | Low | 2 new tests (dedup merge, uniqueness enforcement) + existing tests pass |
| R3: Journal cross-reference | Single PR (skill prompt edit) | Trivial | Verify in next exercise run |
| R4: Help dynamic injection | Single PR (skill rewrite) | Trivial | Manual invocation test |
| R5: Parameter warning suppression | Single PR (validation defaults) | Trivial | 1 new test case |

**Recommended priority order:** R4, R3, R5, R1, R2

R4 and R3 are trivial skill-prompt changes with immediate UX improvement. R5 is a clean code-quality fix. R1 and R2 involve service-layer changes and warrant unit tests.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| R1: Router raising instead of returning empty list may break callers | Medium | `_actions_navigation.py` already catches `RouteNotFoundError`; the exception propagates the same way |
| R2: v10 migration on existing databases with duplicates | Low | Dedup uses `INSERT OR IGNORE` to handle overlapping items; column `COLLATE NOCASE` is new-install only (no `ALTER COLUMN` needed); index rebuild follows dedup to avoid UNIQUE violation |
| R2: Case normalization changes existing watchlist names | Low | Normalize to lowercase only; document the change |
| R2: Dedup must run before index rebuild | Low | Both steps are in a single v10 migration block executed sequentially |
| R4: `jq` not available in all environments | Low | `jq` is already a project dependency (used in hooks and scripts); add a fallback `python -c` alternative if needed |
| R4: Dynamic injection increases skill-load latency | Negligible | `jq` on a 70KB file completes in <50ms vs. 42.8s current |

---

## Out of Scope

- **Arbitrage anomaly filtering** (report High-ROI item #1): requires changes to the market MCP tool's result pipeline. Tracked separately.
- **Help skill precomputed index** (Option B): not needed if dynamic injection (Option A) works.
- **Market dispatcher restructuring into per-action classes**: architecturally desirable but disproportionate effort for a cosmetic fix.
- **ESI-authenticated exercise run**: recommended as follow-up but is an operational activity, not a code fix.
