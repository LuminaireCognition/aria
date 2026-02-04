# Python Code Quality Review: ARIA ESI

**Reviewer:** Claude Opus 4.5
**Date:** 2026-01-23
**Updated:** 2026-01-24 (status tracking)
**Scope:** Full Python codebase review for LLM-integrated application

---

## 1) Codebase Map

### Key Modules/Packages

```
src/aria_esi/
├── __main__.py           # CLI entrypoint (argparse-based with dynamic subparser registration)
├── core/                 # Infrastructure layer
│   ├── auth.py           # Two-tier credential management (keyring + file)
│   ├── client.py         # ESI HTTP client with retry/timeout
│   ├── retry.py          # Tenacity-based exponential backoff with jitter
│   ├── logging.py        # Structured logging with JSON output support
│   ├── formatters.py     # ISK/duration/number formatting utilities
│   ├── constants.py      # Game constants (trade hubs, ship groups)
│   ├── data_integrity.py # SHA256 checksum verification
│   └── keyring_backend.py # Secure credential storage
│
├── models/               # Pydantic data models
│   ├── fitting.py        # Ship fitting models (13.6KB)
│   ├── market.py         # Market/arbitrage models (40.3KB, most complex)
│   └── sde.py            # Static Data Export models
│
├── services/             # Business logic services
│   ├── arbitrage_engine.py # Cross-region arbitrage (45.2KB)
│   ├── hauling_score.py  # Trade route risk/reward calculation
│   ├── history_cache.py  # Market history caching
│   └── market_refresh.py # Scope-based market data refresh
│
├── mcp/                  # MCP server + tool implementations
│   ├── server.py         # FastMCP server entrypoint
│   ├── tools.py          # Tool registration framework
│   ├── context.py        # Output wrapping, truncation, trace context
│   ├── context_policy.py # Token budgeting limits
│   ├── context_budget.py # Context window tracking
│   ├── policy.py         # Capability gating with sensitivity levels
│   ├── errors.py         # MCP error types with suggestions
│   ├── models.py         # Pydantic models for MCP responses
│   ├── activity.py       # Live activity data caching
│   ├── dispatchers/      # 6 unified dispatchers (universe, market, sde, skills, fitting, status)
│   ├── market/           # Market tool implementations (10 files)
│   ├── sde/              # SDE tool implementations (8 files)
│   └── fitting/          # Fitting tool implementations
│
├── commands/             # 25 CLI command modules
├── universe/             # Graph building and navigation
├── cache/                # Cache construction
├── fitting/              # EOS integration and EFT parsing
└── persona/              # Persona context compilation
```

### Entrypoints

| Entrypoint | Location | Purpose |
|------------|----------|---------|
| `aria-esi` | `__main__.py:main()` | CLI with 25 subcommands |
| `aria-universe` | `mcp/server.py:main()` | MCP server with 6 dispatchers |

### Main Execution Flow

```
CLI: aria-esi <command> [args]
    → __main__.py loads command parsers dynamically
    → Command handler calls ESI client / services / MCP tools
    → JSON output returned

MCP: aria-universe (via .mcp.json)
    → server.py loads universe graph from pickle
    → Registers 6 dispatchers (universe, market, sde, skills, fitting, status)
    → Claude Code calls dispatchers → tool implementations → response with _meta
```

### Where LLM Calls/Tooling Are Orchestrated

The codebase does **not** make direct LLM API calls. LLM orchestration happens externally via:
- **Claude Code** invoking MCP tools through `dispatchers/`
- **Skills** in `.claude/skills/` providing prompt templates
- **Hooks** in `.claude/hooks/` running at session start

---

## 2) Python Quality Assessment

### Architecture & Separation of Concerns

**Findings:**
- Clean layered architecture: `core/` → `models/` → `services/` → `mcp/` → `commands/`
- MCP dispatchers consolidate 45+ tools into 6 unified interfaces (`src/aria_esi/mcp/dispatchers/`)
- Commands follow consistent registration pattern via `register_parsers()` (`src/aria_esi/commands/*.py`)

**Evidence:**
- `src/aria_esi/mcp/dispatchers/universe.py:L65-289` - Clean action dispatch pattern
- `src/aria_esi/commands/navigation.py:L1-50` - Standard command registration

