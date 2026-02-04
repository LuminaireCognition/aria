# Remediation Backlog

Outstanding findings from external reviews requiring action. Consolidated from:
- `dev/reviews/SECURITY_000.md` (2026-01-22)
- `dev/reviews/CONTEXT_MANAGEMENT_REVIEW.md` (2026-01-22)
- `dev/reviews/PROJECT_REVIEW_2026-01.md` (2026-01-18)

**Last Updated:** 2026-02-02

---

## Priority 1: Critical/High Security Findings

From SECURITY_000.md:

### SEC-001: Persona file path allowlisting
**Severity:** Critical | **Source:** SECURITY_000.md Finding 1
**Status:** ✅ COMPLETED (2026-02-02)

User-editable `persona_context` enables arbitrary file inclusion via unvalidated paths. Can lead to secret exfiltration, unsafe tool invocation, and persistent prompt injection.

**Remediation Applied:**
- Added `ALLOWED_EXTENSIONS` constant (`.md`, `.yaml`, `.json` only)
- Added `validate_persona_file_path()` - combines prefix allowlist with extension checking
- Added `safe_read_persona_file()` - validates path + extension + size limit before reading
- Added pilot_directory validation in notification persona loader
- Updated CLAUDE.md with explicit runtime validation rules

**Implementation:**
- `src/aria_esi/core/path_security.py:178-282` - new validation functions
- `src/aria_esi/services/redisq/notifications/persona.py:337-355` - pilot_directory validation
- `CLAUDE.md` "Runtime Path Validation (SEC-001/SEC-002)" section

**Verification:** Tests in `tests/core/test_path_security.py` (TestExtensionValidation, TestSafeReadPersonaFile) and `tests/integration/test_security_paths.py` cover:
- Extension allowlist enforcement
- Path traversal rejection
- Absolute path rejection
- Symlink escape detection
- Oversized file rejection
- End-to-end malicious profile rejection

---

### SEC-002: Skill overlay path validation
**Severity:** High | **Source:** SECURITY_000.md Finding 2
**Status:** ✅ COMPLETED (2026-02-02)

Overlay and persona-exclusive redirects resolved using `persona_context` and `_index.json` without strict validation. Compromised index or profile can route to arbitrary files.

**Remediation Applied:**
- Added `validate_skill_redirects()` for compile-time redirect path validation
- Integrated into `cmd_persona_context()` to warn on unsafe redirects
- All overlay paths validated via `validate_persona_file_path()` at runtime
- Extension allowlist prevents loading of dangerous file types (.py, .sh, etc.)

**Implementation:**
- `src/aria_esi/commands/persona.py:499-541` - `validate_skill_redirects()` function
- `src/aria_esi/commands/persona.py:443-460` - integration into persona-context command
- Existing `validate_persona_context()` now uses `validate_persona_file_path()`

**Verification:** Tests in `tests/integration/test_security_paths.py` cover:
- Traversal in redirect paths rejected
- Absolute redirect paths rejected
- Wrong extension (.py) in redirect rejected
- Valid redirects pass
- Overlay path injection rejected

---

### SEC-003: Replace pickle serialization for universe graph
**Severity:** High | **Source:** SECURITY_000.md Finding 3
**Status:** ✅ COMPLETED (2026-02-02)

MCP server loads `universe.pkl` with `pickle.load()`, enabling RCE if file is tampered. Located in `src/aria_esi/universe/builder.py:258-276`.

**Remediation Applied:**
- New `.universe` format using msgpack + igraph picklez (no arbitrary code execution)
- SHA256 checksum verification BEFORE deserialization via `verify_universe_graph_integrity()`
- Legacy `.pkl` support retained with deprecation warning for migration
- Format detection via magic bytes header (`b'ARIA'` + version), not file extension
- Type validation after load with `isinstance()` check

**Implementation:**
- `src/aria_esi/universe/builder.py:330-402` - safe loading with format detection
- `src/aria_esi/core/data_integrity.py` - checksum verification before any deserialization
- `reference/data-sources.json` - manifest with SHA256 checksums
- `src/aria_esi/data/universe.universe` - new safe format (primary)

**Verification:** Tests in `tests/universe/test_graph.py` (lines 441-564) cover:
- Safe format loading and saving
- Checksum verification
- Legacy pickle deprecation warning
- Malicious pickle rejection via integrity check

---

### SEC-004: Checksum verification for SDE/EOS downloads
**Severity:** High | **Source:** SECURITY_000.md Finding 4

SDE/EOS data downloaded without integrity checks or version pinning. Compromised upstream can poison local databases.

**Required action:**
- Pin versions/commits and verify checksums/signatures
- Add schema/content sanity checks before ingest
- Provide `--break-glass-latest` override for users needing newest data

**Verification:** Tests that tampered downloads are rejected.

---

### SEC-005: MCP tool capability gating
**Severity:** Medium-High | **Source:** SECURITY_000.md Finding 5

All MCP tools registered without policy gate. Prompt injection can call any available tool.

**Required action:**
- Add tool policy gate (allowlist + explicit confirmation for sensitive tools)
- Enforce scope checks inside tools for authenticated endpoints
- Add rate limits and audit logging for tool calls

**Verification:** Integration tests for disallowed tool calls.

---

## Priority 2: High Context Management Findings

From CONTEXT_MANAGEMENT_REVIEW.md:

### CTX-001: Singleton reset functions for caches
**Severity:** Critical | **Source:** CONTEXT_MANAGEMENT_REVIEW.md Finding 1
**Status:** ✅ **Completed** (2026-02-02)

