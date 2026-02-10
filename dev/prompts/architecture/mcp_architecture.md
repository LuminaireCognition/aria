<!-- owner: @anthropic/aria -->
<!-- last_reviewed: 2026-02-10T00:00:00Z -->
<!-- depends_on: [] -->
<!-- adjacent_prompts: ["architecture/system_design.md", "testing/coverage_quality.md"] -->

# MCP Server Contracts and Dispatcher Behavior Review

Review this repository from the perspective of a **senior engineer specializing in MCP (Model Context Protocol) server design**, evaluating dispatcher contracts, tool schemas, and server behavior.

## Scope

**In-scope (MCP architecture):**

* MCP server configuration and registration (`.mcp.json`, server entrypoints)
* Dispatcher action routing: correctness, completeness, parameter validation
* Tool schema design: input/output contracts, type safety, documentation
* Response formatting: truncation, pagination, error propagation to model/client
* Transport and connection handling (stdio, SSE, lifecycle)
* Idempotency and safe defaults for tool invocations

**Out-of-scope:**

* CI policy design and pipeline reliability (see `cicd/pipeline_quality.md`)
* Documentation information architecture quality (see `docs/onboarding_first_run_ux.md`)
* Broader system modularity beyond MCP (see `architecture/system_design.md`)

## Adjacent Prompts

* `architecture/system_design.md` — broader system design; this prompt focuses on MCP-specific contracts
* `testing/coverage_quality.md` — test coverage; this prompt evaluates MCP behavioral contracts

## Deep-Dive Triggers

This prompt is selected for deep-dive when changes touch:

* `src/aria_esi/mcp/**`
* `.mcp.json`

## How to Run the Review

Examine MCP server and dispatcher implementations:

* Map all registered tools and their action routing
* Verify input validation occurs before any external calls (ESI, SDE)
* Check response schemas match documented contracts
* Evaluate error handling and propagation to callers
* Review transport configuration for security and reliability

## Deliverables

For each finding include:

* Severity (Critical / High / Medium / Low / Info)
* File path and line range
* What is wrong
* Why it matters
* Specific fix

Produce:

1. Tool registry inventory (tools, actions, schemas)
2. Contract violation findings
3. Validation gap analysis
4. Error propagation assessment
5. Actionable recommendations ranked by priority

## Output

Emit findings in `prompt_results.schema.v1`.
