# Notification Filter Re-Architecture Proposal (Interest Engine v2)

**Status:** Draft (rev 7)
**Owner:** ARIA Notifications
**Related:** `POLITICAL_ENTITY_TRIGGERS_PROPOSAL.md`, `CONTEXT_AWARE_TOPOLOGY.md`
**Changelog:** See git history for revision details.

---

## Executive Summary

The current notification filter pipeline mixes **binary triggers** (watchlist, gatecamp, high-value threshold, NPC faction kill) with a **max-of-layers** topology interest score. This makes it hard to express profiles where multiple factors should **blend** (trade hubs = locality + value), or where **politics should dominate** (Serpentis intel = entity involvement with minimal location/value relevance).

This proposal introduces **Interest Engine v2**, a unified, per-profile scoring model with:

- **Modular provider architecture** (signals, rules, presets, delivery, scaling as pluggable modules)
- **Weighted signals** (location, value, politics, activity, routes, assets, war, ship class, etc.)
- **Hard rules** for must-notify/must-ignore conditions (template-based default, DSL opt-in)
- **Three-tier UX** (simple presets + sliders → intermediate weights + rules → advanced full config)
- **Explainability + validation** (explain and simulate/replay tooling)
- **Two-stage scoring** (prefetch vs post-fetch) with auto-derived prefetch behavior
- **Feature-flagged rollout** for safe, incremental migration
- **12 configuration recipes** for common use cases
- **User-defined presets** and **custom delivery destinations**

It intentionally **absorbs** `political_entity_kill` into a generalized **political signal** rather than adding another trigger type, while still allowing trigger-style overrides for backward compatibility.

---

## Design Principles

These principles guide trade-offs throughout the design:

1. **Safety over API efficiency**: When uncertain, fetch more rather than miss notifications. ESI rate limits are soft constraints; missed intel is a hard failure.

2. **Simple by default, powerful when needed**: The simple tier (preset + sliders) should cover 80% of use cases. Advanced configuration is an escape hatch, not the default path.

3. **Explicit over implicit**: Scoring semantics, rule precedence, and prefetch behavior are deterministically defined. No "it depends" answers.

4. **Backward compatible**: Existing profiles continue working. Migration is opt-in with tooling support.

5. **Observable**: Every decision point emits metrics. Operators can diagnose issues without reading code.

6. **Reversible**: Feature flags allow instant rollback. No big-bang cutovers.

7. **Modular by design**: Core engine defines extension points; advanced features are pluggable modules loaded on demand.

---

## Modular Framework

Interest Engine v2 uses a **provider-based architecture** where the core engine is minimal and stable, while domain-specific logic lives in pluggable modules. This enables:

- **Simple defaults**: Out-of-box experience requires no configuration
- **Progressive complexity**: Advanced features are opt-in, not default
- **Independent evolution**: Modules can be added/updated without core changes
- **Reduced testing surface**: Core engine tests are stable; module tests are isolated
- **Community extensibility**: Users can contribute modules without touching core

### Extension Points

| Extension Point | Purpose | Built-in Providers | Custom/Opt-In Providers |
|-----------------|---------|-------------------|------------------------|
| **Signals** | Score computation per category | 9 category providers | Custom signal plugins |
| **Rules** | Custom rule evaluation | Template-based rules | Expression DSL |
| **Presets** | Weight/signal defaults | 6 built-in presets | User-defined presets |
| **Scaling** | Value normalization curves | Sigmoid, linear, log, step, inverse | Custom scaling functions |
| **Delivery** | Notification output | Discord, webhook, log | Slack, email, custom |

**Built-in vs Custom clarification:**
- **Built-in providers**: Always available, no feature flag required
- **Custom/Opt-in providers**: Require feature flags (e.g., `features.rule_dsl: true`)

