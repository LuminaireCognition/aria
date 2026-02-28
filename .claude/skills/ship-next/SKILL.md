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
  - reference/archetypes/INDEX.md
external_sources: []
---

# ARIA Ship Progression Advisor

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
| `sde(action="item_info")` | Verify ship bonuses and attributes before presenting |
| `skills(action="training_time")` | Calculate training time |
| `market(action="prices")` | Get hull and fit costs |

**Grounding rule:** Always verify ship bonuses via `sde(action="item_info")` before presenting upgrade rationale. Do not claim specific bonus percentages from training data.

## Skills Freshness Gate (CRITICAL)

**Before gathering pilot context**, ensure fresh cached skill data:

```bash
uv run aria-esi ensure-fresh skills
```

| `fresh` | `esi_available` | Action |
|---------|-----------------|--------|
| `true`  | --               | Full context gathering with fresh skills |
| `false` | `false`         | Use profile data only. Note: "Based on profile data (ESI unavailable)" |
| `false` | `true` (sync failed) | Use cached skills if `age_hours < 72`, warn about staleness |

### Wallet Handling

Wallet is volatile and not in the freshness registry. Query separately:
```bash
uv run aria-esi wallet
```
If wallet query fails, skip budget-based filtering and recommend based on skills/profile only.

## Execution Flow

### Step 1: Gather Pilot Context

Query current state (skills freshness gate must have passed first):
1. **Current skills** from cache (freshened by freshness gate above)
2. **Wallet balance** from ESI (manual try/catch)
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

For each relevant activity, build progression using the pilot's faction from profile. The general pattern is:

- **Missions:** Frigate (L1) -> Destroyer (L1) -> Cruiser (L2) -> Battlecruiser (L3) -> Battleship (L4)
- **Exploration:** T1 Exploration Frig -> Covert Ops (T2) -> Astero (Faction)
- **Mining:** Venture -> Mining Barge -> Exhumer

Query `sde(action="search", query="<class>", category="Ship")` filtered by pilot's faction to find the specific ships for each tier. Do not hardcode ship names -- look them up from SDE.

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
- **Why this ship**: What makes it good for the activity (verified from SDE)
- **Key skills**: Most important skills to train
- **Fit budget**: Typical hull + fit cost (check `reference/archetypes/INDEX.md` for reference fit and use archetype `skill_requirements.required` for readiness calculation)
- **Upgrade path**: What comes after this ship

## Response Format

```
SHIP PROGRESSION: [Current Position]
───────────────────────────────────────────────────────────────────
Current: [Ship or skill level summary]
Wallet: [X]M ISK
Faction: [Primary faction from profile]
───────────────────────────────────────────────────────────────────

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

───────────────────────────────────────────────────────────────────
RECOMMENDED PATH:
  [Current] -> [Next Step] -> [Medium Goal] -> [Long-term Goal]

  Training focus: [Priority skill category]
```

## Budget Awareness

Scale recommendations to wallet. Suggest maintaining 3x replacement cost before upgrading.

## Error Handling

| Scenario | Response |
|----------|----------|
| No skill data | "Cannot determine current skills. Please ensure ESI is connected." |
| Unknown faction | "What faction ships are you interested in? Gallente, Caldari, Amarr, or Minmatar?" |
| No activity specified | Show recommendations for top 2-3 activities based on profile |

## Behavior Notes

- Default to pilot's faction from profile
- Always show at least one "ready now" option if possible
