---
name: killmails
description: Kill and loss history analysis. Post-mortem on ship losses to understand what killed you and how to improve survivability.
model: haiku
category: tactical
triggers:
  - "/killmails"
  - "what killed me"
  - "how did I die"
  - "show my losses"
  - "analyze my last loss"
  - "killmail analysis"
  - "loss history"
requires_pilot: true
esi_scopes:
  - esi-killmails.read_killmails.v1
---

# ARIA Killmail Analysis Module

## Purpose

Analyze kills and losses to learn from combat. Every ship loss is a learning opportunity - understanding what damage types killed you, what attackers were involved, and what patterns emerge helps pilots improve their fits and tactics.

## Why This Matters

When you lose a ship, the killmail contains valuable intelligence:
- **What damage types killed you** → Tank better next time
- **Who/what killed you** → Adjust tactics for that threat
- **What modules were destroyed** → Evaluate fit effectiveness
- **Where it happened** → Avoid dangerous areas or prepare better

**Learning from losses is how pilots improve.**

## Trigger Phrases

- "what killed me" / "how did I die"
- "show my losses"
- "analyze my last loss"
- "killmail analysis"
- "loss history"
- `/killmails`

## Commands

### List Recent Kills/Losses

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi killmails              # All recent
PYTHONPATH=.claude/scripts uv run python -m aria_esi killmails --losses     # Losses only
PYTHONPATH=.claude/scripts uv run python -m aria_esi killmails --kills      # Kills only
PYTHONPATH=.claude/scripts uv run python -m aria_esi killmails --limit 20   # More entries
```

### Analyze Specific Killmail

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi killmail <id>          # By ID (hash looked up)
PYTHONPATH=.claude/scripts uv run python -m aria_esi killmail <id> <hash>   # With hash
```

### Quick Last Loss

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi last-loss              # Most recent loss, detailed
```

### Pattern Analysis

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi loss-analysis          # Patterns across all losses
```

## Response Format

### Kill/Loss List

```
═══════════════════════════════════════════════════════════════════
ARIA COMBAT RECORD
───────────────────────────────────────────────────────────────────
RECENT LOSSES: 3
RECENT KILLS: 7

LOSSES:
  2026-01-15 14:32 | Venture | Tama (0.3) | 5 attackers | 12,450 dmg
  2026-01-14 22:15 | Imicus | Hek (0.5) | 1 attacker | 3,200 dmg
  2026-01-12 09:45 | Catalyst | Auviken (0.4) | 3 attackers | 8,100 dmg

KILLS:
  2026-01-15 16:00 | Serpentis Frigate | Masalle (0.9) | Solo
  [...]
───────────────────────────────────────────────────────────────────
Use 'aria-esi killmail <id>' for detailed analysis
═══════════════════════════════════════════════════════════════════
```

### Detailed Loss Analysis

```
═══════════════════════════════════════════════════════════════════
ARIA LOSS ANALYSIS
───────────────────────────────────────────────────────────────────
KILLMAIL: 12345678
TIME: 2026-01-15 14:32:18 UTC
SYSTEM: Tama (0.3)
───────────────────────────────────────────────────────────────────
VICTIM:
  Ship: Venture
  Damage Taken: 12,450

ATTACKERS: 5 (all players)
  1. PirateName [YARR] - Thrasher - 6,200 dmg (Final Blow)
  2. GankAlt1 - Catalyst - 3,100 dmg
  3. GankAlt2 - Catalyst - 2,050 dmg
  4. GankAlt3 - Catalyst - 1,100 dmg
  5. Unknown - Capsule - 0 dmg

DAMAGE BREAKDOWN:
  Kinetic: 45% (5,600)
  Thermal: 35% (4,350)
  Explosive: 20% (2,500)

ITEMS DESTROYED:
  • Miner II x2
  • Survey Scanner II
  • Medium Shield Extender I

ITEMS DROPPED:
  • Veldspar x4,500
  • 1MN Afterburner I
───────────────────────────────────────────────────────────────────
ANALYSIS:
This was a coordinated gank by 4 Catalysts and a Thrasher.
Primary damage was kinetic/thermal (hybrid weapons).
Location (Tama 0.3) is a known low-sec gank system.

RECOMMENDATIONS:
• In 0.3 systems, keep aligned and D-scan constantly
• Consider +2 warp core stabilizers for mining in low-sec
• Avoid Tama - it's a famous pirate hotspot
═══════════════════════════════════════════════════════════════════
```

### Pattern Analysis

