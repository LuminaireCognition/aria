# Documentation and Onboarding UX Review
**Date:** 2026-02-24
**Prompt:** dev/prompts/docs/onboarding_first_run_ux.md
**Reviewer:** Claude Opus 4.6

---

## Executive Summary

ARIA's documentation is notably comprehensive for a project of this complexity. The README is clear, the onboarding path is well-defined, and the `aria-init` wizard abstracts away most manual setup. The docs/ directory has a proper index, cross-references are generally accurate, and troubleshooting coverage is unusually thorough.

The issues found are predominantly Medium/Low severity -- documentation inconsistencies, a few stale references, and minor discoverability gaps rather than fundamental onboarding blockers. A new user following the README can reach a working state in under 10 minutes with no tribal knowledge.

**Findings by severity:**
- Critical: 0
- High: 2
- Medium: 7
- Low: 6
- Info: 4

---

## 1. Onboarding Flow Assessment (Clone to Working State)

### Happy Path (Rating: Excellent)

The core onboarding flow is one of the best I've reviewed for a developer-tool project:

```
git clone ... && cd aria
./aria-init        # Interactive wizard: asks name, faction, downloads data
claude             # Start using ARIA
```

Three commands to a working state. The `aria-init` wizard:
- Checks prerequisites (uv) with clear error messages pointing to install URLs
- Detects unsupported platforms (native Windows) and exits cleanly
- Handles JSON operations with or without jq (Python fallback)
- Provides progress indicators during data seeding (~100MB download)
- Creates all required directory structure and config files
- Uses color output with graceful degradation for dumb terminals

The DevContainer path is equally clean and well-documented as an alternative.

### Pain Points Identified

1. **No `--help` signpost in README Quick Start** -- The README shows `./aria-init` but doesn't mention `--help`. A user who wants to understand options before running would benefit from seeing the flag.

2. **`aria-init` version is hardcoded at 1.0.0** (line 20 of `aria-init`) while `pyproject.toml` says version 2.0.0. Not a functional issue but signals staleness to observant users.

3. **ESI is described as "optional" consistently** -- which is good -- but the boundary of "what works without ESI" is scattered across README (line 267), FIRST_RUN.md (lines 137-149), ESI.md (lines 25-36), and FAQ.md (lines 49-54). A single canonical table would reduce redundancy.

---

## 2. Documentation Completeness Audit

### What Exists (Strong)

| Area | Status | Notes |
|------|--------|-------|
| Value proposition | Complete | README lines 9, 29-31, 45-55 |
| Prerequisites | Complete | README lines 66-72; FIRST_RUN lines 7-10 |
| Install (local) | Complete | README lines 98-111; DEPLOYMENT.md lines 26-50 |
| Install (container) | Complete | README lines 84-95; DEPLOYMENT.md lines 1-24 |
| First run wizard | Complete | FIRST_RUN.md lines 40-56 |
| ESI setup | Complete | ESI.md is thorough (427 lines) |
| Manual config | Complete | FIRST_RUN.md lines 68-132 |
| Command reference | Complete | COMMANDS.md covers all 48 commands |
| Feature matrix | Complete | FEATURES.md with ESI dependency column |
| Troubleshooting | Complete | TROUBLESHOOTING.md covers 10+ scenarios |
| Architecture | Complete | ARCHITECTURE.md with mermaid diagram |
| Security | Complete | SECURITY.md + SECURITY_000.md review |
| Contributing | Complete | CONTRIBUTING.md with PR process |
| Examples | Complete | 4 faction examples + README |
| Developer setup | Complete | dev/docs/GETTING_STARTED.md |
| FAQ | Complete | FAQ.md covers common questions |
| Doc freshness process | Complete | dev/docs/DOC_FRESHNESS.md |

### What Is Missing or Incomplete

See individual findings below.

---

## 3. Information Architecture Evaluation

### Structure (Rating: Good)

```
docs/                        # User-facing docs (19 files)
  README.md                  # Index with "Where to Start" routing
  TLDR.md                   # 1-page quickstart
  FIRST_RUN.md              # Detailed setup
  ...
dev/docs/                    # Developer docs (14 files)
  README.md                 # Developer index
  GETTING_STARTED.md        # Developer quickstart
  ai-runtime/               # LLM instruction docs
  ...
```

