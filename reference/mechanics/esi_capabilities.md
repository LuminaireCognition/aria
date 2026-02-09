# ESI API Capabilities Reference

## Overview

EVE's ESI (EVE Swagger Interface) API is predominantly **read-only**. Most endpoints query game state but cannot modify it. ARIA can monitor your character but cannot play the game for you.

## Read-Only vs Write-Capable

### Read-Only Endpoints (95%+ of ESI)

These endpoints query data. ARIA can display this information but **cannot take action**.

| Category | What ARIA Can See | What ARIA CANNOT Do |
|----------|-------------------|---------------------|
| **Location** | Current system, ship, docked status | Move your ship, undock, warp |
| **Skills** | Training queue, skill levels, SP | Start/stop training, inject skills |
| **Industry** | Job status, progress, completion | Deliver jobs, start manufacturing, research |
| **Wallet** | Balance, transactions, journal | Transfer ISK, buy/sell items |
| **Assets** | Inventory, ship fittings | Move items, repackage, trash |
| **Blueprints** | BPO/BPC list, ME/TE levels | Research, copy, invent |
| **Market** | Prices, orders, history | Place buy/sell orders |
| **Corp** | Wallet, assets, members | Any corporate actions |

### Write-Capable Endpoints (Very Limited)

A few endpoints allow modifications, but with significant restrictions:

| Category | Endpoint | What It Can Do | Limitations |
|----------|----------|----------------|-------------|
| **Mail** | POST /mail | Send EVE mail | Text only, no attachments |
| **Contacts** | POST/PUT/DELETE | Manage contact list | Standings only |
| **Fittings** | POST/DELETE | Save/delete fits | To character's saved fits only |
| **Fleet** | Various | Fleet management | Only if fleet boss |
| **Calendar** | POST | Create events | Corp/alliance calendars |
| **Bookmarks** | POST/DELETE | Manage bookmarks | Personal only |

**Note:** Even write-capable endpoints cannot interact with the game world - they modify data structures but don't control your ship or perform in-game actions.

## What This Means for ARIA

### ARIA Can:
- **Monitor** your character's status
- **Display** information about your assets, skills, industry, wallet
- **Analyze** data and provide recommendations
- **Track** progress over time
- **Alert** you when action is needed

### ARIA Cannot:
- **Control** your ship in any way
- **Perform** in-game actions (manufacturing, research, trading)
- **Interact** with the EVE client
- **Automate** gameplay
- **Make decisions** that affect your character

## Response Guidelines

When displaying ESI data that might prompt action requests:

1. **Always clarify limitations** when showing actionable data
2. **Provide in-game steps** for required actions
3. **Use monitoring language** ("I can see...", "Status shows...")
4. **Avoid action language** that implies capability ("I'll deliver...", "Starting job...")

### Example Patterns

**Good:**
```
Your 3 ME Research jobs are ready for delivery.

In-Game Action Required:
  Industry window (Alt+S) → Jobs tab → Select jobs → Deliver

Run /industry-jobs again after delivery to confirm.
```

**Bad:**
```
Your 3 ME Research jobs are ready. Would you like me to deliver them?
```

## Why These Limitations Exist

CCP intentionally limits ESI write access to prevent:
- Botting and automation
- Third-party tools playing the game
- Security risks from external control
- Unfair advantages

ESI is designed for **information** and **integration**, not **automation**.

## Quick Reference by Skill

| ARIA Skill | ESI Access | Can Modify? |
|------------|------------|-------------|
| `/industry-jobs` | Read-only | No - view only |
| `/skillqueue` | Read-only | No - view only |
| `/wallet-journal` | Read-only | No - view only |
| `/esi-query` | Read-only | No - view only |
| `/lp-store` | Read-only | No - view only |
| `/clones` | Read-only | No - view only |
| `/killmails` | Read-only | No - view only |
| `/contracts` | Read-only | No - view only |
| `/agents-research` | Read-only | No - view only |
| `/mining` | Read-only | No - view only |
| `/orders` | Read-only | No - view only |
| `/fittings` | Read-only | No - view only |
| `/mail` | Read-only | No - view only |
| `/price` | Read-only (public) | No - market data only |
| `/route` | Read-only (public) | No - calculation only |
| `/threat-assessment` | Read-only (public) | No - activity data only |
| `/corp` | Read-only | No - view only |
| `/fitting` | Read-only | No - export only* |

*Fitting export provides EFT format for manual import into EVE client.
