# Skill Review: first-run-setup

**Skill path:** `.claude/skills/first-run-setup/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Files reviewed:** 1 (SKILL.md only, 430 lines, ~3,151 tokens)

## 1. Executive Summary

The first-run-setup skill is the largest in this review batch at 430 lines (~3,151 tokens) and functions as a procedural script rather than a typical analytical skill. Its bulk comes from large template blocks (profile template, registry format, config format, completion messages) that serve as data templates Claude must emit, which are harder to cut. However, ~25% of the file is genuinely removable: the pseudocode blocks in Phase 1 (lines 67-108) that describe Claude Code tool usage patterns Claude already knows, the Faction Lookup Table that could be a prerequisite file, and behavioral notes that restate the flow.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| ESI-first enforcement | 🟢 | Skill correctly prioritizes ESI detection over manual questions. Boot hook state check avoids redundant file reads. Phase 2 fetches character data from ESI endpoints before proceeding. |
| Prompt hygiene | 🟡 | Phases are clear but pseudocode blocks (lines 67-108) mix Python-like syntax with natural language in ways that may confuse execution. Claude doesn't use `watcher = Bash(...)` syntax. |
| Failure handling | 🟢 | OAuth timeout, ESI fetch failure, and file write errors all covered (lines 393-421). Graceful fallback to manual setup. |
| Context window efficiency | 🔴 | Pseudocode blocks consume ~250 tokens for patterns Claude already understands. Faction Lookup Table (lines 303-310) should be reference data. Large template sections are necessary but could be more compact. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 67-108 | Phase 1 pseudocode -- Python-like `watcher = Bash(...)`, `TaskOutput(task_id=...)`, `json.loads()` syntax. Claude Code doesn't use this API; it uses `Bash` tool calls directly | REMOVE | ~300 tokens |
| `SKILL.md` | 303-310 | "Faction Lookup Table" -- static game data (faction/corp/hostile mappings) that should be a reference/prerequisite file, not inlined | REMOVE (Pattern A) | ~80 tokens |
| `SKILL.md` | 312-317 | "Date Formatting" section -- YC date conversion formula. This is general ARIA knowledge, not setup-specific | REMOVE | ~50 tokens |
| `SKILL.md` | 423-430 | "Behavior Notes" section -- 6 bullets restating the flow's own logic ("ESI-First", "Minimal Questions", "Smart Defaults") | REMOVE (Pattern D) | ~80 tokens |
| `SKILL.md` | 124-127 | "Key UX improvement" explanation -- justification prose for the background polling design | REMOVE (Pattern D) | ~40 tokens |
| `SKILL.md` | 332-362 | "Registry Format" and "Config Format" JSON examples -- could be a single compact example each instead of full formatted blocks | CONSOLIDATE | ~100 tokens |
| `SKILL.md` | 371-388 | "Completion Messages" full ASCII box template -- only one variant shown (RP Off); could be trimmed | CONSOLIDATE | ~80 tokens |

**Total estimated savings: ~730 tokens (~23%)**

## 4. Specific Findings

### High Severity

**H1. Pseudocode uses non-existent API patterns**
- `SKILL.md` lines 67-108: Uses `Bash(command=..., run_in_background=True)`, `watcher.task_id`, `TaskOutput(task_id=..., block=True)`, `json.loads(result.output)`
- Claude Code doesn't have a Python API for `Bash()` or `TaskOutput()`. It uses tool calls. The pseudocode is misleading and may cause Claude to attempt invalid patterns.

**Fix:** Replace with natural language instructions:
1. Run the credential watcher in background: `uv run python .claude/scripts/aria-credential-watch.py --timeout 300`
2. Tell user to run OAuth setup in their terminal
3. Wait for watcher to complete (it outputs JSON with status)
4. Parse the JSON result -- if `status: found`, continue; if `status: timeout`, offer retry

**H2. Faction Lookup Table is inlined reference data (Pattern A)**
- `SKILL.md` lines 303-310: Faction-to-corp-to-hostile mapping table
- This is static game data. If it changes (e.g., new faction warfare mechanics), it must be updated here AND anywhere else it's referenced. Should be in `reference/mechanics/` or a data file.

### Medium Severity

**M1. Behavior Notes restate the flow (Pattern D)**
- `SKILL.md` lines 423-430: "ESI-First: Always try to connect ESI before asking questions"
- The entire Phase 1 flow already implements this. The note is pure justification restating what the flow does.

**M2. Date Formatting is not setup-specific**
- `SKILL.md` lines 312-317: YC year conversion formula
- This is used in exactly one place (the profile template's birthday field). Could be an inline note in the template rather than a standalone section.

**M3. "Key UX improvement" is justification prose (Pattern D)**
- `SKILL.md` lines 124-127: "User doesn't need to return and type 'done' - the background watcher detects completion automatically."
- This explains why the design works. Claude doesn't need this -- the instructions already specify background watching.

### Low Severity

**L1. Registry and Config format blocks are verbose**
- `SKILL.md` lines 332-362: Full JSON examples with all fields. The structure is simple enough that a compact inline example would steer equally well.

**L2. AskUserQuestion JSON block may not match actual tool**
- `SKILL.md` lines 183-219: Full JSON structure for multi-question prompt
- Claude Code's `AskFollowupQuestion` tool doesn't support this structured format. The skill should use sequential prompts or describe the desired UX without specifying a non-existent API.

## 5. Prioritized Recommendations

1. **REMOVE** the pseudocode blocks in Phase 1 (lines 67-108). Replace with 4-line natural language instructions describing the background watcher pattern. (~300 tokens saved)

2. **REMOVE** the Behavior Notes section (lines 423-430). The flow is self-documenting. (~80 tokens saved)

3. **REMOVE** the Faction Lookup Table (lines 303-310). Extract to a reference data file or inline as a compact mapping in the profile template section. (~80 tokens saved)

4. **REMOVE** the "Key UX improvement" explanation (lines 124-127). (~40 tokens saved)

5. **Modify** the AskUserQuestion block (lines 183-219) to use sequential natural language prompts that match Claude Code's actual tool capabilities.

6. **CONSOLIDATE** Registry Format and Config Format (lines 332-362) into minimal inline examples. (~100 tokens saved)

7. **CONSOLIDATE** the Date Formatting section (lines 312-317) into a one-line note within the Profile Template. (~50 tokens saved)
