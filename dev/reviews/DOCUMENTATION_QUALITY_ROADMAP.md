# Documentation Quality Roadmap

**Date:** 2026-02-15
**Reviewer:** AI-assisted audit (Claude Opus 4.6)
**Scope:** Full documentation audit — user-facing, developer-facing, and AI-runtime docs
**Context:** Pre-public-announcement readiness review

---

## Executive Summary

ARIA has extensive documentation (~250 markdown files, ~33,000+ lines), but it suffers from a fundamental structural problem: **user-facing and developer-facing documentation are co-mingled in `docs/`**, and a third category — **AI runtime instructions** — lives alongside both without clear labeling. Before public announcement, the highest-impact work is splitting `docs/` by audience so that new users see a clean, focused documentation surface rather than a mixed bag of setup guides and MCP context policy internals.

The documentation is strong in coverage but weak in organization. Most content exists; it just needs to be in the right place, for the right reader.

---

## 1. The Audience Problem

### Current State: Everything in `docs/`

`docs/` currently contains 26 files serving three distinct audiences:

| Audience | Description | Files Currently in `docs/` |
|----------|-------------|---------------------------|
| **Users** | People installing and using ARIA to play EVE | TLDR, FIRST_RUN, FAQ, ESI, DEPLOYMENT, MULTI_PILOT, NOTIFICATION_PROFILES, ADHOC_MARKETS, REALTIME_CONFIGURATION, ARCHITECTURE |
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
├── COMMANDS.md                 # Slash command reference (NEW)
├── TROUBLESHOOTING.md          # Consolidated troubleshooting (NEW)
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

If `docs/` contains 26 files including MCP context budget tracking and singleton reset patterns, the project looks like an internal engineering document dump. If `docs/` contains 16 focused user guides, it looks like a polished product.

---

## 2. File-by-File Audience Classification

### Files That Should Stay in `docs/` (User-Facing)

| File | Lines | Quality | Notes |
|------|------:|---------|-------|
| README.md | 113 | High | Good navigation hub. Needs update after restructure. |
| TLDR.md | 86 | High | Excellent quick reference. Model for signal-to-noise. |
| FIRST_RUN.md | 266 | High | Comprehensive setup guide. Examples section needs expansion. |
| FAQ.md | 117 | High | Clear, practical. Could grow with community questions. |
| ESI.md | 424 | Medium | Good content but long. Could split auth setup from scope reference. |
| DEPLOYMENT.md | 172 | High | Clean installation guide. |
| MULTI_PILOT_ARCHITECTURE.md | 145 | High | Clear user feature doc. |
| NOTIFICATION_PROFILES.md | 766 | Medium | Good content, overwhelming length. Needs Quick Start + Cookbook split. |
| ADHOC_MARKETS.md | 234 | High | Well-structured feature doc with examples. |
| REALTIME_CONFIGURATION.md | 390 | Medium | Somewhat long but necessary complexity for the feature. |
| ARCHITECTURE.md | 166 | High | System diagram useful for users understanding what ARIA is. |
| PERSONA_LOADING.md | 424 | Medium | Mix of user config and developer internals. Needs splitting. |
| ROUTE_SCENARIOS.md | 80 | Low | Flavor text. Not actionable. See signal-to-noise section. |
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
| `docs/ROUTE_SCENARIOS.md` | 80 | EVE route planning flavor text. No ARIA-specific content. Describes scenarios ARIA can't handle (jump bridges, cyno chains, Thera). Not actionable for users. | **Delete** or move to `reference/lore/`. Serves no user or developer purpose in `docs/`. |
| `dev/DESIGN.md` (PROPOSAL.md) | 533 | Original project proposal from inception. Describes a single-faction RP concept that has been superseded. References directory structures that no longer exist. | **Move to `dev/archive/`**. Historical interest only. |
| `dev/archive/*.md` (17 files) | ~3000+ | Implemented proposals, superseded designs, historical documents. All properly archived. | **No action needed.** Archive structure is correct. |
| `dev/reviews/archive/*.md` (12 files) | ~5000+ | Historical code reviews from various LLMs. | **No action needed.** Archive structure is correct. |

### High Signal-to-Noise (Keep As-Is)

