# ARIA Project Review - January 2026

**Review Date:** 2026-01-18
**Revision:** 2.0 (Updated with remediation status)
**Scope:** LLM Integration Patterns, Claude Code Skills Architecture, Fitness to Purpose
**Audience:** Developers, Engineers, Contributors

---

## Executive Summary

This document captures findings from an architectural review of ARIA (Adaptive Reasoning & Intelligence Array), an EVE Online tactical assistant built on Claude Code. The review focuses on LLM integration patterns, skill system design, and operational reliability.

**Revision 2.0 Updates:**
- Three high-priority findings (2, 4, 9) have been partially remediated
- Test coverage improved from 19% to 42%
- `validate-overlays` command added for staleness/dependency detection
- Four new concerns identified during follow-up review

---

## Review Methodology

- Static analysis of project structure and configuration files
- Examination of skill definitions and loading pipelines
- Review of MCP server implementation and CLI fallback patterns
- Analysis of persona system and context management
- Evaluation against Claude Code Skills best practices
- Code coverage analysis via pytest-cov

---

## Remediation Status Summary

| Finding | Original Severity | Status | Notes |
|---------|------------------|--------|-------|
| 1. Session init context overhead | Medium | **Open** | Design tradeoff, not addressed |
| 2. Unvalidated overlay dependencies | High | **Mitigated** | `validate-overlays` command added |
| 3. MCP/CLI implementation duality | Medium | **Open** | No changes |
| 4. Pre-computed persona staleness | High | **Mitigated** | Staleness detection in `validate-overlays` |
| 5. Skill definition inconsistency | Medium | **Open** | No changes |
| 6. ESI read-only discovery latency | Low | **Open** | No changes |
| 7. Volatile data protocol unenforced | Medium | **Open** | No changes |
| 8. Multi-pilot complexity overhead | Low | **Open** | No changes |
| 9. Test coverage below threshold | High | **Improved** | 19% → 42%, significant gaps remain |
| 10. Persona-exclusive skill confusion | Low | **Fixed** | Improved stubs with availability table and faction change instructions |

---

## Findings

### Finding 1: Session Initialization Context Overhead

**Severity:** Medium
**Category:** Performance / Context Efficiency
**Status:** Open - Design Tradeoff

#### Problem Statement

The session bootstrap sequence loads all persona context files before any user interaction occurs. For users with `rp_level: full`, this loads 5+ files totaling 800-1500 tokens into context—regardless of whether persona-specific behavior will be invoked during the session.

This approach assumes all sessions will exercise persona features. In practice, many sessions involve simple queries (route planning, price checks) that never reference persona voice or faction-specific overlays.

#### Trace Locations

| File | Section | Relevance |
|------|---------|-----------|
| `CLAUDE.md` | Session Initialization, Step 3 | Mandates loading all `persona_context.files` at boot |
| `pilots/{id}/profile.md` | `persona_context.files` array | Defines the file list loaded unconditionally |
| `personas/{persona}/voice.md` | Entire file | Loaded at boot, may never be referenced |
| `personas/{persona}/intel-sources.md` | Entire file | Only relevant for `full` RP, loaded regardless |

#### Observable Symptoms

- Increased token usage in sessions that don't invoke persona-aware skills
- Longer effective context for simple queries
- No degradation in functionality—purely an efficiency concern

#### Measurement Approach

Compare token counts for identical queries between `rp_level: off` and `rp_level: full` sessions. The delta represents persona overhead.

---

### Finding 2: Skill Overlay Dependencies Are Implicit and Unvalidated

**Severity:** High
**Category:** Reliability / Silent Failures
**Status:** Mitigated - Reactive validation available

#### Problem Statement

The skill loading pipeline implements a three-level lookup chain:

1. Base skill: `.claude/skills/{name}/SKILL.md`
2. Persona overlay: `{persona_context.skill_overlay_path}/{name}.md`
3. Fallback overlay: `{persona_context.overlay_fallback_path}/{name}.md`

These paths are computed at profile creation time and stored in `persona_context`. No validation occurs at session start or skill invocation time to confirm these paths still resolve to existing files.

