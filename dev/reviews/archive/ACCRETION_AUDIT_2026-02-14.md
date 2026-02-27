# Accretion Audit — 2026-02-14

**Auditor:** Staff-engineer simplification pass (automated)
**Scope:** Full repository — code, skills, personas, docs, reference data, dev tooling
**Method:** Accretion Score = (Complexity Cost × Removal Feasibility) − Utility Yield

---

## Top Removal Candidates

### Rank 1 — Legacy Individual MCP Tool Modules

**Accretion Score: 16** `(C=5, U=1, R=4)`

**Area:** `src/aria_esi/mcp/tools_*.py` (9 files, 2,941 lines)

**Evidence:**
- `src/aria_esi/mcp/tools_route.py` (619 lines)
- `src/aria_esi/mcp/tools_loop.py` (889 lines)
- `src/aria_esi/mcp/tools_activity.py` (922 lines)
- `src/aria_esi/mcp/tools_borders.py` (440 lines)
- `src/aria_esi/mcp/tools_search.py` (770 lines)
- `src/aria_esi/mcp/tools_systems.py` (432 lines)
- `src/aria_esi/mcp/tools_nearest.py` (619 lines)
- `src/aria_esi/mcp/tools_analyze.py` (551 lines)
- `src/aria_esi/mcp/tools_waypoints.py` (489 lines)

**Why low leverage:** The dispatcher consolidation (`mcp/dispatchers/universe.py`, 1,794 lines) already replaced these 9 files. The dispatchers are the registered MCP tools; the old modules now serve only as an import indirection layer. Every call routes through the dispatcher. Keeping both doubles the code surface that contributors must understand and that tests must cover.

**Action:** Delete. Remove the 9 `tools_*.py` files after confirming all logic is reachable through the dispatcher. Inline any residual helper functions into the dispatcher or `mcp/utils.py`.

**Expected gain:** −2,941 lines. Eliminates the "which layer handles this?" confusion for new contributors. Reduces MCP test matrix.

**Guardrail:** Run `uv run pytest -n auto tests/mcp/` before and after removal. Verify no import errors via `uv run python -c "from aria_esi.mcp.dispatchers.universe import *"`.

---

### Rank 2 — Interest Engine v2 Signal Overengineering

**Accretion Score: 12** `(C=5, U=2, R=3)`

**Area:** `src/aria_esi/services/redisq/interest_v2/` (9,685 lines source + 12,998 lines tests)

**Evidence:**
- 9 signal categories with dedicated modules (`signals/*.py`)
- 4 CLI sub-tools (explain, migrate, simulate, tune)
- 3 aggregation modes (RMS, linear, max)
- 3 config tiers (simple, intermediate, advanced)
- Prefetch scoring with RMS safety factors
- 28 test files, 971 test functions

**Why low leverage:** This is a sophisticated rule engine for a single-user assistant filtering zkillboard kills. The 3-tier config model (simple/intermediate/advanced) and 9 signal categories create a combinatorial configuration space that a single pilot will explore a fraction of. The `simulate`, `tune`, and `explain` CLI tools are powerful debugging aids but add ~2K lines for what is essentially developer tooling. The prefetch scoring with RMS safety factor calculation is enterprise-grade optimization for a system that processes a few kills per minute.

**Action:** Simplify, don't remove. Collapse the 3 config tiers to 2 (simple + advanced). Merge the 4 CLI sub-tools into a single `interest debug` command. Consider whether `time` and `routes` signals pull their weight vs. configuration burden.

**Expected gain:** Reduced configuration surface, fewer moving parts for users to misunderstand. Cuts ~1-2K lines of tier-detection and migration code.

**Guardrail:** Keep the engine core and signal providers intact. Only collapse the config surface and CLI tooling. Run full `tests/services/redisq/interest_v2/` suite.

---

### Rank 3 — Archetype Fittings Library

**Accretion Score: 11** `(C=3, U=1, R=5)`

**Area:** `reference/archetypes/` (78 YAML files, 804 KB)

