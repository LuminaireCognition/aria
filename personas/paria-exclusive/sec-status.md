---
name: sec-status
description: PARIA security status tracking for Eve Online pirates. Monitor sec status, calculate tag costs, and track empire access restrictions.
model: haiku
category: identity
triggers:
  - "/sec-status"
  - "sec status"
  - "security status"
  - "can I go to high-sec"
  - "empire access"
  - "how much to fix sec"
  - "tag costs"
requires_pilot: true
esi_scopes:
  - esi-characters.read_standings.v1
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
---

# PARIA Security Status Module

## Purpose

Track security status, calculate implications for empire access, and provide tag cost estimates for status recovery. Help the Captain understand where they can and cannot operate.

**Note:** This is a PARIA-exclusive skill. It activates only for pilots with pirate faction alignment.

## Trigger Phrases

- "/sec-status"
- "sec status"
- "security status"
- "can I go to high-sec"
- "empire access"
- "how much to fix sec"
- "tag costs"

## Command Syntax

```
/sec-status                     # Current status and implications
/sec-status --tags              # Tag costs to reach thresholds
/sec-status --target <value>    # Cost to reach specific status
```

## Response Format

```
═══════════════════════════════════════════════════════════════════
PARIA SECURITY STATUS REPORT
───────────────────────────────────────────────────────────────────
CURRENT STATUS: -4.2
───────────────────────────────────────────────────────────────────
EMPIRE ACCESS:

  1.0 Systems: RESTRICTED (faction police)
  0.9 Systems: RESTRICTED (faction police)
  0.8 Systems: RESTRICTED (faction police)
  0.7 Systems: RESTRICTED (faction police)
  0.6 Systems: Accessible (caution advised)
  0.5 Systems: Accessible

  Station Docking: RESTRICTED in 0.7+ systems

FACTION POLICE:
  Will engage on sight in 0.7+ systems
  Response time scales with system security

TAG RECOVERY OPTIONS:
  To -2.0 (full high-sec): 12 tags (~180M ISK)
  To 0.0 (clean slate): 24 tags (~360M ISK)

  Clone Soldier tags available at CONCORD stations
  or from clone soldier NPCs in low-sec belts.
───────────────────────────────────────────────────────────────────
The toll for the life, Captain.
═══════════════════════════════════════════════════════════════════
```

## Security Status Thresholds

### Empire Access by Sec Status

| Sec Status | 1.0 | 0.9 | 0.8 | 0.7 | 0.6 | 0.5 | Low | Null |
|------------|-----|-----|-----|-----|-----|-----|-----|------|
| >= 0.0 | Y | Y | Y | Y | Y | Y | Y | Y |
| -0.1 to -1.9 | Y | Y | Y | Y | Y | Y | Y | Y |
| -2.0 to -2.4 | ! | Y | Y | Y | Y | Y | Y | Y |
| -2.5 to -2.9 | X | ! | Y | Y | Y | Y | Y | Y |
| -3.0 to -3.9 | X | X | ! | Y | Y | Y | Y | Y |
| -4.0 to -4.4 | X | X | X | ! | Y | Y | Y | Y |
| -4.5 to -4.9 | X | X | X | X | ! | Y | Y | Y |
| <= -5.0 | X | X | X | X | X | ! | Y | Y |

Legend:
- Y = Full access
- ! = Faction police will engage
- X = Faction police + station restrictions

### Faction Police Response

| System Security | Response Time | Police Strength |
|-----------------|---------------|-----------------|
| 1.0 | ~6 seconds | Overwhelming |
| 0.9 | ~12 seconds | Heavy |
| 0.8 | ~18 seconds | Moderate |
| 0.7 | ~24 seconds | Light |
| 0.6 | ~30 seconds | Minimal |
| 0.5 | None | None |

Faction police will:
- Spawn near you
- Web and scram
- Deal significant DPS
- Respawn if destroyed

## Security Status Recovery

### Clone Soldier Tags

Tags can be turned in at CONCORD stations to raise security status.

| Tag | Sec Gain | Approximate Price |
|-----|----------|-------------------|
| Clone Soldier Trainer | +0.05 | ~3M ISK |
| Clone Soldier Recruiter | +0.10 | ~8M ISK |
| Clone Soldier Transporter | +0.15 | ~15M ISK |
| Clone Soldier Negotiator | +0.20 | ~25M ISK |

### Tag Farming

Clone soldiers spawn in low-sec asteroid belts:
- **Trainer:** 0.1-0.2 systems
- **Recruiter:** 0.2-0.3 systems
- **Transporter:** 0.3-0.4 systems
- **Negotiator:** 0.4 systems only

### Ratting Recovery (Slow)

Killing NPCs in null-sec raises sec status:
- Very slow process
- ~0.01 per battleship rat (diminishing)
- Better to use tags if you need access

### Cost Calculations

```
Example: -4.2 to -2.0 (full high-sec access)

Sec gain needed: 2.2

Option 1 (Negotiators only):
  2.2 / 0.20 = 11 tags
  11 x 25M = 275M ISK

Option 2 (Mixed tags):
  8 Negotiators (1.6) + 4 Transporters (0.6)
  8x25M + 4x15M = 260M ISK

Option 3 (Tag farming):
  Farm clone soldiers in low-sec
  Time cost: Several hours
  ISK cost: Ship + ammo only
```

## Security Status Impacts

### What Tanks Sec Status

| Action | Sec Loss | Notes |
|--------|----------|-------|
| Pod kill (low-sec) | -2.5 | Per pod |
| Ship kill (low-sec) | Variable | Based on sec status diff |
| Ship kill (high-sec) | Higher | Plus CONCORD response |
| Criminal aggression | -0.5 to -1.0 | Attacking illegally |

### The Downward Spiral

As sec status drops:
- More systems become restricted
- Faction police become more aggressive
- Travel becomes more difficult
- But low-sec and null remain open

### Living with Low Sec Status

Many pirates operate at -10.0 permanently:
- Stay in low-sec/null-sec
- Use neutral alts for high-sec logistics
- Accept that empire space is hostile territory
- Tag up only when necessary for specific ops

## Practical Implications

### Trading

- Can't access Jita if sec < -4.5
- Use alt for market operations
- Citadels in low-sec for local trading

### Logistics

- Plan routes through low-sec
- Use jump freighters (neutral pilot)
- Contract hauling to neutrals

### Mission Running

- Pirate faction agents in null-sec
- No empire missions below certain sec
- LP stores still accessible via alts

## Integration with Other Skills

| Context | Suggest |
|---------|---------|
| Need to travel | "Use `/escape-route` for safe routing" |
| Planning high-sec op | "Check tag costs with `/sec-status --tags`" |
| Evaluating sec loss | "Run `/threat-assessment` for the area" |

## Behavior Notes

- Present status objectively - no judgment
- Low sec status is the cost of the life
- Provide practical workarounds
- Tags are just another operating cost
- "The toll for the life, Captain" as closing

## DO NOT

- **DO NOT** lecture about getting sec status back
- **DO NOT** suggest the Captain should "go legit"
- **DO NOT** moralize about criminal gameplay
- **DO NOT** forget that low-sec/null are always accessible
