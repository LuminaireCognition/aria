# Skill Review: esi-query

**Skill path:** `.claude/skills/esi-query/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Files reviewed:** 1 (SKILL.md only, 309 lines, ~3,195 tokens)

## 1. Executive Summary

The esi-query skill is the most verbose of the system skills at ~3,195 tokens, with significant dead weight in repeated "ESI is optional" messaging (stated 3 separate times in different sections), redundant ASCII box response templates, and a Documentation Security section that duplicates reference file content. The skill's core behavior -- query ESI, display with timestamp, warn about staleness -- could be expressed in roughly half the current token count.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟡 | Skill uses CLI (`uv run aria-esi`) rather than MCP tools. Acceptable for ESI queries which have no MCP dispatcher. No risk of hallucination since output is CLI JSON. |
| Prompt hygiene | 🟢 | Clear about what comes from ESI vs. profile. Volatility classifications are well-defined. |
| Failure handling | 🟢 | Good coverage: unavailable ESI, missing credentials, expired token. Graceful fallback to manual data. |
| Context window efficiency | 🔴 | Heavy redundancy: "ESI is optional" stated 3 times, 4 separate response format templates with ASCII boxes, Documentation Security section duplicates a reference file. ~40% of tokens are noise. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 86-103 | "ESI is Optional" section -- restates CLAUDE.md's ESI-optional stance plus lists 6 capabilities that work without ESI | REMOVE | ~200 tokens |
| `SKILL.md` | 225-253 | "Missing Credentials" error block -- duplicates the "ESI is optional" messaging a third time with another ASCII box | CONSOLIDATE | ~180 tokens |
| `SKILL.md` | 248-258 | "ARIA should NOT / ARIA SHOULD" bullet lists -- behavioral guidance that just restates the error handling response format | REMOVE | ~100 tokens |
| `SKILL.md` | 53-68 | "ESI UNAVAILABLE" ASCII box response template -- 16-line template that could be a 3-line description | CONSOLIDATE | ~120 tokens |
| `SKILL.md` | 163-203 | Three separate response format templates (volatile, wallet, semi-stable) with ASCII box art -- could be one template with field placeholders | CONSOLIDATE | ~200 tokens |
| `SKILL.md` | 273-278 | "In-Universe Framing" section -- 4 bullet points of RP flavor mappings. Persona overlays handle this; not needed in base skill | REMOVE | ~60 tokens |
| `SKILL.md` | 285-302 | "Documentation Security" section -- complete URL allow/deny list that duplicates `reference/mechanics/esi_api_urls.md` | REMOVE (Pattern A) | ~200 tokens |
| `SKILL.md` | 304-309 | "DO NOT" section -- restates volatility rules already covered in lines 31-38 | REMOVE (Pattern G) | ~70 tokens |
| `SKILL.md` | 206-220 | "Brevity Mode" section -- two more response format examples. Redundant with the 3 templates above | CONSOLIDATE (Pattern G) | ~100 tokens |

**Total estimated savings: ~1,230 tokens (~38%)**

## 4. Specific Findings

### High Severity

**H1. Triple-redundant "ESI is optional" messaging (Pattern G)**
- `SKILL.md` lines 86-103: Dedicated "ESI is Optional" section
- `SKILL.md` lines 225-258: "Missing Credentials" error handler repeats "ESI is an optional enhancement" plus behavioral DO/DON'T lists
- `SKILL.md` lines 96-103: Bullet list of features that work without ESI

The skill says "ESI is optional" or equivalent three separate times. One brief note in the error handling section is sufficient. The rest is noise.

**H2. Documentation Security section duplicates reference file (Pattern A)**
- `SKILL.md` lines 285-302: Complete URL allow/deny list with 8+ URLs
- Already maintained in `reference/mechanics/esi_api_urls.md` (referenced on line 287)

The skill declares the reference file and then inlines its content immediately below. This is exactly Pattern A -- the reference is already pointed to on line 287; the inline copy should be deleted.

### Medium Severity

**M1. Six response format templates for three query types**
- `SKILL.md` lines 53-68: ESI Unavailable box
- `SKILL.md` lines 163-175: Volatile data box
- `SKILL.md` lines 180-189: Wallet box
- `SKILL.md` lines 192-203: Semi-stable box
- `SKILL.md` lines 210-215: Brevity volatile
- `SKILL.md` lines 218-220: Brevity wallet

Six templates is excessive. The volatile and wallet templates are near-identical (both show timestamp + data + staleness warning). Consolidate to one template with slot annotations.

**M2. "DO NOT" section duplicates earlier volatility rules (Pattern G)**
- `SKILL.md` lines 304-309: Four "DO NOT" bullets about not caching, not referencing old data
- `SKILL.md` lines 31-38: "Data Volatility" section covers identical ground

### Low Severity

**L1. In-Universe Framing section is persona overlay territory**
- `SKILL.md` lines 273-278: Maps ESI concepts to in-universe terms
- This belongs in persona overlays, not the base skill. With `rp_level: off` (the default), these are unused tokens.

**L2. JSON Response Format example is unnecessary**
- `SKILL.md` lines 143-155: Shows an example JSON structure from CLI output
- Claude will see the actual JSON from the CLI call. Showing an example doesn't improve steering.

## 5. Prioritized Recommendations

1. **REMOVE** the "ESI is Optional" section (lines 86-103) and the DO/DON'T behavioral lists (lines 248-258). Keep one line in the Missing Credentials handler: "ESI is optional. Guide user to manual data files." (~300 tokens saved)

2. **REMOVE** the Documentation Security section (lines 285-302). The reference file path on line 287 is sufficient. (~200 tokens saved)

3. **CONSOLIDATE** the six response templates into two: one standard template with field annotations, one brevity template. (~320 tokens saved)

4. **REMOVE** the "DO NOT" section (lines 304-309) -- already covered by Data Volatility section. (~70 tokens saved)

5. **REMOVE** the In-Universe Framing section (lines 273-278) -- defer to persona overlays. (~60 tokens saved)

6. **REMOVE** the JSON Response Format example (lines 143-155) -- Claude sees real output. (~80 tokens saved)
