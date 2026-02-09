# Context-Aware Topology

Context-aware topology extends ARIA's kill filtering from simple geographic proximity to a multi-layer interest calculation system. Instead of asking "is this system nearby?", it answers "does this kill matter?"

## Overview

Traditional topology filtering uses BFS expansion from configured operational systems with decay weights. While effective (~80-90% API call reduction), it fails to capture what actually matters to a corporation:

| What Geography Misses | Context-Aware Solution |
|----------------------|------------------------|
| Corp member losses anywhere | **Entity Layer** - Corp losses always notify |
| War target activity far away | **Entity Layer** - War targets tracked globally |
| Threats on logistics routes | **Route Layer** - Named routes with ship filtering |
| Activity at corp structures | **Asset Layer** - Auto-include structure systems |
| Forming gatecamps | **Pattern Layer** - Activity spike detection |

## Layers

Interest is calculated as `max(layer_scores) * pattern_multiplier`, ensuring high-priority events always surface.

### Geographic Layer

System proximity with classifications (home/hunting/transit) and per-classification decay weights.

```json
{
  "geographic": {
    "systems": [
      {"name": "Tama", "classification": "home"},
      {"name": "Kedama", "classification": "hunting"}
    ],
    "home_weights": {"0": 1.0, "1": 0.95, "2": 0.8, "3": 0.5},
    "hunting_weights": {"0": 1.0, "1": 0.85, "2": 0.5}
  }
}
```

**Classifications:**
- `home` - Staging systems, headquarters (highest interest decay)
- `hunting` - Active roam areas (moderate decay)
- `transit` - Pass-through systems (fastest decay)

### Entity Layer

Interest based on *who* is involved, not just *where*.

```json
{
  "entity": {
    "corp_id": 98000001,
    "alliance_id": 99000001,
    "watched_corps": [98506879, 98326526],
    "watched_alliances": [99003214]
  }
}
```

**Key behavior:** Corp member losses (`corp_member_victim: 1.0`) **always** generate notifications regardless of location.

| Relationship | Default Interest |
|-------------|------------------|
| Corp member victim | 1.0 (always notify) |
| Corp member attacker | 0.9 |
| Alliance member | 0.8 |
| War target | 0.95 |
| Watched entity | 0.9 |

### Route Layer

Named routes make all waypoint systems high-interest, with optional ship type filtering.

```json
{
  "routes": [
    {
      "name": "jita_logistics",
      "waypoints": ["Tama", "Nourvukaiken", "Jita"],
      "interest": 0.95,
      "ship_filter": ["Freighter", "Transport Ship"]
    },
    {
      "name": "fw_roam",
      "waypoints": ["Tama", "Sujarento", "Nennamaila"],
      "interest": 0.85
    }
  ]
}
```

**Use case:** A hauler corp cares about Uedama even if it's 15 jumps from home—because every freighter passes through it.

### Asset Layer

Auto-include systems containing corp assets.

```json
{
  "assets": {
    "structures": true,
    "offices": true,
    "structure_interest": 1.0,
    "office_interest": 0.8
  }
}
```

Systems with corp structures get maximum interest. Currently supports manual `add_structure()` / `add_office()` calls; ESI integration planned.

### Pattern Layer

Activity patterns boost interest via multipliers.

```json
{
  "patterns": {
    "gatecamp_detection": true,
    "spike_detection": true,
    "gatecamp_multiplier": 1.5,
    "spike_multiplier": 1.3,
    "spike_threshold": 2.0
  }
}
```

**Pattern types:**
- **Gatecamp** - 3+ kills in 10 minutes with force asymmetry (1.5x multiplier)
- **Activity spike** - Current hour > baseline × threshold (1.3x multiplier)

The spike threshold (default 2.0) means current activity must be at least 2x the 24-hour average baseline to trigger escalation.

## Configuration

Full configuration lives in `userdata/config.json` under `redisq.context_topology`:

