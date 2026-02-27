# ARIA Context Efficiency Proposal

**Status:** Implemented
**Date:** 2026-02-26
**Owner:** Architecture
**Scope:** CLAUDE.md, AGENTS.md, ai-runtime docs, skill files, boot hook
**Related:** ADR-006, ADR-002, `dev/reviews/ACCRETION_AUDIT_2026-02-24.md`

---

## Executive Summary

ARIA's instruction layer has grown to serve two masters: preventing Claude from hallucinating EVE game data, and controlling Claude's conversational behavior. The first concern is legitimate and empirically grounded. The second is largely unnecessary — Claude handles audience adaptation, progressive disclosure, and contextual suggestion natively.

This proposal establishes a model for distinguishing the two, eliminates the unnecessary layer, and restructures the necessary layer to use *data injection at point of use* rather than *behavioral policy loaded at all times*.

**Core thesis:** The only reliable way to prevent domain-specific hallucination is to make authoritative data more accessible than training data at the moment of generation. Behavioral instructions ("verify first", "do not guess") are necessary as a single clear principle but do not scale through repetition. Six instructions saying "don't hallucinate" are not more effective than one.

**What changes:**

1. CLAUDE.md drops from ~530 lines to ~290 lines (-45%)
2. AGENTS.md drops from 61 lines to ~20 lines (-67%)
3. Six ai-runtime docs (1,219 lines total) consolidate to two (~350 lines, -71%)
4. Boot hook stops duplicating what CLAUDE.md describes
5. Skill files adopt a consistent structure that separates *edge-case guardrails* from *procedural narration*

**What does NOT change:**

- The MCP tool architecture (already well-designed)
- The persona system (already well-scoped)
- The `prerequisite_files` mechanism (the right idea, kept and clarified)
- ADR-006's ownership model (correct, needs completion not replacement)
- Security rules (untrusted data handling, path validation, sensitive files)

---

## Problem Statement

### 1. Context window pressure from always-loaded instructions

Every ARIA conversation starts approximately 11,500 tokens deep:

| Source | Tokens | Content |
|--------|--------|---------|
| CLAUDE.md | ~6,500 | System instructions |
| AGENTS.md | ~2,000 | Skill registry + usage rules |
| Boot hook JSON | ~500 | Session context |
| Persona files | ~2,500 | Voice, identity (when RP enabled) |
| **Total** | **~11,500** | **Before user speaks** |

A skill invocation adds 800–4,000 tokens (SKILL.md) plus 0–5,000 tokens (prerequisite files). The `skillplan` skill is an extreme case: its three prerequisite YAML files total ~61,000 lines. Complex interactions easily exceed 20,000 tokens of instruction before Claude generates a single word of output.

This matters because always-loaded context competes with conversation history, tool outputs, and reasoning for first-turn quality, and accelerates the onset of automatic context compression in longer sessions. Claude Code compresses prior messages as conversations approach the context limit, which partially mitigates the pressure — but reducing the always-loaded baseline delays compression and preserves more conversation history at every turn. The tradeoff is justified only when the instruction actually changes Claude's behavior.

### 2. Behavioral policy that doesn't change behavior

Several instruction documents teach Claude things it already does:

| Document | Lines | What it teaches | Claude's native capability |
|----------|-------|-----------------|---------------------------|
| `EXPERIENCE_ADAPTATION.md` | 109 | Adjust depth by audience | Core LLM capability |
| `COMMAND_SUGGESTIONS.md` | 129 | Suggest commands naturally | Contextual awareness |
| `DATA_VERIFICATION.md` (non-case-study sections) | ~200 | "Check tools before claiming" | Already expressed in one Prime Directive line |

These documents exist because Claude *once* got something wrong, and the response was to write a document preventing that specific failure. But the documents don't actually prevent future failures — they add tokens. The case studies in DATA_VERIFICATION.md are genuinely useful (they show *what* Claude gets wrong), but the process checklists and flowcharts are not (they describe *how to think*, which Claude cannot be instructed to do mechanistically).

### 3. Partial dual initialization

The boot hook (1,505 lines across 4 modules) resolves pilot identity, detects persona, validates security, syncs ESI, and outputs structured JSON. CLAUDE.md then describes a 5-step Session Initialization process in 62 lines of prose.

Steps 1–2 (pilot resolution, profile loading) are genuinely redundant — the boot hook does this and reports results in JSON. Steps 3–4 (staleness validation, persona artifact loading) are Claude's runtime responsibility and are *not* performed by the boot hook — these instructions must be retained. Step 5 (fresh install check) can be derived from the boot JSON's `state.fresh_install` field.

