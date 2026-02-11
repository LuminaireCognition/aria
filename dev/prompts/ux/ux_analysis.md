---
category: ux
description: Evaluate product interaction UX, CLI flow quality, output clarity, and user trust signals.
when_to_use: When reviewing user-facing command flows, prompts, errors, and output formatting changes.
related_prompts:
  - docs/onboarding_first_run_ux.md
  - repo/github_first_impression.md
  - architecture/llm_integration.md
---

# Product and Interaction UX Review

Review this repository from the perspective of a **senior UX engineer** evaluating interaction design quality, usability, and trust in user-facing workflows.

## Scope

**In-scope (UX analysis):**

* Task flow clarity: can users complete common goals without confusion?
* CLI interaction quality: command discoverability, help text quality, argument ergonomics, and progressive disclosure
* Output usability: readability, scanability, structure, and signal-to-noise ratio
* Error UX: actionable failures, recovery guidance, and prevention of repeated mistakes
* Consistency: terminology, tone, formatting, severity language, and behavior across commands
* Trust signals: explicit uncertainty, provenance/citations when relevant, and clear boundaries on what the tool can/cannot do
* Friction analysis: unnecessary steps, hidden prerequisites, surprising defaults, and avoidable cognitive load

**Out-of-scope:**

* Deep system/module boundary design (see `architecture/system_design.md`)
* Security threat modeling and prompt-injection controls (see `security/audit_ai.md`)
* CI/CD process reliability (see `cicd/pipeline_quality.md`)
* Documentation IA and onboarding docs quality (see `docs/onboarding_first_run_ux.md`)

## How to Run the Review

Evaluate UX from first interaction to advanced use:

* Identify top user journeys (for example: setup, first successful command, routine workflows, troubleshooting)
* Walk each journey step-by-step and record points of confusion, ambiguity, or unnecessary effort
* Audit CLI help and command surfaces for naming clarity and option consistency
* Evaluate output examples (normal, warning, error) for readability and actionability
* Verify whether failures provide concrete next steps and whether recovery paths are obvious
* Check consistency of interaction patterns across commands and subsystems

## Deliverables

For each finding include:

* Severity (Critical / High / Medium / Low / Info)
* File path and line range
* What is wrong
* Why it matters for user success/trust
* Specific fix

Produce:

1. UX journey map for primary workflows (concise)
2. Interaction friction findings ranked by severity
3. Output clarity and trustworthiness assessment
4. Error and recovery UX assessment
5. Actionable recommendations ranked by implementation priority

## Output Format

For each finding, provide:

* **Severity:** Critical / High / Medium / Low / Info
* **File:** `path/to/file.py:L10-L25`
* **Finding:** What is wrong
* **Impact:** Why it matters
* **Fix:** Specific remediation

Organize findings by severity (highest first). If no issues found, state "No findings" with residual risks.
