# Frequently Asked Questions

## General

### Can ARIA control my ship?

No. ESI is read-only. ARIA provides advice and intel - you execute in-game. It cannot undock, warp, shoot, or perform any game actions.

### Is my data sent anywhere?

No external telemetry. ARIA only makes calls to:
- CCP's ESI API (if you enable ESI integration)
- Fuzzwork for market data
- EVE University Wiki for mission intel (cached locally)

Your pilot profiles and credentials stay on your machine.

### Does this work offline?

Partially. These work offline:
- Reference data (damage profiles, mechanics)
- Skill documentation
- Cached mission intel
- Fitting advice (general)

These need internet:
- Live market prices
- System activity/kills
- Current location (ESI)
- Real-time gatecamp detection

### Can I use this commercially?

No. EVE Online content is subject to CCP's [Developer License Agreement](https://developers.eveonline.com/license-agreement) which prohibits commercial use. While ARIA's code is MIT-licensed, any use incorporating EVE data must comply with CCP's terms.

### Is ARIA affiliated with CCP?

No. ARIA is an independent fan project. It is not affiliated with, endorsed by, or sponsored by CCP Games. ARIA is not related to AURA, CCP's in-game AI assistant.

## Setup & Configuration

### Do I need ESI?

No. ARIA works fully without ESI. All tactical features, mission briefs, fitting assistance, and reference data work out of the box. ESI is an optional upgrade for automatic data sync.

### Alpha clone friendly?

Yes. All features work regardless of clone state. ARIA doesn't check or restrict based on Omega status.

### Can I use multiple characters?

Yes. ARIA supports multiple pilots with separate profiles and credentials. See [MULTI_PILOT_ARCHITECTURE.md](MULTI_PILOT_ARCHITECTURE.md).

### How do I switch characters?

Edit `userdata/config.json` and change `active_pilot` to the character ID, then start a new session. Or run `./aria-init` to reconfigure.

## Features

### Why is roleplay off by default?

Most users want quick answers, not theater. The RP system is comprehensive but opt-in. Enable it in your pilot profile if you want faction personas and immersive framing.

### What's the difference between RP levels?

| Level | Behavior |
|-------|----------|
| `off` | Just the facts, no persona |
| `on` | Faction voice, professional tone |
| `full` | Full immersion, in-universe framing |

### How accurate is the market data?

Market prices come from Fuzzwork (aggregated from ESI). Data is typically 5-15 minutes old. For time-sensitive trades, verify in-game.

### How current is the activity/kill data?

System activity (kills, jumps) comes from ESI and is typically 1 hour old. Real-time gatecamp detection uses zKillboard's RedisQ feed when enabled.

## Troubleshooting

### ARIA gives wrong information about game mechanics

ARIA verifies data against SDE and trusted sources, but mistakes can happen. If you find an error, check:
1. Is it a recent game change? SDE updates lag patches.
2. Is it mission-specific? Wiki data may be outdated.

Report issues at the GitHub repository.

### Commands aren't working

Make sure you're running inside Claude Code (`claude` command). ARIA slash commands only work within the Claude Code environment, not in a regular terminal.

### ESI data seems stale

Token may need refresh:
```bash
.claude/scripts/aria-refresh
```

Or check token status:
```bash
.claude/scripts/aria-refresh --check
```

### How do I keep tokens fresh automatically?

Set up scheduled token refresh to run every 15 minutes in the background:

**macOS / Linux:**
```bash
crontab -e
# Add: */15 * * * * /path/to/EveOnline/.claude/scripts/aria-refresh --quiet 1> /dev/null
```

**Windows:** Use Task Scheduler. See [ESI.md](ESI.md#scheduled-token-refresh) for detailed setup instructions.