```json
{
  "redisq": {
    "context_topology": {
      "enabled": true,
      "archetype": "hunter",

      "geographic": {
        "systems": [
          {"name": "Tama", "classification": "home"},
          {"name": "Kedama", "classification": "hunting"}
        ]
      },

      "entity": {
        "corp_id": 98000001,
        "alliance_id": 99000001,
        "watched_corps": [98506879]
      },

      "routes": [
        {
          "name": "jita_logistics",
          "waypoints": ["Tama", "Nourvukaiken", "Jita"],
          "ship_filter": ["Freighter", "Transport Ship"]
        }
      ],

      "assets": {
        "structures": true,
        "offices": true
      },

      "patterns": {
        "gatecamp_detection": true,
        "spike_detection": true,
        "spike_threshold": 2.0
      },

      "fetch_threshold": 0.0,
      "log_threshold": 0.3,
      "digest_threshold": 0.6,
      "priority_threshold": 0.8
    }
  }
}
```

### After Modifying Configuration

**IMPORTANT:** Changes to `context_topology` in `userdata/config.json` do not take effect until the topology cache is rebuilt:

```bash
uv run aria-esi topology-build
```

The cache file (`cache/topology_map.json`) stores pre-computed interest levels. Without rebuilding:
- New home systems remain at hop-level interest (not 1.0)
- Removed systems continue to be monitored
- Route changes are ignored

**Always run `topology-build` after modifying:**
- `geographic.systems` (home/hunting/transit systems)
- `routes` (logistics or patrol routes)
- `archetype` (preset changes)

### Interest Thresholds

| Threshold | Default | Effect |
|-----------|---------|--------|
| `fetch_threshold` | 0.0 | Below this: don't fetch from ESI |
| `log_threshold` | 0.3 | Below this: log only (debug) |
| `digest_threshold` | 0.6 | Below this: batch into digests |
| `priority_threshold` | 0.8 | Above this: priority notification |

## Archetype Presets

Presets provide sensible defaults for common playstyles. Set `"archetype": "<name>"` and customize as needed.

| Archetype | Description | Key Settings |
|-----------|-------------|--------------|
| `hunter` | FW/piracy focused | Wide gatecamp detection, high spike sensitivity |
| `industrial` | Trade/industry focused | Route protection, asset monitoring |
| `sovereignty` | Null-sec focused | Deep territory coverage, alliance intel |
| `wormhole` | W-space focused | Entity-centric, no fixed geography |
| `mission_runner` | PvE focused | Minimal interest in PvP, aggressive filtering |

View preset details:

```bash
uv run aria-esi topology-presets
```

## CLI Commands

### topology-build

Build legacy operational topology (for backward compatibility).

```bash
uv run aria-esi topology-build Tama Sujarento --weights 1.0 1.0 0.7
```

### topology-show

Display current topology summary.

```bash
uv run aria-esi topology-show
```

### topology-explain

Debug interest calculation for a specific system.

```bash
uv run aria-esi topology-explain Tama
uv run aria-esi topology-explain Uedama
```

Output shows:
- Layer-by-layer interest scores
- Pattern escalation status (gatecamp, spike)
- Final interest calculation
- Notification tier

### topology-migrate

Convert legacy topology config to context-aware format.

```bash
uv run aria-esi topology-migrate
uv run aria-esi topology-migrate --dry-run
```

### topology-presets

List available archetype presets.

```bash
uv run aria-esi topology-presets
```

## Migration

### From Legacy Topology

Existing configurations continue to work. The legacy format:

```json
{
  "redisq": {
    "topology": {
      "enabled": true,
      "operational_systems": ["Tama", "Sujarento"],
      "interest_weights": {"operational": 1.0, "hop_1": 1.0, "hop_2": 0.7}
    }
  }
}
```

Is internally converted to:

```json
{
  "redisq": {
    "context_topology": {
      "enabled": true,
      "geographic": {
        "systems": [
          {"name": "Tama", "classification": "home"},
          {"name": "Sujarento", "classification": "home"}
        ],
        "home_weights": {"0": 1.0, "1": 1.0, "2": 0.7}
      }
    }
  }
}
```

