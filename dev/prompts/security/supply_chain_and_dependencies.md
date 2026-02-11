---
category: security
description: Evaluate dependency management, lockfile integrity, licensing compliance, and third-party supply chain risk.
when_to_use: When changes touch pyproject.toml, uv.lock, or GitHub Actions workflow dependencies.
related_prompts:
  - security/audit_ai.md
  - cicd/pipeline_quality.md
---

# Supply Chain and Dependency Security Review

Review this repository from the perspective of a **supply chain security engineer** evaluating dependency management, licensing compliance, and third-party risk.

## Scope

**In-scope (supply chain):**

* Dependency manifest review (`pyproject.toml`, `uv.lock`)
* Transitive dependency analysis and known vulnerability exposure
* Lockfile integrity and reproducibility
* Dependency pinning strategy (exact pins vs ranges vs unpinned)
* License compatibility audit (permissive vs copyleft vs unknown)
* Install scripts, post-install hooks, and build system security
* GitHub Actions workflow dependencies (action versions, hash pinning)
* Container base images and layer provenance (if applicable)

**Out-of-scope:**

* Runtime observability and runbook quality (out of scope for this prompt)
* Application-level security and prompt injection (see `security/audit_ai.md`)

## How to Run the Review

Examine dependency and build configuration:

* Parse `pyproject.toml` for direct dependencies and version constraints
* Check `uv.lock` for pinning completeness and hash integrity
* Audit GitHub Actions for unpinned or mutable action references
* Review any install/build scripts for arbitrary code execution risks
* Check license declarations for compatibility

## Deliverables

For each finding include:

* Severity (Critical / High / Medium / Low / Info)
* File path and line range
* What is wrong
* Why it matters
* Specific fix

Produce:

1. Dependency inventory summary
2. Vulnerability exposure findings
3. License compatibility assessment
4. Pinning and reproducibility assessment
5. Actionable recommendations ranked by priority

## Output Format

For each finding, provide:

* **Severity:** Critical / High / Medium / Low / Info
* **File:** `path/to/file.py:L10-L25`
* **Finding:** What is wrong
* **Impact:** Why it matters
* **Fix:** Specific remediation

Organize findings by severity (highest first). If no issues found, state "No findings" with residual risks.