The ~25 lines describing steps 1–2 are pure narration of completed work. The remaining ~37 lines for steps 3–5 can be simplified but not eliminated.

### 4. Defense-in-width against hallucination

Six separate mechanisms address the same concern (Claude fabricating EVE game data):

1. Prime Directive #6 in CLAUDE.md ("Verify Before Claiming")
2. `prerequisite_files` mandatory gate in skill loading
3. Per-skill `HALLUCINATION GUARD` sections
4. `DATA_VERIFICATION.md` (415 lines, 3 case studies)
5. Static Game Data References table in CLAUDE.md (53 lines)
6. Per-skill "DO NOT" sections

Mechanism #1 is the principle. Mechanism #2 is the enforcement. These two are sufficient and complementary: the principle tells Claude *why* to verify, the mechanism ensures authoritative data is *in context* when it matters.

Mechanisms #3–6 are restatements of #1 in different locations, consuming tokens without adding reliability. A skill that loads `drones.json` via `prerequisite_files` does not additionally need a HALLUCINATION GUARD saying "use drones.json not training data" — the data is already there.

### 5. AGENTS.md duplicates native discovery

Claude Code natively discovers skills from `.claude/skills/*/SKILL.md`. The AGENTS.md file (61 lines) re-lists all 49 skills with descriptions and file paths, plus usage instructions that largely restate Claude Code's built-in skill handling. The system-reminder in the conversation already lists all available skills.

Note: AGENTS.md is a **generated artifact** produced by `aria-skill-index.py` and regenerated at every boot. It also serves as the skill registry for the Anthropic Agents API path (non-Claude-Code agents). Phase 2 must address both the generator and the non-Claude-Code consumer.

### 6. Outsized prerequisite file loads

While `prerequisite_files` is the right mechanism, some skills load disproportionate amounts of data. The `skillplan` skill's three prerequisite files total ~61,000 lines:

| File | Lines |
|------|------:|
| `reference/activities/skill_plans.yaml` | 23,130 |
| `reference/skills/ship_efficacy_rules.yaml` | 27,929 |
| `reference/skills/meta_module_alternatives.yaml` | 9,934 |

This dwarfs the entire always-loaded instruction layer. The data is loaded on-demand (only when `/skillplan` is invoked), so it doesn't contribute to baseline context pressure — but it creates severe pressure during the skill's execution, leaving minimal room for conversation history and reasoning.

This problem is out of scope for the current proposal (it requires structural changes to the data files, not the instruction layer), but Phase 5 includes a note on investigating lazy-loading strategies for oversized prerequisite files.

---

## The Model: Data at Point of Use

### Principle

The only thing that reliably prevents Claude from using training data for domain-specific facts is *having authoritative data in context when generating the response*. This is not a behavioral instruction — it is an architectural property.

```
┌─────────────────────────────────────────────────┐
│            ARIA Context Architecture             │
├─────────────────────────────────────────────────┤
│                                                  │
│  CLAUDE.md (always loaded)                       │
│  ├─ Identity & boundaries (who ARIA is)          │
│  ├─ Security rules (untrusted data, secrets)     │
│  ├─ Infrastructure (Python, MCP, boot)           │
│  └─ ONE verification principle                   │
│                                                  │
│  Skill SKILL.md (loaded on invocation)           │
│  ├─ Tool calls required                          │
│  ├─ Output format                                │
│  ├─ Edge-case guardrails (empirical failures)    │
│  └─ prerequisite_files → data injection          │
│                                                  │
│  Prerequisite files (loaded before output)       │
│  └─ Authoritative facts (the actual defense)     │
│                                                  │
└─────────────────────────────────────────────────┘
```

### What goes where

| Layer | Content type | Loaded when | Token budget |
|-------|-------------|-------------|--------------|
| **CLAUDE.md** | Identity, security, infrastructure mechanisms | Every session | Target: ~3,600 tokens (from ~6,500) |
| **AGENTS.md** | Skill discovery supplement (minimal) | Every session | Target: ~400 tokens (from ~2,000) |
| **SKILL.md** | Required tools, output format, edge-case guardrails | On skill invocation | Varies by skill complexity |
| **Prerequisite files** | Authoritative data that prevents hallucination | On skill invocation | Varies by data volume |
| **ai-runtime docs** | Deep reference for development/debugging | On demand (never auto-loaded) | N/A (not in conversation) |

### What constitutes an edge-case guardrail

Not all "DO NOT" instructions are equal. A guardrail earns its tokens when:

