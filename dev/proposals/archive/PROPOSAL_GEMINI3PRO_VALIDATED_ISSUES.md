# Improvement Proposal: Gemini 3 Pro Review Validated Issues

**Date:** 2026-01-31
**Source Review:** `dev/reviews/GEMINI3PRO_REVIEW_*.md`
**Status:** ✅ COMPLETE (2026-02-02)
**Completed:** Issues #1, #2, #4 (universe cache, EOS vendored, typing roadmap documented)
**Remaining:** Issue #3 (test coverage) is ongoing maintenance, not a discrete deliverable

> **Validation (2026-02-02):** Issue #4 is COMPLETE:
> - `docs/TYPING_ROADMAP.md` exists with full 6-phase roadmap
> - `README.md` has typing roadmap summary table (lines 177-194)
> - `CONTRIBUTING.md` now links to typing roadmap with code quality guidelines
> - `pyproject.toml` has comprehensive mypy config with phase markers

---

## Executive Summary

This proposal addresses issues identified in the Gemini 3 Pro security/code review. Each claim was investigated against the actual codebase. Three claims were validated, one was partially validated with caveats, and one was invalidated as a misunderstanding of the architecture.

---

## Claim Validation Summary

| # | Claim | Verdict | Action |
|---|-------|---------|--------|
| 1 | Universe cache not distributed | ✅ **VALIDATED** | Implement fix |
| 2 | eos dependency fragility | ✅ **VALIDATED** | Implement fix |
| 3 | Low test coverage in security modules | ⚠️ **PARTIAL** | Lower priority |
| 4 | Loose type safety configuration | ✅ **VALIDATED** | Document intent |
| 5 | Brittle prompt injection defenses | ❌ **INVALIDATED** | No action needed |

---

## Issue 1: Universe Cache Distribution (VALIDATED)

### Evidence

```
.gitignore:30     → src/aria_esi/data/universe.universe
dev/RELEASE.md:11 → "Takes ~3 hours due to API rate limits"
Actual file size  → 816 KB
```

The universe graph file IS gitignored, and rebuilding DOES take ~3 hours. A fresh clone cannot use route planning without this build step.

### Recommendation

**Immediate (v2.0.1):** Include `universe.universe` in the repository.

At 816 KB, this is well within Git's comfort zone for binary files. The file changes only when EVE expansions add/remove systems (rare - once or twice per year).

**Implementation:**

```bash
# 1. Remove from .gitignore
sed -i '' '/universe\.universe/d' .gitignore

# 2. Add to repo
git add src/aria_esi/data/universe.universe
git commit -m "Include pre-built universe graph for zero-config installation"
```

**Alternative (if file grows significantly):**

- Publish as GitHub Release asset
- Add first-run download logic to `aria-esi` CLI:
  ```python
  def ensure_universe_cache():
      if not UNIVERSE_PATH.exists():
          download_from_release()
  ```

### Impact

- **Before:** Fresh install requires 3-hour build
- **After:** Works immediately after `uv sync`

---

## Issue 2: eos Dependency Fragility (VALIDATED)

### Evidence

```toml
# pyproject.toml:66
"eos @ git+https://github.com/pyfa-org/eos.git@c2cc80fd"

# pyproject.toml:238-242 (acknowledgment of build issues)
[tool.uv.extra-build-dependencies]
eos = ["pip"]
```

The eos fitting engine is pinned to a specific commit of a third-party repository. If that repo is deleted or force-pushed, installations break permanently.

### Recommendation

**Short-term (v2.1):** Vendor a fork under organization control.

1. Fork `pyfa-org/eos` to `aria-tools/eos-vendored`
2. Tag the specific commit as `v0.1.0-aria`
3. Update dependency:
   ```toml
   "eos @ git+https://github.com/aria-tools/eos-vendored.git@v0.1.0-aria"
   ```

**Medium-term (v2.2):** Build and publish wheel.

1. Create GitHub Actions workflow to build wheels for common platforms
2. Publish to PyPI as `aria-eos` or private package index
3. Update dependency to simple version pin:
   ```toml
   "aria-eos>=0.1.0"
   ```

**Graceful degradation (v2.0.1):** Make fitting optional.

The `fitting` extra already isolates this dependency. Ensure `fitting()` MCP tool returns a clear error if eos is not installed:

```python
def fitting(action: str, **kwargs):
    try:
        from aria_esi.mcp.fitting import calculate_stats
    except ImportError:
        return {"error": "Fitting requires optional dependency. Install with: uv pip install aria[fitting]"}
```

### Impact

- **Before:** Single point of failure in third-party repo
- **After:** Controlled dependency with fallback behavior

---

## Issue 3: Test Coverage (PARTIALLY VALIDATED)

### Evidence

```toml
# pyproject.toml:130-133
# Note: Core modules (auth, client, retry) have 49-73% coverage
# Command modules: clones 72%, skills 89%, industry 72%, mining 76%, contracts 50%
fail_under = 45
```

