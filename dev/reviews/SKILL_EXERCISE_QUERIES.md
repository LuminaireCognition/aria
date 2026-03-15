# ARIA Skill Exercise Queries

A comprehensive catalog of natural language queries designed to exercise each ARIA skill. If every query in this document were issued, every skill would be exercised for at least the obvious 80% of expected real-world use cases.

## ESI Flag Key

| Flag | Meaning | Criteria |
|------|---------|----------|
| `NONE` | No ESI calls | Skill uses no ESI scopes |
| `LOW` | Light ESI usage | 1 ESI scope |
| `MED` | Moderate ESI usage | 2-3 ESI scopes |
| `HEAVY` | Heavy ESI usage | 4+ ESI scopes |
| `UKN` | Unknown | ESI usage unclear or conditional |

---

## System

### help
- **ESI:** NONE
- **Queries:**
  1. "What can you do?"
  2. "Help with fitting"

### first-run-setup
- **ESI:** NONE
- **Queries:**
  1. "Set up my profile"

### esi-query
- **ESI:** HEAVY
- **Queries:**
  1. "Where am I right now and what ship am I flying?"
  2. "What's my wallet balance?"
  3. "Refresh my standings and blueprint library from ESI"

---

## Identity

### aria-status
- **ESI:** NONE
- **Queries:**
  1. "Give me a status report"

### pilot
- **ESI:** MED
- **Queries:**
  1. "Show my pilot profile"
  2. "Who is Chribba?"

### corp
- **ESI:** HEAVY
- **Queries:**
  1. "Show me the corp dashboard with wallet, assets, and industry jobs"
  2. "What blueprints does the corp own?"
  3. "Look up the corporation Brave Newbies Inc"

### standings
- **ESI:** MED
- **Queries:**
  1. "Can I use L4 agents with Federation Navy?"
  2. "How do I raise my Caldari State standing to 5.0?"
  3. "How do I repair my negative Amarr standing?"

### sec-status *(persona-exclusive: paria)*
- **ESI:** LOW
- **Queries:**
  1. "What's my sec status and how much would tags cost to get back to -2.0 for full high-sec access?"

---

## Tactical

### abyssal
- **ESI:** NONE
- **Queries:**
  1. "What weather type should I use for a Gila in Tier 4 abyssal?"
  2. "What NPCs will I face in Electrical T3 abyssal sites?"
  3. "How should I fit a Stormbringer for abyssal deadspace?"

### clones
- **ESI:** MED
- **Queries:**
  1. "Where is my medical clone and what implants will I lose if I get podded?"
  2. "Can I jump clone right now or am I on cooldown?"

### escape-route *(persona-exclusive: paria)*
- **ESI:** LOW
- **Queries:**
  1. "I need an escape route from Tama, my sec status is -4.2"
  2. "Find the nearest NPC null station from Amamake"

### fitting
- **ESI:** NONE
- **Queries:**
  1. "Fit my Vexor for L2 security missions against Serpentis"
  2. "Export my Drake ratting fit in EFT format"

### fitting
- **ESI:** LOW
- **Queries:**
  3. "Export my Drake ratting fit in EFT format"

### fit-check
- **ESI:** MED
- **Queries:**
  1. "Can I fly this fit and afford it? [Vexor, L2 Mission Runner]\nDrone Damage Amplifier II\nDrone Damage Amplifier II\nDrone Damage Amplifier II\nMedium Armor Repairer II\nMultispectrum Energized Membrane II\n\n10MN Afterburner II\nCap Recharger II\nCap Recharger II\nLarge Cap Battery II\n\nDrone Link Augmentor I\n\nMedium Auxiliary Nano Pump I\nMedium Auxiliary Nano Pump I\nMedium Nanobot Accelerator I\n\nHammerhead II x5\nHobgoblin II x5"

### fit-budget
- **ESI:** MED
- **Queries:**
  1. "Make this fit cheaper: [Vexor, L3 Runner]\nDrone Damage Amplifier II\nDrone Damage Amplifier II\nDrone Damage Amplifier II\nMedium Armor Repairer II\nMultispectrum Energized Membrane II\n\n10MN Afterburner II\nCap Recharger II\nCap Recharger II\nLarge Cap Battery II\n\nDrone Link Augmentor I\n\nMedium Auxiliary Nano Pump I\nMedium Auxiliary Nano Pump I\nMedium Nanobot Accelerator I\n\nHammerhead II x5\nHobgoblin II x5"
  2. "Budget version of this fit with a 20M ISK target"

### gatecamp
- **ESI:** NONE
- **Queries:**
  1. "Is there a gatecamp in Niarja?"
  2. "Check for camps on the route from Jita to Amarr"

