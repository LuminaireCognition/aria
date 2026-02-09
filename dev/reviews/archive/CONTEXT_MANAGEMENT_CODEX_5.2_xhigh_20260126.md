# Context Management Review: Codex 5.2 xhigh (2026-01-26)

**Scope:** LLM request context handling (session context assembly, persona loading, MCP tool outputs, and LLM commentary prompts)

## Findings (ordered by severity)

1) **High — "Hard limit triggers automatic summarization" is documented but not implemented.** ✅ RESOLVED
- **Evidence:** `docs/CONTEXT_POLICY.md:35-36` states the 100 KB hard limit triggers automatic summarization, but `src/aria_esi/mcp/context_budget.py:59-95` only returns warnings and `src/aria_esi/mcp/context.py:762-780` only attaches those warnings to `_meta`.
- **Impact:** Multi-tool turns can exceed the budget with no enforced compaction, increasing noise and pushing LLM context toward overload even when the policy says it should be summarized.
- **Recommendation:** Add a hard-limit enforcement hook (e.g., in `log_context()` or a higher-level MCP response wrapper) to summarize or trim outputs when `hard_limit_exceeded` is true. If automatic summarization is not desired, update the policy to match behavior.

**Status (2026-01-26):** Documentation updated in commit `1af2cee`. `docs/CONTEXT_POLICY.md:36` now reads: "**Hard limit:** 100 KB (advisory warning, no automatic enforcement)" and line 274 explicitly states these are advisory signals only. Policy now matches implementation.

2) **Medium — Context budgets are never reset per conversation turn.** — DOCUMENTED AS DESIGN
- **Evidence:** `reset_context_budget()` exists in `src/aria_esi/mcp/context_budget.py:129-136`, but no call sites exist in the codebase (no usage outside the module).
- **Impact:** Budget warnings can accumulate across unrelated tool calls, causing persistent "budget_warning" metadata even for small responses, which degrades signal and discourages follow-up queries.
- **Recommendation:** Invoke `reset_context_budget()` at the start of each LLM turn or at the entrypoint that batches tool calls for a user request.

**Status (2026-01-26):** `docs/CONTEXT_POLICY.md:268` now explicitly documents this as intentional: "`reset_context_budget()` is available but not currently called in production. Budget accumulates across all tool calls in a session." This is a design decision—the function remains available for future use if per-turn resets become desirable.

3) **Medium — Session context can exceed its declared size budget and includes low-signal fields.**
- **Evidence:** `docs/CONTEXT_POLICY.md:7-15` caps Session Context at 2 KB, but `.claude/scripts/aria-context-assembly.py:406-446` loads every project file and stores `active_projects`, `completed_projects`, and `abandoned_projects`. Each project includes an absolute `path` and `pilot_directory` (`.claude/scripts/aria-context-assembly.py:290-417`). There is no size or count cap.
- **Impact:** A pilot with many projects will bloat `.session-context.json`, diluting signal and possibly pushing context size beyond the intended budget. Absolute paths also add noise and leak local filesystem structure into LLM context.
- **Recommendation:** Limit session context to the top N active projects (sorted by recency), drop `completed_projects` and `abandoned_projects` from the LLM-facing artifact, and remove absolute `path`/`pilot_directory` fields or replace with relative identifiers. Enforce a byte-size cap (e.g., 2 KB) with truncation metadata.

4) **Low/Medium — Scalar outputs bypass byte-size enforcement.**
- **Evidence:** `wrap_scalar_output()` in `src/aria_esi/mcp/context.py:376-408` only attaches `_meta` and does not enforce `GLOBAL.MAX_OUTPUT_SIZE_BYTES`. In contrast, list outputs are byte-limited via `_enforce_output_bytes()`.
- **Impact:** Large scalar payloads (nested dicts, verbose stats) can exceed the per-tool size guard, increasing LLM context noise in a way that list outputs avoid.
- **Recommendation:** Add optional byte enforcement to `wrap_scalar_output()` (or a shared `_enforce_output_bytes` pass for all outputs) and set `_meta.byte_limit_enforced` when truncation happens.

5) **Low — LLM commentary prompts accept unbounded notification text.**
- **Evidence:** `src/aria_esi/services/redisq/notifications/prompts.py:38-99` interpolates `notification_text` and pattern descriptions without truncation.
- **Impact:** If notification formatting expands (e.g., adding item lists or long attacker summaries), prompt size will grow unpredictably, lowering signal-to-noise and increasing latency/cost.
- **Recommendation:** Apply a conservative character cap to `notification_text` and `patterns_description`, optionally adding a “(truncated)” indicator for transparency.

## Open Questions / Assumptions
- I assumed `.session-context.json` is ingested directly into LLM context as-is. If a downstream loader already filters or truncates it, that would reduce the severity of finding #3.
- I did not find an MCP entrypoint that resets budgets or enforces cross-call summarization; if this exists outside the repo (e.g., in orchestration tooling), findings #1–2 may be partially mitigated.

## Change Summary

### Addressed
- ✅ **Finding 1:** Documentation updated to clarify hard limit is advisory-only (commit `1af2cee`)
- ✅ **Finding 2:** Documented as intentional design—budget accumulation is expected behavior

### Remaining (lower priority)
- **Finding 3:** Cap session context size and remove low-signal fields (low priority—typical usage is <5 projects)
- **Finding 4:** Enforce byte limits for scalar outputs (medium priority)
- **Finding 5:** Bound notification text in LLM commentary prompts (low priority—inputs are internally generated)
