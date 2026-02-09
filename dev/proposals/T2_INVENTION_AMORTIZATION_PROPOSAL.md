# T2 Invention Cost Amortization Proposal

**Status:** PROPOSED (2026-02-02)
**Predecessor:** BUILD_COST_PROPOSAL.md (archived)
**Related:** `/build-cost` skill, `industry_costs.py`, `industry_chains.py`

---

## Executive Summary

Extend `/build-cost` to include invention costs when calculating T2 item profitability. Currently, the skill calculates material and job costs but ignores the amortized cost of inventing the T2 BPC itself. This leads to overstated profit margins for T2 production.

**Primary value:** Accurate T2 manufacturing profitability that accounts for invention inputs and success rates.

---

## Problem Statement

T2 manufacturing requires invention before production:

```
T1 BPC + Datacores + [Decryptor] → Invention Job → T2 BPC (probabilistic)
```

Current `/build-cost` for T2 items shows material costs assuming you already have a T2 BPC. This ignores:

1. **Datacore costs** - 2 types required per invention attempt
2. **T1 BPC cost** - Consumed on each attempt (copy time or market purchase)
3. **Decryptor costs** - Optional, affects ME/TE/runs on success
4. **Success probability** - Base ~25-40%, modified by skills
5. **Amortization** - Invention cost spread across expected successful runs

Without invention amortization, a T2 item showing "50M profit" might actually yield 20M after accounting for failed invention attempts.

---

## Invention Mechanics

### Inputs Per Attempt

| Input | Quantity | Consumed On |
|-------|----------|-------------|
| T1 BPC (1 run) | 1 | Every attempt |
| Datacore (type 1) | 2-4 | Every attempt |
| Datacore (type 2) | 2-4 | Every attempt |
| Decryptor | 0-1 | Every attempt (optional) |

### Success Probability

```python
base_chance = item_base_probability  # 25-40% depending on item
skill_modifier = 1 + (0.02 * encryption_skill) + (0.01 * datacore_skill_1) + (0.01 * datacore_skill_2)
decryptor_modifier = decryptor.probability_modifier  # -20% to +20%

final_chance = base_chance * skill_modifier * (1 + decryptor_modifier)
```

**Typical ranges:**
- No skills: 25-40%
- Max skills (V/V/V): 35-56%
- Max skills + Accelerant decryptor: 43-68%

### Decryptor Effects

| Decryptor | Prob Mod | ME Mod | TE Mod | Runs Mod | Use Case |
|-----------|----------|--------|--------|----------|----------|
| None | 0% | 0 | 0 | 0 | Baseline |
| Accelerant | +20% | +2 | +10 | +1 | Max success rate |
| Attainment | +80% | -1 | +4 | +4 | High volume, low margin |
| Augmentation | -40% | -2 | +2 | +9 | Volume over efficiency |
| Optimized Attainment | +90% | +1 | -2 | +2 | Best for expensive items |
| Parity | +50% | +1 | -2 | +0 | Balanced ME/success |
| Process | +10% | +3 | +6 | +0 | Best ME |
| Symmetry | 0% | +1 | +8 | +2 | TE focused |

---

## Amortization Formula

### Cost Per Successful BPC

```python
def calculate_invention_cost_per_bpc(
    datacore_1_cost: float,
    datacore_1_qty: int,
    datacore_2_cost: float,
    datacore_2_qty: int,
    t1_bpc_cost: float,
    decryptor_cost: float,
    success_probability: float,
    runs_per_success: int
) -> float:
    """
    Calculate amortized invention cost per T2 BPC run.
    """
    cost_per_attempt = (
        datacore_1_cost * datacore_1_qty +
        datacore_2_cost * datacore_2_qty +
        t1_bpc_cost +
        decryptor_cost
    )

    expected_attempts = 1 / success_probability
    expected_cost_per_bpc = cost_per_attempt * expected_attempts

    # Amortize across runs on successful BPC
    cost_per_run = expected_cost_per_bpc / runs_per_success

    return cost_per_run
```

### Example: Hobgoblin II

```
Inputs per attempt:
- Hobgoblin I BPC: ~5K ISK (copy time)
- Datacore - Mechanical Engineering x2: 80K ISK
- Datacore - Gallentean Starship Engineering x2: 60K ISK
- No decryptor

Success rate (max skills): 48%
Runs per BPC: 10

Cost per attempt: 145K ISK
Expected attempts per success: 2.08
Cost per successful BPC: 302K ISK
Cost per run (amortized): 30.2K ISK

This 30.2K must be added to material cost per unit.
```

