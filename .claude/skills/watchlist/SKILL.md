---
name: watchlist
description: Manage entity watchlists for tracking corporations and alliances. Monitor war targets and get alerts when watched entities appear in kills.
category: tactical
triggers:
  - "/watchlist"
  - "who am I tracking"
  - "add [corp] to watchlist"
  - "track [alliance]"
  - "sync war targets"
requires_pilot: false
preferred_max_lines: 30
argument-hint: "[add|remove|list] [entity_name]"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash, mcp__aria-universe__market, mcp__aria-universe__sde
---

# Entity Watchlist Module

## Entity Resolution Gate

Watchlists track **player entities (corporations and alliances) only**. When a user says "add X", X is always a corp or alliance name.

| Step | Action |
|------|--------|
| 1 | `sde(action="resolve_names", names=["<entity_name>"])` → get numeric ID |
| 2 | `uv run aria-esi watchlist-add "<list>" <id> --type <corporation|alliance> --entity-name "<name>"` |

**Never** use `sde(action="search")` or `sde(action="item_info")` — those search game items, not player entities.

If MCP unavailable or name resolution fails: ask the pilot for the numeric entity ID.

## CLI Commands

```bash
uv run aria-esi watchlist-list                                    # List all watchlists
uv run aria-esi watchlist-show "<name>"                           # Show entities
uv run aria-esi watchlist-create "<name>" --description "..."     # Create
uv run aria-esi watchlist-add "<name>" <id> --type alliance --entity-name "NAME"
uv run aria-esi watchlist-remove "<name>" <id> --type alliance    # Remove
uv run aria-esi watchlist-delete "<name>"                         # Delete
uv run aria-esi sync-wars --character-id <id> --corporation-id <id>
uv run aria-esi redisq-watched --minutes 60                      # Recent kills
```

## Name Normalization

When listing watchlists, perform case-insensitive deduplication. If multiple lists differ only by case (e.g., "Default" and "default"), warn the user:

```
[!] Duplicate watchlist names detected (case mismatch): "Default" and "default"
    Consider merging with: uv run aria-esi watchlist-delete "default"
```

## War Target Sync

Requires ESI authentication. If ESI unavailable:
- Do NOT report "Synced — 0 entities" (false success)
- State sync requires ESI, show cached data with staleness warning

## Response Format

List watchlists with name, type, entity count, and last sync time. Show entities grouped by type (corporations, alliances) with IDs and add dates.

## Output Rules

- Keep response under 30 lines
- Append a one-line `Sources:` footer listing MCP calls and CLI commands used

## Contextual Suggestions

| Context | Suggest |
|---------|---------|
| Added war target | `/threat-assessment` for their activity |
| Synced wars | `/gatecamp` on common routes |
| Tracking gankers | `/route --safe` to avoid hotspots |

## Error Handling
If CLI commands (`aria-esi watchlist-*`) return errors:
1. Report the error to the user with the exact message
2. Suggest they run `uv run aria-esi db-migrate` if the error suggests schema issues
3. Do NOT attempt to debug source code or fix bugs during skill execution