**Evidence:**
- `reference/archetypes/hulls/` — 78 YAML fit definitions across 30+ hulls
- `reference/archetypes/_shared/` — 5 shared config files (damage_profiles, faction_tuning, module_tiers, tank_archetypes, skill_tiers)
- No Python code references `archetypes` in `src/aria_esi/` (0 matches)
- Only referenced in 2 skills: `fitting/SKILL.md` and `ship-next/SKILL.md` (as context data)
- CLI archetype commands deprecated per PR #28 (2026-02)

**Why low leverage:** The archetype system was designed as a structured fitting recommendation library, but it's consumed only as passive read context by 2 skills. No Python code loads, validates, or queries these YAML files programmatically. The EOS fitting engine and SDE provide the actual ground-truth data. The 78 YAML files are effectively static markdown with extra structure — the same information could be a single reference document.

**Action:** Deprecate directory. Migrate the ~10 most-used fits (Venture mining, Vexor L3, Drake L3, Dominix L4, exploration frigates) into the relevant skill files as inline EFT blocks. Delete the rest. Remove `_shared/` entirely — the EOS engine is the authority on damage profiles and module tiers.

**Expected gain:** −804 KB of reference data that no code reads. Eliminates a structural abstraction (hull→activity→level→tank→skill_tier hierarchy) that provides no programmatic value.

**Guardrail:** Verify the 2 referencing skills (`fitting`, `ship-next`) still have access to needed fit examples after migration. No Python tests to break.

---

### Rank 4 — MCP Context Policy Subsystem

**Accretion Score: 10** `(C=4, U=2, R=3)`

**Area:** `src/aria_esi/mcp/context_policy.py`, `context_budget.py`, `context.py` (1,169 lines)

**Evidence:**
- `src/aria_esi/mcp/context_policy.py` (199 lines) — per-domain token budget policies
- `src/aria_esi/mcp/context_budget.py` (136 lines) — dynamic context trimming
- `src/aria_esi/mcp/context.py` (834 lines) — output wrapping, route summarization
- `docs/CONTEXT_POLICY.md` (separate documentation)

**Why low leverage:** The context policy system enforces token budgets on MCP tool responses to avoid overwhelming the LLM context window. In practice, Claude handles large tool responses well via its own context management, and the truncation logic adds a layer of complexity that can silently drop useful data. The domain-specific policies (different budgets for market vs. universe vs. SDE) create maintenance overhead every time a new dispatcher action is added. The 834-line `context.py` includes route summarization logic that duplicates formatting already handled by the skills.

**Action:** Simplify. Replace the per-domain policy system with a single global max-response-size guard. Move route summarization into the universe dispatcher where it belongs. Delete `context_policy.py` and `context_budget.py`.

**Expected gain:** −335 lines of policy code. Eliminates a maintenance tax on new dispatcher actions. Reduces risk of silent data truncation.

**Guardrail:** Before removing, audit whether any MCP responses currently exceed ~30K tokens. If not, the policy is pure overhead. Run `tests/mcp/` suite.

---

### Rank 5 — Sovereignty & Coalition Territory Analysis

**Accretion Score: 9** `(C=3, U=1, R=4)`

**Area:** `src/aria_esi/services/sovereignty/` (1,332 lines) + `src/aria_esi/commands/sovereignty.py` (835 lines)

**Evidence:**
- `services/sovereignty/database.py` (495 lines) — SQLite sov tracking
- `services/sovereignty/coalition_service.py` (450 lines) — coalition membership
- `services/sovereignty/fetcher.py` (192 lines) — ESI sov data
- `services/sovereignty/models.py` (158 lines) — data models
- `commands/sovereignty.py` (835 lines) — CLI commands
- `src/aria_esi/data/sovereignty/coalitions.yaml` (manually maintained)
- MCP dispatcher: `universe(action="territory_analysis")`

