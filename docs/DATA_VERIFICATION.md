# Data Verification Protocol

**Purpose:** Prevent hallucinated game mechanics from reaching users by enforcing verification against ground truth sources.

## Core Principle

> **Never present EVE game mechanics as fact without verification from a trusted source.**

Training data knowledge about EVE Online is **not a trusted source**. It may be outdated, incomplete, or simply wrong. Always verify claims against authoritative data before presenting them to the user.

## Trust Hierarchy

When making claims about EVE Online mechanics, verify from these sources in order of preference:

| Priority | Source | Tool/Method | Use For |
|----------|--------|-------------|---------|
| 1 | **SDE** | `sde_item_info`, `sde_blueprint_info`, `sde_skill_requirements` | Item stats, skill effects, blueprint data |
| 2 | **Pyfa/EOS** | `calculate_fit_stats` | Fitting calculations, DPS, EHP, capacitor |
| 3 | **ESI** | `/esi-query`, MCP tools | Live game state, market data, pilot data |
| 4 | **EVE University Wiki** | `WebFetch` | Mechanics explanations, strategy guides |
| 5 | Training data | Never trust alone | Only as starting hypothesis to verify |

## Verification Patterns

### Pattern 1: Skill Effect Claims

**Wrong approach:**
```
User: "What does Drones skill do?"
ARIA: "Drones IV gives you 5 drones" ← Hallucinated, never verified
```

**Correct approach:**
```
User: "What does Drones skill do?"
ARIA: [Calls sde_item_info("Drones")]
      → Description: "Can operate 1 drone per skill level"
ARIA: "Drones gives +1 drone per level, so level IV = 4 drones, level V = 5 drones"
```

### Pattern 2: Module/Ship Statistics

**Wrong approach:**
```
User: "How much DPS does a Vexor do?"
ARIA: "About 400 DPS with T2 drones" ← Guess based on training data
```

**Correct approach:**
```
User: "How much DPS does a Vexor do?"
ARIA: [Calls calculate_fit_stats with actual fit]
      → Returns calculated DPS from EOS
ARIA: "With this fit and all V skills: 548 DPS"
```

### Pattern 2a: Fitting Recommendations

**CRITICAL:** All fitting recommendations MUST pass EOS validation before presentation. See `.claude/skills/fitting/SKILL.md` for the complete protocol.

**Wrong approach:**
```
User: "Fit my Vexor for Survey Rendezvous"
ARIA: [Builds fit from memory]
      "Use a Reactive Armor Hardener I and Data Analyzer in high slot"
      ← Wrong module name (no "I" suffix), wrong slot (Data Analyzer is mid)
```

**Correct approach:**
```
User: "Fit my Vexor for Survey Rendezvous"
ARIA: [Verifies module names via SDE]
      sde(action="item_info", item="Reactive Armor Hardener") → Valid
      sde(action="item_info", item="Data Analyzer I") → Valid, mid slot
ARIA: [Validates complete fit via EOS]
      fitting(action="calculate_stats", eft="...", use_pilot_skills=true)
      → Returns validation status + calculated stats
ARIA: [Presents validated fit with accurate stats]
```

**See also:** `reference/fittings/MODULE_NAMES.md` for common naming issues

### Pattern 3: Skill Requirements

**Wrong approach:**
```
User: "What do I need for Hammerhead II?"
ARIA: "Medium Drone Operation IV" ← Incomplete, from memory
```

**Correct approach:**
```
User: "What do I need for Hammerhead II?"
ARIA: [Calls skill_t2_requirements("Hammerhead II")]
      → Returns: Drones V, Medium Drone Operation V, Gallente Drone Spec I
ARIA: [Presents verified requirements]
```

## When to Verify

**Always verify when claiming:**
- Specific numbers (damage, HP, capacitor, training time)
- Skill effects per level
- Module/ship bonuses
- Blueprint materials or times
- T2 requirements
- Any "X gives Y" statement

**May skip verification for:**
- General strategic advice ("armor tank is typical for Gallente")
- Directional guidance ("train drone skills for a Vexor")
- Questions that don't involve specific mechanics

## Red Flags

Watch for these patterns that indicate unverified claims:

| Pattern | Example | Risk |
|---------|---------|------|
| Specific numbers without tool call | "15% bonus per level" | Likely hallucinated |
| "I believe" / "I think" | "I think Drones V gives 5 drones" | Uncertainty = verify |
| Common knowledge assumptions | "Everyone knows that..." | Verify anyway |
| Rounded/convenient numbers | "About 500 DPS" | Get actual calculation |

## When Tools Don't Have the Data

Sometimes verification tools return incomplete data. **This does not authorize filling the gap with training knowledge.**

### The Correct Response

1. **Acknowledge the gap explicitly**
   - "The SDE doesn't expose invention requirements directly"
   - "I cannot verify the specific skill from available tools"

2. **Do not fill with training knowledge**
   - Even plausible-sounding information from training data is unverified
   - Presenting it as fact is still hallucination

