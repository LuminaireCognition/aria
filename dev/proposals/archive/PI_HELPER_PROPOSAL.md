# Planetary Interaction Helper Proposal

**Status:** ✅ COMPLETE (2026-02-02)
**Completed:** All 4 phases

> **Validation (2026-02-02):** Phase 4 (location-aware planning) is COMPLETE:
> - `_calculate_distances_from_home()` added to `commands/pi.py` - uses universe graph for O(1) routing
> - `pi-near` command now calculates jump distances from home systems
> - Results filtered by `--jumps` parameter (default 10)
> - Results sorted by: home systems first, then by distance, then by planet coverage
> - Output includes `distance_jumps`, `is_home`, and `max_jumps` fields
> - Integration with `NavigationService` and `UniverseGraph` for efficient pathfinding
>
> **Validation (2026-02-02):** Phase 3 (market profitability) is COMPLETE by design:
> - SKILL.md contains full `/pi profit` algorithm (lines 55-113) with pseudocode
> - Documented workflow: extract schematic → `market(action="prices")` → calculate profit
> - Works via AI-executed algorithm at runtime (not backend automation)
> - Schema defined in `tests/skills/schemas/pi.schema.yaml` (ProfitAnalysisResponse)
> - All PI products have type_ids in reference data for market lookups

---

## Executive Summary

Add a `/pi` skill that helps pilots plan and optimize Planetary Interaction colonies. PI is universally confusing for new players and tedious to plan for veterans. Complete reference data already exists in `reference/mechanics/planetary-interaction.json`.

**Primary value:** Answer "what planets do I need for X?" without external tools.

---

## Problem Statement

Planetary Interaction has steep learning curves:

1. **Production chains are opaque** - P0 → P1 → P2 → P3 → P4 requires memorizing dozens of recipes
2. **Planet selection is confusing** - Which planet types have which resources?
3. **Math is tedious** - Input/output ratios, cycle times, extractor head optimization
4. **No in-game planning tools** - Players rely on external spreadsheets or trial-and-error

ARIA already has the reference data. It just isn't exposed to users.

---

## Existing Data

`reference/mechanics/planetary-interaction.json` contains:

```json
{
  "production_constants": {
    "p0_to_p1": { "input_qty": 3000, "output_qty": 20, "cycle_seconds": 1800 },
    "p1_to_p2": { "input_qty_each": 40, "output_qty": 5, "cycle_seconds": 3600 },
    "p2_to_p3": { "input_qty_each": 10, "output_qty": 3, "cycle_seconds": 3600 },
    "p3_to_p4": { "input_qty_p3": 6, "input_qty_p1": 40, "output_qty": 1 }
  },
  "planet_resources": {
    "Barren": ["Aqueous Liquids", "Base Metals", ...],
    "Gas": ["Aqueous Liquids", "Noble Gas", ...],
    ...
  },
  "p0_to_p1_recipes": { ... },
  "p1_to_p2_recipes": { ... },
  "p2_to_p3_recipes": { ... },
  "p3_to_p4_recipes": { ... }
}
```

This is complete and verified. No additional data collection needed.

---

## Proposed Skill: `/pi`

### Triggers

```yaml
triggers:
  - "/pi"
  - "planetary interaction"
  - "PI help"
  - "what planets for [item]"
  - "how to make [PI item]"
  - "PI production chain"
  - "planet resources"
```

### Commands

| Command | Description |
|---------|-------------|
| `/pi chain <item>` | Show full production chain from P0 to target |
| `/pi planets <resource>` | Which planet types have this resource |
| `/pi recipe <item>` | Inputs and outputs for a specific product |
| `/pi plan <item> [quantity]` | Full colony plan with planet count estimates |
| `/pi compare <item1> <item2>` | Compare profitability (with market integration) |

### Example Interactions

**Chain lookup:**
```
User: /pi chain Robotics

ARIA: ## Robotics (P2) Production Chain

      P0 → P1:
      ├─ Base Metals → Reactive Metals (Barren, Lava, Plasma)
      └─ Noble Metals → Precious Metals (Barren, Plasma)

      P1 → P2:
      └─ Reactive Metals + Precious Metals → Robotics

      Planets needed: 1 (Barren covers both P0 resources)

      Cycle: 40 Reactive + 40 Precious → 5 Robotics per hour
```

**Planet lookup:**
```
User: What planets have Aqueous Liquids?

ARIA: ## Aqueous Liquids Availability

      | Planet Type | Other Resources |
      |-------------|-----------------|
      | Barren | Base Metals, Carbon Compounds, Heavy Metals, ... |
      | Gas | Base Metals, Heavy Metals, Ionic Solutions, ... |
      | Ice | Heavy Metals, Noble Gas, Planktic Colonies |
      | Oceanic | Carbon Compounds, Complex Organisms, ... |
      | Storm | Base Metals, Heavy Metals, Ionic Solutions, ... |
      | Temperate | Autotrophs, Carbon Compounds, Complex Organisms, ... |

      Most versatile: Barren (7 resources) or Oceanic (7 resources)
```

