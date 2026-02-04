# Notification Profiles

Notification profiles allow multiple Discord channels to receive different types of intel with independent filters, triggers, and throttle settings.

## Overview

Key benefits of notification profiles:

- **Multiple webhooks**: Send different intel to different Discord channels
- **Independent filters**: Each profile has its own topology (systems to monitor)
- **Per-profile throttling**: Control notification rate per channel
- **Template-based**: Quick setup from pre-configured templates
- **YAML format**: Human-readable, easy to customize

## Quick Start

### 1. Create a Profile from Template

List available templates:
```bash
uv run aria-esi notifications templates
```

Create a profile:
```bash
uv run aria-esi notifications create my-intel --template market-hubs --webhook https://discord.com/api/webhooks/xxx/yyy
```

### 2. Test the Webhook

```bash
uv run aria-esi notifications test my-intel
```

### 3. Validate Configuration

```bash
uv run aria-esi notifications validate
```

### 4. View Profile Details

```bash
uv run aria-esi notifications show my-intel
```

## Profile Location

Profiles are stored as YAML files in `userdata/notifications/`:

```
userdata/
  notifications/
    my-intel.yaml
    home-ops.yaml
    pvp-hunting.yaml
```

Templates are in `reference/notification-templates/` (read-only, tracked in git).

## Profile Schema

A profile YAML file has this structure:

```yaml
schema_version: 1

name: "profile-name"           # Unique identifier (matches filename)
display_name: "Human Name"     # Display name for UI/logs
description: "What this monitors"
enabled: true                  # false to disable without deleting

webhook_url: "https://discord.com/api/webhooks/..."

# Which systems to monitor
topology:
  geographic:
    systems:
      - name: "Jita"
        classification: "hunting"   # hunting, transit, home, avoidance
      - name: "Perimeter"
        classification: "transit"

# What events trigger notifications
triggers:
  watchlist_activity: true      # Entity watchlist matches
  gatecamp_detected: true       # Gatecamp pattern detection
  high_value_threshold: 500000000  # ISK value (500M = hauler-class)

# Rate limiting (minutes between notifications for same system/trigger)
throttle_minutes: 5

# Quiet hours (suppress notifications during sleep)
quiet_hours:
  enabled: false
  start: "02:00"                # HH:MM format
  end: "08:00"
  timezone: "America/New_York"  # IANA timezone

# Optional: LLM commentary on kills
commentary:
  enabled: false
  model: "claude-3-haiku-20240307"
  timeout_ms: 3000
  max_tokens: 100
  warrant_threshold: 0.3
  cost_limit_daily_usd: 1.0
  style: "conversational"         # "conversational" or "radio" (tactical brevity)
  max_chars: 120                  # Soft upper bound for radio style only (50-500)
  persona: "paria"                # Optional persona override
```

### Schema Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | int | Yes | Always `1` for current version |
| `name` | string | Yes | Unique identifier (alphanumeric, hyphens, underscores) |
| `display_name` | string | No | Human-readable name (auto-generated from name if omitted) |
| `description` | string | No | Purpose description |
| `enabled` | bool | No | Default `true` |
| `webhook_url` | string | Yes | Discord webhook URL |
| `topology` | object | No | Systems to monitor (see below) |
| `triggers` | object | No | Event types to notify on |
| `throttle_minutes` | int | No | Default `5`, max `60` |
| `quiet_hours` | object | No | Time-based suppression |
| `commentary` | object | No | LLM commentary settings |
| `polling` | object | No | Worker polling behavior (v2) |
| `rate_limit_strategy` | object | No | Discord rate limit handling (v2) |
| `delivery` | object | No | Message delivery retry (v2) |

### Topology Configuration

The `topology.geographic.systems` array defines which systems to monitor:

```yaml
topology:
  geographic:
    systems:
      # Simple format (just system name)
      - "Jita"

      # Detailed format (with classification)
      - name: "Perimeter"
        classification: "transit"
```

#### System Classifications