If a persona overlay file is renamed, moved, or deleted, the skill loads without its overlay—silently degrading functionality.

#### Remediation Applied

The `validate-overlays` command (`aria-esi validate-overlays`) now:
- Validates all files in `persona_context.files` exist
- Checks overlay paths for skills with `has_persona_overlay: true`
- Validates exclusive skill redirect paths
- Reports errors (critical), warnings (degraded), and stale (out-of-sync) issues

**Implementation:** `.claude/scripts/aria_esi/commands/persona.py:583-871`

#### Remaining Gap

Validation is **reactive** (command-invoked), not **proactive** (session-start). CLAUDE.md Session Initialization Step 3 still reads paths directly without validation. Users must remember to run validation after persona changes.

#### Trace Locations

| File | Section | Relevance |
|------|---------|-----------|
| `CLAUDE.md` | Skill Loading | Documents the lookup chain |
| `pilots/{id}/profile.md` | `persona_context.skill_overlay_path` | Pre-computed path, not validated at boot |
| `.claude/skills/_index.json` | `has_persona_overlay` flag | Indicates overlay expected |
| `commands/persona.py` | `validate_persona_context()` | New validation logic |

---

### Finding 3: MCP/CLI Implementation Duality

**Severity:** Medium
**Category:** Maintainability / Technical Debt
**Status:** Open

#### Problem Statement

Navigation features are implemented twice: once in MCP tools (`.claude/scripts/aria_esi/mcp/tools_*.py`) and again in CLI commands (`.claude/scripts/aria_esi/commands/navigation.py`). The "MCP with CLI fallback" pattern documented in CLAUDE.md requires both implementations to exist and stay synchronized.

Current state shows drift between implementations:
- MCP `universe_loop` integrates activity data; CLI `loop` command does not
- MCP tools use Pydantic models for response structure; CLI uses ad-hoc dicts
- Error handling patterns differ between the two codebases

#### Trace Locations

| File | LOC | Relevance |
|------|-----|-----------|
| `.claude/scripts/aria_esi/mcp/tools_route.py` | ~400 | MCP route implementation |
| `.claude/scripts/aria_esi/mcp/tools_loop.py` | ~500 | MCP loop implementation |
| `.claude/scripts/aria_esi/mcp/tools_activity.py` | ~300 | Activity integration (MCP only) |
| `.claude/scripts/aria_esi/commands/navigation.py` | ~500 | CLI implementations |
| `CLAUDE.md` | MCP Fallback Behavior table | Documents expected parity |

#### Observable Symptoms

- Feature available in MCP not available in CLI fallback
- Different response structures require conditional handling in skills
- Bug fixes applied to one implementation may not propagate to the other

#### Complexity Factors

- MCP tools use `UniverseGraph` class directly
- CLI commands invoke the same graph but with different wrapper code
- No shared abstraction layer between the two

---

### Finding 4: Pre-Computed Persona Context Staleness

**Severity:** High
**Category:** Reliability / Data Integrity
**Status:** Mitigated - Staleness detection available

#### Problem Statement

The `persona_context` section in pilot profiles contains pre-computed file paths:

```yaml
persona_context:
  files:
    - personas/_shared/pirate/identity.md
    - personas/_shared/pirate/terminology.md
    - personas/paria/manifest.yaml
    - personas/paria/voice.md
  skill_overlay_path: personas/paria/skill-overlays
```

These paths are computed by `aria-esi persona-context` and written to the profile. The session initialization sequence reads these paths directly without validating they still exist.

Staleness occurs when:
- Persona files are reorganized
- Persona directory is renamed
- User changes faction without regenerating context

#### Remediation Applied

The `validate-overlays` command includes staleness detection:
- Compares `persona_context` values against current profile settings
- Detects persona/branch/rp_level mismatches
- Identifies file list drift from reorganization
- Reports actionable fix recommendations

**Implementation:** `.claude/scripts/aria_esi/commands/persona.py:473-580` (`detect_staleness()`)

#### Remaining Gap

Staleness detection requires manual invocation. Session initialization does not automatically validate freshness. A stale `persona_context` will load the wrong persona files without warning.

