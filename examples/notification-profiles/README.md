# Notification Profile Examples

Example Discord notification profiles for common use cases.

## Quick Setup

1. Copy an example to `userdata/notifications/`
2. Edit the `webhook_url` with your Discord webhook
3. Customize systems and thresholds as needed
4. Validate: `uv run aria-esi notifications validate`
5. Test: `uv run aria-esi notifications test <profile-name>`

## Examples

| File | Use Case | Description |
|------|----------|-------------|
| [killwatch.yaml](killwatch.yaml) | PvP Intel | High-value kills in your region |
| [home-defense.yaml](home-defense.yaml) | Home System | Activity alerts for your staging area |

## Using Templates

ARIA includes pre-built templates for common scenarios:

```bash
# List available templates
uv run aria-esi notifications templates

# Create from template
uv run aria-esi notifications create my-intel \
  --template market-hubs \
  --webhook https://discord.com/api/webhooks/xxx/yyy
```

Available templates:
- `market-hubs` - Major trade hub activity
- `gank-pipes` - Known ganking systems (Uedama, Niarja, etc.)
- `fw-frontlines` - Faction warfare contested systems
- `starter-systems` - Rookie help channel monitoring
- `serpentis-space` - Serpentis NPC null activity

## Getting a Discord Webhook

1. Open Discord, go to your server
2. Server Settings > Integrations > Webhooks
3. New Webhook > Copy Webhook URL
4. Paste into profile's `webhook_url` field

## Profile Structure

```yaml
schema_version: 1

name: "profile-name"              # Must match filename (without .yaml)
display_name: "Human Readable"    # Shows in Discord embeds
description: "What this monitors"
enabled: true                     # Set false to disable without deleting

webhook_url: "https://discord.com/api/webhooks/..."

topology:
  geographic:
    systems:
      - name: "Jita"
        classification: "hunting"   # hunting, transit, home, avoidance

triggers:
  watchlist_activity: true          # Alert on watchlist corp/alliance activity
  gatecamp_detected: true           # Alert on suspected gatecamps
  high_value_threshold: 100000000   # Minimum kill value (ISK) to alert

throttle_minutes: 5                 # Minimum time between alerts

quiet_hours:                        # Optional: suppress during off-hours
  enabled: false
  start: "02:00"
  end: "08:00"
  timezone: "America/New_York"
```

## Documentation

- [NOTIFICATION_PROFILES.md](../../docs/NOTIFICATION_PROFILES.md) - Full configuration reference with recipes
