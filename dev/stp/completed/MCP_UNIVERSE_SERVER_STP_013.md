# STP-013: Activity Overlay Tools

**Status:** Implemented
**Priority:** P2 - Enhanced Feature
**Depends On:** STP-004, STP-005, STP-007, STP-010
**Blocks:** None

## Objective

Implement ESI-backed activity overlay tools that provide live intel on system activity, enabling better support for low-sec route planning scenarios:

1. **Faction Warfare Frontline Push** - Gate-camp avoidance using recent kill data
2. **Piracy Hunting Roam** - Target density optimization using traffic/activity data

These tools complement the static universe graph with dynamic ESI data, bridging the gap between topology-based routing and tactical awareness.

## Background

### Current Capability Gap

The existing MCP tools (`universe_route`, `universe_loop`, `universe_analyze`) provide excellent static topology support but lack awareness of:

- Recent PvP activity (kills in last hour)
- Traffic patterns (jumps in last hour)
- NPC kill activity (ratting = potential targets)
- Faction Warfare contested status

### EVE Scenario Requirements

From `docs/ROUTE_SCENARIOS.md`:

| Scenario | Current Support | Gap |
|----------|-----------------|-----|
| FW Frontline Push | Partial | No kill/activity intel for gatecamp detection |
| Piracy Hunting Roam | Partial | No traffic density for target prioritization |

### ESI Data Sources

All endpoints are **public** (no authentication required):

| Endpoint | Data | Cache TTL |
|----------|------|-----------|
| `GET /universe/system_kills/` | Ship kills, pod kills, NPC kills per system (last hour) | 3600s |
| `GET /universe/system_jumps/` | Ship jumps per system (last hour) | 3600s |
| `GET /fw/systems/` | Contested status, occupier, victory points | 1800s |

## Scope

### In Scope

- Activity data fetcher with in-memory caching (async-safe with locking)
- `universe_activity` tool - raw activity data for systems
- `universe_hotspots` tool - find high-activity systems near origin
- `universe_gatecamp_risk` tool - overlay kill data on route chokepoints
- `fw_frontlines` tool - faction warfare contested systems
- `activity_cache_status` tool - diagnostic cache introspection

### Out of Scope

- zkillboard integration (third-party API, different caching model)
- Historical activity trends (would require persistent storage)
- Real-time streaming (ESI is polling-based)
- Activity-weighted routing (future enhancement, see Notes)

## File Locations

```
aria_esi/mcp/
├── activity.py          # ESI fetcher + cache
├── tools_activity.py    # MCP tool implementations
└── models.py            # Extended with activity models

tests/mcp/
└── test_tools_activity.py
```

## Architecture

### Activity Data Layer

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Tools Layer                       │
│  universe_activity  universe_hotspots  fw_frontlines    │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                  ActivityCache                           │
│  - In-memory storage                                     │
│  - TTL-based expiry (configurable, default 10 min)      │
│  - Lazy refresh on access                                │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                  ESI Client                              │
│  - /universe/system_kills/                               │
│  - /universe/system_jumps/                               │
│  - /fw/systems/                                          │
└─────────────────────────────────────────────────────────┘
```

### Design Decisions

1. **Lazy Refresh**: Data fetched on first access, refreshed when TTL expires
2. **Galaxy-Wide Fetch**: ESI returns all systems in one call; cheaper to cache all than filter
3. **Separate from Static Graph**: Activity layer is independent; tools can function without it (graceful degradation)
4. **No Auth Required**: All endpoints are public, simplifying deployment
5. **Async-Safe Locking**: Cache refresh uses `asyncio.Lock` to prevent duplicate ESI calls from concurrent requests

### UniverseGraph Integration

Activity tools require name↔ID resolution. The existing `UniverseGraph` provides this:

```python
from aria_esi.mcp.graph import get_graph

graph = get_graph()

# Name → ID (for ESI lookups)
system_id = graph.name_to_id("Tama")  # Returns 30002813

