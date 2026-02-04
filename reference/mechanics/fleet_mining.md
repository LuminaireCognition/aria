# Fleet Mining Guide

Complete reference for coordinated mining operations with 2-5 pilots. Covers fleet roles, boost mechanics, compression, and efficient coordination.

## Why Fleet Mining?

| Aspect | Solo Mining | Fleet Mining |
|--------|-------------|--------------|
| Yield | Base | +25-60% with boosts |
| Tank | Limited | Shared defense |
| Hauling | Interrupts mining | Dedicated hauler |
| Efficiency | Good | Excellent |
| Social | Alone | Shared experience |

Fleet mining is significantly more efficient than solo operations when properly coordinated.

---

## Fleet Roles

### The Four Core Roles

| Role | Ship Type | Primary Task |
|------|-----------|--------------|
| **Booster** | Porpoise, Orca, Rorqual | Provide mining boosts |
| **Miner** | Barge, Exhumer | Extract ore |
| **Hauler** | Industrial, Miasmos | Move ore to station |
| **Security** | Combat ship | Protect fleet |

### Role Priority by Fleet Size

| Fleet Size | Roles Needed |
|------------|--------------|
| 2 pilots | Miner + Miner (one with boosts) |
| 3 pilots | Booster + 2 Miners |
| 4 pilots | Booster + 2 Miners + Hauler |
| 5 pilots | Booster + 3 Miners + Hauler |
| 5+ pilots | Add Security as needed |

---

## Fleet Booster

The booster dramatically increases fleet mining efficiency.

### Boosting Ships

| Ship | Boosts | Other Features | Skill Requirement |
|------|--------|----------------|-------------------|
| **Porpoise** | Mining Foreman Bursts | Ore hold, some defense | Mining Foreman I |
| **Orca** | Mining Foreman Bursts | Large ore hold, hangar | Mining Director I |
| **Rorqual** | Mining Foreman Bursts | Compression, PANIC | Capital Industrial V |

### Mining Foreman Bursts

Boosters use **Mining Foreman Burst** modules:

| Burst Type | Effect |
|------------|--------|
| Mining Laser Field Enhancement | +Mining yield |
| Mining Laser Optimization | -Cycle time (faster mining) |
| Mining Equipment Preservation | -Crystal volatility |

**Only one burst of each type active at a time.**

### Burst Strength

Burst effectiveness depends on:
- **Mining Foreman** skill (2% per level)
- **Mining Director** skill (5% per level)
- **Mindlink Implant** (+25% with Mining Foreman Mindlink)
- **Ship bonus** (varies by hull)

### Burst Range

| Default Range | With Skills | With Implant |
|---------------|-------------|--------------|
| ~15 km | ~25 km | ~50+ km |

Fleet members must be **within burst range** to receive bonuses.

---

## Mining Boost Mechanics

### How Boosts Work

1. Booster activates Mining Foreman Burst
2. Burst cycles (~60 seconds)
3. Fleet members in range receive buff
4. Buff lasts until burst cycles again

### Boost Stacking

- **Multiple boosters do NOT stack** - only the strongest applies
- All three burst types CAN be active simultaneously
- One booster can run all three bursts

### Calculated Boost Values

| Setup | Yield Boost | Cycle Reduction |
|-------|-------------|-----------------|
| Porpoise (basic) | ~15% | ~15% |
| Porpoise (skilled) | ~25% | ~25% |
| Orca (basic) | ~25% | ~25% |
| Orca (max skills) | ~40% | ~40% |
| Orca (max + mindlink) | ~57% | ~57% |

### Effective Yield Increase

Combining yield boost AND cycle time reduction:

```
Effective Increase = (1 + Yield%) / (1 - Cycle%) - 1

Example: 40% yield + 40% cycle reduction
= (1.40) / (0.60) - 1 = 133% effective increase
```

**An Orca with max skills more than doubles fleet mining yield.**

---

## Mining Ships

> **Reference:** See `reference/mechanics/mining_ships.md` for complete ship specifications.

### Fleet Role Recommendations

