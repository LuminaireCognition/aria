---
category: dev
description: Post-merge regression verification checking for merge artifacts, test suite health, and unintended side effects.
when_to_use: After merging a feature branch to main, to verify no regressions were introduced.
related_prompts:
  - dev/premerge.md
  - testing/test_harness.md
---

# Post-Merge Regression Verification

Act as a strict senior engineer performing a post-merge regression audit on `main`.

## Scope

**In-scope (post-merge regression):**

* Verify that the merged changes do not introduce regressions in existing behavior
* Confirm test suite passes on the merged commit
* Check for unintended side effects on adjacent modules
* Validate that merge resolution (if any) preserved intended behavior
* Verify build artifacts are producible from the merged state

**Out-of-scope:**

* Repository first-impression and documentation IA evaluation (see `docs/onboarding_first_run_ux.md`, `repo/github_first_impression.md`)
* Pre-merge review concerns (see `dev/premerge.md`)

## Review Goals

1. Verify test suite passes on the merged commit without flakes or skipped critical tests.
2. Check for merge conflict artifacts (conflict markers, duplicate code, missing imports).
3. Verify that the merged state is consistent with the pre-merge review's expectations.
4. Identify regressions in functionality, performance, or correctness.
5. Confirm build and CI pipeline health on the merged commit.

## Deliverables

For each finding include:

* Severity (Critical / High / Medium / Low / Info)
* File path and line range
* What is wrong
* Why it matters
* Specific fix

Produce:

1. Regression findings (if any)
2. Merge resolution assessment
3. Test suite health on merged commit
4. Build artifact verification
5. Explicit "no regressions found" statement if clean

## Output Format

For each finding, provide:

* **Severity:** Critical / High / Medium / Low / Info
* **File:** `path/to/file.py:L10-L25`
* **Finding:** What is wrong
* **Impact:** Why it matters
* **Fix:** Specific remediation

Organize findings by severity (highest first). If no issues found, state "No findings" with residual risks.
