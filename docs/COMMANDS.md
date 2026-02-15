# ARIA Command Reference

All commands can be invoked as slash commands (`/command`) or as natural language. ARIA understands both.

**Quick tip:** You don't need to memorize commands. Just describe what you want — "what should I mine?", "is this system safe?", "fit my Vexor" — and ARIA will figure it out.

---

## Combat & Tactical

| Command | Description | Example |
|---------|-------------|---------|
| `/fitting` | Ship fitting assistance — module recommendations, tank analysis, EFT export | "fit my Vexor for L3 missions" |
| `/fit-check` | Validate if you can fly and afford a fit — paste any EFT format | "can I fly this fit?" |
| `/fit-budget` | Downgrade an expensive fit to match your skills and wallet | "make this fit cheaper" |
| `/mission-brief` | Tactical intel for missions — enemy damage types, waves, recommended loadout | "mission brief for Blockade L4" |
| `/abyssal` | Abyssal Deadspace guide — weather types, tiers, fits, NPC threats | "what filament for my Gila?" |
| `/threat-assessment` | System security and risk analysis | "is Uedama safe?" |
| `/gatecamp` | Real-time gatecamp detection along routes or in systems | "any camps on route to Jita?" |
| `/route` | Route planning with security analysis and activity data | "safest route from Dodixie to Amarr" |
| `/orient` | Local area intel — use after jumping into unfamiliar space | "just landed in Amamake" |
| `/killmail` | Analyze a specific killmail from zKillboard | Paste a zkillboard.com/kill/ URL |
| `/killmails` | Your kill and loss history with post-mortem analysis | "what killed me last?" |
| `/ship-next` | Ship progression advisor — what to fly next based on your skills | "what ship after my Vexor?" |
| `/skillplan` | Skill planning with training time estimates and Easy 80% plans | "skills needed for Dominix" |
| `/skillqueue` | Monitor your skill training queue and ETAs | "what am I training?" |
| `/clones` | Clone and implant status — check before risky operations | "where's my medical clone?" |
| `/watchlist` | Track corporations and alliances for kill alerts | "add CODE to watchlist" |

## Market & Finance

| Command | Description | Example |
|---------|-------------|---------|
| `/price` | Market price lookups across trade hubs | "price check PLEX" |
| `/find` | Find items for sale near a location | "where can I buy a Vexor near Dodixie?" |
| `/orders` | Your active buy/sell orders and fill status | "my market orders" |
| `/assets` | Asset inventory with market valuation | "what do I own?" |
| `/contracts` | Personal contracts — item exchange, courier, auction | "my contracts" |
| `/wallet-journal` | ISK flow analysis and transaction history | "where did my ISK go?" |
| `/lp-store` | LP balance and store offers | "what can I buy with LP?" |
| `/isk-compare` | Compare ISK/hour across activities you can do | "best way to make ISK" |
| `/arbitrage` | Cross-region trade opportunity scanner | "arbitrage opportunities" |

## Industry & Operations

| Command | Description | Example |
|---------|-------------|---------|
| `/build-cost` | Manufacturing cost calculator with profit margins | "cost to build a Dominix" |
| `/industry-jobs` | Monitor manufacturing, research, and invention jobs | "what's being built?" |
| `/reactions` | Moon reaction and fuel block calculator | "fuel block cost" |
| `/agents-research` | Research agent partnerships and accumulated RP | "my research agents" |
| `/mining` | Mining ledger — what you've mined over the past 30 days | "mining stats" |
| `/mining-advisory` | Ore recommendations and mining optimization | "what should I mine?" |
| `/exploration` | Relic/data site analysis and hacking tips | "I found a relic site" |
| `/pi` | Planetary Interaction production chains and planet resources | "how to make Robotics" |
| `/fittings` | View your saved ship fittings from EVE | "my saved fits" |
| `/mail` | Read EVE mail inbox | "check mail" |
| `/journal` | Log mission completions and exploration discoveries | "log that mission" |

## Identity & Status

| Command | Description | Example |
|---------|-------------|---------|
| `/pilot` | Your pilot profile, or look up another character | "who am I?" |
| `/standings` | Standings tracker and agent access progression | "can I use L4 agents?" |
| `/corp` | Corporation status, wallet, assets, blueprints | "corp status" |
| `/aria-status` | ARIA operational summary and session status | "sitrep" |
| `/esi-query` | Live ESI data — location, wallet, skills, blueprints | "wallet balance" |

## System

| Command | Description | Example |
|---------|-------------|---------|
| `/help` | List available commands and capabilities | "what can you do?" |
| `/setup` | First-run configuration wizard | "set up my profile" |

## Pirate-Exclusive Commands

These commands are only available when using the PARIA persona (pirate faction alignment).

| Command | Description | Example |
|---------|-------------|---------|
| `/hunting-grounds` | Analyze systems for target availability and traffic | "where should I hunt?" |
| `/mark-assessment` | Evaluate potential targets for engagement viability | "is this worth ganking?" |
| `/escape-route` | Find fastest routes to safe harbor | "get me out" |
| `/ransom-calc` | Calculate appropriate ransom amounts | "ransom for a Retriever" |
| `/sec-status` | Security status tracking and tag cost calculator | "can I go to high-sec?" |

---

## Natural Language

You don't need slash commands at all. ARIA responds to natural phrasing:

- "I accepted a mission against Serpentis" → triggers mission brief
- "Is the route to Jita safe?" → triggers threat assessment + route
- "What skills do I need for a Dominix?" → triggers skill planning
- "How much is Tritanium worth?" → triggers price check

Multiple commands can chain naturally in conversation — ask a follow-up and ARIA uses context from previous answers.

---

*48 commands across 7 categories. For in-session help, type `/help`.*