1. **Empirically observed:** Claude has actually made this specific mistake (not hypothetically could)
2. **Non-obvious:** The correct behavior isn't obvious from the tool output or data
3. **Consequential:** Getting it wrong causes real harm (wrong fit = lost ship, not just suboptimal formatting)
4. **Not fixable by data injection:** The mistake isn't "used training data instead of reference data" (that's solved by loading the data), but rather "misinterpreted correct data" or "applied the wrong mental model"

Examples from the current codebase that **pass** this test:

| Skill | Guardrail | Why it earns its tokens |
|-------|-----------|------------------------|
| fitting | Ammo items misparsed as drones (line 92-101) | EOS parser limitation, not a Claude reasoning error |
| fitting | Mixed armor/shield tank detection | Claude genuinely conflates tank types without explicit rules |
| exploration | System Core Analyzer behavior | Counter-intuitive mechanic (always succeeds on System Core) |
| orient | `include_realtime=True` required | MCP default is `false`, Claude won't discover this from tool description |
| skillplan | Don't call SDE alongside easy_80_plan | Real redundancy that wastes an API call and confuses output |
| price | Never recall prices from training data | Prices are the most volatile data type in the game |

Examples that **fail** this test (should be removed):

| Skill | Guardrail | Why it doesn't earn its tokens |
|-------|-----------|-------------------------------|
| Any | "Use drones.json not training data" (when drones.json is in prerequisite_files) | The data is already loaded — this is telling Claude to use what's in front of it |
| Any | "Verify before claiming" (restated per-skill) | Already a Prime Directive — repetition doesn't add reliability |
| fitting | 14-line response format template | Claude formats fitting output well without a template |
| mission-brief | 90-line response format template | Useful as a reference, but can be trimmed to essential fields |

---

## Migration Plan

### Phase 0: Establish baselines (1 session)

Before changing anything, measure what we're working with:

1. **Count tokens** in current CLAUDE.md, AGENTS.md, and each ai-runtime doc using `cl100k_base` tokenizer (via `tiktoken`). Use word-count approximation (`wc -w` × 1.3) as a cross-check but report `cl100k_base` as the canonical number.
2. **Classify lines** in the top 5 skills by size (fitting, mission-brief, skillplan, threat-assessment, hunting-grounds). Categorize every line as: guardrail (empirical), guardrail (speculative), data/reference, procedure, or format template.
3. **Document the boot hook's JSON output schema** — the exact fields Claude receives from `output_json_context()` in `boot-display.sh`. This is a prerequisite for writing Phase 4's CLAUDE.md replacement text.
4. **Write regression test prompts** — 2–3 concrete prompts per top-5 skill that exercise the behaviors the removed content was supposed to control. Derive prompts from the failure modes identified during line classification (step 2): each `guardrail-empirical` line implies at least one prompt that would trigger the failure if the guardrail were absent. These prompts are the pass/fail baseline: run them after each phase and compare output quality against Phase 0 results. A regression is: Claude produces a factually wrong EVE game data claim that the Phase 0 baseline got right. **Accepted limitation:** prompts are derived at classification time, not pre-enumerated. Edge cases not represented in the top-5 skills' guardrails may be missed; the rollback strategy (revert + diagnose) covers this risk.

**Deliverable:** Baseline metrics file at `dev/reviews/context-efficiency-baseline.md` with these sections:

```
## Token Counts
(Table: file → word count → cl100k_base token count)

## Line Classification — {Skill Name}
(One section per top-5 skill. Table: line range → category → notes)
Categories: guardrail-empirical, guardrail-speculative, data/reference, procedure, format-template

## Boot Hook JSON Schema
(Field paths and types from output_json_context(). Required for Phase 4.)

## Regression Test Prompts
(Grouped by skill. Each prompt derived from guardrail-empirical lines in
Line Classification above. Each entry: prompt text, guardrail(s) exercised,
expected behavior, Phase 0 baseline output.)
```

### Phase 1: Slim CLAUDE.md (-45%, ~3,600 tokens target)

**Remove entirely:**

| Section | Lines | Reason |
|---------|-------|--------|
| Session Initialization steps 1-2 | ~25 | Boot hook does this; Claude receives the JSON result. **Gate:** Phase 0's boot hook schema must confirm that pilot resolution (step 1) and profile loading (step 2) are fully covered by boot hook JSON output before this removal is implemented. |
| Static Game Data References table | 53 | Move references into relevant skills' `prerequisite_files` |

**Reference file migration mapping:** When removing the Static Game Data References table, promote or add files to the appropriate skills:

