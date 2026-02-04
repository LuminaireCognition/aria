# Planetary Interaction Guide

Complete reference for Planetary Interaction (PI) - extracting and processing planetary resources for manufacturing and passive income.

## What is Planetary Interaction?

PI allows you to:
- Extract raw materials from planets
- Process materials through production chains (P0 → P1 → P2 → P3 → P4)
- Create components used in manufacturing

### PI Value Proposition

| Playstyle | PI Value |
|-----------|----------|
| Market trader | Passive ISK (sell products) |
| Manufacturer | Free inputs for production |
| Self-sufficient | Essential for fuel, structures, T2 |

**Note:** PI products have no NPC buy orders. Monetization requires player market sales.

---

## Skill Requirements

### Essential Skills

| Skill | Effect | Priority |
|-------|--------|----------|
| **Command Center Upgrades** | +1 planet per level | **Critical** |
| **Interplanetary Consolidation** | +1 upgrade level per level | **Critical** |
| **Planetology** | Better resource visibility | High |
| **Remote Sensing** | Scan from further away | Medium |
| **Advanced Planetology** | Even better visibility | Low |

### Skill Progression

| Level | Planets | Upgrade Level | Training Time |
|-------|---------|---------------|---------------|
| I | 1 | Basic | Minutes |
| III | 3 | Good | Hours |
| IV | 4 | Better | Days |
| V | 5-6 | Maximum | Weeks |

### Recommended Training Order

1. **Command Center Upgrades III** - Access 3 planets
2. **Interplanetary Consolidation III** - Decent infrastructure
3. **Planetology III** - See resources clearly
4. **Remote Sensing III** - Convenience
5. Then train to IV/V as needed

**Alpha Clone Limit:** Command Center Upgrades IV maximum (4 planets).

---

## Planet Types

Each planet type has specific resources available.

### Planet Type Reference

| Planet Type | Resources Available |
|-------------|---------------------|
| **Barren** | Aqueous Liquids, Base Metals, Carbon Compounds, Micro Organisms, Noble Metals |
| **Gas** | Aqueous Liquids, Base Metals, Ionic Solutions, Noble Gas, Reactive Gas |
| **Ice** | Aqueous Liquids, Heavy Metals, Micro Organisms, Noble Gas, Planktic Colonies |
| **Lava** | Base Metals, Felsic Magma, Heavy Metals, Non-CS Crystals, Suspended Plasma |
| **Oceanic** | Aqueous Liquids, Carbon Compounds, Complex Organisms, Micro Organisms, Planktic Colonies |
| **Plasma** | Base Metals, Heavy Metals, Noble Metals, Non-CS Crystals, Suspended Plasma |
| **Storm** | Aqueous Liquids, Base Metals, Ionic Solutions, Noble Gas, Suspended Plasma |
| **Temperate** | Aqueous Liquids, Autotrophs, Carbon Compounds, Complex Organisms, Micro Organisms |

### Best Planet Types by Use

| Goal | Best Planet Types |
|------|-------------------|
| P1 extraction variety | Barren, Storm, Temperate |
| Fuel block components | Gas (coolant), Storm (coolant), Lava (mech parts) |
| High-value P2 | Plasma (enriched uranium), Lava (mech parts) |

---

## Command Center Setup

The Command Center is your base of operations on each planet.

### Initial Setup Steps

1. **Open Planetary Production** - Neocom → Industry → Planetary Production
2. **Buy Command Center** - Market → Planetary Infrastructure → Command Centers
3. **Travel to system** - Must be in same system as planet
4. **View planet** - Right-click planet → View in Planet Mode
5. **Place Command Center** - Drag from inventory, click to place
6. **Submit changes** - Click "Submit" to finalize

### Command Center Types

| Type | Planet Type | Cost |
|------|-------------|------|
| Barren Command Center | Barren | ~80K ISK |
| Gas Command Center | Gas | ~80K ISK |
| Temperate Command Center | Temperate | ~80K ISK |
| (etc.) | (matching type) | ~80K ISK |

