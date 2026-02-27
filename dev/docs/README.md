# Developer Documentation

Developer-focused documentation for ARIA contributors.

## Guides

| Document | Description |
|----------|-------------|
| [PYTHON_ENVIRONMENT.md](PYTHON_ENVIRONMENT.md) | Python/uv setup, credential security, keyring backends |
| [TESTING.md](TESTING.md) | Test tiers, coverage, fixtures, pytest markers |
| [TYPING_ROADMAP.md](TYPING_ROADMAP.md) | Type checking phases and status |

## Architecture & Internals

| Document | Description |
|----------|-------------|
| [CONTEXT_POLICY.md](CONTEXT_POLICY.md) | MCP context management, output limits, singleton patterns |
| [SESSION_CONTEXT.md](SESSION_CONTEXT.md) | Session initialization and boot hooks |
| [DATA_SOURCES.md](DATA_SOURCES.md) | External data source registry and caching policy |
| [PERSONA_LOADING.md](PERSONA_LOADING.md) | Persona loading internals, overlay resolution, security delimiters |

## Contributing

| Document | Description |
|----------|-------------|
| [CONTRIBUTING_SKILLS.md](CONTRIBUTING_SKILLS.md) | How to create a new skill |
| [CONTRIBUTING_PERSONAS.md](CONTRIBUTING_PERSONAS.md) | How to create a new persona |
| [MCP_DEVELOPMENT.md](MCP_DEVELOPMENT.md) | Adding MCP dispatcher actions |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Developer quick start (clone to first test) |

## AI Runtime Instructions

Documents in [ai-runtime/](ai-runtime/) are read by the LLM during sessions, not by humans:

| Document | Description |
|----------|-------------|
| [DATA_TRUST.md](ai-runtime/DATA_TRUST.md) | Data trust hierarchy, verification rules, cache authority |
| [SESSION_BEHAVIOR.md](ai-runtime/SESSION_BEHAVIOR.md) | Data volatility, file paths, experience adaptation, command suggestions |