Run `topology-migrate` to generate the new format for your config.

### Enabling Context-Aware Features

1. **Start with an archetype:**
   ```json
   "context_topology": {
     "enabled": true,
     "archetype": "hunter"
   }
   ```

2. **Add your systems:**
   ```json
   "geographic": {
     "systems": [{"name": "Tama", "classification": "home"}]
   }
   ```

3. **Enable entity tracking:**
   ```json
   "entity": {
     "corp_id": 98000001
   }
   ```

4. **Test with topology-explain:**
   ```bash
   uv run aria-esi topology-explain Tama
   ```

## Troubleshooting

### No Notifications for Corp Losses

1. Verify `entity.corp_id` is set correctly
2. Run `topology-explain` on a distant system
3. Check that context_topology is enabled

### Route Systems Not Included

1. Ensure waypoints are valid system names
2. Check that universe graph is loaded (first run may take longer)
3. Verify route interest is above fetch_threshold

### Spike Detection Not Working

1. Confirm `patterns.spike_detection: true`
2. Verify the poller has been running for 24+ hours (baseline needs history)
3. Check `spike_threshold` isn't too high (default 2.0)

### Pattern Layer Shows No Escalation

- Gatecamp detection requires 3+ kills in 10 minutes
- Spike detection requires 24 hours of baseline data
- Escalations expire after 5 minutes by default

### Performance Concerns

- Interest calculation is O(layers × 1) - constant time per system
- Route layer pre-computes all waypoint systems on startup
- Geographic layer uses pre-indexed graph lookups

## Integration with Notifications

Context-aware topology is the **first stage** in ARIA's notification pipeline. It determines which kills are worth processing before any notification logic runs.

```
Kill Stream (RedisQ)
       │
       ▼
┌──────────────────┐
│ Topology Filter  │  ← Context-aware topology decides: should we fetch this?
│ (should_fetch)   │
└────────┬─────────┘
         │ interest > fetch_threshold
         ▼
┌──────────────────┐
│   ESI Fetch      │  ← Full kill details retrieved
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Interest Calc    │  ← Full interest score with entity layer
│ (with kill data) │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Notification     │  ← Tier determines notification behavior
│ Manager          │
└──────────────────┘
         │
         ├── interest < 0.3 → Log only
         ├── interest < 0.6 → Digest batch
         ├── interest < 0.8 → Standard notification
         └── interest ≥ 0.8 → Priority notification
```

### Two-Stage Filtering

1. **Pre-fetch** (system ID only): Geographic, route, and asset layers can score. Entity layer returns 0.0 (no kill data yet).

2. **Post-fetch** (full kill data): All layers score, including entity layer. A corp member loss in a distant system may score 0.0 pre-fetch but 1.0 post-fetch.

**Important:** Pre-fetch uses conservative filtering. If *any* layer might be interested, the kill is fetched. This prevents missing corp losses in unexpected locations.

### Notification Tiers

| Tier | Interest Range | Behavior |
|------|---------------|----------|
| Filter | 0.0 | Not fetched, not logged |
| Log Only | 0.0 - 0.3 | Debug logging, no notification |
| Digest | 0.3 - 0.6 | Batched into periodic summaries |
| Standard | 0.6 - 0.8 | Individual Discord notification |
| Priority | 0.8 - 1.0 | Priority notification with commentary |

See [REALTIME_CONFIGURATION.md](REALTIME_CONFIGURATION.md) for Discord webhook setup and [NOTIFICATION_PROFILES.md](NOTIFICATION_PROFILES.md) for LLM commentary.

## Related Documentation

- [REALTIME_CONFIGURATION.md](REALTIME_CONFIGURATION.md) - RedisQ poller and Discord webhooks
- [NOTIFICATION_PROFILES.md](NOTIFICATION_PROFILES.md) - LLM commentary and multi-webhook routing
- [PROTOCOLS.md](PROTOCOLS.md) - Data handling protocols
- [ESI.md](ESI.md) - ESI integration details
- [DATA_FILES.md](DATA_FILES.md) - Data file locations and volatility
