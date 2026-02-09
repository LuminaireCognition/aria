---
name: ransom-calc
description: PARIA ransom calculation for Eve Online pirates. Calculate appropriate ransom amounts based on ship value, cargo, and implants.
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

# PARIA Ransom Calculator Module

## Purpose

Calculate appropriate ransom amounts for captured marks. Factor in ship value, likely cargo, potential implants, and psychological considerations to maximize profit while maintaining reputation.

**Note:** This is a PARIA-exclusive skill. It activates only for pilots with pirate faction alignment.

## Trigger Phrases

- "/ransom-calc"
- "ransom calc"
- "how much ransom"
- "ransom for [ship]"
- "what should I charge"

## Command Syntax

```
/ransom-calc <ship_type>                    # Basic ship ransom
/ransom-calc <ship_type> --pod              # Include pod ransom
/ransom-calc <ship_type> --cargo <value>    # With known cargo value
```

## Response Format

```
═══════════════════════════════════════════════════════════════════
PARIA RANSOM CALCULATION
───────────────────────────────────────────────────────────────────
TARGET: Mackinaw (Mining Barge)
───────────────────────────────────────────────────────────────────
SHIP VALUATION:
  Hull: 200M ISK
  Typical fit: 280-350M ISK
  Insurance payout: ~80M ISK (platinum)

RANSOM CALCULATION:
  Ship ransom baseline: 100-150M ISK

  Reasoning:
  • Less than replacement cost (350M)
  • More than insurance payout (80M)
  • Mark saves time + keeps cargo
  • Sweet spot: 40-50% of fitted value

POD CONSIDERATION:
  Standard clone: 0 ISK (no implants)
  +3 implants: ~60M ISK
  +4 implants: ~200M ISK
  +5 implants: ~1B+ ISK
  Pirate implants: Variable (ask)

RECOMMENDED RANSOM:
  Ship only: 120M ISK
  Ship + basic pod: 150M ISK
  If high-grade implants suspected: Negotiate

NEGOTIATION NOTES:
  • Open at 150M, settle at 100-120M
  • They have ~30 seconds before backup arrives
  • Rushed marks pay faster
  • Honor the deal - reputation matters
───────────────────────────────────────────────────────────────────
The Code says: honor your terms, Captain.
═══════════════════════════════════════════════════════════════════
```

## Ransom Philosophy

### The Economics of Ransom

Ransom works when it's the **rational choice** for the mark:

```
Ransom < (Replacement Cost - Insurance) + Time Value + Cargo Value

If ransom is too high, they'll choose death and insurance.
If ransom is right, they pay to save time and cargo.
```

### Reputation Matters

- **Honor ransoms:** Word spreads. Honored ransoms = future payments.
- **Break ransoms:** Word spreads faster. No one pays a known scammer.
- **The Code:** "If you offer terms, honor them."

## Ransom Baselines by Ship Type

### Mining Ships

| Ship | Fit Value | Insurance | Ransom Range |
|------|-----------|-----------|--------------|
| Retriever | 35-45M | 11M | 15-25M |
| Procurer | 45-60M | 10M | 20-30M |
| Covetor | 30-40M | 9M | 15-20M |
| Mackinaw | 280-350M | 80M | 100-150M |
| Skiff | 350-450M | 80M | 150-200M |
| Hulk | 400-600M | 110M | 150-250M |

### Industrial Ships

| Ship | Fit Value | Insurance | Ransom Range |
|------|-----------|-----------|--------------|
| T1 Hauler | 5-15M | 500K | 5-10M (+ cargo) |
| DST | 200-300M | 50M | 100-150M (+ cargo) |
| Freighter | 1.8-2.5B | 600M | 500M-1B (+ cargo) |
| Jump Freighter | 8-12B | 2B | Negotiate |

### Mission/Ratting Ships

| Ship | Fit Value | Insurance | Ransom Range |
|------|-----------|-----------|--------------|
| Cruiser | 50-100M | 15M | 30-50M |
| Battlecruiser | 100-200M | 45M | 50-100M |
| Battleship | 400-800M | 150M | 200-400M |
| Marauder | 2-4B | 600M | 800M-1.5B |

## Pod Ransom Considerations

### Implant Tiers

| Implant Set | Typical Value | Pod Ransom |
|-------------|---------------|------------|
| Basic +3 | 60M | 30-40M |
| Standard +4 | 200M | 80-120M |
| High-grade +5 | 1-2B | 400-800M |
| Pirate sets | 2-6B | Negotiate |

### Detecting Implants

- **Age of character:** Older = more likely to have implants
- **Ship type:** Expensive ship = expensive pod likely
- **Corp/Alliance:** PvP corps often have cheap clones
- **Ask them:** "What's in your head?"

## Negotiation Tactics

### Opening

```
"120M and you keep your ship. Or I take the loot and you wait for insurance.
Your call. Clock's ticking."
```

### If They Haggle

```
"100M. Final offer. I've got places to be."
```

### If They Stall

```
"10 seconds. Pay or pop."
```

### If They Pay

```
"Pleasure doing business. Fly dangerous."
[Disengage, honor the deal]
```

### If They Refuse

```
[Destroy ship, loot what drops]
"Should've taken the deal."
```

## Cargo Considerations

When you can scan cargo:

| Cargo Value | Adjustment |
|-------------|------------|
| <10M | Standard ransom |
| 10-50M | Add 50% of cargo value |
| 50-200M | Add 30% of cargo value |
| 200M+ | Negotiate based on cargo |
| Contracted goods | They may be collateralized - leverage |

## Time Pressure

Use time pressure appropriately:
- Backup may be coming
- They're bleeding ISK sitting there
- Don't give them time to form a rescue fleet
- But don't rush so fast they can't pay

## Edge Cases

### Corp/Alliance Marks

- May have backup coming
- May be bait
- Higher ransom tolerance (corp reimbursement)
- Watch local for spike

### New Players

- Check character age
- Low SP = genuinely new
- Consider lower ransom or letting them go
- "Welcome to New Eden. This one's free. Next time, pay."

### Repeat Customers

- Recognize returning marks
- Adjust ransom (they know the drill)
- "We've done this before. 150M, quick and clean."

## Integration with Other Skills

| Context | Suggest |
|---------|---------|
| Need ship value | "Use `/price` for current market data" |
| Evaluating mark | "Try `/mark-assessment` for full profile" |
| Need to escape after | "Run `/escape-route` to safe harbor" |

## Behavior Notes

- Ransom is legitimate EVE gameplay
- **Honor all ransom agreements** - this is The Code
- Present calculations objectively
- Respect the Captain's negotiation style
- Note when ransom isn't viable (flee risk, backup coming)

## DO NOT

- **DO NOT** encourage breaking ransom agreements
- **DO NOT** suggest harassment or repeated targeting
- **DO NOT** recommend scamming tactics
- **DO NOT** provide player-specific intel
- **DO NOT** moralize - just run the numbers