| Classification | Weight | Use Case |
|----------------|--------|----------|
| `home` | 1.0 | Base of operations, always notify |
| `hunting` | 1.0 | Active engagement areas |
| `transit` | 0.8 | Travel corridors |
| `avoidance` | 0.5 | Known dangerous systems (lower priority) |

### Trigger Configuration

| Trigger | Default | Description |
|---------|---------|-------------|
| `watchlist_activity` | `true` | Notify when watched entities are involved |
| `gatecamp_detected` | `true` | Notify on gatecamp pattern detection |
| `high_value_threshold` | `1000000000` | ISK value threshold (0 = disabled) |
| `war_activity` | `false` | Notify on war target engagements |
| `npc_faction_kill` | (object) | Notify when NPC factions are involved |

#### NPC Faction Kill Trigger

The `npc_faction_kill` trigger notifies when NPC faction corporations (Serpentis, Angel Cartel, etc.) are involved in kills. Designed for RP immersion where faction-aligned pilots want "corporate intelligence briefings" about their faction's operations.

```yaml
triggers:
  npc_faction_kill:
    enabled: true
    factions:
      - serpentis        # Serpentis Corporation, Serpentis Inquest
      - angel_cartel     # Archangels, Guardian Angels, etc.
    as_attacker: true    # Notify when faction NPCs kill someone
    as_victim: false     # Notify when someone kills faction NPCs
    ignore_topology: true  # Ignore profile topology filter (cluster-wide)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `false` | Enable/disable NPC faction kill notifications |
| `factions` | list | `[]` | Faction keys to monitor (see table below) |
| `as_attacker` | bool | `true` | Notify when NPC is the attacker |
| `as_victim` | bool | `false` | Notify when NPC is the victim |
| `ignore_topology` | bool | `true` | Skip topology filter for NPC kills |

**Available Factions:**

| Faction Key | Display Name | Notable Corps |
|-------------|--------------|---------------|
| `serpentis` | Serpentis | Serpentis Corporation, Serpentis Inquest |
| `angel_cartel` | Angel Cartel | Archangels, Guardian Angels, Dominations |
| `guristas` | Guristas Pirates | Guristas, Commando Guri |
| `blood_raiders` | Blood Raider Covenant | Blood Raiders |
| `sansha` | Sansha's Nation | True Creations, True Power |

**Volume Control:** NPC kills are frequent. Recommended `throttle_minutes: 15` or higher to avoid notification spam.

### Quiet Hours

Suppress notifications during specific hours:

```yaml
quiet_hours:
  enabled: true
  start: "02:00"    # 2:00 AM
  end: "08:00"      # 8:00 AM
  timezone: "America/New_York"
```

Time format is `HH:MM` in 24-hour notation. Timezone uses IANA names (e.g., `America/New_York`, `Europe/London`, `Asia/Tokyo`).

### Commentary (Optional)

Enable LLM-generated tactical commentary for interesting kills:

```yaml
commentary:
  enabled: true
  model: "claude-3-haiku-20240307"
  timeout_ms: 3000              # Max generation time
  max_tokens: 100               # Max response length
  warrant_threshold: 0.3        # Pattern significance threshold
  cost_limit_daily_usd: 1.0     # Daily API cost limit
  style: "radio"                # Optional: "conversational" or "radio"
  max_chars: 120                # Soft character limit (radio style only)
  persona: "paria"              # Optional persona override
