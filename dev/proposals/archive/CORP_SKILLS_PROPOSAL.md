# Corporation Skills Implementation Plan

## Phase 1 Design Document

**Date:** YC128.01.15
**Status:** Design Complete - Ready for Implementation
**Revision:** 2.0 - Consolidated `/corp` command structure

---

## Executive Summary

This document specifies the implementation of ARIA's Phase 1 corporation support using a **consolidated command structure**. Instead of 5 separate `/corp-*` commands, a single `/corp` command with subcommands provides cleaner UX for occasional corp management tasks.

| Component | Description | Files Affected |
|-----------|-------------|----------------|
| **1 New Skill** | `/corp` with 6 subcommands | `.claude/skills/corp/SKILL.md` |
| **Script Extension** | Add `corp` namespace to aria-esi | `.claude/scripts/aria-esi` |
| **OAuth Update** | Add corp scope selection | `.claude/scripts/aria-oauth-setup.py` |
| **Data Storage** | Corp data directory structure | `pilots/{id}/corporation/` |
| **Help Integration** | `/help corp` topic | `.claude/skills/help/SKILL.md` |

---

## Design Rationale

### Why Consolidate?

| Factor | Separate Commands | Consolidated `/corp` |
|--------|-------------------|---------------------|
| **Commands to remember** | 5 top-level | 1 + subcommands |
| **Help output** | 5 lines | 1 line |
| **Discoverability** | Must know each | `/corp help` lists all |
| **Usage pattern** | Daily use | Episodic (weekly/monthly) |
| **EVE mental model** | N/A | Mirrors "Corporation" window |
| **Existing ARIA patterns** | N/A | Matches `/esi-query`, `/journal` |

Corporation data is checked episodically, not daily. A single entry point with discoverable subcommands suits occasional use better than memorizing multiple commands.

### Precedent in ARIA

Existing commands already use subcommand patterns:
```
/esi-query location|wallet|standings|skills|blueprints
/journal mission|exploration
```

The `/corp` command follows this established pattern.

---

## Command Structure

```
/corp                              # Default: Corporation status dashboard
/corp help                         # List available subcommands
/corp info [name|id]               # Public corp lookup (any corporation)
/corp wallet [--journal] [--div N] # Wallet balances and journal
/corp assets [--ships] [--loc X]   # Corporation hangar inventory
/corp blueprints [--filter X]      # BPO/BPC library
/corp jobs [--active|--history]    # Industry job status
```

### Natural Language Triggers

All of these map to the appropriate subcommand:

| Phrase | Maps To |
|--------|---------|
| "corp status" / "how's the corp" | `/corp` (default) |
| "corp wallet" / "corp finances" | `/corp wallet` |
| "corp assets" / "corp hangar" | `/corp assets` |
| "corp blueprints" / "corp BPOs" | `/corp blueprints` |
| "corp jobs" / "what's being built" | `/corp jobs` |
| "lookup [corp name]" | `/corp info [name]` |

---

## Architecture Overview

### Command Flow

```
User: /corp wallet
       │
       ▼
┌─────────────────────────────────┐
│   corp/SKILL.md (ARIA guidance) │ ← Defines behavior, output format
└─────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   aria-esi corp wallet          │ ← Script dispatches to subcommand
└─────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   ESI API Calls                 │ ← /corporations/{id}/wallets/
└─────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   JSON Response                 │ ← With query_timestamp, volatility
└─────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   ARIA Formatted Output         │ ← Report format per RP level
└─────────────────────────────────┘
```

### Corporation ID Resolution

**Automatic:** The character's corporation ID is resolved from the public character endpoint:
```
GET /characters/{character_id}/ → { "corporation_id": 98765432, ... }
```

Cached as semi-stable data (changes only when joining/leaving corp).

**Validation Required:**
- Is character in a player corporation? (corp_id >= 2000000)
- Does character have required roles? (CEO/Director for protected endpoints)

---

## Subcommand Specifications

