# Notification Cookbook

Advanced configuration recipes, troubleshooting, and LLM commentary for notification profiles.

For setup, schema reference, and CLI commands, see [NOTIFICATION_PROFILES.md](NOTIFICATION_PROFILES.md).

---

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

### Location Gate Not Filtering

**Symptoms**: Using `require_all: [location]` with only `geographic` configured, but kills in unrelated systems still trigger notifications.

**Cause**: Prior to the signal opt-in fix, unconfigured signals (like `security`) would run and return a default score, inflating the location category average past the match threshold.

**Fix**: Update to the latest version. Run `notifications validate` and check for these warnings:
- `LOCATION_GATE_GEOGRAPHIC_ONLY` — informational: location matching uses only `geographic` (this is usually correct)
- `LOCATION_GATE_NO_SIGNALS` — error condition: gate requires `location` but no location signals are configured, so the gate will always fail

If you see `LOCATION_GATE_NO_SIGNALS`, add a `signals.location.geographic` block with your systems.

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
- `LOCATION_GATE_GEOGRAPHIC_ONLY` — gate on `location` with only geographic signal (informational)
- `LOCATION_GATE_NO_SIGNALS` — gate on `location` with no location signals configured

### Multiple Profiles, Same Webhook

This is supported. Multiple profiles can send to the same webhook URL. Each evaluates kills independently, so you might get duplicate notifications if a kill matches multiple profiles.

To avoid duplicates, ensure profiles have non-overlapping topology configurations.

---

## Examples

### Minimal Profile

```yaml
schema_version: 3
name: "simple"
webhook_url: "https://discord.com/api/webhooks/xxx/yyy"

interest:
  engine: v2
  preset: trade-hub
```

Uses preset defaults with 5 minute throttle.

### Home System Monitoring

```yaml
schema_version: 3
name: "home-ops"
display_name: "Home Operations"
webhook_url: "https://discord.com/api/webhooks/xxx/yyy"

interest:
  engine: v2
  preset: trade-hub

  signals:
    location:
      geographic:
        systems:
          - name: "Sortet"
            classification: "home"
          - name: "Augnais"
            classification: "transit"
          - name: "Mies"
            classification: "transit"

    value:
      min: 100000000  # 100M

  rules:
    always_notify:
      - watchlist_match
      - gatecamp_detected

throttle_minutes: 3

quiet_hours:
  enabled: true
  start: "01:00"
  end: "07:00"
  timezone: "America/New_York"
```

### High-Value Only

```yaml
schema_version: 3
name: "expensive-losses"
display_name: "Expensive Losses"
webhook_url: "https://discord.com/api/webhooks/xxx/yyy"

interest:
  engine: v2
  preset: trade-hub

  signals:
    value:
      min: 5000000000  # 5B+

throttle_minutes: 1
```

No location filter, only value-based notifications.

### Political / Faction Operations (Serpentis)

For faction-aligned pilots who want notifications about their faction's activity:

```yaml
schema_version: 3
name: "serpentis-ops"
display_name: "Serpentis Corporate Intelligence"
webhook_url: "https://discord.com/api/webhooks/xxx/yyy"

interest:
  engine: v2
  preset: political

  customize:
    politics: "+20%"

  signals:
    politics:
      groups:
        serpentis:
          corporations: [1000135]  # Serpentis Corporation

      role_filter:
        attacker: true
        victim: false

  rules:
    always_notify:
      - gatecamp_detected

throttle_minutes: 15  # Higher throttle for NPC activity volume

# Optional: Add PARIA-S persona for Serpentis-flavored commentary
commentary:
  enabled: true
  persona: paria-s
  warrant_threshold: 0.3
```

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
  provider: "anthropic"         # "anthropic", "openai", or "gemini"
  model: "claude-sonnet-4-5-20241022"
  timeout_ms: 3000
  max_tokens: 100
  warrant_threshold: 0.3
  cost_limit_daily_usd: 1.0
  style: "radio"                # "conversational" or "radio"
  max_chars: 120                # Soft limit for radio style
  persona: "paria"              # Optional persona override
```

Requires the API key for the chosen provider (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`).

**Multi-provider example (OpenAI):**

```yaml
commentary:
  enabled: true
  provider: "openai"
  model: "gpt-4o-mini"          # Provider-native model name
  cost_limit_daily_usd: 1.0
```

Install the optional dependency: `uv sync --extra openai`

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

Approximate costs per commentary by provider:

| Provider | Default Model | Approx. Cost/Commentary |
|----------|--------------|------------------------|
| Anthropic | Claude Sonnet | ~$0.00019 |
| OpenAI | GPT-4o-mini | ~$0.00011 |
| Gemini | Gemini 2.0 Flash | ~$0.00007 |