**Missing/Risk:**
- Some circular import potential between `mcp/` modules (mitigated with local imports)
- `services/arbitrage_engine.py` at 45KB is a candidate for decomposition

**What to Change:**
- Consider splitting `arbitrage_engine.py` into `arbitrage/scanner.py`, `arbitrage/calculator.py`, `arbitrage/models.py`
- Add `__all__` exports to package `__init__.py` files for explicit public APIs

### API Design

**Findings:**
- Consistent JSON return format across CLI commands
- MCP dispatchers use unified `action` parameter pattern
- Error types provide actionable suggestions

**Evidence:**
- `src/aria_esi/mcp/errors.py:L24-78` - Errors include suggestions like `did_you_mean`
- `src/aria_esi/core/auth.py:L74-93` - `CredentialsError` includes `action` and `command` hints

**Missing/Risk:**
- Some commands return inconsistent structures (dict vs list at top level)
- Docstrings vary in completeness across modules

**What to Change:**
- Standardize command output to always be `{"data": ..., "meta": {...}}` format
- Add docstrings to all public functions in `commands/` modules

### Type Hints

**Findings:**
- Good coverage in newer modules (`mcp/`, `models/`)
- Core modules have partial coverage
- `typing.Optional` and `typing.Union` used consistently

**Evidence:**
- `src/aria_esi/mcp/context.py:L100-144` - Well-typed `OutputMeta` dataclass
- `src/aria_esi/mcp/policy.py:L46-54` - Clear `SensitivityLevel` enum
- `pyproject.toml:L168-214` - mypy configured with gradual adoption roadmap

**Missing/Risk:**
- ~~Phase 1 mypy adoption disables many error codes~~ Phase 3 complete (2026-01-24)
- Some functions use `dict[str, Any]` where more specific types would help

**What to Change:** *(Partially complete)*
- ✅ Progress to Phase 2 of typing roadmap (enable `union-attr`, `attr-defined`)
- ✅ Progress to Phase 3 of typing roadmap (enable `arg-type`, `return-value`)
- Add `TypedDict` definitions for common dict shapes (e.g., `PersonaContext`)
- Create `protocols.py` for duck-typed interfaces

### Static Analysis Readiness

**Findings:**
- ruff configured with good rule selection (E, W, F, I, B, C4, UP)
- mypy configured but permissive
- Pre-commit hooks available

**Evidence:**
- `pyproject.toml:L129-166` - Comprehensive ruff configuration
- `pyproject.toml:L168-214` - Gradual mypy adoption with roadmap documented

**Missing/Risk:**
- B904 (raise from) disabled - exception chaining would improve tracebacks
- No strict mode on any module yet

**What to Change:**
- Enable B904 and add `from e` to exception chains
- Add strict mypy overrides for `core/formatters.py`, `core/constants.py` (pure functions)

### Datamodels & Validation

**Findings:**
- Pydantic v2 used extensively in `models/` and `mcp/models.py`
- Dataclasses used for internal data structures
- Input validation via argparse type converters

**Evidence:**
- `src/aria_esi/models/market.py:L1-40` - Pydantic models with validators
- `src/aria_esi/mcp/context.py:L100-144` - Dataclass with `to_dict()` method
- `src/aria_esi/mcp/models.py:L15-35` - `MCPModel` base class with frozen config

**Missing/Risk:**
- Some dict-based data structures could benefit from Pydantic models
- MCP dispatcher parameters not validated via Pydantic

**What to Change:**
- Add Pydantic models for `persona_context` structure
- Consider `@validate_call` decorator for dispatcher functions

### Error Handling

**Findings:**
- Custom exception hierarchy exists (`CredentialsError`, `RetryableESIError`, `PolicyError`)
- Exceptions include context for user action
- Retry logic distinguishes retryable vs non-retryable errors

**Evidence:**
- `src/aria_esi/core/retry.py:L117-157` - `RetryableESIError` and `NonRetryableESIError` with full context
- `src/aria_esi/core/auth.py:L74-93` - `CredentialsError` with action/command hints
- `src/aria_esi/mcp/policy.py:L129-149` - `CapabilityDenied` with sensitivity info

**Missing/Risk:**
- Some bare `except Exception` blocks without re-raise or logging
- Exception chaining (`raise from`) not consistently used

