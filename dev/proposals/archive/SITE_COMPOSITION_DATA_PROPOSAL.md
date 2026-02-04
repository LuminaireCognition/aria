# ARIA Site Composition Data Proposal

**Status:** Draft (Updated, SDE-Validated)
**Created:** 2026-01-18
**Updated:** 2026-01-19
**Research:** Complete - See research documents below
**SDE Validation:** Complete - All type_ids cross-referenced 2026-01-19

### Research Documents
- `dev/mechanics/EveOnlineSpecialSpawnSitesInventory.md` - 45 cited sources covering all site types
- `dev/mechanics/EVEOnlineGasRegionalDataInquiry.md` - Gas-specific regional data and mission item clarifications

## Executive Summary

This proposal outlines a strategy for maintaining authoritative data about EVE Online site compositions (e.g., what ores spawn in Empire Border Rare Asteroid sites) that is not available through the official SDE or ESI.

**Problem:** Site spawn tables are server-side data that CCP does not export. ARIA needs this information to provide accurate mining, exploration, and PvE guidance.

**Solution:** Maintain a curated local data file (`reference/sites/site-compositions.yaml`) with:
1. Explicit source attribution (URLs to authoritative references)
2. Verification timestamps for staleness detection
3. Structured schema for programmatic access
4. Clear maintenance workflow for updates

**Research Status:** Comprehensive research has been compiled in:
- `dev/mechanics/EveOnlineSpecialSpawnSitesInventory.md` - 45 cited sources covering all site types
- `dev/mechanics/EVEOnlineGasRegionalDataInquiry.md` - 12 cited sources on gas regional data and mission item clarifications

---

## Research Foundation

### Primary Research Document

The **Special Spawn Sites Inventory** (`dev/mechanics/EveOnlineSpecialSpawnSitesInventory.md`) provides comprehensive coverage of:

| Category | Sections | Data Quality |
|----------|----------|--------------|
| Mining anomalies | EBRA, A0 Blue (W-Space, Nullsec) | Complete with ore counts |
| Gas sites | Mykoserocin, Cytoserocin by region | Regional distribution mapped |
| Special NPCs | Clone Soldiers, Mordu's Legion | Spawn conditions documented |
| Combat sites | Besieged Facilities, Officer spawns | Loot tables, True Sec thresholds |
| Advanced content | NPC Shipyards, Pochven, Drifters | Mechanics documented |

The Inventory contains **45 cited sources** including EVE University Wiki, CCP patch notes, Reddit discussions, and forum posts.

### Supplementary Research: Gas Regional Data

The **Gas Regional Data Inquiry** (`dev/mechanics/EVEOnlineGasRegionalDataInquiry.md`) provides comprehensive regional data for two previously under-documented Mykoserocin flavors and clarifies the nature of two Cytoserocin types:

| Contribution | Details |
|-------------|---------|
| Azure Mykoserocin | Regional distribution (Derelik, Devoid, Bleak Lands, Heimatar, Molden Heath, Curse) |
| Vermillion Mykoserocin | Regional distribution (Heimatar, Great Wildlands, Insmother, Omist, Tenerifis, Metropolis, Curse) |
| Booster corrections | Azure → Synth Sooth Sayer, Vermillion → Synth X-Instinct |
| High-sec spawns | Confirmed rare Azure/Vermillion spawns in 0.5+ systems (Derelik, Heimatar) |
| Nebula associations | Azure: Ghost/Eagle Nebula; Vermillion: Flame/Pipe Nebula |
| Mission item clarification | **Chartreuse/Gamboge Cytoserocin are mission items, NOT harvestable cosmic signatures** |
| Industrial utility | Chartreuse ("Like Drones to a Cloud") and Gamboge ("Gas Injections") have zero manufacturing use |

### Research-to-Data Mapping

The Inventory's narrative content maps directly to YAML schema entries:

