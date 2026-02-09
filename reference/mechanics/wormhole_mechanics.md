# Wormhole Mechanics Reference

Technical reference for wormhole space mechanics. This guide explains how wormholes work - their types, lifecycles, mass limits, and environmental effects.

For practical daytrip procedures, see `wormhole_daytrips.md`.

---

## Wormhole Basics

Wormholes are unstable connections between solar systems that bypass stargates.

### Key Properties

| Property | Details |
|----------|---------|
| **Lifespan** | 16-48 hours (varies by type) |
| **Mass Limit** | Total mass that can pass through |
| **Jump Mass** | Maximum mass per single jump |
| **Destination** | Fixed when spawned |
| **Visibility** | Cosmic signature (requires probes) |

### Two-Sided Nature

Every wormhole has two ends:
- **Entry side** - Has a specific designation (H121, C247, etc.)
- **Exit side** - Always labeled "K162"

When you scan a wormhole, you see the entry. When someone scans from the other side, they see K162.

---

## Connection Types

Wormholes are categorized by how they spawn and behave.

### Static Connections

Every wormhole system has 1-2 **static** connections that always regenerate.

| Property | Details |
|----------|---------|
| **Behavior** | When closed, a new one spawns to same class |
| **Destination** | Always same class (e.g., "static C3") |
| **Predictable** | You always know what type to expect |

**Example:** A C2 with "static highsec" will always have a connection to some highsec system. If you close it, a new highsec connection spawns within minutes.

### Wandering Connections

Random connections that spawn in addition to statics.

| Property | Details |
|----------|---------|
| **Behavior** | Spawn randomly, don't regenerate |
| **Destination** | Varies |
| **Frequency** | 0-3 per system typically |

### K162 (Exit Signatures)

The K162 designation means someone opened a wormhole TO your system.

| Property | Details |
|----------|---------|
| **Meaning** | "Someone warped to the entry side" |
| **Implication** | Another system has a connection to you |
| **Spawn Timing** | Appears when entry is first warped to |

**Important:** K162s don't exist until someone warps to the other side. A system can have "hidden" incoming connections.

### Frigate-Sized Holes

Some wormholes only allow small ships.

| Property | Details |
|----------|---------|
| **Ship Limit** | Frigates, destroyers, some cruisers |
| **Mass Limit** | Very low (~20,000,000 kg total) |
| **Jump Mass** | ~20,000,000 kg per jump |
| **Purpose** | Small-gang content, less threat |

Common frigate hole designations: E004, L005, Z006, M001, C008, G008, Q003

---

## Wormhole Designations

Each wormhole type has a letter-number code indicating its destination.

### K-Space Destinations

| Code | Destination | Max Jump Mass | Total Mass | Lifetime |
|------|-------------|---------------|------------|----------|
| **B274** | Highsec | 300M kg | 2B kg | 24h |
| **D845** | Highsec | 300M kg | 5B kg | 24h |
| **N110** | Highsec | 20M kg | 1B kg | 24h |
| **A239** | Lowsec | 300M kg | 2B kg | 24h |
| **U210** | Lowsec | 300M kg | 3B kg | 24h |
| **N432** | Lowsec | 1.35B kg | 3B kg | 24h |
| **K346** | Nullsec | 300M kg | 3B kg | 24h |
| **Z142** | Nullsec | 1.35B kg | 3B kg | 24h |
| **N770** | Nullsec (pochven) | 300M kg | 2B kg | 24h |

### C1 Wormhole Destinations

| Code | Destination | Max Jump Mass | Total Mass | Lifetime |
|------|-------------|---------------|------------|----------|
| **H121** | C1 | 20M kg | 500M kg | 16h |
| **Z971** | C1 | 300M kg | 2B kg | 24h |

### C2 Wormhole Destinations

| Code | Destination | Max Jump Mass | Total Mass | Lifetime |
|------|-------------|---------------|------------|----------|
| **D382** | C2 | 300M kg | 2B kg | 24h |
| **O883** | C2 | 20M kg | 1B kg | 16h |

### C3 Wormhole Destinations

| Code | Destination | Max Jump Mass | Total Mass | Lifetime |
|------|-------------|---------------|------------|----------|
| **O477** | C3 | 300M kg | 2B kg | 24h |
| **M267** | C3 | 300M kg | 1B kg | 16h |

