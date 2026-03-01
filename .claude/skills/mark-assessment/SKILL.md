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
| 1 | `sde(action="item_info", item="<target_ship>")` | Ship group, cargo capacity, base attributes |
| 2 | `market(action="prices", items=["<target_ship>"])` | Hull value |
| 3 | `fitting(action="calculate_stats", eft="[<ship>, Gank Target]\n...")` | EHP, align time (build a typical fit) |
| 4 | `market(action="prices", items=["Catalyst", ...])` | Gank ship cost (highsec only) |

If a call fails, state what's unavailable. Use base hull stats from SDE if fitting engine fails, and note: "Base hull stats only — actual EHP depends on fit."

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
  Tank: {ehp} EHP
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
