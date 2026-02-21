# Developer Getting Started

Clone-to-first-test-run guide for ARIA contributors.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://www.python.org/) |
| uv | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Claude Code | Latest | [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code) |
| git | 2.x+ | Your package manager |

**Alternative: DevContainer.** If you have Docker Desktop, you can skip local setup entirely. Open the repo in VS Code, click "Reopen in Container", and you get Python 3.13, uv, and all dev tools pre-installed. See [DEPLOYMENT.md](../../docs/DEPLOYMENT.md) for details.

## Setup

```bash
# Clone the repository
git clone git@github.com:LuminaireCognition/aria.git
cd aria

# Install dependencies (creates .venv automatically)
uv sync
```

That's it. No `.env` file is needed for development — tests use mocks and don't require API keys.

## Run Tests

```bash
# Fast unit tests (start here)
uv run pytest -m unit

# Unit + integration (no API calls)
uv run pytest -m "not tier2 and not tier3"

# Full suite, parallel execution
uv run pytest -n auto
```

All tests should pass on a fresh clone. If they don't, check [TESTING.md](TESTING.md) for troubleshooting.

## Project Layout

```
aria/
├── .claude/
│   ├── hooks/              # Session lifecycle hooks
│   ├── scripts/            # Utility scripts (index builder, preflight, etc.)
│   └── skills/             # 48 slash commands (see skills/README.md)
│
├── src/aria_esi/
│   ├── commands/           # CLI commands (aria-esi <command>)
│   ├── mcp/                # MCP server (6 dispatchers)
│   │   ├── dispatchers/    # universe, market, sde, skills, fitting, status
│   │   ├── market/         # Market tools and database
│   │   ├── sde/            # Static Data Export tools
│   │   └── fitting/        # Ship fitting engine
│   ├── core/               # Shared core (auth, client, path security)
│   └── services/           # Business logic services
│
├── personas/               # 5 faction AI personas + shared resources
├── reference/              # Static game data (mechanics, archetypes, PvE intel)
├── userdata/               # Per-pilot profiles and credentials (gitignored)
├── docs/                   # User-facing documentation
├── dev/                    # Developer docs, decisions, proposals, archives
└── tests/                  # pytest test suite
```

For the full architecture overview, see [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md).

## Key Development Commands

```bash
# Type checking
uv run mypy .

# Regenerate skill index after modifying SKILL.md frontmatter
uv run python .claude/scripts/aria-skill-index.py

# Validate skill dependencies
uv run python .claude/scripts/aria-skill-preflight.py --all

# Rebuild topology cache (after modifying config)
uv run aria-esi topology-build

# Recompile persona context (after changing faction/rp_level)
uv run aria-esi persona-context
```

## MCP Server Development

The MCP server runs inside Claude Code sessions. For local development:

```bash
# Run the MCP server directly (for testing outside Claude Code)
uv run aria-mcp

# Run MCP-specific tests
uv run pytest tests/mcp/ -m tier1
```

Dispatcher source: `src/aria_esi/mcp/dispatchers/`. See [MCP_DEVELOPMENT.md](MCP_DEVELOPMENT.md) for adding new actions.

## Where to Find Things

| Question | Document |
|----------|----------|
| How do I create a new skill? | [CONTRIBUTING_SKILLS.md](CONTRIBUTING_SKILLS.md) |
| How do I create a new persona? | [CONTRIBUTING_PERSONAS.md](CONTRIBUTING_PERSONAS.md) |
| How do I add an MCP action? | [MCP_DEVELOPMENT.md](MCP_DEVELOPMENT.md) |
| What are the test tiers? | [TESTING.md](TESTING.md) |
| What's the typing policy? | [TYPING_ROADMAP.md](TYPING_ROADMAP.md) |
| How does context management work? | [CONTEXT_POLICY.md](CONTEXT_POLICY.md) |
| What external data sources exist? | [DATA_SOURCES.md](DATA_SOURCES.md) |
| How does the boot sequence work? | [SESSION_CONTEXT.md](SESSION_CONTEXT.md) |
| Architecture decisions? | [dev/decisions/](../decisions/README.md) |

## Next Steps

- Read [CONTRIBUTING.md](../../CONTRIBUTING.md) for contribution guidelines and PR process
- Browse [.claude/skills/README.md](../../.claude/skills/README.md) for the skill directory
- Check [dev/decisions/](../decisions/README.md) for architecture decision records
