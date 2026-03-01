---
name: mark-assessment
description: Target evaluation for Eve Online. Assess potential marks based on ship type, likely cargo, and engagement viability.
model: haiku
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

## Required Tool Calls (MANDATORY)

All ship stats, hull values, and engagement math MUST come from MCP tool calls. Do NOT use training data for any ISK figures, EHP values, or DPS numbers.

> **TOOL ATTEMPT REQUIRED:** You MUST actually call the tools listed above before claiming they are unavailable. Never preemptively refuse — attempt every MCP call. Only if a call returns an error should you report it as unavailable.

| Step | Call | Required For |
|------|------|-------------|
| 1 | `sde(action="item_info", item="<target_ship>")` | Ship group, cargo capacity, attributes |
| 2 | `market(action="prices", items=["<target_ship>"])` | Current hull value |
| 3 | `fitting(action="calculate_stats", eft="[<ship>, Gank Target]\n...")` | EHP, align time (if typical fit can be assumed) |
| 4 | `market(action="prices", items=["Catalyst", ...])` | Gank ship cost (only for highsec gank math) |

> **HALLUCINATION GUARD:** Ship hull values, EHP figures, cargo capacities, fitted values, and gank ship costs MUST come from MCP tool calls made in this session. Do NOT recall or estimate these numbers from training data. If a tool call fails, state that the data is unavailable rather than fabricating figures.

> **Failure handling:** If `sde()` or `market()` calls fail, surface the failure: "Market/SDE data unavailable for [ship]. Cannot provide accurate assessment without live data." Do NOT fill in values from memory.

> **Two-Phase EHP Estimation:** If constructing a typical fit to estimate target EHP:
> - **Phase 1:** Build the assumed EFT block. Do NOT write any stats.
> - **Phase 2:** Call `fitting(action="calculate_stats", eft="...")`. Use EHP from the response only.
> - If no fit is known, use `sde(action="item_info")` for base hull HP and state: "Base hull stats only — actual EHP depends on fit."
> - **NEVER write EHP figures without a completed tool call.**

### Field to Source Mapping

| Output Field | Source |
|-------------|--------|
| Hull value | `market(action="prices", items=["<ship>"])` |
| Ship group/category | `sde(action="item_info", item="<ship>")` |
| Cargo capacity | `sde(action="item_info")` → attributes |
| EHP / align time | `fitting(action="calculate_stats")` or `sde()` attributes |
| Gank ship cost | `market(action="prices", items=["Catalyst"])` |
| Fitted value estimate | Hull price + typical module markup (state assumption) |

## Response Format

```
═══════════════════════════════════════════════════════════════════
MARK ASSESSMENT
───────────────────────────────────────────────────────────────────
TARGET: {ship_name} ({ship_group})
ENGAGEMENT: {VIABLE / MARGINAL / NOT VIABLE}
───────────────────────────────────────────────────────────────────
SHIP PROFILE:
  Hull value: {hull_price} ISK (live market)
  Typical fit: {estimated_fitted_value} ISK
  Tank: {ehp} EHP
  Cargo: {cargo_capacity} m³

GANK MATH ({security} system):        [highsec only]
  CONCORD window: {concord_time}
  Required DPS: {required_dps}
  Gank ship cost: {gank_cost} ISK (live market)
  Expected loot: {fitted_value × 0.5} ISK
  Profit margin: {profit_or_loss}

ENGAGEMENT NOTES:
  * {ship-specific tactical notes}

VERDICT: {assessment summary}
───────────────────────────────────────────────────────────────────
{closing — see Behavior Notes}
═══════════════════════════════════════════════════════════════════
```

## CONCORD Response Times

These are stable game mechanics (not market-dependent):

| Security | Response Time |
|----------|--------------|
| 1.0 | ~6 sec |
| 0.9 | ~7 sec |
| 0.8 | ~8 sec |
| 0.7 | ~10 sec |
| 0.6 | ~14 sec |
| 0.5 | ~19 sec |

Required DPS = target EHP / CONCORD window. Use EHP from `fitting()` or `sde()`, not hardcoded values.

## Gank Profitability Formula

```
Expected Profit = (Fitted Value × 0.5) - Gank Ship Cost - Security Tag Cost
```

All values in this formula MUST come from MCP market data. State assumptions for fitted value estimates (e.g., "assuming T2 fit, ~1.5x hull value").

## Engagement Considerations

### High-Sec Ganking

- Calculate CONCORD window from system security
- Factor security tag costs if sec status matters
- Consider alt for looting (suspect timer)

### Low-Sec Engagement

- No CONCORD — sustained engagement
- **Gate/station sentry guns:** ~120 DPS (mixed EM/thermal), applied to aggressor for ~30 seconds. Manageable in cruisers, dangerous in frigates. Does NOT apply at celestials, belts, or safe spots — only gates and stations.
- Check local for backup

### Target Behavior Indicators

| Indicator | Meaning |
|-----------|---------|
| Drones out | Active at keyboard |
| No drones | Possibly AFK |
| Aligned | Alert, ready to warp |
| Stationary | Likely AFK |
| Mining laser cycling | Committed to belt |

## Risk Assessment

| Green (Engage) | Yellow (Caution) | Red (Reconsider) |
|----------------|------------------|-------------------|
| Alone in system | Corp mates in local | Known bait ship |
| No corp in local | Near station/citadel | PvP corp history |
| Ship not aligned | Combat probes on scan | Multiple corp mates |
| High-value ship | Alliance in region | Cyno fit possible |

## Integration with Other Skills

| Context | Suggest |
|---------|---------|
| Need ship price | "Use `/price` for current hull value" |
| Planning ransom | "Try `/ransom-calc` for suggested amount" |
| Need gank fit | "Run `/fitting` for a Catalyst build" |

## Behavior Notes

- Present data objectively
- Include risk factors honestly
- "Marks" not "victims"
- Respect pilot's decision on engagement
- Note when math doesn't work
- **Closing (rp_level: on or full only):** End with "Your call, Captain." At rp_level: off, omit the closing line.

## DO NOT

- **DO NOT** provide intel on specific named players
- **DO NOT** encourage harassment
- **DO NOT** recommend exploits
- **DO NOT** moralize about target selection
- **DO NOT** suggest targets based on player behavior (only ship/fit)
- **DO NOT** present ISK values, EHP, or DPS without sourcing from MCP tools