### C4 Wormhole Destinations

| Code | Destination | Max Jump Mass | Total Mass | Lifetime |
|------|-------------|---------------|------------|----------|
| **Y683** | C4 | 300M kg | 2B kg | 24h |
| **X877** | C4 | 300M kg | 2B kg | 16h |

### C5 Wormhole Destinations

| Code | Destination | Max Jump Mass | Total Mass | Lifetime |
|------|-------------|---------------|------------|----------|
| **H296** | C5 | 1.35B kg | 3B kg | 24h |
| **N062** | C5 | 300M kg | 3B kg | 24h |

### C6 Wormhole Destinations

| Code | Destination | Max Jump Mass | Total Mass | Lifetime |
|------|-------------|---------------|------------|----------|
| **V753** | C6 | 1.35B kg | 3B kg | 24h |
| **W237** | C6 | 1.35B kg | 3B kg | 24h |

### Special Destinations

| Code | Destination | Notes |
|------|-------------|-------|
| **K162** | Unknown | Exit side of any wormhole |
| **F353** | Thera | Connection to Thera system |
| **Q003** | Null (frigate) | Frigate-only to nullsec |
| **E004** | C1 (frigate) | Frigate-only |
| **L005** | C2 (frigate) | Frigate-only |
| **Z006** | C3 (frigate) | Frigate-only |
| **M001** | C4 (frigate) | Frigate-only |
| **C008** | C5 (frigate) | Frigate-only |
| **G008** | C6 (frigate) | Frigate-only |

---

## Mass Mechanics

Wormholes have mass limits that determine how much can pass through.

### Mass Properties

| Property | Description |
|----------|-------------|
| **Total Mass** | Maximum mass that can ever pass through |
| **Jump Mass** | Maximum mass for a single ship jump |
| **Regeneration** | Mass regenerates ~10% over lifetime |

### Ship Mass Reference

| Ship Class | Approximate Mass |
|------------|------------------|
| Frigate | 1-2M kg |
| Destroyer | 1-2M kg |
| Cruiser | 10-13M kg |
| Battlecruiser | 12-16M kg |
| Battleship | 95-105M kg |
| Capital | 1,000-1,500M kg |
| Supercarrier | 1,300-1,500M kg |
| Titan | 2,400M+ kg |

### Mass Status Messages

Right-click → Show Info reveals mass status:

| Message | Mass Remaining | Implication |
|---------|----------------|-------------|
| "not yet been disrupted" | >50% | Plenty of room |
| "has had its stability reduced" | 10-50% | Moderate use |
| "critically disrupted" | <10% | Close to collapse |

### Jump Mass Limits

| Max Jump Mass | What Can Pass |
|---------------|---------------|
| 5M kg | Frigates, destroyers only |
| 20M kg | Up to cruisers |
| 62M kg | Up to battlecruisers |
| 300M kg | Up to battleships |
| 375M kg | Up to some capitals |
| 1,000M kg | Most capitals |
| 1,350M kg | All subcaps + most capitals |
| 1,800M kg | Supercarriers |

### Mass Manipulation

Propulsion modules affect your mass:

| Module | Effect on Mass |
|--------|----------------|
| MWD (active) | +500% (5x mass) |
| 100MN AB (active) | +500% (5x mass) |
| Higgs Anchor Rig | +100% base mass |
| Plates | +mass (varies) |

**Rolling holes:** Use MWD + plates to add mass and close wormholes faster.

### Spawn Mass Variance

Wormholes spawn with random mass within a range:
- Typically 50-100% of maximum listed mass
- A "2B kg" hole might spawn with 1-2B actual mass

---

## Lifetime Mechanics

All wormholes have a natural lifespan.

### Lifetime Stages

| Stage | Show Info Message | Time Remaining |
|-------|-------------------|----------------|
| Fresh | "not yet begun to decay" | >24h remaining |
| Decaying | "beginning to decay" | 4-24h remaining |
| End of Life (EOL) | "reaching the end of its natural lifetime" | <4h remaining |
| Critical | "on the verge of dissipating" | Minutes |

### Typical Lifespans

