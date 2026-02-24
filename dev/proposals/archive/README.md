# Archived Proposals

Proposals that have been implemented, superseded, or consolidated.

## Contents

| Proposal | Status | Date | Notes |
|----------|--------|------|-------|
| SITE_COMPOSITION_DATA_PROPOSAL.md | Implemented | - | PvE site data structure |
| SKILL_PLANNER_PROPOSAL.md | Implemented | - | `skills()` MCP dispatcher |
| REDISQ_REALTIME_INTEL_PROPOSAL.md | Implemented | 2026-02 | Phases 1-5 complete, real-time intel working |
| POLITICAL_ENTITY_TRIGGERS_PROPOSAL.md | Implemented | 2026-02 | Part of notification system |
| NPC_FACTION_KILL_NOTIFICATIONS.md | Implemented | 2026-02 | Part of notification system |
| PERSONA_DRIVEN_DISCORD_NOTIFICATIONS.md | Implemented | 2026-02 | Part of notification system |
| EmulatingRadioVoiceinTextLLMs.md | Reference | 2026-02 | Research document, not actionable proposal |
| FORGE_PERSONA_PROPOSAL.md | Consolidated | 2026-02 | Merged into PERSONA_VARIANTS_PROPOSAL.md |
| PARIA_S_SERPENTIS_PROPOSAL.md | Consolidated | 2026-02 | Merged into PERSONA_VARIANTS_PROPOSAL.md |
| PARIA_G_GURISTAS_PROPOSAL.md | Consolidated | 2026-02 | Merged into PERSONA_VARIANTS_PROPOSAL.md |
| INSTANCE_LOCAL_DATA_PATHS_PROPOSAL.md | Implemented | 2026-02-02 | ARIA_INSTANCE_ROOT + all defaults instance-local |
| FITTING_VALIDATION_PROPOSAL.md | Implemented | 2026-02-02 | EOS integration, SKILL.md protocol, reference docs |
| LLM_INTEGRATION_IMPROVEMENTS_000.md | Implemented | 2026-02-02 | P0/P1 complete: context-aware policy, byte limits, tracing |
| PI_HELPER_PROPOSAL.md | Implemented | 2026-02-02 | All 4 phases: chains, math, market, location-aware |
| ASSET_AUDIT_PROPOSAL.md | Implemented | 2026-02-02 | All 4 phases: queries, categorization, snapshots, insights |
| SKILL_TEST_HARNESS_PROPOSAL.md | Implemented | 2026-02-02 | All 3 layers: contract, structural, semantic evals |
| EXPAND_SDE_INJEST.md | Implemented | 2026-02-02 | Meta types SDE import for T2/Faction variant lookups |
| SKILL_AWARE_FIT_SELECTION.md | Implemented | 2026-02-02 | Stats caching CLI, omega/T2 validation, tier system |
| PROMPT_LIBRARY_REVIEW_COVERAGE_PROPOSAL.md | Superseded | 2026-02-10 | CI automation not adopted; standalone prompts retained in `dev/prompts/` |
| FRESHNESS_GATED_AUTO_SYNC_LIBRARY.md | Implemented | 2026-02-13 | All 4 phases: core library, enhanced markers, consolidation, skill integration |
| MINMAX_SKILL_PLANNING_PROPOSAL.md | Implemented | 2026-02-15 | Phases A-C: core algorithm, dispatcher, SKILL.md, hauler role |
| MULTI_LLM_SERVICE_FOR_NOTIFICATIONS.md | Implemented | 2026-02-16 | Provider abstraction (Anthropic/OpenAI/Gemini), per-profile config |
| INIT_INFORMATION_SPACE_CLEANUP.md | Implemented | 2026-02-22 | Phase 1: duplicate files, persona context stubs, dead templates |
| SKILL_ROUND2_REMAINING_ISSUES.md | Implemented | 2026-02-24 | Doc-only fixes: watchlist name resolution, stub termination guards |
| LINUX_VM_DOCKER_RUNTIME_PROPOSAL.md | Complete | 2026-02-24 | `aria-init` already uses correct paths and `uv run python`; proposal outdated |
| ship-hull-value-signal.md | Implemented | 2026-02-24 | Notification filtering by hull price |

## Archive Policy

Proposals are moved here when:
1. The feature is fully implemented
2. Consolidated into a larger proposal
3. Superseded by a different approach
4. Research/reference documents (not actionable)

For older archived documents (pre-proposal era), see `dev/archive/`.
