# Manufacturing Reference

Complete guide to producing items from blueprints.

## Blueprint Types

| Type | Abbreviation | Runs | Researchable | Source |
|------|--------------|------|--------------|--------|
| Blueprint Original | BPO | Infinite | Yes | NPC market |
| Blueprint Copy | BPC | Limited | No | Copying BPOs, Invention, Drops |

## Material Efficiency (ME) Research

Reduces material requirements per run.

| ME Level | Total Reduction | Research Time (Rank 1) |
|----------|-----------------|------------------------|
| 0 | 0% | - |
| 1 | -1% | ~2 minutes |
| 2 | -2% | ~6 minutes |
| 3 | -3% | ~14 minutes |
| 4 | -4% | ~33 minutes |
| 5 | -5% | ~1 hour 16 min |
| 6 | -6% | ~2 hours 31 min |
| 7 | -7% | ~5 hours 3 min |
| 8 | -8% | ~10 hours |
| 9 | -9% | ~20 hours |
| 10 | -10% (max) | ~1 day 18 hours |

**Note:** Higher rank blueprints multiply these times. Capitals are rank 200+.

## Time Efficiency (TE) Research

Reduces manufacturing duration.

| TE Level | Build Time Reduction |
|----------|---------------------|
| 0 | 0% |
| 2 | -4% |
| 4 | -8% |
| 6 | -12% |
| 8 | -16% |
| 10 | -20% (max) |

TE has 10 levels but each grants 2% reduction.

## Manufacturing Job Cost

```
Total Cost = Est. Item Value × ((System Index × Structure Bonus) + Taxes)
```

### Tax Components

| Tax Type | Rate |
|----------|------|
| NPC Facility Tax | 0.25% |
| SCC Surcharge | 4% |
| Alpha Clone Tax | 0.25% (Alpha only) |
| Player Structure Tax | Variable (0-10%) |

### System Cost Index

Calculated from manufacturing activity over past 28 days:
- Low activity system = Low index = Cheaper
- High activity system (Jita) = High index = Expensive

**Tip:** Manufacture in quieter systems to reduce costs.

## Concurrent Job Limits

| Skill | Jobs Granted |
|-------|--------------|
| Base (no skills) | 1 |
| Mass Production I-V | +1 per level (max +5) |
| Advanced Mass Production I-V | +1 per level (max +5) |
| **Maximum Total** | **11 jobs** |

## Material Rounding

**Critical:** Rounding happens per JOB, not per run.

Example (10 units required per run, ME 10 = -10%):
- 1 job × 3 runs: 10 × 3 × 0.9 = 27 → rounds to 27
- 3 jobs × 1 run: (10 × 1 × 0.9) × 3 = 9 × 3 = 27

BUT with smaller quantities:
- 1 job × 3 runs: 2 × 3 × 0.9 = 5.4 → rounds to 6
- 3 jobs × 1 run: (2 × 1 × 0.9 = 1.8 → 2) × 3 = 6

**Always batch runs in single jobs when possible.**

## Copying

Creates BPCs from BPOs:

| Item Type | Max Runs per Copy |
|-----------|-------------------|
| Ships | 10 runs |
| Modules | Up to 600 runs |
| Ammunition | Up to 1,500 runs |

- Copy time = 80% of build time × runs
- BPCs inherit ME/TE from source BPO
- Cannot research BPCs

## Invention (T2 Manufacturing)

Converts T1 BPCs into T2 BPCs:

1. Acquire T1 BPC (copy from BPO or buy)
2. Install invention job with datacores
3. Success = T2 BPC (limited runs, fixed ME/TE)
4. Failure = Materials lost

**Base success rate:** ~25-40% depending on skills/decryptors

T2 BPCs always start at ME -2 / TE -4 (penalty, not bonus).

## Facility Bonuses

| Facility Type | ME Bonus | TE Bonus |
|---------------|----------|----------|
| NPC Station | 0% | 0% |
| Raitaru (Eng Complex) | 1% | 15% |
| Azbel (Eng Complex) | 1% | 20% |
| Sotiyo (Eng Complex) | 1% | 30% |

Rigs provide additional bonuses based on security status.

## Self-Sufficient Manufacturing Workflow

1. **Acquire BPO** from NPC market
2. **Research** to ME 10 / TE 10
3. **Mine/acquire** raw materials
4. **Reprocess** ore to minerals
5. **Install job** at facility
6. **Deliver** completed items

## Recommended Starting BPOs

For self-sufficient gameplay:

| Category | Priority BPOs |
|----------|---------------|
| Ammo | Antimatter charges (your hybrid ammo) |
| Drones | Light/Medium combat drones |
| Modules | Damage mods, tank mods, prop mods |
| Ships | Start with frigates, work up |

---
Source: EVE University Wiki
Last updated: YC128 (2026)