#### Trace Locations

| File | Section | Relevance |
|------|---------|-----------|
| `pilots/{id}/profile.md` | `persona_context` block | Contains pre-computed paths |
| `commands/persona.py` | `detect_staleness()` | New staleness detection |
| `CLAUDE.md` | Session Initialization, Step 3 | Still reads paths without validation |

---

### Finding 5: Skill Definition Quality Inconsistency

**Severity:** Medium
**Category:** User Experience / Maintainability
**Status:** Open

#### Problem Statement

The 31 skill definitions in `.claude/skills/` exhibit inconsistent patterns:

- **Frontmatter completeness:** Some skills specify `data_sources`, `esi_scopes`, `model` hints; others have minimal metadata
- **Trigger phrase coverage:** Ranges from 2-3 generic triggers to 10+ specific patterns
- **Content length:** 20-line stubs to 150+ line comprehensive guides
- **Path references:** Some use `{active_pilot}` placeholder correctly, others hardcode or omit

The `_index.json` auto-generation captures structure but cannot enforce quality or consistency.

#### Trace Locations

| File | Issue |
|------|-------|
| `.claude/skills/_index.json` | Generated index reflects but doesn't validate quality |
| `.claude/skills/SCHEMA.md` | Defines optional fields, doesn't enforce minimums |
| `.claude/scripts/aria-skill-index.py` | Generator script, structural validation only |
| Individual `SKILL.md` files | Quality varies per skill |

#### Observable Symptoms

- Natural language triggers work well for some skills, poorly for others
- Users learn to use exact `/command` syntax, bypassing trigger system
- New contributors lack clear quality baseline for new skills

---

### Finding 6: ESI Read-Only Limitation Discovery Latency

**Severity:** Low
**Category:** User Experience
**Status:** Open

#### Problem Statement

ARIA's ESI integration is strictly read-only—it cannot execute in-game actions. This limitation is documented in CLAUDE.md but users encounter it only after formulating an action request:

- "Set my destination to Jita"
- "Buy 1000 Tritanium"
- "Accept this contract"

The refusal comes after Claude has processed the request, consuming context and user time.

#### Trace Locations

| File | Section | Relevance |
|------|---------|-----------|
| `CLAUDE.md` | ESI Capability Boundaries | Documents the limitation |
| `.claude/skills/help/SKILL.md` | Help content | Does not prominently surface limitation |
| `pilots/{id}/profile.md` | No relevant section | Limitation not per-pilot |

#### Observable Symptoms

- User asks for action, receives polite refusal
- Refusal consumes response context
- Repeated occurrences for users unfamiliar with ESI constraints

---

### Finding 7: Volatile Data Protocol Lacks Structural Enforcement

**Severity:** Medium
**Category:** Data Integrity / Trust
**Status:** Open

#### Problem Statement

The "Data Volatility" protocol in CLAUDE.md instructs:

> Never proactively mention volatile data (location, wallet, current ship). Only reference when explicitly requested via `/esi-query`.

This protocol relies entirely on LLM instruction following. There is no structural mechanism preventing volatile data from being:
- Loaded into context during session init
- Referenced by skills that read pilot profiles
- Mentioned in responses despite the instruction

#### Trace Locations

| File | Section | Relevance |
|------|---------|-----------|
| `CLAUDE.md` | Data Volatility | States the protocol |
| `docs/DATA_FILES.md` | Volatility classifications | Defines which data is volatile |
| `pilots/{id}/profile.md` | May contain stale location/ship data | Source of volatile data |
| `.claude/skills/*/SKILL.md` | `data_sources` field | Skills may load volatile data |

#### Observable Symptoms

- LLM references outdated location ("You're in Jita" when user has moved)
- Wallet balance mentioned from cached data
- User makes decisions based on stale information

---

### Finding 8: Multi-Pilot Architecture Overhead for Single-Pilot Users

**Severity:** Low
**Category:** User Experience / Complexity
**Status:** Open

#### Problem Statement

The multi-pilot architecture introduces resolution overhead:

```
.aria-config.json → active_pilot (ID)
    ↓
pilots/_registry.json → find entry → get directory
    ↓
pilots/{directory}/profile.md
```

