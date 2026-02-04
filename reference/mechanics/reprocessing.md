# Reprocessing Reference

Guide to maximizing mineral yield from ore, ice, and loot.

## Core Formula (NPC Stations)

```
Yield = Base × (1 + Reprocessing × 0.03) × (1 + Reproc Eff × 0.02) × (1 + Ore Skill × 0.02) × (1 + Implant)
```

## Skill Effects

| Skill | Requirement | Effect | Max Bonus |
|-------|-------------|--------|-----------|
| **Reprocessing** | None | +3%/level | +15% at V |
| **Reprocessing Efficiency** | Reprocessing IV | +2%/level | +10% at V |
| **Ore-Specific Skills** | Reprocessing V | +2%/level | +10% at V |

### Ore-Specific Skills

| Skill | Ores Covered |
|-------|--------------|
| Simple Ore Processing | Veldspar, Scordite, Pyroxeres, Plagioclase |
| Coherent Ore Processing | Omber, Kernite, Jaspet, Hemorphite, Hedbergite |
| Complex Ore Processing | Gneiss, Dark Ochre, Crokite, Spodumain, Bistot, Arkonor |
| Mercoxit Ore Processing | Mercoxit |
| Variegated Ore Processing | Eifyrium, Ducinium |
| Ice Processing | All ice types |
| Abyssal Ore Processing | Bezdnacine, Rakovene, Talassonite |
| Scrapmetal Processing | Modules, ships, loot |

## Station Types Comparison

### NPC Stations

| Station Quality | Base Efficiency |
|-----------------|-----------------|
| Poor | 30% |
| Average | 35% |
| Good | 50% |

**Tax:** 5% at 0 standings, scales to 0% at 6.67 standings.

### Upwell Structures (Player-Owned)

| Structure | Base Efficiency |
|-----------|-----------------|
| Citadel / Engineering Complex | 50% |
| Athanor (Moon Mining) | 51% |
| Tatara (Refinery) | 52% |

**Rig Bonuses (stacking):**

| Security | T1 Rig | T2 Rig |
|----------|--------|--------|
| Highsec | +1% | +2% |
| Lowsec | +3% | +4% |
| Nullsec/WH | +4% | +5% |

## Maximum Yields

| Setup | Max Yield |
|-------|-----------|
| NPC Station (50% base, perfect skills, 6.67 standings) | 70% |
| Tatara (nullsec, T2 rigs, perfect skills, implant) | 90.6% |
| Typical highsec Upwell (T2 rigs, decent skills) | 75-80% |

## Reprocessing Implants

| Implant | Bonus | Slot |
|---------|-------|------|
| Zainou 'Beancounter' RX-801 | +1% | 10 |
| Zainou 'Beancounter' RX-802 | +2% | 10 |
| Zainou 'Beancounter' RX-804 | +4% | 10 |

## Practical Yield Table

With **Reprocessing V + Reprocessing Efficiency IV + Ore Skill III** at a 50% NPC station:

```
Base:     50.0%
Reproc:   × 1.15 = 57.5%
Eff:      × 1.08 = 62.1%
Ore:      × 1.06 = 65.8%
```

**Effective yield: ~66%** (before standings tax)

## Self-Sufficient Strategy

1. **Train Reprocessing V first** - Biggest multiplier
2. **Train Reprocessing Efficiency IV** - Good return on investment
3. **Train relevant Ore Processing to III** - Diminishing returns after
4. **Find a 50% base station** - Check station info
5. **Grind standings to 6.67** - Eliminates tax

**Alternative:** Use player-owned Upwell structures (often public access, better rates, but check standings).

## Batch Processing Note

```
Rounding is per JOB, not per run.
```

A single job with 3 runs uses LESS material than 3 separate 1-run jobs. Always batch when possible.

## Scrapmetal Processing

Loot and salvage use **Scrapmetal Processing** skill instead of ore skills.

Particularly valuable for:
- Mission loot (modules)
- Salvage from wrecks
- Recovered ship hulls

**Tip:** Reprocess cheap meta modules for minerals rather than selling to NPCs.

## Compression Note

Compressed ore (100:1 ratio):
- Same mineral output when reprocessed
- Requires Upwell structure
- Essential for hauling to better facilities

---
Source: EVE University Wiki
Last updated: YC128 (2026)
