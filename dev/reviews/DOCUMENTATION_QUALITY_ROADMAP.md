# Documentation Quality Roadmap Review

**Date:** 2026-02-10
**Reviewer:** AI-assisted audit (Claude Opus 4.6)
**Scope:** All user-facing documentation per `dev/prompts/docs/documentation_quality_roadmap.md`

---

## 1. Documentation Maturity Snapshot

### Current State

ARIA's documentation is **mature and comprehensive** for a project of this scope. With ~250 markdown files totaling ~33,000+ lines, the project demonstrates strong documentation discipline. The docs cover the full lifecycle from first-run setup through advanced features like real-time intel and Discord notifications.

### Strengths

- **Progressive disclosure:** Three-layer onboarding path (TLDR.md → FIRST_RUN.md → detailed docs) serves both impatient and thorough users
- **Security-first documentation:** Threat model, path validation, data integrity, prompt injection defense are all documented prominently
- **Example-driven:** 4 complete playstyle example configurations spanning all major factions
- **Audience segmentation:** Clear separation between user docs, contributor docs, and developer docs
- **Well-indexed:** `docs/README.md` provides organized navigation by audience and topic
- **Real-world demonstrations:** README includes actual ARIA output examples (route planning, mission briefs, fit recommendations)

### Major Deficits

- **No CLI command reference:** 51 slash commands + CLI subcommands have no single reference page
- **Broken internal links:** Several cross-references point to files that don't exist
- **Stale terminology:** Deprecated 4-level RP system ("lite") persists in some files
- **Missing contributor guides:** No guide for creating new personas or skills
- **Signal-to-noise in CLAUDE.md:** 600+ line system instructions file mixes user-facing and machine-facing concerns

---

## 2. Findings List (Ranked by Severity)

### Critical

No critical issues found that block usability or safety.

### High

| # | File | Lines | Finding | Impact | Fix |
|---|------|-------|---------|--------|-----|
| H-1 | `personas/README.md` | 171 | References `.claude/hooks/aria-boot.d/persona-detect.sh` which does not exist | New contributor following "Adding a New Persona" instructions hits dead end | Update to reference `uv run aria-esi persona-context` or verify file exists |
| H-2 | `reference/INDEX.md` | 42-89 | Links to `missions/*.md`, `ships/fittings/*.md` directories that don't exist | INDEX.md advertises content that was never created or was removed | Remove broken entries or create the referenced files |
| H-3 | Multiple | -- | No CLI command reference card exists | Users and contributors have no quick reference for all 51 commands | Create `docs/COMMANDS.md` with categorized command listing |
| H-4 | `docs/NOTIFICATION_PROFILES.md` | 113, 515 | Schema version inconsistency (v1 in docs, v2 in examples) | Users may write invalid notification profiles | Reconcile schema version across all examples |

### Medium

| # | File | Lines | Finding | Impact | Fix |
|---|------|-------|---------|--------|-----|
| M-1 | `personas/_shared/rp-levels.md` | 54-65 | Retains "Migration from 4-Level System" section for deprecated `lite` level | Confusion about current RP levels | Archive migration section or mark clearly as historical |
| M-2 | `personas/paria/voice.md` | -- | References `lite` RP level in address table | Stale data conflicts with current 3-level system | Remove `lite` entries from all manifest/voice files |
| M-3 | `docs/CONTEXT_AWARE_TOPOLOGY.md` | 19, 250 | Layer score formula lacks worked example; `topology-explain` output not shown | Users can't verify their understanding of scoring | Add concrete calculation example and sample output |
| M-4 | `docs/DATA_AUTHORITY.md` | 96 | References `sov-load-coalitions` command without full documentation | Users can't follow the described workflow | Document the command or link to where it's documented |
| M-5 | `CONTRIBUTING.md` | 44 | Lists `ship_status.md` as required example file but examples use different filenames | Contributors may create wrong file structure | Align filenames with actual example directory contents |
| M-6 | `docs/CONTEXT_POLICY.md` | 259-274 | Documents budget tracking feature noted as "not currently called in production" | Developer confusion about feature maturity | Mark section as `[Not Yet Implemented]` or remove |
| M-7 | `personas/_shared/skill-loading.md` | 94-111 | Examples 2 and 3 differ by one subtle condition (file existence) that's easy to miss | Overlay resolution logic misunderstood | Add explicit callout: "The only difference is whether the variant overlay FILE EXISTS" |
| M-8 | -- | -- | No `.claude/skills/README.md` exists | 51 skill directories with no navigation guide | Create categorized skill index |
| M-9 | `docs/FIRST_RUN.md` | 254-256 | Examples section only lists one example despite 4 existing | Users miss 3 of 4 available example configurations | List all 4 examples with descriptions |
| M-10 | `docs/ESI.md` | 205 | References `cron-example.txt` script not verified to exist | Scheduled refresh instructions may be incomplete | Verify file exists or inline the cron example |

