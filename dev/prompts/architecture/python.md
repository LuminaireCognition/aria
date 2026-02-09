# Prompt for Codex CLI: Python code quality review for an LLM-integrated application

You are a senior Python engineer with deep experience building and maintaining **LLM-integrated applications** (agent/tooling systems, MCP/tool servers, RAG pipelines, evaluation harnesses). Review this repository's **Python code** for correctness, clarity, maintainability, and modern best practices.

## Scope

* Python source only (including any MCP server/client code written in Python)
* Include config, CLI entrypoints, packaging, tests, and developer tooling as they relate to Python quality
* Treat this as a production-oriented codebase that must be safe, reliable, and easy to extend

## Workflow

1. Identify all Python packages/modules, entrypoints, and execution paths.
2. Build a dependency and responsibility map (what each module owns, what it imports).
3. Review file-by-file for quality issues and modernization opportunities.
4. Recommend concrete changes with file:line references and patch-ready snippets.

Use `rg`, `find`, reading files, and lightweight local checks (no network assumed). If pyproject tooling exists, run what's available (e.g., `python -m compileall`, unit tests).

## Deliverable: Markdown report

### 1) Codebase map

* Key modules/packages and what they do
* Entrypoints (CLI, scripts) and main flows
* Where LLM calls/tooling are orchestrated

### 2) Python quality assessment (deep)

For each category below, provide:

* Findings with evidence: `path/to/file.py:Lx-Ly`
* Why it matters (impact)
* Exactly what to change (repo-specific)

Categories:

* **Architecture & separation of concerns**: boundaries, layering, coupling, circular imports
* **API design**: function/class responsibilities, interfaces, docstrings, naming
* **Type hints**: coverage, correctness, use of `typing`/`collections.abc`, generics, protocols
* **Static analysis readiness**: mypy/pyright compatibility, `typing_extensions`, `__all__`
* **Datamodels & validation**: `pydantic`/dataclasses, input validation, structured outputs
* **Error handling**: exceptions, error taxonomy, retryable vs fatal, context-rich errors
* **Async vs sync correctness**: event loop usage, concurrency safety, cancellation, timeouts
* **Resource management**: files, subprocesses, network clients, context managers
* **Logging & observability**: structured logging, log levels, correlation ids, redaction
* **Configuration**: env var parsing, defaults, config objects, `.env` usage, secret handling
* **Testing**: unit/integration boundaries, mocks for LLM/tooling, golden tests, fixtures
* **Performance**: hot paths, caching, batching, token budgeting hooks (if applicable)
* **Security & safety** (Python-level): path traversal, command injection, unsafe deserialization

### 3) Priority-ranked action list

A table with:

* Priority (P0/P1/P2)
* Change description
* Files to touch
* Effort (S/M/L)
* Benefit and risk reduced

### 4) Patch-ready recommendations

For the **top 3** highest-impact improvements, include:

* Proposed diff-style snippets or new module skeletons
* Suggested type signatures
* Any new tests to add

### 5) Tooling & standards proposal

Propose a modern baseline for this repo (only if missing), including:

* `pyproject.toml` configuration for formatting/linting/type-checking (e.g., ruff, mypy/pyright)
* Pre-commit hooks
* CI recommendations (fast checks vs full suite)

Keep it minimal and incremental; prefer conventions that match the repo's current style.

## Rubric and scoring

Score each area 0–5 with a short justification:

* Code clarity
* Type safety
* Testability
* Reliability (timeouts/retries/cancellation)
* Security hygiene
* Maintainability

## Constraints

* Be specific and evidence-based; avoid generic Python advice.
* Recommend changes that are realistic to implement.
* If something is missing, state it explicitly and propose the smallest scaffolding that adds value.

Start by producing the Codebase map, then proceed through sections in order.
