# Security Review: Prompt Injection & LLM Integration (ARIA)

**Review Date:** 2026-02-03
**Created On:** 2026-02-03
**Scope:** Prompt injection defenses, persona/skill loading, MCP tool boundaries, and Claude Code integration safety.
**Reviewer Lens:** Security engineer focused on injection, and LLM-integrated application engineering experience.
**Generated With:** OpenAI Codex (GPT-5)
**Generation Prompt (verbatim):** “As a security engineer with good understanding of prompt injection and a software engineer with good Claude Code and LLM-integated application experience, review this project and write a report to ./dev/reviews/.”

---

## Executive Summary

ARIA has strong, explicit guardrails for untrusted data and a growing set of technical controls (path validation, context sanitization, MCP policy gating, and output size limits). The largest remaining risks are around enforcement gaps: some guardrails are still conceptual or rely on the model following instructions rather than being enforced in code, and there are a few places where the “secure by default” posture can be tightened.

**Top risks to address next:**
1. Persona compilation does not enforce extension or size limits (despite having a safe reader available), allowing oversized or unintended file types into the compiled context.
2. Compiled persona artifacts include an integrity hash but are never verified on load, so manual tampering can bypass untrusted-data wrapping.
3. ~~MCP policy defaults allow authenticated actions, which increases the blast radius if prompt injection causes tool calls.~~ ✅ **RESOLVED**
4. ~~Claude tool permissions still allow raw `python3`/`python -m` usage, contrary to the `uv run` policy.~~ ✅ **RESOLVED**

---

## What’s Working Well

- **Prompt injection hardening in context assembly** is implemented and tested, including sanitization and alias validation. See `.claude/scripts/aria-context-assembly.py` and `tests/test_context_sanitization.py`.
- **Persona context compilation** wraps files in `<untrusted-data>` delimiters with integrity hashes. See `src/aria_esi/persona/compiler.py`.
- **Path traversal protection** is centralized and used for persona paths. See `src/aria_esi/core/path_security.py` and `src/aria_esi/commands/persona.py`.
- **MCP capability policy** is implemented and enforced by dispatchers. See `src/aria_esi/mcp/policy.py` and `src/aria_esi/mcp/dispatchers/*`.
- **Tool output size controls** are enforced in `wrap_output`/`wrap_output_multi`. See `src/aria_esi/mcp/context.py`.

---

## Findings

### 1) Persona compiler bypasses extension + size safety checks

**Severity:** Medium
**Likelihood:** Medium
**Status:** ✅ **RESOLVED** (2026-02-03)

**Risk:** The persona compiler reads files with only prefix-based validation. Extension allowlisting and size limits (which exist) are not enforced. A malicious or oversized file under `personas/` or `.claude/skills/` could be compiled into the persona context, inflating context or introducing unwanted content.

**Evidence:**
- Persona compiler uses `validate_persona_path()` and `read_text()` directly. `src/aria_esi/persona/compiler.py`.
- Safe reader and extension checks exist but are unused: `safe_read_persona_file()` and `validate_persona_file_path()` in `src/aria_esi/core/path_security.py`.

**Recommendation:**
- Update `PersonaCompiler._load_and_compile_file()` to use `safe_read_persona_file()` so extension allowlists and size limits are enforced uniformly.
- Consider setting a stricter max file size for persona content (e.g., 25–50KB per file) to avoid context bloat.

**Resolution:**
- Updated `PersonaCompiler._load_and_compile_file()` to use `safe_read_persona_file()` instead of manual path validation and file reading
- Set persona-specific max file size to 50KB (`PERSONA_MAX_FILE_SIZE = 50_000`) to prevent context bloat
- Extension allowlist enforced: only `.md`, `.yaml`, `.json` files are permitted
- Added 9 new tests in `tests/test_persona.py::TestPersonaCompilerSecurity` covering:
  - Extension rejection (`.py`, `.sh` blocked)
  - Extension allowance (`.md`, `.yaml`, `.json` allowed)
  - Size limit enforcement (>50KB rejected)
  - Graceful degradation (invalid files skipped during compilation)

