# ARIA - TL;DR

**EVE Online tactical assistant powered by Claude Code.** Mission briefs, fitting advice, threat assessment, exploration tips. Roleplay mode available but off by default.

## Install

**Option A: DevContainer** (Docker Desktop + VS Code — zero host setup):
```bash
git clone https://github.com/LuminaireCognition/aria.git
code aria    # "Reopen in Container" → wait ~3 min → ./aria-init → claude
```

**Option B: Local** (uv + Python 3.11+):
```bash
git clone https://github.com/LuminaireCognition/aria.git
cd aria
```

## Configure

Use either setup path depending on context:

```bash
# From terminal (recommended first run)
./aria-init
```

```text
# Inside Claude Code session
/setup
```

ARIA asks your name, faction, and experience level, then downloads game data (~100MB).

**Optional:** ESI integration for live game data (~5 min):
```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

## Run

```bash
cd /path/to/aria
claude
```

Just talk naturally. Ask about missions, fittings, threats, whatever.

## Commands

| Command | What it does |
|---------|--------------|
| `/help` | List all commands |
| `/aria-status` | Operational summary |
| `/mission-brief` | Enemy intel, damage types, tactics |
| `/threat-assessment` | System security analysis |
| `/fitting` | Ship fit recommendations + EFT export |
| `/mining-advisory` | Ore recommendations |
| `/exploration` | Site analysis, hacking tips |
| `/journal` | Log missions/discoveries |
| `/esi-query` | Live data (location, wallet, skills) |

Natural language works: *"is Hek safe"*, *"fit my Vexor"*, *"prepare for Serpentis"*

## Roleplay (Opt-In)

RP is off by default. To enable, set `rp_level` in your pilot profile:

| Level | What you get |
|-------|--------------|
| `off` | Just the facts (default) |
| `on` | Faction persona voice, professional tone |
| `full` | Full immersion, faction AI persona |

Edit `userdata/pilots/{your_pilot}/profile.md` and add/change:
```
- **RP Level:** on
```

## Quick Reference

- **Enable RP:** Set `rp_level` in profile (see above)
- **Re-seed game data:** `./aria-init --seed-only`
- **Check token:** `.claude/scripts/aria-refresh --check`
- **Main README:** [../README.md](../README.md)
- **Docs index:** [README.md](README.md)
- **First run guide:** [FIRST_RUN.md](FIRST_RUN.md)

---

*Inspired by [tldr-pages](https://tldr.sh/) - practical examples, no fluff.*