### Default: `/corp` (Status Dashboard)

**Purpose:** Quick overview of corporation status - the most common "just checking" use case.

**Output Format:**
```
═══════════════════════════════════════════════════════════════════
HORADRIC ACQUISITIONS [AREAT] - CORPORATION STATUS
───────────────────────────────────────────────────────────────────
GalNet Sync: 2026-01-15 10:30 UTC

IDENTITY
  Corporation:   Horadric Acquisitions
  Ticker:        AREAT
  Members:       1
  CEO:           Federation Navy Suwayyah
  Tax Rate:      0%
  Founded:       YC128.01.15

FINANCIAL SUMMARY
  Master Wallet: 15,234,567 ISK
  Other Divs:    0 ISK
                 ─────────────────
  Total:         15,234,567 ISK

ASSETS
  Locations:     2 stations
  Ships:         3 assembled
  Items:         47 unique types

INDUSTRY
  Active Jobs:   2 (1 completes in 2h 15m)
  Blueprints:    12 BPOs, 3 BPCs

───────────────────────────────────────────────────────────────────
Subcommands: info, wallet, assets, blueprints, jobs
Use "/corp [subcommand]" for details, or "/corp help"
═══════════════════════════════════════════════════════════════════
```

**ESI Endpoints Used:**
```
GET /corporations/{id}/                          # Public
GET /corporations/{id}/wallets/                  # Auth required
GET /corporations/{id}/assets/                   # Auth required (count only)
GET /corporations/{id}/blueprints/               # Auth required (count only)
GET /corporations/{id}/industry/jobs/            # Auth required (count only)
```

**Behavior:**
- Combines data from multiple endpoints into summary view
- Shows counts, not full details (those come from subcommands)
- Gracefully degrades if some scopes missing (shows "N/A" for unauthorized data)
- Lists available subcommands at bottom

---

### `/corp info [target]`

**Purpose:** Query public corporation information. Works for ANY corporation.

**Arguments:**
- No argument or `my` → User's own corporation
- Corporation ID → Direct lookup
- Corporation name → Search and lookup

**Scopes Required:** None (public endpoints only)

**ESI Endpoints:**
```
GET /corporations/{id}/                    # Public
GET /corporations/{id}/icons/              # Public
GET /characters/{ceo_id}/                  # Public (resolve CEO name)
GET /alliances/{alliance_id}/              # Public (if in alliance)
GET /search/?categories=corporation&search={name}  # Public (name search)
```

**Output Format:**
```
═══════════════════════════════════════════════════════════════════
ARIA CORPORATION INTELLIGENCE
───────────────────────────────────────────────────────────────────
GalNet Query: [timestamp]

CORPORATION: [Name]
TICKER:      [TICK]
MEMBERS:     [count]
CEO:         [Character Name]
TAX RATE:    [X]%
FOUNDED:     [date]
ALLIANCE:    [Alliance Name or "Independent"]
HOME STATION:[Station name, if set]

DESCRIPTION:
[Corporation bio - first 500 chars, truncated if longer]

───────────────────────────────────────────────────────────────────
Public record query. No authentication required.
═══════════════════════════════════════════════════════════════════
```

**Script Command:**
```bash
aria-esi corp info                    # Own corporation
aria-esi corp info my                 # Own corporation (explicit)
aria-esi corp info 98000001           # By ID (EVE University)
aria-esi corp info "Horadric"         # By name search
```

---

### `/corp wallet`

**Purpose:** Query corporation wallet balances and transaction journal.

**Scopes Required:**
```
esi-wallet.read_corporation_wallets.v1
esi-corporations.read_divisions.v1
```

**ESI Endpoints:**
```
GET /corporations/{id}/wallets/                    # Division balances
GET /corporations/{id}/wallets/{div}/journal/      # Transaction history
GET /corporations/{id}/divisions/                  # Division names
```