**Why low leverage:** Sovereignty tracking is a nullsec alliance feature. The pilot profile indicates highsec PvE/industrial gameplay. Coalition data (`coalitions.yaml`) must be manually maintained — it drifts as alliances join/leave coalitions. The `territory_analysis` MCP action and CLI commands serve a niche analytical use case that a single-pilot assistant rarely needs. The notification system's `politics` signal category is the only consumer, and it could use a simpler alliance-watchlist instead.

**Action:** Deprecate. Keep the `coalitions.yaml` data file and a minimal lookup function for the notification `politics` signal. Remove the full sovereignty database, CLI commands, and territory analysis features.

**Expected gain:** −2,167 lines of code + tests. Removes an entire SQLite database and its migration overhead. Eliminates manually-maintained coalition data that drifts.

**Guardrail:** Verify the `politics` signal in interest_v2 can function with a simpler coalition lookup. Check if any notification profiles reference `territory_analysis`.

---

### Rank 6 — Notification Commentary System

**Accretion Score: 8** `(C=4, U=2, R=2)`

**Area:** `src/aria_esi/services/redisq/notifications/commentary.py` (716 lines) + `persona.py` (289 lines)

**Evidence:**
- `commentary.py` (716 lines) — LLM-powered kill commentary generation
- `persona.py` (289 lines) — RP-aware commentary formatting
- `political_entities.py` (500 lines) — coalition/alliance display names
- Referenced in notification delivery pipeline

**Why low leverage:** LLM-generated commentary on Discord kill notifications is a creative feature, but it adds latency to every notification, requires LLM API calls (cost), and the commentary quality is unverifiable at test time. The persona-aware commentary (`persona.py`) layers RP voice onto automated notifications, compounding complexity. The `political_entities.py` module duplicates knowledge that should live in `coalitions.yaml`.

**Action:** Make commentary opt-in and default-off. Merge `political_entities.py` into the coalition service. Consider whether persona-aware commentary is worth 289 lines — a static format string per persona would suffice.

**Expected gain:** Reduced notification latency. Clearer separation between "filter and deliver" vs. "annotate with LLM".

**Guardrail:** Commentary is already configurable per-profile. Verify default-off doesn't break existing profiles that expect it.

---

### Rank 7 — Hook Scripts Complexity

**Accretion Score: 7** `(C=3, U=2, R=3)`

**Area:** `.claude/scripts/` (9 Python scripts, 4,693 lines)

**Evidence:**
- `aria-esi-sync.py` (29 KB / ~900 lines) — ESI data synchronization
- `aria-token-refresh.py` (20 KB / ~600 lines) — OAuth token management
- `aria-context-assembly.py` (22 KB / ~700 lines) — Session context builder
- `aria-skill-index.py` (18 KB / ~550 lines) — Skill manifest indexing
- `aria-boot-sync` (15 KB / ~450 lines) — Boot sequence
- 4 more scripts totaling ~1,500 lines

**Why low leverage:** These scripts duplicate logic that exists in the `aria-esi` CLI commands (e.g., `sync-profile`, `persona-context`, `validate-overlays`). They were created as Claude Code hook entry points, but the hook system can invoke `uv run aria-esi <command>` directly. The scripts add a parallel maintenance surface that must be kept in sync with the CLI.

**Action:** Audit each script for logic not already in the CLI. Migrate unique logic into CLI commands. Replace hook scripts with thin wrappers that call `uv run aria-esi`.

**Expected gain:** −2-3K lines of duplicated logic. Single source of truth for session initialization.

**Guardrail:** Map each script to its CLI equivalent before deletion. Test hooks with the replacement wrappers. Some scripts may handle boot-time edge cases (no venv, no config) that the CLI assumes are resolved.

---

## Quick Wins

### QW-1: Delete Legacy MCP Tool Files (Rank 1)

**Effort:** 1 hour. Delete 9 files, run tests.
**Risk:** Low — dispatchers are the registered tools.

### QW-2: Archive `dev/proposals/archive/` and `dev/reviews/archive/`

