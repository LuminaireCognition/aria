---
name: clones
description: Clone and implant status tracking. Safety-critical for knowing your medical clone location and active implants before risky operations.
model: haiku
category: tactical
triggers:
  - "/clones"
  - "clone status"
  - "where's my clone"
  - "check my implants"
  - "jump clone status"
  - "can I jump clone"
  - "medical clone location"
requires_pilot: true
esi_scopes:
  - esi-clones.read_clones.v1
  - esi-clones.read_implants.v1
---

# ARIA Clone Status Module

## Purpose

Track clone locations and implants - **safety-critical information** for mission running and PvP. Knowing where your medical clone is set and what implants you'll lose if podded helps pilots make informed risk decisions.

## Why This Matters

When your pod is destroyed:
1. **You respawn at your medical clone location** - if it's 30 jumps away, you're stranded
2. **All implants in your active clone are destroyed** - expensive hardwirings are lost forever
3. **Jump clones preserve implants** - swap to a clean clone before risky ops

**Check your clone status before:**
- Low-sec or null-sec operations
- Missions with high ship loss risk
- PvP roams
- Any activity where pod loss is possible

## Trigger Phrases

- "clone status" / "where's my clone"
- "check my implants"
- "jump clone status"
- "can I jump clone"
- "medical clone location"
- `/clones`

## Commands

### Full Clone Status

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi clones
```

Shows:
- Medical clone location (where you respawn)
- All jump clones and their locations
- Implants in each clone
- Jump clone cooldown status

### Active Implants Only

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi implants
```

Shows implants in your current active clone, organized by slot:
- Attribute Enhancers (slots 1-5)
- Hardwirings (slots 6-10)

### Jump Clone Status

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi jump-clones
```

Shows jump clone locations and whether you can currently jump (24h cooldown).

## Response Format

### Full Clone Status

```
═══════════════════════════════════════════════════════════════════
ARIA CLONE STATUS
───────────────────────────────────────────────────────────────────
MEDICAL CLONE:
  Location: Masalle - X-Sense Chemical Refinery
  System: Masalle (0.9)

JUMP CLONES: 2
┌─────────────────────────────────────────────────────────────────┐
│ Clone 1: "PvP Clone"                                            │
│ Location: Jita IV - Moon 4 - Caldari Navy Assembly Plant        │
│ Implants: 0 (clean clone)                                       │
├─────────────────────────────────────────────────────────────────┤
│ Clone 2: "Learning Clone"                                       │
│ Location: Dodixie IX - Moon 20 - Fed Navy Assembly Plant        │
│ Implants: 5 (attribute enhancers)                               │
└─────────────────────────────────────────────────────────────────┘

JUMP STATUS: Available (last jump: 2 days ago)

ACTIVE IMPLANTS: 3
  Slot 6: Zainou 'Deadeye' Sharpshooter ST-901
  Slot 7: Inherent Implants 'Squire' Capacitor Management EM-801
  Slot 8: Zainou 'Gnome' Shield Management SM-801
───────────────────────────────────────────────────────────────────
⚠ These implants will be lost if your pod is destroyed.
  Consider jumping to a clean clone before risky operations.
═══════════════════════════════════════════════════════════════════
```

### Implants Only

```
═══════════════════════════════════════════════════════════════════
ARIA IMPLANT STATUS
───────────────────────────────────────────────────────────────────
ACTIVE CLONE IMPLANTS: 8

ATTRIBUTE ENHANCERS (Slots 1-5):
  Slot 1: Limited Social Adaptation Chip - Basic
  Slot 2: Limited Memory Augmentation - Basic
  Slot 3: Limited Neural Boost - Basic
  Slot 4: Limited Cybernetic Subprocessor - Basic
  Slot 5: [Empty]

HARDWIRINGS (Slots 6-10):
  Slot 6: Zainou 'Deadeye' Sharpshooter ST-901
  Slot 7: Inherent Implants 'Squire' Capacitor Management EM-801
  Slot 8: Zainou 'Gnome' Shield Management SM-801
  Slot 9: [Empty]
  Slot 10: [Empty]
───────────────────────────────────────────────────────────────────
⚠ All implants lost on pod destruction. Estimated value at risk.
═══════════════════════════════════════════════════════════════════
```

### Jump Clone Status

```
═══════════════════════════════════════════════════════════════════
ARIA JUMP CLONE STATUS
───────────────────────────────────────────────────────────────────
JUMP CLONES: 2

1. "PvP Clone" @ Jita (0 implants)
2. "Learning Clone" @ Dodixie (5 implants)

COOLDOWN: Available (can jump now)
  Last jump: 2026-01-14 15:30 UTC
