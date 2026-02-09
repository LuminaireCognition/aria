---
name: fit-check
description: Validate if you can fly a ship fit (skill check) and afford it (cost check). Paste any EFT fit for comprehensive analysis with substitution suggestions.
model: haiku
category: tactical
triggers:
  - "/fit-check"
  - "can I fly this fit"
  - "check this fit"
  - "fit requirements"
  - "can I afford this fit"
  - "what skills do I need for this fit"
  - "validate fit"
requires_pilot: true
esi_scopes:
  - esi-skills.read_skills.v1
  - esi-wallet.read_character_wallet.v1
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
external_sources: []
---

# ARIA Fit Check Module

## Purpose

Provide comprehensive fit validation that answers two questions new players always ask:
1. **Can I fly this?** - Check if pilot has the skills to use all modules
2. **Can I afford this?** - Calculate total cost and compare to wallet

Additionally suggests substitutions for modules the pilot can't use yet.

## Target Audience

New and intermediate pilots who:
- Copy fits from the internet without knowing if they can use them
- Don't want to buy a ship only to find they can't fit half the modules
- Need to know the total cost before committing ISK

## Command Syntax

```
/fit-check                     # Prompts for EFT paste
/fit-check [EFT block]         # Direct analysis
```

## MCP Tools Required

| Tool | Purpose |
|------|---------|
| `fitting(action="check_requirements")` | Check pilot skills against fit requirements |
| `fitting(action="extract_requirements")` | Get all skill requirements from fit |
| `market(action="valuation")` | Calculate total fit cost |
| `sde(action="meta_variants")` | Find substitutes for unflyable modules |
| `sde(action="skill_requirements")` | Get skill tree for problematic modules |
| `skills(action="training_time")` | Calculate time to train missing skills |

**ESI queries (when available):**
- Current skills: `uv run aria-esi skills`
- Wallet balance: `uv run aria-esi wallet`

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi` commands - they will timeout
2. **USE** profile data for context:
   - `module_tier` from profile tells you T1/T2 capability
   - Skip wallet comparison (just show cost breakdown)
3. **STILL VALIDATE** the fit via MCP tools (fitting, sde, market work without ESI)
4. **ANSWER IMMEDIATELY** with partial analysis
5. **NOTE** in response: "Skill check unavailable (ESI offline) - showing cost analysis only"

### If ESI is AVAILABLE:

Proceed with full skill + wallet validation.

### Degraded Mode Output

When ESI unavailable, still provide value:
- Cost breakdown (market tools work)
- Fit validation via EOS (fitting tools work)
- Module list and slot assignments
- Skip: skill check, wallet comparison, training time

**Rationale:** Partial information now beats complete information never. A cost breakdown alone is still useful.

## Execution Flow

### Step 1: Parse EFT Input

Accept fit in standard EFT format:
```
[Ship Name, Fit Name]
Low Slot Module 1
...

Mid Slot Module 1
...

High Slot Module 1
...

Rig 1
...

Drone Name x5
```

If no EFT provided, prompt user to paste their fit.

### Step 2: Extract Requirements

Call `fitting(action="extract_requirements", eft="...")`:

Returns:
- `skills`: List of "Skill Name Level" strings
- `skill_ids`: Dict mapping skill_id to required level
- `total_skills`: Count of unique skills required

### Step 3: Check Against Pilot Skills

Call `fitting(action="check_requirements", eft="...", pilot_skills={...})`:

**Getting pilot skills:**
```bash
uv run aria-esi skills
```

Returns skills as `{skill_id: level}` dict.

**check_requirements returns:**
- `can_fly`: bool - True if pilot meets ALL requirements
- `missing_skills`: List of `{skill_id, skill_name, required, current}`
- `total_skills_checked`: int

### Step 4: Calculate Training Time for Missing Skills

For each missing skill, call:
```
skills(action="training_time", skill_list=[
  {"skill_name": "Medium Drone Operation", "from_level": 3, "to_level": 5}
])
```

Sum total training time for all missing skills.

### Step 5: Find Substitutions

For modules requiring skills the pilot doesn't have, find alternatives:

```
sde(action="meta_variants", item="Hammerhead II")
```

Returns meta variants (T1, faction, etc.) that may have lower requirements.

For each variant, check skill requirements and suggest the best option the pilot CAN use.

### Step 6: Calculate Fit Cost

Call `market(action="valuation", items=[...], price_type="sell", region="jita")`:

**Build items list from EFT:**
```json
[
  {"name": "Vexor", "quantity": 1},
  {"name": "Drone Damage Amplifier II", "quantity": 3},
  {"name": "Hammerhead II", "quantity": 5},
  ...
]
```

Returns:
- `total_value`: Total ISK
- `items`: Breakdown by item with individual prices
- `missing_items`: Items not found in market data

### Step 7: Get Wallet Balance

```bash
uv run aria-esi wallet
```

Compare wallet to fit cost.

### Step 8: Generate Replacement Cost Analysis

Calculate how many times the pilot can afford to lose this ship:
- `replacement_count = wallet / total_cost`
- Warn if below 3x (not enough buffer for losses)

## Response Format

```
═══════════════════════════════════════════════════════════════════════════════
FIT CHECK: [Ship] - [Fit Name]
───────────────────────────────────────────────────────────────────────────────

SKILL REQUIREMENTS
  [Skill Name] [Level]         [OK] You have [X]
  [Skill Name] [Level]         [MISSING] You have [X] - train [time]
  ...

  You can fly [X]/[Y] modules ([Z]%)

SUBSTITUTION SUGGESTIONS
  [T2 Module Name] → [T1/Meta Alternative] (you can use now, [stat diff])
  ...

