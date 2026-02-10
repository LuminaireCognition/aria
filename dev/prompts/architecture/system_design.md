<!-- owner: @anthropic/aria -->
<!-- last_reviewed: 2026-02-10T00:00:00Z -->
<!-- depends_on: [] -->
<!-- adjacent_prompts: ["architecture/mcp_architecture.md", "cicd/release_and_rollback.md"] -->

# System Design and Modularity Review

Review this repository from the perspective of a **senior systems architect** evaluating system boundaries, modularity, and separation of concerns.

## Scope

**In-scope (system design):**

* Module boundaries and dependency direction (are imports clean and acyclic?)
* Layering: does the architecture separate data access, business logic, and presentation?
* Interface contracts between modules (function signatures, data classes, protocols)
* Configuration management (centralized vs scattered, environment handling)
* Error propagation strategy (exception hierarchy, error codes, boundary handling)
* Extensibility points (plugin interfaces, hook systems, registration patterns)

**Out-of-scope:**

* Dependency licensing and supply chain security (see `security/supply_chain_and_dependencies.md`)
* Prompt-injection controls and AI security posture (see `security/audit_ai.md`)
* MCP-specific dispatcher contracts (see `architecture/mcp_architecture.md`)
* CI/CD pipeline design (see `cicd/pipeline_quality.md`)

## Adjacent Prompts

* `architecture/mcp_architecture.md` — MCP-specific architecture; this prompt covers broader system design
* `cicd/release_and_rollback.md` — release engineering; this prompt covers in-code modularity

## How to Run the Review

Examine the repository structure, imports, and module boundaries:

* Map the dependency graph between packages under `src/`
* Identify circular dependencies or layer violations
* Evaluate whether interfaces are explicit (protocols, ABCs) or implicit
* Check configuration loading patterns for consistency
* Review error handling at module boundaries

## Deliverables

For each finding include:

* Severity (Critical / High / Medium / Low / Info)
* File path and line range
* What is wrong
* Why it matters
* Specific fix

Produce:

1. Module dependency map (concise)
2. Boundary violation findings
3. Interface contract assessment
4. Configuration management assessment
5. Actionable recommendations ranked by priority

## Output

Emit findings in `prompt_results.schema.v1`.
