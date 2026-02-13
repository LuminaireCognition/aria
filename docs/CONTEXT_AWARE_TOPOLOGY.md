# Operational Topology

Operational topology provides system-level kill pre-filtering for the RedisQ poller. It answers "is this kill in our area of operations?" using simple BFS expansion from configured systems.

## Overview

Topology filtering uses BFS expansion from configured operational systems with decay weights. This provides ~80-90% API call reduction by filtering kills in irrelevant systems before fetching from ESI.

For advanced interest scoring (entity tracking, value thresholds, pattern detection), use the **Interest Engine v2** in notification profiles. See [NOTIFICATION_PROFILES.md](NOTIFICATION_PROFILES.md).

## How It Works

The topology builder creates an **InterestMap** by expanding outward from your configured operational systems:

| Hop Level | Interest | Description |
|-----------|----------|-------------|
| 0 (operational) | 1.0 | Your configured systems |
| 1 (1-hop) | 1.0 | Direct neighbors |
| 2 (2-hop) | 0.7 | Two jumps away |

Systems outside hop 2 are filtered before ESI fetch, saving API quota.

## Configuration

Operational systems are configured in `userdata/config.json`:

```json
{
  "redisq": {
    "context_topology": {
      "geographic": {
        "systems": [
          {"name": "Tama", "classification": "home"},
          {"name": "Kedama", "classification": "hunting"},
          {"name": "Sujarento", "classification": "transit"}
        ]
      }
    }
  }
}
```

### System Classifications

| Classification | Weight | Use Case |
|----------------|--------|----------|
| `home` | 1.0 | Base of operations |
| `hunting` | 1.0 | Active engagement areas |
| `transit` | 0.8 | Travel corridors |
| `avoidance` | 0.5 | Known dangerous systems |

### After Modifying Configuration

**IMPORTANT:** Changes to `context_topology` in `userdata/config.json` do not take effect until the topology cache is rebuilt:

```bash
uv run aria-esi topology-build
```

The cache file (`cache/topology_map.json`) stores pre-computed interest levels. Without rebuilding:
- New home systems remain at hop-level interest (not 1.0)
- Removed systems continue to be monitored

**Always run `topology-build` after modifying:**
- `geographic.systems` (home/hunting/transit systems)

## CLI Commands

### topology-build

Build or rebuild operational topology.

```bash
uv run aria-esi topology-build --systems Tama Sujarento
```

Without `--systems`, reads from `userdata/config.json`.

### topology-show

Display current topology summary.

```bash
uv run aria-esi topology-show
```

## Special Systems

The topology builder automatically classifies well-known systems:

| Category | Systems |
|----------|---------|
| **Gank Pipes** | Uedama, Niarja, Sivala, Aufay |
| **Trade Hubs** | Jita, Amarr, Dodixie, Rens, Hek |

These are flagged in the InterestMap for display purposes.

## Integration with Notifications

Operational topology is the **pre-filter** stage in the notification pipeline. It determines which kills are worth fetching from ESI.

For per-profile interest scoring, notification profiles use the **Interest Engine v2** which provides:
- Weighted signal scoring (location, value, politics, activity)
- Rule-based always-notify / always-ignore
- Configurable thresholds and presets

See [NOTIFICATION_PROFILES.md](NOTIFICATION_PROFILES.md) for details.

```
Kill Stream (RedisQ)
       │
       ▼
┌──────────────────┐
│ Topology Filter  │  ← InterestMap: is this system in our area?
│ (should_fetch)   │
└────────┬─────────┘
         │ system in topology
         ▼
┌──────────────────┐
│   ESI Fetch      │  ← Full kill details retrieved
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Profile Evaluator│  ← Interest Engine v2 per-profile scoring
│ (per profile)    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Discord Webhook  │  ← Notification delivery
└──────────────────┘
```

## Related Documentation

- [REALTIME_CONFIGURATION.md](REALTIME_CONFIGURATION.md) - RedisQ poller and Discord webhooks
- [NOTIFICATION_PROFILES.md](NOTIFICATION_PROFILES.md) - Interest Engine v2 and multi-webhook routing
- [DATA_FILES.md](DATA_FILES.md) - Data file locations and volatility