This three-file resolution occurs even when only one pilot exists. The "single-pilot shortcut" documented in CLAUDE.md creates a separate code path:

> **Single-pilot shortcut:** If config doesn't exist and registry has one pilot, use that.

Two code paths (with-config and without-config) must be maintained and tested.

#### Trace Locations

| File | Relevance |
|------|-----------|
| `.aria-config.json` | May or may not exist |
| `pilots/_registry.json` | Always exists, may have 1 or N entries |
| `CLAUDE.md` | Session Initialization, Step 1 | Documents both paths |
| `.claude/scripts/aria_esi/core/auth.py` | Implements pilot resolution |

---

### Finding 9: Test Coverage Below Reliability Threshold

**Severity:** High
**Category:** Quality Assurance / Reliability
**Status:** Improved - Significant gaps remain

#### Problem Statement

For a system providing tactical recommendations (routes through dangerous space, threat assessments, financial queries), test coverage must support confident refactoring and regression detection.

#### Remediation Applied

Overall coverage improved from **19%** to **42%** (41.66% actual).

#### Current Coverage by Module

| Module | Coverage | Change | Risk |
|--------|----------|--------|------|
| **MCP tools** | 71-100% | Maintained | Low |
| **Core formatters** | 95% | New | Low |
| **Persona commands** | 68% | New | Medium |
| **Wallet commands** | 78% | New | Low |
| **Navigation commands** | 35% | Improved | High |
| **Most other commands** | 4-14% | Unchanged | High |

#### Remaining Gaps

Command modules remain undertested:

| Module | Coverage | Critical Paths Untested |
|--------|----------|------------------------|
| `assets.py` | 4% | Asset search, location queries |
| `contracts.py` | 7% | Contract parsing, status filtering |
| `clones.py` | 7% | Jump clone management |
| `industry.py` | 7% | Job status, blueprint lookup |
| `skills.py` | 8% | Queue parsing, skill lookup |
| `mining.py` | 6% | Ledger parsing, ore tracking |

#### Configuration Gap

`pyproject.toml` still has `fail_under = 19` despite 42% actual coverage. This allows coverage regression without CI failure.

#### Trace Locations

| File | Relevance |
|------|-----------|
| `pyproject.toml` | `[tool.coverage.report]` fail_under=19 |
| `tests/` | Test directory structure |
| `.github/workflows/ci.yml` | CI runs coverage |

---

### Finding 10: Persona-Exclusive Skill Availability Confusion

**Severity:** Low
**Category:** User Experience / Feature Discovery
**Status:** Fixed

#### Problem Statement

Certain skills are exclusive to specific personas:

| Skill | Exclusive To |
|-------|--------------|
| `mark-assessment` | PARIA (pirate) |
| `hunting-grounds` | PARIA (pirate) |
| `ransom-calc` | PARIA (pirate) |
| `escape-route` | PARIA (pirate) |
| `sec-status` | PARIA (pirate) |

When a user with a non-pirate faction invokes these skills, they receive a stub response indicating unavailability. The stub does not explain:
- Which faction/persona unlocks this skill
- Whether similar functionality exists for their faction
- How to change factions if desired

#### Remediation Applied

All 5 persona-exclusive skill stubs now include:
1. **Availability table** showing all pirate factions that unlock the skill
2. **Alternative suggestions** explaining similar empire functionality
3. **Enable instructions** with step-by-step faction change process

**Example stub structure:**
```markdown
## Availability
| Faction | Persona | Access |
|---------|---------|--------|
| `pirate` | PARIA | Yes |
| `angel_cartel` | PARIA-A | Yes |
| Empire factions | ARIA/etc | No |

## For Empire Pilots
[Alternative skill suggestions]

## Enabling This Skill
1. Edit profile.md faction field
2. Run: uv run aria-esi persona-context
3. Start new session
```

#### Trace Locations

| File | Relevance |
|------|-----------|
| `.claude/skills/_index.json` | `persona_exclusive` field |
| `.claude/skills/{exclusive-skill}/SKILL.md` | Improved stubs with availability info |
| `personas/paria-exclusive/` | Actual skill implementations |

