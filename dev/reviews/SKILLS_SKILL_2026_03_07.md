# ARIA Best Practices Review — 2026-03-07

Review of `~/git/aria/` against Claude Code best practices documented in `~/git/SKILLSSKILLS/docs/`.

**Scope:** CLAUDE.md, skills, agents, hooks, rules, permissions, memory, context management.

---

## Executive Summary

ARIA is a mature, well-engineered Claude Code extension with strong security practices and a sophisticated boot pipeline. However, it predates several Claude Code extension features and has diverged from the current standard in key areas. The primary gaps are: **skills use non-standard frontmatter fields** that Claude Code does not recognize, **no `.claude/rules/`** for path-scoped instructions, **no custom agents** despite clear use cases, **no persistent memory**, and **CLAUDE.md exceeds the recommended size**. Addressing these would improve skill discovery, context efficiency, and maintainability.

---

## 1. CLAUDE.md — Over Budget, No Imports

**Current state:** 215 lines, 12,259 bytes, 17 headers. Single monolithic file with no `@path` imports.

**Best practice:** Target under 200 lines. Use `@path/to/file` imports for reference material. Keep CLAUDE.md focused on always-on conventions; move reference docs to skills or imported files.

### Findings

| Issue | Severity | Detail |
|-------|----------|--------|
| Line count exceeds 200 | Medium | 215 lines — 15 lines over target. Every extra line dilutes adherence to all instructions. |
| MCP Fallback table is reference, not convention | Medium | The 16-row "MCP Fallback Behavior" table (§ Universe Navigation) is lookup reference that should be a skill prerequisite or `@`-imported file, not always-on context. |
| Reference Documentation index at bottom | Low | The final table is pure navigation. Could be an imported file or moved to a skill. |
| No `@path` imports used | Medium | The file could be split: core directives in CLAUDE.md, reference tables imported via `@path`. |

### Recommendations

1. **Extract the MCP Fallback table** to a reference file (e.g., `docs/MCP_FALLBACK.md`) and `@`-import it or make it a skill prerequisite.
2. **Extract the Reference Documentation table** to an imported file.
3. **Target ≤180 lines** for the core CLAUDE.md to leave headroom.
4. **Use `@` imports** for extracted sections: `@docs/MCP_FALLBACK.md` keeps content accessible but out of the main body.

---

## 2. Skills — Non-Standard Frontmatter Fields

**Current state:** 50+ skills, all with YAML frontmatter. Skills use a custom `_index.json` registry (55 KB) and custom frontmatter fields.

**Best practice:** Skills use a defined set of frontmatter fields recognized by Claude Code: `name`, `description`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `context`, `agent`, `hooks`.

### Findings

| Issue | Severity | Detail |
|-------|----------|--------|
| Non-standard frontmatter fields | High | `triggers`, `category`, `requires_pilot`, `esi_scopes`, `data_sources`, `prerequisite_files`, `has_persona_overlay`, `external_sources` — none of these are recognized by Claude Code's skill system. They are only consumed by the custom `_index.json` registry and CLAUDE.md instructions. |
| Missing `description` best practices | Medium | Skill descriptions are present but terse (e.g., "Clone and implant status tracking"). Best practice: descriptions should tell Claude *when* to use the skill so it can auto-invoke correctly. |
| Missing `argument-hint` | Medium | No skills declare `argument-hint`, so autocomplete shows no usage hint. E.g., `arbitrage` should have `argument-hint: "[item] [from-region] [to-region]"`. |
| Missing `user-invocable` | Low | All skills default to user+model invocable. Skills like `aria-review` (system/dev tool) might benefit from `disable-model-invocation: true` to prevent unintended auto-firing. |
| Missing `allowed-tools` | Medium | No skills restrict their tool access. Skills that only read data (e.g., `arbitrage`, `price`, `route`) should declare `allowed-tools: Read, Grep, Glob, Bash` to prevent unintended writes. |
| Missing `context: fork` | Medium | Verbose skills that generate large outputs (e.g., `assets` at 180 lines, `fit-check` at 192 lines) could benefit from `context: fork` to run in a subagent and protect the main context window. |
| Custom `_index.json` registry | Medium | The 55 KB `_index.json` is a custom discovery mechanism. Claude Code has its own skill discovery via `description` fields. The registry duplicates metadata already in SKILL.md frontmatter and adds context cost. |
| No skill hooks | Low | No skills use frontmatter `hooks` for lifecycle automation (e.g., validating prerequisites before execution via a `PreToolUse` hook). |

