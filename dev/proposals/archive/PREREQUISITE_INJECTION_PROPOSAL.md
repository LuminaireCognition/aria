# Prerequisite File Injection via Dynamic Context

**Status:** Implemented
**Date:** 2026-03-10
**Owner:** Architecture
**Scope:** `.claude/skills/*/SKILL.md`, `CLAUDE.md`, `_index.json`, skill-loading docs
**Related:** `SKILL_LOADING_PATH_RESOLUTION.md`, `PREREQ_PATH_DISAMBIGUATION.md`, `CONTEXT_EFFICIENCY_PROPOSAL.md`

---

## Executive Summary

Exercise runs confirm that the agent does not reliably read `prerequisite_files` before producing output, despite:

1. Correct paths in every skill definition and `_index.json`
2. A protocol-level rule in `CLAUDE.md` §Skill Loading step 3 ("MANDATORY GATE")
3. An explicit "project-root-relative" path resolution rule (SKILL_LOADING_PATH_RESOLUTION)
4. Per-skill parenthetical annotations on read instructions (PREREQ_PATH_DISAMBIGUATION)

Two independent exercise runs (high effort, medium effort) of the same query both skipped the prerequisite read step, tried invented paths from training data, then self-corrected via Glob. The protocol rule is correctly authored — the agent simply doesn't comply with it.

**Core thesis:** Telling the agent to read files is an instruction compliance problem. Injecting file content before the agent runs is a preprocessing guarantee. Claude Code's `!`command`` dynamic context injection eliminates the compliance gap by baking prerequisite data into the skill prompt at invocation time.

**What changes:**

- Skills with static reference data prerequisites adopt `!`cat ...`` injection in their SKILL.md body
- `prerequisite_files` frontmatter is **narrowed to agent-loaded files only** — files that require runtime resolution (pilot data, ESI-synced)
- A new `injected_prerequisites` frontmatter field (`list[str]`) enumerates files loaded via `!`cat`` injection
- CLAUDE.md §Skill Loading gains a "do not re-read" rule for injected content
- Pilot-specific and dynamic paths remain agent-loaded (no change)

**What does NOT change:**

- `prerequisite_files` remains `list[str]` — no type change, no parser updates needed
- Per-skill parenthetical annotations (remain as defense-in-depth)
- The MANDATORY GATE rule in CLAUDE.md (still applies to `prerequisite_files` entries)
- The persona/overlay system
- `data_sources` loading behavior

---

## Problem Statement

### Evidence from exercise runs (2026-03-10)

Query: `"Damsel in Distress L3, Vexor, strictly T1 and meta"` via `/mission-brief`.

| Run | Effort | `npc_damage_types.md` path attempted first | Correct? | Recovery |
|-----|--------|---------------------------------------------|----------|----------|
| 003933 | high | `reference/npc_damage_types.md` | No | Glob → found at `reference/mechanics/` |
| 010336 | medium | `reference/pve-intel/npc_damage_types.md` | No | Glob → found at `reference/mechanics/` |

Both agents confabulated paths. Neither read the `prerequisite_files` list from the SKILL.md frontmatter before attempting file reads. The correct path (`reference/mechanics/npc_damage_types.md`) is declared in the frontmatter, in `_index.json`, and in every cross-reference across the codebase.

### Why prior mitigations are insufficient

| Mitigation | Level | Failure mode |
|------------|-------|-------------|
| `prerequisite_files` in frontmatter | Schema | Agent must parse YAML frontmatter and act on it — compliance not guaranteed |
| MANDATORY GATE rule in CLAUDE.md | Protocol | Agent must remember and follow an instruction from a different file |
| Path resolution rule | Protocol | Addresses *wrong resolution*, not *skipping the read entirely* |
| Per-skill parentheticals | Per-skill | Agent must encounter and follow inline prose — same compliance gap |

All four rely on the agent choosing to follow instructions. None provide a deterministic guarantee.

### The structural gap

The `prerequisite_files` mechanism is the right design: gate authoritative data before output. But it delegates execution to the agent. The agent's actual behavior is:

1. Receive skill prompt
2. Begin working on the task
3. Realize it needs reference data mid-generation
4. Guess a path from training data
5. Fail, Glob, find the file, read it
6. Continue (with correct data, but wasted tool calls and risk of silent fallback)

The desired behavior is:

1. Receive skill prompt with reference data already present
2. Produce output grounded in that data

---

