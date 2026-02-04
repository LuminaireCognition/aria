# Fitting Construction Checklist

Operational checklist for building ship fittings. Complete each phase before proceeding to the next.

## Phase 1: Context Gathering

Before building any fit:

- [ ] Read `EFT-FORMAT.md` (slot order: low → mid → high → rig)
- [ ] Read pilot's `profile.md` (module tier, operational constraints)
- [ ] Read pilot's `ships.md` (existing fits for reference)
- [ ] If mission fit: Read mission cache for enemy damage/weakness
- [ ] If drones needed: Read `reference/mechanics/drones.json`
- [ ] Query ship slot layout: `sde(action="item_info", item="[ship name]")`

## Phase 2: Fit Construction

When building the EFT string:

- [ ] Use correct section order: Low → Mid → High → Rig → Drones
- [ ] Separate sections with single empty line
- [ ] **Fill ALL available slots** (check ship info from Phase 1)
- [ ] Verify uncertain module names via `sde(action="item_info")`
- [ ] Match drone selection to enemy weakness (from drones.json)
- [ ] Respect module tier constraints (T1/Meta vs T2)
- [ ] **Verify tank coherence** (see Tank Coherence Rules below)

## Phase 3: Validation

After `fitting(action="calculate_stats")`:

- [ ] Check `validation_errors` - must be empty to proceed
- [ ] Check `metadata.warnings` - investigate each one
- [ ] For warnings: query SDE to verify slot types, module names
- [ ] Verify CPU/PG not overloaded (`resources.*.overloaded: false`)
- [ ] Confirm drone bandwidth doesn't exceed ship limit

## Phase 4: Verification

Before presenting the fit:

- [ ] **Check `slots` output**: Verify `used == total` for all slot types
- [ ] If empty slots exist: Fill them OR document why (CPU/PG constrained)
- [ ] **Check `metadata.warnings`**: Address any tank coherence warnings
- [ ] Cross-check drone damage type against drones.json (not memory)
- [ ] Verify DPS numbers match EOS output exactly
- [ ] Confirm tank type matches mission damage profile
- [ ] Check cap stability is acceptable for fit purpose

## Phase 5: Presentation

When presenting to capsuleer:

- [ ] Include copy-paste ready EFT block
- [ ] State calculated stats with source ("via EOS with your skills")
- [ ] Note fitting room (CPU%, PG%)
- [ ] Include tactical notes relevant to purpose
- [ ] Suggest one related command if contextually helpful

## Tank Coherence Rules

**CRITICAL:** Never mix armor and shield active tank modules.

### Armor Tank (Gallente/Amarr Standard)
- **Low slots:** Armor Repairer, Armor Hardeners, Energized Membranes, Damage Control, Damage Mods
- **Mid slots:** Prop mod, Cap Battery, Utility (tackle, EWAR, application)
- **Rigs:** Auxiliary Nano Pump, Nanobot Accelerator, Trimark Armor Pump
- **NEVER:** Shield Hardeners, Shield Boosters, Shield Extenders in mids

### Shield Tank (Caldari/Minmatar Standard)
- **Mid slots:** Shield Extender, Shield Hardeners, Shield Booster, Prop mod
- **Low slots:** Damage Control, Damage Mods, tracking/application mods
- **Rigs:** Core Defense Field Extender, Anti-X Screen Reinforcer
- **NEVER:** Armor Repairers, Armor Hardeners (Damage Control is OK)

### Mixed Tank Indicators (Tool Will Warn)
The fitting tool now generates warnings for:
- Armor rigs + shield modules → "Shield hardeners are ineffective once shields depleted"
- Shield rigs + armor modules → "Consider committing to one tank type"
- Both armor and shield active modules → "This splits tank effectiveness"

## Common Failure Modes

| Symptom | Cause | Prevention |
|---------|-------|------------|
| Multiple validation failures | Built fit without reading EFT format | Always read EFT-FORMAT.md first |
| Wrong slot placement | Guessed slot type from memory | Query SDE for uncertain modules |
| Incorrect damage claim | Didn't verify drone damage type | Always read drones.json |
| Dismissed warnings | Assumed warnings were cosmetic | Investigate every warning |
| T2 modules for T1 pilot | Didn't check profile constraints | Read profile.md before building |
| **Empty slots** | Didn't check ship slot layout | Query SDE for ship info first |
| **Mixed tank** | Armor rigs with shield modules | Follow Tank Coherence Rules |
