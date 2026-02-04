# EVE Fitting Tool (EFT) Format Reference

**Source:** https://developers.eveonline.com/docs/guides/fitting/

This document contains the official EFT format specification for generating EVE Online fitting exports compatible with the in-game fitting tool.

## Format Structure

EFT format follows a strict ordering with sections separated by empty lines:

```
[Ship Type, Fitting Name]

<Low Slots>

<Medium Slots>

<High Slots>

<Rigs>

<Subsystems>       (Tech 3 only)

<Services>         (Structures only)


<Drones/Fighters>

<Cargo Items>
```

**Section Separators:**
- Sections 2-7 (slots through services): Single empty line between each
- Sections 7-9 (services through cargo): Two empty lines between each

## Syntax Rules

### First Line (Required)
```
[Ship Type, Fitting Name]
```
- Ship type must be exact game name
- Fitting name is user-defined
- Enclosed in square brackets, separated by comma

### Module Lines
```
Module Name
Module Name, Charge Name
Module Name /offline
```
- One module per line
- Charges specified after comma (e.g., `Prototype Cloaking Device I`)
- Offline modules append `/offline` suffix (ignored on import)

### Empty Slots
```
[Empty Low slot]
[Empty Med slot]
[Empty High slot]
[Empty Rig slot]
[Empty Service slot]
```
- Use exact capitalization shown above
- Optional: can omit empty slots entirely

### Drones and Fighters
```
Drone Name x5
Fighter Name x9
```
- Quantity specified with `x` prefix
- No space before `x`

### Cargo Items
```
Item Name x100
Nanite Repair Paste x50
```
- Same quantity format as drones
- Includes ammo, paste, scripts, etc.

## Complete Example

```
[Miasmos, Slippery - Self-Sufficient]

Inertial Stabilizers I
Inertial Stabilizers I
Inertial Stabilizers I
Damage Control I

50MN Microwarpdrive I
Medium Shield Extender I
Medium Shield Extender I

Prototype Cloaking Device I
[Empty High slot]

Medium Low Friction Nozzle Joints I
Medium Low Friction Nozzle Joints I
Medium Hyperspatial Velocity Optimizer I
```

## Combat Ship Example (with charges and drones)

```
[Vexor, Federation Navy Ratting]

Drone Damage Amplifier I
Drone Damage Amplifier I
Armor Repairer I
Energized Adaptive Nano Membrane I

50MN Microwarpdrive I
Large Compact Pb-Acid Cap Battery
Omnidirectional Tracking Link I, Tracking Speed Script

Drone Link Augmentor I
[Empty High slot]
[Empty High slot]
[Empty High slot]

Medium Auxiliary Nano Pump I
Medium Auxiliary Nano Pump I
Medium Nanobot Accelerator I


Hammerhead I x5
Hobgoblin I x5


Tracking Speed Script x1
Nanite Repair Paste x20
```

## Import Instructions

To import a fitting into EVE Online:

1. Copy the complete fitting text block
2. Open EVE Client
3. Open Fitting Window (`Alt+F`)
4. Click "Browse" in the left panel
5. Select "Import & Export" at bottom
6. Click "Import from Clipboard"
7. Fitting appears in Personal Fittings

## Localization Note

Type names can be specified in any localized format supported by EVE Online, not only English. The client will match items regardless of language used in the export.

## DNA Format (Alternative)

For compact single-line representation (used in chat links):

```
SHIP_TYPE_ID:MODULE_ID;QTY:MODULE_ID;QTY:...::
```

This format uses numeric type IDs and is primarily for programmatic use. EFT format is preferred for human-readable exports.
