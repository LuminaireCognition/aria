# Accretion Audit Report

**Date:** 2026-02-10
**Scope:** Full repository analysis per `dev/prompts/architecture/accretion_auditor.md`
**Method:** Complexity Cost (C) x Removal Feasibility (R) - Utility Yield (U)

---

## Executive Summary

ARIA has grown from a focused EVE Online tactical assistant into a 108K+ LOC Python project with 49 registered skills, 366 markdown files, and 4,000+ JSON/YAML data files. Several subsystems have accreted significant complexity with diminishing returns. The single highest-impact finding is the **coexistence of two complete interest-scoring engines** (v1 and v2) in the notification pipeline, totaling 50 Python files for the same conceptual job.

The top 3 cuts alone would remove ~15K lines of code and 50+ files while preserving all user-facing functionality.

---

## 1. Top Removal Candidates

### Rank 1: Interest Engine v1/v2 Coexistence

**Accretion Score: 15** `(C=5, U=2, R=4)`

**Area:** `src/aria_esi/services/redisq/interest/` + `src/aria_esi/services/redisq/interest_v2/`

**Evidence:**
- `interest/` — 12 Python files, ~3,100 LOC (multi-layer max-of-scores approach)
- `interest_v2/` — 38 Python files, ~9,700 LOC (RMS-weighted signal blending)
- `interest_v2/cli/migrate.py` — migration tool from v1 configs exists but coexistence persists
- `notifications/profile_evaluator.py` — runtime router that dispatches to v1 OR v2 based on `profile.uses_interest_v2`
- Tests: ~3,400 LOC for v1, ~13,000 LOC for v2 — **16,400 lines of test code for duplicated logic**

**Why low leverage:** Two complete implementations of "should this kill generate a notification?" living side by side. The v2 engine alone has 7 subpackages (`signals/`, `rules/`, `providers/`, `scaling/`, `presets/`, `delivery/`, `cli/`) with feature flags (`rule_dsl`, `custom_signals`, `custom_scaling`, `delivery_slack`). This is framework-grade complexity for a single-user notification filter.

**Action:** Complete migration to v2, delete v1. Or: collapse both into a single simplified scorer if v2's full feature surface is unused.

**Expected gain:** Remove ~12 files + ~3,100 LOC of source, ~3,400 LOC of tests. Eliminate runtime branching in profile_evaluator. Simplify notification profile schema (no more dual-mode topology/interest config).

**Guardrail:** Migrate any active v1 notification profiles to v2 config format using `interest_v2/cli/migrate.py` before deletion. Run notification integration tests to verify parity.

---

### Rank 2: Archetype Selection Framework

**Accretion Score: 14** `(C=4, U=2, R=5)`

**Area:** `src/aria_esi/archetypes/` + `reference/archetypes/`

**Evidence:**
- `src/aria_esi/archetypes/` — 8 Python modules: `loader.py`, `models.py`, `selection.py`, `tank_selection.py`, `tuning.py`, `pricing.py`, `validator.py`
- `reference/archetypes/` — 78 YAML files defining ship fits across hulls/activities/tiers
- `reference/archetypes/_shared/` — 5 shared YAML files (damage profiles, tank archetypes, skill tiers, module tiers, faction tuning)
- The MCP `fitting(action="calculate_stats")` tool already validates fits via EOS engine
- The 437-line `.claude/skills/fitting/SKILL.md` already contains inline fitting philosophy, tank coherence rules, and drone selection protocol

**Why low leverage:** The archetype system builds a Python framework (selection algorithms, tank selection logic, pricing integration, tuning parameters) to choose from pre-defined YAML fits. But the fitting skill's actual workflow is: user describes need -> LLM builds EFT -> `fitting(action="calculate_stats")` validates -> iterate. The archetype YAML files are reference data that could be read directly without a framework mediating access. The selection/tuning/validation framework adds ~1,500 LOC of indirection that the LLM doesn't need.

**Action:** Deprecate the Python framework (`src/aria_esi/archetypes/`). Retain `reference/archetypes/` YAML files as static reference data the fitting skill reads directly. Remove `selection.py`, `tank_selection.py`, `tuning.py`, `validator.py`.

**Expected gain:** Remove ~1,500 LOC of framework code. Eliminate archetype-related test surface. Simplify fitting recommendations from "framework-selected archetype" to "LLM reads reference YAML + validates via EOS."

**Guardrail:** Verify that no CLI command depends on archetype Python modules before removal. Check `pyproject.toml` entry points and `commands/fit.py` imports. Keep YAML data files intact.

---

