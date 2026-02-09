---
name: help
description: Display available ARIA commands and capabilities. Use when capsuleer needs guidance on what ARIA can do.
model: haiku
category: system
triggers:
  - "/help"
  - "help"
  - "what can you do"
  - "commands"
  - "what commands are available"
  - "how do I..."
  - "show me the options"
requires_pilot: false
data_sources:
  - .claude/skills/_index.json
---

# ARIA Help & Discovery Module

## Purpose
Surface available commands, capabilities, and reference data. Reduce the need for external documentation by making ARIA's features discoverable in-session.

## Trigger Phrases
- `/help`
- "help"
- "what can you do"
- "commands"
- "what commands are available"
- "how do I..."
- "show me the options"

## Response Format

### Default `/help` Output

**Note:** Use standard markdown format unless `rp_level` is `moderate` or `full`. The formatted box version is shown below for reference, but at `off`/`lite` use plain markdown tables.

**Plain version (rp_level: off or lite):**

```markdown
## ARIA Commands

**Identity:**
| Command | Description |
|---------|-------------|
| `/pilot` | Full identity card (ARIA config + ESI data) |
| `/pilot <name>` | Public lookup of another pilot |

**Tactical:**
| Command | Description |
|---------|-------------|
| `/aria-status` | Operational status report |
| `/esi-query` | Live data (location, wallet, skills) |
| `/skillqueue` | Skill training queue and ETA |
| `/industry-jobs` | Manufacturing and research job monitoring |
| `/route` | Route planning between systems |
| `/mission-brief` | Mission intel and enemy analysis |
| `/threat-assessment` | System security and risk evaluation |
| `/fitting` | Ship fitting assistance and EFT export |

**Financial:**
| Command | Description |
|---------|-------------|
| `/price` | Market price lookup |
| `/wallet-journal` | Transaction history and income analysis |

**Operations:**
| Command | Description |
|---------|-------------|
| `/mining-advisory` | Ore recommendations and belt guidance |
| `/exploration` | Relic/data site analysis, hacking tips |
| `/journal` | Log missions and discoveries |

**Corporation:**
| Command | Description |
|---------|-------------|
| `/corp` | Corporation management (status, wallet, assets, etc.) |

**System:**
| Command | Description |
|---------|-------------|
| `/help` | This command listing |
| `/help <topic>` | Detailed help (rp, status, missions, fitting, corp, pilot, etc.) |
| `/setup` | Profile configuration |

Natural language works too: "is Hek safe", "fit my Vexor", "prepare for Serpentis"

Roleplay is off by default. See `/help rp` to enable immersive mode.
```

**Formatted version (rp_level: moderate or full):**

```
═══════════════════════════════════════════════════════════════════
ARIA COMMAND INTERFACE
───────────────────────────────────────────────────────────────────
IDENTITY:

  /pilot ............... Full identity card (ARIA config + ESI)
  /pilot <name> ........ Public lookup of another pilot

TACTICAL MODULES:

  /aria-status ......... Operational status report (stable data)
  /esi-query ........... Live GalNet data (location, wallet, skills)
  /skillqueue .......... Skill training queue and ETA
  /industry-jobs ....... Manufacturing/research job monitoring
  /route ............... Route planning between systems
  /mission-brief ....... Mission intel and enemy analysis
  /threat-assessment ... System security and risk evaluation
  /fitting ............. Ship fitting assistance and EFT export

FINANCIAL:

  /price ............... Market price lookup (buy/sell orders)
  /wallet-journal ...... Transaction history and income analysis

OPERATIONS:

  /mining-advisory ..... Ore recommendations and belt guidance
  /exploration ......... Relic/data site analysis, hacking tips
  /journal ............. Log missions and exploration discoveries

CORPORATION:

  /corp ................ Corporation management (status, wallet, etc.)

SYSTEM:

  /help ................ This command listing
  /help <topic> ........ Detailed help on specific topic
  /setup ............... Conversational profile configuration

───────────────────────────────────────────────────────────────────
Natural language works too: "prepare for mission", "is this system
safe", "what should I mine", "fit my Vexor"

For reference data: say "show database" or "data index"
═══════════════════════════════════════════════════════════════════
```

## Topic-Specific Help

When capsuleer requests `/help <topic>`, provide focused guidance:

### `/help aria-status` or `/help status`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Pilot Status Reports
───────────────────────────────────────────────────────────────────
Command: /aria-status

Generates operational summary using STABLE data only.

INCLUDES:
• Capsuleer identity and home base
• Ship roster and designated roles
• Faction standings summary
• Current objectives