**Buy the correct type** for your target planet.

### Upgrade Levels

Higher upgrade levels allow more structures and power/CPU.

| Upgrade Level | Power (MW) | CPU (tf) | Structures |
|---------------|------------|----------|------------|
| 1 | 6,000 | 1,675 | Basic setup |
| 2 | 9,000 | 7,057 | Small operation |
| 3 | 12,000 | 12,136 | Medium operation |
| 4 | 15,000 | 17,215 | Large operation |
| 5 | 17,000 | 21,315 | Maximum |

Upgrade level is limited by **Interplanetary Consolidation** skill.

---

## PI Structures

### Structure Types

| Structure | Purpose | Power | CPU |
|-----------|---------|-------|-----|
| **Extractor Control Unit** | Extracts raw P0 materials | 2,600 | 400 |
| **Basic Industry Facility** | P0 → P1 processing | 800 | 200 |
| **Advanced Industry Facility** | P1 → P2 processing | 700 | 500 |
| **High-Tech Production Plant** | P2 → P3/P4 processing | 400 | 1,100 |
| **Storage Facility** | Holds materials | 700 | 500 |
| **Launchpad** | Storage + export/import | 700 | 3,600 |

### Structure Recommendations

| Setup Type | Structures Needed |
|------------|-------------------|
| Extraction planet | 1 Launchpad, 2-3 Extractors, 4-6 Basic Factories |
| Factory planet | 1 Launchpad, Multiple Advanced/High-Tech Facilities |
| Hybrid | 1 Launchpad, 1-2 Extractors, Mixed Factories |

### Links

Structures must be connected via **links** to transfer materials.

| Link Length | Power Cost |
|-------------|------------|
| Short (<5km) | Minimal |
| Long (>20km) | Significant |

**Tip:** Place structures close together to minimize link power costs.

---

## Production Chains

PI materials flow through processing tiers.

### Tier Overview

| Tier | Name | Example | Processing |
|------|------|---------|------------|
| P0 | Raw | Aqueous Liquids | Extracted from planet |
| P1 | Processed | Water | Basic Industry (P0 → P1) |
| P2 | Refined | Coolant | Advanced Industry (P1 → P2) |
| P3 | Specialized | Robotics | High-Tech (P2 → P3) |
| P4 | Advanced | Broadcast Node | High-Tech (P3 → P4) |

### P0 → P1 Conversion

| P0 Raw Material | P1 Processed Material |
|-----------------|----------------------|
| Aqueous Liquids | Water |
| Autotrophs | Industrial Fibers |
| Base Metals | Reactive Metals |
| Carbon Compounds | Biofuels |
| Complex Organisms | Proteins |
| Felsic Magma | Silicon |
| Heavy Metals | Toxic Metals |
| Ionic Solutions | Electrolytes |
| Micro Organisms | Bacteria |
| Noble Gas | Oxygen |
| Noble Metals | Precious Metals |
| Non-CS Crystals | Chiral Structures |
| Planktic Colonies | Biomass |
| Reactive Gas | Oxidizing Compound |
| Suspended Plasma | Plasmoids |

**Ratio:** 3,000 P0 → 20 P1 (per cycle)

### P1 → P2 Conversion