| Reference file | Target skill | Change |
|----------------|-------------|--------|
| `missiles.json` | `mission-brief` | Promote `data_sources` → `prerequisite_files` |
| `projectile_turrets.json` | `mission-brief` | Promote `data_sources` → `prerequisite_files` |
| `laser_turrets.json` | `mission-brief` | Promote `data_sources` → `prerequisite_files` |
| `hybrid_turrets.json` | `mission-brief` | Promote `data_sources` → `prerequisite_files` |
| `planetary-interaction.json` | `pi` | Promote `data_sources` → `prerequisite_files` |
| `missiles.json` | `fitting` | Add to `data_sources` |
| `projectile_turrets.json` | `fitting` | Add to `data_sources` |
| `laser_turrets.json` | `fitting` | Add to `data_sources` |
| `hybrid_turrets.json` | `fitting` | Add to `data_sources` |

**Rationale:** `prerequisite_files` = mandatory gate (skill always needs the data). `data_sources` = contextual (fitting only needs ammo data when user asks about charges/crystals). `drones.json` already in `prerequisite_files` for both `fitting` and `mission-brief` — no change needed.

| Universe Navigation `### Option 1: MCP Tools` subsection (dispatcher table, tool name mapping, usage pattern examples, `sde` vs `skills` disambiguation — lines 188–248 in current CLAUDE.md) | 61 | Tool descriptions already enumerate actions; `sde`/`skills` disambiguation moves to a 3-line note in `### MCP Fallback Behavior` |
| Notification Profiles quick-start | 28 | Belongs in docs, not always-loaded context |
| Configuration Change Protocol | 10 | Rare operation; belongs in dev docs |
| "Do NOT Write Inline Python" section | 7 | Covered by MCP tool availability |

**Simplify:**

| Section | Current lines | Target lines | Change |
|---------|--------------|-------------|--------|
| Session Initialization steps 3-5 | ~37 | ~15 | Steps 3-4 (staleness check, persona loading) are Claude's runtime actions — keep the instructions but trim prose. Step 5 (fresh install check) stays as-is. |
| MCP Fallback Behavior | 21 | 5 | Keep table, remove prose |
| Skill Loading | 69 | 25 | Keep mechanism, remove path validation details (move to `personas/_shared/skill-loading.md`, which already documents overlay security) |
| Persona Loading | 26 | 10 | Keep pointer to compiled artifact, remove example YAML |
| `sde` vs `skills` disambiguation | 20 | 10 | Keep table, remove examples |
| Reference Documentation table | 24 | 12 | Remove dev-only entries. **Keep:** Ad-hoc market scopes, Persona loading, Skill loading & overlays, RP level configuration, ESI integration, Multi-pilot architecture, Context-aware topology, Real-time intel config, Notification profiles. **Remove:** Data verification (→ DATA_TRUST.md), Data authority (→ DATA_TRUST.md), Context policy, External data sources, Data files & volatility (→ SESSION_BEHAVIOR.md), Data protocols (→ SESSION_BEHAVIOR.md), Experience adaptation (→ SESSION_BEHAVIOR.md), Session context, Python environment (already in CLAUDE.md body), Persona system (contributor doc). |

**Important distinction:** Session Init steps 1–2 (pilot resolution, profile loading) are performed by the boot hook and reported in JSON — Claude receives the results. Steps 3–4 (staleness validation, persona context loading) are actions Claude must perform at runtime after reading the boot hook output. Step 5 (fresh install check) can be derived from the boot JSON's `state.fresh_install` field. The instructions for steps 3–4 must be retained in simplified form.

**Keep unchanged:**

| Section | Lines | Why |
|---------|-------|-----|
| ESI Capability Boundaries | 11 | Always relevant, compact |
| Untrusted Data Handling | 48 | Security-critical |
| Sensitive Files | 16 | Security-critical |
| Prime Directives | 15 | Core identity, includes the ONE verification principle |
| Python Execution | 21 | Prevents real errors |
| Data Volatility | 7 | Compact, always relevant |