**What to Change:**
- Audit for bare exception handlers; add logging or re-raise
- Enable ruff B904 and add exception chaining throughout

### Async vs Sync Correctness

**Findings:**
- MCP tools are async (`async def`)
- Sync ESI client uses `urllib` with retry decorator
- Async ESI client exists but not integrated into MCP (2026-01-24)

**Evidence:**
- `src/aria_esi/mcp/dispatchers/universe.py:L65` - `async def universe(...)`
- `src/aria_esi/core/client.py:L127-149` - Sync HTTP with timeouts
- `src/aria_esi/core/async_client.py` - Async httpx client (new)
- `src/aria_esi/mcp/market/database_async.py` - Async SQLite operations

**Missing/Risk:**
- Mixing sync ESI calls in async MCP handlers could block event loop
- Async client exists but not wired into dispatchers
- No cancellation handling in async tools

**What to Change:** *(Partially complete)*
- ✅ Add async ESI client wrapper using httpx (`core/async_client.py`)
- Integrate async client into MCP dispatchers
- Add `asyncio.CancelledError` handling in long-running async operations

### Resource Management

**Findings:**
- Context managers used for file operations
- SQLite connections managed via aiosqlite
- HTTP connections have timeouts

**Evidence:**
- `src/aria_esi/core/auth.py:L143-145` - `with open(credentials_file) as f`
- `src/aria_esi/mcp/market/database_async.py` - aiosqlite connection management
- `src/aria_esi/core/client.py:L131` - 30-second timeout on requests

**Missing/Risk:**
- Some database connections may not be properly closed on exception paths
- No explicit connection pooling for ESI client

**What to Change:**
- Add `finally` blocks or context managers for all database operations
- Consider httpx connection pooling for ESI client

### Logging & Observability

**Findings:**
- Structured logging with JSON output option
- MCP calls logged with sanitized parameters
- Policy engine has audit logging
- Trace context variables for correlation

**Evidence:**
- `src/aria_esi/core/logging.py:L59-138` - `AriaFormatter` with JSON mode
- `src/aria_esi/mcp/context.py:L699-833` - `log_context` decorator
- `src/aria_esi/mcp/policy.py:L380-420` - Policy audit logging with trace IDs
- `src/aria_esi/mcp/context.py:L54-93` - Trace context variables

**Missing/Risk:**
- ~~Not all modules use the structured logger~~ All 46 modules migrated (2026-01-24)
- No metrics collection (latency histograms, error rates)

**What to Change:** *(Partially complete)*
- ✅ Migrate all modules to use `core.logging.get_logger()`
- Add optional Prometheus/StatsD metrics for MCP tool latencies

### Configuration

**Findings:**
- Environment variables for configuration (`ARIA_LOG_LEVEL`, `ARIA_DEBUG`)
- JSON config files for pilot data
- Policy can be overridden via `ARIA_MCP_POLICY` env var

**Evidence:**
- `src/aria_esi/core/logging.py:L34-51` - `_get_log_level()` from environment
- `src/aria_esi/mcp/policy.py:L32-38` - Policy path from environment
- `src/aria_esi/core/auth.py:L330-331` - Pilot ID from `ARIA_PILOT`

**Missing/Risk:**
- ~~No centralized config object~~ `core/config.py` implemented (2026-01-24)
- ~~No validation of config values at startup~~ Pydantic Settings validates on import

**What to Change:** *(Complete)*
- ✅ Create `src/aria_esi/core/config.py` with Pydantic `Settings` class
- ✅ Validate all config at startup with clear error messages

### Testing

**Findings:**
- 67+ test files with 2,200+ test functions (2026-01-24: 2208 passing)
- Good MCP tool coverage (71-100%)
- Singleton reset fixture prevents test contamination
- Snapshot testing framework available (syrupy) and active

**Evidence:**
- `tests/conftest.py:L1-200` - Comprehensive fixtures including `reset_all_singletons`
- `tests/mcp/conftest.py:L1-100` - Mock universe factory
- `tests/commands/conftest.py` - Command test fixtures (new)
- `pyproject.toml:L72-99` - pytest configuration with markers

**Missing/Risk:**
- ~~Command modules have minimal implementation tests~~ 96 command tests added (2026-01-24)
- ~~Snapshot tests not yet active~~ Status output snapshots enabled

