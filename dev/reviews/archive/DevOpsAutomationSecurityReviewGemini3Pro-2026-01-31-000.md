# DevOps, Automation & Security Review

**Reviewer:** Gemini 3 Pro
**Date:** 2026-01-31
**Context:** Pre-public release assessment
**Reference:** `@dev/reviews/decomposition_guide.md`

## Executive Summary

The project demonstrates a mature "shift-left" security posture and a modern Python build toolchain (`uv`, `hatch`). The adoption of `keyring` for credential storage significantly hardens local security. However, resilience in dependency management (specifically git dependencies) and maintainability of mixed-language shell scripts need attention before public release.

---

## 1. Security Posture

### Strengths (Brief)
*   **Credential Management:** The Two-Tier Auth model (System Keyring > File) is implemented robustly with clear fallbacks for headless environments (`ARIA_NO_KEYRING`).
*   **CI Guardrails:** `gitleaks` active in CI prevents secret commit.
*   **Minimal Permissions:** `aria-esi-sync.py` uses standard library only, reducing attack surface for boot-time scripts.

### Actionable Improvements
1.  **Dependency Pinning & Integrity**:
    *   **Issue:** The `eos` dependency is pulled via git (`git+https://github.com/pyfa-org/eos.git@c2cc80fd`). This creates a build-time dependency on GitHub availability and prevents verifying package checksums in standard PyPI flows.
    *   **Recommendation:** Vendorize the `eos` library or publish a fork to a private PyPI/release asset if the upstream is not on PyPI. Git dependencies are fragile for public releases.

2.  **Linting & Typing Strictness**:
    *   **Issue:** `pyproject.toml` shows `disallow_untyped_defs = false` and loose type checking in many areas.
    *   **Recommendation:** Enforce `disallow_untyped_defs = true` for `src/aria_esi/core/auth.py` and `keyring_backend.py` specifically to ensure strict typing on security-critical paths.

3.  **Pre-commit Configuration**:
    *   **Issue:** `.pre-commit-config.yaml` manually manages `additional_dependencies` (e.g., `types-PyYAML`), risking drift from `pyproject.toml`.
    *   **Recommendation:** Use `uv export` or sync mechanisms to ensure pre-commit hooks use the same dependency versions as the project.

## 2. DevOps & Automation

### Strengths (Brief)
*   **Toolchain:** Excellent usage of `uv` for fast resolution and installation.
*   **CI Matrix:** Testing across Python 3.10-3.13 ensures broad compatibility.

### Actionable Improvements
1.  **CI Optimization**:
    *   **Issue:** The `lint` job in `ci.yml` runs `uv sync --all-extras`. This installs heavy dependencies (like `eos` and `igraph`) just to run `ruff`.
    *   **Recommendation:** Configure a lightweight `lint` group in `pyproject.toml` or `uv` command to install only `ruff` and `mypy` (and types) for the lint job, speeding up feedback loops.

2.  **Script Architecture**:
    *   **Issue:** `.claude/scripts/aria-boot-sync` uses extensive inline Python (via heredocs) to parse JSON. This "shell-wrapping-python" pattern is hard to debug and test.
    *   **Recommendation:** Port `aria-boot-sync` entirely to Python (merging logic into `aria-esi-sync.py` or a new module). The shell script should be a thin wrapper only, or removed entirely in favor of a Python entry point.

3.  **Release Automation**:
    *   **Issue:** No semantic release or changelog automation is visible in `ci.yml`.
    *   **Recommendation:** Add a `release.yml` workflow that triggers on tag push to build wheels (`hatch build`) and publish to PyPI (or TestPyPI) to verify packaging integrity.

## 3. Resilience

1.  **Bot/Headless Awareness**:
    *   **Observation:** The `keyring` fallback logic is good, but ensure the `ARIA_NO_KEYRING` warning is prominent in logs when running in CI/Docker to avoid confusion about missing credentials.
    *   **Recommendation:** Add a "Doctor" command (`aria-esi doctor`) that validates the environment (keyring status, ESI connectivity, git deps) to aid user debugging.

## Summary of Recommendations

| Priority | Category | Recommendation | Rationale |
| :--- | :--- | :--- | :--- |
| **High** | Security | Replace `eos` git dependency | Prevents build failures and supply chain risks. |
| **High** | DevOps | Refactor `aria-boot-sync` to Python | Improves maintainability and reduces "magic string" errors. |
| **Medium** | DevOps | Optimize CI `lint` job | Reduces CI cost and time. |
| **Medium** | Security | Enforce strict typing on `auth.py` | Reduces bug risk in critical security code. |
