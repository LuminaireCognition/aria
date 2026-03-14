# Skills Review Remediation — Context, Security, and Skill UX

**Status:** Implemented
**Date:** 2026-03-08
**Owner:** Architecture
**Scope:** CLAUDE.md, `.claude/rules/`, `.claude/settings.json`, `.claude/hooks/`, `.claude/skills/*/SKILL.md`
**Source:** `dev/reviews/SKILLS_SKILL_2026_03_07.md` (validated 2026-03-08)

---

## Executive Summary

The March 2026 best-practices review identified gaps between ARIA's Claude Code configuration and current platform standards. This proposal addresses the **P1 and P2 items** — changes that are low-to-medium effort with high or medium impact. Each change is independently shippable.

**What changes:**

1. CLAUDE.md drops from 215 to ~165 lines via `@`-imports and extraction to `.claude/rules/`
2. New `.claude/rules/` directory with path-scoped Python and security rules
3. Credential protection upgraded from instructional to programmatic (deny rules + `PreToolUse` hook)
4. All user-facing skills gain `argument-hint` for autocomplete
5. Read-only skills gain `allowed-tools` to prevent unintended writes
6. System/dev skills gain `disable-model-invocation: true` to reduce context budget

**What does NOT change:**

- Custom frontmatter fields (`prerequisite_files`, `data_sources`, `has_persona_overlay`, etc.) — these are ARIA-specific extensions consumed by CLAUDE.md's skill-loading protocol; migrating them is a separate, larger effort (P3)
- No `.claude/agents/` created — clear use cases exist but the ROI requires more design work (P3)
- No `context: fork` on skills — low impact until context budget is measured (P4)
- The `_index.json` registry — it's read by boot scripts, not loaded into Claude's context directly

---

## Problem Statement

Six independent gaps reduce ARIA's context efficiency, security posture, and skill UX:

| Gap | Impact |
|-----|--------|
| CLAUDE.md at 215 lines (target: ≤200) | Every extra line dilutes adherence to all instructions |
| Python rules load even in non-Python sessions | Wasted context when reviewing docs, discussing fits, or planning routes |
| Credential protection is purely instructional | CLAUDE.md says "DO NOT READ .env" but nothing enforces it |
| No `argument-hint` on any of 50+ skills | Autocomplete shows no usage hints; capsuleer guesses at syntax |
| No `allowed-tools` on read-only skills | A `/price` lookup has write access it will never need |
| All skills are model-invocable | Dev/system skills inflate the description context budget |

---

## Design

### Phase 1: CLAUDE.md Trimming and Rules Extraction

**Goal:** Reduce CLAUDE.md to ≤165 lines. Move path-scoped content to `.claude/rules/` and reference content to `@`-imported files.

#### 1a. Extract Python Execution to `.claude/rules/python.md`

The "Python Execution" section (current lines 122–144, 23 lines) applies only when working with Python files. Extract to a path-scoped rule.

**New file: `.claude/rules/python.md`**
```yaml
---
paths:
  - "src/**/*.py"
  - "tests/**/*.py"
  - ".claude/scripts/**/*.py"
  - "pyproject.toml"
  - "uv.lock"
---
```

Content: the current Python Execution section verbatim, including the `uv run` mandate, the `uv pip install` prohibition, the code block with example commands, the call-signature check instruction, and the link to `dev/docs/PYTHON_ENVIRONMENT.md`.

**CLAUDE.md change:** Replace the 23-line section with a single line:
```
Python conventions: see `.claude/rules/python.md` (loads when working with `.py` files).
```

**Savings:** ~21 lines.

#### 1b. Extract MCP Fallback Table to imported file

The "MCP Fallback Behavior" table (current lines 150–167, 18 rows) is lookup reference, not a convention Claude must always follow. Extract it.

**New file: `docs/MCP_FALLBACK.md`** — contains the table verbatim plus the "MCP tools are preferred" preamble.

**CLAUDE.md change:** Replace the table with an `@`-import:
```markdown
## Universe Navigation

@docs/MCP_FALLBACK.md
```

The `@`-import loads the content at session start identically to inline content, but keeps CLAUDE.md scannable. The "External Data Queries" subsection (lines 169–173) stays inline — it's compact and always-relevant.

**Savings:** ~16 lines from CLAUDE.md body (content still loaded via import).

#### 1c. Extract Reference Documentation table to imported file

The "Reference Documentation" table (current lines 200–215, 16 lines) is pure navigation. It helps Claude find docs but doesn't change behavior.

**New file: `docs/REFERENCE_INDEX.md`** — the table verbatim.

**CLAUDE.md change:** Replace with:
```markdown
## Reference Documentation

@docs/REFERENCE_INDEX.md
```

**Savings:** ~14 lines from CLAUDE.md body.

