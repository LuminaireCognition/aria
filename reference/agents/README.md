# Agent Reference Data

This directory contains verified agent data for EVE Online NPC corporations. The primary use case is finding mission agents by corporation, level, and division (Security, Distribution, Mining).

## SDE Agent Import (Preferred)

Agent data is now imported from the EVE SDE. After running `uv run aria-esi sde-seed`, you can query agents using MCP tools:

```
sde_agent_search(corporation="Sisters of EVE", level=2, division="Security")
sde_agent_search(corporation="Caldari Navy", level=4, highsec_only=True)
sde_agent_divisions()  # List all division types
```

The SDE import includes:
- `agents` table: Agent name, level, division, corporation, station, system
- `agent_divisions` table: Division ID to name mapping (Security, Distribution, Mining, etc.)
- `agent_types` table: Agent type classification (BasicAgent, ResearchAgent, StorylineMissionAgent)

## Local Reference Files (Deprecated)

With the SDE agent import now complete, local JSON reference files are **no longer needed**.
The `sde_agent_search` MCP tool provides complete, authoritative data including:
- All agents with correct division information
- Level, corporation, station, system, and security data
- Efficient filtering by any combination of criteria

Legacy JSON files have been retired. Use `sde_agent_search` for all agent queries.

## SDE Agent Data

The `sde_agent_search` tool returns agent records with these fields:

| Field | Description |
|-------|-------------|
| `agent_id` | Unique agent identifier |
| `agent_name` | Agent's name |
| `level` | Agent level (1-5) |
| `division_id` | Division type ID |
| `division_name` | Division name (Security, Distribution, Mining, Research, etc.) |
| `corporation_id` | NPC corporation ID |
| `corporation_name` | NPC corporation name |
| `station_id` | Station ID where agent is located |
| `station_name` | Full station name |
| `system_id` | Solar system ID |
| `system_name` | Solar system name |
| `security` | System security status |
| `region_name` | Region name |
| `agent_type` | Agent type (BasicAgent, ResearchAgent, etc.) |

## Division Types

| Division | Description | Connection Skill |
|----------|-------------|------------------|
| `security` | Combat missions (kill NPCs) | Security Connections |
| `distribution` | Hauling/courier missions | Distribution Connections |
| `mining` | Mining missions | Mining Connections |
| `research` | R&D agents for datacores | Research Project Management |
| `epic_arc` | Epic arc starting agents | N/A |
| `event` | Event mission agents | N/A |
| `storyline` | Triggered after 16 missions | N/A |
| `unknown` | Needs in-game verification | N/A |

## Faction Coverage

All factions are now covered by the SDE import. Use `sde_agent_search` to query any corporation.

### Example Queries

```python
# Sisters of EVE agents
sde_agent_search(corporation="Sisters of EVE", level=2, division="Security")

# Caldari Navy L4 highsec agents
sde_agent_search(corporation="Caldari Navy", level=4, highsec_only=True)

# All R&D agents for CreoDron
sde_agent_search(corporation="CreoDron", division="Research")
```

### Pirate & Independent Factions (Reference)

These are high-priority factions commonly used for LP farming and epic arcs.

| Corporation | SDE Status | Notes |
|-------------|------------|-------|
| Sisters of EVE | ✅ Complete | Use `sde_agent_search` |
| The Sanctuary | ✅ Complete | SOE subsidiary |
| Food Relief | ✅ Complete | SOE subsidiary |
| Thukker Mix | ✅ Complete | Thukker Tribe |
| Mordu's Legion | ✅ Complete | Independent |
| Outer Ring Excavations | ✅ Complete | ORE |
| Serpentis Corporation | ✅ Complete | Pirate (lowsec only) |
| Guristas | ✅ Complete | Pirate (nullsec only) |

### Empire Factions

All empire faction corporations are covered by the SDE import:

| Faction | Example Corporations | SDE Status |
|---------|---------------------|------------|
| Caldari State | Caldari Navy, Ishukone, Lai Dai | ✅ Complete |
| Gallente Federation | Federation Navy, CreoDron, Duvolle Labs | ✅ Complete |
| Amarr Empire | Amarr Navy, Ministry of War, Kador Family | ✅ Complete |
| Minmatar Republic | Republic Fleet, Brutor Tribe, Boundless Creation | ✅ Complete |
| Ammatar Mandate | Ammatar Fleet, Ammatar Consulate | ✅ Complete |

## SDE Import Status

**Agent import is now implemented.** After running `uv run aria-esi sde-seed`, the following tables are populated:

| Table | Source | Contents |
|-------|--------|----------|
| `agents` | `agtAgents` | All NPC agents with level, division, corporation, location |
| `agent_divisions` | `crpNPCDivisions` | Division ID to name mapping |
| `agent_types` | `agtAgentTypes` | Agent type classification |

### MCP Tools

| Tool | Description |
|------|-------------|
| `sde_agent_search` | Search agents by corporation, level, division, highsec filter |
| `sde_agent_divisions` | List all available divisions |

### Manual Verification

For agents not in SDE or to verify specific data:

1. **In-game Agent Finder** (The Agency > Agents & Missions) - Filter by corporation, level, and division
2. **Show Info on agents** - Division shown in agent details

## Manual Verification

For agents not behaving as expected or to verify specific data:

1. **In-game Agent Finder** (The Agency > Agents & Missions) - Filter by corporation, level, and division
2. **Show Info on agents** - Division shown in agent details
3. **Report discrepancies** - If SDE data doesn't match in-game, the SDE importer may need updating
