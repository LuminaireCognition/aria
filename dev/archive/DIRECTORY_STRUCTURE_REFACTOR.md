# Directory Structure Refactor Proposal

**Status:** ✅ Implemented (All Phases Complete)
**Date:** 2026-01-18
**Updated:** 2026-01-18
**Author:** ARIA Analysis

## Executive Summary

The ARIA project has organically grown from a single bash script into a full Python package with MCP server integration, multi-pilot architecture, and extensive documentation. This growth has created organizational debt: source code lives in an unconventional location, documentation sprawls across the root directory, and the boundary between product files, development artifacts, and user data is unclear.

This proposal defines a directory structure that:
1. Follows the **Principle of Least Surprise** for both developers and end-users
2. Clearly separates **development**, **product**, and **user data** concerns
3. Respects **Claude Code conventions** while following **Python standards**
4. Supports a **healthy project development lifecycle** (STPs, ADRs, proposals)

---

## Current State Analysis

### Root Directory Inventory

```
/EveOnline/
├── .aria-config.json          # User config (gitignored)
├── .aria-credentials.json     # Credentials (gitignored)
├── .claude/                   # Claude Code + Source code (!)
│   ├── settings.json          # Claude settings
│   ├── skills/                # 32 slash commands
│   ├── hooks/                 # Pre-commit hooks
│   └── scripts/aria_esi/      # THE ENTIRE PYTHON PACKAGE
├── .mcp.json                  # MCP server config
├── pyproject.toml             # Build config
├── uv.lock                    # Dependency lock
│
├── CLAUDE.md                  # ARIA instructions (user-facing)
├── README.md                  # Project overview (user-facing)
├── TLDR.md                    # Quick start (user-facing)
├── FIRST_RUN.md               # Onboarding (user-facing)
├── DESIGN.md                  # Architecture (dev-facing)
├── SPLIT_PROPOSAL.md          # Historical proposal (dev-facing)
├── PROJECT_REVIEW_001.md      # Code review (dev-facing)
├── TODO.md                    # Task tracking (dev-facing)
├── TODO_SECURITY.md           # Security tasks (dev-facing)
├── CONTRIBUTING.md            # Contributor guide (dev-facing)
├── ATTRIBUTION.md             # Credits (dev-facing)
├── LICENSE                    # MIT license
│
├── data/                      # Reference data (committed)
├── docs/                      # Documentation (mixed purposes)
│   ├── adr/                   # Architecture decisions
│   ├── stp/                   # Skill tracking plans
│   │   ├── active/
│   │   ├── completed/
│   │   └── proposed/
│   ├── proposals/             # Feature proposals
│   └── *.md                   # Various docs
├── personas/                  # RP personas (committed)
├── templates/                 # User data templates
├── examples/                  # Example profiles
├── tests/                     # Test suite
│
├── pilots/                    # USER DATA (gitignored)
├── credentials/               # USER DATA (gitignored)
├── sessions/                  # USER DATA (gitignored)
└── .venv/, caches, etc.       # Generated (gitignored)
```

### Key Problems Identified

| Problem | Impact | Affected Users |
|---------|--------|----------------|
| Source code in `.claude/scripts/` | Non-standard, confuses tooling, IDE support issues | Developers |
| 11 markdown files at root | Unclear what's user-facing vs dev-facing | Everyone |
| User data scattered | `pilots/`, `credentials/`, `sessions/`, `.aria-config.json` all separate | End users |
| Mixed documentation in `docs/` | STPs, ADRs, proposals, user docs all intermingled | Developers |
| `data/` ambiguity | Contains committed reference data + gitignored paths | Everyone |
| Personas separate from skills | Tightly coupled systems physically separated | Developers |

---

## Identified Tensions

The following tensions must be balanced in any restructuring:

### 1. Claude Code Conventions vs Python Standards

| Requirement | Claude Code | Python Standard | Tension |
|-------------|-------------|-----------------|---------|
| Skills location | `.claude/skills/` | N/A | **Must keep** |
| Settings | `.claude/settings.json` | N/A | **Must keep** |
| Hooks | `.claude/hooks/` | N/A | **Must keep** |
| Source code | Any location | `src/` or root package | **Conflict** |
| Entry point | pyproject.toml | pyproject.toml | Compatible |

