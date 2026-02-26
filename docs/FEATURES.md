# ARIA Feature Showcase

ARIA is a Claude Code extension that turns Claude into a tactical EVE Online assistant. It provides real-time intel, fitting advice, market analysis, and mission preparation — all through natural conversation.

---

## Feature Matrix

### Combat & Tactical

| Feature | Description | Command | Requires ESI? |
|---------|-------------|---------|:-------------:|
| Ship fitting | Module recommendations, tank analysis, EOS-validated stats | `/fitting` | No |
| Fit validation | Check if you can fly and afford a fit | `/fit-check` | Yes |
| Budget fitting | Downgrade expensive fits to match your skills | `/fit-budget` | Yes |
| Mission briefs | Enemy intel, damage profiles, wave breakdowns, blitz strategies | `/mission-brief` | No |
| Abyssal guide | Weather types, tiers, ship fits, NPC threats | `/abyssal` | No |
| Threat assessment | System security analysis with live kill activity | `/threat-assessment` | No |
| Gatecamp detection | Real-time camp alerts along routes or in systems | `/gatecamp` | No |
| Route planning | Safe/shortest/unsafe routing with activity data | `/route` | No |
| Local area intel | Orientation after wormhole jumps or filaments | `/orient` | No |
| Killmail analysis | Tactical breakdown of individual killmails | `/killmail` | No |
| Loss post-mortem | Analyze your deaths and improve survivability | `/killmails` | Yes |
| Ship progression | What to fly next based on your skills and wallet | `/ship-next` | Yes |
| Skill planning | Training time estimates, Easy 80% plans, min-max plans | `/skillplan` | Yes |
| Skill queue | Monitor training progress and ETAs | `/skillqueue` | Yes |
| Clone status | Medical clone location and implant check | `/clones` | Yes |
| Entity tracking | Watch corporations and alliances for kill alerts | `/watchlist` | No |

### Market & Finance

| Feature | Description | Command | Requires ESI? |
|---------|-------------|---------|:-------------:|
| Price check | Market prices across trade hubs | `/price` | No |
| Item finder | Find items for sale near a location | `/find` | No |
| Market orders | Your active buy/sell orders and fill status | `/orders` | Yes |
| Asset valuation | Inventory with market value calculations | `/assets` | Yes |
| Contracts | Item exchange, courier, and auction contracts | `/contracts` | Yes |
| Wallet journal | ISK flow analysis and transaction history | `/wallet-journal` | Yes |
| LP store | LP balance and store offers | `/lp-store` | Yes |
| ISK/hour compare | Compare earnings across activities you can do | `/isk-compare` | Yes |
| Arbitrage scanner | Cross-region trade opportunity finder | `/arbitrage` | No |

### Industry & Operations

| Feature | Description | Command | Requires ESI? |
|---------|-------------|---------|:-------------:|
| Build cost | Manufacturing cost calculator with profit margins | `/build-cost` | No |
| Industry jobs | Monitor manufacturing, research, and invention | `/industry-jobs` | Yes |
| Reactions | Moon reaction and fuel block calculator | `/reactions` | No |
| Research agents | Research agent partnerships and RP tracking | `/agents-research` | Yes |
| Mining ledger | What you've mined over the past 30 days | `/mining` | Yes |
| Mining advisory | Ore recommendations and optimization | `/mining-advisory` | No |
| Exploration | Relic/data site analysis and hacking tips | `/exploration` | No |
| Planetary interaction | PI production chains and planet resources | `/pi` | No |
| Saved fittings | View ship fittings from EVE | `/fittings` | Yes |
| EVE mail | Read inbox and specific messages | `/mail` | Yes |
| Operations journal | Log mission completions and discoveries | `/journal` | No |

### Identity & Status

| Feature | Description | Command | Requires ESI? |
|---------|-------------|---------|:-------------:|
| Pilot profile | Your identity, or look up another character | `/pilot` | Yes |
| Standings | Agent access progression and standing repair | `/standings` | Yes |
| Corporation | Corp status, wallet, assets, blueprints | `/corp` | Yes |
| Status report | ARIA operational summary | `/aria-status` | No |
| ESI query | Live data — location, wallet, skills, blueprints | `/esi-query` | Yes |

### Pirate-Exclusive (PARIA Persona)

| Feature | Description | Command | Requires ESI? |
|---------|-------------|---------|:-------------:|
| Hunting grounds | Analyze systems for target availability | `/hunting-grounds` | No |
| Mark assessment | Evaluate targets for engagement viability | `/mark-assessment` | No |
| Escape routes | Fastest routes to safe harbor | `/escape-route` | Yes |
| Ransom calculator | Calculate appropriate ransom amounts | `/ransom-calc` | No |
| Sec status tracking | Security status and tag cost calculator | `/sec-status` | Yes |

---

## Key Capabilities

### Natural Language Understanding

No need to memorize commands. ARIA responds to natural phrasing:

- "I accepted a mission against Serpentis" → mission brief
- "Is the route to Jita safe?" → threat assessment + route
- "What skills do I need for a Dominix?" → skill planning
- "How much is Tritanium worth?" → price check

### Faction Personas

Optional roleplay mode with 5 faction-specific AI personalities:

| Persona | Faction | Style |
|---------|---------|-------|
| ARIA Mk.IV | Gallente | Warm, witty, values freedom and choice |
| AURA-C | Caldari | Formal, efficient, corporate and metrics-driven |
| THRONE | Amarr | Dignified, reverent, tradition and faith |
| VIND | Minmatar | Direct, passionate, tribal loyalty |
| PARIA | Pirate | Irreverent, pragmatic, unlocks pirate commands |

### Data Verification

ARIA never presents unverified training data as fact. All game mechanics data is verified against CCP's Static Data Export (SDE) and the EOS fitting engine before presentation.

### MCP-Powered Backend

Real-time data through 8 MCP dispatchers covering universe navigation, market data, static game data, skill planning, ship fitting, killmails, pilot data, and system status.

---

*48 commands across 5 categories. See [COMMANDS.md](COMMANDS.md) for the full reference.*