The two-tier split (docs/ for users, dev/docs/ for developers) is sound and clearly signposted. The docs/README.md index routes users by persona ("New to ARIA?", "Setting up ESI?", "Building or contributing?") which is good information architecture.

### Strengths

- **Progressive disclosure**: TLDR.md -> FIRST_RUN.md -> detailed docs
- **Multiple entry points**: README Quick Docs bar links to 5 key pages
- **Consistent cross-referencing**: Most docs link to related docs
- **"Where to Find Things" table** in dev/docs/GETTING_STARTED.md

### Weaknesses

- **Duplication**: Troubleshooting content is duplicated across README.md (lines 305-345), FIRST_RUN.md (lines 249-285), TROUBLESHOOTING.md, and FAQ.md. Four places maintain the same "ESI token expired" fix.
- **DEPLOYMENT.md vs FIRST_RUN.md overlap**: Both cover installation. DEPLOYMENT.md also covers MCP server setup and upgrading, making it half-reference, half-setup-guide.
- **No changelog or "What's New"**: Users upgrading have no way to see what changed between versions other than reading git log.

---

## 4. Error Message Quality Assessment

### aria-init (Rating: Excellent)

The wizard script has thoughtful error handling:

```bash
# Missing prerequisite -- clear message with install URL
"uv is required but was not found on PATH."
"Install from: https://docs.astral.sh/uv/"

# Unsupported platform -- clear rejection with alternative
"Native Windows shell is unsupported. Use WSL2 on Windows 11."

# Optional dependency -- graceful degradation
"jq not found on PATH; using uv run python stdlib fallback for JSON operations."
```

Color-coded output (green checkmarks, red X marks, yellow warnings) with proper fallback for non-color terminals.

### CLI Entry Point (Rating: Good)

The `aria-esi` CLI (`src/aria_esi/__main__.py`):
- Returns structured JSON errors with `error_type`, `message`, and `query_timestamp`
- Provides a `hint` field for unknown commands ("Run 'aria-esi help' for usage")
- Handles KeyboardInterrupt cleanly (exit code 130)
- Generic exceptions are caught and wrapped in structured output

One concern: the `output_error` function outputs errors as JSON to stdout rather than stderr. This is intentional for machine consumption but can confuse users who run commands interactively and see `{"error": "command_error", "message": "..."}` instead of a human-readable message.

### Boot Sequence (Rating: Good)

The `.claude/hooks/aria-boot.sh` hook provides clear feedback during session startup. Failure modes are documented in TROUBLESHOOTING.md.

---

## 5. Findings

### High Severity

---

**Finding H-1: `.mcp.json` config disagrees with DEPLOYMENT.md instructions**

- **Severity:** High
- **File:** `/home/aurelien/git/aria/.mcp.json` (entire file) and `/home/aurelien/git/aria/docs/DEPLOYMENT.md` (lines 122-133)
- **Finding:** The checked-in `.mcp.json` uses `"args": ["run", "python", "-m", "aria_esi.mcp.server"]` with `"cwd": "src"`, while DEPLOYMENT.md documents a different configuration: `"args": ["run", "aria-universe"]` with no `cwd` field. The `pyproject.toml` entry point `aria-universe = "aria_esi.mcp.server:main"` confirms the documented form should work, but a user copying the DEPLOYMENT.md snippet would get a different configuration than what the project ships.
- **Impact:** A developer or user who manually configures MCP from the docs gets a configuration that differs from the working shipped version. If the shipped version has the `cwd` for a reason (e.g., relative imports), the documented version may fail silently.
- **Fix:** Reconcile `.mcp.json` and DEPLOYMENT.md. Either update the docs to match the shipped config, or update `.mcp.json` to use the simpler `aria-universe` entry point. Add a note explaining why `cwd` is needed if it is.

---

**Finding H-2: `DEPLOYMENT.md` references `--extra dev` but dev tools are in `[dependency-groups]`, not `[project.optional-dependencies]`**