#### 1d. Net result

| Source | Before | After | Delta |
|--------|--------|-------|-------|
| CLAUDE.md body | 215 lines | ~164 lines | -51 |
| `.claude/rules/python.md` | — | ~25 lines | new |
| `docs/MCP_FALLBACK.md` | — | ~20 lines | new |
| `docs/REFERENCE_INDEX.md` | — | ~16 lines | new |

Always-on context cost is reduced by the Python rules (now path-scoped, ~23 lines saved in non-Python sessions). The imported files load the same content but CLAUDE.md stays well under the 200-line target with headroom for growth.

---

### Phase 2: Credential Protection — Deny Rules + Hook

**Goal:** Upgrade credential protection from instructional ("DO NOT READ") to programmatic (blocked by platform).

#### 2a. Add deny rules to `.claude/settings.json`

These rules are shared (committed to repo) and enforced by Claude Code's permission system. Deny rules take precedence over all allow rules at any level.

```json
{
  "permissions": {
    "deny": [
      "Read(.env)",
      "Read(.env.local)",
      "Read(userdata/credentials/**)"
    ]
  }
}
```

This blocks the Read tool (and tools that respect Read rules, like Grep and Glob) from accessing credential files. The CLAUDE.md "Sensitive Files" section stays as documentation but is no longer the sole enforcement layer.

#### 2b. Add `PreToolUse` hook for Bash credential protection

Deny rules block the Read tool but not `cat .env` via Bash. Add a `PreToolUse` hook to catch Bash-based credential access.

**New file: `.claude/hooks/protect-credentials.sh`**

```bash
#!/bin/bash
# Block Bash commands that read credential files
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE '\.(env|env\.local)\b|userdata/credentials/'; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Credential file access blocked by hook"}}'
  exit 0
fi

exit 0
```

