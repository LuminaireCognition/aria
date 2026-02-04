---
name: hunting-grounds
description: PARIA hunting ground analysis for Eve Online pirates. Analyze systems for target availability, traffic patterns, and competition.
model: haiku
category: tactical
triggers:
  - "/hunting-grounds"
  - "hunting grounds"
  - "where should I hunt"
  - "good systems for piracy"
  - "find targets"
  - "busy systems"
requires_pilot: true
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
---

# PARIA Hunting Grounds Module

## Purpose

Analyze solar systems for pirate operational viability. Evaluate target availability, traffic patterns, competition presence, and tactical considerations for hunting operations.

**Note:** This is a PARIA-exclusive skill. It activates only for pilots with pirate faction alignment.

## Trigger Phrases

- "/hunting-grounds"
- "hunting grounds"
- "where should I hunt"
- "good systems for piracy"
- "find targets"
- "what systems are busy"

## Command Syntax

```
/hunting-grounds <system>           # Analyze specific system
/hunting-grounds <region>           # Regional overview
/hunting-grounds --near <system>    # Systems within 5 jumps
```

## Live Activity Intel

**CRITICAL:** For hunting ground analysis, query live activity data.

### Activity Intel Command

```bash
uv run aria-esi activity <system>
```

Returns (public endpoint, no auth):
- **Ship kills** - Player ship losses in last hour
- **Pod kills** - Capsule losses in last hour
- **NPC kills** - Indicates ratting/mission activity (potential marks)
- **Jumps** - Total traffic through system

## Response Format

```
═══════════════════════════════════════════════════════════════════
PARIA HUNTING GROUND ANALYSIS
───────────────────────────────────────────────────────────────────
SYSTEM: Tama (0.3) - The Citadel
VIABILITY: HIGH
───────────────────────────────────────────────────────────────────
LIVE INTEL (last hour):
  Ship kills: 47      Pod kills: 12
  NPC kills: 892      Jumps: 1,247

MARK AVAILABILITY: HIGH
  • Heavy traffic indicates marks passing through
  • NPC kills suggest ratters/mission runners in space

COMPETITION: PRESENT
  • 47 ship kills = active hunters
  • Known groups: Snuffed Out, locals

TACTICAL NOTES:
  • Nourvukaiken gate is primary camp spot
  • Kedama side sees less traffic but cleaner kills
  • Gate guns active on all gates

RECOMMENDATIONS:
  • Off-peak hours for less competition
  • Bring fast tackle - marks are alert here
───────────────────────────────────────────────────────────────────
Your call, Captain.
═══════════════════════════════════════════════════════════════════
```

## Hunting Ground Metrics

### Traffic Analysis

| Jumps (last hour) | Assessment |
|-------------------|------------|
| <50 | Dead - not worth the trip |
| 50-200 | Quiet - patient hunting |
| 200-500 | Moderate - steady traffic |
| 500-1000 | Busy - good mark flow |
| 1000+ | Hot - marks and competition |

### Mark Availability Indicators

| Indicator | Meaning |
|-----------|---------|
| High NPC kills | Ratters/mission runners in space |
| Low ship kills + high jumps | Marks passing through, not hunted |
| Mining anomalies | Potential mining barges |
| Mission agents in system | Mission runner traffic |

### Competition Assessment

| Ship Kills (last hour) | Assessment |
|------------------------|------------|
| 0 | Unclaimed territory |
| 1-10 | Light activity - room for more |
| 10-30 | Active hunting - competition |
| 30+ | Crowded - consider elsewhere |

## System Type Analysis

### Low-Sec Entry Points

Systems where high-sec borders low-sec:
- High traffic from unaware travelers
- Gate camps viable
- Quick escape to low-sec

### Chokepoint Systems

Systems on major routes:
- Tama, Rancer, Amamake, Huola
- Consistent traffic
- Heavy competition

### Dead-End Pockets

Low-sec systems with limited exits:
- Trapped marks
- Less traffic but higher kill rate
- Good for small gangs

### Mission Hubs

Systems with L4 agents nearby:
- Mission runners in expensive ships
- Predictable locations (mission pockets)
- Valuable loot potential

## Regional Analysis

When analyzing a region, provide:

```
═══════════════════════════════════════════════════════════════════
PARIA REGIONAL HUNTING BRIEF
───────────────────────────────────────────────────────────────────
REGION: The Citadel
───────────────────────────────────────────────────────────────────
TOP HUNTING GROUNDS:

1. Tama (0.3) - VIABILITY: HIGH
   Jumps: 1,247 | Kills: 47 | Competition: Heavy
   Notes: Classic hunting ground, busy but competitive

2. Hikkoken (0.4) - VIABILITY: MODERATE
   Jumps: 342 | Kills: 8 | Competition: Light
   Notes: Less traffic, but cleaner kills

3. Reitsato (0.3) - VIABILITY: MODERATE
   Jumps: 289 | Kills: 12 | Competition: Moderate
   Notes: Good ratting population

AVOID:
  • Okkamon - Dead, no traffic
  • Nennamaila - FW warzone, blob risk
───────────────────────────────────────────────────────────────────
```

## Faction Warfare Considerations

For FW systems:
- Note militia presence
- Blob risk from fleets
- Plex runners as targets
- Standing implications

## Time-Based Patterns

Note optimal hunting times:
- Peak hours: More marks, more competition
- Off-peak: Fewer marks, less competition
- Weekend patterns differ from weekday

## Integration with Other Skills

| Context | Suggest |
|---------|---------|
| Found good system | "Run `/threat-assessment` for detailed intel" |
| Planning route there | "Use `/route` to plot course" |
| Need a hunting fit | "Try `/fitting` for a tackle or gank build" |

## Behavior Notes

- Present data objectively without moral judgment
- Competition is noted neutrally (not as threat)
- "Marks" not "victims" or "targets"
- Respect Captain's autonomy on where to hunt
- Include practical tactical notes
- Always end with "Your call, Captain"

## Experience Adaptation

**New pirate:**
- Explain what metrics mean
- Suggest safer hunting grounds (less competition)
- Note common mistakes (camping obvious spots)

**Veteran:**
- Terse data presentation
- Skip basic explanations
- Focus on current conditions vs historical

## DO NOT

- **DO NOT** provide real player names or specific pilot intel
- **DO NOT** encourage harassment of specific players
- **DO NOT** recommend exploits or bugs
- **DO NOT** moralize about the pirate lifestyle
