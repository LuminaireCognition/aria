# Module Naming Reference

EVE Online module naming is inconsistent. Many modules do not follow the expected "Name I / Name II" convention. This reference documents common naming patterns to prevent fit validation failures.

## Golden Rule

> When in doubt, verify via `sde(action="item_info", item="...")` which returns the exact canonical name.

## Modules WITHOUT Tier Suffix

These modules have NO "I" or "II" suffix. Using "Reactive Armor Hardener I" will fail validation.

| Correct Name | Common Mistake | Notes |
|--------------|----------------|-------|
| Reactive Armor Hardener | Reactive Armor Hardener I | Unique module, no tiers |
| Damage Control II | Damage Control 2 | Has tier, but "2" is wrong |
| Assault Damage Control I/II | ADC I | No abbreviations |

## Size-Prefixed Modules

Propulsion modules require size prefix. The prefix varies by ship class.

| Module Type | Frigate | Cruiser | Battleship |
|-------------|---------|---------|------------|
| Afterburner | 1MN Afterburner I | 10MN Afterburner I | 100MN Afterburner I |
| MWD | 5MN Microwarpdrive I | 50MN Microwarpdrive I | 500MN Microwarpdrive I |

**Common Mistakes:**
- "MWD I" → Should be "5MN Microwarpdrive I" (or 50MN, 500MN)
- "Afterburner I" → Should be "1MN Afterburner I" (or 10MN, 100MN)
- "Microwarpdrive" → Must include size prefix

## Named Variants (Meta Modules)

Meta modules have descriptive names rather than numeric tiers.

| Category | Naming Pattern | Example |
|----------|----------------|---------|
| Compact | "Compact" prefix | Compact Multispectrum Energized Membrane |
| Enduring | "Enduring" prefix | Enduring Multispectrum Shield Hardener |
| Scoped | "Scoped" prefix | Scoped Survey Scanner |
| Restrained | "Restrained" prefix | Restrained Drone Damage Amplifier |
| Ample | "Ample" prefix | Ample Armor Repairer |

**Note:** Named modules are NOT "Meta I" or "Meta 4". Use the actual item name.

## Cap Batteries

Cap batteries use named variants, not numeric tiers.

| Size | Compact Variant | Standard |
|------|-----------------|----------|
| Small | Small Compact Pb-Acid Cap Battery | Small Cap Battery I |
| Medium | Medium Compact Pb-Acid Cap Battery | Medium Cap Battery I |
| Large | Large Compact Pb-Acid Cap Battery | Large Cap Battery I |

## Drones

Drones follow faction + size + tier pattern.

| Pattern | Example |
|---------|---------|
| Light Scout | Hobgoblin I, Hobgoblin II |
| Medium Scout | Hammerhead I, Hammerhead II |
| Heavy Attack | Ogre I, Ogre II |
| Sentry | Garde I, Garde II |

**By Faction:**
| Faction | Light | Medium | Heavy | Sentry |
|---------|-------|--------|-------|--------|
| Gallente | Hobgoblin | Hammerhead | Ogre | Garde |
| Caldari | Hornet | Vespa | Wasp | Warden |
| Amarr | Acolyte | Infiltrator | Praetor | Curator |
| Minmatar | Warrior | Valkyrie | Berserker | Bouncer |

## Analyzers and Hacking Modules

| Module | Slot | Correct Name |
|--------|------|--------------|
| Data Analyzer | Mid | Data Analyzer I / Data Analyzer II |
| Relic Analyzer | Mid | Relic Analyzer I / Relic Analyzer II |
| Cargo Scanner | Mid | Cargo Scanner I / Cargo Scanner II |
| Ship Scanner | Mid | Ship Scanner I / Ship Scanner II |
| Survey Scanner | Mid | Survey Scanner I / Survey Scanner II |

**Common Mistake:** Placing mid-slot modules in high slots. EOS validation catches this.

## Probe Launchers

| Type | Correct Name |
|------|--------------|
| Combat Probes | Expanded Probe Launcher I |
| Core Probes Only | Core Probe Launcher I |
| Sisters Variant | Sisters Core Probe Launcher |

## Cloaking Devices

| Type | Correct Name |
|------|--------------|
| Prototype | Prototype Cloaking Device I |
| Improved | Improved Cloaking Device II |
| Covert Ops | Covert Ops Cloaking Device II |

**Note:** Covert Ops Cloaking Device II requires a covert ops capable ship (Covert Ops frigates, Stealth Bombers, etc.).

## Validation Workflow

1. **Draft fit** with module names from memory
2. **Verify each module** via `sde(action="item_info", item="...")`
3. **Correct any naming errors** before building EFT
4. **Validate complete fit** via `fitting(action="calculate_stats", eft="...")`
5. **Present validated fit** with calculated stats

## Adding to This Reference

When a module name causes validation failure:

1. Verify correct name via SDE
2. Add to appropriate section above
3. Include both wrong and correct forms

This reference is a living document. Update it when new naming issues are discovered.