DOES NOT INCLUDE (volatile data):
• Current location — use /esi-query
• Current ship — use /esi-query
• Wallet balance — use /esi-query

TRIGGERS: "status report", "sitrep", "what's my status"
═══════════════════════════════════════════════════════════════════
```

### `/help pilot` or `/help identity`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Pilot Identity
───────────────────────────────────────────────────────────────────
Command: /pilot [name|id]

SELF QUERY (no arguments):
  Shows full identity card combining:
  • ARIA configuration (experience, RP level, constraints)
  • Live ESI data (corp, alliance, security status)
  • Account snapshot (wallet, skill points)
  • ESI scope availability

OTHER PILOT LOOKUP (with name/id):
  Shows public data only:
  • Character name and ID
  • Corporation and alliance
  • Security status and capsuleer birthday

TRIGGERS: "who am I", "my profile", "look up [name]"
═══════════════════════════════════════════════════════════════════
```

### `/help esi` or `/help live`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Live Data Queries
───────────────────────────────────────────────────────────────────
Command: /esi-query <type>

Query Types:
  location .... Current system and ship (volatile)
  wallet ...... ISK balance (volatile)
  standings ... Faction reputation (semi-stable)
  skills ...... Trained skills (semi-stable)
  blueprints .. Owned BPOs/BPCs (semi-stable)

REQUIRES: ESI authentication configured
SETUP: See docs/ESI.md

TRIGGERS: "where am I", "what ship", "my wallet", "check skills"
═══════════════════════════════════════════════════════════════════
```

### `/help skillqueue` or `/help training`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Skill Queue Monitoring
───────────────────────────────────────────────────────────────────
Command: /skillqueue

Monitor your skill training queue in real-time.

DISPLAYS:
  • Currently training skill with progress %
  • Full queue with completion estimates
  • Total queue duration
  • Queue completion date/time

VOLATILITY: Data changes continuously as skills train.
            Always includes query timestamp.

REQUIRES: ESI authentication with skillqueue scope
  → esi-skills.read_skillqueue.v1

TRIGGERS: "what am I training", "skill queue", "training status",
          "skill eta", "when will skills finish"

RELATED:
  /esi-query skills .... List trained skill levels (not queue)
  /pilot ............... Total skill points summary
═══════════════════════════════════════════════════════════════════
```

### `/help industry-jobs` or `/help manufacturing`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Industry Jobs Monitoring
───────────────────────────────────────────────────────────────────
Command: /industry-jobs [options]

Monitor your personal manufacturing and research jobs.

OPTIONS:
  --active ....... Active jobs only (default)
  --completed .... Jobs ready for delivery
  --history ...... Include recently completed jobs
  --all .......... Show all jobs

DISPLAYS:
  • Active manufacturing runs with progress
  • Research jobs (ME/TE) with completion times
  • Copying and invention status
  • Jobs ready for delivery (action needed!)

JOB TYPES:
  Manufacturing .... Producing items from blueprints
  ME Research ...... Improving material efficiency
  TE Research ...... Improving time efficiency
  Copying .......... Creating blueprint copies
  Invention ........ T2/T3 invention attempts

VOLATILITY: Semi-stable. Jobs progress on fixed timers.

REQUIRES: ESI authentication with industry jobs scope
  → esi-industry.read_character_jobs.v1

TRIGGERS: "my industry jobs", "what's being built",
          "manufacturing status", "check my jobs"

RELATED:
  /corp jobs ............. Corporation industry jobs
  /esi-query blueprints .. View owned blueprints
  /wallet-journal ........ Track industry costs
═══════════════════════════════════════════════════════════════════
```

### `/help missions`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Mission Intelligence
───────────────────────────────────────────────────────────────────
Command: /mission-brief

Provides tactical briefings including:
• Enemy damage types (what to tank)
• Recommended damage to deal
• EWAR and special mechanics
• Ship fitting recommendations

TRIGGERS: "mission brief", "prepare for mission", "what should I
          know about [faction]"

CACHED INTEL: reference/pve-intel/INDEX.md
DAMAGE TYPES: reference/mechanics/npc_damage_types.md
═══════════════════════════════════════════════════════════════════
```

### `/help fitting`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Fitting Assistance
───────────────────────────────────────────────────────────────────
Command: /fitting

Capabilities:
• Ship fitting recommendations by role
• EFT format export (importable to EVE client)
• Module alternatives for self-sufficient pilots
• Tank/damage analysis

TRIGGERS: "fit my [ship]", "export fitting", "EFT format",
          "what modules for [ship]"

