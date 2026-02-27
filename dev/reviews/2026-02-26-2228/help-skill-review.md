# Skill Review: help

**Skill path:** `.claude/skills/help/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File stats:** 873 lines, ~9,780 tokens

## 1. Executive Summary

The help skill is by far the largest of this batch at ~9,780 tokens and is almost entirely static content that could be auto-generated from `_index.json`. The core problem is that 13 topic-specific help blocks (lines 200-787) are individually hand-maintained, totaling ~590 lines of box-formatted templates that will drift out of sync with the actual skills they describe. Additionally, the command listing itself (lines 28-113, 115-198) is duplicated in two formats (plain markdown and RP-formatted), which is Pattern G. The entire file should be replaced with a thin dispatcher that reads `_index.json` and generates help dynamically.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :yellow_circle: | Not MCP-backed. Data source is `_index.json` (declared in frontmatter). However, the skill inlines all command descriptions rather than reading them from `_index.json` at runtime — defeating the purpose of declaring the data source. |
| Prompt hygiene (data source freshness) | :red_circle: | All 50+ command descriptions are hardcoded in the skill file. When a skill is added, renamed, or its description changes, this file must be manually updated. No mechanism ensures synchronization with `_index.json`. |
| Failure handling | :green_circle: | Lines 858-873 handle unknown topics with a fallback listing. Adequate. |
| Context window efficiency | :red_circle: | 873 lines / ~9,780 tokens for a help command. The 13 topic-specific help blocks alone (lines 200-787) are ~4,800 tokens of static templates. The dual-format command listing (lines 28-198) adds ~1,400 tokens of duplication. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 115-198 | RP-formatted command listing — duplicate of the plain markdown listing at lines 28-113 (Pattern G) | REMOVE | ~700 tokens |
| `SKILL.md` | 200-232 | `/help aria-status` topic block | REMOVE | ~200 tokens |
| `SKILL.md` | 234-251 | `/help pilot` topic block | REMOVE | ~130 tokens |
| `SKILL.md` | 253-271 | `/help esi` topic block (first instance) | REMOVE | ~130 tokens |
| `SKILL.md` | 273-301 | `/help skillqueue` topic block | REMOVE | ~200 tokens |
| `SKILL.md` | 303-344 | `/help industry-jobs` topic block | REMOVE | ~270 tokens |
| `SKILL.md` | 346-365 | `/help missions` topic block | REMOVE | ~130 tokens |
| `SKILL.md` | 367-385 | `/help fitting` topic block | REMOVE | ~130 tokens |
| `SKILL.md` | 387-404 | `/help mining` topic block | REMOVE | ~110 tokens |
| `SKILL.md` | 406-424 | `/help exploration` topic block | REMOVE | ~130 tokens |
| `SKILL.md` | 426-453 | `/help threat` topic block | REMOVE | ~170 tokens |
| `SKILL.md` | 455-485 | `/help route` topic block | REMOVE | ~200 tokens |
| `SKILL.md` | 487-524 | `/help price` topic block | REMOVE | ~250 tokens |
| `SKILL.md` | 526-567 | `/help wallet-journal` topic block | REMOVE | ~270 tokens |
| `SKILL.md` | 569-589 | `/help journal` topic block | REMOVE | ~130 tokens |
| `SKILL.md` | 591-625 | `/help corp` topic block | REMOVE | ~220 tokens |
| `SKILL.md` | 627-644 | `/help data` topic block | REMOVE | ~110 tokens |
| `SKILL.md` | 646-675 | `/help esi` topic block (second instance — Pattern G duplicate) | REMOVE | ~180 tokens |
| `SKILL.md` | 677-702 | `/help experience` topic block | REMOVE | ~170 tokens |
| `SKILL.md` | 704-732 | `/help rp` topic block | REMOVE | ~190 tokens |
| `SKILL.md` | 734-759 | `/help faction` topic block | REMOVE | ~170 tokens |
| `SKILL.md` | 761-787 | `/help setup` topic block | REMOVE | ~170 tokens |
| `SKILL.md` | 789-815 | "Quick Start Guidance" section with box-formatted template | REMOVE | ~180 tokens |
| `SKILL.md` | 817-826 | "Show Database Index" section — duplicates reference/INDEX.md concern | REMOVE | ~60 tokens |
| `SKILL.md` | 828-856 | "Behavior Notes" and "Cross-References" tables — generic filler; cross-references duplicate the command listing | REMOVE | ~200 tokens |

**Total estimated savings:** ~4,800 tokens (~49%)

## 4. Specific Findings

### High Severity

**H1. All topic-specific help blocks are hand-maintained static content (Pattern A / staleness risk)**
- **File:** `SKILL.md`, lines 200-787
- 13+ topic help blocks hardcode command names, descriptions, triggers, options, and related commands. These will inevitably drift from the actual skills. The `_index.json` is declared as a data source but never actually used — all content is inlined.
- **Action:** REMOVE all topic blocks. Replace with a dynamic generation instruction: "For `/help <topic>`, read `_index.json` to find the matching skill entry. Present its description, triggers, and category. If the skill has `data_sources`, mention them. Do not maintain hardcoded topic descriptions."

**H2. Dual command listing is Pattern G duplication**
- **File:** `SKILL.md`, lines 28-113 (plain) and 115-198 (RP-formatted)
- The entire command listing appears twice in two formats. The RP format adds ~700 tokens. RP formatting is a persona overlay concern, not a skill concern.
- **Action:** REMOVE the RP-formatted listing (lines 115-198). Keep only the plain markdown version. If RP formatting is needed, it should come from a persona overlay or be derived at runtime from the plain listing.

**H3. `/help esi` topic appears twice (Pattern G)**
- **File:** `SKILL.md`, lines 253-271 and 646-675
- Two separate `/help esi` blocks with different content. This is direct duplication within the same file.
- **Action:** REMOVE both. See H1 — all topic blocks should be generated dynamically.

### Medium Severity

**M1. Command listing will drift from `_index.json`**
- **File:** `SKILL.md`, lines 28-113
- The command listing hardcodes 50+ commands with descriptions. When skills are added or removed, this list must be manually updated. `_index.json` is the authoritative source and is already declared as a `data_sources` entry.
- **Action:** Replace the hardcoded listing with an instruction: "Read `_index.json`. Group skills by category. Present each with name and description."

**M2. "Quick Start Guidance" is rarely triggered and verbose**
- **File:** `SKILL.md`, lines 789-815
- A 27-line box-formatted block for "new capsuleers." This is niche content that consumes tokens in every `/help` invocation. The standard command listing already serves new users.
- **Action:** REMOVE. If needed, reduce to a 3-line instruction: "If the user seems new, highlight /mission-brief, /fitting, /mining-advisory, and /threat-assessment as starting points."

**M3. "Cross-References" table duplicates the command listing**
- **File:** `SKILL.md`, lines 839-855
- A 17-line table mapping topics to commands — information already present in the command listing above it.
- **Action:** REMOVE entirely.

### Low Severity

**L1. "Behavior Notes" are generic tone instructions**
- **File:** `SKILL.md`, lines 828-836
- "Default /help should fit on one screen (~25 lines)" — useful constraint. The rest ("progressive disclosure", "persona", "contextual suggestions") are generic LLM behavior.
- **Action:** CONSOLIDATE to the one useful constraint (line count limit).

**L2. "Show Database Index" section is tangential**
- **File:** `SKILL.md`, lines 817-826
- Describes handling "show database" queries. This is not a `/help` concern — it's a separate implicit trigger. It adds 10 lines for an edge case.
- **Action:** REMOVE. If this behavior is needed, it's a separate implicit skill or handled naturally.

## 5. Prioritized Recommendations

1. **REMOVE** all 13+ topic-specific help blocks (lines 200-787) — replace with dynamic generation from `_index.json`. This alone saves ~4,000 tokens. [remove]
2. **REMOVE** the RP-formatted command listing (lines 115-198) — Pattern G duplication. [remove]
3. **Modify** the plain command listing (lines 28-113) to be dynamically generated from `_index.json` rather than hardcoded. [modify]
4. **REMOVE** "Quick Start Guidance" (lines 789-815) — reduce to a 3-line conditional instruction. [remove]
5. **REMOVE** "Cross-References" table (lines 839-855) and "Show Database Index" (lines 817-826). [remove]
6. **CONSOLIDATE** "Behavior Notes" (lines 828-836) to the 25-line constraint only. [modify]

**Architectural recommendation:** The ideal help skill is ~50 lines: read `_index.json`, group by category, format as table for plain or boxes for RP. Topic help reads the specific skill's entry from `_index.json`. This replaces 873 hand-maintained lines with ~50 auto-generating lines. Estimated final size: ~500 tokens (95% reduction).
