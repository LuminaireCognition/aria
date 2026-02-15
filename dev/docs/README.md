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

## AI Runtime Instructions

Documents in [ai-runtime/](ai-runtime/) are read by the LLM during sessions, not by humans:

| Document | Description |
|----------|-------------|
| [DATA_VERIFICATION.md](ai-runtime/DATA_VERIFICATION.md) | Rules for verifying game data claims |
| [DATA_AUTHORITY.md](ai-runtime/DATA_AUTHORITY.md) | Data source hierarchy for caching |
| [PROTOCOLS.md](ai-runtime/PROTOCOLS.md) | Data volatility tiers and freshness rules |
| [EXPERIENCE_ADAPTATION.md](ai-runtime/EXPERIENCE_ADAPTATION.md) | Calibrating explanation depth |
| [COMMAND_SUGGESTIONS.md](ai-runtime/COMMAND_SUGGESTIONS.md) | Progressive disclosure for slash commands |
| [DATA_FILES.md](ai-runtime/DATA_FILES.md) | File path reference for pilot data |
