# ARIA - Adaptive Reasoning & Intelligence Array

[![CI](https://github.com/LuminaireCognition/aria/actions/workflows/ci.yml/badge.svg)](https://github.com/LuminaireCognition/aria/actions/workflows/ci.yml)

**Ship-Board AI Framework for EVE Online**

ARIA is a Claude Code extension that turns Claude into a tactical EVE Online assistant. It provides mission briefs, fitting advice, threat assessment, mining guidance, and exploration tips.

```
═══════════════════════════════════════════════════════════════════
    ___    ____  _________
   /   |  / __ \/  _/   |   Adaptive Reasoning & Intelligence Array
  / /| | / /_/ // // /| |   Ship-Board Tactical Assistant
 / ___ |/ _, _// // ___ |
/_/  |_/_/ |_/___/_/  |_|   by Luminaire Cognition [LUCOS]
```

<p><strong>Quick Docs:</strong>
<a href="./docs/TLDR.md">TL;DR</a> |
<a href="./docs/FIRST_RUN.md">First Run</a> |
<a href="./docs/ESI.md">ESI Setup</a> |
<a href="./docs/FAQ.md">FAQ</a> |
<a href="./docs/README.md">Full Docs Index</a>
</p>

---

## Requirements

- **Python 3.10+**
- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)**
- **[uv](https://docs.astral.sh/uv/)**

---

## Quick Start

```bash
# 1. Clone the repository
git clone git@github.com:LuminaireCognition/aria.git
# or (HTTPS)
git clone https://github.com/LuminaireCognition/aria.git
cd aria

# 2. Run the setup wizard
./aria-init

# 3. Launch ARIA
claude
```

---

## Using ARIA

Start a session from the repo root:

```bash
claude
```

Setup paths:

- From your shell, run `./aria-init` for first-time bootstrap and local file generation.
- Inside Claude Code, run `/setup` to configure or update your pilot profile conversationally.

You can also run the CLI directly for data lookups and utilities:

```bash
uv run aria-esi --help
```

---

## Examples

### Route Planning (Natural Language)

```text
❯ I just filamented into 7BIX-A. Find me a ~20 jump route through goon ratting systems, avoiding hotspots.
```

<details>
<summary>MCP tool calls (collapsed)</summary>

```text
aria-universe (MCP) local_area: origin=7BIX-A max_jumps=15 include_realtime=true
aria-universe (MCP) territory_analysis: coalition=imperium
aria-universe (MCP) optimize_waypoints: origin=7BIX-A waypoints=[...]
aria-universe (MCP) hotspots: origin=7BIX-A max_jumps=20 activity_type=kills limit=10
```
</details>

```text
You're in Fountain - Imperium territory. Threat level: LOW.

Recommended ~20-jump loop (ratting-heavy systems):
7BIX-A → G-UTHL → A-1CON → YZ-LQL → Z30S-A → V6-NY1 → 9DQW-W → PXF-RF → return

Hotspots to avoid:
- 75FA-Z (recent kills)
- L7-APB (recent kills)
```

### Mission Brief (Natural Language)

```text
❯ I need to run level 2 Damsel in Distress in a vexor.
```

<details>
<summary>MCP tool calls (collapsed)</summary>

```text
Read 2 files
Found it in the cache. Let me pull the detailed intel.
Read 2 files
```
</details>

```text
Damsel in Distress L2 - Vexor Briefing

Mission Profile
Faction: Mercenaries
Incoming Damage: Thermal/Kinetic
Deal Damage: Thermal > Kinetic
Objective: Destroy Kruul's Pleasure Hub, loot "The Damsel"

Enemy Forces
Initial Spawn (auto-aggro, 10-20km):
- 8x Frigate (Kruul's Henchman)
- 1x Cruiser (Kruul) ⚠️ Trigger

Reinforcements (if you attack Kruul):
- 10x Elite Frigate (Mercenary Elite Fighter)

Drone Loadout
Vexor: 75 Mbit bandwidth, 125 m³ bay
- Hammerhead II x5 (Thermal)
- Hobgoblin II x5 (Thermal)
Carry spares - 50 m³ bay remaining for 5 more Hobgoblins.

Tank Priority
Thermal > Kinetic - Fit thermal hardener(s) or rig for thermal resist. An Adaptive Invulnerability Field or Medium Armor Repairer with thermal membranes works well.

Blitz Strategy
1. Warp in, ignore Kruul (attacking him spawns 10 elite frigates)
2. Destroy Kruul's Pleasure Hub - ⚠️ it deals AoE damage when it pops, keep 5-10km range
3. Loot "The Damsel" from the wreck
4. Warp out

If you engage everything instead of blitzing, clear frigates first with Hobgoblins, then switch to Hammerheads for Kruul.
```

### Fit Recommendation (Natural Language)

```text
❯ Give me a vexor fit for level 2 damsel using t1/meta modules.
```

<details>
<summary>MCP tool calls (collapsed)</summary>

```text
aria-universe (MCP) fitting.calculate_stats: [Vexor, Damsel L2 - T1/Meta]
aria-universe (MCP) market.valuation: items=[Vexor + fit], region=jita
```
</details>

```text
Vexor - Damsel L2 (T1/Meta)

[Vexor, Damsel L2 - T1/Meta]
Medium Armor Repairer I
Drone Damage Amplifier I
Drone Damage Amplifier I
Thermal Armor Hardener I
Kinetic Armor Hardener I

10MN Afterburner I
Cap Recharger I
Omnidirectional Tracking Link I
Drone Navigation Computer I

Drone Link Augmentor I

Medium Auxiliary Nano Pump I
Medium Capacitor Control Circuit I
Medium Capacitor Control Circuit I

Hammerhead I x5
Hobgoblin I x5

Stats (All V)
DPS: 380 thermal
EHP: 8,952
Speed: 244 m/s
Align: 6s

Cost (Jita Sell)
Total: 17.7M

380 DPS is more than enough for L2 content. You'll clear slightly slower but save nearly 15M ISK while training into T2.
```

---

## ESI Integration (Optional)

ARIA works without ESI. If you want live character data, run the setup wizard:

```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

Details: [docs/ESI.md](docs/ESI.md)

---

## Data Freshness & Trust

Before relying on route safety, market prices, or mission detail timing, check:

- [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) for source origin and update behavior
- [docs/DATA_VERIFICATION.md](docs/DATA_VERIFICATION.md) for validation and integrity controls
- [docs/ESI.md](docs/ESI.md) for live-data setup and token lifecycle

---

## Development Setup

```bash
# Install dependencies (creates .venv automatically)
uv sync

# Run tests
uv run pytest

# Run a script
uv run python .claude/scripts/aria-esi-sync.py
```

---

## Troubleshooting

### Boot sequence doesn't appear

```bash
ls -la .claude/hooks/aria-boot.sh
# Should show: -rwxr-xr-x
```

If not executable:

```bash
chmod +x .claude/hooks/aria-boot.sh
```

### ESI token expired

```bash
.claude/scripts/aria-refresh
```

If refresh fails, re-run the setup wizard:

```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

---

## Security

See [SECURITY.md](SECURITY.md) for full details.

**Key protections:**
- **Path validation** - User-editable configs cannot load arbitrary files
- **Data integrity** - External data verified via SHA256 checksums before loading
- **Safe serialization** - Universe graph uses msgpack, not pickle
- **Prompt injection defense** - Untrusted data is sandboxed with strict delimiters

**Credential handling:**
- OAuth tokens stored locally in `userdata/credentials/` (gitignored)
- ESI scopes are read-only - ARIA cannot modify your game state
- No telemetry or external data transmission (except ESI API calls)

---

## Attribution & Licensing

### EVE Online

© 2014 CCP hf. All rights reserved. "EVE", "EVE Online", "CCP", and all related logos and images are trademarks or registered trademarks of CCP hf.

This is a fan project and is **not affiliated with, endorsed by, or sponsored by CCP Games**. ARIA is not affiliated with AURA, CCP's in-game AI assistant.

### License

The ARIA framework is released under the [MIT License](LICENSE), with the following exceptions:

| Content | License | Notes |
|---------|---------|-------|
| ARIA framework code | MIT | Scripts, templates, skills |
| PvE intelligence (`reference/pve-intel/`) | CC-BY-SA 4.0 | Derived from [EVE University Wiki](https://wiki.eveuniversity.org/) |
| EVE Online content | CCP Games | Subject to [Developer License Agreement](https://developers.eveonline.com/license-agreement) |

### Commercial Use Restriction

Use of EVE Online content and the ESI API is subject to the [CCP Developer License Agreement](https://developers.eveonline.com/license-agreement), which restricts commercial use. While the ARIA framework code is MIT-licensed, any use incorporating EVE Online intellectual property must comply with CCP's terms.

### Disclaimer

ARIA dispenses tactical wisdom with the confidence of a thousand battles—none of which she has actually fought. Ship fittings, mission tactics, and strategic recommendations are provided **without warranty**, express or implied, by an AI with strong opinions and zero killboard history.

Your ships will explode. Some of those explosions may be ARIA's fault. This is EVE.

The developers and contributors accept no liability for lost vessels, empty wallets, or strongly-worded messages in Local. Remember the capsuleer's first rule: never undock what you can't afford to lose—*especially* on the advice of an AI who has never experienced the unique terror of watching her own capacitor hit zero.

See [ATTRIBUTION.md](ATTRIBUTION.md) for complete attribution details.

---

*by Luminaire Cognition [LUCOS]*