| P2 Product | P1 Inputs (40 each) |
|------------|---------------------|
| Biocells | Biofuels + Precious Metals |
| Construction Blocks | Reactive Metals + Toxic Metals |
| Consumer Electronics | Toxic Metals + Chiral Structures |
| Coolant | Water + Electrolytes |
| Enriched Uranium | Toxic Metals + Precious Metals |
| Fertilizer | Proteins + Bacteria |
| Genetically Enhanced Livestock | Proteins + Biomass |
| Livestock | Proteins + Biofuels |
| Mechanical Parts | Reactive Metals + Precious Metals |
| Microfiber Shielding | Industrial Fibers + Silicon |
| Miniature Electronics | Silicon + Chiral Structures |
| Nanites | Bacteria + Reactive Metals |
| Oxides | Oxygen + Oxidizing Compound |
| Polyaramids | Industrial Fibers + Oxidizing Compound |
| Polytextiles | Industrial Fibers + Biofuels |
| Rocket Fuel | Electrolytes + Plasmoids |
| Silicate Glass | Silicon + Oxidizing Compound |
| Superconductors | Water + Plasmoids |
| Super Tensile Plastics | Oxygen + Biomass |
| Synthetic Oil | Electrolytes + Oxygen |
| Test Cultures | Water + Bacteria |
| Transmitter | Chiral Structures + Plasmoids |
| Viral Agent | Bacteria + Biomass |
| Water-Cooled CPU | Water + Reactive Metals |

**Ratio:** 40 P1 + 40 P1 → 5 P2 (per cycle)

### P2 → P3 Conversion

| P3 Product | P2 Inputs (10 each) |
|------------|---------------------|
| Biotech Research Reports | Livestock + Construction Blocks + Nanites |
| Camera Drones | Silicate Glass + Rocket Fuel |
| Condensates | Coolant + Oxides |
| Cryoprotectant Solution | Fertilizer + Synthetic Oil + Test Cultures |
| Data Chips | Microfiber Shielding + Super Tensile Plastics |
| Gel-Matrix Biopaste | Biocells + Oxides + Super Tensile Plastics |
| Guidance Systems | Transmitter + Water-Cooled CPU |
| Hazmat Detection Systems | Polytextiles + Transmitter + Viral Agent |
| Hermetic Membranes | Genetically Enhanced Livestock + Polyaramids |
| High-Tech Transmitters | Polyaramids + Transmitter |
| Industrial Explosives | Polytextiles + Fertilizer |
| Neocoms | Biocells + Silicate Glass |
| Nuclear Reactors | Enriched Uranium + Microfiber Shielding |
| Planetary Vehicles | Mechanical Parts + Miniature Electronics + Super Tensile Plastics |
| Robotics | Consumer Electronics + Mechanical Parts |
| Smartfab Units | Construction Blocks + Miniature Electronics |
| Supercomputers | Consumer Electronics + Coolant + Water-Cooled CPU |
| Synthetic Synapses | Super Tensile Plastics + Test Cultures |
| Transcranial Microcontrollers | Biocells + Nanites |
| Ukomi Superconductors | Superconductors + Synthetic Oil |
| Vaccines | Livestock + Viral Agent |

**Ratio:** 10 P2 + 10 P2 (+ sometimes 10 P2) → 3 P3

### P3 → P4 Conversion

| P4 Product | P3 Inputs (6 each) |
|------------|---------------------|
| Broadcast Node | Data Chips + High-Tech Transmitters + Neocoms |
| Integrity Response Drones | Gel-Matrix Biopaste + Hazmat Detection Systems + Planetary Vehicles |
| Nano-Factory | Industrial Explosives + Reactive Metals + Ukomi Superconductors |
| Organic Mortar Applicators | Condensates + Robotics + Bacteria |
| Recursive Computing Module | Guidance Systems + Synthetic Synapses + Transcranial Microcontrollers |
| Self-Harmonizing Power Core | Camera Drones + Hermetic Membranes + Nuclear Reactors |
| Sterile Conduits | Smartfab Units + Vaccines + Water |
| Wetware Mainframe | Biotech Research Reports + Cryoprotectant Solution + Supercomputers |

**Ratio:** 6 P3 + 6 P3 + 6 P3 → 1 P4

---

## Extraction vs Factory Planets

Two main approaches to PI setup.

### Extraction Planets

Focus on extracting and basic processing.

| Aspect | Details |
|--------|---------|
| **Setup** | Extractors + Basic Factories |
| **Output** | P1 materials |
| **Maintenance** | Reset extractors every 1-7 days |
| **Best For** | Resource-rich planets |