| Wormhole Type | Base Lifetime |
|---------------|---------------|
| Most K-space connections | 24 hours |
| Some WH-to-WH connections | 16 hours |
| Frigate holes | 16 hours |
| Wandering connections | Varies |

### EOL Behavior

When a wormhole enters EOL:
- It will collapse within 4 hours (randomly)
- Could be minutes, could be hours
- **Never enter an EOL hole without scanning ability**

### Regeneration

Wormholes regenerate approximately 10% of their mass over their lifetime. This happens gradually, not all at once.

---

## Wormhole Classes

Wormhole space is divided into classes (C1-C6) indicating difficulty and content.

### Class Overview

| Class | Difficulty | Static To | Site Difficulty | Blue Loot/Site |
|-------|------------|-----------|-----------------|----------------|
| **C1** | Easy | K-space | Solo frigate | ~8-15M |
| **C2** | Easy-Med | 2 statics (varies) | Solo destroyer | ~15-25M |
| **C3** | Medium | K-space | Solo BC/cruiser | ~30-50M |
| **C4** | Hard | W-space only | Fleet (2-3) | ~50-80M |
| **C5** | Very Hard | W-space only | Fleet (5+) | ~100-300M |
| **C6** | Extreme | W-space only | Large fleet | ~200-500M |

### C1 Wormholes

| Property | Details |
|----------|---------|
| **Static** | 1 static to K-space |
| **Sites** | Perimeter sites (frigate Sleepers) |
| **Solo** | Yes, in frigate/destroyer |
| **Typical Residents** | New players, daytrippers, PI alts |

### C2 Wormholes

| Property | Details |
|----------|---------|
| **Static** | 2 statics (one K-space, one W-space) |
| **Sites** | Frontier sites (destroyer Sleepers) |
| **Solo** | Yes, in cruiser |
| **Typical Residents** | Small corps, content farmers |

C2s are popular because they have both K-space access and W-space connections for content.

### C3 Wormholes

| Property | Details |
|----------|---------|
| **Static** | 1 static to K-space |
| **Sites** | Core sites (cruiser Sleepers) |
| **Solo** | Yes, in well-fit BC or T3C |
| **Typical Residents** | Solo players, small groups |

### C4 Wormholes

| Property | Details |
|----------|---------|
| **Static** | 2 statics to W-space (no K-space) |
| **Sites** | Frontier/Core sites |
| **Solo** | Difficult, fleet preferred |
| **Typical Residents** | PvP corps |

C4s have no direct K-space static, making them more isolated.

### C5 Wormholes

| Property | Details |
|----------|---------|
| **Static** | 1-2 statics to W-space |
| **Sites** | Capital escalation sites |
| **Solo** | No (requires fleet/capitals) |
| **Typical Residents** | Large corps, capital groups |

### C6 Wormholes

| Property | Details |
|----------|---------|
| **Static** | 1-2 statics to W-space |
| **Sites** | Hardest Sleeper content |
| **Solo** | No (requires fleet/capitals) |
| **Typical Residents** | Large alliances, elite groups |

### Special Wormhole Systems

#### Shattered Wormholes

| Property | Details |
|----------|---------|
| **Identifying** | All planets are shattered |
| **Stations** | Cannot anchor structures |
| **Statics** | Multiple random connections |
| **Effect** | Has a wormhole effect |

#### Thera

| Property | Details |
|----------|---------|
| **Size** | Largest WH system (342 AU) |
| **Connections** | Many random connections to K-space |
| **Stations** | Has NPC stations (rare in WH) |
| **Use** | Travel hub, content finding |
| **Intel** | eve-scout.com tracks Thera connections |

#### Drifter Wormholes (C14-C18)

| Property | Details |
|----------|---------|
| **Access** | Through Drifter wormholes or unidentified structures |
| **Content** | Drifter NPCs, unique sites |
| **Difficulty** | Extreme (Drifters use doomsdays) |
| **Loot** | Drifter components, high value |

---

## Wormhole Effects

Some wormhole systems have permanent environmental effects.

### Effect Overview

