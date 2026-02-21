# Deployment & Installation

This guide covers installing ARIA.

## Prerequisites

- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** with an active [Anthropic API plan](https://console.anthropic.com/)
- **[uv](https://docs.astral.sh/uv/)** (Python package manager)
- **Python 3.11+**
- **An EVE Online account** (any faction, Alpha or Omega)

## Install

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/LuminaireCognition/aria.git
cd aria

# Run the setup wizard
./aria-init

# Launch ARIA
claude
```

### Optional Dependencies

Install extras for additional functionality:

```bash
# Enhanced retry logic (tenacity)
uv sync --extra resilient

# Ship fitting simulation (EOS vendored)
uv sync --extra fitting

# All optional features
uv sync --extra full

# Development tools (testing, linting)
uv sync --extra dev
```

## First Run

The setup wizard handles everything:

```bash
./aria-init
```

This will:
1. Install dependencies (runs `uv sync`)
2. Create your pilot profile directory
3. Configure your character identity and faction
4. Generate all required data files
5. Download game data caches (~100MB, requires internet) — SDE database, fitting engine, market prices, sovereignty map, persona context

Use `--skip-seed` to defer the download, or `--seed-only` to run just the seeding step later.

For detailed first-run guidance, see [FIRST_RUN.md](FIRST_RUN.md).

## ESI Authentication (Optional)

ARIA works fully without ESI. To enable live character data (skills, wallet, assets, etc.):

```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

Follow the browser prompts to authorize your EVE character. See [ESI.md](ESI.md) for scope details.

## Configuration Files

After setup, your files will be in:

```
userdata/
  config.json              # Active pilot selection
  pilots/
    _registry.json         # Pilot directory registry
    {pilot_id}_{name}/
      profile.md           # Pilot identity and preferences
      operations.md        # Ship roster and activities
```

## MCP Server (Claude Code Integration)

ARIA includes an MCP server for Claude Code integration:

```bash
# Start MCP server (typically done automatically)
uv run aria-universe
```

Configure in `.mcp.json`:
```json
{
  "mcpServers": {
    "aria-universe": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "aria-universe"]
    }
  }
}
```

## Upgrading

```bash
cd aria
git pull
uv sync
```

After major updates (especially SDE schema changes), re-seed game data:
```bash
./aria-init --seed-only
```

## Uninstalling

Simply delete the cloned directory. Your `userdata/` is preserved unless you delete it.

## Troubleshooting

### "Command not found: aria-esi"

Ensure uv's bin directory is in your PATH:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Python Version Issues

ARIA requires Python 3.11+. Check your version:
```bash
# Checking system Python version (not running ARIA code, so bare python is fine here)
python --version
# or
uv python list
```

### Dependency Conflicts

Use uv's isolated environments:
```bash
uv sync --reinstall
```

### ESI Token Expiry

Refresh the token:
```bash
.claude/scripts/aria-refresh
```

If refresh fails, re-run the OAuth setup wizard:
```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ARIA_CONFIG_DIR` | Override config directory | `./userdata` |
| `ARIA_LOG_LEVEL` | Logging verbosity | `INFO` |
| `ESI_CLIENT_ID` | Custom ESI application | (bundled) |

## Credential Security

ARIA stores ESI credentials using a two-tier model:
- **Tier II**: System keyring (macOS Keychain, GNOME Keyring, Windows Credential Manager)
- **Tier I**: JSON file with 0600 permissions (fallback)

On headless servers, set `ARIA_NO_KEYRING=1` to suppress warnings.

For full details on keyring backends and migration, see [dev/docs/PYTHON_ENVIRONMENT.md](../dev/docs/PYTHON_ENVIRONMENT.md).

## Related Documentation

- [FIRST_RUN.md](FIRST_RUN.md) - Detailed first-time setup
- [ESI.md](ESI.md) - ESI authentication details
- [PYTHON_ENVIRONMENT.md](../dev/docs/PYTHON_ENVIRONMENT.md) - Developer environment setup
- [MULTI_PILOT_ARCHITECTURE.md](MULTI_PILOT_ARCHITECTURE.md) - Multiple character support