COST BREAKDOWN
  Hull:     [X]M
  Highs:    [X]M
  Mids:     [X]M
  Lows:     [X]M
  Rigs:     [X]M
  Drones:   [X]M
  ─────────────────
  TOTAL:    [X]M

  Your wallet: [X]M
  After purchase: [X]M remaining
  Replacements affordable: [X]x

  [WARNING if < 3x replacement cost]
═══════════════════════════════════════════════════════════════════════════════
```

## Skill Check Logic

### Can Fly Module?

A pilot can use a module if they have ALL required skills at the required levels.

```python
def can_use_module(module_reqs, pilot_skills):
    for skill_id, required_level in module_reqs.items():
        if pilot_skills.get(skill_id, 0) < required_level:
            return False
    return True
```

### Flyability Percentage

```python
flyable_modules = sum(1 for m in modules if can_use_module(m.reqs, pilot_skills))
flyability_pct = flyable_modules / total_modules * 100
```

## Substitution Strategy

When finding substitutions for modules the pilot can't use:

1. **Get meta variants** via `sde(action="meta_variants", item="...")`
2. **Check each variant's requirements** against pilot skills
3. **Prefer** (in order):
   - Meta 4 (compact, enduring) - best stats among T1
   - Faction (if affordable) - often fewer skill requirements
   - Meta 1-3 (if nothing else fits)
   - T1 base (last resort)
4. **Show stat difference** compared to original module

### Substitution Display

```
Hammerhead II → Hammerhead I (you can use now, -15% DPS)
Medium Armor Repairer II → 'Meditation' Med Armor Rep (you can use now, -10% rep)
```

## Cost Analysis Logic

### Replacement Cost Rule

Industry-standard guidance: maintain 3x replacement cost minimum.

```python
replacements = wallet / total_cost
if replacements < 3:
    warning = "WARNING: Below 3x replacement cost. Consider budget fit or earn more ISK first."
elif replacements < 5:
    note = "Comfortable buffer. 5+ replacements recommended for PvP."
else:
    note = "Healthy ISK buffer for this hull."
```

### Cost Categories

Group costs by slot type for clarity:
- **Hull**: Ship itself
- **Highs**: High slot modules
- **Mids**: Mid slot modules
- **Lows**: Low slot modules
- **Rigs**: Rig modules
- **Drones**: All drones
- **Charges**: Ammo, scripts, cap boosters (if included)

## Error Handling

| Error | Response |
|-------|----------|
| Invalid EFT format | "Please paste a valid EFT format fit. Example: [Ship, Name]..." |
| Unknown module | "Module '[name]' not found. Check spelling or try the exact in-game name." |
| ESI unavailable | "Cannot check skills/wallet. Running with partial analysis." |
| Market data missing | "Price data unavailable for some items. Marked as '?' in cost." |

## Wallet Privacy Note

Wallet balance is fetched via ESI for the comparison but is only shown as a relative indicator ("You can afford X replacements"). If the pilot prefers not to show wallet, the cost breakdown is still useful on its own.

## Partial Flyability

Even if the pilot can't fly 100% of the fit, provide actionable guidance:

```
You can fly 8/11 modules (73%)

The fit is mostly usable. You're missing:
- Medium Drone Operation V (4d 12h to train)
- Mechanics V (2d 8h to train)

With substitutions, you could fly a modified version now:
- Swap Hammerhead II → Hammerhead I
- Swap Medium Armor Rep II → 'Meditation' Med Armor Rep
```

## Example Output

```
═══════════════════════════════════════════════════════════════════════════════
FIT CHECK: Vexor - L2 Mission Runner
───────────────────────────────────────────────────────────────────────────────

SKILL REQUIREMENTS
  Gallente Cruiser III         [OK] You have III
  Drones V                     [OK] You have V
  Medium Drone Operation V     [MISSING] You have III - train 6d 4h
  Drone Interfacing IV         [OK] You have IV
  Mechanics V                  [MISSING] You have IV - train 4d 9h

  You can fly 8/11 modules (73%)
  Total training needed: 10d 13h

SUBSTITUTION SUGGESTIONS
  Hammerhead II → Hammerhead I (you can use now, -15% DPS)
  Medium Armor Repairer II → 'Meditation' Medium Armor Repairer I
    (you can use now, -12% rep)

COST BREAKDOWN
  Hull:     8.2M (Vexor)
  Highs:    1.1M (Drone Link Augmentor I x1)
  Mids:     4.3M (Cap Battery, MWD, Cap Rechargers)
  Lows:     12.1M (Drone Damage Amp II x3, MAR II, EANM II)
  Rigs:     2.8M (Aux Nano Pump I x2, Nanobot Accelerator I)
  Drones:   8.5M (Hammerhead II x5, Hobgoblin II x5)
  ─────────────────
  TOTAL:    37.0M

  Your wallet: 45M
  After purchase: 8M remaining
  Replacements affordable: 1.2x

  ⚠️ WARNING: Below 3x replacement cost.
  Consider: Use T1 drones (saves 6M) or earn more ISK before buying.
═══════════════════════════════════════════════════════════════════════════════
```

## Integration with Other Skills

| After fit-check | Suggest |
|-----------------|---------|
| Missing skills identified | "Try `/skillplan` for efficient training order" |
| Budget concerns | "Run `/fit-budget` to generate an affordable version" |
| Fit is flyable | "Good to go! Use `/fitting` to validate stats" |

## Behavior Notes

- Always query live ESI data for skills and wallet (not profile cache)
- Default to Jita prices for cost estimates
- Show training times using default attributes (no implants assumed)
- Be encouraging even if pilot can't fully fly the fit
- Prioritize substitutions that maintain the fit's core purpose