| Effect | Primary Bonus | Primary Penalty |
|--------|---------------|-----------------|
| **Magnetar** | +Damage | -Tracking/Guidance |
| **Black Hole** | +Speed/Agility | -Stasis Web/Inertia |
| **Pulsar** | +Shield HP/Capacitor | -Armor/Signature |
| **Wolf-Rayet** | +Armor HP/Small Weapon | -Shield/Signature |
| **Cataclysmic Variable** | +Shield Boost/Cap Regen | -Cap Amount/Remote Rep |
| **Red Giant** | +Heat/Smartbomb/Overload | -Bomb Damage |

### Magnetar

| Attribute | C1 | C2 | C3 | C4 | C5 | C6 |
|-----------|----|----|----|----|----|----|
| Damage | +30% | +44% | +58% | +72% | +86% | +100% |
| Missile Exp Velocity | -15% | -22% | -29% | -36% | -43% | -50% |
| Missile Exp Radius | +15% | +22% | +29% | +36% | +43% | +50% |
| Drone Tracking | -15% | -22% | -29% | -36% | -43% | -50% |
| Turret Tracking | -15% | -22% | -29% | -36% | -43% | -50% |
| Target Painter Strength | -15% | -22% | -29% | -36% | -43% | -50% |

**Magnetar Meta:** High alpha, missiles/drones struggle with application. Favor turrets with high base damage.

### Black Hole

| Attribute | C1 | C2 | C3 | C4 | C5 | C6 |
|-----------|----|----|----|----|----|----|
| Ship Velocity | +30% | +44% | +58% | +72% | +86% | +100% |
| Stasis Web Strength | -15% | -22% | -29% | -36% | -43% | -50% |
| Inertia | +15% | +22% | +29% | +36% | +43% | +50% |
| Targeting Range | +30% | +44% | +58% | +72% | +86% | +100% |

**Black Hole Meta:** Kiting paradise. Ships are fast but hard to catch. Tackle is less effective.

### Pulsar

| Attribute | C1 | C2 | C3 | C4 | C5 | C6 |
|-----------|----|----|----|----|----|----|
| Shield HP | +30% | +44% | +58% | +72% | +86% | +100% |
| Armor Resist | -15% | -22% | -29% | -36% | -43% | -50% |
| Capacitor Recharge | -15% | -22% | -29% | -36% | -43% | -50% |
| Signature | +30% | +44% | +58% | +72% | +86% | +100% |
| NOS/Neut Drain | +30% | +44% | +58% | +72% | +86% | +100% |

**Pulsar Meta:** Shield ships dominate. Armor ships suffer. Neuts are very powerful.

### Wolf-Rayet

| Attribute | C1 | C2 | C3 | C4 | C5 | C6 |
|-----------|----|----|----|----|----|----|
| Armor HP | +30% | +44% | +58% | +72% | +86% | +100% |
| Shield Resist | -15% | -22% | -29% | -36% | -43% | -50% |
| Small Weapon Damage | +60% | +88% | +116% | +144% | +172% | +200% |
| Signature | -15% | -22% | -29% | -36% | -43% | -50% |

**Wolf-Rayet Meta:** Small ships with armor tank excel. Frigates do battleship damage. Shield ships suffer.

### Cataclysmic Variable

| Attribute | C1 | C2 | C3 | C4 | C5 | C6 |
|-----------|----|----|----|----|----|----|
| Shield Boost Amount | +30% | +44% | +58% | +72% | +86% | +100% |
| Armor Rep Amount | +30% | +44% | +58% | +72% | +86% | +100% |
| Local Rep Cap Need | +30% | +44% | +58% | +72% | +86% | +100% |
| Remote Rep Amount | -15% | -22% | -29% | -36% | -43% | -50% |
| Remote Rep Cap Need | +30% | +44% | +58% | +72% | +86% | +100% |
| Cap Amount | -15% | -22% | -29% | -36% | -43% | -50% |
| Cap Recharge Rate | +30% | +44% | +58% | +72% | +86% | +100% |

**Cataclysmic Variable Meta:** Local tank strong but cap hungry. Remote reps (logi) weaker. Solo-friendly.

### Red Giant

| Attribute | C1 | C2 | C3 | C4 | C5 | C6 |
|-----------|----|----|----|----|----|----|
| Heat Damage | -15% | -22% | -29% | -36% | -43% | -50% |
| Overload Bonus | +30% | +44% | +58% | +72% | +86% | +100% |
| Smart Bomb Damage | +30% | +44% | +58% | +72% | +86% | +100% |
| Smart Bomb Range | +30% | +44% | +58% | +72% | +86% | +100% |
| Bomb Damage | -15% | -22% | -29% | -36% | -43% | -50% |

