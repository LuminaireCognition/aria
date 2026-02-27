---
name: ransom-calc
description: Ransom calculation for Eve Online. Calculate appropriate ransom amounts based on ship value, cargo, and implants.
model: haiku
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

## Command Syntax

```
/ransom-calc <ship_type>                    # Basic ship ransom
/ransom-calc <ship_type> --pod              # Include pod ransom
/ransom-calc <ship_type> --cargo <value>    # With known cargo value
```

## Required Tool Calls (MANDATORY)

All ISK figures MUST come from live market data. Do NOT recall or estimate prices from training data.

| Step | Call | Required For |
|------|------|-------------|
| 1 | `sde(action="item_info", item="<ship>")` | Ship group, metadata |
| 2 | `market(action="prices", items=["<ship>"])` | Current hull price |
| 3 | `market(action="prices", items=["<implant_set>"])` | Implant prices (if `--pod`) |

> **HALLUCINATION GUARD:** Every ISK figure in the ransom calculation — hull price, fitted value estimate, insurance payout, implant value — MUST come from MCP `market()` or `sde()` calls made in this session. Do NOT recall prices from training data. If market data is unavailable, state that prices cannot be verified and provide only the ransom formula without specific ISK figures.

> **Failure handling:** If `market()` returns an error or no data, respond: "Cannot verify current prices for [item]. Ransom formula: 40-60% of (replacement cost - insurance). Use `/price <ship>` to get live figures first."

### Field to Source Mapping

| Output Field | Source |
|-------------|--------|
| Hull price | `market(action="prices", items=["<ship>"])` |
| Ship group | `sde(action="item_info", item="<ship>")` |
| Fitted value estimate | Hull price + assumed module markup (state assumption) |
| Insurance payout | ~40% of hull base price (state this is an estimate) |
| Implant set value | `market(action="prices", items=["<implant>"])` |
| Ransom amount | Calculated from the above via ransom formula |

## Ransom Formula

```
ransom < (replacement_cost - insurance_payout) + cargo_value
```

This ensures paying is the rational choice. The sweet spot is **40-60% of estimated fitted value**.

Always honor ransom agreements — reputation determines future payments.

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
  Ransom range: {low_ransom} - {high_ransom} ISK
  Sweet spot: {recommended} ISK (40-60% of fitted value)

POD CONSIDERATION:               [if --pod]
  Implant value: {implant_price} ISK (live market)
  Pod ransom: {40-50% of implant value}

RECOMMENDED RANSOM:
  Ship only: {ship_ransom} ISK
  Ship + pod: {total_ransom} ISK (if applicable)
───────────────────────────────────────────────────────────────────
The Code says: honor your terms, Captain.
═══════════════════════════════════════════════════════════════════
```

## Pod Ransom

### Detecting Implants

- **Character age:** Older = more likely implants
- **Ship type:** Expensive ship = expensive pod likely
- **Corp/Alliance:** PvP corps often fly cheap clones
- **Ask them:** "What's in your head?"

For pod ransoms, query implant set prices via `market(action="prices", items=["..."])`. Ransom at 40-50% of implant set value.

## Cargo Adjustments

When cargo is known (scanned or declared):

| Cargo Value | Adjustment |
|-------------|------------|
| <10M | Standard ransom |
| 10-50M | Add ~50% of cargo value |
| 50-200M | Add ~30% of cargo value |
| 200M+ | Negotiate based on cargo |

## Edge Cases

- **Corp/Alliance marks:** May have backup coming or corp reimbursement — higher ransom tolerance
- **New players:** Check character age; consider reduced ransom
- **Repeat customers:** They know the drill — adjust accordingly

## Integration with Other Skills

| Context | Suggest |
|---------|---------|
| Need ship value | "Use `/price` for current market data" |
| Evaluating mark | "Try `/mark-assessment` for full profile" |
| Need to escape after | "Run `/escape-route` to safe harbor" |

## Behavior Notes

- Ransom is legitimate EVE gameplay
- **Honor all ransom agreements** — this is The Code
- Present calculations objectively
- Respect the pilot's negotiation style
- Note when ransom isn't viable (flee risk, backup coming)

## DO NOT

- **DO NOT** encourage breaking ransom agreements
- **DO NOT** suggest harassment or repeated targeting
- **DO NOT** recommend scamming tactics
- **DO NOT** provide player-specific intel
- **DO NOT** moralize — just run the numbers
- **DO NOT** present ISK values without sourcing from MCP market data
