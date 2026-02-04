# Context Management Review: ARIA Codebase

**Review Date:** 2026-01-22
**Reviewer:** Claude Code (Automated Analysis)
**Scope:** LLM application context management for MCP-based Claude Code extension

---

## A) Executive Summary (Top 10 Findings)

1. **Critical:** Module-level singleton caches (19 identified) lack consistent reset functions, risking cross-run contamination in long-running MCP servers.

2. **High:** No centralized token budget policy exists—MCP tool output limits are scattered across individual tools with inconsistent max values (10-100).

3. **High:** Tool outputs have no standardized truncation wrapper; some tools return unbounded results that could overwhelm context.

4. **Medium:** YAML configuration caches (`_efficacy_rules_cache`, `_breakpoint_skills_cache`, `_activities_cache`) are loaded once and never invalidated.

5. **Medium:** No context observability—cannot answer "what context was sent?" or "how many tokens per segment?"

6. **Medium:** Input sanitization exists (`sanitize_field()`) but only for session context assembly, not for all tool outputs echoed into prompts.

7. **Low:** MCP dispatcher consolidation (60→6 tools) is good for attention; docstrings serve as schema but lack explicit JSON Schema validation.

8. **Low:** Data verification protocol is well-documented but enforcement is manual (relies on LLM following CLAUDE.md instructions).

9. **Low:** Session state separation relies on boot hooks regenerating `.session-context.json`; no explicit session isolation in Python layer.

10. **Positive:** Cache-first patterns for mission data, SDE re-import detection, and TTL-based activity cache show good design patterns to extend.

---

