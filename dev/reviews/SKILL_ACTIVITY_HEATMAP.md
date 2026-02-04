# ARIA Skill Activity Heatmap

**Generated:** 2026-01-30
**Analysis Period:** 2026-01-13 to 2026-01-30 (Project inception to present)
**Total Skill Commits:** 71 this month

## Executive Summary

This heatmap analyzes git commit activity across ARIA's 43 slash commands (skills) to identify:
- Which skills have received the most testing and iteration
- Which skills are newly added and may need more testing
- Areas of technical debt or neglect

## Activity Heatmap

### 🔴 HIGH ACTIVITY (10+ commits)
*Heavily tested, iterated upon, production-ready*

| Skill | Commits | First | Last | Activity Pattern |
|-------|---------|-------|------|------------------|
| `/mission-brief` | 18 | Jan 13 | Jan 30 | █████████████████▊ Continuous iteration |
| `/help` | 16 | Jan 14 | Jan 30 | █████████████████░ Regular updates |
| `/fitting` | 14 | Jan 13 | Jan 25 | █████████████▊░░░ Major feature work |
| `/threat-assessment` | 14 | Jan 13 | Jan 25 | █████████████▊░░░ Intel system core |
| `/esi-query` | 11 | Jan 13 | Jan 23 | ██████████▉░░░░░░ ESI foundation |
| `/route` | 10 | Jan 15 | Jan 25 | ██████████░░░░░░░ Navigation core |
| `/journal` | 10 | Jan 13 | Jan 24 | ██████████░░░░░░░ Logging system |
| `/aria-status` | 10 | Jan 13 | Jan 24 | ██████████░░░░░░░ Diagnostics |

### 🟡 MEDIUM ACTIVITY (5-9 commits)
*Functional, tested for primary use cases*

| Skill | Commits | First | Last | Activity Pattern |
|-------|---------|-------|------|------------------|
| `/price` | 7 | Jan 15 | Jan 23 | ███████░░░░░░░░░░ Market queries |
| `/first-run-setup` | 7 | Jan 14 | Jan 19 | ███████░░░░░░░░░░ Onboarding |
| `/exploration` | 7 | Jan 13 | Jan 19 | ███████░░░░░░░░░░ Site guidance |
| `/skillqueue` | 6 | Jan 15 | Jan 23 | ██████░░░░░░░░░░░ Training monitor |
| `/pilot` | 6 | Jan 15 | Jan 23 | ██████░░░░░░░░░░░ Identity lookup |
| `/mining-advisory` | 6 | Jan 13 | Jan 19 | ██████░░░░░░░░░░░ Mining guidance |
| `/corp` | 6 | Jan 15 | Jan 23 | ██████░░░░░░░░░░░ Corp management |
| `/industry-jobs` | 5 | Jan 15 | Jan 23 | █████░░░░░░░░░░░░ Manufacturing |
| `/escape-route` | 5 | Jan 17 | Jan 19 | █████░░░░░░░░░░░░ Safety routes |
| `/agents-research` | 5 | Jan 15 | Jan 29 | █████░░░░░░░░░░░░ R&D agents |

### 🟢 LOW ACTIVITY (3-4 commits)
*Basic implementation, limited iteration*

| Skill | Commits | First | Last | Activity Pattern |
|-------|---------|-------|------|------------------|
| `/wallet-journal` | 4 | Jan 15 | Jan 23 | ████░░░░░░░░░░░░░ Financial tracking |
| `/sec-status` | 4 | Jan 17 | Jan 19 | ████░░░░░░░░░░░░░ Pirate exclusive |
| `/ransom-calc` | 4 | Jan 17 | Jan 19 | ████░░░░░░░░░░░░░ Pirate exclusive |
| `/orders` | 4 | Jan 15 | Jan 16 | ████░░░░░░░░░░░░░ Market orders |
| `/mining` | 4 | Jan 15 | Jan 16 | ████░░░░░░░░░░░░░ Mining ledger |
| `/mark-assessment` | 4 | Jan 17 | Jan 19 | ████░░░░░░░░░░░░░ Pirate exclusive |
| `/mail` | 4 | Jan 15 | Jan 16 | ████░░░░░░░░░░░░░ EVE mail |
| `/hunting-grounds` | 4 | Jan 17 | Jan 19 | ████░░░░░░░░░░░░░ Pirate exclusive |
| `/fittings` | 4 | Jan 15 | Jan 16 | ████░░░░░░░░░░░░░ Saved fittings |
| `/contracts` | 4 | Jan 15 | Jan 16 | ████░░░░░░░░░░░░░ Contract viewer |
| `/clones` | 4 | Jan 15 | Jan 16 | ████░░░░░░░░░░░░░ Clone status |
| `/skillplan` | 3 | Jan 20 | Jan 20 | ███░░░░░░░░░░░░░░ Single-day add |
| `/lp-store` | 3 | Jan 15 | Jan 16 | ███░░░░░░░░░░░░░░ LP store browse |
| `/killmails` | 3 | Jan 15 | Jan 16 | ███░░░░░░░░░░░░░░ Kill history |
| `/arbitrage` | 3 | Jan 18 | Jan 22 | ███░░░░░░░░░░░░░░ Trade scanning |