**Production planning:**
```
User: /pi plan Wetware Mainframe 10/day

ARIA: ## Wetware Mainframe Production Plan

      Target: 10 units/day (P4)

      Required colonies:
      ├─ 1x Oceanic: Aqueous Liquids, Complex Organisms
      ├─ 1x Temperate: Autotrophs, Carbon Compounds
      ├─ 1x Barren: Base Metals, Noble Metals (factory planet)
      └─ Total: 3 planets minimum

      Factory setup:
      ├─ P3 production: Biotech Research Reports, Cryoprotectant Solution
      └─ P4 assembly: Barren planet (required for P4)

      Skill requirements:
      ├─ Command Center Upgrades IV+ (for CCU capacity)
      ├─ Interplanetary Consolidation III+ (3 planets)
      └─ Planetology III+ (resource scanning)

      Estimated setup cost: ~15M ISK (command centers + infrastructure)
```

---

## Implementation

### Phase 1: Chain and Recipe Lookups

**Deliverables:**
- [ ] Create `/pi` skill definition
- [ ] Load `planetary-interaction.json` on skill invocation
- [ ] Implement chain traversal (target → inputs recursively)
- [ ] Implement planet resource lookup

**Logic:**
```python
def get_production_chain(target_item: str, pi_data: dict) -> dict:
    """
    Recursively build production chain from P4/P3/P2 down to P0.
    Returns tree structure with inputs at each tier.
    """
    # Check P4 recipes first, then P3, P2, P1
    # For each input, recurse until P0 (raw resources)
    pass

def find_planets_for_resources(resources: list[str], pi_data: dict) -> list[str]:
    """
    Find planet types that have ALL specified resources.
    Used for "can I do this on one planet?" questions.
    """
    pass
```

### Phase 2: Production Math

**Deliverables:**
- [ ] Calculate input/output ratios for full chains
- [ ] Estimate extractor head requirements
- [ ] CCU capacity planning

**Key formulas:**
```python
# P0 → P1: 3000 P0 → 20 P1 per 30min cycle
P1_PER_HOUR = 40  # (20 * 2 cycles)

# P1 → P2: 40+40 P1 → 5 P2 per 60min cycle
P2_PER_HOUR = 5
P1_CONSUMED_PER_P2 = 16  # (80 P1 / 5 P2)

# Extractor output varies by cycle length:
# 15min cycles: high yield, high maintenance
# 24h cycles: low yield, low maintenance
```

### Phase 3: Market Integration

**Deliverables:**
- [ ] Fetch current prices for PI commodities via `market(action="prices")`
- [ ] Calculate ISK/hour for different products
- [ ] Compare products by profitability

**Example output:**
```
/pi compare Robotics "Mechanical Parts"

## PI Profitability Comparison

| Product | Jita Sell | ISK/hour* | Complexity |
|---------|-----------|-----------|------------|
| Robotics | 12,500 | 62,500 | 1 planet |
| Mechanical Parts | 8,200 | 41,000 | 1 planet |

* Based on max factory output, not including extraction time

Recommendation: Robotics has 52% higher returns for same effort.
```

### Phase 4: Location-Aware Planning

**Deliverables:**
- [x] Integration with pilot's home system from profile
- [x] "Best planets near X" queries using universe data
- [x] Tax rate awareness (NPC vs player POCOs)

> **Implementation (2026-02-02):**
> - Home systems loaded from `userdata/config.json` via `_load_home_systems()`
> - Distance calculation via `_calculate_distances_from_home()` using `NavigationService`
> - `pi-near` command filters by `--jumps` and sorts by proximity
> - POCO tax documented in SKILL.md with `--poco-tax` parameter for profit calculations

---

## Skill Definition

```yaml
---
name: pi
description: Planetary Interaction production planning and optimization. Use for PI chains, planet selection, and colony planning.
model: haiku
category: industry
triggers:
  - "/pi"
  - "planetary interaction"
  - "PI help"
  - "what planets for [item]"
  - "how to make [PI item]"
  - "PI production chain"
  - "planet resources"
  - "PI setup"
requires_pilot: false
esi_scopes: []
data_sources:
  - reference/mechanics/planetary-interaction.json
has_persona_overlay: false
---
```

---

## Data Verification

The PI reference data should be verified against:
- EVE University wiki (primary source)
- Fuzzwork PI tools (secondary validation)
- In-game PI interface (ground truth)

Current data was verified 2026-01-29. Production constants and recipes are stable (rarely changed by CCP).

---

## User Experience Goals

1. **Zero external tools** - All PI planning within ARIA
2. **Progressive disclosure** - Simple questions get simple answers
3. **Actionable output** - "You need X planets" not just data dumps
4. **Skill-aware** - Warn if pilot lacks required PI skills

---

## Compatibility

### With Existing Systems

- **Market tools:** Use `market(action="prices")` for profitability
- **Universe tools:** Use for planet location queries (future)
- **Skill tools:** Check PI skill requirements

### With Pilot Profile

- Read home system for location-aware suggestions
- Check `self_sufficient` flag for LP store PI alternatives

---

## Open Questions

1. **Include Equinox colony materials?**
   - These use sovereignty mechanics, not traditional PI
   - Recommendation: Exclude from initial implementation, note in help

2. **Track active colonies?**
   - ESI has planetary data but requires additional scope
   - Recommendation: Phase 2+ feature, not MVP

3. **Tax calculation?**
   - POCO taxes vary by owner
   - Recommendation: Use default 10% NPC tax, note it's configurable

---

## Summary

| Aspect | Decision |
|--------|----------|
| Skill name | `/pi` |
| Data source | `reference/mechanics/planetary-interaction.json` |
| Core features | Chain lookup, planet finder, recipe math |
| Market integration | Phase 3 (profitability comparison) |
| ESI integration | None required for MVP |
| Complexity | Low - data complete, logic straightforward |

This skill addresses a universal pain point with data ARIA already has.