**What to Change:** *(Partially complete)*
- ✅ Add implementation tests for command modules (7 modules covered)
- ✅ Enable snapshot tests for skill outputs
- Target 70% coverage minimum

### Performance

**Findings:**
- Pre-built universe graph for O(1) lookups
- Multi-tier market caching (Fuzzwork → ESI → history)
- Context output byte limits with truncation
- Safe serialization format with msgpack (2026-01-24)

**Evidence:**
- `src/aria_esi/universe/serialization.py` - Safe `.universe` format with msgpack
- `src/aria_esi/mcp/market/cache.py` - Multi-tier caching
- `src/aria_esi/mcp/context.py:L146-220` - Byte size enforcement

**Missing/Risk:**
- ~~Pickle loading is a security risk~~ Replaced with safe serialization (2026-01-24)
- No profiling or benchmarking in CI

**What to Change:** *(Partially complete)*
- ✅ Replace pickle with safe serialization (msgpack + igraph binary)
- Add benchmark tests to CI for route/search performance

### Security & Safety (Python-Level)

**Findings:**
- Credentials have file permission checks
- Path validation for persona files with allowlist (2026-01-24)
- Sensitive data redacted in logs
- Safe serialization eliminates pickle RCE risk (2026-01-24)

**Evidence:**
- `src/aria_esi/core/auth.py:L47-71` - Permission checks for credential files
- `src/aria_esi/core/path_security.py` - Centralized path validation with allowlist
- `src/aria_esi/mcp/context.py:L661-696` - `_sanitize_params()` redacts sensitive keys
- `src/aria_esi/persona/compiler.py:L89-100` - Untrusted data wrapping
- `src/aria_esi/universe/serialization.py` - Safe msgpack + igraph format

**Missing/Risk:**
- ~~Pickle loading without verification~~ Replaced with safe serialization (2026-01-24)
- ~~No path traversal protection~~ Allowlist + symlink escape protection (2026-01-24)

**What to Change:** *(Complete)*
- ✅ Replace pickle with signed/verified serialization
- ✅ Add `pathlib.Path.resolve()` and allowlist checks to all file operations

---

## 3) LLM-Integration-Specific Python Practices

### LLM Client Wrapper Design

**Current State:**
- No direct LLM API calls in Python code
- External orchestration via Claude Code + MCP

**Evidence:**
- `pyproject.toml:L31-70` - No LLM SDK dependencies (anthropic, openai)

**What to Change (if direct calls added):**
- Create `src/aria_esi/llm/adapter.py` with:
  - Timeout configuration (30s default)
  - Exponential backoff (reuse `core/retry.py` patterns)
  - Streaming support with partial result handling
  - Model fallback chain

### Prompt Construction

**Current State:**
- Prompts live in `.claude/skills/*/SKILL.md` with YAML frontmatter
- Persona files compiled with untrusted-data delimiters
- `aria-context-assembly.py` generates session context

**Evidence:**
- `src/aria_esi/persona/compiler.py:L89-100` - `_wrap_content()` with delimiters
- `.claude/scripts/aria-context-assembly.py` - Session context generation
- `.claude/skills/SCHEMA.md` - Skill frontmatter schema

**What to Change:**
- Add `src/aria_esi/skills/loader.py` for programmatic skill loading with validation
- Create Pydantic model for skill frontmatter
- Add injection pattern detection in persona compiler

### Tool/MCP Interaction

**Current State:**
- 6 unified dispatchers with action-based routing
- Policy engine with sensitivity levels
- Schema validation via Pydantic models

**Evidence:**
- `src/aria_esi/mcp/dispatchers/universe.py:L65-289` - Action dispatch pattern
- `src/aria_esi/mcp/policy.py:L301-354` - `check_capability()` with context
- `src/aria_esi/mcp/models.py:L15-144` - Pydantic response models

**What to Change:**
- Add input validation via Pydantic for dispatcher parameters
- Implement request ID tracking across tool chains

### Structured Outputs

**Current State:**
- All MCP outputs include `_meta` with count, timestamp, truncation status
- Provenance fields (`source`, `as_of`) available
- Byte size limits enforced

**Evidence:**
- `src/aria_esi/mcp/context.py:L100-144` - `OutputMeta` dataclass
- `src/aria_esi/mcp/context.py:L304-372` - `wrap_output()` with provenance
- `src/aria_esi/mcp/context.py:L146-220` - Byte enforcement