### Low

| # | File | Lines | Finding | Impact | Fix |
|---|------|-------|---------|--------|-----|
| L-1 | `docs/PROTOCOLS.md` | 44 | "fluid router" terminology used without definition | Minor confusion for new developers | Define term or link to explanation |
| L-2 | `docs/DEPLOYMENT.md` | 96-107 | `.mcp.json` configuration unclear whether auto-generated or manual | Minor setup friction | Clarify generation method |
| L-3 | `docs/DATA_SOURCES.md` | 139 | Non-SDE data registry lists only 3 items | Registry appears incomplete | Complete the registry or note it's partial |
| L-4 | `docs/MULTI_PILOT_ARCHITECTURE.md` | 145 | References `ADR-001` which was not verified to exist | Minor navigation dead-end | Verify ADR exists at `dev/decisions/` |
| L-5 | `personas/vind/manifest.yaml` | 15 | Gender-conditional greeting comment `"brother" # or "sister"` | YAML can't express conditional logic | Document how gender-aware greetings are resolved at runtime |
| L-6 | `examples/README.md` | 44 | References `ship_status.md` but actual file names may differ per example | Minor confusion when using examples as templates | Verify file names match across all examples |
| L-7 | `docs/TESTING.md` | 124 | Coverage target percentages may be stale | Minor - developers may have wrong expectations | Add "Last verified" date or automate from CI |
| L-8 | Multiple persona voice.md | -- | Inconsistent terminology table coverage across personas (PARIA has 7 mappings, others have none) | Empire persona voices are less well-defined | Add terminology tables to aria-mk4, aura-c, vind, throne |

### Info

| # | File | Lines | Finding | Impact | Fix |
|---|------|-------|---------|--------|-----|
| I-1 | `CLAUDE.md` | -- | 600+ lines mixing user-facing and machine-facing instructions | Not user-facing, but large maintenance surface | Consider splitting into sections or using includes |
| I-2 | `docs/NOTIFICATION_PROFILES.md` | -- | 754 lines is very long for a single doc | Scan-ability suffers | Consider splitting into basic + advanced cookbook |
| I-3 | `CHANGELOG.md` | -- | Only covers ~3 weeks of history (project is new) | Expected for a new project | Maintain as project matures |
| I-4 | `dev/` directory | -- | 30+ development docs are comprehensive but not indexed beyond dev/README.md | Developer onboarding friction | Consider adding dev/decisions/INDEX.md |

---

## 3. Gap Matrix by Doc Type

| Doc Type | Status | Quality | Key Gap |
|----------|--------|---------|---------|
| **Getting Started** | Complete | Excellent | FIRST_RUN.md only lists 1 of 4 examples |
| **Core Usage** | Complete | Very Good | Missing CLI command reference card |
| **Advanced Usage** | Complete | Very Good | NOTIFICATION_PROFILES.md schema version confusion |
| **Troubleshooting** | Partial | Good | Scattered across docs; no centralized troubleshooting guide |
| **Contributing** | Partial | Good | Missing persona/skill creation guides |
| **Reference/API** | Complete | Excellent | CLI help text is good; reference/INDEX.md has broken links |

### Getting Started (TLDR.md, FIRST_RUN.md, FAQ.md)

- **Coverage:** Install, configure, run, ESI setup, faction selection, RP levels
- **Gap:** No "What can ARIA do?" feature gallery with screenshots/examples beyond README
- **Gap:** FIRST_RUN.md examples section incomplete

### Core Usage (slash commands, natural language, data files)

- **Coverage:** COMMAND_SUGGESTIONS.md explains progressive disclosure; DATA_FILES.md covers data locations
- **Gap:** No single-page command reference. Users must use `/help` inside Claude Code or read 51 separate SKILL.md files

### Advanced Usage (notifications, topology, real-time intel, market scopes)

- **Coverage:** NOTIFICATION_PROFILES.md (754 lines), REALTIME_CONFIGURATION.md (382 lines), ADHOC_MARKETS.md (234 lines), CONTEXT_AWARE_TOPOLOGY.md (440 lines)
- **Gap:** Schema version inconsistency in notifications; topology scoring needs worked examples