**Output Format (Summary - default):**
```
═══════════════════════════════════════════════════════════════════
HORADRIC ACQUISITIONS [AREAT] - FINANCIAL STATUS
───────────────────────────────────────────────────────────────────
GalNet Sync: [timestamp]

WALLET DIVISIONS:
  1. Master Wallet:     15,234,567.89 ISK
  2. [Division Name]:          0.00 ISK
  3. [Division Name]:          0.00 ISK
  4. [Division Name]:          0.00 ISK
  5. [Division Name]:          0.00 ISK
  6. [Division Name]:          0.00 ISK
  7. [Division Name]:          0.00 ISK
                       ─────────────────
  TOTAL:               15,234,567.89 ISK

RECENT ACTIVITY (Master Wallet - last 10):
  [date] + 1,250,000 ISK  Agent mission reward
  [date] +   125,000 ISK  Bounty prizes
  [date] - 1,599,800 ISK  Corporation registration fee

───────────────────────────────────────────────────────────────────
⚠ Balance as of query time. Use --journal for full history.
═══════════════════════════════════════════════════════════════════
```

**Output Format (Journal - with --journal):**
```
═══════════════════════════════════════════════════════════════════
HORADRIC ACQUISITIONS - WALLET JOURNAL (Division 1)
───────────────────────────────────────────────────────────────────
GalNet Sync: [timestamp]

DATE                 AMOUNT           TYPE                    BALANCE
─────────────────────────────────────────────────────────────────────
YC128.01.15 09:30   + 1,250,000 ISK   agent_mission_reward   15,234,567
YC128.01.15 09:15   +   125,000 ISK   bounty_prizes          13,984,567
YC128.01.15 08:00   - 1,599,800 ISK   corporation_registration 13,859,567
...

───────────────────────────────────────────────────────────────────
Showing last 25 entries. Use --limit N to adjust.
═══════════════════════════════════════════════════════════════════
```

**Script Command:**
```bash
aria-esi corp wallet                        # Summary of all divisions
aria-esi corp wallet --journal              # Full journal (master wallet)
aria-esi corp wallet --journal --div 2      # Journal for division 2
aria-esi corp wallet --limit 50             # More entries
```

**Journal Reference Type Categories:**
- **Income:** `bounty_prizes`, `agent_mission_reward`, `agent_mission_time_bonus_reward`
- **Fees:** `corporation_registration`, `office_rental_fee`, `industry_job_tax`
- **Transfers:** `corporation_account_withdrawal`, `player_donation`
- **Industry:** `manufacturing`, `researching_material_productivity`

---

### `/corp assets`

**Purpose:** Query corporation asset inventory across all locations.

**Scopes Required:**
```
esi-assets.read_corporation_assets.v1
```

**ESI Endpoints:**
```
GET /corporations/{id}/assets/              # Full inventory
POST /corporations/{id}/assets/names/       # Custom names
GET /universe/types/{type_id}/              # Resolve type names
GET /universe/stations/{station_id}/        # Resolve station names
```

**Output Format:**
```
═══════════════════════════════════════════════════════════════════
HORADRIC ACQUISITIONS [AREAT] - CORPORATION ASSETS
───────────────────────────────────────────────────────────────────
GalNet Sync: [timestamp]

SUMMARY:
  Total Items:     47 unique types
  Locations:       2 stations
  Ships:           3 assembled

BY LOCATION:
┌──────────────────────────────────────────────────────────────────
│ SORTET V - X-SENSE CHEMICAL REFINERY
├──────────────────────────────────────────────────────────────────
│ Ships:
│   • Vexor "Mining Support"
│   • Catalyst "cat0"
│
│ Materials:
│   • Tritanium x 50,000
│   • Pyerite x 12,000
│
│ Modules:
│   • Hammerhead I x 5
│   • Medium Armor Repairer I x 2
└──────────────────────────────────────────────────────────────────
┌──────────────────────────────────────────────────────────────────
│ DODIXIE IX - FEDERATION NAVY ASSEMBLY PLANT
├──────────────────────────────────────────────────────────────────
│ Ships:
│   • Imicus "im0"
└──────────────────────────────────────────────────────────────────

───────────────────────────────────────────────────────────────────
Use --ships, --location, or --type to filter.
═══════════════════════════════════════════════════════════════════
```

