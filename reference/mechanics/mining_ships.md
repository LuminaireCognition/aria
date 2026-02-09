# Mining Ships Reference

Master reference for ORE mining ships. This is the single source of truth for mining ship data in the ARIA project.

**Source:** [EVE University Wiki - ORE Basic Ship and Skill Overview](https://wiki.eveuniversity.org/ORE_Basic_Ship_and_Skill_Overview)

## Mining Ship Progression

```
Venture ──┬──→ Expedition Frigates ──┬──→ Prospect (Ore/Gas, Covert)
          │                          └──→ Endurance (Ice, Cloak)
          │
          └──→ Mining Barges ──┬──→ Procurer ──→ Skiff (Tank)
                               ├──→ Retriever ──→ Mackinaw (Capacity)
                               └──→ Covetor ───→ Hulk (Yield)
```

## Mining Ships Comparison

| Ship | Class | Ore Hold | Yield | Tank | Best For |
|------|-------|----------|-------|------|----------|
| **Venture** | Mining Frigate | 5,000 m³ | Low | Low | Starting out, gas harvesting |
| **Prospect** | Expedition Frigate | 12,500 m³ | Med | Low | Covert ore/gas in dangerous space |
| **Endurance** | Expedition Frigate | 19,000 m³ | Low | Low | Covert ice harvesting |
| **Procurer** | Mining Barge | 16,000 m³ | Low | **High** | Solo mining in dangerous space |
| **Retriever** | Mining Barge | 27,500 m³ | Med | Med | Extended solo mining |
| **Covetor** | Mining Barge | 9,000 m³ | **High** | Low | Fleet mining with hauler support |
| **Skiff** | Exhumer | 18,500 m³ | Med | **High** | Null/low-sec mining operations |
| **Mackinaw** | Exhumer | 31,500 m³ | Med | Med | Extended solo operations |
| **Hulk** | Exhumer | 11,500 m³ | **High** | Low | Maximum yield fleet mining |

## Detailed Ship Specifications

### Mining Frigate

#### Venture

| Attribute | Value |
|-----------|-------|
| Ore Hold | 5,000 m³ |
| High Slots | 3 |
| Med Slots | 3 |
| Low Slots | 1 |
| Drone Bay | 10 m³ |
| Drone Bandwidth | 10 Mbit/s |
| Warp Core Strength | +2 (role bonus) |

**Bonuses (per Mining Frigate level):**
- +5% mining yield
- -5% gas cloud scoop duration

**Role Bonus:**
- +100% mining and gas cloud scoop yield

**Skill Required:** Mining Frigate I

---

### Expedition Frigates

#### Prospect

| Attribute | Value |
|-----------|-------|
| Ore Hold | 12,500 m³ |
| High Slots | 3 |
| Med Slots | 3 |
| Low Slots | 4 |
| Drone Bay | None |
| Drone Bandwidth | None |
| Covert Cloak | Yes |

**Bonuses (per Mining Frigate level):**
- +5% mining yield
- -5% gas cloud scoop duration

**Bonuses (per Expedition Frigates level):**
- +5% mining yield
- -5% gas cloud scoop duration

**Role Bonus:**
- +100% mining and gas cloud scoop yield
- Can fit Covert Ops Cloaking Device
- -100% Cloaking Device CPU requirement

**Skill Required:** Expedition Frigates I

#### Endurance

| Attribute | Value |
|-----------|-------|
| Ore Hold | 19,000 m³ |
| High Slots | 3 |
| Med Slots | 4 |
| Low Slots | 3 |
| Drone Bay | 30 m³ |
| Drone Bandwidth | 15 Mbit/s |
| Covert Cloak | No (but reduced cloak penalties) |

**Bonuses (per Mining Frigate level):**
- +5% ore mining yield
- -5% ice harvester duration

**Bonuses (per Expedition Frigates level):**
- +5% ore mining yield
- -5% ice harvester duration

**Role Bonus:**
- +300% ore mining yield
- -50% ice harvester duration
- -50% Cloaking Device CPU requirement
- No targeting delay after cloaking
- Full velocity while cloaked

**Skill Required:** Expedition Frigates I

---

### Mining Barges

#### Procurer (Tank Focus)

| Attribute | Value |
|-----------|-------|
| Ore Hold | 16,000 m³ |
| High Slots | 2 |
| Med Slots | 3 |
| Low Slots | 3 |
| Drone Bay | 100 m³ |
| Drone Bandwidth | 50 Mbit/s |

**Bonuses (per Mining Barge level):**
- +2% strip miner yield
- -2% ice harvester duration
- -2% gas harvester duration

**Role Bonus:**
- +50% drone damage and hitpoints
- Can use Strip Miners, Ice Harvesters, Gas Cloud Scoops

**Skill Required:** Mining Barge I

#### Retriever (Capacity Focus)

| Attribute | Value |
|-----------|-------|
| Ore Hold | 27,500 m³ (base) |
| High Slots | 2 |
| Med Slots | 2 |
| Low Slots | 3 |
| Drone Bay | 50 m³ |
| Drone Bandwidth | 50 Mbit/s |

**Bonuses (per Mining Barge level):**
- +3% strip miner yield
- -2% ice/gas harvester duration
- +5% ore hold capacity

**Skill Required:** Mining Barge I

#### Covetor (Yield Focus)

| Attribute | Value |
|-----------|-------|
| Ore Hold | 9,000 m³ |
| High Slots | 2 |
| Med Slots | 2 |
| Low Slots | 3 |
| Drone Bay | 50 m³ |
| Drone Bandwidth | 50 Mbit/s |

**Bonuses (per Mining Barge level):**
- +3% strip miner yield
- -3% ice/gas harvester duration
- +6% strip miner and ice harvester range

**Skill Required:** Mining Barge I

---

### Exhumers

#### Skiff (Tank Focus)

| Attribute | Value |
|-----------|-------|
| Ore Hold | 18,500 m³ |
| High Slots | 2 |
| Med Slots | 4 |
| Low Slots | 3 |
| Drone Bay | 100 m³ |
| Drone Bandwidth | 50 Mbit/s |

**Bonuses (per Mining Barge level):**
- +2% strip miner yield
- -4% ice harvester duration

**Bonuses (per Exhumers level):**
- +2% strip miner yield
- -3% ice harvester duration

**Role Bonus:**
- +50% drone damage and hitpoints
- Can use Strip Miners, Ice Harvesters, Gas Cloud Scoops

**Skill Required:** Exhumers I

#### Mackinaw (Capacity Focus)

| Attribute | Value |
|-----------|-------|
| Ore Hold | 31,500 m³ (base) |
| High Slots | 2 |
| Med Slots | 4 |
| Low Slots | 3 |
| Drone Bay | 50 m³ |
| Drone Bandwidth | 50 Mbit/s |

**Bonuses (per Mining Barge level):**
- +3% strip miner yield
- -4% ice harvester duration

**Bonuses (per Exhumers level):**
- +4% strip miner yield
- -3% ice harvester duration
- +5% ore hold capacity

**Skill Required:** Exhumers I

#### Hulk (Yield Focus)

| Attribute | Value |
|-----------|-------|
| Ore Hold | 11,500 m³ |
| High Slots | 2 |
| Med Slots | 4 |
| Low Slots | 3 |
| Drone Bay | 50 m³ |
| Drone Bandwidth | 50 Mbit/s |

**Bonuses (per Mining Barge level):**
- +3% strip miner yield
- -3% ice harvester duration

**Bonuses (per Exhumers level):**
- +6% strip miner yield
- -4% ice harvester duration

**Role Bonus:**
- -25% strip miner and ice harvester capacitor use

**Skill Required:** Exhumers I

---

## Industrial Command Ships

These ships provide fleet boosts and have large ore holds for collecting from fleet members.

| Ship | Ore Hold | Fleet Hangar | Ship Bay | Drone Bay | Role |
|------|----------|--------------|----------|-----------|------|
| **Porpoise** | 50,000 m³ | 5,000 m³ | None | 125 m³ | Entry-level fleet booster |
| **Orca** | 150,000 m³ | 40,000 m³ | 400,000 m³ | 200 m³ | Primary fleet command ship |

### Porpoise

| Attribute | Value |
|-----------|-------|
| Ore Hold | 50,000 m³ |
| Fleet Hangar | 5,000 m³ |
| High Slots | 4 |
| Med Slots | 4 |
| Low Slots | 2 |
| Drone Bay | 125 m³ |
| Drone Bandwidth | 50 Mbit/s |

**Bonuses (per Industrial Command Ships level):**
- +2% Mining Foreman Burst strength and duration
- +5% Mining Foreman Burst range
- +10% drone damage, hitpoints, and ore mining yield

**Skill Required:** Industrial Command Ships I

### Orca

| Attribute | Value |
|-----------|-------|
| Ore Hold | 150,000 m³ |
| Fleet Hangar | 40,000 m³ |
| Ship Maintenance Bay | 400,000 m³ |
| Cargo | 30,000 m³ |
| High Slots | 6 |
| Med Slots | 5 |
| Low Slots | 2 |
| Drone Bay | 200 m³ |
| Drone Bandwidth | 50 Mbit/s |

**Bonuses (per Industrial Command Ships level):**
- +3% Mining Foreman Burst strength and duration
- +5% Mining Foreman Burst range
- +5% cargo and ore hold capacity

**Skill Required:** Industrial Command Ships I

---

## Skill Requirements

| Ship | Required Skill | Prerequisites |
|------|----------------|---------------|
| Venture | Mining Frigate I | — |
| Prospect | Expedition Frigates I | Mining Frigate V |
| Endurance | Expedition Frigates I | Mining Frigate V |
| Procurer | Mining Barge I | Industry V, Astrogeology III, Mining IV |
| Retriever | Mining Barge I | Industry V, Astrogeology III, Mining IV |
| Covetor | Mining Barge I | Industry V, Astrogeology III, Mining IV |
| Skiff | Exhumers I | Mining Barge V, Astrogeology V |
| Mackinaw | Exhumers I | Mining Barge V, Astrogeology V |
| Hulk | Exhumers I | Mining Barge V, Astrogeology V |
| Porpoise | Industrial Command Ships I | Mining Foreman V, ORE Hauler III |
| Orca | Industrial Command Ships I | Mining Foreman V, ORE Hauler III |

---

## Ship Selection Guide

### By Activity

| Activity | Recommended Ship | Reason |
|----------|------------------|--------|
| Starting out | Venture | Free from career agent, forgiving |
| Gas harvesting | Venture, Prospect | Gas cloud scoop bonuses |
| Ice harvesting | Endurance, Skiff/Mackinaw/Hulk | Ice harvester capability |
| Solo high-sec | Retriever, Mackinaw | Large ore holds |
| Solo dangerous space | Procurer, Skiff | Tank survivability |
| Fleet with hauler | Covetor, Hulk | Maximum yield |
| Fleet boosting | Porpoise, Orca | Command bursts |

### By Security Space

| Space | Primary | Secondary | Notes |
|-------|---------|-----------|-------|
| High-sec | Retriever/Mackinaw | Covetor/Hulk | Capacity or yield |
| Low-sec | Procurer/Skiff | Prospect | Tank or covert |
| Null-sec | Skiff | Procurer | Tank is critical |
| Wormhole | Prospect | Venture | Covert capability |

---

*Last verified: 2026-01-18 from EVE University Wiki*
