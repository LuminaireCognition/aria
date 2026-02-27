# Skill Review: journal

**Skill Path:** `.claude/skills/journal/SKILL.md`
**Review Timestamp:** 2026-02-26-2228
**Files in skill directory:** `SKILL.md` (1 file, 260 lines)

---

## 1. Executive Summary

The journal skill is a local-file-writing skill that does not use MCP or ESI -- it writes structured entries to pilot markdown files. The skill is moderately efficient but has significant dead weight in duplicate confirmation display templates (pattern E/G), verbose error handling blocks with ASCII art, and a hardcoded "Federation Navy" default that should come from the pilot profile. The core entry format templates are the skill's primary value and are well-designed.

---

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| Data source usage (adapted -- no MCP/ESI) | :green_circle: | Correctly reads/writes to pilot data files declared in `data_sources`. No external data fetching needed. |
| Prompt hygiene | :yellow_circle: | Entry templates are clear, but the "Federation Navy" default (lines 58, 89) is hardcoded rather than derived from pilot profile faction. |
| Failure handling | :green_circle: | File-not-found and write-failure cases handled with recovery paths. |
| Context window efficiency | :yellow_circle: | Confirmation display templates (lines 172-204) repeat information already shown in entry format templates (lines 86-105). ASCII box art in entry-type prompt, confirmations, and error blocks adds ~80 lines of low-value formatting. |

---

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 26 | "(where `{active_pilot}` is the resolved directory)" parenthetical -- pilot resolution is CLAUDE.md system behavior (pattern B) | **REMOVE** | ~10 tokens |
| `SKILL.md` | 39-52 | Entry type selection prompt with ASCII box art (pattern E) -- this is a simple two-option disambiguation; a 2-line instruction suffices | **CONSOLIDATE** | ~100 tokens |
| `SKILL.md` | 58 | Hardcoded "Federation Navy" default -- should be "default from pilot profile faction" | **Modify** | ~5 tokens |
| `SKILL.md` | 107-133 | "File Insertion Points" section -- restates target file paths already declared in lines 27-28 (pattern G) | **CONSOLIDATE** | ~120 tokens |
| `SKILL.md` | 135-146 | "Statistics Updates" section -- a brief note that counters should be incremented would suffice instead of showing the full markdown structure | **CONSOLIDATE** | ~80 tokens |
| `SKILL.md` | 148-167 | "Inline Argument Parsing" section -- useful but the two examples could be compressed to one line each | **CONSOLIDATE** | ~60 tokens |
| `SKILL.md` | 170-204 | Confirmation display templates (mission + exploration) -- two 16-line ASCII box templates (pattern E) that duplicate the entry format templates with minor rewording (pattern G) | **REMOVE** | ~250 tokens |
| `SKILL.md` | 219-238 | Error handling with ASCII box templates -- two error cases that could be 2 lines each instead of 20 lines with box art (pattern E) | **CONSOLIDATE** | ~140 tokens |
| `SKILL.md` | 213 | "Persona: Maintain ARIA voice" behavior note -- persona behavior is a system-level concern (pattern B) | **REMOVE** | ~10 tokens |
| `SKILL.md` | 241-247 | "Cross-References" section -- offering to update other files is useful but overly verbose | **CONSOLIDATE** | ~40 tokens |
| `SKILL.md` | 249-259 | "Contextual Suggestions" table -- standard cross-skill suggestion pattern that could be 2 lines | **CONSOLIDATE** | ~60 tokens |

**Total estimated savings: ~875 tokens (~34% of file)**

---

## 4. Specific Findings

### High Severity

**H1. Confirmation templates duplicate entry format templates (lines 170-204 vs 86-105, patterns E+G)**
The confirmation display blocks are essentially the entry format templates wrapped in ASCII box art with minor label changes ("Recording mission completion:" vs "**Mission:**"). This is a dual rendering of the same data structure. Replace with: "Preview the formatted entry (using the templates above) and ask for confirmation before writing."

### Medium Severity

**M1. File insertion points restate target files (lines 107-133, pattern G)**
Lines 27-28 already declare the target files and insertion headers ("## Recent Completions", "## Recent Discoveries"). Lines 107-133 restate this with additional detail about placeholder replacement. Consolidate into lines 27-28 with one additional note about replacing the placeholder template on first use.

**M2. ASCII box art in entry-type prompt and errors (lines 39-52, 219-238, pattern E)**
Three blocks of ASCII box art for simple interactions: entry type selection, file-not-found, and write-failure. These should be plain text instructions: "Ask the pilot whether they're logging a mission or exploration entry" and "If the target file is missing, offer to create it."

**M3. Hardcoded "Federation Navy" default (line 58)**
The agent default "Federation Navy" should read from the pilot's profile faction alignment. A Caldari-aligned pilot would get incorrect defaults.

### Low Severity

**L1. Statistics Updates section is over-specified (lines 135-146)**
Shows the exact markdown structure of exploration statistics. A single imperative line ("Increment the relevant counters in the statistics section at the top of the file") would steer identically.

**L2. Persona behavior note is system-level (line 213, pattern B)**
"Maintain ARIA voice" is handled by the persona loading system, not individual skills.

---

## 5. Prioritized Recommendations

1. **Remove** confirmation display templates (lines 170-204) -- replace with "Preview the entry using the format templates above, then ask for confirmation."
2. **Consolidate** file insertion points (lines 107-133) into the existing target file declarations (lines 27-28).
3. **Consolidate** ASCII box art in entry-type prompt and error blocks (lines 39-52, 219-238) into plain imperative text.
4. **Modify** hardcoded "Federation Navy" default (line 58) to reference pilot profile faction.
5. **Consolidate** statistics updates and inline argument parsing (lines 135-167) into more compact form.
6. **Remove** persona behavior note (line 213) and pilot resolution parenthetical (line 26).
7. **Consolidate** cross-references and contextual suggestions (lines 241-259) into brief text.