**What to Change:**
- Enforce provenance fields on all tool outputs (not just optional)
- Add output schema validation before returning

### Determinism & Evals

**Current State:**
- No golden/snapshot tests for tool outputs
- Syrupy framework installed but empty snapshots

**Evidence:**
- `tests/skills/__snapshots__/test_skill_outputs.ambr` - Snapshot file with status output golden tests
- `tests/skills/conftest.py:L1-30` - Normalization utilities ready

**What to Change:** *(Partially complete)*
- ✅ Enable snapshot tests for key tool outputs
- Add deterministic test fixtures with fixed timestamps
- Create eval harness for skill output quality

---

## 4) Priority-Ranked Action List

| Priority | Change Description | Files to Touch | Effort | Status | Benefit / Risk Reduced |
|----------|-------------------|----------------|--------|--------|------------------------|
| P0 | Replace pickle with safe serialization | `universe/serialization.py` | M | ✅ Done | RCE vulnerability from malicious pickle |
| P0 | Add path allowlist to all file operations | `core/path_security.py` | S | ✅ Done | Path traversal / arbitrary file read |
| P1 | Create centralized config with validation | `core/config.py` | M | ✅ Done | Scattered config, missing validation |
| P1 | Add async ESI client for MCP | `core/async_client.py`, `mcp/dispatchers/*` | M | ⏳ Partial | Event loop blocking |
| P1 | Enable mypy Phase 2 (`union-attr`, `attr-defined`) | `pyproject.toml` | M | ✅ Done | Type safety gaps |
| P1 | Enable mypy Phase 3 (`arg-type`, `return-value`) | `pyproject.toml` | M | ✅ Done | Function signature safety |
| P2 | Add command implementation tests | `tests/commands/test_*.py` | L | ✅ Done | Low command coverage (50-89%) |
| P2 | Enable snapshot tests for tool outputs | `tests/mcp/test_status_output.py` | S | ✅ Done | Output quality regression |
| P2 | Split arbitrage_engine.py | `services/arbitrage_*.py` | M | ✅ Done | Maintainability (45KB file) |
| P2 | Migrate to `core.logging.get_logger()` | All modules (46 files) | S | ✅ Done | Inconsistent logging |
| P3 | Add Prometheus metrics | New `core/metrics.py`, `mcp/context.py` | M | ❌ Not started | No observability metrics |

**Implementation Notes (2026-01-24):**
- P0 safe serialization: Custom `.universe` format with msgpack + igraph binary (eliminates pickle RCE)
- P0 path security: Allowlist validation with symlink escape protection, break-glass via `ARIA_ALLOW_UNSAFE_PATHS`
- P1 async client: `AsyncESIClient` exists but not yet integrated into MCP dispatchers
- P1 mypy: Jumped through Phase 3; only 6 error codes remain disabled
- P2 arbitrage: Extracted `arbitrage_fees.py` (169 LOC) and `arbitrage_freshness.py` (147 LOC)
- P2 logging: All 46 modules migrated to structured `get_logger()`

---

## 5) Patch-Ready Recommendations

### 1. Safe Serialization for Universe Graph (P0)

**Current:** `pickle.load()` enables RCE via malicious pickle.

**Proposed Changes:**

```python
# src/aria_esi/universe/builder.py

import hashlib
import json
from pathlib import Path
from typing import Any

# Add checksum verification
EXPECTED_CHECKSUMS_FILE = Path(__file__).parent.parent / "data" / "checksums.json"

def verify_checksum(file_path: Path, expected_hash: str) -> bool:
    """Verify SHA256 checksum of file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest() == expected_hash

def load_universe_graph(path: Path) -> "UniverseGraph":
    """Load universe graph with integrity verification."""
    # Verify checksum before loading
    if EXPECTED_CHECKSUMS_FILE.exists():
        checksums = json.loads(EXPECTED_CHECKSUMS_FILE.read_text())
        expected = checksums.get("universe.pkl")
        if expected and not verify_checksum(path, expected):
            raise ValueError(f"Checksum mismatch for {path}")

    # Use restricted unpickler or migrate to msgpack
    import pickle
    with open(path, "rb") as f:
        return pickle.load(f)
```

**Alternative (better):** Migrate to msgpack with schema:

