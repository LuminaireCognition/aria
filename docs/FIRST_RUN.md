# ARIA First Run Setup

Welcome, Capsuleer! This guide will help you configure ARIA for your character.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) with an active [Anthropic API plan](https://console.anthropic.com/)
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Python 3.11+
- An EVE Online character (any faction)

All commands below should be run from the repository root (`cd aria`).

## DevContainer Setup (Docker Desktop)

If you have **Docker Desktop** and **VS Code**, you can skip all local installation:

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) VS Code extension
2. Clone the repo and open it in VS Code:
   ```bash
   git clone https://github.com/LuminaireCognition/aria.git
   code aria
   ```
3. When prompted, click **"Reopen in Container"** (or run `Dev Containers: Reopen in Container` from the command palette)
4. Wait ~3 minutes for the first build (installs Python, Claude Code, and seeds game data)
5. In the container terminal:
   ```bash
   ./aria-init    # Configure your pilot
   claude         # Start ARIA
   ```

The container includes Python 3.13, uv, Claude Code CLI, and all game data — nothing to install on your machine. Your `userdata/` (pilot profiles, credentials) persists across container rebuilds via a Docker volume.

For ESI OAuth inside the container, port 8421 is forwarded automatically. Run `uv run python .claude/scripts/aria-oauth-setup.py` as normal.

---

## Quick Setup (Recommended)

Run the interactive setup wizard:

```bash
./aria-init
```

The wizard will:
1. Ask for your character name and faction
2. Configure ARIA's personality to match your faction
3. Set up your home region and playstyle
4. Generate all required data files
5. Download game data caches (~100MB) — SDE database, fitting engine, market prices, sovereignty map, persona context

That's all you need! ARIA is fully functional after this step.

> **Tip:** Use `./aria-init --skip-seed` to defer the download. Run `./aria-init --seed-only` later to seed game data without re-running the full wizard.
ESI integration is optional and can be added anytime later.

After the wizard completes:

```bash
claude
```

ARIA will greet you with a faction-appropriate boot sequence.

---

## Manual Setup (Alternative)

If you prefer to configure files manually:

### Step 1: Create Pilot Directory via ESI (Optional)

If you plan to use ESI, running it first creates your pilot directory structure automatically:

