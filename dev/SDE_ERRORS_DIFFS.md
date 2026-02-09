# SDE Data Errors and Proposed Fixes

Generated: 2026-01-19
Validated against: Local SDE cache via MCP tools

## Summary

| File | Errors Found | Severity |
|------|--------------|----------|
| docs/NPC_BLUEPRINT_SOURCES.md | 8 critical errors | HIGH |
| All other files | 0 errors | - |

---

## File: docs/NPC_BLUEPRINT_SOURCES.md

### Error 1: ORE Corporation ID (Line 13)

**Documented:**
```markdown
| ORE | 1000115 | Outer Ring | 10000057 | Mining ships, equipment |
```

**SDE Actual:**
- `1000115` = "University of Caille" (Gallente education corp, Sinq Laison)
- ORE = `1000129` "Outer Ring Excavations"

**Proposed Fix:**
```diff
-| ORE | 1000115 | Outer Ring | 10000057 | Mining ships, equipment |
+| ORE | 1000129 | Outer Ring | 10000057 | Mining ships, equipment |
```

---

### Error 2: Angel Cartel Corporation ID (Line 16)

**Documented:**
```markdown
| Angel Cartel | 1000135 | Curse | 10000012 | Pirate faction |
```

**SDE Actual:**
- `1000135` = "Serpentis Corporation" (not Angel Cartel)
- Angel faction corporation = "Archangels" (`1000124`), primary region Curse

**Proposed Fix:**
```diff
-| Angel Cartel | 1000135 | Curse | 10000012 | Pirate faction |
+| Archangels | 1000124 | Curse | 10000012 | Angel Cartel faction |
```

---

### Error 3: Serpentis Corporation ID and Region (Line 20)

**Documented:**
```markdown
| Serpentis Corporation | 1000126 | Fountain | 10000058 | Pirate faction |
```

**SDE Actual:**
- `1000126` = "Ammatar Consulate" (Derelik)
- Serpentis Corporation = `1000135`
- Serpentis primary region = Curse (10000012), Fountain is secondary (3 stations)

**Proposed Fix:**
```diff
-| Serpentis Corporation | 1000126 | Fountain | 10000058 | Pirate faction |
+| Serpentis Corporation | 1000135 | Curse | 10000012 | Pirate faction |
```

---

### Error 4: Mordu's Legion Corporation ID (Line 21)

**Documented:**
```markdown
| Mordu's Legion | 1000140 | Pure Blind | 10000023 | Mordu's ships |
```