### hunting-grounds *(persona-exclusive: paria)*
- **ESI:** NONE
- **Queries:**
  1. "Where should I hunt near Tama?"
  2. "Analyze the hunting grounds in Rancer"
  3. "Show me hunting viability for Imperium renter space"

### killmail
- **ESI:** NONE
- **Queries:**
  1. "Analyze this killmail: https://zkillboard.com/kill/133484996/"

### killmails
- **ESI:** LOW
- **Queries:**
  1. "Show my recent losses"
  2. "Analyze my loss patterns over the last 90 days"
  3. "Show my recent kills from the last 24 hours"

### mark-assessment *(persona-exclusive: paria)*
- **ESI:** NONE
- **Queries:**
  1. "Assess a Retriever as a gank target in a 0.5 system"
  2. "Should I engage a Bestower in low-sec?"

### mission-brief
- **ESI:** NONE
- **Queries:**
  1. "Mission brief for The Blockade L4 against Serpentis"
  2. "Prepare for Gone Berserk level 3"

### orient
- **ESI:** NONE
- **Queries:**
  1. "I just jumped out of a wormhole into 1DQ1-A, orient me"
  2. "What's around Tama within 10 jumps?"

### route
- **ESI:** NONE
- **Queries:**
  1. "Safest route from Dodixie to Jita avoiding Uedama"
  2. "Shortest route from Amarr to Hek"

### ship-next
- **ESI:** MED
- **Queries:**
  1. "What ship should I fly next for L3 missions as Gallente?"
  2. "I'm in a Vexor, what's the upgrade path?"

### skillplan
- **ESI:** LOW
- **Queries:**
  1. "What skills do I need for an Ishtar and how long will it take with Easy 80%?"
  2. "What's the skill plan for gas huffing?"
  3. "What skills do I need for a Prospect and gas mining?"

### skillqueue
- **ESI:** LOW
- **Queries:**
  1. "What am I currently training and when does my queue finish?"

### threat-assessment
- **ESI:** NONE
- **Queries:**
  1. "Is Tama safe right now?"
  2. "Threat assessment for the 1DQ1-A region"

### watchlist
- **ESI:** NONE
- **Queries:**
  1. "Add CODE. to my watchlist"
  2. "Sync my war targets and show all tracked entities"

---

## Financial

### arbitrage
- **ESI:** NONE
- **Queries:**
  1. "Find arbitrage opportunities for my Bustard with 60000 m3 cargo, sorted by hauling score, with volume history"
  2. "Show me high-margin station trading opportunities above 15% profit"

### assets
- **ESI:** LOW
- **Queries:**
  1. "Show me all my assets with market valuations"
  2. "What ships do I have and where are they?"
  3. "Run asset insights to find forgotten items I should consolidate"

### contracts
- **ESI:** LOW
- **Queries:**
  1. "Show me my active contracts"
  2. "What courier contracts do I have in progress and what's the collateral at risk?"
  3. "List all my contracts"

### find
- **ESI:** NONE
- **Queries:**
  1. "Where can I buy a Venture Blueprint near Dodixie?"
  2. "Find NPC-seeded Orca Blueprint near Jita"
  3. "Find Nanite Repair Paste within 10 jumps of Rens"

### isk-compare
- **ESI:** MED
- **Queries:**
  1. "What is the best way to make ISK with my current skills?"
  2. "Compare ISK per hour for low-risk activities only"

### lp-store
- **ESI:** LOW
- **Queries:**
  1. "How much LP do I have and what can I buy from the Federation Navy LP store?"

### orders
- **ESI:** LOW
- **Queries:**
  1. "Show my active market orders"

### price
- **ESI:** NONE
- **Queries:**
  1. "How much is a Vexor Navy Issue selling for in Jita?"
  2. "Compare PLEX prices across all trade hubs"

### ransom-calc *(persona-exclusive: paria)*
- **ESI:** NONE
- **Queries:**
  1. "How much ransom should I charge for a Mackinaw with a pod?"

### wallet-journal
- **ESI:** LOW
- **Queries:**
  1. "Show me my income breakdown for the last 7 days"

---

## Operations

### exploration
- **ESI:** NONE
- **Queries:**
  1. "I found a Ruined Serpentis Temple in Sinq Laison, what loot should I expect and how do I hack it?"
  2. "Give me hacking tips for data sites"

### fittings
- **ESI:** LOW
- **Queries:**
  1. "Show my saved fittings"
  2. "Export my saved Vexor fits in EFT format"

