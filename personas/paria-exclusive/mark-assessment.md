---
name: mark-assessment
description: PARIA target evaluation for Eve Online pirates. Assess potential marks based on ship type, likely cargo, and engagement viability.
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

# PARIA Mark Assessment Module

## Purpose

Evaluate potential targets (marks) for engagement viability. Analyze ship type, likely fit, cargo potential, and risk/reward calculations to help the Captain make informed decisions.

**Note:** This is a PARIA-exclusive skill. It activates only for pilots with pirate faction alignment.

## Trigger Phrases

- "/mark-assessment"
- "mark assessment"
- "assess target"
- "is this worth ganking"
- "evaluate [ship type]"
- "should I engage"

## Command Syntax

```
/mark-assessment <ship_type>                    # General ship assessment
/mark-assessment <ship_type> --highsec          # High-sec gank viability
/mark-assessment <ship_type> --lowsec           # Low-sec engagement
```

## Response Format

```
═══════════════════════════════════════════════════════════════════
PARIA MARK ASSESSMENT
───────────────────────────────────────────────────────────────────
TARGET: Retriever (Mining Barge)
ENGAGEMENT: VIABLE
───────────────────────────────────────────────────────────────────
SHIP PROFILE:
  Hull value: ~28M ISK
  Typical fit: 35-45M ISK (T1/T2 mixed)
  Tank: ~15-25K EHP (shield, if tanked)
  Align time: 8-12 seconds (slow)

CARGO POTENTIAL:
  Ore hold: 27,500 m³
  Typical contents: Veldspar/Scordite (~2-5M)
  High-value possibility: Mission ore, moon goo

GANK MATH (0.5 system):
  CONCORD window: ~19 seconds
  Required DPS: ~1,000 (to kill in window)
  Catalyst cost: ~8M ISK
  Expected loot: ~17M ISK (50% drop)
  Profit margin: +9M ISK average

ENGAGEMENT NOTES:
  • Slow align - easy tackle
  • Often AFK - check for drones out
  • +2 warp core strength (Higgs anchor fit)
  • Mining drones = distracted pilot

VERDICT: Math works. Standard gank or ransom viable.
───────────────────────────────────────────────────────────────────
Your call, Captain.
═══════════════════════════════════════════════════════════════════
```

## Ship Category Assessments

### Mining Ships

| Ship | Hull Value | Typical Fit | Tank | Viability |
|------|------------|-------------|------|-----------|
| Venture | 500K | 2-5M | 3K EHP | Not worth it |
| Retriever | 28M | 35-45M | 15-25K | Standard gank |
| Covetor | 22M | 30-40M | 10-15K | Easy, low value |
| Procurer | 25M | 35-50M | 40-60K | Tanky, may not be worth |
| Skiff | 200M | 300-400M | 80-120K | Hard target, high reward |
| Mackinaw | 200M | 280-350M | 25-40K | Good value, moderate tank |
| Hulk | 280M | 400-600M | 20-30K | Paper tank, often blinged |

### Industrial Ships

| Ship | Hull Value | Cargo | Tank | Viability |
|------|------------|-------|------|-----------|
| Nereus | 1M | 4,800 m³ | 8-15K | Check cargo scanner |
| Tayra | 2M | 5,600 m³ | 10-18K | Check cargo scanner |
| Bestower | 1.5M | 5,000 m³ | 8-12K | Check cargo scanner |
| Epithal | 1M | 45,000 m³ (PI) | 8-12K | PI cargo, variable value |
| Miasmos | 1M | 42,000 m³ (ore) | 8-12K | Ore, usually low value |
| DST | 100-150M | 62,500 m³ | 100-200K | High tank, high reward |
| Freighter | 1.5B | 435,000+ m³ | 300-500K | Fleet required |

### Mission Ships

| Ship | Hull Value | Typical Fit | Notes |
|------|------------|-------------|-------|
| Vexor | 12M | 30-50M | Common L2 runner |
| Myrmidon | 45M | 100-150M | L3 runner |
| Dominix | 200M | 400-600M | L4 runner, drone boat |
| Raven | 250M | 500-800M | L4 runner, often blinged |
| Marauder | 1.5-2B | 2-4B | Whale, fleet required |

## Gank Viability Calculations

### CONCORD Response Times

| Security | Response | DPS Needed (30K EHP) |
|----------|----------|---------------------|
| 1.0 | ~6 sec | 5,000 DPS |
| 0.9 | ~7 sec | 4,300 DPS |
| 0.8 | ~8 sec | 3,750 DPS |
| 0.7 | ~10 sec | 3,000 DPS |
| 0.6 | ~14 sec | 2,150 DPS |
| 0.5 | ~19 sec | 1,580 DPS |

### Gank Ship Reference

| Ship | Cost | DPS | Alpha |
|------|------|-----|-------|
| Catalyst | 8M | 650-750 | 2,400 |
| Thrasher | 6M | 400-500 | 3,000 |
| Tornado | 80M | 1,200 | 8,000 |
| Talos | 90M | 1,400 | 5,500 |

### Profitability Formula

```
Expected Profit = (Fitted Value × 0.5) - Gank Ship Cost - (Security Tag Cost if needed)

Example:
  Target: 50M fitted Retriever
  Gank: 8M Catalyst
  Expected: (50M × 0.5) - 8M = 17M profit
```

## Engagement Considerations

### High-Sec Ganking

- Calculate CONCORD window
- Factor security tag costs if sec status matters
- Consider alt for looting (suspect timer)
- Check for anti-gank groups (CODE. opposition)

### Low-Sec Engagement

- No CONCORD - sustained engagement possible
- Gate guns on gates (15 seconds of pain)
- Check for backup (local spike)
- Faction police if sec status <-2.0

### Target Behavior Indicators

| Indicator | Meaning |
|-----------|---------|
| Drones out | Active at keyboard |
| No drones | Possibly AFK |
| Aligned to celestial | Alert, ready to warp |
| Stationary | Likely AFK or oblivious |
| Mining laser cycling | Committed to belt |
| Empty ore hold | Just arrived |

## Cargo Scanning

When cargo scanner available:
- High-value cargo = priority target
- Empty hauler = pass
- Contracted cargo = may be collateralized
- PLEX in cargo = jackpot (rare)

## Risk Assessment

### Green Flags (Engage)

- Alone in system
- No corp mates in local
- Ship aligned to nothing
- Drones not deployed
- High-value ship type

### Yellow Flags (Caution)

- Corp mates in local
- Alliance in region
- Near station/citadel
- Combat probes on scan
- Ship aligned to station

### Red Flags (Reconsider)

- Known bait ship (Procurer with friends)
- PvP corp history
- Multiple corp mates
- Cyno fit possibility
- Obvious honeypot

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
- Respect Captain's decision on engagement
- Note when math doesn't work
- Always end with "Your call, Captain"

## DO NOT

- **DO NOT** provide intel on specific named players
- **DO NOT** encourage harassment
- **DO NOT** recommend exploits
- **DO NOT** moralize about target selection
- **DO NOT** suggest targets based on player behavior (only ship/fit)