**Rewrite the verification principle** (Prime Directive #6) to be self-contained:

```markdown
6. **Verify Before Claiming:** EVE game data (stats, damage types, requirements,
   prices, slot layouts) changes across patches. Query SDE, fitting, or market tools
   for specific numbers. Never state EVE-specific values from training data alone.
   Skills that need reference data declare it in `prerequisite_files` — this data
   will be loaded before you generate output.
```

This is 4 lines. It replaces the current 1-line principle + pointer to a 415-line document + per-skill repetitions.

### Phase 2: Slim AGENTS.md (-67%, ~400 tokens target)

Replace the full skill listing with minimal discovery guidance:

```markdown
# AGENTS.md

## Python (CRITICAL)
Always use `uv run`. Never bare `python`, `python3`, or `pip`.

## Skills
Skills live in `.claude/skills/{name}/SKILL.md`. The system-reminder lists all
available skills with descriptions. When a skill matches the user's request,
read its SKILL.md and follow its workflow.

If SKILL.md declares `prerequisite_files`, read ALL listed files before
generating any output. These contain authoritative game data.
```

**Rationale:** Claude Code already provides skill discovery through the system-reminder. AGENTS.md's 49-skill registry is redundant for Claude Code sessions. The "How to use skills" section largely restates Claude Code's native behavior. Keep only the two things Claude Code doesn't handle natively: `uv run` requirement and `prerequisite_files` gate.

**Generator disposal:** AGENTS.md is currently a generated artifact produced by `aria-skill-index.py` and regenerated at every boot. **Decision: option (b) — remove the generator and hand-maintain AGENTS.md.** 10 lines of static text does not benefit from generation. Delete `aria-skill-index.py` and remove its boot hook invocation. Git history preserves the file if the Agents API path is reactivated.

**Agents API consumer:** AGENTS.md also serves as the skill registry for the Anthropic Agents API path (non-Claude-Code agents), which does not have a system-reminder listing available skills. The Agents API path is experimental and not actively deployed. If it is reactivated, a separate `AGENTS_API.md` can be generated from `_index.json` at that time — this does not block slimming the Claude Code AGENTS.md now.

### Phase 3: Consolidate ai-runtime docs (-71%, ~350 lines from 1,219)

**Merge into two files:**

**File 1: `dev/docs/ai-runtime/DATA_TRUST.md` (~200 lines)**

Merges: `DATA_VERIFICATION.md` (415 lines) + `DATA_AUTHORITY.md` (308 lines)

Content:
- Trust hierarchy (one version, not two with different orderings)
- The three case studies from DATA_VERIFICATION.md (these are genuinely useful — they show specific failure modes)
- Cache authority rules from DATA_AUTHORITY.md
- Data source characteristics (ESI vs zKillboard precision/recall)

Removes:
- Process checklists and flowcharts (behavioral narration Claude can't mechanistically follow)
- "Integration with Response Flow" section (describes how Claude should think)
- Redundant "Summary" sections
- The "When Tools Don't Have the Data" section (3 paragraphs restating "use blessed sources")

**File 2: `dev/docs/ai-runtime/SESSION_BEHAVIOR.md` (~150 lines)**

Merges: `PROTOCOLS.md` (126 lines) + `DATA_FILES.md` (125 lines) + `EXPERIENCE_ADAPTATION.md` (109 lines) + `COMMAND_SUGGESTIONS.md` (129 lines)

Content:
- Data volatility tiers + file path reference (from PROTOCOLS.md + DATA_FILES.md — these are complementary halves of the same topic)
- One table of experience levels with one-line descriptions (from EXPERIENCE_ADAPTATION.md)
- Command suggestion principles as a 5-line section (from COMMAND_SUGGESTIONS.md)

**Acceptance criteria for distilled content:**

- **Command suggestions section (5 lines):** Must include the progressive disclosure principle ("suggest commands when topics arise, mention each once") and the four command tiers (Must-Know, Situational, Power User, Rarely Needed) with 1–2 example commands per tier.
- **Experience levels table:** Must include the three levels (`new`, `intermediate`, `veteran`) with columns for explanation depth and one example phrase per level demonstrating density difference.
- **DATA_TRUST.md:** Must include (a) the canonical trust hierarchy from DATA_AUTHORITY.md (ESI → SDE → DOTLAN → EVE Uni Wiki → never training data), (b) the three case studies from DATA_VERIFICATION.md condensed to ~20 lines each, and (c) cache authority rules.
- **"Verified" defined:** Phase 0 regression prompts still pass after the merge. A contributor unfamiliar with the original files can locate the trust hierarchy, case studies, and data volatility tiers within 60 seconds.

Removes:
- 5 detailed explanation example pairs from EXPERIENCE_ADAPTATION.md (Claude does audience adaptation natively)
- Progressive revelation flow from COMMAND_SUGGESTIONS.md (Claude does progressive disclosure natively)
- Good/bad example pairs from COMMAND_SUGGESTIONS.md (teaching natural language use to an LLM)
- Redundant "Recommended Phrasing" section from PROTOCOLS.md
- "Query Triggers" detail from PROTOCOLS.md (when to query is obvious from the data type)

**Neither file is auto-loaded.** They exist as development reference and for onboarding contributors. CLAUDE.md does not need to reference them — the principles that matter are already in the Prime Directives.

**File disposition:** After the two new files are written and verified, **delete all 6 source files** (`DATA_VERIFICATION.md`, `DATA_AUTHORITY.md`, `PROTOCOLS.md`, `DATA_FILES.md`, `EXPERIENCE_ADAPTATION.md`, `COMMAND_SUGGESTIONS.md`). Update any cross-references in CLAUDE.md's Reference Documentation table to point to the new filenames. Phase 6's cleanup table lists `EXPERIENCE_ADAPTATION.md` and `COMMAND_SUGGESTIONS.md` as post-Phase-3 deletions — with this change, those two Phase 6 rows become no-ops and can be removed.

**Trust hierarchy ordering:** `DATA_AUTHORITY.md`'s hierarchy (ESI → SDE → MCP-derived → community) is the canonical ordering. `DATA_VERIFICATION.md`'s hierarchy is a subset focused on verification steps. Use `DATA_AUTHORITY.md`'s as the single trust hierarchy in `DATA_TRUST.md`.

### Phase 4: Rationalize boot hook ↔ CLAUDE.md boundary

**Principle:** The boot hook *does things and reports results*. CLAUDE.md *tells Claude how to interpret the results*. No overlap.

**Boot hook keeps:** Pilot resolution, persona detection, ESI sync, security checks, JSON output.

**CLAUDE.md changes:**

Replace the Session Initialization section. **This phase is gated on Phase 0's boot hook schema deliverable** — the draft below uses placeholder field names that must be replaced with actual JSON paths from Phase 0's documented schema before implementation:

```markdown
## Session Context

The boot hook outputs JSON with pilot identity, persona, ESI status, and
diagnostics. Use this data directly — do not re-resolve pilot or persona.

If `state.fresh_install` is true, offer `/setup`.
If `diagnostics.warnings` is non-empty, mention them briefly.

### Persona Loading (runtime)

If `persona.name` is not "ARIA" and `rp_level` is not "off":
1. Read the compiled persona artifact from the path in the boot JSON.
2. Validate staleness: profile `faction` should map to the persona branch
   (empire factions → `empire`, pirate → `pirate`). If mismatch, warn the
   user and suggest `uv run aria-esi persona-context`. Continue with
   current context.
3. Use `raw_content` from the compiled artifact directly (security
   delimiters pre-applied). Store overlay paths from `skill_overlay_path`.
```

~15 lines replacing the current ~62. Steps 1–2 of the old Session Initialization (pilot resolution, profile loading) are handled by the boot hook. Steps 3–4 (staleness check, persona loading) are Claude's runtime responsibility and must be retained. Step 5 (fresh install) is derived from the boot JSON.

**Implementation gate:** Do not implement Phase 4 until Phase 0's `dev/reviews/context-efficiency-baseline.md` contains a `## Boot Hook JSON Schema` section documenting the exact field paths. Replace `state.fresh_install`, `diagnostics.warnings`, and `persona.name` in the draft above with the actual field paths from that schema.

**Exit criterion:** After applying Phase 4, run 5 fresh sessions: (1) default persona, (2) non-default persona with RP enabled, (3) stale persona context (faction mismatch), (4) fresh install (no profile), (5) persona with RP off. All must initialize correctly.

### Phase 5: Skill file rationalization (ongoing, per ADR-006)

This phase applies ADR-006's migration approach to the remaining large skills, with one clarification: **the standard for what survives in SKILL.md**.

#### Skill file structure standard

Every SKILL.md should follow this structure:

```markdown
---
(YAML frontmatter: triggers, prerequisite_files, data_sources, esi_scopes)
---

## Required Tool Calls
(Table: tool → action → when to use)

## Output Format
(Template or description of expected response structure)

## Edge Cases
(Numbered list of empirically observed failure modes with corrections.
Each must be a real mistake Claude has made, not a hypothetical.)

**Classification pragmatics:** No systematic log of Claude's past failures exists. The implementing agent applies the four-criteria test (empirically observed, non-obvious, consequential, not fixable by data injection). When evidence is ambiguous, classify as `guardrail-empirical` and retain — the cost of keeping a speculative guardrail (a few extra tokens) is lower than removing a load-bearing one (a regression). Guardrails classified `guardrail-speculative` in Phase 0 are removed in Phase 5 and validated by regression testing.

## Anti-Patterns
(Brief list of specific wrong behaviors with right alternatives.)

## Behavior
(Persona adaptation, experience adaptation, contextual suggestions.)
```

**What gets cut from existing large skills:**

| Pattern to remove | Example | Why |
|-------------------|---------|-----|
| Restating prerequisite file content | "Drone damage types are: thermal (Hobgoblin)..." when `drones.json` is a prerequisite | Data is already loaded |
| Step-by-step validation procedures | "Step 1: Parse EFT. Step 2: Validate ship. Step 3: Check modules..." | Claude follows tool output naturally |
| Speculative guardrails | "DO NOT recommend faction modules to new players" | Claude reads the profile and adapts |
| Response format templates >20 lines | 90-line mission-brief template | Keep essential fields, trust Claude for formatting |
| "Prerequisites" prose section | "You MUST read drones.json before proceeding" | Already declared in frontmatter and handled by skill loading mechanism |

**Estimated impact on top 5 skills:**

| Skill | Current lines | Estimated target | Reduction |
|-------|--------------|-----------------|-----------|
| mission-brief | 448 | ~200 | -55% |
| skillplan | 391 | ~180 | -54% |
| fitting | 357 | ~180 | -50% |
| threat-assessment | 208 | ~120 | -42% |
| hunting-grounds | 158 | ~100 | -37% |

Note: threat-assessment and hunting-grounds are smaller than initially estimated. The average reduction across the top 5 is ~48%, not ~51%. Precise targets will be set after Phase 0 line classification.

#### Oversized prerequisite files

Phase 5 should also investigate whether oversized prerequisite files (particularly `skillplan`'s ~61,000 lines of YAML) can be made lazy-loadable — i.e., load only the subsection relevant to the user's query rather than the entire file. This is a structural change to the data files and the skill loading mechanism, not just a SKILL.md trim, so it should be scoped as a separate sub-task within Phase 5. If lazy loading is infeasible, document why and accept the cost.

### Phase 6: Dead code and artifact cleanup

| Item | Action | Prerequisite | Size recovered |
|------|--------|-------------|---------------|
| `reference/archetypes/` | Delete if present; no-op if absent | Phase 0 baseline audit must verify directory existence. **If present:** Inline 5–10 representative EFT fits into fitting and skillplan SKILL.md files before deletion. Selection: one T1 or faction hull per class (frigate, destroyer, cruiser, battlecruiser, battleship); ensure diversity of weapon systems (at least one drone boat, one turret boat) and tank types (at least one armor, one shield). Target: ~3 fits into fitting SKILL.md, ~3 into skillplan SKILL.md. **If absent:** No-op — directory was already removed or never created. | 1.5 MB (if present) |
| `dev/reviews/exercise-outputs/` | Delete | None — git history preserves content | 1.5 MB |
| `context_budget.py` | Delete (dead code; git history preserves for reimplementation) | None | 136 lines |
| Legacy display functions in `boot-display.sh` | Delete lines 186-454 | Verify `aria-banner.sh` is not used (it invokes these functions for manual terminal display). If still used, either keep or port to a standalone script. | 268 lines |
| ~~`EXPERIENCE_ADAPTATION.md`~~ | ~~Superseded by Phase 3 merge~~ | ~~Phase 3 complete~~ | ~~109 lines~~ — **No-op:** Phase 3 now deletes all 6 source files |
| ~~`COMMAND_SUGGESTIONS.md`~~ | ~~Superseded by Phase 3 merge~~ | ~~Phase 3 complete~~ | ~~129 lines~~ — **No-op:** Phase 3 now deletes all 6 source files |

---

## Risk Assessment

### Risk: Removing behavioral policy causes regression

**Severity:** Medium
**Mitigation:** Phase 0 establishes baselines. After each phase, run the top 5 skills through representative queries and compare output quality. The `aria-review` infrastructure already supports this.

**Key insight:** If a guardrail was preventing a hallucination, removing it will produce a visible regression in testing. If removing it produces no change, it wasn't doing anything. Either outcome is informative.

### Risk: Reduced CLAUDE.md causes session initialization failures

**Severity:** Low
**Mitigation:** Steps 1–2 of Session Initialization are narration of the boot hook's work — removing them doesn't break the mechanism. Steps 3–4 (staleness check, persona loading) are retained in simplified form since they are Claude's runtime actions. Test with 5 fresh sessions after Phase 4, including at least one with a non-default persona and one with a stale persona context.

### Risk: Contributors add content to the wrong layer

**Severity:** Medium (the original cause of accretion)
**Mitigation:** ADR-006 already defines the ownership rules. This proposal adds the *Edge Cases test* (empirical, non-obvious, consequential, not fixable by data injection) as a concrete rubric for evaluating new guardrails. Add this rubric to a contributor guide or the skill migration guide.

### Risk: Consolidated ai-runtime docs lose useful information

**Severity:** Low
**Mitigation:** The three case studies are preserved. The trust hierarchy is preserved. What's removed is process narration that describes how Claude should think — which is not something that can be controlled through instruction. The git history preserves the original documents if anything needs recovery.

### Rollback strategy

Each phase ships as a single PR. If regression testing (Phase 0 prompts) reveals a problem after a phase merges, the response is:

1. **Revert the PR** — each phase is scoped to be independently revertible
2. **Diagnose** — identify which removed content was load-bearing
3. **Re-apply with the load-bearing content restored** — the revert is temporary, not a permanent rollback

This requires discipline in Phase scoping: a Phase must not depend on another Phase's changes being present (except where explicit dependencies exist in the dependency graph). Phases 1–3 are independent by design. Phase 4 depends on Phase 1. Phase 6 depends on Phases 3 and 5.

---

## Success Metrics

| Metric | Baseline (current) | Target | How to measure |
|--------|-------------------|--------|----------------|
| Always-loaded token cost | ~11,500 tokens | ~6,500 tokens | `cl100k_base` tokenizer on CLAUDE.md + AGENTS.md + boot JSON + persona |
| CLAUDE.md lines | 532 | ~290 | `wc -l` |
| AGENTS.md lines | 61 | ~20 | `wc -l` |
| ai-runtime doc total lines | 1,219 | ~350 | `wc -l dev/docs/ai-runtime/*.md` |
| Top-5 skill average lines | ~312 | ~156 | `wc -l` on fitting (357), mission-brief (448), skillplan (391), threat-assessment (208), hunting-grounds (158) |
| Hallucination rate on EVE facts | Phase 0 baseline prompts | No regression | Run Phase 0 regression prompts (2–3 per top-5 skill) after each phase. Regression = factually wrong EVE claim that baseline got right. |
| Session functionality | (baseline test suite) | No regression | Run `/help`, `/fitting`, `/mission-brief`, `/price`, `/orient` after each phase |

---

## Implementation Order and Dependencies

```
Phase 0 (baselines)
  │
  ├──→ Phase 1 (CLAUDE.md)  ──→ Phase 4 (boot/CLAUDE.md boundary)
  │
  ├──→ Phase 2 (AGENTS.md)         (independent)
  │
  ├──→ Phase 3 (ai-runtime docs)   (independent)
  │
  └──→ Phase 5 (skill files)       (independent, ongoing)
            │
            └──→ Phase 6 (cleanup)  (after skills stabilize)
```

Phases 1–3 are independent and can proceed in parallel. Phase 4 depends on Phase 1 (CLAUDE.md must be slimmed before restructuring the boot boundary). Phase 5 is ongoing and can start in parallel. Phase 6 is cleanup that follows naturally.

Each phase is an independent, reviewable change. No big-bang rewrite.

---

## Appendix: The Anti-Hallucination Model

This is the mental model underlying the entire proposal:

**Claude hallucinating EVE data has three root causes:**

1. **Authoritative data is not in context.** Claude has no choice but to use training data. This is a *data availability* problem.

2. **Authoritative data is in context but Claude misapplies it.** The data is there, but Claude's reasoning about EVE mechanics is wrong (e.g., mixing armor and shield tank concepts). This is a *domain reasoning* problem.

3. **Multi-tool synthesis errors.** No single tool answers the question; Claude must combine outputs from multiple tools (or tool outputs with general knowledge) and makes errors in the synthesis. Example: "What's a good system for ratting near Amarr?" requires combining `universe(action="search")` with `universe(action="activity")` with game knowledge about ratting mechanics. Each data source is correct; the error is in how they're combined.

**Cause 1 is solved by `prerequisite_files` and MCP tools.** Make the right data available and Claude uses it. No behavioral policy needed.

**Cause 2 is solved by targeted edge-case guardrails.** When Claude consistently misapplies a specific mechanic (mixed tank, drone damage types, System Core behavior), a 2-3 line guardrail in the relevant skill corrects the specific error.

**Cause 3 is partially mitigated by skill workflows** that prescribe the tool-call sequence for complex queries. This is the one area where procedural instructions in SKILL.md earn their tokens — not as "verification checklists" but as *query orchestration* that ensures the right combination of tools is called. The `Required Tool Calls` section in the skill file structure standard (Phase 5) serves this purpose.

**None of these causes are solved by:**
- Process checklists ("Step 1: Check if you have the data. Step 2: If not, query the tool...")
- Repeated "DO NOT" instructions across multiple locations
- Flowcharts describing verification workflows
- Documents teaching Claude "how to think about" data trust

These feel productive because they address the anxiety of "what if Claude gets it wrong." But they don't actually reduce the probability of error — they only reduce the probability that the *instruction layer* lacks coverage. The instruction layer isn't the bottleneck. Data availability, targeted guardrails, and query orchestration are.