### Recommendations

1. **Audit all custom frontmatter fields.** Determine which can be:
   - Migrated to standard fields (e.g., `triggers` → improve `description` for auto-invocation)
   - Moved into the skill body as structured comments (e.g., `esi_scopes`, `data_sources`)
   - Kept as custom fields but documented as ARIA-specific extensions
2. **Add `argument-hint`** to all user-facing skills for autocomplete clarity.
3. **Add `allowed-tools`** to read-only skills to enforce least privilege.
4. **Add `context: fork`** to output-heavy skills to prevent context bloat.
5. **Evaluate `_index.json` necessity.** If it's only used by custom boot/preflight scripts, keep it but document that it's a project-specific extension, not a Claude Code standard.
6. **Add `disable-model-invocation: true`** to development/system skills (`aria-review`) that should only fire when explicitly requested.

---

## 3. Agents — None Defined

**Current state:** No `.claude/agents/` directory. A `.claude/AGENTS.md` file exists (23 lines) but is a free-form instruction file, not a Claude Code agent definition.

**Best practice:** Define custom agents in `.claude/agents/<name>.md` with YAML frontmatter specifying `name`, `description`, `tools`, `model`, `permissionMode`, etc.

### Findings

| Issue | Severity | Detail |
|-------|----------|--------|
| No custom agents despite clear use cases | High | The project has isolation-worthy workflows: ESI data sync, security audits, exercise running, skill reviews. These would benefit from dedicated agents with scoped tools and persistent memory. |
| AGENTS.md is not an agent definition | Medium | `.claude/AGENTS.md` contains instructions for *any* subagent but uses no frontmatter — Claude Code ignores it as an agent definition. Its content should be in CLAUDE.md or rules. |

### Recommendations

1. **Create `.claude/agents/` directory** with at least:
   - `esi-researcher.md` — Read-only agent for ESI data queries, scoped to `Read, Grep, Glob, Bash`, with `permissionMode: plan` or explicit tool deny for `Write, Edit`.
   - `skill-reviewer.md` — Agent for running `aria-review` exercises with `context: fork` and `memory: project`.
   - `security-auditor.md` — Read-only agent for security validation tasks.
2. **Migrate AGENTS.md content** into CLAUDE.md or `.claude/rules/python.md` (the `uv run` instruction belongs with Python conventions).

---

## 4. Rules — None Defined

**Current state:** No `.claude/rules/` directory exists.

**Best practice:** Use `.claude/rules/` for path-scoped instructions. Rules load only when Claude works with matching files, reducing always-on context cost.

### Findings

| Issue | Severity | Detail |
|-------|----------|--------|
| Python conventions in CLAUDE.md apply globally | Medium | The "Python Execution" section (always use `uv run`, never `uv pip install`) is in CLAUDE.md and loads every session, even when not working with Python. Should be a path-scoped rule. |
| Security guardrails in CLAUDE.md apply globally | Low | Untrusted data handling rules are always loaded. Could be scoped to `personas/**` and `userdata/**` paths. |
| No file-type specific conventions | Medium | No rules for `.py` files (import ordering, type annotation style), `.md` files (formatting), or `.json` files (schema validation). |

### Recommendations

1. **Create `.claude/rules/` directory** with:
   - `python.md` — `paths: ["src/**/*.py", "tests/**/*.py", ".claude/scripts/*.py"]` — Python execution rules, `uv run` mandate, test conventions.
   - `personas.md` — `paths: ["personas/**", "userdata/**"]` — Untrusted data handling, delimiter rules, injection prevention.
   - `skills.md` — `paths: [".claude/skills/**"]` — Skill authoring conventions, frontmatter requirements.