- **Severity:** High
- **File:** `/home/aurelien/git/aria/docs/DEPLOYMENT.md` (line 68)
- **Finding:** DEPLOYMENT.md instructs users to run `uv sync --extra dev` for development tools. However, `pyproject.toml` defines dev dependencies under `[dependency-groups]` (line 232), not `[project.optional-dependencies]`. The correct command is `uv sync --dev` (which is used in CLAUDE.md, `.devcontainer/post-create.sh`, and other files). The `--extra dev` flag would fail or install nothing because no `dev` optional-dependency group exists.
- **Impact:** A developer following DEPLOYMENT.md's instructions for development setup would not get pytest, mypy, ruff, pre-commit, or other dev tools installed.
- **Fix:** Change line 68 of DEPLOYMENT.md from `uv sync --extra dev` to `uv sync --dev`. The other `--extra` examples (resilient, fitting, full) are correct since those are in `[project.optional-dependencies]`.

---

### Medium Severity

---

**Finding M-1: README Development Setup uses `uv sync` instead of `uv sync --dev`**

- **Severity:** Medium
- **File:** `/home/aurelien/git/aria/README.md` (line 294)
- **Finding:** The "Development Setup" section shows `uv sync` without the `--dev` flag. This installs runtime dependencies but not dev tools (pytest, mypy, ruff, pre-commit). The next line `uv run pytest` would fail because pytest is not installed.
- **Impact:** A contributor following the README development instructions hits an immediate failure on `uv run pytest`.
- **Fix:** Change `uv sync` to `uv sync --dev` in the Development Setup section. This is consistent with CLAUDE.md's instruction ("Use `uv sync --dev` to install them").

---

**Finding M-2: CONTRIBUTING.md example file names don't match actual pilot directory structure**

- **Severity:** Medium
- **File:** `/home/aurelien/git/aria/CONTRIBUTING.md` (lines 42-44)
- **Finding:** CONTRIBUTING.md tells contributors to create example configs with files named `pilot_profile.md`, `operational_profile.md`, and `ship_status.md`. These match the example directories but diverge from the actual pilot directory naming convention used by `aria-init`, which creates `profile.md`, `operations.md`, and `ships.md`. A contributor following CONTRIBUTING.md would create examples with different filenames than what `aria-init` generates.
- **Impact:** Confusion when a new user copies an example to their pilot directory -- the files won't be found by ARIA's session initialization, which looks for `profile.md` (as documented in CLAUDE.md).
- **Fix:** Add a note to CONTRIBUTING.md clarifying the naming difference: example files use descriptive names (`pilot_profile.md`) for readability, while the actual pilot directory uses shorter names (`profile.md`). Alternatively, standardize the example filenames to match. Optionally, update the "Using Examples" section in `examples/README.md` (lines 96-102) to include a rename step.

---

**Finding M-3: Troubleshooting content duplicated in four locations**