SAVED FITS: reference/ships/fittings/
SHIP TREES: reference/ships/[faction]_progression.md
═══════════════════════════════════════════════════════════════════
```

### `/help mining`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Mining Operations
───────────────────────────────────────────────────────────────────
Command: /mining-advisory

Provides:
• Ore recommendations by mineral needs
• Belt selection guidance
• Venture optimization tips
• Safety considerations by security level

TRIGGERS: "mining advisory", "what should I mine", "ore help"

REFERENCE: reference/mechanics/ore_database.md
═══════════════════════════════════════════════════════════════════
```

### `/help exploration`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Exploration Analysis
───────────────────────────────────────────────────────────────────
Command: /exploration

Provides:
• Site classification and difficulty
• Expected loot by faction
• Hacking minigame strategies
• Ghost site warnings

TRIGGERS: "exploration analysis", "I found a [site]", "hacking tips"

REFERENCE: reference/mechanics/exploration_sites.md
           reference/mechanics/hacking_guide.md
═══════════════════════════════════════════════════════════════════
```

### `/help threat` or `/help security`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Threat Assessment
───────────────────────────────────────────────────────────────────
Command: /threat-assessment

Evaluates:
• System security status implications
• CONCORD response times
• Live activity data (kills/jumps in last hour)
• Activity-specific risks
• Mitigation recommendations

LIVE INTEL:
  When assessing a specific system, ARIA queries live kill/jump
  statistics from the last hour to enhance threat analysis.
  No authentication required - uses public ESI endpoints.

THREAT LEVELS: MINIMAL | ELEVATED | HIGH | CRITICAL

TRIGGERS: "is [system] safe", "threat assessment", "security
          analysis", "what are the risks"

RELATED:
  aria-esi activity <system> ... Raw activity data (JSON)
═══════════════════════════════════════════════════════════════════
```

### `/help route` or `/help navigation`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Route Planning
───────────────────────────────────────────────────────────────────
Command: /route <origin> <destination> [flags]

Calculate optimal routes between solar systems.

FLAGS:
  --safe ...... High-sec only routes (avoid low/null)
  --shortest .. Shortest path regardless of security (default)
  --risky ..... Prefer low-sec/null routes

EXAMPLES:
  /route Dodixie Jita           Shortest route
  /route Amarr Hek --safe       Safe route (high-sec only)
  /route Jita                   From current location (ESI required)

OUTPUT INCLUDES:
• Jump count and system list
• Security status per system
• Region information
• Threat level assessment

TRIGGERS: "route to [system]", "how do I get to", "plot course",
          "safest route to"

NO AUTHENTICATION REQUIRED - uses public ESI endpoint.
═══════════════════════════════════════════════════════════════════
```

### `/help price` or `/help market`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Market Price Lookup
───────────────────────────────────────────────────────────────────
Command: /price <item> [--region]

Look up market prices for any tradeable item.

REGION FLAGS:
  --jita ...... The Forge (Jita 4-4)
  --amarr ..... Domain (Amarr VIII)
  --dodixie ... Sinq Laison (Dodixie IX)
  --rens ...... Heimatar (Rens VI)
  --hek ....... Metropolis (Hek VIII)

EXAMPLES:
  /price Tritanium              Global average price
  /price Tritanium --jita       Jita buy/sell orders
  /price "Hammerhead II" --amarr  Multi-word item names

OUTPUT INCLUDES:
• Global average and adjusted prices
• Best buy/sell orders (with region flag)
• Volume at each price point
• Buy/sell spread percentage

USE CASES:
• Loot valuation
• Manufacturing cost analysis
• LP store comparisons
• Salvage prioritization

TRIGGERS: "price check", "how much is X worth", "market price"

NO AUTHENTICATION REQUIRED - uses public ESI endpoint.
═══════════════════════════════════════════════════════════════════
```

### `/help wallet-journal` or `/help finances`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Wallet Journal & Financial Analysis
───────────────────────────────────────────────────────────────────
Command: /wallet-journal [options]

Analyze ISK flow with income and expense breakdowns.

OPTIONS:
  --days N ....... Period to analyze (default: 7, max: 30)
  --type TYPE .... Filter by category

TYPE CATEGORIES:
  bounty ........ NPC bounties and mission rewards
  market ........ Buy/sell market transactions
  industry ...... Manufacturing and research costs
  tax ........... Broker fees and sales tax
  transfer ...... Player donations and corp transfers
  insurance ..... Ship insurance payouts

EXAMPLES:
  /wallet-journal                # Last 7 days summary
  /wallet-journal --days 30      # Last 30 days
  /wallet-journal --type bounty  # Only bounty income