---

## New Findings (Revision 2.0)

### Finding 11: Validation Is Reactive, Not Proactive

**Severity:** Medium
**Category:** Reliability / User Experience
**New in Revision 2.0**

#### Problem Statement

The `validate-overlays` command provides excellent detection of stale/missing dependencies, but validation requires explicit user invocation. Session initialization (CLAUDE.md Step 3) still loads `persona_context.files` directly without validation.

This creates a gap where:
1. User modifies profile faction/rp_level
2. User forgets to run `aria-esi persona-context`
3. Session starts with stale persona_context
4. Wrong persona files load (or load fails silently)
5. User experiences incorrect behavior

#### Proposed Mitigation

Session init could include a lightweight staleness check:
- Compare profile `faction` and `rp_level` against `persona_context` values
- If mismatch detected, warn user and suggest regeneration

#### Trace Locations

| File | Section | Relevance |
|------|---------|-----------|
| `CLAUDE.md` | Session Initialization, Step 3 | No validation before loading |
| `commands/persona.py` | `detect_staleness()` | Logic exists but not invoked at boot |

---

### Finding 12: Coverage Threshold Drift

**Severity:** Low
**Category:** Quality Assurance / Configuration
**New in Revision 2.0**

#### Problem Statement

`pyproject.toml` specifies `fail_under = 19` for coverage, but actual coverage is 42%. This configuration drift:
- Allows coverage to regress from 42% to 20% without CI failure
- Doesn't reflect the improved quality standard
- Creates false sense of CI enforcement

#### Trace Locations

| File | Line | Issue |
|------|------|-------|
| `pyproject.toml` | `fail_under = 19` | Should be ~40% to prevent regression |

#### Recommended Fix

```toml
[tool.coverage.report]
fail_under = 40  # Prevent regression from current 42%
```

---

### Finding 13: Gradual Typing Adoption Stalled

**Severity:** Low
**Category:** Maintainability / Technical Debt
**New in Revision 2.0**

#### Problem Statement

`pyproject.toml` documents a 5-phase typing roadmap:

```
Phase 1 (current): Baseline - catches syntax errors, undefined names
Phase 2: Enable union-attr, attr-defined
Phase 3: Enable arg-type, return-value
Phase 4: Enable disallow_untyped_defs on core modules
Phase 5: Strict mode on all modules
```

Currently, **11 error codes are disabled** in mypy. No progress has been made beyond Phase 1, and no tracking mechanism exists for advancement.

#### Impact

- Type errors not caught at development time
- Refactoring risk without type safety
- IDE tooling less effective

#### Trace Locations

| File | Section | Relevance |
|------|---------|-----------|
| `pyproject.toml` | `[tool.mypy]` | 11 disabled error codes |
| `pyproject.toml` | Comments | Documents roadmap with no progress tracking |

---

### Finding 14: persona.py Module Complexity

**Severity:** Low
**Category:** Maintainability / Code Organization
**New in Revision 2.0**

#### Problem Statement

`commands/persona.py` has grown to 924 lines with multiple responsibilities:
- Persona context generation (`build_persona_context()`)
- Profile parsing (`extract_profile_field()`, `extract_persona_context_from_profile()`)
- Staleness detection (`detect_staleness()`)
- Overlay validation (`validate_persona_context()`)
- Two CLI commands (`cmd_persona_context`, `cmd_validate_overlays`)

This creates:
- High cognitive load for maintainers
- Testing complexity (multiple concerns in one file)
- Risk of unintended coupling between responsibilities

#### Proposed Mitigation

Consider splitting into:
- `persona_context.py` - Context generation and profile updates
- `persona_validation.py` - Staleness detection and overlay validation

---

## Summary Matrix