---

### 2) Compiled persona artifact integrity is not verified at load

**Severity:** Medium
**Likelihood:** Low–Medium
**Status:** ✅ **RESOLVED** (2026-02-03)

**Risk:** The compiled artifact includes hashes but there is no verification step before loading. If `.persona-context-compiled.json` is modified (removing delimiters, injecting instructions), the session start instructions in `CLAUDE.md` will still load it.

**Evidence:**
- `compile_persona_context()` computes and stores `integrity` hashes but there is no validation function or boot-time verification. `src/aria_esi/persona/compiler.py`.
- Session startup instructions explicitly load `.persona-context-compiled.json` without verification. `CLAUDE.md`.

**Recommendation:**
- Add a verification step in the boot sequence (e.g., in `.claude/hooks/aria-boot.sh` or a new `aria-verify-persona-context` script) that recomputes hashes from source files and rejects or regenerates the artifact on mismatch.
- Optionally sign compiled artifacts or store a detached hash in a write-protected location.

**Resolution:**
- Added `verify_persona_artifact()` function to `src/aria_esi/persona/compiler.py` that:
  - Verifies stored `raw_content` hash matches stored integrity hash (catches direct tampering)
  - Re-reads source files and compares hashes against stored values (catches modification)
  - Detects missing source files
  - Returns detailed verification result with issues list
- Added `cmd_verify_persona_context` CLI command (`uv run aria-esi verify-persona-context`)
  - Supports `--regenerate` flag to auto-fix on verification failure
- Integrated verification into boot sequence in `.claude/hooks/aria-boot.d/boot-operations.sh`:
  - `run_artifact_verification()` runs before security validation
  - Tampering detection blocks boot with `ARTIFACT TAMPERING` error
  - Missing artifact generates warning (fresh install case)
- Added 8 new tests in `tests/test_persona.py::TestPersonaArtifactVerification` covering:
  - Valid artifact verification
  - Missing artifact detection
  - Source file modification detection
  - Direct artifact tampering detection
  - Delimiter removal detection
  - Missing source file detection
  - Malformed artifact handling

---

### 3) MCP policy defaults allow authenticated actions

**Severity:** Medium
**Likelihood:** Medium
**Status:** ✅ **RESOLVED** (2026-02-03)

**Risk:** The default policy file allows `authenticated` actions. If the model is prompt-injected and tokens are present, authenticated data could be accessed without explicit opt-in.

**Evidence:**
- Policy file includes `"authenticated"` in `allowed_levels`: `reference/mcp-policy.json`.
- Policy engine loads this file by default: `src/aria_esi/mcp/policy.py`.

**Recommendation:**
- Change the default policy file to allow only `public`, `aggregate`, and `market`, and require explicit user opt-in for `authenticated` (and any future `restricted`) levels.
- For authenticated actions that are user-facing, consider a "confirm/deny" flow in the skill or dispatcher layer.

**Resolution:**
- Removed `authenticated` from `allowed_levels` in `reference/mcp-policy.json`
- Added `require_confirmation` policy field for sensitivity levels that need user consent
- Added `ConfirmationRequired` exception in `src/aria_esi/mcp/policy.py` (distinct from `CapabilityDenied`)
- Updated `check_capability()` to raise `ConfirmationRequired` when action sensitivity is in `require_confirmation`
- Updated fitting dispatcher to handle `ConfirmationRequired` gracefully with fallback to all-V skills
- Added 8 new tests in `tests/mcp/test_policy.py` covering confirmation flow

---

### 4) Claude permissions allow raw Python execution (contradicts `uv run` policy)

**Severity:** Medium
**Likelihood:** Medium
**Status:** ✅ **RESOLVED** (2026-02-03)

