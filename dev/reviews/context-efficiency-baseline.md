# Context Efficiency Baseline Metrics

**Date:** 2026-02-27
**Proposal:** `dev/proposals/CONTEXT_EFFICIENCY_PROPOSAL.md`
**Phase:** 0 — Establish baselines

---

## Token Counts

Token estimates use word count × 1.3 approximation (cl100k_base cross-check).

### Always-Loaded Files

| File | Lines | Words | Est. Tokens |
|------|------:|------:|------------:|
| CLAUDE.md | 531 | 3,096 | ~4,025 |
| .claude/AGENTS.md | 61 | 1,078 | ~1,401 |
| Boot hook JSON | ~30 | ~200 | ~260 |
| Persona files (when RP on) | ~100 | ~1,500 | ~1,950 |
| **Total (RP off)** | **~622** | **~4,374** | **~5,686** |
| **Total (RP on)** | **~722** | **~5,874** | **~7,636** |

### ai-runtime Docs (not auto-loaded, but referenced)

| File | Lines | Words | Est. Tokens |
|------|------:|------:|------------:|
| DATA_VERIFICATION.md | 414 | 2,258 | ~2,935 |
| DATA_AUTHORITY.md | 307 | 1,678 | ~2,181 |
| PROTOCOLS.md | 125 | 801 | ~1,041 |
| DATA_FILES.md | 124 | 548 | ~712 |
| EXPERIENCE_ADAPTATION.md | 108 | 799 | ~1,039 |
| COMMAND_SUGGESTIONS.md | 128 | 714 | ~928 |
| **Total** | **1,206** | **6,798** | **~8,837** |

### Top 5 Skills

| Skill | Lines | Words | Est. Tokens |
|-------|------:|------:|------------:|
| fitting | 357 | 1,997 | ~2,596 |
| mission-brief | 448 | 2,223 | ~2,890 |
| skillplan | 391 | 2,163 | ~2,812 |
| threat-assessment | 208 | 1,276 | ~1,659 |
| hunting-grounds | 158 | 836 | ~1,087 |
| **Total** | **1,562** | **8,495** | **~11,044** |

---

## Line Classification — fitting (357 lines)

| Line Range | Category | Content | Notes |
|-----------|----------|---------|-------|
| 1-24 | metadata | YAML frontmatter | Keep |
| 26-45 | guardrail-empirical | Prerequisites (load files before building fits) | Keep — Claude hallucinates module names without reference data |
| 46-68 | procedure | Operational Constraints checking | Remove — Claude reads profile naturally |
| 69-90 | guardrail-empirical | Gear Tier Validation Protocol | Keep — Claude defaults to T2 without check |
| 92-102 | guardrail-empirical | Known Limitation: ammo lines misparsed as drones | Keep — EOS parser edge case |
| 103-218 | guardrail-empirical | Fit Validation Protocol (SDE verify, EOS validate, warnings) | Keep — Claude skips validation without explicit gate |
| 219-236 | format-template | Response Format (~18 lines) | Keep, compress slightly |
| 237-281 | data/reference | Tank Coherence Rules tables | Keep |
| 282-288 | procedure | Manufacturing Awareness | Remove |
| 289-310 | guardrail-empirical | Drone Selection Protocol | Keep — Claude gets drone damage types wrong |
| 312-322 | data/reference | Faction-Specific Fitting table | Keep |
| 323-345 | procedure | Behavior guidelines | Remove |
| 346-357 | procedure | Persona Adaptation | Remove |

**Summary:** ~140 lines removable (39%). Target: ~220 lines.

---

## Line Classification — mission-brief (448 lines)

| Line Range | Category | Content | Notes |
|-----------|----------|---------|-------|
| 1-30 | metadata | YAML frontmatter | Keep |
| 34-60 | format-template | Response Format header template | Keep, compress to ~15 lines |
| 61-138 | format-template | Experience-level adaptation templates | Remove — Claude adapts natively |
| 139-159 | guardrail-empirical | Mission Disambiguation (never assume faction/level) | Keep |
| 160-197 | procedure | AskUserQuestion flow, cache retrieval | Remove |
| 198-238 | guardrail-empirical | Intel Retrieval (trusted sources: wiki.eveuniversity.org only) | Keep core rule |
| 239-291 | procedure | Special:Search Method, keyword extraction | Remove |
| 292-321 | procedure | Zero Results Clarification | Keep core (5 lines), remove procedure |
| 323-375 | procedure | Cache File Format | Remove |
| 383-420 | guardrail-empirical | Fit Adaptation validation gate + Gear Tier | Keep |
| 422-448 | procedure | Behavior notes, persona adaptation | Remove |

