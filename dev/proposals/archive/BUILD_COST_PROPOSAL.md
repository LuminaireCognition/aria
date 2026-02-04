# Production Profitability Calculator Proposal

**Status:** ✅ ARCHIVED (2026-02-02)
**Completed:** Phases 1-2, Phase 4, Phase 3 partial (skill exists, SDE + market integration, ME formulas, job cost calculations, character integration, component chains, profit/hr)
**Remaining:** None - see successor document

> **Archive Note (2026-02-02):** This proposal is COMPLETE for its original scope.
> The remaining Phase 3 work (T2 invention cost amortization) has been extracted to:
> **`T2_INVENTION_AMORTIZATION_PROPOSAL.md`**
>
> This separation allows focused tracking of invention mechanics, which have
> distinct data sources, formulas, and edge cases from standard manufacturing.

> **Validation (2026-02-02):** Phase 3 component chains COMPLETE:
> - `industry_chains.py` service implemented with `ChainResolver` class
> - `--full-chain` flag for recursive BOM resolution
> - Terminal materials definition in `reference/industry/terminal_materials.json`
> - Build vs Buy analysis with savings calculation
> - Circular reference protection and max depth limit (5)
> - Test coverage: 14 tests in `tests/services/test_industry_chains.py`
>
> **Validation (2026-02-02):** Profit Per Hour calculation COMPLETE:
> - `calculate_profit_per_hour()` function in `industry_costs.py`
> - TE (Time Efficiency) calculations with blueprint and facility bonuses
> - Helper functions: `format_time_duration()`, `format_isk()`
> - Test coverage: 23 new tests in `tests/services/test_industry_costs.py`
>
> **Related:** New `/reactions` skill created separately for fuel blocks and moon goo calculations.
> See `reference/industry/fuel_blocks.json` and `src/aria_esi/services/reactions.py`.

> **Validation (2026-02-02):** Phase 4 (character integration) is COMPLETE:
> - `character_industry.py` service implemented (324 lines)
> - Functions: `get_character_blueprints()`, `find_blueprint_for_item()`, `get_character_industry_skills()`, `summarize_industry_capabilities()`
> - SKILL.md updated with step-by-step workflow for `--use-character` flag (lines 720-828)
> - Skill-aware invention bonus calculation via `calculate_character_invention_bonus()`
> - Response format examples for blueprint found/not found scenarios
>
> **Validation (2026-02-02):** Phase 2 (job costs/industry indices) is COMPLETE:
> - `industry_costs.py` service implemented (265 lines) with full job cost formula
> - Functions: `apply_me()`, `apply_facility_me()`, `calculate_job_cost()`, `estimate_total_build_cost()`
> - Job cost formula: `EIV × System Index + SCC Surcharge + Facility Tax` (all components implemented)
> - Facility bonuses: Raitaru, Azbel, Sotiyo, NPC Station in `reference/industry/facility_bonuses.json`
> - Test coverage: 227 lines in `tests/services/test_industry_costs.py` (all passing)
> - **Design decision:** Live ESI indices intentionally use hardcoded estimates (documented as "examples only")
>   - `get_typical_system_index()` returns estimated values for Jita, Amarr, Perimeter, nullsec
>   - Rationale: ESI indices change hourly; skill doc notes "actual indices change hourly"

---

## Executive Summary

Add a `/build-cost` skill that calculates manufacturing profitability by comparing material costs to market prices. This answers the industrialist's core question: "Should I build or buy?"

**Primary value:** Instant profit/loss analysis for any manufacturable item.

---

## Problem Statement

Manufacturing in EVE requires complex calculations:

1. **Material costs** - Prices for all inputs (minerals, components, PI)
2. **Research levels** - ME/TE affects input quantities
3. **Job costs** - System cost index, facility bonuses
4. **Market comparison** - Is building cheaper than buying?
5. **Margin analysis** - What's my profit if I sell?

Players use spreadsheets or tools like EVE IPH. ARIA has all the data sources but no unified skill.

---

## Data Sources

### SDE (via MCP)

```python
sde(action="blueprint_info", item="Vexor Navy Issue")
# Returns:
# - materials: [{type_id, quantity}, ...]
# - manufacturing_time: seconds
# - research levels (base ME/TE)
```

### Market (via MCP)

```python
market(action="prices", items=["Tritanium", "Pyerite", ...])
# Returns buy/sell prices at trade hubs
```

### ESI (optional)

```python
# Industry indices for job cost calculation
# Character blueprints for ME/TE levels
```

---

## Proposed Skill: `/build-cost`

### Triggers

```yaml
triggers:
  - "/build-cost"
  - "should I build [item]"
  - "is building [item] profitable"
  - "manufacturing cost for [item]"
  - "build vs buy [item]"
  - "production profit [item]"
```

### Commands

