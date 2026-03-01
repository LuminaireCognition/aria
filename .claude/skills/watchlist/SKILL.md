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
---

# ARIA Entity Watchlist Module

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

## Critical: Entity-Only Scope

Watchlists track **player entities (corporations and alliances) only** — never market items, ships, or game objects. When a user says "add X to my watchlist", X is ALWAYS a corporation or alliance name.

**Resolution workflow — do this FIRST for every add operation:**
1. Call `sde(action="resolve_names", names=["<entity_name>"])` to get the numeric ID
2. Extract the corporation or alliance ID from the response
3. Pass the numeric ID to CLI: `watchlist-add "<list>" <id> --type <corporation|alliance> --entity-name "<name>"`

Never use `sde(action="search")` or `sde(action="item_info")` for watchlist operations — those search game items, not player entities.

- **MCP unavailable fallback:** No CLI equivalent for name resolution exists. Use the ESI Swagger UI or ask the pilot for the entity ID directly.
- **NPC corporations:** The SDE `corporation_info` action only indexes NPC corporations. Player corps and alliances must be resolved via `sde(action="resolve_names")` (which calls ESI `POST /universe/ids/`). This action is MCP-only.

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


## War Target Synchronization

Requires `esi-wars.read_wars.v1`. Auto-syncs every 4 hours when poller active, or on demand via `/watchlist sync-wars`.

## Error Handling

| Error | Response |
|-------|----------|
| Entity name not resolvable | Report that the name could not be resolved via ESI; ask pilot for numeric ID |
| Watchlist not found | List existing watchlists and suggest correct name |
| Duplicate entity in watchlist | Note the entity is already tracked |

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

