# Documentation Quality Roadmap

**Date:** 2026-02-15 (updated)
**Reviewer:** AI-assisted audit (Claude Opus 4.6)
**Scope:** Full documentation audit — user-facing, developer-facing, and AI-runtime docs
**Context:** Pre-public-announcement readiness review
**Revision:** 4 — Updated with Phase 4 (quality gates) and final polish completions

---

## Executive Summary

ARIA has extensive documentation (~250 markdown files, ~33,000+ lines), but it suffers from a fundamental structural problem: **user-facing and developer-facing documentation are co-mingled in `docs/`**, and a third category — **AI runtime instructions** — lives alongside both without clear labeling. Before public announcement, the highest-impact work is splitting `docs/` by audience so that new users see a clean, focused documentation surface rather than a mixed bag of setup guides and MCP context policy internals.

All four phases are **complete**. Phase 1 (PR #34), Phase 2 (audience split), Phase 3 (contributor enablement), and Phase 4 (quality gates + final polish) addressed all critical, high-priority, and nice-to-have items. The documentation is release-ready.

---

## 1. The Audience Problem

### Current State: Everything in `docs/`

`docs/` currently contains 28 files serving three distinct audiences:

| Audience | Description | Files Currently in `docs/` |
|----------|-------------|---------------------------|
| **Users** | People installing and using ARIA to play EVE | TLDR, FIRST_RUN, FAQ, ESI, DEPLOYMENT, MULTI_PILOT, NOTIFICATION_PROFILES, ADHOC_MARKETS, REALTIME_CONFIGURATION, ARCHITECTURE, COMMANDS, TROUBLESHOOTING, ROUTE_SCENARIOS, CONTEXT_AWARE_TOPOLOGY |
| **Developers** | People modifying ARIA's code or contributing | TESTING, TYPING_ROADMAP, PYTHON_ENVIRONMENT, CONTEXT_POLICY, SESSION_CONTEXT |
| **AI Runtime** | Instructions ARIA follows during sessions (read by the LLM, not humans) | DATA_VERIFICATION, DATA_AUTHORITY, PROTOCOLS, EXPERIENCE_ADAPTATION, COMMAND_SUGGESTIONS, DATA_FILES, DATA_SOURCES |

A new user browsing `docs/` encounters `CONTEXT_POLICY.md` (MCP singleton management, budget tracking internals) alongside `FIRST_RUN.md`. A developer looking for test guidance has to scan past `NOTIFICATION_PROFILES.md` (766 lines of YAML recipes). Neither audience is well-served.

### What Good Open-Source Projects Do

Projects with respected documentation (Astro, FastAPI, Tailwind, Homebrew, Next.js) share common patterns:

1. **`docs/` is user-facing.** It contains guides, tutorials, and reference material for end users. Period.
2. **Developer docs live separately.** Either in `dev/`, `internal/`, `contributing/`, or behind a "Development" section clearly walled off.
3. **Progressive disclosure.** README links to a quick start. Quick start links to detailed guides. Detailed guides link to reference. Users never land on internal architecture docs accidentally.
4. **One question, one page.** Docs are organized by the question they answer, not by the subsystem they describe.

### Proposed Structure

```
docs/                           # User-facing only
├── README.md                   # Docs index (user navigation)
├── TLDR.md                     # 1-page quick reference
├── FIRST_RUN.md                # Setup guide
├── FAQ.md                      # Common questions
├── ESI.md                      # ESI integration
├── DEPLOYMENT.md               # Installation
├── COMMANDS.md                 # Slash command reference ✅ DONE
├── TROUBLESHOOTING.md          # Consolidated troubleshooting ✅ DONE
├── MULTI_PILOT_ARCHITECTURE.md # Multi-character
├── NOTIFICATION_PROFILES.md    # Discord notifications (trimmed)
├── ADHOC_MARKETS.md            # Market scopes
├── REALTIME_CONFIGURATION.md   # Real-time intel
├── ARCHITECTURE.md             # System overview (stays; useful for users understanding what ARIA is)
├── PERSONA_LOADING.md          # Persona system (user-facing portions)
├── ROUTE_SCENARIOS.md          # Route examples
└── CONTEXT_AWARE_TOPOLOGY.md   # Topology config

dev/docs/                       # Developer-facing (NEW location)
├── README.md                   # Developer docs index
├── TESTING.md                  # ← moved from docs/
├── TYPING_ROADMAP.md           # ← moved from docs/
├── PYTHON_ENVIRONMENT.md       # ← moved from docs/ (with user-facing snippet left in docs/DEPLOYMENT.md)
├── CONTEXT_POLICY.md           # ← moved from docs/
├── SESSION_CONTEXT.md          # ← moved from docs/
├── DATA_SOURCES.md             # ← moved from docs/
├── CONTRIBUTING_PERSONAS.md    # Persona creation guide (NEW)
└── CONTRIBUTING_SKILLS.md      # Skill creation guide (NEW)

dev/docs/ai-runtime/            # AI runtime instructions (NEW location)
├── README.md                   # What these files are and why they exist
├── DATA_VERIFICATION.md        # ← moved from docs/
├── DATA_AUTHORITY.md           # ← moved from docs/
├── PROTOCOLS.md                # ← moved from docs/
├── EXPERIENCE_ADAPTATION.md    # ← moved from docs/
├── COMMAND_SUGGESTIONS.md      # ← moved from docs/
└── DATA_FILES.md               # ← moved from docs/
```

### Why This Matters for Public Announcement

A GitHub visitor evaluating ARIA will:

1. Read README.md (currently good)
2. Click into `docs/` (currently confusing)
3. Judge the project by what they see

If `docs/` contains 28 files including MCP context budget tracking and singleton reset patterns, the project looks like an internal engineering document dump. If `docs/` contains 16 focused user guides, it looks like a polished product.

---

## 2. File-by-File Audience Classification

### Files That Should Stay in `docs/` (User-Facing)

| File | Lines | Quality | Notes |
|------|------:|---------|-------|
| README.md | 115 | High | Good navigation hub. Needs update after restructure. |
| TLDR.md | 86 | High | Excellent quick reference. Model for signal-to-noise. |
| FIRST_RUN.md | 270 | High | Comprehensive setup guide. Examples have full descriptions. |
| FAQ.md | 117 | High | Clear, practical. Could grow with community questions. |
| ESI.md | 424 | Medium | Good content but long. Could split auth setup from scope reference. |
| DEPLOYMENT.md | 172 | High | Clean installation guide. Includes MCP server setup. |
| COMMANDS.md | 104 | High | 48 commands across 7 categories. Includes natural language examples. |
| TROUBLESHOOTING.md | 219 | High | 8 sections covering setup, ESI, data, notifications. Clean escalation path. |
| MULTI_PILOT_ARCHITECTURE.md | 145 | High | Clear user feature doc. |
| NOTIFICATION_PROFILES.md | 766 | Medium | Good content, overwhelming length. Needs Quick Start + Cookbook split. |
| ADHOC_MARKETS.md | 234 | High | Well-structured feature doc with examples. |
| REALTIME_CONFIGURATION.md | 390 | Medium | Somewhat long but necessary complexity for the feature. |
| ARCHITECTURE.md | 166 | Medium | System diagram useful. Missing MCP dispatcher examples. |
| PERSONA_LOADING.md | 424 | Medium | Mix of user config and developer internals. Naturally organized but could benefit from splitting. |
| ROUTE_SCENARIOS.md | 80 | Low | Scenario guide. Well-written but describes some features ARIA can't do (jump bridges, cynos, Thera). |
| CONTEXT_AWARE_TOPOLOGY.md | 139 | Medium | User config reference. Needs worked example. |

### Files That Should Move to `dev/docs/` (Developer-Facing)

| File | Lines | Audience | Why It's Not User-Facing |
|------|------:|----------|--------------------------|
| TESTING.md | 295 | Developer | Test tiers, pytest markers, coverage targets, fixtures |
| TYPING_ROADMAP.md | 152 | Developer | mypy phases, per-module overrides, disabled error codes |
| PYTHON_ENVIRONMENT.md | 176 | Developer/User hybrid | `uv run` instructions are user-relevant but keyring backends, dependency management, and venv details are developer-only. Extract user-relevant bits into DEPLOYMENT.md. |
| CONTEXT_POLICY.md | 283 | Developer | MCP output limits, singleton management, budget tracking, error response format. Pure internal architecture. |
| SESSION_CONTEXT.md | 60 | Developer | Session init boot hook internals. |
| DATA_SOURCES.md | 210 | Developer | External data source registry, blessed URLs, caching policy. |

### Files That Should Move to `dev/docs/ai-runtime/` (AI Instructions)

These files are referenced by CLAUDE.md and read by the LLM at runtime, not by humans during setup:

| File | Lines | Purpose |
|------|------:|---------|
| DATA_VERIFICATION.md | 414 | Runtime rules for verifying game data claims before presenting |
| DATA_AUTHORITY.md | 230 | Rules for what data sources can be cached |
| PROTOCOLS.md | 125 | Data volatility tiers, freshness rules, query triggers |
| EXPERIENCE_ADAPTATION.md | 108 | How to calibrate explanation depth by player experience |
| COMMAND_SUGGESTIONS.md | 128 | Progressive disclosure rules for suggesting slash commands |
| DATA_FILES.md | 130 | File path reference for pilot data (used by CLAUDE.md lookups) |

**Important:** Moving these files requires updating CLAUDE.md references. Each `docs/X.md` reference becomes `dev/docs/ai-runtime/X.md`. This is a mechanical find-and-replace but must be done carefully.

---

## 3. Signal-to-Noise Assessment

### Low-Value Files

| File | Lines | Problem | Recommendation |
|------|------:|---------|----------------|
| `docs/ROUTE_SCENARIOS.md` | 80 | Describes some scenarios ARIA can't handle (jump bridges, cyno chains, Thera). Potentially misleading for new users who may expect these features. | **Add disclaimer** at top noting which scenarios are aspirational vs currently supported, or move to `reference/lore/`. |
| `docs/CONTEXT_POLICY.md` §10 | ~38 | Context Budget Tracking section marked `[Not Yet Implemented]`. | Will move with the file to `dev/docs/`. Mark more clearly or remove the unimplemented section. |

### High Signal-to-Noise (Keep As-Is)

| File | Lines | Why It's Good |
|------|------:|---------------|
| `docs/TLDR.md` | 86 | Perfect quick reference. Every line earns its place. |
| `docs/FAQ.md` | 117 | Practical questions, concise answers. |
| `docs/ADHOC_MARKETS.md` | 234 | Clean structure: overview → quick start → reference → patterns → troubleshooting. |
| `docs/COMMANDS.md` | 104 | Compact, categorized, includes natural language triggers. |
| `docs/TROUBLESHOOTING.md` | 219 | 8 sections, clear escalation path, well-organized by problem domain. |
| `SECURITY.md` | 133 | Appropriately detailed for the sensitivity level. |
| `README.md` | 355 | Strong first impression. Real examples. Clear quick start. |
| `CHANGELOG.md` | ~280 | Fully compliant with Keep a Changelog v1.1.0. Detailed entries with context. |

### Verbose But Justified

| File | Lines | Assessment |
|------|------:|------------|
| `docs/DATA_VERIFICATION.md` | 414 | Case studies are long but educational. Each documents a real error and its fix. Keeps ARIA honest. **Keep.** |
| `docs/NOTIFICATION_PROFILES.md` | 766 | Comprehensive but overwhelming. **Split** into Quick Start (setup + 2 examples, ~150 lines) and Cookbook (advanced recipes + commentary config, ~600 lines). |
| `docs/ESI.md` | 424 | Long but covers OAuth flow end-to-end. Could extract scope reference table to an appendix. **Low priority.** |
| `docs/PERSONA_LOADING.md` | 424 | Mixes user config ("how to enable RP") with developer internals ("persona context compilation pipeline"). Well-organized internally but could benefit from a split for audience clarity. |

### Concrete Noise Reduction Edits

1. **`docs/ROUTE_SCENARIOS.md`** — Add disclaimer or move to `reference/lore/route_scenarios.md`.
2. **`docs/CONTEXT_POLICY.md` §10 (Budget Tracking `[Not Yet Implemented]`)** — Mark clearly or remove the unimplemented section. Will move with file to `dev/docs/`.
3. **`docs/ARCHITECTURE.md`** — Add MCP dispatcher usage examples and CLI fallback mention.

---

## 4. User-Facing Documentation Gaps

### Critical (Blocks New User Success)

| Gap | Impact | Status | Remedy |
|-----|--------|--------|--------|
| ~~**No slash command reference**~~ | ~~Users must use `/help` or read 51 SKILL.md files~~ | **✅ DONE** | `docs/COMMANDS.md` — 48 commands across 7 categories *(PR #34)* |
| ~~**No consolidated troubleshooting**~~ | ~~Troubleshooting scattered across 5 files~~ | **✅ DONE** | `docs/TROUBLESHOOTING.md` — 219 lines, 8 sections *(PR #34)* |
| ~~**`FIRST_RUN.md` examples incomplete**~~ | ~~Examples lacked descriptions~~ | **✅ DONE** | 4 examples with 2-3 sentence descriptions each *(PR #34)* |
| **No link to CONTRIBUTING.md from README** | Contributors browsing the repo can't discover contribution guidelines from the main README | **NEW** | Add "Contributing" section or link in root README.md |

### High (Affects User Experience)

| Gap | Impact | Status | Remedy |
|-----|--------|--------|--------|
| **No "What Can ARIA Do?" showcase** | README has 3 examples. Users wanting a feature gallery before installing have nothing. | Open | Add `docs/FEATURES.md` or expand README's "What ARIA Does" with collapsed examples. |
| **NOTIFICATION_PROFILES.md overwhelming** | 766 lines. User wanting basic Discord alerts must wade through advanced recipes. | Open | Split into Quick Start (~200 lines) and Cookbook (~550 lines). |
| **No persona quick-switch guide** | Users wanting to try different personas must hunt through FIRST_RUN.md. | Open | Add "Switching Personas" to FAQ or make FIRST_RUN.md section more discoverable. |
| **CONTEXT_AWARE_TOPOLOGY.md lacks worked example** | Users can't verify they understand the scoring formula. | Open | Add concrete calculation example. |

### Medium (Polish for Public Release)

| Gap | Impact | Status | Remedy |
|-----|--------|--------|--------|
| ~~**No Windows/WSL2 specific guide**~~ | ~~README notes WSL2 support but no guidance~~ | **✅ Sufficient** | WSL2 mentioned in README.md (platform support), FAQ.md (cron setup), and DEPLOYMENT.md (implicit via uv instructions). Adequate for current audience. |
| **No upgrade/migration guide** | DEPLOYMENT.md has `git pull && uv sync` but no breaking-change guidance. | Open | Add "Upgrading" section to DEPLOYMENT.md with version-specific notes pattern. |
| **No "How ARIA Uses Your Data" privacy page** | FAQ covers "Is my data sent anywhere?" but a dedicated privacy page aids trust. | Open | Consider `docs/PRIVACY.md` or expand Security section. |
| **CONTRIBUTING.md missing testing requirements** | PR checklist doesn't mention running pytest before submitting | **NEW** | Add testing step to pull request workflow section. |

---

## 5. Developer-Facing Documentation Gaps

### Critical (Blocks Contributor Success)

| Gap | Impact | Status | Remedy |
|-----|--------|--------|--------|
| **No skill creation guide** | 51 skills exist with no how-to documentation. | Open | Create `dev/docs/CONTRIBUTING_SKILLS.md` with step-by-step walkthrough. |
| **No persona creation guide** | Adding a persona requires reading 4+ files. | Open | Create `dev/docs/CONTRIBUTING_PERSONAS.md` with checklist. |
| **No `.claude/skills/` index** | 51 skill directories with no navigation. `.claude/skills/SCHEMA.md` exists (frontmatter format reference) but no categorized listing. | Open | Create `.claude/skills/README.md` with categorized skill listing. |

### High (Friction for Contributors)

| Gap | Impact | Status | Remedy |
|-----|--------|--------|--------|
| **No MCP dispatcher development guide** | Adding new MCP actions requires understanding context policy, output wrapping, error handling, testing patterns. | Open | Create `dev/docs/MCP_DEVELOPMENT.md`. |
| **ADR index minimal** | 5 ADRs exist in `dev/decisions/` with a template README. No decision log table. | Open | Expand `dev/decisions/README.md` with decision log. |
| **No dev environment quick start** | Clone → first-test-run path isn't documented. | Open | Add `dev/docs/GETTING_STARTED.md`. |
| **`dev/README.md` lacks navigation aid** | Lists directories but doesn't help find specific information. | Open | Add "Finding Things" section to `dev/README.md`. |

### Medium (Quality of Life)

| Gap | Impact | Status | Remedy |
|-----|--------|--------|--------|
| **No code architecture guide** | `docs/ARCHITECTURE.md` covers high-level diagram but not code organization. | Open | Add `dev/docs/CODE_ARCHITECTURE.md` or expand ARCHITECTURE.md. |
| **Test fixture documentation** | TESTING.md mentions fixtures but no inventory or usage patterns. | Open | Expand TESTING.md fixtures section. |
| **No release process detail** | `dev/RELEASE.md` is 56 lines — a task checklist, not comprehensive process docs. No versioning policy, changelog workflow, or announcement process. | Open | Expand `dev/RELEASE.md` for public project. |

---

## 6. AI-Facing Documentation Gaps

### Issues Specific to LLM Runtime Instructions

| Gap | Impact | Status | Remedy |
|-----|--------|--------|--------|
| **CLAUDE.md references all resolve correctly** | All 18 doc references, 6 JSON references, all script references verified. | **✅ No action needed** | Fully compliant — no broken references. |
| **No deprecated `lite` references in CLAUDE.md** | Only `off`, `on`, `full` used. | **✅ Clean** | No action needed. |
| **CONTEXT_POLICY.md budget tracking unimplemented** | Section documents code that isn't called in production. Could confuse LLM about available capabilities. | Open | Mark more prominently as unimplemented or remove section. |
| ~~**docs/ESI.md line 21 may reference non-existent file**~~ | ~~References `reference/mechanics/esi_capabilities.md`~~ | **✅ Verified** | File exists. No action needed. |

---

## 7. Documentation Debt: Broken Links, Stale Content, Inconsistencies

### Broken References

| Source | Reference | Status | Fix |
|--------|-----------|--------|-----|
| ~~`personas/README.md` L171~~ | ~~`.claude/hooks/aria-boot.d/persona-detect.sh`~~ | **✅ FIXED** | Updated to `uv run aria-esi persona-context` *(PR #34)* |
| ~~`reference/INDEX.md` L42-89~~ | ~~`missions/*.md`, `ships/fittings/*.md`~~ | **✅ FIXED** | Broken entries removed *(PR #34)* |
| ~~`docs/ESI.md` L21~~ | ~~`reference/mechanics/esi_capabilities.md`~~ | **✅ Verified** | File exists |
| ~~`docs/DATA_AUTHORITY.md` L96~~ | ~~`sov-load-coalitions` command~~ | **Deferred** | Low priority — developer-facing file |

### Stale Terminology

| Term | Location | Status | Fix |
|------|----------|--------|-----|
| ~~`lite` RP level~~ | ~~`personas/*/voice.md`, `rp-levels.md`, skills~~ | **✅ FIXED** | Removed from 13 skills, rp-levels.md, test fixtures, first-run-setup *(PR #34 + polish)* |
| `lite` migration note | `personas/_shared/rp-levels.md` L56 | **✅ Acceptable** | Collapsed to single-line migration note. Appropriate historical context. |
| ~~`ship_status.md`~~ | ~~`CONTRIBUTING.md` L44~~ | **Needs verification** | Check if example filenames align with actual filenames |

### Schema Inconsistencies

| Document | Issue | Status |
|----------|-------|--------|
| ~~NOTIFICATION_PROFILES.md~~ | ~~Schema version v1 in prose, v2 in examples~~ | **✅ FIXED** — All docs, templates, examples updated to v3 *(polish commit)* |

---

## 8. Big Wins: Highest Impact for Least Effort

Ordered by impact-to-effort ratio. Completed items struck through.

### ~~1. Create `docs/COMMANDS.md`~~ ✅ DONE

~~A single-page command reference is the #1 missing doc.~~ 48 commands across 7 categories with natural language examples. *(PR #34)*

### ~~2. Create `docs/TROUBLESHOOTING.md`~~ ✅ DONE

~~Consolidate the ~15 troubleshooting items.~~ 219 lines, 8 sections, clear escalation path. *(PR #34)*

### ~~3. Split `docs/` by Audience~~ ✅ DONE

~~Moving ~12 files from `docs/` to `dev/docs/` and `dev/docs/ai-runtime/`.~~ 12 files moved, all references updated, README indexes created. *(Phase 2)*

### ~~4. Add CONTRIBUTING.md link to README~~ ✅ DONE

~~Root README.md has no link to CONTRIBUTING.md.~~ Contributing section + Quick Docs bar link added. *(Phase 3)*

### ~~5. Fix All Broken Links~~ ✅ DONE

~~~4 broken references.~~ Fixed in PR #34. One new potential issue in ESI.md L21 (low priority).

### ~~6. Split `NOTIFICATION_PROFILES.md`~~ ✅ DONE

~~Move everything after "CLI Reference" into a separate `NOTIFICATION_COOKBOOK.md`.~~ Split into setup doc (~390 lines) and cookbook (~280 lines). *(Phase 2)*

### ~~7. Purge Stale `lite` RP References~~ ✅ DONE

~~Grep-and-fix across ~5 files.~~ Cleaned from 13 skills, rp-levels.md, test fixtures, first-run-setup.

---

## 9. Pre-Announcement Checklist

Issues that should be resolved before publicly announcing the project:

### Must Fix

- [x] **Create `docs/COMMANDS.md`** — 48-command reference across 7 categories *(PR #34)*
- [x] **Fix all broken links** — personas/README.md, reference/INDEX.md *(PR #34)*
- [x] **Remove stale `lite` RP references** — 13 skills, rp-levels.md, test fixtures, first-run-setup *(PR #34 + polish)*
- [x] **Fix `personas/README.md` hook reference** — updated to `uv run aria-esi persona-context` *(PR #34)*
- [x] **Reconcile notification schema version** — all docs, templates, examples updated to v3 *(polish commit)*
- [x] **Expand FIRST_RUN examples** — 2-3 sentence descriptions per example *(PR #34)*
- [x] **Verify LICENSE file exists and is correct** — confirmed MIT license present
- [x] **Verify `.env.example` exists** — confirmed present
- [x] **Add `docs/TROUBLESHOOTING.md`** — consolidated from 8 source files *(PR #34)*
- [x] **Add CONTRIBUTING.md link to root README** — Contributing section + Quick Docs bar link *(Phase 3)*

### Should Fix

- [x] **Split `docs/` by audience** — 12 files moved to `dev/docs/` and `dev/docs/ai-runtime/` *(Phase 2)*
- [x] **Split `NOTIFICATION_PROFILES.md`** — Quick Start + Cookbook *(Phase 2)*
- [x] **Split `PERSONA_LOADING.md`** — user config vs developer internals *(Phase 2)*
- [x] **Add WSL2 guidance** — present in README.md (platform support), FAQ.md (cron in WSL2), and implicitly in DEPLOYMENT.md *(verified 2026-02-15)*
- [x] **Create `dev/docs/CONTRIBUTING_SKILLS.md`** — step-by-step skill creation guide *(Phase 3)*
- [x] **Create `dev/docs/CONTRIBUTING_PERSONAS.md`** — step-by-step persona creation guide *(Phase 3)*
- [x] **Expand `dev/RELEASE.md`** — release process for public project *(Phase 4)*
- [x] **Add `ROUTE_SCENARIOS.md` disclaimer** — clarifies which scenarios ARIA supports *(Phase 3)*
- [x] **Archive `dev/DESIGN.md`** — moved to `dev/archive/DESIGN.md` *(polish commit 0644453)*
- [x] **Add testing requirements to CONTRIBUTING.md** — pytest command + link to TESTING.md *(Phase 3)*
- [x] **Verify `docs/ESI.md` L21 reference** — `reference/mechanics/esi_capabilities.md` confirmed to exist *(Phase 3)*

### Nice to Have

- [x] **Add CI link checker** — lychee in GitHub Actions *(Phase 4)*
- [x] **Create `docs/FEATURES.md`** — expanded showcase for GitHub visitors *(Phase 4)*
- [x] **Add `dev/docs/MCP_DEVELOPMENT.md`** — dispatcher development guide *(Phase 3)*
- [x] **Expand `dev/decisions/README.md`** — ADR index with summaries *(Phase 3)*
- [x] **Add `dev/docs/GETTING_STARTED.md`** — developer quick start *(Phase 3)*
- [x] **Create `.claude/skills/README.md`** — categorized skill directory index *(Phase 3)*
- [x] **Add terminology tables to empire personas** — parity with PARIA's voice definition *(Phase 4)*
- [x] **Expand `docs/ARCHITECTURE.md`** — MCP dispatcher examples + CLI fallback *(Phase 3)*
- [x] **Add more README badges** — coverage, Python version, license *(Phase 4)*
- [x] **Add "Finding Things" section to `dev/README.md`** — help developers navigate 80+ dev files *(Phase 4)*

---

## 10. CLAUDE.md Assessment

`CLAUDE.md` is 574 lines and serves as the system prompt for ARIA sessions. It is not user-facing documentation in the traditional sense — it's machine-readable instructions.

### Current State (Verified 2026-02-15)

- **All 18 documentation references** resolve to existing files ✅
- **All 6 reference JSON files** exist ✅
- **All persona/shared files** exist ✅
- **All script references** exist and are accessible ✅
- **No deprecated terminology** (`lite`, `moderate`) in CLAUDE.md ✅
- **No stale file paths** detected ✅

### Ongoing Concerns

1. **Duplicates content from `docs/`** — MCP tool reference tables, agent query docs, data verification principles all exist in both CLAUDE.md and separate docs.
2. **Maintenance burden** — changes to MCP dispatchers require updating both CLAUDE.md and the relevant docs file.
3. **Cannot be split easily** — Claude Code reads CLAUDE.md as a single file. It can't `#include` other files.

### Recommendation

**Accept CLAUDE.md as a necessary monolith.** It serves a fundamentally different purpose than human docs. The duplication with `docs/` files is the real problem — not CLAUDE.md's length. Once developer/AI-runtime docs are moved to `dev/docs/`, the duplication is reduced because the canonical version lives in one place with CLAUDE.md referencing it by path.

**Do not** attempt to "simplify" CLAUDE.md for readability. It's not read by humans during normal use. Its verbosity is intentional — the LLM needs explicit, unambiguous instructions.

---

## 11. `dev/` Directory Health

### Current State

`dev/` is well-organized with clear subdirectories:

```
dev/
├── archive/          # 19 historical docs (properly archived, includes DESIGN.md)
├── decisions/        # 5 ADRs (ADR-001 through ADR-005, all accepted)
├── mechanics/        # 3 game mechanics research docs
├── plans/            # 1 implementation plan
├── proposals/        # 1 active + 25 archived proposals
├── reviews/          # Active reviews + 12 archived
├── spikes/           # 1 technical spike
├── stp/              # 1 active + 11 completed skill tracking plans
├── RELEASE.md        # Release checklist (needs expansion)
└── README.md         # Directory guide (adequate)
```

### Changes Since Last Review

1. **`dev/DESIGN.md` archived** ✅ — Moved to `dev/archive/DESIGN.md` in polish commit 0644453.
2. **Archive discipline remains strong** — Proposals archived when implemented, reviews archived when superseded.
3. **`dev/docs/` does not exist yet** — The audience split (Phase 2) hasn't been executed.

### Remaining Issues

1. **`dev/README.md` is adequate but not great.** It lists directories but doesn't help a developer find specific information. Add a "Finding Things" section.
2. **No developer getting-started guide.** A contributor clone → first-test-run path isn't documented.
3. **STP directory well-maintained.** 11 completed, 1 active. Good process evidence.

---

## 12. Implementation Phases

### Phase 1: Pre-Announcement Critical Path ✅ COMPLETE

All 9 items completed in PR #34 and subsequent polish commit.

| # | Action | Status |
|---|--------|--------|
| 1 | Create `docs/COMMANDS.md` from skill index | ✅ Done |
| 2 | Create `docs/TROUBLESHOOTING.md` consolidation | ✅ Done |
| 3 | Fix all broken links (4 instances) | ✅ Done |
| 4 | Remove stale `lite` RP references | ✅ Done |
| 5 | Fix personas/README.md hook reference | ✅ Done |
| 6 | Reconcile notification schema v1→v3 | ✅ Done |
| 7 | Expand FIRST_RUN.md examples with descriptions | ✅ Done |
| 8 | Archive dev/DESIGN.md | ✅ Done |
| 9 | Add CONTRIBUTING.md link to root README | ✅ Done |

### Phase 2: Audience Split ✅ COMPLETE

| # | Action | Status |
|---|--------|--------|
| 10 | Create `dev/docs/` and `dev/docs/ai-runtime/` directories | ✅ Done |
| 11 | Move 6 developer docs from `docs/` to `dev/docs/` | ✅ Done |
| 12 | Move 6 AI-runtime docs from `docs/` to `dev/docs/ai-runtime/` | ✅ Done |
| 13 | Update all CLAUDE.md references to new paths | ✅ Done |
| 14 | Update `docs/README.md` index (remove moved files, add new ones) | ✅ Done |
| 15 | Create `dev/docs/README.md` developer index | ✅ Done |
| 16 | Create `dev/docs/ai-runtime/README.md` explaining these files | ✅ Done |
| 17 | Extract user-relevant parts of PYTHON_ENVIRONMENT.md into DEPLOYMENT.md | ✅ Done |
| 18 | Split NOTIFICATION_PROFILES.md → Quick Start + Cookbook | ✅ Done |
| 19 | Split PERSONA_LOADING.md → user config + dev internals | ✅ Done |

### Phase 3: Contributor Enablement ✅ COMPLETE

| # | Action | Status |
|---|--------|--------|
| 20 | Create `dev/docs/CONTRIBUTING_SKILLS.md` | ✅ Done |
| 21 | Create `dev/docs/CONTRIBUTING_PERSONAS.md` | ✅ Done |
| 22 | Create `.claude/skills/README.md` skill index | ✅ Done |
| 23 | Create `dev/docs/MCP_DEVELOPMENT.md` | ✅ Done |
| 24 | Create `dev/docs/GETTING_STARTED.md` (dev quick start) | ✅ Done |
| 25 | Expand `dev/decisions/README.md` with ADR summaries | ✅ Done |
| 26 | Add worked example to CONTEXT_AWARE_TOPOLOGY.md | ✅ Done |
| 27 | Add testing requirements to CONTRIBUTING.md | ✅ Done |

### Phase 4: Quality Gates ✅ COMPLETE

| # | Action | Status |
|---|--------|--------|
| 28 | Add lychee link checker to CI | ✅ Done |
| 29 | Add PR template COMMANDS.md reminder | ✅ Done |
| 30 | Terminology lint in pre-commit | ✅ Done |
| 31 | Quarterly doc freshness audit cadence | ✅ Done |
| 32 | Auto-generate COMMANDS.md from skill index | ✅ Done |

---

## 13. Success Criteria

Documentation is "release-ready" when:

1. **A new user can go from `git clone` to first ARIA response in under 10 minutes** following only docs/ files
2. **A GitHub visitor can understand what ARIA does in under 2 minutes** from README + docs/COMMANDS.md
3. **`docs/` contains zero developer-only files** — all developer docs are in `dev/docs/`
4. **Zero broken internal links** verified by CI
5. **Zero stale terminology** (no `lite` RP level, no non-existent file references)
6. **A contributor can create a new skill** following `dev/docs/CONTRIBUTING_SKILLS.md` without external help
7. **Every slash command** is documented in `docs/COMMANDS.md`
8. **Troubleshooting has a single entry point** at `docs/TROUBLESHOOTING.md`

### Current Progress Against Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Clone-to-response in 10 min | ✅ Achievable with current docs |
| 2 | Understand ARIA in 2 min | ✅ README + COMMANDS.md cover this |
| 3 | `docs/` user-only | ✅ 12 developer/AI-runtime files moved to `dev/docs/` |
| 4 | Zero broken links | ✅ ESI.md L21 reference verified (file exists) |
| 5 | Zero stale terminology | ✅ `lite` references cleaned; migration note is appropriate |
| 6 | Skill creation guide | ✅ `dev/docs/CONTRIBUTING_SKILLS.md` created |
| 7 | All commands in COMMANDS.md | ✅ 48 commands documented |
| 8 | Single troubleshooting entry | ✅ `docs/TROUBLESHOOTING.md` exists |

---

## Appendix A: Comparison with Open-Source Documentation Standards

| Practice | ARIA Status | Target |
|----------|-------------|--------|
| README has clear quick start | ✅ Yes | Maintain |
| README shows real output examples | ✅ Yes (3 examples) | Expand to 5-6 |
| README links to CONTRIBUTING.md | ✅ Yes | Maintain |
| docs/ is user-focused | ✅ Yes (split in Phase 2) | Maintain |
| Progressive disclosure (quick start → guide → reference) | ✅ Yes (TLDR → FIRST_RUN → COMMANDS → detailed) | Maintain |
| Consolidated troubleshooting | ✅ Yes (TROUBLESHOOTING.md) | Maintain |
| Contributing guide for major extension points | ✅ Yes (skills, personas, MCP) | Maintain |
| Automated link checking in CI | ✅ Yes (lychee) | Maintain |
| Command/API reference page | ✅ Yes (COMMANDS.md) | Maintain |
| Architecture overview | ✅ Yes (ARCHITECTURE.md + MCP examples) | Maintain |
| Security policy | ✅ Yes (SECURITY.md) | Maintain |
| License clarity | ✅ Yes (README, CONTRIBUTING, LICENSE) | Maintain |
| Example configurations | ✅ Yes (4 examples with descriptions) | Maintain, grow organically |
| Changelog | ✅ Yes (Keep a Changelog v1.1.0 compliant) | Maintain as project matures |
| CI badges | ✅ Yes (CI, coverage, Python, license) | Maintain |

## Appendix B: File Move Mapping

Complete mapping for the audience split (Phase 2):

```
# Developer docs
docs/TESTING.md              → dev/docs/TESTING.md
docs/TYPING_ROADMAP.md       → dev/docs/TYPING_ROADMAP.md
docs/PYTHON_ENVIRONMENT.md   → dev/docs/PYTHON_ENVIRONMENT.md
docs/CONTEXT_POLICY.md       → dev/docs/CONTEXT_POLICY.md
docs/SESSION_CONTEXT.md      → dev/docs/SESSION_CONTEXT.md
docs/DATA_SOURCES.md         → dev/docs/DATA_SOURCES.md

# AI runtime docs
docs/DATA_VERIFICATION.md    → dev/docs/ai-runtime/DATA_VERIFICATION.md
docs/DATA_AUTHORITY.md        → dev/docs/ai-runtime/DATA_AUTHORITY.md
docs/PROTOCOLS.md             → dev/docs/ai-runtime/PROTOCOLS.md
docs/EXPERIENCE_ADAPTATION.md → dev/docs/ai-runtime/EXPERIENCE_ADAPTATION.md
docs/COMMAND_SUGGESTIONS.md   → dev/docs/ai-runtime/COMMAND_SUGGESTIONS.md
docs/DATA_FILES.md            → dev/docs/ai-runtime/DATA_FILES.md
```

**CLAUDE.md references to update (after moves):**

| Current Reference | New Reference |
|-------------------|---------------|
| `docs/DATA_VERIFICATION.md` | `dev/docs/ai-runtime/DATA_VERIFICATION.md` |
| `docs/DATA_AUTHORITY.md` | `dev/docs/ai-runtime/DATA_AUTHORITY.md` |
| `docs/PROTOCOLS.md` | `dev/docs/ai-runtime/PROTOCOLS.md` |
| `docs/EXPERIENCE_ADAPTATION.md` | `dev/docs/ai-runtime/EXPERIENCE_ADAPTATION.md` |
| `docs/COMMAND_SUGGESTIONS.md` | `dev/docs/ai-runtime/COMMAND_SUGGESTIONS.md` |
| `docs/DATA_FILES.md` | `dev/docs/ai-runtime/DATA_FILES.md` |
| `docs/CONTEXT_POLICY.md` | `dev/docs/CONTEXT_POLICY.md` |
| `docs/SESSION_CONTEXT.md` | `dev/docs/SESSION_CONTEXT.md` |
| `docs/TESTING.md` | `dev/docs/TESTING.md` |
| `docs/PYTHON_ENVIRONMENT.md` | `dev/docs/PYTHON_ENVIRONMENT.md` |
| `docs/DATA_SOURCES.md` | `dev/docs/DATA_SOURCES.md` |
| `docs/TYPING_ROADMAP.md` | `dev/docs/TYPING_ROADMAP.md` |

---

*Review generated 2026-02-15. Revision 4: All phases complete. Documentation release-ready. Supersedes revision 3.*
