  Act as a strict senior engineer performing a pre-merge review for `main`.

  Scope:
  - Proposal: `dev/proposals/LINUX_VM_DOCKER_RUNTIME_PROPOSAL.md`
  - Current branch contains the implementation; `pytest` is already passing.

  Review goals:
  1. Verify the implementation fully matches the proposal requirements (call out missing, partial, or extra behavior).
  2. Verify professional production standards: correctness, reliability, security, maintainability, observability, performance, and rollback safety.
  3. Verify project standards/conventions are followed (architecture, style, lint/type expectations, test patterns, docs/changelog/release notes, error handling, logging, config/env handling).
  4. Identify merge risks, regressions, and hidden edge cases not covered by tests.
  5. Confirm “definition of done” completeness for shipping.

  Instructions:
  - Focus on findings first, not a narrative summary.
  - Prioritize by severity: `critical`, `high`, `medium`, `low`.
  - For each finding include:
    - `severity`
    - `file:path:line` (or nearest location)
    - `what is wrong`
    - `why it matters`
    - `specific fix`
  - Explicitly list:
    - proposal requirements satisfied
    - proposal requirements missing/ambiguous
    - test coverage gaps (unit/integration/e2e)
    - documentation/operational gaps
  - If no issues are found, explicitly say “No blocking findings” and list residual risks and recommended follow-up checks.
  - Be concrete and actionable; avoid generic advice.