---

## Data Sources

### SDE (via MCP)

```python
# Get invention requirements
sde(action="blueprint_info", item="Hobgoblin II")
# Returns:
# - invention: {
#     base_probability: 0.40,
#     datacores: [{type_id, quantity}, ...],
#     skills: [encryption_skill, datacore_skill_1, datacore_skill_2],
#     products: [{type_id, quantity, runs}]
#   }
```

**Note:** SDE `blueprint_info` may need extension to return invention data. Current implementation focuses on manufacturing. Check `src/aria_esi/services/sde.py` for schema.

### Market (via MCP)

```python
# Datacore prices
market(action="prices", items=[
    "Datacore - Mechanical Engineering",
    "Datacore - Gallentean Starship Engineering"
])

# Decryptor prices
market(action="prices", items=["Accelerant Decryptor"])
```

### ESI (optional)

```python
# Character invention skills for probability calculation
# - Encryption skill (per race)
# - Datacore skills (per discipline)
```

---

## Proposed Implementation

### Phase 1: Static Invention Data

**Deliverables:**
- [ ] Add invention data to SDE blueprint queries
- [ ] Create `reference/industry/invention_requirements.json` for datacore mappings
- [ ] Add decryptor definitions to `reference/industry/decryptors.json`

**Scope:** Data availability, no calculation logic yet.

### Phase 2: Invention Cost Calculator

**Deliverables:**
- [ ] `calculate_invention_cost()` function in `industry_costs.py`
- [ ] Success probability calculation with skill modifiers
- [ ] Decryptor effect application
- [ ] Amortization across expected runs

**Core logic:**
```python
def calculate_invention_cost(
    item_name: str,
    encryption_skill: int = 0,
    datacore_skill_1: int = 0,
    datacore_skill_2: int = 0,
    decryptor: str | None = None,
    region: str = "jita"
) -> InventionCost:
    """Calculate amortized invention cost per T2 item produced."""
    # 1. Get invention requirements from SDE
    # 2. Fetch datacore/decryptor prices
    # 3. Calculate success probability
    # 4. Compute amortized cost per run
    pass
```

### Phase 3: Integration with `/build-cost`

**Deliverables:**
- [ ] Auto-detect T2 items and include invention costs
- [ ] `--include-invention` flag (default: True for T2)
- [ ] `--decryptor <name>` flag for decryptor selection
- [ ] `--invention-skills <enc>/<dc1>/<dc2>` flag
- [ ] Clear breakdown in output separating invention vs. production costs

**Updated output example:**
```
User: /build-cost Hobgoblin II --runs 100

ARIA: ## Hobgoblin II x100 Manufacturing Analysis

### Invention Costs (amortized)
| Component | Per Attempt | Expected Attempts | Per BPC | Per Unit |
|-----------|-------------|-------------------|---------|----------|
| Hobgoblin I BPC | 5K | 2.08 | 10.4K | 1.0K |
| Datacore - Mech Eng x2 | 80K | 2.08 | 166K | 16.6K |
| Datacore - Gal Ship Eng x2 | 60K | 2.08 | 125K | 12.5K |
| **Invention Total** | 145K | | 302K | **30.1K** |

Success probability: 48% (assuming max skills)
Runs per successful BPC: 10
BPCs needed for 100 units: 10

### Production Costs (ME 2 from invention)
| Material | Qty/Unit | x100 | Unit Cost | Total |
|----------|----------|------|-----------|-------|
| Hobgoblin I | 1 | 100 | 45K | 4.5M |
| Morphite | 2 | 196 | 8.5K | 1.7M |
| ... | | | | |
| **Materials** | | | | **8.2M** |
| Job Cost | | | 2K | 200K |
| **Production Total** | | | | **8.4M** |

### Summary
| Component | Total | Per Unit |
|-----------|-------|----------|
| Invention | 3.0M | 30.1K |
| Production | 8.4M | 84.0K |
| **Total Cost** | **11.4M** | **114.1K** |

### Profitability
| Metric | Value |
|--------|-------|
| Market (Jita sell) | 580K/unit |
| Total revenue | 58.0M |
| Gross profit | 46.6M |
| Margin | 408% |
| Profit/unit | 466K |

Note: Invention costs assume max skills (V/V/V).
Use --invention-skills to specify actual levels.
```

### Phase 4: Character Integration

