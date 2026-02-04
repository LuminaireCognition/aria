# Beginner-Intermediate Features Implementation Review

**Date:** 2026-02-03
**Author:** ARIA Development
**Status:** Implemented

## Summary

Implemented 5 high-leverage features targeting beginner to intermediate EVE Online pilots (T1/T2/faction ships, frigate to battleship, plus barges). These features address the most common pain points identified from new player questions and veteran feedback.

## Target Audience

| Stage | Timeline | Typical Activities |
|-------|----------|-------------------|
| New players | First month | Career Agents → L2 missions, exploration basics |
| Early intermediate | Months 2-3 | L3 missions, first cruiser/battlecruiser |
| Mid intermediate | Months 3-6 | L4 missions, battleships, T2 consideration |

**Ship scope:** Frigates, destroyers, cruisers, battlecruisers, battleships, mining barges
**Hull types:** T1 (primary), meta/faction (common upgrades), T2 (aspirational)

---

## Implemented Features

### 1. `/fit-check` - Fit Validation

**Location:** `.claude/skills/fit-check/SKILL.md`

**Problem solved:** New players copy fits from the internet, buy the ship, then discover they can't use half the modules. They also don't calculate total cost until checkout.

**What it does:**
- Paste any EFT fit for comprehensive analysis
- Checks pilot skills against fit requirements
- Shows which modules can be used (X/Y = Z%)
- Calculates training time for missing skills
- Suggests T1/meta substitutions for unflyable modules
- Calculates total fit cost and compares to wallet
- Warns if below 3x replacement cost buffer

**Example output:**
```
SKILL REQUIREMENTS:
  Medium Drone Operation V     [MISSING] You have III - train 6d 4h
  Mechanics V                  [MISSING] You have IV - train 4d 9h

  You can fly 8/11 modules (73%)

SUBSTITUTION SUGGESTIONS:
  Hammerhead II → Hammerhead I (you can use now, -15% DPS)

COST BREAKDOWN:
  TOTAL:    37.0M
  Replacements affordable: 1.2x
  ⚠️ WARNING: Below 3x replacement cost.
```

**MCP tools used:** `fitting(check_requirements)`, `fitting(extract_requirements)`, `market(valuation)`, `sde(meta_variants)`, `skills(training_time)`

---

### 2. `/ship-next` - Ship Progression Advisor

**Location:** `.claude/skills/ship-next/SKILL.md`

**Problem solved:** "What ship should I fly next?" is the #1 question from new players. They complete Career Agents in a frigate and have no clear path forward.

**What it does:**
- Analyzes current skills and wallet
- Recommends ships by activity (missions, exploration, mining)
- Shows "ready now", "train X days", and "aspirational" options
- Explains why each ship is recommended
- Shows natural progression paths (e.g., Vexor → Myrmidon → Dominix)
- Estimates hull + fit costs

**Example output:**
```
FOR L2 MISSIONS:

READY NOW:
  Vexor (Cruiser)                        Hull: 8M | Fit: ~15M
  Why: Your drone skills transfer directly. Can passive tank L2s.

TRAIN 8 DAYS:
  Myrmidon (Battlecruiser)               Hull: 45M | Fit: ~60M
  Train: Battlecruisers III (8d)
  Why: Natural upgrade, same drone skills

RECOMMENDED PATH:
  Tristan → Vexor → Myrmidon → Dominix
```

**Integrates with:** Existing archetypes at `reference/archetypes/hulls/`

---

### 3. `/fit-budget` - Budget Fit Generator

**Location:** `.claude/skills/fit-budget/SKILL.md`

**Problem solved:** All public fits assume T2 skills. New players need "the same fit but with modules I can actually use" automatically generated.

**What it does:**
- Takes any EFT fit and downgrades to match pilot skills
- Optionally targets a budget
- Shows exact substitutions with stat differences
- Calculates performance comparison (DPS, EHP, tank)
- Maintains fit's core purpose (doesn't mix tank types)
- Provides verdict on what content the budget fit can handle