**Script Command:**
```bash
aria-esi corp assets                        # Full inventory
aria-esi corp assets --ships                # Assembled ships only
aria-esi corp assets --location "Sortet"    # Filter by location
aria-esi corp assets --type "Tritanium"     # Filter by item type
```

---

### `/corp blueprints`

**Purpose:** Query corporation blueprint library (BPOs and BPCs).

**Scopes Required:**
```
esi-corporations.read_blueprints.v1
```

**ESI Endpoints:**
```
GET /corporations/{id}/blueprints/          # Full library
GET /universe/types/{type_id}/              # Resolve names
```

**Output Format:**
```
═══════════════════════════════════════════════════════════════════
HORADRIC ACQUISITIONS [AREAT] - BLUEPRINT LIBRARY
───────────────────────────────────────────────────────────────────
GalNet Sync: [timestamp]

BLUEPRINT ORIGINALS (BPOs): 12
┌────────────────────────────────────────────────────────────┬────┬────┐
│ Blueprint                                                  │ ME │ TE │
├────────────────────────────────────────────────────────────┼────┼────┤
│ Antimatter Charge S Blueprint                              │ 10 │ 20 │
│ Cap Booster 25 Blueprint                                   │  0 │  0 │
│ Hammerhead I Blueprint                                     │  5 │ 10 │
│ Hobgoblin I Blueprint                                      │ 10 │ 20 │
│ ...                                                        │    │    │
└────────────────────────────────────────────────────────────┴────┴────┘

BLUEPRINT COPIES (BPCs): 3
┌────────────────────────────────────────────────────────────┬──────┬────┬────┐
│ Blueprint                                                  │ Runs │ ME │ TE │
├────────────────────────────────────────────────────────────┼──────┼────┼────┤
│ Vexor Blueprint                                            │   5  │ 10 │ 20 │
│ ...                                                        │      │    │    │
└────────────────────────────────────────────────────────────┴──────┴────┴────┘

───────────────────────────────────────────────────────────────────
Use --filter to search, --bpos or --bpcs to filter by type.
═══════════════════════════════════════════════════════════════════
```

**Script Command:**
```bash
aria-esi corp blueprints                    # Full library
aria-esi corp blueprints --filter "drone"   # Search by name
aria-esi corp blueprints --bpos             # BPOs only
aria-esi corp blueprints --bpcs             # BPCs only
```

---

### `/corp jobs`

**Purpose:** Query active and recent corporation industry jobs.

**Scopes Required:**
```
esi-industry.read_corporation_jobs.v1
```

**ESI Endpoints:**
```
GET /corporations/{id}/industry/jobs/       # All jobs
GET /universe/types/{type_id}/              # Resolve product names
```

**Output Format:**
```
═══════════════════════════════════════════════════════════════════
HORADRIC ACQUISITIONS [AREAT] - INDUSTRY STATUS
───────────────────────────────────────────────────────────────────
GalNet Sync: [timestamp]

ACTIVE JOBS: 2
┌──────────────────────────────────────────────────────────────────
│ [Manufacturing] Hammerhead I x 10
│ Installer:  Federation Navy Suwayyah
│ Location:   Sortet V - X-Sense Chemical Refinery
│ Started:    YC128.01.14 15:30
│ Completes:  YC128.01.14 18:45 (2h 15m remaining)
├──────────────────────────────────────────────────────────────────
│ [ME Research] Hobgoblin I Blueprint (8% → 10%)
│ Installer:  Federation Navy Suwayyah
│ Location:   Sortet V - X-Sense Chemical Refinery
│ Completes:  YC128.01.15 06:00 (ready for delivery)
└──────────────────────────────────────────────────────────────────

RECENTLY COMPLETED (last 24h): 2
  • [Manufacturing] Antimatter Charge S x 1000 - YC128.01.14 12:00
  • [Copying] Vexor Blueprint (5 runs) - YC128.01.14 10:30

───────────────────────────────────────────────────────────────────
Use --active, --completed, or --history for filtered views.
═══════════════════════════════════════════════════════════════════
```