**Settings change:** Add to `.claude/settings.json` alongside existing `SessionStart` hook:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/protect-credentials.sh"
          }
        ]
      }
    ]
  }
}
```

#### 2c. Defense-in-depth layering

| Layer | Mechanism | Blocks |
|-------|-----------|--------|
| CLAUDE.md instruction | "DO NOT READ" | Cooperative model behavior |
| `permissions.deny` rules | `Read(.env)`, etc. | Read, Grep, Glob on credential paths |
| `PreToolUse` hook | `protect-credentials.sh` | `cat .env`, `grep .env`, etc. via Bash |

---

### Phase 3: Skill Frontmatter — `argument-hint`

**Goal:** Add `argument-hint` to all user-facing skills that accept arguments, improving autocomplete UX.

This is a mechanical change to each skill's YAML frontmatter. No skill body content changes. The `argument-hint` field is displayed during autocomplete to show expected input format.

#### Proposed hints by skill

| Skill | `argument-hint` |
|-------|-----------------|
| `arbitrage` | `[--cargo M3] [--sort mode] [--min-profit %]` |
| `aria-review` | `<template> <target\|ALL>` |
| `assets` | `[--ships\|--type NAME\|--location NAME\|--value]` |
| `build-cost` | `<item_name> [--me LEVEL] [--runs N]` |
| `clones` | — (no arguments) |
| `contracts` | `[--type exchange\|courier\|auction]` |
| `corp` | `[status\|wallet\|assets\|blueprints\|jobs]` |
| `escape-route` | `[--from SYSTEM]` |
| `esi-query` | `<query>` |
| `exploration` | `[--system NAME\|--region NAME]` |
| `find` | `<item_name> [--near SYSTEM]` |
| `fit-budget` | `<EFT fit block>` |
| `fit-check` | `<EFT fit block>` |
| `fit-recommend` | `<hull\|role> [--budget ISK] [--tier t1\|t2]` |
| `fitting` | `<ship> [<activity>]` |
| `fittings` | `[--hull NAME]` |
| `gatecamp` | `<system\|route>` |
| `hunting-grounds` | `<system\|region> [--range N]` |
| `industry-jobs` | `[--active\|--history]` |
| `isk-compare` | — (no arguments) |
| `killmail` | `<kill_id\|URL>` |
| `killmails` | `[--losses\|--kills] [--limit N]` |
| `lp-store` | `[--corp NAME\|--item NAME]` |
| `mail` | `[--unread\|--id N]` |
| `mark-assessment` | `<pilot_name\|ship_type>` |
| `mining` | `[--days N]` |
| `mining-advisory` | `[--system NAME\|--ore NAME]` |
| `mission-brief` | `<mission_name> [--level N]` |
| `orders` | `[--buy\|--sell\|--history]` |
| `orient` | — (no arguments, uses current location) |
| `pi` | `[--planet TYPE\|--product NAME]` |
| `pilot` | `[pilot_name]` |
| `price` | `<item_name> [--region NAME\|--jita\|--amarr]` |
| `ransom-calc` | `<ship_type> [--cargo ISK] [--implants]` |
| `reactions` | `[--product NAME\|--fuel]` |
| `route` | `[<origin>] <destination> [--safe\|--shortest]` |
| `sec-status` | — (no arguments) |
| `ship-next` | `[--activity NAME]` |
| `skillplan` | `<ship\|module\|activity>` |
| `skillqueue` | — (no arguments) |
| `standings` | `[--faction NAME\|--corp NAME]` |
| `threat-assessment` | `<system> [--route <origin> <destination>]` |
| `wallet-journal` | `[--days N] [--type TYPE]` |
| `watchlist` | `[add\|remove\|list] [entity_name]` |

Skills with no meaningful arguments (`clones`, `isk-compare`, `orient`, `sec-status`, `skillqueue`, `help`, `abyssal`, `agents-research`) get no `argument-hint`.

---

### Phase 4: Skill Frontmatter — `allowed-tools`

**Goal:** Add `allowed-tools` to read-only skills to enforce least privilege. Skills that only query data should not have write access.

The `allowed-tools` field restricts which tools Claude can use while the skill is active. Only listed tools are available.

#### Classification

**Read-only skills** — query ESI/MCP/SDE, display results, never modify files:

| Skill | `allowed-tools` |
|-------|-----------------|
| `price` | `Read, Grep, Glob, mcp__aria-universe__market, mcp__aria-universe__sde` |
| `route` | `Read, Grep, Glob, mcp__aria-universe__universe` |
| `arbitrage` | `Read, Grep, Glob, mcp__aria-universe__market` |
| `threat-assessment` | `Read, Grep, Glob, mcp__aria-universe__universe, mcp__aria-universe__killmails` |
| `orient` | `Read, Grep, Glob, mcp__aria-universe__universe` |
| `escape-route` | `Read, Grep, Glob, mcp__aria-universe__universe` |
| `gatecamp` | `Read, Grep, Glob, mcp__aria-universe__universe, mcp__aria-universe__killmails` |
| `killmail` | `Read, Grep, Glob, mcp__aria-universe__killmails, mcp__aria-universe__sde` |
| `killmails` | `Read, Grep, Glob, mcp__aria-universe__killmails, mcp__aria-universe__sde, mcp__aria-universe__pilot` |
| `mark-assessment` | `Read, Grep, Glob, mcp__aria-universe__killmails, mcp__aria-universe__sde, mcp__aria-universe__universe` |
| `hunting-grounds` | `Read, Grep, Glob, mcp__aria-universe__universe, mcp__aria-universe__killmails` |
| `exploration` | `Read, Grep, Glob, mcp__aria-universe__universe, mcp__aria-universe__sde` |
| `mining-advisory` | `Read, Grep, Glob, mcp__aria-universe__market, mcp__aria-universe__sde` |
| `sec-status` | `Read, Grep, Glob, mcp__aria-universe__pilot, mcp__aria-universe__market` |
| `standings` | `Read, Grep, Glob, mcp__aria-universe__pilot, mcp__aria-universe__sde` |
| `clones` | `Read, Grep, Glob, mcp__aria-universe__pilot` |

**Read + Bash skills** — need CLI fallback when MCP is unavailable:

| Skill | `allowed-tools` |
|-------|-----------------|
| `wallet-journal` | `Read, Grep, Glob, Bash, mcp__aria-universe__pilot` |
| `orders` | `Read, Grep, Glob, Bash, mcp__aria-universe__pilot` |
| `assets` | `Read, Grep, Glob, Bash, mcp__aria-universe__pilot, mcp__aria-universe__market, mcp__aria-universe__sde, mcp__aria-universe__universe` |
| `contracts` | `Read, Grep, Glob, Bash, mcp__aria-universe__pilot` |
| `mail` | `Read, Grep, Glob, Bash, mcp__aria-universe__pilot` |
| `mining` | `Read, Grep, Glob, Bash, mcp__aria-universe__pilot` |
| `fittings` | `Read, Grep, Glob, Bash, mcp__aria-universe__pilot, mcp__aria-universe__fitting` |
| `industry-jobs` | `Read, Grep, Glob, Bash, mcp__aria-universe__pilot` |
| `lp-store` | `Read, Grep, Glob, Bash, mcp__aria-universe__pilot, mcp__aria-universe__market` |
| `agents-research` | `Read, Grep, Glob, Bash, mcp__aria-universe__pilot` |
| `pi` | `Read, Grep, Glob, Bash, mcp__aria-universe__sde` |

**Write-capable skills** — modify files or generate output that may be saved. These do NOT get `allowed-tools` restrictions:

- `fitting`, `fit-check`, `fit-budget`, `fit-recommend` — may write fit exports
- `mission-brief` — writes to mission cache
- `journal` — writes operational logs
- `watchlist` — writes watchlist files
- `first-run-setup` — creates profile files
- `aria-review` — writes review output
- `aria-status`, `help`, `pilot`, `esi-query`, `ship-next`, `skillplan`, `skillqueue`, `isk-compare`, `ransom-calc`, `build-cost`, `reactions`, `abyssal`, `corp`, `find` — either need broad tool access or are output-only (no restriction benefit)

#### Implementation note

If `allowed-tools` is too restrictive and a skill fails at runtime, the fix is simple: add the missing tool to the list. Start restrictive, loosen as needed.

---

### Phase 5: Skill Frontmatter — `disable-model-invocation`

**Goal:** Prevent system/dev skills from consuming context budget when they should only fire on explicit invocation.

When `disable-model-invocation: true` is set, the skill's description is removed from Claude's context entirely. Claude cannot auto-invoke it; only the user can trigger it via `/skill-name`.

#### Candidates

| Skill | Rationale |
|-------|-----------|
| `aria-review` | Dev/system dispatcher. Should never auto-fire on a user query. Only meaningful when explicitly invoked with a template name and target. |
| `journal` | Logging tool. Writing operational logs should be an explicit user action, not triggered by Claude interpreting a conversation as log-worthy. |
| `watchlist` | Modifies watchlist files. Should only fire on explicit `/watchlist add` or `/watchlist remove`. |
| `first-run-setup` | One-time setup. Auto-invocation is handled by CLAUDE.md's boot logic (`state.fresh_install`), not by skill description matching. Safe to hide from context. |

Skills like `aria-status` and `help` were considered but rejected — they respond to natural language queries ("status report", "what can you do") and should remain model-invocable.

---

## Implementation Plan

Each phase is independently shippable. Phases are ordered by dependency, not priority.

| Phase | Changes | Files touched | Risk |
|-------|---------|---------------|------|
| **1** | CLAUDE.md trim + rules extraction | `CLAUDE.md`, `.claude/rules/python.md`, `docs/MCP_FALLBACK.md`, `docs/REFERENCE_INDEX.md` | Low — content moves, not deleted |
| **2** | Credential deny rules + hook | `.claude/settings.json`, `.claude/hooks/protect-credentials.sh` | Low — additive security, no behavior change for compliant sessions |
| **3** | `argument-hint` on ~40 skills | `.claude/skills/*/SKILL.md` (frontmatter only) | Negligible — additive metadata, no body changes |
| **4** | `allowed-tools` on ~27 skills | `.claude/skills/*/SKILL.md` (frontmatter only) | Medium — if tool list is too narrow, skill may fail at runtime. Mitigated by testing. |
| **5** | `disable-model-invocation` on 4 skills | `.claude/skills/*/SKILL.md` (frontmatter only) | Low — only 4 skills affected, all system/dev tools |

### Testing approach

- **Phase 1:** Verify CLAUDE.md line count. Run a session, confirm `@`-imports load via `/memory`. Confirm Python rules load only when editing `.py` files.
- **Phase 2:** Attempt to `Read(.env)` and `cat .env` — both should be blocked. Verify normal Read/Bash operations are unaffected.
- **Phase 3:** Invoke `/price` and confirm autocomplete shows `<item_name> [--region NAME|--jita|--amarr]`. Spot-check 5 skills.
- **Phase 4:** Invoke `/price Gold`, `/route Jita Amarr`, `/threat-assessment Rancer` — confirm they complete successfully with restricted tools. Invoke a write-capable skill (`/fitting`) — confirm it still has full tool access.
- **Phase 5:** Confirm `/aria-review` works when explicitly invoked. Confirm it does NOT appear when asking Claude "review my code" in a general conversation.

---

## Out of Scope (Future Work)

| Item | Review Priority | Why deferred |
|------|-----------------|--------------|
| Custom agents (`.claude/agents/`) | P3 | Medium effort, needs design work on agent scope, memory, and MCP access patterns |
| Custom frontmatter field migration | P3 | Medium effort, tightly coupled to CLAUDE.md skill-loading protocol and `_index.json` |
| `PreCompact` hook for boot state | P3 | Low impact — CLAUDE.md survives compaction; only boot hook JSON is at risk |
| `context: fork` on output-heavy skills | P4 | Low impact until context budget pressure is measured via `/context` |
| Security rules extraction to path-scoped rule | P3 | The Untrusted Data Handling section (~48 lines) could be scoped to `personas/**` and `userdata/**`, but it's security-critical content where always-on loading is the safer default |

---

*Proposal responds to findings in `dev/reviews/SKILLS_SKILL_2026_03_07.md` (validated 2026-03-08).*
