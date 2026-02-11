---
category: cicd
description: Evaluate release processes, versioning strategy, rollback safety, and deployment artifact integrity.
when_to_use: When reviewing release workflows, versioning changes, or migration scripts.
related_prompts:
  - cicd/pipeline_quality.md
  - architecture/system_design.md
---

# Release Engineering and Rollback Safety Review

Review this repository from the perspective of a **senior release engineer** evaluating release processes, versioning strategy, and rollback safety.

## Scope

**In-scope (release and rollback):**

* Versioning strategy: is it consistent, automated, and well-documented?
* Release process: are releases reproducible and auditable?
* Rollback safety: can any release be safely rolled back?
* Changelog and release notes: are they maintained and accurate?
* Migration safety: do schema or data migrations support rollback?
* Feature flags and gradual rollout mechanisms (if applicable)
* Deployment artifact integrity: are build outputs deterministic?

**Out-of-scope:**

* Prompt-level rubric schema design (see `meta/scoring_rubric.md`)
* CI pipeline mechanics (see `cicd/pipeline_quality.md`)

## How to Run the Review

Examine release and deployment configuration:

* Check versioning in `pyproject.toml` and any version management tooling
* Review release workflows and automation
* Evaluate rollback procedures (documented or automated)
* Check for migration scripts and their reversibility
* Review changelog maintenance practices

## Deliverables

For each finding include:

* Severity (Critical / High / Medium / Low / Info)
* File path and line range
* What is wrong
* Why it matters
* Specific fix

Produce:

1. Release process inventory
2. Versioning strategy assessment
3. Rollback safety analysis
4. Migration safety findings
5. Actionable recommendations ranked by priority

## Output Format

For each finding, provide:

* **Severity:** Critical / High / Medium / Low / Info
* **File:** `path/to/file.py:L10-L25`
* **Finding:** What is wrong
* **Impact:** Why it matters
* **Fix:** Specific remediation

Organize findings by severity (highest first). If no issues found, state "No findings" with residual risks.
