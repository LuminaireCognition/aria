---
category: cicd
description: Evaluate CI/CD pipeline reliability, job dependencies, secret handling, and failure diagnostics.
when_to_use: When reviewing GitHub Actions workflows or CI configuration changes.
related_prompts:
  - cicd/release_and_rollback.md
  - security/supply_chain_and_dependencies.md
---

# CI/CD Pipeline Reliability Review

Review this repository from the perspective of a **senior DevOps/platform engineer** evaluating CI/CD pipeline reliability, correctness, and operational safety.

## Scope

**In-scope (pipeline quality):**

* GitHub Actions workflow correctness (job dependencies, conditional execution, artifact handling)
* Pipeline reliability: flake resilience, timeout configuration, retry strategy
* Secret handling in workflows (exposure risk, minimal-scope tokens)
* Job dependency graph: are dependencies correct and minimal?
* Caching strategy: are caches effective and invalidated correctly?
* Matrix and parallel execution: are jobs parallelized where possible?
* Failure modes: do failures produce actionable diagnostics?

**Out-of-scope:**

* Deep architecture boundary correctness (see `architecture/system_design.md`)
* Application-level security posture (see `security/audit_ai.md`)

## How to Run the Review

Examine CI/CD configuration:

* Parse all workflow files under `.github/workflows/`
* Map job dependency graphs and identify missing or unnecessary dependencies
* Check for hardcoded secrets, unpinned actions, or insecure patterns
* Evaluate timeout and retry configuration
* Review artifact upload/download patterns for correctness

## Deliverables

For each finding include:

* Severity (Critical / High / Medium / Low / Info)
* File path and line range
* What is wrong
* Why it matters
* Specific fix

Produce:

1. Workflow inventory and job dependency map
2. Reliability findings (flakes, timeouts, retries)
3. Security findings (secrets, permissions)
4. Artifact handling assessment
5. Actionable recommendations ranked by priority

## Output Format

For each finding, provide:

* **Severity:** Critical / High / Medium / Low / Info
* **File:** `path/to/file.py:L10-L25`
* **Finding:** What is wrong
* **Impact:** Why it matters
* **Fix:** Specific remediation

Organize findings by severity (highest first). If no issues found, state "No findings" with residual risks.