```
═══════════════════════════════════════════════════════════════════
ARIA LOSS PATTERN ANALYSIS
───────────────────────────────────────────────────────────────────
ANALYSIS PERIOD: Last 90 days
TOTAL LOSSES: 8

BREAKDOWN:
  PvP Losses: 5 (62%)
  PvE Losses: 3 (38%)

SHIPS LOST:
  Venture: 3
  Imicus: 2
  Catalyst: 2
  Vexor: 1

DANGEROUS SYSTEMS:
  Tama: 2 losses
  Auviken: 1 loss
  Hek: 1 loss

RECOMMENDATIONS:
• Most losses (5/8) are to players. Consider: D-scan vigilance,
  safer travel routes, or PvP-fit ships.
• You've lost 3 Venture(s). Consider: Reviewing your fit, or
  trying a different hull.
• Review individual losses with 'aria-esi killmail <id>' for
  detailed analysis.
═══════════════════════════════════════════════════════════════════
```

## Damage Type Analysis

### What Damage Types Mean

| Damage | Common Sources | Tank Priority |
|--------|---------------|---------------|
| **EM** | Lasers, some drones | Amarr regions, Blood Raiders |
| **Thermal** | Lasers, hybrids, missiles | Serpentis, Sansha, Amarr |
| **Kinetic** | Hybrids, projectiles, missiles | Guristas, Caldari, Gallente |
| **Explosive** | Projectiles, missiles, some drones | Angels, Minmatar |

### Using Damage Analysis

When ARIA shows damage breakdown, use it to improve your tank:

**Example:** Loss shows 60% kinetic, 30% thermal damage
- **Lesson:** Tank kinetic > thermal for similar threats
- **Action:** Fit Kinetic Shield Hardener or Kinetic Armor Hardener
- **Drones:** If using drones, Hobgoblins (thermal) hit their resist hole

## Experience-Based Adaptation

### Loss Explanation

**new:**
```
WHAT IS A KILLMAIL?
When a ship is destroyed in EVE, a "killmail" is generated recording:
- What ship was destroyed
- Who destroyed it (and with what weapons)
- What modules were fitted and what dropped

You can learn a lot from studying your losses:
- What damage type killed you? Tank against that next time.
- Were you ganked? Maybe avoid that system or fit differently.
- What dropped vs destroyed? Sometimes you get lucky with loot.
```

**intermediate:**
```
Loss to 5 player Catalysts in Tama (0.3).
Primary damage: kin/therm (hybrids).
Classic gank - tank wouldn't have saved you, avoid system.
```

**veteran:**
```
5x Cat gank | Tama | kin/therm | alpha'd
```

### Damage Breakdown

**new:**
- Explain each damage type and where it comes from
- Suggest specific modules to counter
- Explain why the damage profile matters

**veteran:**
- Just show percentages: "kin 45% / therm 35% / exp 20%"
- Assume they know the implications

## Contextual Suggestions

After providing killmail information, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Died to NPC pirates | "Run `/mission-brief` for damage profiles" |
| Died in low-sec | "Check `/threat-assessment` before returning" |
| Lost expensive implants | "Use `/clones` to track implant locations" |
| Fit could be improved | "Try `/fitting` for an optimized build" |

## Learning Integration

ARIA can proactively use killmail data:

### Before Risky Operations
If pilot discusses returning to a system where they recently died:
```
⚠ LOCATION WARNING
You lost a Venture in Tama 2 days ago (5 player attackers).
This system has active PvP. Proceed with caution or consider
an alternate route.
```

### When Fitting Ships
Reference past losses when suggesting fits:
```
Based on your recent losses showing 60% kinetic damage,
I've prioritized kinetic resistance in this fit.
```

## Scopes Required

- `esi-killmails.read_killmails.v1` - Access to kill/loss history

Note: The killmail detail endpoint is **public** once you have the ID and hash - the scope just lets you see which killmails are yours.

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run killmail commands - they will timeout
2. **SUGGEST** alternative: "ESI is currently unavailable. You can view your kill history at:"
   - zKillboard: `https://zkillboard.com/character/{character_id}/`
   - In-game: Character Sheet → Interactions → Combat Log
3. **ANSWER IMMEDIATELY** with the alternative

### If ESI is AVAILABLE:

Proceed with killmail queries.

## Error Handling

### No Killmails Found

```
No recent killmails found.

This means either:
• You haven't lost any ships recently (good!)
• You haven't killed anything recently
• Killmails older than 90 days aren't included

Note: NPC kills don't generate killmails unless you're on a
player kill too.
```

### Missing Scope

```
Killmail access requires ESI authorization.

To enable loss analysis:
  uv run python .claude/scripts/aria-oauth-setup.py

This will authorize:
  - esi-killmails.read_killmails.v1 (kill/loss history)
```

## Privacy Note

Killmails are semi-public in EVE - anyone involved can see them, and many are posted to zKillboard. ARIA only accesses your personal killmail history through ESI, not external sites.