**Effort:** 30 minutes. Compress to tarball, remove from tree.
**Risk:** None — already archived, only git history value.
**Gain:** −1.7 MB from working tree.

### QW-3: Delete Empty/WIP Dev Files

**Effort:** 15 minutes.
- `dev/reviews/ACCRETION_AUDIT_2026-02.md` (empty)
- `dev/NL_TESTS.md`, `dev/query15.txt`, `dev/query16.txt` (WIP scratch)
- `dev/run_nl_tests.py` (untracked)

### QW-4: Collapse Archetype Library Into Inline Fits

**Effort:** 1 day. Extract ~10 key fits, embed in skill SKILL.md files, delete 78 YAML files.
**Risk:** Low — no Python code reads these files.
**Gain:** −804 KB, eliminates dead abstraction layer.

### QW-5: Merge `political_entities.py` Into Coalition Service

**Effort:** 2 hours. Single-file refactor.
**Risk:** Low — purely internal data consolidation.
**Gain:** −500 lines of duplicated entity knowledge.

---

## Consolidation Plan

| Current State | Target State | Action |
|---------------|-------------|--------|
| 9 legacy `tools_*.py` + 7 dispatchers | 7 dispatchers only | Delete legacy files |
| 78 archetype YAMLs + `_shared/` | Inline EFT blocks in skills | Migrate and delete |
| 3-file context policy subsystem | Single response-size guard | Collapse into `context.py` |
| Full sovereignty subsystem (2,167 lines) | Minimal coalition lookup (~200 lines) | Deprecate and shrink |
| 9 hook scripts (4,693 lines) | Thin wrappers calling CLI | Migrate unique logic, replace |
| 3-tier interest config | 2-tier (simple + advanced) | Collapse intermediate tier |
| LLM commentary (default-on) | LLM commentary (default-off) | Config change + doc update |
| 1.7 MB dev archives in tree | Compressed archive or git-only | Compress/remove |

---

## Reoptimization Plan (Target Architecture After Removals)

**MCP Layer:** 7 dispatchers → domain services → core. No intermediate tool modules. Context wrapping is a single-function guard, not a policy framework.

**Notification Pipeline:** RedisQ → topology filter → interest engine (2-tier config) → Discord delivery. Commentary is an opt-in decorator, not a pipeline stage. Coalition data is a single YAML lookup, not a database.

**Reference Data:** Static game mechanics in JSON (ground truth). Ship fits inline in skills as EFT blocks. No archetype YAML hierarchy. PvE intel cache unchanged (working as designed).

**Hook Scripts:** Thin JSON-producing wrappers that call `uv run aria-esi <command>`. No duplicated business logic outside `src/aria_esi/`.

**Net reduction:** ~8-10K lines of source code, ~800 KB of reference data, 1 SQLite database, and a simpler mental model for contributors.

---

## Risk Notes

| Area | Preserve | Reason |
|------|----------|--------|
| Interest engine v2 core | Signal providers, aggregation, rules | Notification filtering is a real user feature |
| Persona system | All 6 personas + overlays + exclusives | Actively used, well-structured, low overhead |
| EOS vendor code | All 19K lines | Required for fitting calculations, no alternative |
| PvE intel cache | Full cache-first pattern | Working design, growing over time |
| Freshness library | All of `core/freshness.py` | Recent addition (PR #29), solves real staleness problems |
| SDE/Market MCP modules | Full 18K lines | Core product value — market + item data |
| Test suite | All 102K lines | 1:1 test-to-code ratio is an asset, not bloat |

---

## Priority Cut List

1. **Delete legacy `tools_*.py`** — Highest signal-to-noise improvement. 2,941 lines of pure indirection. Zero user impact. 1 hour.

2. **Delete archetype library, inline key fits** — 804 KB of structured data that nothing reads programmatically. Removes a dead abstraction. 1 day.

3. **Deprecate sovereignty subsystem** — 2,167 lines serving a niche use case for a highsec pilot. Keeps the coalition lookup for notifications. 1-2 days.
