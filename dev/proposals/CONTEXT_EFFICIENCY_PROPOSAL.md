# ARIA Context Efficiency Proposal

**Status:** Draft
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

1. CLAUDE.md drops from ~530 lines to ~280 lines (-47%)
2. AGENTS.md drops from 61 lines to ~20 lines (-67%)
3. Six ai-runtime docs (1,212 lines total) consolidate to two (~350 lines, -71%)
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

A skill invocation adds 800–4,000 tokens (SKILL.md) plus 0–5,000 tokens (prerequisite files). Complex interactions easily exceed 20,000 tokens of instruction before Claude generates a single word of output.

This matters because context window is a finite resource. Every token spent on instructions is a token unavailable for conversation history, tool outputs, and reasoning. The tradeoff is justified only when the instruction actually changes Claude's behavior.

### 2. Behavioral policy that doesn't change behavior

Several instruction documents teach Claude things it already does:

| Document | Lines | What it teaches | Claude's native capability |
|----------|-------|-----------------|---------------------------|
| `EXPERIENCE_ADAPTATION.md` | 109 | Adjust depth by audience | Core LLM capability |
| `COMMAND_SUGGESTIONS.md` | 129 | Suggest commands naturally | Contextual awareness |
| `DATA_VERIFICATION.md` (non-case-study sections) | ~200 | "Check tools before claiming" | Already expressed in one Prime Directive line |

These documents exist because Claude *once* got something wrong, and the response was to write a document preventing that specific failure. But the documents don't actually prevent future failures — they add tokens. The case studies in DATA_VERIFICATION.md are genuinely useful (they show *what* Claude gets wrong), but the process checklists and flowcharts are not (they describe *how to think*, which Claude cannot be instructed to do mechanistically).

### 3. Dual initialization

The boot hook resolves pilot identity, detects persona, validates security, syncs ESI, and outputs structured JSON. CLAUDE.md then describes this same 5-step process in 62 lines of prose, instructing Claude to... do what the boot hook already did.

The boot hook's JSON output already tells Claude who the pilot is, what persona to use, and whether ESI is configured. The CLAUDE.md procedure is a redundant narration of completed work.

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

Claude Code natively discovers skills from `.claude/skills/*/SKILL.md`. The AGENTS.md file (61 lines) re-lists all 43 skills with descriptions and file paths, plus usage instructions that largely restate Claude Code's built-in skill handling. The system-reminder in the conversation already lists all available skills.

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
| **CLAUDE.md** | Identity, security, infrastructure mechanisms | Every session | Target: ~3,500 tokens (from ~6,500) |
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

1. Count tokens in current CLAUDE.md, AGENTS.md, and each ai-runtime doc
2. For the top 5 skills by size (fitting, mission-brief, skillplan, threat-assessment, hunting-grounds), classify every line as: guardrail (empirical), guardrail (speculative), data/reference, procedure, or format template
3. Document the boot hook's JSON output schema (what Claude already receives)

**Deliverable:** Baseline metrics file at `dev/reviews/context-efficiency-baseline.md`

### Phase 1: Slim CLAUDE.md (-47%, ~3,500 tokens target)

**Remove entirely:**

| Section | Lines | Reason |
|---------|-------|--------|
| Session Initialization steps 1-5 | 62 | Boot hook does this; Claude receives the JSON result |
| Static Game Data References table | 53 | Move references into relevant skills' `prerequisite_files` |
| Universe Navigation MCP dispatcher table | 61 | Tool descriptions already enumerate actions |
| Notification Profiles quick-start | 28 | Belongs in docs, not always-loaded context |
| Configuration Change Protocol | 10 | Rare operation; belongs in dev docs |
| "Do NOT Write Inline Python" section | 7 | Covered by MCP tool availability |

**Simplify:**

| Section | Current lines | Target lines | Change |
|---------|--------------|-------------|--------|
| MCP Fallback Behavior | 21 | 5 | Keep table, remove prose |
| Skill Loading | 69 | 25 | Keep mechanism, remove path validation details (move to dev doc) |
| Persona Loading | 26 | 10 | Keep pointer to compiled artifact, remove example YAML |
| `sde` vs `skills` disambiguation | 20 | 10 | Keep table, remove examples |
| Reference Documentation table | 24 | 12 | Remove docs that are dev-only |

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

**Rationale:** Claude Code already provides skill discovery through the system-reminder. AGENTS.md's 43-line skill registry is redundant. The "How to use skills" section largely restates Claude Code's native behavior. Keep only the two things Claude Code doesn't handle natively: `uv run` requirement and `prerequisite_files` gate.

### Phase 3: Consolidate ai-runtime docs (-71%, ~350 lines from 1,212)

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

Removes:
- 5 detailed explanation example pairs from EXPERIENCE_ADAPTATION.md (Claude does audience adaptation natively)
- Progressive revelation flow from COMMAND_SUGGESTIONS.md (Claude does progressive disclosure natively)
- Good/bad example pairs from COMMAND_SUGGESTIONS.md (teaching natural language use to an LLM)
- Redundant "Recommended Phrasing" section from PROTOCOLS.md
- "Query Triggers" detail from PROTOCOLS.md (when to query is obvious from the data type)

**Neither file is auto-loaded.** They exist as development reference and for onboarding contributors. CLAUDE.md does not need to reference them — the principles that matter are already in the Prime Directives.