```python
# Migration to msgpack
import msgpack

def save_universe_graph(graph: "UniverseGraph", path: Path) -> None:
    """Save graph in safe msgpack format."""
    data = {
        "version": "2.0",
        "systems": {sid: s.to_dict() for sid, s in graph.systems.items()},
        "edges": [(s, d) for s, d in graph.edges],
    }
    with open(path, "wb") as f:
        msgpack.pack(data, f, use_bin_type=True)

def load_universe_graph_safe(path: Path) -> "UniverseGraph":
    """Load graph from safe msgpack format."""
    with open(path, "rb") as f:
        data = msgpack.unpack(f, raw=False, strict_map_key=True)

    if data.get("version") != "2.0":
        raise ValueError("Unsupported graph version")

    return UniverseGraph.from_dict(data)
```

**Tests to Add:**
```python
# tests/universe/test_builder.py

def test_checksum_mismatch_raises():
    """Tampered graph file should be rejected."""
    with pytest.raises(ValueError, match="Checksum mismatch"):
        load_universe_graph(tampered_path)

def test_msgpack_roundtrip():
    """Graph survives msgpack serialization."""
    save_universe_graph(graph, path)
    loaded = load_universe_graph_safe(path)
    assert loaded.systems == graph.systems
```

---

### 2. Centralized Configuration (P1)

**Current:** Environment variables read scattered across modules.

**Proposed Changes:**

```python
# src/aria_esi/core/config.py

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AriaSettings(BaseSettings):
    """Centralized ARIA configuration with validation."""

    model_config = SettingsConfigDict(
        env_prefix="ARIA_",
        env_file=".env",
        extra="ignore",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "WARNING"
    log_json: bool = False
    debug: bool = False  # Legacy, sets log_level to DEBUG

    # Paths
    project_dir: Path = Field(default_factory=Path.cwd)
    universe_graph: Path | None = None
    mcp_policy: Path | None = None

    # Security
    no_retry: bool = False
    mcp_bypass_policy: bool = False

    # Pilot (optional)
    pilot: str | None = None

    @field_validator("log_level", mode="before")
    @classmethod
    def handle_debug_compat(cls, v, info):
        """Handle legacy ARIA_DEBUG."""
        if info.data.get("debug"):
            return "DEBUG"
        return v.upper() if v else "WARNING"

    @field_validator("project_dir", mode="after")
    @classmethod
    def validate_project_dir(cls, v):
        """Ensure project directory exists."""
        if not v.exists():
            raise ValueError(f"Project directory does not exist: {v}")
        return v


# Singleton
_settings: AriaSettings | None = None

def get_settings() -> AriaSettings:
    """Get validated settings singleton."""
    global _settings
    if _settings is None:
        _settings = AriaSettings()
    return _settings
```

**Usage:**

```python
# src/aria_esi/core/logging.py
from .config import get_settings

def _get_log_level() -> int:
    settings = get_settings()
    return getattr(logging, settings.log_level)
```

**Tests to Add:**

```python
# tests/core/test_config.py

def test_debug_compat(monkeypatch):
    """ARIA_DEBUG=1 sets log level to DEBUG."""
    monkeypatch.setenv("ARIA_DEBUG", "1")
    settings = AriaSettings()
    assert settings.log_level == "DEBUG"

def test_invalid_project_dir(tmp_path):
    """Non-existent project_dir raises ValidationError."""
    with pytest.raises(ValidationError):
        AriaSettings(project_dir=tmp_path / "nonexistent")
```

---

### 3. Async ESI Client (P1)

**Current:** Sync `urllib` calls in async MCP handlers block event loop.

**Proposed Changes:**

```python
# src/aria_esi/core/async_client.py

import httpx
from typing import Any

from .retry import esi_retry_async, RetryableESIError


class AsyncESIClient:
    """Async ESI HTTP client with retry and timeout."""

    BASE_URL = "https://esi.evetech.net/latest"

    def __init__(
        self,
        token: str | None = None,
        timeout: float = 30.0,
    ):
        self.token = token
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AsyncESIClient":
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._headers(),
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @esi_retry_async()
    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """GET request with retry."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with.")

        url = f"{self.BASE_URL}{path}"
        response = await self._client.get(url, params=params)

        if response.status_code in (429, 502, 503, 504):
            retry_after = response.headers.get("Retry-After")
            raise RetryableESIError(
                f"ESI error {response.status_code}",
                status_code=response.status_code,
                retry_after=int(retry_after) if retry_after else None,
            )

        response.raise_for_status()
        return response.json()
```

