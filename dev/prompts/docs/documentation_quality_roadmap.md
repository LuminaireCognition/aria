---
category: docs
description: Audit all user-facing documentation and produce a prioritized roadmap to reach high-quality GitHub project standards.
when_to_use: When you need a full documentation quality assessment and a concrete improvement plan.
related_prompts:
  - docs/onboarding_first_run_ux.md
  - repo/github_first_impression.md
  - ux/ux_analysis.md
---

# Documentation Quality Roadmap Review

Review this repository from the perspective of a **documentation lead** responsible for improving user-facing docs to the level of high-quality open source GitHub projects.

## Scope

**In-scope (user-facing documentation):**

* `README.md`, `docs/`, onboarding guides, tutorials, examples, and FAQs
* CLI help text, usage examples, error-message guidance, and troubleshooting content
* API docs or reference docs exposed to users/contributors
* Contribution docs that affect onboarding quality (`CONTRIBUTING.md`, setup guides)
* Discoverability, navigation, consistency, and information architecture
* Accuracy and freshness versus current repository behavior
* Clarity and concision: approachability for new users while keeping high signal-to-noise

**Out-of-scope:**

* Deep code architecture critique unrelated to docs quality
* Internal CI/CD implementation details unless they directly break docs workflows

## How to Run the Review

Evaluate documentation end-to-end:

* Inventory user-facing docs and map them by audience (new user, contributor, maintainer)
* Walk first-run setup as documented and note friction, ambiguity, or missing prerequisites
* Verify examples and commands against current repository structure and tooling
* Check for contradictions, stale claims, broken links, duplicate content, and missing cross-links
* Assess writing quality: clarity, brevity, scan-ability, and unnecessary noise
* Benchmark quality against strong OSS documentation norms (quickstart, reference, troubleshooting, contribution path, maintenance cadence)

## Deliverables

For each finding include:

* Severity (Critical / High / Medium / Low / Info)
* File path and line range
* What is wrong
* Why it matters
* Specific fix

Produce:

1. Documentation maturity snapshot (current state, strengths, major deficits)
2. Findings list ranked by severity
3. Gap matrix by doc type:
   * Getting started
   * Core usage
   * Advanced usage
   * Troubleshooting
   * Contributing
   * Reference/API
4. Signal-to-noise assessment:
   * Where docs are too sparse to be usable
   * Where docs are too verbose or repetitive
   * Concrete edits to balance approachability with density
5. Prioritized roadmap to raise quality:
   * Phase 1 (quick wins, 1-2 weeks)
   * Phase 2 (structural improvements, 2-6 weeks)
   * Phase 3 (ongoing governance and quality controls)
6. Success metrics and maintenance guardrails (what to measure and how to keep docs healthy)

## Output Format

For each finding, provide:

* **Severity:** Critical / High / Medium / Low / Info
* **File:** `path/to/file.md:L10-L25`
* **Finding:** What is wrong
* **Impact:** Why it matters
* **Fix:** Specific remediation

Then provide a final roadmap section:

* **Target State:** What "high-quality docs" means for this repo
* **Phased Plan:** Phase 1, Phase 2, Phase 3 with owners, effort, and dependency notes
* **Top 10 Actions:** Ordered checklist
* **Definition of Done:** Objective criteria to declare docs up to par

Organize findings by severity (highest first). If no issues found, state "No findings" with residual risks and verification limits.
