# ARIA ESI Script Split Proposal

## Executive Summary

The `aria-esi` script is currently 3,794 lines (~37K tokens), exceeding Claude Code's 25K token read limit. Analysis reveals a well-organized but monolithic bash script with embedded Python heredocs. This proposal recommends splitting into a modular Python package while preserving the existing bash interface.

## Current Architecture Analysis

### Structure Overview

```
aria-esi (3,794 lines)
├── Bash Framework (~200 lines)
│   ├── Credential resolution
│   ├── Helper functions (esi_query, esi_public)
│   └── Corporation scope checks
│
├── Character Commands (~1,600 lines)
│   ├── cmd_profile, cmd_location, cmd_standings, cmd_wallet
│   ├── cmd_wallet_journal (complex Python heredoc)
│   ├── cmd_blueprints, cmd_skills, cmd_skillqueue
│   ├── cmd_industry_jobs, cmd_assets, cmd_fitting
│   └── cmd_pilot (self + public)
│
├── Corporation Commands (~900 lines)
│   ├── cmd_corp_status, cmd_corp_info
│   ├── cmd_corp_wallet, cmd_corp_assets
│   ├── cmd_corp_blueprints, cmd_corp_jobs
│   └── cmd_corp_help
│
├── Navigation & Market Commands (~800 lines)
│   ├── cmd_route (public, no auth)
│   ├── cmd_activity (public, no auth)
│   └── cmd_price (public, no auth)
│
└── Main Dispatcher (~30 lines)
```

### Key Observations

1. **Repeated Code Patterns**
   - `esi_get()` and `esi_post()` defined in ~15 different Python heredocs
   - Ship group ID constants defined 4 times (cmd_assets, cmd_fitting, cmd_corp_assets)
   - Date/time parsing logic duplicated across skill queue, industry jobs, wallet journal
   - Error handling patterns repeated throughout

2. **Logical Command Groups**
   - **Personal Data**: Authenticated character queries (location, wallet, skills, assets)
   - **Corporation**: Authenticated corp queries (requires director/CEO role)
   - **Public**: No authentication needed (route, activity, price, pilot lookup)

3. **Complexity Distribution**
   | Command | Lines | Complexity |
   |---------|-------|------------|
   | wallet_journal | ~230 | High - category mapping, aggregation |
   | fitting | ~275 | High - EFT format generation |
   | industry_jobs | ~260 | Medium - time calculations |
   | route | ~315 | Medium - threat assessment |
   | price | ~305 | Medium - order aggregation |
   | corp_* (total) | ~900 | Medium - similar to personal |

## Proposed Architecture

### Option A: Python Package with Bash Wrapper (Recommended)

Convert the core logic to a Python package while preserving the existing bash command interface for backwards compatibility.

```
.claude/scripts/
├── aria-esi                          # Thin bash wrapper (keeps existing interface)
├── aria_esi/                         # Python package
│   ├── __init__.py                   # Package init, CLI entry point
│   ├── __main__.py                   # Allow `python -m aria_esi`
│   │
│   ├── core/                         # Shared infrastructure
│   │   ├── __init__.py
│   │   ├── client.py                 # ESI HTTP client (esi_get, esi_post)
│   │   ├── auth.py                   # Credential resolution, token refresh
│   │   ├── constants.py              # Ship groups, trade hubs, activity types
│   │   └── formatters.py             # ISK formatting, duration, EFT output
│   │
│   ├── commands/                     # Command implementations
│   │   ├── __init__.py
│   │   ├── character.py              # profile, location, standings, wallet, skills
│   │   ├── assets.py                 # assets, fitting, blueprints
│   │   ├── industry.py               # industry_jobs, skillqueue
│   │   ├── wallet.py                 # wallet, wallet_journal
│   │   ├── corporation.py            # All corp_* commands
│   │   ├── navigation.py             # route, activity
│   │   ├── market.py                 # price
│   │   └── pilot.py                  # pilot self/public lookup
│   │
│   └── models/                       # Data structures (optional but clean)
│       ├── __init__.py
│       └── responses.py              # JSON response builders
│
├── aria-token-refresh.py             # (existing, unchanged)
└── aria-oauth-setup.py               # (existing, unchanged)
```

**New bash wrapper (`aria-esi`):**
```bash
#!/bin/bash
# Thin wrapper maintaining existing interface
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 -m aria_esi "$@"
```

### Option B: Modular Bash with Sourced Files

Keep bash but split into sourced files (less recommended due to heredoc complexity):

```
.claude/scripts/
├── aria-esi                          # Main entry point
├── aria-esi.d/                       # Sourced modules
│   ├── core.sh                       # Credential resolution, helpers
│   ├── character.sh                  # Character commands
│   ├── corporation.sh                # Corporation commands
│   ├── navigation.sh                 # Route, activity
│   └── market.sh                     # Price lookup
```

**Why Option A is better:**
- Python heredocs are already doing the heavy lifting
- Eliminates 15+ duplicate function definitions
- Better testability and error handling
- Easier to extend and maintain
- IDE support and type hints

## Implementation Details (Option A)

### Module Breakdown with Estimated Sizes

| Module | Source Lines | Token Estimate | Description |
|--------|-------------|----------------|-------------|
| `core/client.py` | ~80 | ~400 | HTTP client, request helpers |
| `core/auth.py` | ~100 | ~500 | Credential resolution, token mgmt |
| `core/constants.py` | ~80 | ~400 | Ship groups, hubs, mappings |
| `core/formatters.py` | ~60 | ~300 | ISK, duration, EFT formatters |
| `commands/character.py` | ~200 | ~1,000 | Profile, location, standings |
| `commands/wallet.py` | ~350 | ~1,800 | Wallet, journal with categories |
| `commands/assets.py` | ~400 | ~2,000 | Assets, fitting, blueprints |
| `commands/industry.py` | ~300 | ~1,500 | Industry jobs, skill queue |
| `commands/corporation.py` | ~500 | ~2,500 | All corp commands |
| `commands/navigation.py` | ~250 | ~1,200 | Route, activity |
| `commands/market.py` | ~200 | ~1,000 | Price lookups |
| `commands/pilot.py` | ~250 | ~1,200 | Pilot identity |
| **Total** | **~2,770** | **~13,800** | |

