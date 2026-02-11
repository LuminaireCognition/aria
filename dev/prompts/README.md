# Review Prompt Library

Standalone review prompts for evaluating code quality across software lifecycle facets. Each prompt is designed to be given to an AI agent with full codebase access.

## How to Use

1. Pick a prompt from the catalog below based on what you want to review.
2. Give the prompt file to an AI coding agent (Claude Code, Codex, etc.) with access to the repository.
3. The agent will produce a structured report with findings ranked by severity.

For prompts marked with `<PROPOSAL_PATH>`, replace the placeholder with the path to your proposal file.

## Prompt Catalog

### Architecture

| Prompt | Reviews | When to Use |
|--------|---------|-------------|
| [`system_design.md`](architecture/system_design.md) | Module boundaries, dependency direction, layering, interfaces | Structural changes to packages under `src/` |
| [`mcp_architecture.md`](architecture/mcp_architecture.md) | MCP dispatcher contracts, tool schemas, transport handling | Changes to MCP server code or `.mcp.json` |
| [`python.md`](architecture/python.md) | Python code quality, types, async, error handling, tooling | Major refactors or code quality sweeps |
| [`llm_integration.md`](architecture/llm_integration.md) | LLM integration patterns, prompting, tool use, Skills extension | Changes to LLM call sites or tool orchestration |
| [`context_management.md`](architecture/context_management.md) | Context lifecycle, token budgeting, state management | Changes to context assembly or routing |
| [`accretion_auditor.md`](architecture/accretion_auditor.md) | High-complexity/low-utility accretions, bloat reduction, simplification cuts | When the codebase feels bloated and you need a remove-or-simplify plan |

### Security

| Prompt | Reviews | When to Use |
|--------|---------|-------------|
| [`audit_ai.md`](security/audit_ai.md) | Prompt injection, agent misuse, MCP trust boundaries, secrets | Security posture review of LLM/tool code |
| [`supply_chain_and_dependencies.md`](security/supply_chain_and_dependencies.md) | Dependencies, lockfile integrity, licensing, supply chain risk | Changes to `pyproject.toml`, `uv.lock`, or Actions |

### Testing

| Prompt | Reviews | When to Use |
|--------|---------|-------------|
| [`test_harness.md`](testing/test_harness.md) | Test infrastructure, fixtures, mocking, determinism, coverage tooling | Changes to test harness or fixture patterns |
| [`coverage_quality.md`](testing/coverage_quality.md) | Coverage adequacy, gap analysis, coverage enforcement | Changes to `tests/` or coverage configuration |

### CI/CD

| Prompt | Reviews | When to Use |
|--------|---------|-------------|
| [`pipeline_quality.md`](cicd/pipeline_quality.md) | Workflow reliability, job dependencies, secrets, failure modes | GitHub Actions workflow changes |
| [`release_and_rollback.md`](cicd/release_and_rollback.md) | Release process, versioning, rollback safety, migrations | Release workflow or versioning changes |

### Docs

| Prompt | Reviews | When to Use |
|--------|---------|-------------|
| [`onboarding_first_run_ux.md`](docs/onboarding_first_run_ux.md) | Documentation quality, onboarding flow, first-run UX | README, setup instructions, or `docs/` changes |

### UX

| Prompt | Reviews | When to Use |
|--------|---------|-------------|
| [`ux_analysis.md`](ux/ux_analysis.md) | Product interaction UX, CLI flow quality, output clarity, and trust signals | User-facing command flow, output formatting, or error/interaction changes |

### Repo

| Prompt | Reviews | When to Use |
|--------|---------|-------------|
| [`github_first_impression.md`](repo/github_first_impression.md) | Repository presentation, community health files, contributor readiness | Changes to `.github/`, README, LICENSE, CONTRIBUTING |

### Dev Workflow

| Prompt | Reviews | When to Use |
|--------|---------|-------------|
| [`premerge.md`](dev/premerge.md) | Proposal compliance, production standards, merge readiness | Final review before merging to `main` |
| [`postmerge_regression_audit.md`](dev/postmerge_regression_audit.md) | Regression detection, merge artifacts, test suite health | After merging a feature branch |
| [`proposal_implementation_readiness.md`](dev/proposal_implementation_readiness.md) | Proposal specificity, ambiguity detection, implementation blockers | Reviewing a proposal before implementation |

## Reference

| File | Purpose |
|------|---------|
| [`meta/scoring_rubric.md`](meta/scoring_rubric.md) | Shared severity and confidence level definitions (not a runnable review) |

## Planned Prompts

These prompts are planned but not yet written:

- `architecture/data_flow_and_boundaries.md` — Data flow across service boundaries, provenance, and integrity
- `testing/non_determinism_and_flakes.md` — Test flakiness detection, non-determinism sources, and remediation

## Related Prompts Matrix

Some prompts cover adjacent concerns. When reviewing a specific area, consider running related prompts together:

| If you run... | Also consider... | Why |
|---------------|------------------|-----|
| `system_design.md` | `mcp_architecture.md` | System boundaries vs MCP-specific contracts |
| `audit_ai.md` | `supply_chain_and_dependencies.md` | Application security vs dependency risk |
| `test_harness.md` | `coverage_quality.md` | Test infrastructure vs coverage adequacy |
| `pipeline_quality.md` | `release_and_rollback.md` | Pipeline reliability vs release safety |
| `premerge.md` | `postmerge_regression_audit.md` | Pre-merge gates vs post-merge verification |
| `onboarding_first_run_ux.md` | `github_first_impression.md` | Documentation depth vs repository presentation |
| `ux_analysis.md` | `onboarding_first_run_ux.md` | Product interaction UX vs documentation UX |
| `accretion_auditor.md` | `system_design.md` | Simplification/deletion priorities vs architecture boundaries |