| File | Lines | Why It's Good |
|------|------:|---------------|
| `docs/TLDR.md` | 86 | Perfect quick reference. Every line earns its place. |
| `docs/FAQ.md` | 117 | Practical questions, concise answers. |
| `docs/ADHOC_MARKETS.md` | 234 | Clean structure: overview → quick start → reference → patterns → troubleshooting. |
| `SECURITY.md` | 133 | Appropriately detailed for the sensitivity level. |
| `README.md` | 355 | Strong first impression. Real examples. Clear quick start. |

### Verbose But Justified

| File | Lines | Assessment |
|------|------:|------------|
| `docs/DATA_VERIFICATION.md` | 414 | Case studies are long but educational. Each documents a real error and its fix. Keeps ARIA honest. **Keep.** |
| `docs/NOTIFICATION_PROFILES.md` | 766 | Comprehensive but overwhelming. **Split** into Quick Start (setup + 2 examples, ~150 lines) and Cookbook (advanced recipes + commentary config, ~600 lines). |
| `docs/ESI.md` | 424 | Long but covers OAuth flow end-to-end. Could extract scope reference table to an appendix. **Low priority.** |
| `docs/PERSONA_LOADING.md` | 424 | Mixes user config ("how to enable RP") with developer internals ("persona context compilation pipeline"). **Split** user-facing persona config from developer-facing loading mechanics. |

### Concrete Noise Reduction Edits

1. **`docs/ROUTE_SCENARIOS.md`** — Delete from `docs/`. If kept anywhere, move to `reference/lore/route_scenarios.md` as EVE world-building reference.
2. **`docs/CONTEXT_POLICY.md` §9 (Singleton Management)** — Pure developer concern. Will move with the file to `dev/docs/`.
3. **`docs/CONTEXT_POLICY.md` §10 (Budget Tracking `[Not Yet Implemented]`)** — Mark clearly or remove the unimplemented section.
4. **`personas/_shared/rp-levels.md` §Migration from 4-Level System** — Replace 12-line section with one-line footnote: `> The previous "lite" level was merged into "off" in v0.2.`
5. **`CONTRIBUTING.md` §Keep It In-Universe** — Reads as if all contributions must be in-character. Reword to clarify this applies to persona content, not code or docs.

---

## 4. User-Facing Documentation Gaps

### Critical (Blocks New User Success)

| Gap | Impact | Remedy |
|-----|--------|--------|
| **No slash command reference** | Users must use `/help` inside Claude Code or read 51 separate SKILL.md files. No way to browse commands before installing. | Create `docs/COMMANDS.md` with categorized table: command, description, example trigger phrase. |
| **No consolidated troubleshooting** | Troubleshooting is scattered across README (3 items), FIRST_RUN (4), FAQ (4), DEPLOYMENT (4). A user with "something broke" has to guess which doc to check. | Create `docs/TROUBLESHOOTING.md` consolidating all troubleshooting sections. Individual docs link to it instead of duplicating. |
| **`FIRST_RUN.md` examples incomplete** | Section lists 4 examples now (fixed in previous review) but lacks descriptions of what each demonstrates. | Add 1-2 sentence description per example explaining the playstyle and what makes it distinctive. |

### High (Affects User Experience)

| Gap | Impact | Remedy |
|-----|--------|--------|
| **No "What Can ARIA Do?" showcase** | README has 3 examples. Users wanting a feature gallery before installing have nothing. GitHub visitors deciding whether to star/clone see limited surface area. | Add `docs/FEATURES.md` or expand README's "What ARIA Does" section with more collapsed examples covering market, mining, skill planning. |
| **NOTIFICATION_PROFILES.md overwhelming** | 766 lines. User wanting basic Discord alerts must read past advanced recipe cookbook, LLM commentary config, and warrant scoring. | Split into `NOTIFICATION_PROFILES.md` (setup + basic examples, ~200 lines) and `NOTIFICATION_COOKBOOK.md` (advanced recipes + commentary, ~550 lines). |
| **No persona quick-switch guide** | FIRST_RUN.md covers faction switching but it's buried. Users wanting to try different personas need to hunt. | Add a "Switching Personas" section to FAQ or make the FIRST_RUN.md section more discoverable via docs/README.md. |
| **CONTEXT_AWARE_TOPOLOGY.md lacks worked example** | Users configuring topology can't verify they understand the scoring formula. | Add concrete calculation: "System X with these properties scores Y because..." |

### Medium (Polish for Public Release)

