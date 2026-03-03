# Exploration Site Types

Complete reference for relic, data, and special exploration sites.

Source: EVE University Wiki — validated YC128 (2026)

---

## Standard Relic & Data Sites

### Site Prefixes by Security Band

| Security | Relic Site Prefix | Data Site Prefix | NPCs? | Difficulty |
|----------|-------------------|------------------|-------|------------|
| Highsec | Crumbling [Faction] | Local [Faction] | No | Easy |
| Lowsec | Decayed [Faction] | Regional [Faction] | No | Easy-Medium |
| Nullsec | Ruined [Faction] | Central [Faction] | No | Medium |
| Wormhole C1-C3 | Ruined [Faction] | Central [Faction] | No | Medium |
| Wormhole C4-C6 | Forgotten (Sleeper) | Unsecured (Sleeper) | **Yes (Sleepers)** | Hard |

**Security flag rule:**
- "Ruined"/"Central" prefix found in highsec or lowsec = **mismatch**, double-check site name
- "Crumbling"/"Local" found in nullsec = **mismatch**
- "Forgotten"/"Unsecured" = Sleeper wormhole sites (C4+), always guarded

### Pirate Factions by Region

Sites are named by the local pirate faction for each region, indicating loot type:

| Faction | Primary Regions | Notable Loot |
|---------|-----------------|--------------|
| Angel Cartel | Minmatar null (Curse, Catch, Scalding Pass, Immensea) | Projectile components |
| Blood Raiders | Amarr null (Delve, Querious, Period Basis), Bleak Lands lowsec | Laser components |
| Guristas | Caldari null (Venal, Pure Blind, Tribute, Vale of the Silent, Geminate) | Missile/Shield components |
| Sansha's Nation | Amarr null (Stain, Esoteria), Providence adjacents | Beam laser components |
| Serpentis | Gallente null (Fountain, Syndicate area) | Hybrid/Armor components |
| Rogue Drones | Null: Cobalt Edge, Perrigen Falls, Malpais, Oasa, Kalevala Expanse, Outer Passage, Etherium Reach, The Spire; also C1-C3 wormholes | Drone components |

**Note:** Faction-to-region mapping is determined by "the local pirate group for each region." Verify specific assignments on Dotlan when scouting new regions.

### Container Names by Difficulty

| Tier | Data Container | Relic Container | Difficulty |
|------|----------------|-----------------|------------|
| I | [Faction] Info Shard | [Faction] Debris | Very Easy |
| II | [Faction] Com Tower | [Faction] Rubble | Easy |
| III | [Faction] Mainframe | [Faction] Remains | Medium |
| IV | [Faction] Databank | [Faction] Ruins | Hard |

Full site name example: "Crumbling Angel Covert Research Facility"

**Standard container mechanic:** Two failed hacks are required to destroy a container. Retry after each failed attempt.
**Exception:** Ghost Sites — one failed hack destroys the container immediately (see Ghost Sites below).
**Exception:** Drone data sites — failed hacks do not destroy containers; instead, hostile frigates may spawn.

### Null-Sec Relic Loot Quality by Container

| Container | T1 Rig Blueprint Probability | T2 Rig Blueprint Probability |
|-----------|-------------------------------|-------------------------------|
| Rubble | 25% | 5.5% |
| Remains | 50% | 12.5% |
| Ruins | 0% | 25% |

---

## Loot Reference

### Relic Site Loot

| Item Type | Value | Used For |
|-----------|-------|----------|
| Intact Armor Plates | High | T2 Rig manufacturing |
| Power Circuit | Medium | T2 Rig manufacturing |
| Burned Logic Circuit | Low | T2 Rig manufacturing |
| T2 Rig BPCs | Variable | Direct use/sale |
| Faction salvage | Medium | Faction rig manufacturing |

### Data Site Loot

| Item Type | Value | Used For |
|-----------|-------|----------|
| Decryptors | High | T2 Invention |
| Datacores | Medium | T2 Invention |
| Faction Module BPCs | Variable | Manufacturing |
| Filaments (Calm) | Low | Abyssal deadspace entry |
| Skillbooks | Low | Training |

---

## Ghost Sites

High-risk, high-reward data sites with explosion mechanics. Found in all security bands.

### Types by Security Band

| Site Name | Security | Timer Explosion Damage | Notes |
|-----------|----------|------------------------|-------|
| Lesser Covert Research Facility | Highsec | **6,000** explosive (10 km radius) | |
| Standard Covert Research Facility | Lowsec | **8,000** explosive (10 km radius) | |
| Improved Covert Research Facility | Nullsec | **10,000** explosive (10 km radius) | |
| Superior Covert Research Facility | Wormhole | **12,000** explosive (10 km radius) | |

### Ghost Site Mechanics (Post-July 2025)

- **One site-wide 30-second timer** starts when the first player warps in (or decloaks if entering cloaked)
- **Timer is visible** — a 30-second countdown is displayed
- **At expiry:** All remaining canisters detonate simultaneously
- **Failed hack:** Container explodes immediately (individual failure, not site-wide)
- **Only one attempt** per container — failed hack = container gone
- **NPC warp disruptors:** 24 km range; players >30 km away are not aggressed
- **NPC types by faction:** Serpentis, Sansha's, Guristas, Blood Raiders use Sentry warp disruptors; Angel Cartel uses Watcher type