### Rank 3: Documentation Fragmentation (Data Trust + Persona Loading)

**Accretion Score: 14** `(C=4, U=2, R=4)`

**Area:** Multiple overlapping documentation sets

**Evidence — Data Trust (3 docs, same topic):**
- `docs/DATA_VERIFICATION.md` — 413 lines, "verify before presenting"
- `docs/DATA_AUTHORITY.md` — 233 lines, "validate before caching"
- `docs/PROTOCOLS.md` — data volatility rules, overlaps both above
- `CLAUDE.md:357-396` — Data Freshness Rules table, duplicates PROTOCOLS.md content

**Evidence — Persona Loading (4 locations):**
- `CLAUDE.md:501-582` — Persona Loading + Skill Loading overview
- `docs/PERSONA_LOADING.md` — Full specification
- `personas/_shared/skill-loading.md` — Overlay loading procedure
- `personas/_shared/rp-levels.md` — RP level definitions

**Evidence — Path Security (3 locations):**
- `CLAUDE.md:550-580` — SEC-001/SEC-002 validation rules
- `personas/_shared/skill-loading.md` — Same rules repeated
- `src/aria_esi/core/path_security.py` — Canonical implementation

**Why low leverage:** The same information is restated across 3-4 files per topic. A developer or the LLM must read all variants to be sure they have the complete picture. The cognitive overhead scales with number of restated sources, not with conceptual complexity. The actual rules are simple; the documentation makes them appear complex.

**Action:** Consolidate each topic to one authoritative source:
- Merge DATA_VERIFICATION + DATA_AUTHORITY + PROTOCOLS volatility section into single `docs/DATA_TRUST.md`
- Consolidate persona loading into `docs/PERSONA_LOADING.md`, remove content from CLAUDE.md (replace with one-line reference)
- Delete path security from `personas/_shared/skill-loading.md` (keep in CLAUDE.md + code)

**Expected gain:** Remove ~800 lines of duplicated documentation. Reduce CLAUDE.md by ~150 lines. Eliminate "which doc is canonical?" confusion.

**Guardrail:** Grep for cross-references to deleted files and update them. No code changes needed.

---

### Rank 4: Interest Engine v2 Internal Over-Engineering

**Accretion Score: 12** `(C=5, U=3, R=2)`

**Area:** `src/aria_esi/services/redisq/interest_v2/`

**Evidence:**
- 38 Python files across 7 subpackages for a single-user notification filter
- `signals/` — 8 signal modules: location, value, politics, war, assets, activity, ship, time, routes
- `rules/` — DSL evaluator + templates + builtins (behind `rule_dsl` feature flag)
- `providers/` — Abstract provider registry pattern
- `scaling/` — Custom scaling functions (behind `custom_scaling` feature flag)
- `delivery/` — Routing + builtin delivery (behind `delivery_webhook`, `delivery_slack` flags)
- `cli/` — 4 CLI tools: explain, tune, migrate, simulate
- `features.py` — Feature flag system with 6 flags
- `validation.py` — Config validation layer

**Why low leverage:** This is a framework for an audience of one. Feature flags for capabilities (rule DSL, custom signals, Slack delivery) that have no evidence of external users. The provider/registry abstraction pattern adds extension points that aren't extended. The 9 signal categories with RMS-weighted blending is mathematically elegant but operationally identical to "is this kill near my stuff and is it valuable?"

**Action:** Simplify. Collapse signals into 3-4 inline scorers (location, entity, value, pattern). Remove feature flags, provider registry, rule DSL, custom scaling. Eliminate `cli/` tools except `explain`. Target: 8-10 files from 38.

**Expected gain:** ~6,000 LOC reduction. Dramatically reduced cognitive load for notification debugging. Faster startup (no feature flag evaluation, no provider registration).

**Guardrail:** Preserve the scoring semantics that active notification profiles depend on. Run existing notification tests after simplification. The `explain` CLI tool is genuinely useful for debugging — keep it.

---

### Rank 5: Skill Surface Sprawl (49 Skills)

**Accretion Score: 9** `(C=4, U=3, R=3)`

**Area:** `.claude/skills/` — 49 registered skills

**Evidence — Overlapping skill clusters:**

| Cluster | Skills | Overlap |
|---------|--------|---------|
| Fitting | `fitting`, `fit-check`, `fit-budget`, `fittings` | 4 skills for "help me with ship fitting" |
| Navigation | `route`, `gatecamp`, `threat-assessment`, `orient` | 4 skills for "is it safe to go there?" |
| Killmails | `killmail`, `killmails` | Singular vs plural, same domain |
| Standings | `standings`, `standings-plan` | View vs plan, could be one |
| Mining | `mining`, `mining-advisory` | Ledger vs guidance, could be one |
| Skills | `skillplan`, `skillqueue` | Plan vs queue, could be one |