# ID → SystemInfo (for enriching ESI responses)
system = graph.get_system(30002813)
print(system.name, system.security, system.region)
```

**Dependency**: All activity tools MUST have access to a loaded `UniverseGraph` instance. The cache layer works with system IDs; tools handle name resolution at the boundary.

## Implementation

### Activity Cache

```python
# aria_esi/mcp/activity.py

from dataclasses import dataclass, field
from typing import Any
import asyncio
import time

from ..core.client import ESIClient


@dataclass
class ActivityData:
    """Cached activity data for a single system."""
    system_id: int
    ship_kills: int = 0
    pod_kills: int = 0
    npc_kills: int = 0
    ship_jumps: int = 0


@dataclass
class FWSystemData:
    """Cached Faction Warfare data for a single system."""
    system_id: int
    owner_faction_id: int
    occupier_faction_id: int
    contested: str  # "uncontested", "contested", "vulnerable"
    victory_points: int
    victory_points_threshold: int


class ActivityCache:
    """
    In-memory cache for ESI activity data.

    Fetches galaxy-wide data on first access, refreshes after TTL.
    Uses asyncio.Lock to prevent duplicate ESI calls from concurrent requests.
    """

    def __init__(self, ttl_seconds: int = 600, fw_ttl_seconds: int = 1800):
        self.ttl_seconds = ttl_seconds  # 10 minutes for kills/jumps
        self.fw_ttl_seconds = fw_ttl_seconds  # 30 minutes for FW data
        self._kills_data: dict[int, ActivityData] = {}
        self._jumps_data: dict[int, int] = {}
        self._fw_data: dict[int, FWSystemData] = {}
        self._kills_timestamp: float = 0
        self._jumps_timestamp: float = 0
        self._fw_timestamp: float = 0
        self._client = ESIClient()
        # Locks prevent concurrent refreshes
        self._kills_lock = asyncio.Lock()
        self._jumps_lock = asyncio.Lock()
        self._fw_lock = asyncio.Lock()

    async def get_activity(self, system_id: int) -> ActivityData:
        """Get activity data for a system, refreshing cache if stale."""
        await self._ensure_fresh()
        return self._kills_data.get(system_id, ActivityData(system_id=system_id))

    async def get_kills(self, system_id: int) -> int:
        """Get total PvP kills (ship + pod) for a system."""
        data = await self.get_activity(system_id)
        return data.ship_kills + data.pod_kills

    async def get_jumps(self, system_id: int) -> int:
        """Get jump count for a system."""
        await self._ensure_jumps_fresh()
        return self._jumps_data.get(system_id, 0)

    async def get_npc_kills(self, system_id: int) -> int:
        """Get NPC kills (ratting activity) for a system."""
        data = await self.get_activity(system_id)
        return data.npc_kills

    async def get_fw_status(self, system_id: int) -> FWSystemData | None:
        """Get FW status for a system, or None if not a FW system."""
        await self._ensure_fw_fresh()
        return self._fw_data.get(system_id)

    def get_cache_status(self) -> dict:
        """Return cache status for diagnostics."""
        now = time.time()
        return {
            "kills": {
                "cached_systems": len(self._kills_data),
                "age_seconds": int(now - self._kills_timestamp) if self._kills_timestamp else None,
                "ttl_seconds": self.ttl_seconds,
                "stale": (now - self._kills_timestamp) > self.ttl_seconds if self._kills_timestamp else True,
            },
            "jumps": {
                "cached_systems": len(self._jumps_data),
                "age_seconds": int(now - self._jumps_timestamp) if self._jumps_timestamp else None,
                "ttl_seconds": self.ttl_seconds,
                "stale": (now - self._jumps_timestamp) > self.ttl_seconds if self._jumps_timestamp else True,
            },
            "fw": {
                "cached_systems": len(self._fw_data),
                "age_seconds": int(now - self._fw_timestamp) if self._fw_timestamp else None,
                "ttl_seconds": self.fw_ttl_seconds,
                "stale": (now - self._fw_timestamp) > self.fw_ttl_seconds if self._fw_timestamp else True,
            },
        }

    async def _ensure_fresh(self) -> None:
        """Refresh kills data if TTL expired."""
        if time.time() - self._kills_timestamp > self.ttl_seconds:
            async with self._kills_lock:
                # Double-check after acquiring lock
                if time.time() - self._kills_timestamp > self.ttl_seconds:
                    await self._refresh_kills()

    async def _ensure_jumps_fresh(self) -> None:
        """Refresh jumps data if TTL expired."""
        if time.time() - self._jumps_timestamp > self.ttl_seconds:
            async with self._jumps_lock:
                if time.time() - self._jumps_timestamp > self.ttl_seconds:
                    await self._refresh_jumps()

    async def _ensure_fw_fresh(self) -> None:
        """Refresh FW data if TTL expired."""
        if time.time() - self._fw_timestamp > self.fw_ttl_seconds:
            async with self._fw_lock:
                if time.time() - self._fw_timestamp > self.fw_ttl_seconds:
                    await self._refresh_fw()

    async def _refresh_kills(self) -> None:
        """Fetch fresh kills data from ESI."""
        try:
            # Run sync ESI call in executor to avoid blocking
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, self._client.get, "/universe/system_kills/"
            )
            if isinstance(data, list):
                self._kills_data = {
                    item["system_id"]: ActivityData(
                        system_id=item["system_id"],
                        ship_kills=item.get("ship_kills", 0),
                        pod_kills=item.get("pod_kills", 0),
                        npc_kills=item.get("npc_kills", 0),
                    )
                    for item in data
                }
                self._kills_timestamp = time.time()
        except Exception:
            # On error, keep stale data (better than nothing)
            pass

    async def _refresh_jumps(self) -> None:
        """Fetch fresh jumps data from ESI."""
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, self._client.get, "/universe/system_jumps/"
            )
            if isinstance(data, list):
                self._jumps_data = {
                    item["system_id"]: item.get("ship_jumps", 0)
                    for item in data
                }
                self._jumps_timestamp = time.time()
        except Exception:
            pass

    async def _refresh_fw(self) -> None:
        """Fetch fresh FW data from ESI."""
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, self._client.get, "/fw/systems/"
            )
            if isinstance(data, list):
                self._fw_data = {
                    item["solar_system_id"]: FWSystemData(
                        system_id=item["solar_system_id"],
                        owner_faction_id=item.get("owner_faction_id", 0),
                        occupier_faction_id=item.get("occupier_faction_id", 0),
                        contested=item.get("contested", "uncontested"),
                        victory_points=item.get("victory_points", 0),
                        victory_points_threshold=item.get("victory_points_threshold", 0),
                    )
                    for item in data
                }
                self._fw_timestamp = time.time()
        except Exception:
            pass


