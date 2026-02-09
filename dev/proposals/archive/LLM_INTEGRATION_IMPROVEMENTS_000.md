# LLM Integration Improvements Proposal

**Status:** ✅ P0/P1 COMPLETE (2026-02-02)
**Implemented:** Context-aware policy, byte limit enforcement, trace/turn logging, skill preflight, provenance fields
**Remaining:** Minor permission cleanup (python3:* in settings.local.json)

---

## Executive Summary

This proposal addresses findings from the LLM integration review (`dev/reviews/LLM_INTEGRATION_000.md`). The review identified gaps in security enforcement, context management, observability, and skill maturity. The proposed improvements are organized into four work streams with clear priorities and dependencies.

**Key findings:**
- Policy engine doesn't enforce elevated sensitivity for authenticated operations
- Output byte limits are advisory only, not enforced
- No trace/turn correlation for observability
- Broad Bash permissions expand prompt injection blast radius
- Skills lack preflight validation and golden tests

**Recommendation:** Address P0 security issues first, then build out infrastructure for P1/P2 improvements.

---

## Review Summary

### Scores by Category (from review)

| Category | Score | Key Gap |
|----------|-------|---------|
| Reliability | 3/5 | No model invocation adapter; no hard output-size enforcement |
| Security | 4/5 | Context-sensitive auth missing; broad Bash permissions |
| Maintainability | 4/5 | Strong dispatcher design; skill metadata schema defined |
| Observability | 3/5 | JSON logging exists but no trace/turn correlation |
| Data Governance | 3/5 | Provenance required by docs but not enforced in outputs |
| Cost Control | 3/5 | Budgets advisory only; no hard byte enforcement |
| Skill-readiness | 3/5 | Frontmatter schema present; no preflight or golden tests |

### Issues by Priority

| Priority | Issue | Risk |
|----------|-------|------|
| P0 | Policy doesn't elevate sensitivity for `use_pilot_skills` | Authenticated data exposed without proper gating |
| P0 | No skill preflight validates `requires_pilot`, `esi_scopes` | Skills execute without required context |
| P1 | Per-tool byte limits not enforced | Context overflow, degraded performance |
| P1 | No trace/turn IDs in logging | Cannot correlate LLM calls with tool calls |
| P2 | Broad Bash permissions include `python3`, `pip3` | Prompt injection blast radius |
| P2 | No CI check for skill index staleness | Metadata drift from SKILL.md changes |

---

## Work Streams

### Stream 1: Security Hardening (P0)

**Goal:** Close authentication and permission gaps before they become exploitable.

#### 1.1 Context-Aware Policy for Authenticated Operations

**Problem:** `fitting(action="calculate_stats", use_pilot_skills=True)` accesses authenticated pilot data but policy treats it as PUBLIC sensitivity.

**Solution:** Modify `PolicyEngine.get_action_sensitivity()` to accept context and elevate sensitivity when authenticated data is requested.

**Files to modify:**
- `src/aria_esi/mcp/policy.py:L276-L345` - Add context parameter to `get_action_sensitivity()`
- `src/aria_esi/mcp/dispatchers/fitting.py:L31-L99` - Pass context to `check_capability()`
- `tests/mcp/test_policy.py` - Add tests for context-aware sensitivity

**Implementation:**

```python
# policy.py
def get_action_sensitivity(
    self, dispatcher: str, action: str, context: dict[str, Any] | None = None
) -> SensitivityLevel:
    """Get sensitivity level, elevating for authenticated context."""
    # Context-aware elevation
    if dispatcher == "fitting" and action == "calculate_stats" and context:
        if context.get("use_pilot_skills"):
            return SensitivityLevel.AUTHENTICATED

    # Default lookup
    dispatcher_actions = DEFAULT_ACTION_SENSITIVITY.get(dispatcher, {})
    return dispatcher_actions.get(
        action, dispatcher_actions.get("_default", SensitivityLevel.PUBLIC)
    )

def check_capability(
    self,
    dispatcher: str,
    action: str,
    *,
    context: dict[str, Any] | None = None,
) -> None:
    # ... existing code ...
    sensitivity = self.get_action_sensitivity(dispatcher, action, context)
    # ... rest of check ...
```

