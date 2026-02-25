# Public Release Readiness Report

**Status:** ASSESSMENT
**Date:** 2026-02-24
**Review baseline:** 2026-02-24 (8 reviews, 3,860 lines total)
**Scope:** Full proposal audit + cross-referenced review findings -- what has been done, what remains before initial public release

## Executive Summary

An audit of all 46 proposals (5 active, 41 archived) plus 8 fresh code reviews concludes that ARIA is **near-ready for a quiet public release**. The repo is already public on GitHub. The prior `GITHUB_RELEASE_READINESS` proposal graded the project "A- for first-visitor impressions"; the fresh GitHub First Impression review confirms this at **B+**, with a few targeted fixes to reach A.

The reviews surfaced **1 security regression** (authenticated MCP actions re-enabled without confirmation gate), **critical test coverage gaps** in the MCP market tools layer (8 modules at 0%), and **documentation inconsistencies** that would trip up new contributors. None are hard release blockers, but the security regression should be fixed before promoting the release.

**Test suite:** 6,271 tests passing, 60.3% coverage (threshold: 59%). Coverage is unevenly distributed: navigation/loop planning at 90-100%, MCP market tools at 0%.

**Aggregate review scores:**
| Review | Grade/Score | Key Verdict |
|--------|------------|-------------|
| GitHub First Impression | B+ | Strong README, missing CODE_OF_CONDUCT and Dependabot |
| Onboarding UX | 8.3/10 | Excellent first-run wizard, a few stale doc references |
| Python Code Quality | 3.7/5 | Good architecture, exception handling debt |
| System Design | 0 Critical, 3 High | Layer inversions in core, mcp as hybrid data layer |
| Security | 9 findings (1 Medium-High) | Authenticated-level policy regression |
| Coverage Quality | 18 findings (4 Critical/High) | MCP market tools and auth module under-covered |
| Test Harness | B+ | Sound architecture, under-applied markers, low threshold |
| Accretion Audit | 7 candidates, 1.5 MB dead weight | Archetype library still undeleted |

---

## Part 1: What Has Been Done

### Core Infrastructure (all complete)

| Proposal | What It Delivered |
|----------|-------------------|
| SDE_GROUND_TRUTH | Replaced 230 lines of hardcoded (37% incorrect) type IDs with live SDE lookups |
| FITTING_VALIDATION | Mandatory EOS engine validation for all fit recommendations |
| KILLMAIL_STORE_REDESIGN | SQLite-backed ingest/store/worker architecture |
| INSTANCE_LOCAL_DATA_PATHS | `ARIA_INSTANCE_ROOT` for multi-instance support |
| FRESHNESS_GATED_AUTO_SYNC | `ensure_fresh()` library for stale data detection |
| INIT_INFORMATION_SPACE_CLEANUP | Fixed profile bootstrap file placement |
| LLM_INTEGRATION_IMPROVEMENTS_000 | Context-aware policy, byte limits, preflight validation |
| PROPOSAL_GEMINI3PRO_VALIDATED_ISSUES | Security review -- issues validated and fixed |

### Navigation & Intelligence (all complete)

| Proposal | What It Delivered |
|----------|-------------------|
| SOVEREIGNTY_TERRITORY_DATA | Coalition awareness, FW frontlines, territory analysis |
| REDISQ_REALTIME_INTEL | Live killmail streaming, gatecamp detection, operational alerts |
| ship-hull-value-signal | Notification filtering by hull price |

### Skill & Fitting Systems (all complete)

| Proposal | What It Delivered |
|----------|-------------------|
| SKILL_PLANNER | "Easy 80%" and full requirements analysis via `skills()` dispatcher |
| MINMAX_SKILL_PLANNING | Role-scoped phased training recommendations for alts |
| SKILL_TEST_HARNESS | Contract, structural, and LLM-as-judge validation layers |
| SKILL_AWARE_FIT_SELECTION | Pilot-aware fit selection (Python deprecated, MCP actions retained) |
| SKILL_ROUND2_REMAINING_ISSUES | Doc-only fixes for name resolution and stub guards |

### Market & Industry (all complete)