| Command | Description |
|---------|-------------|
| `/build-cost <item>` | Full cost breakdown with profit analysis |
| `/build-cost <item> --me <level>` | Calculate with specific ME research |
| `/build-cost <item> --runs <n>` | Multi-run calculation |
| `/build-cost <item> --buy-from <hub>` | Use specific hub for material prices |

### Example Interactions

**Basic analysis:**
```
User: /build-cost Vexor Navy Issue

ARIA: ## Vexor Navy Issue Manufacturing Analysis

      ### Bill of Materials (ME 0)
      | Material | Quantity | Jita Sell | Cost |
      |----------|----------|-----------|------|
      | Tritanium | 2,400,000 | 5.12 | 12.3M |
      | Pyerite | 600,000 | 8.45 | 5.1M |
      | Mexallon | 180,000 | 42.30 | 7.6M |
      | Isogen | 36,000 | 65.20 | 2.3M |
      | Nocxium | 9,000 | 420.00 | 3.8M |
      | Zydrine | 2,400 | 890.00 | 2.1M |
      | Megacyte | 1,200 | 1,250.00 | 1.5M |
      | **Total Materials** | | | **34.7M** |

      ### Costs
      | Component | Amount |
      |-----------|--------|
      | Materials | 34.7M |
      | Est. Job Cost (1% index) | 347K |
      | **Total Build Cost** | **35.0M** |

      ### Market Comparison
      | | Price |
      |-|-------|
      | Jita Sell | 98.5M |
      | Jita Buy | 95.2M |

      ### Profitability
      | Scenario | Profit | Margin |
      |----------|--------|--------|
      | Sell at Jita Sell | 63.5M | 181% |
      | Sell at Jita Buy | 60.2M | 172% |
      | After 8% taxes* | 55.6M | 159% |

      *Assumes 4% broker + 4% sales tax

      Verdict: PROFITABLE - Build cost is 36% of market price.

      Build time: 4h 0m (base, no TE bonus)
```

**With ME research:**
```
User: /build-cost Vexor Navy Issue --me 10

ARIA: ## Vexor Navy Issue (ME 10)

      Material savings vs ME 0: -10% quantity

      | Material | ME 0 Qty | ME 10 Qty | Savings |
      |----------|----------|-----------|---------|
      | Tritanium | 2,400,000 | 2,160,000 | 1.2M ISK |
      | Pyerite | 600,000 | 540,000 | 507K ISK |
      | ... | ... | ... | ... |

      Total build cost: 31.2M (vs 35.0M at ME 0)
      Additional profit from ME 10: +3.8M per unit
```

**Multi-run batch:**
```
User: /build-cost Hobgoblin II --runs 100

ARIA: ## Hobgoblin II x100

      ### Per-Unit Costs
      | Material | Each | x100 Total |
      |----------|------|------------|
      | Hobgoblin I | 1 | 100 |
      | Morphite | 2 | 200 |
      | ... | ... | ... |

      Total material cost: 42.5M (425K/unit)
      Market value (sell): 58.0M (580K/unit)
      Profit (before tax): 15.5M (155K/unit)

      Note: T2 manufacturing requires invention.
      This calculation assumes you have Hobgoblin II BPC.
```

---

## Implementation

### Phase 1: Basic Bill of Materials

**Deliverables:**
- [ ] Create `/build-cost` skill definition
- [ ] SDE blueprint lookup via `sde(action="blueprint_info")`
- [ ] Material price fetching via `market(action="prices")`
- [ ] Simple cost summation

**Core logic:**
```python
def calculate_build_cost(item_name: str, me_level: int = 0) -> dict:
    # 1. Get blueprint info
    bp = sde(action="blueprint_info", item=item_name)

    # 2. Apply ME reduction
    materials = apply_me_reduction(bp["materials"], me_level)

    # 3. Get prices
    prices = market(action="prices",
                   items=[m["name"] for m in materials])

    # 4. Calculate total
    total = sum(m["quantity"] * prices[m["name"]]["sell"]
                for m in materials)

    return {
        "materials": materials,
        "material_cost": total,
        "market_price": market(action="prices", items=[item_name]),
        # ...
    }
```

### Phase 2: Job Cost Calculation

**Deliverables:**
- [ ] Fetch industry indices from ESI
- [ ] Calculate job installation cost
- [ ] Factor in facility bonuses (NPC station vs. engineering complex)

**Job cost formula:**
```python
job_cost = base_value * system_index * runs
# base_value = sum of input materials' base prices (from SDE)
# system_index = 0.01 to 0.10+ depending on system activity
```

### Phase 3: T2/T3 Production Chains

**Deliverables:**
- [x] Component manufacturing chains (T2 components, reactions) ✅ COMPLETE
- [ ] Invention cost estimates (T2 BPC invention: datacores, decryptors)
- [x] Full "build from scratch" vs. "buy components" comparison ✅ COMPLETE

