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

A profile YAML file uses the v3 interest engine format:

```yaml
schema_version: 3

name: "profile-name"           # Unique identifier (matches filename)
display_name: "Human Name"     # Display name for UI/logs
description: "What this monitors"
enabled: true                  # false to disable without deleting

webhook_url: "https://discord.com/api/webhooks/..."

# Interest Engine v2 Configuration
interest:
  engine: v2
  preset: trade-hub            # Preset: trade-hub, political, hunter, etc.

  # Optional weight customization
  customize:
    location: "+30%"           # Boost location signal

  # Signal configuration
  signals:
    location:
      geographic:
        systems:
          - name: "Jita"
            classification: "hunting"   # hunting, transit, home, avoidance
          - name: "Perimeter"
            classification: "transit"

    value:
      min: 500000000           # ISK value threshold (500M = hauler-class)

    # Hull value filtering (hull price only, excluding modules/cargo)
    # hull_value:
    #   min: 1000000000        # 1B ISK hull (Marauders, Black Ops, capitals)
    #   scale: sigmoid
    #   pivot: 2000000000

    # Activity-based signals (spike detection, gatecamps)
    # See "Activity Signal Configuration" section below
    # activity:
    #   spike:
    #     enabled: true
    #     threshold: 2.0

    # Ship type filtering
    # ship:
    #   prefer: ["capsule"]
    #   prefer_score: 1.0

  # Rules for always-notify / always-ignore
  rules:
    always_notify:
      - watchlist_match        # Entity watchlist matches
      - gatecamp_detected      # Gatecamp pattern detection
    always_ignore:
      - pod_only               # Skip empty pod kills

  # Interest score thresholds
  thresholds:
    notify: 0.55               # Minimum to send notification
    priority: 0.85             # Minimum for priority notification
    digest: 0.35               # Minimum for digest batching

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
  provider: "anthropic"            # "anthropic", "openai", or "gemini"
  model: "claude-sonnet-4-6"  # Omit to use provider default
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
| `schema_version` | int | Yes | Current version: `3` |
| `name` | string | Yes | Unique identifier (alphanumeric, hyphens, underscores) |
| `display_name` | string | No | Human-readable name (auto-generated from name if omitted) |
| `description` | string | No | Purpose description |
| `enabled` | bool | No | Default `true` |
| `webhook_url` | string | Yes | Discord webhook URL |
| `interest` | object | Yes | Interest engine v2 configuration (see below) |
| `throttle_minutes` | int | No | Default `5`, max `60` |
| `quiet_hours` | object | No | Time-based suppression |
| `commentary` | object | No | LLM commentary settings |
| `polling` | object | No | Worker polling behavior |
| `rate_limit_strategy` | object | No | Discord rate limit handling and rollup batching |
| `delivery` | object | No | Message delivery retry |

### Interest Engine v2 Configuration

The `interest` section controls which kills generate notifications using weighted signal scoring:

```yaml
interest:
  engine: v2                   # Required
  preset: trade-hub            # Optional preset for default weights

  signals:
    location:
      geographic:
        systems:
          - name: "Jita"
            classification: "hunting"

    value:
      min: 500000000           # ISK threshold (total fitted value)

    # hull_value:               # Hull price only (excludes modules/cargo)
    #   min: 1000000000         # 1B ISK hull minimum

  rules:
    always_notify:
      - watchlist_match
      - gatecamp_detected
```

#### System Classifications

| Classification | Weight | Use Case |
|----------------|--------|----------|
| `home` | 1.0 | Base of operations, always monitor |
| `hunting` | 1.0 | Active engagement areas |
| `transit` | 0.8 | Travel corridors |
| `avoidance` | 0.5 | Known dangerous systems (lower priority) |

#### Rules

| Rule Type | Description |
|-----------|-------------|
| `always_notify` | Always send notification when these conditions match |
| `always_ignore` | Never notify when these conditions match |
| `require_all` | All listed categories must match (AND gate) |
| `require_any` | At least one listed category must match (OR gate) |

Common rule values for `always_notify`/`always_ignore`: `watchlist_match`, `gatecamp_detected`, `corp_member_victim`, `war_target_activity`, `pod_only`, `npc_only`.

Gate values for `require_all`/`require_any` are category names: `location`, `value`, `politics`, `activity`, `ship`, `war`, `time`, `routes`, `assets`.

**Example — require location match for all notifications:**

```yaml
rules:
  require_all:
    - location
  always_notify:
    - watchlist_match    # Bypasses gates
