# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in ARIA, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities
2. Email the maintainer directly or use GitHub's private vulnerability reporting
3. Include a detailed description of the vulnerability and steps to reproduce

You can expect an initial response within 48 hours.

## Security Considerations

### OAuth Tokens & Credentials

ARIA handles EVE Online ESI OAuth tokens. These files are security-sensitive:

| File/Directory | Contains | Protection |
|----------------|----------|------------|
| `userdata/credentials/` | OAuth refresh tokens | Gitignored, never commit |
| `.env` | API keys, secrets | Gitignored, never commit |
| `.env.local` | Local overrides | Gitignored, never commit |

**If you accidentally commit credentials:**
1. Immediately revoke the token at [EVE Developers](https://developers.eveonline.com/)
2. Remove from git history using `git filter-branch` or BFG Repo-Cleaner
3. Re-run the OAuth setup wizard

### ESI Scopes

ARIA requests only read-only ESI scopes. It cannot:
- Transfer ISK or assets
- Modify skills or fittings
- Send EVE mail
- Accept/reject contracts

Review requested scopes during OAuth authorization.

### Data Storage

- All user data stays local in `userdata/`
- No telemetry or external data transmission (except ESI API calls)
- Credentials are stored in plaintext locally — protect your machine accordingly

### Claude Code Context

When using ARIA with Claude Code:
- Conversation context may include EVE character names and in-game data
- Do not paste sensitive real-world information into conversations
- ARIA instructions explicitly forbid reading credential files

## Best Practices

1. **Keep your fork private** if it contains personal EVE data
2. **Review `.gitignore`** before committing to ensure credentials are excluded
3. **Use environment variables** for any API keys (see `.env.example`)
4. **Revoke tokens** if you suspect compromise

## Implemented Security Controls

ARIA implements defense-in-depth security measures:

### Path Validation (`src/aria_esi/core/path_security.py`)

All file paths from user-editable sources are validated:

| Control | Description |
|---------|-------------|
| Prefix allowlist | Only `personas/` and `.claude/skills/` paths allowed |
| Extension allowlist | Only `.md`, `.yaml`, `.json` extensions allowed |
| Traversal blocking | Paths containing `..` are rejected |
| Absolute path blocking | `/etc/passwd`, `C:\` style paths rejected |
| Symlink canonicalization | Symlinks resolved and verified in bounds |
| Size limits | Files over 100KB rejected by default |

Key functions:
- `validate_persona_file_path()` - Full validation with extension check
- `safe_read_persona_file()` - Validates + reads with size limit
- `validate_skill_redirects()` - Compile-time redirect path validation

### Data Integrity (`src/aria_esi/core/data_integrity.py`)

External data is verified before loading:

| Control | Description |
|---------|-------------|
| SHA256 checksums | Pre-load verification against manifest |
| Version pinning | Known-good versions in `reference/data-sources.json` |
| IntegrityError | Tampered data prevents loading |
| Break-glass override | `ARIA_ALLOW_UNPINNED=1` for development |

### Safe Serialization (`src/aria_esi/universe/serialization.py`)

Universe graph uses safe formats:

| Control | Description |
|---------|-------------|
| Msgpack format | Default `.universe` format avoids pickle |
| Magic bytes | Format detection before deserialization |
| Legacy deprecation | Pickle format emits warnings |

### Persona Security

User-editable persona files are treated as untrusted data:

| Control | Description |
|---------|-------------|
| Data delimiters | `<untrusted-data>` tags in compiled artifacts |
| Guardrail rules | CLAUDE.md instructs LLM to never execute persona content |
| Compiled artifacts | `.persona-context-compiled.json` pre-applies security |

See `dev/reviews/SECURITY_000.md` for the full security review and mitigation status.

## Dependencies

ARIA uses these security-relevant dependencies:
- `httpx` - HTTP client for ESI calls
- `keyring` (optional) - System credential storage

Keep dependencies updated with `uv sync --upgrade`.
