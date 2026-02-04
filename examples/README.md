# Example Configurations

This directory contains example ARIA configurations for reference.

## Available Examples

### gallente-selfsufficient/

A Gallente Federation pilot using self-sufficiency mode (no player market trading).

**Playstyle characteristics:**
- Primary faction: Gallente Federation
- No market orders or contracts with other players
- NPC-seeded BPOs, skillbooks, and LP store permitted
- Focus on mining, mission running, and exploration
- Manufacturing-focused gameplay loop

**Files included:**
- `pilot_profile.md` - Character identity and faction standings
- `operational_profile.md` - Home base and operational patterns
- `ship_status.md` - Ship roster and fittings
- `blueprint_library.md` - BPO collection and manufacturing capability
- `mission_log.md` - Mission history and preferences
- `exploration_catalog.md` - Exploration site records

---

### caldari-mission-runner/

A Caldari State pilot focused on maximum ISK efficiency through L4 mission running.

**Playstyle characteristics:**
- Primary faction: Caldari State
- Full market participation (trading, arbitrage)
- L4 security missions with Caldari Navy
- LP store optimization
- ISK/hour focused decision-making

**Files included:**
- `pilot_profile.md` - Corporate efficiency philosophy
- `operational_profile.md` - Jita/Motsu staging, mission optimization
- `ship_status.md` - Raven, Jackdaw, Crane, Noctis fits
- `blueprint_library.md` - Minimal (market-focused playstyle)
- `mission_log.md` - Detailed mission tracking and LP conversion
- `exploration_catalog.md` - Opportunistic only

---

### minmatar-explorer/

A Minmatar Republic pilot embracing nomadic exploration lifestyle.

**Playstyle characteristics:**
- Primary faction: Minmatar Republic
- Nomadic operations (no fixed home)
- Wormhole daytripping (C1-C3)
- Nullsec exploration runs
- Ghost site specialist
- High risk tolerance

**Files included:**
- `pilot_profile.md` - Nomadic freedom philosophy
- `operational_profile.md` - Distributed staging, wormhole chains
- `ship_status.md` - Cheetah, Hound, Vagabond, disposable Probes
- `blueprint_library.md` - Travel light (sell BPCs from exploration)
- `mission_log.md` - Minimal (exploration-focused)
- `exploration_catalog.md` - Comprehensive site tracking and statistics

---

### amarr-industrialist/

An Amarr Empire pilot dedicated to traditional industry and manufacturing.

**Playstyle characteristics:**
- Primary faction: Amarr Empire
- Vertical integration (mining to manufacturing)
- Blueprint research focus (ME/TE optimization)
- T1 Amarr ship and module production
- Planetary Interaction for components
- Patience-oriented gameplay

**Files included:**
- `pilot_profile.md` - Divine industry philosophy
- `operational_profile.md` - Amarr manufacturing hub operations
- `ship_status.md` - Procurer, Epithal, Bestower, Omen fits
- `blueprint_library.md` - Extensive (54+ BPOs, research queues)
- `mission_log.md` - Standing-focused (industry corp taxes)
- `exploration_catalog.md` - Secondary (data sites for invention prep)

---

## Using Examples

To use an example as your starting point:

```bash
# Copy example files to your pilot directory
cp -r examples/gallente-selfsufficient/* pilots/YOUR_ID_SLUG/

# Then customize with your character details
```

## File Purposes

| File | Purpose |
|------|---------|
| `pilot_profile.md` | Identity, standings, philosophy |
| `operational_profile.md` | Home base, ship roster, activities |
| `ship_status.md` | Detailed fittings and ship notes |
| `blueprint_library.md` | BPO/BPC inventory for industry |
| `mission_log.md` | Mission history and preferences |
| `exploration_catalog.md` | Exploration site records |

## Contributing Examples

Want to share your ARIA configuration? Examples for other playstyles are welcome:

- Nullsec PvP pilot
- Wormhole resident
- Market mogul
- Faction warfare soldier
- Incursion runner

Create a pull request with your example in a descriptively-named subdirectory.