2. **Remove migrated content from CLAUDE.md** to bring it under 200 lines.

---

## 5. Hooks — Minimal Usage

**Current state:** Single `SessionStart` hook running `aria-boot.sh`. No other hook events used.

**Best practice:** Use hooks for deterministic automation: auto-formatting after edits, file protection, context re-injection after compaction, audit logging.

### Findings

| Issue | Severity | Detail |
|-------|----------|--------|
| No `PreToolUse` hooks | Medium | CLAUDE.md documents sensitive files (.env, credentials) as "DO NOT READ" but enforcement is purely instructional. A `PreToolUse` hook on `Read` could programmatically block access to credential files. |
| No `PreCompact` hook | Medium | After context compaction, critical persona and pilot context may be lost. A `PreCompact` hook could re-inject essential state. |
| No `PostToolUse` hooks | Low | No auto-formatting after file edits. If the project enforces `ruff` formatting, a `PostToolUse` hook on `Edit\|Write` could auto-run `ruff format`. |
| No `UserPromptSubmit` hooks | Low | Could inject pilot context or session state reminders into every prompt. |

### Recommendations

1. **Add `PreToolUse` hook for credential protection:**
   ```json
   {
     "hooks": {
       "PreToolUse": [{
         "matcher": "Read",
         "hooks": [{
           "type": "command",
           "command": ".claude/hooks/protect-credentials.sh"
         }]
       }]
     }
   }
   ```
   Script checks if the read target matches `userdata/credentials/*`, `.env`, or `.env.local` and returns `{"permissionDecision": "deny"}`.

2. **Add `PreCompact` hook** to re-inject active pilot identity and persona into context.

3. **Add `PostToolUse` hook for Python formatting** on `Edit|Write` targeting `*.py` files — run `ruff format` and `ruff check --fix`.

---

## 6. Permissions — No Deny Rules

**Current state:** `settings.local.json` has 59 allow rules. No deny rules anywhere. No managed settings.

**Best practice:** Start restrictive (deny, then ask). Use deny rules to block risky operations. Deny takes precedence at any level.

### Findings

| Issue | Severity | Detail |
|-------|----------|--------|
| No deny rules | Medium | No explicit denials for dangerous operations. Sensitive file protection relies entirely on CLAUDE.md instructions. |
| Broad `Bash(cat *)` allow | Low | Allows `cat` with any argument — could read sensitive files via Bash even if Read is blocked. |
| No WebFetch domain restrictions in shared settings | Low | Domain restrictions are in `settings.local.json` (gitignored), not in `settings.json` (shared). Other contributors won't inherit the restrictions. |

### Recommendations

1. **Add deny rules** to `settings.json` (shared):
   ```json
   {
     "permissions": {
       "deny": [
         "Read(userdata/credentials/**)",
         "Read(.env)",
         "Read(.env.local)",
         "Bash(rm -rf *)",
         "Bash(* --force *)"
       ]
     }
   }
   ```
2. **Move shared permission patterns** from `settings.local.json` to `settings.json` where they represent project conventions (MCP server permissions, safe Bash commands).
3. **Tighten `Bash(cat *)` to specific safe patterns** or remove it (prefer the Read tool).

---

## 7. Memory — Not Configured

**Current state:** No `.claude/memory/` directory. No `MEMORY.md`. No persistent learning across sessions.

**Best practice:** Enable auto memory for persistent learnings. Create `MEMORY.md` (loaded every session, keep under 200 lines). Use topic files for detailed notes.

### Findings

| Issue | Severity | Detail |
|-------|----------|--------|
| No persistent memory | Medium | Each session starts from scratch regarding learned patterns, debugging insights, and pilot-specific context. |
| Boot hook partially compensates | Low | The `SessionStart` hook injects pilot/persona context, partially compensating for lack of memory. But session-learned patterns (e.g., "this pilot always asks about Jita prices") are lost. |

### Recommendations

1. **Enable auto memory** (toggle with `/memory` command or environment variable).
2. **Seed `MEMORY.md`** with stable project patterns: build commands, common debugging steps, architectural decisions.
3. **Consider `memory: project`** on future custom agents for shared learnings.

