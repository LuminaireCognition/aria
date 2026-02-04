# Site Composition Data Sources

This document links to the research that backs the site composition data.

## Primary Research Documents

### Special Spawn Sites Inventory

**Path:** `dev/mechanics/EveOnlineSpecialSpawnSitesInventory.md`

Comprehensive research document covering:
- Mining anomalies (EBRA, A0 sites)
- Gas sites (Mykoserocin, Cytoserocin)
- Special NPCs (Clone Soldiers, Mordu's Legion)
- Combat sites (Besieged Facilities)
- Nullsec mechanics (True Sec, Officer spawns)

**Citations:** 45 sources
**Last Updated:** 2026-01-19

### Gas Regional Data Inquiry

**Path:** `dev/mechanics/EVEOnlineGasRegionalDataInquiry.md`

Supplementary research for gas site regional distribution:
- Azure Mykoserocin regional data
- Vermillion Mykoserocin regional data
- Mission-only gas clarifications (Chartreuse, Gamboge)

**Citations:** 12 sources
**Last Updated:** 2026-01-19

## External Sources

### EVE University Wiki

Primary community reference for EVE mechanics.

| Topic | URL |
|-------|-----|
| Asteroids and Ore | https://wiki.eveuniversity.org/Asteroids_and_ore |
| Empire Border Rare Asteroids | https://wiki.eveuniversity.org/Empire_Border_Rare_Asteroids |
| W-Space Blue A0 Rare Asteroids | http://wiki.eveuniversity.org/W-Space_Blue_A0_Rare_Asteroids |
| Nullsec Blue A0 Rare Asteroids | https://wiki.eveuniversity.org/Nullsec_Blue_A0_Rare_Asteroids |
| Gas Cloud Harvesting | https://wiki.eveuniversity.org/Gas_cloud_harvesting |
| Security Tags | https://wiki.eveuniversity.org/Security_tags |
| Besieged Covert Research Facility | https://wiki.eveuniversity.org/Besieged_Covert_Research_Facility |

### Official CCP Sources

| Topic | URL |
|-------|-----|
| Catalyst Expansion Notes | https://www.eveonline.com/news/view/catalyst-expansion-notes |
| Patch Notes Archive | https://www.eveonline.com/news/patch-notes |

### Community Resources

| Topic | URL |
|-------|-----|
| Gas Mining Guide | https://www.wckg.net/PVE/gas-mining |
| Mordu's Legion Spawns | https://www.reddit.com/r/Eve/comments/xq4mqt/ |
| Officer Spawn Mechanics | https://forums.eveonline.com/t/officer-spawns/116571 |

## Source Reliability Tiers

| Tier | Source Type | Trust Level |
|------|-------------|-------------|
| 1 | CCP Patch Notes | Authoritative |
| 2 | EVE University Wiki | High (community-maintained) |
| 3 | Hoboleaks SDE | High (auto-updated) |
| 4 | EVE Forums (Dev posts) | Authoritative but scattered |
| 5 | Reddit/Community | Variable (needs verification) |
| 6 | In-game observation | Ground truth (manual) |

## SDE Validation

All `type_id` values in `site-compositions.yaml` have been cross-referenced against the Static Data Export using the `sde_search` MCP tool.

Last validated: 2026-01-19

## Maintenance Notes

When updating site composition data:

1. Check EVE University Wiki for recent edits
2. Review patch notes for relevant changes
3. Verify in-game if sources conflict
4. Update `accessed` dates in source entries
5. Run `uv run aria-esi validate-sites` to check staleness