3. **Suggest in-game verification**
   - "You can check in-game via Industry → Invention on a T1 BPC"
   - "The Show Info window will display the exact requirements"

4. **Offer to search other sources**
   - EVE University Wiki via `WebFetch`
   - Ask user if they have documentation to share

### Example: Invention Requirements

**Wrong approach:**
```
User: "What skills do I need to invent DDA II?"
ARIA: [Calls sde_blueprint_info, gets manufacturing data but no invention data]
ARIA: "You need Electronic Engineering and Gallentean Starship Engineering"
      ↑ Gap filled with training data, presented as fact
```

**Correct approach:**
```
User: "What skills do I need to invent DDA II?"
ARIA: [Calls sde_blueprint_info, gets manufacturing data but no invention data]
ARIA: "The SDE tools don't expose invention requirements directly.
       I cannot verify which specific science skills DDA II invention requires.
       You can check in-game via Industry → Invention on a DDA I BPC,
       or I can search EVE University Wiki for this information."
```

### Key Principle

> **An honest "I don't know" is better than a confident hallucination.**

The user can verify in-game or provide documentation. A wrong answer wastes their time and erodes trust.

## Available Verification Tools

### SDE Tools (Static Data Export)
```
sde_item_info(item)           # Item description, stats, category
sde_skill_requirements(item)  # Full skill tree for ships/modules
sde_blueprint_info(item)      # Manufacturing data, materials
sde_search(query)             # Find items by partial name
```

### Skill Planning Tools
```
skill_easy_80_plan(item)      # Training recommendations
skill_t2_requirements(item)   # What needs level V for T2
skill_training_time(skills)   # Actual training duration
skill_get_multipliers(role)   # High-impact skills by role
```

### Fitting Tools
```
calculate_fit_stats(eft)      # Full fit statistics via EOS
fitting_status()              # Check if fitting engine available
```

**Fitting Validation Protocol:** When recommending ship fittings, ALWAYS:
1. Verify module names via `sde_item_info()` before building EFT
2. Validate the complete fit via `calculate_fit_stats(eft, use_pilot_skills=true)`
3. Check for `validation_errors`, CPU/PG overload, or unknown types
4. Only present fits that pass validation with calculated (not estimated) stats

See `.claude/skills/fitting/SKILL.md` for the complete fitting validation protocol.

### Market Tools
```
market_prices(items)          # Current prices
market_orders(item)           # Order book details
```

## Process Checklist

Before presenting game mechanics to the user:

- [ ] Did I make a specific claim about how something works?
- [ ] Did I verify that claim with an appropriate tool?
- [ ] Can I cite the source (SDE description, EOS calculation, etc.)?
- [ ] If I'm uncertain, did I verify instead of guessing?
- [ ] If the tool lacked data, did I acknowledge the gap instead of filling it?

**Additional checks for fitting recommendations:**

- [ ] Did I verify all module names via SDE before building the EFT?
- [ ] Did I validate the complete fit via EOS `calculate_fit_stats`?
- [ ] Are the stats I'm presenting calculated (not estimated)?
- [ ] If validation failed, did I fix and re-validate before presenting?

## Case Study: The Drones Skill Error

**What happened:**
1. User asked for Vexor skill recommendations
2. ARIA claimed "Drones IV gives +1 drone (5 total)"
3. This was wrong—Drones gives 1 drone *per level*, so IV = 4 drones
4. User challenged the claim
5. ARIA verified with `sde_item_info("Drones")` and found the error

**Root cause:** Hallucinated skill effect from training data without verification.

**What should have happened:**
1. Before claiming what Drones skill does, call `sde_item_info("Drones")`
2. Read the description: "Can operate 1 drone per skill level"
3. Present verified information: "Drones IV = 4 drones, V = 5 drones"

**Lesson:** The SDE had the correct answer. The failure was not checking it.

## Case Study: The Invention Requirements Error

**What happened:**
1. User asked what skills are needed to invent Drone Damage Amplifier II
2. ARIA called `sde_blueprint_info` which returned manufacturing data but not invention requirements
3. ARIA filled the data gap with training knowledge, listing "Gallentean Starship Engineering" as a skill
4. User challenged: "Gallentean Starship Engineering is a datacore, not a skill"
5. ARIA verified with `sde_search` and confirmed the error

**Root cause:** When verification tools returned incomplete data, ARIA filled the gap with unverified training knowledge instead of acknowledging the limitation.

**What the tools showed:**
- "Gallente Starship Engineering" (type_id 11450) → **Skill**
- "Datacore - Gallentean Starship Engineering" (type_id 20410) → **Datacore**

The "-ean" suffix distinguishes datacores from skills. Training data conflated them.

**What should have happened:**
1. Call `sde_blueprint_info("Drone Damage Amplifier II")` - got manufacturing data only
2. Recognize the gap: no invention requirements returned
3. State clearly: "The SDE tools don't expose invention requirements. I cannot verify the specific science skills needed."
4. Offer alternatives: "You can check in-game via Industry → Invention, or I can search EVE University Wiki."

