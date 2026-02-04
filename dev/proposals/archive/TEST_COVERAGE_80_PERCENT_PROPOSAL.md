# Test Coverage 80% Target Proposal

## Executive Summary

ARIA currently has **54.97% test coverage** with a threshold of 54%. This proposal evaluates the feasibility of reaching **80% coverage** and recommends a phased approach with tiered thresholds by module type.

**Assessment: Achievable with strategic effort.** The path requires ~8,100 additional statements covered, which is ambitious but realistic given that significant portions of uncovered code are pure logic that simply lack tests.

**Recommended Target: 75% overall** with tiered per-module thresholds.

---

## Effort Tracking

### Progress Summary

| Metric | Baseline | Current | Target (Phase 1) | Target (Final) |
|--------|----------|---------|------------------|----------------|
| Coverage | 52.89% | **60.04%** | 60% | 75-80% |
| Threshold | 50% | **54%** | 58% | 75% |
| Tests | 3,920 | **4,916** | ~4,600 | ~5,500 |

### Phase 1: Quick Wins (Target: 60%)

#### Priority 1: Archetypes Companion Modules - COMPLETE

| Module | Before | After | Tests Added | Status |
|--------|--------|-------|-------------|--------|
| `archetypes/selection.py` | ~14% | **79%** | 34 | Done |
| `archetypes/pricing.py` | ~12% | **91%** | 21 | Done |
| `archetypes/tuning.py` | ~10% | **82%** | 24 | Done |
| `archetypes/validator.py` | ~17% | **90%** | 33 | Done |
| `archetypes/migration.py` | ~15% | **85%** | 32 | Done |
| **Total** | | | **175** | |

**Completed:** 2026-01-31

**Test files created:**
- `tests/archetypes/test_selection.py` - FitCandidate, SelectionResult, skill/tank/damage checks
- `tests/archetypes/test_pricing.py` - EFT parsing, market price fetching, fit estimation
- `tests/archetypes/test_tuning.py` - Faction substitutions, damage profiles
- `tests/archetypes/test_validator.py` - Alpha restrictions, schema/consistency validation
- `tests/archetypes/test_migration.py` - T2 detection, tier mapping, YAML migration

**Fixtures added to `tests/archetypes/conftest.py`:**
- `sample_eft_string`, `sample_eft_with_charges`, `sample_alpha_eft`
- `mock_pilot_skills`, `mock_empty_skills`, `mock_mission_context`
- `mock_market_prices`

#### Priority 2: Signal Providers (~600 statements) - COMPLETE

| Signal Module | Lines | Test File | Coverage | Status |
|---------------|-------|-----------|----------|--------|
| `signals/activity.py` | 64 | `test_activity.py` | **100%** | Done |
| `signals/location.py` | 112 | `test_location.py` | **99%** | Done |
| `signals/value.py` | 56 | `test_value.py` | **100%** | Done |
| `signals/ship.py` | 62 | `test_ship.py` | **93%** | Done |
| `signals/politics.py` | 123 | `test_politics.py` | **98%** | Done |
| `signals/routes.py` | 64 | `test_routes.py` | **99%** | Done |
| `signals/time.py` | 77 | `test_time.py` | **93%** | Done |
| `signals/war.py` | 55 | `test_war.py` | **100%** | Done |
| `signals/assets.py` | 36 | `test_assets.py` | **100%** | Done |
| **Total** | **649** | **9 files** | **~97%** | |

**Completed:** 2026-01-31