**Red Giant Meta:** Overheat everything with less penalty. Smartbombs are dangerous. Bombs are weak.

### No Effect

Many wormhole systems have no environmental effect. These are often preferred for predictable combat.

---

## Wormhole Rolling

"Rolling" a wormhole means intentionally collapsing it.

### Why Roll Holes

| Reason | Details |
|--------|---------|
| Security | Close connections to reduce threats |
| Content | Close bad static, get new one |
| Trapping | Close hole behind enemy fleet |
| Eviction | Isolate target system |

### Basic Rolling Method

1. Check hole mass status
2. Jump heavy ships through repeatedly
3. Use MWD to increase jump mass
4. Final ship may get trapped on wrong side

### The "Rage Roll"

When rolling statics for content:
1. Roll current static
2. New static spawns (same class)
3. Scout new connection
4. If bad, roll again
5. Repeat until good connection found

### Rolling Ships

| Ship | Base Mass | With MWD | With Higgs+MWD | Notes |
|------|-----------|----------|----------------|-------|
| Battleship | 100M kg | 500M kg | 1B kg | Common roller |
| Megathron | 98M kg | 490M kg | 980M kg | Popular choice |
| Orca | 250M kg | N/A | 500M kg | Industrial roller |

---

## Useful Formulas

### Effective HP in Effect Systems

```
Pulsar Shield EHP = Base Shield HP × (1 + effect bonus)
Wolf-Rayet Armor EHP = Base Armor HP × (1 + effect bonus)
```

### Mass Needed to Collapse

```
Jumps needed ≈ (Current Mass) / (Ship Mass × MWD multiplier)
```

### Wormhole Spawn Timing

| Event | Timing |
|-------|--------|
| K162 appears | When entry side is first warped to |
| New static spawns | Within minutes of old one closing |
| Wandering holes | Random throughout lifetime |

---

## Quick Reference Tables

### Wormhole Class Summary

| Class | Statics | K-Space Access | Solo Viable | Typical Activity |
|-------|---------|----------------|-------------|------------------|
| C1 | 1 (K-space) | Yes | Frigate+ | PI, daytrips |
| C2 | 2 (mixed) | Yes | Cruiser+ | Small gang |
| C3 | 1 (K-space) | Yes | BC+ | Solo PvE |
| C4 | 2 (W-space) | No direct | Fleet | PvP |
| C5 | 1-2 (W-space) | No direct | Fleet + caps | Krabbing |
| C6 | 1-2 (W-space) | No direct | Large fleet | Elite PvE |

### Effect Summary

| Effect | Favors | Avoid |
|--------|--------|-------|
| Magnetar | Alpha, turrets | Drones, missiles |
| Black Hole | Kiters | Brawlers |
| Pulsar | Shield tanks | Armor tanks |
| Wolf-Rayet | Armor/small | Shield/large |
| Cataclysmic | Solo, local tank | Logi fleets |
| Red Giant | Overheat, smartbomb | Bombers |

### Mass Limits Quick Reference

| Jump Mass | Ship Limit |
|-----------|------------|
| 20M kg | Cruisers |
| 300M kg | Battleships |
| 1,000M kg | Most capitals |
| 1,350M kg | All subcaps |

---

## Glossary

| Term | Definition |
|------|------------|
| **Static** | Permanent wormhole type that regenerates |
| **Wandering** | Random temporary connection |
| **K162** | Exit signature (other side came to you) |
| **EOL** | End of Life (<4 hours remaining) |
| **Crit** | Critically low mass (<10%) |
| **Rolling** | Intentionally collapsing a wormhole |
| **Chain** | Series of connected wormhole systems |
| **Rage rolling** | Repeatedly rolling static for content |
| **Hole control** | Watching/controlling connections |
| **Blue loot** | Sleeper components (NPC buy orders) |
| **Krab** | PvE for ISK (from "carebear") |

---
Source: EVE University Wiki, wormhole community resources
Last updated: YC128 (2026)
