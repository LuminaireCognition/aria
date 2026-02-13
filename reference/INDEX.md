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
| Mission intel | [pve-intel/INDEX.md](pve-intel/INDEX.md) |
| Ship fitting | [fittings/MODULE_NAMES.md](fittings/MODULE_NAMES.md) |

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
| [pve-intel/INDEX.md](pve-intel/INDEX.md) | Mission & PvE intel index by faction/level |
| [pve-intel/cache/](pve-intel/cache/) | Cached mission briefings (auto-populated by `/mission-brief`) |

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
| [fittings/MODULE_NAMES.md](fittings/MODULE_NAMES.md) | Module naming reference |

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
| [pve-intel/README.md](pve-intel/README.md) | PvE intel format specification |

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
├── pve-intel/                  [Mission & PvE Intel]
│   ├── INDEX.md
│   ├── README.md
│   └── cache/                  ← Cached mission briefings (auto-populated)
│
├── fittings/                   [Fittings Reference]
│   └── MODULE_NAMES.md         ← Module naming reference
│
├── industry/                   [Manufacturing & Research]
│   ├── npc_blueprint_sources.md
│   └── manufacturing.md
│
├── ships/                      [Vessels]
│   └── *_progression.md        ← Faction ship trees
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
| `/fitting` | Ship fitting help | fittings/*, EOS engine |
| `/journal` | Log operations | mission_log, exploration_catalog |

Natural language works too: "prepare for mission", "is this system safe", "what should I mine"

---

## Maintenance Notes

- **Adding missions:** Use `/mission-brief` to auto-cache intel in `pve-intel/cache/`
- **Adding fittings:** Add files to `fittings/` directory
- **Data sources:** EVE University Wiki, in-game databases
- **Update frequency:** As needed; lore data is stable, mechanics may change with patches

---

```
═══════════════════════════════════════════════════════════════════
ARIA LOCAL INTELLIGENCE - FULLY OPERATIONAL
═══════════════════════════════════════════════════════════════════
```