**Test files created in `tests/services/redisq/interest_v2/signals/`:**
- `conftest.py` - MockProcessedKill, MockGatecampStatus, signal-specific fixtures
- `test_value.py` - Sigmoid/linear/log/step scaling, ISK formatting (35 tests)
- `test_ship.py` - Ship class matching, capitals_only, prefer/exclude (35 tests)
- `test_time.py` - Time windows, overnight windows, timezone conversion (32 tests)
- `test_location.py` - GeographicSignal + SecuritySignal, distance/security callbacks (45 tests)
- `test_routes.py` - Route membership, ship filters (28 tests)
- `test_activity.py` - Gatecamp detection, spike/sustained patterns (28 tests)
- `test_politics.py` - Group matching, role weights, require_any/all, penalties (35 tests)
- `test_war.py` - War targets, hostile standings (27 tests)
- `test_assets.py` - Structure/office proximity (30 tests)

**Total tests added:** ~295

#### Priority 3: Rules Evaluator (~400 statements) - COMPLETE

| Module | Coverage | Test File to Create | Status |
|--------|----------|---------------------|--------|
| `rules/evaluator.py` | **91%** | `test_rules.py` | Done |
| `rules/templates.py` | **99%** | `test_templates.py` | Done |
| `rules/builtin.py` | **100%** | `test_builtin.py` | Done |

**Completed:** 2026-01-31

**Test files created in `tests/services/redisq/interest_v2/rules/`:**
- `test_builtin.py` - All 9 built-in rules: NpcOnly, PodOnly, CorpMemberVictim, AllianceMemberVictim, WarTargetActivity, WatchlistMatch, HighValue, GatecampDetected, StructureKill (~92 tests)

#### Priority 4: Delivery Module (~200 statements) - COMPLETE

| Module | Before | After | Test File | Status |
|--------|--------|-------|-----------|--------|
| `delivery/builtin.py` | 14% | **95%** | `test_builtin.py` | Done |
| `delivery/routing.py` | 24% | **96%** | `test_routing.py` | Done |

**Completed:** 2026-01-31

**Test files created in `tests/services/redisq/interest_v2/delivery/`:**
- `test_builtin.py` - DiscordDelivery, WebhookDelivery, LogDelivery (42 tests)
- `test_routing.py` - TierRouting, DeliveryRouter, create_default_router (25 tests)

**Total tests added:** 67

### Phase 2: Infrastructure Investment (Target: 70%)

#### Priority 3: MCP Tools Coverage - COMPLETE

| File | Before | After | Tests Added | Status |
|------|--------|-------|-------------|--------|
| `mcp/tools_activity.py` | 71% | **86%** | 17 | Done |
| `mcp/market/clients.py` | 42% | **95%** | 24 | Done |
| `mcp/sde/tools_activities.py` | 33% | **88%** | 25 | Done |
| **Total** | | | **66** | |

**Completed:** 2026-01-31

**Test files created/modified:**
- `tests/mcp/test_tools_activity.py` - Added error condition and edge case tests for universe_activity, universe_hotspots, universe_gatecamp_risk, fw_frontlines (17 new tests)
- `tests/mcp/market/__init__.py` - New test directory
- `tests/mcp/market/test_clients.py` - New file: FuzzworkAggregate parsing, URL building, HTTP mocking, rate limiting, bulk CSV (24 tests)
- `tests/mcp/test_sde_tools_activities.py` - Added tests for cache management, impl functions (_activity_skill_plan_impl, _activity_list_impl, _activity_search_impl, _activity_compare_tiers_impl), training time calculation (25 new tests)

**Coverage improvements:**
- `tools_activity.py`: Exceeded 85% target (+15 percentage points)
- `market/clients.py`: Exceeded 75% target (+53 percentage points)
- `sde/tools_activities.py`: Exceeded 70% target (+55 percentage points)

#### Priority 4: Notification Pipeline & Interest Engine - COMPLETE

| File | Before | After | Tests Added | Status |
|------|--------|-------|-------------|--------|
| `interest_v2/cli/tune.py` | 0% | **99%** | 56 | Done |
| `interest_v2/validation.py` | 44% | **98%** | 32 | Done |
| `notifications/political_entities.py` | 26% | **95%** | 33 | Done |
| **Total** | | | **121** | |

**Completed:** 2026-01-31