| Gap | Impact | Remedy |
|-----|--------|--------|
| **No Windows/WSL2 specific guide** | README notes WSL2 support but no guide for Windows users on WSL2 setup specifics. | Add WSL2 section to DEPLOYMENT.md or FAQ. |
| **No upgrade/migration guide** | DEPLOYMENT.md has `git pull && uv sync` but no guidance for breaking changes, data migrations, or config format updates. | Add "Upgrading" section to DEPLOYMENT.md with version-specific notes pattern. |
| **No "How ARIA Uses Your Data" privacy page** | FAQ covers "Is my data sent anywhere?" but a dedicated, linkable privacy/data-handling page would be valuable for trust. | Consider `docs/PRIVACY.md` or expand the Security section of README. |

---

## 5. Developer-Facing Documentation Gaps

### Critical (Blocks Contributor Success)

| Gap | Impact | Remedy |
|-----|--------|--------|
| **No skill creation guide** | 51 skills exist with no documentation on how to create a new one. Skill loading is documented in `skill-loading.md` but from the architecture perspective, not as a contributor walkthrough. | Create `dev/docs/CONTRIBUTING_SKILLS.md` with step-by-step: create directory, write SKILL.md, add to _index.json, test, add overlay support. |
| **No persona creation guide** | `personas/README.md` L171 references a non-existent hook script. Adding a persona requires reading 4+ files. | Create `dev/docs/CONTRIBUTING_PERSONAS.md` with checklist: directory, manifest.yaml, voice.md, intel-sources.md, regenerate context. |
| **No `.claude/skills/` index** | 51 skill directories with no navigation. Contributor must `ls` and guess. | Create `.claude/skills/README.md` with categorized listing. |

### High (Friction for Contributors)

| Gap | Impact | Remedy |
|-----|--------|--------|
| **No MCP dispatcher development guide** | Adding a new MCP action requires understanding context policy, output wrapping, error handling, testing patterns. No guide exists. | Create `dev/docs/MCP_DEVELOPMENT.md` covering: dispatcher pattern, action implementation, context wrapping, testing with conftest fixtures. |
| **ADR index incomplete** | 5 ADRs exist in `dev/decisions/` but the README there is minimal. No index of what decisions were made and why. | Expand `dev/decisions/README.md` with decision log table. |
| **No dev environment quick start** | PYTHON_ENVIRONMENT.md covers `uv run` but doesn't explain the full dev setup flow: clone → uv sync --all-extras → run tests → understand project structure. | Add `dev/docs/GETTING_STARTED.md` for developers. |
| **`dev/` not indexed beyond README** | 80+ files in dev/ across proposals, reviews, STPs, decisions, archives. No way to find what you need. | Expand `dev/README.md` with better cross-referencing. The current structure section is good; add "Finding Things" section. |

### Medium (Quality of Life)

| Gap | Impact | Remedy |
|-----|--------|--------|
| **No code architecture guide** | `docs/ARCHITECTURE.md` covers high-level system diagram but nothing about code organization: where to find services, how dispatchers call implementations, the MCP→services→data flow. | Add `dev/docs/CODE_ARCHITECTURE.md` or expand ARCHITECTURE.md with code-level details. |
| **Test fixture documentation** | TESTING.md mentions fixtures but doesn't document what's available in conftest.py or how to use mock ESI/market fixtures effectively. | Expand TESTING.md fixtures section with inventory and usage patterns. |
| **No release process documentation** | `dev/RELEASE.md` exists but is minimal (56 lines). Doesn't cover versioning policy, changelog workflow, or announcement process. | Expand `dev/RELEASE.md` for pre-public-announcement. |

---

## 6. Documentation Debt: Broken Links, Stale Content, Inconsistencies

### Broken References

| Source | Reference | Status | Fix |
|--------|-----------|--------|-----|
| `personas/README.md` L171 | `.claude/hooks/aria-boot.d/persona-detect.sh` | File does not exist | Update to `uv run aria-esi persona-context` |
| `reference/INDEX.md` L42-89 | `missions/*.md`, `ships/fittings/*.md` | Directories don't exist | Remove broken entries |
| `docs/DATA_AUTHORITY.md` L96 | `sov-load-coalitions` command | Undocumented command | Add docs or link to CLI help |
| `docs/CONTEXT_POLICY.md` L67-68 | `src/aria_esi/mcp/context.py` imports | Verify paths still accurate | Check and update |