```

Requires `ANTHROPIC_API_KEY` environment variable.

#### Commentary Styles

| Style | Character Limit | Description |
|-------|-----------------|-------------|
| `conversational` | None | Natural prose, 1-3 sentences. Complete sentences with personality. |
| `radio` | `max_chars` | Tactical brevity, operator cadence. Subject ellipsis, understatement. |

**Radio style example output:**
- "Watchlist contact. Thorax down, Tama."
- "Camp on Amamake gate. Eyes open."
- "Friendly down, 2.1B ISK. Stings."

**Conversational style example output:**
- "Third gank in this system in the last hour. They're running a rotation through the pipe."
- "That's a significant loss. The attackers have been working this system aggressively."

#### Stress-Aware Output

The commentary system automatically derives a "stress level" from detected patterns:

| Pattern | Stress Level | LLM Behavior |
|---------|--------------|--------------|
| `npc_faction_activity` | LOW | More expressive, fillers OK |
| `repeat_attacker` | MODERATE | Balanced tone |
| `unusual_victim` | MODERATE | Balanced tone |
| `gank_rotation` | HIGH | Calm understatement (Yeager-style) |
| `war_target_activity` | HIGH | Calm understatement |

When multiple patterns are detected, the highest-severity stress level is used.

### Polling Configuration (v2)

Control how the profile worker polls the killmail store:

```yaml
polling:
  interval_seconds: 5.0      # How often to poll (default: 5.0)
  batch_size: 50             # Max kills per poll iteration (default: 50)
  overlap_window_seconds: 60 # Look-back window for duplicate safety (default: 60)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `interval_seconds` | float | `5.0` | Seconds between poll iterations |
| `batch_size` | int | `50` | Maximum killmails to process per poll |
| `overlap_window_seconds` | int | `60` | Overlap window to prevent missed kills |

### Rate Limit Strategy (v2)

Handle Discord rate limits gracefully:

```yaml
rate_limit_strategy:
  rollup_threshold: 10       # Pending kills to trigger rollup (default: 10)
  max_rollup_kills: 20       # Max kills in a single rollup message (default: 20)
  backoff_seconds: 30.0      # Backoff time on rate limit (default: 30.0)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `rollup_threshold` | int | `10` | Pending kills before rollup mode |
| `max_rollup_kills` | int | `20` | Maximum kills in rollup message |
| `backoff_seconds` | float | `30.0` | Backoff duration on 429 response |

When pending notifications exceed `rollup_threshold`, the worker switches to rollup mode, combining multiple kills into a single summary message.

### Delivery Configuration (v2)

Control message retry behavior:

```yaml
delivery:
  max_attempts: 3            # Max delivery attempts (default: 3)
  retry_delay_seconds: 5.0   # Delay between retries (default: 5.0)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_attempts` | int | `3` | Maximum delivery attempts before marking failed |
| `retry_delay_seconds` | float | `5.0` | Seconds to wait between retry attempts |

## CLI Reference

### List Profiles

```bash
uv run aria-esi notifications list
```

Shows all profiles with status (enabled/disabled), system count, and webhook status.

### Show Profile Details

```bash
uv run aria-esi notifications show <name>
```

Displays full profile configuration including masked webhook URL.

### Create Profile

```bash
uv run aria-esi notifications create <name> --template <template> --webhook <url>
```

| Flag | Required | Description |
|------|----------|-------------|
| `--template` | Yes | Template name (see `templates` command) |
| `--webhook` | Yes | Discord webhook URL |

### Enable/Disable

```bash
uv run aria-esi notifications enable <name>
uv run aria-esi notifications disable <name>
```

Toggle profile without deleting. Disabled profiles are not loaded at runtime.

### Test Webhook

```bash
uv run aria-esi notifications test <name>
```

Sends a test message to verify webhook is working.

### Validate All

```bash
uv run aria-esi notifications validate
```

Validates all profile files, reporting any schema errors.

### List Templates

```bash
uv run aria-esi notifications templates
```

Shows available templates with descriptions and system counts.

### Delete Profile

```bash
uv run aria-esi notifications delete <name> --force
```

Permanently deletes a profile. Requires `--force` for safety.

## Available Templates

| Template | Systems | Description |
|----------|---------|-------------|
| `market-hubs` | 15 | Major trade hubs + adjacent systems |
| `gank-pipes` | 12 | Known high-sec ganking corridors |
| `fw-frontlines` | 16 | Faction warfare contested zones |
| `starter-systems` | 16 | New player hubs and career agents |

## Troubleshooting

### Profile Not Loading

**Symptoms**: Profile doesn't appear in `notifications list`

**Checks**:
1. File is in `userdata/notifications/` (not templates directory)
2. File extension is `.yaml` or `.yml`
3. YAML syntax is valid: `uv run aria-esi notifications validate`
4. Profile is enabled (`enabled: true`)

### Webhook Errors