**Summary:** ~250 lines removable (56%). Target: ~200 lines.

---

## Line Classification — skillplan (391 lines)

| Line Range | Category | Content | Notes |
|-----------|----------|---------|-------|
| 1-24 | metadata | YAML frontmatter | Keep |
| 29-52 | guardrail-empirical | MCP availability + hallucination guard | Keep — Claude fabricates training times |
| 54-70 | data/reference | Field→Source Mapping table | Keep |
| 72-74 | guardrail-empirical | current_skills requirement | Keep |
| 76-114 | procedure | Freshness Gate, skills loading CLI | Remove |
| 115-132 | guardrail-empirical | Golden Path + anti-pattern | Keep |
| 134-199 | procedure | Execution Flow steps | Remove |
| 216-242 | format-template | Response Format template (27 lines) | Remove |
| 244-291 | procedure | Item Type Handling | Remove |
| 299-365 | procedure | Error Handling, Example Outputs | Remove |
| 370-382 | guardrail-empirical | Anti-Patterns section | Keep |
| 384-392 | procedure | Behavior Notes | Remove |

**Summary:** ~240 lines removable (61%). Target: ~150 lines.

---

## Line Classification — threat-assessment (208 lines)

| Line Range | Category | Content | Notes |
|-----------|----------|---------|-------|
| 1-16 | metadata | YAML frontmatter | Keep |
| 20-41 | guardrail-empirical | Required Tool Calls, include_realtime=True | Keep |
| 43-54 | data/reference | Field→Source Mapping | Keep |
| 56-69 | procedure | Live Activity Intel explanation | Remove |
| 71-81 | data/reference | Activity Data Interpretation table | Keep |
| 83-133 | format-template | Response Format (~50 lines) | Compress to ~20 lines |
| 135-145 | procedure | When to Query Activity Data | Remove |
| 147-161 | guardrail-empirical | Sovereignty-aware assessment | Keep |
| 163-178 | data/reference | FW and Threat Level definitions | Keep |
| 180-193 | procedure | Behavior guidelines, experience adaptation | Remove |
| 195-208 | guardrail-empirical | Anti-Patterns | Keep |

**Summary:** ~60 lines removable (29%). Target: ~150 lines.

---

## Line Classification — hunting-grounds (158 lines)

| Line Range | Category | Content | Notes |
|-----------|----------|---------|-------|
| 1-16 | metadata | YAML frontmatter | Keep |
| 20-26 | procedure | Command Syntax | Remove |
| 28-42 | guardrail-empirical | Required Tool Calls, search radius guardrail | Keep |
| 44-52 | procedure | Live Activity Intel explanation | Remove |
| 54-86 | format-template | Response Format (~33 lines) | Compress to ~15 lines |
| 88-117 | data/reference | Metrics tables (Traffic, Marks, Competition) | Keep |
| 118-127 | procedure | Coalition Intelligence, Multiple Systems | Remove |
| 129-148 | procedure | Behavior Notes, Experience Adaptation | Remove |
| 149-158 | guardrail-empirical | Anti-Patterns | Keep |

**Summary:** ~70 lines removable (44%). Target: ~90 lines.

---

## Boot Hook JSON Schema

Source: `.claude/hooks/aria-boot.d/boot-display.sh` → `output_json_context()`

### Root Fields

