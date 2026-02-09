# Build Cost Skill Improvements Proposal

**Status:** ✅ COMPLETE (2026-01-31)

---

## Executive Summary

The `/build-cost` skill produces incomplete and potentially misleading profitability assessments due to hardcoded mineral lists and silent handling of missing data. A session review revealed that a Dominix build cost calculation omitted 19.6M ISK in required components, incorrectly reporting ~15.9M profit when the actual result was a ~3.7M loss.

**Problem:** The skill fetches prices only for minerals, ignoring PI materials, reaction products, and specialized components required by modern ship blueprints.

**Recommendation:** Update the skill to dynamically extract ALL materials from SDE responses, fail loudly on missing prices, and surface supply chain complexity to users.

---

## Problem Statement

### Failure Mode Observed

**Session Date:** 2026-01-31
**Query:** `/build-cost Dominix`

1. **Incomplete material extraction:** SDE returned 10 materials; only 7 (minerals) were priced
2. **Silent omission:** Components listed as "Specialized component prices not currently available" without fetching
3. **Incorrect profitability:** Reported 7.8% margin (profit) when actual margin was negative (loss)
4. **Hidden supply chain:** No indication that Dominix requires PI, reactions, and moon goo

### Root Cause Analysis

The skill documentation (`SKILL.md`) uses Hammerhead I as its example - a simple T1 drone requiring only minerals. The implementation guidance implicitly assumes:

```python
# SKILL.md example (problematic)
materials = ["Tritanium", "Pyerite", "Mexallon", "Isogen", "Nocxium"]
market(action="prices", items=materials)
```

This pattern fails for any item requiring:
- Auto-Integrity Preservation Seal (PI + reactions)
- Life Support Backup Unit (PI + reactions)
- Core Temperature Regulator (PI + moon materials)
- T2 components (invention chain)
- Planetary materials (P1-P4)
- Reaction intermediates

### Impact

| Error Type | Consequence |
|------------|-------------|
| Missing component costs | Understated build cost by 10-30% |
| False profitability | Player builds at a loss |
| Hidden complexity | Player unprepared for supply chain |
| Silent failures | No indication answer is incomplete |

---

## Proposed Solution

### 1. Dynamic Material Extraction (Critical)

**Current (Wrong):**
```python
# Hardcoded mineral list
market(action="prices", items=["Tritanium", "Pyerite", "Mexallon", ...])
```

**Proposed (Correct):**
```python
# Extract ALL materials from SDE response
blueprint = sde(action="blueprint_info", item=item_name)
material_names = [m["type_name"] for m in blueprint["materials"]]
material_names.append(blueprint["product_name"])  # Include product for comparison

# Single query for all materials
prices = market(action="prices", items=material_names)
```

**SKILL.md Addition:**
```markdown
## Material Extraction Protocol (MANDATORY)

**CRITICAL:** Never hardcode material lists. Always extract from SDE response.

### Steps:
1. Query `sde(action="blueprint_info", item=...)`
2. Extract ALL entries from `materials` array
3. Include product name for market comparison
4. Query prices for complete list

### Validation:
- Count materials from SDE response
- Count prices received
- If mismatch → warning required
```

### 2. Fail Loudly on Missing Prices (Critical)

When any material price is unavailable, display a prominent warning rather than silent omission.

**Current (Wrong):**
```markdown
| Core Temperature Regulator | 1 | — | — |

*Note: Specialized component prices not currently available*
```

**Proposed (Correct):**
```markdown
## Build Cost: Dominix

⚠️ **INCOMPLETE CALCULATION**

Missing prices for 3 materials:
- Auto-Integrity Preservation Seal (150 units)
- Life Support Backup Unit (75 units)
- Core Temperature Regulator (1 unit)

The totals below are UNDERSTATED. Fetch component prices before making build decisions.

[Rest of output...]
```

**SKILL.md Addition:**
```markdown
## Price Completeness Check (MANDATORY)

After fetching prices, verify completeness:

```python
requested = set(material_names)
received = set(price["type_name"] for price in prices["items"])
missing = requested - received

if missing:
    # MUST display prominent warning
    # MUST NOT present as complete calculation
```

### Warning Format:
- Use ⚠️ emoji prefix
- List all missing items with quantities
- State that totals are understated
- Suggest fetching missing prices
```

### 3. Material Source Classification

Categorize materials by supply chain source to surface complexity.

**Proposed Output Section:**
```markdown
### Supply Chain Requirements

| Source | Materials | Acquisition |
|--------|-----------|-------------|
| Minerals | Tritanium, Pyerite, ... | Mining / Market |
| PI (P1-P2) | Water, Nanites, Test Cultures, ... | Planetary colonies |
| Reactions | Reinforced Carbon Fiber, Pressurized Oxidizers | Refinery + intermediates |
| Moon Materials | Chiral Structures | Nullsec/lowsec moon mining |

**Complexity Rating:** High (requires PI infrastructure + reaction chains)
```

**Implementation:**

Create reference file `reference/industry/material_sources.json`:
```json
{
  "minerals": ["Tritanium", "Pyerite", "Mexallon", "Isogen", "Nocxium", "Zydrine", "Megacyte", "Morphite"],
  "pi_p1": ["Water", "Oxygen", "Bacteria", ...],
  "pi_p2": ["Nanites", "Test Cultures", "Viral Agent", "Supertensile Plastics", ...],
  "reaction_intermediates": ["Reinforced Carbon Fiber", "Pressurized Oxidizers", ...],
  "moon_materials": ["Chiral Structures", "Fullerides", ...]
}
```