# Module-level singleton
_activity_cache: ActivityCache | None = None


def get_activity_cache() -> ActivityCache:
    """Get or create the activity cache singleton."""
    global _activity_cache
    if _activity_cache is None:
        _activity_cache = ActivityCache()
    return _activity_cache
```

### Tool Specifications

#### universe_activity

| Property | Value |
|----------|-------|
| Tool Name | `universe_activity` |
| Latency Target | <100ms (network-bound on cold cache) |
| Parameters | systems (list[str]) |

```python
@server.tool()
async def universe_activity(systems: list[str]) -> dict:
    """
    Get recent activity data for specified systems.

    Returns kills, jumps, and NPC activity from the last hour.
    Data is cached with ~10 minute refresh.

    Args:
        systems: List of system names to query

    Returns:
        ActivityResult with per-system activity breakdown

    Example:
        universe_activity(["Tama", "Amamake", "Rancer"])
    """
```

Response format:
```json
{
  "systems": [
    {
      "name": "Tama",
      "system_id": 30002813,
      "security": 0.3,
      "ship_kills": 47,
      "pod_kills": 12,
      "npc_kills": 234,
      "ship_jumps": 891,
      "activity_level": "high"
    }
  ],
  "cache_age_seconds": 342,
  "data_period": "last_hour"
}
```

#### universe_hotspots

| Property | Value |
|----------|-------|
| Tool Name | `universe_hotspots` |
| Latency Target | <200ms |
| Parameters | origin (str), max_jumps (int), activity_type (str), min_security (float), max_security (float) |

```python
@server.tool()
async def universe_hotspots(
    origin: str,
    max_jumps: int = 15,
    activity_type: str = "kills",
    min_security: float | None = None,
    max_security: float | None = None,
    limit: int = 10
) -> dict:
    """
    Find high-activity systems near origin.

    Useful for hunting roams (find targets) or avoidance (find danger).

    Args:
        origin: Starting system for search
        max_jumps: Maximum distance to search
        activity_type: What to measure
            - "kills": PvP kills (ship + pod)
            - "jumps": Traffic volume
            - "ratting": NPC kills (potential targets)
        min_security: Minimum security status filter
        max_security: Maximum security status filter
        limit: Maximum systems to return

    Returns:
        List of high-activity systems sorted by activity level

    Example:
        # Find busy low-sec hunting grounds
        universe_hotspots("Hek", activity_type="jumps",
                         min_security=0.1, max_security=0.4)
    """
