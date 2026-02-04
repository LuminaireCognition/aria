---
name: first-run-setup
description: Conversational first-run configuration for new ARIA users. Guides capsuleer through profile setup via dialogue.
model: haiku
category: system
triggers:
  - "/setup"
  - "/first-run-setup"
  - "set up my profile"
  - "configure ARIA"
  - "first run"
  - "help me set up"
requires_pilot: false
---

# ARIA First-Run Setup Module

## Purpose
Guide new capsuleers through initial profile configuration with an **ESI-first approach**. Connect to EVE first, auto-fill what we can from the API, then only ask for preferences that require human input.

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

## Design Philosophy

**ESI-First Principle:** Don't ask questions that ESI can answer.

| Data | Source | Ask User? |
|------|--------|-----------|
| Character name | ESI | NO - auto-fill |
| Corporation | ESI | NO - auto-fill |
| Alliance | ESI | NO - auto-fill |
| Character birthday | ESI | NO - auto-fill |
| Faction standings | ESI | Confirm suggestion |
| RP preference | User choice | YES - always ask |
| Experience level | User choice | YES - ask with hint |

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

```python
# Start credential watcher in background FIRST
watcher = Bash(
    command="uv run python .claude/scripts/aria-credential-watch.py --timeout 300",
    run_in_background=True,
    description="Watch for OAuth completion"
)
# Save the task_id for polling
watcher_task_id = watcher.task_id
```

Then tell user:
```
I'm watching for your credentials. Run this in your terminal:

  uv run python .claude/scripts/aria-oauth-setup.py

Complete the setup there - I'll automatically continue when done.
```

3. **Wait for watcher to detect credentials:**

```python
# Block until watcher completes (finds credentials or times out)
result = TaskOutput(
    task_id=watcher_task_id,
    block=True,
    timeout=310000  # 310 seconds (slightly longer than watcher timeout)
)

# Parse JSON result from watcher
# Output: {"status": "found", "character_id": "12345", ...}
# Or:     {"status": "timeout", ...}
import json
watch_result = json.loads(result.output)

if watch_result["status"] == "found":
    char_id = watch_result["character_id"]
    credentials_found = True
else:
    credentials_found = False
```

4. **On success, continue immediately:**
```
✓ Credentials detected for character {char_id}!

Fetching your character data from ESI...
```

Then continue to Phase 2.

5. **On timeout, offer options:**
```
Haven't detected new credentials yet.

Type "retry" to watch again, or "skip" for manual setup.
```

**Key UX improvement:** User doesn't need to return and type "done" - the background watcher detects completion automatically. The conversation stays responsive.

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

**IMPORTANT:** Ask all preferences in ONE AskUserQuestion call to reduce round-trips.

Use AskUserQuestion with multiple questions:

```json
{
  "questions": [
    {
      "question": "Which faction persona? (Based on your standings, Gallente/ARIA is suggested)",
      "header": "Faction",
      "options": [
        {"label": "Gallente (Recommended)", "description": "ARIA - warm, witty, libertarian"},
        {"label": "Caldari", "description": "AURA-C - formal, precise, professional"},
        {"label": "Minmatar", "description": "VIND - direct, passionate, loyal"},
        {"label": "Amarr", "description": "THRONE - reverent, formal, devoted"}
      ],
      "multiSelect": false
    },
    {
      "question": "How much roleplay flavor?",
      "header": "RP Level",
      "options": [
        {"label": "Off (Recommended)", "description": "Just facts, no theater"},
        {"label": "Lite", "description": "EVE terminology, direct style"},
        {"label": "Moderate", "description": "Light personality, formatted reports"},
        {"label": "Full", "description": "Maximum immersion, ship AI roleplay"}
      ],
      "multiSelect": false
    },
    {
      "question": "Your EVE experience level?",
      "header": "Experience",
      "options": [
        {"label": "New", "description": "Still learning - I'll explain mechanics"},
        {"label": "Intermediate (Recommended)", "description": "Comfortable with basics"},
        {"label": "Veteran", "description": "Know mechanics well - skip basics"}
      ],
      "multiSelect": false
    }
  ]
}
```

**Note:** Mark the suggested option as "(Recommended)" based on:
- Faction: Highest standing from ESI
- RP Level: Always "Off"
- Experience: Based on SP (< 5M = New, 5-50M = Intermediate, > 50M = Veteran)

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
3. Generate profile from template (see Profile Template section)
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
- **Capsuleer Since:** [birthday_yc]
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

## Faction Lookup Table

| Faction | Mission Corp | Hostile Factions | Target Pirates |
|---------|--------------|------------------|----------------|
| Gallente | Federation Navy | Caldari State | Serpentis |
| Caldari | Caldari Navy | Gallente Federation | Guristas |
| Minmatar | Republic Fleet | Amarr Empire | Angel Cartel |
| Amarr | Imperial Navy | Minmatar Republic | Blood Raiders |

## Date Formatting

Convert dates to YC format:
- Real year 2026 = YC128 (YC year = real year - 1898)
- Format: YC128.01.14 for January 14, 2026

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

## Registry Format

Update `userdata/pilots/_registry.json`:

```json
{
  "pilots": [
    {
      "character_id": "2119654321",
      "character_name": "Suwayyah",
      "directory": "2119654321_suwayyah",
      "corporation": "Federal Navy Academy",
      "faction": "Gallente",
      "added_date": "2026-01-14T18:45:00Z"
    }
  ],
  "last_updated": "2026-01-14T18:45:00Z"
}
```

## Config Format

Update `userdata/config.json`:

```json
{
  "version": "2.0",
  "active_pilot": "2119654321",
  "last_active": "2026-01-14T18:45:00Z"
}
```

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

Or create the profile manually from the template.
```

## Behavior Notes

- **ESI-First:** Always try to connect ESI before asking questions
- **Minimal Questions:** Only ask what ESI can't answer
- **Smart Defaults:** Use SP to hint experience, standings to suggest faction
- **One Question at a Time:** Don't overwhelm
- **Allow Corrections:** User can say "go back" or "change [field]"
- **Graceful Fallback:** If ESI fails, smoothly transition to manual setup
