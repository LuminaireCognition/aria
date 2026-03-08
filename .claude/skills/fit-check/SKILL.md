---
name: fit-check
description: Validate if you can fly a ship fit (skill check) and afford it (cost check). Paste any EFT fit for comprehensive analysis with substitution suggestions.
model: sonnet
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

## Skills Freshness Gate (CRITICAL)

**Before checking pilot skills**, ensure fresh cached data:

```bash
uv run aria-esi ensure-fresh skills
```

| `fresh` | `esi_available` | Action |
|---------|-----------------|--------|
| `true`  | —               | Proceed with full skill check using cached skills |
| `false` | `false`         | Skip skill check, show cost-only analysis. Note: "Skill check unavailable (ESI offline) - showing cost analysis only" |
| `false` | `true` (sync failed) | Use cached skills if `age_hours < 72`, warn about staleness |

### Wallet Handling

Wallet is volatile and not in the freshness registry. Query it separately:
```bash
uv run aria-esi wallet
```
If wallet query fails, skip wallet comparison and show cost breakdown only.

### Degraded Mode Output

When skills are unavailable, still provide value:
- Cost breakdown (market tools work)
- Fit validation via EOS (fitting tools work)
- Module list and slot assignments
- Skip: skill check, wallet comparison, training time

## Execution Flow

### Step 1: Parse EFT Input

Accept EFT-format fit from user. If none provided, prompt for paste.

### Step 2: Extract Requirements

Call `fitting(action="extract_requirements", eft="...")` to get all skill requirements from the fit.

### Step 3: Check Against Pilot Skills

Get pilot skills via `uv run aria-esi skills`, then call `fitting(action="check_requirements", eft="...", pilot_skills={...})` to get the can/can't-fly verdict and list of missing skills.

### Step 4: Calculate Training Time for Missing Skills

For missing skills, call `skills(action="training_time", skill_list=[...])` to get total training time.

### Step 5: Find Substitutions

For modules requiring skills the pilot doesn't have, call `sde(action="meta_variants", item="...")` to find alternatives the pilot CAN use. Prefer Meta 4 > Faction (if affordable) > Meta 1-3 > T1 base.

### Step 6: Calculate Fit Cost

Call `market(action="valuation", items=[...], price_type="sell", region="jita")` with all items from the EFT fit. Default to Jita prices.

### Step 7: Get Wallet Balance

```bash
uv run aria-esi wallet
```

Compare wallet to fit cost.

### Step 8: Generate Replacement Cost Analysis

Calculate `replacement_count = wallet / total_cost`. Warn if below 3x (not enough buffer for losses).

## Response Format

```
═══════════════════════════════════════════════════════════════════════════════
FIT CHECK: [Ship] - [Fit Name]
───────────────────────────────────────────────────────────────────────────────

SKILL REQUIREMENTS
  [Skill Name] [Level]         [OK] You have [X]
  [Skill Name] [Level]         [MISSING] You have [X] - train [time]

  You can fly [X]/[Y] modules ([Z]%)

SUBSTITUTION SUGGESTIONS
  [T2 Module Name] → [T1/Meta Alternative] (you can use now, [stat diff])

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

## Cost Analysis

### Replacement Cost Rule

Industry-standard guidance: maintain 3x replacement cost minimum.

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

Be encouraging even if pilot can't fully fly the fit — frame substitutions as a path forward.
