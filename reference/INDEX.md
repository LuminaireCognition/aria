# ARIA Local Intelligence Database

Master index for all cached reference data.

```
═══════════════════════════════════════════════════════════════════
ARIA DATABASE v1.0
Gallente Federation Navy Mk.IV Tactical Assistant
───────────────────────────────────────────────────────────────────
Total Files: 31 | Cache Size: ~156 KB
Last Updated: YC128.01.13
═══════════════════════════════════════════════════════════════════
```

## Quick Access

| Need | File |
|------|------|
| What damage to deal/tank? | [mechanics/npc_damage_types.md](mechanics/npc_damage_types.md) |
| Drone damage types | [mechanics/drones.md](mechanics/drones.md) |
| Hacking help | [mechanics/hacking_guide.md](mechanics/hacking_guide.md) |
| Mission intel | [missions/INDEX.md](missions/INDEX.md) |
| Ship fitting | [ships/fittings/README.md](ships/fittings/README.md) |

---

## Capsuleer Data

Personal operational files are stored in `userdata/pilots/{active_pilot}/`:

| File | Description |
|------|-------------|
| `profile.md` | Character information, standings, goals |
| `ships.md` | Ship roster and fittings |
| `missions.md` | Mission history |
| `exploration.md` | Discovered sites and loot records |

---

## Reference Database

### Combat & Missions

| File | Contents |
|------|----------|
| [mechanics/npc_damage_types.md](mechanics/npc_damage_types.md) | Faction damage tables, EWAR types, tank priorities |
| [mechanics/drones.md](mechanics/drones.md) | **Drone damage types**, faction recommendations, bandwidth |
| [mechanics/drones.json](mechanics/drones.json) | Machine-readable drone data (Python/JSON) |
| [missions/INDEX.md](missions/INDEX.md) | Mission intel index by faction/level |
| [missions/gone_berserk_l2.md](missions/gone_berserk_l2.md) | Gone Berserk L2 (EoM) |
| [missions/gone_berserk_l3.md](missions/gone_berserk_l3.md) | Gone Berserk L3 (EoM) |
| [missions/drone_infestation_l2.md](missions/drone_infestation_l2.md) | Drone Infestation L2 |
| [missions/the_blockade_serpentis_l2.md](missions/the_blockade_serpentis_l2.md) | The Blockade L2 (Serpentis) |
| [missions/silence_the_informant_l2.md](missions/silence_the_informant_l2.md) | Silence the Informant L2 |

### Exploration

| File | Contents |
|------|----------|
| [mechanics/exploration_sites.md](mechanics/exploration_sites.md) | Site types, difficulty, loot tables, ghost sites, sleeper caches |
| [mechanics/hacking_guide.md](mechanics/hacking_guide.md) | Minigame mechanics, node types, strategies |
| [mechanics/gas_harvesting.md](mechanics/gas_harvesting.md) | Gas types, locations, booster production |

### Mining & Industry

| File | Contents |
|------|----------|
| [mechanics/ore_database.md](mechanics/ore_database.md) | Ore by security, minerals, ice types |
| [mechanics/reprocessing.md](mechanics/reprocessing.md) | Yield formulas, skill effects, facility comparison |
| [industry/npc_blueprint_sources.md](industry/npc_blueprint_sources.md) | BPO acquisition, NPC sellers, prices |
| [industry/manufacturing.md](industry/manufacturing.md) | ME/TE research, job costs, production |

### Ships & Fittings

| File | Contents |
|------|----------|
| [ships/gallente_progression.md](ships/gallente_progression.md) | Combat, mining, exploration ship trees |
| [ships/fittings/README.md](ships/fittings/README.md) | Fitting index, substitution guide |
| [ships/fittings/venture_mining.md](ships/fittings/venture_mining.md) | Venture highsec mining fit |
| [ships/fittings/venture_gas.md](ships/fittings/venture_gas.md) | Venture gas harvesting fit |
| [ships/fittings/vexor_l2_general.md](ships/fittings/vexor_l2_general.md) | Vexor omni-tank mission fit |
| [ships/fittings/vexor_serpentis.md](ships/fittings/vexor_serpentis.md) | Vexor anti-Serpentis fit |
| [ships/fittings/imicus_exploration.md](ships/fittings/imicus_exploration.md) | Imicus exploration fit |