```python
# dispatchers/fitting.py
check_capability("fitting", action, context={"use_pilot_skills": use_pilot_skills})
```

**Tests to add:**
```python
def test_fitting_with_pilot_skills_requires_authenticated_level():
    """Fitting with pilot skills should require AUTHENTICATED sensitivity."""
    engine = PolicyEngine(PolicyConfig(allowed_levels=[SensitivityLevel.PUBLIC]))
    with pytest.raises(CapabilityDenied):
        engine.check_capability(
            "fitting", "calculate_stats",
            context={"use_pilot_skills": True}
        )
```

**Effort:** S (Small)

---

#### 1.2 Tighten Bash Permissions

**Problem:** `.claude/settings.local.json` includes broad permissions for `python3:*` and `pip3 install:*`, violating CLAUDE.md's `uv run` policy.

**Solution:** Remove bare Python/pip permissions and rely exclusively on `uv run` wrappers.

**Files to modify:**
- `.claude/settings.local.json:L64-L67` - Remove `python3:*` and `pip3 install:*`

**Current (problematic):**
```json
"Bash(python3 -m pytest:*)",
"Bash(python3:*)",
"Bash(pip3 install:*)",
```

**Proposed:**
```json
// Remove these lines entirely - uv run wrappers already exist:
// "Bash(python3:*)",
// "Bash(pip3 install:*)",
// Keep specific pytest via uv:
"Bash(uv run pytest:*)",
```

**Effort:** S (Small)

---

### Stream 2: Context Management (P1)

**Goal:** Enforce output limits and add provenance for data governance.

#### 2.1 Enforce Per-Tool Byte Size Limits

**Problem:** `GLOBAL.MAX_OUTPUT_SIZE_BYTES` (10KB) is defined but never enforced. Large outputs can overflow context.

**Solution:** Add `_enforce_output_bytes()` function called by `wrap_output()` and `wrap_output_multi()`.

**Files to modify:**
- `src/aria_esi/mcp/context.py:L90-L200` - Add enforcement function
- `tests/mcp/test_context.py` - Add truncation tests

**Implementation:**

```python
# context.py
import json

def _enforce_output_bytes(data: dict[str, Any], items_key: str) -> None:
    """
    Trim list payloads if serialized output exceeds GLOBAL.MAX_OUTPUT_SIZE_BYTES.

    Modifies data in place if truncation needed.
    """
    try:
        size = len(json.dumps(data))
    except (TypeError, ValueError):
        return  # Can't serialize, skip enforcement

    if size <= GLOBAL.MAX_OUTPUT_SIZE_BYTES:
        return

    items = data.get(items_key)
    if not isinstance(items, list) or len(items) <= 1:
        return  # Can't truncate further

    # Estimate items to keep based on size ratio
    ratio = GLOBAL.MAX_OUTPUT_SIZE_BYTES / max(size, 1)
    new_len = max(1, int(len(items) * ratio * 0.9))  # 10% buffer

    original_count = len(items)
    data[items_key] = items[:new_len]

    meta = data.setdefault("_meta", {})
    meta["truncated"] = True
    meta["truncated_from"] = original_count
    meta["original_bytes"] = size
    meta["byte_limit_enforced"] = True


def wrap_output(
    data: dict[str, Any],
    items_key: str,
    max_items: int = 50,
) -> dict[str, Any]:
    # ... existing truncation logic ...

    data["_meta"] = OutputMeta(
        count=len(items),
        truncated=truncated,
        truncated_from=original_count if truncated else None,
    ).to_dict()

    # NEW: Enforce byte limit after item truncation
    _enforce_output_bytes(data, items_key)

    return data
```

