# Configuration Management Review

Date: 2026-01-28
Updated: 2026-01-28 (post instance-local data paths implementation)

## Scope
Reviewed configuration sources and usage across `src/aria_esi`, `docs/`, `userdata/`, and project root config files. Focus: what is configurable, how users are expected to configure it, and where runtime behavior actually reads configuration.

## Inventory: Configuration Sources & Tunables

### 1) Environment variables (centralized via `AriaSettings`)
**Source:** `src/aria_esi/core/config.py`
**Mechanism:** Pydantic Settings (`env_prefix="ARIA_"`), auto-loads project `.env` via `_find_project_env_file`.

Exposed env vars (with defaults):
- Logging: `ARIA_LOG_LEVEL`, `ARIA_DEBUG`, `ARIA_LOG_JSON`, `ARIA_DEBUG_TIMING`
- Pilot selection: `ARIA_PILOT`
- Optional deps: `ARIA_NO_KEYRING`, `ARIA_NO_RETRY`
- Security break-glass: `ARIA_ALLOW_UNSAFE_PATHS`, `ARIA_ALLOW_UNPINNED`
- MCP policy: `ARIA_MCP_POLICY`, `ARIA_MCP_BYPASS_POLICY`
- MCP universe server: `ARIA_UNIVERSE_GRAPH`, `ARIA_UNIVERSE_LOG_LEVEL`
- RedisQ: `ARIA_REDISQ_ENABLED`, `ARIA_REDISQ_REGIONS`, `ARIA_REDISQ_MIN_VALUE`, `ARIA_REDISQ_RETENTION_HOURS`
- External API key: `ANTHROPIC_API_KEY` (no `ARIA_` prefix)

**Notes:**
- `.env.example` only documents log settings + `ANTHROPIC_API_KEY`.
- ~~Several modules bypass `AriaSettings` and read `os.environ` directly~~ **FIXED:** All data path consumers now use `get_settings()`.

### 2) Data Paths (Instance-Local)
**Source:** `src/aria_esi/core/config.py` computed properties

All data paths are derived from `instance_root` (project root containing `pyproject.toml`):
- `settings.cache_dir` → `{instance_root}/cache/`
- `settings.db_path` → `{instance_root}/cache/aria.db`
- `settings.eos_data_path` → `{instance_root}/cache/eos-data/`
- `settings.killmail_db_path` → `{instance_root}/cache/killmails.db`

**Design:** Single source of truth. No env var overrides for data paths. All consumers use `get_settings()`.

### 3) User-managed JSON configuration
**Primary:** `userdata/config.json`

Observed keys:
- `version` — schema marker (not validated/used at runtime)
- `active_pilot` — used in `core/auth.py` and notification persona loading
- `settings` — documented (`boot_greeting`, `auto_refresh_tokens`, `token_refresh_buffer_minutes`), **not used in code**
- `redisq.context_topology` — used (context-aware topology)
- `redisq.topology` — used (legacy topology)
- `redisq.enabled` — present in sample config, **not used in code**
- `redisq.notifications` — documented in docs, **not used in code**

### 4) User-managed notification profiles (YAML)
**Path:** `userdata/notifications/*.yaml`
**Schema:** `schema_version = 2` in code (`src/aria_esi/services/redisq/notifications/profiles.py`)

Configurable fields (per profile):
- Identity: `name`, `display_name`, `description`, `enabled`
- Delivery: `webhook_url`
- Topology: `topology` (context-aware topology structure)
- Triggers: `watchlist_activity`, `gatecamp_detected`, `high_value_threshold`, `war_activity`, `war_suppress_gatecamp`, `npc_faction_kill` (+ subfields)
- Throttling: `throttle_minutes`
- Quiet hours: `quiet_hours` (enabled, start, end, timezone)
- Commentary: `commentary` (enabled, model, timeout, max tokens, warrant threshold, cost limit, style, max chars, persona)
- Polling/runtime: `polling` (interval, batch_size, overlap window)
- Rate limits: `rate_limit_strategy` (rollup_threshold, max_rollup_kills, backoff)
- Delivery retry: `delivery` (max_attempts, retry_delay)