**Test files created:**
- `tests/services/redisq/interest_v2/cli/test_tune.py` - WeightVisualization, visualize_weights, format_weight_display, suggest_adjustments, calculate_effective_weights, compare_weights, estimate_impact, format_impact_report (56 tests)
- `tests/services/redisq/interest_v2/test_validation.py` - ValidationError, ValidationResult, validate_interest_config, weight/rule/signal/prefetch validation, format_validation_result (32 tests)
- `tests/services/redisq/notifications/test_political_entities.py` - PoliticalEntityTriggerResult properties, resolve_entity_names, _search_entity ESI mocking (33 tests)

**Coverage improvements:**
- `tune.py`: 0% → **99%** (primary coverage gain)
- `validation.py`: 44% → **98%** (+54 percentage points)
- `political_entities.py`: 26% → **95%** (+69 percentage points)

#### Priority 5: Notification Pipeline Deep Coverage - COMPLETE

| File | Before | After | Tests Added | Status |
|------|--------|-------|-------------|--------|
| `notifications/triggers.py` | 56% | **98%** | ~35 | Done |
| `notifications/config.py` | 50% | **99%** | ~25 | Done |
| `notifications/profile_evaluator.py` | 54% | **80%** | ~17 | Done |
| `notifications/worker.py` | 46% | **79%** | ~22 | Done |
| `notifications/manager.py` | 45% | **72%** | ~25 | Done |
| `notifications/formatter.py` | 67% | **92%** | ~12 | Done |
| `notifications/profiles.py` | 70% | **76%** | ~8 | Done |
| **Total** | | | **~144** | |

**Completed:** 2026-02-01

**Test files created/expanded:**
- `tests/services/redisq/notifications/conftest.py` - Shared factory fixtures (make_processed_kill, make_entity_match, make_gatecamp_status, make_war_context, make_trigger_config, make_notification_profile)
- `tests/services/redisq/notifications/test_triggers.py` (NEW) - TriggerType, TriggerResult, evaluate_triggers, _resolve_entity_name, _evaluate_political_entity_kill (~35 tests)
- `tests/services/redisq/notifications/test_config.py` (NEW) - CommentaryConfig, QuietHoursConfig, NPCFactionKillConfig, PoliticalEntityKillConfig, TopologyConfig validation (~25 tests)
- `tests/services/redisq/notifications/test_profile_evaluator.py` - Added quiet hours, topology, war context, v2 engine tests (~17 tests)
- `tests/services/redisq/notifications/test_worker.py` - Added ESI fetch, parse, rollup, rate limit, HTTP client tests (~22 tests)
- `tests/services/redisq/notifications/test_manager_profiles.py` - Added lifecycle, commentary, test_webhook, health status tests (~25 tests)
- `tests/services/redisq/notifications/test_formatter.py` - Added war engagement, NPC faction, commentary, smartbomb tests (~12 tests)
- `tests/services/redisq/notifications/test_profiles.py` - Added interest engine validation tests (~8 tests)

**Coverage improvements:**
- `triggers.py`: 56% → **98%** (+42 percentage points)
- `config.py`: 50% → **99%** (+49 percentage points)
- `profile_evaluator.py`: 54% → **80%** (+26 percentage points)
- `worker.py`: 46% → **79%** (+33 percentage points)
- `manager.py`: 45% → **72%** (+27 percentage points)
- `formatter.py`: 67% → **92%** (+25 percentage points)
- `profiles.py`: 70% → **76%** (+6 percentage points)

### Phase 2-4: Remaining Work

See Implementation Plan section below for details.

---

## Current State Analysis

### Coverage Breakdown

| Metric | Value |
|--------|-------|
| Total statements | 32,467 |
| Covered statements | ~17,850 |
| Current coverage | 54.97% |
| Current threshold | 54% |
| Tests passing | 4,095 |

### Coverage by Module Area

