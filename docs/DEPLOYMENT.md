# Deployment & Installation

This guide covers installing ARIA for both end users and developers.

## Quick Install (Recommended)

For most users, install via uv:

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install ARIA (when published to PyPI)
uv tool install aria-esi
```

## Development Install

For contributors or those wanting the latest code:

```bash
# Clone the repository
git clone https://github.com/yourusername/aria.git
cd aria

# Install dependencies with uv
uv sync

# Verify installation
uv run aria-esi --version
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

After installation, run the setup wizard:

```bash
uv run aria-esi setup
```

This will:
1. Create your pilot profile directory
2. Configure your character identity
3. Optionally set up ESI authentication

For detailed first-run guidance, see [FIRST_RUN.md](FIRST_RUN.md).

## ESI Authentication (Optional)

To enable ESI features (skills, wallet, assets, etc.):

```bash
uv run aria-esi auth
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

### Via uv tool

```bash
uv tool upgrade aria-esi
```

### Development Install

```bash
cd aria
git pull
uv sync
```

## Uninstalling

### Via uv tool

```bash
uv tool uninstall aria-esi
```

### Development Install

Simply delete the cloned directory. Your `userdata/` is preserved unless you delete it.

## Troubleshooting

### "Command not found: aria-esi"

Ensure uv's bin directory is in your PATH:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Python Version Issues

ARIA requires Python 3.10+. Check your version:
```bash
python --version
```

### Dependency Conflicts

Use uv's isolated environments:
```bash
uv sync --reinstall
```

### ESI Token Expiry

Re-authenticate if tokens expire:
```bash
uv run aria-esi auth --refresh
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ARIA_CONFIG_DIR` | Override config directory | `./userdata` |
| `ARIA_LOG_LEVEL` | Logging verbosity | `INFO` |
| `ESI_CLIENT_ID` | Custom ESI application | (bundled) |

## Related Documentation

- [FIRST_RUN.md](FIRST_RUN.md) - Detailed first-time setup
- [ESI.md](ESI.md) - ESI authentication details
- [PYTHON_ENVIRONMENT.md](PYTHON_ENVIRONMENT.md) - Developer environment setup
- [MULTI_PILOT_ARCHITECTURE.md](MULTI_PILOT_ARCHITECTURE.md) - Multiple character support