### Stale Terminology

| Term | Location | Status | Fix |
|------|----------|--------|-----|
| `lite` RP level | `personas/*/voice.md`, `rp-levels.md` | Deprecated; merged into `off` | Remove from all files |
| `ship_status.md` | `CONTRIBUTING.md` L44 | Examples use different filenames | Align with actual filenames |
| 4-level RP migration | `rp-levels.md` L54-65 | Historical; no longer relevant | Collapse to footnote |

### Schema Inconsistencies

| Document | Issue | Fix |
|----------|-------|-----|
| `NOTIFICATION_PROFILES.md` | Schema version v1 in prose, v2 in examples | Reconcile to v2 throughout |

---

## 7. Big Wins: Highest Impact for Least Effort

Ordered by impact-to-effort ratio:

### 1. Create `docs/COMMANDS.md` (HIGH impact, MEDIUM effort)

A single-page command reference is the #1 missing doc. Every user needs it. No competing project in the EVE tooling space has 51 commands without a reference card.

**Format:** Table with columns: Command, Category, Description, Example. Group by category (Combat, Navigation, Market, Industry, Administration).

**Source:** Auto-generate from `.claude/skills/_index.json` + each SKILL.md's first line. This could even be a script.

### 2. Split `docs/` by Audience (HIGH impact, MEDIUM effort)

Moving ~12 files from `docs/` to `dev/docs/` and `dev/docs/ai-runtime/` is a mechanical operation. The hardest part is updating CLAUDE.md references (find-and-replace). The payoff is a dramatically cleaner first impression.

### 3. Create `docs/TROUBLESHOOTING.md` (HIGH impact, LOW effort)

Consolidate the ~15 troubleshooting items scattered across 5 files into one page. Takes 1-2 hours. Eliminates the "where do I look when something breaks?" problem entirely.

### 4. Fix All Broken Links (MEDIUM impact, LOW effort)

~4 broken references. ~30 minutes to fix. Eliminates dead-end navigation for contributors.

### 5. Split `NOTIFICATION_PROFILES.md` (MEDIUM impact, LOW effort)

Move everything after "CLI Reference" into a separate `NOTIFICATION_COOKBOOK.md`. Reduces the main doc from 766 to ~300 lines.

### 6. Purge Stale `lite` RP References (LOW impact, LOW effort)

Grep-and-fix across ~5 files. 30 minutes.

---

## 8. Pre-Announcement Checklist

Issues that should be resolved before publicly announcing the project:

### Must Fix

- [ ] **Create `docs/COMMANDS.md`** — visitors need to see what ARIA can do
- [ ] **Fix all broken links** — dead links signal unmaintained project
- [ ] **Remove stale `lite` RP references** — internal inconsistency visible to contributors
- [ ] **Fix `personas/README.md` hook reference** — blocks "Adding a New Persona" instructions
- [ ] **Reconcile notification schema version** — v1/v2 inconsistency confuses early adopters
- [ ] **Expand FIRST_RUN examples** — with descriptions per example
- [ ] **Verify LICENSE file exists and is correct** — MIT license mentioned but verify
- [ ] **Verify `.env.example` exists** — CLAUDE.md references it as template
- [ ] **Add `docs/TROUBLESHOOTING.md`** — consolidate scattered troubleshooting

### Should Fix