```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

This creates:
- `userdata/pilots/{character_id}_{name}/` directory with all profile files
- `userdata/credentials/{character_id}.json` for authentication

### Step 2: Configure Your Pilot Profile

Edit `userdata/pilots/{your_pilot}/profile.md`:

#### 2.1 Set Your Identity

```markdown
- **Character Name:** [Your character name]
- **Corporation:** [Your corp]
```

#### 2.2 Choose Your Faction

This determines ARIA's personality and cultural expressions:

```markdown
- **Primary Faction:** [GALLENTE/CALDARI/MINMATAR/AMARR/PIRATE/ANGEL_CARTEL/SERPENTIS/GURISTAS/BLOOD_RAIDERS/SANSHAS_NATION]
```

| Faction | AI Persona | Style |
|---------|------------|-------|
| Gallente | ARIA Mk.IV | Libertarian, cultured, witty |
| Caldari | AURA-C | Corporate, efficient, formal |
| Minmatar | VIND | Direct, passionate, tribal |
| Amarr | THRONE | Reverent, dignified, imperial |
| Pirate (and pirate subfactions) | PARIA variants | Opportunistic, ruthless, underworld tone |

> **Note:** The `aria-init` wizard only offers the four empire factions. To use pirate factions, set the faction field manually here or use `/setup` inside Claude Code.

For full faction/persona mapping (including pirate variants), see [PERSONA_LOADING.md](PERSONA_LOADING.md#faction-to-persona-mapping).

#### 2.3 Define Your Playstyle

Set any self-imposed restrictions or focus areas in the Playstyle section.

### Step 3: Configure Operational Profile

Edit `userdata/pilots/{your_pilot}/operations.md`:

1. Set your **Home Region** and **Primary Station**
2. Define your **Primary Activities**
3. Ship roster is managed in `ships.md` (populated by ESI sync)

### Step 4: Launch ARIA

```bash
claude
```

---

## ESI Integration (Optional - Add Later)

ARIA is fully functional without ESI. All tactical features work immediately.

**ESI is a convenience enhancement** - add it when you're comfortable with ARIA.

### Without ESI (What You Have Now)

| Data | How to Update |
|------|---------------|
| Standings | Edit `userdata/pilots/{your_pilot}/profile.md` periodically |
| Ship roster | Edit `userdata/pilots/{your_pilot}/ships.md` when you acquire ships |
| Location | Tell ARIA: "I'm heading to Dodixie" |

All mission briefs, threat assessments, fitting help, and reference data work fully.

### With ESI (When Ready)

ESI adds automatic tracking:
- Location and ship detection
- Live standings sync
- Wallet monitoring
- Skill tracking

### Setup ESI (5 minutes, when you're ready)

```bash
uv run python .claude/scripts/aria-oauth-setup.py
```

The wizard guides you through creating an EVE Developer app and authorizing.

**Detailed guide:** [ESI.md](ESI.md)

---

## Updating Your Profile

Fill these files in as you play:

| File | Purpose | When to Update |
|------|---------|----------------|
| `userdata/pilots/{your_pilot}/ships.md` | Ship roster | Updated by ESI sync |
| `userdata/pilots/{your_pilot}/missions.md` | Mission history | After completing missions |
| `userdata/pilots/{your_pilot}/exploration.md` | Site discoveries | After exploration runs |
| `userdata/pilots/{your_pilot}/industry/blueprints.md` | BPO inventory | After purchases (or ESI sync) |

---

## Changing Your Faction (Switching Personas)

Want to try a different AI persona? You can switch factions anytime.

### What Changes

| Aspect | Before → After Example |
|--------|------------------------|
| AI Persona Name | ARIA Mk.IV → AURA-C |
| Boot Greeting | "Freedom through knowledge" → "Efficiency is the path to victory" |
| Cultural Expressions | Libertarian wit → Corporate precision |
| Default Ship Recommendations | Gallente hulls → Caldari hulls |

### What Stays the Same

- All your logs (`missions.md`, `exploration.md`)
- Your ship fittings and status
- ESI credentials (tied to character, not faction)
- Blueprint library and industry data

### How to Switch

**Step 1:** Edit your pilot profile (`userdata/pilots/{your_pilot}/profile.md`)

Change the Primary Faction field:
```markdown
- **Primary Faction:** CALDARI
```

Valid options include empire and pirate factions:
`GALLENTE`, `CALDARI`, `MINMATAR`, `AMARR`, `PIRATE`, `ANGEL_CARTEL`, `SERPENTIS`, `GURISTAS`, `BLOOD_RAIDERS`, `SANSHAS_NATION`

> **Note:** The `aria-init` wizard only supports empire factions. Pirate factions must be set manually in the profile or via `/setup` inside Claude Code.

**Step 2:** Update related fields (optional but recommended)

| Field | Example Change |
|-------|----------------|
| Mission Provider | Federation Navy → Caldari Navy |
| Hostile Factions | Caldari State → Gallente Federation |
| Target Pirates | Serpentis → Guristas |

**Step 3:** Restart ARIA

```bash
# Exit current session, then:
claude
```

The boot sequence will now reflect your new faction persona.

### Faction Reference

| Faction | AI Name | Mission Corp | Home Region | Pirates |
|---------|---------|--------------|-------------|---------|
| Gallente | ARIA Mk.IV | Federation Navy | Sinq Laison | Serpentis |
| Caldari | AURA-C | Caldari Navy | The Forge | Guristas |
| Minmatar | VIND | Republic Fleet | Heimatar | Angel Cartel |
| Amarr | THRONE | Imperial Navy | Domain | Blood Raiders |

Note: This only changes the faction field. Update Mission Provider and other fields manually for full consistency.

---

## Troubleshooting

### ARIA doesn't adapt to my faction

Ensure your pilot profile exists at `userdata/pilots/{your_pilot}/profile.md` and has:
```markdown
- **Primary Faction:** [YOUR FACTION]
```

### Boot sequence doesn't appear

Check hook permissions:
```bash
chmod +x .claude/hooks/aria-boot.sh
```

### "File not found" errors

Run the wizard again to regenerate data files:
```bash
./aria-init
```

### Game data seeding failed

If one or more seeds failed during setup, retry just the seeding step:
```bash
./aria-init --seed-only
```

Or retry individual commands:
```bash
uv run aria-esi sde-seed       # SDE database
uv run aria-esi eos-seed       # Fitting engine
uv run aria-esi market-seed    # Market prices
uv run aria-esi sov-update     # Sovereignty map
uv run aria-esi persona-context # Persona compilation
```

### ESI token expired

```bash
.claude/scripts/aria-refresh
```

---

## Examples

See `examples/` for complete reference configurations you can copy and customize:

- **`examples/gallente-selfsufficient/`** - Gallente self-sufficient playstyle. Mines ore, runs missions for standings, and manufactures ships and modules. A well-rounded "do everything" profile that prioritizes independence over ISK/hour efficiency.

- **`examples/caldari-mission-runner/`** - Caldari L4 mission runner. Optimized for ISK/hour with a dedicated mission-running ship roster. Focused on grinding Caldari Navy standings to unlock L4 agents and maximize LP payouts.

- **`examples/minmatar-explorer/`** - Minmatar nomadic explorer. Roams wormholes and nullsec in scanning frigates and covops ships. No fixed home — moves between regions following relic sites and data sites for profit.

- **`examples/amarr-industrialist/`** - Amarr industrialist. Mining-to-manufacturing pipeline focused on T1 ship production. Tracks blueprints, material efficiency research, and profit margins across multiple production lines.

---

## Need Help?

- Talk to ARIA: Just ask naturally in conversation
- Break character: Say "ARIA, drop RP" for out-of-character discussion
- Resume roleplay: Say "ARIA, resume"
