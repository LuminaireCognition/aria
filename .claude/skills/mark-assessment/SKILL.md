---
name: mark-assessment
description: Target evaluation for Eve Online. Assess potential marks based on ship type, likely cargo, and engagement viability.
model: sonnet
category: tactical
triggers:
  - "/mark-assessment"
  - "mark assessment"
  - "assess target"
  - "is this worth ganking"
  - "evaluate target"
  - "should I engage"
requires_pilot: true
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/ships.md
---

# Mark Assessment Module

## Command Syntax

```
/mark-assessment <ship_type>                    # General ship assessment
/mark-assessment <ship_type> --highsec          # High-sec gank viability
/mark-assessment <ship_type> --lowsec           # Low-sec engagement
```

## Tool Call Sequence

Every assessment starts with these calls. Do not write any stats until all calls complete.

| Step | Call | Provides |
|------|------|----------|
| 1 | `sde(action="item_info", item="<target_ship>")` | Ship group, cargo capacity, base HP/resists |
| 2 | `market(action="prices", items=["<target_ship>"])` | Hull value |
| 3 | `market(action="prices", items=["Catalyst", ...])` | Gank ship cost (highsec only) |
| 4 | `fitting(action="calculate_stats", eft="...")` | EHP, align time — **only if user supplies a fit** |

Step 4 is conditional. If no fit is provided, use SDE base HP/resist attributes and note: "Base hull stats only — actual EHP depends on fit."

If SDE does not return numeric attributes (HP, cargo capacity, align time), state "unavailable from SDE" for each missing field. Do NOT substitute training-data estimates (e.g., "typically 5-10K EHP" or "expect 10-15K m³"). Suggest `/fitting` with an observed fit or killmail for precise stats.

If a market call fails, present the formula with placeholder variables and suggest `/price <ship>`.

> **HALLUCINATION GUARD:** Hull price and gank ship cost MUST come from `market(action="prices")` in this session. Ship group, cargo capacity, base HP, and align time MUST come from `sde(action="item_info")`. Never state ISK values or ship stats from training data — this includes EHP ranges, cargo capacity estimates, and align times. If a tool call returns no numeric attributes, show the gap explicitly — do not fill it with approximate ranges from recall.

### Field → Source Mapping

| Output Field | Required Source |
|-------------|----------------|
| Ship group, cargo capacity | `sde(action="item_info")` response |
| Base HP / resists | `sde(action="item_info")` response |
| Hull value | `market(action="prices")` → `sell` price |
| EHP (when fit supplied) | `fitting(action="calculate_stats")` with user-provided EFT |
| EHP (no fit, SDE has HP) | SDE base stats with "actual EHP depends on fit" caveat |
| EHP (no fit, SDE lacks HP) | State "unavailable" — suggest `/fitting` with observed fit |
| Gank ship cost | `market(action="prices")` → `sell` price |
| Expected loot | Computed: fitted value × 0.5 (fitted value from tool-sourced hull price × multiplier) |
| Profit margin | Computed from tool-sourced values above |

### Anti-Patterns

❌ **WRONG:** "A Retriever has about 10k EHP" with no tool call
✅ **RIGHT:** Call `sde(action="item_info")` for base stats, note "actual EHP depends on fit"

❌ **WRONG:** Invent a hypothetical fit, feed it to `fitting(action="calculate_stats")`, present result as fact
✅ **RIGHT:** Use SDE base stats with caveat, or ask user for observed fit / killmail reference

❌ **WRONG:** "A Hulk hull is worth about 350M ISK" from memory
✅ **RIGHT:** Call `market(action="prices", items=["Hulk"])` first, use the returned sell price

## Response Format

```
═══════════════════════════════════════════════════════════════════
MARK ASSESSMENT
───────────────────────────────────────────────────────────────────
TARGET: {ship_name} ({ship_group})
ENGAGEMENT: {VIABLE / MARGINAL / NOT VIABLE}
───────────────────────────────────────────────────────────────────
SHIP PROFILE:
  Hull value: {hull_price} ISK
  Typical fit: {estimated_fitted_value} ISK
  Tank: {ehp} EHP {(fitted) or (base hull — actual depends on fit)}
  Cargo: {cargo_capacity} m³

GANK MATH ({security} system):        [highsec only]
  CONCORD window: {concord_time}
  Required DPS: {required_dps}
  Gank ship cost: {gank_cost} ISK
  Expected loot: {fitted_value × 0.5} ISK
  Profit margin: {profit_or_loss}

ENGAGEMENT NOTES:
  * {ship-specific tactical notes}

VERDICT: {assessment summary}
───────────────────────────────────────────────────────────────────
{closing — rp_level on/full: "Your call, Captain." | off: omit}
═══════════════════════════════════════════════════════════════════
```

## CONCORD Response Times

Stable game mechanic — safe to reference directly:

| Security | Response Time |
|----------|--------------|
| 1.0 | ~6 sec |
| 0.9 | ~7 sec |
| 0.8 | ~8 sec |
| 0.7 | ~10 sec |
| 0.6 | ~14 sec |
| 0.5 | ~19 sec |

Required DPS = target EHP / CONCORD window.

## Gank Profitability

```
Expected Profit = (Fitted Value × 0.5) - Gank Ship Cost - Security Tag Cost
```

State assumptions for fitted value (e.g., "assuming T2 fit, ~1.5x hull value").

## Engagement Reference

**High-sec:** Calculate CONCORD window, factor tag costs, note suspect timer for looting alt.

**Low-sec:** No CONCORD. Gate/station sentries deal ~120 DPS (EM/thermal) for ~30 sec to aggressor — manageable in cruisers, dangerous in frigates. Does not apply at celestials, belts, or safe spots.

**Target behavior indicators:**

| Indicator | Meaning |
|-----------|---------|
| Drones out | Active at keyboard |
| No drones | Possibly AFK |
| Aligned | Alert, ready to warp |
| Stationary | Likely AFK |

**Risk quick-reference:**

| Green (Engage) | Yellow (Caution) | Red (Reconsider) |
|----------------|------------------|-------------------|
| Alone in system | Corp mates in local | Known bait ship |
| Ship not aligned | Near station/citadel | PvP corp history |
| High-value ship | Combat probes on scan | Cyno fit possible |

## Related Commands

| Context | Suggest |
|---------|---------|
| Need ship price | `/price` |
| Planning ransom | `/ransom-calc` |
| Need gank fit | `/fitting` |

## Behavior Notes

- Present data objectively — "marks" not "victims"
- No intel on specific named players
- No harassment encouragement or exploit recommendations
- Respect pilot's decision on engagement
