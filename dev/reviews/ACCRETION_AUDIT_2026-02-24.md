# Accretion Audit
**Date:** 2026-02-24
**Prompt:** dev/prompts/architecture/accretion_auditor.md
**Reviewer:** Claude Opus 4.6

---

## Prior Audit Status (2026-02-14)

| Prior Finding | Status | Notes |
|---------------|--------|-------|
| Rank 1: Legacy `tools_*.py` (9 files, 2,941 lines) | **ACTIONED** | All 9 files deleted. MCP directory now contains only dispatchers. |
| Rank 2: Interest Engine v2 signal overengineering | **NOT ACTIONED** | 3-tier config still present. CLI sub-tools (explain, migrate, simulate, tune) unchanged. Source grew from 9,685 to 9,982 lines. |
| Rank 3: Archetype fittings library | **NOT ACTIONED** | 149 YAML files, 1.5 MB. Still unreferenced by Python code. |
| Rank 4: MCP Context Policy subsystem | **NOT ACTIONED** | 3-file subsystem (1,169 lines) unchanged. `context_budget.py` only used within `context.py`. |
| Rank 5: Sovereignty subsystem | **NOT ACTIONED** | Full subsystem intact (2,167 source + 1,675 test lines). |
| Rank 6: Notification commentary system | **NOT ACTIONED** | Commentary still default behavior. `political_entities.py` reduced from 500 to 144 lines. |
| Rank 7: Hook scripts | **PARTIALLY ACTIONED** | Boot hooks now modular (4 bash modules). Python scripts remain: grew from 9 to 12 scripts (6,829 lines including compiled .pyc counted by wc). New scripts: `aria-oauth-setup.py` (1,228 lines), `aria-credential-watch.py`. |
| QW-2: Archive dev dirs | **NOT ACTIONED** | `dev/reviews/archive/` (160 KB, 16 files) and `dev/proposals/archive/` (1.3 MB) still in tree. |
| QW-3: Delete empty/WIP files | **PARTIALLY ACTIONED** | Some cleanup done, but dev directory still has active review files. |
| QW-5: Merge political_entities.py | **PARTIALLY ACTIONED** | File reduced from 500 to 144 lines, but still separate. |

**Summary:** 1 of 7 top candidates fully actioned. 2 partially actioned. 4 completely unchanged. The highest-leverage cut (legacy tool files) was executed. The remaining debt persists.

---

## Codebase Size Profile

| Component | Lines | Notes |
|-----------|------:|-------|
| Source code (excl. vendor) | 102,601 | `src/aria_esi/` |
| Vendor (EOS) | 19,003 | Required, not reviewable |
| Tests | 108,780 | ~1.06:1 test-to-code ratio |
| Skills (markdown) | 595 KB | 48 skills, 51 directories |
| Reference data | 2.3 MB | Archetypes = 1.5 MB of this |
| Hook scripts | ~5,300 | 12 Python scripts + 4 bash modules |

**RedisQ pipeline (the largest subsystem):**

| Layer | Lines | % of Source |
|-------|------:|-------------|
| RedisQ core | 5,857 | 5.7% |
| Interest Engine v2 | 9,982 | 9.7% |
| Notifications | 7,928 | 7.7% |
| **Total RedisQ** | **23,767** | **23.2%** |
| RedisQ tests | 31,237 | 28.7% of tests |

The RedisQ killmail pipeline represents nearly a quarter of all source code and nearly a third of all tests.

---

## Top Removal Candidates

### Rank 1 -- Archetype Fittings Library

**Accretion Score: 14** `(C=3, U=1, R=5)`

**Area:** `reference/archetypes/` (149 YAML files, 1.5 MB)

**Evidence:**
- `reference/archetypes/hulls/` -- 149 YAML fit definitions
- `reference/archetypes/_shared/` -- 5 shared config files
- Zero Python imports of archetypes: `grep -r "archetypes" src/aria_esi/` returns nothing
- Referenced only in 2 skill SKILL.md files: `fitting/SKILL.md` and `ship-next/SKILL.md` (as `data_sources` globs)
- EOS fitting engine + SDE provide ground-truth data programmatically

**Why low leverage:** This was Rank 3 in the prior audit and remains completely unactioned. No Python code loads, validates, or queries these YAML files. They serve as passive read context for 2 skills, but the fitting skill already uses EOS for calculations and the SDE for requirements. The 149-file YAML hierarchy (hull > activity > level > tank > skill_tier) provides no programmatic value.