**Example output:**
```
SUBSTITUTIONS:
  Drone Damage Amp II → 'Basic' DDA | -8% damage | Save 3.2M
  Medium Armor Rep II → Prototype Repair | -10% rep | Save 1.1M

PERFORMANCE COMPARISON:
                    Original    Budget    Difference
  DPS:              412         328       -20%
  EHP:              18,200      16,100    -12%

COST:  37M → 18.5M (-50%)

VERDICT: Budget fit handles L2 missions comfortably.
```

---

### 4. `/isk-compare` - Activity ISK/Hour Comparison

**Location:** `.claude/skills/isk-compare/SKILL.md`

**Problem solved:** "Should I do missions or mining or exploration?" Players waste time on inefficient activities because they don't know the math.

**What it does:**
- Shows ISK/hour estimates for activities pilot can do
- Checks skills and standings for activity access
- Shows what's locked and what to train for unlock
- Includes variance warnings (exploration is gambling)
- Recommends passive income options (PI often overlooked)
- Provides practical recommendations based on pilot state

**Reference data:** Created `reference/activities/isk_estimates.yaml` with baseline estimates

**Example output:**
```
MISSION RUNNING:
  L2 Security (Vexor)         4-8M/hr     [You can do this]
  L3 Security (Drake)         8-15M/hr    [Needs: Battlecruisers III - 8d]
  L4 Security (Dominix)       15-30M/hr   [Needs: BS III + 5.0 standing]

MINING:
  Venture (Veldspar)          2-3M/hr     [You can do this]
  Retriever (Scordite)        6-10M/hr    [Needs: Mining Barge III - 4d]

RECOMMENDATION:
Your best active ISK right now: L2 Security Missions (4-8M/hr)
Consider setting up PI for passive income (8-15M/day).
```

---

### 5. `/standings-plan` - Standings Progression Planner

**Location:** `.claude/skills/standings-plan/SKILL.md`

**Problem solved:** Standings are deeply confusing. Players don't understand they need 5.0 standing for L4 agents or how long it takes to get there.

**What it does:**
- Shows current standings (raw and effective with skill bonuses)
- Shows agent access at each level
- Calculates gap to target standing
- Provides phased progression plan with time estimates
- Lists accelerators (epic arcs, data centers, Connections skill)
- Warns about faction warfare implications

**Example output:**
```
CURRENT STATUS:
  Federation Navy:    2.34 raw → 3.68 effective
  Connections:        V (+20% bonus)

AGENT ACCESS:
  L3 Agents: ✓ Available
  L4 Agents: ✗ Locked (need 5.0, you have 3.68)

PROGRESSION PATH:

PHASE 1: 3.68 → 5.0 (Est. 15 hours)
  Run L3 missions for Federation Navy
  ~50 missions to reach 5.0 effective
  Tip: Every 16 missions triggers a storyline (faction standing!)

ACCELERATORS:
  - Epic Arc: Blood-Stained Stars (every 90 days)
  - Data Center Tags (one-time boost)
```

---

## Implementation Details

### Files Created

| File | Purpose |
|------|---------|
| `.claude/skills/fit-check/SKILL.md` | Fit validation skill |
| `.claude/skills/ship-next/SKILL.md` | Ship progression advisor |
| `.claude/skills/fit-budget/SKILL.md` | Budget fit generator |
| `.claude/skills/isk-compare/SKILL.md` | ISK/hour comparison |
| `.claude/skills/standings-plan/SKILL.md` | Standings progression planner |
| `reference/activities/isk_estimates.yaml` | ISK/hour reference data |

### Skill Index Update

Regenerated `.claude/skills/_index.json`:
- Previous skill count: 44
- New skill count: 49
- New triggers mapped: 307 (was ~248)

### New Triggers Added

| Skill | Key Triggers |
|-------|--------------|
| `/fit-check` | "can I fly this fit", "check this fit", "fit requirements" |
| `/ship-next` | "what ship should I fly next", "ship progression", "upgrade from [ship]" |
| `/fit-budget` | "budget version of this fit", "make this fit cheaper", "T1 version" |
| `/isk-compare` | "best way to make ISK", "ISK per hour", "what should I do for money" |
| `/standings-plan` | "how to get L4 agents", "path to 5.0 standing", "standings grind" |

