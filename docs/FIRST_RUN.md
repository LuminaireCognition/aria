# ARIA First Run Setup

Welcome, Capsuleer! This guide will help you configure ARIA for your character.

## Prerequisites

- [Claude Code](https://claude.com/claude-code) installed
- An EVE Online character (any faction)

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

That's all you need! ARIA is fully functional after this step.
ESI integration is optional and can be added anytime later.

After the wizard completes:

```bash
claude
```

ARIA will greet you with a faction-appropriate boot sequence.

---

## Manual Setup (Alternative)

If you prefer to configure files manually:

### Step 1: Set Up ESI (Recommended First)

ESI setup creates your pilot directory structure automatically:

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
- **Primary Faction:** [GALLENTE/CALDARI/MINMATAR/AMARR]
```

| Faction | AI Persona | Style |
|---------|------------|-------|
| Gallente | ARIA Mk.IV | Libertarian, cultured, witty |
| Caldari | AURA-C | Corporate, efficient, formal |
| Minmatar | VIND | Direct, passionate, tribal |
| Amarr | THRONE | Reverent, dignified, imperial |

#### 2.3 Define Your Playstyle

Set any self-imposed restrictions or focus areas in the Playstyle section.

### Step 3: Configure Operational Profile

Edit `userdata/pilots/{your_pilot}/operations.md`:

1. Set your **Home Region** and **Primary Station**
2. Add your **Ship Roster** with designated roles
3. Define your **Primary Activities**

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
| Ship fittings | Edit `userdata/pilots/{your_pilot}/ships.md` when you refit |
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
| `userdata/pilots/{your_pilot}/ships.md` | Ship fittings | When you change fits |
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

- All your logs (mission_log.md, exploration_catalog.md)
- Your ship fittings and status
- ESI credentials (tied to character, not faction)
- Blueprint library and industry data

### How to Switch

**Step 1:** Edit your pilot profile (`userdata/pilots/{your_pilot}/profile.md`)

Change the Primary Faction field:
```markdown
- **Primary Faction:** CALDARI
```

Valid options: `GALLENTE`, `CALDARI`, `MINMATAR`, `AMARR`

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

Run the wizard again or ensure all templates were copied:
```bash
./aria-init
```

### ESI token expired

```bash
.claude/scripts/aria-refresh
```

---

## Examples

See `examples/` directory for reference configurations:
- `examples/gallente-selfsufficient/` - Gallente self-sufficient playstyle

---

## Need Help?

- Talk to ARIA: Just ask naturally in conversation
- Break character: Say "ARIA, drop RP" for out-of-character discussion
- Resume roleplay: Say "ARIA, resume"