**Lesson:** Incomplete tool data is not permission to fill gaps with training knowledge. Acknowledge limitations honestly.

## Case Study: The Build Cost Component Error

**What happened:**
1. User asked for Dominix build cost via `/build-cost Dominix`
2. ARIA called `sde(action="blueprint_info")` which returned 10 materials (7 minerals + 3 components)
3. ARIA only priced the 7 minerals, silently omitting 3 component materials:
   - Auto-Integrity Preservation Seal (150 units)
   - Life Support Backup Unit (75 units)
   - Core Temperature Regulator (1 unit)
4. Reported 7.8% profit margin when actual result was a **loss** (negative margin)
5. The understated cost was approximately 19.6M ISK

**Root cause:** The skill implementation used a hardcoded mineral list pattern inherited from simple item examples (like Hammerhead I), instead of dynamically extracting ALL materials from the SDE response.

**Problematic pattern:**
```python
# WRONG: Hardcoded list misses components
materials = ["Tritanium", "Pyerite", "Mexallon", "Isogen", "Nocxium", "Zydrine", "Megacyte"]
market(action="prices", items=materials)
```

**What should have happened:**
1. Call `sde(action="blueprint_info", item="Dominix")` - got 10 materials
2. Extract **ALL** material names dynamically from the response
3. Query prices for complete list including components
4. Verify price count matches material count
5. If mismatch, display **prominent warning** before any results
6. Include component costs in total (mineral cost + component cost)

**Correct pattern:**
```python
# CORRECT: Dynamic extraction includes everything
blueprint = sde(action="blueprint_info", item="Dominix")
material_names = [m["type_name"] for m in blueprint["materials"]]
material_names.append(blueprint["product"])
market(action="prices", items=material_names)

# Verify completeness
if len(prices) < len(material_names):
    # MUST warn user, MUST NOT present as complete
```

**Impact:** The user could have lost 3.7M ISK per Dominix built based on the incomplete profitability assessment. For a 10-run build, that's a 37M ISK loss instead of the 159M profit reported.

**Lesson:**
- Never hardcode material lists - always extract from SDE response
- Silent omission of materials is **forbidden** - missing data must be flagged prominently
- Simple examples (Hammerhead I) don't represent complex items (ships with components)
- Verify that prices received matches materials requested before presenting results

## Integration with Response Flow

```
User Question
     │
     ▼
┌─────────────────────────────────┐
│ Does response involve specific  │
│ game mechanics or numbers?      │
└─────────────────────────────────┘
     │
     ├── No → Respond directly
     │
     ▼ Yes
┌─────────────────────────────────┐
│ Query appropriate tool:         │
│ • sde_item_info for items       │
│ • skill_* for training          │
│ • calculate_fit_stats for fits  │
│ • market_* for prices           │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ Did tool return needed data?    │
└─────────────────────────────────┘
     │
     ├── Yes → Present verified information
     │
     ▼ No
┌─────────────────────────────────┐
│ Acknowledge the gap:            │
│ • State what tool didn't have   │
│ • Do NOT fill with training     │
│ • Suggest in-game verification  │
│ • Offer to search other sources │
└─────────────────────────────────┘
```

## Mission Data Flow

Mission intel follows a different verification path than item/skill data:

```
Mission-Related Question
     │
     ▼
┌──────────────────────────────────┐
│ Check reference/pve-intel/INDEX.md│
│ for cached PvE intel             │
└──────────────────────────────────┘
     │
     ├── Cached → Read local file
     │
     ▼ Not cached
┌─────────────────────────────────┐
│ Check INDEX.md damage quick ref │
│ for faction-level intel         │
└─────────────────────────────────┘
     │
     ├── Sufficient for request → Use it
     │
     ▼ Need detailed spawns/waves
┌─────────────────────────────────┐
│ WebFetch wiki.eveuniversity.org │
│ NEVER use general web search    │
└─────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────┐
│ Cache result to                      │
│ reference/pve-intel/cache/{name}.md  │
└──────────────────────────────────────┘
```

**Key principle:** General web search is prohibited for mission data. The EVE University Wiki is the only blessed external source. See `docs/DATA_SOURCES.md` for rationale.

**Recognition triggers for mission context:**
- Explicit: "mission brief", "/mission-brief", "prepare for [mission]"
- Implicit: "fitting for [ship] running [mission]", "[mission name] L[N]"

## Summary

1. **Verify first, respond second** when discussing game mechanics
2. **SDE is ground truth** for item/skill data
3. **EOS/Pyfa is ground truth** for fitting calculations
4. **Training data is not a source**—it's a hypothesis to verify
5. **When uncertain, query**—the tools exist for this purpose
6. **When tools lack data, acknowledge the gap**—never fill with training knowledge
7. **Mission data uses local cache + EVE Uni Wiki**—never general web search