| Path | Type | Description |
|------|------|-------------|
| `aria_boot.version` | String | Schema version (`"2.0"`) |
| `aria_boot.timestamp` | String | Boot timestamp (`YYYY.MM.DD HH:MM:SS`) |
| `aria_boot.source` | String | Event type: `startup`, `resume`, `clear`, `compact`, `fresh_install` |
| `pilot.id` | String/null | Active pilot character ID |
| `pilot.name` | String/null | Active pilot character name |
| `pilot.count` | Number | Total configured pilots |
| `pilot.selection_needed` | Boolean | True if multi-pilot and no selection made |
| `config.status` | String | `OK`, `WARNINGS`, `CRITICAL`, `NOT_CONFIGURED` |
| `esi.status` | String | `SYNCED`, `CHANGES_DETECTED`, `CONFIGURED`, `NOT_CONFIGURED` |
| `esi.reason` | String/null | Explanation for ESI status |
| `esi.changes` | Array[String] | Detected changes list |
| `persona.name` | String | Persona name (`ARIA`, `PARIA`, etc.) |
| `persona.subtitle` | String | Full persona subtitle |
| `state.fresh_install` | Boolean | True if no pilots configured |
| `state.credentials` | Boolean | True if ESI credentials exist |
| `diagnostics.warnings` | Array[String] | Non-critical boot issues |
| `diagnostics.errors` | Array[String] | Critical boot issues |
| `guidance.message` | String | Fresh install only: setup guidance |
| `guidance.commands` | Array[String] | Fresh install only: suggested commands |

### Key Observations for Phase 4

1. **Pilot resolution (Session Init step 1):** Fully covered by `pilot.*` fields
2. **Profile loading (Session Init step 2):** Covered by `config.status` and `pilot.*`
3. **Fresh install (Session Init step 5):** Covered by `state.fresh_install`
4. **Persona detection:** Covered by `persona.*` fields
5. **Staleness check (Session Init step 3):** NOT in boot JSON — Claude's runtime responsibility
6. **Persona artifact loading (Session Init step 4):** NOT in boot JSON — Claude's runtime responsibility

---

## Regression Test Prompts

### fitting

**Prompt 1:** "Fit a Vexor for level 2 missions" (exercises: SDE name verification, EOS validation, drone selection from drones.json, gear tier check)
- **Guardrails exercised:** Fit Validation Protocol, Drone Selection Protocol, Gear Tier Validation
- **Expected:** T1/meta modules, correct drone damage type from drones.json, EOS-validated fit

**Prompt 2:** "Add a Medium Armor Repairer to my Caracal shield fit" (exercises: mixed tank detection)
- **Guardrails exercised:** Tank Coherence Rules
- **Expected:** Warning about armor module on shield-tanked ship

### mission-brief

**Prompt 1:** "Brief me on The Blockade level 4" (exercises: mission disambiguation, trusted source, fit adaptation)
- **Guardrails exercised:** Mission Disambiguation, Intel Retrieval (wiki only), Gear Tier Validation
- **Expected:** Correct faction identification, damage/tank recommendations from npc_damage_types.md

**Prompt 2:** "Mission brief for some random mission name that doesn't exist" (exercises: zero results handling)
- **Guardrails exercised:** Zero Results Clarification
- **Expected:** Clear "not found" message, no fabricated mission data

### skillplan

**Prompt 1:** "What skills do I need for a Dominix?" (exercises: easy_80_plan tool usage, no fabricated times)
- **Guardrails exercised:** Hallucination Guard, Golden Path, anti-pattern (no redundant SDE call)
- **Expected:** All training times from MCP response only, current_skills passed

**Prompt 2:** "How long to train into a Tengu?" (exercises: training time accuracy)
- **Guardrails exercised:** current_skills requirement, training time from tool only
- **Expected:** Delta-based training times (not from-scratch), clear if ESI unavailable

### threat-assessment

**Prompt 1:** "Is Tama safe to travel through?" (exercises: live data requirement, include_realtime)
- **Guardrails exercised:** include_realtime=True, tool-sourced data only
- **Expected:** All kill/jump data from MCP call, include_realtime=True used

**Prompt 2:** "Threat assessment for 1DQ1-A" (exercises: sovereignty data from tools)
- **Guardrails exercised:** Sovereignty-aware assessment, anti-patterns
- **Expected:** Sovereignty data from universe(action="systems") call, not training data

### hunting-grounds

**Prompt 1:** "Find hunting grounds within 5 jumps of Hek" (exercises: search radius respect)
- **Guardrails exercised:** Search radius guardrail, tool-sourced data only
- **Expected:** Only systems within 5 jumps, all metrics from hotspots/activity calls

**Prompt 2:** "Where should I hunt near Rancer?" (exercises: fabrication prevention)
- **Guardrails exercised:** Anti-patterns (no invented group names without killmail data)
- **Expected:** Activity data from tools only, no fabricated hunter group names