**Challenge:** T2 items require:
1. Invention (datacores, decryptors) → BPC
2. Component manufacturing (R.A.M., advanced materials)
3. Final assembly

Recommendation: Show component cost at market price by default, offer `--full-chain` for complete breakdown.

### Phase 4: Character Integration

**Deliverables:**
- [ ] Read character blueprints for ME/TE levels
- [ ] Factor in character industry skills (time reduction)
- [ ] Use character's facility bonus if known

---

## Skill Definition

```yaml
---
name: build-cost
description: Manufacturing profitability calculator. Compare build costs to market prices for any manufacturable item.
model: haiku
category: industry
triggers:
  - "/build-cost"
  - "should I build [item]"
  - "is building [item] profitable"
  - "manufacturing cost for [item]"
  - "build vs buy [item]"
  - "production profit [item]"
  - "what does it cost to make [item]"
requires_pilot: false
esi_scopes: []
data_sources:
  - reference/mechanics/industry_indices.json  # (if cached)
external_sources: []
has_persona_overlay: false
---
```

---

## Material Efficiency Formula

```python
def apply_me_reduction(base_quantity: int, me_level: int) -> int:
    """
    Apply Material Efficiency reduction.
    ME 10 = 10% reduction from base.
    Minimum 1 unit per run.
    """
    reduction = 1 - (me_level / 100)
    adjusted = max(1, math.ceil(base_quantity * reduction))
    return adjusted
```

Note: Actual game rounds per-run, then multiplies by runs. This can cause minor discrepancies for multi-run jobs.

---

## Edge Cases

### Items Without Blueprints

Some items (deadspace, officer, event) cannot be manufactured:
```
User: /build-cost Dread Guristas Shield Booster

ARIA: No blueprint exists for "Dread Guristas Shield Booster".
      This is a deadspace drop item (looted from DED sites).

      Current market value: 890M ISK (Jita sell)
```

### Blueprint Copies (BPCs)

BPCs have limited runs and may have different ME/TE from BPOs:
```
User: /build-cost Vexor Navy Issue (I have a BPC)

ARIA: Calculating for Vexor Navy Issue BPC.

      Note: BPC research levels vary. Assuming ME 0 / TE 0.
      Use --me and --te flags to specify your BPC's levels.
```

### Reactions and PI

Reaction and PI inputs have their own production chains:
```
User: /build-cost Tengu

ARIA: ## Tengu Manufacturing Analysis

      Subsystem Assembly Requirements:
      - Fullerene polymers (from wormhole gas reactions)
      - Ancient Salvage (looted)
      - ...

      Full chain calculation not available.
      Showing market cost for reaction inputs.
```

---

## Integration Points

### With SDE Tools

```python
# Blueprint lookup
bp_info = sde(action="blueprint_info", item="Vexor Navy Issue")

# Material name resolution (type_id → name)
mat_info = sde(action="item_info", item=type_id)
```

### With Market Tools

```python
# Batch price lookup
prices = market(action="prices",
               items=["Tritanium", "Pyerite", ...],
               region="jita")
```

### With Skill Tools (Future)

```python
# Check industry skills for time reduction
skills = pilot_skills(["Industry", "Advanced Industry", ...])
```

---

## Open Questions

1. **Include facility bonuses?**
   - Engineering complexes have material/time bonuses
   - Recommendation: Show "base cost" with note about potential bonuses

2. **How to handle reactions?**
   - Reactions are a separate system (moon goo → intermediate → fuel blocks)
   - Recommendation: Market price for reaction outputs, separate `/reactions` skill later

3. **Include opportunity cost?**
   - ISK tied up in materials could be invested elsewhere
   - Recommendation: Out of scope for MVP

4. **Profit per hour calculation?**
   - Common metric for comparing activities
   - Recommendation: Include for single items, complex for chains

---

## Example CLI Integration

```bash
# Quick check
uv run aria-esi build-cost "Vexor Navy Issue"

# With ME research
uv run aria-esi build-cost "Vexor Navy Issue" --me 10

# Multiple runs
uv run aria-esi build-cost "Hobgoblin II" --runs 100

# Different price source
uv run aria-esi build-cost "Megathron" --buy-from amarr
```

---

## Summary

| Aspect | Decision |
|--------|----------|
| Skill name | `/build-cost` |
| Blueprint data | SDE via `sde(action="blueprint_info")` |
| Price data | Market via `market(action="prices")` |
| ME/TE handling | User-specified, default to 0 |
| Job costs | Phase 2 (requires industry index data) |
| T2/T3 chains | Phase 3 (complex, market price fallback) |
| MVP output | Material cost vs. market price comparison |

This addresses a core industrialist workflow with existing data infrastructure.