OUTPUT INCLUDES:
• Net change (income - expenses)
• Income breakdown by source (bounties, missions, sales)
• Expense breakdown (taxes, purchases, fees)
• Recent transactions with details

REQUIRES: ESI authentication (uses existing wallet scope)

TRIGGERS: "where did my ISK go", "income breakdown",
          "wallet history", "ISK flow"

RELATED:
  /esi-query wallet .... Current balance snapshot
  /price ............... Market price lookup
═══════════════════════════════════════════════════════════════════
```

### `/help journal` or `/help logging`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Operations Logging
───────────────────────────────────────────────────────────────────
Command: /journal

Records:
• Mission completions (standing tracking)
• Exploration discoveries (loot records)

Entry Types:
  /journal mission ..... Log completed mission
  /journal exploration . Log site discovery

LOG FILES: Mission log and exploration catalog
           (location varies by structure version)

TRIGGERS: "log mission", "record that", "log site"
═══════════════════════════════════════════════════════════════════
```

### `/help corp` or `/help corporation`
```
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
  uv run python .claude/scripts/aria-oauth-setup.py
  Select "Yes" when asked about corporation scopes.

NOTE: NPC corporation members cannot access corp data endpoints.
═══════════════════════════════════════════════════════════════════
```

### `/help data` or `/help database`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Reference Database
───────────────────────────────────────────────────────────────────
ARIA maintains local intelligence files for offline access.

QUICK ACCESS:
• PvE intel ............ reference/pve-intel/INDEX.md
• Ship fittings ........ reference/ships/fittings/README.md
• NPC damage types ..... reference/mechanics/npc_damage_types.md
• Hacking guide ........ reference/mechanics/hacking_guide.md
• Ore database ......... reference/mechanics/ore_database.md

FULL INDEX: reference/INDEX.md

Say "show [topic]" to display specific reference data.
═══════════════════════════════════════════════════════════════════
```

### `/help esi` or `/help live`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Live Data (Optional Enhancement)
───────────────────────────────────────────────────────────────────
ESI integration is OPTIONAL. All ARIA features work without it.

WITHOUT ESI (default):
• Update your pilot profile with standings
• Update your ship status file with fittings
• Tell me your location for local intel

WITH ESI (optional enhancement):
• Automatic location and ship detection
• Live standings sync
• Wallet and skill tracking
• Blueprint inventory sync

SETUP (when ready, ~5 minutes):
  uv run python .claude/scripts/aria-oauth-setup.py

COMMANDS (after setup):
  /esi-query location .... Current system and ship
  /esi-query wallet ...... ISK balance
  /esi-query standings ... Faction reputation
  /esi-query blueprints .. BPO/BPC inventory

Detailed guide: docs/ESI.md
═══════════════════════════════════════════════════════════════════
```

### `/help experience` or `/help level`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Experience Level
───────────────────────────────────────────────────────────────────
Your experience level affects how I explain things.

LEVELS:
  new ............ Detailed explanations, define terms, extra warnings
  intermediate ... Moderate detail, explain advanced concepts
  veteran ........ Shorthand notation, assume game knowledge

CURRENT: Check your pilot profile → "EVE Experience" field

TO CHANGE:
Edit your pilot profile and set:
  - **EVE Experience:** new|intermediate|veteran

EXAMPLES:
  new:      "Security 0.5 (borderline dangerous) - CONCORD response
             is slow here, giving pirates time to attack..."
  veteran:  "Sec 0.5 | CONCORD delayed | gank viable"

If not set, I'll infer from context based on your questions.
═══════════════════════════════════════════════════════════════════
```

### `/help rp` or `/help roleplay`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Roleplay Mode
───────────────────────────────────────────────────────────────────
Roleplay is OFF by default. ARIA provides EVE knowledge without
persona, formatted boxes, or in-universe framing.

TO ENABLE RP:
Edit your pilot profile and set:
  - **RP Level:** [level]

LEVELS:
  off ......... Just the facts (default)
  lite ........ EVE terminology, no persona
  moderate .... Light flavor, formatted reports, "pilot" address
  full ........ Maximum immersion, faction AI persona, "capsuleer"

CURRENT: Check your pilot profile → "RP Level" field

WHY OPT-IN?
The RP system is polished and complete - faction personas,
formatted intel reports, in-universe framing. It's there for
pilots who want immersion. But most users just want answers.

If RP is enabled at 'full' or 'moderate':
  "ARIA, drop RP" ... temporarily disable roleplay
  "ARIA, resume" .... re-enable roleplay
═══════════════════════════════════════════════════════════════════
```

