# Real-Time Intel Configuration

> **Feature:** RedisQ Real-Time Intel (Phase 1-5)
> **Status:** Active

This document explains how to configure ARIA's real-time intelligence features, including gatecamp detection and killmail streaming.

## Overview

ARIA can stream killmails from zKillboard's RedisQ service to provide:
- Real-time gatecamp detection
- Minute-level kill data (vs hourly ESI aggregates)
- Active threat warnings in route and threat assessment skills

## Enabling Real-Time Intel

### 1. Start the RedisQ Poller

Real-time intel requires the background poller to be running:

```bash
# Start the poller
uv run aria-esi redisq start

# Check status
uv run aria-esi redisq status

# Stop the poller
uv run aria-esi redisq stop
```

The poller runs in the background and streams killmails to a local SQLite cache.

### 2. Configure Topology Filtering

The poller filters killmails to avoid processing the entire galaxy. You have two options:

#### Option A: Context-Aware Topology (Recommended)

Context-aware topology provides multi-layer filtering based on geography, entity relationships, routes, and assets. See [CONTEXT_AWARE_TOPOLOGY.md](CONTEXT_AWARE_TOPOLOGY.md) for full documentation.

```json
{
  "redisq": {
    "context_topology": {
      "enabled": true,
      "archetype": "hunter",
      "geographic": {
        "systems": [{"name": "Tama", "classification": "home"}]
      },
      "entity": {
        "corp_id": 98000001
      }
    }
  }
}
```

**Key benefit:** Corp member losses are always notified regardless of location.

#### Option B: Legacy Region-Based Filtering

Configure your operational regions in your pilot's `operations.md`:

```markdown
## Intel Regions

Regions to monitor for real-time threat intel:

- **Primary Region:** Sinq Laison (10000032)
- **Adjacent Regions:**
  - Essence (10000064)
  - Placid (10000048)
  - Verge Vendor (10000068)
```

Or using the structured format:

```yaml
intel_regions:
  - region_id: 10000032  # Sinq Laison
    priority: primary
  - region_id: 10000064  # Essence
    priority: adjacent
  - region_id: 10000002  # The Forge (travel)
    priority: travel
```

### Multi-Pilot Installations

When multiple pilots are configured, the poller monitors the **union** of all pilots' operational regions. Post-fetch filtering narrows results to the active pilot's specific areas of interest.

## Region ID Reference

Common region IDs for configuration:

| Region | ID | Notes |
|--------|-----|-------|
| The Forge | 10000002 | Jita trade hub |
| Domain | 10000043 | Amarr trade hub |
| Sinq Laison | 10000032 | Dodixie trade hub |
| Heimatar | 10000030 | Rens trade hub |
| Metropolis | 10000042 | Hek trade hub |
| Essence | 10000064 | Gallente core |
| Placid | 10000048 | Low-sec gateway |
| Black Rise | 10000069 | FW zone |
| The Citadel | 10000033 | Caldari core |

Use the SDE or `universe(action="systems", systems=["Jita"])` to find region IDs for other areas.

## Using Real-Time Data

### CLI Commands

```bash
# Activity with real-time data
uv run aria-esi activity-systems Tama Amamake --realtime

# Single-system gatecamp check
uv run aria-esi gatecamp Niarja

# Route analysis with real-time
uv run aria-esi gatecamp-risk Jita Amarr --realtime
```

### MCP Tools

When using ARIA skills, real-time data is automatically included when the poller is healthy:

```python
# Activity with realtime
universe(action="activity", systems=["Tama"], include_realtime=True)

# Gatecamp risk analysis
universe(action="gatecamp_risk", origin="Jita", destination="Amarr", mode="safe")
```

### Skills

The following skills automatically use real-time data when available:

| Skill | Real-Time Usage |
|-------|-----------------|
| `/threat-assessment` | Gatecamp alerts, recent kill details |
| `/route` | Active gatecamp warnings on route |
| `/gatecamp` | Full gatecamp analysis with attacker details |

## Discord Webhook Notifications (Phase 5)

ARIA can send real-time alerts to Discord when significant events occur. This is useful for monitoring while actively playing EVE on other monitors.

> **Full Documentation:** See `docs/NOTIFICATION_PROFILES.md` for complete configuration reference.

### Quick Setup

1. Create a Discord webhook (Server Settings → Integrations → Webhooks)
2. Create a notification profile:

```bash
# List available templates
uv run aria-esi notifications templates

# Create a profile from template
uv run aria-esi notifications create my-intel --template market-hubs --webhook https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN

# Test the webhook
uv run aria-esi notifications test my-intel
```

### Profile-Based Configuration

Notification profiles are YAML files in `userdata/notifications/`. Each profile has:

- **Webhook URL**: Discord webhook for this profile
- **Topology**: Which systems to monitor
- **Triggers**: What events to notify on
- **Throttling**: Rate limiting per profile
- **Quiet Hours**: Time-based suppression

Example profile (`userdata/notifications/my-intel.yaml`):

```yaml
schema_version: 2
name: my-intel
display_name: My Intel Feed
enabled: true
webhook_url: "https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"

topology:
  geographic:
    systems:
      - name: "Jita"
        classification: "hunting"
      - name: "Perimeter"
        classification: "transit"

triggers:
  watchlist_activity: true
  gatecamp_detected: true
  high_value_threshold: 500000000  # 500M ISK

throttle_minutes: 5

quiet_hours:
  enabled: true
  start: "02:00"
  end: "08:00"
  timezone: "America/New_York"
```

### Migrating from Legacy Config

If you have an existing webhook configuration in `config.json`, migrate it:

```bash
uv run aria-esi notifications migrate
```

This creates a YAML profile from your legacy `redisq.notifications` settings.

