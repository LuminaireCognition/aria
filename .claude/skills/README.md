# ARIA Skills Directory

ARIA provides 48 slash commands across 6 categories. Skills are invoked with `/{name}` or natural language triggers.

For the frontmatter specification, see [SCHEMA.md](SCHEMA.md). To create a new skill, see [dev/docs/CONTRIBUTING_SKILLS.md](../../dev/docs/CONTRIBUTING_SKILLS.md).

## Tactical (19)

| Skill | Description | Persona |
|-------|-------------|---------|
| `/abyssal` | Abyssal Deadspace guide — weather, tiers, fits, NPC threats | All |
| `/clones` | Clone and implant status tracking | All |
| `/escape-route` | Fastest route to safe harbor | PARIA only |
| `/fit-budget` | Downgrade T2 fits to match current skills | All |
| `/fit-check` | Validate if you can fly and afford a fit | All |
| `/fitting` | Ship fitting assistance — EFT format, EOS-validated stats | All |
| `/gatecamp` | Real-time gatecamp detection and intel | All |
| `/hunting-grounds` | System analysis for target availability | PARIA only |
| `/killmail` | Individual killmail analysis with tactical context | All |
| `/killmails` | Kill and loss history analysis | All |
| `/mark-assessment` | Target evaluation for engagement viability | PARIA only |
| `/mission-brief` | Mission intel — enemy factions, damage profiles, blitz strategies | All |
| `/orient` | Local area intel for orientation in unknown space | All |
| `/route` | Safe/shortest/unsafe routing with activity data | All |
| `/ship-next` | Ship progression advisor based on skills and wallet | All |
| `/skillplan` | Skill planning — training time, Easy 80%, min-max plans | All |
| `/skillqueue` | Skill training queue and ETA | All |
| `/threat-assessment` | System security and activity risk analysis | All |
| `/watchlist` | Entity watchlists for tracking corps and alliances | All |

## Financial (10)

| Skill | Description | Persona |
|-------|-------------|---------|
| `/arbitrage` | Cross-region arbitrage opportunity scanner | All |
| `/assets` | Asset inventory with market valuation | All |
| `/contracts` | Personal contract management | All |
| `/find` | Find market sources near your location | All |
| `/isk-compare` | Compare ISK/hour across activities | All |
| `/lp-store` | LP balance and store offers | All |
| `/orders` | Active market orders and order history | All |
| `/price` | Market price lookups and spread analysis | All |
| `/ransom-calc` | Ransom calculation based on ship/cargo value | PARIA only |
| `/wallet-journal` | Wallet transaction history and ISK flow | All |

## Operations (7)

| Skill | Description | Persona |
|-------|-------------|---------|
| `/exploration` | Relic/data site analysis and hacking guidance | All |
| `/fittings` | View saved ship fittings from ESI | All |
| `/journal` | Log mission completions and exploration discoveries | All |
| `/mail` | Read EVE mail headers and bodies | All |
| `/mining` | Mining ledger — ore extraction history | All |
| `/mining-advisory` | Ore recommendations and mining optimization | All |
| `/pi` | Planetary Interaction production chains and resources | All |

## Industry (4)

| Skill | Description | Persona |
|-------|-------------|---------|
| `/agents-research` | Research agent partnerships and RP tracking | All |
| `/build-cost` | Manufacturing cost calculator with ME efficiency | All |
| `/industry-jobs` | Manufacturing, research, copying, invention jobs | All |
| `/reactions` | Moon material reactions and fuel block calculator | All |

## Identity (5)

| Skill | Description | Persona |
|-------|-------------|---------|
| `/aria-status` | Operational status report | All |
| `/corp` | Corporation status, wallet, assets, blueprints | All |
| `/pilot` | Pilot identity and configuration | All |
| `/sec-status` | Security status tracking and empire access | PARIA only |
| `/standings` | Standings tracker and progression planner | All |

## System (3)

| Skill | Description | Persona |
|-------|-------------|---------|
| `/esi-query` | Query ESI for live character data | All |
| `/help` | Display available commands and capabilities | All |
| `/setup` | First-run configuration wizard | All |

## Persona-Exclusive Skills

5 skills are exclusive to the PARIA persona:

| Skill | Description |
|-------|-------------|
| `/escape-route` | Route planning to safe harbor |
| `/hunting-grounds` | System analysis for piracy targets |
| `/mark-assessment` | Target evaluation for engagement |
| `/ransom-calc` | Ransom amount calculation |
| `/sec-status` | Security status and empire access tracking |

Non-PARIA users see a stub message when invoking these commands. See [skill-loading.md](../../personas/_shared/skill-loading.md) for the exclusivity mechanism.

## Skills with Persona Overlays

8 skills have persona-specific overlays that modify presentation:

`aria-status`, `fitting`, `gatecamp`, `journal`, `killmail`, `mission-brief`, `price`, `route`, `threat-assessment`, `watchlist`

Overlays change terminology and framing without altering core skill logic.
