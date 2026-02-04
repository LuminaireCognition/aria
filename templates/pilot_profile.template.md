# Capsuleer Profile

## Identity

- **Character Name:** [YOUR CHARACTER NAME]
- **Corporation:** [YOUR CORPORATION]
- **Alliance:** [YOUR ALLIANCE OR "None"]
- **Security Status:** [YOUR SEC STATUS, e.g., 0.0]
- **Capsuleer Since:** [JOIN DATE, e.g., YC128.01.14]
- **EVE Experience:** [new/intermediate/veteran]
- **RP Level:** off
<!--
  RP Level controls immersion (default: off - roleplay is opt-in):

  off       = Just the facts. No persona, no formatted boxes, no theater.
  lite      = Minimal flavor. EVE terminology, direct communication.
  moderate  = Light flavor. Some personality, occasional formatted reports.
  full      = Maximum immersion. Faction AI persona, in-universe framing.

  To enable roleplay, change 'off' to your preferred level.
-->
<!--
  EVE Experience affects how ARIA explains things:

  new         = First few months, learning basics
                ARIA provides detailed explanations, defines terms,
                explains mechanics, suggests caution

  intermediate = Comfortable with basics, expanding activities
                 ARIA provides moderate detail, explains advanced concepts

  veteran     = Experienced player, knows mechanics well
                ARIA uses shorthand, assumes knowledge, skips basics

  Leave blank or omit for ARIA to infer from context.
-->

## Faction Alignment

Choose your primary faction. This affects ARIA's persona and cultural expressions.

- **Primary Faction:** [FACTION]
<!--
  === EMPIRE FACTIONS ===
  gallente  : ARIA expresses libertarian values, cultural sophistication, dry wit
  caldari   : ARIA expresses corporate efficiency, honor-focused pragmatism
  minmatar  : ARIA expresses tribal bonds, freedom fighter ethos, direct speech
  amarr     : ARIA expresses religious devotion, imperial dignity, formal address

  === PIRATE FACTIONS (activates PARIA persona) ===
  pirate       : Generic outlaw - radical agency, fatalistic courage, no empire ties
  angel_cartel : Angel-aligned - Minmatar tech focus, Curse region expertise
  serpentis    : Serpentis-aligned - Gallente space ops, drug trade flavor
  guristas     : Guristas-aligned - Caldari corporate targets, sardonic humor
  blood_raiders: Blood Raider-aligned - Amarr space, darker tone
  sanshas_nation: Sansha-aligned - Colder, mechanical, "unity" themes

  Pirate factions activate PARIA instead of ARIA. PARIA addresses you as "Captain,"
  sources intel from underworld networks, and embraces the outlaw philosophy:
  "A merry life and a short one." See personas/paria/voice.md for details.
-->

- **Mission Provider:** [YOUR PRIMARY MISSION CORP OR "None"]
<!--
  Empire examples: Federation Navy, Caldari Navy, Republic Fleet, Imperial Navy
  Pirate examples: Guardian Angels, Serpentis Corporation, Guristas, None
-->

- **Hostile Factions:** [FACTIONS YOU FIGHT AGAINST]
- **Target Factions:** [PRIMARY ENEMIES]
<!-- For pirates, this might be empire navies or rival pirate factions -->

## Operational Philosophy

<!-- DELETE ONE OF THESE SECTIONS based on your playstyle -->

<!-- === OPTION A: SELF-SUFFICIENCY MODE === -->
<!-- Use this if you want to challenge yourself with market restrictions -->
Self-imposed market restriction - **Challenge Mode: Self-Sufficiency**

| Transaction Type | Permitted | Notes |
|------------------|-----------|-------|
| Player market orders | **NO** | Cannot buy/sell with other players |
| Contracts | **NO** | No contract usage of any kind |
| NPC-seeded BPOs | **YES** | Blueprint Originals from NPC stations |
| NPC-seeded Skillbooks | **YES** | From NPC stations |
| LP Store | **YES** | Faction items, implants, special modules |
| Loot/Drops | **YES** | Keep what you kill/hack |
| Mission Rewards | **YES** | ISK, LP, items, standings |
| Manufacturing | **YES** | Core gameplay loop |

This is a deliberate choice to experience New Eden through self-sufficiency.

## Operational Constraints
<!-- ARIA Economic Advisory Protocol reads this section for validation -->
<!-- Format: constraint_name: true/false -->

```yaml
market_trading: false      # Cannot buy/sell on player market
contracts: false           # No contract usage
fleet_required: false      # Solo play preferred
security_preference: 0.5   # Minimum system security (highsec)
```

### ISK Generation Implications
Activities that generate ISK for this pilot MUST use one of:
- Direct mission rewards (ISK payment)
- NPC bounties (rat kills)
- NPC buy orders (Overseer Effects, specific trade goods)
- LP store → personal use items (not ISK, but value)