**Symptoms**: Test message fails

**Checks**:
1. Webhook URL starts with `https://discord.com/api/webhooks/`
2. Webhook hasn't been deleted from Discord
3. Bot has permission to post in channel
4. Run `notifications test <name>` for specific error

### Notifications Not Sending

**Symptoms**: Kills in monitored systems not generating notifications

**Checks**:
1. Profile is enabled
2. System is in topology configuration
3. Throttle hasn't suppressed (wait `throttle_minutes`)
4. Not in quiet hours
5. Trigger conditions met (value threshold, watchlist, etc.)

### Schema Validation Errors

Run validation for specific errors:
```bash
uv run aria-esi notifications validate
```

Common issues:
- Invalid time format in quiet_hours (use `HH:MM`)
- Throttle exceeds maximum (60 minutes)
- Missing required webhook_url
- Unknown system classification

### Multiple Profiles, Same Webhook

This is supported. Multiple profiles can send to the same webhook URL. Each evaluates kills independently, so you might get duplicate notifications if a kill matches multiple profiles.

To avoid duplicates, ensure profiles have non-overlapping topology configurations.

## Examples

### Minimal Profile

```yaml
schema_version: 1
name: "simple"
webhook_url: "https://discord.com/api/webhooks/xxx/yyy"
```

Uses defaults: all triggers enabled, 5 minute throttle, no topology filter.

### Home System Monitoring

```yaml
schema_version: 1
name: "home-ops"
display_name: "Home Operations"
webhook_url: "https://discord.com/api/webhooks/xxx/yyy"

topology:
  geographic:
    systems:
      - name: "Sortet"
        classification: "home"
      - name: "Augnais"
        classification: "transit"
      - name: "Mies"
        classification: "transit"

triggers:
  watchlist_activity: true
  gatecamp_detected: true
  high_value_threshold: 100000000  # 100M

throttle_minutes: 3

quiet_hours:
  enabled: true
  start: "01:00"
  end: "07:00"
  timezone: "America/New_York"
```

### High-Value Only

```yaml
schema_version: 1
name: "expensive-losses"
display_name: "Expensive Losses"
webhook_url: "https://discord.com/api/webhooks/xxx/yyy"

triggers:
  watchlist_activity: false
  gatecamp_detected: false
  high_value_threshold: 5000000000  # 5B+

throttle_minutes: 1
```

No topology filter, only value-based notifications.

### NPC Faction Operations (Serpentis)

For faction-aligned pilots who want notifications about their faction's NPC activity:

```yaml
schema_version: 2
name: "serpentis-ops"
display_name: "Serpentis Corporate Intelligence"
webhook_url: "https://discord.com/api/webhooks/xxx/yyy"

triggers:
  watchlist_activity: false
  gatecamp_detected: false
  high_value_threshold: 0  # Disabled

  npc_faction_kill:
    enabled: true
    factions:
      - serpentis
      - angel_cartel  # Guardian Angels protect Serpentis per lore
    as_attacker: true
    as_victim: false
    ignore_topology: true  # Cluster-wide monitoring

throttle_minutes: 15  # Higher throttle for NPC activity volume

# Optional: Add PARIA-S persona for Serpentis-flavored commentary
commentary:
  enabled: true
  persona: paria-s
  warrant_threshold: 0.3
```

See `userdata/notifications/serpentis-operations.yaml.example` for a complete example.

---

## LLM Commentary

When enabled, ARIA can generate tactical commentary on killmail notifications using an LLM. Commentary adds context beyond the raw kill data.

### When Commentary Triggers

1. Pattern detection runs on each kill
2. Patterns contribute to a "warrant score"
3. If score exceeds threshold, LLM generates commentary
4. Commentary appends to notification (never blocks it)

### Commentary Configuration

Add to your profile YAML:

```yaml
commentary:
  enabled: true
  model: "claude-3-haiku-20240307"
  timeout_ms: 3000
  max_tokens: 100
  warrant_threshold: 0.3
  cost_limit_daily_usd: 1.0
  style: "radio"                # "conversational" or "radio"
  max_chars: 120                # Soft limit for radio style
  persona: "paria"              # Optional persona override
```