| Situation | Recommended Ship |
|-----------|------------------|
| Highsec (gankers present) | Procurer/Skiff |
| Highsec (safe system) | Retriever/Mackinaw |
| With dedicated hauler | Covetor/Hulk |
| Lowsec/Nullsec | Procurer/Skiff |
| Solo AFK | Retriever/Mackinaw |

---

## Compression

Compression reduces ore volume for easier transport.

### What is Compression?

| State | Volume | Transport |
|-------|--------|-----------|
| Raw ore | 100% | Difficult |
| Compressed ore | ~1% | Easy |

### Where to Compress

| Location | Compression Available |
|----------|----------------------|
| Orca | No (removed) |
| Rorqual | Yes (Industrial Core) |
| Athanor/Tatara | Yes (Reprocessing service) |
| NPC Station | No |

**Note:** As of current mechanics, field compression requires a Rorqual or structure.

### Compression Workflow

**With Structure:**
1. Mine ore into fleet hangar/jetcan
2. Haul raw ore to structure
3. Compress at structure
4. Haul compressed ore to market

**With Rorqual:**
1. Mine ore
2. Transfer to Rorqual
3. Rorqual compresses in-field
4. Haul compressed ore

### Compression Efficiency

Compression has no yield loss - mineral content is identical.

---

## Fleet Compositions

### 2-Person Fleet

**Minimum viable fleet mining.**

| Pilot | Ship | Role |
|-------|------|------|
| 1 | Porpoise | Boost + some mining |
| 2 | Retriever/Procurer | Primary miner |

**Workflow:**
- Porpoise provides boosts
- Both mine (Porpoise has mining drones)
- Miner hauls when full
- ~40% yield increase over solo

### 3-Person Fleet

**Efficient small operation.**

| Pilot | Ship | Role |
|-------|------|------|
| 1 | Porpoise/Orca | Booster |
| 2 | Retriever/Covetor | Miner |
| 3 | Retriever/Covetor | Miner |

**Workflow:**
- Booster maintains bursts
- Miners focus on extraction
- Miners take turns hauling OR jetcan mine
- Excellent efficiency

### 4-Person Fleet

**Full roles covered.**

| Pilot | Ship | Role |
|-------|------|------|
| 1 | Orca | Booster + storage |
| 2 | Covetor/Hulk | Miner |
| 3 | Covetor/Hulk | Miner |
| 4 | Miasmos | Hauler |

**Workflow:**
- Orca provides boosts and fleet hangar storage
- Miners deposit into Orca fleet hangar
- Hauler transfers from Orca to station
- Miners never stop mining

### 5-Person Fleet

**Maximum small-gang efficiency.**

| Pilot | Ship | Role |
|-------|------|------|
| 1 | Orca | Booster |
| 2 | Covetor/Hulk | Miner |
| 3 | Covetor/Hulk | Miner |
| 4 | Covetor/Hulk | Miner |
| 5 | Miasmos | Hauler |

**Alternative 5-person (dangerous space):**

| Pilot | Ship | Role |
|-------|------|------|
| 1 | Orca | Booster |
| 2 | Procurer/Skiff | Tanky miner |
| 3 | Procurer/Skiff | Tanky miner |
| 4 | Procurer/Skiff | Tanky miner |
| 5 | Combat ship | Security |

---

## Coordination Tips

### Communication

| Method | Use Case |
|--------|----------|
| Fleet chat | General coordination |
| Voice comms | Real-time alerts, social |
| Fleet broadcast | "Need shields," target calling |

### Watchlist Setup

Add fleet members to watchlist:
1. Right-click fleet member → Add to Watchlist
2. Monitor their shield/armor/hull
3. React quickly to attacks

### Belt Management

| Practice | Benefit |
|----------|---------|
| Start at different rocks | No competition |
| Call out when rock depletes | Others know to skip it |
| Work toward center | Natural convergence |
| Bookmark large rocks | Return if interrupted |

### Hauler Coordination

| Practice | Benefit |
|----------|---------|
| Announce when heading to station | Miners know storage is full |
| Announce when returning | Miners prepare ore |
| Use fleet hangar (Orca) | Continuous mining |
| Jetcan backup | If fleet hangar full |

### Defense Protocol

**When hostiles appear:**