**Script Command:**
```bash
aria-esi corp jobs                          # Active + recent completed
aria-esi corp jobs --active                 # Active only
aria-esi corp jobs --completed              # Completed only
aria-esi corp jobs --history                # Extended history
```

**Job Activity Types:**
| ID | Type | Display |
|----|------|---------|
| 1 | Manufacturing | `[Manufacturing]` |
| 3 | TE Research | `[TE Research]` |
| 4 | ME Research | `[ME Research]` |
| 5 | Copying | `[Copying]` |
| 7 | Reverse Engineering | `[Reverse Eng]` |
| 8 | Invention | `[Invention]` |

---

### `/corp help`

**Purpose:** List available subcommands and usage.

**Output Format:**
```
═══════════════════════════════════════════════════════════════════
ARIA CORPORATION MODULE
───────────────────────────────────────────────────────────────────
Usage: /corp [subcommand] [options]

SUBCOMMANDS:
  (none)      Status dashboard - overview of all corp data
  info        Public corporation lookup (works for any corp)
  wallet      Wallet balances and transaction journal
  assets      Corporation hangar inventory
  blueprints  BPO/BPC library
  jobs        Manufacturing and research status
  help        This help message

EXAMPLES:
  /corp                          # Corp status dashboard
  /corp info "EVE University"    # Lookup another corp
  /corp wallet --journal         # Full transaction history
  /corp assets --ships           # List corp ships only
  /corp blueprints --filter ammo # Search blueprints

AUTHENTICATION:
  'info' subcommand requires no authentication.
  All other subcommands require CEO/Director role and corp scopes.

SETUP:
  python3 .claude/scripts/aria-oauth-setup.py
  Select "Yes" when asked about corporation scopes.
═══════════════════════════════════════════════════════════════════
```

---

## OAuth Setup Extension

### New Scope Constants

Add to `aria-oauth-setup.py`:

```python
# Corporation scopes (CEO/Director only)
CORP_SCOPES = [
    "esi-wallet.read_corporation_wallets.v1",
    "esi-assets.read_corporation_assets.v1",
    "esi-corporations.read_blueprints.v1",
    "esi-industry.read_corporation_jobs.v1",
    "esi-corporations.read_standings.v1",
    "esi-corporations.read_divisions.v1",
]

CORP_SCOPE_INFO = {
    "esi-wallet.read_corporation_wallets.v1": "Corp wallet and journal",
    "esi-assets.read_corporation_assets.v1": "Corp hangar inventory",
    "esi-corporations.read_blueprints.v1": "Corp blueprint library",
    "esi-industry.read_corporation_jobs.v1": "Corp manufacturing/research",
    "esi-corporations.read_standings.v1": "Corp faction standings",
    "esi-corporations.read_divisions.v1": "Corp division names",
}
```

### Wizard Flow Addition

After personal scope selection:

```
═══════════════════════════════════════════════════════════════════
CORPORATION SCOPES (Optional)
───────────────────────────────────────────────────────────────────
If you are CEO or Director of a player corporation, you can also
authorize corporation data access.

NOTE: These scopes only work if you have the required corp roles.
      NPC corporation members should skip this section.

Do you want to add corporation scopes? [y/N]:
```

### Player Corp Detection

After token verification:

```python
# Fetch character's corporation
char_public = esi_get(f"/characters/{character_id}/")
corp_id = char_public.get("corporation_id")

# Check if player corp (ID >= 2000000)
if corp_id and corp_id >= 2000000:
    corp_info = esi_get(f"/corporations/{corp_id}/")
    corp_name = corp_info.get("name", "Unknown")
    print(f"\nPlayer corporation detected: {corp_name}")
    # Offer corp scopes
else:
    print("\nNPC corporation detected - skipping corp scopes")
```

