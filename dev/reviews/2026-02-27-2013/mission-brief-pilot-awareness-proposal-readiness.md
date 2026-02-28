# Proposal Readiness Review: MISSION_BRIEF_PILOT_AWARENESS

**Reviewed:** 2026-02-27-2013
**Proposal:** `dev/proposals/MISSION_BRIEF_PILOT_AWARENESS.md`
**Template:** `proposal`
**Against:** `.claude/skills/mission-brief/SKILL.md` (current HEAD)

---

## 1. Ship Decision

**READY**

All three changes are specified as verbatim before/after text blocks — the implementing agent performs mechanical substitution with no architectural decisions required.

---

## 2. Blockers

None found.

The proposal provides exact replacement text for each of its three changes. No implementation-time guessing is necessary.

---

## 3. Specification Gaps

### 3.1 `Capsuleer Since` field existence not verified

**Location:** Change 2 (step 6 rewrite) and Change 3 (step 4b), both reference `profile.md Capsuleer Since`.

The proposal reads: "< 60 days old (per profile.md `Capsuleer Since`)" and "per profile.md, `Capsuleer Since`". This assumes the field name is `Capsuleer Since` and that it is present in the pilot's profile.md. Neither is verified against the actual profile.md schema.

**Impact:** If the field is absent or named differently, both the step 6 tier logic and the step 4b headroom heuristic silently degrade. The warning never fires; there is no stated fallback.

**Decision needed:** Confirm the exact field name in profile.md, or add a fallback clause: "If `Capsuleer Since` is absent from profile.md, default to assuming the pilot is new (< 60 days) when no module tier evidence exists from ships.md."

### 3.2 "Highest-consumption module" identification method unspecified

**Location:** Change 3, step 4b: "Identify...the highest-consumption module that could be swapped to a compact variant."

`fitting(action="calculate_stats")` returns aggregate CPU/PG totals, not per-module breakdowns. The implementing instruction in SKILL.md tells the runtime Claude instance to identify a specific module, but provides no method. The runtime agent must use EVE domain knowledge or parse the EFT block manually to estimate which module is the heaviest consumer.

This is a runtime quality concern, not a blocking implementation issue — the developer copies the text verbatim. However, the heuristic may produce unreliable "downgrade X" suggestions.

**Decision needed:** Either accept that Claude will use domain heuristics (e.g., largest active module class first), or add a grounding hint: "The highest-CPU module is typically the largest active tank module or propulsion module; inspect the EFT block and name the most likely candidate."

---

## 4. Test Coverage Assessment

The validation section defines four observable checks against the exact failure scenario:

1. `profile.md` read before any output — covers Change 1
2. `extract_requirements` called on final fit — covers Change 2
3. CPU 97.8% triggers headroom warning for 6-day pilot — covers Change 3
4. Brief includes fitting skill note or module downgrade suggestion — covers Change 3 output

**Untested contracts:**
- Behavior when `Capsuleer Since` is absent from profile.md (see Gap 3.1)
- Behavior when `extract_requirements` returns all skills at level I–III (expected: no flags — obvious, not a gap)
- Behavior when CPU > 90% but pilot > 60 days (expected: no warning — AND condition is explicit, not a gap)

The test coverage is adequate for the stated changes. The `Capsuleer Since` fallback is the only untested behavioral contract that is non-obvious.

---

## 5. Readiness Checklist

- [x] All three changes have verbatim before/after implementation text
- [x] Change 1 target location confirmed: `prerequisite_files` in SKILL.md front-matter (line 17–19)
- [x] Change 2 target location confirmed: Validation Gate step 6, line 214 of SKILL.md
- [x] Change 3 target location confirmed: after Validation Gate step 4 (line 213), before step 5 (line 213 — same block, insert between)
- [x] No new files required; single-file scope is correct
- [x] Pilot age threshold change (30 → 60 days) is consistent across both new instructions
- [ ] Verify `Capsuleer Since` field exists and is correctly named in an actual `profile.md` before shipping (Gap 3.1)
- [ ] Decide whether to accept domain-heuristic module identification in step 4b or add a grounding hint (Gap 3.2)
- [x] Validation scenario defined and re-runnable against the original failure case
- [x] Solutions 5 and 6 explicitly deferred — no orphan work