### `/help faction` or `/help persona`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Faction Personas (RP Mode Only)
───────────────────────────────────────────────────────────────────
Faction personas only apply when rp_level is 'moderate' or 'full'.
At 'off' or 'lite', faction choice doesn't affect communication.

AVAILABLE PERSONAS (when RP enabled):
  GALLENTE ... ARIA Mk.IV (libertarian, witty, cultured)
  CALDARI .... AURA-C (corporate, efficient, formal)
  MINMATAR ... VIND (direct, passionate, tribal)
  AMARR ...... THRONE (reverent, dignified, imperial)

CURRENT: Check your pilot profile → "Primary Faction" field

TO SWITCH FACTIONS:
1. Edit your pilot profile
2. Change: - **Primary Faction:** [NEW FACTION]
3. Optionally update Mission Provider, Hostile Factions
4. Restart session (exit and run 'claude' again)

NOTE: To experience faction personas, set rp_level to 'moderate'
or 'full'. See /help rp for details.
═══════════════════════════════════════════════════════════════════
```

### `/help setup` or `/help configure`
```
═══════════════════════════════════════════════════════════════════
ARIA HELP: Profile Setup
───────────────────────────────────────────────────────────────────
Command: /setup

Guides you through initial profile configuration via conversation.
No file editing required - just answer a few questions.

WHAT I'LL ASK:
  1. Your character name (or callsign)
  2. Your faction alignment (determines my personality)
  3. Your EVE experience level (determines explanation depth)
  4. Optionally: corporation, primary activities

WHEN TO USE:
  • First time running ARIA
  • After clearing your profile
  • Anytime you want to reconfigure

TRIGGERS: "/setup", "configure ARIA", "set up my profile"

After setup, your profile is saved to the appropriate location.
You can always edit this file directly for fine-tuning.
═══════════════════════════════════════════════════════════════════
```

## Quick Start Guidance

### For New Capsuleers

When help request suggests unfamiliarity, offer the quick start:

```
═══════════════════════════════════════════════════════════════════
ARIA QUICK START
───────────────────────────────────────────────────────────────────
Welcome aboard, Capsuleer. Here's how I can assist:

1. BEFORE MISSIONS: "/mission-brief" for enemy intel
2. FITTING HELP: "fit my [ship name]" for recommendations
3. MINING: "/mining-advisory" for ore guidance
4. EXPLORATION: Tell me the site name for analysis
5. SAFETY CHECK: "is [system] safe" for threat assessment

Your pilot profile and ship roster are in your data files.
Use /aria-status for a summary, or ask me about specific data.

Full command list: /help
Reference database: /help data

What operation are you preparing for?
═══════════════════════════════════════════════════════════════════
```

## Show Database Index

When capsuleer says "show database", "data index", or similar:

Read and display a summary of `reference/INDEX.md`, highlighting:
- Quick Access table
- Directory structure overview
- How to request specific reference files

## Behavior Notes

- **Brevity:** Default `/help` should fit on one screen (~25 lines)
- **Progressive Disclosure:** Offer `/help <topic>` for deeper dives
- **Persona:** Maintain ARIA voice - professional, helpful, slightly warm
- **Contextual Suggestions:** If capsuleer asks about an activity, mention the relevant command
  - Discussing missions? "For tactical intel, try /mission-brief"
  - Planning travel? "Use /threat-assessment for security analysis"
- **New Player Detection:** If questions suggest new player, offer Quick Start
- **Natural Language Reminder:** Always note that natural phrasing works too

## Cross-References

| If discussing... | Suggest... |
|------------------|------------|
| Pilot identity/profile | `/pilot` |
| Missions | `/mission-brief`, `/journal mission` |
| Exploration | `/exploration`, `/journal exploration` |
| Mining | `/mining-advisory` |
| Fitting | `/fitting` |
| Travel/Routes | `/route` |
| Safety/Security | `/threat-assessment` |
| Market/Prices | `/price` |
| ISK flow/finances | `/wallet-journal` |
| Skill training/queue | `/skillqueue` |
| Manufacturing/research | `/industry-jobs` |
| Current location/ship | `/esi-query` |
| Overall status | `/aria-status` |
| Corporation | `/corp` |
| Looking up another pilot | `/pilot <name>` |

## Error Handling

### Unknown Topic
```
═══════════════════════════════════════════════════════════════════
ARIA HELP
───────────────────────────────────────────────────────────────────
Topic "[input]" not recognized.

Available topics:
  pilot, aria-status, skillqueue, industry-jobs, route, price,
  wallet-journal, rp, missions, fitting, mining, exploration, threat,
  journal, data, esi, experience, faction, setup, corp

Full command list: /help
═══════════════════════════════════════════════════════════════════
```
