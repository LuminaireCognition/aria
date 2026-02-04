# Instance-Local Data Paths Proposal

**Status:** ✅ COMPLETE (2026-02-02)
**Implemented:** ARIA_INSTANCE_ROOT, computed path properties, all defaults instance-local

---

## Summary
Multi-instance clones (e.g., `instance0/`, `instance1/`) should keep all defaults inside the repo, in gitignored directories. Today, several defaults write to `~/.aria`, which creates shared state across clones. This proposal moves default paths to project-local locations and adds an optional `ARIA_INSTANCE_ROOT` override for users who want custom layouts.

## Findings (outside-project defaults)

### Persistent, default outside-root storage
- EOS data defaults to `~/.aria/eos-data`.
  - `src/aria_esi/core/config.py:268`
  - `src/aria_esi/fitting/eos_data.py:29`
- Market database defaults to `~/.aria/aria.db`.
  - `src/aria_esi/core/config.py:275`
  - `src/aria_esi/mcp/market/database.py:30`
  - `src/aria_esi/mcp/market/database_async.py:52`
- RedisQ killmail store defaults to `~/.aria/killmails.db`.
  - `src/aria_esi/services/redisq/poller.py:174`
  - `src/aria_esi/mcp/dispatchers/killmails.py:52`
  - `src/aria_esi/mcp/dispatchers/status.py:243`

### Ephemeral outside-root paths
- SDE importer uses system temp dir: `tempfile.gettempdir()/aria_sde`.
  - `src/aria_esi/mcp/sde/importer.py:63`
- EOS seed commands use `tempfile.TemporaryDirectory()`.
  - `src/aria_esi/commands/fitting.py:281`

### Configurable paths that may point outside root (acceptable, user-directed)
- `ARIA_EOS_DATA`, `ARIA_DB`, `ARIA_KILLMAIL_DB`, `ARIA_MCP_POLICY`, `ARIA_UNIVERSE_GRAPH`.
  - `src/aria_esi/core/config.py` (fields)
  - `src/aria_esi/services/killmail_store/sqlite.py:61`
  - `src/aria_esi/mcp/policy.py:242`
  - `src/aria_esi/mcp/server.py:52`

### Docs referencing `~/.aria`
- `docs/REALTIME_CONFIGURATION.md:287` (log path)
- Docstrings/examples in: `src/aria_esi/core/config.py`, `src/aria_esi/mcp/market/database.py`, `src/aria_esi/mcp/market/database_async.py`, `src/aria_esi/mcp/fitting/tools_status.py`.

## Goals
- Defaults are instance-local (inside repo) and gitignored.
- Support `ARIA_INSTANCE_ROOT` for power users; keep explicit path overrides working.
- Avoid surprises: one clone never writes into another clone unless configured.

## Recommended Path Forward

### 1) Introduce an instance root concept
Add `ARIA_INSTANCE_ROOT` in settings, defaulting to the project root.
- The root should be resolved once (e.g., by finding `pyproject.toml`).
- If `ARIA_INSTANCE_ROOT` is set, all default paths resolve under it.

### 2) Standardize instance-local default layout
Use existing gitignored directories:
- `cache/` already ignored in `.gitignore`.
- `userdata/` already ignored with `.gitkeep`.

Proposed defaults:
- Market DB: `cache/aria.db`
- EOS data: `cache/eos-data/`
- Killmail store: `cache/killmails.db`
- RedisQ logs (if/when a file handler is used): `cache/logs/redisq.log`

Rationale:
- `cache/` is already the default for runtime caches (see `.gitignore`).
- Keeps heavy, auto-generated data out of `userdata/` (which tends to be user-auth data).

### 3) Centralize path resolution in config
Add computed properties to `AriaSettings`:
- `instance_root`
- `effective_eos_data_path` (already exists, but update default)
- `effective_db_path` (already exists, but update default)
- `effective_killmail_db_path` (new)
- `effective_log_path` (optional, if file logging is adopted)

All runtime code should depend on these instead of hardcoding `Path.home() / ".aria"`.

### 4) Replace hardcoded `~/.aria` in runtime code
Targets:
- `src/aria_esi/services/redisq/poller.py`
- `src/aria_esi/mcp/dispatchers/killmails.py`
- `src/aria_esi/mcp/dispatchers/status.py`
- `src/aria_esi/mcp/market/database.py` (default DB)
- `src/aria_esi/mcp/market/database_async.py` (default DB)
- `src/aria_esi/fitting/eos_data.py` (default EOS data)

### 5) Update docs and examples
- Replace `~/.aria/...` with instance-local defaults (e.g., `cache/...`).
- Ensure docs mention `ARIA_INSTANCE_ROOT` and explicit overrides.

### 6) Migration / backward compatibility
Keep explicit overrides as-is. For defaults:
- Prefer instance-local paths.
- Optionally: if a legacy `~/.aria/` data file exists and the new default does not, emit a warning and suggest copying into `cache/`. Avoid silently using `~/.aria` as the default to keep clones isolated.

## Implementation Outline
1) Add `ARIA_INSTANCE_ROOT` to `AriaSettings` and a helper to resolve project root.
2) Update `effective_*` defaults in `src/aria_esi/core/config.py`.
3) Create a new `effective_killmail_db_path` and use it in RedisQ + MCP dispatchers.
4) Update EOS seed CLI command to use settings or computed defaults.
5) Update docs and docstrings for new defaults.
6) Add/adjust tests to validate new defaults.

## Risks / Notes
- Users relying on `~/.aria` will need a migration path. Clear warnings and a simple copy step should be sufficient.
- Temp directories remain OS-level (expected), but all persistent state becomes instance-local by default.

## Outcome
Cloned repos become isolated instances by default while still allowing power users to centralize data via `ARIA_INSTANCE_ROOT` or per-path overrides.
