# Project Decomposition & Review Guide

This document outlines how the ARIA project is decomposed into distinct domains to facilitate focused and effective reviews. Instead of attempting to review the entire system at once, contributors and reviewers should focus on these specific areas.

## 1. Core Application Logic (Python)

This domain covers the primary business logic and functionality of the application, excluding the specific MCP layer.

*   **Primary Paths**:
    *   `src/aria_esi/` (root package)
    *   `src/aria_esi/services/` (Business logic, ESI interaction)
    *   `src/aria_esi/commands/` (CLI command implementations)
    *   `src/aria_esi/fitting/` & `src/aria_esi/archetypes/` (EVE specific logic)
    *   `src/aria_esi/core/` (Core utilities)
*   **Review Focus**:
    *   **Code Quality**: Adherence to PEP 8, typing standards (mypy), and project conventions.
    *   **Error Handling**: Robustness in handling API failures or invalid state.
    *   **Architecture**: Separation of concerns between services and presentation.
    *   **Type Safety**: Ensuring gradual typing progression as defined in `pyproject.toml`.

## 2. MCP Integration (Model Context Protocol)

This domain focuses on how ARIA exposes its capabilities to LLMs via the Model Context Protocol.

*   **Primary Paths**:
    *   `src/aria_esi/mcp/`
    *   `.mcp.json`
*   **Review Focus**:
    *   **Protocol Compliance**: Adherence to the MCP specification.
    *   **Tool Definition**: Correct schema definitions for tools.
    *   **Context Management**: How context is assembled and passed to the model.
    *   **Dispatching**: efficient routing of tool calls to underlying services.

## 3. Test Infrastructure & Quality Assurance

This area concerns the safety net of the project: the test suite and its configuration.

*   **Primary Paths**:
    *   `tests/`
    *   `conftest.py` (Global fixtures)
    *   `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage]`)
*   **Review Focus**:
    *   **Coverage**: Identifying gaps in test coverage (aiming for project targets).
    *   **Fixtures**: Reusability and isolation of test fixtures.
    *   **Mocking**: Proper mocking of external dependencies (ESI, file system).
    *   **Performance**: Benchmarks and slow test management.

## 4. Documentation & User Experience

This domain covers all user-facing content, including documentation and the defined AI personas.

*   **Primary Paths**:
    *   `docs/`
    *   `README.md`
    *   `CLAUDE.md`
    *   `personas/`
    *   `dev/` (Developer documentation)
*   **Review Focus**:
    *   **Clarity & Accuracy**: Ensuring docs match current implementation.
    *   **Onboarding**: Ease of setup for new users (`FIRST_RUN.md`).
    *   **Persona consistency**: Voice and tone alignment in `personas/` files.
    *   **Prompt Engineering**: Effectiveness of system prompts and instructions.

## 5. DevOps, Automation & Security

This domain handles the build lifecycle, scripts, dependency management, and security posture.

*   **Primary Paths**:
    *   `.claude/scripts/`
    *   `scripts/`
    *   `aria-init`
    *   `pyproject.toml` (Dependencies, build system)
    *   `SECURITY.md`
*   **Review Focus**:
    *   **Script Robustness**: Error handling and cross-platform compatibility in shell/python scripts.
    *   **Dependency Management**: Reviewing `uv.lock` and `pyproject.toml` updates.
    *   **Security**: Credential handling (keyring integration), secret management, and safe coding practices.

## 6. Data Architecture

This domain concerns how static and dynamic data is organized, validated, and stored.

*   **Primary Paths**:
    *   `reference/` (Static game data)
    *   `userdata/` (User profile structure)
    *   `cache/`
    *   `templates/`
*   **Review Focus**:
    *   **Data Integrity**: Validation of JSON/YAML schemas.
    *   **Isolation**: ensuring user data is properly separated from application logic.
    *   **Caching**: Strategy for caching ESI data and cache invalidation.
    *   **Templates**: Correctness and usability of file templates.