## B) Context Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLAUDE CODE SESSION                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONTEXT SOURCES                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  CLAUDE.md      │  │  Pilot Profile  │  │  Persona Files              │  │
│  │  (System Prompt)│  │  profile.md     │  │  personas/{persona}/*.md   │  │
│  │  15.6 KB        │  │  ~2 KB          │  │  ~10 KB total               │  │
│  └────────┬────────┘  └────────┬────────┘  └──────────────┬──────────────┘  │
│           │                    │                          │                  │
│           └────────────────────┼──────────────────────────┘                  │
│                                │                                             │
│                                ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    SESSION INIT (Boot Hooks)                        │    │
│  │  1. Resolve active_pilot → read config.json, _registry.json        │    │
│  │  2. Load profile.md → extract persona_context                       │    │
│  │  3. Validate staleness → check faction/rp_level match              │    │
│  │  4. Load persona files → iterate persona_context.files             │    │
│  │  5. Generate .session-context.json → project aliases               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SKILL INVOCATION                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User: "/route Jita Amarr" ──▶ Skill Loader ──▶ SKILL.md loaded             │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Skill Index (_index.json)                                          │    │
│  │  • Check persona_exclusive flag                                     │    │
│  │  • Check has_persona_overlay flag                                   │    │
│  │  • Load base skill + optional overlay                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MCP TOOL CALLS                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  6 Domain Dispatchers (Tool Context)                               │     │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │     │
│  │  │universe()│ │market() │ │sde()    │ │skills() │ │fitting()│ │     │
│  │  │14 actions│ │19 actions│ │8 actions│ │9 actions│ │1 action │ │     │
│  │  └────┬─────┘ └────┬─────┘ └────┬────┘ └────┬────┘ └────┬────┘ │     │
│  │       │            │            │           │           │       │     │
│  │       ▼            ▼            ▼           ▼           ▼       │     │
│  │  ┌─────────────────────────────────────────────────────────────┐│     │
│  │  │              Data Sources (Cached Context)                  ││     │
│  │  │  • UniverseGraph (pickle, ~5MB compressed)                  ││     │
│  │  │  • SDE Database (SQLite, ~15MB)                             ││     │
│  │  │  • Market Cache (SQLite, 30-day TTL)                        ││     │
│  │  │  • Activity Cache (Memory, 10-30min TTL)                    ││     │
│  │  │  • EOS/Pyfa Data (pickle, ~50MB)                            ││     │
│  │  └─────────────────────────────────────────────────────────────┘│     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  Output Limits (per-tool, not centralized):                                  │
│  • borders: max 50 systems                                                   │
│  • search: max 100 systems                                                   │
│  • orders: max 50 per side                                                   │
│  • agents: max 100 agents                                                    │
│  • arbitrage: default 20 opportunities                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RESPONSE TO CLAUDE CODE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Tool Result ──▶ Claude Code ──▶ Formatted Response ──▶ User                │
│                                                                              │
│  ⚠️ NO COMPACTION LAYER: Tool results pass through unchanged                 │
│  ⚠️ NO TOKEN COUNTING: No visibility into context budget consumption        │
│  ⚠️ NO SUMMARIZATION: Large results not summarized before inclusion         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## C) Findings (Evidence-Based)

### Finding 1: Inconsistent Singleton Reset Functions

**Severity:** Critical
**Status:** ✅ **RESOLVED** (2026-02-02) - See REMEDIATION_BACKLOG.md CTX-001
**Symptom:** Cross-run state contamination in long-running MCP servers; test isolation failures
**Evidence:**

| Singleton | File | Has Reset | Risk |
|-----------|------|-----------|------|
| `_market_cache` | `src/aria_esi/mcp/market/cache.py:796` | ✓ | Low |
| `_market_db` | `src/aria_esi/mcp/market/database.py` | ✗ | High |
| `_async_market_db` | `src/aria_esi/mcp/market/database_async.py` | ✗ | High |
| `_eos_data_manager` | `src/aria_esi/fitting/eos_data.py:298` | ✓ | Low |
| `_skill_requirements` | `src/aria_esi/fitting/skills.py:32` | ✗ | High |
| `_activities_cache` | `src/aria_esi/mcp/sde/tools_activities.py:37` | ✗ | High |
| `_efficacy_rules_cache` | `src/aria_esi/mcp/sde/tools_easy80.py:114` | ✗ | High |
| `_breakpoint_skills_cache` | `src/aria_esi/mcp/sde/tools_easy80.py:115` | ✗ | High |
| `_universe` | `src/aria_esi/mcp/tools.py:42` | ✗ | High |

**Impact:** Tests may pass in isolation but fail in CI due to shared state. Production MCP server accumulates stale data.
**Fix:** Add `reset_*()` functions to all singletons; create `reset_all_caches()` utility; add autouse pytest fixture.
**Effort:** Small (S)

---

### Finding 2: No Centralized Token Budget Policy

**Severity:** High
**Symptom:** Tool outputs can vary from 10 to unbounded items; no enforcement of total context size
**Evidence:**

```python
# src/aria_esi/mcp/tools_borders.py
MAX_LIMIT = 50
MAX_JUMPS = 30

# src/aria_esi/mcp/tools_search.py
MAX_LIMIT = 100
MAX_JUMPS = 50

# src/aria_esi/mcp/market/tools_orders.py
limit = max(1, min(50, limit))  # Clamped per-tool

# src/aria_esi/mcp/market/tools_arbitrage.py
max_results = 20  # Default, no hard cap
```

No central configuration file; limits hardcoded per-tool.

**Impact:** A single `search(limit=100)` + `orders(limit=50)` + `activity()` could return 200+ items, consuming significant context budget.
**Fix:** Create `src/aria_esi/mcp/context_policy.py` with centralized limits; wrap tool outputs in `truncate_output()` helper.
**Effort:** Medium (M)

---

### Finding 3: Missing Output Truncation Wrapper

**Severity:** High
**Symptom:** Some tools return unbounded lists; no automatic summarization for large results
**Evidence:**

```python
# src/aria_esi/mcp/tools_route.py - returns full route, no truncation
async def calculate_route(...) -> RouteResult:
    route = universe.get_route(...)
    return RouteResult(route=route, ...)  # Full route, could be 50+ jumps

# src/aria_esi/mcp/sde/tools_item.py - returns full item info, no truncation
async def item_info(...) -> dict:
    return result  # Full item data
```

Market scope refresh has truncation tracking (`pages_truncated: bool`) but doesn't actually truncate output.

**Impact:** Long routes (Jita→Amarr = 45 jumps) or detailed item lookups consume disproportionate context.
**Fix:** Implement `ContextWrapper` that:
1. Counts output items
2. Applies configurable truncation
3. Adds `truncated: true, total_count: N` metadata
4. Optionally summarizes large results

**Effort:** Medium (M)

---

### Finding 4: YAML Configuration Caches Never Invalidate

**Severity:** Medium
**Symptom:** Changes to YAML files require MCP server restart; no hot-reload capability
**Evidence:**

```python
# src/aria_esi/mcp/sde/tools_easy80.py:114-156
_efficacy_rules_cache: dict | None = None
_meta_alternatives_cache: dict | None = None
_breakpoint_skills_cache: dict | None = None

def load_breakpoint_skills() -> dict:
    global _breakpoint_skills_cache
    if _breakpoint_skills_cache is not None:
        return _breakpoint_skills_cache  # Never reloaded
    # ... load from YAML ...
```

Same pattern in `tools_activities.py:37`.

**Impact:** Development iteration requires restart; can't update skill plans without downtime.
**Fix:** Add file modification timestamp checking (like SDE import timestamp check in `queries.py`); or add reset functions.
**Effort:** Small (S)

---

### Finding 5: No Context Observability

**Severity:** Medium
**Symptom:** Cannot answer: "What context was sent?" "How many tokens?" "What was trimmed?"
**Evidence:**

Logging exists but is generic:
```python
# src/aria_esi/core/logging.py
class AriaFormatter(logging.Formatter):
    def _format_text(self, record, timestamp):
        msg = f"[ARIA {record.levelname}] [{module}] {record.getMessage()}"
```

No specialized logging for:
- Tool input/output sizes
- Token counts per segment
- Truncation events
- Context assembly timeline

**Impact:** Debugging context issues requires manual inspection; no metrics for optimization.
**Fix:** Add structured logging middleware:
```python
@log_context
async def universe(action: str, ...) -> dict:
    # Logs: input_params, output_size, execution_time, truncation_applied
```
**Effort:** Medium (M)

---

### Finding 6: Input Sanitization Scope Limited

**Severity:** Medium
**Symptom:** `sanitize_field()` only applies to session context assembly, not tool outputs
**Evidence:**

Strong sanitization exists for project files:
```python
# tests/test_context_sanitization.py
def test_strips_script_tags():
    text = "Project <script>alert('xss')</script> Name"
    result = sanitize_field(text, 100)
    assert "<script>" not in result
```

But tool outputs are not sanitized:
```python
# src/aria_esi/mcp/sde/tools_item.py
async def item_info(...) -> dict:
    result = await get_query_service().get_item_info(item)
    return result  # Raw from database, no sanitization
```

**Impact:** Malicious EVE item names (theoretically) could inject prompt content via SDE data.
**Fix:** Apply sanitization to all tool output strings before returning; or trust SDE data as controlled source.
**Effort:** Low (L) if trust SDE; Medium (M) if full sanitization

---

### Finding 7: MCP Tool Schema Validation

**Severity:** Low
**Symptom:** Docstrings serve as implicit schema; no explicit JSON Schema validation
**Evidence:**

```python
# src/aria_esi/mcp/dispatchers/universe.py
@server.tool()
async def universe(
    action: str,
    origin: str | None = None,
    destination: str | None = None,
    # ... 20+ optional params
) -> dict:
    """
    Unified universe navigation interface.

    Actions:
    - route: Calculate optimal route between two systems
    ...
    """
```

No Pydantic model or JSON Schema validation for inputs.

**Impact:** Invalid parameter combinations discovered at runtime rather than validation time.
**Fix:** Use Pydantic models for action-specific parameters; FastMCP supports model-based tools.
**Effort:** Medium (M)

---

### Finding 8: Data Verification Protocol Manual

**Severity:** Low
**Symptom:** Trust hierarchy (SDE > EOS > ESI > Wiki > Training) relies on LLM following CLAUDE.md
**Evidence:**

`docs/DATA_VERIFICATION.md` documents the protocol clearly:
```
| Priority | Source | Tool/Method | Use For |
|----------|--------|-------------|---------|
| 1 | SDE | sde_item_info | Item stats, skill effects |
| 2 | Pyfa/EOS | calculate_fit_stats | DPS, EHP calculations |
```

But enforcement is:
```markdown
# CLAUDE.md
> **Never present EVE game mechanics as fact without verification from a trusted source.**
```

No code-level enforcement.

**Impact:** Hallucination prevention depends on prompt compliance; no runtime guardrails.
**Fix:** Add skill pre-flight checks that require tool calls before claims; or add post-response validation.
**Effort:** Large (L)

---

### Finding 9: Session Isolation at Boot Level Only

**Severity:** Low
**Symptom:** Session state separated by boot hooks, not Python runtime
**Evidence:**

```python
# .claude/hooks/aria-boot.sh orchestrates:
# 1. pilot-resolution.sh → determines active pilot
# 2. aria-context-assembly.py → generates .session-context.json

# But Python layer has no session concept:
# src/aria_esi/mcp/tools.py
_universe: UniverseGraph | None = None  # Global, not per-session
```

MCP server is single-threaded/single-session by design, but if extended to multi-session, state leaks.

**Impact:** Low for current architecture; risk increases with scale.
**Fix:** Wrap singletons in `SessionContext` class; pass session ID through tool calls.
**Effort:** Large (L)

---

### Finding 10: Good Patterns to Extend

**Severity:** Positive
**Evidence:**

1. **Cache-first mission pattern** (`docs/DATA_VERIFICATION.md:270-303`):
   ```
   Check cache → If miss, fetch wiki → Write cache → Read from cache → Present
   ```

2. **SDE re-import detection** (`src/aria_esi/mcp/sde/queries.py`):
   ```python
   def _check_cache_validity(self) -> None:
       """Invalidate caches if SDE was re-imported."""
   ```

3. **TTL-based activity cache** (`src/aria_esi/mcp/activity.py:49`):
   ```python
   self._kills_timestamp: float = 0
   self._ttl_seconds: int = 600  # 10 minutes
   ```

4. **Truncation tracking** (`src/aria_esi/mcp/market/scope_refresh.py`):
   ```python
   pages_truncated: bool = False
   scan_status: Literal["new", "complete", "truncated", "error"]
   ```

**Recommendation:** Generalize these patterns into shared utilities.

---

## D) Recommended Context Policy

Create `docs/CONTEXT_POLICY.md`:

```markdown
# ARIA Context Policy

## 1. Context Segments and Ordering

| Segment | Max Size | Priority | Load Order |
|---------|----------|----------|------------|
| CLAUDE.md | 20 KB | System | 1 (always) |
| Pilot Profile | 3 KB | Session | 2 |
| Persona Files | 15 KB | Session | 3 |
| Session Context | 2 KB | Session | 4 |
| Skill Base | 5 KB | Invocation | 5 |
| Skill Overlay | 2 KB | Invocation | 6 |
| Tool Results | 10 KB per call | Dynamic | 7 |

## 2. Budgets and Limits

### Per-Tool Output Limits

| Tool | Max Items | Max Size | Truncation Strategy |
|------|-----------|----------|---------------------|
| universe.route | 100 jumps | 5 KB | Summarize middle hops |
| universe.search | 50 systems | 3 KB | Top-N by relevance |
| market.orders | 20 per side | 3 KB | Top by price |
| market.arbitrage | 20 opportunities | 5 KB | Top by margin |
| sde.search | 20 items | 2 KB | Top by match score |
| sde.agent_search | 30 agents | 3 KB | Top by distance |

### Total Context Budget

- **Soft limit:** 50 KB of tool output per conversation turn
- **Hard limit:** 100 KB triggers automatic summarization

## 3. Tool Output Handling Rules

1. **All tool outputs must include metadata:**
   ```json
   {
     "_meta": {
       "count": 45,
       "truncated": true,
       "truncated_from": 120,
       "timestamp": "2026-01-22T12:00:00Z"
     }
   }
   ```

2. **Large results must summarize:**
   - Routes > 20 jumps: Show first 5, summary, last 5
   - Lists > 30 items: Show top 10, count remaining

3. **Error responses bounded:**
   - Max 500 chars for error messages
   - Include error code for programmatic handling

## 4. Summarization Triggers

| Condition | Action |
|-----------|--------|
| Route > 20 jumps | Summarize middle segment |
| List > 30 items | Truncate with count |
| History > 30 days | Aggregate to daily stats |
| Skill tree > 20 skills | Group by category |

## 5. Provenance Rules

All data presented must cite source:

| Source | Citation Format |
|--------|-----------------|
| SDE | "Per SDE: {description}" |
| EOS | "Calculated: {value} (EOS)" |
| ESI | "Current: {value} (as of {timestamp})" |
| Wiki | "Reference: wiki.eveuniversity.org" |

## 6. Secret/PII Redaction

| Data Type | Handling |
|-----------|----------|
| OAuth tokens | Never in tool output |
| Character names | Pass through (public) |
| Wallet balance | Only on explicit request |
| Corporation keys | Redact in logs |
| User passwords | N/A (not stored) |

### Sanitization Layers

1. **Input sanitization:** `sanitize_field()` for user-provided project data
2. **Output sanitization:** Strip HTML, limit lengths, escape markdown
3. **Logging sanitization:** Redact tokens in structured logs
```

---

## E) Implementation Plan

### Quick Wins (≤1 day each)

1. **Add reset functions to missing singletons** (S)
   - Files: `tools_easy80.py`, `tools_activities.py`, `fitting/skills.py`, `database.py`
   - Pattern: Follow `reset_market_cache()` example
   - Add `reset_all_caches()` to `__init__.py`

2. **Create pytest autouse fixture for singleton resets** (S)
   - File: `tests/conftest.py`
   - Import and call all reset functions in `@pytest.fixture(autouse=True)`

3. **Add truncation metadata to tool outputs** (S)
   - Create `src/aria_esi/mcp/context.py` with `OutputMeta` dataclass
   - Modify dispatchers to include `_meta` in responses

4. **Document context policy** (S)
   - Create `docs/CONTEXT_POLICY.md` as specified above
   - Link from CLAUDE.md

5. **Add file timestamp checking to YAML caches** (S)
   - Store `_yaml_mtime` alongside cached data
   - Check on each access, invalidate if changed

### Deeper Refactors (Multi-day)

1. **Centralized context budget system** (M)
   - Create `ContextBudget` class tracking total output size
   - Wrap all tool dispatchers with budget middleware
   - Log budget consumption per call

2. **Structured logging for context observability** (M)
   - Add `@log_context` decorator to dispatchers
   - Log: input params, output size, execution time, truncation
   - Enable `ARIA_LOG_JSON=1` for machine-parseable logs

3. **Pydantic models for tool schemas** (M)
   - Define per-action input models (e.g., `RouteParams`, `SearchParams`)
   - Validate at dispatcher level before delegation
   - Generate JSON Schema from models

4. **Output truncation wrapper** (M)
   - Create `truncate_list()`, `summarize_route()` helpers
   - Apply configurable limits from `context_policy.py`
   - Add `truncated: true` metadata

5. **Session context manager** (L)
   - Create `SessionContext` class holding all per-session state
   - Pass through tool calls as optional parameter
   - Prepare for potential multi-session MCP server

---

## F) Suggested Code Changes

### Change 1: Add Reset Functions to YAML Caches

```diff
--- a/src/aria_esi/mcp/sde/tools_easy80.py
+++ b/src/aria_esi/mcp/sde/tools_easy80.py
@@ -113,6 +113,18 @@ from aria_esi.mcp.sde.queries import get_query_service
 _efficacy_rules_cache: dict | None = None
 _meta_alternatives_cache: dict | None = None
 _breakpoint_skills_cache: dict | None = None
+_yaml_mtimes: dict[str, float] = {}
+
+
+def reset_easy80_caches() -> None:
+    """Reset all Easy 80% caches (for testing and hot-reload)."""
+    global _efficacy_rules_cache, _meta_alternatives_cache, _breakpoint_skills_cache, _yaml_mtimes
+    _efficacy_rules_cache = None
+    _meta_alternatives_cache = None
+    _breakpoint_skills_cache = None
+    _yaml_mtimes.clear()


 def load_breakpoint_skills() -> dict:
```

### Change 2: Add Output Metadata Wrapper

```python
# New file: src/aria_esi/mcp/context.py
"""Context management utilities for MCP tool outputs."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class OutputMeta:
    """Metadata for tool outputs."""
    count: int
    truncated: bool = False
    truncated_from: int | None = None
    timestamp: str | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def to_dict(self) -> dict[str, Any]:
        d = {"count": self.count, "timestamp": self.timestamp}
        if self.truncated:
            d["truncated"] = True
            d["truncated_from"] = self.truncated_from
        return d


def wrap_output(data: dict, items_key: str, max_items: int = 50) -> dict:
    """Wrap tool output with metadata and optional truncation."""
    items = data.get(items_key, [])
    original_count = len(items)
    truncated = original_count > max_items

    if truncated:
        data[items_key] = items[:max_items]

    data["_meta"] = OutputMeta(
        count=len(data[items_key]),
        truncated=truncated,
        truncated_from=original_count if truncated else None,
    ).to_dict()

    return data
```

### Change 3: Pytest Fixture for Singleton Resets

```python
# Add to tests/conftest.py

import pytest

@pytest.fixture(autouse=True)
def reset_all_singletons():
    """Reset all module-level singletons between tests."""
    # Import reset functions
    from aria_esi.mcp.market.cache import reset_market_cache
    from aria_esi.mcp.sde.tools_easy80 import reset_easy80_caches
    from aria_esi.mcp.sde.tools_activities import reset_activities_cache
    from aria_esi.fitting.eos_data import reset_eos_data_manager
    from aria_esi.services.arbitrage_engine import reset_arbitrage_engine
    from aria_esi.services.history_cache import reset_history_cache_service
    from aria_esi.cache import clear_cache

    # Reset before test
    reset_market_cache()
    reset_easy80_caches()
    reset_activities_cache()
    reset_eos_data_manager()
    reset_arbitrage_engine()
    reset_history_cache_service()
    clear_cache()

    yield

    # Reset after test
    reset_market_cache()
    reset_easy80_caches()
    reset_activities_cache()
    reset_eos_data_manager()
    reset_arbitrage_engine()
    reset_history_cache_service()
    clear_cache()
```

---

## Special Focus Checklist Answers

### 1. Where is conversation/session context stored, and how is it bounded?

**Location:** Session context is assembled by boot hooks into `userdata/pilots/{active_pilot}/.session-context.json`. Pilot profile (`profile.md`) and persona files are loaded at session start per CLAUDE.md instructions.

**Bounding:** Context is implicitly bounded by:
- File size limits in `sanitize_field()` (MAX_NAME_LENGTH=100, MAX_SUMMARY_LENGTH=200)
- Persona file count (typically 5-7 files, ~15KB total)
- No explicit token budget enforcement

**Gap:** No measurement or enforcement of total context size.

### 2. What prevents tool outputs from flooding the model context?

**Current controls:**
- Per-tool `max_limit` constants (10-100 items depending on tool)
- `limit` parameters clamped to max values
- Some tools have `pages_truncated` tracking

**Gap:** No centralized budget, no automatic summarization, no cross-tool coordination.

### 3. How does the system decide what to keep vs. summarize vs. drop?

**Current behavior:** Keep everything within per-tool limits. No summarization layer exists. Truncation is basic (first N items).

**Gap:** No intelligent summarization (e.g., route middle-hop compression, result clustering).

### 4. How are provenance and citations handled for retrieved data/tool outputs?

**Current approach:** `DATA_VERIFICATION.md` documents trust hierarchy. Skills like `/mission-brief` cite sources in output. No automatic citation injection.

**Gap:** Provenance metadata not standardized in tool outputs.

### 5. How is token usage measured and enforced?

**Current:** Not measured or enforced at Python layer. Relies on Claude Code's context window.

**Gap:** No visibility into token consumption per segment.

### 6. How are secrets/PII prevented from entering prompts?

**Current controls:**
- OAuth tokens stored in `userdata/credentials/` (not in profile/persona)
- `sanitize_field()` strips certain patterns
- Volatile data (wallet, location) only queried on explicit request per CLAUDE.md

**Gap:** No automated PII detection; relies on data architecture separation.

### 7. What is the recommended architecture for context modules in this repo?

**Recommended structure:**
```
src/aria_esi/
├── mcp/
│   ├── context.py          # NEW: Context policy, truncation, metadata
│   ├── context_policy.py   # NEW: Centralized limits configuration
│   ├── dispatchers/        # Existing domain dispatchers
│   └── ...
├── core/
│   ├── logging.py          # Extend with context logging
│   └── ...
```

**Key principles:**
1. Centralize limits in `context_policy.py`
2. Wrap all tool outputs through `context.wrap_output()`
3. Add structured logging for observability
4. Reset singletons between sessions
5. Trust SDE/ESI data (controlled sources); sanitize user-provided data
