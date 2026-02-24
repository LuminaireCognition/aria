# Public Release Readiness Report

**Status:** ASSESSMENT
**Date:** 2026-02-24
**Scope:** Full proposal audit — what has been done, what remains before initial public release

## Executive Summary

An audit of all 45 proposals (5 active, 40 archived) concludes that ARIA is **near-ready for a quiet public release**. The prior `GITHUB_RELEASE_READINESS` proposal (archived as complete) graded the project "A- for first-visitor impressions" and declared it "ready for a quiet release." The repo is already public on GitHub.

The single most likely blocker is verifying that `aria-init` works correctly with the current `userdata/` directory layout. Beyond that, remaining work is polish and future enhancements.

**Test suite:** 6,255 tests passing, 60.3% coverage (threshold: 59%).

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
| PROPOSAL_GEMINI3PRO_VALIDATED_ISSUES | Security review — issues validated and fixed |

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
| PROMPT_LIBRARY_REVIEW_COVERAGE | Superseded — CI automation not adopted |
| UNIFIED_FIT_SOURCES | Blocked — Eve Workbench API requires manual developer approval |
| EmulatingRadioVoiceinTextLLMs | Reference document, not actionable |

---

## Part 2: What Remains Before Public Release

### Tier 1 — Must-Do (blockers or near-blockers)

#### 1.1 Verify `aria-init` onboarding path — VERIFIED

**Source:** LINUX_VM_DOCKER_RUNTIME_PROPOSAL (archived 2026-02-24)

Investigation confirmed that `aria-init` already uses the correct `userdata/pilots/{id}_{slug}/` layout and calls `uv run python`. The proposal was outdated — the issues it described had already been fixed. Proposal archived as COMPLETE.

#### 1.2 Spot-check GITHUB_RELEASE_READINESS deliverables

**Source:** GITHUB_RELEASE_READINESS (archived as complete)

All items were marked done on 2026-02-02. Spot-check results:

- [x] README contains a real ARIA response example (sample output block) — confirmed
- [x] CI badge is present and green — confirmed
- [x] "What This Is NOT" section exists (not a bot, not an overlay, not CCP-affiliated) — added in `cleanup/pre-release-tier1`
- [x] CHANGELOG.md has meaningful content (not just a stub) — confirmed (209 lines, proper Keep a Changelog format)
- [x] Recovery / "Starting Fresh" section in troubleshooting docs — added in `cleanup/pre-release-tier1`

### Tier 2 — Should-Do (high-impact polish)

#### 2.1 README first-run improvements — DONE

**Source:** README_FIRST_RUN_IMPROVEMENTS_PROPOSAL (archived, proposed, not implemented)

Targets a "clone to first useful response in under 5 minutes" experience. Cherry-picked highest-impact items:
- Added "Get Value in 60 Seconds" section with copy-paste first prompt
- Added "Verify It Worked" block after Quick Start
- Expanded troubleshooting with `Permission denied` and missing game data fixes
- Added SECURITY.md link to Data Freshness section
- Tightened disclaimer to professional copy
- Collapsed Route Planning and Fit Recommendation examples behind `<details>`

#### 2.2 Test coverage push toward 75%

**Source:** TEST_COVERAGE_80_PERCENT_PROPOSAL (archived, in-progress)

Currently at 60.3% (up from 52.9% baseline). The proposal tracks a phased approach with tiered per-module thresholds. Not blocking, but higher coverage signals project quality to potential contributors.

**Action:** Continue opportunistic coverage gains. Prioritize modules with high blast radius (core services, ESI integration).

#### 2.3 Finish sovereignty remaining items — PARTIALLY DONE

**Source:** SOVEREIGNTY_TERRITORY_DATA_PROPOSAL (active, mostly implemented)

- Territory-preferring routing — **DONE**: Added `prefer_territory` and `avoid_territory` params to `universe(action="route")`. Expands coalition aliases to system sets via `get_systems_by_coalition()`. Weight-based preference (3x penalty for non-territory systems).
- Hunting-grounds skill enhancement — **DEFERRED**: The `/hunting-grounds` skill already has a full "Coalition Intelligence (Null-Sec Hunting)" section (lines 158-225 in SKILL.md). The proposal marks additional work as PARIA-exclusive persona overlay, which is cosmetic/persona work.

#### 2.4 DevContainer end-to-end validation

**Source:** DEVCONTAINER_PROPOSAL (active, implemented)

The Docker onboarding path is implemented but should be validated on a clean Docker Desktop install to confirm the zero-friction promise.

**Action:** Run through the DevContainer flow on a clean machine before advertising it in release notes.

#### 2.5 Market watchlist user-facing skill — ALREADY DONE

**Source:** MARKET_WATCHLIST_PROPOSAL (archived, backend complete)

The `/watchlist` skill already exists (`.claude/skills/watchlist/SKILL.md`) and exposes the full MCP watchlist backend to users. No additional work needed.

### Tier 3 — Not Needed for Release (future enhancements)

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

---

## Part 3: Recommended Release Sequence

### Pre-release checklist

1. **Verify `aria-init`** works with the current `userdata/` layout — the single most likely blocker for new users
2. **Spot-check README** for sample output, CI badge, "What This Is NOT", and CHANGELOG content
3. **Run the DevContainer path** end-to-end on a clean Docker install
4. **Tag v0.1.0** — the project is ready; remaining items are polish, not blockers

### Post-release priorities

1. Push test coverage toward 75%
2. Build `/price-watch` skill for market watchlists
3. Finish sovereignty routing enhancements
4. Implement README first-run improvements based on real user feedback
5. Tackle Tier 3 enhancements based on user demand

---

## Appendix: Proposal Census

| Category | Count | Status |
|----------|-------|--------|
| Fully implemented and archived | 28 | Done |
| Consolidated or superseded | 4 | Done |
| Blocked / dead | 1 | UNIFIED_FIT_SOURCES (Eve Workbench API) |
| Reference documents | 1 | EmulatingRadioVoiceinTextLLMs |
| Active — implemented | 3 | DEVCONTAINER, SOVEREIGNTY, ship-hull-value-signal |
| Active — proposed | 2 | LINUX_VM_DOCKER_RUNTIME, T2_INVENTION_AMORTIZATION |
| Archived — proposed (not started) | 6 | ABYSSAL, ADHOC_MARKETS, HAULING_SCORE, COMMS_STYLE, CORP_SKILLS, README_FIRST_RUN |
| Archived — in progress | 1 | TEST_COVERAGE_80_PERCENT (60.3%) |
| **Total** | **46** | |