### Troubleshooting

- **Coverage:** README.md has 3 troubleshooting items; FIRST_RUN.md has 4; FAQ.md has 4; most docs have tail troubleshooting sections
- **Gap:** No centralized troubleshooting guide. A user with "something broke" must guess which doc to check

### Contributing (CONTRIBUTING.md, dev/)

- **Coverage:** Licensing, example contributions, code quality, PR process
- **Gap:** No guide for creating new personas (scattered across 3+ docs). No guide for creating new skills. No skill index at `.claude/skills/`

### Reference/API (reference/, SDE, CLI)

- **Coverage:** 79 reference files; comprehensive mechanics, lore, industry data; well-structured CLI with click commands
- **Gap:** reference/INDEX.md advertises files that don't exist (missions/, ships/fittings/)

---

## 4. Signal-to-Noise Assessment

### Too Sparse

| Area | Problem | Remedy |
|------|---------|--------|
| CLI command reference | No consolidated listing exists | Create `docs/COMMANDS.md` |
| Persona creation workflow | Instructions scattered across 3+ files | Create `personas/CONTRIBUTING.md` with checklist |
| Skill creation workflow | No documentation exists | Add section to `personas/_shared/skill-loading.md` |
| Overlay sync timestamps | "Last synced with base skill" unexplained | Document what sync means in skill-loading.md |
| Exclusive skill stub pattern | Architecture described but not implementation | Show concrete stub→redirect examples |

### Too Verbose or Repetitive

| Area | Problem | Remedy |
|------|---------|--------|
| `NOTIFICATION_PROFILES.md` (754 lines) | Comprehensive but overwhelming as single doc | Split: basic setup (200 lines) + advanced cookbook (500 lines) |
| `CLAUDE.md` (600+ lines) | Mixes session init, security, data handling, CLI, MCP tools | Accept as system-instructions file; not user-facing |
| Agent query docs | Duplicated between `DATA_SOURCES.md` and `CLAUDE.md` | Keep canonical version in DATA_SOURCES.md; have CLAUDE.md reference it |
| RP level migration | 12 lines in rp-levels.md for deprecated feature | Archive or collapse to 2-line footnote |
| Data verification case studies | DATA_VERIFICATION.md has extensive examples (~400 lines) | Keep - educational value outweighs verbosity |

### Concrete Edits for Balance

1. **FIRST_RUN.md L254:** Expand examples section to list all 4 example configurations
2. **rp-levels.md L54-65:** Replace 12-line migration section with: `> Note: The previous "lite" level was merged into "off" in v0.2.`
3. **NOTIFICATION_PROFILES.md:** Add `## Quick Start` section at top (10 lines) before deep schema docs
4. **CONTRIBUTING.md L44:** Add "See `examples/README.md` for the full list of example configurations and file naming conventions"

---

## 5. Prioritized Roadmap

### Phase 1: Quick Wins (1-2 weeks)

| # | Action | Files Affected | Effort |
|---|--------|----------------|--------|
| 1 | Fix broken links in `reference/INDEX.md` | `reference/INDEX.md` | 30 min |
| 2 | Remove/update `lite` RP level references | `personas/*/voice.md`, `personas/*/manifest.yaml`, `rp-levels.md` | 1 hr |
| 3 | Fix `personas/README.md` L171 hook reference | `personas/README.md` | 15 min |
| 4 | Reconcile notification schema version (v1 vs v2) | `docs/NOTIFICATION_PROFILES.md` | 30 min |
| 5 | Expand FIRST_RUN.md examples section | `docs/FIRST_RUN.md` | 15 min |
| 6 | Verify/fix ESI.md cron-example.txt reference | `docs/ESI.md` | 15 min |
| 7 | Align CONTRIBUTING.md file names with examples | `CONTRIBUTING.md` | 15 min |
| 8 | Add "Not Yet Implemented" marker to CONTEXT_POLICY.md budget tracking | `docs/CONTEXT_POLICY.md` | 5 min |

**Total estimated effort:** ~3 hours

### Phase 2: Structural Improvements (2-6 weeks)