```

Response format:
```json
{
  "origin": "Hek",
  "activity_type": "kills",
  "hotspots": [
    {
      "name": "Amamake",
      "system_id": 30002537,
      "security": 0.4,
      "jumps_from_origin": 8,
      "activity_value": 47,
      "activity_level": "high"
    }
  ],
  "search_radius": 15,
  "systems_scanned": 127
}
```

#### universe_gatecamp_risk

| Property | Value |
|----------|-------|
| Tool Name | `universe_gatecamp_risk` |
| Latency Target | <150ms |
| Parameters | route (list[str]) or origin+destination |

```python
@server.tool()
async def universe_gatecamp_risk(
    route: list[str] | None = None,
    origin: str | None = None,
    destination: str | None = None,
    mode: str = "safe"
) -> dict:
    """
    Analyze gatecamp risk along a route.

    Combines static chokepoint analysis (from universe_analyze) with
    live kill data to identify likely gatecamps.

    Args:
        route: Explicit route as system list, OR
        origin/destination: Calculate route first
        mode: Routing mode if calculating (shortest, safe, unsafe)

    Returns:
        Route with risk assessment for each chokepoint

    Gatecamp Heuristic:
        A system is flagged as likely gatecamp if:
        - It's a chokepoint (security transition or pipe)
        - Recent kills > 5 in last hour

    Example:
        universe_gatecamp_risk(origin="Jita", destination="Tama")
    """
```

Response format:
```json
{
  "route_summary": {
    "origin": "Jita",
    "destination": "Tama",
    "total_jumps": 12,
    "risk_level": "high"
  },
  "chokepoints": [
    {
      "system": "Nourvukaiken",
      "security": 0.4,
      "type": "lowsec_entry",
      "recent_kills": 23,
      "recent_pods": 8,
      "risk_level": "high",
      "warning": "Active gatecamp likely"
    }
  ],
  "high_risk_systems": ["Nourvukaiken", "Tama"],
  "recommendation": "Route has 2 high-risk chokepoints. Consider scouting or using wormholes."
}
```

**Safe Alternatives Algorithm (Simplified)**:

Rather than computing alternative routes (which adds complexity and latency), `universe_gatecamp_risk` provides:

1. **high_risk_systems**: List of systems with `risk_level` >= "high" - can be passed directly to `universe_route(..., avoid_systems=[...])`
2. **recommendation**: Human-readable advice based on overall risk level

This keeps the tool focused on *analysis* while letting `universe_route` handle *alternative routing*. Users can chain the tools:

```python
# Analyze risk
risk = await universe_gatecamp_risk(origin="Jita", destination="Tama")

# If risky, get alternative route avoiding dangerous systems
if risk["route_summary"]["risk_level"] in ("high", "extreme"):
    alt_route = await universe_route(
        origin="Jita",
        destination="Tama",
        mode="safe",
        avoid_systems=risk["high_risk_systems"]
    )