Each module fits comfortably under the 25K token limit, with the largest (`corporation.py`) at ~2,500 tokens.

### Shared Code Consolidation

**`core/constants.py`** - Currently duplicated 4x:
```python
SHIP_GROUP_IDS = {
    25,    # Frigate
    26,    # Cruiser
    27,    # Battleship
    # ... full list
    2001,  # Mining Frigate (Venture!)
}

TRADE_HUB_STATIONS = {
    "10000002": 60003760,  # Jita 4-4
    "10000043": 60008494,  # Amarr VIII
    # ...
}

ACTIVITY_TYPES = {
    1: ("manufacturing", "Manufacturing"),
    3: ("research_te", "TE Research"),
    # ...
}

REF_TYPE_CATEGORIES = {
    "bounty": ["bounty_prizes", "bounty_prize", ...],
    "market": ["market_transaction", "market_escrow"],
    # ...
}
```

**`core/client.py`** - Currently duplicated 15x:
```python
class ESIClient:
    BASE_URL = "https://esi.evetech.net/latest"

    def __init__(self, token: str = None):
        self.token = token

    def get(self, endpoint: str, auth: bool = False) -> dict:
        """GET request to ESI"""
        # Single implementation

    def post(self, endpoint: str, data: list) -> dict:
        """POST request to ESI"""
        # Single implementation
```

**`core/formatters.py`** - Currently duplicated 6x:
```python
def format_isk(value: float) -> str:
    """Format ISK with B/M/K suffix"""

def format_duration(seconds: float) -> str:
    """Format seconds as Xd Yh Zm"""

def to_roman(level: int) -> str:
    """Convert skill level to roman numeral"""

def parse_datetime(dt_str: str) -> datetime:
    """Parse ESI datetime string"""
```

### CLI Entry Point

**`aria_esi/__main__.py`**:
```python
import argparse
import sys
from .commands import character, wallet, assets, industry, corporation, navigation, market, pilot

def main():
    parser = argparse.ArgumentParser(prog='aria-esi')
    subparsers = parser.add_subparsers(dest='command')

    # Register subcommands
    character.register_parser(subparsers)
    wallet.register_parser(subparsers)
    assets.register_parser(subparsers)
    # ...

    args = parser.parse_args()
    # Dispatch to appropriate handler

if __name__ == '__main__':
    main()
```

## Migration Strategy

### Phase 1: Core Infrastructure (Foundation)
1. Create `aria_esi/` package structure
2. Implement `core/client.py` with ESI HTTP client
3. Implement `core/auth.py` with credential resolution
4. Implement `core/constants.py` with all shared constants
5. Implement `core/formatters.py` with utility functions
6. Create bash wrapper that calls Python package

### Phase 2: Public Commands (No Auth Required)
1. Migrate `cmd_route` → `commands/navigation.py`
2. Migrate `cmd_activity` → `commands/navigation.py`
3. Migrate `cmd_price` → `commands/market.py`
4. Migrate `cmd_pilot_public` → `commands/pilot.py`
5. Test all public commands work without credentials

### Phase 3: Personal Character Commands
1. Migrate `cmd_profile`, `cmd_location`, `cmd_standings` → `commands/character.py`
2. Migrate `cmd_wallet`, `cmd_wallet_journal` → `commands/wallet.py`
3. Migrate `cmd_skills`, `cmd_skillqueue` → `commands/industry.py`
4. Migrate `cmd_industry_jobs` → `commands/industry.py`
5. Migrate `cmd_assets`, `cmd_fitting`, `cmd_blueprints` → `commands/assets.py`

### Phase 4: Corporation Commands
1. Migrate all `cmd_corp_*` functions → `commands/corporation.py`
2. Test with corp scope authentication

### Phase 5: Cleanup
1. Remove original monolithic heredocs from bash wrapper
2. Add comprehensive error handling
3. Add type hints throughout
4. Update CLAUDE.md documentation references

## Benefits Summary

| Aspect | Current | After Split |
|--------|---------|-------------|
| **Context Window** | 37K tokens (exceeds limit) | Largest module ~2.5K tokens |
| **Code Duplication** | ~1,000 lines duplicated | Single source of truth |
| **Testability** | Hard to unit test | Easy to test each module |
| **Maintainability** | One change = full file read | Targeted file reads |
| **Error Handling** | Inconsistent | Centralized in client |
| **IDE Support** | None (bash) | Full Python tooling |
| **Type Safety** | None | Type hints available |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing commands | Keep bash wrapper interface identical |
| Environment differences | Use only stdlib (urllib.request, json) |
| Token refresh timing | Import existing `aria-token-refresh.py` |
| Permission model changes | Wrapper preserves `Bash(.claude/scripts/aria-esi:*)` |

## Recommendation

**Proceed with Option A (Python package).**

The current architecture is already 80% Python via heredocs. Converting to a proper Python package:
- Eliminates massive code duplication
- Makes each module individually readable by Claude Code
- Preserves the existing command interface
- Sets up for future features (async, caching, etc.)

Estimated effort: ~4 hours for full migration, testable incrementally per phase.

---

*Analysis performed on 2026-01-15 by ARIA tactical systems.*
