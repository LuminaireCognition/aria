# Python Environment

> **CRITICAL:** Always use `uv run` for Python execution. Never use bare `python`, `python3`, or `pip`.

## Credential Security

ARIA stores ESI credentials using a two-tier security model:

| Tier | Storage | Security Level |
|------|---------|----------------|
| II | System keyring (macOS Keychain, GNOME Keyring, Windows Credential Manager) | OS-encrypted, user-protected |
| I | JSON file with 0600 permissions | File-system protected only |

**Default behavior:** ARIA attempts Tier II storage first. If no keyring backend is available, it falls back to Tier I with a warning.

### Keyring Backends by Platform

- **macOS:** Built-in Keychain (no extra setup required)
- **Windows:** Credential Manager (no extra setup required)
- **Linux:** Requires one of: GNOME Keyring, KWallet, or SecretService-compatible backend

### Headless Servers

On servers without a desktop environment, no keyring backend may be available. Options:

1. **Accept Tier I storage** - Ensure proper file permissions (0600 is set automatically)
2. **Set `ARIA_NO_KEYRING=1`** - Suppress security warnings
3. **Install `keyrings.alt`** - For file-based encrypted storage (see [keyring docs](https://pypi.org/project/keyring/))

### Migration

To migrate existing plaintext credentials to keyring:

```bash
uv run aria-esi migrate-keyring
```

To check current storage status:

```bash
uv run aria-esi migrate-keyring --info
```

## Quick Reference

```bash
# ARIA ESI CLI (preferred method)
uv run aria-esi <command> [args]

# Run Python scripts
uv run python .claude/scripts/script.py

# Run tests
uv run pytest
```

## ARIA ESI CLI

The project provides the `aria-esi` command-line tool for ESI operations. This is installed as a package entry point.

**Always invoke via `uv run`:**

```bash
# Get help
uv run aria-esi --help

# Example commands
uv run aria-esi route Jita Amarr --safe
uv run aria-esi borders --system Masalle --limit 25
uv run aria-esi loop Sortet --target-jumps 20 --min-borders 3
uv run aria-esi price "Tritanium" --jita
uv run aria-esi pilot me
uv run aria-esi skillqueue
uv run aria-esi wallet-journal --days 7
```

### Universe Navigation Commands

These commands use the pre-built universe graph for fast lookups:

```bash
# Route between systems (supports --safe, --shortest, --risky)
uv run aria-esi route Dodixie Jita --safe

# Find high-sec systems bordering low-sec
uv run aria-esi borders --system Masalle --limit 10
uv run aria-esi borders --region "Verge Vendor"

# Plan circular mining route through border systems
uv run aria-esi loop Sortet --target-jumps 20 --min-borders 3

# Loop with security constraint and avoidance
uv run aria-esi loop Jita --security highsec --avoid Uedama Niarja

# Graph management
uv run aria-esi graph-build    # Build graph from cache
uv run aria-esi graph-verify   # Verify graph integrity
uv run aria-esi graph-stats    # Show graph statistics
```

**DO NOT use these patterns** (they will fail or use wrong Python):

```bash
# WRONG - invokes system Python, module not found
python -m aria_esi borders --system Masalle
python3 -m aria_esi borders --system Masalle

# WRONG - requires manual PYTHONPATH
cd .claude/scripts && python3 -m aria_esi ...
```

## Running Scripts

For standalone scripts in `.claude/scripts/`:

```bash
# OAuth setup
uv run python .claude/scripts/aria-oauth-setup.py

# ESI sync
uv run python .claude/scripts/aria-esi-sync.py

# Token refresh
uv run python .claude/scripts/aria-token-refresh.py
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_foo.py

# Run with coverage
uv run pytest --cov

# Run specific test
uv run pytest tests/test_foo.py::test_specific_function
```

**Alternative - use venv binaries directly:**

```bash
.venv/bin/pytest
.venv/bin/python script.py
```

## What NOT to Do

- **Never use bare `python`, `python3`, or `pytest`** - invokes system Python, wrong environment
- **Never run `pip install`** - use `uv add <package>` or `uv sync`
- **Never create a new virtual environment** - one exists at `.venv/`
- **Never run `source .venv/bin/activate`** - `uv run` handles this
- **Never use `cd` + `python -m`** - use `uv run aria-esi` instead

## Managing Dependencies

```bash
# Install all dependencies (including dev)
uv sync --all-extras

# Add a new dependency
uv add <package>

# Add a dev dependency
uv add --optional dev <package>
```

## Why uv?

- `uv run` automatically uses the correct Python and virtual environment
- No need to activate/deactivate environments
- Faster than pip for package resolution
- Lockfile (`uv.lock`) ensures reproducible installs