**Layout:**
```
[Extractor] → [Basic Factory] → [Launchpad]
[Extractor] → [Basic Factory] ↗
```

### Factory Planets

Import P1, produce P2/P3/P4.

| Aspect | Details |
|--------|---------|
| **Setup** | Launchpad + Advanced/High-Tech Factories |
| **Output** | P2, P3, or P4 materials |
| **Maintenance** | Restock inputs as needed |
| **Best For** | Near trade hubs |

**Layout:**
```
[Launchpad] → [Advanced Factory] → [Storage/Launchpad]
            → [Advanced Factory] ↗
            → [Advanced Factory] ↗
```

### Hybrid Planets

Extract and process on same planet.

| Aspect | Details |
|--------|---------|
| **Setup** | Extractors + All factory types |
| **Output** | P2 or P3 on-planet |
| **Maintenance** | Higher |
| **Best For** | Reducing hauling |

### Recommendation by Goal

| Goal | Approach |
|------|----------|
| Minimum hauling | Extraction (P1 export) |
| Maximum value/m³ | Factory (P4 production) |
| Self-sufficiency | Hybrid (complete chains) |
| Passive income | Extraction (less management) |

---

## Planet Selection

Choosing the right planets is crucial for efficiency.

### Security Status Differences

| Security | Resource Quality | POCO Tax | Risk |
|----------|------------------|----------|------|
| Highsec | Lower | 10% NPC + player | None |
| Lowsec | Medium | Player-set | Ganks |
| Nullsec | Higher | Player-set (often 0%) | Variable |
| Wormhole | Highest | Player-set | High |

### Resource Quality

When viewing a planet:
1. **Select resource type** from dropdown
2. **White = high concentration**
3. **Colored bands = lower concentration**

**Skill matters:** Planetology and Advanced Planetology reveal more detail.

### Hotspot Strategy

1. Scan for resource hotspots (white areas)
2. Place Command Center near hotspot
3. Position extractors on whitest area
4. Resource depletes over time - move extractors periodically

### Multi-Resource Extraction

Some setups extract two P0 types to make P2 on-planet:
1. Find planet with overlapping hotspots
2. Place extractors on each resource
3. Process both P0 → P1
4. Combine P1 → P2

**Example:** Storm planet with Aqueous Liquids + Ionic Solutions → Water + Electrolytes → Coolant

---

## POCO and Taxes

### What is a POCO?

**Planetary Customs Office (POCO)** - Orbital structure for importing/exporting materials.

| Property | Details |
|----------|---------|
| **Purpose** | Transfer materials to/from planet |
| **Owner** | Player corp or NPC (Interbus) |
| **Tax** | Set by owner |

### Tax Rates

| Owner | Typical Tax |
|-------|-------------|
| Interbus (NPC) | 10% base + export tax |
| Player corp (friendly) | 0-5% |
| Player corp (unfriendly) | 5-15% |
| Player corp (hostile) | 15-100% |

### Tax Calculation

```
Tax = (Item Base Value) × (Tax Rate) × (Quantity)
```

**High-tier products have higher base values** - exporting P4 costs more than P0.

### Tax Reduction Skills

| Skill | Effect |
|-------|--------|
| Customs Code Expertise | -10% NPC tax per level |

At level V: 50% reduction to NPC portion of tax.

### Tax Strategies

| Strategy | Details |
|----------|---------|
| Find low-tax POCOs | Scout systems for player POCOs |
| Join POCO-owning corp | Often 0% tax for members |
| Use wormholes | Corp-owned POCOs, no outsiders |
| Process on-planet | Export higher-tier = less volume, same % |

---

## Hauling PI Products

### Volume Comparison

| Tier | Volume per Unit | Units per Trip (Epithal) |
|------|-----------------|--------------------------|
| P0 | 0.01 m³ | 6,700,000 |
| P1 | 0.38 m³ | 176,000 |
| P2 | 1.50 m³ | 44,666 |
| P3 | 6.00 m³ | 11,166 |
| P4 | 100.00 m³ | 670 |