| # | Action | Files Affected | Effort |
|---|--------|----------------|--------|
| 9 | Create `docs/COMMANDS.md` command reference | New file | 2-3 hrs |
| 10 | Create `.claude/skills/README.md` skill index | New file | 1-2 hrs |
| 11 | Create `personas/CONTRIBUTING.md` persona creation guide | New file | 1-2 hrs |
| 12 | Add worked example to CONTEXT_AWARE_TOPOLOGY.md scoring | `docs/CONTEXT_AWARE_TOPOLOGY.md` | 1 hr |
| 13 | Add terminology tables to empire persona voice files | `personas/aria-mk4/voice.md`, `aura-c/voice.md`, `vind/voice.md`, `throne/voice.md` | 2 hrs |
| 14 | Split NOTIFICATION_PROFILES.md into basic + advanced | `docs/NOTIFICATION_PROFILES.md` + new file | 1-2 hrs |
| 15 | Create centralized troubleshooting guide | New `docs/TROUBLESHOOTING.md` | 2-3 hrs |
| 16 | Document overlay creation workflow in skill-loading.md | `personas/_shared/skill-loading.md` | 1 hr |

**Total estimated effort:** ~15 hours

### Phase 3: Ongoing Governance & Quality Controls (continuous)

| # | Action | Owner | Cadence |
|---|--------|-------|---------|
| 17 | Internal link checker in CI | Maintainer | Per PR |
| 18 | Doc review as part of PR template | Contributor | Per PR |
| 19 | Quarterly doc freshness audit | Maintainer | Quarterly |
| 20 | Automated coverage check: new CLI command → COMMANDS.md entry | CI | Per PR |
| 21 | CHANGELOG maintenance | Maintainer | Per release |
| 22 | Example configuration validation (templates match examples) | CI | Per release |

---

## 6. Success Metrics & Maintenance Guardrails

### Target State

"High-quality docs" for ARIA means:

1. **Zero broken internal links** verified by CI
2. **Every slash command** documented in COMMANDS.md with trigger phrases and one-line description
3. **Every user-facing feature** reachable within 2 clicks from docs/README.md
4. **No stale terminology** (deprecated RP levels, removed commands, renamed files)
5. **New contributor can create a persona** following a single guide without hunting across files
6. **Troubleshooting is centralized** with links from individual doc troubleshooting sections

### Metrics to Track

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Broken internal links | ~8-10 | 0 | CI link checker |
| Documented slash commands | 0 (in reference) | 51 | COMMANDS.md row count |
| Example configurations | 4 | 6+ | `examples/` subdirectory count |
| Stale RP level references | ~3-5 files | 0 | Grep for "lite" in personas/ |
| Doc-to-feature ratio | High | High | Maintain current coverage |

### Maintenance Guardrails

1. **PR template check:** "Does this PR add/remove a command? Update docs/COMMANDS.md"
2. **Link validation:** Add `markdown-link-check` or equivalent to CI
3. **Terminology lint:** Grep for deprecated terms ("lite" level, old file paths) in pre-commit
4. **Quarterly audit:** Run this documentation review prompt every quarter against main branch
5. **Doc ownership:** Each docs/ file should have implicit ownership (the person who last substantially edited it)

---

## Top 10 Actions (Ordered Checklist)

1. [ ] Fix broken links in `reference/INDEX.md` (remove references to non-existent missions/, ships/fittings/ directories)
2. [ ] Audit and remove all `lite` RP level references across personas/ directory
3. [ ] Fix `personas/README.md` L171 - update "Adding a New Persona" instructions
4. [ ] Reconcile notification profile schema version (v1 vs v2 inconsistency)
5. [ ] Create `docs/COMMANDS.md` - consolidated slash command reference
6. [ ] Create `.claude/skills/README.md` - categorized skill index for contributors
7. [ ] Create `personas/CONTRIBUTING.md` - persona creation checklist
8. [ ] Add worked scoring example to `docs/CONTEXT_AWARE_TOPOLOGY.md`
9. [ ] Expand `docs/FIRST_RUN.md` examples section to list all 4 configurations
10. [ ] Add internal link checking to CI pipeline

## Definition of Done

Documentation is "up to par" when:

- [ ] All items in Phase 1 are complete (0 broken links, 0 stale terminology)
- [ ] COMMANDS.md exists and covers all 51 slash commands
- [ ] A new contributor can create a persona by following `personas/CONTRIBUTING.md` without external help
- [ ] A new user can go from clone → first ARIA response in under 10 minutes following docs
- [ ] CI validates internal markdown links on every PR
- [ ] No file references deprecated RP levels, removed commands, or non-existent files

---

*Review generated per `dev/prompts/docs/documentation_quality_roadmap.md` specification.*