### journal
- **ESI:** NONE
- **Queries:**
  1. "Log mission Gone Berserk against Equilibrium of Mankind, success, standing +0.15"
  2. "Log exploration site Crumbling Serpentis Crystal Quarry, relic, Masalle 0.6, 3 containers hacked"

### mail
- **ESI:** LOW
- **Queries:**
  1. "Check my unread mail"

### mining
- **ESI:** LOW
- **Queries:**
  1. "Show my mining history for the last 7 days"

### mining-advisory
- **ESI:** NONE
- **Queries:**
  1. "What ore should I mine in Masalle for manufacturing?"

### pi
- **ESI:** NONE
- **Queries:**
  1. "How do I make Robotics in PI?"
  2. "What's the profit on Mechanical Parts with 5% POCO tax?"

---

## Industry

### agents-research
- **ESI:** LOW
- **Queries:**
  1. "Show me my research agents and accumulated RP"
  2. "Do I have enough standing to use Level 3 R&D agents at CreoDron?"

### build-cost
- **ESI:** NONE
- **Queries:**
  1. "What's the cost to build a Dominix at ME 10 in an Azbel in Perimeter?"
  2. "Is it profitable to build Hammerhead II with the Attainment decryptor?"
  3. "Show me the full build chain for an Ishtar to compare vertical integration vs buying components"

### industry-jobs
- **ESI:** LOW
- **Queries:**
  1. "What are my current industry jobs?"
  2. "Show completed manufacturing jobs ready for delivery"

### reactions
- **ESI:** NONE
- **Queries:**
  1. "What's the cost and profit for 100 runs of Nitrogen Fuel Blocks in a Tatara with Reactions IV?"
  2. "List all fuel block types"

---

## Summary

| # | Skill | Category | ESI | Query Count |
|---|-------|----------|-----|-------------|
| 1 | help | system | NONE | 2 |
| 2 | first-run-setup | system | NONE | 1 |
| 3 | esi-query | system | HEAVY | 3 |
| 4 | aria-status | identity | NONE | 1 |
| 5 | pilot | identity | MED | 2 |
| 6 | corp | identity | HEAVY | 3 |
| 7 | standings | identity | MED | 3 |
| 8 | sec-status | identity | LOW | 1 |
| 9 | abyssal | tactical | NONE | 3 |
| 10 | clones | tactical | MED | 2 |
| 11 | escape-route | tactical | LOW | 2 |
| 12 | fitting | tactical | NONE | 2 |
| 12b | fitting | tactical | LOW | 1 |
| 13 | fit-check | tactical | MED | 1 |
| 14 | fit-budget | tactical | MED | 2 |
| 15 | gatecamp | tactical | NONE | 2 |
| 16 | hunting-grounds | tactical | NONE | 3 |
| 17 | killmail | tactical | NONE | 1 |
| 18 | killmails | tactical | LOW | 2 |
| 19 | mark-assessment | tactical | NONE | 2 |
| 20 | mission-brief | tactical | NONE | 2 |
| 21 | orient | tactical | NONE | 2 |
| 22 | route | tactical | NONE | 2 |
| 23 | ship-next | tactical | MED | 2 |
| 24 | skillplan | tactical | LOW | 2 |
| 25 | skillqueue | tactical | LOW | 1 |
| 26 | threat-assessment | tactical | NONE | 2 |
| 27 | watchlist | tactical | NONE | 2 |
| 28 | arbitrage | financial | NONE | 2 |
| 29 | assets | financial | LOW | 3 |
| 30 | contracts | financial | LOW | 2 |
| 31 | find | financial | NONE | 3 |
| 32 | isk-compare | financial | MED | 2 |
| 33 | lp-store | financial | LOW | 1 |
| 34 | orders | financial | LOW | 1 |
| 35 | price | financial | NONE | 2 |
| 36 | ransom-calc | financial | NONE | 1 |
| 37 | wallet-journal | financial | LOW | 1 |
| 38 | exploration | operations | NONE | 2 |
| 39 | fittings | operations | LOW | 2 |
| 40 | journal | operations | NONE | 2 |
| 41 | mail | operations | LOW | 1 |
| 42 | mining | operations | LOW | 1 |
| 43 | mining-advisory | operations | NONE | 1 |
| 44 | pi | operations | NONE | 2 |
| 45 | agents-research | industry | LOW | 2 |
| 46 | build-cost | industry | NONE | 3 |
| 47 | industry-jobs | industry | LOW | 2 |
| 48 | reactions | industry | NONE | 2 |

**Totals:** 48 skills, 89 queries

**ESI distribution:** NONE: 24, LOW: 15, MED: 8, HEAVY: 2