**Evidence — Persona-exclusive skills (5 paria-only):**
- `escape-route`, `hunting-grounds`, `mark-assessment`, `ransom-calc`, `sec-status`
- Only usable with the `paria` persona (pirate roleplay)
- Each requires the exclusive-skill routing mechanism in `_index.json`
- No evidence of other personas being implemented

**Why low leverage:** 49 skills creates trigger disambiguation overhead — the LLM must pattern-match user intent to one of 49 options. Clusters like fitting (4 skills) could be a single skill with subcommands. Persona-exclusive skills add 5 entries to the index that are unreachable for non-paria users, plus the `persona_exclusive` routing logic in skill loading.

**Action:** Merge clusters:
- `fitting` + `fit-check` + `fit-budget` → single `fitting` with modes
- `killmail` + `killmails` → single `killmails`
- `standings` + `standings-plan` → single `standings`
- `mining` + `mining-advisory` → single `mining`
- `skillplan` + `skillqueue` → single `skills`

**Expected gain:** Reduce from 49 to ~40 skills. Simpler trigger disambiguation. ~8 fewer SKILL.md files to maintain. Eliminate skill-cluster confusion.

**Guardrail:** Ensure merged SKILL.md files include all trigger patterns from both originals. Update `_index.json` accordingly. Merge, don't delete, to preserve functionality.

---

### Rank 6: Notification Subsystem File Count

**Accretion Score: 7** `(C=5, U=3, R=2)`

**Area:** `src/aria_esi/services/redisq/notifications/`

**Evidence:**
- 23 Python files in the notifications subdirectory alone
- Includes: `manager.py`, `supervisor.py`, `worker.py`, `queue.py`, `throttle.py`, `formatter.py`, `commentary.py`, `persona.py`, `discord_client.py`, `prompts.py`, `profiles.py`, `profile_loader.py`, `profile_evaluator.py`, `triggers.py`, `patterns.py`, `warrant.py`, `npc_factions.py`, `political_entities.py`, `esi_coordinator.py`, `quiet_hours.py`, `config.py`, `types.py`
- Commentary and persona modules generate flavor text for Discord embeds
- Political entities and NPC factions are specialized trigger types
- Quiet hours implements time-of-day notification suppression

**Why low leverage:** A 23-file microservice architecture for "format kill data and POST to Discord webhook." The supervisor/worker/queue pattern implies async job processing complexity. Commentary and persona modules generate RP-flavored notification text — nice-to-have but high maintenance cost for a cosmetic feature.

**Action:** Simplify to ~8-10 files. Inline commentary into formatter. Merge supervisor/worker/queue into a single async sender. Merge npc_factions + political_entities into triggers. Move quiet_hours into throttle.

**Expected gain:** ~2,000 LOC reduction. Clearer notification debugging path. Fewer files to navigate when troubleshooting "why didn't my notification fire?"

**Guardrail:** Preserve Discord webhook formatting. Maintain throttling behavior. Test with active notification profiles.

---

### Rank 7: Helper Script Sprawl

**Accretion Score: 7** `(C=3, U=2, R=3)`

**Area:** `.claude/scripts/`

**Evidence:**
- 10+ scripts: `aria-skill-preflight.py`, `aria-data-freshness.py`, `aria-context-assembly.py`, `aria-oauth-setup.py`, `aria-esi-sync.py`, `aria-token-refresh.py`, `aria-credential-watch.py`, `aria-config-validate.py`, `aria-boot-sync.py`, `count_persona_tokens.py`
- Each requires users to know when to invoke it
- `aria-skill-preflight.py` — validates prerequisites before skill execution (could be automatic)
- `aria-data-freshness.py` — checks staleness (could be part of session init)
- `count_persona_tokens.py` — dev-only utility

**Why low leverage:** Operational scripts that exist because their logic wasn't integrated into the main CLI. Each adds a separate invocation path that users must discover and remember. The `aria-esi` CLI already has a command surface — these scripts should be subcommands, not standalone files.

**Action:** Migrate essential logic into `aria-esi` CLI subcommands. Delete dev-only utilities (`count_persona_tokens.py`). Make preflight and freshness checks automatic at session init.

**Expected gain:** Eliminate 6-8 standalone scripts. Reduce operational surface from "10 scripts + CLI" to "CLI only."