Activities that do NOT generate ISK for this pilot:
- Exploration loot (requires market to monetize)
- Abyssal loot (requires market to monetize)
- Any item drops without NPC buy orders
- PI products (requires market to monetize)
<!-- === END OPTION A === -->

<!-- === OPTION B: STANDARD PLAYSTYLE === -->
<!-- Use this for normal gameplay with full market access -->
<!--
Standard gameplay - full market access enabled.

| Transaction Type | Permitted | Notes |
|------------------|-----------|-------|
| Player market orders | **YES** | Full market access |
| Contracts | **YES** | Contracts available |
| NPC-seeded BPOs | **YES** | Blueprint Originals from NPC stations |
| NPC-seeded Skillbooks | **YES** | From NPC stations |
| LP Store | **YES** | Faction items, implants, special modules |
| Loot/Drops | **YES** | Keep what you kill/hack |
| Mission Rewards | **YES** | ISK, LP, items, standings |
| Manufacturing | **YES** | Available |

## Operational Constraints

```yaml
market_trading: true       # Full market access
contracts: true            # Contracts available
fleet_required: false      # Solo or fleet
security_preference: 0.5   # Minimum system security
```
-->
<!-- === END OPTION B === -->

<!-- === OPTION C: OUTLAW PLAYSTYLE === -->
<!-- Use this for pirate/criminal gameplay -->
<!--
Outlaw operations - **The Rogue's Life**

| Activity | Approach | Notes |
|----------|----------|-------|
| PvP | **Primary** | Ganking, gate camps, wardecs |
| Low/Null-sec | **Preferred** | Where the real ISK is |
| Ransoming | **YES** | Honor your terms - reputation matters |
| Mission Running | **Optional** | Pirate faction missions if aligned |
| Market | **YES** | Loot must be fenced |
| Empire Space | **Careful** | Sec status may restrict access |

"A merry life and a short one, Captain."

## Operational Constraints

```yaml
market_trading: true       # Need to fence loot
contracts: true            # Ransom payments, etc.
fleet_required: false      # Solo or gang
security_preference: -1.0  # Low/null preferred, empire when needed
pvp_focus: true            # Primary activity
```

### Security Status Implications
Activities that tank sec status:
- Pod kills in low-sec
- Ship kills in high-sec (criminal timer)
- Attacking without war rights

Sec status recovery options:
- Clone soldier tags (requires ISK)
- Ratting in null-sec (slow)
- Just embrace it and stay in low/null
-->
<!-- === END OPTION C === -->

## Standings

### Empire Factions

| Faction | Standing | Relation |
|---------|----------|----------|
| Gallente Federation | 0.00 | Neutral |
| Caldari State | 0.00 | Neutral |
| Minmatar Republic | 0.00 | Neutral |
| Amarr Empire | 0.00 | Neutral |

### Mission Corporations

| Corporation | Standing | Access |
|-------------|----------|--------|
| [Your mission corp] | 0.00 | L1 Missions |

### Pirate Factions

| Faction | Standing | Notes |
|---------|----------|-------|
| Serpentis | 0.00 | [If in Gallente space] |
| Guristas Pirates | 0.00 | [If in Caldari space] |
| Angel Cartel | 0.00 | [If in Minmatar space] |
| Blood Raiders | 0.00 | [If in Amarr space] |
| Sansha's Nation | 0.00 | [Incursion runners] |

<!--
  === FOR PIRATE-ALIGNED PILOTS ===
  If your Primary Faction is a pirate faction, you may have POSITIVE standings
  with one pirate group and NEGATIVE with empires. Flip the tables accordingly.

  Example for Angel Cartel pilot:
  | Angel Cartel | 3.50 | Allied - mission provider |
  | Gallente Federation | -2.10 | Hostile |
-->

## Primary Activities

<!-- Rank your main activities, 1 = highest priority -->
1. [Activity, e.g., Mission Running]
2. [Activity, e.g., Mining]
3. [Activity, e.g., Exploration]
<!--
  === PIRATE ACTIVITY EXAMPLES ===
  - Gate camping
  - Low-sec roaming
  - Wardec hunting
  - Suicide ganking
  - Ransoming
  - Pirate faction missions
  - Null-sec ratting
  - Wormhole diving
-->

## Skill Focus

<!-- Update as you train -->
- [ ] [Skill category 1]
- [ ] [Skill category 2]
- [ ] [Skill category 3]

## Notable Achievements

<!-- ARIA will reference these in conversation -->
- [Achievement 1]

## Current Goals

<!-- What are you working toward? -->
- [Goal 1]
- [Goal 2]