**Note on Aggregation**: Score blending mode (`weighted`/`linear`/`max`) is a configuration option, not a pluggable provider. See [Weighted Aggregation](#2-weighted-aggregation) for mode selection.

### Provider Protocol Pattern

All providers implement: `name` property, `validate(config) -> list[ValidationError]`, plus domain-specific methods (`score()`, `send()`, etc.). Providers are lazy-loaded when referenced.

### Feature Flag Governance

Opt-in features are gated behind feature flags in `userdata/config.json`:

```json
{
  "notifications": {
    "features": {
      "rule_dsl": false,
      "custom_signals": false,
      "custom_presets": true,
      "custom_scaling": false,
      "delivery_webhook": true,
      "delivery_slack": false,
      "delivery_email": false
    }
  }
}
```

**Feature flag categories:**

| Flag | Controls | Default |
|------|----------|---------|
| `rule_dsl` | Expression DSL for custom rules | false |
| `custom_signals` | User-defined signal plugins | false |
| `custom_presets` | User-defined preset files | true |
| `custom_scaling` | User-defined scaling functions | false |
| `delivery_webhook` | Generic webhook provider (built-in, but gated) | true |
| `delivery_slack` | Slack provider | false |
| `delivery_email` | Email provider | false |

**Note:** Built-in scaling functions (sigmoid, linear, log, step, inverse) are **always available**—`custom_scaling` only gates user-defined Python scaling classes.

**Default strategy**: Most opt-in features default to `false` except:
- `custom_presets`: Low risk, high value — enabled by default
- `delivery_webhook`: Generic webhooks are common — enabled by default

---

## Review of Current Implementation (Key Gaps)

1. **Max-of-layers blocks multi-factor relevance**
   - `InterestCalculator` uses `max(layer_scores)` (not weighted composition). A kill that is "moderately local AND moderately valuable" cannot out-rank a single strong signal. This conflicts with trade-hub use cases. (`src/aria_esi/services/redisq/interest/calculator.py`)

2. **Binary triggers are siloed from interest scoring**
   - Triggers (watchlist, gatecamp, high-value) decide notification eligibility independently from interest. There is no consistent weighting or explainability across them. (`src/aria_esi/services/redisq/notifications/triggers.py`)

3. **Ignore-topology only applies after fetch**
   - `npc_faction_kill.ignore_topology` bypasses profile topology during evaluation, but the **global poller topology pre-filter can still suppress ESI fetch**, preventing the notification entirely. (`src/aria_esi/services/redisq/poller.py`, `src/aria_esi/services/redisq/topology.py`)

4. **No per-profile political/entity scope**
   - Political/entity filtering is global via watchlist. There is no per-profile entity group with role weighting (attacker/victim) or political relevance. (`src/aria_esi/services/redisq/entity_filter.py`, `.../notifications/config.py`)

5. **No graded value signal**
   - Value is only a hard threshold trigger; it cannot be weighted or scaled. (`src/aria_esi/services/redisq/notifications/config.py`)

---

## Goals

- Provide **per-profile interest weighting** for who/where/what/how-much.
- Enable **political intel** channels without over-dependence on topology/value.
- Preserve **API efficiency** with a prefetch gate that aligns with profile intent.
- Improve UX with **presets, sliders, and explainable scoring**.
- Keep the schema **simple by default** with progressive disclosure: simple tier (preset + sliders) → intermediate tier (weights + rules) → advanced tier (full signals).
- Add a **validation loop** (simulate/replay/conflict warnings) to prevent surprises.
- Avoid breaking existing templates; offer migration paths.
- Enable **safe rollout** via feature flags with instant rollback capability.
- Support **extensibility** via modular providers (signals, rules, presets, delivery, scaling).
- Allow **user-defined presets** and **custom delivery destinations** without core changes.

## Non-Goals

- Replace the global watchlist system (see **Watchlist Scope Clarification** below).
- Auto-discover political ties (manual IDs/labels remain acceptable).
- Build a full UI; focus on schema + CLI ergonomics.
- Optimize for minimal ESI fetches at the cost of missed notifications.

### Watchlist Scope Clarification

The **global watchlist** (`userdata/watchlists/*.yaml`) and **profile-local politics groups** serve different purposes and coexist:

| Scope | Data Location | Used By | Purpose |
|-------|---------------|---------|---------|
| **Global watchlist** | `userdata/watchlists/*.yaml` | `watchlist_match` rule | Cross-profile entity tracking (e.g., war targets, known hostiles) |
| **Profile groups** | `signals.politics.groups` in profile | Politics signal scoring | Profile-specific political interest (e.g., Serpentis intel channel) |

**How `watchlist_match` works:**
- The built-in `watchlist_match` rule queries the **global watchlist** (not profile groups).
- **Victim-only matching**: `watchlist_match` checks if the **victim** is on the watchlist. This is prefetch-capable (victim corp/alliance visible in RedisQ).
- Entities are added to the global watchlist via `aria-esi watchlist add <entity>`.
- This rule is binary (match/no-match) and typically used in `always_notify`.

**Why victim-only?** Attacker data requires ESI fetch. A rule matching "any role" would be post-fetch-only, defeating prefetch optimization. For attacker-role matching, use `signals.politics.groups` with watchlist entities (weighted scoring) or set `prefetch.mode: conservative`.

**Migration behavior (`--preserve-triggers`):**
- v1 `watchlist_activity` trigger is mapped to: `always_notify: [watchlist_match]`
- The global watchlist data is NOT migrated into profile groups.
- Profiles that want **weighted** watchlist behavior (not must-notify) should manually copy entities to `signals.politics.groups`.

**Why this separation?**
- Global watchlist = "always tell me about these entities" (operational alert)
- Profile groups = "weight these entities in my interest calculation" (intel tuning)
- A corporation might be both on the global watchlist (always-notify) AND in a profile group (weighted higher in that specific profile).

**Combining both:**
```yaml
# Profile uses global watchlist for always_notify, plus local group for weighted scoring
interest:
  preset: political
  rules:
    always_notify:
      - watchlist_match        # Uses global watchlist
  signals:
    politics:
      groups:
        my-frenemies:          # Profile-local group
          corporations: [98612345]
          alliances: [99001234]
```

---

## Proposed Model: Interest Engine v2

### 0) Three-Tier Configuration (Simple → Intermediate → Advanced)

Configuration complexity is progressive. Most users stay in Simple tier. Intermediate provides weight control without signal complexity. Advanced is the full escape hatch.

#### Simple Tier (Default)

For 80% of users. Pick a preset, optionally adjust category emphasis with sliders.

```yaml
interest:
  preset: trade-hub
  customize:
    location: +20%
    value: -10%
  thresholds:
    notify: 0.6
```

**What you get:** Preset defaults for weights AND signals. Sliders adjust emphasis. No configuration of individual signals required.

#### Intermediate Tier

For users who need weight control and rules, but don't want to configure individual signals.

```yaml
interest:
  preset: trade-hub           # Still uses preset's signal defaults
  weights:                    # Override preset weights explicitly
    location: 0.8
    value: 0.7
    politics: 0.3
  rules:                      # Add hard rules
    always_notify:
      - corp_member_victim
      - high_value
  thresholds:
    notify: 0.5
    priority: 0.8
```

**What you get:** Full control over category weights and rules. Signals are still auto-configured from the preset. No need to understand signal internals.

**When to use:** You want to emphasize/de-emphasize categories beyond what sliders allow, or you need `always_notify`/`always_ignore` rules.

#### Advanced Tier (Escape Hatch)

For power users who need per-signal configuration, custom rules, or prefetch control.

```yaml
interest:
  mode: weighted
  weights: { ... }
  signals: { ... }          # Full signal configuration
  rules: { ... }
  prefetch: { ... }         # Optional prefetch override
```

**What you get:** Complete control over everything. Required when preset signal defaults don't fit your use case.

**When to use:** You need to configure specific signals (e.g., custom value pivot, time windows, ship class preferences) or define custom rules with complex conditions.

#### Tier Detection Rules

The system auto-detects which tier a profile uses:

| Condition | Tier | Behavior |
|-----------|------|----------|
| Has `preset`, optional `customize`/`thresholds`/`rules.always_*`, NO `weights`, `signals`, or `rules.custom`/`rules.require_*` | Simple | Weights AND signals from preset |
| Has `weights` but no `signals` block; may have `rules.require_*` | Intermediate | Weights explicit, signals from preset |
| Has `signals` block (or `rules.custom`) | Advanced | Full explicit configuration |

**Simple tier allows:**
- `preset` (required)
- `customize` (optional slider adjustments)
- `thresholds` (optional tier thresholds)
- `rules.always_notify` (optional, built-in rule IDs only)
- `rules.always_ignore` (optional, built-in rule IDs only)

**Simple tier does NOT allow:**
- `weights` (use `customize` percentages instead)
- `signals` (use preset defaults)
- `prefetch` (auto-derived)
- `rules.custom` (custom rule definitions require Advanced tier)
- `rules.require_any` / `rules.require_all` (category gates require Intermediate+ tier)

**Simple tier rule validation:**
- `always_notify`/`always_ignore` must reference only built-in rule IDs (see Built-in Rules table)
- Referencing a custom rule ID in Simple tier fails validation: "Custom rule '{id}' requires Advanced tier; use built-in rules or upgrade to Advanced tier"
- Using `rules.require_any`/`rules.require_all` fails validation: "Category gates require Intermediate tier or higher"

**Validation rules:**
- If `customize` is present and `weights` are absent, weights are derived from the preset plus adjustments.
- Weight adjustments are **multiplicative**, then normalized (see UX Strategy).
- `prefetch` is **auto-derived** by default and only exposed in advanced mode.
- **Missing preset/weights**: If neither `preset` nor explicit `weights` are specified, validation fails with: "Either preset or explicit weights required."
- **Intermediate tier requires preset**: If `weights` are specified without `signals`, a `preset` must be provided for signal defaults. Otherwise validation fails with: "Explicit weights without signals block requires a preset for signal defaults."

### 1) Unified Signal Registry

Each signal returns a normalized score `0..1` plus reasoning. Signals are grouped by **category** for UX.

**Canonical Category Taxonomy (9 categories):**

| Category | Signals | Prefetch-Capable |
|----------|---------|------------------|
| **location** | geographic (topology), distance decay, security band | ✓ (system_id) |
| **value** | total ISK (sigmoid-scaled), ship class value, loot ratio | ✓ (zkb.totalValue) |
| **politics** | corp/alliance/faction involvement, role weighting | Partial (victim only) |
| **activity** | gatecamp, spike detection, repeat attacker patterns | ✗ |
| **time** | time-of-day windows, quiet hours | ✓ (timestamp) |
| **routes** | route membership, transit system detection | ✗ |
| **assets** | corp structures, offices, POCOs | ✗ |
| **war** | war engagement, war targets, standings buckets | ✗ |
| **ship** | freighter/industrial focus, capital involvement, pod kill | ✓ (victim ship_type_id) |

**Note:** This 9-category taxonomy is canonical. Weights, presets, and provider implementations all use these exact category names. Existing layers (geographic, entity, route, assets, patterns) become signals. New signals add value/ship/war/politics.

#### Signal Providers

**Built-in** (always available):

| Provider | Category | Prefetch | Description |
|----------|----------|----------|-------------|
| `GeographicSignal` | location | ✓ | Topology-based scoring |
| `SecuritySignal` | location | ✓ | Security band matching |
| `ValueSignal` | value | ✓ | ISK-based scoring with scaling |
| `PoliticsSignal` | politics | Partial | Entity group matching |
| `ActivitySignal` | activity | ✗ | Gatecamp/spike detection |
| `TimeSignal` | time | ✓ | Time window matching |
| `RouteSignal` | routes | ✗ | Route membership |
| `AssetSignal` | assets | ✗ | Structure proximity |
| `WarSignal` | war | ✗ | War target detection |
| `ShipSignal` | ship | ✓ | Ship class/group matching |

**Custom signals** require `features.custom_signals: true`. Define in `userdata/signals/*.yaml` with category, prefetch capability, and Python scoring class.

### 1a) Category Scoring Semantics

To avoid divergent implementations, category composition is explicitly defined:

- **Signal aggregation (within category)**: each signal returns `score ∈ [0..1]` and an optional `signal_weight` (default `1.0`; if not configurable, treat all signals as `1.0`).
  ```
  category_score = sum(signal_weight * score) / sum(signal_weight)
  ```
  Only **configured signals** are included. If a category has **no configured signals**, `category_score = null`.

- **Weight validation constraints**:
  - All weights (category and signal) must be **non-negative** (`>= 0.0`). Negative weights fail validation with: "Weight must be non-negative: {field} = {value}"
  - Weights must be **finite** (not NaN, not Infinity). Non-finite weights fail validation with: "Weight must be finite: {field} = {value}"
  - If `sum(signal_weight) = 0` for a category with configured signals, treat as `category_score = null` (category is effectively disabled). Emit warning: "Category '{name}' has all-zero signal weights; treating as unconfigured."
  - If `sum(category_weight) = 0` across all configured categories, validation fails with: "All category weights are zero; no notifications will match."

- **Penalties**: apply multiplicative reduction **before** match determination:
  ```
  penalty_factor = clamp(1 - sum(penalties), 0.0, 1.0)  # Clamped to valid range
  penalized_score = raw_score * penalty_factor
  category_score = penalized_score  # This is the final category score
  ```
  Penalties reduce both the score AND affect whether the category matches.

  **Penalty validation:**
  - Individual penalties must be in range `[0.0, 1.0]`. Values outside this range fail validation: "Penalty '{name}' must be between 0.0 and 1.0, got {value}"
  - `sum(penalties) > 1.0` is allowed but produces a warning: "Total penalties exceed 1.0 ({sum}); category score will be 0"
  - If `sum(penalties) >= 1.0`, `penalty_factor = 0.0` and the category effectively contributes nothing (score = 0, match = false)

  **Why allow sum > 1.0?** Multiple independent penalties (e.g., known-alt + scout-character) may stack. Rather than requiring manual coordination, we clamp the result and warn. This is safer than silently ignoring excess penalties.

- **Match semantics (per signal/category)**:
  - Each signal may return `match: true|false`. If omitted, `match = (penalized_score >= match_threshold)`.
  - **Critical:** Match is evaluated against the **penalized** score, not the raw score. A heavily-penalized category will NOT satisfy `require_any`/`require_all` gates.
  - `match_threshold` can be set per signal or per category (category value is the default for its signals).
  - Default `match_threshold = 0.3` (chosen to represent "meaningful but not dominant" contribution).
  - If `require_any` / `require_all` is used and a configured signal has neither `match` nor a resolvable `match_threshold` (e.g., explicitly `null`), validation should warn and treat that signal as `match = false`.

- **Within-category gates**: `require_any` / `require_all` evaluate against configured signal **match** (derived from penalized scores).
  - If the gate fails, `category_score = 0` and `category_match = false`.
  - If gates pass and the category has configured signals, `category_match = true`.
  - If a category is referenced by `rules.require_all` / `rules.require_any` but has no configured signals, validation should warn and `category_match = false`.

**Example (penalty affecting match):**
```
politics raw_score = 0.8
known-scout-alt penalty = 0.7
penalized_score = 0.8 * (1 - 0.7) = 0.24
match_threshold = 0.3
category_match = (0.24 >= 0.3) = false  # Penalty caused match failure
```

- **Empty categories are excluded** from top-level weighting to avoid score dilution.

### Category Disable Semantics

When a category weight is set to **zero**, the category is considered **disabled**. This affects multiple aspects of scoring:

| Aspect | Disabled Behavior | Rationale |
|--------|-------------------|-----------|
| **Score contribution** | Excluded from RMS/linear aggregation | Zero weight = no influence on interest score |
| **Match evaluation** | `category_match = false` always | Cannot satisfy gates if disabled |
| **require_any gates** | Excluded from OR evaluation | Disabled categories cannot trigger require_any |
| **require_all gates** | **Validation error if referenced** | Cannot require a disabled category |
| **Signal computation** | Signals are still computed but not used | Useful for `explain` debugging |

**Why strict gate exclusion?** If a category with weight=0 could still satisfy `require_any`, users would get unexpected notifications from categories they thought they disabled. Similarly, `require_all` with a disabled category is a configuration error (impossible to satisfy).

**Validation rules:**
- `require_all` referencing a zero-weight category: ERROR "Category '{name}' in require_all has weight 0 (disabled)"
- `require_any` containing only zero-weight categories: ERROR "All categories in require_any are disabled"
- Zero-weight category in `require_any` alongside non-zero categories: WARNING "Category '{name}' in require_any is disabled (weight 0) and will never match"

**Example:**
```yaml
interest:
  preset: trade-hub
  weights:
    location: 0.7
    politics: 0      # Disabled
    value: 0.5
  rules:
    require_any:
      - location     # Can match
      - politics     # WARNING: disabled, will never match
```

This differs from **unconfigured** categories (no signals defined), which are simply excluded from everything without warning.

### 2) Weighted Aggregation

Replace `max(layer_scores)` with a **weighted blend** (default), with optional alternatives for legacy mode.

**Default formula (RMS)**:
Uses **Root Mean Square (RMS)** weighting to prevent strong signals (e.g., Titan kill) from being diluted by neutral signals (e.g., Time/Politics = 0).

```
interest = clamp(
  sqrt( sum(weight_c * category_score_c^2) / sum(weight_c) ),
  0.0,
  1.0
)
```
`c` ranges over **configured categories** where `category_score` is not null.

**Why RMS over Linear?**
Linear averaging (`sum(w*s)/sum(w)`) causes signal dilution: a 1.0 location score with 0.0 politics yields 0.5 interest, even when politics is irrelevant. RMS preserves strong signal influence while still blending. Example:

| Scenario | Location | Politics | Linear | RMS |
|----------|----------|----------|--------|-----|
| Local kill, no political tie | 1.0 | 0.0 | 0.50 | 0.71 |
| Political kill, far away | 0.0 | 1.0 | 0.50 | 0.71 |
| Both strong | 1.0 | 1.0 | 1.00 | 1.00 |
| Both moderate | 0.6 | 0.6 | 0.60 | 0.60 |

RMS rewards "at least one strong signal" without ignoring secondary factors.

**Options**:
- `mode: weighted` (default, uses RMS logic)
- `mode: linear` (traditional weighted average, simpler but prone to signal dilution)
- `mode: max` (legacy-compatible)

**Prefetch alignment**
- Prefetch scoring is only defined for `mode: weighted` or `linear`.
- If `mode: max` is selected, `prefetch.mode` must be `bypass` (validation error otherwise).

### 3) Hard Rules (Overrides & Gates)

Rules allow must-notify and must-ignore conditions that bypass the blend.

- **Always Notify** (e.g., corp member loss, specific political groups)
- **Always Ignore** (e.g., exclude NPC-only kills, exclude pods)
- **Require All** (`rules.require_all`): all listed categories must match (e.g., politics AND topology)
- **Require Any** (`rules.require_any`): at least one listed category must match (e.g., politics OR topology)

**Rule precedence (deterministic)**
1. `always_ignore` wins. If it matches, drop the notification (no thresholds or rate limits apply).
2. `always_notify` applies only if `always_ignore` did not match; it bypasses **all gates and thresholds** (but not rate limits unless explicitly configured).
3. `rules.require_all` / `rules.require_any` gates apply.
4. Interest scoring + thresholds apply.
5. `rate_limit` applies to all notifications by default, including `always_notify`.

**Conflict handling**
- If a kill matches both `always_ignore` and `always_notify`, **`always_ignore` wins** (per Design Principle #1: safety over efficiency).
- Optional configuration can override this (see schema).

**Prefetch safety**
- Prefetch must not block `always_notify` candidates. If any `always_notify` rule relies on post-fetch-only data, `prefetch.mode: strict` is invalid (coerce to conservative with warning).

### 3a) Rule System (Modular Architecture)

The rule system uses a **modular architecture** with two tiers:

1. **Template-based rules** (default) — Predefined rule templates with parameters
2. **Expression DSL** (opt-in) — Full expression language for edge cases

**Design rationale:** Templates cover ~90% of use cases with simpler validation, clearer errors, and known prefetch behavior. The DSL is an escape hatch for edge cases, not the primary interface.

#### Built-in Rules

Rules referenced in `rules.always_notify` and `rules.always_ignore` include these built-in identifiers:

| Rule ID | Evaluation | Prefetch-Capable | Description |
|---------|------------|------------------|-------------|
| `npc_only` | No player attackers | ✓ (attackers in RedisQ) | Exclude NPC-only deaths |
| `pod_only` | Victim ship is Capsule | ✓ (victim ship_type_id) | Exclude/include pod kills |
| `corp_member_victim` | Victim corp matches profile | Partial (victim corp_id) | Corp member losses |
| `alliance_member_victim` | Victim alliance matches | Partial (victim alliance_id) | Alliance member losses |
| `war_target_activity` | War target involved | ✗ (requires ESI war data) | War target kills/losses |
| `watchlist_match` | Victim is on global watchlist | ✓ (victim corp/alliance) | Watchlist victim detection |
| `high_value` | `zkb.totalValue >= value.min` | ✓ (zkb.totalValue) | High-value kills (requires `signals.value.min`) |
| `gatecamp_detected` | Gatecamp pattern detected | ✗ (requires activity analysis) | Gatecamp activity |
| `structure_kill` | Victim is a structure | ✓ (victim ship_type_id) | Structure destruction |

#### Template-Based Custom Rules (Default)

Custom rules use predefined templates with parameters. Each template has known prefetch capability—no derivation required.

**Template Registry:**

| Template | Parameters | Description | Prefetch |
|----------|------------|-------------|----------|
| `group_role` | `group`, `role` | Entity from group in specified role | victim only |
| `category_match` | `category` | Category passes match_threshold | varies by category |
| `category_score` | `category`, `min`, `max`? | Category score in range | varies by category |
| `value_above` | `min` | Kill value ≥ amount | ✓ |
| `value_below` | `max` | Kill value < amount | ✓ |
| `ship_class` | `classes[]` | Victim ship class in list | ✓ |
| `ship_group` | `groups[]` | Victim ship group ID in list | ✓ |
| `security_band` | `bands[]` | System security (high/low/null/wh) | ✓ |
| `system_match` | `systems[]` | Kill in listed systems | ✓ |
| `attacker_count` | `min`?, `max`? | Number of attackers in range | ✗ |
| `solo_kill` | — | Exactly one attacker | ✗ |

**Valid roles** for `group_role`: `victim` (prefetch-capable), `attacker`, `final_blow`, `any` (post-fetch only).

**Example:**

*(Note: These rule syntax examples show the `interest.rules:` block in isolation for clarity. In a complete profile, they would be nested under `interest:`.)*

```yaml
# Inside interest: block
rules:
  custom:
    serpentis_loss:
      template: group_role
      params:
        group: serpentis-aligned
        role: victim
      description: "Serpentis-aligned entity died"
  always_notify:
    - serpentis_loss
    - corp_member_victim
```

#### Simple Combinators

For combining templates, use **one level** of `all:` (AND) or `any:` (OR) without nesting:

```yaml
# Inside interest: block
rules:
  custom:
    # AND: all conditions must match
    valuable_serpentis_loss:
      all:
        - template: group_role
          params: { group: serpentis-aligned, role: victim }
        - template: value_above
          params: { min: 100_000_000 }
      description: "Serpentis loss worth 100M+"

    # OR: any condition matches
    political_activity:
      any:
        - template: group_role
          params: { group: hostiles, role: any }
        - template: group_role
          params: { group: friendlies, role: victim }
      description: "Hostiles active or friendly died"

    # Single template (no combinator needed)
    cheap_pod:
      all:
        - template: ship_class
          params: { classes: [capsule] }
        - template: value_below
          params: { max: 100_000_000 }
      description: "Pod worth less than 100M"

  always_ignore:
    - cheap_pod
```

**Combinator constraints:**
- No nesting (`all:` inside `any:` is invalid)
- No `not:` operator in template mode
- Each element must be a template reference with `template:` and `params:`

**Prefetch capability for combinators:**
- `all:` → prefetch-capable only if ALL elements are prefetch-capable
- `any:` → prefetch-capable if ANY element is prefetch-capable

#### Expression DSL (Opt-In Feature)

For edge cases not covered by templates, an expression DSL is available behind a feature flag:

```yaml
# userdata/config.json
{
  "notifications": {
    "features": {
      "rule_dsl": true  # Default: false
    }
  }
}
```

When enabled, the `condition:` syntax becomes available:

```yaml
# Inside interest: block
rules:
  custom:
    complex_political:
      condition:
        and:
          - group.serpentis-aligned.victim: true
          - category.value.score >= 0.5
      prefetch_capable: false  # Optional; derived if omitted
      description: "Political involvement on valuable kill"
```

**DSL condition syntax:**

| Condition Type | Syntax | Description | Prefetch |
|----------------|--------|-------------|----------|
| Category match | `category.{name}.match: true` | Category passes match_threshold | Depends on category |
| Category score | `category.{name}.score >= {value}` | Category score comparison | Depends on category |
| Group role match | `group.{group_name}.{role}: true` | Entity from group in role | Partial (victim only) |
| Signal value | `signal.{category}.{signal}.{field}` | Specific signal field | Depends on signal |
| Logical AND | `and: [cond1, cond2, ...]` | All conditions must match | Lowest of children |
| Logical OR | `or: [cond1, cond2, ...]` | Any condition matches | Highest of children |
| Logical NOT | `not: condition` | Negate condition | Same as child |

**Group role values:**
- `victim`: Entity died (prefetch-capable)
- `attacker`: Entity participated in kill (NOT prefetch-capable)
- `final_blow`: Entity got final blow (NOT prefetch-capable)
- `any`: Entity in any role (NOT prefetch-capable)

**prefetch_capable derivation (DSL mode):**
- If `prefetch_capable` is explicitly set, use that value
- Otherwise, derive from condition AST:
  - `group.*.victim` → true
  - `group.*.attacker`, `group.*.final_blow`, `group.*.any` → false
  - `category.*` → true only if ALL signals in that category are prefetch-capable
  - `and: [...]` → true only if ALL children are prefetch-capable
  - `or: [...]` → true only if ANY child is prefetch-capable
  - `not: ...` → same as child
- If derivation fails or is ambiguous, default to `false` (conservative)

Without the feature flag, `condition:` blocks fail validation with a suggestion to use templates instead.

Rule providers (builtin, template, DSL) are selected based on config shape. DSL module is lazy-loaded only when `features.rule_dsl: true`.

### 4) Signal Composition and Negative Influence

Clarify **OR/AND** within categories and **AND** across categories:

- **Within a category**: `require_any` (OR) and `require_all` (AND) control group matching.
- **Across categories**: `rules.require_all` enforces **AND** across categories (e.g., politics AND value). `rules.require_any` enforces **OR** across categories (e.g., politics OR value).
- **Negative influence**: `penalties` reduce category score (clamped to `0..1`), for cases like known scout alts.

### 5) Two-Stage Scoring (Prefetch + Post-Fetch)

To maintain performance, scoring is split:

- **Prefetch score** uses RedisQ-visible signals (system ID, zkb value, victim corp/alliance, victim ship type). Note: `zkb` (value) and `system_id` are confirmed reliable for this stage.
- **Post-fetch score** uses full ESI details.

**Default: auto-derived prefetch**
- Only valid when `interest.mode: weighted` or `linear`; if `mode` is `max`, validation errors unless `prefetch.mode: bypass`.
- Each signal declares **prefetch capability** based on RedisQ-visible fields (e.g., `system_id`, `zkb.value`, victim corp/alliance, victim ship type).
- If **no prefetch-capable categories** are configured -> **auto-conservative** (warn; strict would never fetch).
- If **any configured category includes post-fetch-only signals (even mixed)** -> **auto-conservative** to avoid under-fetch from unknown in-category signals.
- If `rules.require_all` or `rules.require_any` include categories with post-fetch-only signals -> **auto-conservative**
- If any `always_notify` rule depends on post-fetch-only data -> **auto-conservative** (with warning)
- Otherwise -> **auto-strict**

**Advanced override (optional)**:
- `prefetch.mode: conservative` (fetch if *any* configured signal might match)
- `prefetch.mode: strict` (fetch only if known signals already pass)
- `prefetch.mode: bypass` (fetch all; explicit warning)

**Override vs auto-coercion semantics:**

When `prefetch.mode` is **explicitly set** by the user:
- `strict`: Respected if valid. If invalid, **coerced to conservative with warning**. Invalid conditions:
  - No prefetch-capable categories configured
  - `always_notify` rule depends on post-fetch-only data
  - `rules.require_any` or `rules.require_all` references categories with post-fetch-only signals

  The warning includes: "Explicit strict mode coerced to conservative: {reason}. Set mode: conservative to suppress this warning."
- `conservative`: Always respected (no coercion needed).
- `bypass`: Always respected. Warning emitted about API usage, but not coerced.

When `prefetch.mode` is **auto** (default):
- System derives mode based on configured signals (see auto-derivation rules above).
- No warnings for auto-derived conservative mode.

**Design principle alignment:** Explicit configuration is respected when safe. When explicit `strict` would violate Design Principle #1 (safety over efficiency), the system coerces to conservative rather than silently missing notifications. The warning makes the coercion visible.

This resolves the current ignore-topology mismatch.

### Prefetch Semantics (Unambiguous)

Prefetch uses **only prefetch-capable signals** (RedisQ-visible fields). Signals that require post-fetch data are **unknown**, not zero.
Prefetch aggregation is only supported for `interest.mode: weighted` or `linear` (see Prefetch alignment).

**Aggregation asymmetry and strict mode safety:** Prefetch bounds use **linear averaging** for simplicity, while post-fetch scoring uses **RMS**. This asymmetry can cause a kill scoring below threshold at prefetch (linear) to score above threshold at post-fetch (RMS) when signals are unevenly distributed.

To preserve Design Principle #1 (safety over API efficiency), `prefetch.mode: strict` applies a **dynamic RMS safety margin** based on the number of configured categories:

```
adjusted_threshold = prefetch_threshold * RMS_SAFETY_FACTOR(n)
```

Where `RMS_SAFETY_FACTOR(n) = 1 / sqrt(n)` and `n` is the count of **configured categories** (categories with non-null, non-zero weight).

| Categories (n) | RMS_SAFETY_FACTOR | Rationale |
|----------------|-------------------|-----------|
| 1 | 1.00 | No asymmetry with single category |
| 2 | 0.71 | 1/√2 ≈ 0.707 |
| 3 | 0.58 | 1/√3 ≈ 0.577 |
| 4 | 0.50 | 1/√4 = 0.5 |
| 5+ | 0.45 | Floor at 1/√5 ≈ 0.447 to prevent excessive over-fetch |

**Why dynamic scaling?** The worst-case linear/RMS divergence occurs when one category scores 1.0 and all others score 0.0. In this case:
- Linear: `1.0 / n`
- RMS: `sqrt(1.0 / n) = 1 / sqrt(n)`

The RMS score is always higher by a factor of `sqrt(n)`. Without scaling the safety factor, strict mode with 4+ categories can still drop kills that would pass post-fetch RMS, violating Design Principle #1.

**Example (2 configured categories):**
- Post-fetch threshold: 0.6
- Configured categories: 2 → RMS_SAFETY_FACTOR = 0.71
- Prefetch threshold with strict: 0.6 × 0.71 = 0.426
- A kill scoring 0.45 linear at prefetch will be fetched (0.45 ≥ 0.426)
- At post-fetch with RMS, if the strong signal scores 0.9, interest ≈ 0.64 → passes 0.6 threshold

**Example (4 configured categories):**
- Post-fetch threshold: 0.6
- Configured categories: 4 → RMS_SAFETY_FACTOR = 0.50
- Prefetch threshold with strict: 0.6 × 0.50 = 0.30
- More aggressive prefetch to account for greater potential RMS uplift

**Conservative mode** uses `unknown_assumption=1.0` to inflate `upper_bound`, ensuring over-fetch rather than missed notifications. The RMS safety margin is NOT applied to conservative mode (already over-fetches by design).

**Weight source**
- `w_i` in prefetch math refers to **category weights** (`interest.weights.*`), not per-signal weights.
- A category is considered **prefetch-known only if all configured signals in that category are prefetch-capable**. If a category includes any post-fetch-only signals (even mixed), its prefetch category score is `null` and it is treated as **unknown** for bounds and gating.
- Within a prefetch-known category, compute the category score using **prefetch-capable signals only**; if none are configured or known, that category score is `null`.

**Prefetch score (known-only blend, weighted mode)**:
```
prefetch_score = sum(w_c * s_c) / sum(w_c)   # c over categories with known prefetch scores
```
If no categories have known prefetch scores, `prefetch_score = null`.

**Bounds for unknowns**:
To avoid "optimistic trap" where unknowns force a fetch, `unknown_assumption` controls the placeholder score for missing data. Defaults to 1.0 (per Design Principle #1: safety over efficiency).
```
upper_bound = sum(w_known * s_known + w_unknown * unknown_assumption) / sum(w_known + w_unknown)
```

**Gating**:

**Threshold resolution (ordered):**
1. Use `prefetch.min_threshold` if explicitly set
2. Otherwise, use `min(prefetch.thresholds.*)` if `prefetch.thresholds` is defined
3. Otherwise, use `min(interest.thresholds.*)` if `interest.thresholds` is defined
4. Otherwise, use system default: `0.3`

**Threshold ordering:** Thresholds must satisfy `digest ≤ notify ≤ priority` (if all three are defined). Validation fails if ordering is violated. Missing tiers are ignored for ordering checks.

**Gating decisions** (evaluated in order):

**Step 1: always_notify rule check (before threshold gating)**
Evaluate all **prefetch-capable** `always_notify` rules against RedisQ-visible data:
- If ANY prefetch-capable `always_notify` rule matches → **fetch unconditionally**, bypassing threshold checks
- This prevents low prefetch_score from blocking must-notify events

**Step 2: Threshold gating** (with RMS safety margin applied to strict mode threshold):
- `strict`: fetch if `prefetch_score >= adjusted_threshold`. If `prefetch_score = null` (no prefetch-capable signals), **coerce to conservative with warning** rather than blocking all fetches.
- `conservative`: fetch if `prefetch_score >= threshold` **OR** `upper_bound >= threshold` **OR** `prefetch_score = null`
- `bypass`: fetch all

**Critical:** `prefetch.mode: strict` with `prefetch_score = null` is a configuration error (indicates no prefetch-capable categories). The system auto-coerces to conservative and emits: "Strict mode requires at least one prefetch-capable category; coercing to conservative."

**Worked example (mixed prefetch/post-fetch categories)**:
```
weights: { location: 0.6, politics: 0.4 }
threshold: 0.5
unknown_assumption: 1.0 (default)

prefetch-capable: location (score = 0.4)
post-fetch-only: politics (unknown at prefetch)

prefetch_score = (0.6 * 0.4) / 0.6 = 0.4
lower_bound   = (0.6 * 0.4) / (0.6 + 0.4) = 0.24
upper_bound   = (0.6 * 0.4 + 0.4 * 1.0) / 1.0 = 0.64

strict:       0.4 < 0.5 -> do not fetch
conservative: upper_bound 0.64 >= 0.5 -> fetch
```

---

## Profile Schema

See **`docs/NOTIFICATION_PROFILE_SCHEMA.md`** for complete field reference.

### Tier Detection

| Tier | Detection Rule |
|------|----------------|
| Simple | Has `preset`, no `weights` or `signals` |
| Intermediate | Has `weights`, no `signals` |
| Advanced | Has `signals` |

### Thresholds

```yaml
thresholds:
  priority: 0.85    # High-importance alerts
  notify: 0.60      # Standard notifications
  digest: 0.40      # Low-priority, batch-eligible
```

Ordering constraint: `digest ≤ notify ≤ priority`. Kills are assigned to the highest tier they qualify for.

### Examples

**Simple:**
```yaml
interest:
  preset: trade-hub
  customize: { location: +20%, value: -10% }
  rules:
    always_notify: [corp_member_victim]
```

**Intermediate:**
```yaml
interest:
  preset: hunter
  weights: { activity: 0.9, routes: 0.7, location: 0.4 }
  rules:
    always_notify: [gatecamp_detected]
    always_ignore: [npc_only]
```

**Advanced:**
```yaml
interest:
  engine: v2
  mode: weighted
  weights: { location: 0.7, value: 0.7, politics: 0.2 }
  signals:
    value: { min: 50_000_000, scale: sigmoid }
    politics:
      groups:
        target: { alliances: [99001234] }
      require_any: [target]
  rules:
    always_notify: [corp_member_victim]
  prefetch:
    mode: auto
```

---

## Default Rate Limits

Rate limits prevent notification flooding. These defaults apply when `rate_limit` is not specified:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_per_hour` | 60 | Maximum notifications per hour per profile |
| `burst` | 5 | Maximum notifications in rapid succession |
| `bypass_for_always_notify` | false | Whether `always_notify` rules skip rate limiting |

**Rationale:** 60/hour (~1/minute) balances awareness with noise. Burst of 5 allows short activity spikes without suppression. `bypass_for_always_notify: false` by default to prevent runaway notifications from misconfigured rules.

---

## Delivery Providers (Modular)

Notification delivery uses a pluggable provider architecture. The core engine scores kills; delivery providers handle output formatting and transport.

### Built-in Providers

All built-in providers ship with the core engine. Some are gated by feature flags (enabled by default for common use cases).

| Provider | Feature Flag | Default | Description |
|----------|--------------|---------|-------------|
| `discord` | — | enabled | Discord webhook with rich embeds |
| `webhook` | `delivery_webhook` | enabled | Generic HTTP POST with JSON payload |
| `log` | — | enabled | Local file logging (for debugging) |

**Note:** The `webhook` provider is built-in (not a custom/community provider), but gated behind a feature flag that's enabled by default. This allows operators to disable generic webhooks in restricted environments.

### Opt-In Providers

| Provider | Feature Flag | Description |
|----------|--------------|-------------|
| `slack` | `delivery_slack` | Slack webhook with Block Kit |
| `email` | `delivery_email` | Email digest (batched) |
| `pushover` | `delivery_pushover` | Mobile push |
| `matrix` | `delivery_matrix` | Matrix protocol |

### Configuration

```yaml
# Simple
delivery:
  webhook: "https://discord.com/api/webhooks/..."

# Tier-based routing
delivery:
  destinations:
    - provider: discord
      webhook: "${DISCORD_PRIORITY_WEBHOOK}"
      tiers: [priority]
      mention: "@here"
    - provider: discord
      webhook: "${DISCORD_GENERAL_WEBHOOK}"
      tiers: [notify]
```

Custom providers can be defined in `userdata/delivery/*.yaml` with `base:` inheritance from built-in providers.

---

## Scaling Function Providers (Modular)

Scaling functions normalize raw values (ISK, distance, time) to scores in `[0, 1]`. Different use cases benefit from different curves.

### Built-in Scaling Functions (Always Available)

All built-in scaling functions are available without feature flags:

| Function | Description | Best For |
|----------|-------------|----------|
| `sigmoid` | S-curve with configurable pivot | Value (differentiates 100M vs 10B) |
| `linear` | Direct proportion | Distance decay |
| `logarithmic` | Log scale | Wide-range values |
| `step` | Discrete thresholds | Tier-based scoring |
| `inverse` | 1/x decay | Proximity scoring |

**Note:** These are all built-in. The `features.scaling_functions` flag gates **custom** scaling functions (user-defined Python classes), not the built-in functions above.

### Configuration

```yaml
# Sigmoid (default)
value:
  min: 50_000_000
  max: 10_000_000_000
  scale: sigmoid
  pivot: 500_000_000    # Where score = 0.5

# Step function
value:
  scale:
    provider: step
    thresholds:
      - { below: 100_000_000, score: 0.3 }
      - { below: 1_000_000_000, score: 0.8 }
      - { default: 1.0 }
```

Custom scaling requires `features.custom_scaling: true`.

### Visual Comparison

```
Score
1.0 ┤                    ╭────── sigmoid
    │                 ╭──╯
0.8 ┤              ╭──╯        ╭── step
    │           ╭──╯       ────╯
0.6 ┤        ╭──╯      ────╯
    │     ╭──╯     ────╯             ╱ linear
0.4 ┤  ╭──╯    ────╯            ╱───╯
    │╭─╯   ────╯           ╱───╯
0.2 ┤│ ────╯          ╱───╯
    ││────╯      ╱───╯
0.0 ┼┴───────────────────────────────────
    0   100M   500M    1B    5B   10B  ISK
```

---

## Default Role Weights

Role weights determine how much an entity's involvement contributes to the politics score based on their role in the kill.

| Role | Default Weight | Rationale |
|------|----------------|-----------|
| `victim` | 1.0 | Primary interest - who died matters most |
| `final_blow` | 0.8 | Credited killer, high tactical relevance |
| `attacker` | 0.6 | Involved but less significant than victim/final blow |
| `solo` | 1.0 | Modifier applied when kill is solo (multiplied with attacker role) |

These defaults can be overridden per-profile in `signals.politics.role_weights`.

### Politics Aggregation (Deterministic Algorithm)

To ensure consistent scoring across implementations, politics aggregation follows this deterministic algorithm:

**Step 1: Identify matching entities and their roles**

For each entity (corporation, alliance, faction) in the kill:
1. Check if entity matches any configured group
2. Record which groups matched and in which role(s)

Entity-to-role mapping:
- **Victim**: Single entity (victim's corp + alliance + faction)
- **Final blow**: Single entity (final_blow attacker's corp + alliance + faction)
- **Attackers**: All attacking entities' corps + alliances + factions (excluding final_blow)

**Step 2: Calculate per-group scores**

For each group with at least one match:
```
group_score = max(
    victim_matches    * role_weights.victim,
    final_blow_match  * role_weights.final_blow * solo_modifier,
    max_attacker_match * role_weights.attacker * solo_modifier
)
```

Where:
- `victim_matches` = 1.0 if victim's corp/alliance/faction matches group, else 0.0
- `final_blow_match` = 1.0 if final_blow's corp/alliance/faction matches group, else 0.0
- `max_attacker_match` = 1.0 if any attacker's corp/alliance/faction matches group, else 0.0
- `solo_modifier` = `role_weights.solo` (default 1.0) if attackers.length == 1, else 1.0

**Why max() instead of sum()?** Multiple attackers from the same group shouldn't inflate the score beyond a single match. The question is "is this group involved?" not "how many members participated?"

**Step 3: Aggregate across groups**

```
politics_score = max(group_scores)   # if require_any or no gates
politics_score = min(group_scores)   # if require_all
```

If `require_any` is specified but empty, use max(). If `require_all` is specified but empty, use max() (no constraint).

**Step 4: Apply penalties**

Penalties are applied AFTER group aggregation:
```
final_politics_score = clamp(politics_score * (1 - sum(penalties)), 0.0, 1.0)
```

**Worked example:**

```yaml
politics:
  groups:
    blue-donut:
      alliances: [1354830081, 99001234]  # Goons + TEST
    hostiles:
      corporations: [98612345]
  role_weights:
    victim: 1.0
    final_blow: 0.8
    attacker: 0.6
    solo: 1.0
```

Kill: Goon (1354830081) dies to 3 attackers, one from hostile corp (98612345) gets final blow.

```
blue-donut group:
  victim_match = 1.0 (Goon died)
  final_blow_match = 0.0 (hostile got final blow)
  attacker_match = 0.0 (no blue-donut attackers)
  group_score = max(1.0 * 1.0, 0.0 * 0.8, 0.0 * 0.6) = 1.0

hostiles group:
  victim_match = 0.0
  final_blow_match = 1.0
  attacker_match = 1.0 (at least one hostile attacker)
  solo_modifier = 1.0 (3 attackers, not solo)
  group_score = max(0.0 * 1.0, 1.0 * 0.8 * 1.0, 1.0 * 0.6 * 1.0) = 0.8

politics_score = max(1.0, 0.8) = 1.0  # Goon death dominates
```

---

## Global Entity Groups

Define common political groups once in `userdata/entity-groups.yaml` and reference them from profiles:

```yaml
# userdata/entity-groups.yaml
groups:
  serpentis-aligned:
    factions: [serpentis]
    corporations: [98612345]
    alliances: [99001234]

  goonswarm:
    alliances: [1354830081]
    corporations: []

  hostiles:
    alliances: [99001234, 99005678]
    corporations: [98612345]
```

**Resolution rules**:
- Profiles reference groups by name in `signals.politics.groups`
- Local profile definitions **merge** with global ones (additive IDs, local weights override)
- Unknown group names trigger validation error

**Why separate file?** Keeps `userdata/config.json` focused on runtime settings. Entity groups are reference data that changes infrequently and may be shared across tools.

---

## Examples

### A) Trade Hub Intel (Locality + Value)
```yaml
interest:
  preset: trade-hub
  weights:
    location: 0.8
    value: 0.7
    politics: 0.1
  signals:
    location:
      geographic:
        systems:
          - { name: Jita, classification: hunting }
          - { name: Perimeter, classification: transit }
    value:
      min: 100_000_000
      max: 10_000_000_000
      scale: sigmoid
```
**Behavior:** High-value hauler kills near Jita score high even without political ties.

### B) Serpentis Political Intel (Politics > Location/Value)
```yaml
interest:
  preset: political
  weights:
    politics: 1.0
    location: 0.1
    value: 0.1
  signals:
    politics:
      groups:
        serpentis-aligned:
          factions: [serpentis]
          corporations: [98612345]
          alliances: [99001234]
      role_weights: { attacker: 0.7, victim: 1.0 }
      require_any: [serpentis-aligned]
```
**Behavior:** Political involvement drives notifications even outside local space.

---

## Configuration Recipes

See **`docs/NOTIFICATION_RECIPES.md`** for full copy-paste configurations.

| # | Use Case | Tier | Key Pattern |
|---|----------|------|-------------|
| 1 | Corp member losses | Simple | `always_notify` rule |
| 2 | High-value near home | Simple | `customize` sliders |
| 3 | Gatecamp alerts | Intermediate | Weights + `always_notify` |
| 4 | War target activity | Intermediate | `war` + `politics` weights |
| 5 | Ignore cheap pods | Advanced | Template combinator rule |
| 6 | Freighter focus | Intermediate | `industrial` preset + `ship` weight |
| 7 | Political intel | Advanced | Politics groups + role weights |
| 8 | Quiet hours | Advanced | `time` signal + penalties |
| 9 | Sov defense | Advanced | `assets` + `structure_kill` rule |
| 10 | Wormhole chain | Advanced | Low threshold + chain tracking |
| 11 | Solo PvP hunting | Advanced | `solo_kill` template |
| 12 | Trade hub intel | Advanced | Full RMS blend |

**Quick examples:**

```yaml
# Simple: always notify on corp losses
interest:
  preset: industrial
  rules:
    always_notify: [corp_member_victim]

# Intermediate: gatecamp alerts with weights
interest:
  preset: hunter
  weights: { activity: 0.9, routes: 0.7, location: 0.4 }
  rules:
    always_notify: [gatecamp_detected]
    always_ignore: [npc_only]
```

---

## UX Strategy

### Progressive Disclosure

The three-tier configuration model supports users at different expertise levels:

| Tier | User Profile | Configuration Surface |
|------|-------------|----------------------|
| **Simple** | New users, most operators | Preset selection + slider adjustments |
| **Intermediate** | Experienced users | Preset + explicit weights + rules |
| **Advanced** | Power users, edge cases | Full weights + signals + rules + prefetch |

Users naturally progress through tiers as needs grow. Each tier is self-contained—no need to understand later tiers to use earlier ones.

### Presets

Presets define complete weight baselines **and default signal configurations**. All nine categories are specified to ensure predictable slider behavior. Each preset also enables a minimal set of signals per category to ensure the simple path always produces meaningful scores.

| Preset | Use Case |
|--------|----------|
| `trade-hub` | Market system intel |
| `political` | Entity tracking |
| `industrial` | Hauler/mining losses |
| `hunter` | Gatecamp/hotspot alerts |
| `sovereignty` | Nullsec structure defense |
| `wormhole` | Chain security |

**Critical:** A preset **must** enable at least one signal in at least one category with non-zero weight. If a preset's enabled signals produce no configured categories (e.g., all zero weights), validation fails with: "Preset 'X' produces no active categories."

**Preset signal defaults:** Each preset implicitly enables the following signals (users can override in `signals:` block):

| Preset | Enabled Signals |
|--------|-----------------|
| `trade-hub` | location.geographic, location.security, value.*, ship.prefer[freighter,industrial] |
| `political` | politics.groups (with NPC faction defaults), war.* |
| `industrial` | location.geographic, value.*, ship.prefer[freighter,industrial,mining], routes.* |
| `hunter` | location.geographic, activity.gatecamp, activity.spike, time.windows |
| `sovereignty` | location.geographic, politics.groups, assets.*, war.* |
| `wormhole` | location.geographic, activity.*, assets.* |

#### Political Preset Onboarding

The `political` preset requires special handling because it's useless without defined entity groups. To prevent user frustration:

**Default NPC faction groups:** When `preset: political` is used without explicit `politics.groups`, the following default groups are auto-enabled:

```yaml
# Auto-enabled for political preset (can be overridden)
politics:
  groups:
    pirate-factions:
      factions: [serpentis, guristas, blood_raiders, sansha, angel_cartel, mordus_legion]
    empire-factions:
      factions: [caldari, gallente, amarr, minmatar]
    triglavian:
      factions: [triglavian_collective]
```

**Validation behavior:**
- `preset: political` with NO `politics.groups` → uses defaults above, emits INFO: "Using default NPC faction groups. Define custom groups to track specific entities."
- `preset: political` with empty `politics.groups: {}` → validation ERROR: "Political preset requires at least one group. Remove empty groups block to use defaults, or define your groups."
- `preset: political` with defined groups → uses user's groups, no defaults added

**Rationale:** Users selecting "political" want political intel immediately. Default NPC factions provide useful intel out-of-the-box. Explicitly empty groups signals intent to configure manually but forgot—this is an error.

**Combining defaults with custom groups:**
```yaml
interest:
  preset: political
  signals:
    politics:
      groups:
        # These REPLACE defaults (not merge)
        my-enemies:
          alliances: [99001234]
        serpentis-aligned:
          factions: [serpentis]
          corporations: [98612345]
```

To ADD to defaults rather than replace, use the `extend_defaults: true` flag:
```yaml
interest:
  preset: political
  signals:
    politics:
      extend_defaults: true    # Keep pirate-factions, empire-factions, triglavian
      groups:
        my-enemies:            # Added alongside defaults
          alliances: [99001234]
```

**Complete preset weight baselines:**

```yaml
# trade-hub: High-value kills near market systems
trade-hub:
  location: 0.8
  value: 0.7
  politics: 0.1
  activity: 0.2
  time: 0.0
  routes: 0.3
  assets: 0.1
  war: 0.0
  ship: 0.3

# political: Entity involvement is primary interest
political:
  location: 0.1
  value: 0.1
  politics: 1.0
  activity: 0.1
  time: 0.0
  routes: 0.0
  assets: 0.0
  war: 0.3
  ship: 0.0

# industrial: Hauler and mining losses
industrial:
  location: 0.5
  value: 0.6
  politics: 0.1
  activity: 0.3
  time: 0.0
  routes: 0.4
  assets: 0.3
  war: 0.0
  ship: 0.8

# hunter: Gatecamp and hotspot detection
hunter:
  location: 0.6
  value: 0.2
  politics: 0.1
  activity: 0.8
  time: 0.3
  routes: 0.5
  assets: 0.0
  war: 0.0
  ship: 0.2

# sovereignty: Nullsec structure and war defense
sovereignty:
  location: 0.4
  value: 0.3
  politics: 0.7
  activity: 0.4
  time: 0.0
  routes: 0.2
  assets: 0.6
  war: 0.9
  ship: 0.3

# wormhole: Chain security monitoring
wormhole:
  location: 1.0
  value: 0.2
  politics: 0.2
  activity: 0.6
  time: 0.0
  routes: 0.0
  assets: 0.3
  war: 0.0
  ship: 0.3
```

#### User-Defined Presets (Modular)

In addition to built-in presets, users can define custom presets in `userdata/presets/`:

```yaml
# userdata/presets/my-corp-intel.yaml
name: my-corp-intel
description: "Intel focused on our corp's operating area"
base: trade-hub  # Optional: inherit from built-in preset

weights:
  location: 0.9
  value: 0.6
  politics: 0.4
  activity: 0.5
  time: 0.2
  routes: 0.6
  assets: 0.3
  war: 0.3
  ship: 0.4

signals:
  location:
    geographic:
      systems:
        - { name: Dodixie, classification: home }
        - { name: Botane, classification: transit }
  politics:
    groups:
      corp-members:
        corporations: [98000001]
```

**Usage in profiles:**

```yaml
interest:
  preset: my-corp-intel  # References userdata/presets/my-corp-intel.yaml
  customize:
    value: +20%
```

**Preset resolution order:**
1. Check `userdata/presets/{name}.yaml`
2. Check built-in presets (trade-hub, political, etc.)
3. Fail validation if not found

**Inheritance:** `base: trade-hub` starts with that preset's weights/signals, then overrides with user values.

### Sliders

- Range: **0-100** with **50 = neutral (1.0x multiplier)**
- Mapping: `multiplier = clamp(slider / 50, 0.0, 2.0)` (0.0x to 2.0x)
- Weights are normalized after adjustment to preserve total influence
- Slider at 0 = category disabled (weight becomes 0)
- Slider at 100 = category doubled (weight becomes 2x base)

**Slider weight validation:**
- Sliders produce weights in range `[0.0, 2.0 * base_weight]`, always non-negative
- If all sliders are set to 0, validation fails: "All category weights are zero; no notifications will match."
- The `customize` percentage syntax (`+20%`, `-10%`) is converted to slider values: `+20%` → slider 60, `-10%` → slider 45

**Normalization:** After slider adjustments, weights are normalized so `sum(weights) = 1.0` for consistent scoring across presets:
```
normalized_weight[c] = adjusted_weight[c] / sum(adjusted_weight)
```

### CLI Tools

**Explainability**: `aria-esi notifications explain <profile> <kill_id>`
- Show signal breakdown, total interest, and why it passed/failed
- Output example:
  ```
  Kill 12345678 | Vexor | Uedama (0.50)
  ─────────────────────────────────────
  Location:  0.82 (weight 0.7) [geographic: 0.9, security: 0.6]
  Value:     0.45 (weight 0.7) [total: 85M ISK, sigmoid: 0.45]
  Politics:  0.00 (weight 0.2) [no group match]
  ─────────────────────────────────────
  Interest:  0.68 (RMS blend)
  Threshold: 0.60 (notify)
  Result:    ✓ NOTIFY
  ```

**Validation**: `aria-esi notifications simulate <profile> --last-24h`
- Report expected notification count, sample pass/fail with signal breakdown
- Warn on contradictions (e.g., `rules.require_all` includes politics but no groups configured)

**Tuning**: `aria-esi notifications tune <profile>`
```text
aria-esi notifications tune <profile>
  Location:  [=====>    ] 60%
  Value:     [======>   ] 70%
  Politics:  [=>        ] 15%
  Time:      [====      ] 40%
```

### Validation

**Error categories:**
- **Weight validation**: Non-negative, finite, not all-zero
- **Threshold ordering**: `digest ≤ notify ≤ priority`
- **Reference validation**: Groups, rules, templates, categories must exist
- **Prefetch compatibility**: Strict mode coerces to conservative when configuration requires post-fetch data
- **Tier requirements**: Intermediate tier requires preset; political preset requires groups
- **Rule dependencies**: e.g., `high_value` requires `signals.value.min`

Errors include field path, code, message, and actionable suggestion.

---

## Compatibility & Migration

### Feature Flag Rollout

The `interest.engine` field controls which engine evaluates the profile:

| Value | Behavior |
|-------|----------|
| `v1` | Current trigger-based system (default during rollout) |
| `v2` | Interest Engine v2 with weighted scoring |

**Additional feature flags** (in `userdata/config.json`):

| Flag | Default | Description |
|------|---------|-------------|
| `notifications.features.rule_dsl` | `false` | Enable expression DSL for custom rules |

**Rollout phases**:
1. **Phase 1 (Week 1-2)**: Ship v2 code with `engine: v1` default. Early adopters opt-in with `engine: v2`. DSL disabled by default.
2. **Phase 2 (Week 3-4)**: Default remains `v1`. Gather metrics on v2 profiles. Template-based rules only.
3. **Phase 3 (Week 5-6)**: If metrics are healthy, flip default to `v2`. Explicit `engine: v1` still works.
4. **Phase 4 (Month 3)**: Deprecation warnings for `engine: v1`. Consider enabling DSL by default if demand exists.
5. **Phase 5 (Month 6)**: Remove v1 code path.

**Instant rollback**: If v2 causes issues, operators can set `engine: v1` globally in `userdata/config.json`:
```yaml
notifications:
  default_engine: v1  # Override default for all profiles
```

**DSL feature flag**: The `rule_dsl` flag is independent of engine version. Even with `engine: v2`, DSL remains opt-in. This allows template-only deployments for simpler maintenance.

### Trigger Migration

Existing v1 triggers are **binary** (match → always notify). Converting them to weighted signals changes semantics: scores can be diluted below threshold. To preserve legacy behavior, migration **must** map critical triggers to `always_notify` rules OR use `require_any` gates.

| v1 Trigger | v2 Signal | Preserving Behavior |
|------------|-----------|---------------------|
| `watchlist_activity` | **`always_notify: watchlist_match`** | Watchlist remains global; watchlist match → always notify. Does NOT migrate IDs into profile groups (see Watchlist Scope Clarification). **Note:** v2 `watchlist_match` is victim-only (prefetch-capable). If v1 detected attacker-only matches, those will require `prefetch.mode: conservative` or adding entities to `politics.groups`. |
| `high_value_threshold` | `value.min` + **`always_notify: high_value`** | Threshold becomes `value.min`; exceeding min → always notify |
| `gatecamp_detected` | `activity.gatecamp` + **`always_notify: gatecamp_detected`** | Gatecamp detection → always notify |
| `npc_faction_kill` | `politics.groups` | Faction IDs become a profile group (weighted, not must-notify) |

**Migration modes:**
- `--preserve-triggers` (default): Maps binary triggers to `always_notify` rules. Behavior is identical to v1.
- `--weighted-only`: Maps triggers to signals without `always_notify`. Scores can be diluted. Use for profiles that want blended behavior.
- `--hybrid`: Preserves `watchlist_activity` and `high_value_threshold` as `always_notify`, but converts `gatecamp_detected` to weighted signal.

**Migration CLI**: `aria-esi notifications migrate <profile> [--advanced] [--preserve-triggers|--weighted-only|--hybrid]`
- Default: generates simple schema (preset + customize) with `--preserve-triggers`
- `--advanced`: generates full weights/signals schema
- `--dry-run`: show what would be generated without writing

**Warning:** Using `--weighted-only` may cause previously-notified kills to be filtered out if their scores are diluted below threshold. Review with `notifications simulate --compare-v1` before deploying.

### Deprecation Timeline

| Milestone | Date | Action |
|-----------|------|--------|
| v2 ships | T+0 | v1 default, v2 opt-in |
| v2 default | T+6 weeks | v2 default, v1 opt-in |
| v1 deprecated | T+3 months | v1 emits warnings |
| v1 removed | T+6 months | v1 profiles fail validation with migration instructions |

---

## Observability & Monitoring

### Metrics

All metrics are emitted with profile and engine labels for segmentation.

| Metric | Type | Description |
|--------|------|-------------|
| `aria_notifications_processed_total` | Counter | Kills evaluated (labels: profile, engine, result) |
| `aria_notifications_sent_total` | Counter | Notifications actually sent (labels: profile, tier) |
| `aria_notifications_prefetch_decisions` | Counter | Prefetch gate decisions (labels: profile, decision: fetch/skip) |
| `aria_notifications_interest_score` | Histogram | Interest score distribution (labels: profile) |
| `aria_notifications_signal_scores` | Histogram | Per-signal score distribution (labels: profile, signal) |
| `aria_notifications_fetch_latency_seconds` | Histogram | ESI fetch latency |
| `aria_notifications_rate_limited_total` | Counter | Notifications dropped by rate limit |
| `aria_notifications_rule_matches_total` | Counter | Hard rule matches (labels: profile, rule) |

### Performance Baseline

Current system performance (as of 2024-01):

| Metric | Current | Target (v2) |
|--------|---------|-------------|
| ESI fetches/hour (per profile) | ~150 | ≤200 (+33% budget) |
| Prefetch pass rate | 35% | 25-45% (profile-dependent) |
| Notification latency p99 | 2.1s | ≤3.0s |
| Memory per profile | 12MB | ≤15MB |

**Acceptable degradation**: Up to 33% increase in ESI fetches is acceptable for improved accuracy. Beyond that, investigate prefetch tuning.

### Health Checks

The notification service exposes health endpoints:

- `/health/ready`: Engine initialized, can process kills
- `/health/live`: Not deadlocked, processing queue depth < 1000
- `/metrics`: Prometheus-format metrics

---

## Rollback Plan

### Immediate Rollback (Operator Action)

If v2 causes production issues:

1. **Per-profile**: Set `interest.engine: v1` in affected profile YAML
2. **Global**: Set `notifications.default_engine: v1` in `userdata/config.json`
3. **Service restart**: Not required; config reload picks up changes within 60s

### Rollback Triggers

Consider rollback if:
- Notification latency p99 exceeds 5s for >10 minutes
- ESI fetch rate exceeds 2x baseline for >30 minutes
- Error rate exceeds 1% of processed kills
- User reports of missed critical notifications

### Post-Rollback

1. Collect logs from affected period
2. Reproduce issue with `notifications simulate --replay <timerange>`
3. Fix and re-test before re-enabling v2

---

## Implementation Plan

**Phases:**
1. Provider framework + feature flags (Week 1)
2. Signal providers (9 categories) + scaling (Week 1-2)
3. Interest engine core + rule system (Week 3-4)
4. Prefetch alignment (Week 5)
5. Preset + delivery providers (Week 6)
6. Migration CLI + tooling (Week 7)
7. Staged rollout (Week 8+)

DSL rule engine is optional for initial release.

---

## Testing Strategy

**Critical test areas:**
- RMS aggregation vs linear (score preservation)
- Prefetch safety margin (`1/sqrt(n)` scaling)
- Rule precedence (`always_ignore` > `always_notify` > gates > scoring)
- Three-tier detection and validation
- Template prefetch capability (static lookup)
- Migration with `--preserve-triggers` produces identical v1 behavior

**Performance targets:**
- ESI fetches: ≤200/hour (+33% budget)
- Latency p99: ≤3.0s
- Memory: ≤15MB per profile

---

## Key Design Decisions

These decisions involve trade-offs that may not be obvious from the spec:

1. **RMS over Linear Aggregation**: Linear averaging dilutes strong signals (1.0 location + 0.0 politics = 0.5). RMS preserves strong signal influence (= 0.71). Trade-off: slightly more complex math for better user experience.

2. **Safety over Efficiency**: When uncertain, fetch more (`unknown_assumption=1.0`, conservative prefetch default). ESI rate limits are soft constraints; missed intel is a hard failure.

3. **RMS Safety Factor**: `prefetch.mode: strict` multiplies threshold by `1/sqrt(n)` to account for linear/RMS divergence. Example: 2 categories → threshold × 0.71. This prevents false negatives without excessive over-fetch.

4. **Politics uses max(), not sum()**: Multiple attackers from the same group score the same as one. We care about involvement, not headcount. This keeps scores interpretable.

5. **Watchlist vs. Profile Groups**: Global watchlist = always-notify (operational alert). Profile groups = weighted scoring (intel tuning). Separate systems, not merged. `watchlist_match` is victim-only for prefetch capability.

6. **Templates over DSL**: Template-based rules cover ~90% of use cases with simpler validation and known prefetch capability. DSL is an escape hatch, not the default. This keeps the simple path simple.

7. **match_threshold = 0.3**: Gates use this threshold to determine category match. Chosen as "meaningful but not dominant" contribution. Could be tuned based on user feedback.

---

## Recommendation

Adopt Interest Engine v2 as the new notification filtering backbone, and fold the `political_entity_kill` concept into a generalized, weighted **politics signal**. This yields a single, explainable model with better UX, cleaner configuration, and fewer edge cases than adding more trigger types.

The feature-flagged rollout ensures safe migration with instant rollback capability.
