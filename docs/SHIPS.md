# Ship Roster & Fittings Guide

Your `ships.md` file tracks your ship roster and fittings. ARIA reads this file to tailor mission briefs, fitting recommendations, and module suggestions to what you actually fly.

## File Structure

The file has two zones:

1. **Ship Roster** (top) — a table of your ships, names, and locations. If you have ESI connected, this section updates automatically on each session start. It's wrapped in sync markers (`<!-- ESI-SYNC:ROSTER:START -->` / `<!-- ESI-SYNC:ROSTER:END -->`).

2. **Fitting Details** (below the roster) — your manually-added ship fittings in EFT format. This section is **never touched by ESI sync**, so your fittings are always preserved.

Without ESI, both sections are fully manual — just edit the file directly.

## Adding a Ship Fitting

To add a fitting, paste the EFT (EVE Fitting Tool) block under a heading for that ship. You can export EFT from the in-game fitting window (hamburger menu > Copy to Clipboard).

### Step by step

1. Open your fitting window in-game
2. Click the hamburger menu (top-left of the fit) and select **Copy to Clipboard**
3. Open `userdata/pilots/{your_pilot}/ships.md`
4. Below the roster section (or anywhere below the `<!-- ESI-SYNC:ROSTER:END -->` marker if present), add a heading and paste the fit:

```markdown
## Vexor — Serpentis Missions

[Vexor, Serpentis Runner]
Drone Damage Amplifier I
Drone Damage Amplifier I
Medium Armor Repairer I
Multispectrum Energized Membrane I
Reactive Armor Hardener

10MN Y-S8 Compact Afterburner
Medium Compact Pb-Acid Cap Battery
Omnidirectional Tracking Link I

Drone Link Augmentor I

Medium Auxiliary Nano Pump I
Medium Drone Durability Enhancer I
Medium Capacitor Control Circuit I

Hammerhead I x5
Hobgoblin I x5
Salvage Drone I x3
```

That's it. ARIA will pick up the fitting next time you ask for a mission brief or fitting help.

## EFT Format Reference

EFT format follows a simple structure:

- **Header line:** `[Hull Name, Fit Name]` — the ship hull and your name for the fit
- **Modules:** One per line, using the exact in-game module name
- **Drones:** `Drone Name xN` (e.g., `Hammerhead I x5`)
- **Ammo/charges:** `Ammo Name xN` (e.g., `Inferno Heavy Missile x1000`)

Module names must match in-game names exactly. If a name is wrong, ARIA can't look up the module's stats.

Slot labels (like `[Low Slots]`) are **not needed** — the fitting engine knows where each module goes.

## Module Tier

ARIA infers your gear tier from the module names in your fittings:

| Naming Pattern | Tier | Example |
|----------------|------|---------|
| Ends in `I` | T1 | Armor Repairer I |
| Named variants | Meta | Medium Compact Armor Repairer |
| Ends in `II` | T2 | Armor Repairer II |

This matters because ARIA will match recommendations to your tier. If your fittings show T1 modules, ARIA recommends T1/Meta. If you're using T2, ARIA knows it can suggest T2.

You can also set your tier explicitly in `profile.md` by adding `module_tier: t1` or `module_tier: t2` under Operational Constraints. When set, this overrides what ARIA infers from your fits.

## ESI Sync Behavior

If you have ESI configured:

- The **Ship Roster** table updates automatically at session start with your current hangar contents (ship names, hull types, and locations)
- Everything **outside** the sync markers is preserved — your fitting details, notes, and any other content you've added are safe
- You can also run `uv run aria-esi esi-sync` to trigger a manual sync

Without ESI, the roster section stays as-is. You can fill it in manually or leave it empty — the fitting details section is what matters most for recommendation quality.

## How ARIA Uses Your Fittings

When you ask for a **mission brief**, ARIA reads your fittings to:

- **Adapt your existing fit** for the specific mission (swap hardeners, drones, and ammo to match enemy weaknesses) instead of suggesting a generic fit
- **Match your module tier** — if you fly T1, you get T1 recommendations; if you fly T2, you get T2

When you ask for **fitting help**, ARIA uses your fits to understand what modules you have access to and what style of fitting you prefer.

Without fittings in `ships.md`, ARIA falls back to general-purpose fits. They work, but they won't be tuned to your specific setup.

## Example

Here's what a complete `ships.md` looks like with ESI sync and manual fittings:

```markdown
# Ship Status

<!-- ESI-SYNC:ROSTER:START -->
## Ship Roster (ESI Synced)
*Last sync: 2026-02-27 14:30 UTC*

| Name | Hull | Location |
|------|------|----------|
| Serpentis Runner | Vexor | Dodixie |
| cat0 | Catalyst | Masalle |
| Prospect Pete | Prospect | Dodixie |

*3 ships in hangars*
<!-- ESI-SYNC:ROSTER:END -->

## Vexor — Mission Running

[Vexor, Serpentis Runner]
Drone Damage Amplifier I
Drone Damage Amplifier I
Medium Armor Repairer I
Multispectrum Energized Membrane I
Reactive Armor Hardener

10MN Y-S8 Compact Afterburner
Medium Compact Pb-Acid Cap Battery
Omnidirectional Tracking Link I

Drone Link Augmentor I

Medium Auxiliary Nano Pump I
Medium Drone Durability Enhancer I
Medium Capacitor Control Circuit I

Hammerhead I x5
Hobgoblin I x5
Salvage Drone I x3

## Catalyst — Salvaging

[Catalyst, cat0]
Salvager I
Salvager I
Salvager I
Salvager I
Small Tractor Beam I
Small Tractor Beam I
Small Tractor Beam I
Small Tractor Beam I

1MN Y-S8 Compact Afterburner

Small Salvage Tackle I
Small Salvage Tackle I
Small Salvage Tackle I
```

The roster table at the top updates via ESI. The fitting blocks below are yours to maintain.
