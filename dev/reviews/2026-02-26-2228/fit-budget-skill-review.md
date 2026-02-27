# Skill Review: fit-budget

**Skill path:** `.claude/skills/fit-budget/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Files reviewed:** 1 (SKILL.md only, 373 lines, ~3,201 tokens)

## 1. Executive Summary

The fit-budget skill has strong MCP integration discipline with explicit batch-call guidance and a 12-15 call efficiency target. Its primary issue is a 90-line Substitution Database (lines 226-275) that inlines static module-to-module mappings -- exactly the data that `sde(action="meta_variants")` provides at runtime. This is Pattern A at scale. Additionally, the ESI Availability Check section (lines 51-82) duplicates the pattern from esi-query and could reference a shared protocol. Removing the substitution database and trimming redundancies would save ~500 tokens (~16%).

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟢 | Excellent. Mandatory tool call table (lines 36-43), batch-call patterns throughout, explicit "Do NOT call per module" warnings. Efficiency target of 12-15 calls (line 85) is a strong guardrail. |
| Prompt hygiene | 🟢 | Clear "use meta_variants, not training data" instruction on line 226. Field-to-tool mapping is unambiguous. Selection priority (lines 130-135) provides clear heuristics. |
| Failure handling | 🟢 | Error handling table (lines 325-333) covers all key scenarios. ESI unavailable fallback (lines 59-82) with tier-based assumptions is practical. |
| Context window efficiency | 🟡 | Substitution Database (90 lines) duplicates MCP data. ESI Availability Check duplicates a pattern that appears in multiple skills. Verdict Guidelines (lines 304-322) include examples that could be more concise. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 228-275 | "Common T2 -> Budget Substitutions" tables -- 6 sub-tables mapping T2 modules to budget alternatives. This is exactly what `sde(action="meta_variants")` returns at runtime | REMOVE (Pattern A) | ~300 tokens |
| `SKILL.md` | 51-82 | "ESI Availability Check" section -- duplicates identical pattern in esi-query; should be a shared protocol file | CONSOLIDATE (Pattern B/future shared protocol) | ~150 tokens (if extracted) |
| `SKILL.md` | 313-323 | Verdict example blocks -- two example boxes. One example is sufficient | CONSOLIDATE | ~60 tokens |
| `SKILL.md` | 336-341 | "Integration with Other Skills" suggestion table -- cross-cutting contextual suggestion pattern | REMOVE | ~50 tokens |
| `SKILL.md` | 367-373 | "Behavior Notes" list -- 5 bullets restating instructions already present in the flow | REMOVE (Pattern D) | ~50 tokens |
| `SKILL.md` | 226-227 | Disclaimer paragraph for substitution database -- "These are category hints... NOT ground truth" | REMOVE (with database) | ~40 tokens |

**Total estimated savings: ~650 tokens (~20%)**

## 4. Specific Findings

### High Severity

**H1. Substitution Database inlines MCP data (Pattern A)**
- `SKILL.md` lines 228-275: Six tables covering Weapons, Tank (Armor), Tank (Shield), Drones, Support Modules
- Each table maps a T2 module to a "Typical Budget Alternative"
- Step 3 of the execution flow (line 117) instructs Claude to call `sde(action="meta_variants")` for exactly this data
- The disclaimer on line 226 acknowledges these aren't ground truth, but their presence gives Claude a shortcut to skip the MCP call

**Fix:** Delete lines 226-275 entirely. The execution flow already mandates `meta_variants` calls. If category hints are needed, reduce to a 3-line note:
```
Common downgrade tiers: Faction -> T2 -> Meta 4 -> Meta 1-3 -> T1 base.
For drones: T2 -> T1 (same name without "II"). Use meta_variants to confirm.
```

**H2. ESI Availability Check is a cross-skill pattern**
- `SKILL.md` lines 51-82: Identical structure to `esi-query/SKILL.md` lines 40-74
- Both check session hook for ESI status, provide an unavailable response, then proceed
- This is a candidate for extraction to `reference/protocols/esi-availability-check.md` per ADR-006's shared protocol mechanism

### Medium Severity

**M1. Behavior Notes restate the flow (Pattern D)**
- `SKILL.md` lines 367-373: "Always preserve the fit's intended role" (already in Fit Purpose Preservation section), "Show exact stat differences" (already in Response Format), etc.
- Every bullet restates an instruction that exists elsewhere in the file.

**M2. Integration with Other Skills table is generic**
- `SKILL.md` lines 336-341: Three contextual suggestions. CLAUDE.md's command suggestion protocol handles this. The suggestions themselves are predictable enough that Claude would offer them without explicit instruction.

### Low Severity

**L1. Verdict Guidelines examples are verbose**
- `SKILL.md` lines 313-323: Two example verdict blocks. The verdict table (lines 306-311) already provides clear thresholds and template language. One example would suffice.

**L2. "Session context note" is Pattern B**
- `SKILL.md` line 87: "The pilot profile is already loaded at session start. Do not re-read it."
- This restates CLAUDE.md's session initialization behavior. It's one line so the cost is minimal, but it's technically redundant.

## 5. Prioritized Recommendations

1. **REMOVE** the Substitution Database (lines 226-275). Replace with a 3-line downgrade tier summary. (~300 tokens saved)

2. **REMOVE** or **extract** the ESI Availability Check (lines 51-82) to a shared protocol file if other skills need the same pattern. If kept inline, trim to essential instructions only. (~150 tokens saved if extracted)

3. **REMOVE** the Behavior Notes section (lines 367-373). Instructions are already in the flow. (~50 tokens saved)

4. **REMOVE** the Integration with Other Skills table (lines 336-341). Cross-cutting concern. (~50 tokens saved)

5. **CONSOLIDATE** the Verdict example blocks (lines 313-323) to one example. (~60 tokens saved)

6. **Add** the Substitution Database's only unique insight as a compact note: tier ordering and drone naming convention.