| Proposal | What It Delivered |
|----------|-------------------|
| BUILD_COST | Manufacturing profitability calculator (Phases 1-2, 4) |
| ASSET_AUDIT | Asset inventory and net worth tracking via ESI |
| PI_HELPER | Production chains, math, market integration, colony planning |
| EXPAND_SDE_INJEST | T2/Faction variant lookups via `sde(action="meta_variants")` |
| MARKET_WATCHLIST | Backend watchlist engine + `/watchlist` skill |

### Persona & Notifications (all complete)

| Proposal | What It Delivered |
|----------|-------------------|
| PERSONA_DRIVEN_DISCORD_NOTIFICATIONS | LLM-generated persona-voiced Discord kill commentary |
| MULTI_LLM_SERVICE_FOR_NOTIFICATIONS | Provider abstraction (Anthropic, OpenAI, Gemini) |
| NPC_FACTION_KILL_NOTIFICATIONS | NPC faction ship triggers for roleplay alerts |
| POLITICAL_ENTITY_TRIGGERS | Per-profile corporation/alliance killmail triggers |
| STANDINGS_TRACKER | Faction standings tracking with progression planning |

### Developer Experience (all complete)

| Proposal | What It Delivered |
|----------|-------------------|
| DEVCONTAINER | Zero-friction Docker-based onboarding with firewall allowlist |
| GITHUB_RELEASE_READINESS | README polish, CI badge, FAQ, architecture docs, CHANGELOG |

### Consolidated / Superseded / Dead

| Proposal | Disposition |
|----------|-------------|
| FORGE_PERSONA, PARIA_S, PARIA_G | Consolidated into PERSONA_VARIANTS_PROPOSAL |
| PROMPT_LIBRARY_REVIEW_COVERAGE | Superseded -- CI automation not adopted |
| UNIFIED_FIT_SOURCES | Blocked -- Eve Workbench API requires manual developer approval |
| EmulatingRadioVoiceinTextLLMs | Reference document, not actionable |

---

## Part 2: Review Findings Summary

### 2.1 Finding Counts by Review

| Review | Critical | High | Medium | Low | Info | Total |
|--------|----------|------|--------|-----|------|-------|
| Security | 0 | 0 | 6 (incl. 1 Med-High) | 2 | 1 | 9 |
| Coverage Quality | 4 | 4 | 6 | 2 | 2 | 18 |
| Python Code Quality | 3 (P0) | 4 (P1) | 5 (P2) | 4 (P3) | 0 | 16 |
| System Design | 0 | 3 | 7 | 4 | 3 | 17 |
| GitHub First Impression | 0 | 0 | 3 | 5 | 5 | 13 |
| Onboarding UX | 0 | 2 | 7 | 6 | 4 | 19 |
| Test Harness | 0 | 3 | 7 | 4 | 0 | 14 |
| Accretion Audit | 0 | 0 | 7 (ranked) | 5 (QW) | 0 | 12 |
| **Total** | **7** | **16** | **48** | **32** | **15** | **118** |

### 2.2 Top 5 Findings Impacting Release Readiness

