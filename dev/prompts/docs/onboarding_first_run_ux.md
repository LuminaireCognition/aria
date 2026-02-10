<!-- owner: @anthropic/aria -->
<!-- last_reviewed: 2026-02-10T00:00:00Z -->
<!-- depends_on: [] -->
<!-- adjacent_prompts: ["repo/github_first_impression.md", "dev/premerge.md"] -->

# Documentation and Onboarding UX Review

Review this repository from the perspective of a **developer experience engineer** evaluating documentation quality, onboarding flow, and first-run user experience.

## Scope

**In-scope (onboarding and docs):**

* README completeness: does it explain what the project does, how to install, and how to use it?
* First-run experience: can a new user get from clone to working state without tribal knowledge?
* Documentation information architecture: is content discoverable and well-organized?
* Setup instructions: are prerequisites, environment setup, and configuration documented?
* Error messages and diagnostics: do failures guide users toward resolution?
* Documentation freshness: are docs consistent with current code behavior?

**Out-of-scope:**

* CI failure containment internals (see `cicd/pipeline_quality.md`)
* Code-path security posture (see `security/audit_ai.md`)

## Adjacent Prompts

* `repo/github_first_impression.md` — repository first impression; this prompt goes deeper on documentation
* `dev/premerge.md` — pre-merge quality; this prompt covers documentation as a user-facing deliverable

## How to Run the Review

Evaluate the documentation and onboarding experience:

* Read `README.md` as a first-time user: is the value proposition clear?
* Follow setup instructions: are they complete and correct?
* Check for broken links, outdated references, or missing sections
* Evaluate the `docs/` directory structure for discoverability
* Review error messages in CLI entrypoints for user-friendliness

## Deliverables

For each finding include:

* Severity (Critical / High / Medium / Low / Info)
* File path and line range
* What is wrong
* Why it matters
* Specific fix

Produce:

1. Onboarding flow assessment (clone to working state)
2. Documentation completeness audit
3. Information architecture evaluation
4. Error message quality assessment
5. Actionable recommendations ranked by priority

## Output

Emit findings in `prompt_results.schema.v1`.
