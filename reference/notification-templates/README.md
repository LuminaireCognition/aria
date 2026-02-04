# Notification Profile Templates

Pre-configured notification profiles for common use cases. Create a new profile from a template:

```bash
uv run aria-esi notifications create <profile-name> --template <template-name> --webhook <discord-webhook-url>
```

## Available Templates

| Template | Description | Systems | Use Case |
|----------|-------------|---------|----------|
| `market-hubs` | Major trade hubs + adjacent systems | 15 | Trade route monitoring, hauler intel |
| `gank-pipes` | Known high-sec ganking corridors | 12 | Gank avoidance, freighter safety |
| `fw-frontlines` | Faction warfare contested zones | 16 | FW PvP intel, warzone activity |
| `starter-systems` | New player hubs and career agents | 16 | Helping newbies, griefing detection |

## Template Schema

Templates use the same YAML format as user profiles:

```yaml
schema_version: 1

name: "template-name"
display_name: "Human Readable Name"
description: "What this template monitors"
enabled: true
webhook_url: ""  # Set when creating profile

topology:
  geographic:
    systems:
      - name: "System Name"
        classification: "hunting"  # or "transit", "home", "avoidance"

triggers:
  watchlist_activity: true
  gatecamp_detected: true
  high_value_threshold: 500000000  # ISK threshold

throttle_minutes: 5

quiet_hours:
  enabled: false
  start: "02:00"
  end: "08:00"
  timezone: "America/New_York"
```

## System Classifications

| Classification | Interest Weight | Description |
|----------------|-----------------|-------------|
| `home` | 1.0 | Base of operations, always monitor |
| `hunting` | 1.0 | Active engagement areas |
| `transit` | 0.8 | Travel corridors |
| `avoidance` | 0.5 | Known dangerous areas |

## Customizing Templates

1. Create a profile from template:
   ```bash
   uv run aria-esi notifications create my-intel --template market-hubs --webhook <url>
   ```

2. Edit the generated file in `userdata/notifications/my-intel.yaml`

3. Validate your changes:
   ```bash
   uv run aria-esi notifications validate
   ```

## Creating Custom Templates

To create a new template:

1. Create a YAML file in this directory
2. Follow the schema above
3. Leave `webhook_url` empty (users set this when creating profiles)
4. Include a helpful `description`

Templates are read-only and shared with the repository. User profiles are
stored in `userdata/notifications/` and excluded from version control.