**Classification Logic:**
```python
def classify_material(type_name: str, sources: dict) -> str:
    for source, items in sources.items():
        if type_name in items:
            return source
    return "unknown"  # Flag for investigation
```

### 4. Component Drill-Down Option

For items with manufactured components, offer breakdown:

```markdown
### Components

| Component | Qty | Market Price | Build Cost | Δ |
|-----------|-----|--------------|------------|---|
| Auto-Integrity Preservation Seal | 150 | 8.4M | 7.1M | -1.3M |
| Life Support Backup Unit | 75 | 6.4M | 5.8M | -0.6M |
| Core Temperature Regulator | 1 | 4.8M | 4.2M | -0.6M |

**Component Strategy:**
- Buy from market: 19.6M
- Build yourself: 17.1M (saves 2.5M, requires PI/reactions)
```

**SKILL.md Addition:**
```markdown
## Component Analysis (Optional)

For items with component materials:

1. Identify component materials (non-mineral, non-PI raw)
2. Offer: "Show component breakdown? (adds queries)"
3. If yes: Query `sde(action="blueprint_info")` for each component
4. Compare component build cost vs. market price
5. Recommend buy vs. build per component
```

### 5. Update SKILL.md Examples

Replace Hammerhead I example with ship example that demonstrates full complexity.

**New Primary Example:**
```markdown
## Example: Dominix (Complex Item)

### Step 1: Get Blueprint
```python
sde(action="blueprint_info", item="Dominix")
```

Response includes 10 materials:
- 7 minerals (Tritanium through Megacyte)
- 3 components (Seals, Backup Units, Regulator)

### Step 2: Extract ALL Materials
```python
materials = [m["type_name"] for m in blueprint["materials"]]
# ["Tritanium", "Pyerite", ..., "Auto-Integrity Preservation Seal", ...]
materials.append("Dominix")  # Product for comparison
```

### Step 3: Fetch ALL Prices
```python
market(action="prices", items=materials)
```

### Step 4: Verify Completeness
```python
if len(prices["items"]) < len(materials):
    # Display warning, list missing items
```

### Step 5: Categorize and Sum
```python
mineral_cost = sum(minerals)
component_cost = sum(components)
total_cost = mineral_cost + component_cost
```
```

### 6. Pre-Response Validation Checklist

Add to SKILL.md:

```markdown
## Pre-Response Validation (MANDATORY)

Before presenting build cost results, verify:

- [ ] All materials from `blueprint_info` have corresponding prices
- [ ] Component costs are included (not just minerals)
- [ ] Total equals sum of ALL categories
- [ ] Profit calculation uses complete costs
- [ ] Supply chain complexity is noted for non-mineral inputs
- [ ] Any missing data is prominently flagged

**If any checkbox fails:** Do not present as complete. Show warning.
```

### 7. Complexity Rating System

Add visual indicator for supply chain complexity:

| Rating | Criteria | Icon |
|--------|----------|------|
| Simple | Minerals only | 🟢 |
| Moderate | Minerals + PI | 🟡 |
| Complex | Minerals + PI + Reactions | 🟠 |
| Advanced | T2/T3 invention chain | 🔴 |

**Output Example:**
```markdown
## Build Cost: Dominix 🟠

**Complexity:** Complex (requires PI colonies + reaction chains)
```

---

## Implementation Checklist

### Phase 1: Critical Fixes (SKILL.md Updates)

- [x] Add "Material Extraction Protocol" section requiring dynamic extraction
- [x] Add "Price Completeness Check" section with warning format
- [x] Replace Hammerhead I example with Dominix example
- [x] Add "Pre-Response Validation" checklist
- [x] Document that silent omission of materials is forbidden

### Phase 2: Reference Data

- [x] Create `reference/industry/material_sources.json` with classification data
- [x] Document PI materials (P1-P4) for classification
- [x] Document reaction intermediates and moon materials
- [x] Add complexity rating criteria

### Phase 3: Enhanced Output

- [x] Add supply chain requirements table to output format
- [x] Add complexity rating indicator
- [x] Add component drill-down option documentation
- [x] Document buy-vs-build component analysis

### Phase 4: Validation Testing

- [x] Test with mineral-only item (Hammerhead I) - should work as before
- [x] Test with component item (Dominix) - should include all materials
- [x] Test with T2 item - should show appropriate warning/limitation
- [x] Test with unavailable price - should show prominent warning

---

## File Changes Summary

| File | Change |
|------|--------|
| `.claude/skills/build-cost/SKILL.md` | Add validation protocols, update examples |
| `reference/industry/material_sources.json` | New file - material classification |
| `docs/DATA_VERIFICATION.md` | Reference build-cost validation requirements |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Increased query count | Material list is typically <15 items; single market query handles all |
| Classification data maintenance | Material sources are stable; update with major patches |
| Output verbosity | Supply chain section is optional detail; core output remains concise |

---

## Success Criteria

1. **Completeness:** All materials from SDE are priced or flagged
2. **Accuracy:** Profitability reflects true costs including components
3. **Transparency:** Users know when data is incomplete
4. **Clarity:** Supply chain complexity is surfaced, not hidden

---

## Summary

| Aspect | Current State | Proposed State |
|--------|---------------|----------------|
| Material extraction | Hardcoded mineral list | Dynamic from SDE response |
| Missing prices | Silent omission | Prominent warning |
| Component costs | Often missed | Always included |
| Supply chain | Hidden | Classified and displayed |
| Complexity indicator | None | Visual rating system |
| Validation | None | Mandatory checklist |

This proposal addresses the root cause of incomplete build cost calculations and ensures users receive accurate, actionable profitability assessments.