### ⚪ MINIMAL ACTIVITY (1-2 commits)
*Recently added or untested - potential technical debt*

| Skill | Commits | First | Last | Status |
|-------|---------|-------|------|--------|
| `/gatecamp` | 2 | Jan 25 | Jan 25 | ⚠️ New, needs testing |
| `/watchlist` | 1 | Jan 25 | Jan 25 | ⚠️ Single commit, untested |
| `/standings` | 1 | Jan 29 | Jan 29 | ⚠️ Very new |
| `/pi` | 1 | Jan 29 | Jan 29 | ⚠️ Very new |
| `/orient` | 1 | Jan 26 | Jan 26 | ⚠️ New, needs testing |
| `/killmail` | 1 | Jan 25 | Jan 25 | ⚠️ Single commit |
| `/find` | 1 | Jan 19 | Jan 19 | ⚠️ Untouched since add |
| `/build-cost` | 1 | Jan 29 | Jan 29 | ⚠️ Very new |
| `/assets` | 1 | Jan 29 | Jan 29 | ⚠️ Very new |
| `/abyssal` | 1 | Jan 29 | Jan 29 | ⚠️ Very new |

## Development Timeline

```
Jan 13 ██                  Project inception
Jan 14 █████               Initial skills batch
Jan 15 ████████████████    ESI skills batch (peak activity)
Jan 16 ██████              Schema standardization
Jan 17 ████████            PARIA persona + pirate skills
Jan 18 █████████           Arbitrage system
Jan 19 ███                 Userdata migration
Jan 20 ███                 Skillplan addition
Jan 21 █                   Light day
Jan 22 █████               Mission caching
Jan 23 ██                  Bug fixes
Jan 24 ██                  Journal updates
Jan 25 █████               Real-time intel Phase 3
Jan 26 █                   Orient skill
Jan 29 ██                  New skill batch (pi, abyssal, etc.)
Jan 30 █                   PvE intel rename
```

## Key Insights

### High-Confidence Skills (Battle-Tested)
These skills have received extensive iteration and bug fixes:
1. **`/mission-brief`** - Most active skill, underwent major architecture changes (cache-first pattern, data lookup protocol)
2. **`/route`** - Core navigation with activity data integration
3. **`/fitting`** - Tank coherence, EOS validation, skill prerequisites
4. **`/threat-assessment`** - Real-time intel integration

### Technical Debt Concerns
Skills with 1 commit that may need attention:
- **`/ransom-calc`** - Persona-exclusive, but only schema standardization commits
- **`/watchlist`** - Entity tracking system, single commit
- **`/find`** - Market proximity search, no iteration since initial add
- **Recent batch (Jan 29)** - `/pi`, `/abyssal`, `/standings`, `/build-cost`, `/assets` all added in one commit, untested

### Persona-Exclusive Skills
These 4 skills are PARIA-exclusive and received less testing since they require pirate persona:
- `/ransom-calc` (4 commits)
- `/sec-status` (4 commits)
- `/mark-assessment` (4 commits)
- `/hunting-grounds` (4 commits)

### Recommendations

1. **Prioritize testing for Jan 29 batch:** `/pi`, `/abyssal`, `/standings`, `/build-cost`, `/assets` have minimal testing
2. **Review `/find` skill:** Added Jan 19, no subsequent commits - may have undiscovered issues
3. **Validate `/gatecamp` and `/killmail`:** Part of real-time intel system but only 1-2 commits
4. **Test persona-exclusive skills:** The PARIA skills have schema commits but may lack functional testing

## Commit Distribution by Category

| Category | Skills | Total Commits |
|----------|--------|---------------|
| Core Navigation | route, threat-assessment, gatecamp, orient | 27 |
| ESI Data Display | esi-query, pilot, skillqueue, wallet-journal | 27 |
| Market/Economy | price, arbitrage, orders, find, build-cost | 16 |
| PvE Intel | mission-brief, exploration, abyssal | 26 |
| Industry | industry-jobs, mining, mining-advisory | 15 |
| Fitting/Ships | fitting, fittings, killmails, killmail | 22 |
| Pirate (PARIA) | ransom-calc, sec-status, mark-assessment, hunting-grounds | 16 |
| Meta/System | help, aria-status, journal, first-run-setup | 43 |

---
*Analysis generated from git log data. Commit counts reflect file changes, not necessarily code complexity.*
