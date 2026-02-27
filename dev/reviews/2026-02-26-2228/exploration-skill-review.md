# Skill Review: exploration

**Skill path:** `.claude/skills/exploration/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Files reviewed:** 1 (SKILL.md only, 159 lines, ~1,933 tokens)

## 1. Executive Summary

The exploration skill is relatively lean at ~1,933 tokens and has strong grounding discipline with explicit prerequisite file gates and a hallucination guard. However, it inlines site classification tables and hacking strategies that duplicate content from its own declared prerequisite files (`exploration_sites.md`, `hacking_guide.md`), violating ADR-006 Rule 2. The anti-patterns section is valuable but could be more concise. Cutting the inlined reference data would save ~350 tokens (~18%).

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟢 | Mandatory tool call table (lines 27-34), field-to-source mapping (lines 42-53), explicit "read FIRST, respond SECOND" gate. Excellent. |
| Prompt hygiene | 🟢 | Clear separation of prerequisite files vs MCP calls. Anti-patterns section (lines 119-131) provides concrete wrong/right examples. |
| Failure handling | 🟡 | No explicit instruction for what to do if prerequisite files are missing or if market/SDE calls fail. Relies on implicit behavior. |
| Context window efficiency | 🟡 | Inlined site classification tables (lines 81-105) and hacking strategy (lines 107-112) duplicate prerequisite file content. Anti-patterns section is valuable but verbose. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 77-105 | "Site Classification Reference" section -- inlines prefix/faction/danger tables from `exploration_sites.md` | REMOVE (Pattern A) | ~200 tokens |
| `SKILL.md` | 107-112 | "Hacking Strategy" numbered list -- duplicates content from `hacking_guide.md` | REMOVE (Pattern A) | ~60 tokens |
| `SKILL.md` | 113-118 | "Valuable Loot Categories" list -- general knowledge already in `exploration_sites.md` loot tables | REMOVE (Pattern A) | ~50 tokens |
| `SKILL.md` | 36-38 | Hallucination guard block -- restates the mandatory read gate from lines 27-34 | CONSOLIDATE (Pattern G) | ~50 tokens |
| `SKILL.md` | 141 | "Follow the Intelligence Sourcing Protocol in CLAUDE.md" -- references a section that does not exist in CLAUDE.md | REMOVE | ~20 tokens |

**Total estimated savings: ~380 tokens (~20%)**

## 4. Specific Findings

### High Severity

**H1. Inlined site classification tables duplicate prerequisite file (Pattern A)**
- `SKILL.md` lines 81-105: Three tables (Relic Sites, Data Sites, Faction-Specific Notes) inline data from `exploration_sites.md`
- `exploration_sites.md` is declared as a prerequisite file (line 16) and listed in the mandatory read gate (line 31)
- ADR-006 Rule 2: "SKILL.md must not inline data from prerequisite files." The prerequisite gate forces the read; the inline copy risks Claude treating it as sufficient and skipping the authoritative source.

**Fix:** Replace lines 77-105 with a single imperative reference:
```
Read `exploration_sites.md` for site classification, prefix meanings, faction loot, and security bands.
```

**H2. Inlined hacking strategy duplicates prerequisite file (Pattern A)**
- `SKILL.md` lines 107-112: Four-step hacking strategy list
- `hacking_guide.md` is declared as a prerequisite (line 17)
- Same Pattern A issue. The guide is the authoritative source; the inline summary may diverge.

### Medium Severity

**M1. Hallucination guard is restated (Pattern G)**
- `SKILL.md` lines 27-34: Mandatory tool call table with "MUST be read before responding"
- `SKILL.md` lines 36-38: Warning block restates "read the reference files FIRST, respond SECOND"
- The table already enforces the gate. The warning block is redundant emphasis.

**M2. Phantom CLAUDE.md reference**
- `SKILL.md` line 141: "Follow the Intelligence Sourcing Protocol in CLAUDE.md"
- No section called "Intelligence Sourcing Protocol" exists in CLAUDE.md. This is a vestigial reference to a removed or renamed section. It should be deleted or the intended behavior stated inline.

### Low Severity

**L1. No failure handling for missing prerequisite files**
- If `exploration_sites.md` or `hacking_guide.md` cannot be read, the skill has no instruction for how to proceed. Add a one-line fallback: "If prerequisite files are missing, state that exploration analysis requires reference data and cannot proceed."

**L2. Valuable Loot Categories list is low-value**
- `SKILL.md` lines 113-118: Four bullets listing loot categories. This is generic knowledge already contained in the prerequisite file's loot tables. Removing it loses nothing.

## 5. Prioritized Recommendations

1. **REMOVE** the Site Classification Reference section (lines 77-105). Replace with one-line imperative reference to `exploration_sites.md`. (~200 tokens saved)

2. **REMOVE** the Hacking Strategy section (lines 107-112). Replace with one-line imperative reference to `hacking_guide.md`. (~60 tokens saved)

3. **REMOVE** the Valuable Loot Categories section (lines 113-118). Already in prerequisite file. (~50 tokens saved)

4. **REMOVE** the phantom reference to "Intelligence Sourcing Protocol in CLAUDE.md" on line 141. Replace with the intended behavioral instruction if known, or delete entirely.

5. **CONSOLIDATE** the hallucination guard (lines 36-38) into the mandatory tool call table header. One statement of the gate is sufficient.

6. **Add** a one-line failure instruction for missing prerequisite files.