### Phase 4: Rationalize boot hook ↔ CLAUDE.md boundary

**Principle:** The boot hook *does things and reports results*. CLAUDE.md *tells Claude how to interpret the results*. No overlap.

**Boot hook keeps:** Pilot resolution, persona detection, ESI sync, security checks, JSON output.

**CLAUDE.md changes:**

Replace the 62-line Session Initialization section with:

```markdown
## Session Context

The boot hook outputs JSON with pilot identity, persona, ESI status, and
diagnostics. Use this data directly — do not re-resolve pilot or persona.

If `state.fresh_install` is true, offer `/setup`.
If `diagnostics.warnings` is non-empty, mention them briefly.
If `persona.name` is not "ARIA", load the compiled persona artifact from
`userdata/pilots/{pilot.id}/…/.persona-context-compiled.json`.
```

~8 lines replacing 62. The boot hook JSON is self-descriptive; Claude doesn't need a procedure to interpret `"fresh_install": true`.

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
| mission-brief | 449 | ~200 | -55% |
| skillplan | 392 | ~180 | -54% |
| fitting | 358 | ~180 | -50% |
| threat-assessment | ~300 (est.) | ~150 | -50% |
| hunting-grounds | ~250 (est.) | ~130 | -48% |

### Phase 6: Dead code and artifact cleanup

| Item | Action | Size recovered |
|------|--------|---------------|
| `reference/archetypes/` | Delete (zero Python imports per accretion audit) | 1.5 MB |
| `dev/reviews/exercise-outputs/` | Archive to separate branch or delete | 1.5 MB |
| `context_budget.py` | Delete or implement (currently dead code) | 136 lines |
| Legacy display functions in `boot-display.sh` | Delete (lines 186-454, all marked "legacy") | 268 lines |
| `EXPERIENCE_ADAPTATION.md` | Superseded by Phase 3 merge | 109 lines |
| `COMMAND_SUGGESTIONS.md` | Superseded by Phase 3 merge | 129 lines |

---

## Risk Assessment

### Risk: Removing behavioral policy causes regression

**Severity:** Medium
**Mitigation:** Phase 0 establishes baselines. After each phase, run the top 5 skills through representative queries and compare output quality. The `aria-review` infrastructure already supports this.

**Key insight:** If a guardrail was preventing a hallucination, removing it will produce a visible regression in testing. If removing it produces no change, it wasn't doing anything. Either outcome is informative.

### Risk: Reduced CLAUDE.md causes session initialization failures

**Severity:** Low
**Mitigation:** The boot hook's JSON output is the actual initialization mechanism. CLAUDE.md's Session Initialization section is narration, not mechanism. Removing the narration doesn't break the mechanism. Test with 5 fresh sessions after Phase 4.

### Risk: Contributors add content to the wrong layer

**Severity:** Medium (the original cause of accretion)
**Mitigation:** ADR-006 already defines the ownership rules. This proposal adds the *Edge Cases test* (empirical, non-obvious, consequential, not fixable by data injection) as a concrete rubric for evaluating new guardrails. Add this rubric to a contributor guide or the skill migration guide.

### Risk: Consolidated ai-runtime docs lose useful information

**Severity:** Low
**Mitigation:** The three case studies are preserved. The trust hierarchy is preserved. What's removed is process narration that describes how Claude should think — which is not something that can be controlled through instruction. The git history preserves the original documents if anything needs recovery.

---

## Success Metrics

| Metric | Baseline (current) | Target | How to measure |
|--------|-------------------|--------|----------------|
| Always-loaded token cost | ~11,500 tokens | ~6,500 tokens | Count tokens in CLAUDE.md + AGENTS.md + boot JSON + persona |
| CLAUDE.md lines | 532 | ~280 | `wc -l` |
| AGENTS.md lines | 61 | ~20 | `wc -l` |
| ai-runtime doc total lines | 1,212 | ~350 | `wc -l dev/docs/ai-runtime/*.md` |
| Top-5 skill average lines | ~390 | ~170 | `wc -l` on fitting, mission-brief, skillplan, threat-assessment, hunting-grounds |
| Hallucination rate on EVE facts | (unmeasured) | No regression | Manual testing of domain-specific queries per skill |
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

**Claude hallucinating EVE data has exactly two root causes:**

1. **Authoritative data is not in context.** Claude has no choice but to use training data. This is a *data availability* problem.

2. **Authoritative data is in context but Claude misapplies it.** The data is there, but Claude's reasoning about EVE mechanics is wrong (e.g., mixing armor and shield tank concepts). This is a *domain reasoning* problem.

**Cause 1 is solved by `prerequisite_files` and MCP tools.** Make the right data available and Claude uses it. No behavioral policy needed.

**Cause 2 is solved by targeted edge-case guardrails.** When Claude consistently misapplies a specific mechanic (mixed tank, drone damage types, System Core behavior), a 2-3 line guardrail in the relevant skill corrects the specific error.

**Neither cause is solved by:**
- Process checklists ("Step 1: Check if you have the data. Step 2: If not, query the tool...")
- Repeated "DO NOT" instructions across multiple locations
- Flowcharts describing verification workflows
- Documents teaching Claude "how to think about" data trust

These feel productive because they address the anxiety of "what if Claude gets it wrong." But they don't actually reduce the probability of error — they only reduce the probability that the *instruction layer* lacks coverage. The instruction layer isn't the bottleneck. Data availability and targeted guardrails are.
