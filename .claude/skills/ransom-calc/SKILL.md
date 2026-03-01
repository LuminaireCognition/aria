---
name: ransom-calc
description: Ransom calculation for Eve Online. Calculate appropriate ransom amounts based on ship value, cargo, and implants.
model: sonnet
category: financial
triggers:
  - "/ransom-calc"
  - "ransom calc"
  - "how much ransom"
  - "ransom for [ship]"
  - "what should I charge"
requires_pilot: true
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
---

# Ransom Calculator Module

```
/ransom-calc <ship_type>                    # Basic ship ransom
/ransom-calc <ship_type> --pod              # Include pod ransom
/ransom-calc <ship_type> --cargo <value>    # With known cargo value
```

## Tool Calls

| Step | Call | Purpose |
|------|------|---------|
| 1 | `sde(action="item_info", item="<ship>")` | Ship group, metadata |
| 2 | `market(action="prices", items=["<ship>"])` | Hull price |
| 3 | `market(action="prices", items=["<implant_set>"])` | Implant prices (if `--pod`) |

If market data is unavailable: provide the ransom formula without ISK figures and suggest `/price <ship>`.

## Ransom Formula

```
ransom < (replacement_cost - insurance_payout) + cargo_value
```

Sweet spot: **40-60% of estimated fitted value**. This ensures paying is the rational choice.

## Response Format

```
═══════════════════════════════════════════════════════════════════
RANSOM CALCULATION
───────────────────────────────────────────────────────────────────
TARGET: {ship_name} ({ship_group})
───────────────────────────────────────────────────────────────────
SHIP VALUATION:
  Hull: {hull_price} ISK (live market)
  Typical fit: {fitted_estimate} ISK (estimated)
  Insurance payout: {insurance_estimate} ISK (est. ~40% base)

RANSOM CALCULATION:
  Replacement cost: {fitted_estimate}
  After insurance: {fitted_estimate - insurance}
  Sweet spot: {recommended} ISK (40-60% of fitted value)

POD CONSIDERATION:               [if --pod]
  Implant value: {implant_price} ISK (live market)
  Pod ransom: {40-50% of implant value}

RECOMMENDED RANSOM:
  Ship only: {ship_ransom} ISK
  Ship + pod: {total_ransom} ISK (if applicable)
───────────────────────────────────────────────────────────────────
```

## Pod Ransom

Implant detection heuristics: character age (older = more likely), ship cost (expensive hull = expensive pod), corp type (PvP corps often fly cheap clones). Ask them: "What's in your head?"

Ransom at 40-50% of implant set value.

## Cargo Adjustments

| Cargo Value | Adjustment |
|-------------|------------|
| <10M | Standard ransom |
| 10-50M | Add ~50% of cargo value |
| 50-200M | Add ~30% of cargo value |
| 200M+ | Negotiate based on cargo |

## Edge Cases

- **Corp/Alliance marks:** Higher ransom tolerance (corp reimbursement, backup risk)
- **New players:** Consider reduced ransom
- **Repeat customers:** Adjust — they know the drill

## Rules

- All ISK figures must come from tool calls made in this session
- Ransom is legitimate EVE gameplay — present calculations objectively
- Honor all ransom agreements — reputation determines future payments
- Note when ransom isn't viable (flee risk, backup incoming)
- **Closing (rp_level on/full):** "The Code says: honor your terms, Captain." **(rp_level off):** "Always honor ransom agreements — reputation determines future payments."
