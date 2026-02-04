# CODEX 5.2 xhigh Review: LLM-Integrated Python Practices (ARIA ESI)

**Reviewer:** Codex 5.2 xhigh  
**Date:** 2026-01-26  
**Scope:** Python runtime (`src/aria_esi`), MCP tool layer, `.claude` tooling, and LLM-facing tests

---

## Executive Summary

ARIA demonstrates strong LLM integration fundamentals: tool capability gating, structured outputs with metadata, context budgets, and explicit prompt-injection defenses. The MCP layer is especially well-designed for deterministic, schema-backed outputs. The main gaps are lifecycle integration (compiled persona context is generated but not used during session initialization), inconsistent provenance metadata in `_meta`, and a lack of centralized input/error validation for LLM-provided parameters.

---

## Good Practices Observed

### 1) Tool Safety & Capability Gating
- **Capability policy engine with sensitivity tiers** helps reduce blast radius for prompt-injection failures. (`src/aria_esi/mcp/policy.py`)
- **Audit logging with trace context** is built in for security incident reconstruction. (`src/aria_esi/mcp/policy.py`, `src/aria_esi/mcp/context.py`)

### 2) Output Stability & Context Management
- **Standardized output wrappers** add `_meta` with counts, truncation flags, and timestamps. (`src/aria_esi/mcp/context.py`)
- **Byte-level output enforcement** reduces runaway tool outputs and stabilizes LLM context usage. (`src/aria_esi/mcp/context.py`)
- **Centralized per-domain limits** prevent drift between tools. (`src/aria_esi/mcp/context_policy.py`)

### 3) Prompt Injection Mitigations
- **Persona compiler wraps untrusted data** with `<untrusted-data>` delimiters and integrity hashes. (`src/aria_esi/persona/compiler.py`)
- **Path allowlists + validation** prevent directory traversal and unsafe file loading. (`src/aria_esi/core/path_security.py`)
- **Context sanitization** strips directives and unsafe patterns before LLM exposure, with test coverage. (`.claude/scripts/aria-context-assembly.py`, `tests/test_context_sanitization.py`)

### 4) Observability & Operational Hygiene
- **Structured logging with JSON option** improves machine parsing and trace correlation. (`src/aria_esi/core/logging.py`)
- **Context budgets tracked per tool output** keep multi-call conversations predictable. (`src/aria_esi/mcp/context_budget.py`)

### 5) Testing for LLM-Facing Outputs
- **Golden snapshot tests** for tool outputs stabilize LLM consumption. (`tests/skills/test_skill_outputs.py`)
- **Coverage of security sanitization logic** ensures hardening remains intact. (`tests/test_context_sanitization.py`)

---

## Recommendations (Prioritized)

### 1) Use the compiled persona context as the default session artifact (High) ✅ RESOLVED
**Why it matters:** The compiler already produces an integrity-hashed, delimiter-wrapped context that is safer for LLM ingestion. However, session initialization still loads raw persona files directly, bypassing the compiled artifact's hardening. This creates an avoidable injection surface and duplicates file I/O.
**Evidence:** `src/aria_esi/persona/compiler.py` produces `.persona-context-compiled.json`, but `CLAUDE.md` instructs loading `persona_context.files` directly.

**Status (2026-01-26):** `CLAUDE.md` Session Initialization step 4 now specifies loading `.persona-context-compiled.json` as the primary path, with raw file loading as fallback only when artifact is missing.

### 2) Standardize `_meta.source`/`_meta.as_of` across dispatchers (Medium)
**Why it matters:** LLM responses need provenance to reason about freshness and trust. The metadata model supports it, but many dispatchers do not pass source/as_of into `wrap_output`, leaving `_meta` incomplete even when the payload contains provenance fields.  
**Evidence:** `OutputMeta` in `src/aria_esi/mcp/context.py` supports `source`/`as_of`, but `market` outputs call `wrap_output(...)` without those fields (e.g., `src/aria_esi/mcp/dispatchers/market.py`).

### 3) Reset context budgets per LLM turn (Medium) — DOCUMENTED AS DESIGN
**Why it matters:** The budget logic is described as per-turn, but no runtime resets appear in the MCP entrypoints. Without reset, budgets accumulate across unrelated tool calls, producing misleading warnings and discouraging follow-up queries.
**Evidence:** `reset_context_budget()` is defined in `src/aria_esi/mcp/context_budget.py` but not referenced elsewhere.

**Status (2026-01-26):** `docs/CONTEXT_POLICY.md` now explicitly documents this as a design decision: budget tracking is advisory-only and accumulates across session. The `reset_context_budget()` function remains available for future use but is intentionally not called in production. See commit `1af2cee`.

### 4) Centralize tool input validation for LLM-provided parameters (Medium)
**Why it matters:** LLMs frequently emit invalid or out-of-range values. Some dispatchers perform manual checks, but coverage is uneven. A shared Pydantic input model (or `@validate_call`) would make failures predictable and reduce scattered validation logic.  
**Evidence:** Dispatcher functions accept many optional parameters without common validation scaffolding (e.g., `src/aria_esi/mcp/dispatchers/universe.py`).

### 5) Standardize error payloads for LLM consumption (Low)
**Why it matters:** LLM orchestration benefits from consistent error schemas for retries or user guidance. The helper `create_error_meta()` exists but is not used by dispatchers, leading to inconsistent error shapes.  
**Evidence:** `create_error_meta()` in `src/aria_esi/mcp/context.py` is unused.

---

## LLM Integration Scorecard (1–5)

| Area | Score | Notes |
|------|:-----:|-------|
| Prompt Injection Defense | 5 | Delimiters + path validation + sanitization tests are strong. |
| Tool Output Stability | 4 | Wrappers and byte limits are excellent; provenance metadata inconsistent. |
| Input Validation | 3 | Partial manual checks; no unified validation layer. |
| Observability | 4 | Structured logs + trace context are good; budget reset lifecycle needs wiring. |
| Testing & Regression | 4 | Golden tests exist, but focus on expanding to more actions. |

---

## Suggested Next Steps (30–60 days)

1. ~~Wire session initialization to load compiled persona context artifacts instead of raw files.~~ ✅ Done
2. Add a small helper to enforce `_meta.source`/`_meta.as_of` for dispatchers that already compute provenance.
3. ~~Call `reset_context_budget()` at the start of each LLM turn or tool invocation batch.~~ — Documented as advisory-only design
4. Introduce Pydantic input schemas for the highest-traffic tool actions (route, market prices, fitting stats).
5. Standardize errors using `create_error_meta()` in dispatcher exception handling paths.

---

## Conclusion

ARIA already reflects many of the strongest practices for LLM-integrated Python services: deterministic tool outputs, security hardening, and explicit capability controls. The remaining work is primarily about *consistency* and *lifecycle integration*—ensuring that existing security/metadata mechanisms are used uniformly and reset appropriately across turns. Addressing the recommendations above would push the system toward best-in-class reliability and safety for LLM-driven workflows.