---

## Integration Points

### Cross-Skill Suggestions

Each skill suggests related skills at the end:

| Skill | Suggests |
|-------|----------|
| `/fit-check` | `/skillplan`, `/fit-budget`, `/fitting` |
| `/ship-next` | `/fit-check`, `/skillplan`, `/fitting` |
| `/fit-budget` | `/fit-check`, `/skillplan`, `/isk-compare` |
| `/isk-compare` | `/standings`, `/exploration`, `/mining-advisory`, `/pi`, `/ship-next` |
| `/standings-plan` | `/standings`, `/agent-search`, `/isk-compare`, `/mission-brief` |

### MCP Dependencies

All skills use the existing MCP dispatchers:
- `fitting()` - Fit validation and stats
- `sde()` - Skill requirements, meta variants
- `skills()` - Training time calculations
- `market()` - Price lookups, valuation

### ESI Integration

Skills requiring live data query ESI via CLI:
- `uv run aria-esi skills` - Current skill levels
- `uv run aria-esi wallet` - Wallet balance
- `uv run aria-esi standings` - Current standings

---

## Veteran Wisdom Included

Each skill includes practical advice veterans wish they knew:

- "Vexor → VNI → Dominix is the classic drone path"
- "Drake is boring but incredibly forgiving for new pilots"
- "Don't skip cruisers - they teach skills you'll need in bigger ships"
- "Meta 4 modules are often 80% as good for 20% of the price"
- "Train Connections V - it's the best passive standing boost"
- "Epic arcs don't cause derived standing losses to enemy factions"
- "I mined for a month in a Venture when I could have been running L2s"

---

## Verification Checklist

- [x] All 5 skills created with proper YAML frontmatter
- [x] Skill index regenerated successfully (49 skills)
- [x] Reference data created (`isk_estimates.yaml`)
- [x] Triggers mapped to new skills
- [x] MCP tool usage documented
- [x] ESI integration documented
- [x] Cross-skill suggestions included
- [x] Response format examples provided
- [x] Error handling documented

---

## Future Enhancements

Potential improvements for future iterations:

1. **Skill overlay support** - Add persona-specific variants for these skills
2. **Progress tracking** - Remember pilot's stated goals for follow-up
3. **Fit database** - Cache commonly validated fits for quick reference
4. **ISK tracking** - Integrate with wallet journal to show actual ISK/hour achieved
5. **Standing history** - Track standing progression over time

---

## Post-Implementation Fix: ESI Fallback Behavior

**Issue identified:** Initial implementation would timeout for 5+ minutes when ESI was unavailable, waiting on failed `uv run aria-esi` commands.

**Root cause:** Skills queried ESI without checking availability status from session hook.

**Fix applied:** All 5 skills now include:

1. **ESI availability check** - Read session hook status before any ESI calls
2. **Profile-based fallback** - Use cached profile data when ESI unavailable
3. **Immediate response** - Never block on failed services
4. **Degraded mode notes** - Inform user of data source

```markdown
## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output:
"esi": {"status": "UNAVAILABLE"}

If unavailable: Use profile data, answer immediately, note data source.
```

**Lesson learned:** A fast answer from slightly stale data beats a perfect answer that never arrives. Players will rage-quit before waiting 5 minutes.

---

## Conclusion

These 5 features address the core questions new and intermediate players ask most frequently. They leverage ARIA's existing infrastructure (MCP tools, ESI integration, reference data) while providing actionable, personalized guidance.

The features are designed to:
- Prevent wasted time and ISK (fit-check before buying)
- Provide clear progression paths (ship-next)
- Make expensive fits accessible (fit-budget)
- Guide efficient ISK earning (isk-compare)
- Demystify standings (standings-plan)
- **Respond quickly** even when ESI is unavailable (fallback behavior)