- Typical usage: ~$0.01-0.03/day with moderate activity
- Daily limit configurable via `cost_limit_daily_usd`
- Notifications continue without commentary if limit reached

---

## Advanced Configuration Recipes

These recipes demonstrate common notification use cases. For the full Interest Engine v2 specification, see `dev/archive/NOTIFICATION_FILTER_REARCHITECTURE_PROPOSAL.md`.

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

### Recipe: Expensive Hull Losses

Filter to kills where the hull itself is expensive (Marauders, Black Ops, capitals), ignoring cheap ships carrying expensive cargo:

```yaml
interest:
  engine: v2
  preset: trade-hub

  signals:
    hull_value:
      min: 1000000000  # 1B ISK hull minimum
      scale: sigmoid
      pivot: 2000000000

  rules:
    always_ignore:
      - pod_only

throttle_minutes: 1
```

The `hull_value` signal uses ESI adjusted prices for the ship hull only, excluding modules and cargo. A T1 destroyer hauling 2B in cargo scores 0; a Kronos scores high.

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

### Recipe: Location-Gated Home Intel

Only notify for kills in your home systems, with a hard gate so nothing outside gets through:

```yaml
interest:
  engine: v2
  preset: trade-hub

  signals:
    location:
      geographic:
        systems:
          - name: "Sortet"
            classification: "home"
          - name: "Augnais"
            classification: "transit"
          - name: "Mies"
            classification: "transit"

    value:
      min: 50000000  # 50M

  rules:
    require_all:
      - location             # Hard gate: kill must be in a configured system
    always_notify:
      - watchlist_match      # Bypasses gate
    always_ignore:
      - npc_only
```

The `require_all: [location]` gate ensures only kills in Sortet, Augnais, or Mies generate notifications. `always_notify` rules (like `watchlist_match`) bypass gates, so watchlist matches anywhere still notify.

### Recipe: Pod Spike Alerts

Detect when pod kills spike above baseline in a system — catches gank waves and smartbomb camps without alerting on every individual pod kill:

```yaml
interest:
  engine: v2
  preset: trade-hub
  weights:
    activity: 1.0
    ship: 0.6

  signals:
    location:
      geographic:
        systems:
          - { name: Jita, id: 30000142, classification: hunting }
          - { name: Perimeter, id: 30000144, classification: transit }
    ship:
      prefer: ["capsule"]
      prefer_score: 1.0
      default_score: 0.0
    activity:
      spike:
        enabled: true
        pod_only: true     # Only count pod kills for spike detection
        threshold: 3.0     # 3x above baseline
        min_current: 5     # At least 5 pods/hour before alerting
        score: 0.7
      gatecamp:
        enabled: false
      sustained:
        enabled: false

  rules:
    require_all: ["ship", "activity"]  # Both must match

  thresholds:
    notify: 0.30
    priority: 0.70
```

**How it works:** `require_all: [ship, activity]` gates both signals. ShipSignal scores 1.0 for capsules, 0.0 for everything else. ActivitySignal fires only when pod kills are spiking (3x baseline, minimum 5 pods/hour). Non-capsule kills get gated by ship=0. Capsule kills during non-spike periods get gated by activity=0.

**Pair with forced rollup** to batch pod spike kills into summaries instead of flooding the channel with individual messages:

```yaml
rate_limit_strategy:
  force_rollup: true
  rollup_window_minutes: 5
  max_rollup_kills: 50
```

This buffers matched kills and flushes them every 5 minutes as grouped summaries: "Pod spike (12 pods / 5m) — 📍 Jita".

**Activity spike config fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `pod_only` | bool | `false` | Only count pod kills for spike rate calculation |
| `threshold` | float | `2.0` | Multiplier over 24h baseline to declare spike |
| `min_current` | int | `0` | Minimum kills in current hour before declaring spike |
| `score` | float | `0.7` | Score when spike is detected |

### Recipe: Batched Activity Summaries

Use `force_rollup` to buffer individual kill notifications into periodic digests. Useful for high-traffic systems where per-kill alerts would be overwhelming:

```yaml
interest:
  engine: v2
  preset: lowsec
  signals:
    location:
      geographic:
        systems:
          - name: "Tama"
            classification: "hunting"
          - name: "Amamake"
            classification: "hunting"

throttle_minutes: 1

rate_limit_strategy:
  force_rollup: true
  rollup_window_minutes: 10
  max_rollup_kills: 100
```

Every 10 minutes, matched kills are flushed as a single grouped summary — e.g., "Lowsec Activity (8 kills / 10m) — 📍 Tama, Amamake" — instead of 8 separate notifications. This works independently of pod spike detection; any profile can enable `force_rollup` for batched delivery.

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
