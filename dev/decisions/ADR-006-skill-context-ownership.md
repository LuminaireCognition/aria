# ADR-006: Skill Context Ownership (Model A — Self-Contained Skills)

**Status:** Accepted
**Date:** 2026-02

## Context

ARIA skills vary widely in complexity. Simple skills like `/price` or `/route` are a few hundred tokens. Complex skills like `/mission-brief` have grown to ~9,800 tokens — roughly 42% of which is redundant with CLAUDE.md, prerequisite JSON files, or both.

The root cause is unclear ownership of behavioral context. Three layers can carry instructions:

1. **CLAUDE.md** — loaded in every conversation
2. **SKILL.md** — loaded on-demand when a skill is invoked
3. **Prerequisite/data files** — loaded by the skill loading mechanism

Without a clear rule about what goes where, content drifts into multiple layers simultaneously. Mission-brief's cache-first protocol exists in both CLAUDE.md and SKILL.md. Drone damage tables exist in both SKILL.md and `drones.json`. Pilot resolution exists in both CLAUDE.md and SKILL.md. Each redundancy wastes tokens and creates staleness risk.

Two competing models were evaluated:

- **Model A (self-contained skills):** CLAUDE.md holds system infrastructure; each SKILL.md carries all protocols needed for that skill's behavior.
- **Model B (shared context hub):** CLAUDE.md carries shared protocols; SKILL.md files are thin deltas referencing shared sections.

## Decision

Adopt **Model A with shared protocol files**. The ownership rule is:

| Layer | Owns | Examples |
|-------|------|---------|
| **CLAUDE.md** | System-level *mechanisms* — how things load, connect, and resolve | Session init, MCP tool mapping, skill loading mechanism, security rules, Python execution |
| **SKILL.md** | Skill-specific *behavior* — what to do when invoked | Response format, disambiguation flow, validation gates, retrieval protocols, experience adaptation |
| **Prerequisite/data files** | *Facts* and *reference data* | `drones.json`, `npc_damage_types.md`, weapon JSONs, `MODULE_NAMES.md` |
| **Shared protocol files** (new) | Cross-cutting *protocols* used by 2+ skills | Cache-first retrieval, fit validation pattern (if extracted) |

### Key Rules

1. **CLAUDE.md must not contain skill-specific protocols.** If a protocol only matters when a particular skill is active, it belongs in that SKILL.md or a shared protocol file — not in CLAUDE.md where it taxes every conversation.

2. **SKILL.md must not inline data from prerequisite files.** The `prerequisite_files` gate in the skill loading mechanism already forces reads before output. Inlining the same data in SKILL.md undermines the gate (Claude may treat the inline copy as sufficient) and creates staleness risk.

3. **SKILL.md must not duplicate CLAUDE.md system behaviors.** Pilot resolution, persona loading, and MCP tool usage are system-level — they happen before skill loading. Restating them in a skill is pure noise.

4. **Shared protocol files live in `reference/protocols/`** and are added to `prerequisite_files` or `data_sources` for skills that need them. This handles the small number of genuinely cross-cutting patterns without bloating CLAUDE.md.

### Migration Approach

Skills are migrated one at a time. For each skill:

1. Identify content that duplicates CLAUDE.md — delete from SKILL.md
2. Identify content that duplicates prerequisite/data files — delete from SKILL.md, replace with one-line reference
3. Identify cross-skill protocols — extract to `reference/protocols/` if not already there
4. Compress verbose formats (ASCII flowcharts → numbered lists, checkbox templates → imperative prose)
5. Validate that the slimmed skill still steers correctly via manual testing

No big-bang rewrite. Each skill migration is an independent, reviewable change.

## Consequences

### Positive

- **Token efficiency:** Skills only load when invoked; CLAUDE.md stays lean for non-skill conversations
- **Single source of truth:** Data lives in one place (JSON/md files), not inlined across layers
- **Independent testability:** A skill can be reviewed and tested without reading all of CLAUDE.md
- **Scales to N skills:** Adding skill #49 doesn't make CLAUDE.md larger
- **Leverages existing mechanism:** The `prerequisite_files` gate already exists in the skill loading system (ADR-002)

### Negative

- **Cross-skill consistency requires discipline:** Without a shared hub, two skills could implement similar protocols differently. Shared protocol files mitigate this but require authors to check for existing protocols before writing new ones.
- **Skill files are larger than Model B's thin deltas:** A self-contained SKILL.md is bigger than a "see §Section in CLAUDE.md" reference. This is the intended tradeoff — on-demand loading means the tokens are only spent when needed.
- **Shared protocol updates touch multiple files:** If `reference/protocols/cache-first.md` changes, all skills using it get the change automatically (it's a prerequisite read). But if a protocol needs skill-specific adjustments, the skill must handle that in its own SKILL.md.

## Alternatives Considered

### Model B: Thin SKILL.md with CLAUDE.md as Protocol Hub

Rejected. CLAUDE.md is loaded in every conversation. Skill-specific protocols in CLAUDE.md tax all conversations equally, regardless of whether the skill is invoked. With 48 skills, this makes CLAUDE.md unboundedly large. Cross-reference steering ("Use §Cache-First") is also empirically weaker than inline instructions.

### Status Quo (No Clear Ownership)

Rejected. The current state has triple-redundancy in places and no rule for where new content goes. Token cost grows with each skill update as authors copy context "just to be safe."

### Fully Inlined Skills (No Prerequisite Files)

Rejected. Defeats the purpose of maintaining authoritative data files. Inline copies go stale when the source file is updated.