## Proposed Solution

### Strategy 1: Dynamic Context Injection (`!`command``)

Claude Code skills support [dynamic context injection](https://code.claude.com/docs/en/skills#inject-dynamic-context): shell commands in `` !`command` `` syntax that execute before the skill prompt reaches the agent. The output replaces the placeholder in the skill content.

#### Mechanism

In a SKILL.md body, instead of:

```markdown
## Data Gate
Read `reference/mechanics/npc_damage_types.md` before producing output.
```

Use:

```markdown
## NPC Damage Types (injected)
!`cat reference/mechanics/npc_damage_types.md`
```

The agent receives the file content directly — it never needs to resolve, discover, or read the file.

#### Applicability criteria

A prerequisite file is a candidate for injection when ALL of the following hold:

1. **Static path** — no `{active_pilot}` or runtime-resolved variables
2. **Stable content** — file changes only via commits, not at runtime (no ESI sync, no cache)
3. **Reasonable size** — injecting a 2,000-line file into every invocation wastes context; the threshold is a judgment call per skill
4. **Always needed** — the file is used on every invocation, not conditionally

#### Eligible files (24 files across 33 skills)

| File | Lines | Skills using it | Inject? |
|------|-------|----------------|---------|
| `reference/mechanics/npc_damage_types.md` | 56 | mission-brief | Yes |
| `reference/mechanics/drones.json` | 154 | mission-brief, fitting | Yes |
| `reference/mechanics/missiles.json` | 280 | mission-brief | Yes |
| `reference/mechanics/projectile_turrets.json` | 208 | mission-brief | Yes |
| `reference/mechanics/laser_turrets.json` | 242 | mission-brief | Yes |
| `reference/mechanics/hybrid_turrets.json` | 254 | mission-brief | Yes |
| `reference/pve-intel/INDEX.md` | 30 | mission-brief | Yes |
| `reference/pve-intel/missions/INDEX.md` | 52 | mission-brief | Yes |
| `reference/archetypes/INDEX.md` | 41 | mission-brief, fit-recommend | Yes |
| `reference/archetypes/_shared/faction_tuning.yaml` | 327 | mission-brief | Yes |
| `reference/mechanics/ore_database.md` | 112 | mining-advisory | Yes |
| `reference/mechanics/abyssal_deadspace.json` | 419 | abyssal | Yes |
| `reference/mechanics/exploration_sites.md` | 226 | exploration | Yes |
| `reference/mechanics/hacking_guide.md` | 115 | exploration | Yes |
| `reference/mechanics/chokepoints.json` | 104 | gatecamp | Yes |
| `reference/mechanics/planetary-interaction.json` | 442 | pi | Yes |
| `reference/industry/fuel_blocks.json` | 153 | reactions | Yes |
| `reference/fittings/MODULE_NAMES.md` | 122 | fitting | Yes |
| `.claude/skills/fitting/EFT-FORMAT.md` | 161 | fitting | Yes |
| `.claude/skills/_shared/esi-error-handling.md` | 26 | 24 ESI skills | Yes |
| `reference/activities/skill_plans.yaml` | 917 | skillplan | **Yes** |
| `reference/skills/ship_efficacy_rules.yaml` | 932 | skillplan | **Yes** |
| `reference/skills/meta_module_alternatives.yaml` | 370 | skillplan | **Yes** |
| `reference/archetypes/_shared/module_tiers.yaml` | 226 | fit-budget | Yes |

**Skillplan decision (resolved):** All three skillplan prerequisites (2,219 lines total, ~3% context) are injected. All three are always needed and confabulation risk is high for skill plan data. The total is near the 2,000-line guideline but acceptable given skillplan's complexity. If context pressure emerges in practice, condense the largest files.

#### Files NOT eligible for injection

| File pattern | Reason |
|-------------|--------|
| `userdata/pilots/{active_pilot}/*.md` | Dynamic path, pilot-specific, runtime-resolved |
| `userdata/pilots/{active_pilot}/skills.json` | Dynamic path, ESI-synced |

These remain agent-loaded via the existing MANDATORY GATE protocol.

### Strategy 2: Skill-Scoped `PostToolUse` Hook (validation layer)

As a complementary verification mechanism, a `PostToolUse` hook on the `Skill` tool could validate that prerequisite files were actually read. This acts as a safety net for the files that cannot be injected (pilot data, large files).

#### Mechanism

In `.claude/settings.json` or per-skill frontmatter:

```yaml
hooks:
  PostToolUse:
    - matcher: "Skill"
      hooks:
        - type: prompt
          prompt: >
            Check the tool trace for this skill invocation. Were all
            prerequisite_files listed in the skill's frontmatter actually
            read before the first text output? If any were skipped,
            respond with {"ok": false, "reason": "Missing prerequisite
            reads: [list files]"}.
```

This is a **detection** mechanism, not a prevention mechanism. It cannot inject missing data — only flag when the agent skipped the gate.

#### Assessment

| Aspect | Dynamic Injection | PostToolUse Hook |
|--------|-------------------|------------------|
| **Guarantee level** | Deterministic — data is present before agent runs | Probabilistic — catches violations after the fact |
| **Context cost** | Higher — file content loaded every invocation | Zero — runs externally |
| **Complexity** | Low — `cat` commands in SKILL.md | Medium — hook script, prompt engineering |
| **Handles dynamic paths** | No | Yes |
| **Prevents confabulation** | Yes — data is already in context | No — can only detect and retry |

**Recommendation:** Use Strategy 1 (injection) for all eligible static files. Consider Strategy 2 only if monitoring reveals ongoing compliance failures for the remaining agent-loaded files (pilot data).

---

## Implementation Plan

### Phase 1: Pilot — `mission-brief` skill

Apply injection to `mission-brief` (the skill with the most prerequisites and confirmed confabulation).

1. Add injected data sections to `SKILL.md` body using `!`cat ...`` syntax
2. Wrap each in a labeled section for agent reference:
   ```markdown
   ## Reference: NPC Damage Types
   <!-- prerequisite: reference/mechanics/npc_damage_types.md -->
   !`cat reference/mechanics/npc_damage_types.md`
   ```
3. Move injected file paths from `prerequisite_files` to new `injected_prerequisites` field in frontmatter. `prerequisite_files` retains only agent-loaded entries (pilot data). Update the skill's `_index.json` entry to match: add `injected_prerequisites` array, remove migrated paths from `prerequisite_files`.
4. Add a documentation comment distinguishing injected vs agent-loaded prerequisites:
   ```markdown
   <!-- Injected prerequisites loaded via !`cat` above. Agent-loaded prerequisites
        (pilot data in prerequisite_files) must still be read before producing output. -->
   ```
5. Re-run exercise query; compare tool trace and output quality to baseline runs

**Success criteria:** Zero Glob calls for prerequisite files; correct paths on first read for pilot data; no confabulation.

### Phase 2: Roll out to remaining skills

Apply injection to all eligible skills, prioritized by confabulation risk:

| Priority | Skills | Total injected lines | Rationale |
|----------|--------|---------------------|-----------|
| P1 | mission-brief | ~1,644 | Confirmed confabulation in two runs |
| P1 | fitting | ~437 | Weapon data confabulation risk; EFT format critical |
| P1 | exploration | ~341 | Confirmed confabulation (20260303-232824) |
| P2 | abyssal, mining-advisory, pi, reactions, gatecamp | 112–442 each | Single-file prerequisites, low risk but easy wins |
| P2 | fit-recommend, fit-budget | 41–226 | Index/tier files, moderate risk |
| P3 | skillplan | ~2,219 | Large payload; inject all three (decision: accept context cost) |
| P3 | 24 ESI skills (esi-error-handling.md) | 26 each | Tiny file, universal; 24 individual SKILL.md edits (no shared template mechanism) |

**ESI skills requiring `esi-error-handling.md` injection (24 skills):**

`agents-research`, `assets`, `clones`, `contracts`, `corp`, `escape-route`, `esi-query`, `fit-budget`, `fit-check`, `fittings`, `industry-jobs`, `isk-compare`, `killmails`, `lp-store`, `mail`, `mining`, `orders`, `pilot`, `sec-status`, `ship-next`, `skillplan`, `skillqueue`, `standings`, `wallet-journal`

Discovery command: `jq -r '.skills[] | select(.prerequisite_files[]? == ".claude/skills/_shared/esi-error-handling.md") | .name' .claude/skills/_index.json | sort`

**Per-skill migration step:** For each skill in Phase 2, update its `_index.json` entry: add `injected_prerequisites` array containing the migrated paths, and remove those paths from `prerequisite_files`. This keeps the index in sync with the SKILL.md injection state.

### Phase 3: Schema and documentation updates

1. **`SCHEMA.md`** — Add `injected_prerequisites: list[str]` field. Document the invariant: a skill's total prerequisites = `injected_prerequisites` (loaded via `!`cat``) + `prerequisite_files` (agent-loaded). Neither array may contain entries from the other.
2. **`CLAUDE.md` §Skill Loading** — Add rule: "When prerequisite content is already present in the skill prompt (injected via `!`command`` syntax), do not re-read the source file." This is the single authoritative location for the "do not re-read" instruction — per-skill comments are documentation only.
3. **`personas/_shared/skill-loading.md`** — Add a section on the injection pattern as the recommended approach for new skills with static reference data. (A standalone `CONTRIBUTING_SKILLS.md` is deferred — not needed until contributor onboarding requires its own document.)
4. **`PREREQ_PATH_DISAMBIGUATION.md`** — Add a callout block at the top: *"Path disambiguation for injected prerequisites is superseded by dynamic context injection (see `PREREQUISITE_INJECTION_PROPOSAL.md`). This document applies only to agent-loaded `prerequisite_files` entries."* Retain all existing content for agent-loaded file guidance.
5. **`dev/scripts/validate-reference-data.py`** — Add two validation rules:
   - File existence: every path in both `injected_prerequisites` and `prerequisite_files` must resolve to an existing file
   - Injection presence: for each path in `injected_prerequisites`, the skill's SKILL.md must contain a matching `` !`cat <path>` `` line (catches stale frontmatter after injection removal)

---

## Context Cost Analysis

Injection trades tool calls for context tokens. Is this worthwhile?

### Current cost (agent-loaded)

Per invocation of `mission-brief` with confabulation recovery:
- 2–3 failed Read/Glob attempts (wasted tool calls)
- 1 successful Read (correct file loaded)
- Risk of silent fallback to training data if recovery fails

Tool calls are not free — each consumes a round-trip and context tokens for the tool result.

### Proposed cost (injected)

Per invocation of `mission-brief`:
- ~1,644 lines of reference data loaded into prompt
- Zero tool calls for prerequisite files
- Zero confabulation risk for injected data

### Budget assessment

| Skill | Injected lines | % of typical 200k-token context | Verdict |
|-------|---------------|-------------------------------|---------|
| mission-brief | 1,644 | ~2% | Acceptable — skill is complex, data is always needed |
| fitting | 437 | <1% | Trivially acceptable |
| exploration | 341 | <1% | Trivially acceptable |
| skillplan | 2,219 | ~3% | Accepted — all files always needed, high confabulation risk; condense if context pressure emerges |
| ESI skills (each) | 26 | <0.1% | Negligible |

For comparison, the agent currently spends 3–8 tool calls recovering from path confabulation. Each tool call with its result consumes context tokens comparable to the injected content. Injection is context-neutral or context-positive in practice.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Large injected payloads reduce remaining context for conversation | Skill may hit context limits on complex queries | Set a per-skill injection budget (~2,000 lines max); use condensed versions for large files |
| Agent ignores injected data and re-reads files anyway | Wasted context (data loaded twice) | Add "do not re-read" instruction; monitor via tool traces |
| ~~`!`command`` syntax not available in `claude -p` (exercise runner)~~ | ~~Exercise runs can't test injection~~ | **Resolved:** Verified 2026-03-10 — injection works in `claude -p` mode (Claude Code 2.1.72). No shim needed. |
| Injected content becomes stale if file changes but skill isn't re-invoked | Data inconsistency within a session | Not a real risk — skills are invoked per-query, and `cat` reads current file state at invocation time |
| Reference files grow beyond injection budget | Context pressure increases over time | Validate-reference-data.py can enforce line-count limits on injectable files |

---

## Open Questions (all resolved)

1. ~~**Does `!`command`` work in `claude -p` mode?**~~ **Resolved.** Verified 2026-03-10 (Claude Code 2.1.72): `!`cat file`` injection executes in `claude -p` mode. Tested with `--allowedTools ''` (no tools available) — agent received injected file content and echoed back unguessable canary tokens. Negative control confirmed agent cannot access file content without injection. No preprocessing shim is needed for the exercise runner.

2. ~~**Should injected content use data delimiters?**~~ **Resolved: No.** Files under `reference/` and `.claude/skills/` are git-tracked, author-controlled, and validated by CI — they are not untrusted in the CLAUDE.md §Untrusted Data Handling sense. Wrapping `cat` output in `<untrusted-data>` tags would require a wrapper script around every injection (the `!`command`` syntax outputs raw stdout). **Decision:** Skip delimiters for `reference/` and `.claude/skills/` paths. If injection is later extended to user-editable content (e.g., under `userdata/`), delimiters must be applied via a wrapper script.

3. ~~**Should `_index.json` distinguish injected vs agent-loaded prerequisites?**~~ **Resolved: Separate `injected_prerequisites` array.** A new `injected_prerequisites: list[str]` field is added alongside `prerequisite_files`. This preserves `prerequisite_files` as `list[str]` (no parser changes) while giving validators a clean cross-reference. The inline flag approach (`injected: true` per entry) was rejected because it would change `prerequisite_files` from `list[str]` to `list[dict]`, breaking every existing parser. The `prerequisite_files` field is narrowed to agent-loaded files only; `injected_prerequisites` contains the injection targets. Total prerequisites = union of both arrays.

4. ~~**What about shared prerequisite injection?**~~ **Resolved: Duplicate per skill.** Claude Code skills don't support includes between skills. Each of the 24 ESI skills gets its own `!`cat .claude/skills/_shared/esi-error-handling.md`` line. At 26 lines per injection, duplication cost is negligible.

---

## Decisions Summary

| Item | Decision | Rationale |
|------|----------|-----------|
| Schema | Separate `injected_prerequisites: list[str]` array | Preserves `prerequisite_files` type; clean validator cross-reference |
| `prerequisite_files` scope | Narrowed to agent-loaded only | MANDATORY GATE applies unambiguously to remaining entries |
| Data delimiters | Skip for `reference/` and `.claude/skills/` | Author-controlled, CI-validated; wrapper scripts not warranted |
| "Do not re-read" placement | CLAUDE.md §Skill Loading only | Single authoritative source; per-skill comments are documentation |
| `CONTRIBUTING_SKILLS.md` | Deferred; add section to `skill-loading.md` | Avoids scope creep; existing doc is the right home |
| Skillplan injection | Inject all three files (2,219 lines) | Always needed, high confabulation risk, within context budget |
| Validator updates | File existence + injection presence checks | Catches stale frontmatter and missing files |

---

## Implementation Notes (2026-03-10)

### Phase 1 & 2: Complete

All 33 skills migrated:

- **10 reference-data skills:** mission-brief (10 files), fitting (3), exploration (2), skillplan (4), abyssal (1), mining-advisory (1), gatecamp (1), pi (1), reactions (1), fit-budget (2), fit-recommend (1)
- **24 ESI skills:** `esi-error-handling.md` injected into each

Each skill received:
1. `injected_prerequisites` array in frontmatter
2. Migrated paths removed from `prerequisite_files`
3. `!`cat`` injection blocks appended to SKILL.md body
4. Matching `_index.json` entry updated

`prerequisite_files` narrowed to agent-loaded entries only. Post-migration, only `mission-brief` retains `prerequisite_files` (3 dynamic pilot paths).

### Phase 3: Complete

| Item | Location | Status |
|------|----------|--------|
| `injected_prerequisites` schema | `SCHEMA.md` §Injected Prerequisites | Done |
| "Do not re-read" rule | `CLAUDE.md` §Skill Loading step 3 | Done |
| Injection pattern docs | `personas/_shared/skill-loading.md` §1.6 | Done |
| PREREQ_PATH callout | `PREREQ_PATH_DISAMBIGUATION.md` header | Done |
| Validator rules | `validate-skill-index.py` checks 12–14 | Done (see deviation below) |

### Deviation: Validator location

The proposal specified adding validation rules to `validate-reference-data.py`. The rules were implemented in `validate-skill-index.py` instead (checks 12, 13, 14):

- **Check 12:** `injected_prerequisites_exist` — file existence for all injected paths
- **Check 13:** `injection_presence` — `!`cat <path>`` present in SKILL.md for each injected path
- **Check 14:** `no_overlap` — no path appears in both `prerequisite_files` and `injected_prerequisites`

**Rationale:** These checks operate on `_index.json` skill entries and their corresponding SKILL.md files — the same data domain as all other `validate-skill-index.py` checks. Adding them to `validate-reference-data.py` would duplicate the index-parsing logic and create a cross-file maintenance burden.

### Validation Results

```
validate-skill-index.py: 786 passed, 0 failed, 0 warnings, 51 skipped
```