**Action:** Delete the entire `reference/archetypes/` directory. Extract 5-10 exemplar EFT blocks (Venture mining, Vexor L3, Drake L3, Dominix L4, exploration frigates) and inline them in `fitting/SKILL.md` and `ship-next/SKILL.md`.

**Expected gain:** -1.5 MB from the working tree. Eliminates a dead abstraction layer. Reduces skill `data_sources` entries that force the LLM to glob and read 149 files.

**Guardrail:** Verify `fitting/SKILL.md` and `ship-next/SKILL.md` still contain sufficient fit examples after inlining. Run `uv run python .claude/scripts/aria-skill-preflight.py --all` to confirm no broken references.

---

### Rank 2 -- Interest Engine v2 Config Tiers & CLI Tools

**Accretion Score: 12** `(C=5, U=2, R=3)`

**Area:** `src/aria_esi/services/redisq/interest_v2/` (9,982 lines source + 14,039 lines tests)

**Evidence:**
- 3 config tiers (simple, intermediate, advanced) still present: `config.py:6-8`
- 4 dedicated CLI tools: `cli/explain.py` (314), `cli/migrate.py` (402), `cli/simulate.py` (378), `cli/tune.py` (337) = 1,452 lines
- Prefetch scoring with RMS safety factors: `prefetch.py` (502 lines), `models.py:rms_safety_factor`
- 11 signal providers (10 domain + 1 loader): `signals/` (1,944 lines)
- 370-line scaling subsystem: `scaling/builtin.py`
- 489-line rule templates: `rules/templates.py`

**Why low leverage:** Unchanged from prior audit. This is enterprise-grade scoring infrastructure for a single-user assistant filtering zkillboard kills. The 3-tier config creates migration complexity (402-line migration CLI) that serves a configuration surface a single pilot will use a fraction of. The `simulate` and `tune` CLI tools are developer debugging aids that add 715 lines for what could be a single `--debug` flag on the engine. The prefetch scoring with RMS safety factors is sophisticated optimization for a system processing single-digit kills per minute.

**Action:** (1) Collapse 3 config tiers to 2 (simple + advanced). Delete `migrate.py`. (2) Merge `explain`, `simulate`, and `tune` into a single `interest debug` CLI command. (3) Evaluate whether `time` and `routes` signals justify their configuration burden (322 combined lines).

**Expected gain:** -1.5K lines of config tier management and CLI code. Simpler configuration surface. Reduced test matrix.

**Guardrail:** Run full `tests/services/redisq/interest_v2/` suite after each step. Keep the engine core and signal providers intact.

---

### Rank 3 -- Sovereignty & Coalition Territory Analysis

**Accretion Score: 11** `(C=3, U=1, R=4)`

**Area:** `src/aria_esi/services/sovereignty/` (2,167 source lines) + `src/aria_esi/commands/sovereignty.py` (835 lines) + tests (1,675 lines)

**Evidence:**
- `services/sovereignty/database.py` (686 lines) -- SQLite sov tracking
- `services/sovereignty/coalition_service.py` (450 lines) -- coalition membership
- `services/sovereignty/fetcher.py` (192 lines) -- ESI sov data
- `services/sovereignty/models.py` (158 lines) -- data models
- `commands/sovereignty.py` (835 lines) -- CLI commands
- `src/aria_esi/data/sovereignty/coalitions.yaml` -- manually maintained
- MCP action: `universe(action="territory_analysis")` in `dispatchers/universe.py`
- Territory routing (`prefer_territory`/`avoid_territory`) uses coalition data

**Why low leverage:** Unchanged from prior audit. Coalition data (`coalitions.yaml`) requires manual maintenance and drifts as alliances reorganize. The full sovereignty database with SQLite storage and CLI commands serves a niche analytical use case. The territory routing feature (prefer/avoid coalition space) is the only part with clear user value.

**Action:** (1) Keep `coalitions.yaml` and a minimal coalition lookup function for territory routing. (2) Delete the full sovereignty database (`database.py`), fetcher, and CLI commands. (3) Simplify `territory_analysis` MCP action to use the YAML lookup directly.

**Expected gain:** -3,000+ lines (source + tests). Removes a SQLite database and its migration overhead.

**Guardrail:** Verify territory routing (`prefer_territory`/`avoid_territory` in `dispatchers/universe.py`) still works with the simplified coalition lookup. Check that `politics` signal in interest_v2 can function with a lookup function rather than the full database.

---

### Rank 4 -- MCP Context Policy / Budget / Context Triple

**Accretion Score: 10** `(C=4, U=2, R=3)`