| Module Area | Statements | Missed | Coverage | Notes |
|-------------|-----------|--------|----------|-------|
| Navigation/routing | ~500 | ~50 | **96%** | Excellent |
| Universe graph | ~200 | 0 | **100%** | Complete |
| Interest layers | ~600 | ~50 | **95%** | Excellent |
| Archetypes | ~1,200 | ~200 | **85%** | Improved (was ~14%) |
| MCP tools | ~8,500 | ~3,100 | **63%** | Room for improvement |
| Fitting engine | ~1,300 | ~450 | **65%** | Moderate |
| Redisq services | ~7,500 | ~3,200 | **57%** | Complex async code |
| Notifications | ~5,500 | ~2,500 | **55%** | External dependencies |
| Commands | ~3,000 | ~1,200 | **60%** | CLI integration |

### Remaining Zero/Low Coverage Files

| File | Statements | Type | Testability | Priority |
|------|------------|------|-------------|----------|
| `interest_v2/cli/tune.py` | 139 | CLI | Medium | **DONE** (99%) |
| `redisq/backfill.py` | 277 | Async/DB | Low | Phase 3 |
| `redisq/poller.py` | 381 | WebSocket | Low | Phase 4 |

---

## Feasibility Analysis

### Path to 80%

To reach 80% coverage (25,974 statements), we need to cover **~8,100 more statements**.

| Phase | Target | Additional Coverage | Cumulative | Difficulty | Status |
|-------|--------|---------------------|------------|------------|--------|
| Phase 1 | 60% | +1,600 stmts | 60% | Easy | **COMPLETE** (57.42%) |
| Phase 2 | 70% | +3,200 stmts | 70% | Moderate | Not Started |
| Phase 3 | 75% | +1,600 stmts | 75% | Moderate | Not Started |
| Phase 4 | 80% | +1,600 stmts | 80% | Hard | Not Started |

### Achievability by Category

| Category | Current | Target | Achievability | Effort |
|----------|---------|--------|---------------|--------|
| Archetypes (selection, pricing, tuning, validator, migration) | **85%** | 85% | **Complete** | Done |
| MCP tools | 63% | 80% | **Achievable** | Medium |
| Command modules | 60% | 75% | **Achievable** | Medium |
| Signal providers | **~97%** | 60% | **Complete** | Done |
| Notification delivery | 20% | 50% | Achievable | Medium |
| Real-time poller | 17% | 40% | Challenging | High |
| Async workers | 45% | 60% | Achievable | Medium |

### Inherently Hard-to-Test Code

Some code is legitimately difficult to unit test:

1. **Real-time WebSocket poller** (`poller.py`) - Requires live connection mocking
2. **Discord webhook delivery** - External service dependency
3. **Interactive CLI commands** (`tune.py`) - User input loops
4. **Async coordination** (`fetch_queue.py`, `worker.py`) - Race conditions, timing

**Recommendation:** Apply `# pragma: no cover` selectively to genuinely untestable paths (not as an escape hatch for laziness).

---

## Recommendations

### Option A: Single Global Threshold (Simple)

```toml
[tool.coverage.report]
fail_under = 75
```

**Pros:** Simple, clear target
**Cons:** Doesn't account for legitimately hard-to-test code

### Option B: Tiered Thresholds (Recommended)

Use `coverage.py` contexts or a wrapper script to enforce per-directory minimums:

| Module Path | Threshold | Rationale |
|-------------|-----------|-----------|
| `core/` | 85% | Critical infrastructure |
| `mcp/` | 80% | User-facing tools |
| `universe/` | 90% | Already excellent |
| `archetypes/` | 85% | Now well-tested |
| `fitting/` | 75% | External EOS dependency |
| `commands/` | 70% | CLI integration complexity |
| `services/navigation/` | 90% | Already excellent |
| `services/redisq/interest*/` | 75% | Logic-heavy, testable |
| `services/redisq/notifications/` | 60% | External dependencies |
| `services/redisq/` (other) | 50% | Real-time code |
| **Overall** | **75%** | Balanced target |

