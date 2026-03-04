# ARIA Repository Technical Review (2026-03-04)

## Executive Summary
ARIA is a mature, feature-rich LLM-assisted EVE Online automation framework with strong domain depth, substantial test coverage, and clear investment in security controls (policy gating, path validation, integrity checks, context budgeting). The system architecture is coherent around a core Python platform (`src/aria_esi`), an MCP server with domain dispatchers, and a large skill/prompt layer in `.claude/skills`.

Primary risks are now concentrated in policy ergonomics and operational complexity rather than missing foundations: policy defaults currently allow sensitive pilot actions via explicit allow-list entries, confirmation flows are inconsistently handled across dispatchers, and several key modules are very large and difficult to maintain. LLM integration for notification commentary is practical but can be made more deterministic, safer, and cheaper with stronger output contracts and evaluation loops.

## Architecture Overview
- Core runtime is modularized into `commands/`, `core/`, `mcp/`, `services/`, `store/`, `universe/`, and `persona/` packages under `src/aria_esi`.
- MCP architecture is dispatcher-centric and intentionally reduces tool proliferation (`src/aria_esi/mcp/tools.py`, `src/aria_esi/mcp/dispatchers/__init__.py`). This is a good design for LLM tool selection quality.
- Universe subsystem is cleanly separated into graph build/load/serialization (`src/aria_esi/universe/builder.py`, `serialization.py`, `graph.py`) with safe `.universe` format and checksum verification.
- Boot orchestration is robust and security-aware (`.claude/hooks/aria-boot.sh`, `.claude/hooks/aria-boot.d/boot-operations.sh`), including preflight checks, security validation, artifact integrity checks, and context assembly.
- Skills are externally indexed with metadata (`.claude/skills/_index.json`) and include required tools/scopes, which is strong for governance and preflight capability checks.

Architecture concerns:
- Very large modules reduce evolvability and reviewability, especially in market/store/CLI layers (e.g., `store/market/database.py`, `commands/universe.py`, `store/sde/importer.py`, `mcp/dispatchers/market.py`).
- Some docs and config state are drift-prone: project URLs in `pyproject.toml` differ from README org/repo references.

## Code Quality Assessment
Strengths:
- Good use of typed dataclasses and Pydantic settings (`core/config.py`).
- Clear domain organization and extensive docstrings.
- Strong tests across unit/integration/MCP/skills.

Findings:
- Module size and mixed responsibilities create technical debt in core paths (`store/market/database.py`, `commands/universe.py`, `mcp/dispatchers/market.py`).
- Command/help surface in `__main__.py` is monolithic and difficult to validate end-to-end.
- Repository hygiene issue: committed `__pycache__` directories under `src/` and `tests/` despite `.gitignore` rules. This adds noise and can hide meaningful diffs.
- Type-checking posture is improving but still relies on targeted suppressions/disabled codes in `pyproject.toml`; this is pragmatic but indicates unresolved correctness debt in specific MCP and market modules.

Actionable improvements:
- Split top 5 largest modules into service + adapter + transport layers with strict boundaries.
- Move CLI command registry into generated/structured command metadata instead of one monolithic entrypoint.
- Add CI guard to fail on committed cache artifacts (`__pycache__`, `.pyc`).

## LLM Integration Review
Current state:
- Two main LLM integration surfaces:
  - Claude skill/prompt system (`.claude/skills`, hooks, context assembly scripts).
  - Multi-provider notification commentary generation (`services/redisq/notifications/*`).
- Commentary stack has positive design elements:
  - Provider abstraction (`llm_providers/*`), configurable model/provider.
  - Prompt structure separation (`prompts.py`).
  - Cost tracking and limits (`commentary.py`).
  - Lightweight post-generation token-preservation validator (`validate_preserved_tokens`).

Gaps and risks:
- Determinism: commentary output has no strict schema/structured contract; output is plain text with heuristic validation only.
- Reliability: no retry/circuit-breaker strategy in provider adapters; failures are swallowed to `None` quickly, which is safe but can degrade quality silently.
- Cost accuracy mismatch risk: default model identifiers and pricing comments are inconsistent in places (e.g., Sonnet model with Haiku-style cost comments in commentary/provider constants).
- Prompt-injection resistance depends mostly on instruction quality and selective token checks; there is no model-side or parser-side robust semantic policy check for generated content.
- Skill-level runtime enforcement is partly externalized to prompt instructions; this is effective for behavior shaping but not equivalent to hard guarantees.

Recommendations:
- Add structured output mode for commentary (`pydantic` schema + parser + reject/repair loop).
- Add provider-level retry and timeout strategy with exponential backoff and idempotent safeguards.
- Add golden/eval coverage for LLM outputs beyond current token-preservation checks (failure-mode regression suite).
- Normalize provider pricing/model metadata and validate config combinations at startup.