### Ghost Site Loot

| Security Band | Loot |
|--------------|------|
| Highsec (Lesser) | Mid-grade Ascendancy Alpha/Beta/Delta/Epsilon/Gamma BPCs |
| Lowsec (Standard) | 'Wetu' Mobile Depot BPC, 'Packrat' MTC BPC, High-grade Ascendancy Alpha/Beta BPCs, Mid-grade Ascendancy Delta/Epsilon/Gamma/Omega BPCs |
| Nullsec (Improved) | 'Wetu'/'Yurt' Mobile Depot BPCs, 'Magpie' MTC BPC, High-grade Ascendancy Alpha/Beta/Delta/Epsilon/Gamma BPCs |
| Wormhole (Superior) | 'Magpie' MTC BPC, 'Wetu'/'Yurt' Mobile Depot BPCs, High-grade Ascendancy Delta/Epsilon/Gamma/Omega BPCs |

### Running Ghost Sites

**Blitz Method (30-second window):**
1. Fit explosive hardener + shield extender
2. Hack one container only
3. Warp out immediately — the 30-second timer starts on entry
4. Accept losses: a cheap, fast ship is appropriate

**Tank Method:**
- Armor cruiser with explosive resists
- Can survive single container explosion + initial NPC damage
- Allows targeting highest-value container first

---

## Sleeper Caches

K-space only (never in wormholes). Extremely dangerous sites with environmental hazards. No NPC defenders — hazards are the threat.

### Types

| Variant | Min Probe Strength | Ship Restriction | Approx. Loot Value |
|---------|-------------------|------------------|--------------------|
| Limited Sleeper Cache | 80.9 (Level IV) | Frigates only | 20-50M |
| Standard Sleeper Cache | 92 (Level IV) | All subcapitals | 50-150M |
| Superior Sleeper Cache | 104 (Level V) | All except capitals | 200M-1B+ |

### Unique Mechanics

- **Requires BOTH** Data Analyzer and Relic Analyzer
- **Environmental hazards:** Damage clouds, sentry guns, timed explosions, gas clouds
- **Gated rooms** with ship size restrictions
- **Alarm systems** that escalate hazards on failed hacks

### Sleeper Cache Loot

| Item | Value | Notes |
|------|-------|-------|
| Talocan Artifacts | High | Exclusive to caches |
| Sleeper Data Library | High | Exclusive to caches |
| Intact Hull Sections | High | Exclusive to caches |
| Sleeper Blue Loot | Medium | NPC buy orders |
| T2/Capital Materials | Medium | Manufacturing |

---

## Drone Sites

Drone relic and data sites are found in null-sec drone regions and C1-C3 wormholes.

### Drone Null-Sec Regions

Cobalt Edge, Perrigen Falls, Malpais, Oasa, Kalevala Expanse, Outer Passage, Etherium Reach, The Spire

### Drone Site Mechanics

| Site Type | Contents | Special |
|-----------|----------|---------|
| Drone Data | Two "High-Security Containment Facility", one "Research and Development Laboratories" | Failed hack does NOT destroy container — hostile frigates may spawn instead |
| Drone Relic | Mixed faction loot from all pirate factions | Despawns very quickly; do not warp out mid-run |

**Advantage:** Drone relic sites can contain salvage from ALL pirate factions in one site.

---

## Site Recommendations by Skill Level

### Beginner (T1 Analyzer, <50 Coherence)
- Highsec Crumbling/Local sites (very low risk)
- Practice hacking mechanics safely

### Intermediate (T1/T2 Analyzer, 50-80 Coherence)
- Lowsec Decayed/Regional sites (better loot, manageable risk)
- C1-C3 wormhole pirate sites (Ruined/Central)
- Highsec Ghost Sites with tank fit (30-second window)

### Advanced (T2 Analyzer, 80+ Coherence)
- Nullsec Ruined/Central sites
- Standard Ghost Sites
- Limited Sleeper Caches (requires probe strength 80.9)

### Expert (Max skills, specialized fits)
- Superior Ghost Sites
- Standard Sleeper Caches (probe strength 92, subcapitals)
- Superior Sleeper Caches (probe strength 104)
- C5-C6 Sleeper sites (combat required)

---

## Quick ISK Estimates

| Site Type | Average Loot | Risk Level |
|-----------|--------------|------------|
| Highsec Relic (Crumbling) | 1-5M | Very Low |
| Lowsec Relic (Decayed) | 5-20M | Low-Medium |
| Nullsec Relic (Ruined) | 20-80M | Medium |
| WH C1-C3 Relic (Ruined) | 20-60M | Medium |
| Ghost Site — Lesser | 50-200M | High (30s timer) |
| Ghost Site — Superior | 200M+ | Very High (30s timer) |
| Sleeper Cache — Limited | 20-50M | Very High |
| Sleeper Cache — Superior | 200M-1B+ | Extreme |

---
Source: EVE University Wiki
Last validated: YC128 (2026)
