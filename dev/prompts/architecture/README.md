# Architecture Prompts

This directory contains prompts for high-level design analysis, refactoring strategies, and architectural reviews. Use these prompts to ensure consistency with the project's design patterns and modular structure.

## Contents

| File | Purpose |
|------|---------|
| `system_design.md` | Review system boundaries, modularity, dependency direction, and separation of concerns |
| `mcp_architecture.md` | Review MCP dispatcher contracts, tool schemas, and server behavior |
| `llm_integration.md` | Review LLM integration patterns: prompting, tool use, MCP, Claude Code Skills extension |
| `context_management.md` | Review context lifecycle: token budgeting, state management, tool output handling |
| `accretion_auditor.md` | Identify high-complexity/low-utility accretions and produce a remove-or-simplify plan |
| `python.md` | Python code quality review: types, async, error handling, testing, tooling |

## Intended Use
- Reviewing major feature proposals
- Planning refactors of core services
- Ensuring alignment with ADRs (Architecture Decision Records)
- Assessing LLM integration patterns before significant changes
- Validating Python code quality during code review