- **Severity:** Medium
- **Files:** `/home/aurelien/git/aria/README.md` (lines 305-345), `/home/aurelien/git/aria/docs/FIRST_RUN.md` (lines 249-285), `/home/aurelien/git/aria/docs/TROUBLESHOOTING.md`, `/home/aurelien/git/aria/docs/FAQ.md` (lines 95-131)
- **Finding:** The same troubleshooting entries appear in four files: "Permission denied" fix, "Boot sequence doesn't appear" fix, "ESI token expired" fix, "Game data seeding failed" fix. Each copy is slightly different in wording and detail level.
- **Impact:** When a fix changes, four files need updating. Drift between copies causes confusion (e.g., one mentions `--force` flag, another doesn't). A user who finds an outdated copy in one place may miss the correct fix in another.
- **Fix:** Make TROUBLESHOOTING.md the single source of truth. In README.md and FIRST_RUN.md, keep only the top 2-3 most common issues and link to TROUBLESHOOTING.md for the full list: "For more solutions, see [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)."

---

**Finding M-4: DEPLOYMENT.md documents environment variables that don't exist in code**

- **Severity:** Medium
- **File:** `/home/aurelien/git/aria/docs/DEPLOYMENT.md` (lines 192-197)
- **Finding:** The "Environment Variables" table lists `ARIA_CONFIG_DIR` ("Override config directory") and `ESI_CLIENT_ID` ("Custom ESI application"), but grep finds no references to either variable in `src/aria_esi/`. The `.env.example` file also doesn't reference them. These appear to be aspirational or removed features documented as if they exist.
- **Impact:** A user trying to customize their config directory or ESI client ID via environment variables would find that nothing happens, with no error or explanation.
- **Fix:** Either implement the environment variable support or remove the entries from the table. If planned for future implementation, mark them as "(planned)" or move to a roadmap section.

---

**Finding M-5: Model name `claude-sonnet-4-5-20241022` appears incorrect**

- **Severity:** Medium
- **Files:** `/home/aurelien/git/aria/docs/MIGRATION_MULTI_LLM.md` (lines 11, 17, 125, 171), `/home/aurelien/git/aria/src/aria_esi/services/redisq/notifications/config.py` (lines 31, 48)
- **Finding:** The model ID `claude-sonnet-4-5-20241022` does not follow Anthropic's naming convention. The correct format would be `claude-3-5-sonnet-20241022` or one of the newer model IDs. This appears in both documentation and code.
- **Impact:** If users specify this model explicitly in notification profiles, API calls would fail with an invalid model error. The default config in `config.py` would also cause failures when commentary is enabled.
- **Fix:** Verify the intended model against Anthropic's current model list and update both the code default and documentation references. As of this review, valid model IDs include `claude-sonnet-4-5-20250514` or the older `claude-3-5-sonnet-20241022`.

---

**Finding M-6: No documentation for upgrading between versions**

- **Severity:** Medium
- **File:** `/home/aurelien/git/aria/docs/DEPLOYMENT.md` (lines 136-147)
- **Finding:** The "Upgrading" section says `git pull && uv sync` and mentions re-seeding after major updates, but there is no changelog, migration guide index, or versioning scheme documentation. The only migration doc is `MIGRATION_MULTI_LLM.md` for a specific feature. Users have no way to know what changed or whether they need to take action after pulling updates.
- **Impact:** Users may miss breaking changes, new required setup steps, or deprecated features. The `aria-init` version is stuck at 1.0.0 while `pyproject.toml` says 2.0.0, further obscuring version state.
- **Fix:** Create a `CHANGELOG.md` or add a "What's New" section to the docs index. At minimum, add a note in DEPLOYMENT.md pointing users to `git log --oneline` or GitHub releases for changes. Sync the version in `aria-init` with `pyproject.toml`.

---

**Finding M-7: `.env.example` documents `ANTHROPIC_API_KEY` as needed for Discord commentary but README implies no API keys are needed**

- **Severity:** Medium
- **Files:** `/home/aurelien/git/aria/.env.example` (lines 14-15), `/home/aurelien/git/aria/README.md` (lines 66-72)
- **Finding:** The README "Requirements" section lists Claude Code with an Anthropic API plan but doesn't mention needing an API key in `.env`. The `.env.example` documents `ANTHROPIC_API_KEY` as being for "LLM-generated commentary in Discord notifications" -- a feature most new users won't use initially. However, the DevContainer passes `ANTHROPIC_API_KEY` from the host environment (devcontainer.json line 41), suggesting it may be needed for Claude Code itself. The relationship between the Claude Code API key and the `.env` API key is unclear.
- **Impact:** New users may be confused about whether they need a `.env` file. The answer is "no, not for basic usage" but this isn't stated explicitly.
- **Fix:** Add a brief note in FIRST_RUN.md or the README Quick Start: "No `.env` file is needed for basic usage. The `.env.example` template is only needed for Discord notifications and other optional features. Your Anthropic API key for Claude Code is configured separately through Claude Code's own setup."

---

### Low Severity

---

**Finding L-1: `aria-init` version is 1.0.0, project version is 2.0.0**

- **Severity:** Low
- **File:** `/home/aurelien/git/aria/aria-init` (line 20)
- **Finding:** The `aria-init` script declares `VERSION="1.0.0"` while `pyproject.toml` declares `version = "2.0.0"`. The `--version` flag of `aria-init` reports the stale version.
- **Impact:** Minor confusion for users who check versions. Signals that the init script may be out of date.
- **Fix:** Either sync versions or remove the version from `aria-init` (it's a standalone script, not a versioned package). If keeping it, read the version from `pyproject.toml` dynamically.

---

**Finding L-2: FEATURES.md says "7 categories" in footer but feature tables show 5 section headings**

- **Severity:** Low
- **File:** `/home/aurelien/git/aria/docs/FEATURES.md` (line 115)
- **Finding:** The footer states "48 commands across 7 categories" but the page has 5 sections: Combat & Tactical, Market & Finance, Industry & Operations, Identity & Status, Pirate-Exclusive. COMMANDS.md shows 5 categories as well (with "System" as a 5th instead of Pirate-Exclusive). The count "7" may include subcategories or be stale.
- **Impact:** Minor inconsistency that undermines trust in accuracy.
- **Fix:** Update the footer to match the actual section count, or add the missing category sections.

---

**Finding L-3: `docs/README.md` link to `DEPLOYMENT.md#option-a-devcontainer-zero-host-setup` may break**

- **Severity:** Low
- **File:** `/home/aurelien/git/aria/docs/README.md` (line 18)
- **Finding:** The docs index links to a specific heading anchor in DEPLOYMENT.md. Heading anchors are fragile -- renaming the heading breaks the link with no warning. The target heading currently exists and works.
- **Impact:** Future heading edits would silently break this link.
- **Fix:** Add a comment near the DEPLOYMENT.md heading noting it's linked from the docs index, or change the link to point to the file without an anchor.

---

**Finding L-4: No explicit mention of disk space requirements**

- **Severity:** Low
- **File:** `/home/aurelien/git/aria/README.md`, `/home/aurelien/git/aria/docs/FIRST_RUN.md`
- **Finding:** The docs mention "~100MB of game data" for seeding but don't state total disk space requirements (repo + venv + game data + caches). A rough estimate would be 500MB-1GB.
- **Impact:** Users on constrained environments (small VMs, CI runners) may run out of space during setup with no prior warning.
- **Fix:** Add a disk space estimate to the Prerequisites section: "Approximately 500MB-1GB disk space (repository, Python environment, and game data caches)."

---

**Finding L-5: DevContainer ANTHROPIC_API_KEY passthrough has no fallback guidance**

- **Severity:** Low
- **File:** `/home/aurelien/git/aria/.devcontainer/devcontainer.json` (line 41), `/home/aurelien/git/aria/docs/DEPLOYMENT.md` (line 24)
- **Finding:** The DevContainer passes `ANTHROPIC_API_KEY` from the host via `${localEnv:ANTHROPIC_API_KEY}`. DEPLOYMENT.md notes to "Set your `ANTHROPIC_API_KEY` environment variable on the host before opening the container, or configure it inside the container terminal." However, there's no guidance on *how* to configure it inside the container, and if the host variable is unset, Claude Code will fail with no obvious connection to the missing variable.
- **Impact:** DevContainer users who don't have the key set on their host will get a Claude Code authentication error without clear guidance.
- **Fix:** Add a sentence: "To set the key inside the container, run `export ANTHROPIC_API_KEY=sk-ant-...` in the terminal, or add it to `/home/aria/.bashrc` for persistence across terminal sessions."

---

**Finding L-6: CLI error output uses JSON to stdout, not human-readable to stderr**

- **Severity:** Low
- **File:** `/home/aurelien/git/aria/src/aria_esi/__main__.py` (lines 21-30)
- **Finding:** The `output_error` function prints JSON to stdout for all errors. While this is correct for machine consumption (scripts parsing output), it's confusing for interactive users who see `{"error": "command_error", "message": "No credentials found"}` instead of a plain error message.
- **Impact:** Interactive users get unfriendly error output. The JSON format is appropriate for programmatic use but not for the "try it out" experience.
- **Fix:** Consider detecting if stdout is a TTY (`sys.stdout.isatty()`) and printing a human-friendly message to stderr in that case, while keeping JSON output for piped/scripted usage. Low priority since most interactive use is through Claude Code, not the CLI directly.

---

### Info

---

**Finding I-1: Documentation freshness audit process exists and is well-designed**

- **Severity:** Info
- **File:** `/home/aurelien/git/aria/dev/docs/DOC_FRESHNESS.md`
- **Finding:** The project has a documented quarterly audit process with specific checks (broken links, COMMANDS.md freshness, skill index consistency, stale terminology, command count, reference file spot-check). This is above average for documentation maintenance.
- **Impact:** Positive -- reduces documentation drift over time.
- **Fix:** None needed. Consider automating more of these checks in CI.

---

**Finding I-2: Example configurations are comprehensive and well-structured**

- **Severity:** Info
- **File:** `/home/aurelien/git/aria/examples/README.md`
- **Finding:** Four faction-specific examples cover distinct playstyles (self-sufficient, mission-runner, explorer, industrialist) with 6 files each. The README explains each example's philosophy and file purposes. This is excellent scaffolding for new users.
- **Impact:** Positive -- users can see complete working configurations.
- **Fix:** None needed. Future additions (nullsec PvP, wormhole) would round out coverage.

---

**Finding I-3: Security documentation is thorough for a personal tool**

- **Severity:** Info
- **Files:** `/home/aurelien/git/aria/SECURITY.md`, `/home/aurelien/git/aria/dev/reviews/SECURITY_000.md`
- **Finding:** The project has a security policy, vulnerability reporting process, threat model, and completed security review with mitigation status. Path validation, data integrity checks, safe serialization, and prompt injection defenses are documented and implemented. This is unusually thorough for a personal EVE Online tool.
- **Impact:** Positive -- builds trust and demonstrates security awareness.
- **Fix:** None needed.

---

**Finding I-4: The TLDR.md page is an excellent pattern**

- **Severity:** Info
- **File:** `/home/aurelien/git/aria/docs/TLDR.md`
- **Finding:** A single-page distillation of the entire project: install, configure, run, commands, roleplay, quick reference. Inspired by tldr-pages. This is an excellent complement to the detailed docs.
- **Impact:** Positive -- gives returning users a quick refresher without re-reading FIRST_RUN.md.
- **Fix:** None needed.

---

## 6. Actionable Recommendations (Priority Ranked)

### Priority 1 -- Fix Before Next Release

| # | Finding | Effort | Impact |
|---|---------|--------|--------|
| 1 | H-2: Fix `--extra dev` -> `--dev` in DEPLOYMENT.md | 1 min | Developers can't install test tools |
| 2 | M-1: Fix `uv sync` -> `uv sync --dev` in README dev section | 1 min | Contributors hit immediate failure |
| 3 | H-1: Reconcile `.mcp.json` with DEPLOYMENT.md | 10 min | Prevents MCP misconfiguration |
| 4 | M-5: Verify and fix model name in code and docs | 10 min | Discord commentary feature would fail |

### Priority 2 -- Fix Soon

| # | Finding | Effort | Impact |
|---|---------|--------|--------|
| 5 | M-2: Clarify example vs actual pilot file naming | 15 min | Reduce contributor confusion |
| 6 | M-4: Remove or implement phantom env variables | 10 min | Prevent user frustration |
| 7 | M-7: Document that .env is not needed for basic usage | 5 min | Clearer first-run experience |
| 8 | L-1: Sync aria-init version with pyproject.toml | 1 min | Consistency |

### Priority 3 -- Improve When Convenient

| # | Finding | Effort | Impact |
|---|---------|--------|--------|
| 9 | M-3: Consolidate troubleshooting to single source | 30 min | Reduce maintenance burden |
| 10 | M-6: Create CHANGELOG.md or version notes | 1 hr | Help upgrading users |
| 11 | L-2: Fix category count in FEATURES.md | 1 min | Accuracy |
| 12 | L-4: Add disk space estimate to prerequisites | 1 min | Prevent surprise on constrained systems |
| 13 | L-5: Add DevContainer API key fallback guidance | 5 min | Better container onboarding |
| 14 | L-6: Add TTY detection for human-friendly CLI errors | 30 min | Better interactive experience |

---

## 7. Summary Scorecard

| Dimension | Score | Notes |
|-----------|-------|-------|
| **README Quality** | 9/10 | Clear value prop, quick start, examples, troubleshooting. Minor dev setup issue. |
| **First-Run Experience** | 9/10 | `aria-init` wizard is polished. Three commands to working state. |
| **Documentation Architecture** | 8/10 | Good two-tier split, proper indexing. Some duplication. |
| **Setup Completeness** | 8/10 | Thorough but has `--extra dev` error and phantom env vars. |
| **Error Messages** | 8/10 | `aria-init` is excellent. CLI could be friendlier interactively. |
| **Documentation Freshness** | 7/10 | Freshness audit process exists but a few stale items remain. |
| **Discoverability** | 9/10 | Multiple entry points, persona-based routing, TLDR page. |

**Overall: 8.3/10** -- A well-documented project with strong onboarding that needs a few targeted fixes to reach excellence.