**Resolution:** Keep Claude Code requirements in `.claude/`, move source code to `src/`.

### 2. Developer Experience vs End-User Experience

| Concern | Developer Needs | End-User Needs |
|---------|-----------------|----------------|
| Documentation | ADRs, STPs, proposals, code architecture | Getting started, CLAUDE.md, reference |
| Data files | Test fixtures, development data | Personal pilot data, credentials |
| Visibility | See project internals, contribution guidelines | See their data, not project internals |

**Resolution:** Create `dev/` for development lifecycle artifacts, keep user-facing docs accessible.

### 3. Product Files vs User Data

| Category | Examples | Git Status |
|----------|----------|------------|
| Product | Skills, personas, reference data, source code | Committed |
| User Data | Pilot profiles, credentials, session logs | Gitignored |
| Development | STPs, proposals, code reviews, TODO lists | Committed (dev-only) |

**Resolution:** User data in clearly-named `userdata/` directory (gitignored), development artifacts in `dev/`.

### 4. Discoverability vs Convention

| Principle | Implication |
|-----------|-------------|
| Least Surprise | Users expect `src/` for source, `docs/` for documentation |
| Self-documenting | Directory names should explain their purpose |
| Convention over configuration | Follow established patterns when possible |

**Resolution:** Adopt standard Python project layout with clear naming.

---

## Proposed Directory Structure

```
/EveOnline/
│
├── ══════════════════════════════════════════════════════════════
├── USER-FACING (what end-users interact with)
├── ══════════════════════════════════════════════════════════════
│
├── README.md                      # Project overview, installation
├── CLAUDE.md                      # ARIA instructions for Claude Code
├── LICENSE                        # MIT license
│
├── userdata/                      # ALL USER DATA (gitignored)
│   ├── .gitkeep                   # Ensures directory exists
│   ├── README.md                  # Explains userdata structure (committed)
│   ├── config.json                # Active pilot selector (was .aria-config.json)
│   ├── credentials/               # OAuth tokens (was /credentials/)
│   │   └── {character_id}.json
│   ├── pilots/                    # Pilot profiles (was /pilots/)
│   │   ├── _registry.json
│   │   └── {character_id}_{name}/
│   │       ├── profile.md
│   │       ├── operations.md
│   │       ├── ships.md
│   │       ├── goals.md
│   │       ├── industry/
│   │       └── projects/
│   └── sessions/                  # Session logs (was /sessions/)
│       └── *.json, *.md
│
├── ══════════════════════════════════════════════════════════════
├── PRODUCT (the ARIA application)
├── ══════════════════════════════════════════════════════════════
│
├── src/                           # Python source code
│   └── aria_esi/                  # Main package (was .claude/scripts/aria_esi/)
│       ├── __init__.py
│       ├── __main__.py
│       ├── core/
│       ├── commands/
│       ├── mcp/
│       ├── universe/
│       └── data/                  # Generated data (universe.pkl, etc.)
│
├── .claude/                       # Claude Code integration ONLY
│   ├── settings.json              # Claude Code settings
│   ├── settings.local.json        # Local overrides (gitignored)
│   ├── skills/                    # Slash command definitions
│   │   ├── _index.json
│   │   └── {skill-name}/
│   │       └── SKILL.md
│   └── hooks/                     # Git hooks
│
├── personas/                      # Roleplay personas
│   ├── README.md
│   ├── _shared/
│   └── {persona-name}/
│       ├── manifest.yaml
│       ├── voice.md
│       └── skill-overlays/
│
├── reference/                     # Static reference data (was data/)
│   ├── INDEX.md
│   ├── lore/
│   ├── ships/
│   ├── industry/
│   ├── missions/
│   └── mechanics/                 # (was reference/)
│
├── templates/                     # User data templates
│   └── pilot/
│       ├── profile.template.md
│       └── operations.template.md
│
├── ══════════════════════════════════════════════════════════════
├── DEVELOPMENT (project development lifecycle)
├── ══════════════════════════════════════════════════════════════
│
├── dev/                           # Development lifecycle artifacts
│   ├── README.md                  # Development guide
│   │
│   ├── adr/                       # Architecture Decision Records
│   │   ├── README.md
│   │   ├── 001-multi-pilot-architecture.md
│   │   └── ...
│   │
│   ├── stp/                       # Skill Tracking Plans
│   │   ├── README.md
│   │   ├── active/
│   │   ├── completed/
│   │   └── proposed/
│   │
│   ├── proposals/                 # Feature proposals
│   │   ├── README.md
│   │   └── *.md
│   │
│   ├── reviews/                   # Code reviews, audits
│   │   └── PROJECT_REVIEW_001.md
│   │
│   └── planning/                  # TODO lists, roadmaps
│       ├── TODO.md
│       └── TODO_SECURITY.md
│
├── docs/                          # User-facing documentation
│   ├── getting-started.md         # (was FIRST_RUN.md + TLDR.md)
│   ├── esi-setup.md
│   ├── python-environment.md
│   ├── multi-pilot-guide.md
│   └── api/                       # API documentation (if needed)
│
├── tests/                         # Test suite
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── benchmarks/
│
├── examples/                      # Example configurations
│   └── pilots/
│       ├── caldari-mission-runner/
│       └── gallente-industrialist/
│
├── ══════════════════════════════════════════════════════════════
├── BUILD & CONFIG (standard locations)
├── ══════════════════════════════════════════════════════════════
│
├── pyproject.toml                 # Build configuration
├── uv.lock                        # Dependency lock
├── .pre-commit-config.yaml        # Pre-commit hooks
├── .python-version                # Python version
├── .gitignore                     # Git ignore rules
├── .gitattributes                 # Git attributes
├── .mcp.json                      # MCP server config
├── .github/                       # GitHub workflows
│   └── workflows/
│
├── CONTRIBUTING.md                # Contributor guide
├── ATTRIBUTION.md                 # Credits
│
└── ══════════════════════════════════════════════════════════════
    GENERATED (gitignored, auto-created)
    ══════════════════════════════════════════════════════════════
    .venv/                         # Virtual environment
    .pytest_cache/                 # Pytest cache
    .mypy_cache/                   # MyPy cache
    .ruff_cache/                   # Ruff cache
    .coverage                      # Coverage data
    .benchmarks/                   # Benchmark results
```