───────────────────────────────────────────────────────────────────
```

### Jump Clone On Cooldown

```
═══════════════════════════════════════════════════════════════════
ARIA JUMP CLONE STATUS
───────────────────────────────────────────────────────────────────
JUMP CLONES: 2

1. "PvP Clone" @ Jita (0 implants)
2. "Learning Clone" @ Dodixie (5 implants)

COOLDOWN: 18h 45m remaining
  Available at: 2026-01-16 10:15 UTC
───────────────────────────────────────────────────────────────────
⚠ Cannot jump clone until cooldown expires.
═══════════════════════════════════════════════════════════════════
```

## Implant Slot Reference

### Attribute Enhancers (Slots 1-5)

These boost your attributes, affecting skill training speed:

| Slot | Attribute | Effect |
|------|-----------|--------|
| 1 | Perception | Faster spaceship, gunnery, missile training |
| 2 | Memory | Faster engineering, science training |
| 3 | Willpower | Faster armor, shield, navigation training |
| 4 | Intelligence | Faster electronics, mechanics training |
| 5 | Charisma | Faster social, leadership training |

### Hardwirings (Slots 6-10)

These provide combat/utility bonuses:

| Slot | Common Types |
|------|--------------|
| 6 | Turret/missile damage, mining yield |
| 7 | Capacitor, shield boost, armor repair |
| 8 | Shield/armor resistance, navigation |
| 9 | Signature, agility, speed |
| 10 | Various specialized bonuses |

## Safety Protocols

### Before Risky Operations

**ARIA should proactively warn** when a pilot discusses:
- Low-sec or null-sec travel
- PvP activities
- Difficult missions (L4+, storyline)
- Wormhole exploration

**Warning format:**
```
⚠ IMPLANT RISK CHECK
You have [N] implants currently active worth [estimated value].
Consider checking /clones before this operation.
```

### Risk Assessment Integration

When `/threat-assessment` indicates HIGH or CRITICAL risk, remind pilot about clone status:
```
Note: With elevated pod loss risk, verify your clone status (/clones)
before proceeding. Current implants will be lost if podded.
```

## Experience-Based Adaptation

### Clone Explanation

**new:**
```
CLONE BASICS:
Your "medical clone" is where you respawn if your capsule (pod) is destroyed.
Make sure it's set somewhere convenient! You can change it at any station
with a medical facility (right-click your portrait → Set Home Station).

"Jump clones" are extra bodies you can swap into. They're useful for:
- Keeping expensive implants safe (swap to empty clone before PvP)
- Having different implant sets for different activities
- Instant travel (you appear at the jump clone's location)

Jump clones have a 24-hour cooldown between uses.
```

**intermediate:**
```
Medical clone: Masalle (verify before low-sec ops)
Jump clones: 2 available, 24h cooldown ready
Active implants: 3 hardwirings at risk
```

**veteran:**
```
Med: Masalle | JC: 2 (ready) | Implants: 3 HW
```

## Scopes Required

- `esi-clones.read_clones.v1` - Clone locations, jump clones
- `esi-clones.read_implants.v1` - Active implant list

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run clone/implant commands - they will timeout
2. **RESPOND IMMEDIATELY** with:
   ```
   Clone status requires live ESI data which is currently unavailable.

   Check this in-game:
   • Clone Bay: Right-click portrait → Clone Bay
   • Jump Clones: Character Sheet → Clone tab
   • Implants: Character Sheet → Augmentations tab

   ESI usually recovers automatically.
   ```
3. **DO NOT** block waiting for ESI

### If ESI is AVAILABLE:

Proceed with normal clone queries.

## Contextual Suggestions

After providing clone information, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Planning risky mission | "Run `/threat-assessment` for the mission area" |
| Has implants at risk | "Check `/fitting` for a tankier ship build" |
| No jump clones | "Jump clones require Infomorph Psychology skill" |
| Looking at LP implants | "Browse implants with `/lp-store` search" |

## Error Handling

### Missing Scope

```
Clone data requires ESI authorization.

To enable clone tracking:
  uv run python .claude/scripts/aria-oauth-setup.py

This will authorize:
  - esi-clones.read_clones.v1 (clone locations)
  - esi-clones.read_implants.v1 (active implants)
```

### No Jump Clones

```
No jump clones found.

Jump clones require the Infomorph Psychology skill:
  Level 1: 1 jump clone
  Level 2: 2 jump clones
  ...up to 5 at Level 5

Additional clones available via:
  - Advanced Infomorph Psychology skill (+1 per level)
  - Clone Soldier Tags (from pirate NPCs)
```
