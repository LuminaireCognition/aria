---
name: ship-next
description: Ship progression advisor for new and intermediate pilots. Recommends your next ship based on current skills, wallet, and preferred activities.
model: haiku
category: tactical
triggers:
  - "/ship-next"
  - "what ship should I fly next"
  - "next ship recommendation"
  - "ship progression"
  - "what to train after [ship]"
  - "upgrade from [ship]"
  - "what ship for [activity]"
requires_pilot: true
esi_scopes:
  - esi-skills.read_skills.v1
  - esi-wallet.read_character_wallet.v1
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/operations.md
  - reference/archetypes/hulls/**/*.yaml
external_sources: []
---

# ARIA Ship Progression Advisor

## Purpose

Answer the #1 question from new EVE players: "What ship should I fly next?"

This skill provides personalized ship recommendations based on:
- Current skills (what can you fly soon?)
- Wallet (what can you afford?)
- Activity preference (what do you want to do?)
- Faction alignment (stay in your skill tree or branch out?)

## Target Audience

- **New players** (0-1 month): Completing Career Agents, first ship upgrade
- **Early intermediate** (1-3 months): Moving from frigates to cruisers
- **Mid intermediate** (3-6 months): Battlecruisers, battleships, or specialization

## Command Syntax

```
/ship-next                           # General recommendation
/ship-next missions                  # For mission running
/ship-next exploration               # For exploration
/ship-next mining                    # For mining
/ship-next --from Tristan            # Upgrade from specific ship
/ship-next --faction gallente        # Stay within faction
/ship-next --budget 50m              # Maximum budget
```

## MCP Tools Required

| Tool | Purpose |
|------|---------|
| `sde(action="skill_requirements")` | Get skills needed for ships |
| `skills(action="training_time")` | Calculate training time |
| `market(action="prices")` | Get hull and fit costs |
| `sde(action="item_info")` | Get ship attributes and bonuses |

**ESI queries (when available):**
- Skills: `uv run aria-esi skills`
- Wallet: `uv run aria-esi wallet`

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi` commands - they will timeout
2. **USE** profile data instead:
   - `userdata/pilots/{active_pilot}/profile.md` contains cached standings, goals, module tier
   - `userdata/pilots/{active_pilot}/operations.md` contains current ships
3. **ANSWER IMMEDIATELY** from cached data
4. **NOTE** in response: "Based on profile data (ESI unavailable)"

### If ESI is AVAILABLE:

Proceed with live queries for most accurate data.

**Rationale:** A fast answer from slightly stale profile data is infinitely better than a 5-minute timeout. Players will rage-quit before waiting for failed ESI calls.

## Execution Flow

### Step 1: Gather Pilot Context

Query current state:
1. **Current skills** from ESI
2. **Wallet balance** from ESI
3. **Profile** for faction preference, activity focus
4. **Operations** for current ships owned

### Step 2: Determine Current Position

Based on pilot skills, identify their "tier":

| Tier | Indicators | Typical Ships |
|------|------------|---------------|
| Starter | < 1M SP, Frigate skills III | Career Agent ships |
| Early | 1-3M SP, Cruiser skills I-II | T1 Frigates, Destroyers |
| Developing | 3-8M SP, Cruiser skills III-IV | T1 Cruisers |
| Intermediate | 8-15M SP, BC/BS skills III | Battlecruisers |
| Established | 15M+ SP, BS skills IV+ | Battleships, T2 ships |

### Step 3: Generate Recommendations by Activity

For each relevant activity, generate a recommendation:

#### Mission Running Path

```
Frigate (L1) → Destroyer (L1) → Cruiser (L2) → Battlecruiser (L3) → Battleship (L4)
```

Faction-specific paths:

| Faction | Frigate | Destroyer | Cruiser | Battlecruiser | Battleship |
|---------|---------|-----------|---------|---------------|------------|
| Gallente | Tristan | Algos | Vexor | Myrmidon | Dominix |
| Caldari | Kestrel | Cormorant | Caracal | Drake | Raven |
| Amarr | Punisher | Coercer | Omen | Harbinger | Apocalypse |
| Minmatar | Rifter | Thrasher | Rupture | Hurricane | Maelstrom |

#### Exploration Path

```
T1 Exploration Frig → Covert Ops (T2) → Astero (Faction)
```

| Faction | T1 Explorer | Covert Ops |
|---------|-------------|------------|
| Gallente | Imicus | Helios |
| Caldari | Heron | Buzzard |
| Amarr | Magnate | Anathema |
| Minmatar | Probe | Cheetah |

#### Mining Path

```
Venture → Mining Barge → Exhumer
```

Barges: Procurer (tank) → Retriever (yield) → Covetor (fleet)

### Step 4: Calculate Readiness

For each recommended ship:

1. **Skill check**: `sde(action="skill_requirements", item="Ship Name")`
2. **Training time**: `skills(action="training_time", skill_list=[...])`
3. **Cost estimate**: `market(action="prices", items=["Ship Name"])`

Categorize recommendations:

| Category | Definition |
|----------|------------|
| **Ready Now** | Can fly today, can afford hull + basic fit |
| **Train < 1 week** | Minor skill training, affordable |
| **Train < 1 month** | Moderate training, good milestone |
| **Aspirational** | Long-term goal, major investment |

### Step 5: Add Context for Each Ship

For each recommendation, provide:
- **Why this ship**: What makes it good for the activity
- **Key skills**: Most important skills to train
- **Fit budget**: Typical hull + fit cost
- **Upgrade path**: What comes after this ship

## Response Format

```
═══════════════════════════════════════════════════════════════════════════════
SHIP PROGRESSION: [Current Position]
───────────────────────────────────────────────────────────────────────────────
Current: [Ship or skill level summary]
Wallet: [X]M ISK
Faction: [Primary faction from profile]
───────────────────────────────────────────────────────────────────────────────