### Option C: Exclude Hard-to-Test Modules

```toml
[tool.coverage.run]
omit = [
    # Existing omissions...
    "src/aria_esi/services/redisq/poller.py",
    "src/aria_esi/services/redisq/interest_v2/cli/tune.py",
]

[tool.coverage.report]
fail_under = 80
```

**Pros:** Achieves 80% on testable code
**Cons:** Hides real coverage picture

---

## Implementation Plan

### Phase 1: Quick Wins (50% → 60%)

**Target: +1,600 statements covered**
**Status: COMPLETE (57.42% achieved, ~620 tests added total)**

1. **Test archetypes companion modules** - COMPLETE
   - `archetypes/selection.py` - 79% coverage
   - `archetypes/pricing.py` - 91% coverage
   - `archetypes/tuning.py` - 82% coverage
   - `archetypes/validator.py` - 90% coverage
   - `archetypes/migration.py` - 85% coverage

2. **Test signal providers** (Est: +400 stmts) - COMPLETE
   - Created `tests/services/redisq/interest_v2/signals/` directory
   - Added conftest.py with MockProcessedKill and signal-specific fixtures
   - Tested all 9 signal provider modules (~295 tests, ~97% coverage)

3. **Test rules evaluator** (Est: +300 stmts) - **COMPLETE**
   - `rules/evaluator.py` - **91%**
   - `rules/templates.py` - **99%**
   - `rules/builtin.py` - **100%**

4. **Test delivery module** (Est: +200 stmts) - **COMPLETE**
   - `delivery/builtin.py` - 14% → **95%**
   - `delivery/routing.py` - 24% → **96%**

### Phase 2: Infrastructure Investment (60% → 70%)

**Target: +3,200 statements covered**
**Status: NOT STARTED**

1. **Create mock infrastructure for external services**
   - Discord webhook mock
   - ESI API response fixtures
   - Redis mock for real-time data

2. **Test 0% pure logic files** (Est: +1,000 stmts) - **MOSTLY COMPLETE**
   - `interest_v2/presets/loader.py` - **92%**
   - `interest_v2/presets/builtin.py` - **100%**
   - `interest_v2/rules/templates.py` - **99%**

3. **Increase MCP tool coverage** (Est: +400 stmts)
   - Focus on tools at 50-70% that could easily hit 80%
   - Add edge case tests for existing tools

4. **Test notification pipeline** (Est: +800 stmts)
   - Profile evaluation
   - Trigger matching
   - Formatting

### Phase 3: Deep Coverage (70% → 75%)

**Target: +1,600 statements covered**
**Status: NOT STARTED**

1. **Async test infrastructure**
   - `pytest-asyncio` patterns for workers
   - Controlled timing tests

2. **Notification manager testing** (Est: +400 stmts)
   - End-to-end flow with mocks

3. **Interest engine edge cases** (Est: +400 stmts)
   - Complex rule evaluation
   - Aggregation logic

### Phase 4: Stretch Goal (75% → 80%)

**Target: +1,600 statements covered**
**Status: NOT STARTED**

1. **Integration test expansion**
   - Multi-component flows
   - Error recovery paths

2. **Remaining notification components**
   - Worker lifecycle
   - Supervisor coordination

3. **Apply selective `pragma: no cover`**
   - Document each exclusion with rationale
   - Only for genuinely untestable paths

---

## Configuration Changes

### Current (pyproject.toml)

```toml
[tool.coverage.report]
fail_under = 54  # Raised from 50 after Phase 1 Priority 1
```

### After Phase 1 Complete

```toml
[tool.coverage.report]
fail_under = 58  # Conservative target for 60%

exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "@overload",
    # Add for async infrastructure code
    "async def main\\(",
    "asyncio.run\\(",
]
```

### Phase Milestones