## Security Review
Positive controls:
- Path security with allowlists, symlink containment, extension checks (`core/path_security.py`).
- Data integrity checks for SDE/universe graph (`core/data_integrity.py`, `reference/data-sources.json`).
- MCP capability policy engine with sensitivity classes and audit logging (`mcp/policy.py`).
- Context/log sanitization (`core/sanitization.py`, `mcp/context.py`).
- Boot-time security validation and artifact integrity checks (`.claude/hooks/aria-boot.d/boot-operations.sh`).

High-impact security findings:
1. Policy default allows sensitive pilot actions via explicit allow-list.
- `reference/mcp-policy.json` includes `pilot.mail_list`, `pilot.mail_read`, and `pilot.mining_ledger` in `allowed_actions` while `allowed_levels` excludes `authenticated/restricted`.
- Effect: default installation posture is less restrictive than implied by sensitivity model.

2. Confirmation workflow is not consistently handled.
- `ConfirmationRequired` is raised by policy engine, but explicit fallback handling exists mainly in fitting dispatcher (`mcp/dispatchers/fitting.py`).
- Other dispatchers call `check_capability(...)` directly; user-confirmation semantics are not uniformly implemented.

3. Break-glass environment toggles are powerful and global.
- `ARIA_ALLOW_UNSAFE_PATHS`, `ARIA_ALLOW_UNPINNED`, `ARIA_MCP_BYPASS_POLICY` are useful operationally but high-risk if set in shared environments.
- Current implementation logs/audits, but stronger startup warnings and explicit runtime banners would reduce accidental insecure operation.

4. Legacy pickle reader still exists in serialization layer.
- `universe/serialization.py` still supports v1 picklez path (deprecated). Builder path currently avoids it, but retaining deserialization code increases long-term attack surface.

Mitigations:
- Remove sensitive actions from default `allowed_actions`; move to explicit local opt-in profile.
- Standardize `ConfirmationRequired` handling in a shared dispatcher wrapper.
- Enforce explicit startup warnings/errors when break-glass flags are active in non-dev contexts.
- Remove legacy pickle read support on a defined date/version boundary.

## Operational/Dependency Review
Strengths:
- Reproducibility is good with `uv.lock` and `uv`-based workflows.
- CI coverage is strong and multi-dimensional (`.github/workflows/ci.yml`, `test-universe.yml`, `tier2-skill-tests.yml`, `data-health.yml`).
- Pre-commit is practical (`ruff`, `mypy`, command freshness checks).

Concerns:
- Dependency strategy is mostly lower bounds with broad ranges in `pyproject.toml`; this is flexible but can introduce runtime drift without proactive update testing.
- No explicit dependency vulnerability scan (e.g., `pip-audit`/`uv audit`) in CI.
- Security scan relies on gitleaks; supply-chain checks can be expanded.
- Documentation drift in testing docs vs current coverage settings and thresholds is possible (some docs cite older targets).

Recommendations:
- Add automated dependency vulnerability scanning in CI.
- Add scheduled lockfile refresh + compatibility test workflow.
- Align docs and runtime config references regularly via lint/check jobs.

## Strengths
- Strong domain decomposition and clear intent around MCP dispatchers.
- Excellent investment in testing breadth across runtime, MCP, and skill contracts.
- Security-aware engineering culture visible in path validation, integrity checks, and policy framework.
- Practical multi-provider LLM abstraction with cost controls and graceful degradation.
- Robust boot/runtime operational checks for real user environments.

## Priority Improvements
1. Harden default MCP policy posture.
- Remove pilot-sensitive default `allowed_actions`; require explicit user opt-in per environment/profile.

2. Implement uniform confirmation handling.
- Centralize `ConfirmationRequired` handling so all authenticated/restricted actions have consistent UX and enforcement.

3. Decompose largest modules.
- Target `store/market/database.py`, `commands/universe.py`, `mcp/dispatchers/market.py`, `store/sde/importer.py` first.

4. Strengthen LLM output contracts.
- Move commentary outputs to structured schema + validation/repair path; add regression eval suite for adversarial prompts.

5. Expand supply-chain controls.
- Add dependency CVE scanning and periodic lockfile freshness checks in CI.

6. Improve repository hygiene automation.
- Add CI check for accidental committed `__pycache__`/generated artifacts.

## Suggested Next Steps
1. Security quick win (same week): patch `reference/mcp-policy.json` defaults and add a migration note for users relying on current behavior.
2. Platform reliability (1-2 sprints): add centralized policy confirmation middleware used by all dispatchers.
3. Maintainability (2-4 sprints): execute a refactor plan for top 3 oversized modules with characterization tests first.
4. LLM quality/safety (parallel): implement schema-constrained commentary generation and adversarial test fixtures in `tests/services/redisq`.
5. Ops hardening (ongoing): add dependency audit job and artifact-hygiene gate to CI.
