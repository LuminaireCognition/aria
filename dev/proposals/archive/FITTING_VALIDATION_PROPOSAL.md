# Fitting Validation Proposal

**Status:** ✅ COMPLETE (2026-02-02)
**Implemented:** EOS integration, SKILL.md protocol, MODULE_NAMES.md, CHECKLIST.md, EFT-FORMAT.md

---

## Executive Summary

This proposal establishes a mandatory validation protocol for ship fitting recommendations. All fits must be verified through the EOS fitting engine (via MCP) before being presented to the user. This prevents errors such as incorrect slot assignments, invalid module names, and CPU/PG overloads.

**Problem:** ARIA recommended a Data Analyzer (mid slot module) in a high slot, and used an incorrect module name ("Reactive Armor Hardener I" instead of "Reactive Armor Hardener"). These errors would have been caught by the fitting calculator.

**Recommendation:** Update the `/fitting` skill to require EOS validation as a prerequisite step, not an optional verification.

---

## Problem Statement

### Failure Mode Observed

1. **Slot assignment error:** Data Analyzer I placed in high slot (it's a mid slot module)
2. **Module naming error:** "Reactive Armor Hardener I" is not the correct item name
3. **No validation performed:** Fit was presented without checking against ground truth

### Root Cause

Training data knowledge was used instead of verifying against:
- SDE for module slot types and exact names
- EOS fitting engine for fit validity
- Pilot skills for accurate DPS/tank calculations

### Impact

- Invalid fits cannot be imported into EVE client
- Users may attempt to fit modules in wrong slots
- DPS/tank estimates based on assumptions, not calculations

---

## Proposed Solution

### Mandatory Validation Protocol

Before presenting ANY fitting recommendation:

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Gather Context                                          │
├─────────────────────────────────────────────────────────────────┤
│ • Read pilot profile (module tier, faction, constraints)        │
│ • Read pilot ships.md (existing fits for tier validation)       │
│ • If mission fit: read mission cache for required equipment     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Verify Module Names via SDE                             │
├─────────────────────────────────────────────────────────────────┤
│ For each module in proposed fit:                                │
│ • sde(action="item_info", item="Module Name")                   │
│ • Confirm exact name (many modules lack "I" suffix)             │
│ • Confirm module exists and is published                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Build and Validate EFT                                  │
├─────────────────────────────────────────────────────────────────┤
│ • Construct EFT string with verified module names               │
│ • fitting(action="calculate_stats", eft=..., use_pilot_skills=true) │
│ • Check response for errors and warnings                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Evaluate Validation Results                             │
├─────────────────────────────────────────────────────────────────┤
│ • validation_errors → Fit is INVALID, do not present            │
│ • CPU/PG overloaded → Fit won't work, suggest alternatives      │
│ • Unknown type → Re-verify module name via SDE                  │
│ • Clean validation → Proceed to presentation                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Present Validated Fit                                   │
├─────────────────────────────────────────────────────────────────┤
│ • Include EFT block (copy-paste ready)                          │
│ • Show calculated stats (DPS, EHP, cap stability)               │
│ • Note fitting room (CPU%, PG%)                                 │
│ • Include pilot skill context if relevant                       │
└─────────────────────────────────────────────────────────────────┘
```

### Module Name Verification

Many EVE modules do not follow the "Name I / Name II" pattern:

| Correct Name | Common Mistake |
|--------------|----------------|
| Reactive Armor Hardener | Reactive Armor Hardener I |
| Damage Control II | Damage Control 2 |
| 50MN Microwarpdrive I | 50MN MWD I |
| Large Compact Pb-Acid Cap Battery | Large Cap Battery I |

**Rule:** Always verify exact module names via `sde(action="item_info")` before including in a fit.

### Slot Type Verification

The EOS fitting engine validates slot assignments automatically. If a fit places a mid slot module in a high slot, the validation will fail or produce warnings.

**Backup verification:** For critical modules (Data Analyzer, Probe Launcher, etc.), explicitly verify slot type:

```
sde(action="item_info", item="Data Analyzer I")
→ Check group_name for slot indicator (future SDE enhancement)
```

*Note: Current SDE item_info doesn't expose slot type directly. EOS validation catches these errors.*

---

## Integration Points

### 1. Update `/fitting` Skill

**File:** `.claude/skills/fitting/SKILL.md`

Add new section after "Gear Tier Validation Protocol":

```markdown
## Fit Validation Protocol (MANDATORY)

**CRITICAL:** Never present a fitting without EOS validation.

### Validation Steps

1. **Verify module names** via `sde(action="item_info", item="...")`
   - Catch naming errors before building EFT
   - Many modules lack "I/II" suffix

2. **Validate complete fit** via `fitting(action="calculate_stats", eft="...", use_pilot_skills=true)`
   - Catches slot mismatches
   - Catches CPU/PG overloads
   - Provides accurate DPS/tank with pilot skills

3. **Check validation response:**
   - `validation_errors` present → Fit is invalid, fix before presenting
   - `resources.cpu.overloaded: true` → CPU exceeded, reduce modules
   - `resources.powergrid.overloaded: true` → PG exceeded, downgrade modules
   - `metadata.warnings` → Review but may be acceptable

4. **Only present validated fits** with calculated stats

### Mission Fit Requirements

When building fits for specific missions:

1. Read mission cache for required equipment
2. Verify required modules fit in available slots BEFORE finalizing
3. Example: Data Analyzer (mid slot) requires a free mid slot
```

### 2. Add Reference: Common Module Naming

**File:** `reference/fittings/MODULE_NAMES.md` (new)

Document commonly misnamed modules:

```markdown
# Module Naming Reference

Modules that don't follow "Name I / Name II" convention:

| Module | Correct Name | Notes |
|--------|--------------|-------|
| Reactive Armor Hardener | Reactive Armor Hardener | No tier suffix |
| Damage Control | Damage Control I / II | Has tier suffix |
| Cap Battery | Compact Pb-Acid Cap Battery, etc. | Named variants |
| MWD | 5MN Microwarpdrive I | Size prefix required |

When in doubt: `sde(action="item_info", item="...")` returns exact name.
```

### 3. Skill Index Metadata

**File:** `.claude/skills/fitting/_index.json`

Add validation requirement flag:

```json
{
  "name": "fitting",
  "requires_eos_validation": true,
  "validation_tool": "fitting(action=\"calculate_stats\")",
  ...
}
```

---

## Implementation Checklist

### Phase 1: Skill Documentation Update

- [ ] Add "Fit Validation Protocol" section to `/fitting` skill
- [ ] Document validation as MANDATORY, not optional
- [ ] Add examples of validation failures and how to handle them

### Phase 2: Reference Documentation

- [ ] Create `reference/fittings/MODULE_NAMES.md` with common naming issues
- [ ] Update `docs/DATA_VERIFICATION.md` to reference fitting validation

### Phase 3: SDE Enhancement (Future)

- [ ] Add slot type to `sde(action="item_info")` response
- [ ] Add fitting requirements (CPU, PG, skills) to item_info
- [ ] Enable pre-validation of individual modules before full fit check

---

## Validation Response Interpretation

### Clean Validation

```json
{
  "metadata": {
    "validation_errors": [],
    "warnings": []
  },
  "resources": {
    "cpu": {"overloaded": false, "percent": 84.0},
    "powergrid": {"overloaded": false, "percent": 71.0}
  }
}
```

**Action:** Present fit with confidence.

### Slot Mismatch Error

EOS will fail to place module or produce validation error.

**Action:** Verify module slot type, rebuild fit.

### CPU/PG Overload

```json
{
  "resources": {
    "cpu": {"overloaded": true, "percent": 112.0}
  }
}
```

**Action:** Suggest alternatives - downgrade modules, add fitting implants, or choose different modules.

### Unknown Type Error

```json
{
  "error": "type_resolution_error",
  "message": "Unknown type: Reactive Armor Hardener I",
  "type_name": "Reactive Armor Hardener I"
}
```

**Action:** Query SDE for correct name, rebuild EFT, re-validate.

---

## Example: Corrected Workflow

**Request:** "Fit a Vexor for Survey Rendezvous"

**Step 1 - Context:**
- Read mission cache → requires Data Analyzer
- Read pilot profile → T1/Meta modules only
- Read ships.md → existing Vexor fit available

**Step 2 - Verify Module Names:**
```
sde(action="item_info", item="Data Analyzer I") → Valid
sde(action="item_info", item="Reactive Armor Hardener") → Valid (no "I")
sde(action="item_info", item="Energized Adaptive Nano Membrane I") → Valid
```

**Step 3 - Build and Validate:**
```
fitting(action="calculate_stats", eft="[Vexor, Survey Rendezvous]...", use_pilot_skills=true)
```

**Step 4 - Check Results:**
- No validation errors
- CPU 84%, PG 71%
- DPS 281.54, EHP 9,264

**Step 5 - Present:**
```
[Vexor, Survey Rendezvous]

Drone Damage Amplifier I
...

Stats (your skills):
- DPS: 281
- EHP: 9,264
- CPU: 84% | PG: 71%
```

---

## Open Questions

1. **Should we batch-validate module names or validate on each fit?**
   - Recommendation: Validate per-fit for accuracy
   - Caching common module names could speed up repeated fits

2. **How to handle EOS unavailability?**
   - Recommendation: Warn user that fit is unvalidated
   - Never present as "validated" without EOS confirmation

3. **Should reference fits in `reference/ships/fittings/` be pre-validated?**
   - Recommendation: Yes, all reference fits should pass EOS validation
   - Add CI check for reference fit validity (future)

---

## Summary

| Aspect | Current State | Proposed State |
|--------|---------------|----------------|
| Module name verification | None | SDE lookup required |
| Fit validation | Optional/forgotten | Mandatory via EOS |
| Slot assignment check | None | EOS catches errors |
| Stats accuracy | Estimated | Calculated with pilot skills |
| Mission equipment | Often missed | Cross-referenced from cache |

This protocol ensures every fitting recommendation is valid, importable, and accurately reflects the pilot's capabilities.