---

## Key Changes Summary

| Current Location | Proposed Location | Rationale |
|------------------|-------------------|-----------|
| `.claude/scripts/aria_esi/` | `src/aria_esi/` | Standard Python layout |
| `pilots/` | `userdata/pilots/` | Consolidated user data |
| `credentials/` | `userdata/credentials/` | Consolidated user data |
| `sessions/` | `userdata/sessions/` | Consolidated user data |
| `.aria-config.json` | `userdata/config.json` | Consolidated user data |
| `data/` | `reference/` | Clearer naming, no ambiguity |
| `docs/adr/` | `dev/adr/` | Development lifecycle |
| `docs/stp/` | `dev/stp/` | Development lifecycle |
| `docs/proposals/` | `dev/proposals/` | Development lifecycle |
| `PROJECT_REVIEW_001.md` | `dev/reviews/` | Development lifecycle |
| `TODO.md`, `TODO_SECURITY.md` | `dev/planning/` | Development lifecycle |
| `DESIGN.md` | `dev/README.md` or `dev/architecture.md` | Development documentation |
| `SPLIT_PROPOSAL.md` | `dev/proposals/` (archive) | Historical, move to proposals |
| `FIRST_RUN.md`, `TLDR.md` | `docs/getting-started.md` | Consolidated user docs |

---

## Principle of Least Surprise Analysis

### For a Non-Developer User Cloning from GitHub

**Current experience:**
1. Clones repo, sees 11 markdown files at root - overwhelmed
2. Looks for their data - finds `pilots/` (not obvious)
3. Credentials in `credentials/`, config in `.aria-config.json` - scattered
4. Unclear what's "theirs" vs "the project"

**Proposed experience:**
1. Clones repo, sees README.md and CLAUDE.md at root - clear entry points
2. Sees `userdata/` - obvious where their stuff goes
3. All personal data in one place with its own README explaining structure
4. Clear separation: "userdata is mine, everything else is the product"

### For a Developer Contributing to the Project

**Current experience:**
1. Source code in `.claude/scripts/` - unexpected, IDE confusion
2. STPs in `docs/stp/`, proposals in `docs/proposals/`, TODOs at root - scattered
3. No clear development workflow documentation
4. ADRs exist but hidden in docs

