---
category: architecture
description: Identify high-complexity, low-utility accretions and recommend removals/simplifications that maximize project clarity and leverage.
when_to_use: When the codebase feels bloated/sprawling and you need a ruthlessly prioritized remove-or-simplify plan.
related_prompts:
  - architecture/system_design.md
  - architecture/python.md
  - dev/premerge.md
---

# Accretion Auditor

Review this repository from the perspective of a **staff engineer focused on simplification and leverage**. Your task is to find features, subsystems, abstractions, or workflows that add disproportionate complexity while delivering weak usability, utility, or strategic advantage.

## Scope

**In-scope (accretion analysis):**

* Over-engineered features with low observed payoff
* Duplicate or near-duplicate capabilities across modules/commands
* Framework/abstraction layers that add indirection without clear gain
* Legacy/dead-end code paths retained without active value
* Operational/process overhead with weak user or delivery impact
* Maintenance hotspots: areas with high coupling/churn and low product benefit

**Out-of-scope:**

* Security threat modeling (see `security/audit_ai.md`)
* CI/CD reliability deep-dive (see `cicd/pipeline_quality.md`)
* Documentation-only quality review (see `docs/onboarding_first_run_ux.md`)

## Method

Use repository evidence (code, tests, docs, scripts, command surface, and architecture) to score candidate accretions.

For each candidate, assign 1-5 scores:

* **Complexity Cost (C):** cognitive load, coupling, maintenance burden
* **Utility Yield (U):** real user value, operational usefulness, strategic differentiation
* **Removal Feasibility (R):** ease/safety of removal or collapse into simpler design

Compute:

* **Accretion Score = (C * R) - U**

Higher score means better removal/simplification candidate.

## How to Run the Review

* Map major subsystems and user-facing workflows
* Identify features/paths with high code footprint but weak user-facing outcomes
* Check for overlapping commands, duplicate logic, and “just-in-case” abstractions
* Compare implementation complexity against actual usage evidence in docs/tests/entrypoints
* Prefer removal, consolidation, or default-off over additive remediation

## Deliverables

Produce a concise report with:

1. **Top Removal Candidates (max 7)** ranked by Accretion Score
2. **Quick Wins (max 5)** that can be removed/simplified in <=2 days
3. **Consolidation Plan**: what to merge, deprecate, or delete
4. **Reoptimization Plan**: target architecture after removals (short, concrete)
5. **Risk Notes**: what must be preserved to avoid user harm/regression

## Required Output Format

For each candidate provide:

* **Rank:** 1..N
* **Accretion Score:** numeric + `(C=?, U=?, R=?)`
* **Area:** subsystem/feature name
* **Evidence:** file paths + line references
* **Why low leverage:** why complexity outweighs value
* **Action:** remove / merge / simplify / deprecate
* **Expected gain:** what improves (maintainability, UX clarity, delivery speed, reliability)
* **Guardrail:** tests/migration checks needed for safe change

Then include:

* **Priority Cut List (Short):** the 3 highest-leverage cuts to execute first

Constraints:

* Keep the final cut list short and opinionated.
* Do not propose broad rewrites before deletions/consolidations are attempted.
* If evidence is weak, mark confidence and move the candidate lower.