### Skills & Training

| File | Contents |
|------|----------|
| [skills/training_optimization.md](skills/training_optimization.md) | Attributes, remaps, implants, training paths |

---

## Lore Database

Background intelligence on New Eden.

| File | Contents |
|------|----------|
| [lore/gallente.md](lore/gallente.md) | Federation history, culture, values |
| [lore/factions.md](lore/factions.md) | Major factions overview |
| [lore/regions.md](lore/regions.md) | Regional information |

---

## System Files

| File | Purpose |
|------|---------|
| [.cache-manifest.json](.cache-manifest.json) | Cache freshness tracking (24h TTL) |
| [mechanics/esi_api_urls.md](mechanics/esi_api_urls.md) | **ESI documentation URLs** - working URLs, 404 avoidance |
| [missions/README.md](missions/README.md) | Mission data format specification |

### Cache Policy

Files with ESI sources use 24-hour cache expiration:
- **Fresh (<24h):** Use cached file directly
- **Stale (>24h):** Auto-refresh from GalNet ESI
- **Manual files:** No expiration, capsuleer maintains

---

## Directory Structure

```
reference/
├── INDEX.md                    ← You are here
│
├── mechanics/                  [Game Mechanics]
│   ├── npc_damage_types.md
│   ├── drones.md               ← Master drone reference
│   ├── drones.json             ← Machine-readable drone data
│   ├── hacking_guide.md
│   ├── ore_database.md
│   ├── reprocessing.md
│   ├── exploration_sites.md
│   ├── gas_harvesting.md
│   └── esi_api_urls.md         ← ESI documentation URLs
│
├── missions/                   [Mission Intel]
│   ├── INDEX.md
│   └── *.md                    ← Per-mission briefings
│
├── industry/                   [Manufacturing & Research]
│   ├── npc_blueprint_sources.md
│   └── manufacturing.md
│
├── ships/                      [Vessels & Fittings]
│   ├── *_progression.md        ← Faction ship trees
│   └── fittings/
│       ├── README.md
│       └── *.md                ← Ship fittings in EFT format
│
├── skills/                     [Training]
│   └── training_optimization.md
│
├── sites/                      [Combat & Exploration Sites]
│   └── INDEX.md
│
└── lore/                       [Background Intel]
    ├── gallente.md
    ├── caldari.md
    ├── minmatar.md
    ├── amarr.md
    ├── factions.md
    └── regions.md
```

**Pilot data** is stored separately in `userdata/pilots/{character_id}_{name}/`.

---

## ARIA Skill Commands

Quick access via slash commands:

| Command | Function | Key Data Sources |
|---------|----------|------------------|
| `/help` | Command listing and guidance | This index |
| `/aria-status` | Operational status | pilot_profile, ship_status |
| `/esi-query` | Live GalNet data | ESI API (location, wallet, skills) |
| `/mission-brief` | Mission intelligence | missions/*, npc_damage_types |
| `/mining-advisory` | Mining guidance | ore_database, reprocessing |
| `/exploration` | Site analysis | exploration_sites, hacking_guide |
| `/threat-assessment` | Security analysis | npc_damage_types, factions |
| `/fitting` | Ship fitting help | ships/fittings/* |
| `/journal` | Log operations | mission_log, exploration_catalog |

Natural language works too: "prepare for mission", "is this system safe", "what should I mine"

---

## Maintenance Notes

- **Adding missions:** Create file in `missions/`, update `missions/INDEX.md`
- **Adding fittings:** Create file in `ships/fittings/`, update `fittings/README.md`
- **Data sources:** EVE University Wiki, in-game databases
- **Update frequency:** As needed; lore data is stable, mechanics may change with patches

---

```
═══════════════════════════════════════════════════════════════════
ARIA LOCAL INTELLIGENCE - FULLY OPERATIONAL
═══════════════════════════════════════════════════════════════════
```