**Tests to add:**
```python
def test_wrap_output_enforces_byte_limit():
    """wrap_output should truncate when exceeding byte limit."""
    # Create oversized payload
    large_data = {"items": [{"id": i, "name": "x" * 1000} for i in range(100)]}
    wrapped = wrap_output(large_data, "items", max_items=100)

    # Should be truncated to fit within GLOBAL.MAX_OUTPUT_SIZE_BYTES
    assert wrapped["_meta"]["byte_limit_enforced"] is True
    assert len(json.dumps(wrapped)) <= GLOBAL.MAX_OUTPUT_SIZE_BYTES
```

**Effort:** M (Medium)

---

#### 2.2 Add Provenance Fields to `_meta`

**Problem:** `docs/CONTEXT_POLICY.md` requires source and as_of for external data, but these aren't included in tool outputs.

**Solution:** Extend `OutputMeta` to support optional provenance fields.

**Files to modify:**
- `src/aria_esi/mcp/context.py:L52-L88` - Extend OutputMeta
- Dispatchers that return external data - Add source/as_of

**Implementation:**

```python
# context.py
@dataclass
class OutputMeta:
    """Metadata wrapper for tool outputs."""
    count: int
    truncated: bool = False
    truncated_from: int | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # NEW: Provenance fields
    source: str | None = None
    as_of: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"count": self.count, "timestamp": self.timestamp}
        if self.truncated:
            d["truncated"] = True
            d["truncated_from"] = self.truncated_from
        if self.source:
            d["source"] = self.source
        if self.as_of:
            d["as_of"] = self.as_of
        return d
```

**Usage in dispatchers:**
```python
# market.py - Fuzzwork price data
data["_meta"] = OutputMeta(
    count=len(prices),
    source="fuzzwork",
    as_of=cache_timestamp.isoformat() if cache_timestamp else None,
).to_dict()
```

**Effort:** M (Medium)

---

### Stream 3: Observability (P1)

**Goal:** Enable correlation of LLM calls with tool calls for debugging and auditing.

#### 3.1 Add Trace/Turn IDs to Logging

**Problem:** No correlation between LLM conversation turns and tool invocations. Difficult to debug multi-step issues.

**Solution:** Add optional `trace_id` and `turn_id` fields propagated through context and audit logs.

**Files to modify:**
- `src/aria_esi/mcp/context.py:L419-L507` - Add trace context to `log_context()`
- `src/aria_esi/mcp/policy.py:L371-L401` - Include trace in audit logs
- `src/aria_esi/core/logging.py` - Add trace ID support

**Implementation:**

```python
# context.py
from contextvars import ContextVar

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_turn_id: ContextVar[int | None] = ContextVar("turn_id", default=None)


def set_trace_context(trace_id: str, turn_id: int) -> None:
    """Set trace context for current request."""
    _trace_id.set(trace_id)
    _turn_id.set(turn_id)


def get_trace_context() -> dict[str, Any]:
    """Get current trace context."""
    return {
        "trace_id": _trace_id.get(),
        "turn_id": _turn_id.get(),
    }


def log_context(
    dispatcher: str,
    action: str,
    params: dict[str, Any],
    result_bytes: int,
) -> None:
    """Log MCP call with trace context."""
    trace = get_trace_context()
    logger.info(
        "mcp_call",
        extra={
            "dispatcher": dispatcher,
            "action": action,
            "params": _sanitize_params(params),
            "result_bytes": result_bytes,
            **trace,  # Include trace_id and turn_id
        },
    )
```

**Dispatcher integration:**
```python
# Each dispatcher can set trace from incoming params
if params.get("_trace_id"):
    set_trace_context(params["_trace_id"], params.get("_turn_id", 0))
```

**Effort:** M (Medium)

---

### Stream 4: Skill Maturity (P2)

**Goal:** Improve skill reliability through preflight validation and testing.

#### 4.1 Skill Preflight Validator

**Problem:** Skills with `requires_pilot: true` or `esi_scopes` can execute without the required context present.

**Solution:** Create `aria-skill-preflight.py` script that validates skill prerequisites.

**Files to create:**
- `.claude/scripts/aria-skill-preflight.py` - Preflight validation script

**Implementation:**