```

#### fw_frontlines

| Property | Value |
|----------|-------|
| Tool Name | `fw_frontlines` |
| Latency Target | <100ms |
| Parameters | faction (str, optional) |

```python
@server.tool()
async def fw_frontlines(faction: str | None = None) -> dict:
    """
    Get current Faction Warfare frontline systems.

    Returns contested and vulnerable systems where fighting is active.

    Args:
        faction: Filter to specific faction
            - "caldari", "gallente", "amarr", "minmatar"
            - None for all factions

    Returns:
        FW systems grouped by contested status

    Example:
        fw_frontlines("gallente")
    """
```

Response format:
```json
{
  "faction_filter": "gallente",
  "frontlines": {
    "contested": [
      {
        "name": "Heydieles",
        "system_id": 30002957,
        "security": 0.3,
        "owner": "Caldari State",
        "occupier": "Caldari State",
        "contested_percentage": 67.3,
        "recent_kills": 34
      }
    ],
    "vulnerable": [...],
    "stable": [...]
  },
  "summary": {
    "total_systems": 101,
    "contested_count": 12,
    "vulnerable_count": 5
  }
}
```

#### activity_cache_status

| Property | Value |
|----------|-------|
| Tool Name | `activity_cache_status` |
| Latency Target | <10ms (no network) |
| Parameters | None |

```python
@server.tool()
async def activity_cache_status() -> dict:
    """
    Return diagnostic information about the activity cache.

    Useful for debugging cache behavior, checking data freshness,
    and verifying ESI connectivity.

    Returns:
        Cache status for kills, jumps, and FW data layers

    Example:
        activity_cache_status()
    """
```

Response format:
```json
{
  "kills": {
    "cached_systems": 2847,
    "age_seconds": 342,
    "ttl_seconds": 600,
    "stale": false
  },
  "jumps": {
    "cached_systems": 5201,
    "age_seconds": 342,
    "ttl_seconds": 600,
    "stale": false
  },
  "fw": {
    "cached_systems": 101,
    "age_seconds": 1205,
    "ttl_seconds": 1800,
    "stale": false
  }
}
```

## Models

```python
# aria_esi/mcp/models.py (additions)

from pydantic import BaseModel
from typing import Literal


class SystemActivity(BaseModel):
    """Activity data for a single system."""
    name: str
    system_id: int
    security: float
    security_class: Literal["HIGH", "LOW", "NULL"]
    ship_kills: int = 0
    pod_kills: int = 0
    npc_kills: int = 0
    ship_jumps: int = 0
    activity_level: Literal["none", "low", "medium", "high", "extreme"] = "none"


class ActivityResult(BaseModel):
    """Result from universe_activity tool."""
    systems: list[SystemActivity]
    cache_age_seconds: int
    data_period: str = "last_hour"
    warnings: list[str] = []


class HotspotSystem(BaseModel):
    """A high-activity system from hotspots search."""
    name: str
    system_id: int
    security: float
    security_class: Literal["HIGH", "LOW", "NULL"]
    region: str
    jumps_from_origin: int
    activity_value: int
    activity_level: Literal["low", "medium", "high", "extreme"]


class HotspotsResult(BaseModel):
    """Result from universe_hotspots tool."""
    origin: str
    activity_type: str
    hotspots: list[HotspotSystem]
    search_radius: int
    systems_scanned: int
    cache_age_seconds: int


class GatecampRisk(BaseModel):
    """Risk assessment for a single chokepoint."""
    system: str
    system_id: int
    security: float
    chokepoint_type: Literal["lowsec_entry", "lowsec_exit", "pipe", "hub"]
    recent_kills: int
    recent_pods: int
    risk_level: Literal["low", "medium", "high", "extreme"]
    warning: str | None = None


class GatecampRiskResult(BaseModel):
    """Result from universe_gatecamp_risk tool."""
    origin: str
    destination: str
    total_jumps: int
    overall_risk: Literal["low", "medium", "high", "extreme"]
    chokepoints: list[GatecampRisk]
    high_risk_systems: list[str] = []  # Systems with risk_level >= "high", for avoid_systems param
    recommendation: str = ""  # Human-readable advice
    cache_age_seconds: int