### Hauling Ships

| Ship | PI Hold | Notes |
|------|---------|-------|
| **Epithal** | 67,500 m³ | Dedicated PI hauler |
| Nereus | 2,700 m³ | General hauler |
| Bestower | 5,400 m³ | Amarr hauler |

**Always use Epithal for PI** - specialized hold only accepts PI commodities.

### Hauling Schedule

| Extraction Cycle | Hauling Frequency |
|------------------|-------------------|
| 24 hours | Daily |
| 3-4 days | Every few days |
| 7 days | Weekly |

Longer cycles = less hauling but lower yield efficiency.

---

## Passive Income Expectations

### Realistic Income Estimates

| Setup | Planets | Monthly Income | Effort |
|-------|---------|----------------|--------|
| Casual P1 | 3 | 50-100M | Weekly reset |
| Active P2 | 5 | 200-400M | Every few days |
| Factory P4 | 6 | 400-800M | Daily management |

**These assume market sales.** Without market access, value is in manufacturing inputs.

### Income Variables

| Factor | Impact |
|--------|--------|
| Planet quality | +/- 30% yield |
| Tax rates | -5% to -20% |
| Market prices | Fluctuate significantly |
| Extraction optimization | +20% with active management |

### Self-Sufficient Value

For pilots who cannot sell on market, PI provides:

| Product | Use |
|---------|-----|
| Coolant, Mech Parts, etc. | Fuel block manufacturing |
| Robotics | T2 production |
| P4 products | Structure components |
| Various P2/P3 | POS fuel (legacy) |

**Value is realized through manufacturing**, not sales.

---

## Quick Start Setup

### Minimum Viable PI (3 planets)

**Goal:** Start producing P1 with minimal investment.

**Skills needed:**
- Command Center Upgrades III
- Interplanetary Consolidation III
- Planetology II

**Per planet:**
1. Place Command Center
2. Upgrade to level 3
3. Place 1 Launchpad
4. Place 2 Extractor Control Units
5. Place 4-5 Basic Industry Facilities
6. Link: Extractors → Factories → Launchpad
7. Set extraction program (48-72 hours)
8. Route: P0 to factories, P1 to launchpad

**Total setup cost:** ~10M ISK (command centers + upgrades)

### Expansion Path

| Stage | Planets | Focus |
|-------|---------|-------|
| 1 | 3 | Learn mechanics, P1 production |
| 2 | 4-5 | Optimize extraction, try P2 |
| 3 | 6 | Factory planet for P3/P4 |

---

## Common PI Mistakes

| Mistake | Problem | Solution |
|---------|---------|----------|
| Wrong command center type | Can't place | Buy matching type |
| Structures too far apart | High link power cost | Cluster near launchpad |
| Extractor heads spread thin | Low yield | Concentrate on hotspots |
| Never moving extractors | Depleted resources | Relocate every few weeks |
| Ignoring taxes | Profit eaten by fees | Find low-tax systems |
| Overcomplicating | Burnout | Start simple, scale up |
| Long extraction cycles | Lower yield/hour | Balance effort vs. efficiency |

---

## Summary

| Concept | Key Point |
|---------|-----------|
| Skills | CCU and IC to III minimum, IV+ recommended |
| Planet types | Match resources to production goals |
| Extraction | P0 → P1, reset extractors regularly |
| Factory | Import P1, produce P2/P3/P4 |
| Taxes | Find low-tax POCOs, use Customs Code Expertise |
| Hauling | Use Epithal, higher-tier = less volume |
| Income | 50-800M/month depending on setup |
| Self-sufficient | Value through manufacturing inputs |

PI is low-effort passive income or manufacturing support. Start simple with P1 extraction, then optimize based on your goals.

---
Source: EVE University Wiki, PI community resources
Last updated: YC128 (2026)