**Area:** `src/aria_esi/mcp/context_policy.py` (199), `context_budget.py` (136), `context.py` (834), `policy.py` (537) = 1,706 lines across 4 files

**Evidence:**
- `context_policy.py` -- per-domain frozen dataclass limits (199 lines of constants)
- `context_budget.py` -- conversation-turn budget tracking using ContextVar (136 lines). Only imported by `context.py` (2 call sites at lines 726, 770)
- `context.py` -- output wrapping, route summarization, trace context, log decorator (834 lines)
- `policy.py` -- capability gating with 5 sensitivity levels, rate limiting, audit logging (537 lines)
- `mcp-policy.json` -- policy config file with all defaults (no customization)

**Why low leverage:** Four separate files creating three distinct policy/context systems:
1. **context_policy.py**: Domain-specific constants (already could be inline constants in dispatchers)
2. **context_budget.py**: Turn-level byte counting that only `context.py` uses -- effectively dead code since the budget is tracked but never gates behavior
3. **policy.py**: Security capability gating -- this has clear value (security finding #5) but the rate limiting and audit logging are unused (rate_limit=0, audit goes to debug logs nobody reads)
4. **context.py**: Route summarization duplicates formatting logic in skills

The `context_policy.py` constants are imported by every dispatcher for limit validation. This is fine for constants, but the file's frozen-dataclass-per-domain pattern adds ceremony vs. a simple constants module.

**Action:** (1) Delete `context_budget.py` entirely -- it is a dead abstraction. (2) Merge `context_policy.py` constants into the dispatchers or a single `limits.py` constants file. (3) In `policy.py`, remove the rate limiting logic (never configured) and simplify audit logging. (4) Keep `context.py` output wrapping and `policy.py` capability gating.

**Expected gain:** -300 lines. Removes a dead abstraction (budget tracking) and simplifies the mental model from "4 policy/context files" to "2 files: policy checks + output formatting".

**Guardrail:** Run `tests/mcp/` suite. Verify all dispatchers still import limits correctly after consolidation.

---

### Rank 5 -- Hook Scripts Duplication

**Accretion Score: 9** `(C=4, U=3, R=2)`

**Area:** `.claude/scripts/` (12 Python scripts, ~5,300 lines)

**Evidence:**
- `aria-esi-sync.py` (828 lines) -- duplicates `commands/sync_profile.py` (461 lines). Uses raw `urllib` instead of the project's `httpx`/ESIClient
- `aria-token-refresh.py` (613 lines) -- duplicates `core/auth.py` (830 lines) token refresh logic
- `aria-context-assembly.py` (575 lines) -- builds `.session-context.json` from pilot data. No CLI equivalent
- `aria-skill-index.py` (495 lines) -- builds `_index.json` from skill manifests. No CLI equivalent
- `aria-oauth-setup.py` (1,228 lines) -- standalone OAuth wizard, stdlib-only. Used by first-run-setup skill
- `aria-skill-preflight.py` (361 lines) -- validates skill paths. Referenced in CLAUDE.md
- `aria-credential-watch.py` (82 lines est.) -- polls for credential files
- `aria-data-freshness.py` (257 lines) -- data staleness checks
- All scripts use `"No external dependencies"` pattern (stdlib-only HTTP, JSON parsing)

**Why low leverage:** The stdlib-only pattern was a design choice for boot reliability (scripts must work before `uv sync`). This is defensible for `aria-oauth-setup.py` (which handles the critical first-run flow) and the boot sequence. However, `aria-esi-sync.py` and `aria-token-refresh.py` duplicate significant logic from the CLI commands and will drift as the CLI evolves. Every ESI endpoint change must be made in two places.

**Action:** (1) Keep `aria-oauth-setup.py` (unique first-run wizard, stdlib-only constraint is valid). (2) Keep `aria-skill-preflight.py` and `aria-skill-index.py` (unique functionality, used by CLAUDE.md). (3) Replace `aria-esi-sync.py` and `aria-token-refresh.py` with thin wrappers that call `uv run aria-esi sync-profile` and `uv run aria-esi refresh-token`. (4) Evaluate whether `aria-context-assembly.py` can be replaced with a CLI command.

**Expected gain:** -1,200 lines (sync + token scripts). Single source of truth for ESI sync and token refresh.

**Guardrail:** The boot sequence runs scripts before `uv sync`. Verify the thin wrappers handle the "uv not ready" case gracefully. Test the hook pipeline end-to-end with `aria-boot.sh`.

---

### Rank 6 -- Notification LLM Commentary Pipeline

**Accretion Score: 8** `(C=4, U=2, R=2)`

**Area:** `src/aria_esi/services/redisq/notifications/` (7,928 lines, 25 Python files)

**Evidence:**
- `commentary.py` (605 lines) -- LLM-powered kill commentary
- `persona.py` (436 lines) -- persona voice loading for commentary
- `patterns.py` (375 lines) -- tactical pattern detection for commentary warrant
- `warrant.py` (174 lines) -- decides whether commentary adds value
- `llm_providers/` (4 files, 224 lines) -- Anthropic/OpenAI/Gemini abstraction
- `prompts.py` (186 lines) -- LLM prompt templates
- `types.py` (68 lines) -- shared types extracted to break circular imports
- Total commentary-related: ~2,068 lines (~26% of notification subsystem)
- `political_entities.py` (144 lines) -- still separate from coalition service

**Why low leverage:** The LLM commentary pipeline is a feature within a feature (commentary within notifications within the killmail pipeline). It adds LLM API latency and cost to every qualifying notification. The 3-provider abstraction (Anthropic/OpenAI/Gemini) at 224 lines suggests over-anticipation of provider switching for a feature used by one pilot. The warrant system (patterns + warrant scoring to decide IF commentary should be generated) adds 549 lines of complexity to avoid unnecessary LLM calls -- a problem that would not exist if commentary were opt-in and default-off.

**Action:** (1) Make commentary default-off in notification profiles. (2) When off, the entire warrant/patterns/commentary pipeline is dead code that can be skipped at runtime. (3) Remove the multi-provider abstraction -- pick one provider and hardcode it. Add provider switching back if/when there is a second user. (4) Merge `political_entities.py` into the coalition service.

**Expected gain:** Reduced notification latency for the default case. Simpler mental model. -200 lines from provider consolidation and political_entities merge.

**Guardrail:** Verify existing notification profiles still work. Test that commentary=off profiles skip the LLM pipeline entirely.

---

### Rank 7 -- Reference Data Without Code Consumers

**Accretion Score: 7** `(C=2, U=2, R=4)`

**Area:** `reference/lore/` (52 KB), `reference/agents/` (12 KB), `reference/fittings/` (12 KB), `reference/sites/` (36 KB)

**Evidence:**
- `reference/lore/` (7 files, 52 KB) -- faction lore summaries. Zero Python imports. Zero skill `data_sources` references
- `reference/agents/` (12 KB) -- agent reference. Zero Python imports. Agent data now in SDE MCP tool
- `reference/fittings/` (12 KB) -- fitting reference. Separate from archetypes. May overlap with archetypes
- `reference/sites/` (36 KB) -- cosmic anomaly/signature data. One Python import (`commands/validation.py`)
- Total: ~112 KB of reference data with minimal or zero programmatic consumers

**Why low leverage:** These directories were created as static reference data for LLM context. Some (like `lore/`) serve persona flavor text needs, but they are never loaded by the persona system or any skill. Others (like `agents/`) have been superseded by the SDE MCP tool which provides agent data dynamically. They add to the cognitive surface area of the reference directory without clear value pathways.

**Action:** (1) Delete `reference/lore/` -- persona voice files in `personas/` already contain faction-appropriate language. (2) Delete `reference/agents/` -- superseded by `sde(action="agent_search")`. (3) Audit `reference/fittings/` for overlap with archetypes -- delete or merge. (4) Keep `reference/sites/` (has at least one Python consumer).

**Expected gain:** -76 KB of unreferenced data. Cleaner reference directory.

**Guardrail:** Search for any skill `data_sources` referencing these paths before deletion. Verify no persona overlay loads lore files.

---

## Quick Wins

### QW-1: Delete Archetype Library (Rank 1)

**Effort:** 2-4 hours. Extract key fits into skill files, delete 149 YAML files + `_shared/`.
**Risk:** Low -- no Python code reads these files.
**Gain:** -1.5 MB. Removes the largest single dead-weight directory.

### QW-2: Delete `context_budget.py`

**Effort:** 30 minutes. Remove file, remove 2 import sites in `context.py`.
**Risk:** None -- the budget is tracked but never gates behavior.
**Gain:** -136 lines. Removes a dead abstraction that creates false impression of active budget management.

### QW-3: Delete `reference/lore/` and `reference/agents/`

**Effort:** 15 minutes. Delete 2 directories.
**Risk:** None -- zero code consumers.
**Gain:** -64 KB. Cleaner reference directory.

### QW-4: Replace `aria-esi-sync.py` with CLI Wrapper

**Effort:** 1 hour. Replace 828-line script with 20-line wrapper calling `uv run aria-esi sync-profile`.
**Risk:** Low -- verify boot hook still works.
**Gain:** -800 lines of duplicated ESI logic.

### QW-5: Archive `dev/proposals/archive/`

**Effort:** 15 minutes. Git-rm the 1.3 MB archive directory (history preserved in git).
**Risk:** None -- already archived, only git history value.
**Gain:** -1.3 MB from working tree.

---

## Consolidation Plan

| Current State | Target State | Action | Prior Audit? |
|---------------|-------------|--------|--------------|
| 149 archetype YAMLs + `_shared/` (1.5 MB) | 5-10 inline EFT blocks in skills | Migrate key fits, delete rest | Rank 3 (unchanged) |
| 3-tier interest config + 4 CLI tools | 2-tier config + 1 debug CLI | Collapse intermediate tier, merge CLIs | Rank 2 (unchanged) |
| Full sovereignty subsystem (3,800+ lines) | Minimal coalition lookup (~200 lines) | Deprecate database and CLI | Rank 5 (unchanged) |
| 4 policy/context files (1,706 lines) | 2 files: policy + output formatting | Delete budget, consolidate limits | Rank 4 (unchanged) |
| `aria-esi-sync.py` + `aria-token-refresh.py` (1,441 lines) | Thin CLI wrappers (~40 lines) | Replace with `uv run aria-esi` calls | Rank 7 (partial) |
| LLM commentary pipeline (default-on, 2,068 lines) | Commentary (default-off, ~1,500 lines) | Default-off, single LLM provider | Rank 6 (partial) |
| `reference/lore/` + `agents/` + `fittings/` (76 KB) | Deleted or merged | Remove unreferenced data | New |
| `dev/proposals/archive/` (1.3 MB) | Git-only history | Delete from working tree | QW-2 (unchanged) |

---

## Reoptimization Plan (Target Architecture After Removals)

**MCP Layer:** 8 dispatchers calling domain services. Policy checks via `policy.py`. Output wrapping via `context.py`. No budget tracking abstraction. Limits are inline constants or a single `limits.py`.

**RedisQ Pipeline:** Poller -> topology filter -> interest engine (2-tier: simple + advanced) -> notification delivery. Commentary is opt-in, default-off. Single LLM provider. No multi-tier migration tooling.

**Sovereignty:** A single `coalitions.yaml` + lookup function. No SQLite database. Territory routing preserved via the lookup. Coalition data acknowledged as best-effort.

**Reference Data:** Static game mechanics in JSON (ground truth). Ship fits inline in skills as EFT blocks. No archetype YAML hierarchy. No lore directory (persona voice files handle flavor). PvE intel cache unchanged.

**Hook Scripts:** `aria-oauth-setup.py` (unique, stdlib-only). `aria-skill-preflight.py` and `aria-skill-index.py` (unique functionality). Everything else is a thin wrapper calling `uv run aria-esi`.

**Net reduction target:** ~7-8K lines of source code, ~3 MB of reference/archive data, 1 SQLite database.

---

## Risk Notes

| Area | Preserve | Reason |
|------|----------|--------|
| Interest engine v2 core | Signal providers, aggregation, rules | Notification filtering is real user value |
| Policy capability gating | `policy.py` check_capability | Security finding #5 -- required for prompt injection defense |
| Persona system | All 6 personas + overlays | Actively used, well-structured |
| EOS vendor code | All 19K lines | Required for fitting calculations |
| PvE intel cache | Full cache-first pattern | Working design, growing asset |
| Freshness library | `core/freshness.py` | Solves real staleness problems |
| SDE/Market MCP modules | All 18K+ lines | Core product value |
| Territory routing | `prefer_territory`/`avoid_territory` in universe dispatcher | User-facing feature that depends on coalition data |
| `aria-oauth-setup.py` | Full 1,228-line script | First-run wizard, stdlib-only constraint valid |
| Test suite | All 108K lines | 1.06:1 ratio is an asset |

---

## Priority Cut List

1. **Delete archetype library, inline key fits** -- 1.5 MB of structured data that no code reads. Unchanged since prior audit. Zero user impact. 2-4 hours.

2. **Delete `context_budget.py` + consolidate context/policy files** -- Dead abstraction (budget) plus over-structured constants (context_policy). The budget is tracked but never enforced. 1-2 hours for budget removal, 1 day for full consolidation.

3. **Deprecate sovereignty subsystem to minimal coalition lookup** -- 3,800+ lines (source + tests) serving a niche use case. Keep only what territory routing needs. 1-2 days.
