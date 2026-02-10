<!-- owner: @anthropic/aria -->
<!-- last_reviewed: 2026-02-10T00:00:00Z -->
<!-- depends_on: [] -->
<!-- adjacent_prompts: ["dev/premerge.md", "meta/review_orchestrator.md"] -->

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

## Adjacent Prompts

* `dev/premerge.md` — pre-merge review; this prompt covers post-merge verification
* `testing/test_harness.md` — test infrastructure; this prompt verifies tests pass post-merge

## Applicability

This is a **gate prompt**. It is applicable only when:

* The event is a `push` to the default branch (post-merge)
* The `postmerge_applicable` flag is set

It is **not applicable** for:

* Pull request events (pre-merge review is handled by `dev/premerge.md`)
* Non-default branch pushes
* Workflow dispatch without explicit post-merge context

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

## Output

Emit findings in `prompt_results.schema.v1`.