class FWSystem(BaseModel):
    """Faction Warfare system status."""
    name: str
    system_id: int
    security: float
    owner_faction: str
    occupier_faction: str
    contested: Literal["uncontested", "contested", "vulnerable"]
    contested_percentage: float
    victory_points: int
    victory_points_threshold: int
    recent_kills: int | None = None


class FWFrontlinesResult(BaseModel):
    """Result from fw_frontlines tool."""
    faction_filter: str | None
    contested: list[FWSystem]
    vulnerable: list[FWSystem]
    stable: list[FWSystem]
    summary: dict
    cache_age_seconds: int


class CacheLayerStatus(BaseModel):
    """Status of a single cache layer."""
    cached_systems: int
    age_seconds: int | None
    ttl_seconds: int
    stale: bool


class CacheStatusResult(BaseModel):
    """Result from activity_cache_status tool."""
    kills: CacheLayerStatus
    jumps: CacheLayerStatus
    fw: CacheLayerStatus
```

## Activity Level Classification

```python
def classify_activity(value: int, activity_type: str) -> str:
    """
    Classify activity level based on value and type.

    Thresholds tuned for EVE Online typical activity:
    - Kills: Most systems have 0-5, >20 is notable, >50 is extreme
    - Jumps: Trade hubs have thousands, >500 is busy for low-sec
    - Ratting: Varies by region, >100 is active
    """
    if activity_type == "kills":
        if value == 0:
            return "none"
        elif value < 5:
            return "low"
        elif value < 20:
            return "medium"
        elif value < 50:
            return "high"
        else:
            return "extreme"
    elif activity_type == "jumps":
        if value < 50:
            return "low"
        elif value < 200:
            return "medium"
        elif value < 500:
            return "high"
        else:
            return "extreme"
    elif activity_type == "ratting":
        if value < 50:
            return "low"
        elif value < 100:
            return "medium"
        elif value < 300:
            return "high"
        else:
            return "extreme"
    return "none"
```

## Acceptance Criteria

1. [x] ActivityCache fetches and caches ESI data correctly
2. [x] Cache refreshes automatically after TTL expiry
3. [x] Concurrent requests don't trigger duplicate ESI calls (asyncio.Lock working)
4. [x] Graceful degradation when ESI is unavailable (stale data preserved)
5. [x] `universe_activity` returns accurate data for specified systems
6. [x] `universe_hotspots` finds high-activity systems within range
7. [x] `universe_gatecamp_risk` identifies risky chokepoints and returns `high_risk_systems`
8. [x] `fw_frontlines` returns current FW contested systems
9. [x] `activity_cache_status` returns accurate diagnostic info
10. [x] All tools integrate with existing universe graph (name↔ID resolution)
11. [x] Response times within latency targets
12. [x] Activity levels classified appropriately

## Test Requirements

```python
# tests/mcp/test_tools_activity.py

import asyncio
import time

import pytest
from unittest.mock import Mock, patch

from aria_esi.mcp.activity import ActivityCache, ActivityData


@pytest.fixture
def mock_esi_kills():
    """Mock ESI kills response."""
    return [
        {"system_id": 30002813, "ship_kills": 47, "pod_kills": 12, "npc_kills": 234},
        {"system_id": 30002537, "ship_kills": 23, "pod_kills": 5, "npc_kills": 0},
    ]


@pytest.fixture
def mock_esi_jumps():
    """Mock ESI jumps response."""
    return [
        {"system_id": 30002813, "ship_jumps": 891},
        {"system_id": 30002537, "ship_jumps": 234},
    ]


