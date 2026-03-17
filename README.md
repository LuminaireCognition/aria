# ARIA - Adaptive Reasoning & Intelligence Array

[![CI](https://github.com/LuminaireCognition/aria/actions/workflows/ci.yml/badge.svg)](https://github.com/LuminaireCognition/aria/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/LuminaireCognition/aria/graph/badge.svg)](https://codecov.io/gh/LuminaireCognition/aria)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Tactical Advisor AI Framework for EVE Online**

ARIA is a Claude Code extension that turns Claude into a tactical EVE Online assistant. It provides mission briefs, fitting advice, threat assessment, mining guidance, and exploration tips — all through natural language.

```
═══════════════════════════════════════════════════════════════════
    ___    ____  _________
   /   |  / __ \/  _/   |   Adaptive Reasoning & Intelligence Array
  / /| | / /_/ // // /| |   Tactical Advisory System
 / ___ |/ _, _// // ___ |
/_/  |_/_/ |_/___/_/  |_|   by Luminaire Cognition [LUCOS]
```

<p><strong>Quick Docs:</strong>
<a href="./docs/TLDR.md">TL;DR</a> |
<a href="./docs/FIRST_RUN.md">First Run</a> |
<a href="./docs/ESI.md">ESI Setup</a> |
<a href="./docs/FAQ.md">FAQ</a> |
<a href="./CONTRIBUTING.md">Contributing</a> |
<a href="./docs/README.md">Full Docs Index</a>
</p>

### Get Value in 60 Seconds

ARIA is for **EVE Online players** who want tactical advice without alt-tabbing to wikis. After a 5-minute setup you'll have a Claude-powered copilot that answers questions like *"fit my Vexor for L2 missions"* or *"is Uedama safe right now"* with live game data.

```bash
git clone https://github.com/LuminaireCognition/aria.git && cd aria
./aria-init        # downloads game data, sets up hooks (~2 min)
claude             # start talking to ARIA
```

First prompt to try:

```
I'm a new player flying a Vexor. What should I know about running level 2 missions?
```

### What ARIA Does

- **Mission briefs** — enemy intel, damage profiles, blitz strategies, wave-by-wave breakdowns
- **Ship fitting** — EFT-format fits with EOS-validated stats, budget alternatives, skill-aware recommendations
- **Route planning** — safe/shortest/unsafe routing with live activity data, gatecamp detection, loop planning
- **Market intel** — cross-region price checks, arbitrage scanning, build cost analysis
- **Threat assessment** — system security analysis, kill activity, real-time gatecamp alerts
- **Skill planning** — training time estimates, "Easy 80%" plans, T2 requirement checks
- **Mining & exploration** — ore recommendations, site analysis, hacking guidance
- **Faction personas** — optional roleplay mode with 5 faction-specific AI personalities
- **40+ slash commands** — or just ask naturally: *"is Uedama safe"*, *"fit my Vexor for L2s"*, *"what should I mine"*

### What ARIA Is Not

- **Not a bot** — ARIA cannot control your ship or automate gameplay
- **Not a game overlay** — it runs in your terminal via Claude Code
- **Not affiliated with CCP** — this is a fan project using public ESI/SDE APIs
- **Not required for EVE** — it enhances your experience with tactical advice

---

## Requirements

- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** with an active [Anthropic API plan](https://console.anthropic.com/)
- **[uv](https://docs.astral.sh/uv/)** (Python package manager)
- **Python 3.11+**
- **An EVE Online account** (any faction, Alpha or Omega)

---

## Platform Support

- **Supported:** Linux, macOS, WSL2 (Windows 11)
- **Unsupported:** Native Windows shells (PowerShell/CMD/Git Bash)

---

## Quick Start

### Option A: DevContainer (zero host setup)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) and VS Code with the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension.

```bash
git clone https://github.com/LuminaireCognition/aria.git
code aria
# VS Code prompt: "Reopen in Container" → click yes
# Wait ~3 minutes (first build), then in the container terminal:
./aria-init
claude
```

### Option B: Local Setup

```bash
# 1. Clone the repository
git clone git@github.com:LuminaireCognition/aria.git
# or (HTTPS)
git clone https://github.com/LuminaireCognition/aria.git
cd aria

# 2. Run the setup wizard (downloads ~100MB of game data)
./aria-init

# 3. Launch ARIA
claude
```

### Verify It Worked

After running `./aria-init` you should see:

```
✓ Dependencies installed
✓ Game data seeded
✓ Claude Code hooks configured
```

Quick checks:

```bash
ls userdata/pilots/          # should list your pilot directory
ls -la .claude/hooks/aria-boot.sh  # should be executable (-rwxr-xr-x)
```

If either is missing, re-run `./aria-init`. For detailed first-run guidance, see [docs/FIRST_RUN.md](docs/FIRST_RUN.md).

---

## Using ARIA

Start a session from the repo root:

```bash
claude
```

Setup paths:

- From your shell, run `./aria-init` for first-time bootstrap, local file generation, and game data seeding.
- Inside Claude Code, run `/setup` to configure or update your pilot profile conversationally.

You can also run the CLI directly for data lookups and utilities:

```bash
uv run aria-esi --help
```

---


## See It In Action

> **Note:** These are real ARIA responses, not mockups. ARIA uses natural language — no special syntax needed.

### Mission Brief

```text
❯ I need to run level 2 Damsel in Distress in a Vexor.
```

```text
Damsel in Distress L2 — Mission Brief

| | Details |
|---|---|
| Tank | Thermal / Kinetic |
| Deal | Kinetic & Thermal |
| EWAR | None noted |
| Objective | Destroy Kruul's Pleasure Hub, loot "The Damsel" |

Blitz
1. Warp in — do not shoot Kruul (triggers 10x elite frigates)
2. Destroy Kruul's Pleasure Hub — stay 5–10 km (AoE on destruction)
3. Loot "The Damsel" from the wreck
4. Warp out

Spawns
- Initial (10–20 km, auto-aggro): 8x Frigate (Kruul's Henchman), 1x Cruiser (Kruul)
- Reinforcement (triggered by attacking Kruul): 10x Elite Frigate (Mercenary Elite Fighter)

Tactical Notes
- Blitz avoids the reinforcement wave entirely — ignore Kruul
- Pleasure Hub AoE can hurt at close range; orbit at 5–10 km while destroying it
- Cruiser-class ship recommended; a Vexor handles this comfortably

Sources: Wiki:fetched (EVE University Wiki — The Damsel in Distress L2)
Tip: /mission-brief Damsel in Distress --fit for a tailored ship fitting
```

<details>
<summary>More examples: Route Planning, Fit Recommendation</summary>

#### Route Planning

```text
❯ Route from Dodixie to Jita, safest route.
```

```text
Route: Dodixie → Jita

Mode: Safest | Jumps: 15 | Threat: ELEVATED

| System      | Sec | Ships | Pods | Jumps | Notes                          |
|-------------|-----|------:|-----:|------:|--------------------------------|
| Dodixie     | 0.9 |     1 |    0 |   561 | Trade hub                      |
| Botane      | 0.9 |     0 |    0 |   691 |                                |
| Erme        | 0.8 |     0 |    0 |   383 |                                |
| Grinacanne  | 0.8 |     0 |    0 |   115 |                                |
| Renyn       | 0.9 |     0 |    0 |   692 | Region border                  |
| Algogille   | 0.9 |     1 |    0 |   778 |                                |
| Kassigainen | 0.9 |     0 |    0 |   946 | Caldari border                 |
| Hatakani    | 0.9 |     1 |    0 | 1,042 |                                |
| Sivala      | 0.5 |     0 |    0 | 1,038 | Adjacent low-sec               |
| Uedama      | 0.5 |     2 |    1 | 1,007 | Gank pipe — 3 kills last hour  |
| Haatomo     | 0.6 |     1 |    0 |   183 |                                |
| Suroken     | 0.7 |     0 |    0 |   461 |                                |
| Kusomonmon  | 0.8 |     0 |    0 |   414 |                                |
| Urlen       | 1.0 |     0 |    1 | 1,750 |                                |
| Perimeter   | 1.0 |     6 |    0 | 2,085 | Jita gate                      |
| Jita        | 0.9 |    21 |    8 | 2,729 | Trade hub                      |

Security: 15 high-sec jumps. Lowest: Uedama (0.5) — known ganking system.
Fly aligned, don't autopilot through Sivala/Uedama.

Activity data from last hour.
Sources: ESI route, ESI activity (real-time healthy)
```

#### Fit Recommendation

```text
❯ Give me a Vexor fit for level 2 missions using T1/meta modules.
```

```text
[Vexor, L2 Missions - T1/Meta]

Drone Damage Amplifier I
Drone Damage Amplifier I
Medium Armor Repairer I
Multispectrum Energized Membrane I
Reactive Armor Hardener

10MN Y-S8 Compact Afterburner
Large Compact Pb-Acid Cap Battery
Cap Recharger I
Drone Navigation Computer I

Drone Link Augmentor I
[Empty High slot]
[Empty High slot]
[Empty High slot]

Medium Auxiliary Nano Pump I
Medium Auxiliary Nano Pump I
Medium Nanobot Accelerator I


Hammerhead I x5
Hobgoblin I x5

Fitting engine: 124 DPS | 10,284 EHP | CPU 73.7% | PG 60.3%
Orbit at 30–40 km, drones do the work. Hammerheads for cruisers,
swap to Hobgoblins for frigates. AB keeps you cap stable.
Sources: Archetype library (Vexor L2/meta), EOS validation (pilot skills)
```

</details>

---

## ESI Integration (Optional)

ARIA works without ESI. If you want live character data, run the setup wizard:

```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

Details: [docs/ESI.md](docs/ESI.md)

---

## Data Freshness & Trust

ARIA pulls data from multiple sources with different update frequencies. Market prices and kill activity refresh in near-real-time; mission intel is cached from EVE University Wiki; static ship/module data comes from CCP's SDE. All data is verified against authoritative sources before presentation — ARIA never presents unverified training-data as fact.

For deeper details:

- [dev/docs/DATA_SOURCES.md](dev/docs/DATA_SOURCES.md) — where each data type originates and how it's updated
- [dev/docs/ai-runtime/DATA_TRUST.md](dev/docs/ai-runtime/DATA_TRUST.md) — how ARIA validates game data and data authority hierarchy
- [docs/ESI.md](docs/ESI.md) — live character data setup and token lifecycle
- [SECURITY.md](SECURITY.md) — threat model, path validation, prompt injection defenses

---

## Development Setup

```bash
# Install dependencies (creates .venv automatically)
uv sync --dev

# Run tests
uv run pytest

# Run ESI sync
uv run aria-esi esi-sync
```

---

## Troubleshooting

### `./aria-init: Permission denied`

```bash
chmod +x aria-init
./aria-init
```

### Missing game data after init

If ARIA warns about missing SDE or universe data:

```bash
./aria-init --seed-only
```

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
- No telemetry. ARIA only calls external services needed for game data:
- CCP ESI API (optional, only when you enable ESI integration)
- Fuzzwork market endpoints (market pricing)
- EVE University Wiki pages for mission intel (cached locally)
- zKillboard RedisQ stream (optional, only when real-time intel is enabled)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute configurations, PvE intel, reference data, skills, personas, and code.

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

Ship fittings, mission tactics, and strategic recommendations are provided **without warranty**, express or implied. The developers and contributors accept no liability for lost vessels or empty wallets. Never undock what you can't afford to lose.

See [ATTRIBUTION.md](ATTRIBUTION.md) for complete attribution details.

---

*by Luminaire Cognition [LUCOS]*