**1. Security regression: authenticated MCP actions re-enabled without confirmation gate** (Security Finding #1, Medium-High)

The SECURITY_001 mitigation that removed `authenticated` from the MCP policy's `allowed_levels` has been reverted. Both `reference/mcp-policy.json` and the `PolicyConfig` code default include `authenticated`, and `require_confirmation` is empty. This means prompt injection via cached data could trigger authenticated ESI calls (mail, mining ledger) without user confirmation.

- **Status:** NEW regression (previously mitigated, reverted)
- **Action:** Restore the mitigation. Add a regression test. ~1 hour.

**2. MCP market tools entirely untested -- 8 modules at 0% coverage** (Coverage Finding #1, Critical)

The actual MCP market tool implementations (`tools_prices.py`, `tools_orders.py`, `tools_valuation.py`, `tools_route.py`, `tools_npc.py`, `tools_management.py`, `tools_analysis.py`, `tools_scope_refresh.py`) totaling ~955 statements have zero test coverage. Market operations are the most-used MCP actions.

- **Status:** KNOWN gap (previously tracked as "push toward 75%", now quantified)
- **Action:** Create tests for the 8 market tool modules. Prioritize `tools_prices.py` and `tools_orders.py`.

**3. Documentation commands that fail for new contributors** (Onboarding H-2 + M-1)

DEPLOYMENT.md instructs `uv sync --extra dev` (wrong -- dev tools are in `[dependency-groups]`, not `[project.optional-dependencies]`). README Development Setup shows `uv sync` without `--dev`. Both cause pytest/mypy/ruff to be missing. Two one-line fixes.

- **Status:** NEW (not previously identified)
- **Action:** Fix `--extra dev` to `--dev` in DEPLOYMENT.md; add `--dev` to README. 2 minutes.

**4. `core` package depends upward on `mcp` and `commands` -- layer inversion** (System Design H1)

The foundation `core` package imports from `mcp.sde.queries` and `commands.sync_profile`, creating a logical layer violation. This makes `core` fragile and untestable in isolation.

- **Status:** NEW (not previously identified at this severity)
- **Action:** Extract SDE facade into `core/`, move `freshness_adapters.py` to `services/`. Medium effort.

**5. Version mismatch: `__init__.py` says 1.0.0, `pyproject.toml` says 2.0.0** (Python P0-1, Onboarding L-1)

Multiple locations report different versions: `__init__.py` (1.0.0), `pyproject.toml` (2.0.0), `aria-init` script (1.0.0), CHANGELOG (last versioned: 0.1.0). This confuses users and tooling.

- **Status:** NEW (not previously identified)
- **Action:** Single-source version via `importlib.metadata`. Sync `aria-init` version. 30 minutes.

### 2.3 Cross-Cutting Themes

Several findings recur across multiple reviews:

| Theme | Reviews Identifying It | Summary |
|-------|----------------------|---------|
| Coverage gaps in MCP tools layer | Coverage, Test Harness, Python | 8 market tools at 0%, fitting tools at 0%, 6/8 dispatchers below 50% |
| Exception handling debt | Python (276 broad catches), System Design (no base exception) | `except Exception` used broadly; no `AriaError` base class; B904 suppressed |
| Singleton proliferation | Python (30+), System Design (4 patterns), Test Harness (reset fragility) | 30+ singletons with inconsistent lifecycle patterns |
| Sync/async code duplication | Python, System Design | `ESIResponse`/`AsyncESIResponse` and `ESIError`/`AsyncESIError` are identical |
| Vendored code in coverage | Coverage, Test Harness | EOS vendor code inflates denominator; `*/_vendor/*` not in omit |
| No coverage trend tracking | Coverage, Test Harness, GitHub First Impression | CI generates XML but doesn't upload to Codecov or retain as artifact |

---

## Part 2.5: What Remains Before Public Release

### Tier 1 -- Must-Do (blockers or near-blockers)

#### 1.1 Verify `aria-init` onboarding path -- VERIFIED

**Source:** LINUX_VM_DOCKER_RUNTIME_PROPOSAL (archived 2026-02-24)

Investigation confirmed that `aria-init` already uses the correct `userdata/pilots/{id}_{slug}/` layout and calls `uv run python`. The proposal was outdated -- the issues it described had already been fixed. Proposal archived as COMPLETE.

#### 1.2 Spot-check GITHUB_RELEASE_READINESS deliverables -- VERIFIED

**Source:** GITHUB_RELEASE_READINESS (archived as complete), confirmed by GITHUB_FIRST_IMPRESSION review

All items were marked done on 2026-02-02. Spot-check results:

- [x] README contains a real ARIA response example (sample output block) -- confirmed
- [x] CI badge is present and green -- confirmed
- [x] "What This Is NOT" section exists (not a bot, not an overlay, not CCP-affiliated) -- confirmed
- [x] CHANGELOG.md has meaningful content (not just a stub) -- confirmed (209 lines, proper Keep a Changelog format)
- [x] Recovery / "Starting Fresh" section in troubleshooting docs -- confirmed

The fresh GitHub First Impression review confirmed the README passes the 30-second test and rates the presentation as B+ overall.

#### 1.3 Fix security regression: restore authenticated-level policy gate

**Source:** SECURITY review Finding #1

The `authenticated` sensitivity level must be removed from `allowed_levels` in both `reference/mcp-policy.json` and the `PolicyConfig` code default. Add a regression test to prevent future re-enablement.

**Action:** ~1 hour. This is the only finding with a security regression status.

#### 1.4 Fix documentation commands that fail for contributors

**Source:** ONBOARDING_UX review Findings H-2, M-1

Two one-line fixes:
- DEPLOYMENT.md line 68: `uv sync --extra dev` -> `uv sync --dev`
- README.md line 294: `uv sync` -> `uv sync --dev`

**Action:** 2 minutes. Without this fix, any contributor following the docs cannot run tests.

### Tier 2 -- Should-Do (high-impact polish)

#### 2.1 README first-run improvements -- DONE

**Source:** README_FIRST_RUN_IMPROVEMENTS_PROPOSAL (archived, proposed, not implemented)

Cherry-picked highest-impact items (completed in `cleanup/pre-release-tier1`):
- Added "Get Value in 60 Seconds" section with copy-paste first prompt
- Added "Verify It Worked" block after Quick Start
- Expanded troubleshooting with `Permission denied` and missing game data fixes
- Added SECURITY.md link to Data Freshness section
- Tightened disclaimer to professional copy
- Collapsed Route Planning and Fit Recommendation examples behind `<details>`

#### 2.2 Test coverage: address critical gaps and raise threshold

**Source:** COVERAGE_QUALITY review (18 findings), TEST_HARNESS review

Current state: 60.3% coverage (6,271 tests, threshold 59%). Key gaps from the coverage review:

| Gap | Coverage | Severity | Statements |
|-----|----------|----------|------------|
| MCP market tools (8 modules) | 0% | Critical | ~955 |
| Auth token refresh/OAuth | 59% | Critical | 351 (128 uncovered) |
| SDE importer | 11% | High | 867 |
| Core HTTP client | 64% | High | 329 (109 uncovered) |
| MCP fitting tools | 0% | High | ~73 |
| CLI command layer (18/32 below 50%) | ~45% avg | High | ~4,200 uncovered |
| Market database async | 14% | High | 369 |
| Backfill service | 0% | High | 111 |

**Priority actions:**
1. Exclude vendored code from coverage (`*/_vendor/*` in omit) -- one-line config fix that gives accurate first-party numbers
2. Test MCP market tools (start with `tools_prices.py`, `tools_orders.py`)
3. Test auth token refresh path (security-critical)
4. Raise `fail_under` to 60% (current coverage is 60.3%)
5. Add coverage upload to CI (Codecov or equivalent) for trend tracking

#### 2.3 Fix version mismatch

**Source:** PYTHON_REVIEW P0-1, ONBOARDING_UX L-1

`__init__.py` declares 1.0.0, `pyproject.toml` declares 2.0.0, `aria-init` declares 1.0.0, CHANGELOG shows 0.1.0 as last release. Single-source the version via `importlib.metadata` and sync `aria-init`.

**Action:** 30 minutes. Fixes a persistent confusion point flagged by 3 reviews.

#### 2.4 Security quick wins from Security review

**Source:** SECURITY review Findings #2, #5, #6, #7

| Finding | Fix | Effort |
|---------|-----|--------|
| Shell injection in boot scripts (heredoc pattern) | Replace `json.loads('''$var''')` with stdin piping | ~1 hour |
| Audit log sanitization gaps | Unify sanitization into shared utility | ~2 hours |
| Rate limiting defaults to unlimited | Set `rate_limit_per_minute: 60` in config | ~30 min |
| SDE importer SQL f-string injection | Add identifier quoting to column names | ~30 min |

#### 2.5 Community health files

**Source:** GITHUB_FIRST_IMPRESSION review Findings M-1, M-2, M-3

| Item | Fix | Effort |
|------|-----|--------|
| Missing `CODE_OF_CONDUCT.md` | Adopt Contributor Covenant v2.1 | 5 min |
| Missing `.github/dependabot.yml` | Create with pip + actions ecosystems | 5 min |
| Missing `[project.urls]` in pyproject.toml | Add Homepage, Repository, Issues URLs | 2 min |

#### 2.6 Reconcile `.mcp.json` with DEPLOYMENT.md

**Source:** ONBOARDING_UX Finding H-1

The shipped `.mcp.json` uses `python -m aria_esi.mcp.server` with `cwd: src`, while DEPLOYMENT.md documents `aria-universe` with no `cwd`. Reconcile to prevent MCP misconfiguration for users copying docs.

**Action:** 10 minutes.

#### 2.7 Finish sovereignty remaining items -- PARTIALLY DONE

**Source:** SOVEREIGNTY_TERRITORY_DATA_PROPOSAL (active, mostly implemented)

- Territory-preferring routing -- **DONE**
- Hunting-grounds skill enhancement -- **DEFERRED** (cosmetic/persona work)

Note: The Accretion Audit ranks the full sovereignty subsystem (3,800+ lines) as Rank 3 removal candidate. The territory routing feature is the only part with clear user value; the full sovereignty database with SQLite storage and CLI commands is over-engineered for the use case.

#### 2.8 DevContainer end-to-end validation

**Source:** DEVCONTAINER_PROPOSAL (active, implemented)

The Docker onboarding path is implemented but should be validated on a clean Docker Desktop install to confirm the zero-friction promise.

**Action:** Run through the DevContainer flow on a clean machine before advertising it in release notes.

#### 2.9 Market watchlist user-facing skill -- ALREADY DONE

**Source:** MARKET_WATCHLIST_PROPOSAL (archived, backend complete)

The `/watchlist` skill already exists (`.claude/skills/watchlist/SKILL.md`) and exposes the full MCP watchlist backend to users. No additional work needed.

### Tier 3 -- Not Needed for Release (future enhancements)

These are post-release features. None are prerequisites.

| Proposal | Category | Notes |
|----------|----------|-------|
| T2_INVENTION_AMORTIZATION | Industry | Amortized invention costs for `/build-cost` |
| ABYSSAL_GUIDE | PvE | Abyssal Deadspace tier/weather/ship guide |
| HAULING_SCORE_ARBITRAGE | Market | ISK/m3 ranking algorithm for arbitrage |
| COMMUNICATIONS_STYLE_LAYER | Persona | Radio voice presets for notifications |
| CORP_SKILLS | Management | Unified `/corp` command consolidation |
| SITE_COMPOSITION_DATA | PvE | Curated ore/gas/NPC spawn data |
| PERSONA_VARIANTS | Persona | Pirate faction persona variants (PARIA-S, PARIA-G) |
| ADHOC_MARKETS_HUB_CENTRIC | Market | Hub-centric market engine with ESI scopes |
| SKILL_AWARE_FIT_SELECTION | Fitting | Deprecated Python framework (MCP actions remain) |

Also deferred to post-release based on review findings:

| Item | Source | Rationale |
|------|--------|-----------|
| Decompose `universe.py` dispatcher (3,798 lines) | Python P1-4 | Important but not user-facing |
| Eliminate sync/async client duplication | Python P1-5, System Design M3 | Code quality, not functionality |
| Define `AriaError` base exception | System Design M6 | Architecture improvement |
| Extract shared data access from `mcp` | System Design H2 | Large refactor, no user impact |
| Replace 276 broad `except Exception` catches | Python P1-7 | Incremental, high effort |
| Standardize singleton pattern | System Design H3 | Internal quality |
| Advance mypy to Phase 5 | Python P2-10 | Gradual, in-progress |
| Migrate igraph away from pickle | Security Finding #3 | Medium-term security improvement |

---

## Part 3: Recommended Release Sequence

### Pre-release checklist

1. **Restore authenticated-level policy gate** -- Security regression (Finding #1). Remove `authenticated` from `allowed_levels` in both code and config. Add regression test. (~1 hour)
2. **Fix documentation commands** -- DEPLOYMENT.md `--extra dev` -> `--dev`; README `uv sync` -> `uv sync --dev`. (~2 minutes)
3. **Fix version mismatch** -- Single-source from `pyproject.toml` via `importlib.metadata`. Sync `aria-init`. (~30 minutes)
4. **Reconcile `.mcp.json` with docs** -- Prevent MCP misconfiguration for new users. (~10 minutes)
5. **Add `CODE_OF_CONDUCT.md`** -- Completes GitHub Community Profile. (~5 minutes)
6. **Add `.github/dependabot.yml`** -- Automated dependency vulnerability monitoring. (~5 minutes)
7. **Exclude vendored code from coverage** -- Add `*/_vendor/*` to omit. Gives accurate first-party coverage number. (~1 minute)
8. **Fix boot script shell injection pattern** -- Replace `json.loads('''$var''')` with stdin piping. (~1 hour)
9. **Verify `aria-init`** works with current `userdata/` layout -- already verified, no action needed.
10. **Run the DevContainer path** end-to-end on a clean Docker install.
11. **Tag v0.1.0** -- the project is ready; remaining items are polish, not blockers.

Items 1-8 represent approximately 3-4 hours of work. Items 1-2 are the only items that could cause user-facing failures.

### Post-release priorities

1. Push test coverage: MCP market tools (0%), auth module (59%), SDE importer (11%)
2. Raise coverage threshold to 60%, then 65% as gaps are filled
3. Add coverage trend tracking (Codecov integration)
4. Execute Security review quick wins (audit log sanitization, rate limiting defaults, SQL quoting)
5. Address System Design layer inversions (`core` -> `mcp` dependency)
6. Tackle Accretion Audit quick wins (delete archetype library, `context_budget.py`, unreferenced reference data)
7. Fix remaining Onboarding UX findings (troubleshooting consolidation, phantom env variables, model name fix)
8. Tackle Tier 3 enhancements based on user demand

---

## Appendix A: Proposal Census

| Category | Count | Status |
|----------|-------|--------|
| Fully implemented and archived | 28 | Done |
| Consolidated or superseded | 4 | Done |
| Blocked / dead | 1 | UNIFIED_FIT_SOURCES (Eve Workbench API) |
| Reference documents | 1 | EmulatingRadioVoiceinTextLLMs |
| Active -- implemented | 3 | DEVCONTAINER, SOVEREIGNTY, ship-hull-value-signal |
| Active -- proposed | 2 | LINUX_VM_DOCKER_RUNTIME, T2_INVENTION_AMORTIZATION |
| Archived -- proposed (not started) | 6 | ABYSSAL, ADHOC_MARKETS, HAULING_SCORE, COMMS_STYLE, CORP_SKILLS, README_FIRST_RUN |
| Archived -- in progress | 1 | TEST_COVERAGE_80_PERCENT (60.3%) |
| **Total** | **46** | |

## Appendix B: Review Baseline (2026-02-24)

All 8 reviews were conducted on 2026-02-24 against commit `12b7172f` (branch `fix/benchmark-coverage-failure`).

| # | Review | File | Lines | Reviewer | Key Metric |
|---|--------|------|------:|----------|------------|
| 1 | Accretion Audit | `dev/reviews/ACCRETION_AUDIT_2026-02-24.md` | 321 | Claude Opus 4.6 | 7 ranked candidates, 5 quick wins |
| 2 | Security | `dev/reviews/SECURITY_2026-02-24.md` | 335 | Claude Opus 4.6 | 9 findings, 1 regression |
| 3 | Coverage Quality | `dev/reviews/COVERAGE_QUALITY_2026-02-24.md` | 545 | Claude Opus 4.6 | 18 findings, 60.3% coverage |
| 4 | Python Code Quality | `dev/reviews/PYTHON_REVIEW_2026-02-24.md` | 663 | Claude Opus 4.6 | 3.7/5 overall, 16 action items |
| 5 | GitHub First Impression | `dev/reviews/GITHUB_FIRST_IMPRESSION_2026-02-24.md` | 372 | Claude Opus 4.6 | B+ grade, 5/6 community files |
| 6 | Onboarding UX | `dev/reviews/ONBOARDING_UX_2026-02-24.md` | 408 | Claude Opus 4.6 | 8.3/10, 19 findings |
| 7 | System Design | `dev/reviews/SYSTEM_DESIGN_2026-02-24.md` | 538 | Claude Opus 4.6 | 3 High, 7 Medium findings |
| 8 | Test Harness | `dev/reviews/TEST_HARNESS_2026-02-24.md` | 678 | Claude Opus 4.6 | B+ grade, 11 recommendations |
| | **Total** | | **3,860** | | |
