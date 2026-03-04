# Skill Loading: Protocol-Level Path Resolution

**Status:** Draft
**Date:** 2026-03-04
**Owner:** Architecture
**Scope:** `personas/_shared/skill-loading.md`, `CLAUDE.md`, `dev/docs/CONTRIBUTING_SKILLS.md`, affected `SKILL.md` files
**Related:** `dev/proposals/PREREQ_PATH_DISAMBIGUATION.md`

---

## Executive Summary

The current approach to path resolution for skill prerequisite files patches each skill individually with a per-read parenthetical annotation and a failure-recovery instruction. This is the right instinct applied at the wrong level.

The loading protocol (`skill-loading.md` §1.5 and `CLAUDE.md` §Skill Loading) defines the mandatory read gate but says nothing about how to resolve paths. That is the gap. A single sentence added to the loading protocol closes it project-wide, making per-skill annotations optional defense-in-depth rather than mandatory per-skill maintenance.

**Core thesis:** Path resolution is a loading-protocol concern, not a per-skill concern. A rule defined once in the protocol is more reliable than the same rule repeated across every skill body.

---

## Problem Statement

### Root cause

When the model reads `.claude/skills/{name}/SKILL.md` and encounters a path like `reference/mechanics/npc_damage_types.md`, it must decide what that path is relative to. Two interpretations are possible:

- **Project root** (correct): `/project-root/reference/mechanics/npc_damage_types.md`
- **Skill directory** (wrong): `/project-root/.claude/skills/{name}/reference/mechanics/npc_damage_types.md`

The loading protocol says "read ALL listed files" but does not specify which interpretation to use. Without an authoritative rule, the model may choose the wrong one, fail silently, and fall back to training data. This is the root cause of the `exploration` confabulation confirmed in exercise run 20260303-232824.

### Current mitigation and its limits

The `PREREQ_PATH_DISAMBIGUATION` campaign added two elements to each skill:

1. A parenthetical on every read instruction: `(project-root-relative path, not skill-directory path)`
2. A failure-recovery instruction: `If a read fails, do not output a blanket failure — check that the path is resolved from the project root (not the skill directory) and retry.`

This works, but has structural problems:

| Problem | Impact |
|---------|--------|
| Convention lives in skill bodies, not the protocol | New skills can omit it without violating any documented standard |
| Every skill author must know and apply the pattern | Knowledge doesn't transfer automatically |
| Complex skills need many annotations (`mission-brief`: ~12 inline references) | Maintenance surface grows with skill complexity |
| Failure-recovery is a correction mechanism, not a prevention mechanism | The model must first resolve wrongly and fail before the instruction triggers |
| Per-skill patching is ongoing work | Four skills remain unpatched as of 2026-03-04 |

The failure-recovery instruction is doing real work — it gives the model a path to correct itself. But that path should not be necessary if the resolution rule is established upstream.

---

## Proposed Fix

### 1. Add path resolution rule to the loading protocol

In `skill-loading.md` §1.5, after "read ALL listed files NOW before producing any output", add:

> **Path resolution:** All paths in `prerequisite_files` are project-root-relative. When reading, prepend the working directory — never the skill's own directory (`.claude/skills/{name}/`). A path like `reference/mechanics/ore_database.md` resolves to `{project-root}/reference/mechanics/ore_database.md`, not `.claude/skills/mining-advisory/reference/mechanics/ore_database.md`.

Mirror the rule (condensed) in `CLAUDE.md` §Skill Loading step 3.

### 2. Simplify per-skill failure instructions

Once the global rule is in place, the failure instruction in individual skills can simplify from the retry-from-project-root pattern to:

> If a read fails, report the exact path that failed — do not substitute training data.

This removes the implicit "you may have resolved it wrong" correction logic, since the upstream rule prevents the wrong resolution in the first place.

### 3. Update CONTRIBUTING_SKILLS.md

Replace the §Prerequisite File Path Disambiguation section with:

- Reference the protocol-level rule as the canonical definition
- Note that per-skill failure instructions are still encouraged as inline reminders for authors
- Remove the requirement for per-read parentheticals (they become optional best practice)

---

## What Changes

| File | Change |
|------|--------|
| `personas/_shared/skill-loading.md` | Add path resolution rule to §1.5 |
| `CLAUDE.md` | Add one sentence to Skill Loading step 3 |
| `dev/docs/CONTRIBUTING_SKILLS.md` | Update §Prerequisite File Path Disambiguation |
| `PREREQ_PATH_DISAMBIGUATION.md` | Mark remaining items as lower priority; note protocol fix supersedes per-skill patching |

## What Does NOT Change

- The `prerequisite_files` mechanism itself — still the right design
- Existing per-skill parentheticals — leave them in place as defense-in-depth; no need to remove
- The `mission-brief` Data Gate recommendation — still useful as a structural improvement independent of path resolution
- Preflight validation — still catches missing files at authoring time

---

## Migration

No migration required. The protocol rule applies to all skills immediately on adoption. Existing per-skill annotations remain valid and harmlessly redundant. The `PREREQ_PATH_DISAMBIGUATION.md` remaining work items (`mission-brief`, `fitting` data_sources, `help`) can be addressed at lower priority or deferred — the structural `mission-brief` Data Gate is still worth doing for readability, but path resolution is no longer the driving concern.

---

## Open Questions

1. **Should paths in skill bodies use `./` prefix convention?** (e.g., `./reference/mechanics/...`) — This would make project-root intent self-evident at the path level without relying on prose instructions, and the change is purely cosmetic. Downside: requires updating all existing skills and adds visual noise. Recommendation: defer unless confabulation recurs after protocol fix.

2. **Should the preflight script verify path resolution context?** — The script already validates that `prerequisite_files` paths exist. No change needed; the script operates from the project root by definition.