### 5) User-managed pilot data (Markdown)
**Paths:** `userdata/pilots/{pilot}/profile.md`, `operations.md`, etc.

Observed parsing of `profile.md` (`src/aria_esi/commands/pilot.py` + `services/redisq/notifications/persona.py`):
- `Character Name`, `EVE Experience`, `RP Level`, `Module Tier`, `Primary Faction` (regex-parsed)
- `persona_context` block (used to determine persona voice)
- YAML block for `constraints` (parsed into config dict)

**Note:** `operations.md` is documented for real-time region configuration but not parsed by runtime code.

### 6) Reference configs (committed)
- `reference/data-sources.json` — data integrity/pinning for SDE/EOS/graph
- `reference/mcp-policy.json` — MCP capability policy
- `reference/notification-templates/*.yaml` — notification profile templates

### 7) Repo-level config files
- `.env` / `.env.example` — environment variable configuration
- `.mcp.json` — MCP server invocation
- `.aria-config.json` — legacy config (migrated)

## What Is Exposed Today (and How)

### Environment variables (supported by code)
- Logging & debug (`ARIA_LOG_LEVEL`, `ARIA_DEBUG`, `ARIA_LOG_JSON`, `ARIA_DEBUG_TIMING`)
- Pilot selection (`ARIA_PILOT`)
- Security/feature toggles (`ARIA_NO_KEYRING`, `ARIA_NO_RETRY`, `ARIA_ALLOW_UNSAFE_PATHS`, `ARIA_ALLOW_UNPINNED`, `ARIA_MCP_BYPASS_POLICY`)
- MCP server settings (`ARIA_MCP_POLICY`, `ARIA_UNIVERSE_GRAPH`, `ARIA_UNIVERSE_LOG_LEVEL`)
- RedisQ service controls (`ARIA_REDISQ_ENABLED`, `ARIA_REDISQ_REGIONS`, `ARIA_REDISQ_MIN_VALUE`, `ARIA_REDISQ_RETENTION_HOURS`)
- External API key (`ANTHROPIC_API_KEY`)

### User configuration files (supported by code)
- `userdata/config.json`: `active_pilot`, `redisq.context_topology`, `redisq.topology` (legacy)
- `userdata/notifications/*.yaml`: all notification profile settings
- `userdata/pilots/{pilot}/profile.md`: persona context and profile metadata

### User configuration files (documented but **not** used)
- `userdata/config.json`: `settings.*`, `redisq.enabled`, `redisq.notifications` (docs only)
- `userdata/pilots/{pilot}/operations.md`: real-time region config (docs only)
- `userdata/config.json`: `anthropic.api_key` (docs only)

## Tunables Present in Code That Are Not User-Exposed (Candidates)
These are hard-coded defaults that materially affect behavior, UX, or performance and may need user-facing configuration (possibly under an `advanced` namespace):

**RedisQ / realtime pipeline**
- Poll interval (`RedisQConfig.poll_interval_seconds`)
- Fetch queue rate limits (`KillFetchQueue.MAX_CONCURRENT_FETCHES`, `FETCH_RATE_LIMIT`, `MAX_QUEUE_SIZE`)
- Killmail ingest queue sizing (`BoundedKillQueue(maxsize=1000)`)
- Gatecamp detection thresholds (`GATECAMP_MIN_KILLS`, `GATECAMP_WINDOW_SECONDS`, etc.)
- Pattern detection thresholds (`REPEAT_ATTACKER_MIN_KILLS`, `GANK_ROTATION_MIN_KILLS`, `NPC_FACTION_MIN_KILLS`)
- War inference thresholds (`WAR_INFERENCE_MIN_KILLS`, TTL)

**Market / arbitrage**
- Market cache TTLs (`FUZZWORK_TTL_SECONDS`, `ESI_ORDERS_TTL_SECONDS`, `ESI_HISTORY_TTL_SECONDS`)
- Market refresh TTLs, concurrency, and timeouts
- Arbitrage fee rates (`DEFAULT_BROKER_FEE_PCT`, `DEFAULT_SALES_TAX_PCT`, `V2_*`)