| # | Finding | Severity | Status | Primary Location |
|---|---------|----------|--------|------------------|
| 1 | Session init context overhead | Medium | Open | `CLAUDE.md`, `profile.md` |
| 2 | Unvalidated overlay dependencies | High | Mitigated | `_index.json`, `persona.py` |
| 3 | MCP/CLI implementation duality | Medium | Open | `mcp/`, `commands/navigation.py` |
| 4 | Pre-computed persona staleness | High | Mitigated | `profile.md`, `persona.py` |
| 5 | Skill definition inconsistency | Medium | Open | `.claude/skills/` |
| 6 | ESI read-only discovery latency | Low | Open | `CLAUDE.md`, help skill |
| 7 | Volatile data protocol unenforced | Medium | Open | `CLAUDE.md`, `DATA_FILES.md` |
| 8 | Multi-pilot complexity overhead | Low | Open | `auth.py`, `CLAUDE.md` |
| 9 | Insufficient test coverage | High | Improved | `tests/`, `commands/` |
| 10 | Persona-exclusive skill confusion | Low | Fixed | `_index.json`, stub skills |
| 11 | Reactive validation | Medium | New | `CLAUDE.md`, `persona.py` |
| 12 | Coverage threshold drift | Low | New | `pyproject.toml` |
| 13 | Gradual typing stalled | Low | New | `pyproject.toml` |
| 14 | persona.py complexity | Low | New | `commands/persona.py` |

---

## Fitness to Purpose Assessment

### Strengths

ARIA demonstrates strong patterns for Claude Code skill integration:

1. **Well-structured skill system** with declarative frontmatter, auto-generated index, and persona overlay support
2. **Comprehensive MCP server** with 13+ tools for universe navigation, activity tracking, and route planning
3. **Multi-pilot architecture** supporting account switching and per-pilot personas
4. **Graceful degradation** - core works without keyring, tenacity, or MCP dependencies
5. **Documentation quality** - CLAUDE.md, skill docs, and architectural decision records
6. **CI/CD pipeline** with multi-Python-version testing and coverage reporting

### Areas for Investment

1. **Command module test coverage** - Critical paths in 10+ modules have <15% coverage
2. **Proactive validation** - Staleness detection exists but isn't invoked at session start
3. **Unified navigation layer** - MCP/CLI duality creates maintenance burden
4. **Type safety progression** - Phase 1 mypy adoption hasn't advanced

### Overall Assessment

ARIA is a **production-quality EVE Online assistant** with sophisticated skill loading, persona management, and universe navigation. The recent remediation work (validate-overlays, improved coverage) addresses the highest-severity findings.

Remaining risks are primarily in:
- Command module reliability (low test coverage)
- User experience during persona changes (reactive validation)
- Long-term maintainability (MCP/CLI duality, typing debt)

---

## Appendix A: Files Referenced

```
Configuration & Bootstrap
├── CLAUDE.md
├── .aria-config.json
├── pilots/_registry.json
└── pilots/{id}/profile.md

Skills System
├── .claude/skills/_index.json
├── .claude/skills/SCHEMA.md
├── .claude/skills/{name}/SKILL.md
└── .claude/scripts/aria-skill-index.py

Persona System
├── personas/{persona}/manifest.yaml
├── personas/{persona}/voice.md
├── personas/{persona}/skill-overlays/{skill}.md
├── personas/_shared/skill-loading.md
└── docs/PERSONA_LOADING.md

ESI Integration
├── .claude/scripts/aria_esi/__main__.py
├── .claude/scripts/aria_esi/commands/navigation.py
├── .claude/scripts/aria_esi/commands/persona.py
├── .claude/scripts/aria_esi/core/auth.py
└── .claude/scripts/aria_esi/mcp/tools_*.py

Documentation
├── docs/DATA_FILES.md
├── docs/MULTI_PILOT_ARCHITECTURE.md
└── docs/adr/*.md

Testing
├── pyproject.toml
└── tests/
```

---

## Appendix B: Review Scope Exclusions

The following areas were not evaluated in this review:

- Security posture of OAuth token handling
- ESI API rate limiting compliance
- Performance benchmarks under load
- Accessibility of CLI output
- Cross-platform compatibility (focused on macOS/Darwin)
- Specific EVE Online game mechanic accuracy

---

## Document History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 2026-01-18 | 1.0 | Claude Opus 4.5 | Initial review |
| 2026-01-18 | 2.0 | Claude Opus 4.5 | Remediation status update, 4 new findings |
