---
name: first-run-setup
description: Conversational first-run configuration for new ARIA users. Guides capsuleer through profile setup via dialogue.
model: sonnet
category: system
triggers:
  - "/setup"
  - "/first-run-setup"
  - "set up my profile"
  - "configure ARIA"
  - "first run"
  - "help me set up"
requires_pilot: false
disable-model-invocation: true
---

# ARIA First-Run Setup Module

## Boot Hook State (Skip Redundant Checks)

The boot hook output includes a machine-readable state line:
```
<!-- aria:state fresh_install=true credentials=false pilot=none -->
```

**Use this to skip redundant file checks:**
- `fresh_install=true` → No need to check if profile exists
- `credentials=true` → Skip ESI connection prompt, go straight to character detection
- `pilot={id}` → Active pilot ID if configured

**DO NOT** run `ls userdata/` or `Read userdata/config.json` if boot hook already provided state.

## Preflight Checks

Before starting setup, verify dependencies:

```bash
# Check mcp module (required for persona-context)
uv run python -c "import mcp" 2>/dev/null || echo "MISSING: mcp"
```

If mcp is missing, warn user:
```
Note: The 'mcp' package is not installed. Persona features will be
limited. Run 'uv sync' to install all dependencies.
```

Continue setup anyway - it's not blocking.

## Initial Output Requirement

This skill MUST always produce output on first invocation. Even if ESI is unavailable, boot context is missing, or the environment is constrained, output at minimum:

1. A welcome/greeting message
2. The first setup question (ESI connection or character name)

An empty response is never acceptable for the onboarding skill.

## Conversation Flow

### Phase 1: ESI Connection (Background Polling)

**Check boot hook state first.** If `credentials=true`, skip to Phase 2.

**If NO credentials (from boot state or first check):**

1. **Ask user if they want to connect ESI:**
```
ARIA works best when linked to your EVE character via ESI.
This enables skill tracking, asset management, and market tools.

Connect now? (yes/skip)
```

2. **If "yes", start background watcher and instruct user:**
   - Run the credential watcher in background: `uv run python .claude/scripts/aria-credential-watch.py --timeout 300`
   - Tell user to run `uv run python .claude/scripts/aria-oauth-setup.py` in their terminal
   - Wait for watcher to complete (it outputs JSON with `status` and `character_id`)
   - If `status: found`, continue with the character ID; if `status: timeout`, offer retry

3. **On success, continue immediately:**
```
✓ Credentials detected for character {char_id}!

Fetching your character data from ESI...
```

Then continue to Phase 2.

4. **On timeout, offer options:**
```
Haven't detected new credentials yet.

Type "retry" to watch again, or "skip" for manual setup.
```

**If "skip":** Continue to Manual Setup flow (Phase 1b).

**If credentials ALREADY exist:**
Skip directly to Phase 2.

### Phase 1b: Manual Setup (Skip ESI)

If user skips ESI, fall back to asking questions:

```
No problem! You can connect ESI later with /setup.

What's your character name?
```

Then ask: faction, experience, rp_level (using consolidated AskUserQuestion).
Skip to Phase 4.

### Phase 2: Character Detection (ESI Connected)

After ESI OAuth completes, read the character data:

1. Check `userdata/credentials/` for new credential file
2. Extract character_id from filename
3. Call ESI endpoints to fetch:
   - `/characters/{id}/` → name, corporation_id, alliance_id, birthday
   - `/corporations/{corp_id}/` → corporation name
   - `/alliances/{alliance_id}/` → alliance name (if any)
   - `/characters/{id}/standings/` → faction standings
   - `/characters/{id}/skills/` → total SP (for experience hint)

Display the detected information:

```
═══════════════════════════════════════════════════════════════════
CHARACTER DETECTED
───────────────────────────────────────────────────────────────────
✓ Connected to EVE Online

  Character:   Suwayyah
  Corporation: Federal Navy Academy
  Alliance:    -
  Born:        YC127.03.15 (1 year capsuleer)
  Total SP:    8,450,000

Based on your standings, I suggest the Gallente persona (ARIA).
───────────────────────────────────────────────────────────────────
```

### Phase 3: Preferences (Single Combined Prompt)

Present all three preferences in a single message and ask the user to respond:

1. **Faction persona** — Gallente (ARIA), Caldari (AURA-C), Minmatar (VIND), Amarr (THRONE). Mark recommended based on highest ESI standing.
2. **RP level** — Off (recommended), On, Full
3. **Experience** — New, Intermediate, Veteran. Recommend based on SP (< 5M = New, 5-50M = Intermediate, > 50M = Veteran).

### Phase 4: Save (No Separate Confirmation)

After user answers preferences, **immediately save** - don't ask "Save this configuration?"

Show brief summary as you save:
```
Saving profile...
  Character: Suwayyah (ESI) | Faction: Gallente | RP: Off | Experience: Intermediate
```

Then proceed to Profile Generation.

### Phase 5: Profile Generation

On confirmation:

1. Create pilot directory: `userdata/pilots/{character_id}_{slug}/`
2. Create subdirectories: `industry/`
3. Generate profile (see Profile Template section)
4. Update `userdata/pilots/_registry.json`
5. Update `userdata/config.json` with active_pilot
6. Run `uv run aria-esi persona-context` to generate persona context

Show completion message (faction-appropriate).

## Profile Template

Generate the pilot profile by substituting collected values:

```markdown
# Capsuleer Profile

## Identity

- **Character Name:** [character_name]
- **Character ID:** [character_id]
- **Corporation:** [corporation]
- **Alliance:** [alliance or "None"]
- **Security Status:** 0.0
- **Capsuleer Since:** [birthday_yc] <!-- YC year = real year - 1898, format: YC128.01.14 -->
- **EVE Experience:** [experience]
- **RP Level:** [rp_level]

## Faction Alignment

- **Primary Faction:** [faction]
- **Mission Provider:** [mission_corp]
- **Hostile Factions:** [hostile_factions]
- **Target Pirates:** [target_pirates]

## Playstyle

- [x] General gameplay

## Standings

### Empire Factions

| Faction | Standing | Relation |
|---------|----------|----------|
| Gallente Federation | [from ESI or 0.00] | [Neutral/Friendly/Allied] |
| Caldari State | [from ESI or 0.00] | [Neutral/Hostile] |
| Minmatar Republic | [from ESI or 0.00] | [Neutral] |
| Amarr Empire | [from ESI or 0.00] | [Neutral] |

### Mission Corporations

| Corporation | Standing | Access |
|-------------|----------|--------|
| [mission_corp] | 0.00 | L1 Missions |

## Current Goals

- Explore ARIA capabilities
- Train core skills
```

## Directory Structure

Create this structure for each pilot:

```
userdata/pilots/
├── _registry.json
└── {character_id}_{slug}/
    ├── profile.md           ← Generated by setup
    ├── operations.md        ← Copy from template if exists
    └── industry/
        └── .gitkeep
```

## Registry and Config Formats

Update `userdata/pilots/_registry.json` — `pilots` array with entries: `character_id`, `character_name`, `directory` (`{id}_{slug}`), `corporation`, `faction`, `added_date`. Top-level `last_updated`.

Update `userdata/config.json` — `version: "2.0"`, `active_pilot: "{character_id}"`, `last_active`.

## Slug Generation

Create URL-safe slug from character name:
1. Convert to lowercase
2. Replace spaces with underscores
3. Remove special characters (keep alphanumeric and underscores)
4. Limit to 20 characters

## Completion Messages

**All Factions (RP Off):**
```
═══════════════════════════════════════════════════════════════════
SETUP COMPLETE
───────────────────────────────────────────────────────────────────
Profile saved to: userdata/pilots/{id}_{slug}/profile.md

You're all set, [character_name]. ARIA is ready to assist with:
  • /help        - See available commands
  • /skillqueue  - Check training progress
  • /route       - Plan safe travel routes
  • /price       - Market price lookups

What would you like to do first?
═══════════════════════════════════════════════════════════════════
```

## Error Handling

### OAuth Timeout
```
I haven't detected new credentials yet.

If you completed the OAuth:
  • Check the terminal for errors
  • Ensure the callback succeeded

To retry: uv run python .claude/scripts/aria-oauth-setup.py
Or say "skip" to set up manually.
```

### ESI Fetch Failed
```
I connected but couldn't fetch your character data.
This might be a temporary CCP API issue.

Let's continue with manual setup for now.
You can re-run /setup later to sync with ESI.
```

### File Write Error
```
I couldn't save your profile. Please check:
  • userdata/pilots/ directory exists
  • File permissions allow writing

Or create the profile manually (run ./aria-init to regenerate).
```

