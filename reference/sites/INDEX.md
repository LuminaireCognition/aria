# Site Composition Reference

This directory contains curated data about EVE Online site compositions - information that is not available through ESI or SDE but is essential for accurate tactical guidance.

## Contents

| File | Description |
|------|-------------|
| `site-compositions.yaml` | Machine-readable site composition data |
| `INDEX.md` | This file |
| `SOURCES.md` | Links to research documents and sources |

## What This Data Covers

### Mining Anomalies

| Site | Security | Key Content |
|------|----------|-------------|
| Empire Border Rare Asteroids | 0.5 high-sec (border) | Ytirium, Ducinium, Eifyrium |
| W-Space Blue A0 Rare Asteroids | Wormhole (A0 star) | Mordunium, Ytirium |
| Nullsec Blue A0 Rare Asteroids | Nullsec (A0 star) | Moonshine Ytirium (massive) |

### Gas Sites

| Type | Security | Uses |
|------|----------|------|
| Mykoserocin | High-sec, Low-sec | Synth boosters |
| Cytoserocin | Low-sec, Nullsec | Standard/Strong boosters |

Regional distribution mapped for all 8 Mykoserocin flavors.

### Special NPCs

| NPC | Location | Drops |
|-----|----------|-------|
| Clone Soldiers | Low-sec belts | Security tags (sec status repair) |
| Mordu's Legion | Low-sec belts | Garmur/Orthrus/Barghest BPCs |

### Combat Sites

| Site | Security | Difficulty |
|------|----------|------------|
| Besieged Covert Research Facility | Low-sec | High (1000+ DPS) |

### Nullsec Mechanics

- True Security thresholds for officer spawns (-0.8)
- Faction officer spawn regions
- Mercoxit spawn requirements

## Why This Data Exists

CCP does not export site composition data through ESI or SDE. This information lives server-side and is only discoverable through:

1. In-game observation
2. Community research
3. Patch notes (when sites change)

ARIA maintains this curated dataset to provide accurate mining, exploration, and PvE guidance without requiring real-time in-game queries.

## Data Quality

All entries include:

- **Source URLs** - Links to authoritative references
- **Verification dates** - When data was last confirmed
- **SDE cross-references** - `type_id` values for validation
- **Tactical notes** - Practical guidance for pilots

## Validation

Run the validation command to check data integrity:

```bash
uv run aria-esi validate-sites
```

This validates:
- All `type_id` values exist in SDE
- Source URLs are not stale (>90 days warning)
- Schema structure is valid

## Contributing

To update site composition data:

1. Verify changes in-game or via authoritative source
2. Update `site-compositions.yaml`
3. Add source URL with access date
4. Run `uv run aria-esi validate-sites`
5. Submit PR

See `SOURCES.md` for the research documents that back this data.
