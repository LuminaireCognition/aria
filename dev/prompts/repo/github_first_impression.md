---
category: repo
description: Assess repository presentation, community health files, and contributor readiness from a first-time visitor perspective.
when_to_use: When changes touch .github/, README.md, CONTRIBUTING.md, LICENSE, or ATTRIBUTION.md.
related_prompts:
  - docs/onboarding_first_run_ux.md
  - dev/premerge.md
---

# GitHub Repository First Impression Review

Review this repository from the perspective of a **potential contributor or evaluator** encountering the GitHub repository for the first time, assessing its public-facing presentation and community readiness.

## Scope

**In-scope (first impression):**

* Repository metadata: description, topics, license badge, social preview
* README quality: clear value proposition, quick start, badges, screenshots/examples
* Contributing guidelines: `CONTRIBUTING.md` presence and quality
* License clarity: `LICENSE` file presence and correctness
* Attribution: `ATTRIBUTION.md` or equivalent for third-party credits
* Issue and PR templates: are they present and helpful?
* GitHub-specific configuration: branch protection, code owners, security policy
* Community health files: `CODE_OF_CONDUCT.md`, `SECURITY.md`

**Out-of-scope:**

* Code-path security posture (see `security/audit_ai.md`)
* Deep documentation IA (see `docs/onboarding_first_run_ux.md`)

## How to Run the Review

Evaluate the repository's GitHub presentation:

* Review repository root files for completeness
* Check `.github/` directory for templates, workflows, and community health files
* Assess `README.md` against the "30-second test": can a visitor understand the project in 30 seconds?
* Verify license and attribution accuracy
* Check for broken badges or links

## Deliverables

For each finding include:

* Severity (Critical / High / Medium / Low / Info)
* File path and line range
* What is wrong
* Why it matters
* Specific fix

Produce:

1. Repository presentation inventory
2. Community health file assessment
3. README quality evaluation
4. License and attribution findings
5. Actionable recommendations ranked by priority

## Output Format

For each finding, provide:

* **Severity:** Critical / High / Medium / Low / Info
* **File:** `path/to/file.py:L10-L25`
* **Finding:** What is wrong
* **Impact:** Why it matters
* **Fix:** Specific remediation

Organize findings by severity (highest first). If no issues found, state "No findings" with residual risks.