**Proposed experience:**
1. Source code in `src/` - standard Python, IDE works perfectly
2. All development artifacts in `dev/` with clear subdirectories
3. `dev/README.md` explains the development workflow
4. Clear lifecycle: `dev/stp/proposed/` → `dev/stp/active/` → `dev/stp/completed/`

---

## Migration Strategy

### Phase 1: Create New Structure (Non-Breaking)

1. Create `userdata/` with README explaining the new structure
2. Create `dev/` and move development artifacts
3. Create `src/` and copy (not move) source code
4. Update `pyproject.toml` to point to `src/`
5. Test that everything works from new locations

### Phase 2: Update References

1. Update CLAUDE.md to reference new paths
2. Update all documentation paths
3. Update import paths in source code
4. Update test configurations

### Phase 3: Migrate User Data

1. Create migration script that moves user data to `userdata/`
2. Update `.gitignore` for new locations
3. Update credential resolution to check both old and new paths
4. Document migration in release notes

### Phase 4: Remove Old Structure ✅

1. ✅ Remove old source location (`.claude/scripts/aria_esi/`) - N/A, was never a package here
2. ✅ Remove old user data locations (`pilots/`, `credentials/`, `sessions/`) - Removed from root
3. ✅ Remove root-level development files - Moved to `dev/`
4. ✅ Final cleanup pass - Boot hooks updated to use `userdata/` paths with legacy fallback

**Implementation Notes:**
- Boot hooks (`pilot-resolution.sh`, `boot-operations.sh`) now prefer `userdata/` paths
- Legacy fallback preserved for backward compatibility during transition
- Standalone scripts in `.claude/scripts/` retained for boot operations (oauth, sync, etc.)

---

## Open Questions

1. **Should `personas/` move under `.claude/`?**
   - Pro: Closer to skills they modify
   - Con: `.claude/` should be Claude Code config only
   - **Recommendation:** Keep at root, they're product content not Claude config

2. **Should `examples/` merge with `templates/`?**
   - Pro: Similar purpose, reduces directories
   - Con: Examples are complete, templates are scaffolding
   - **Recommendation:** Keep separate, rename examples to `examples/pilots/`

3. **Should `reference/` be under `src/`?**
   - Pro: It's data used by the application
   - Con: It's human-readable reference material
   - **Recommendation:** Keep at root, it's for both humans and code

4. **MCP server config location?**
   - Current: `.mcp.json` at root
   - Alternative: `userdata/.mcp.json` (user-specific)
   - **Recommendation:** Keep at root, it's project config not user data

---

## Appendix: .gitignore Updates

```gitignore
# ═══════════════════════════════════════════════════════════════════
# User Data (all personal data in one place)
# ═══════════════════════════════════════════════════════════════════
userdata/*
!userdata/.gitkeep
!userdata/README.md

# ═══════════════════════════════════════════════════════════════════
# Legacy locations (for migration period)
# ═══════════════════════════════════════════════════════════════════
pilots/
credentials/
sessions/
.aria-config.json
.aria-credentials.json
.aria-pkce-temp.json

# ═══════════════════════════════════════════════════════════════════
# Claude Code local settings
# ═══════════════════════════════════════════════════════════════════
.claude/settings.local.json

# ═══════════════════════════════════════════════════════════════════
# Generated data
# ═══════════════════════════════════════════════════════════════════
src/aria_esi/data/universe.pkl

# ═══════════════════════════════════════════════════════════════════
# Python / Development
# ═══════════════════════════════════════════════════════════════════
__pycache__/
*.pyc
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
.benchmarks/
```

---

## Appendix: pyproject.toml Updates

```toml
[project]
name = "aria-esi"
# ...

[project.scripts]
aria-esi = "aria_esi.__main__:main"
aria-universe = "aria_esi.mcp.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/aria_esi"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.mypy]
mypy_path = "src"
```

---

## Decision Required

This proposal requires stakeholder review. Key decisions:

1. **Approve overall structure?** The three-tier separation (user/product/development)
2. **Approve `userdata/` naming?** Alternative: `local/`, `user/`, `data-local/`
3. **Approve `dev/` naming?** Alternative: `development/`, `.dev/`, `contrib/`
4. **Approve `src/` migration?** This is a significant change to the source layout
5. **Migration timeline?** Phased or all-at-once?

---

*Proposal generated 2026-01-18 by ARIA directory analysis.*