@pytest.mark.asyncio
class TestActivityCache:
    async def test_cache_refresh_on_expiry(self, mock_esi_kills):
        """Cache refreshes after TTL expires."""
        with patch.object(ESIClient, 'get', return_value=mock_esi_kills):
            cache = ActivityCache(ttl_seconds=1)
            await cache.get_activity(30002813)
            first_timestamp = cache._kills_timestamp

            await asyncio.sleep(1.5)
            await cache.get_activity(30002813)

            assert cache._kills_timestamp > first_timestamp

    async def test_cache_graceful_degradation(self):
        """Cache continues with stale data on ESI error."""
        cache = ActivityCache()
        cache._kills_data = {30002813: ActivityData(30002813, ship_kills=10)}
        cache._kills_timestamp = 0  # Expired

        with patch.object(ESIClient, 'get', side_effect=Exception("ESI down")):
            data = await cache.get_activity(30002813)
            assert data.ship_kills == 10  # Stale data preserved

    async def test_concurrent_requests_single_refresh(self, mock_esi_kills):
        """Concurrent requests only trigger one ESI call."""
        call_count = 0

        def mock_get(endpoint):
            nonlocal call_count
            call_count += 1
            time.sleep(0.1)  # Simulate network latency
            return mock_esi_kills

        with patch.object(ESIClient, 'get', side_effect=mock_get):
            cache = ActivityCache(ttl_seconds=1)
            cache._kills_timestamp = 0  # Force refresh

            # Fire 5 concurrent requests
            await asyncio.gather(*[
                cache.get_activity(30002813)
                for _ in range(5)
            ])

            # Lock should prevent duplicate calls
            assert call_count == 1

    def test_cache_status_returns_diagnostics(self):
        """Cache status returns layer info."""
        cache = ActivityCache()
        cache._kills_data = {1: ActivityData(1), 2: ActivityData(2)}
        cache._kills_timestamp = time.time() - 300  # 5 minutes old

        status = cache.get_cache_status()

        assert status["kills"]["cached_systems"] == 2
        assert status["kills"]["age_seconds"] == pytest.approx(300, abs=5)
        assert status["kills"]["stale"] is False
        assert status["fw"]["stale"] is True  # Never populated


@pytest.mark.asyncio
class TestUniverseActivity:
    async def test_returns_activity_data(self, mock_server, mock_esi_kills):
        """Returns activity data for specified systems."""
        with patch_esi(mock_esi_kills):
            result = await mock_server.call_tool(
                "universe_activity",
                systems=["Tama", "Amamake"]
            )
            assert len(result["systems"]) == 2
            assert result["systems"][0]["ship_kills"] > 0

    async def test_unknown_system_returns_zero(self, mock_server):
        """Unknown systems return zero activity."""
        result = await mock_server.call_tool(
            "universe_activity",
            systems=["Jita"]  # Trade hub, unlikely to have kills
        )
        # Should still return, just with zeros
        assert result["systems"][0]["name"] == "Jita"


@pytest.mark.asyncio
class TestUniverseHotspots:
    async def test_finds_hotspots_in_range(self, mock_server):
        """Finds high-activity systems within range."""
        result = await mock_server.call_tool(
            "universe_hotspots",
            origin="Hek",
            max_jumps=10,
            activity_type="kills"
        )
        assert "hotspots" in result
        for hotspot in result["hotspots"]:
            assert hotspot["jumps_from_origin"] <= 10

    async def test_respects_security_filter(self, mock_server):
        """Filters by security status."""
        result = await mock_server.call_tool(
            "universe_hotspots",
            origin="Hek",
            min_security=0.1,
            max_security=0.4
        )
        for hotspot in result["hotspots"]:
            assert 0.1 <= hotspot["security"] <= 0.4


@pytest.mark.asyncio
class TestUniverseGatecampRisk:
    async def test_identifies_risky_chokepoints(self, mock_server):
        """Identifies chokepoints with high kill activity."""
        result = await mock_server.call_tool(
            "universe_gatecamp_risk",
            origin="Jita",
            destination="Tama"
        )
        assert "chokepoints" in result
        # Tama pipe is notorious, should be flagged
        tama_area = [c for c in result["chokepoints"] if "risk_level" in c]
        assert len(tama_area) > 0

    async def test_returns_high_risk_systems_for_avoidance(self, mock_server):
        """Returns high_risk_systems list for use with universe_route avoid_systems."""
        result = await mock_server.call_tool(
            "universe_gatecamp_risk",
            origin="Jita",
            destination="Amamake"
        )
        assert "high_risk_systems" in result
        assert "recommendation" in result
        # high_risk_systems should contain system names, not IDs
        if result["high_risk_systems"]:
            assert all(isinstance(s, str) for s in result["high_risk_systems"])

    async def test_high_risk_systems_matches_chokepoints(self, mock_server):
        """high_risk_systems contains only systems with risk_level >= high."""
        result = await mock_server.call_tool(
            "universe_gatecamp_risk",
            origin="Jita",
            destination="Tama"
        )
        high_risk_from_chokepoints = {
            c["system"] for c in result["chokepoints"]
            if c["risk_level"] in ("high", "extreme")
        }
        assert set(result["high_risk_systems"]) == high_risk_from_chokepoints