**MCP policy**
- Rate limit (`rate_limit_per_minute`) and audit settings in `reference/mcp-policy.json` are not surfaced in user docs.

## Gaps, Inconsistencies, and UX Risks

~~1) **`.env` is ignored by some modules**~~
   - ~~Modules using `os.environ` directly do not load `.env`, so values defined in `.env` only affect code paths that use `AriaSettings`.~~
   - ~~Affected: `src/aria_esi/mcp/market/database_async.py`, `src/aria_esi/services/killmail_store/sqlite.py`, `scripts/update_eos_data.py`.~~
   - **FIXED:** All data path consumers now use `get_settings()`. Data paths are computed from `instance_root` with no env var overrides.

2) **RedisQ config is split between env and `userdata/config.json` with conflicting docs**
   - Code reads RedisQ enable/regions/min_value/retention only from env (`AriaSettings`).
   - Docs instruct users to set `redisq.enabled` and `redisq.notifications` in `userdata/config.json`, which has no effect.
   - Sample `userdata/config.json` includes `redisq.enabled: true` which is ignored.

3) **Notification system documentation does not match runtime**
   - `docs/REALTIME_CONFIGURATION.md` and `docs/NOTIFICATION_PROFILES.md` describe `redisq.notifications` in `userdata/config.json`.
   - Runtime uses YAML profiles in `userdata/notifications/*.yaml` (schema version 2), including polling/rate-limit/delivery configs.
   - CLI hint for `test-webhook` references config.json instead of profile YAML.

4) **Archetype presets are defined but not applied**
   - `context_topology.archetype` is stored, but presets are never applied in `ContextAwareTopologyConfig.build_calculator`.
   - Docs and CLI suggest adding `archetype`, but it has no effect.

5) **`operations.md` is documented as config input but unused by code**
   - Docs instruct configuring intel regions via `operations.md`; no runtime parsing exists.

~~6) **Killmail store path defaults are inconsistent**~~
   - ~~`SQLiteKillmailStore` defaults to `cache/killmails.db` (repo-local).~~
   - ~~RedisQ poller hardcodes `~/.aria/killmails.db`, bypassing `ARIA_KILLMAIL_DB`.~~
   - **FIXED:** All killmail store consumers now use `get_settings().killmail_db_path` consistently.

7) **Config schema/validation is fragmented**
   - Env config uses Pydantic; YAML profiles have validation; JSON/Markdown config files are parsed ad-hoc without a schema.
   - This increases silent misconfiguration risk.

## Recommendations (Prioritized)

### P0 / High-Impact Fixes
~~1) **Unify config loading for environment variables**~~
   - ~~Replace direct `os.environ` reads with `get_settings()` everywhere; ensure `.env` is honored consistently.~~
   - ~~For scripts, either import `AriaSettings` or load dotenv explicitly.~~
   - **COMPLETE:** All data path consumers use `get_settings()`. Instance-local paths with no env var overrides.

2) **Align RedisQ configuration sources**
   - Decide whether RedisQ controls live in env or `userdata/config.json` (recommended: config.json for persistent user config, env for overrides). Add precedence rules.

3) **Fix documentation & CLI messaging to match runtime**
   - Update docs to reflect YAML notification profiles.
   - Update `test-webhook` and other hints to reference `userdata/notifications/*.yaml`.

### P1 / UX & Correctness Improvements
4) **Apply archetype presets when `context_topology.archetype` is set**
   - Use `apply_preset()` during config load to merge defaults.

5) **Define & validate JSON/Markdown schemas**
   - Add a Pydantic model or JSON schema for `userdata/config.json`.
   - Consider a structured front-matter block in `profile.md` instead of regex parsing.

6) **Clarify `operations.md` usage**
   - Either implement parsing for intel regions or remove/move the docs to avoid misleading users.

