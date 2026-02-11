# Prompt Library Review Coverage Proposal

> **Superseded.** The CI pipeline described in this proposal (matcher, aggregator, orchestrator, waivers, 8-job workflow) was not merged. The prompt library itself was retained as standalone review prompts usable by any AI agent. See [`dev/prompts/README.md`](../prompts/README.md) for the current prompt catalog.

**Status:** SUPERSEDED (2026-02-10)
**Original Status:** PROPOSED (2026-02-09)
**Owner:** DevEx / Quality Engineering
**Scope:** `dev/prompts/` and prompt library governance

## Executive Summary

This proposal defines a complete prompt library for project-quality analysis across software lifecycle facets. The current library has strong depth in architecture/security/testing but does not fully cover documentation UX, CI/CD maturity, release governance, MCP contract integrity, supply chain/licensing, runtime operations, and GitHub-first impressions.

Goal: establish a finite, enforceable prompt library baseline that can be completed and maintained without expanding into an open-ended sub-project.

Implementation note for this proposal: only the v1 baseline in this file is authorized for creation now. All other prompt paths remain design references and are explicitly marked "do not create yet" until a post-v1 amendment is approved.

## Current Prompt Inventory (as-is)

Inventory entries in this section are physical repository file paths. Canonical runtime `prompt_path` semantics are defined in `## Canonical Prompt Path Namespace (required)`.

- `dev/prompts/architecture/llm_integration.md`
- `dev/prompts/architecture/context_management.md`
- `dev/prompts/architecture/python.md`
- `dev/prompts/security/audit_ai.md`
- `dev/prompts/testing/test_harness.md`
- `dev/prompts/dev/premerge.md`
- `dev/prompts/dev/proposal_implementation_readiness.md`

## Canonical Prompt Path Namespace (required)

All `prompt_path` values in matcher/runtime/parser artifacts and registries are **prompt-library-relative** paths rooted under `dev/prompts/` (for example `dev/premerge.md`).

Normative mapping and normalization:

1. `prompt_path` MUST NOT start with `dev/prompts/`.
2. Runtime resolves prompt files with exactly one prefix operation: `repo_prompt_file = "dev/prompts/" + prompt_path`.
3. Matcher trigger paths remain repo-relative and are never rewritten into prompt-library-relative namespace.
4. Any explicit path input (`PROPOSAL_PATH`) is normalized before validation:
   - convert `\` to `/`,
   - remove leading `./`,
   - reject traversal (`..`) after normalization,
   - reject if resolved path escapes repository root (including symlink escape).
5. Canonical example: `prompt_path=dev/premerge.md` maps to repo file `dev/prompts/dev/premerge.md`.

This namespace is authoritative for prompt creation, matcher selection records, registry keys, output schema fields, parser checks, and test assertions.

## Independently Reviewable Facets

1. System architecture and boundaries
2. LLM integration quality (prompting, tool routing, context)
3. MCP architecture, contracts, and dispatcher behavior
4. Python code quality and maintainability
5. Security posture (prompt injection, auth, path safety, secrets)
6. Data governance and integrity (sources, verification, provenance)
7. Test strategy, determinism, and coverage adequacy
8. CI/CD pipeline quality and failure containment
9. Release readiness and rollback safety
10. Operations and observability readiness
11. Performance, latency, and cost controls
12. Dependency and supply-chain hygiene
13. Documentation quality and information architecture
14. New-user onboarding and GitHub first impression
15. Developer workflow (branching, PR process, review gates)
16. Configuration/environment portability (Linux/macOS/WSL/container)
17. UX quality of CLI outputs and interaction flows
18. Compliance/licensing and attribution correctness

## Coverage Gaps (Current -> Needed)

### Already strong

- Architecture: broad (`architecture/*`)
- LLM context handling: strong (`architecture/context_management.md`)
- Security (AI-centric): strong (`security/audit_ai.md`)
- Test harness quality: strong (`testing/test_harness.md`)
- Proposal and premerge review gates: available (`dev/*`)

### Partial or missing

- MCP-specific contract review prompt is missing (currently spread across other prompts)
- CI/CD reliability and workflow policy review prompt is missing
- Release engineering prompt is missing
- Ops/observability prompt is missing (only `ops/README.md` exists)
- Docs IA + first-run UX review prompt is missing
- GitHub repository first-impression review prompt is missing
- Dependency/supply-chain/licensing review prompt is missing
- Product/interaction UX review prompt is missing
- Data governance prompt is not isolated from security/architecture prompts

## Out of Scope / Non-Goals (v1)

This proposal does **not** include the following in v1:

1. Building an automated remediation engine that patches code from findings.
2. Replacing current CI providers, branching model, or repository governance tooling.
3. Rewriting existing prompt content for style-only improvements when coverage already exists.
4. Adding prompt categories unrelated to software quality review (feature ideation, product strategy, marketing copy).
5. Continuous expansion of prompt count without change control; v1 is a bounded baseline.

## Proposed `dev/prompts/` Hierarchy (Reference Only, Not v1 Build Scope)

```text
dev/prompts/
  README.md
  meta/
    review_orchestrator.md
    scoring_rubric.md
    evidence_collection.md
  architecture/
    system_design.md
    llm_integration.md                (existing)
    context_management.md             (existing)
    python.md                         (existing)
    mcp_architecture.md               (new)
    data_flow_and_boundaries.md       (new)
  security/
    audit_ai.md                       (existing)
    appsec_and_secrets.md             (new)
    supply_chain_and_dependencies.md  (new)
    privacy_and_data_handling.md      (new)
  testing/
    test_harness.md                   (existing)
    coverage_quality.md               (new)
    integration_contracts.md          (new)
    non_determinism_and_flakes.md     (new)
  ops/
    observability_and_runbooks.md     (new)
    incident_readiness.md             (new)
    performance_latency_cost.md        (new)
    configuration_portability.md      (new)
  cicd/
    pipeline_quality.md               (new)
    release_and_rollback.md           (new)
    quality_gates_and_policy.md       (new)
  docs/
    docs_information_architecture.md  (new)
    onboarding_first_run_ux.md        (new)
    api_cli_docs_alignment.md         (new)
  repo/
    github_first_impression.md        (new)
    contributor_workflow.md           (new)
    licensing_and_attribution.md      (new)
  ux/
    cli_interaction_quality.md        (new)
    output_clarity_and_trust.md       (new)
  dev/
    premerge.md                       (existing)
    proposal_implementation_readiness.md (existing)
    postmerge_regression_audit.md     (new)
```

Policy: the hierarchy above is a target-state map only. During v1, create only files listed under "Required for v1 (minimum deliverable)". Every other new file in this tree is deferred and must not be created yet.

## Prompt Set Needed for Full Coverage

### Foundation prompts (run for every substantial change)

1. `meta/review_orchestrator.md`
2. `meta/scoring_rubric.md`
3. `architecture/system_design.md`
4. `security/audit_ai.md` (existing)
5. `testing/test_harness.md` (existing)
6. `cicd/pipeline_quality.md`
7. `docs/onboarding_first_run_ux.md`

### Required for v1 (minimum deliverable)

The following prompt set defines the **bounded v1 baseline**. Completing these constitutes v1 completion:

1. `meta/review_orchestrator.md`
2. `meta/scoring_rubric.md`
3. `architecture/system_design.md`
4. `architecture/mcp_architecture.md`
5. `security/audit_ai.md` (existing)
6. `security/supply_chain_and_dependencies.md`
7. `testing/test_harness.md` (existing)
8. `testing/coverage_quality.md`
9. `cicd/pipeline_quality.md`
10. `cicd/release_and_rollback.md`
11. `docs/onboarding_first_run_ux.md`
12. `repo/github_first_impression.md`
13. `dev/premerge.md` (existing)
14. `dev/postmerge_regression_audit.md`

### Deferred (post-v1)

All prompts not listed in the v1 baseline above are deferred to post-v1 phases.

### Deep-dive prompts (run when affected)

1. `architecture/mcp_architecture.md`
2. `architecture/data_flow_and_boundaries.md`
3. `security/appsec_and_secrets.md`
4. `security/supply_chain_and_dependencies.md`
5. `security/privacy_and_data_handling.md`
6. `testing/coverage_quality.md`
7. `testing/integration_contracts.md`
8. `testing/non_determinism_and_flakes.md`
9. `ops/observability_and_runbooks.md`
10. `ops/incident_readiness.md`
11. `ops/performance_latency_cost.md`
12. `ops/configuration_portability.md`
13. `cicd/release_and_rollback.md`
14. `cicd/quality_gates_and_policy.md`
15. `docs/docs_information_architecture.md`
16. `docs/api_cli_docs_alignment.md`
17. `repo/github_first_impression.md`
18. `repo/contributor_workflow.md`
19. `repo/licensing_and_attribution.md`
20. `ux/cli_interaction_quality.md`
21. `ux/output_clarity_and_trust.md`

### Gate prompts

1. `dev/proposal_implementation_readiness.md` (existing)
2. `dev/premerge.md` (existing)
3. `dev/postmerge_regression_audit.md`

## Execution Triggers

### Foundation prompt triggers

Run all foundation prompts when any of these paths change:

- `src/**`
- `.github/workflows/**`
- `pyproject.toml`
- `dev/prompts/**`
- `README.md`
- `docs/**`
- `SECURITY.md`

`meta/scoring_rubric.md` is executable in v1 (not reference-only) and, when selected under foundation rules, MUST emit `selection_reason=foundation_trigger`.

`meta/review_orchestrator.md` is executable in v1 with deferred execution phase. When selected under foundation rules, it MUST emit `selection_reason=foundation_trigger` and execute after all other prompt tiers have produced results. See `### Orchestrator Behavioral Contract`.

### Deep-dive prompt triggers (path-based)

Run deep-dive prompts only when their surfaces change:

1. `architecture/mcp_architecture.md`:
   - `src/aria_esi/mcp/**`, `.mcp.json`
2. `architecture/data_flow_and_boundaries.md`:
   - `src/aria_esi/services/**`, `src/aria_esi/core/**`, `src/aria_esi/persona/**`
3. `security/appsec_and_secrets.md`:
   - `src/aria_esi/core/auth.py`, `src/aria_esi/core/keyring_backend.py`, `.env.example`, `SECURITY.md`
4. `security/supply_chain_and_dependencies.md`:
   - `pyproject.toml`, `uv.lock`, `.github/workflows/**`
5. `security/privacy_and_data_handling.md`:
   - `src/aria_esi/persona/**`, `src/aria_esi/services/**`, `docs/DATA_*`
6. `testing/coverage_quality.md`, `testing/non_determinism_and_flakes.md`:
   - `tests/**`, `pyproject.toml`, `.github/workflows/**`
7. `testing/integration_contracts.md`:
   - `src/aria_esi/mcp/**`, `tests/mcp/**`, `tests/integration/**`
8. `ops/*`:
   - `src/aria_esi/services/**`, `docs/DEPLOYMENT.md`, `.github/workflows/**`
9. `docs/*`:
   - `README.md`, `docs/**`, `CONTRIBUTING.md`
10. `repo/*`:
   - `.github/**`, `README.md`, `CONTRIBUTING.md`, `LICENSE`, `ATTRIBUTION.md`
11. `ux/*`:
   - `src/aria_esi/commands/**`, `src/aria_esi/persona/**`, `README.md`, `docs/FAQ.md`

### Deferred prompt handling (mandatory v1 behavior)

v1 allows trigger matching against deferred prompt paths, but execution is constrained to the v1 set.

1. If a changed path selects a deep-dive prompt that is deferred (not in the 14-prompt v1 set), runtime must not execute the deferred prompt.
2. Every deferred match must map to `deferred_fallback` and run the v1 fallback set using the event-specific composition defined in `### Fallback trigger rule (required safety net)`.
3. CI must record `skipped_deferred` entries in the machine-readable output artifact with selected path evidence.
4. Deferred matches do not fail a check by themselves; failure is based on fallback prompt results and gate policy.
5. This behavior is required until a proposal amendment promotes the deferred prompt into the active set.

### Fallback trigger rule (required safety net)

If a change set modifies files but matches no deep-dive rule above, runtime must execute a minimal safety fallback set using event-specific composition:

1. For `pull_request` events, run:
   - `meta/review_orchestrator.md`
   - `security/audit_ai.md`
   - `testing/test_harness.md`
   - `dev/premerge.md`
2. For `push`, `workflow_dispatch`, and `schedule` events, run:
   - `meta/review_orchestrator.md`
   - `security/audit_ai.md`
   - `testing/test_harness.md`
   - Exception for `workflow_dispatch` and `schedule` when matcher is `not_applicable` due to missing SHAs: fallback is suppressed and only explicitly requested gate prompts may run (see `### Changed-file matcher contract`).
3. If a prompt selected by fallback is not applicable to the current event, emit a prompt result entry with:
   - `status=skipped_not_applicable`
   - `tier=fallback`
   - `selection_reason=global_fallback` (or `deferred_fallback` when selected by deferred matching)

Rationale: prevents silent coverage gaps as repository surfaces evolve.

## Enforcement Model (CI and Merge Blocking)

### CI jobs (required)

1. `prompt-foundation-check`:
   - Runs foundation prompts for any PR with changes in foundation trigger paths.
2. `prompt-deep-dive-check`:
   - Uses changed-file matching to select deep-dive prompts.
   - Applies fallback trigger rule when no deep-dive match is found.
3. `prompt-gate-check`:
   - Runs gate prompts (`dev/proposal_implementation_readiness.md`, `dev/premerge.md`, `dev/postmerge_regression_audit.md` when applicable).
4. `prompt-orchestrator-check`:
   - Runs `meta/review_orchestrator.md` after `prompt-foundation-check`, `prompt-deep-dive-check`, and `prompt-gate-check` complete.
   - Input: per-job result artifacts from jobs 1-3 and matcher output.
   - Output: `artifacts/prompt-results/prompt-orchestrator-check.json`, included in `combined.json` assembly.
5. `prompt-aggregate-parse`:
   - Consumes only `artifacts/prompt-results/combined.json` and computes aggregate severity/runtime gate outcomes.
6. `prompt-waiver-check`:
   - Validates unresolved `High` waivers against `dev/policy/prompt_waivers.yaml` and `.github/CODEOWNERS`.
7. `prompt-metadata-check`:
   - Validates required prompt headers (`owner`, `last_reviewed`, `depends_on`, `adjacent_prompts`) on all v1 prompts.
   - Required status check behavior follows "## Prompt Ownership and Maintenance SLA (v1)" cutover dates.
8. Always-on status behavior:
   - All prompt-review jobs above always report a terminal status on PR and default-branch push events.
   - Non-applicable scenarios emit `skipped_not_applicable` prompt entries and job status remains success unless gate policy fails.
9. Applicability matrix (required, deterministic):
   - `prompt-foundation-check`:
     - `pull_request`: run when foundation trigger paths changed; otherwise terminal success with empty selection.
     - `push`: run with normal matcher semantics.
     - `workflow_dispatch|schedule` with SHAs: run normal matcher semantics.
     - `workflow_dispatch|schedule` missing SHAs: do not execute prompt logic; emit required synthetic `skipped_not_applicable` entries.
   - `prompt-deep-dive-check`:
     - `pull_request|push`: run matcher, deep-dive selection, and fallback rules.
     - `workflow_dispatch|schedule` with SHAs: same as `pull_request|push`.
     - `workflow_dispatch|schedule` missing SHAs: do not execute prompt logic; emit required synthetic `skipped_not_applicable` entries.
   - `prompt-gate-check`:
     - all events: evaluate gate applicability rules and emit deterministic executed/skipped entries.
   - `prompt-orchestrator-check`:
     - `pull_request|push`: run after jobs 1-3 complete; input is their result artifacts plus matcher output.
     - `workflow_dispatch|schedule` with SHAs: same as `pull_request|push`.
     - `workflow_dispatch|schedule` missing SHAs: emit `skipped_not_applicable` with `not_applicable_reason=missing_shas`.
   - `prompt-aggregate-parse`:
     - all events: required; must consume `artifacts/prompt-results/combined.json`; missing required inputs fail closed.
   - `prompt-waiver-check`:
     - events with unresolved `High` findings: required validation.
     - events without unresolved `High`: terminal success after no-op validation pass.
   - `prompt-metadata-check`:
     - `pull_request|push|workflow_dispatch|schedule`: always emits terminal status and applies cutover behavior.

### Gate prompt applicability and input binding (required)

Gate prompt execution must be deterministic and fully derived from changed files and event context.

1. `dev/premerge.md`:
   - Applicable on `pull_request` events.
   - Always runs for PRs (never path-filter skipped).
   - If selected outside `pull_request`, emit `skipped_not_applicable` and do not execute prompt logic.
2. `dev/proposal_implementation_readiness.md`:
   - Applicable only on `pull_request` events when changed files include at least one path matching `dev/proposals/**/*.md` outside `dev/proposals/archive/**`.
   - If exactly one eligible proposal path is changed, set `PROPOSAL_PATH` to that file path.
   - If multiple eligible proposal paths are changed, execute once per file and emit one prompt result entry per `PROPOSAL_PATH`.
   - If zero eligible proposal paths are changed, emit `skipped_not_applicable`.
3. `dev/postmerge_regression_audit.md`:
   - Applicable only by the post-merge policy defined in `### Post-merge applicability rule`.
4. `workflow_dispatch` and `schedule`:
   - `dev/proposal_implementation_readiness.md` runs only when an explicit `PROPOSAL_PATH` input is provided and path validation succeeds.
   - Without explicit `PROPOSAL_PATH`, emit `skipped_not_applicable`.
   - Explicit gate-input envelope is restricted as follows:
     - `dev/proposal_implementation_readiness.md`: `PROPOSAL_PATH` only.
     - `dev/premerge.md`: no explicit inputs accepted (non-`pull_request` always `skipped_not_applicable`).
     - `dev/postmerge_regression_audit.md`: `POSTMERGE_TARGET_SHA` required when explicitly requested; optional `POSTMERGE_PR_NUMBER` for linkage validation.
   - Unknown or disallowed explicit gate input keys must emit `skipped_not_applicable` with reason `invalid_gate_input`.
   - Validation algorithm for `PROPOSAL_PATH`:
     - input separators are first normalized to POSIX `/` (Windows `\` is accepted then normalized);
     - must be a repo-relative path after normalization;
     - must match `dev/proposals/**/*.md`;
     - must not match `dev/proposals/archive/**`;
     - must not contain traversal segments (`..`) after normalization;
     - path resolution must remain inside repository root (symlink escape is invalid);
     - invalid input must emit `skipped_not_applicable` with reason `invalid_proposal_path`.
   - Multi-file fan-out with mixed validity:
     - evaluate each proposal instance independently;
     - valid normalized proposal paths execute normally;
     - invalid normalized proposal paths emit `skipped_not_applicable` with reason `invalid_proposal_path`;
     - invalid instances MUST NOT cancel valid instances.

### Post-merge applicability rule (`dev/postmerge_regression_audit.md`)

`dev/postmerge_regression_audit.md` is applicable only when all conditions below are true:

1. Event type is `push` to the repository default branch, and the pushed commit is attributable to a merged PR (merge, squash, or rebase) using GitHub PR linkage metadata.
   - Primary source: GitHub pull-request linkage for commit SHA (`GET /repos/{owner}/{repo}/commits/{sha}/pulls`).
   - Fallback: if linkage is unavailable but commit message contains `(#<pr_number>)`, resolve that PR and verify merged status; otherwise emit deterministic `skipped_not_applicable` with reason `missing_pr_linkage`.
2. The merged PR changed at least one file under:
   - `src/**`
   - `tests/**`
   - `.github/workflows/**`
   - `dev/prompts/**`
   - `docs/**`
   - `pyproject.toml`
   - `SECURITY.md`
3. Execution timing is the first eligible `push` workflow run after merge, enforced by a required commit-status context named `prompt-postmerge-first-run` on the canonical post-merge status target SHA:
   - Canonical status target SHA is merge-strategy-specific and normative for authoritative-run election and required-check wiring:
     - merge commit strategy: merge commit SHA;
     - squash strategy: squash commit SHA on default branch;
     - rebase strategy: newest rebased commit SHA on default branch linked to the merged PR.
   - A run is eligible when conditions 1 and 2 are satisfied.
   - The first eligible run that starts for that merge commit is authoritative.
   - Authoritative run election is deterministic:
     - primary key: earliest `run_started_at` timestamp;
     - tie-breaker: lowest GitHub Actions `run_id`.
   - Non-authoritative eligible runs must emit `skipped_not_applicable` with reason `non_authoritative_run` for `dev/postmerge_regression_audit.md`.
   - `skipped` means the authoritative run does not emit a terminal parser outcome (`pass` or `fail`) for `prompt-postmerge-first-run` (for example: job skipped, job cancelled, infrastructure failure, or missing required artifact).
   - Fail-closed rule: while the authoritative run is `skipped`, required checks remain failing for that merge commit until a rerun publishes a terminal `pass` or `fail` outcome for the same status context.
4. Recovery path:
   - Manual rerun is allowed via `workflow_dispatch` targeting the same merge commit SHA.
   - If the authoritative first run is non-terminal (`skipped`), the first recovery rerun that publishes terminal `pass` or `fail` for `prompt-postmerge-first-run` satisfies the required context.

### Output schema and parser contract (required)

All prompt jobs must emit JSON artifacts conforming to one schema.

1. Schema id/version: `prompt_results.schema.v1`.
2. Artifact paths:
   - Per job: `artifacts/prompt-results/<job-name>.json`
   - Combined (for merge gate parser): `artifacts/prompt-results/combined.json`
3. Required top-level fields:
   - `schema_version`: enum `["v1"]`
   - `run_context`: object with `event` (enum: `pull_request|push|workflow_dispatch|schedule`), `base_sha`, `head_sha`, `ref`, `pr_number` (int or null), `generated_at_utc` (RFC3339 UTC)
   - `matcher`: object with required fields:
     - `changed_files` (array),
     - `case_sensitive` (bool),
     - `rename_mode` (enum: `old_and_new`),
     - `delete_mode` (enum: `include_deleted_path`),
     - `mode` (enum: `normal|before_missing_fallback|not_applicable|fail_closed`),
     - `error_code` (enum or null; currently `missing_or_unfetchable_shas|null`),
     - `unmatched_files` (array),
     - `matched_rules` (array of canonical matcher `rule_id` values),
     - `before_missing_fallback` (enum or null; `all_files_changed` when used).
   - `prompts`: array of prompt result objects
   - `summary`: object with required fields:
     - `by_severity`: object with integer fields `Critical`, `High`, `Medium`, `Low`, `Info`
     - `by_state`: object with integer fields `unresolved`, `resolved`, `waived`
     - `total_findings`: integer
     - `total_prompts`: integer
   - `gate_decision`: enum `pass|fail`
4. Required prompt result fields (`prompts[]`):
   - `prompt_id` (stable logical id), `prompt_instance_id` (required per-run instance id), `prompt_path`, `tier` (enum: `foundation|deep_dive|gate|fallback`)
   - `selection_reason` (enum: `foundation_trigger|deep_dive_trigger|deferred_fallback|global_fallback|gate_trigger|postmerge_policy|not_applicable_synthetic`)
   - `selection_trace` (array; required) where each entry records a selection intent with:
     - `tier`,
     - `selection_reason`,
     - `matched_by` (enum: `rule_id|gate_policy`),
     - `rule_id` (required when `matched_by=rule_id`; optional for `gate_policy`).
   - `status` (enum: `success|failure|timeout|skipped_not_applicable|skipped_deferred`)
   - `not_applicable_reason` (enum or null; required when `status=skipped_not_applicable`) with allowed values: `missing_shas`, `missing_prompt_file`, `event_not_supported`, `non_authoritative_run`, `missing_pr_linkage`, `invalid_proposal_path`, `no_gate_input`, `invalid_gate_input`.
   - `duration_ms` (integer)
   - `findings` (array)
   - `prompt_instance_id` format:
     - default instance: `<prompt_id>@default`
     - proposal fan-out instance: `<prompt_id>@proposal:<normalized_proposal_path>`
   - `normalized_proposal_path` canonicalization for proposal fan-out:
     - input is repo-relative proposal path only (absolute paths are invalid),
     - separators are normalized to POSIX `/`,
     - no leading `./`,
     - no trailing `/`,
     - case is preserved,
     - `@` is percent-encoded as `%40` and `:` as `%3A`,
     - resulting normalized path is used verbatim in `prompt_instance_id`.
   - `tier` is execution-context-derived (not prompt-path-derived):
     - `foundation` when selected by foundation trigger rules,
     - `deep_dive` when selected by deep-dive trigger rules,
     - `gate` when selected by gate applicability rules,
     - `fallback` when selected by global or deferred fallback rules, including when `prompt_path` is also used by another tier in other runs.
   - Synthetic `not_applicable` emission contract:
     - when `matcher.mode=not_applicable` due to missing SHAs, non-gate prompts MUST emit `status=skipped_not_applicable` and `not_applicable_reason=missing_shas`;
     - if the prompt belongs to foundation set, use `selection_reason=foundation_trigger`;
     - if the prompt belongs to deep-dive set, use `selection_reason=deep_dive_trigger`;
     - use `selection_reason=not_applicable_synthetic` only when an emitted synthetic entry has no applicable trigger lineage in the current event context.
5. Required finding fields (`findings[]`):
   - `finding_id` (unique within each `prompt_instance_id` scope; global uniqueness is not required)
   - `severity` (enum: `Critical|High|Medium|Low|Info`)
   - `state` (enum: `unresolved|resolved|waived`)
   - `summary`
   - `file_refs` (array of repo-relative paths)
   - `waiver_id` (string or null)
6. Deterministic ordering requirements:
   - `prompts[]` must be sorted by `tier_order(gate, deep_dive, foundation, fallback)`, then `prompt_path`, then `prompt_instance_id`.
   - each `findings[]` must be sorted by `severity_rank_desc(Critical..Info)`, then `finding_id`, then `summary`.
7. Parser contract:
   - `prompt-aggregate-parse` consumes only `combined.json`.
   - Invalid JSON, schema mismatch, missing required fields, missing `combined.json`, or missing required per-job artifacts needed to build `combined.json` is a hard failure (`gate_decision=fail`).
   - Exception (explicitly allowed terminal fail shape): when `matcher.mode=fail_closed` and `matcher.error_code=missing_or_unfetchable_shas`, `prompts=[]` is schema-valid and parser must return terminal `gate_decision=fail`.
   - Duplicate findings are deduplicated only by composite key (`prompt_instance_id`, `finding_id`); exact duplicates keep highest severity using order `Critical > High > Medium > Low > Info`.
   - Duplicate prompt entries with the same `prompt_instance_id` and conflicting `status` values are schema-invalid and fail closed.
   - Through `2026-03-30T23:59:59Z`, grandfathered existing prompts may be normalized by a compatibility adapter before schema validation; adapter-recoverable misses are warnings.
   - Adapter-recoverable misses are limited to: missing `prompt_instance_id` derivable as `<prompt_id>@default`.
   - On and after `2026-03-31T00:00:00Z`, the compatibility adapter is disabled and full `prompt_results.schema.v1` compliance is required (missing schema/header compliance fails required checks).
   - `gate_decision` is computed with strict precedence:
     1. Invalid JSON, schema mismatch, missing required fields, or missing required artifact => `fail`.
     2. Any prompt result `status` of `failure` or `timeout` after retry policy is exhausted => `fail`.
     3. Any finding with `severity=Critical` and `state != resolved` => `fail`.
     4. Otherwise => `pass`.
   - `prompt-aggregate-parse` reports unresolved `High` counts but does not validate waiver approval policy.
   - Unresolved `High` waiver validity is enforced by required `prompt-waiver-check`.
   - Merge checks evaluate parser/waiver check outputs only, never free-form logs.
8. Summary counting semantics:
   - `summary.total_prompts` counts all emitted prompt entries, including `skipped_not_applicable` and `skipped_deferred`.
   - `summary.total_findings` counts finding objects only.
   - `summary.by_state` aggregates finding `state` values only (`unresolved`, `resolved`, `waived`); skipped prompts with zero findings do not affect `by_state`.
9. Stable v1 prompt id registry (authoritative map used by runtime and parser):
   - `meta/review_orchestrator.md` => `meta.review_orchestrator`
   - `meta/scoring_rubric.md` => `meta.scoring_rubric`
   - `architecture/system_design.md` => `architecture.system_design`
   - `architecture/mcp_architecture.md` => `architecture.mcp_architecture`
   - `security/audit_ai.md` => `security.audit_ai`
   - `security/supply_chain_and_dependencies.md` => `security.supply_chain_and_dependencies`
   - `testing/test_harness.md` => `testing.test_harness`
   - `testing/coverage_quality.md` => `testing.coverage_quality`
   - `cicd/pipeline_quality.md` => `cicd.pipeline_quality`
   - `cicd/release_and_rollback.md` => `cicd.release_and_rollback`
   - `docs/onboarding_first_run_ux.md` => `docs.onboarding_first_run_ux`
   - `repo/github_first_impression.md` => `repo.github_first_impression`
   - `dev/proposal_implementation_readiness.md` => `dev.proposal_implementation_readiness`
   - `dev/premerge.md` => `dev.premerge`
   - `dev/postmerge_regression_audit.md` => `dev.postmerge_regression_audit`
   - Normative scope rule:
     - Any prompt executable under gate applicability rules MUST appear in this authoritative registry, including prompts outside the 14-prompt v1 creation baseline.

### Changed-file matcher contract

1. Source of truth diff is event-specific:
   - `pull_request`: `git diff <base_sha>..<head_sha>`.
     - If `base_sha` or `head_sha` is missing or unfetchable, matcher fails closed (`matcher_error=missing_or_unfetchable_shas`) and required checks fail.
     - Fail-closed artifact contract is mandatory and deterministic:
       - emit schema-valid `combined.json` with `gate_decision=fail`,
       - emit `prompts=[]`,
       - emit `matcher.mode=fail_closed`,
       - emit `matcher.error_code=missing_or_unfetchable_shas`.
       - `prompt-aggregate-parse` treats this artifact as terminal fail without requiring prompt entries.
   - `push`: `git diff <before_sha>..<after_sha>`
   - `workflow_dispatch` and `schedule` precedence matrix:
     - when both SHAs are explicitly provided: run normal matcher and normal tier flow (foundation -> deep-dive/fallback -> gate);
     - when either SHA is missing: matcher is `not_applicable`; foundation/deep-dive/fallback do not execute; only explicitly requested gate prompts may run; all non-gate active v1 prompts emit `skipped_not_applicable` with `not_applicable_reason=missing_shas`.
     - missing-SHA synthetic emission set is deterministic:
       - emit one prompt entry for every non-gate prompt in the active v1 set;
       - each emitted entry MUST have `findings=[]`;
       - ordering MUST follow `### Output schema and parser contract (required)` deterministic ordering requirements.
   - Fallback when `push.before` is missing (for example, branch creation or history truncation): use `git diff --name-only <after_sha>` equivalent semantics by treating all files reachable at `<after_sha>` as changed (`before_missing_fallback=all_files_changed`), and record this mode in matcher output.
2. Matcher output must include:
   - matched foundation prompts,
   - matched deep-dive prompts,
   - whether fallback set was used,
   - unmatched files list for audit,
   - matcher mode and matcher error code,
   - canonical matched `rule_id` list.
3. Matcher config must live in-repo and be versioned with this proposal policy.
   - Canonical file path: `dev/policy/prompt_matcher_rules.yaml`.
   - Canonical matcher engine: `gitwildmatch` with repo-relative normalized POSIX paths.
   - Canonical rule-id catalog source of truth is `dev/policy/prompt_matcher_rules.yaml`; every selection rule must declare a stable `rule_id`.
   - Duplicate `rule_id` values are schema-invalid configuration and MUST fail closed at matcher startup (no warning-only mode).
4. Path matching is case-sensitive and uses git-reported normalized repository-relative paths.
5. Renames must be treated as both old and new paths for prompt selection (`old_and_new`).
6. Deletes must include the deleted path for prompt selection (`include_deleted_path`).
7. Overlapping rules resolve by union then dedup (a prompt executes at most once per run).
   - Cross-tier dedup precedence is deterministic: `gate > deep_dive > foundation > fallback`.
   - Dedup must preserve lower-tier selection intent by emitting all matched intents in `selection_trace[]` on the single executed prompt entry.
8. Prompt execution order is fixed: `Foundation -> Deep-dive/Fallback -> Gate -> Orchestrator`.
   - `meta/review_orchestrator.md` is classified as a foundation prompt for selection and tier purposes, but executes in a dedicated final phase after all other tiers have produced results. See `### Orchestrator Behavioral Contract`.

### Merge-block behavior

1. `prompt-foundation-check`, `prompt-deep-dive-check`, `prompt-gate-check`, and `prompt-orchestrator-check` are required status checks for merge.
2. `prompt-aggregate-parse` is required and fails closed on artifact/schema violations.
3. `prompt-waiver-check` is required and is authoritative for unresolved `High` waiver validity.
4. `prompt-metadata-check` is required and merge-blocking with cutover behavior from "## Prompt Ownership and Maintenance SLA (v1)".
5. `Critical` waivers are not permitted. Any `Critical` finding with `state != resolved` (including `waived`) fails required checks.
6. Unresolved `High` findings follow the explicit policy in "Unresolved High Policy"; if policy conditions are not met, `prompt-waiver-check` fails required checks.

### Bootstrap enforcement mode (required for v1 rollout)

1. Bootstrap mode applies until all 14 v1 prompt files exist on the default branch at their required paths.
2. In bootstrap mode, required jobs still run, but references to not-yet-created v1 prompts must emit `skipped_not_applicable` entries (never hard-fail solely due to missing prompt file creation sequence).
   - Bootstrap emission cardinality is deterministic:
     - each job MUST emit entries for all required prompts in its applicable tier set, not only selected-existing prompts;
     - if a required prompt file is missing, emit `status=skipped_not_applicable`, `not_applicable_reason=missing_prompt_file`, `findings=[]`;
     - ordering MUST follow global prompt ordering rules.
3. Bootstrap mode ends automatically in the first default-branch commit where all 14 v1 prompt files are present.
4. After bootstrap mode ends, required checks fail closed for any missing v1 prompt file or missing required prompt result entry.

## Prompt Design Contract (applies to every new prompt)

Each prompt should mandate:

1. Evidence-first findings with file references.
2. Severity ranking and confidence level.
3. Clear “what is good / what is missing / what to change”.
4. Priority-ranked action list with effort sizing.
5. Required test or verification commands.
6. A numeric scorecard for that facet.
7. Emission of findings in `prompt_results.schema.v1`.

Migration requirement for existing prompts:

1. Existing prompts present before **2026-02-09** are temporarily grandfathered for structure only.
2. All v1 prompts (existing and new) must emit `prompt_results.schema.v1` and required headers by **2026-03-31** (`2026-03-31T00:00:00Z` enforcement boundary).
3. Through `2026-03-30T23:59:59Z`, missing schema/header compliance is a CI warning when compatibility adapter normalization succeeds.
4. On and after `2026-03-31T00:00:00Z`, missing schema/header compliance is a required-check failure.

### Orchestrator Behavioral Contract (`meta/review_orchestrator.md`)

`meta/review_orchestrator.md` is a **post-execution coverage auditor**. It does not review code directly; it reviews whether the prompt-driven review itself was complete and coherent.

1. **Role:** Audit the review pipeline's output for coverage gaps, cross-prompt coherence, and finding completeness. The orchestrator never produces facet-specific code findings — those are the responsibility of individual facet prompts.

2. **Input (required):**
   - Per-job prompt result artifacts from `prompt-foundation-check`, `prompt-deep-dive-check`, and `prompt-gate-check` (all prompt entries except the orchestrator's own).
   - Matcher output: `changed_files`, `unmatched_files`, `matched_rules`, and `mode`.

3. **Execution phase:**
   - The orchestrator is classified as a foundation prompt for selection, trigger, and tier purposes.
   - It executes in a dedicated final phase **after** all foundation, deep-dive, fallback, and gate prompts have produced results.
   - Pipeline order: `Foundation (excluding orchestrator) -> Deep-dive/Fallback -> Gate -> Orchestrator -> Aggregate parse`.
   - The orchestrator's result artifact is included in `combined.json` before `prompt-aggregate-parse` runs.

4. **Evaluation criteria (what the orchestrator checks):**
   - **Coverage completeness:** Are there changed files in `unmatched_files` or `changed_files` that no prompt's `file_refs` addressed? Flag as coverage gaps.
   - **Selection coherence:** Did the matcher's selected prompts align with the change surface? (Sanity check, not a re-selection.)
   - **Cross-prompt consistency:** Are there contradictory findings across prompts for the same file or surface area?
   - **Finding completeness:** Did any executed prompt produce zero findings for a non-trivial change surface? (Potential false quiet.)

5. **Finding types the orchestrator may produce:**
   - `coverage_gap`: A changed file or surface area was not addressed by any prompt's findings.
   - `selection_anomaly`: The matcher's selection appears misaligned with the change surface.
   - `cross_prompt_conflict`: Two or more prompts produced contradictory findings for the same file.
   - `silent_review`: An executed prompt produced zero findings for a substantive change surface.

6. **Finding types the orchestrator must NOT produce:**
   - Code quality, security, architecture, or any facet-specific technical findings.
   - Severity re-scoring of other prompts' findings (that is `meta/scoring_rubric.md`'s role).
   - Prompt selection overrides or modifications.

7. **Output:** Standard `prompt_results.schema.v1` entries with `prompt_id=meta.review_orchestrator`, `tier=foundation`, `selection_reason=foundation_trigger`.

8. **When the orchestrator has no input** (all other prompts were `skipped_not_applicable`): emit a single `Info`-severity finding noting that no prompt results were available for coverage audit, rather than emitting zero findings silently.

## Suggested Rollout Plan

1. Phase 1: Add `meta/`, `cicd/`, `docs/`, and `repo/` prompts (largest current blind spots).
2. Phase 2: Add `architecture/mcp_architecture.md`, `security/supply_chain_and_dependencies.md`, and `ops/*` prompts.
3. Phase 3: Add UX prompts and `dev/postmerge_regression_audit.md`; then normalize all prompts to one output schema.

## Scope-Control Policy

1. v1 prompt count cap: **14 prompts** (the v1 minimum deliverable set).
2. Adding any new prompt before v1 completion requires a proposal amendment to this file with:
   - rationale,
   - overlap analysis,
   - replacement/deprecation plan if applicable.
3. No category expansion in v1 beyond folders already listed in this proposal.
4. Strict lock: only the 14 v1 prompts may be created in v1. All non-v1 prompt files in this proposal are marked deferred/"do not create yet".
   - Pre-existing non-v1 prompt files present before this proposal are ignored by selection/runtime in v1 and are neither executed nor merge-blocking until explicitly promoted by amendment.
   - Exception: prompts explicitly required by `### Gate prompt applicability and input binding (required)` remain active and executable in v1.
5. Any PR that adds non-v1 prompt files before v1 completion is out of policy and must not merge.
6. Post-v1 prompt additions require explicit owner assignment and maintenance plan.
7. Quarterly prune rule (post-v1): prompts with overlapping scope or low usage must be merged or retired.
8. If deferred prompt triggers match in v1, runtime behavior is `deferred_fallback` (never execute deferred prompts, never silently ignore).

## Prompt Ownership and Maintenance SLA (v1)

Each v1 prompt must have a named owner and maintenance expectations:

1. Owner role: accountable team/individual for prompt correctness and trigger mapping.
2. Review SLA for policy/runtime breakage reports: acknowledge within 2 business days.
3. Fix SLA for confirmed `Critical` prompt defects: 2 business days.
4. Fix SLA for confirmed `High` prompt defects: 5 business days.
5. Drift review cadence: monthly check of trigger mappings and prompt output schema alignment.
6. Required metadata in each v1 prompt header: `owner`, `last_reviewed`, `depends_on`, `adjacent_prompts`.
7. Metadata schema is strict and normative:
   - `owner`: non-empty GitHub identity matching either `@user` or `@org/team`.
   - `last_reviewed`: RFC3339 UTC datetime.
   - `depends_on`: array of prompt ids that MUST exist in the authoritative v1 prompt-id registry.
   - `adjacent_prompts`: array of canonical prompt-library-relative `prompt_path` values.
8. CI enforcement: `prompt-metadata-check` validates required header fields and field grammar on all v1 prompts.
   - Invalid format is a check failure subject to cutover dates.
9. `prompt-metadata-check` failure mode:
   - before **2026-03-31**: warning only for grandfathered existing prompts,
   - on/after **2026-03-31**: required-check failure for any v1 prompt missing required metadata.
10. SLA timing interpretation:
   - SLA windows (`2 business days`, `5 business days`) are governance commitments and are not CI-enforced in v1.
   - CI enforces prompt metadata presence and waiver/runtime policy only.

## Definition of Done

### Objective pass/fail gates

v1 is **PASS** only if all criteria below are met:

1. v1 minimum deliverable prompt set is present at the specified paths.
2. `dev/prompts/README.md` maps facets -> prompt files -> execution triggers.
3. Common output contract exists and is referenced by all v1 prompts.
4. Evaluation calibration sample size is fixed at **10 historical PRs** selected deterministically:
   - PR universe: merged PRs to default branch in the 180 days before calibration start date.
   - Exclude bot-only dependency bump PRs and revert-only PRs.
   - Bucket by dominant surface (`architecture/runtime`, `data/security/dependency`, `docs/workflow/repo`, `mixed`).
   - Selection algorithm: newest-first round-robin across buckets until 10 PRs are selected.
   - Tie-breaker: newer `merged_at`, then smaller PR number.
   - If fewer than 10 eligible PRs exist, use all eligible PRs and record shortage reason.
   - Target distribution: at least 3 architecture/runtime-heavy, at least 3 data/security/dependency-heavy, at least 2 docs/workflow/repo-heavy, and at least 2 mixed-surface PRs.
   - If any bucket has fewer eligible PRs than its target, include all available PRs from that bucket and backfill remaining slots newest-first from the other buckets.
   - Calibration output must include a `bucket_shortage` record with bucket name, target count, selected count, and shortage reason.
5. Across the calibration set evaluation, gate outputs contain:
   - `0` unresolved `Critical` findings,
   - `<=2` unresolved `High` findings total,
   - all unresolved findings have tracked follow-up actions.
6. Pre-merge and post-merge gate prompts reference identical severity thresholds.
7. Severity calibration report is checked into `dev/proposals/` with false-positive/false-negative notes and threshold adjustments.

If any gate fails, status remains **NOT DONE**.

## Unresolved High Policy

An unresolved `High` is temporary only if all conditions below are met:

0. Scope boundary:
   - This policy applies only to `High` findings.
   - `Critical` findings are never waiver-eligible and must be resolved before merge.

1. Time bound: explicit expiry date no later than 14 calendar days from PR merge date.
2. Waiver record: linked issue with owner, mitigation notes, and rollback/containment plan.
3. Approval: waiver approved by prompt owner and code owner for affected surface.
   - Code owner authority source is `.github/CODEOWNERS` at `head_sha`.
   - If no CODEOWNERS pattern matches a waived path, waiver validation fails closed.
   - If multiple rules match, required code-owner approval is from at least one owner in the highest-precedence matching rule.
4. Source of truth: `dev/policy/prompt_waivers.yaml` (authoritative; PR text is non-authoritative).
5. Required waiver fields in `dev/policy/prompt_waivers.yaml`:
   - `waiver_id`, `severity`, `finding_id`, `prompt_id`, `paths`, `approved_by`, `owner`, `follow_up_issue`, `created_on`, `expires_on`, `status`
6. Validation algorithm (performed by `prompt-waiver-check`):
   - parse YAML and validate required fields/types,
   - ensure `severity` is `High`,
   - ensure `finding_id` and `prompt_id` match unresolved findings in `combined.json`,
   - resolve code owner from `.github/CODEOWNERS` at `head_sha` using highest-precedence matching rule for each waived path,
   - ensure approvals satisfy role and cardinality rules:
     - baseline: at least two approvals are present and include prompt owner and resolved code owner,
     - if prompt owner and resolved code owner are the same identity: one approval may satisfy both roles, but at least one additional distinct approver is still required,
   - ensure current UTC time is before or equal to `expires_on`,
   - ensure PR changed files intersect waiver `paths`.
7. Any validation failure or expiry causes required-check failure.
8. Renewal requires a PR updating `dev/policy/prompt_waivers.yaml` with new `expires_on` and mitigation delta; renewal is re-validated by `prompt-waiver-check`.

## Edge Cases and Failure Modes (normative behavior)

1. PR changes only deferred-scope files mapping to non-v1 prompts:
   - matcher records `skipped_deferred`, executes `deferred_fallback`, evaluates normal gate policy.
2. PR modifies docs files outside explicit trigger surfaces:
   - run fallback set, include unmatched files in matcher audit output.
3. Rename from matched path to unmatched path:
   - both old and new paths are considered; selection uses union-then-dedup.
4. Prompt execution timeout/failure:
   - timeout threshold is 600 seconds per attempt;
   - retry once, max 2 attempts total; if still failing, check fails closed.
5. Duplicate finding IDs across prompts:
   - aggregate only exact duplicate tuples by (`prompt_instance_id`, `finding_id`), keep highest severity.
6. Existing prompt missing required header metadata:
   - warning before **2026-03-31**, failure on/after **2026-03-31**.
7. Waiver expires during open PR review window:
   - evaluation at check runtime; expired waiver fails immediately and needs renewal PR.
8. PR appears with no changed files due to merge-commit quirk:
   - run baseline minimum checks: `meta/review_orchestrator.md`, `security/audit_ai.md`, `testing/test_harness.md`, `dev/premerge.md`.
9. `workflow_dispatch` or `schedule` without both SHAs and without `PROPOSAL_PATH`:
   - matcher is `not_applicable`; non-gate prompts emit `skipped_not_applicable` with `missing_shas`; `dev/proposal_implementation_readiness.md` emits `skipped_not_applicable` with `no_gate_input`.
10. Same prompt path selected by multiple tiers in one run:
   - execute once at highest-precedence tier and preserve all selection intents in `selection_trace[]`.
11. Duplicate prompt entries with same `prompt_instance_id` but conflicting status:
   - parser fails closed as schema-invalid.
12. Required per-job artifact missing while assembling `combined.json`:
   - parser fails closed regardless of partial aggregate availability.
13. Two eligible post-merge runs start close together:
   - authoritative run is elected by earliest `run_started_at`, then lowest `run_id`; others are non-authoritative.
14. `PROPOSAL_PATH` supplied with Windows separators:
   - input is accepted, normalized to POSIX `/`, then validated with normal proposal-path rules.
15. Duplicate `rule_id` in `dev/policy/prompt_matcher_rules.yaml`:
   - matcher initialization fails closed; no runtime warning-only fallback.
16. Missing v1 prompt file during bootstrap while selected by fallback:
   - emit `skipped_not_applicable` with `not_applicable_reason=missing_prompt_file` and `findings=[]`.
17. Multiple proposal files changed where one is valid and one is invalid by symlink escape:
   - run valid proposal instance(s); emit `skipped_not_applicable` for invalid instance(s); do not fail whole fan-out solely due to mixed validity.

## Test Plan (minimum required matrix)

The implementation must include automated tests for matcher determinism, deferred handling, schema parsing, waiver lifecycle, and gate decisions.

1. `test_matcher_selects_foundation_on_src_change`
2. `test_matcher_case_sensitive_paths`
3. `test_matcher_rename_uses_old_and_new_paths`
4. `test_matcher_delete_includes_deleted_path`
5. `test_matcher_overlap_union_then_dedup`
6. `test_deferred_prompt_match_maps_to_deferred_fallback`
7. `test_no_deep_dive_match_uses_global_fallback`
8. `test_output_schema_v1_rejects_missing_required_fields`
9. `test_parser_fails_closed_on_missing_combined_artifact`
10. `test_duplicate_prompt_id_finding_id_tuple_uses_highest_severity`
11. `test_gate_prompt_uses_gate_trigger_selection_reason`
12. `test_bootstrap_mode_skips_not_yet_created_v1_prompts_without_failing`
13. `test_schema_cutover_enforces_full_compliance_at_2026_03_31_000000z`
14. `test_postmerge_applicability_push_default_branch_required_surfaces`
15. `test_postmerge_not_applicable_for_non_default_branch_push`
16. `test_waiver_valid_active_high_allows_merge`
17. `test_waiver_expired_fails_gate`
18. `test_waiver_path_mismatch_fails_gate`
19. `test_gate_fails_on_unresolved_critical`
20. `test_gate_fails_on_unwaived_high`
21. `test_prompt_metadata_check_enforces_required_headers`
22. `test_workflow_dispatch_without_shas_gate_only_no_fallback`
23. `test_workflow_dispatch_with_shas_runs_normal_matcher_and_fallback`
24. `test_pull_request_missing_base_or_head_sha_fails_closed`
25. `test_overlap_executes_once_and_preserves_selection_trace`
26. `test_prompt_instance_id_normalization_canonical_repo_relative`
27. `test_prompt_id_registry_is_fixed_for_v1_paths`
28. `test_postmerge_authoritative_run_tiebreaker_start_time_then_run_id`
29. `test_non_authoritative_postmerge_run_emits_not_applicable_reason`
30. `test_dual_role_owner_requires_plus_one_distinct_approver`
31. `test_summary_total_prompts_includes_skipped_by_state_finding_only`
32. `test_duplicate_prompt_instance_conflicting_status_fails_schema`
33. `test_proposal_path_validation_rejects_archive_symlink_traversal_non_md`
34. `test_registry_includes_proposal_readiness_gate_prompt_id`
35. `test_required_gate_prompts_not_suppressed_by_non_v1_ignore_rule`
36. `test_postmerge_status_target_sha_merge_vs_squash_vs_rebase`
37. `test_pr_missing_shas_emits_deterministic_failure_artifact_contract`
38. `test_matcher_output_includes_unmatched_files_and_mode_schema_valid`
39. `test_prompt_path_namespace_is_canonical_end_to_end`
40. `test_scoring_rubric_execution_contract`
41. `test_missing_sha_not_applicable_entries_are_schema_valid`
42. `test_prompt_metadata_schema_validation_strict`
43. `test_bootstrap_missing_prompt_emission_cardinality`
44. `test_windows_proposal_path_normalization_accepts_backslashes`
45. `test_duplicate_rule_id_fails_closed_at_startup`
46. `test_mixed_valid_invalid_proposal_fanout_partial_behavior`
47. `test_orchestrator_executes_after_all_other_prompt_tiers`
48. `test_orchestrator_flags_unmatched_changed_files_as_coverage_gap`
49. `test_orchestrator_does_not_produce_facet_specific_findings`
50. `test_orchestrator_emits_info_finding_when_all_inputs_skipped`
51. `test_orchestrator_detects_cross_prompt_contradictory_findings`

## v1 Overlap and Boundary Matrix

Every v1 prompt must declare adjacent prompts and explicit "not covered" boundaries to prevent duplicate findings and review churn.

1. `meta/review_orchestrator.md`
   - Adjacent: all v1 prompts (consumes their results as input)
   - Covered: review coverage gaps (unaddressed changed files), cross-prompt coherence, finding completeness
   - Not covered: facet-specific technical judgments, code-level findings, severity re-scoring (see `meta/scoring_rubric.md`)
2. `meta/scoring_rubric.md`
   - Adjacent: all v1 prompts
   - Not covered: evidence collection from repository files
3. `architecture/system_design.md`
   - Adjacent: `architecture/mcp_architecture.md`, `cicd/release_and_rollback.md`
   - Not covered: dependency licensing, prompt-injection controls
4. `architecture/mcp_architecture.md`
   - Adjacent: `architecture/system_design.md`, `testing/coverage_quality.md`
   - Not covered: CI policy design, docs IA quality
5. `security/audit_ai.md`
   - Adjacent: `security/supply_chain_and_dependencies.md`, `testing/test_harness.md`
   - Not covered: release rollback mechanics
6. `security/supply_chain_and_dependencies.md`
   - Adjacent: `security/audit_ai.md`, `cicd/pipeline_quality.md`
   - Not covered: runtime observability/runbooks
7. `testing/test_harness.md`
   - Adjacent: `testing/coverage_quality.md`, `dev/premerge.md`
   - Not covered: repository onboarding/first impression
8. `testing/coverage_quality.md`
   - Adjacent: `testing/test_harness.md`, `architecture/mcp_architecture.md`
   - Not covered: legal attribution/licensing text quality
9. `cicd/pipeline_quality.md`
   - Adjacent: `cicd/release_and_rollback.md`, `security/supply_chain_and_dependencies.md`
   - Not covered: deep architecture boundary correctness
10. `cicd/release_and_rollback.md`
   - Adjacent: `cicd/pipeline_quality.md`, `architecture/system_design.md`
   - Not covered: prompt-level rubric schema design
11. `docs/onboarding_first_run_ux.md`
   - Adjacent: `repo/github_first_impression.md`, `dev/premerge.md`
   - Not covered: CI failure containment internals
12. `repo/github_first_impression.md`
   - Adjacent: `docs/onboarding_first_run_ux.md`, `dev/premerge.md`
   - Not covered: code-path security posture
13. `dev/premerge.md`
   - Adjacent: `dev/postmerge_regression_audit.md`, `meta/review_orchestrator.md`
   - Not covered: standalone facet scoring rubric authoring
14. `dev/postmerge_regression_audit.md`
   - Adjacent: `dev/premerge.md`, `testing/test_harness.md`
   - Not covered: repository first-impression/docs IA evaluation

## Risks and Mitigations

- Risk: prompt sprawl and overlap.
  - Mitigation: require each prompt to declare in-scope/out-of-scope and dependencies.
- Risk: reviewers run too many prompts each change.
  - Mitigation: changed-file matcher selects minimal prompt subset by change surface; orchestrator audits coverage completeness post-execution.
- Risk: inconsistent output quality.
  - Mitigation: shared rubric and output schema under `meta/scoring_rubric.md`.

## Implementation Blockers

The following blockers are authoritative for implementation readiness and must each be marked resolved in this proposal before coding begins:

1. `BLK-001` - Deterministic calibration shortage policy is defined so Definition of Done remains achievable when historical PR buckets are sparse.  
   Status: `Resolved` (see `## Definition of Done` item 4).
2. `BLK-002` - Post-merge applicability is defined for merge, squash, and rebase PR strategies.  
   Status: `Resolved` (see `### Post-merge applicability rule` item 1).
3. `BLK-003` - Code-owner authority source and fallback behavior are deterministic for waiver validation.  
   Status: `Resolved` (see `## Unresolved High Policy` items 3 and 6).
4. `BLK-004` - Final readiness criteria references explicit blocker IDs defined in this document.  
   Status: `Resolved` (see `## Final Readiness Criteria` item 1).
5. `BLK-005` - Event precedence for `workflow_dispatch`/`schedule` with and without SHAs is deterministic.  
   Status: `Resolved` (see `### Changed-file matcher contract` item 1 and `### Fallback trigger rule (required safety net)` item 2).
6. `BLK-006` - Cross-tier overlap execution and telemetry retention are deterministic.  
   Status: `Resolved` (see `### Changed-file matcher contract` item 7 and `### Output schema and parser contract (required)` item 4).
7. `BLK-007` - `prompt_instance_id` normalization and stable `prompt_id` mapping are canonicalized.  
   Status: `Resolved` (see `### Output schema and parser contract (required)` items 4 and 9).
8. `BLK-008` - Post-merge authoritative run tie-breaker is deterministic.  
   Status: `Resolved` (see `### Post-merge applicability rule` item 3).
9. `BLK-009` - Waiver approvals remain satisfiable when prompt owner and code owner identities overlap.  
   Status: `Resolved` (see `## Unresolved High Policy` item 6).
10. `BLK-010` - Required gate prompt identity is canonical in the authoritative prompt-id registry.  
   Status: `Resolved` (see `### Output schema and parser contract (required)` item 9).
11. `BLK-011` - Scope-control rules do not suppress required gate prompts in v1.  
   Status: `Resolved` (see `## Scope-Control Policy` item 4 and `### Gate prompt applicability and input binding (required)`).
12. `BLK-012` - PR missing/unfetchable SHA behavior is deterministic for runtime artifact emission and parser outcomes.  
   Status: `Resolved` (see `### Changed-file matcher contract` item 1 and `### Output schema and parser contract (required)` item 7).
13. `BLK-013` - Matcher telemetry fields and canonical `rule_id` catalog are schema-defined and deterministic.  
   Status: `Resolved` (see `### Output schema and parser contract (required)` item 3, item 4, and `### Changed-file matcher contract` item 2-3).
14. `BLK-014` - Governance metadata enforcement is explicitly required in CI and merge-block policy.
   Status: `Resolved` (see `### CI jobs (required)` and `### Merge-block behavior`).
15. `BLK-015` - Orchestrator behavioral contract (input, execution phase, evaluation criteria, permitted finding types) is defined.
   Status: `Resolved` (see `### Orchestrator Behavioral Contract`).

## Final Readiness Criteria

The proposal is implementation-ready only when all items below are true:

1. All implementation blockers in `## Implementation Blockers` (`BLK-001` through `BLK-015`) are marked resolved in this proposal text.
2. A concrete machine-readable result schema and parser contract are specified.
3. Deferred prompt handling in v1 is explicitly defined and CI-testable.
4. Post-merge applicability and waiver validation are deterministic and documented.
5. A deterministic matcher spec and minimum required test matrix are included.
6. Event precedence tables for SHA-present vs SHA-missing dispatch/schedule execution are explicit.
7. Cross-tier dedup behavior preserves lower-tier selection intent in machine-readable telemetry.
8. Proposal fan-out instance identity is canonical and reproducible across implementations.
9. Approval policy has no deadlock branch when ownership roles overlap.
10. Canonical prompt path namespace is explicitly defined and used consistently across matcher/runtime/registry/parser.
11. `meta/scoring_rubric.md` has explicit executable contract in v1.
12. Missing-SHA synthetic skipped behavior is schema-valid and deterministic.
13. Prompt metadata fields have strict validation grammar.
14. Bootstrap missing-file emission behavior is deterministic and tested.
15. `meta/review_orchestrator.md` behavioral contract is defined with explicit input, execution phase, evaluation criteria, and permitted/prohibited finding types.
