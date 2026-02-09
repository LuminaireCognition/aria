# ARIA Data Files Reference

> **Note:** Referenced from CLAUDE.md. Use this guide to locate pilot-specific and shared data files.

## Pilot-Specific Files

All paths use `{active_pilot}` = resolved directory from pilot resolution algorithm.

| File Type | Path | Purpose |
|-----------|------|---------|
| Pilot Profile | `userdata/pilots/{active_pilot}/profile.md` | Identity, standings, RP config |
| Operational Profile | `userdata/pilots/{active_pilot}/operations.md` | Home base, ship roster, activities (context only) |
| Ship Status | `userdata/pilots/{active_pilot}/ships.md` | Fittings, designations |
| Blueprint Library | `userdata/pilots/{active_pilot}/industry/blueprints.md` | BPO/BPC inventory |
| Mission Log | `userdata/pilots/{active_pilot}/missions.md` | Historical mission record |
| Exploration Catalog | `userdata/pilots/{active_pilot}/exploration.md` | Discovered sites, loot |
| Goals & Objectives | `userdata/pilots/{active_pilot}/goals.md` | Long-term priorities |
| Project Documents | `userdata/pilots/{active_pilot}/projects/*.md` | Pilot-specific projects |

### operations.md

**Path:** `userdata/pilots/{active_pilot}/operations.md`

**Purpose:** Human-readable operational context for ARIA LLM sessions.

**IMPORTANT: This file is NOT parsed as structured data.** ARIA reads it as natural language context to understand your:
- Home base and staging systems
- Ship roster and roles
- Primary activities and operational range

This information helps ARIA provide contextually relevant advice but is **not used for automated configuration**.

**For structured topology configuration**, use `context_topology` in `userdata/config.json`:

```json
{
  "redisq": {
    "context_topology": {
      "enabled": true,
      "geographic": {
        "systems": [
          {"name": "Sortet", "classification": "home"}
        ]
      }
    }
  }
}
```

See `docs/CONTEXT_AWARE_TOPOLOGY.md` for full configuration reference.

## Data Volatility

**Critical:** Some data changes frequently. Follow these rules to avoid stale information.

### Safe to Reference (Stable Data)

These files are updated manually and remain accurate between sessions:

- **Operational Profile** - Home base, ship roster, operational patterns
- **Pilot Profile** - Identity, standings, philosophy
- **Goals & Projects** - Long-term objectives
- **Mission Log** - Historical record
- **Exploration Catalog** - Discovered sites
- **Blueprint Library** - BPO/BPC inventory

### Never Proactively Mention (Volatile Data)

These change constantly in-game. Only reference when explicitly requested via `/esi-query`:

- **Current location** - Changes with every jump
- **Current ship** - Changes with every dock
- **Wallet balance** - Changes with every transaction
- **Active market orders** - Expire, fill, update

### Industry Data (Critical for Recommendations)

**MUST READ** before giving BPO/industry advice:
- `userdata/pilots/{active_pilot}/industry/blueprints.md` - What the pilot owns
- `reference/industry/manufacturing.md` - ME/TE research reference
- `reference/industry/npc_blueprint_sources.md` - Where to buy BPOs

## Shared Reference Material

These files contain static game data, shared across all pilots.

### Reference Data (`reference/mechanics/`)

| File | Contents |
|------|----------|
| `npc_damage_types.md` | Faction damage profiles, tank priorities |
| `exploration_sites.md` | Relic/data sites, loot tables |
| `hacking_guide.md` | Minigame strategies |
| `ore_database.md` | Ore by security, mineral composition |
| `reprocessing.md` | Yield calculations |
| `tanking_mechanics.md` | Tank theory |
| `fitting_theory.md` | Fitting principles |

### Faction Lore (`reference/lore/`)

- `gallente.md`, `caldari.md`, `minmatar.md`, `amarr.md`
- `factions.md` - Pirate and NPC corporations

### Ship Data (`reference/ships/`)

- `{faction}_progression.md` - Ship training roadmaps
- `fittings/` - Ready-to-use EFT format fittings

### PvE Intel (`reference/pve-intel/`)

- `INDEX.md` - Intel index by faction/level
- Individual intel files (missions, DED sites, expeditions) with enemy profiles, triggers, tips

### Industry Data (`reference/industry/`)

- `manufacturing.md` - Production costs, ME/TE research
- `npc_blueprint_sources.md` - BPO vendors and prices

## Real-Time Intel Configuration

Real-time intel is configured via `userdata/config.json` and notification profiles:

- **Topology configuration:** `config.json` → `redisq.context_topology`
- **Notification profiles:** `userdata/notifications/*.yaml`

See `docs/REALTIME_CONFIGURATION.md` for full configuration details.

## Master Index

For complete navigation: `reference/INDEX.md`