1. **Booster broadcasts:** "Align [station]"
2. **Miners align immediately**
3. **If attack begins:** Booster broadcasts "Warp [station]"
4. **Miners warp out**
5. **Don't be a hero** - ships are replaceable

### Loot Distribution

| Method | Best For |
|--------|----------|
| Equal split | Casual groups |
| By contribution | Serious operations |
| Corp wallet | Corp fleets |
| Booster gets cut | Compensate boost pilot |

**Common split:** Booster gets 10-20% extra for providing ship/skills.

---

## ISK Efficiency

### Yield Comparison

| Setup | Approx m³/hour | ISK/hour* |
|-------|----------------|-----------|
| Solo Venture | 500 | 2-4M |
| Solo Retriever | 1,200 | 5-10M |
| Boosted Retriever | 1,900 | 8-15M |
| Solo Covetor | 1,600 | 7-12M |
| Boosted Covetor | 2,500 | 10-20M |
| Boosted Hulk | 3,200 | 13-25M |

*ISK values depend heavily on ore type and market prices.

### Break-Even for Booster

A booster is worthwhile when:
```
(Fleet yield with boosts) > (Fleet yield without) + (Booster's solo yield)
```

**Rule of thumb:** 3+ miners makes a dedicated booster efficient.

---

## Safety Considerations

### Highsec Ganking

| Risk Factor | Mitigation |
|-------------|------------|
| Expensive ship | Fly what you can lose |
| AFK mining | Stay at keyboard |
| Known gank systems | Check zkillboard |
| Full ore hold | Haul regularly |

### CODE/Ganker Response

If gankers appear:
1. **Don't panic** - align to station
2. **Watch for scout** (often in Catalyst)
3. **If they warp to you** - warp immediately
4. **Don't negotiate** - they'll kill you anyway

### Lowsec/Nullsec Mining

| Practice | Why |
|----------|-----|
| Scout system first | Know if hostiles present |
| Use D-scan constantly | Early warning |
| Pre-align to safe | Faster escape |
| Use tanky ships | Survive initial volley |
| Have backup fleet | Response force |

---

## Skill Priorities

### For Miners

| Priority | Skill | Effect |
|----------|-------|--------|
| 1 | Mining IV | Use Mining Barges |
| 2 | Astrogeology IV | +25% yield |
| 3 | Mining Barge IV | Ship bonuses |
| 4 | Mining Upgrades IV | MLU effectiveness |
| 5 | Reprocessing skills | Better refining |

### For Boosters

| Priority | Skill | Effect |
|----------|-------|--------|
| 1 | Mining Foreman V | Burst access |
| 2 | Mining Director IV+ | Burst strength |
| 3 | Industrial Command Ships IV | Porpoise/Orca bonuses |
| 4 | Leadership V | Fleet size |
| 5 | Shield skills | Survivability |

---

## Quick Reference

### Boost Checklist

- [ ] Booster in fleet command position (Boss/Wing Commander/Squad Commander)
- [ ] Fleet members within burst range
- [ ] Correct charges loaded in burst modules
- [ ] Bursts activated and cycling

### Fleet Setup Checklist

- [ ] Fleet created and advertised
- [ ] Roles assigned (booster, miners, hauler)
- [ ] Communication method agreed
- [ ] Defense protocol discussed
- [ ] Loot split agreed
- [ ] Everyone has bookmarks

### Efficiency Checklist

- [ ] Booster running all three bursts
- [ ] Miners using appropriate crystals
- [ ] Hauler keeping up with ore production
- [ ] No one waiting on full hold
- [ ] Working systematically through belt

---

## Summary

| Concept | Key Point |
|---------|-----------|
| Fleet benefit | +25-60% yield with proper boosts |
| Minimum fleet | 2 pilots (Porpoise + Barge) |
| Optimal small fleet | 4-5 pilots with dedicated roles |
| Booster value | Worthwhile at 3+ miners |
| Compression | Requires Rorqual or structure |
| Defense | Pre-align, watchlist, voice comms |
| Coordination | Communication is key to efficiency |

Fleet mining transforms a solo grind into an efficient, social activity. Start with a friend and a Porpoise, scale up as your group grows.

---
Source: EVE University Wiki, mining community resources
Last updated: YC128 (2026)