**Deliverables:**
- [ ] Read character invention skills from ESI
- [ ] `--use-character` applies actual skill levels to probability
- [ ] Show skill-adjusted vs. max-skill comparison

---

## Edge Cases

### Items Without Invention

Capital ships, T3, and some items use different production paths:
```
User: /build-cost Revelation

ARIA: Revelation is a capital ship.
      Capital production does not use standard invention.
      Showing material costs only.
```

### Faction/Deadspace Items

Cannot be invented:
```
User: /build-cost Dread Guristas Warp Scrambler

ARIA: "Dread Guristas Warp Scrambler" is faction loot.
      No manufacturing path exists.
```

### T1 Items

No invention required:
```
User: /build-cost Hobgoblin I

ARIA: (standard T1 output, no invention section)
```

### Rigs

T2 rigs use invention but have different datacore requirements:
```
User: /build-cost Medium Capacitor Control Circuit II

ARIA: (include rig-specific invention datacores)
```

---

## Reference Data Files

### `reference/industry/decryptors.json`

```json
{
  "decryptors": [
    {
      "name": "Accelerant Decryptor",
      "type_id": 34201,
      "probability_modifier": 0.20,
      "me_modifier": 2,
      "te_modifier": 10,
      "runs_modifier": 1
    },
    ...
  ]
}
```

### `reference/industry/invention_datacores.json`

```json
{
  "categories": {
    "drones": {
      "encryption_skill": "Gallentean Encryption Methods",
      "datacores": [
        "Datacore - Mechanical Engineering",
        "Datacore - Gallentean Starship Engineering"
      ]
    },
    "caldari_ships": {
      "encryption_skill": "Caldari Encryption Methods",
      "datacores": [
        "Datacore - Caldari Starship Engineering",
        "Datacore - Mechanical Engineering"
      ]
    },
    ...
  }
}
```

---

## Testing Strategy

### Unit Tests

```python
def test_invention_probability_no_skills():
    """Base probability with no skill modifiers."""
    prob = calculate_invention_probability(
        base_chance=0.40,
        encryption_skill=0,
        datacore_skill_1=0,
        datacore_skill_2=0
    )
    assert prob == 0.40

def test_invention_probability_max_skills():
    """Max skills should increase probability."""
    prob = calculate_invention_probability(
        base_chance=0.40,
        encryption_skill=5,
        datacore_skill_1=5,
        datacore_skill_2=5
    )
    assert prob == pytest.approx(0.56, rel=0.01)

def test_amortization_calculation():
    """Verify cost spread across expected runs."""
    cost = calculate_invention_cost_per_run(
        cost_per_attempt=145000,
        success_probability=0.48,
        runs_per_success=10
    )
    # 145000 / 0.48 / 10 = 30,208
    assert cost == pytest.approx(30208, rel=100)
```

### Integration Tests

```python
def test_build_cost_t2_includes_invention():
    """T2 items should include invention costs."""
    result = build_cost("Hobgoblin II")
    assert "invention_cost" in result
    assert result["invention_cost"]["per_unit"] > 0

def test_build_cost_t1_no_invention():
    """T1 items should not include invention section."""
    result = build_cost("Hobgoblin I")
    assert "invention_cost" not in result or result["invention_cost"] is None
```

---

## Open Questions

1. **T1 BPC cost estimation**
   - Option A: Assume copied (factor in copy time as opportunity cost)
   - Option B: Assume purchased (use market price)
   - Recommendation: Default to copy time, flag for market price

2. **Skill level assumptions**
   - Option A: Assume max skills (optimistic)
   - Option B: Assume no skills (pessimistic)
   - Option C: Require explicit specification
   - Recommendation: Default to max skills with clear note, `--use-character` for actual

3. **Decryptor optimization**
   - Should we suggest optimal decryptor based on item value?
   - Recommendation: Out of scope for MVP, add as enhancement

---

## Success Criteria

- [ ] T2 items in `/build-cost` show invention cost breakdown
- [ ] Profit margins reflect true cost including invention
- [ ] Success probability adjustable via skill flags
- [ ] Decryptor selection supported with effect preview
- [ ] Clear separation between invention and production costs in output

---

## Summary

| Aspect | Decision |
|--------|----------|
| Scope | Invention cost amortization for T2 items |
| Integration | Extends existing `/build-cost` skill |
| Data sources | SDE (invention reqs), Market (datacores), ESI (skills) |
| Default behavior | Include invention for T2, max skill assumption |
| MVP output | Amortized cost per unit added to build cost |

This completes the manufacturing profitability picture for T2 production.
