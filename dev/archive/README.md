# Development Archive

Implemented and superseded design documents preserved for historical reference.

## Purpose

This archive contains proposals and design documents that have been:
- **Implemented** - The feature was built and merged
- **Superseded** - A newer proposal replaced this approach
- **Deprecated** - The direction was abandoned with lessons learned

These documents are kept for:
- Understanding why certain design decisions were made
- Avoiding re-litigating settled questions
- Onboarding contributors to project history

## Contents

| Document | Status | What It Became |
|----------|--------|----------------|
| BUILD_COST_IMPROVEMENTS_PROPOSAL.md | Implemented | Fixed `/build-cost` material extraction |
| CONTEXT_AWARE_TOPOLOGY_PROPOSAL.md | Implemented | Multi-layer interest calculation, `docs/CONTEXT_AWARE_TOPOLOGY.md` |
| DIRECTORY_STRUCTURE_REFACTOR.md | Implemented | Current `userdata/` layout |
| LOCAL_INTEL_ORIENT_PROPOSAL.md | Implemented | `/orient` skill, `local_area` MCP action |
| MARKET_MCP_PROPOSAL.md | Implemented | `market()` MCP dispatcher |
| NOTIFICATION_FILTER_REARCHITECTURE_PROPOSAL.md | Implemented | Notification profiles system, `docs/NOTIFICATION_PROFILES.md` |
| PERSONA_HIERARCHY_PROPOSAL.md | Implemented | Current persona system |
| PERSONA_CLEANUP_PROPOSAL.md | Implemented | Streamlined persona loading |
| PERSONA_SKILL_SEPARATION.md | Implemented | Skill overlays system |
| PARIA_PERSONA.md | Implemented | `personas/paria/` |
| PROJECT_PARIA.md | Implemented | Pirate faction support |
| PERSONAS.md | Superseded | Early persona concepts |
| PROXIMITY_MARKET_SEARCH_PROPOSAL.md | Implemented | `market(action="find_nearby")` |
| ROLEPLAY_CONFIG.md | Implemented | `rp_level` in profiles |
| SDE_DATA_ACCESS_REFACTOR.md | Implemented | `sde()` MCP dispatcher |
| SPLIT_PROPOSAL.md | Superseded | Early modularization ideas |
| token_analysis.json | Reference | Context token budget analysis |

## Archive Policy

Documents are moved here when:
1. The proposal is fully implemented, or
2. A newer proposal supersedes it, or
3. The approach was tried and abandoned

Active proposals remain in `dev/proposals/`.