**SDE Actual:**
- `1000140` = "Genolution" (not Mordu's Legion)
- Mordu's Legion = `1000128`, primary region Pure Blind (correct region)

**Proposed Fix:**
```diff
-| Mordu's Legion | 1000140 | Pure Blind | 10000023 | Mordu's ships |
+| Mordu's Legion | 1000128 | Pure Blind | 10000023 | Mordu's ships |
```

---

### Error 5: Thukker Tribe Corporation ID and Region (Line 22)

**Documented:**
```markdown
| Thukker Tribe | 1000118 | Great Wildlands | 10000011 | Thukker items |
```

**SDE Actual:**
- `1000118` = "Supreme Court" (Gallente judicial corp, Essence)
- Thukker-related seeding corp = "Thukker Mix" (`1000160`)
- Thukker Mix primary region = Metropolis (10000042), Great Wildlands has only 2 stations

**Proposed Fix:**
```diff
-| Thukker Tribe | 1000118 | Great Wildlands | 10000011 | Thukker items |
+| Thukker Mix | 1000160 | Metropolis | 10000042 | Thukker items |
```

**Note:** Great Wildlands (10000011) is listed as a secondary region for Thukker Mix but has minimal station presence. May want to list both regions or clarify primary.

---

### Error 6: Intaki Syndicate Corporation ID (Line 23)

**Documented:**
```markdown
| Intaki Syndicate | 1000133 | Syndicate | 10000041 | Syndicate items |
```

**SDE Actual:**
- `1000133` = "Salvation Angels" (Angel Cartel affiliated, Curse)
- Intaki Syndicate = `1000147`, primary region Syndicate (correct region)

**Proposed Fix:**
```diff
-| Intaki Syndicate | 1000133 | Syndicate | 10000041 | Syndicate items |
+| Intaki Syndicate | 1000147 | Syndicate | 10000041 | Syndicate items |
```

---

## Clarifications (Not Errors, But Worth Noting)

### Sisters of EVE Primary Region (Line 14)

**Documented:**
```markdown
| Sisters of EVE | 1000130 | Syndicate | 10000041 | SOE ships, probes |
```

**SDE Actual:**
- Sisters of EVE (`1000130`) primary region by station count = Genesis (10000067) with 6 stations
- Syndicate (10000041) is NOT in their region list at all
- They have stations in: Genesis, Solitude, Metropolis, The Forge, Essence, Aridia, Placid, Domain, Everyshore, Heimatar, Pure Blind

**Assessment:** This appears to be a conceptual error. SOE ships may be commonly purchased in Syndicate through other means (player market, contracts), but they are NOT NPC-seeded there by Sisters of EVE corporation directly.

**Potential Fix:**
```diff
-| Sisters of EVE | 1000130 | Syndicate | 10000041 | SOE ships, probes |
+| Sisters of EVE | 1000130 | Genesis | 10000067 | SOE ships, probes (also: Solitude, Metropolis, The Forge) |
```

---

### CONCORD Primary Region (Line 15)

**Documented:**
```markdown
| CONCORD | 1000125 | The Forge | 10000002 | CONCORD modules |
```

**SDE Actual:**
- CONCORD (`1000125`) primary region = Metropolis (10000042) with 12 stations
- The Forge has 6 CONCORD stations (lower than primary)

**Assessment:** Not technically wrong since CONCORD does have presence in The Forge, but listing The Forge as primary is misleading.

**Optional Fix:**
```diff
-| CONCORD | 1000125 | The Forge | 10000002 | CONCORD modules |
+| CONCORD | 1000125 | Metropolis | 10000042 | CONCORD modules (also: The Forge, Genesis, Molden Heath) |
```

---

### Sansha's Nation Entry (Line 19)

**Documented:**
```markdown
| Sansha's Nation | 1000161 | Stain | 10000022 | Pirate faction |
```

**SDE Actual:**
- `1000161` = "True Creations" (Sansha-affiliated corp)
- This corporation does seed Sansha items in Stain
- There is no corporation named exactly "Sansha's Nation" in the SDE

**Assessment:** Functionally correct - True Creations is the NPC corp that seeds Sansha items. The name in docs is a faction name rather than corporation name, which may cause confusion when doing lookups.

**Optional Fix (for accuracy):**
```diff
-| Sansha's Nation | 1000161 | Stain | 10000022 | Pirate faction |
+| True Creations | 1000161 | Stain | 10000022 | Sansha's Nation faction |
```

---

## Complete Corrected Table

```markdown
| Corporation | Corp ID | Region | Region ID | Notes |
|-------------|---------|--------|-----------|-------|
| ORE | 1000129 | Outer Ring | 10000057 | Mining ships, equipment |
| Sisters of EVE | 1000130 | Genesis | 10000067 | SOE ships, probes |
| CONCORD | 1000125 | Metropolis | 10000042 | CONCORD modules |
| Archangels | 1000124 | Curse | 10000012 | Angel Cartel faction |
| Blood Raiders | 1000134 | Delve | 10000060 | Pirate faction |
| Guristas | 1000127 | Venal | 10000015 | Pirate faction |
| True Creations | 1000161 | Stain | 10000022 | Sansha's Nation faction |
| Serpentis Corporation | 1000135 | Curse | 10000012 | Pirate faction |
| Mordu's Legion | 1000128 | Pure Blind | 10000023 | Mordu's ships |
| Thukker Mix | 1000160 | Metropolis | 10000042 | Thukker items |
| Intaki Syndicate | 1000147 | Syndicate | 10000041 | Syndicate items |
```

---

## Files With No Errors Found

The following files were validated and contain correct SDE data:

| File | Data Validated |
|------|----------------|
| `src/aria_esi/core/constants.py` | Ship group IDs (25, 26, 27, etc.), category references |
| `src/aria_esi/models/sde.py` | ORE_CORPORATION_ID (1000129), category constants (6, 7, 8, 9, 16, 18, 25) |
| `tests/integration/test_sde_data_integrity.py` | Category IDs, corporation assertions |
| `tests/mcp/test_sde_queries.py` | Mock data (intentionally different from SDE) |
| `tests/test_constants.py` | Tests structure, not SDE values |
| `tests/test_market_clipboard.py` | Uses item names for parsing tests only |
| `reference/industry/manufacturing.md` | Game mechanics reference, no type IDs |
| `reference/industry/npc_blueprint_sources.md` | General guidance, no hardcoded IDs |

---

## Validation Method

Data was validated using the `aria-universe` MCP server tools:
- `sde_corporation_info` - Corporation ID and region lookups
- `sde_item_info` - Item type and category validation
- `sde_search` - Name-based lookups

All queries executed against locally seeded SDE data from Fuzzwork dump.