| Milestone | Threshold | Timeline | Status |
|-----------|-----------|----------|--------|
| Phase 1 Priority 1 | 54% | Complete | **DONE** |
| Phase 1 Complete | 58% | Complete | **DONE** (57.42%) |
| Phase 2 Complete | 68% | After mock infrastructure | Not Started |
| Phase 3 Complete | 75% | Recommended stable target | Not Started |
| Phase 4 Complete | 80% | Stretch goal | Not Started |

---

## Metrics to Track

1. **Overall coverage %** - Primary metric
2. **0% files count** - Should reach zero
3. **<50% files count** - Should decrease each phase
4. **Test count** - Should grow proportionally
5. **Test runtime** - Monitor for bloat

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Mock complexity explodes | Medium | High | Limit mock depth, prefer fakes |
| Test suite becomes slow | Medium | Medium | Use `pytest-xdist` parallel execution |
| Coverage gaming (trivial tests) | Low | Medium | Code review for test quality |
| Real bugs in "covered" code | Medium | High | Mutation testing for critical paths |

---

## Success Criteria

1. **75% overall coverage** with CI enforcement
2. **Zero files at 0% coverage** (excluding legitimate `pragma: no cover`)
3. **No files below 50%** in core business logic
4. **<5% of statements** marked `pragma: no cover`
5. **Test suite runs in <90 seconds** with parallel execution

---

## Conclusion

**80% is achievable but aggressive.** The recommended path:

1. **Commit to 75% as the stable target** - Achievable with reasonable effort
2. **Implement tiered thresholds** - Fair to different code types
3. **Start with quick wins** - 0% files are easy points (archetypes DONE)
4. **Invest in mock infrastructure** - Enables testing external dependencies
5. **Reserve 80% as stretch goal** - After infrastructure is in place

**Phase 1 is complete** with ~620 tests added across 4 priorities:
1. Archetypes (175 tests) - 85% average coverage
2. Signal providers (295 tests) - 97% average coverage
3. Rules/builtin (92 tests) - 100% coverage
4. Delivery module (67 tests) - 95% average coverage

**Phase 2 Priority 3 is complete** with 66 tests added:
5. MCP tools (66 tests) - 90% average coverage achieved

**Phase 2 Priority 4 is complete** with 121 tests added:
6. Notification Pipeline & Interest Engine (121 tests) - 97% average coverage achieved

**Phase 2 Priority 5 is complete** with ~144 tests added:
7. Notification Pipeline Deep Coverage (144 tests) - Major coverage gains across 7 files

Overall coverage increased from 52.89% to **60.04%**, achieving the 60% target. The Phase 2 Priority 5 chunk achieved excellent coverage improvements across the notification pipeline:
- `triggers.py`: 56% → 98% (+42 points)
- `config.py`: 50% → 99% (+49 points)
- `worker.py`: 46% → 79% (+33 points)
- `manager.py`: 45% → 72% (+27 points)
- `formatter.py`: 67% → 92% (+25 points)

---

## Changelog

| Date | Change | Coverage |
|------|--------|----------|
| 2026-01-31 | Initial proposal | 52.89% |
| 2026-01-31 | Phase 1 Priority 1 complete (archetypes) | 54.97% |
| 2026-01-31 | Phase 1 Priority 2 complete (signals) | 56.68% |
| 2026-01-31 | Phase 1 Priority 3 complete (rules/builtin) | 57% |
| 2026-01-31 | Phase 1 Priority 4 complete (delivery module) | 57.42% |
| 2026-01-31 | **Phase 1 Complete** | **57.42%** |
| 2026-01-31 | Phase 2 Priority 3 complete (MCP tools) | 58.06% |
| 2026-01-31 | Phase 2 Priority 4 complete (tune, validation, political_entities) | 58.88% |
| 2026-02-01 | Phase 2 Priority 5 complete (notification pipeline deep coverage) | **60.04%** |

---

*Last Updated: 2026-02-01*
