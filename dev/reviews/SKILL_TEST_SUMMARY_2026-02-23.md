# ARIA Skill Test Summary Report - 2026-02-23

## Test Scope

- **Skills tested:** 11 of 48 total (23%)
- **Selection criteria:** Single-query skills with ESI flag NONE or LOW
- **Pilot:** Federation Navy Suwayyah (new character, 1 day old, Gallente, rp_level: off)
- **Method:** Parallel sub-agent execution via Task tool, each invoking the Skill tool

## Outcome Summary

| Outcome | Count | Skills |
|---------|------:|--------|
| Full success | 5 | aria-status, mining-advisory, skillqueue, orders, wallet-journal |
| Expected stub | 2 | ransom-calc, sec-status |
| Blocked (permissions) | 3 | mail, mining, lp-store |
| Blocked (no fallback) | 1 | killmail |

**Effective success rate:** 7/11 (64%) executed as designed. 4/11 blocked by test environment constraints, not skill bugs.

**Adjusted success rate (excluding environment issues):** 7/7 (100%) of skills that could execute did so correctly.

## Findings by Category

### 1. Documentation Bug

| Skill | Issue | Severity |
|-------|-------|----------|
| orders | Skill docs reference `--active` CLI flag that doesn't exist | Low |

The agent's first invocation failed with `unrecognized arguments: --active`. It recovered by checking `--help` and retrying without the flag. The CLI defaults to active orders anyway, making the flag redundant — but the docs should match reality.

**Action:** Remove `--active` from the orders skill documentation, or add the flag to the CLI.

### 2. Missing Fallback Paths

Three skills have a hard dependency on Bash CLI execution with no alternative data path:

| Skill | CLI Command | MCP Alternative | Degradation |
|-------|-------------|-----------------|-------------|
| mail | `aria-esi mail` | None | Total failure |
| mining | `aria-esi mining` | None | Total failure |
| lp-store | `aria-esi lp / lp-offers` | None | Total failure |
| killmail | `aria-esi killmail` + WebFetch | None | Total failure |

These skills cannot function if CLI execution is unavailable. In contrast, skills like `route` and `price` have MCP dispatchers as primary paths with CLI as fallback.

**Impact:** Low in normal operation (Bash is typically available), but this creates a fragile dependency. If ESI CLI auth breaks, these skills have zero degradation path.

**Action:** Consider adding MCP actions for `mail`, `mining`, `lp-store`, and `killmail` to match the pattern used by market/universe/sde skills.

### 3. Persona Exclusivity System

Both paria-exclusive skills (ransom-calc, sec-status) behaved correctly:

- Stub loaded instead of redirect target
- Persona match checked against `persona`, `fallback`, and `unrestricted_skills`
- Helpful alternatives suggested for empire pilots
- No ESI calls wasted on blocked skills
- Double-gating (both `_index.json` and SKILL.md frontmatter) provides defense-in-depth

**Verdict:** Working as designed. No issues found.

### 4. ESI Data Integrity

All ESI-connected skills that executed returned clean, validated data:

| Skill | Endpoint | Response Quality |
|-------|----------|-----------------|
| skillqueue | `/characters/{id}/skillqueue/` | 30 skills, timestamps valid, progress tracking correct |
| orders | `/characters/{id}/orders/` | Empty set (expected for new char), all counters consistent |
| wallet-journal | `/characters/{id}/wallet/journal/` | 42 entries, income/expense math verified, balances correct |
| aria-status | `sync-profile` | Standings synced (4 empire, 18 corps, 5 pirates), sec status 1.58 |

No stale data, no auth failures, no timeouts. ESI integration is solid.

### 5. New Character Edge Cases

The test pilot was created the same day. Skills handled this gracefully:

| Skill | Edge Case | Handling |
|-------|-----------|----------|
| orders | 0 active orders | Clean empty state, helpful suggestion |
| wallet-journal | Only 1 day of history despite 7-day query | Returned available data without error |
| mining-advisory | No blueprints, no minerals | Adapted advisory for "future manufacturing" |
| aria-status | Incomplete home base config | Noted `[To be determined]` fields without failing |
| skillqueue | 99-day queue on day-1 character | Displayed normally |

**Verdict:** Skills degrade gracefully for new characters. No crashes or confusing output.

### 6. Agent Execution Quality

Sub-agents demonstrated varying levels of thoroughness:

| Behavior | Agents |
|----------|--------|
| Executed skill + verified via source code | killmail, lp-store |
| Read all data sources before responding | mining-advisory, ransom-calc, sec-status |
| Minimal execution (skill + CLI only) | skillqueue, orders |
| Blocked early, documented expected behavior | mail, mining |

**Observation:** Agents that were denied Bash access sometimes performed deep source code analysis instead, producing valuable architectural documentation even without live execution.

## Common Themes

### What Worked Well

1. **Skill loading framework** — All 11 skills loaded correctly via the Skill tool. No loading failures, no missing files, no schema errors.

2. **ESI integration** — Every authenticated ESI call succeeded. Token refresh, scope validation, and response parsing all worked without issues.

3. **Persona gating** — The exclusivity system correctly blocked 2 skills and served appropriate stubs with alternative suggestions. Defense-in-depth (double declaration) adds resilience.

4. **Data volatility compliance** — No skill leaked volatile data (current location, ship) unprompted. The `rp_level: off` format was consistently applied.

5. **Contextual suggestions** — Skills offered relevant follow-up commands (e.g., `/mission-brief` from wallet-journal, `/fitting` from mining-advisory) without over-suggesting.

### What Needs Attention

1. **CLI-only skills have no fallback** — 4 skills (mail, mining, lp-store, killmail) cannot degrade when CLI is unavailable. This is the single largest gap.

2. **Documentation drift** — The orders skill `--active` flag mismatch is minor but symptomatic. Skill docs should be validated against actual CLI `--help` output periodically.

3. **Test coverage gap** — This run only covered 23% of skills (11/48). The remaining 37 skills include higher-ESI, multi-query, and more complex skills that may have additional issues.

## Recommendations

| Priority | Action | Effort |
|----------|--------|--------|
| Low | Fix orders skill docs (remove `--active` reference) | 5 min |
| Medium | Add MCP actions for mail, mining, lp-store, killmail | Days |
| Medium | Run test pass on remaining 37 skills (MED/HEAVY ESI, multi-query) | Hours |
| Low | Add automated CLI flag validation (compare skill docs vs `--help`) | Hours |

## Raw Data

- Full test results: `dev/reviews/SKILL_TEST_RESULTS_2026-02-23.md`
- Skill query catalog: `dev/reviews/SKILL_EXERCISE_QUERIES.md`