---

## Script Implementation

### aria-esi Extension

Add `corp` as a command namespace:

```bash
# Main case statement addition
case "${1:-help}" in
    # ... existing commands ...

    corp)       shift; cmd_corp "$@" ;;

    help|--help|-h) cmd_help ;;
    *)
        echo "Unknown command: $1"
        exit 1
        ;;
esac
```

### Corp Command Dispatcher

```bash
cmd_corp() {
    local subcmd="${1:-status}"
    shift 2>/dev/null || true

    case "$subcmd" in
        status|"")  cmd_corp_status "$@" ;;
        info)       cmd_corp_info "$@" ;;
        wallet)     cmd_corp_wallet "$@" ;;
        assets)     cmd_corp_assets "$@" ;;
        blueprints) cmd_corp_blueprints "$@" ;;
        jobs)       cmd_corp_jobs "$@" ;;
        help)       cmd_corp_help ;;
        *)
            echo "Unknown corp subcommand: $subcmd"
            echo "Available: info, wallet, assets, blueprints, jobs, help"
            exit 1
            ;;
    esac
}
```

### Shared Helper Functions

```bash
# Get character's corporation ID
get_corp_id() {
    local char_id=$(get_character_id)
    local char_info=$(curl -s "${ESI_BASE}/characters/${char_id}/?datasource=tranquility")
    echo "$char_info" | python3 -c "import sys,json; print(json.load(sys.stdin).get('corporation_id',''))"
}

# Check if player corporation (not NPC)
is_player_corp() {
    local corp_id=$(get_corp_id)
    if [[ -n "$corp_id" ]] && [[ "$corp_id" -ge 2000000 ]]; then
        return 0
    fi
    return 1
}

# Check for required scope
require_corp_scope() {
    local scope="$1"
    local has_scope=$(python3 -c "
import json
scopes = json.load(open('$CREDS_FILE')).get('scopes', [])
print('yes' if '$scope' in scopes else 'no')
")
    if [[ "$has_scope" != "yes" ]]; then
        echo "{"
        echo "  \"error\": \"scope_not_authorized\","
        echo "  \"message\": \"Missing required scope: $scope\","
        echo "  \"action\": \"Re-run OAuth setup with corporation scopes\","
        echo "  \"command\": \"python3 .claude/scripts/aria-oauth-setup.py\""
        echo "}"
        exit 1
    fi
}
```

---

## SKILL.md Specification

### File Location
`.claude/skills/corp/SKILL.md`

### Skill Metadata
```yaml
---
name: corp
description: Corporation management and queries. Use for corp status, wallet, assets, blueprints, or industry jobs.
---
```

### Trigger Phrases

```markdown
## Trigger Phrases

### Default Dashboard (/corp)
- "/corp"
- "corp status"
- "corporation status"
- "how's the corp"
- "check on corp"

### Info Subcommand
- "/corp info"
- "corp info [name]"
- "lookup corporation"
- "what is [corp name]"

### Wallet Subcommand
- "/corp wallet"
- "corp wallet"
- "corp finances"
- "corporation balance"
- "corp journal"

### Assets Subcommand
- "/corp assets"
- "corp assets"
- "corp hangar"
- "what's in corp hangar"
- "corporation inventory"

### Blueprints Subcommand
- "/corp blueprints"
- "corp blueprints"
- "corp BPOs"
- "corporation blueprint library"

### Jobs Subcommand
- "/corp jobs"
- "corp jobs"
- "manufacturing status"
- "what's being built"
- "corp industry"
```

---

## Data Storage

### Directory Structure