```python
#!/usr/bin/env python3
"""
Skill preflight validator.

Validates that prerequisites are met before skill execution:
- Active pilot exists if requires_pilot: true
- Required data sources are readable
- Required ESI scopes are authorized
"""
import json
import sys
from pathlib import Path


def load_active_pilot(root: Path) -> dict | None:
    """Load active pilot from config/registry."""
    config_path = root / "userdata" / "config.json"
    registry_path = root / "userdata" / "pilots" / "_registry.json"

    if not config_path.exists():
        return None

    config = json.loads(config_path.read_text())
    active_id = config.get("active_pilot")

    if not active_id or not registry_path.exists():
        return None

    registry = json.loads(registry_path.read_text())
    for pilot in registry.get("pilots", []):
        if str(pilot.get("character_id")) == str(active_id):
            return pilot
    return None


def validate_skill(root: Path, skill_name: str) -> dict:
    """Validate prerequisites for a skill."""
    index_path = root / ".claude" / "skills" / "_index.json"
    index = json.loads(index_path.read_text())

    skill = index.get("skills", {}).get(skill_name)
    if not skill:
        return {"ok": False, "error": f"Skill '{skill_name}' not found"}

    result = {"ok": True, "warnings": []}

    # Check requires_pilot
    if skill.get("requires_pilot"):
        pilot = load_active_pilot(root)
        if not pilot:
            result["ok"] = False
            result["missing_pilot"] = True
            result["warnings"].append("Skill requires active pilot but none configured")

    # Check data sources exist
    missing_sources = []
    for source in skill.get("data_sources", []):
        source_path = root / source.replace("{active_pilot}", pilot.get("directory", "") if pilot else "")
        if not source_path.exists():
            missing_sources.append(source)

    if missing_sources:
        result["warnings"].append(f"Missing data sources: {missing_sources}")
        result["missing_sources"] = missing_sources

    # Check ESI scopes (would require ESI token introspection)
    # For now, just document required scopes
    if skill.get("esi_scopes"):
        result["required_scopes"] = skill["esi_scopes"]

    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "Usage: aria-skill-preflight.py <skill-name>"}))
        sys.exit(1)

    skill_name = sys.argv[1]
    root = Path(__file__).resolve().parents[2]

    result = validate_skill(root, skill_name)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
```

**Effort:** M (Medium)

---

#### 4.2 Skill Index Staleness Check

**Problem:** Changes to SKILL.md frontmatter don't automatically update `_index.json` until next boot.

**Solution:** Add `--check` mode to `aria-skill-index.py` for CI validation.

**Files to modify:**
- `.claude/scripts/aria-skill-index.py` - Add check mode
- CI configuration (if exists)

**Implementation addition:**

```python
# aria-skill-index.py
def check_index_staleness(root: Path) -> bool:
    """Check if index is stale compared to SKILL.md files."""
    index_path = root / ".claude" / "skills" / "_index.json"
    if not index_path.exists():
        return True

    index_mtime = index_path.stat().st_mtime
    skills_dir = root / ".claude" / "skills"

    for skill_md in skills_dir.rglob("SKILL.md"):
        if skill_md.stat().st_mtime > index_mtime:
            return True

    return False


if __name__ == "__main__":
    if "--check" in sys.argv:
        if check_index_staleness(ROOT):
            print("ERROR: Skill index is stale. Run aria-skill-index.py to update.")
            sys.exit(1)
        print("OK: Skill index is current.")
        sys.exit(0)
```

**Effort:** S (Small)

---

#### 4.3 Golden Tests for Skills

**Problem:** Skill outputs are unvalidated free text with no regression protection.

**Solution:** Add golden test fixtures for key skills.

**Files to create:**
- `tests/skills/` - Skill test directory
- `tests/skills/fixtures/` - Expected outputs
- `tests/skills/test_skill_outputs.py` - Golden test harness

**Example structure:**
```
tests/skills/
  fixtures/
    aria-status/
      input_01.json
      expected_01.md
    route/
      input_01.json
      expected_01.md
  test_skill_outputs.py
```

**Effort:** M (Medium)

---

## Priority Matrix