**Risk:** `.claude/settings.local.json` allows `python3:*` and `python -m pytest:*` while `CLAUDE.md` requires `uv run`. This increases the blast radius if a prompt injection succeeds (e.g., running arbitrary Python outside the expected environment).

**Evidence:**
- Permission allowlist includes `Bash(python3:*)` and `Bash(python -m pytest:*)`. `.claude/settings.local.json`.
- `CLAUDE.md` explicitly says to use `uv run` and avoid bare Python. `CLAUDE.md`.

**Recommendation:**
- Remove raw Python and pip permissions and keep only `uv run` wrappers.
- Add a small boot preflight check that fails fast if prohibited commands are still allowed.

**Resolution:**
- Removed `Bash(python3:*)` and `Bash(python -m pytest:*)` from `.claude/settings.local.json`
- Only `uv run` wrappers are now permitted: `Bash(uv run python:*)`, `Bash(uv run pytest:*)`, `Bash(uv run aria-esi:*)`

---

### 5) Killmail tools are not classified in default sensitivity map

**Severity:** Low
**Likelihood:** Medium
**Status:** ✅ **RESOLVED** (2026-02-03)

**Risk:** `killmails` actions default to `PUBLIC` sensitivity because they are missing from `DEFAULT_ACTION_SENSITIVITY`. This reduces policy clarity and makes fine-grained allow/deny controls less effective.

**Evidence:**
- Dispatcher calls `check_capability("killmails", action)` but no default sensitivity mapping exists. `src/aria_esi/mcp/dispatchers/killmails.py`, `src/aria_esi/mcp/policy.py`.

**Recommendation:**
- Add a `killmails` entry to `DEFAULT_ACTION_SENSITIVITY` (likely `aggregate`).
- Consider adding `killmails.*` overrides in the policy file if you want opt-in control.

**Resolution:**
- Added `killmails` entry to `DEFAULT_ACTION_SENSITIVITY` in `src/aria_esi/mcp/policy.py`:
  - `query`: AGGREGATE (killmail data is aggregated public zKillboard data)
  - `stats`: AGGREGATE
  - `recent`: AGGREGATE
- Added 5 new tests in `tests/mcp/test_policy.py::TestKillmailsSensitivity` covering:
  - Each action has correct AGGREGATE sensitivity
  - Actions allowed by default policy
  - Actions denied when AGGREGATE not in allowed_levels

---

## Suggested Next Steps

1. ~~Apply safe persona file reads with size + extension limits in `PersonaCompiler`.~~ ✅ Done
2. ~~Add persona artifact verification to the boot workflow.~~ ✅ Done
3. ~~Tighten default MCP policy to exclude `authenticated` until explicitly enabled.~~ ✅ Done
4. ~~Reduce Claude tool permissions to align with `uv run` policy.~~ ✅ Done
5. ~~Classify `killmails` in sensitivity map for policy clarity.~~ ✅ Done

**All findings resolved.**

---

## Overall Risk Rating

- **Prompt Injection Risk:** Low (extension + size limits enforced, artifact integrity verified at boot) ✅ Resolved
- **Tool/MCP Abuse Risk:** Low (policy enforced, all dispatchers classified, authenticated actions require confirmation) ✅ Resolved
- **Operational Robustness:** High (solid context controls, integrity verification, and comprehensive tests) ✅ Resolved

**All identified security findings have been remediated.**

---

## Remediation Progress

| Finding | Status | Date |
|---------|--------|------|
| #1 Persona compiler bypasses | ✅ Resolved | 2026-02-03 |
| #2 Artifact integrity not verified | ✅ Resolved | 2026-02-03 |
| #3 MCP authenticated defaults | ✅ Resolved | 2026-02-03 |
| #4 Raw Python permissions | ✅ Resolved | 2026-02-03 |
| #5 Killmails sensitivity map | ✅ Resolved | 2026-02-03 |

**Progress: 5/5 findings resolved (100%)** ✅