**Guardrail:** Verify no boot hooks depend on script file paths before renaming/moving.

---

## 2. Quick Wins (<=2 days each)

| # | Action | Files Affected | LOC Removed | Effort |
|---|--------|----------------|-------------|--------|
| 1 | Delete `interest/` v1 (after migrating active profiles) | 12 .py + ~10 test files | ~6,500 | 1 day |
| 2 | Merge DATA_VERIFICATION + DATA_AUTHORITY + PROTOCOLS into DATA_TRUST.md | 3 docs consolidated → 1 | ~800 | 0.5 day |
| 3 | Merge `killmail` + `killmails` skills | 2 SKILL.md → 1, update _index.json | ~100 | 0.5 day |
| 4 | Delete path security duplication from `personas/_shared/skill-loading.md` | 1 file edited | ~50 | 0.25 day |
| 5 | Delete `count_persona_tokens.py` and `aria-credential-watch.py` | 2 scripts | ~200 | 0.25 day |

---

## 3. Consolidation Plan

### Phase 1: Delete Dead Weight (1 week)
- Complete interest v1 → v2 migration, delete `interest/`
- Merge overlapping documentation (data trust, persona loading, path security)
- Merge trivially-overlapping skills (killmail/killmails, standings/standings-plan)
- Delete dev-only helper scripts

### Phase 2: Simplify Frameworks (2 weeks)
- Collapse interest v2 from 38 files to ~10 (inline signals, remove feature flags, delete provider registry)
- Deprecate archetype Python framework, retain YAML reference data
- Simplify notification subsystem from 23 files to ~10 (inline commentary, merge supervisor/worker/queue)
- Merge fitting skill cluster (fitting + fit-check + fit-budget → single skill with modes)

### Phase 3: Integrate Operations (1 week)
- Migrate helper scripts into `aria-esi` CLI subcommands
- Make preflight/freshness checks automatic at session init
- Delete standalone script files after CLI integration

---

## 4. Reoptimization Plan: Target Architecture

**After all removals, the codebase targets:**

| Area | Current | Target |
|------|---------|--------|
| Interest engines | 50 files (v1+v2) | ~10 files (simplified v2) |
| Notifications | 23 files | ~10 files |
| Archetypes Python | 8 modules | 0 (YAML data only) |
| Skills | 49 | ~40 (merged clusters) |
| Documentation | 25+ docs with overlaps | ~18 docs, no duplication |
| Helper scripts | 10+ standalone | 0 (integrated into CLI) |
| Total Python LOC | ~108K | ~90K (est. 17% reduction) |

**Architectural principles post-cleanup:**
- One interest engine, not two
- Notification pipeline: poller → scorer → formatter → webhook (linear, not microservice)
- Fitting recommendations: LLM reads YAML reference + validates via EOS (no framework)
- One skill per user intent domain (not 4 fitting skills)
- One canonical doc per topic (not 3-4 restating the same rules)

---

## 5. Risk Notes

**Must preserve:**
- All user-facing skill functionality (merge, don't delete capabilities)
- Active notification profile configurations (migrate before deleting v1)
- Reference YAML data in `reference/archetypes/` (used by fitting skill for lookup)
- Discord webhook formatting and throttling behavior
- Path security validation in `src/aria_esi/core/path_security.py` (delete docs duplication only)
- Persona overlay mechanism (simplify docs, don't remove feature — it's opt-in)
- Boot hook scripts in `.claude/hooks/aria-boot.d/` (these are NOT the helper scripts being removed)

**Regression risks:**
- Interest v1 deletion: any notification profile still using v1 config format will break. Run `interest_v2/cli/migrate.py` first.
- Skill merges: trigger pattern coverage must be preserved. Test that natural language triggers still route correctly.
- Archetype framework removal: verify `commands/fit.py` doesn't call archetype selection at runtime. If it does, inline the lookup.

---

## Priority Cut List

**Execute these 3 cuts first for maximum leverage:**

1. **Delete Interest v1** — 12 source files + 10 test files, ~6,500 LOC. Eliminates the largest single instance of duplicated logic. Prerequisite: run migration tool on any active v1 profiles.

2. **Consolidate Data Trust Documentation** — 3 docs → 1, ~800 lines of duplication removed. Zero code risk. Immediately reduces cognitive load for anyone reading the system prompt or docs.

3. **Deprecate Archetype Python Framework** — 8 modules, ~1,500 LOC. The YAML data stays; the selection/tuning/validation framework goes. The fitting skill already works by having the LLM read reference data and validate via EOS — the framework is an unused intermediary.