| Source Document | Section | YAML Path | Extraction Status |
|-----------------|---------|-----------|-------------------|
| Inventory | Section 2.2 (EBRA table) | `mining_anomalies.empire_border_rare_asteroids.contents` | **Extracted** |
| Inventory | Section 3.2.1 (W-Space A0) | `mining_anomalies.wspace_blue_a0_rare_asteroids.contents` | **Extracted** |
| Inventory | Section 3.2.2 (Nullsec A0) | `mining_anomalies.nullsec_blue_a0_rare_asteroids.contents` | **Extracted** |
| Inventory | Section 4.1 (Mykoserocin) | `gas_sites.mykoserocin.*` | **Extracted** |
| Inventory | Section 4.2 (Cytoserocin) | `gas_sites.cytoserocin.*` | **Extracted** |
| Inventory | Section 5.1 (Clone Soldiers) | `special_npcs.clone_soldiers` | **Extracted** |
| Inventory | Section 5.2 (Mordu's Legion) | `special_npcs.mordus_legion` | **Extracted** |
| Inventory | Section 5.3 (Besieged) | `combat_sites.besieged_covert_research_facility` | **Extracted** |
| Inventory | Section 6 (True Sec) | `nullsec_mechanics.true_security_spawns` | **Extracted** |
| Gas Inquiry | Section 2 (Azure) | `gas_sites.mykoserocin.azure_sooth_sayer.regions` | **Extracted** |
| Gas Inquiry | Section 3 (Vermillion) | `gas_sites.mykoserocin.vermillion_x_instinct.regions` | **Extracted** |
| Gas Inquiry | Section 4 (Mission items) | `gas_sites.mission_commodities` | **Extracted** |

---

## The Data Gap

### What the SDE Provides

| Data Type | Available | Example |
|-----------|-----------|---------|
| Item definitions | Yes | Ytirium, type_id 74525 |
| Item descriptions | Yes | "Contains Isogen..." |
| Reprocessing outputs | Yes | Ytirium → Isogen |
| Blueprint materials | Yes | Manufacturing inputs |
| Universe topology | Yes | Systems, gates, regions |

### What the SDE Does Not Provide

| Data Type | Available | Needed For |
|-----------|-----------|------------|
| Anomaly spawn tables | No | Mining site guidance |
| Site compositions | No | "What's in this site?" |
| Spawn conditions | No | Security, adjacency, stellar type |
| NPC spawn triggers | No | Belt farming guidance |
| Loot tables | No | Exploration value estimates |
| Gas regional distribution | No | Booster production guidance |

---

## Authoritative Sources

### Primary Sources

| Source | URL | Reliability | Update Frequency |
|--------|-----|-------------|------------------|
| **EVE University Wiki** | wiki.eveuniversity.org | High | Community-maintained |
| **CCP Patch Notes** | eveonline.com/news | Authoritative | Per release |
| **Hoboleaks SDE** | sde.hoboleaks.space | High | Auto per patch |

### Secondary Sources

| Source | URL | Reliability | Notes |
|--------|-----|-------------|-------|
| EVE Forums (Dev posts) | forums.eveonline.com | Authoritative | Scattered |
| Reddit r/eve | reddit.com/r/eve | Variable | Needs verification |
| In-game observation | N/A | Ground truth | Manual, doesn't scale |

### Source Priority

1. **CCP Patch Notes** - When sites are added/changed
2. **EVE University Wiki** - Comprehensive, well-maintained
3. **Hoboleaks** - For datamined content not in wiki
4. **In-game verification** - When sources conflict

---

## Proposed Data Structure

### File Location

```
reference/
└── sites/
    ├── INDEX.md                    # Human-readable overview
    ├── site-compositions.yaml      # Machine-readable data
    └── SOURCES.md                  # Links to dev/mechanics/Inventory
```

### Schema Definition

```yaml
# reference/sites/site-compositions.yaml
---
# Metadata
schema_version: "1.0"
last_updated: "2026-01-19"
maintainer: "ARIA Project"
research_source: "dev/mechanics/EveOnlineSpecialSpawnSitesInventory.md"

# =============================================================================
# MINING ANOMALIES
# =============================================================================
mining_anomalies:

  # ---------------------------------------------------------------------------
  # Empire Border Rare Asteroids (Inventory Section 2)
  # ---------------------------------------------------------------------------
  empire_border_rare_asteroids:
    display_name: "Empire Border Rare Asteroids"
    description: "Rare ore deposits in 0.5 high-sec systems adjacent to low-sec"
    category: "cosmic_anomaly"

    spawn_conditions:
      security_status: 0.5
      security_type: "high-sec"
      adjacency_requirement: "Gate connection to low-sec (0.1-0.4) system"
      max_spawns_per_system: 1  # Catalyst patch restriction

    respawn_behavior:
      trigger: "clearance"
      description: "Respawns elsewhere in region/constellation when fully mined"
      mechanic: "whac-a-mole distribution"

    contents:
      - ore: "Ytirium"
        type_id: 74525
        group: "Ytirium"
        count: 16
        quantity: 200000
        volume_m3: 120000
        strategic_value: "Primary Isogen source in high-sec"
      - ore: "Ducinium"
        type_id: 74533
        group: "Ducinium"
        count: 1
        quantity: 2073
        volume_m3: 33168
        strategic_value: "High-value Megacyte source"
      - ore: "Eifyrium"
        type_id: 74529
        group: "Eifyrium"
        count: 1
        quantity: 2073
        volume_m3: 33168
        strategic_value: "High-value Zydrine source"
      - ore: "Jet Ochre"
        type_id: 46675
        group: "Dark Ochre"
        count: 1
        quantity: 1036
        volume_m3: 8288
        strategic_value: "Compact Nocxium and Isogen"
      - ore: "Pellucid Crokite"
        type_id: 46677
        group: "Crokite"
        count: 1
        quantity: 1036
        volume_m3: 16576
        strategic_value: "High-yield Nocxium, Zydrine, Megacyte"

    totals:
      asteroid_count: 20
      total_quantity: 206218
      total_volume_m3: 211200

    tactical_notes:
      - "Ducinium and Eifyrium are 'jackpot' nodes - extract first"
      - "Single barge can clear high-value ores in <2 cycles"
      - "Ytirium bulk suitable for subsequent miners"

    sources:
      - url: "https://wiki.eveuniversity.org/Empire_Border_Rare_Asteroids"
        citation: 4
        accessed: "2026-01-19"
        verified: true
      - url: "https://www.eveonline.com/news/view/catalyst-expansion-notes"
        citation: 5
        accessed: "2026-01-19"
        note: "Spawn restriction patch"

    tags:
      - "border"
      - "rare-ore"
      - "high-sec"
      - "isogen"
      - "0.5-security"

  # ---------------------------------------------------------------------------
  # W-Space Blue A0 Rare Asteroids (Inventory Section 3.2.1)
  # ---------------------------------------------------------------------------
  wspace_blue_a0_rare_asteroids:
    display_name: "W-Space Blue A0 Rare Asteroids"
    description: "Rare ore deposits in wormhole systems with Type A0 (blue) stars"
    category: "cosmic_anomaly"

    spawn_conditions:
      space_type: "wormhole"
      stellar_class: "A0"
      stellar_description: "Small Blue Star"

    contents:
      - ore: "Mordunium"
        type_id: 74521
        group: "Mordunium"
        count: 15
        quantity: 1335465
        volume_m3: null  # High - needs verification
        strategic_value: "Exclusive Pyerite/Mexallon source in W-space"
      - ore: "Ytirium"
        type_id: 74525
        group: "Ytirium"
        count: 30
        quantity: 2000000
        volume_m3: 1200000  # 0.6 m³/unit
        strategic_value: "Isogen bulk source"
      - ore: "Ducinium"
        type_id: 74533
        group: "Ducinium"
        count: 2
        quantity: 13554
        volume_m3: 216864
        strategic_value: "Zydrine/Megacyte"
      - ore: "Eifyrium"
        type_id: 74529
        group: "Eifyrium"
        count: 2
        quantity: 8012
        volume_m3: 128192
        strategic_value: "Zydrine source"
      - ore: "Jet Ochre"
        type_id: 46675
        group: "Dark Ochre"
        count: 2
        quantity: 5342
        volume_m3: 42736
        strategic_value: "Nocxium/Isogen"
      - ore: "Pellucid Crokite"
        type_id: 46677
        group: "Crokite"
        count: 2
        quantity: 5342
        volume_m3: 85472
        strategic_value: "Nocxium/Zydrine"

    tactical_notes:
      - "30 Ytirium + 15 Mordunium = can sustain small WH corp industry"
      - "Significantly larger than Empire EBRA sites"

    sources:
      - url: "http://wiki.eveuniversity.org/W-Space_Blue_A0_Rare_Asteroids"
        citation: 6
        accessed: "2026-01-19"
        verified: true

    tags:
      - "wormhole"
      - "a0-star"
      - "rare-ore"
      - "mordunium"

  # ---------------------------------------------------------------------------
  # Nullsec Blue A0 Rare Asteroids (Inventory Section 3.2.2)
  # ---------------------------------------------------------------------------
  nullsec_blue_a0_rare_asteroids:
    display_name: "Nullsec Blue A0 Rare Asteroids"
    description: "Massive rare ore deposits in nullsec systems with Type A0 stars"
    category: "cosmic_anomaly"

    spawn_conditions:
      space_type: "nullsec"
      stellar_class: "A0"
      stellar_description: "Small Blue Star"
      max_spawns_per_system: 1  # Catalyst patch restriction

    contents:
      - ore: "Moonshine Ytirium"
        type_id: 74528
        group: "Ytirium"
        count: 94
        quantity: 7000000
        volume_m3: 4200000
        strategic_value: "Massive Isogen deposit"
      - ore: "Plunder Mordunium"
        type_id: 74524
        group: "Mordunium"
        count: 20
        quantity: 1795960
        volume_m3: 179596
        strategic_value: "Pyerite/Mexallon"
      - ore: "Imperial Ducinium"
        type_id: 74536
        group: "Ducinium"
        count: 2
        quantity: 17960
        volume_m3: 287360
        strategic_value: "Enhanced Megacyte yield"
      - ore: "Augmented Eifyrium"
        type_id: 74532
        group: "Eifyrium"
        count: 2
        quantity: 10776
        volume_m3: 172416
        strategic_value: "Enhanced Zydrine yield"
      - ore: "Jet Ochre"
        type_id: 46675
        group: "Dark Ochre"
        count: 2
        quantity: 7184
        volume_m3: 57472
        strategic_value: "Nocxium/Isogen"

    tactical_notes:
      - "4.2M m³ Moonshine Ytirium requires Rorqual or compression"
      - "Logistical challenge - not suitable for small fleets"

    sources:
      - url: "https://wiki.eveuniversity.org/Nullsec_Blue_A0_Rare_Asteroids"
        citation: 8
        accessed: "2026-01-19"
        verified: true

    tags:
      - "nullsec"
      - "a0-star"
      - "rare-ore"
      - "rorqual-scale"

# =============================================================================
# GAS SITES (Inventory Section 4)
# =============================================================================
gas_sites:

  # ---------------------------------------------------------------------------
  # Mykoserocin Distribution
  # ---------------------------------------------------------------------------
  mykoserocin:
    description: "Synth booster gas, spawns in high-sec and low-sec"
    security_types: ["high-sec", "low-sec"]

    flavors:
      amber_blue_pill:
        gas_type: "Amber Mykoserocin"
        type_id: 28694
        booster: "Synth Blue Pill"
        nebula: "Sunspark Nebula"
        regions:
          - "Black Rise"
          - "Lonetrek"
          - "Outer Passage"
          - "Sinq Laison"
          - "The Citadel"
          - "The Forge"
          - "The Spire"

      azure_sooth_sayer:
        gas_type: "Azure Mykoserocin"
        type_id: 28695
        booster: "Synth Sooth Sayer"
        nebulae:
          - "Ghost Nebula"
          - "Eagle Nebula"
        regions:
          - "Derelik"
          - "Devoid"
          - "The Bleak Lands"
          - "Heimatar"
          - "Molden Heath"
          - "Curse"
        highsec_spawns:
          confirmed: true
          regions: ["Derelik", "Heimatar"]
          security_min: 0.5
          note: "Rare spawns, significantly lower volume than lowsec"
        notes: "Minmatar/Ammatar border regions"

      celadon_exile:
        gas_type: "Celadon Mykoserocin"
        type_id: 28696
        booster: "Synth Exile"
        nebula: "Calabash Nebula"
        regions:
          - "Domain"
          - "Genesis"
          - "Placid"
          - "Solitude"
          - "Fountain (Pegasus Constellation)"

      golden_crash:
        gas_type: "Golden Mykoserocin"
        type_id: 28697
        booster: "Synth Crash"
        nebula: null
        regions:
          - "Lonetrek (Umamon constellation)"
        notes: "Historical data - verify current spawn"

      lime_frentix:
        gas_type: "Lime Mykoserocin"
        type_id: 28698
        booster: "Synth Frentix"
        nebula: "Sister Nebula"
        regions:
          - "Aridia"
          - "Curse"
          - "Derelik"
          - "Kador"
          - "Khanid"
          - "Omist"
          - "Solitude"
          - "Wicked Creek"

      malachite_mindflood:
        gas_type: "Malachite Mykoserocin"
        type_id: 28699
        booster: "Synth Mindflood"
        nebula: "Wild Nebula"
        regions:
          - "Aridia"
          - "Insmother"
          - "Kor-Azor"
          - "Curse"
          - "Omist"
          - "Solitude"
          - "Tash-Murkon"

      vermillion_x_instinct:
        gas_type: "Vermillion Mykoserocin"
        type_id: 28700
        booster: "Synth X-Instinct"
        nebulae:
          - "Flame Nebula"
          - "Pipe Nebula"
        regions:
          - "Heimatar"
          - "Great Wildlands"
          - "Insmother"
          - "Omist"
          - "Tenerifis"
          - "Metropolis"
          - "Curse"
        highsec_spawns:
          confirmed: true
          regions: ["Heimatar"]
          security_min: 0.5
          note: "Rare spawns, significantly lower volume than lowsec"
        notes: "Minmatar space and southern nullsec"

      viridian_drop:
        gas_type: "Viridian Mykoserocin"
        type_id: 28701
        booster: "Synth Drop"
        nebula: "Bright Nebula"
        regions:
          - "Essence"
          - "Fountain"
          - "Placid"
          - "Tenal"
          - "Venal"

    respawn_behavior:
      trigger: "depletion"
      scope: "regional"
      description: "Depleting a site triggers respawn elsewhere in region"

    sources:
      - url: "https://wiki.eveuniversity.org/Gas_cloud_harvesting"
        citation: 9
        accessed: "2026-01-19"

  # ---------------------------------------------------------------------------
  # Cytoserocin Distribution
  # ---------------------------------------------------------------------------
  cytoserocin:
    description: "Standard/Strong booster gas, primarily nullsec"
    security_types: ["nullsec", "low-sec"]

    hazard:
      type: "thermal"
      description: "Clouds deal thermal damage to ships inside"
      mitigation: "Hardened mining vessels or logistics support"

    flavors:
      amber_cytoserocin:
        type_id: 25268
        booster: "Blue Pill"
      azure_cytoserocin:
        type_id: 25279
        booster: "Sooth Sayer"
      celadon_cytoserocin:
        type_id: 25275
        booster: "Exile"
      golden_cytoserocin:
        type_id: 25273
        booster: "Crash"
      lime_cytoserocin:
        type_id: 25277
        booster: "Frentix"
      malachite_cytoserocin:
        type_id: 25276
        booster: "Mindflood"
      vermillion_cytoserocin:
        type_id: 25278
        booster: "X-Instinct"
      viridian_cytoserocin:
        type_id: 25274
        booster: "Drop"

    spawn_notes:
      - "Specific constellations act as high-probability anchors"
      - "Example: Serthoulde (Placid) for Viridian Cytoserocin"
      - "Regional distribution needs research - Inventory Section 4.2 has partial data"

    sources:
      - url: "https://wiki.eveuniversity.org/Gas_cloud_harvesting"
        citation: 9
        accessed: "2026-01-19"
      - url: "https://www.wckg.net/PVE/gas-mining"
        citation: 12
        accessed: "2026-01-19"

  # ---------------------------------------------------------------------------
  # Mission-Only Gas Commodities (NOT Harvestable)
  # ---------------------------------------------------------------------------
  mission_commodities:
    description: |
      These gas types exist in SDE but are NOT harvestable cosmic signatures.
      They are mission objective items only, obtained from specific missions.

    items:
      chartreuse_cytoserocin:
        type_id: 28630
        mission: "Like Drones to a Cloud"
        agent_type: "Distribution"
        notes: "Mission objective item, not a harvestable gas site"

      gamboge_cytoserocin:
        type_id: 28629
        mission: "Gas Injections"
        agent_type: "Distribution"
        notes: "Mission objective item, not a harvestable gas site"

    sources:
      - url: "dev/mechanics/EVEOnlineGasRegionalDataInquiry.md"
        note: "Research document clarifying mission-only status"
        accessed: "2026-01-19"

# =============================================================================
# SPECIAL NPC SPAWNS (Inventory Section 5)
# =============================================================================
special_npcs:

  # ---------------------------------------------------------------------------
  # Clone Soldiers (Inventory Section 5.1)
  # ---------------------------------------------------------------------------
  clone_soldiers:
    description: "Security tag NPCs in low-sec asteroid belts"
    spawn_location: "asteroid_belt"
    security_type: "low-sec"
    spawn_frequency: "~10% of belt spawns"

    spawns_by_security:
      - security: 0.4
        designation: "Clone Soldier Trainer"
        drop: "Clone Soldier Trainer Tag"
        value_tier: "lowest"
      - security: 0.3
        designation: "Clone Soldier Recruiter"
        drop: "Clone Soldier Recruiter Tag"
        value_tier: "low"
      - security: 0.2
        designation: "Clone Soldier Transporter"
        drop: "Clone Soldier Transporter Tag"
        value_tier: "high"
        estimated_value: "~25M ISK"
      - security: 0.1
        designation: "Clone Soldier Negotiator"
        drop: "Clone Soldier Negotiator Tag"
        value_tier: "highest"
        estimated_value: "~30M+ ISK"

    farming_mechanic:
      method: "belt_chaining"
      description: "Clear all rats (or just BS/commanders) to force respawn"
      respawn_timer: "~20 minutes"

    tactical_notes:
      - "Negotiators/Transporters spawn in most dangerous 0.1/0.2 systems"
      - "Dead-end systems have highest capital escalation risk"

    sources:
      - url: "https://wiki.eveuniversity.org/Security_tags"
        citation: 14
        accessed: "2026-01-19"

  # ---------------------------------------------------------------------------
  # Mordu's Legion (Inventory Section 5.2)
  # ---------------------------------------------------------------------------
  mordus_legion:
    description: "Rare spawns dropping Garmur/Orthrus/Barghest BPCs"
    spawn_location: "asteroid_belt"
    security_type: "low-sec"
    preferred_security: [0.1, 0.2]

    spawn_conditions:
      - "Non-Faction Warfare low-sec"
      - "Replaces standard belt rat spawn"

    combat_profile:
      warning: "Not standard rats"
      traits:
        - "Fast and agile"
        - "Long-range warp scramblers"
        - "Can tackle/destroy unprepared frigates"

    farming_mechanic:
      method: "belt_clearing"
      description: "Same as Clone Soldier farming - clear belts to roll for spawn"

    sources:
      - url: "https://www.reddit.com/r/Eve/comments/xq4mqt/beat_the_rare_npc_mordus_special_warfare_unit/"
        citation: 19
        accessed: "2026-01-19"

# =============================================================================
# COMBAT SITES (Inventory Section 5.3)
# =============================================================================
combat_sites:

  # ---------------------------------------------------------------------------
  # Besieged Covert Research Facility
  # ---------------------------------------------------------------------------
  besieged_covert_research_facility:
    display_name: "Besieged Covert Research Facility"
    description: "High-difficulty low-sec combat anomaly"
    category: "combat_anomaly"
    security_type: "low-sec"
    gated: false

    defenders:
      faction: "Mordu's Legion"
      dps_output: "up to 1000 DPS"
      damage_types: ["Kinetic", "Thermal"]
      ewar:
        - type: "Web"
          range: "100km"
        - type: "Warp Disruptor"
          range: "100km"

    loot_table:
      - category: "BPCs"
        items: ["Mordu hull blueprints"]
      - category: "Implants"
        items: ["Low-Grade sets", "Mid-Grade sets (Virtue, Nomad, etc.)"]
      - category: "Ammo"
        items: ["Faction missiles/charges"]
      - category: "Skillbooks"
        items: ["Neurotoxin Recovery", "other drug skills"]

    completion_mechanic:
      method: "Destroy structure"
      target: "Guristas Research and Trade Hub"
      hacking_required: false

    recommended_ships:
      - "Passive Gila"
      - "Marauder"

    sources:
      - url: "https://wiki.eveuniversity.org/Besieged_Covert_Research_Facility"
        citation: 22
        accessed: "2026-01-19"

# =============================================================================
# NULLSEC SPECIAL MECHANICS (Inventory Section 6)
# =============================================================================
nullsec_mechanics:

  # ---------------------------------------------------------------------------
  # True Security Thresholds
  # ---------------------------------------------------------------------------
  true_security_spawns:
    description: "Spawns gated by True Sec (hidden floating-point value)"

    officer_spawns:
      threshold: -0.8
      description: "Officers only spawn in -0.8 True Sec or lower"

      faction_regions:
        angel_cartel:
          officers: ["Domination"]
          regions: ["Curse", "Fountain", "Stain"]
        blood_raiders:
          officers: ["Dark Blood"]
          regions: ["Delve", "Period Basis", "Querious"]
        guristas:
          officers: ["Dread Guristas"]
          regions: ["Venal", "Tenal", "Tribute", "Deklein"]
        sanshas_nation:
          officers: ["True Sansha"]
          regions: ["Stain", "Catch"]
        drones:
          officers: ["Sentient (Unit P, Unit F, etc.)"]
          regions: ["Malpais", "Perrigen Falls"]

    mercoxit:
      threshold: -0.8
      description: "Natural Mercoxit only in -0.8 True Sec or lower"
      bypass: "Ore Prospecting Array IHUB upgrade forces spawns regardless of True Sec"
      npc_nullsec_note: "No bypass available - -0.8 rule is absolute"

    sources:
      - url: "https://forums.eveonline.com/t/officer-spawns/116571"
        citation: 24
        accessed: "2026-01-19"

# =============================================================================
# METADATA
# =============================================================================
_metadata:
  research_documents:
    - path: "dev/mechanics/EveOnlineSpecialSpawnSitesInventory.md"
      citations: 45
      scope: "All site types (mining, gas, combat, special NPCs)"
    - path: "dev/mechanics/EVEOnlineGasRegionalDataInquiry.md"
      citations: 12
      scope: "Gas regional distribution, mission item clarifications"
  schema_version: "1.0"

  sde_validation:
    last_validated: "2026-01-19"
    validation_method: "Cross-referenced via sde_search MCP tool and EVE University Wiki"
    status: "complete"
    findings:
      - "All ore type_ids verified against SDE"
      - "All gas type_ids verified against SDE"
      - "Added 2 missing Mykoserocin flavors (Azure, Vermillion) with full regional data"
      - "Azure Mykoserocin: Derelik, Devoid, Bleak Lands, Heimatar, Molden Heath, Curse"
      - "Vermillion Mykoserocin: Heimatar, Great Wildlands, Insmother, Omist, Tenerifis, Metropolis, Curse"
      - "Confirmed Chartreuse Cytoserocin is mission item ('Like Drones to a Cloud'), not harvestable"
      - "Confirmed Gamboge Cytoserocin is mission item ('Gas Injections'), not harvestable"
      - "Corrected 4 booster mappings per EVE Uni Wiki: Golden→Crash, Azure→Sooth Sayer, Vermillion→X-Instinct"
      - "Ytirium volume confirmed: 0.6 m³/unit (W-Space totals calculated)"
      - "Mission-only gas status (Chartreuse/Gamboge) validated - prevents false industrial advice"

  coverage_notes: |
    This file covers Phases 1-3 of the original proposal roadmap.
    Additional content from Inventory not yet extracted:
    - NPC Shipyard mechanics (Section 7)
    - Pochven sites (Section 8.1-8.2)
      NOTE: Observatory Flashpoint Keys are legacy/lore artifacts and are NOT
      required to enter or warp to Pochven sites in the 2026 environment.
    - Drifter Hives (Section 8.3)
    - Shattered Wormhole Ice (Section 8.4)
    - Metaliminal Storm effects (Section 9.1)
    - Chemical Labs (Section 9.2)
    - Thukker Component sites (Section 9.3)

  data_gaps:
    - "W-Space A0 Mordunium volume: Marked null, needs in-game verification"
    - "Cytoserocin constellation-specific spawn weights: Inventory Section 4.2 has partial data"
    - "High-sec Mykoserocin spawn frequency: Confirmed rare but no quantitative data"
```

### Schema Principles

1. **Source Attribution Required** - Every entry must cite Inventory section + original sources
2. **Verification Timestamps** - Track when data was last confirmed
3. **SDE Cross-Reference** - Include `type_id` where available for validation
4. **Tactical Notes** - Practical guidance for pilots
5. **Tags for Filtering** - Enable programmatic queries

---

## Validation Strategy

### Automated Validation

```python
# src/aria_esi/validation/site_compositions.py

def validate_site_compositions(data: dict) -> list[str]:
    """
    Validate site composition data against SDE.

    Checks:
    1. All type_ids exist in SDE
    2. Ore names match SDE canonical names
    3. Sources have valid URLs
    4. Verification dates are not stale (>90 days warning)

    Returns:
        List of validation warnings/errors
    """
    warnings = []

    for category_name, category in data.items():
        if category_name.startswith("_"):
            continue  # Skip metadata

        for site_id, site in category.items():
            # Check source freshness
            for source in site.get("sources", []):
                accessed = parse_date(source.get("accessed"))
                if (today() - accessed).days > 90:
                    warnings.append(
                        f"{site_id}: Source not verified in 90+ days"
                    )

            # Validate type_ids against SDE
            for content in site.get("contents", []):
                if content.get("type_id"):
                    if not sde_type_exists(content["type_id"]):
                        warnings.append(
                            f"{site_id}: Unknown type_id {content['type_id']}"
                        )

    return warnings
```

### CLI Validation Command

```bash
# Validate site composition data
uv run aria-esi validate-sites

# Output:
# Validating reference/sites/site-compositions.yaml...
# ✓ 12 sites validated
# ⚠ golden_x_instinct: Source not verified in 90+ days
# ✓ All type_ids valid against SDE
```

---

## Integration with ARIA

### Skill Access

Skills like `/mining-advisory` and `/exploration` can query this data:

```python
# In skill implementation
def get_site_info(site_type: str) -> dict | None:
    """
    Load site composition from curated data.

    Args:
        site_type: Site identifier (e.g., "empire_border_rare_asteroids")

    Returns:
        Site composition dict or None if not found
    """
    data = load_yaml("reference/sites/site-compositions.yaml")

    # Search all categories
    for category_name, category in data.items():
        if category_name.startswith("_"):
            continue
        if isinstance(category, dict) and site_type in category:
            return category[site_type]

    return None
```

### Example Skill Output

```
/mining-advisory border sites

Empire Border Rare Asteroids
────────────────────────────
Spawn: 0.5 security systems with low-sec gate connection
Respawn: Clearance-based (moves within region when depleted)

Contents (20 asteroids, 211,200 m³ total):
┌─────────────────┬───────┬───────────┬─────────────────────────┐
│ Ore             │ Count │ Volume    │ Strategic Value         │
├─────────────────┼───────┼───────────┼─────────────────────────┤
│ Ytirium         │ 16    │ 120,000   │ Primary Isogen source   │
│ Ducinium        │ 1     │ 33,168    │ Megacyte (extract first)│
│ Eifyrium        │ 1     │ 33,168    │ Zydrine (extract first) │
│ Jet Ochre       │ 1     │ 8,288     │ Nocxium/Isogen          │
│ Pellucid Crokite│ 1     │ 16,576    │ Nocxium/Zydrine         │
└─────────────────┴───────┴───────────┴─────────────────────────┘

Source: EVE University Wiki (verified 2026-01-19)
```

### MCP Tool (Future)

```python
@server.tool()
async def site_composition(
    site_type: str,
    category: str | None = None
) -> SiteCompositionResult:
    """
    Get composition data for a cosmic anomaly or signature.

    Args:
        site_type: Site identifier or search term
        category: Optional category filter (mining, gas, combat)

    Returns:
        Site contents, spawn requirements, and source attribution
    """
```

---

## Data Coverage Roadmap

### Phase 1: Mining Sites (Research Complete)

| Site Type | Inventory Section | Implementation Status |
|-----------|-------------------|----------------------|
| Empire Border Rare Asteroids | 2.2 | Ready to extract |
| W-Space Blue A0 Rare | 3.2.1 | Ready to extract |
| Nullsec Blue A0 Rare | 3.2.2 | Ready to extract |

### Phase 2: Gas Sites (Research Complete)

| Site Type | Inventory Section | Implementation Status |
|-----------|-------------------|----------------------|
| Mykoserocin by region | 4.1 | Ready to extract |
| Cytoserocin distribution | 4.2 | Ready to extract |

### Phase 3: Special NPCs (Research Complete)

| Site Type | Inventory Section | Implementation Status |
|-----------|-------------------|----------------------|
| Clone Soldiers by sec status | 5.1 | Ready to extract |
| Mordu's Legion spawns | 5.2 | Ready to extract |
| Besieged Facilities | 5.3 | Ready to extract |

### Phase 4: Advanced Content (Research Complete)

| Site Type | Inventory Section | Implementation Status |
|-----------|-------------------|----------------------|
| Officer spawn regions | 6.1 | Ready to extract |
| True Sec mechanics | 6.2 | Ready to extract |
| NPC Shipyards | 7 | Documented, complex |
| Pochven sites | 8.1-8.2 | Documented |
| Drifter Hives | 8.3 | Documented |

### Phase 5: Edge Cases

| Site Type | Inventory Section | Implementation Status |
|-----------|-------------------|----------------------|
| Metaliminal Storms | 9.1 | Documented |
| Chemical Labs | 9.2 | Documented |
| Thukker Component sites | 9.3 | Documented |
| Shattered WH Ice | 8.4 | Documented |

---

## Implementation Tasks

### Immediate (Phase 1)

1. [ ] Create `reference/sites/` directory structure
2. [ ] Extract mining anomaly data from Inventory to YAML
3. [ ] Implement `validate-sites` CLI command
4. [ ] Resolve missing `type_id` values from SDE
5. [ ] Update `/mining-advisory` skill to use site data

### Short-term (Phase 2-3)

6. [ ] Extract gas site regional data to YAML
7. [ ] Extract special NPC spawn data to YAML
8. [ ] Add staleness check to ARIA startup
9. [ ] Create `reference/sites/SOURCES.md` linking to Inventory

### Medium-term (Phase 4-5)

10. [ ] Extract advanced content (Officers, Pochven, etc.)
11. [ ] Implement `site_composition` MCP tool
12. [ ] Add pre-commit hook for validation

---

## References

### Research Document

- **Special Spawn Sites Inventory**: `dev/mechanics/EveOnlineSpecialSpawnSitesInventory.md`
  - 45 cited sources
  - Comprehensive coverage of special spawn mechanics
  - Last updated: 2026-01-19

### EVE University Wiki

- [Asteroids and Ore](https://wiki.eveuniversity.org/Asteroids_and_ore)
- [Empire Border Rare Asteroids](https://wiki.eveuniversity.org/Empire_Border_Rare_Asteroids)
- [W-Space Blue A0 Rare Asteroids](http://wiki.eveuniversity.org/W-Space_Blue_A0_Rare_Asteroids)
- [Nullsec Blue A0 Rare Asteroids](https://wiki.eveuniversity.org/Nullsec_Blue_A0_Rare_Asteroids)
- [Gas Cloud Harvesting](https://wiki.eveuniversity.org/Gas_cloud_harvesting)
- [Security Tags](https://wiki.eveuniversity.org/Security_tags)
- [Besieged Covert Research Facility](https://wiki.eveuniversity.org/Besieged_Covert_Research_Facility)

### Official Sources

- [Catalyst Expansion Notes](https://www.eveonline.com/news/view/catalyst-expansion-notes) - Spawn restriction changes
- [EVE Online Patch Notes](https://www.eveonline.com/news/patch-notes)
