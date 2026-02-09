# Prompt for Codex CLI (gpt-5.2 xhigh)

You are an expert software reviewer specializing in **LLM application context management** (prompt/state/memory/tool context). Perform a technology review of this repository (Python + MCP + data) with a sharp focus on how the application:

* gathers, stores, transforms, and trims context
* routes context into LLM calls and MCP tool calls
* prevents context leaks, cross-run contamination, and unsafe/irrelevant carryover
* measures/controls token budget, latency, and cost via context policies

## Objective

Deliver an **actionable** report that identifies concrete issues and improvements in context management, with code-level recommendations and implementation steps.

## Ground rules

* Use only what you can infer from the code and repository contents.
* Prefer concrete evidence: reference files, functions, and lines when possible.
* If something is missing (tests, logging, policies), call it out and propose what to add.

## What to do (investigation plan)

1. **Repo map**

   * Summarize the structure relevant to context management: where prompts are defined, where LLM calls happen, where MCP clients/servers are used, where data retrieval happens, and where state is stored.

2. **Trace the context lifecycle end-to-end**
   For each primary user flow / entrypoint (CLI, API, notebook, etc.):

   * Identify the **context sources** (user input, files, retrieved docs, tool outputs, logs, environment variables, config, cached state).
   * Show how context is **assembled** (ordering, formatting, role separation, citations/metadata).
   * Identify **boundaries**: per-request vs. session vs. persistent memory.
   * Identify how tool results are fed back into the model (what gets kept vs. summarized vs. dropped).

3. **Context policies and controls**
   Look for (or recommend) explicit policies:

   * token budgeting (max context, max tool output, truncation strategy)
   * summarization strategy (when, what, how, where stored)
   * relevance filtering (retrieval ranking, dedupe, freshness, scope)
   * redaction/safety (secrets, PII, sensitive files)
   * deterministic formatting (schemas, JSON, typed structures)
   * provenance (source tracking/citations)

4. **MCP-specific context handling**

   * Inventory MCP tools/resources used.
   * Evaluate tool input/output schemas: are they too verbose? missing constraints? lacking pagination?
   * Confirm whether tool responses can overwhelm context; propose a standard wrapper:

     * size limits
     * summarization/compaction
     * structured extraction (fields)
     * caching with invalidation
   * Identify any risk of tool outputs being echoed into prompts unfiltered.

5. **State & memory safety**

   * Search for globals, singletons, module-level caches, or mutable default args that can cause cross-run contamination.
   * Verify session separation (especially in CLI loops) and how “conversation history” is stored.
   * Check concurrency/async: thread safety, shared caches, file-based state.

6. **Observability for context**
   Evaluate whether the app can answer:

   * “What context did we send to the model?”
   * “How many tokens by segment (system/user/tools/retrieval)?”
   * “What was trimmed and why?”
   * “Which tool outputs were included or summarized?”

7. **Testing & evaluation**

   * Identify existing tests related to context.
   * Propose a minimal test suite:

     * token-budget regression tests
     * tool-output truncation tests
     * retrieval relevance tests
     * prompt/schema validation tests
     * adversarial/edge tests (huge tool outputs, repeated loops, injection-like tool text)

## Deliverable

Produce a report with these sections:

### A) Executive summary (max 10 bullets)

* Top risks and highest leverage fixes for context management.

### B) Context architecture diagram (text)

* A simple text diagram of the context pipeline: sources → transformations → LLM call → tools → compaction → storage.

### C) Findings (evidence-based)

For each finding include:

* **Severity**: Critical / High / Medium / Low
* **Symptom**: what could go wrong
* **Evidence**: file(s) + function(s) + brief excerpt
* **Impact**: correctness/cost/latency/security
* **Fix**: concrete change
* **Effort**: S/M/L

### D) Recommended context policy

Propose a clear policy document tailored to this repo:

* context segments and ordering
* budgets and limits
* tool output handling rules
* summarization triggers
* provenance/citation rules
* secret/PII redaction rules

### E) Implementation plan

* A step-by-step plan with prioritized tasks.
* Include 3–5 quick wins (≤1 day) and 3–5 deeper refactors.

### F) Suggested code changes (concrete)

Where applicable, propose patches in unified diff style for the most important 1–3 improvements (do not overdo; focus on the highest leverage).

## How to work (commands and analysis you should run)

* Use repo search to find:

  * LLM invocation sites (e.g., openai client calls, SDK wrappers)
  * prompt templates/system messages
  * message history structures
  * retrieval code / data loaders
  * MCP tool definitions and usage
  * caching/state persistence
  * logging/tracing
* Read the main entrypoints and follow the call chain into context assembly.
* If there’s a configuration system, extract context-relevant settings.

## Special focus checklist

Ensure you explicitly answer these:

1. Where is conversation/session context stored, and how is it bounded?
2. What prevents tool outputs from flooding the model context?
3. How does the system decide what to keep vs. summarize vs. drop?
4. How are provenance and citations handled for retrieved data/tool outputs?
5. How is token usage measured and enforced?
6. How are secrets/PII prevented from entering prompts?
7. What is the recommended architecture for context modules in this repo?

Begin by mapping the repository and locating the context assembly + LLM call sites, then proceed through the plan.