~~7) **Normalize DB path defaults**~~
   - ~~Ensure `SQLiteKillmailStore` uses `settings.effective_*` and respects `ARIA_KILLMAIL_DB` consistently.~~
   - **COMPLETE:** All DB paths use `get_settings()` computed properties.

### P2 / Advanced Configuration
8) **Expose advanced RedisQ tuning knobs**
   - Add optional `redisq.advanced` settings for poll interval, fetch queue limits, gatecamp thresholds, and pattern detection.

9) **Expose market/arbitrage tuning**
   - Allow per-pilot or global config for broker fees, sales tax, and cache TTLs (advanced only).

10) **Document all env vars and configuration sources**
   - Expand `.env.example` and add a single "Configuration Reference" doc that covers env + file-based settings with precedence rules.

## Suggested Target Configuration Model
- **Global config:** `userdata/config.json`
  - `active_pilot`
  - `redisq` (enable, filters, retention, context_topology, advanced tuning)
  - `security` (read-only flags, no break-glass options)
- **Per-profile config:** `userdata/notifications/*.yaml`
- **Per-pilot config:** `userdata/pilots/{pilot}/profile.md` (structured front-matter)
- **Environment variables:** overrides + sensitive API keys + break-glass flags
- **Data paths:** Instance-local (`{instance_root}/cache/`), not user-configurable

---

## Change Log

### 2026-01-28: Instance-Local Data Paths Implementation
**Branch:** `feature/instance-local-data-paths`

**Changes:**
1. All data paths now derive from `instance_root` (project root):
   - `cache/aria.db` - Market database
   - `cache/eos-data/` - EOS fitting data
   - `cache/killmails.db` - Killmail store

2. Removed env var overrides for data paths:
   - ~~`ARIA_EOS_DATA`~~
   - ~~`ARIA_DB`~~
   - ~~`ARIA_KILLMAIL_DB`~~

3. All consumers now use `get_settings()` computed properties:
   - `settings.db_path`
   - `settings.eos_data_path`
   - `settings.killmail_db_path`
   - `settings.cache_dir`

4. Migrated existing data from `~/.aria/` to `cache/`

**Rationale:** Single source of truth for data paths. Enables isolated multi-instance deployments. Eliminates configuration fragmentation.

---

### 2026-01-28: Configuration Management Improvements

**Branch:** `feature/configuration-management-improvements`

**Changes:**

1. **P1.4 Archetype Presets Applied:**
   - Modified `ContextAwareTopologyConfig.build_calculator()` to apply presets
   - Added `_to_mergeable_dict()` and `_from_merged()` helper methods
   - User's `context_topology.archetype` setting now affects topology filtering

2. **P0.3 Documentation Aligned:**
   - Updated `docs/REALTIME_CONFIGURATION.md` to reference YAML profiles
   - Removed legacy `redisq.notifications` JSON format documentation
   - Added migration instructions for legacy config users
   - Documented the intentional split between env vars and config.json

3. **P0.2 RedisQ Config Split Documented:**
   - Added "Configuration Sources" section explaining the split
   - Env vars = deployment/runtime overrides
   - config.json = persistent user preferences
   - YAML profiles = per-channel notification routing

4. **P1.6 operations.md Clarified:**
   - Added explicit documentation in `docs/DATA_FILES.md`
   - Clarified that operations.md is human-readable context, NOT parsed
   - Pointed users to `context_topology` for structured configuration

5. **Notifications Migrate Command:**
   - Added `notifications migrate` CLI command
   - Migrates legacy `redisq.notifications` to YAML profile
   - Added deprecation warning to `test-webhook` command

6. **Config Cleanup:**
   - Removed misleading `redisq.enabled` from `userdata/config.json`
   - Updated `docs/NOTIFICATION_PROFILES.md` with v2 operational schema fields

**Deferred:**
- P1.5 Schema Validation: Pydantic schemas for config.json deferred to future work

---

This review focuses on configuration correctness and UX. It intentionally does not attempt to refactor behavior; it highlights where behavior and docs diverge, and where user intent is currently ignored.