| Phase | Stream | Items | Effort | Dependencies |
|-------|--------|-------|--------|--------------|
| **1** | Security | 1.1, 1.2 | S+S | None |
| **2** | Context | 2.1, 2.2 | M+M | Phase 1 |
| **3** | Observability | 3.1 | M | Phase 1 |
| **4** | Skill Maturity | 4.1, 4.2, 4.3 | M+S+M | Phases 1-2 |

---

## Implementation Plan

### Phase 1: Security Hardening (Immediate)

1. **Context-aware policy** (1.1)
   - Modify `get_action_sensitivity()` signature
   - Update fitting dispatcher
   - Add tests

2. **Permission tightening** (1.2)
   - Audit `.claude/settings.local.json`
   - Remove bare Python/pip permissions
   - Verify `uv run` alternatives cover all use cases

### Phase 2: Context Management

3. **Byte limit enforcement** (2.1)
   - Implement `_enforce_output_bytes()`
   - Integrate with wrap_output functions
   - Add overflow tests

4. **Provenance fields** (2.2)
   - Extend OutputMeta dataclass
   - Update market/SDE dispatchers
   - Document expected sources

### Phase 3: Observability

5. **Trace correlation** (3.1)
   - Add contextvars for trace/turn
   - Update logging functions
   - Add audit log fields

### Phase 4: Skill Maturity

6. **Preflight validator** (4.1)
   - Create aria-skill-preflight.py
   - Document in CLAUDE.md
   - Add boot integration (optional)

7. **Staleness check** (4.2)
   - Add --check mode
   - Integrate with CI

8. **Golden tests** (4.3)
   - Create test fixtures
   - Write test harness
   - Add 2-3 key skill tests

---

## Acceptance Criteria

### Security Hardening Checklist

- [ ] `use_pilot_skills=True` requires AUTHENTICATED sensitivity level
- [ ] Test verifies fitting with pilot skills is denied at PUBLIC level
- [ ] No bare `python3:*` or `pip3:*` in settings.local.json
- [ ] All Python execution uses `uv run` wrapper

### Context Management Checklist

- [ ] wrap_output enforces GLOBAL.MAX_OUTPUT_SIZE_BYTES
- [ ] Truncation metadata includes `byte_limit_enforced` flag
- [ ] OutputMeta supports `source` and `as_of` fields
- [ ] Market dispatcher outputs include Fuzzwork provenance

### Observability Checklist

- [ ] MCP calls logged with optional trace_id/turn_id
- [ ] Policy audit logs include trace context
- [ ] Log format documented for correlation

### Skill Maturity Checklist

- [ ] aria-skill-preflight.py validates requires_pilot
- [ ] Preflight reports missing data sources
- [ ] aria-skill-index.py --check detects staleness
- [ ] Golden tests exist for aria-status, route skills

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Policy changes break existing flows | Add tests before modifying; allow bypass for testing |
| Byte truncation loses critical data | Use 10% buffer; always keep at least 1 item |
| Trace overhead impacts performance | Make trace context optional; only log when set |
| Preflight blocks valid skill execution | Start with warnings; make blocking opt-in |

---

## Future Considerations

Items identified but not prioritized for this proposal:

1. **Compiled context artifacts** - Boot-time concatenation of persona/overlay content with actual `<untrusted-data>` tags (currently conceptual)

2. **LLM client adapter** - If direct model invocation is added, need timeout/retry wrapper in `src/aria_esi/llm/adapter.py`

3. **RAG for reference data** - Chunking/retrieval for large reference files instead of loading entire files

4. **Skill I/O schemas** - JSON Schema validation for skill inputs/outputs (extends ADR-002)

5. **Human-in-the-loop for writes** - `requires_confirmation` field in skill metadata for destructive operations

---

## References

- Review document: `dev/reviews/LLM_INTEGRATION_000.md`
- Skill metadata schema: `dev/decisions/ADR-002-skill-metadata-schema.md`
- Context policy: `docs/CONTEXT_POLICY.md`
- Policy implementation: `src/aria_esi/mcp/policy.py`
- Context wrappers: `src/aria_esi/mcp/context.py`