---

## 8. Context Efficiency — Opportunities

**Current state:** CLAUDE.md (215 lines) + `_index.json` (55 KB) + skill descriptions loaded at session start.

**Best practice:** Minimize always-on context. Use skills for on-demand content. Use `disable-model-invocation: true` for side-effect skills. Keep descriptions loaded at start, full content loaded on use.

### Findings

| Issue | Severity | Detail |
|-------|----------|--------|
| `_index.json` at 55 KB is large | Medium | If loaded at session start, this consumes significant context. Standard Claude Code skill discovery uses description fields in individual SKILL.md files, not a centralized index. |
| Boot hook JSON output size unknown | Low | The `SessionStart` hook outputs JSON context — if this is large, it adds to first-turn context cost. |
| No `disable-model-invocation` on any skill | Low | All 50+ skills are candidates for auto-invocation, increasing the description context loaded at start. Dev/system skills should opt out. |

### Recommendations

1. **Measure total context cost** — run `/context` to see skill description budget usage.
2. **Set `disable-model-invocation: true`** on system/dev skills: `aria-review`, `first-run-setup`, `aria-status` (if rarely auto-triggered).
3. **Evaluate `_index.json` loading path** — if it's read by boot scripts (not Claude), it has no context cost. If Claude reads it, consider trimming or eliminating it.

---

## 9. Positive Findings — What ARIA Does Well

These areas already align with or exceed best practices:

| Area | Assessment |
|------|------------|
| **Security architecture** | Excellent. Multi-layer defense: path validation, data delimiters, injection prevention, artifact integrity verification, credential protection. Exceeds what most projects implement. |
| **Boot pipeline** | Excellent. Modular, parallel, graceful degradation. Well-structured SessionStart hook with sub-modules. |
| **Skill content quality** | Strong. Hallucination guards, field-to-source mapping, data provenance rules, volatility classification. |
| **Sensitive file handling** | Good. `.env`, credentials documented as off-limits. (Would be stronger with programmatic enforcement via hooks.) |
| **Python execution standards** | Good. Clear `uv run` mandate, lockfile discipline documented. |
| **MCP integration** | Good. Clean `.mcp.json`, fallback behavior documented. |
| **Persona system** | Strong. Compiled artifacts, overlay system, opt-in roleplay. Sophisticated but well-documented. |
| **Testing infrastructure** | Excellent. Multi-tier tests, coverage thresholds, CI/CD, benchmark suite. |
| **Project documentation** | Extensive. ADRs, proposals, STPs, dev docs, contributing guides. |

---

## Priority Action Items

Ranked by impact and effort:

| Priority | Action | Effort | Impact |
|----------|--------|--------|--------|
| **P1** | Create `.claude/rules/` with path-scoped Python and persona rules; trim CLAUDE.md to ≤180 lines | Medium | High — reduces always-on context, improves instruction adherence |
| **P1** | Add `argument-hint` to all user-facing skills | Low | Medium — immediate UX improvement for autocomplete |
| **P2** | Add `PreToolUse` hook to enforce credential file protection | Low | High — upgrades security from instructional to programmatic |
| **P2** | Add `allowed-tools` to read-only skills | Low | Medium — enforces least privilege |
| **P2** | Add `disable-model-invocation: true` to system/dev skills | Low | Medium — reduces context budget usage |
| **P3** | Create `.claude/agents/` with esi-researcher and skill-reviewer agents | Medium | Medium — enables context isolation for data-heavy workflows |
| **P3** | Evaluate migrating custom frontmatter fields to standard fields or skill body | Medium | Medium — improves compatibility with Claude Code's built-in discovery |
| **P3** | Add `PreCompact` hook for context re-injection | Low | Medium — preserves critical state across compaction |
| **P4** | Enable persistent memory | Low | Low-Medium — incremental benefit given boot hook compensation |
| **P4** | Add `context: fork` to output-heavy skills | Low | Low — prevents context bloat for specific skills |

---

*Review performed against Claude Code best practices documented in `~/git/SKILLSSKILLS/docs/` (retrieved 2026-03-07).*