**Actual state:**
- `auth.py`: 796 lines, 22 test functions in `test_auth.py`
- Coverage range: 49-73% (not "~50%" as claimed)
- `contracts` is a command module, not a "core security module"

### Assessment

The review overstates the risk. The auth module:
- Has proper security practices (permission checking, keyring support)
- Has 22 dedicated tests
- Uses structured logging and path validation

The 45% threshold is low, but this is acknowledged and tracked.

### Recommendation (Lower Priority)

**v2.2:** Raise coverage floor incrementally.

```toml
# Phased approach
fail_under = 50  # v2.1
fail_under = 55  # v2.2
fail_under = 60  # v2.3
```

**Focus areas:**
1. `auth.py` edge cases (token refresh failures, permission errors)
2. `client.py` retry logic
3. Error paths in credential loading

### Impact

- Incremental improvement without blocking releases
- Targeted testing of security-critical paths

---

## Issue 4: Type Safety Configuration (VALIDATED - BY DESIGN)

### Evidence

```toml
# pyproject.toml:207-208
check_untyped_defs = false
disallow_untyped_defs = false
```

The review correctly identifies these settings. However, the configuration explicitly documents this as **Phase 1 of a gradual adoption roadmap**:

```toml
# GRADUAL TYPING ADOPTION ROADMAP
# Phase 1 (current): Baseline - catches syntax errors, undefined names
# Phase 2: Enable union-attr, attr-defined - fix dict/list type annotations
# Phase 3: Enable arg-type, return-value - fix function signatures
# Phase 4: Enable disallow_untyped_defs on core modules
# Phase 5: Strict mode on all modules
```

Phases 2 and 3 are already complete (lines 219-220).

### Recommendation

**No code change needed.** Document the roadmap publicly.

Add to `README.md` or `CONTRIBUTING.md`:

```markdown
## Type Safety

We use gradual typing adoption. Current phase: **Phase 3 complete**.

Next milestone: Enable `disallow_untyped_defs` on core modules (auth, client).
```

**v2.2:** Enable `check_untyped_defs = true` as the next phase.

### Impact

- Transparent roadmap addresses the concern
- Continues planned improvement trajectory

---

## Issue 5: Prompt Injection Defenses (INVALIDATED)

### Review Claim

> The security hardening in `.claude/scripts/aria-context-assembly.py` relies on regex-based filtering... These defenses are "Tier I" (sanitization) and can often be bypassed.

### Evidence Against

The review **misidentifies the purpose** of `aria-context-assembly.py`.

**What the script actually does:**
- Parses project metadata files (markdown with `**Status:**`, `**Aliases:**` fields)
- Sanitizes field values before including in `.session-context.json`
- Used for natural language references ("the new corp" → project name lookup)

**What it does NOT do:**
- Process user prompts to the LLM
- Defend against prompt injection attacks

**The actual prompt injection defense** uses structural data delimiters, documented in:
- `CLAUDE.md` (lines 30-54): Untrusted Data Handling
- `docs/PERSONA_LOADING.md` (lines 202-265): Security: Data Delimiters

**Defense-in-depth architecture:**

```
Layer 1: Path validation (prevents loading arbitrary files)
Layer 2: Data delimiters (<untrusted-data> tags wrap all external content)
Layer 3: Compiled artifacts (pre-wrapped at build time with integrity hashes)
Layer 4: Metadata sanitization (context-assembly.py - defense in depth)
```

The regex patterns in `aria-context-assembly.py` are **Layer 4** - a belt-and-suspenders approach for session context metadata, not the primary defense.

**Evidence from PERSONA_LOADING.md:**

```markdown
All persona files are **untrusted data sources**. The compiled artifact
provides defense-in-depth by pre-applying security delimiters.

| Field | Purpose |
|-------|---------|
| `raw_content` | All files with `<untrusted-data>` delimiters pre-applied |
| `integrity.hash` | Combined hash for tampering detection |
```

### Recommendation

**No action needed.** The architecture is sound.

**Optional enhancement:** Add architecture diagram to security documentation showing the defense layers.

---

## Implementation Priority

| Priority | Issue | Effort | Risk Reduction |
|----------|-------|--------|----------------|
| P0 | #1 Universe cache | 30 min | High (UX) |
| P1 | #2 eos vendoring | 2-4 hours | High (stability) |
| P2 | #4 Document typing roadmap | 30 min | Low (transparency) |
| P3 | #3 Coverage improvements | Ongoing | Medium |

---

## Appendix: Files Reviewed

```
.gitignore
dev/RELEASE.md
pyproject.toml
.claude/scripts/aria-context-assembly.py
docs/PERSONA_LOADING.md
src/aria_esi/core/auth.py
tests/test_auth.py
src/aria_esi/data/universe.universe (816 KB)
```