FOR [ACTIVITY] ([Current Capability]):

READY NOW:
  [Ship Name] ([Class])                        Hull: [X]M | Fit: ~[X]M
  Why: [Brief explanation of ship strengths]
  Key skills: [Primary skill] at [level]

TRAIN [X DAYS]:
  [Ship Name] ([Class])                        Hull: [X]M | Fit: ~[X]M
  Why: [Brief explanation]
  Train: [Skill] to [Level] ([time])

ASPIRATIONAL ([X WEEKS]):
  [Ship Name] ([Class/Faction])                Hull: [X]M | Fit: ~[X]M
  Why: [Brief explanation - why it's worth the wait]
  Unlocks: [What this enables]

───────────────────────────────────────────────────────────────────────────────
RECOMMENDED PATH:
  [Current] → [Next Step] → [Medium Goal] → [Long-term Goal]

  Training focus: [Priority skill category]
═══════════════════════════════════════════════════════════════════════════════
```

## Ship Database

### Mission Running Ships (by effectiveness at level)

| Level | Budget Option | Recommended | Premium |
|-------|---------------|-------------|---------|
| L1 | Starter frigate | Tristan/Kestrel | Navy variant |
| L2 | T1 Cruiser | Vexor/Caracal | Navy cruiser |
| L3 | T1 Battlecruiser | Drake/Myrmidon | Navy BC |
| L4 | T1 Battleship | Dominix/Raven | Marauder |

### Exploration Ships

| Tier | Ship | Notes |
|------|------|-------|
| Entry | Heron/Imicus | Free from Career Agents |
| Budget | T1 Explorer | ~1M hull, 5M fit |
| Intermediate | Astero | Faction, ~80M, can fight |
| Advanced | Covert Ops | T2, can cloak warp |

### Mining Ships

| Tier | Ship | Yield | Tank | Notes |
|------|------|-------|------|-------|
| Entry | Venture | Low | None | Free from Career Agents |
| Barge | Procurer | Medium | High | Safe for highsec |
| Barge | Retriever | High | Low | Max yield, riskier |
| Barge | Covetor | Highest | None | Fleet only |

## Activity-Specific Guidance

### For "I want to do L2 missions"

```
Your drone skills suggest Gallente path.

RECOMMENDED: Vexor
  Hull: 8M | Full fit: ~20M
  Why:
    - Your Drones IV transfers directly
    - Passive tank handles L2 content
    - Can scale to L3 with same skills

  Train: Gallente Cruiser III (4h if you have Frigate III)

ALTERNATIVE: Caracal (if you prefer missiles)
  Hull: 10M | Full fit: ~18M
  Why: Good range, easier to kite
  Train: Caldari Cruiser III (need Caldari Frigate first)
```

### For "I'm in a Vexor, what's next?"

```
Natural progression from Vexor:

SAME ACTIVITY (L3 missions):
  Myrmidon (Battlecruiser)
    Hull: 45M | Fit: ~60M total
    Train: Battlecruisers III (8d from scratch)
    Why: More drones (5 heavies), more tank, same skills

SAME ROLE (drone boat upgrade):
  Vexor Navy Issue (Faction Cruiser)
    Hull: 80M | Fit: ~100M total
    Train: None - same skills as Vexor
    Why: +50% drone damage, better tank
    Note: Skip this if going to Myrmidon anyway

LONG TERM (L4 missions):
  Dominix (Battleship)
    Hull: 200M | Fit: ~300M total
    Train: Gallente Battleship III (28d)
    Why: King of drone boats, handles L4s comfortably
```

## Skill Transfer Awareness

When recommending cross-faction ships, note skill overlap:

```
Your Caldari skills (Missiles, Shields) also help with:
  - Minmatar ships (shield-tanked variants)
  - Some Gallente ships (Ishtar uses shields sometimes)

Your Gallente skills (Drones, Armor) also help with:
  - Amarr ships (armor tank)
  - All factions use drones as secondary
```

## Budget Awareness

Adjust recommendations based on wallet:

| Wallet | Recommendation Style |
|--------|---------------------|
| < 10M | Stick with T1 frigates/destroyers, emphasize free ships |
| 10-50M | T1 cruisers affordable, suggest earning more before BC |
| 50-150M | Battlecruisers feasible, consider faction cruiser |
| 150M+ | Can afford battleship progression |

**Always suggest maintaining 3x replacement cost.**

## Error Handling

| Scenario | Response |
|----------|----------|
| No skill data | "Cannot determine current skills. Please ensure ESI is connected." |
| Unknown faction | "What faction ships are you interested in? Gallente, Caldari, Amarr, or Minmatar?" |
| No activity specified | Show recommendations for top 2-3 activities based on profile |

## Integration with Other Skills

| After ship-next | Suggest |
|-----------------|---------|
| Ship recommended | "Use `/fit-check` to validate a specific fit" |
| Long training identified | "Check `/skillplan` for optimal training order" |
| Budget concerns | "Run `/isk-compare` to find efficient ISK sources" |
| Ship chosen | "Try `/fitting` for a recommended fit" |

## Veteran-Endorsed Wisdom

Include practical wisdom that veterans wish they knew:

- "Vexor → VNI → Dominix is the classic drone path"
- "Drake is boring but incredibly forgiving for new pilots"
- "Don't skip cruisers - they teach skills you'll need in bigger ships"
- "Faction cruisers are often better ISK/performance than T1 battleships"
- "Train your support skills (capacitor, tank, navigation) alongside ship skills"

## Archetype Integration

When available, reference existing archetypes:
```
reference/archetypes/hulls/{class}/{ship}/manifest.yaml
```

These contain:
- Validated fits for each tier
- Engagement profiles
- Slot layouts
- Role classifications

## Behavior Notes

- Default to pilot's faction from profile
- Always show at least one "ready now" option if possible
- Include one aspirational goal to keep pilots motivated
- Be honest about time investments ("this takes 28 days")
- Emphasize that skills transfer - nothing is wasted
