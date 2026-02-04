# ARIA - Adaptive Reasoning & Intelligence Array

[![CI](https://github.com/availlancourt/aria/actions/workflows/ci.yml/badge.svg)](https://github.com/availlancourt/aria/actions/workflows/ci.yml)

**Ship-Board AI Framework for EVE Online**

> **This is a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) extension.** It transforms Claude into a tactical EVE Online assistant with mission briefs, fitting advice, market analysis, and more.

```
═══════════════════════════════════════════════════════════════════
    ___    ____  _________
   /   |  / __ \/  _/   |   Adaptive Reasoning & Intelligence Array
  / /| | / /_/ // // /| |   Ship-Board Tactical Assistant
 / ___ |/ _, _// // ___ |
/_/  |_/_/ |_/___/_/  |_|   "Your faction. Your rules. Your AI."
═══════════════════════════════════════════════════════════════════
```

ARIA is a tactical assistant for EVE Online, powered by [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (Anthropic's AI-powered CLI tool). It provides mission briefs, fitting advice, threat assessment, mining guidance, and exploration tips. Roleplay mode is available but **off by default** - most users just want the facts.

## Requirements

- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** - Anthropic's AI coding assistant (required)
- **An EVE Online character** - Any faction works
- **[uv](https://docs.astral.sh/uv/)** - Python package manager (for ESI integration, optional)

**Full documentation:** [docs/README.md](docs/README.md) | **Quick reference:** [docs/TLDR.md](docs/TLDR.md)

---

## Quick Start

### New Users

```bash
# 1. Clone or fork this repository
git clone <your-fork-url>
cd aria

# 2. Run the setup wizard
./aria-init

# 3. Launch ARIA
claude
```

> **Note:** This is a template repository. Fork it to your own GitHub account, or download and push to your own repo. Your pilot profiles and credentials stay local to your copy.

The wizard guides you through:
- Character name and faction selection
- Experience level (affects explanation depth)
- Roleplay preference (off by default)

That's it! ESI integration is optional and can be added later.

### Returning Users

```bash
cd /path/to/your/aria-installation
claude
```

ARIA starts and you can immediately ask questions.

### ARIA In Action

**Mission Intelligence**

```
You: Brief me on The Blockade against Serpentis

┌─────────────────────────────────────────────────────┐
│ THE BLOCKADE (L4) - Serpentis Corporation           │
├─────────────────────────────────────────────────────┤
│ DAMAGE PROFILE                                      │
│   Incoming: Kinetic 55% / Thermal 45%               │
│   Tank:     Kinetic primary, Thermal secondary      │
│   Deal:     Thermal (best) > Kinetic                │
│                                                     │
│ THREATS                                             │
│   ⚠ Sensor dampeners - bring ECCM or close range   │
│   ⚠ Heavy alpha from BS in wave 3                  │
│                                                     │
│ RECOMMENDATION                                      │
│   Passive shield tank, drone DPS                    │
│   Stay mobile, kill frigates first                  │
└─────────────────────────────────────────────────────┘
```

**Real-Time Threat Assessment**

```
You: Is Uedama safe?

⚠️ HIGH RISK - Active gatecamp detected

│ System │  Sec  │ Ship Kills │ Pod Kills │ Status            │
│ Uedama │  0.50 │         12 │         8 │ Gank fleet active │

Last kill: 4 minutes ago (Obelisk, 2.1B ISK)
Recommendation: Use Ahbazon bypass (+3 jumps) or scout ahead
```

**Situational Awareness**

```
You: Just jumped into Tama, orient me

═════════════════════════════════════════════
TAMA (The Citadel) - Security: 0.3
═════════════════════════════════════════════
THREAT LEVEL: EXTREME
  23 ship kills within 5 jumps (last hour)

AVOID              ESCAPE ROUTES
├─ Tama (gate)     ├─ Highsec: 1j → Nourvukaiken
├─ Sujarento       └─ Lowsec:  2j → Okkamon
└─ Nennamaila

Faction Warfare frontline - expect frigate gangs
```

With roleplay mode enabled, responses include faction persona voice and in-universe framing. See [Roleplay Mode](#roleplay-mode-opt-in) below.

### What ARIA Is Not

- **Not a bot** - ARIA cannot control your ship or automate gameplay
- **Not a game overlay** - It's a conversational assistant you run in terminal
- **Not required for EVE** - It's an enhancement for players who want tactical advice
- **Not connected to CCP** - This is a fan project using public APIs

### Example Configurations

Not sure how to configure your pilot? Start with a pre-built example:

| Example | Playstyle | Focus |
|---------|-----------|-------|
| [gallente-selfsufficient](examples/gallente-selfsufficient/) | No market trading | Mining, manufacturing, self-reliance |
| [caldari-mission-runner](examples/caldari-mission-runner/) | ISK optimization | L4 missions, LP store conversion |
| [minmatar-explorer](examples/minmatar-explorer/) | Nomadic | Wormholes, nullsec, ghost sites |
| [amarr-industrialist](examples/amarr-industrialist/) | Vertical integration | Blueprint research, T1 production |

Copy an example to your pilot directory and customize:
```bash
cp -r examples/gallente-selfsufficient/* userdata/pilots/YOUR_PILOT/
```

See [examples/README.md](examples/README.md) for detailed descriptions.

### Development Setup

ARIA uses [uv](https://docs.astral.sh/uv/) for Python dependency management.

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: brew install uv

# Install dependencies (creates .venv automatically)
uv sync

# Run tests
uv run pytest

# Run a script
uv run python .claude/scripts/aria-esi-sync.py
```

**Optional extras:**
- `dev` - pytest, mypy, ruff (for development)
- `resilient` - tenacity (enhanced retry logic for ESI)
- `fitting` - eos (ship fitting calculations)
- `full` - all optional dependencies

Core functionality (MCP server, ESI client, routing) works with just `uv sync`.

### Type Safety

ARIA uses **gradual typing adoption** for maintainability without blocking development velocity.

| Phase | Status | Focus |
|-------|--------|-------|
| Phase 1 | ✅ Complete | Baseline - syntax errors, undefined names |
| Phase 2 | ✅ Complete | `union-attr`, `attr-defined` - dict/list annotations |
| Phase 3 | ✅ Complete | `arg-type`, `return-value` - function signatures |
| Phase 4 | 🔜 Next | `disallow_untyped_defs` on core modules |
| Phase 5 | Planned | Strict mode on all modules |

Run type checking with:
```bash
uv run mypy .
```

See `pyproject.toml` for the full mypy configuration and roadmap comments.

### Use Slash Commands

ARIA has 40+ specialized commands. Key ones by category:

| Category | Commands |
|----------|----------|
| **Tactical** | `/mission-brief`, `/threat-assessment`, `/fitting`, `/route`, `/gatecamp` |
| **Navigation** | `/route`, `/orient`, `/gatecamp` |
| **Financial** | `/price`, `/arbitrage`, `/assets`, `/orders` |
| **Operations** | `/mining-advisory`, `/exploration`, `/pi`, `/skillplan` |
| **Identity** | `/aria-status`, `/pilot`, `/standings`, `/skillqueue` |

Type `/help` to see all available commands.

---

## Roleplay Mode (Opt-In)

Roleplay is **off by default**. ARIA provides EVE knowledge without persona, formatted boxes, or in-universe framing.

To enable immersive mode, set `rp_level` in your pilot profile:

| Level | What You Get |
|-------|--------------|
| `off` | Just the facts (default) |
| `on` | Faction persona voice, professional tone |
| `full` | Full immersion with faction AI persona |

### Faction Personas (RP Mode)

When roleplay is enabled (`on` or `full`), ARIA adapts to your faction:

| Faction | AI Persona | Cultural Style |
|---------|------------|----------------|
| Gallente | ARIA Mk.IV | Libertarian, cultured, witty |
| Caldari | AURA-C | Corporate, efficient, formal |
| Minmatar | VIND | Direct, passionate, tribal |
| Amarr | THRONE | Reverent, dignified, imperial |
| Pirate | PARIA | Outlaw code, sardonic wit |

Your faction is set during `/setup`. With roleplay enabled, you'll get faction-appropriate greetings, formatted tactical reports, and in-universe framing.

ARIA respects your playstyle choices regardless of RP setting.

---

## ESI Integration (Optional Enhancement)

ARIA works fully without ESI. All tactical features, mission briefs, fitting assistance, and reference data work out of the box.

**ESI is an optional upgrade** you can add later when you're comfortable with ARIA. It enables automatic tracking instead of manual file updates. Multiple characters are supported - each pilot gets their own profile directory and credentials.

### Without ESI (Default Experience)

| Feature | How It Works |
|---------|--------------|
| Your standings | Update `userdata/pilots/{your_pilot}/profile.md` periodically |
| Ship fittings | Update `userdata/pilots/{your_pilot}/ships.md` when you refit |
| Current location | Tell ARIA: "I'm in Dodixie" |
| All tactical features | Work fully - mission briefs, fittings, threat assessment |

### With ESI (When You're Ready)

| Feature | Benefit |
|---------|---------|
| Location awareness | ARIA detects your current system and ship |
| Live standings | Automatic sync from the game |
| Wallet tracking | Track ISK balance changes |
| Skill monitoring | See training progress |

### Setup ESI (5 minutes)

When you're ready for automatic data sync:

```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

The wizard guides you through:
1. Creating an EVE Developer application
2. Authorizing your character
3. Saving credentials automatically

**Detailed guide:** [docs/ESI.md](docs/ESI.md)

---

## Project Structure

```
aria/
├── README.md                    # This file
├── CLAUDE.md                    # ARIA's core configuration
├── LICENSE                      # MIT License
├── aria-init                    # Setup wizard
│
├── docs/                        # Documentation
│   ├── README.md                # Documentation index (start here)
│   ├── TLDR.md                  # Quick reference
│   ├── FIRST_RUN.md             # Setup guide for new users
│   └── ...                      # See docs/README.md for full list
│
├── personas/                    # Faction AI personas (RP mode)
│   ├── aria-mk4/                # Gallente persona
│   ├── aura-c/                  # Caldari persona
│   ├── vind/                    # Minmatar persona
│   ├── throne/                  # Amarr persona
│   ├── paria/                   # Pirate persona
│   └── _shared/                 # Shared persona resources
│
├── .claude/
│   ├── hooks/                   # Session hooks
│   ├── scripts/                 # Utility scripts
│   └── skills/                  # 40+ slash commands
│
├── src/aria_esi/                # Python package
│   ├── commands/                # CLI commands
│   ├── mcp/                     # MCP server tools
│   └── services/                # Core services
│
├── userdata/                    # User data (gitignored)
│   ├── config.json              # Active pilot selection
│   ├── credentials/             # ESI tokens per pilot
│   └── pilots/                  # Per-pilot profiles
│
├── reference/                   # Game reference data
│   ├── mechanics/               # Static game data
│   ├── archetypes/              # Ship fitting library
│   └── missions/                # Mission intel cache
│
└── templates/                   # Profile templates
```

---

## Personalizing ARIA

### Update Your Pilot Profile

Edit your pilot profile at `userdata/pilots/{your_pilot}/profile.md` with:
- Current standings
- Skill focus
- Goals

### Track Your Ships

Edit `userdata/pilots/{your_pilot}/ships.md` with your current fittings. ARIA can reference this for fitting advice.

### Mission Log

Use `userdata/pilots/{your_pilot}/missions.md` to track:
- Completed missions
- Standing progress
- Lessons learned

ARIA can reference your history in conversation.

---

## Commands Reference

### Talking to ARIA

ARIA responds to natural conversation. Some examples:

| You Say | ARIA Does |
|---------|-----------|
| "Status report" | Full operational summary |
| "I'm going to mine in Dodixie" | Updates context, offers advice |
| "Mission brief for Serpentis" | Tactical intelligence |
| "Is Hek safe?" | Threat assessment |
| "What's Plagioclase good for?" | Mining/industry info |
| "Tell me about the Federation" | Lore discussion |

### Roleplay Toggle (When RP Enabled)

If you've enabled roleplay mode (`on` or `full`):

| Command | Effect |
|---------|--------|
| "ARIA, drop RP" | Temporarily disable roleplay |
| "ARIA, resume" | Re-enable roleplay |

### CLI Commands

ARIA includes a command-line interface for direct queries outside of Claude:

```bash
# Route planning
uv run aria-esi route Jita Amarr --safe

# Market prices
uv run aria-esi price "Tritanium" --region jita

# System activity
uv run aria-esi activity Tama Amamake

# List all commands
uv run aria-esi --help
```

Run `uv run aria-esi --help` for the full command list.

### Utility Scripts

```bash
# Check ESI token status
.claude/scripts/aria-refresh --check

# Refresh token manually
.claude/scripts/aria-refresh

# Force refresh
.claude/scripts/aria-refresh --force

# Run ESI setup wizard
uv run python .claude/scripts/aria-oauth-setup.py
```

---

## Troubleshooting

### ARIA isn't using roleplay mode

Roleplay is off by default. To enable it, edit your pilot profile and set:
```
- **RP Level:** on
```
Or `full` for maximum immersion. Then restart the session.

### Boot sequence doesn't appear

The hook may need permissions. Check:
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

### "Credentials not found"

You haven't set up ESI yet. This is optional - ARIA works fine without it, just without live game data. To set up:
```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

### Starting Fresh

If setup went wrong and you want to start over:

```bash
# Remove generated pilot data
rm -rf userdata/pilots/*/

# Remove pilot registry
rm -f userdata/pilots/_registry.json

# Remove active pilot config
rm -f userdata/config.json

# Re-run setup
./aria-init
```

If ESI setup failed specifically:
```bash
rm -rf userdata/credentials/
uv run python .claude/scripts/aria-oauth-setup.py
```

---

## Security

ARIA implements defense-in-depth security measures. See [SECURITY.md](SECURITY.md) for full details.

**Key protections:**
- **Path validation** - User-editable configs cannot load arbitrary files
- **Data integrity** - External data verified via SHA256 checksums before loading
- **Safe serialization** - Universe graph uses msgpack, not pickle
- **Prompt injection defense** - Persona files treated as untrusted data with security delimiters

**Credential handling:**
- OAuth tokens stored locally in `userdata/credentials/` (gitignored)
- ESI scopes are read-only - ARIA cannot modify your game state
- No telemetry or external data transmission (except ESI API calls)

---

## About

ARIA (Adaptive Reasoning & Intelligence Array) is a tactical assistant for EVE Online pilots. It provides mission intel, fitting advice, threat assessment, and exploration guidance.

**Design Philosophy:**
- **Facts first.** Roleplay is off by default. Most users want answers, not theater.
- **RP when you want it.** The immersive mode is polished and complete - faction personas, formatted tactical reports, in-universe framing. It's there for pilots who want it.
- **The flex is optional.** We built comprehensive roleplay because we could. Not because you have to use it.

**With RP Enabled (Faction Personas):**
- Gallente: Libertarian wit and cultural sophistication
- Caldari: Corporate efficiency and honor-bound duty
- Minmatar: Tribal solidarity and direct honesty
- Amarr: Imperial dignity and reverent formality
- Pirate: Outlaw code and sardonic professionalism

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

*"Your faction. Your rules. Your AI."*