@pytest.mark.asyncio
class TestFWFrontlines:
    async def test_returns_contested_systems(self, mock_server):
        """Returns FW systems grouped by status."""
        result = await mock_server.call_tool(
            "fw_frontlines"
        )
        assert "contested" in result
        assert "vulnerable" in result
        assert "summary" in result

    async def test_faction_filter(self, mock_server):
        """Filters by faction correctly."""
        result = await mock_server.call_tool(
            "fw_frontlines",
            faction="gallente"
        )
        assert result["faction_filter"] == "gallente"
        # All systems should involve Gallente
        for system in result["contested"] + result["vulnerable"]:
            assert "Gallente" in system["owner_faction"] or \
                   "Gallente" in system["occupier_faction"]


@pytest.mark.asyncio
class TestActivityCacheStatus:
    async def test_returns_all_cache_layers(self, mock_server):
        """Returns status for all three cache layers."""
        result = await mock_server.call_tool("activity_cache_status")
        assert "kills" in result
        assert "jumps" in result
        assert "fw" in result

    async def test_status_fields_present(self, mock_server):
        """Each layer has required status fields."""
        result = await mock_server.call_tool("activity_cache_status")
        for layer in ["kills", "jumps", "fw"]:
            assert "cached_systems" in result[layer]
            assert "ttl_seconds" in result[layer]
            assert "stale" in result[layer]
```

## CLI Fallback Commands

For parity with MCP tools, CLI commands are available:

```bash
# Activity data for systems
uv run aria-esi activity-systems Tama Amamake Rancer

# Find hotspots
uv run aria-esi hotspots Hek --type kills --max-jumps 15

# Gatecamp risk analysis
uv run aria-esi gatecamp-risk Jita Tama --mode safe

# FW frontlines
uv run aria-esi fw-frontlines --faction gallente

# Cache diagnostics
uv run aria-esi activity-cache-status
```

## Estimated Effort

| Component | Effort | Notes |
|-----------|--------|-------|
| ActivityCache | Small | Caching with async locks, FW support |
| universe_activity | Small | Map IDs to names, format output |
| universe_hotspots | Medium | BFS + activity filtering |
| universe_gatecamp_risk | Medium | Combines analyze + activity, high_risk_systems extraction |
| fw_frontlines | Small | ESI fetch + formatting |
| activity_cache_status | Trivial | Direct cache introspection |
| Tests | Medium | Requires ESI mocking, concurrent request tests |
| CLI commands | Small | Reuse MCP implementations |

**Total: Medium-Large**

## Rollout Strategy

### Phase 1: Core Activity Layer
- Implement ActivityCache
- Implement universe_activity tool
- Basic tests with mocked ESI

### Phase 2: Advanced Tools
- Implement universe_hotspots
- Implement universe_gatecamp_risk
- Integration with existing analyze tool

### Phase 3: FW Support
- Implement fw_frontlines
- Add faction resolution

### Phase 4: CLI Parity
- Add CLI commands
- Documentation updates

## Future Enhancements

1. **Activity-Weighted Routing**: Extend `universe_route` with `avoid_activity="high_kills"` parameter
2. **zkillboard Integration**: More detailed kill information (ship types, attackers)
3. **Trend Analysis**: Track activity over time with persistent storage
4. **Push Notifications**: Alert on activity spikes in watched systems

## Notes

- ESI data is delayed ~5 minutes from live game state
- Cache TTL of 10 minutes balances freshness vs API load
- Activity thresholds based on typical EVE activity patterns; may need tuning
- Gatecamp detection is heuristic, not guaranteed accurate
- FW systems change slowly; 30-minute cache acceptable