- [ ] **Split `docs/` by audience** — move developer/AI-runtime docs out
- [ ] **Split `NOTIFICATION_PROFILES.md`** — Quick Start + Cookbook
- [ ] **Split `PERSONA_LOADING.md`** — user config vs developer internals
- [ ] **Add WSL2 guidance** — platform support claims WSL2 but no setup guide
- [ ] **Create `dev/docs/CONTRIBUTING_SKILLS.md`** — skill creation guide
- [ ] **Create `dev/docs/CONTRIBUTING_PERSONAS.md`** — persona creation guide
- [ ] **Expand `dev/RELEASE.md`** — release process for public project
- [ ] **Add `ROUTE_SCENARIOS.md` notice or remove** — currently misleading (describes features ARIA can't do)

### Nice to Have

- [ ] **Add CI link checker** — `markdown-link-check` or `lychee` in GitHub Actions
- [ ] **Create `docs/FEATURES.md`** — expanded showcase for GitHub visitors
- [ ] **Add `dev/docs/MCP_DEVELOPMENT.md`** — dispatcher development guide
- [ ] **Expand `dev/decisions/README.md`** — ADR index
- [ ] **Add `dev/docs/GETTING_STARTED.md`** — developer quick start
- [ ] **Create `.claude/skills/README.md`** — skill directory index
- [ ] **Add terminology tables to empire personas** — parity with PARIA's voice definition

---

## 9. CLAUDE.md Assessment

`CLAUDE.md` is 600+ lines and serves as the system prompt for ARIA sessions. It is not user-facing documentation in the traditional sense — it's machine-readable instructions.

### Current Issues

1. **Duplicates content from `docs/`** — MCP tool reference tables, agent query docs, data verification principles all exist in both CLAUDE.md and separate docs.
2. **Maintenance burden** — changes to MCP dispatchers require updating both CLAUDE.md and the relevant docs file.
3. **Cannot be split easily** — Claude Code reads CLAUDE.md as a single file. It can't `#include` other files.

### Recommendation

**Accept CLAUDE.md as a necessary monolith.** It serves a fundamentally different purpose than human docs. The duplication with `docs/` files is the real problem — not CLAUDE.md's length. Once developer/AI-runtime docs are moved to `dev/docs/`, the duplication is reduced because the canonical version lives in one place with CLAUDE.md referencing it by path.

**Do not** attempt to "simplify" CLAUDE.md for readability. It's not read by humans during normal use. Its verbosity is intentional — the LLM needs explicit, unambiguous instructions.

---

## 10. `dev/` Directory Health

### Current State

`dev/` is well-organized with clear subdirectories:

```
dev/
├── archive/          # 17 historical docs (properly archived)
├── decisions/        # 5 ADRs
├── mechanics/        # 3 game mechanics research docs
├── plans/            # 1 implementation plan
├── proposals/        # 1 active + 25 archived proposals
├── reviews/          # 10 active reviews + 12 archived
├── spikes/           # 1 technical spike
├── stp/              # 1 active + 11 completed skill tracking plans
├── DESIGN.md         # Original project proposal (should archive)
├── RELEASE.md        # Release checklist (needs expansion)
└── README.md         # Directory guide (adequate)
```

### Issues

1. **`dev/DESIGN.md` is a historical artifact.** It describes the original single-faction ARIA concept. The project has evolved far beyond it. Move to `dev/archive/`.
2. **`dev/README.md` is adequate but not great.** It lists directories but doesn't help a developer find specific information. Add a "Finding Things" section.
3. **No developer getting-started guide.** A contributor clone → first-test-run path isn't documented.
4. **STP directory well-maintained.** 11 completed, 1 active. Good process evidence.
5. **Archive discipline is strong.** Proposals get archived when implemented. Reviews get archived when superseded. This is good.

### Recommendations for `dev/`

1. Move `dev/DESIGN.md` → `dev/archive/DESIGN.md`
2. After the `docs/` split, `dev/docs/` becomes the developer documentation home
3. Expand `dev/README.md` to cross-reference `dev/docs/` content
4. Keep archive discipline — it's working well

---

## 11. Implementation Phases

### Phase 1: Pre-Announcement Critical Path (1 week)

| # | Action | Effort | Files |
|---|--------|--------|-------|
| 1 | Create `docs/COMMANDS.md` from skill index | 3 hrs | New file |
| 2 | Create `docs/TROUBLESHOOTING.md` consolidation | 2 hrs | New file + edits to 5 docs |
| 3 | Fix all broken links (4 instances) | 30 min | 3 files |
| 4 | Remove stale `lite` RP references | 30 min | ~5 files |
| 5 | Fix personas/README.md hook reference | 15 min | 1 file |
| 6 | Reconcile notification schema v1→v2 | 30 min | 1 file |
| 7 | Expand FIRST_RUN.md examples with descriptions | 15 min | 1 file |

**Total: ~7 hours**

### Phase 2: Audience Split (1-2 weeks)

| # | Action | Effort | Files |
|---|--------|--------|-------|
| 8 | Create `dev/docs/` and `dev/docs/ai-runtime/` directories | 15 min | Directories |
| 9 | Move 6 developer docs from `docs/` to `dev/docs/` | 1 hr | 6 files + updates |
| 10 | Move 6 AI-runtime docs from `docs/` to `dev/docs/ai-runtime/` | 1 hr | 6 files + updates |
| 11 | Update all CLAUDE.md references to new paths | 1 hr | CLAUDE.md |
| 12 | Update `docs/README.md` index (remove moved files, add new ones) | 30 min | 1 file |
| 13 | Create `dev/docs/README.md` developer index | 1 hr | New file |
| 14 | Create `dev/docs/ai-runtime/README.md` explaining these files | 30 min | New file |
| 15 | Extract user-relevant parts of PYTHON_ENVIRONMENT.md into DEPLOYMENT.md | 1 hr | 2 files |
| 16 | Split NOTIFICATION_PROFILES.md → Quick Start + Cookbook | 1 hr | 2 files |
| 17 | Split PERSONA_LOADING.md → user config + dev internals | 1.5 hrs | 2 files |

**Total: ~9 hours**

### Phase 3: Contributor Enablement (2-4 weeks)

| # | Action | Effort | Files |
|---|--------|--------|-------|
| 18 | Create `dev/docs/CONTRIBUTING_SKILLS.md` | 2 hrs | New file |
| 19 | Create `dev/docs/CONTRIBUTING_PERSONAS.md` | 2 hrs | New file |
| 20 | Create `.claude/skills/README.md` skill index | 1.5 hrs | New file |
| 21 | Create `dev/docs/MCP_DEVELOPMENT.md` | 3 hrs | New file |
| 22 | Create `dev/docs/GETTING_STARTED.md` (dev quick start) | 2 hrs | New file |
| 23 | Expand `dev/decisions/README.md` with ADR index | 30 min | 1 file |
| 24 | Move `dev/DESIGN.md` to archive | 5 min | 1 file |
| 25 | Add worked example to CONTEXT_AWARE_TOPOLOGY.md | 1 hr | 1 file |

**Total: ~12 hours**

### Phase 4: Quality Gates (ongoing)

| # | Action | Cadence |
|---|--------|---------|
| 26 | Add `markdown-link-check` or `lychee` to CI | One-time setup |
| 27 | Add PR template: "Does this PR add/remove a command? Update COMMANDS.md" | One-time setup |
| 28 | Terminology lint in pre-commit (grep for deprecated terms) | One-time setup |
| 29 | Quarterly doc freshness audit | Quarterly |
| 30 | Auto-generate COMMANDS.md from skill index (script) | Per release |

---

## 12. Success Criteria

Documentation is "release-ready" when:

1. **A new user can go from `git clone` to first ARIA response in under 10 minutes** following only docs/ files
2. **A GitHub visitor can understand what ARIA does in under 2 minutes** from README + docs/COMMANDS.md
3. **`docs/` contains zero developer-only files** — all developer docs are in `dev/docs/`
4. **Zero broken internal links** verified by CI
5. **Zero stale terminology** (no `lite` RP level, no non-existent file references)
6. **A contributor can create a new skill** following `dev/docs/CONTRIBUTING_SKILLS.md` without external help
7. **Every slash command** is documented in `docs/COMMANDS.md`
8. **Troubleshooting has a single entry point** at `docs/TROUBLESHOOTING.md`

---

## Appendix A: Comparison with Open-Source Documentation Standards

| Practice | ARIA Status | Target |
|----------|-------------|--------|
| README has clear quick start | Yes | Maintain |
| README shows real output examples | Yes (3 examples) | Expand to 5-6 |
| docs/ is user-focused | No (mixed audiences) | Split by Phase 2 |
| Progressive disclosure (quick start → guide → reference) | Partial (TLDR → FIRST_RUN → detailed) | Complete with COMMANDS.md |
| Consolidated troubleshooting | No (scattered) | TROUBLESHOOTING.md |
| Contributing guide for major extension points | No (skills, personas undocumented) | Phase 3 |
| Automated link checking in CI | No | Phase 4 |
| Command/API reference page | No | COMMANDS.md in Phase 1 |
| Architecture overview | Yes (ARCHITECTURE.md) | Maintain |
| Security policy | Yes (SECURITY.md) | Maintain |
| License clarity | Yes (README, CONTRIBUTING) | Maintain |
| Example configurations | Yes (4 examples) | Maintain, grow organically |
| Changelog | Yes (new, short) | Maintain as project matures |

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

*Review generated 2026-02-15. Supersedes previous review dated 2026-02-10.*