```

`always_notify` bypasses gates; `always_ignore` takes precedence over everything.

#### Activity Signal Configuration

The `activity` signal detects dangerous activity patterns. When enabled, it queries ThreatCache directly if no pre-injected data is available (self-sufficient mode).

```yaml
signals:
  activity:
    spike:
      enabled: true
      pod_only: true       # Only count pod kills for spike detection
      threshold: 3.0       # Current rate must exceed baseline * threshold
      min_current: 5       # Minimum kills in current hour before spike fires
      score: 0.7           # Score when spike detected
    gatecamp:
      enabled: true        # Detect gatecamp patterns
      min_confidence: medium  # low, medium, high
      score: 0.9
    sustained:
      enabled: true
      threshold: 5         # Minimum kills in window
      window_minutes: 60
      score: 0.5
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `spike.enabled` | bool | `true` | Enable spike detection |
| `spike.pod_only` | bool | `false` | Only count pod kills for spike rate |
| `spike.threshold` | float | `2.0` | Multiplier over 24h baseline |
| `spike.min_current` | int | `0` | Min kills in current hour to declare spike |
| `spike.score` | float | `0.7` | Score when spike detected |
| `gatecamp.enabled` | bool | `true` | Enable gatecamp detection |
| `gatecamp.min_confidence` | string | `medium` | Minimum gatecamp confidence |
| `gatecamp.score` | float | `0.9` | Score when gatecamp detected |
| `sustained.enabled` | bool | `true` | Enable sustained activity detection |
| `sustained.threshold` | int | `5` | Kill count threshold |
| `sustained.window_minutes` | int | `60` | Time window for sustained check |
| `sustained.score` | float | `0.5` | Score when sustained activity detected |

#### Location Signal Opt-In

The `location` category has two independent signals: `geographic` and `security`. Only signals explicitly configured under `signals.location` will run. If you configure only `geographic`, the `security` signal is not evaluated — the location score is based entirely on geographic matching.

```yaml
signals:
  location:
    geographic:                    # Only this signal runs
      systems:
        - name: "Jita"
          classification: "home"
    # security: ...               # Not configured — skipped entirely
```

This prevents unconfigured signals from inflating category scores. If you want both geographic and security-band filtering, configure both explicitly:

```yaml
signals:
  location:
    geographic:
      systems:
        - name: "Jita"
          classification: "home"
    security:
      bands:
        - { min: 0.5, max: 1.0 }  # High-sec only
```

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
  provider: "anthropic"         # "anthropic", "openai", or "gemini"
  model: "claude-sonnet-4-6"
  timeout_ms: 3000              # Max generation time
  max_tokens: 100               # Max response length
  warrant_threshold: 0.3        # Pattern significance threshold
  cost_limit_daily_usd: 1.0     # Daily API cost limit
  style: "radio"                # Optional: "conversational" or "radio"
  max_chars: 120                # Soft character limit (radio style only)
  persona: "paria"              # Optional persona override
```

Requires the API key for your chosen provider:

| Provider | Environment Variable | Default Model |
|----------|---------------------|---------------|
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| `gemini` | `GEMINI_API_KEY` | `gemini-2.0-flash` |

The `provider` field defaults to `"anthropic"` when omitted (backward compatible).

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
  force_rollup: false        # Buffer all kills and send batched summaries (default: false)
  rollup_window_minutes: 5   # Flush window in minutes, 1-30 (default: 5 when force_rollup)
  rollup_title: "Pod spike"  # Custom rollup message title (optional)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `rollup_threshold` | int | `10` | Pending kills before rollup mode |
| `max_rollup_kills` | int | `20` | Maximum kills in rollup message |
| `backoff_seconds` | float | `30.0` | Backoff duration on 429 response |
| `force_rollup` | bool | `false` | Buffer all matched kills and send batched summaries |
| `rollup_window_minutes` | int | `null` | Override flush window (1–30). Defaults to 5 when `force_rollup` is true, 0 otherwise |
| `rollup_title` | string | `null` | Custom title for rollup messages. Defaults to "Pod spike" or "Activity" based on content |

**Threshold-based rollup (default):** When pending notifications exceed `rollup_threshold`, the worker switches to rollup mode, combining multiple kills into a single summary message. This is reactive — it only triggers when Discord rate limits cause a backlog.

**Forced rollup mode:** When `force_rollup: true`, the worker *always* buffers matched kills instead of sending individual notifications. After `rollup_window_minutes` elapse, buffered kills are flushed as batched summaries grouped by system. This is ideal for high-volume profiles like pod spike detection, where individual messages would flood the channel.

> **Shutdown safety:** On graceful shutdown, all buffered rollup kills are force-flushed regardless of age, and all webhook queues (both rollup and non-rollup) are drained before the process exits. No queued notifications are silently dropped.

> **Note:** `throttle_minutes` applies *before* rollup buffering. With the default `throttle_minutes: 5`, only one kill per 5 minutes per system/trigger reaches the buffer — which may defeat the purpose of rollup aggregation. For `force_rollup` profiles that need to capture every kill, set `throttle_minutes: 0`.

Forced rollup message format:
```
📊 Pod spike (12 pods / 5m)
📍 Jita
🔗 https://zkillboard.com/related/30000142/...
```

**Pod-aware rollup format:** When 80% or more of kills in a rollup are pods (capsules, including Genolution capsules), the rollup message switches to a pod-specific format with a zkillboard related-kills link, omitting the ISK total (since pods have near-zero value). This pairs well with the activity spike `pod_only` configuration.

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

---

For troubleshooting, examples, LLM commentary configuration, and advanced recipes, see [NOTIFICATION_COOKBOOK.md](NOTIFICATION_COOKBOOK.md).