**Async retry decorator:**

```python
# src/aria_esi/core/retry.py (addition)

from tenacity import retry, stop_after_attempt, wait_exponential_jitter

def esi_retry_async(max_attempts: int = 3):
    """Async retry decorator for ESI calls."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=2, max=30),
        retry=retry_if_exception(_should_retry_exception),
        reraise=True,
    )
```

**Tests to Add:**

```python
# tests/core/test_async_client.py

@pytest.mark.asyncio
async def test_get_success(httpx_mock):
    """Successful GET returns JSON."""
    httpx_mock.add_response(json={"character_id": 123})

    async with AsyncESIClient() as client:
        result = await client.get("/characters/123/")

    assert result["character_id"] == 123

@pytest.mark.asyncio
async def test_retry_on_503(httpx_mock):
    """503 triggers retry."""
    httpx_mock.add_response(status_code=503)
    httpx_mock.add_response(json={"ok": True})

    async with AsyncESIClient() as client:
        result = await client.get("/status/")

    assert result["ok"] is True
```

---

## 6) Tooling & Standards Proposal

### Current State

The repository has good tooling already configured:
- ruff for linting and formatting
- mypy for type checking (gradual adoption)
- pytest with coverage
- Pre-commit hooks

### Recommended Additions

**pyproject.toml updates:**

```toml
[tool.mypy]
# Phase 2: Enable these after fixing ~50 errors
# disable_error_code = [
#     "union-attr",
#     "attr-defined",
# ]

# Per-module strict overrides (start with pure modules)
[[tool.mypy.overrides]]
module = "aria_esi.core.formatters"
disallow_untyped_defs = true
warn_return_any = true

[[tool.mypy.overrides]]
module = "aria_esi.core.constants"
disallow_untyped_defs = true
warn_return_any = true
```

**Pre-commit additions:**

```yaml
# .pre-commit-config.yaml (additions)
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic>=2.0
          - types-PyYAML
        args: [--config-file=pyproject.toml]
```

**CI recommendations:**

```yaml
# .github/workflows/ci.yml
jobs:
  fast-checks:
    - ruff check
    - ruff format --check
    - mypy

  tests:
    - pytest --cov --cov-fail-under=50
    - pytest -m benchmark (weekly only)
```

---

## 7) Review Rubric

| Area | Score | Justification |
|------|-------|---------------|
| **Code Clarity** | 4.5/5 | Clean architecture, good naming, consistent patterns. Arbitrage decomposed. |
| **Type Safety** | 4/5 | Good Pydantic usage, mypy Phase 3 complete. Only 6 error codes remain disabled. |
| **Testability** | 4/5 | Good fixtures, singleton reset. Command tests added (96 tests). Snapshot tests enabled. |
| **Reliability** | 4/5 | Retry logic with backoff, timeouts configured, error types with context. Async client exists but not integrated. |
| **Security Hygiene** | 4.5/5 | Credential permission checks, log redaction, policy engine. Safe serialization, path allowlists. |
| **Maintainability** | 4.5/5 | Modular design, centralized config and logging, good separation. |

---

## Summary

ARIA is a well-architected LLM-integrated application with solid foundations:
- Clean layered architecture with separation of concerns
- Comprehensive MCP tool implementation with policy engine
- Good observability with structured logging and trace context
- Thoughtful error handling with actionable messages

**Completed improvements (2026-01-24):**
- ✅ **Security (P0):** Safe serialization (msgpack + igraph binary), path allowlists with symlink protection
- ✅ **Configuration (P1):** Centralized Pydantic Settings, mypy Phase 2+3 complete
- ✅ **Quality (P2):** Command tests (96 new), snapshot tests, arbitrage decomposition, logger migration

**Remaining work:**
1. **Reliability (P1):** Integrate `AsyncESIClient` into MCP dispatchers (client exists, not wired up)
2. **Observability (P3):** Add Prometheus metrics for MCP tool latencies
3. **Type Safety (Phase 4+):** Enable `disallow_untyped_defs` on core modules