~~19 module-level singleton caches identified, 9 lack reset functions.~~ Investigation found all singletons already have reset functions. The actual issue was that 14 reset functions existed but were not called by the `reset_all_singletons` pytest fixture.

**Resolution:**
- Added 14 missing reset calls to `reset_all_singletons` fixture in `tests/conftest.py`
- RedisQ services: name_resolver, war_context, database, registry, preset_loader, threat_cache, notification_manager, npc_faction_mapper, persona_loader, entity_watchlist_manager, fetch_queue, poller, entity_filter
- MCP services: trace_context
- Updated fixture docstring to document all 33 reset calls

**Verification:** Test isolation passes in CI; no cross-run state leakage.

---

### CTX-002: Centralized token budget policy
**Severity:** High | **Source:** CONTEXT_MANAGEMENT_REVIEW.md Finding 2

Tool output limits scattered across individual tools (10-100 items) with no central configuration. No enforcement of total context size.

**Required action:**
- Create `src/aria_esi/mcp/context_policy.py` with centralized limits
- Wrap tool outputs in `truncate_output()` helper
- Document budgets in `docs/CONTEXT_POLICY.md`

**Verification:** Single configuration file controls all tool output limits.

---

### CTX-003: Output truncation wrapper
**Severity:** High | **Source:** CONTEXT_MANAGEMENT_REVIEW.md Finding 3

Some tools return unbounded lists with no automatic summarization. Long routes (45+ jumps) consume disproportionate context.

**Required action:**
- Implement `ContextWrapper` that counts output items
- Apply configurable truncation with metadata (`truncated: true, total_count: N`)
- Summarize large results (routes > 20 jumps: show first 5, summary, last 5)

**Verification:** All tool outputs include `_meta` with count and truncation status.

---

### CTX-004: YAML cache invalidation
**Severity:** Medium | **Source:** CONTEXT_MANAGEMENT_REVIEW.md Finding 4

YAML configuration caches (`_efficacy_rules_cache`, `_breakpoint_skills_cache`, `_activities_cache`) loaded once and never invalidated. Changes require MCP restart.

**Required action:**
- Add file modification timestamp checking
- Invalidate cache when source file changes
- OR add reset functions (overlaps with CTX-001)

**Verification:** YAML changes take effect without server restart.

---

## Priority 3: Project Quality Findings

From PROJECT_REVIEW_2026-01.md (7 open findings):

### PROJ-001: Test coverage
**Severity:** High | **Source:** PROJECT_REVIEW_2026-01.md Finding 9

Coverage improved from 19% to 42%, but significant gaps remain. Command modules (`assets.py`, `contracts.py`, `clones.py`, etc.) have 4-8% coverage.

**Required action:**
- Increase coverage threshold in pyproject.toml from 19% to 40%
- Prioritize testing for critical command paths
- Target 60%+ overall coverage

**Verification:** CI fails on coverage regression below threshold.

---

### PROJ-002: MCP/CLI duality maintenance burden
**Severity:** Medium | **Source:** PROJECT_REVIEW_2026-01.md Finding 3

Navigation features implemented twice (MCP and CLI) with drift between implementations. MCP has activity integration; CLI does not.

**Required action:**
- Create shared abstraction layer between MCP and CLI
- OR deprecate CLI fallback in favor of MCP-only
- Document synchronization requirements

**Verification:** Feature parity tests between MCP and CLI.

---

### PROJ-003: Session init context overhead
**Severity:** Medium | **Source:** PROJECT_REVIEW_2026-01.md Finding 1

Session bootstrap loads all persona context files (800-1500 tokens) before any interaction, even for simple queries that don't need persona features.

**Required action:**
- Consider lazy loading of persona files
- OR accept as design tradeoff (current decision)

**Status:** Open - Design tradeoff accepted.

---

## Tracking

| ID | Severity | Status | Owner | Notes |
|----|----------|--------|-------|-------|
| SEC-001 | Critical | **Completed** | - | Path + extension allowlisting |
| SEC-002 | High | **Completed** | - | Overlay + redirect validation |
| SEC-003 | High | **Completed** | - | Safe format deployed, checksum verification |
| SEC-004 | High | Open | - | Download checksums |
| SEC-005 | Medium-High | Open | - | Tool gating |
| CTX-001 | Critical | **Completed** | - | Added 14 missing resets to fixture |
| CTX-002 | High | Open | - | Token budget |
| CTX-003 | High | Open | - | Output truncation |
| CTX-004 | Medium | Open | - | YAML invalidation |
| PROJ-001 | High | In Progress | - | Test coverage |
| PROJ-002 | Medium | Open | - | MCP/CLI duality |
| PROJ-003 | Medium | Accepted | - | Design tradeoff |

---

## Quick Wins (1-2 days each)

From SECURITY_000.md:
1. ~~Allowlist + canonicalize all persona/overlay/redirect paths~~ ✅ SEC-001/SEC-002 complete
2. ~~Make `validate-overlays` a required preflight; warn-and-block on out-of-allowlist paths~~ ✅ SEC-002 complete
3. Wrap all loaded files/tool outputs in data-only delimiters with "untrusted data" guardrails
4. Add checksums and version pinning for SDE downloads (SEC-004)
5. Add basic tool policy gate (allowlist + user confirmation for high-risk tools) (SEC-005)

From CONTEXT_MANAGEMENT_REVIEW.md:
1. ~~Add reset functions to missing singletons (Pattern: follow `reset_market_cache()`)~~ ✅ CTX-001 complete
2. ~~Create pytest autouse fixture for singleton resets~~ ✅ CTX-001 complete
3. Add truncation metadata to tool outputs (CTX-003)
4. Document context policy (CTX-002)
5. Add file timestamp checking to YAML caches (CTX-004)
