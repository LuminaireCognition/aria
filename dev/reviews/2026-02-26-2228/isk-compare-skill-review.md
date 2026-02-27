# Skill Review: isk-compare

**Skill Path:** `.claude/skills/isk-compare/SKILL.md`
**Review Timestamp:** 2026-02-26-2228
**Files in skill directory:** `SKILL.md` (1 file, 384 lines)

---

## 1. Executive Summary

The isk-compare skill is the most bloated skill in this review batch. Over 60% of the file consists of inlined ISK estimate tables (lines 152-221, pattern A) that duplicate the declared `reference/activities/isk_estimates.yaml` data source, plus pseudo-code that Claude will never execute (lines 127-131, 312-325). The skill has no MCP integration and relies on ESI CLI calls with a profile-based fallback, but the grounding discipline is undermined by the massive volume of inlined reference data that invites hallucination when numbers change.

---

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :yellow_circle: | No MCP dispatcher exists for ISK comparison. ESI skills/standings via CLI is appropriate. However, the skill should use `sde(action="skill_requirements")` for access gate validation instead of inlining skill tables. |
| Prompt hygiene | :red_circle: | The skill inlines ~70 lines of ISK/hour estimates (lines 152-221) while declaring `reference/activities/isk_estimates.yaml` as a data source. This creates a dual-source problem: Claude may use the inline data instead of reading the YAML file. |
| Failure handling | :green_circle: | ESI unavailable fallback to profile data is well-designed (lines 59-83). Clear degradation path. |
| Context window efficiency | :red_circle: | 384 lines for a recommendation skill is excessive. ISK tables, pseudo-code, access gate table, recommendation logic, effort/variance classifications, and standing integration code consume enormous token budget for what is fundamentally "read profile + read reference YAML + present comparison." |

---

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 50-83 | "ESI Availability Check" block -- duplicates CLAUDE.md system behavior (pattern B) | **REMOVE** | ~250 tokens |
| `SKILL.md` | 84 | "Rationale:" line in profile-based fallback (pattern D) | **REMOVE** | ~15 tokens |
| `SKILL.md` | 102-121 | "Determine Accessible Activities" table -- inlined reference data (pattern A) duplicating what should come from `isk_estimates.yaml` requirements field | **REMOVE** | ~200 tokens |
| `SKILL.md` | 118-121 | "Mission access is gated by standings" explanation paragraph -- justification prose (pattern D) | **REMOVE** | ~50 tokens |
| `SKILL.md` | 123-131 | "Calculate Estimated ISK/Hour" section with pseudo-code -- Claude doesn't execute Python; this is noise | **REMOVE** | ~80 tokens |
| `SKILL.md` | 150-221 | All ISK estimate tables (Mission Running, Exploration, Mining, Passive, Combat Anomalies, DED Sites) -- pattern A, duplicates `reference/activities/isk_estimates.yaml` | **REMOVE** | ~600 tokens |
| `SKILL.md` | 222-258 | Full response format ASCII box template (pattern E) -- 36 lines of box art | **CONSOLIDATE** | ~300 tokens |
| `SKILL.md` | 260-284 | "Recommendation Logic" section with SP-based tiers -- opinionated guidance that should come from reference data, not inline | **CONSOLIDATE** | ~150 tokens |
| `SKILL.md` | 286-305 | Effort level, risk tolerance, and variance classification tables -- reference data that belongs in `isk_estimates.yaml` metadata | **REMOVE** | ~150 tokens |
| `SKILL.md` | 307-325 | "Standing Integration" section with Python pseudo-code -- Claude doesn't execute this; standing checks come from ESI | **REMOVE** | ~150 tokens |
| `SKILL.md` | 327-334 | Error handling table -- 3 generic cases that don't need a table | **CONSOLIDATE** | ~60 tokens |
| `SKILL.md` | 336-343 | "Caveats to Include" section -- generic disclaimers | **REMOVE** | ~60 tokens |
| `SKILL.md` | 345-352 | "Integration with Other Skills" cross-reference table | **REMOVE** | ~60 tokens |
| `SKILL.md` | 354-376 | "Economic Advisory Protocol" section -- partially duplicates CLAUDE.md operational constraints and profile reading | **CONSOLIDATE** | ~200 tokens |

**Total estimated savings: ~2,325 tokens (~60% of file)**

---

## 4. Specific Findings

### High Severity

**H1. ISK estimate tables duplicate declared data source (lines 150-221, pattern A)**
The skill declares `reference/activities/isk_estimates.yaml` in its `data_sources` frontmatter, yet inlines 70+ lines of ISK/hour tables covering 6 activity categories. This is the textbook pattern A violation: the same data exists in two places, creating staleness risk and giving Claude permission to skip reading the authoritative YAML file. All inline ISK data must be removed, replaced with: "Read `reference/activities/isk_estimates.yaml` for all ISK/hour baselines, requirements, and variance data."

**H2. Python pseudo-code pollutes the prompt (lines 127-131, 312-325)**
Two blocks of Python code (`calculate_skill_bonus`, `get_mission_access`) will never be executed by Claude. They consume ~230 tokens describing algorithms that Claude should implement via natural reasoning over the data. Remove entirely.

**H3. ESI availability check duplicates CLAUDE.md (lines 50-83, pattern B)**
Same boilerplate as every other ESI skill. System-level mechanism, not skill-specific.

### Medium Severity

**M1. Access gate table partially duplicates reference YAML (lines 102-121)**
The "Determine Accessible Activities" table maps activities to skill/standing requirements. This data should live in `isk_estimates.yaml` (or already does), not be inlined.

**M2. Economic Advisory Protocol is partially redundant with CLAUDE.md (lines 354-376)**
The protocol to check operational constraints before recommending activities is valid skill behavior, but the "ARIA MUST" framing and validation template duplicate the profile-reading system behavior. Consolidate to: "Validate each recommendation against the pilot's operational constraints (profile.md). State which constraints were checked."

**M3. Response format is oversized (lines 222-258, pattern E)**
A 36-line ASCII box template with sample data. A 10-line compact example would steer identically.

### Low Severity

**L1. Recommendation logic hardcodes SP tiers (lines 260-284)**
SP-based recommendation tiers (< 5M, 5-15M) are hardcoded opinion. This should either live in the reference YAML or be removed in favor of skills-based analysis from ESI data.

**L2. Caveats section is boilerplate (lines 336-343)**
Generic disclaimers like "Market prices fluctuate" don't improve output quality. Remove.

---

## 5. Prioritized Recommendations

1. **Remove** all inlined ISK estimate tables (lines 150-221) -- replace with imperative reference to `isk_estimates.yaml`. This is the single highest-impact change.
2. **Remove** Python pseudo-code blocks (lines 127-131, 312-325) -- Claude reasons over data, not code.
3. **Remove** ESI availability check (lines 50-83) -- system-level duplication.
4. **Remove** access gate table (lines 102-121) -- consolidate into `isk_estimates.yaml`.
5. **Consolidate** response format (lines 222-258) into a compact 10-line template.
6. **Consolidate** Economic Advisory Protocol (lines 354-376) into 3 imperative lines.
7. **Remove** effort/variance/risk classification tables (lines 286-305) -- move metadata to YAML.
8. **Remove** caveats and cross-reference sections (lines 336-352).
