# External Data Sources

**Purpose:** Document authoritative sources for EVE game data that is NOT available in machine-readable formats (SDE, ESI).

## The Gap

The SDE and ESI provide authoritative data for many game elements, but some mechanics exist only as game logic:

| Data Type | In SDE? | In ESI? | Source |
|-----------|---------|---------|--------|
| Item stats, descriptions | Yes | - | `sde_item_info` |
| Blueprint materials | Yes | - | `sde_blueprint_info` |
| Skill attributes | Yes | - | `sde_skill_requirements` |
| NPC agent locations | Yes | - | `sde_agent_search` |
| Market prices | - | Yes | `market_prices` |
| Agent standing requirements | **No** | **No** | Game logic |
| Mission reward formulas | **No** | **No** | Game logic |
| RP generation formulas | **No** | **No** | Game logic |
| Security status penalties | **No** | **No** | Game logic |

For data not in SDE/ESI, we rely on community-documented sources.

## Blessed External Sources

These sources are considered authoritative for non-SDE game mechanics:

| Priority | Source | URL | Strengths | Weaknesses |
|----------|--------|-----|-----------|------------|
| 1 | **EVE University Wiki** | https://wiki.eveuniversity.org | Well-maintained, community-verified, detailed | Can lag behind patches |
| 2 | **DOTLAN EveMaps** | https://evemaps.dotlan.net | Map data, NPC corp info, station details | Reference only, no mechanics explanations |
| 3 | **Backstage Lore Wiki** | https://wiki.eve-inspiracy.com | Lore-focused, stable mechanics | Less frequently updated |
| 4 | **Official EVE Support** | https://support.eveonline.com | CCP-authored | Often high-level, not detailed |
| 5 | **EVE Forums** | https://forums.eveonline.com | Developer responses, current discussions | Signal-to-noise ratio |

### NPC Agent Lookups (SDE - Preferred)

**Agent data is now in SDE.** Use MCP tools for agent queries:

```python
# Find agents by corporation, level, division
sde_agent_search(corporation="Sisters of EVE", level=2, division="Security")
sde_agent_search(corporation="Caldari Navy", level=4, highsec_only=True)

# List all division types
sde_agent_divisions()
```

**Available filters:**
- `corporation`: Corporation name (fuzzy matched)
- `level`: Agent level (1-5)
- `division`: Division name (Security, Distribution, Mining, Research)
- `system`: Solar system name
- `highsec_only`: Only return agents in highsec (>=0.45)

### Agent Query Workflows

**1. Find nearest L[N] agent for [Corporation]**
```
sde_agent_search(corporation, level, division) → universe_route for distances → Sort by jumps
```
Example: "Find nearest L2 SOE security agent to Sortet"

**2. Find R&D agents for [Corporation]**
```
sde_agent_search(corporation, division="Research") → Include level for standing check
→ Cross-reference with pilot standings via ESI if available
```
Example: "Which SOE agents can I use for research point generation?"

**3. Find high-sec agents for [Corporation]**
```
sde_agent_search(corporation, highsec_only=True) → Group by level
```
Example: "Show me SOE agents in high-sec only"

**4. Find agents in [System] for [Corporation]**
```
sde_agent_search(corporation, system="Arnon")
```
Example: "What Federation Navy agents are in Arnon?"

**5. Standing requirements for L[N] agents**
```
Standing requirements are game logic constants (NOT in SDE).
Reference directly without fetching:
  L1 = None required
  L2 = 1.0 standing
  L3 = 3.0 standing
  L4 = 5.0 standing
  L5 = 7.0 standing
Source: https://wiki.eveuniversity.org/Agent
```

### DOTLAN Useful Endpoints (Fallback)

Use DOTLAN when SDE is unavailable or for supplemental data:

| Endpoint | Use Case | Example |
|----------|----------|---------|
| `/npc/` | List all NPC factions/corps | Browse faction hierarchy |
| `/npc/{corp}/agents` | Agent locations (fallback) | `/npc/Sisters_of_EVE/agents` |
| `/station/{name}` | Station details | `/station/Arnon_IX_-_Moon_3_-_Sisters_of_EVE_Bureau` |
| `/system/{name}` | System info and stations | `/system/Vivanier` |

**Note:** Corporation names use underscores for spaces (e.g., `Sisters_of_EVE`, `Caldari_Navy`).

## Source Annotation Format

When adding non-SDE data to project files, use this comment format:

```yaml
# Source: <URL>
# Verified: <YYYY-MM>
# Notes: <optional context>
- "Standing requirements: L1=any, L2=1.0, L3=3.0, L4=5.0"
```

Example:
```yaml
notes:
  # Source: https://wiki.eveuniversity.org/Agent
  # Verified: 2026-01
  # Notes: Not in SDE - standings are game logic based on agent level
  - "Standing requirements: L1=any, L2=1.0, L3=3.0, L4=5.0"
```

## Non-SDE Data Registry

This table tracks all manually-maintained game mechanics data in the project:

| Data Point | File Location | Primary Source | Last Verified |
|------------|---------------|----------------|---------------|
| Agent standing requirements | `reference/activities/skill_plans.yaml` | [EVE Uni - Agent](https://wiki.eveuniversity.org/Agent) | 2026-01 |
| R&D RP formula | `reference/activities/skill_plans.yaml` | [EVE Uni - Datacore farming](https://wiki.eveuniversity.org/Datacore_farming) | - |
| Mission standing gains | - | [EVE Uni - Missions](https://wiki.eveuniversity.org/Missions) | - |

**Note:** NPC agent locations are now in SDE via `sde_agent_search`. DOTLAN is no longer the primary source.

## Verification Procedures

### When to Verify

Check external sources against blessed sources:

1. **After major expansions** - CCP sometimes changes mechanics
2. **When users report discrepancies** - Community testing catches issues
3. **Before adding new non-SDE data** - Always cite source on first entry

### How to Verify

1. **Fetch the source page:**
   ```
   WebFetch(url, "Extract [specific data point]")
   ```

2. **Cross-reference if possible:**
   - Check multiple blessed sources
   - Search EVE Forums for recent discussions
   - Test in-game if feasible

3. **Update with annotation:**
   ```yaml
   # Source: <URL>
   # Verified: <YYYY-MM>
   - "The verified data"
   ```

### Verification Checklist

Before committing non-SDE data changes:

- [ ] Data comes from a blessed source (Priority 1-3)
- [ ] Source URL is included in comment
- [ ] Verification date is included
- [ ] Registry table above is updated
- [ ] Cross-referenced with at least one other source if critical

## Known Gaps

Data we know is NOT in SDE that we should track:

| Mechanic | Status | Notes |
|----------|--------|-------|
| Agent standing thresholds | Documented | `skill_plans.yaml` |
| Storyline mission triggers | Not documented | Every 16 missions of same faction |
| Derived standing formulas | Not documented | Complex, faction-dependent |
| CONCORD response times | Not documented | Security-dependent |
| Wormhole spawn rates | Not documented | Community-estimated |

## Relationship to DATA_VERIFICATION.md

- **DATA_VERIFICATION.md** - How to verify claims using tools (SDE, EOS, ESI)
- **DATA_SOURCES.md** (this file) - Where to find data that isn't in those tools

Both documents support the core principle:

> **Never present EVE game mechanics as fact without verification from a trusted source.**

## Future: Automated Verification

A potential `verify-sources` command could:

1. Fetch each URL in the registry
2. Extract known data patterns
3. Compare against stored values
4. Flag discrepancies for review

This is not currently implemented but the annotation format supports it.
