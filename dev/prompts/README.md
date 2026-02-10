# Prompt Library v1

This directory contains the v1 prompt library for CI-driven code review. Each prompt targets a specific software lifecycle facet and is executed by the review pipeline based on file-change triggers.

## Facet-to-Prompt Mapping

### Foundation Tier

Foundation prompts run on every PR that touches core surfaces (`src/**`, `.github/workflows/**`, `pyproject.toml`, `dev/prompts/**`, `README.md`, `docs/**`, `SECURITY.md`).

| Facet | Prompt File | Rule ID |
|-------|-------------|---------|
| Review orchestration | `meta/review_orchestrator.md` | `foundation.core_surfaces.v1` |
| Scoring calibration | `meta/scoring_rubric.md` | `foundation.core_surfaces.v1` |
| System design | `architecture/system_design.md` | `foundation.core_surfaces.v1` |
| Security audit | `security/audit_ai.md` | `foundation.core_surfaces.v1` |
| Test harness | `testing/test_harness.md` | `foundation.core_surfaces.v1` |
| CI/CD pipeline | `cicd/pipeline_quality.md` | `foundation.core_surfaces.v1` |
| Onboarding/docs | `docs/onboarding_first_run_ux.md` | `foundation.core_surfaces.v1` |

### Deep-Dive Tier

Deep-dive prompts activate when specific subsystem paths are modified.

| Facet | Prompt File | Rule ID | Triggers |
|-------|-------------|---------|----------|
| MCP architecture | `architecture/mcp_architecture.md` | `deep_dive.mcp_architecture.v1` | `src/aria_esi/mcp/**`, `.mcp.json` |
| Supply chain security | `security/supply_chain_and_dependencies.md` | `deep_dive.supply_chain.v1` | `pyproject.toml`, `uv.lock`, `.github/workflows/**` |
| Coverage quality | `testing/coverage_quality.md` | `deep_dive.coverage_quality.v1` | `tests/**`, `pyproject.toml`, `.github/workflows/**` |
| Repo first impression | `repo/github_first_impression.md` | `deep_dive.github_first_impression.v1` | `.github/**`, `README.md`, `CONTRIBUTING.md`, `LICENSE`, `ATTRIBUTION.md` |

### Gate Tier

Gate prompts enforce merge/deploy policies and are event-driven rather than file-driven.

| Facet | Prompt File | Rule ID | Trigger Condition |
|-------|-------------|---------|-------------------|
| Pre-merge review | `dev/premerge.md` | `gate.premerge.v1` | `pull_request` event |
| Post-merge audit | `dev/postmerge_regression_audit.md` | `gate.postmerge_regression_audit.v1` | `push` event with `postmerge_applicable=true` |
| Proposal readiness | `dev/proposal_implementation_readiness.md` | `gate.proposal_implementation_readiness.v1` | PR with proposal files, or manual `workflow_dispatch` |

### Deferred Prompts

These prompts are defined in the config but not yet active. When their triggers match, the pipeline falls back to the global fallback set.

| Facet | Prompt File | Rule ID | Triggers |
|-------|-------------|---------|----------|
| Data flow boundaries | `architecture/data_flow_and_boundaries.md` | `deep_dive.data_flow_and_boundaries.v1` | `src/aria_esi/services/**`, `src/aria_esi/core/**`, `src/aria_esi/persona/**` |
| Non-determinism/flakes | `testing/non_determinism_and_flakes.md` | `deep_dive.non_determinism_and_flakes.v1` | `tests/**`, `.github/workflows/**` |

## Overlap and Boundary Matrix

Some prompts share adjacent concerns. The `adjacent_prompts` metadata header in each file documents these relationships. Key overlaps:

- **architecture/system_design.md** <-> **architecture/mcp_architecture.md**: System boundaries vs. MCP-specific contracts
- **security/audit_ai.md** <-> **security/supply_chain_and_dependencies.md**: Application security vs. dependency risk
- **testing/test_harness.md** <-> **testing/coverage_quality.md**: Test infrastructure vs. coverage adequacy
- **cicd/pipeline_quality.md** <-> **cicd/release_and_rollback.md**: Pipeline reliability vs. release safety
- **dev/premerge.md** <-> **dev/postmerge_regression_audit.md**: Pre-merge gates vs. post-merge verification

## Fallback Behavior

When no deep-dive rule matches (or only deferred rules match), the pipeline selects a fallback prompt set:

- `meta/review_orchestrator.md`
- `security/audit_ai.md`
- `testing/test_harness.md`
- `dev/premerge.md` (pull_request only)

## Configuration

Trigger rules are defined in `dev/policy/prompt_matcher_rules.yaml`. Metadata validation is enforced by the `metadata-check` CI job. All v1 prompts require `owner`, `last_reviewed`, `depends_on`, and `adjacent_prompts` metadata headers.
