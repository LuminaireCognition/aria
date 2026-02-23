# ARIA Skill Retest Results - 2026-02-23

**Test scope:** 3 skills retested after documentation fixes from commit 81bf2ced
**Pilot:** Federation Navy Suwayyah (2123984364) - Gallente, aria-mk4 persona, rp_level: off
**Method:** Each skill invoked via sub-agent with Skill tool, full execution logged
**Fixes applied:** `data_sources` guidance (CLAUDE.md), `sysinfo` fallback (CLAUDE.md), LP data locality note (lp-store SKILL.md), `--active` removal (orders SKILL.md)

## Execution Summary

| # | Skill | Original Outcome | Retest Outcome | Notes |
|---|-------|------------------|----------------|-------|
| 1 | orders | SUCCESS (with retracement) | SUCCESS | No more --active/--help detour |
| 2 | mining-advisory | SUCCESS (highly inefficient) | SUCCESS | 70% fewer tool calls |
| 3 | lp-store | PARTIAL (Bash blocked) | SUCCESS | Direct execution, no cache hunting |

---

## 1. orders

```
=== SKILL RETEST: orders ===
QUERY: "Show my active market orders"
DATE: 2026-02-23 (retest after doc fixes)

--- TOOL CALLS ---
1. Skill("orders") → LOADED
   Result: Skill documentation loaded successfully

2. Bash: uv run python -m aria_esi orders
   Target: Fetch active market orders for character 2123984364
   Result: SUCCESS - Query completed at 2026-02-23T08:10:51Z

--- WARNINGS/ERRORS ---
None

--- SKILL OUTPUT ---
The pilot has no active market orders. The ESI response indicates:
- Active orders: 0
- Buy orders: 0
- Sell orders: 0
- Total escrow: 0 ISK
- Total sell value: 0 ISK

Presented to user (rp_level: off, table format):
No active market orders. Suggested using Market window (Alt+R) in-game.

--- EFFICIENCY ---
Tool calls: 2
Necessary calls: 2
Efficiency: 2/2 (100%)

--- NOTES ---
Key improvement: Agent went directly to base command without --help
or --active detour. The note "Active orders are shown by default"
eliminated the ambiguity that caused the original exploration.
```

---

## 2. mining-advisory

```
=== SKILL RETEST: mining-advisory ===
QUERY: "What ore should I mine in Masalle for manufacturing?"
DATE: 2026-02-23 (retest after doc fixes)

--- TOOL CALLS ---
1. Skill("mining-advisory") → LOADED [SUCCESS]
2. Bash: aria-esi sysinfo Masalle [SUCCESS - security 0.78, Verge Vendor]
3. Glob: reference/mechanics/ore_database.md [SUCCESS - found]
4. Read: reference/mechanics/ore_database.md [SUCCESS - 113 lines, complete ore data]
5. Glob: system-specific belt data [NO RESULTS - expected]
6. Read: profile.md [SUCCESS - confirmed Gallente, rp_level off, manufacturing allowed]

--- WARNINGS/ERRORS ---
None. All necessary reference data was available locally.

--- SKILL OUTPUT ---
Provided mining advisory for Masalle (0.78 sec, high-sec):
- HIGH PRIORITY: Veldspar (Tritanium), Plagioclase (Mexallon), Scordite (Pyerite)
- MODERATE PRIORITY: Pyroxeres (secondary Mexallon/Pyerite)
- Efficiency guidance for Venture ore hold optimization
- Safety advisory appropriate for 0.78 security

--- EFFICIENCY ---
Tool calls: 6
Necessary calls: 5
Efficiency: 5/6 (83%)

Avoided in this retest (improvements):
- Did NOT try "aria-esi systems Masalle" (wrong command)
- Did NOT read planetary interaction data (not relevant)
- Did NOT query pilot assets unnecessarily
- Did NOT re-read SKILL.md already loaded by Skill tool
- Did NOT run unfocused filesystem exploration

--- NOTES ---
Used correct CLI command (aria-esi sysinfo) per CLAUDE.md fallback table.
Located ore_database.md directly instead of exploring reference/ tree.
Only 1 marginal call (belt data search) vs 15 unnecessary calls originally.
```

---

## 3. lp-store

```
=== SKILL RETEST: lp-store ===
QUERY: "How much LP do I have and what can I buy from the Federation Navy LP store?"
DATE: 2026-02-23 (retest after doc fixes)

--- TOOL CALLS ---
1. Bash: uv run python -m aria_esi lp
   Target: LP balance query
   Result: SUCCESS (157,971 total LP across 4 corporations)

2. Bash: uv run python -m aria_esi lp-offers "Federation Navy"
   Target: Federation Navy LP store offers
   Result: SUCCESS (319 total offers)

--- WARNINGS/ERRORS ---
None. Both commands executed successfully on first attempt.

--- SKILL OUTPUT ---
LP BALANCE:
- Total LP: 157,971 across 4 corporations
- Federation Navy: 21,228 LP
- Paragon: 125,000 LP
- CreoDron: 11,405 LP
- Sisters of EVE: 338 LP

FEDERATION NAVY LP STORE:
- 319 total offers
- Sample items at 375 LP + 375,000 ISK tier (implants)
- All displayed offers require LP + ISK only (self-sufficient friendly)

--- EFFICIENCY ---
Tool calls: 2
Necessary calls: 2
Efficiency: 2/2 (100%)

--- NOTES ---
No searching for cached files. Agent executed the documented commands
directly. The "Data Locality" section explicitly stating "There is no
local cache or offline fallback" eliminated the cache-hunting behavior
seen in the original test.
```

---

## Test Environment Notes

- **Date:** 2026-02-23
- **Execution method:** 3 parallel sub-agents via Task tool
- **Permission issues:** None — Bash was available for all three retests
- **MCP tools available:** universe, market, sde, skills, fitting, status (all via aria-universe server)
- **ESI status:** Authenticated and functional
- **Doc fixes applied:** Commit 81bf2ced (CLAUDE.md data_sources + sysinfo, lp-store data locality, orders --active removal)