```
pilots/{character_id}_{slug}/
├── profile.md
├── operations.md
├── ships.md
├── missions.md
├── exploration.md
├── goals.md
├── industry/
│   └── blueprints.md         # Personal blueprints
├── projects/
│   └── *.md
└── corporation/              # NEW
    ├── .corp-cache.json      # Cached corp ID, last sync times
    ├── info.md               # Corp identity (synced)
    ├── wallet.md             # Wallet summary (synced)
    ├── assets.md             # Asset inventory (synced)
    ├── blueprints.md         # Corp BPO/BPC library (synced)
    └── jobs.md               # Industry job status (synced)
```

### Cache File

`.corp-cache.json` stores session-stable data:

```json
{
  "corporation_id": 98765432,
  "corporation_name": "Horadric Acquisitions",
  "ticker": "AREAT",
  "is_ceo": true,
  "resolved_at": "2026-01-15T10:00:00Z"
}
```

### Sync Markers

Use established ARIA pattern:

```markdown
<!-- ESI-SYNC:CORP-WALLET:START -->
*Last sync: 2026-01-15 10:30 UTC*
...synced content...
<!-- ESI-SYNC:CORP-WALLET:END -->
```

---

## Help Integration

### Update `/help` Output

Add single line for corporation:

```
CORPORATION:
  /corp ................. Corporation management (status, wallet, assets, etc.)
```

### Add `/help corp` Topic

```markdown
### `/help corp`

═══════════════════════════════════════════════════════════════════
ARIA HELP: Corporation Management
───────────────────────────────────────────────────────────────────
Command: /corp [subcommand]

SUBCOMMANDS:
  (default)   Corporation status dashboard
  info        Public corporation lookup (any corp, no auth)
  wallet      Wallet balances and transaction journal
  assets      Corporation hangar inventory
  blueprints  BPO/BPC library
  jobs        Manufacturing and research status
  help        Subcommand listing

EXAMPLES:
  /corp                     Quick status overview
  /corp info Goonswarm      Lookup another corporation
  /corp wallet --journal    Full transaction history
  /corp assets --ships      Corporation ships only

AUTHENTICATION:
  The 'info' subcommand queries public data (no auth required).
  All other subcommands require:
    1. CEO or Director role in your corporation
    2. Corporation ESI scopes authorized

SETUP:
  python3 .claude/scripts/aria-oauth-setup.py
  Select "Yes" when asked about corporation scopes.

NOTE: NPC corporation members cannot access corp data endpoints.
═══════════════════════════════════════════════════════════════════
```

---

## Error Handling

### NPC Corporation

```json
{
  "error": "npc_corporation",
  "message": "Corporation endpoints only work for player corporations",
  "corporation_id": 1000125,
  "corporation_name": "Serpentis Corporation",
  "suggestion": "Join or create a player corporation to use these features",
  "public_info_available": true
}
```

Display:
```
═══════════════════════════════════════════════════════════════════
ARIA CORPORATION MODULE
───────────────────────────────────────────────────────────────────
You are currently in an NPC corporation (Serpentis Corporation).

Corporation management features require membership in a player
corporation. The 'info' subcommand still works for lookups:

  /corp info [corporation name or ID]

To access full corp features, join or create a player corporation.
═══════════════════════════════════════════════════════════════════
```

### Missing Scopes

```json
{
  "error": "scope_not_authorized",
  "message": "Corporation wallet query requires: esi-wallet.read_corporation_wallets.v1",
  "action": "Re-run OAuth setup with corporation scopes enabled",
  "command": "python3 .claude/scripts/aria-oauth-setup.py"
}
```

### Insufficient Role

```json
{
  "error": "forbidden",
  "message": "Character lacks required corporation role",
  "detail": "Wallet access requires CEO, Director, or Accountant role",
  "http_status": 403
}
```

### Empty Results

```json
{
  "query_timestamp": "2026-01-15T10:30:00Z",
  "volatility": "semi_stable",
  "corporation_id": 98765432,
  "blueprints": [],
  "count": 0,
  "message": "No blueprints found in corporation hangars"
}
```

---

## Implementation Checklist