### Testing Your Webhook

```bash
uv run aria-esi notifications test <profile-name>
```

This sends a test message to verify your webhook URL is valid.

### Webhook Health

Check webhook status via the MCP `status()` tool or CLI:

```bash
uv run aria-esi redisq status
```

Health metrics include:
- `is_healthy`: Overall webhook health
- `success_rate`: Recent send success rate
- `queue_depth`: Pending notifications
- `is_paused`: Circuit breaker triggered (after repeated failures)

### Circuit Breaker

If Discord is unreachable, ARIA pauses webhook processing after 3 consecutive failures spanning >5 minutes. The queue resumes automatically when Discord becomes available. Maximum queue size is 100 messages—oldest are dropped if exceeded during extended outages.

### Security Warning

⚠️ **Webhook URLs are bearer credentials.** Anyone with the URL can post to your Discord channel. Keep your notification profiles private:

- The `userdata/` directory is in `.gitignore` by default
- Don't share your profile YAML files or include them in screenshots
- Don't commit webhook URLs to version control
- If compromised, delete the webhook in Discord and create a new one

## Configuration Sources

Real-time intel uses a split configuration model by design:

### Environment Variables (Runtime/Deployment)

Control RedisQ service behavior via environment variables or `.env`:

| Variable | Purpose | Default |
|----------|---------|---------|
| `ARIA_REDISQ_ENABLED` | Enable/disable the poller | `false` |
| `ARIA_REDISQ_REGIONS` | Region IDs to monitor (comma-separated) | All regions |
| `ARIA_REDISQ_MIN_VALUE` | Minimum ISK value to process | `0` |
| `ARIA_REDISQ_RETENTION_HOURS` | Data retention period | `24` |

These are deployment-level settings—useful for CI, containers, or temporary overrides.

### userdata/config.json (Persistent User Config)

Topology configuration lives in `config.json`:

```json
{
  "redisq": {
    "context_topology": {
      "enabled": true,
      "archetype": "hunter",
      "geographic": {
        "systems": [{"name": "Tama", "classification": "home"}]
      }
    }
  }
}
```

See `docs/CONTEXT_AWARE_TOPOLOGY.md` for full topology documentation.

### userdata/notifications/*.yaml (Per-Profile Config)

Each notification profile is self-contained with its own webhook, topology filter, and settings. See `docs/NOTIFICATION_PROFILES.md`.

### Why the Split?

- **Environment variables** are for runtime behavior that may vary by deployment (local vs CI vs production)
- **config.json** is for persistent user preferences that define "what to monitor"
- **YAML profiles** are for notification routing that may differ per Discord channel

This separation allows running the same codebase with different operational parameters without modifying user configuration files.

## Data Freshness

| Data Type | Freshness | Source |
|-----------|-----------|--------|
| Real-time kills | ~1 minute | RedisQ poller |
| Hourly aggregates | ~10 minutes | ESI activity cache |
| Gatecamp detection | 10-minute window | Threat cache analysis |
| Discord notifications | <5 seconds from processing | Webhook queue |

## Graceful Degradation

When real-time data is unavailable (poller stopped, network issues), ARIA automatically falls back to hourly ESI data without error. The response includes `realtime_healthy: false` to indicate degraded mode.

## Data Retention

| Data Type | Retention | Purpose |
|-----------|-----------|---------|
| Kill records | 24 hours | Tactical intel |
| Gatecamp detections | 7 days | Backtesting/analysis |

Cleanup runs automatically on poller startup or can be triggered manually:

```bash
uv run aria-esi redisq cleanup
```

## Troubleshooting

### Poller Not Starting

```bash
# Check for existing process
uv run aria-esi redisq status

# Check logs
tail -f ~/.aria/logs/redisq.log
```

### No Real-Time Data

1. Verify poller is running: `uv run aria-esi redisq status`
2. Check region configuration in `operations.md`
3. Verify network connectivity to `zkillredisq.stream`
4. Check for rate limiting (429 errors in logs)

### Stale Data

If `realtime_healthy` returns `false` despite poller running:

1. Check last poll time: `uv run aria-esi redisq status`
2. Poller considers data stale after 5 minutes without activity
3. Low-activity regions may naturally have sparse kills

### Discord Notifications Not Working

1. Test webhook: `uv run aria-esi test-webhook`
2. Check webhook URL is valid (not expired or deleted in Discord)
3. Verify triggers are enabled in config
4. Check throttle status—you may have received an alert recently
5. Check quiet hours—notifications are suppressed during configured window
6. Check circuit breaker—queue pauses after repeated failures

If webhook shows 401/403 errors, the URL is invalid—create a new webhook in Discord.

## Security Considerations

- Kill data is public (from zKillboard)
- No private pilot data is exposed
- Entity watchlists (Phase 4) are stored locally
- Poller uses a unique queue ID per installation
- **Discord webhook URLs are bearer credentials**—keep `userdata/config.json` private

## Related Documentation

- `docs/CONTEXT_AWARE_TOPOLOGY.md` - Multi-layer kill filtering (geography, entity, routes, assets)
- `docs/NOTIFICATION_PROFILES.md` - LLM commentary and multi-webhook routing
- `dev/proposals/REDISQ_REALTIME_INTEL_PROPOSAL.md` - Full design document
- `docs/DATA_FILES.md` - Pilot data file reference
- `.claude/skills/gatecamp/SKILL.md` - Gatecamp skill documentation
- `.claude/skills/threat-assessment/SKILL.md` - Threat assessment skill
- `.claude/skills/killmail/SKILL.md` - Killmail analysis skill (Phase 5)
- `.claude/skills/watchlist/SKILL.md` - Entity watchlist management (Phase 4)
