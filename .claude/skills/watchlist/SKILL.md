---
name: watchlist
description: Manage entity watchlists for tracking corporations and alliances. Monitor war targets and get alerts when watched entities appear in kills.
model: haiku
category: tactical
triggers:
  - "/watchlist"
  - "who am I tracking"
  - "add [corp] to watchlist"
  - "track [alliance]"
  - "sync war targets"
requires_pilot: false
has_persona_overlay: true
---

# ARIA Entity Watchlist Module

## Purpose
Manage entity watchlists for tracking specific corporations and alliances. When watched entities appear in kills (as victims or attackers), they are flagged in threat intelligence. Supports manual lists and automatic war target synchronization from ESI.

## Trigger Phrases
- "/watchlist"
- "who am I tracking"
- "add [corp] to watchlist"
- "track [alliance]"
- "sync war targets"

## Command Syntax

```
/watchlist                            # List all watchlists
/watchlist show <name>                # Show entities in watchlist
/watchlist create <name>              # Create manual watchlist
/watchlist add <name> <entity>        # Add corp/alliance
/watchlist remove <name> <entity>     # Remove entity
/watchlist delete <name>              # Delete watchlist
/watchlist sync-wars                  # Sync war targets from ESI
```

### Arguments

| Argument | Description |
|----------|-------------|
| `name` | Watchlist name (e.g., "War Targets", "Hostiles") |
| `entity` | Corporation or alliance name/ID |

## Data Source

Uses the entity watchlist database via CLI commands:

```bash
# List watchlists
uv run aria-esi watchlist-list

# Show entities in watchlist
uv run aria-esi watchlist-show "War Targets"

# Create watchlist
uv run aria-esi watchlist-create "Hostiles" --description "Known hostile corps"

# Add entity (corporation)
uv run aria-esi watchlist-add "Hostiles" 99002775 --type alliance --entity-name "CODE."

# Add entity (alliance)
uv run aria-esi watchlist-add "Hostiles" 99000001 --type alliance --entity-name "Goonswarm"

# Remove entity
uv run aria-esi watchlist-remove "Hostiles" 99002775 --type alliance

# Delete watchlist
uv run aria-esi watchlist-delete "Hostiles"

# Sync war targets (requires character/corp IDs)
uv run aria-esi sync-wars --character-id 123456 --corporation-id 789012

# Query kills involving watched entities
uv run aria-esi redisq-watched --minutes 60
uv run aria-esi redisq-watched --system 30002187 --minutes 30
```

## Watchlist Types

| Type | Description |
|------|-------------|
| `manual` | User-created lists for tracking specific entities |
| `war_targets` | Automatically synced from ESI war data |
| `contacts` | Synced from character contacts (future) |

## Response Format

### List Watchlists

```
===============================================================
ARIA ENTITY WATCHLISTS
---------------------------------------------------------------
WATCHLIST: War Targets
  Type: war_targets
  Entities: 3
  Last sync: 2 hours ago

WATCHLIST: Hostiles
  Type: manual
  Entities: 7
  Description: Known hostile corps in region

Total: 2 watchlists, 10 entities tracked
===============================================================
```

### Show Watchlist

```
===============================================================
ARIA WATCHLIST: War Targets
---------------------------------------------------------------
Type: war_targets | Entities: 3
---------------------------------------------------------------
CORPORATIONS:
  (none)

ALLIANCES:
  [99002775] CODE.
    Reason: War target
    Added: 2024-01-15

  [99000001] TEST Alliance Please Ignore
    Reason: War target
    Added: 2024-01-14

  [99005338] Pandemic Horde
    Reason: War target
    Added: 2024-01-14
===============================================================
```

### War Sync Result

```
===============================================================
ARIA WAR TARGET SYNC
---------------------------------------------------------------
Corporation: My Corp [98000001]
Wars checked: 3
---------------------------------------------------------------
SYNC RESULTS:
  Entities added: 2
  Entities removed: 1

CURRENT WAR TARGETS:
  [99000001] Enemy Alliance
  [98000002] Mercenary Corp
===============================================================
```

## Entity Resolution

Before adding an entity by name, resolve it to a numeric ID:

1. Call `sde(action="resolve_names", names=["Entity Name"])` via MCP
2. Extract the corporation or alliance ID from the response
3. Pass the numeric ID to the CLI: `watchlist-add "list" <id> --type corporation --entity-name "Entity Name"`

**Example:** Adding "Pandemic Horde" to a watchlist:
```
sde(action="resolve_names", names=["Pandemic Horde"])
→ {"alliances": [{"id": 99005338, "name": "Pandemic Horde"}]}

uv run aria-esi watchlist-add "Hostiles" 99005338 --type alliance --entity-name "Pandemic Horde"
```

**MCP unavailable fallback:** No CLI equivalent exists. Use the ESI Swagger UI or ask the pilot for the entity ID directly.

**Note:** The SDE `corporation_info` action only indexes NPC corporations. Player corps and alliances must be resolved via `sde(action="resolve_names")` (which calls ESI `POST /universe/ids/`). This action is MCP-only.

## Integration with Threat Assessment

When watched entities appear in kills, they are flagged:

1. **In `/threat-assessment`**: Shows "Watched entity activity" section
2. **In `/gatecamp`**: Notes if attackers are on watchlist
3. **In database**: Kills are tagged with `watched_entity_match=1`

Example in threat assessment:

```
WATCHED ENTITY ACTIVITY:
  3 kills involving watched entities in last hour
  - CODE. (attacker) - 2 kills in Uedama
  - Enemy Alliance (victim) - 1 kill in Tama
```

## War Target Synchronization

The `/watchlist sync-wars` command:

1. Queries ESI for corporation wars
2. Identifies enemy corps/alliances
3. Creates/updates "War Targets" watchlist
4. Removes ended wars

**ESI Scopes Required:**
- `esi-wars.read_wars.v1` (corporation wars)

**Sync Schedule:**
- On demand via command
- Automatic on poller startup
- Every 4 hours while poller running

## Behavior Notes

- **Entity IDs are immutable** - Corporation/alliance IDs don't change, safe for tracking
- **Names are display only** - Stored for convenience, not used for matching
- **Global vs pilot-specific** - Manual lists can be global; war targets are pilot-specific
- **Real-time flagging** - Kills are flagged as they arrive, no reprocessing needed
- **Graceful degradation** - If entity tracking fails, kills still process normally

## Contextual Suggestions

After watchlist operations, suggest related commands:

| Context | Suggest |
|---------|---------|
| Added war target | "Run `/threat-assessment` to see their activity" |
| Synced wars | "Check `/gatecamp` on common routes for enemy activity" |
| Tracking gankers | "Use `/route --safe` to avoid their hotspots" |

---

## Persona Adaptation

This skill supports persona-specific overlays. When active persona has an overlay file, load additional context from:

```
personas/{active_persona}/skill-overlays/watchlist.md
```

If no overlay exists, use the default framing above.