### Phase 1a: Infrastructure

- [ ] Create `pilots/{id}/corporation/` directory on first corp query
- [ ] Add `CORP_SCOPES` and `CORP_SCOPE_INFO` to OAuth setup
- [ ] Add corp scope selection flow to wizard
- [ ] Add player corp detection after token verification
- [ ] Add `get_corp_id()`, `is_player_corp()`, `require_corp_scope()` helpers

### Phase 1b: Script Implementation

- [ ] Add `corp` case to main dispatcher in aria-esi
- [ ] Implement `cmd_corp()` dispatcher function
- [ ] Implement `cmd_corp_status()` - dashboard
- [ ] Implement `cmd_corp_info()` - public lookup
- [ ] Implement `cmd_corp_wallet()` - finances
- [ ] Implement `cmd_corp_assets()` - inventory
- [ ] Implement `cmd_corp_blueprints()` - BPO/BPC library
- [ ] Implement `cmd_corp_jobs()` - industry status
- [ ] Implement `cmd_corp_help()` - subcommand listing

### Phase 1c: SKILL.md

- [ ] Create `.claude/skills/corp/SKILL.md`
- [ ] Define all trigger phrases
- [ ] Document output formats for each subcommand
- [ ] Document error handling patterns
- [ ] Document volatility classifications

### Phase 1d: Help Integration

- [ ] Add `/corp` line to main `/help` output
- [ ] Create `/help corp` topic in help SKILL.md
- [ ] Update docs/ESI.md with corp scope documentation

### Phase 1e: Testing

- [ ] Test `/corp info` with known corps (EVE University, own corp)
- [ ] Test `/corp` dashboard with full scopes
- [ ] Test graceful degradation with partial scopes
- [ ] Test NPC corp error handling
- [ ] Test missing scope error handling
- [ ] Verify output formatting matches spec

---

## Testing Plan

### Public Endpoint Tests

```bash
# No auth required
aria-esi corp info 98000001           # EVE University
aria-esi corp info "Pandemic Horde"   # By name
aria-esi corp info my                 # Own corp
aria-esi corp info                    # Own corp (implicit)
```

### Authenticated Endpoint Tests

```bash
# Requires CEO/Director auth
aria-esi corp                         # Status dashboard
aria-esi corp wallet                  # Wallet summary
aria-esi corp wallet --journal        # Full journal
aria-esi corp assets                  # Asset inventory
aria-esi corp assets --ships          # Ships only
aria-esi corp blueprints              # Blueprint library
aria-esi corp jobs                    # Industry status
aria-esi corp help                    # Subcommand listing
```

### Error Case Tests

```bash
# Should return appropriate errors
aria-esi corp wallet                  # Without scopes → scope error
aria-esi corp info 1000125            # NPC corp → limited public info
aria-esi corp info "nonexistent"      # → not found
```

---

## Security Considerations

### Scope Minimization

Phase 1 requests only 6 scopes. Additional scopes deferred:
- `esi-corporations.read_corporation_membership.v1` → Phase 3
- `esi-corporations.read_structures.v1` → Phase 3
- `esi-industry.read_corporation_mining.v1` → Phase 3

### Role-Based Access

ESI enforces role requirements server-side. ARIA provides clear messaging when 403 Forbidden is returned.

### Credential Storage

Corporation scopes stored in same `credentials/{char_id}.json` file. Consider adding `corp_authorized: true` flag for quick validation.

---

## Future Extensions (Phase 2+)

The consolidated `/corp` structure makes future additions clean:

```
/corp standings     # Phase 2 - Corp faction standings
/corp contacts      # Phase 2 - Corp contact list
/corp members       # Phase 3 - Member roster (if recruiting)
/corp structures    # Phase 3 - Upwell structures
/corp mining        # Phase 3 - Mining ledger observers
```

Each becomes a new subcommand with minimal user learning curve.

---

*Implementation plan version 2.0*
*Consolidated /corp command structure*
*Ready for development*
