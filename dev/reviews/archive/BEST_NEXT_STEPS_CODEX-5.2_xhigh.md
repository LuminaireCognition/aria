# Best Next Steps Review (Codex 5.2 xhigh)

**Reviewer:** Codex 5.2 xhigh
**Date:** 2026-01-27
**Lens:** LLM-integrated applications, Claude Code Skills architecture, EVE Online CSM + corp CEO operations
**Scope:** ARIA core runtime, MCP/CLI tool layer, skills system, and user-facing workflow

---

## Quick Assessment

ARIA is already strong on safety (prompt-injection hardening), tool determinism (MCP wrappers), and player value (mission/route/mining/exploration). The biggest leverage now is consistency and timeliness: make skills more discoverable/reliable, tighten data freshness/volatility handling, and add real-time intel and corp-ops workflows that map to how pilots and corporations actually operate.

---

## Status Tracking

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | RedisQ real-time intel | ✅ Verified | E2E verified; see evidence below |
| 2 | MCP/CLI unification | 🔄 In Progress | Route unified; loop/activity remain |
| 3 | Skill quality baselines | Not Started | CI/pre-commit integration |
| 4 | Volatile data + provenance | Not Started | TTLs and freshness flags |
| 5 | Input validation + error schemas | Not Started | Pydantic models |
| 6 | PI + wormholes + fleet mining | Not Started | Consider splitting scope |
| 7 | Corp-ops dashboards | Not Started | ESI scope implications |
| 8 | Onboarding + compliance | Not Started | First-run flow improvements |

**Last updated:** 2026-01-27 (route unification verified)

### Verification Evidence (Item 1)

- Unit tests: 32/32 passed (`tests/unit/test_threat_cache.py`, `tests/unit/test_realtime_integration.py`)
- Poller: running; 2,798 kills cached, 110 in last hour
- MCP: include_realtime returns `realtime_healthy: true`
- Endpoints: activity/gatecamp/local_area include realtime objects
- CLI: `--realtime` works for activity-systems and gatecamp

### Verification Evidence (Item 2 - Route Unification)

- Commit: `5c6450e` - "Unify route calculation with NavigationService"
- New service: `src/aria_esi/services/navigation/` with router, weights, result_builder, errors
- CLI uses NavigationService: `commands/navigation.py:180`
- MCP uses NavigationService: `mcp/tools_route.py:166`
- Tests: 15/15 passed (`tests/commands/test_navigation.py`)
- CLI now supports `--avoid` parameter, matching MCP capabilities
- **Remaining:** Loop planning and activity queries still have separate implementations

---

## Best Next Steps (Prioritized)

1) Ship real-time intel (RedisQ) into threat/route/gatecamp workflows

Status: Verified (2026-01-27)

Why this is best: the single biggest gameplay gap is freshness. Hourly ESI aggregates are too slow for gank/gatecamp decisions. Real-time killmail streams materially reduce losses, enable safe routing, and add corp-level defensive value. It also creates a clear differentiator versus static "tips" assistants.

What to do: operationalize the feature (monitoring/alerting, retention tuning, clear freshness messaging in skills, and a brief runbook for degraded mode).

2) Unify MCP and CLI implementations behind a shared core layer

Status: In Progress (2026-01-27) - Route calculation unified

Why this is best: the MCP/CLI dual-path is already drifting. Feature parity issues increase maintenance burden and cause inconsistent outputs that confuse the LLM and users. A shared core eliminates duplicated logic, keeps skills consistent when MCP is unavailable, and makes testing simpler.

What to do: extract shared route/loop/activity logic into a single service module, have MCP tools and CLI commands call it, and standardize response models.

Progress:
- ✅ Route calculation: `NavigationService` in `services/navigation/` (commit 5c6450e)
- ⬜ Loop planning: Still separate implementations
- ⬜ Activity queries: Still separate implementations

Next: Apply same pattern to loop planning (`cmd_loop` / `universe_loop`).

3) Enforce skill quality baselines and preflight gating

Why this is best: skills are the product surface area, and variability in frontmatter/triggers/data_sources lowers discoverability and reliability. Claude Code Skills benefit most when metadata is consistent and validated before invocation.

What to do: make `.claude/scripts/aria-skill-index.py --check` part of CI/pre-commit, define a minimum-required frontmatter set (name/description/triggers/category/data_sources/esi_scopes), and auto-run skill preflight for pilot-dependent skills by default (with an opt-out for power users).

4) Add structural enforcement for volatile data + provenance freshness

Why this is best: stale location/wallet/ship data causes real decision errors in EVE. A "protocol-only" rule is too easy to violate under LLM pressure. You already have `_meta` support; now make freshness first-class.

What to do: tag volatile data sources in the skill index, require explicit user intent before exposing them, and standardize `_meta.source`/`_meta.as_of` across dispatchers. Add TTLs and "freshness required" flags to route/threat outputs.

5) Centralize tool input validation and error schemas

Why this is best: LLMs are brittle when inputs are unvalidated and errors are inconsistent. A unified validation layer reduces hallucinated parameter bugs and makes retries/clarifications reliable.

What to do: introduce Pydantic input models or `@validate_call` for high-traffic actions (route, market, fitting, skills), and use `create_error_meta()` in dispatcher exception paths to guarantee a consistent error envelope.

6) Expand high-demand gameplay coverage (PI + wormholes + fleet mining)

Why this is best: these are the most common "what should I do next" gaps for both new pilots and corp ops. PI and wormholes are unique enough to justify dedicated skills, and mining fleets benefit from boost/hauler/compression guidance.

What to do: implement `/pi-advisory` and `/wormhole` from the TODO, extend `/mining-advisory` for fleet mode, and add wormhole-aware exploration heuristics.

7) Add corp-ops dashboards and multi-pilot aggregation

Why this is best: as a CEO/CSM, the highest-value assistant behaviors are corp-level: wallet/industry health, asset posture, war-target watchlists, and member activity summaries. The repo already has corp skills and watchlists; the missing piece is aggregation and cadence.

What to do: build a "corp daily brief" that combines corp wallet/industry/killmail intel with pilot safety status; support multi-pilot rollups (alts) and role-based views (CEO/Director vs member).

8) Improve onboarding clarity and compliance guardrails

Why this is best: many support questions come from expectation mismatch (ESI is read-only, persona staleness, missing scopes). Clearer early guidance reduces friction and prevents user-error loops.

What to do: surface ESI read-only constraints in `/help` and first-run flow, add an automated startup preflight (credentials + persona context + skill index freshness), and include an explicit "no automation/botting" compliance reminder.

---

## Optional Follow-On (Once the Above Land)

- Raise coverage thresholds and expand golden tests to top 10 skills and most-used MCP actions.
- Introduce a lightweight "activity state" tracker so skills can infer intent (mining/exploration/mission) without re-asking every time.
- Package a minimal "starter profile" for new players with curated skills and a simplified persona context.
