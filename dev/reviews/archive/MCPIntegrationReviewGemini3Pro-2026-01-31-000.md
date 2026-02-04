# MCP Integration Review

**Reviewer:** Gemini 3 Pro
**Date:** 2026-01-31
**Scope:** `src/aria_esi/mcp/` and `.mcp.json`

## Executive Summary

The MCP implementation in ARIA is architecturally mature and sophisticated. The decision to use a **Dispatcher Pattern**—grouping ~45 tools into 6 domain-specific dispatchers—is a strong design choice that effectively manages context window pressure. The supporting infrastructure for context budgeting, output truncation, and policy enforcement is robust.

However, the complexity of these dispatchers (specifically the argument density) and the lifecycle management of the context budget present potential risks for a public release.

## Strengths (Brief)

*   **Dispatcher Architecture:** significantly reduces the number of tools exposed to the LLM, likely improving tool selection accuracy.
*   **Context Management:** `OutputMeta`, `summarize_route`, and `ContextBudget` provide excellent safeguards against context overflow.
*   **Documentation:** Tool docstrings (e.g., in `universe.py`) are high-quality, providing clear schemas and examples for the LLM.
*   **Policy Engine:** Fine-grained access control with sensitivity levels and audit logging (`policy.py`) is a standout feature for enterprise/secure usage.

## Critical Findings & Recommendations

### 1. Dispatcher Argument Complexity
**Risk:** High
**Observation:** The `universe` dispatcher (`src/aria_esi/mcp/dispatchers/universe.py`) defines a single tool with over 30 parameters to support 14 distinct actions. While Python handles this fine, some LLMs may struggle with such a dense signature, potentially leading to hallucinated arguments or parameter bleeding (e.g., passing `security_min` to an action that ignores it).
**Recommendation:**
*   **Validation:** Ensure strict validation inside the dispatcher to reject arguments that are irrelevant to the selected `action`. The current implementation checks strict validity of `action` and some params, but might silently ignore others.
*   **Testing:** Verify `tier1` tests cover "mixed" argument scenarios to ensure no cross-talk between actions.

### 2. Context Budget Lifecycle
**Risk:** Medium
**Observation:** `ContextBudget` relies on `contextvars` to track usage "within a conversation turn." However, `reset_context_budget()` exists but its invocation trigger in the `FastMCP` server lifecycle is not immediately obvious.
**Recommendation:**
*   **Verify Reset:** Confirm that `reset_context_budget()` is called at the start of each request (or conversation turn). If `FastMCP` treats every JSON-RPC request as a new async task, `contextvars` will isolate requests, but they won't persist "cumulative" usage across *multiple* tool calls if the model treats them as a single turn (unless the server state is explicitly managed).
*   **Middleware:** Consider implementing a middleware or decorator at the `Server` level to guarantee budget initialization and cleanup for every request.

### 3. Policy Configuration Path
**Risk:** Low
**Observation:** `DEFAULT_POLICY_PATH` in `src/aria_esi/mcp/policy.py` is calculated using `Path(__file__).parent...`. This relative path assumption is brittle and may break if the package is installed in a zipped format or a different environment structure (e.g., via `pip install`).
**Recommendation:**
*   **Use Resources:** Switch to `importlib.resources` (or `pkg_resources`) to locate the default `mcp-policy.json` file reliably within the installed package.

### 4. Dependency Management
**Risk:** Low
**Observation:** `pyproject.toml` lists `mcp>=1.0.0`. Ensure this version aligns with the usage of `mcp.server.fastmcp.FastMCP`.
**Recommendation:**
*   **Lock Version:** Verify `uv.lock` ensures a compatible version of the `mcp` SDK is used in production.

## Action Plan
1.  **Refactor Path Handling:** specific to `policy.py` to use `importlib.resources`.
2.  **Audit Budget Reset:** Trace the execution path in `server.py` to ensure `reset_context_budget` is effectively utilized.
3.  **Strict Parameter Validation:** Add a utility to `dispatcher` base logic to warn or fail if non-applicable parameters are passed for a specific `action`.