Requires `ANTHROPIC_API_KEY` environment variable.

### Pattern Detection

| Pattern | Detection Criteria | Weight |
|---------|-------------------|--------|
| `repeat_attacker` | Same corp with 3+ kills/hour in system | 0.4 |
| `gank_rotation` | Known gank corp (SAFETY., CODE.) with 2+ kills | 0.5 |
| `unusual_victim` | 1B+ ISK loss | 0.3 |
| `war_target_activity` | Watched entity with 2+ kills/hour | 0.5 |

### Warrant Score

| Score Range | Action |
|-------------|--------|
| < 0.3 | Skip - no commentary |
| 0.3 - 0.5 | Opportunistic - short timeout (1500ms) |
| > 0.5 | Generate - full timeout (3000ms) |

### Persona Voice

Commentary uses the active pilot's persona to match communication style:

| Persona | Address | Tone |
|---------|---------|------|
| ARIA Mk.IV | Capsuleer | Warm, witty, cultured |
| PARIA | Captain | Direct, irreverent, pragmatic |
| Default | pilot | Concise and tactical |

### Cost Model

- Uses Claude Haiku (~$0.00034/commentary)
- Typical usage: ~$0.02/day with moderate activity
- Daily limit configurable via `cost_limit_daily_usd`
- Notifications continue without commentary if limit reached

---

## Advanced Configuration Recipes

These recipes demonstrate common notification use cases. For the full Interest Engine v2 specification, see `dev/proposals/NOTIFICATION_FILTER_REARCHITECTURE_PROPOSAL.md`.

### Recipe: Corp Member Losses

Always notify when a corp member dies:

```yaml
interest:
  preset: industrial
  rules:
    always_notify:
      - corp_member_victim
```

### Recipe: Gatecamp Alerts

Monitor for gatecamp activity along hauling routes:

```yaml
interest:
  preset: hunter
  weights:
    activity: 0.9
    routes: 0.7
    location: 0.4
    value: 0.2
  rules:
    always_notify:
      - gatecamp_detected
    always_ignore:
      - npc_only
```

### Recipe: War Target Activity

Track kills involving war targets:

```yaml
interest:
  preset: political
  weights:
    politics: 1.0
    war: 0.8
    location: 0.2
  rules:
    always_notify:
      - war_target_activity
      - alliance_member_victim
```

### Recipe: Freighter/Industrial Focus

Prioritize hauler and industrial kills for gank intel:

```yaml
interest:
  preset: industrial
  weights:
    ship: 0.9
    value: 0.7
    location: 0.5
    activity: 0.4
  rules:
    always_ignore:
      - pod_only
```

### Recipe: Ignore Cheap Pods

Filter out pod kills unless they had expensive implants:

```yaml
interest:
  preset: trade-hub
  weights:
    value: 0.8
    location: 0.6
  signals:
    value:
      min: 100_000_000
    ship:
      pod_penalty: 0.8
  rules:
    custom:
      cheap_pod:
        all:
          - template: ship_class
            params: { classes: [capsule] }
          - template: value_below
            params: { max: 100_000_000 }
        description: "Pod kill under 100M"
    always_ignore:
      - cheap_pod
```

### Recipe: Quiet Hours

Reduce notifications during sleep hours:

```yaml
interest:
  preset: trade-hub
  weights:
    location: 0.7
    value: 0.7
    time: 0.5
  signals:
    time:
      windows:
        - { start: "08:00", end: "23:00", tz: "America/New_York" }
      outside_window_penalty: 0.6
  thresholds:
    notify: 0.6
    priority: 0.85
```

### Recipe: Wormhole Chain Security

Track all activity in your wormhole chain:

```yaml
interest:
  preset: wormhole
  weights:
    location: 1.0
    activity: 0.6
    ship: 0.3
  signals:
    location:
      geographic:
        systems:
          - { name: "J123456", classification: home }
          - { name: "J234567", classification: static }
      include_chain: true
  rules:
    always_ignore:
      - npc_only
  thresholds:
    notify: 0.3
```
