# Query Resolution Optimization: Reducing MCP Round-Trips

**Status:** IMPLEMENTED (2026-03-18)
**Related:** `universe` dispatcher, `_actions_intel.py`, `_actions_navigation.py`, `_actions_planning.py`, CLAUDE.md routing hints

---

## Executive Summary

Reduce multi-step universe query resolution from 4+ tool rounds to 1-2 rounds by eliminating redundant MCP calls, enriching existing responses with activity data, adding a purpose-built roaming route action, and documenting composite query patterns.

**Primary value:** Hunting/roaming route queries that currently take 4.5+ minutes and 10 MCP calls should resolve in under 60 seconds with 2-3 calls.

---

## Problem Statement

A real session (2026-03-18) was analyzed where a capsuleer filamented into 7BIX-A and requested a ~20 jump hunting route through Fountain ratting systems. The model required:

- **4 tool rounds** (sequential, blocking)
- **10 MCP calls** (6 redundant or dead-end)
- **~4.5 minutes** wall-clock resolution time

The final output was a well-structured 21-jump route with tactical annotations. The quality was fine -- the cost was entirely in resolution time.

### Call-by-call breakdown

| Round | Calls | Useful | Wasted |
|-------|-------|--------|--------|
| 1 | `local_area`, `hotspots(ratting)`, `hotspots(kills)`, `territory_analysis` | 2 | 2 (`hotspots(ratting)` duplicated `local_area.ratting_banks`; `territory_analysis` returned empty) |
| 2 | `optimize_waypoints(9 systems)`, `activity(12 systems)` | 0 | 2 (optimizer produced 39j backtracking route, discarded; activity data already in local_area) |
| 3 | `route(7BIX-A→Y-2ANO)`, `route(9DQW-W→LBGI-2)`, `systems(9)` | 2 | 1 (9DQW-W route was exploratory, confirmed dead-end inferable from topology) |
| 4 | `route(00GD-D→LBGI-2, avoid=[...])`, `systems(3)` | 0 | 2 (41j avoidance route just validated what neighbor data showed) |

### Optimal path (identified post-hoc)

**Round 1 (parallel):**
```
local_area(origin="7BIX-A", max_jumps=25, include_realtime=true, ratting_threshold=50)
route(origin="7BIX-A", destination="Y-2ANO", mode="shortest")
```

Two calls, one round. `local_area` provides ratting banks + PVP hotspots + escape routes. `route` provides the backbone with full neighbor topology. All data needed for the final answer was present after this single round.

---

## Root Causes

| Cause | Impact |
|-------|--------|
| **No documentation that `local_area` is a superset of `hotspots` and `activity`** | Model calls both, doubling data retrieval |
| **`route` responses lack activity data** | Model must call `activity` separately for systems already in the route response |
| **No action exists for linear roaming routes** | Model improvises with `optimize_waypoints` (TSP, allows backtracking) then manually builds topology from multiple `systems` and `route` calls |
| **No routing hints for hunting/roaming queries** | Model has no prior for which calls compose well, explores incrementally |
| **`optimize_waypoints` has no linear/no-backtrack mode** | Its TSP solution is structurally wrong for roaming, wasting a call every time |
| **No response metadata indicating data overlap** | Model cannot detect that data it needs is already in a prior response |

---

## Proposed Changes

### Change 1: Add `action="roam_route"` to universe dispatcher

**Priority:** P0 (highest impact)
**Effort:** Medium
**Files:** `_dispatcher.py`, new `_actions_roaming.py`, `_helpers_roam.py`

A single action that constructs a linear hunting/roaming route through active ratting or PVP systems, respecting topology constraints.

#### Parameters

```python
async def _roam_route(
    origin: str,                          # Starting system
    target_jumps: int = 20,               # Desired route length (10-40)
    activity_type: str = "ratting",        # "ratting" or "kills" - what to route through
    mode: str = "linear",                 # "linear" (no backtrack) or "sweep" (allow 1-2 system retrace through transit)
    avoid_systems: list[str] | None = None,
    avoid_hotspots: bool = True,          # Auto-avoid PVP hotspots
    hotspot_threshold: int = 5,           # PVP kills threshold for avoidance
    direction: str | None = None,         # Optional destination system to bias direction
    include_activity: bool = True,        # Embed NPC/ship kill data per system
) -> dict:
```

#### Algorithm

**Step 1: Data collection.** BFS from origin to `target_jumps * 2` radius. For every system in range, fetch activity from the hourly cache (same source as `local_area`). Store `(idx, distance_from_origin, npc_kills, pvp_kills, ship_jumps)` per system.

**Step 2: System classification.** Each system is classified for routing purposes. The scoring metric depends on `activity_type`:

| `activity_type` | Hunt metric | Threat metric |
|-----------------|-------------|---------------|
| `"ratting"` | `npc_kills` | `ship_kills + pod_kills` |
| `"kills"` | `ship_kills + pod_kills` | *(no separate threat — hunt and threat overlap; use `ship_jumps` as traffic proxy instead)* |

Classification table (using the hunt metric for the active `activity_type`):

| Classification | Predicate | Phase label |
|----------------|-----------|-------------|
| **hunt** | `hunt_metric >= hunt_threshold` | `"hunt"` |
| **threat** | `threat_metric >= hotspot_threshold` | excluded from route when `avoid_hotspots=True` |
| **transit** | `hunt_metric < hunt_threshold AND threat_metric < hotspot_threshold` | `"transit"` |

When `activity_type="kills"`, threat avoidance uses `ship_jumps >= hotspot_threshold * 50` as a proxy (high-traffic pipe systems are camped, not hunting grounds). This prevents the paradox of a kill-seeking route that avoids all kill-active systems.

`hunt_threshold` is derived from the BFS data: **P75 of non-zero values of the hunt metric** across all systems in range. This adapts to regional activity — a quiet region gets a lower bar, a busy one gets a higher bar. Minimum floor: 50 for `activity_type="ratting"` (NPC kills), 3 for `activity_type="kills"` (ship+pod kills). **Empty-set guard:** If no systems in BFS range have non-zero hunt metric values (dead region or stale cache), skip the P75 computation and use the minimum floor directly.

**Step 3: Greedy forward-walk with 3-jump lookahead.**

From the current position, evaluate every **unvisited** neighbor within 3 graph hops. For each candidate next-hop (the immediate neighbor you'd jump to), compute a lookahead score:

```python
def score_candidate(candidate_idx: int, visited: set[int], depth: int = 3) -> float:
    """Score a candidate next-hop by the activity reachable through it."""
    reachable = bfs_unvisited(candidate_idx, visited, max_depth=depth)

    # hunt_metric[idx] = npc_kills when activity_type="ratting", ship_kills+pod_kills when "kills"
    activity_score = sum(
        hunt_metric[idx] / (hop_distance ** 0.5)  # sqrt decay: nearby activity worth more
        for idx, hop_distance in reachable
        if classification[idx] == "hunt"
    )

    # Direction bias: if direction target set, bonus for reducing distance to it.
    # graph_distance = BFS hop count from the Step 1 expansion (already computed and stored
    # per-system as distance_from_origin; for candidate→direction, run a single BFS from
    # direction_idx at route start and cache the results).
    direction_score = 0.0
    if direction_idx is not None:
        origin_dist = graph_distance(origin_idx, direction_idx)
        candidate_dist = graph_distance(candidate_idx, direction_idx)
        # Normalized: +1.0 when moving directly toward target, -1.0 when moving away
        direction_score = (origin_dist - candidate_dist) / max(origin_dist, 1)

    # Combine: activity is primary, direction is tiebreaker
    # direction_weight=0.15 means a perfect directional alignment adds ~15% to score
    return activity_score * (1.0 + 0.15 * direction_score)
```

**Advancement rule:** Pick the candidate with the highest score. If all candidates score 0 (no reachable hunt systems), pick the neighbor that maximizes unvisited reachable system count (keep options open). If tied, prefer the neighbor with fewer total connections (explore dead-ends before they become traps).

**Termination:** Stop when `len(route) >= target_jumps` or no unvisited neighbors remain.

**Step 4: Sweep-mode retrace (only when `mode="sweep"`).**

After the forward walk terminates, if `len(route) < target_jumps` and additional hunt clusters exist reachable via 1-2 transit systems that were already visited:

1. From the route endpoint, find hunt systems reachable through exactly 1-2 already-visited **transit** systems (not hunt systems — retracing through a ratting system counts as backtracking).
2. The retrace limit is **hard**: maximum 2 transit systems may be revisited, total across the entire route. If this limit is already reached, stop.
3. Append the retrace segment: the 1-2 transit systems get `phase="retrace"`, then continue the forward walk from the new position.

When `mode="linear"`, skip Step 4 entirely. The route may be shorter than `target_jumps` if topology constrains it.

**Step 5: Annotate and return.** Tag each system with its phase, attach activity data and neighbor info, compute escape routes from the endpoint using the same logic as `local_area`'s `_find_escape_routes` (nearest highsec/lowsec/NPC-station exits by jump distance), return `RoamRouteResult`.

#### Response Structure

```python
class RoamRouteResult(MCPModel):
    origin: str
    systems: list[RoamRouteSystem]      # Full route with activity data
    total_jumps: int
    hunting_systems: int                 # Count of systems with activity above threshold
    total_npc_kills: int                 # Sum of NPC kills along route
    total_pvp_kills: int                 # Sum of PVP kills along route (threat indicator)
    retrace_systems: list[str]           # Systems visited twice (empty if mode="linear")
    escape_routes: list[EscapeRoute]     # Nearest exits from route endpoint
    warnings: list[str]
    corrections: dict[str, str]

class RoamRouteSystem(MCPModel):
    name: str
    system_id: int
    security: float
    region: str
    jump_number: int                     # Position in route (1-indexed)
    phase: str                           # "transit", "hunt", "retrace"
    npc_kills: int                       # Last-hour NPC kills
    ship_kills: int                      # Last-hour ship kills
    pod_kills: int                       # Last-hour pod kills
    ship_jumps: int                      # Last-hour traffic
    neighbors: list[NeighborInfo]        # Gate connections (for tactical awareness)
```

#### Dispatcher Integration

Add to `VALID_ACTIONS` and `UniverseAction` in `_dispatcher.py`:

```python
case "roam_route":
    result = await _roam_route(
        origin,
        target_jumps,
        activity_type,
        mode,
        avoid_systems,
        avoid_hotspots=True,      # Intentionally unexposed — always on for roaming safety
        hotspot_threshold=hotspot_threshold,
        direction=destination,    # Reuse existing param
        include_activity=True,
    )
```

**Design decision:** `avoid_hotspots` is intentionally hardcoded to `True` and not exposed as a dispatcher parameter. A roaming route that walks through PVP hotspots is a misuse of the action — capsuleers wanting to route *toward* PVP should use `hotspots` + manual `route` calls instead. This may be revisited if a concrete use case emerges.

#### Tool Description Addition

Add to the universe dispatcher docstring:

```
Roam route params (action="roam_route"):
    origin: Starting system
    target_jumps: Desired route length (default 20, max 40)
    activity_type: "ratting" or "kills" - systems to route through
    mode: "linear" (no backtrack) or "sweep" (minimal retrace ok)
    avoid_systems: Systems to skip
    destination: Optional system to bias route direction
    hotspot_threshold: PVP kill count to auto-avoid (default 5)
```

---

### Change 2: Document `local_area` as composite query

**Priority:** P0 (zero-effort, immediate impact)
**Effort:** Trivial
**Files:** `_dispatcher.py` (docstring), CLAUDE.md

#### Tool Description Change

Add to the `local_area` section of the universe dispatcher docstring:

```
Local area params (action="local_area"):
    ...existing params...

    NOTE: local_area is a composite query that supersedes separate calls to:
    - hotspots (ratting): covered by ratting_banks in response
    - hotspots (kills): covered by hotspots in response
    - activity (for systems in radius): covered by per-system data in all lists
    Do NOT call hotspots or activity separately when local_area covers the same origin/radius.
```

#### CLAUDE.md Routing Hint

Add a new section under "Routing Hints":

```markdown
### Composite Query Patterns

| Query type | Optimal call | Do NOT also call |
|------------|-------------|------------------|
| Orientation / local intel | `local_area` | `hotspots`, `activity` for same area |
| Route with activity data | `route` (includes activity if enriched) | `activity` for route systems |
| Roaming / hunting route | `roam_route` | `local_area`, `hotspots`, `optimize_waypoints` |
```

---

### Change 3: Add `linear` mode to `optimize_waypoints`

**Priority:** P2
**Effort:** Medium
**Files:** `_helpers_waypoints.py`, `_actions_planning.py`, `_dispatcher.py` (docstring)

#### Current Behavior

`optimize_waypoints` uses nearest-neighbor TSP to minimize total travel distance. This naturally produces backtracking routes through shared hub nodes. For a 9-waypoint request in Fountain, it returned a 39-jump route that was entirely discarded.

#### Proposed Change

Add a `linear: bool = False` parameter. When `linear=True`:

1. Do NOT solve TSP (minimum total distance is the wrong objective)
2. Instead, find the **longest non-repeating Hamiltonian path** through the waypoint set
3. Use greedy longest-path heuristic: from origin, pick the next unvisited waypoint that maximizes remaining reachable waypoints (avoid painting into dead-end corners)
4. Accept that not all waypoints may be reachable without backtracking -- return `skipped_waypoints` for unreachable ones

#### Parameter Addition

```python
async def _optimize_waypoints(
    waypoints: list[str] | None,
    origin: str | None,
    return_to_origin: bool,
    security_filter: str,
    avoid_systems: list[str] | None,
    linear: bool = False,               # NEW
) -> dict:
```

#### Response Addition

When `linear=True`, add to response:
```python
"skipped_waypoints": ["system1", "system2"],  # Unreachable without backtracking
"mode": "linear",                              # vs "tsp"
```

#### Parameter Interaction: `linear=True` + `return_to_origin=True`

These parameters are contradictory — a linear path cannot return to origin without backtracking. When both are set, `linear` wins: ignore `return_to_origin` and emit a warning in `warnings`:

```python
if linear and return_to_origin:
    warnings.append("linear=True overrides return_to_origin — linear paths cannot loop")
    return_to_origin = False
```

#### Docstring Update

```
Optimize waypoints params (action="optimize_waypoints"):
    ...existing params...
    linear: If true, find longest non-repeating path instead of TSP loop.
            Use for roaming routes where backtracking is unacceptable.
            Some waypoints may be skipped if unreachable without repeat.
            Overrides return_to_origin if both are set. (default False)
```

---

### Change 4: Add routing hints for hunting/roaming queries

**Priority:** P0 (documentation only, immediate impact)
**Effort:** Trivial
**Files:** CLAUDE.md

Add to the routing hints table:

```markdown
| "roam through", "hunting route", "sweep through [space]" | `roam_route` action (or `local_area` + `route` if `roam_route` unavailable) |
| "route through ratting systems", "find ratters" | `roam_route` with `activity_type="ratting"` |
| "avoid backtracking", "linear route", "no doubling back" | `roam_route` with `mode="linear"` (or `optimize_waypoints` with `linear=true`) |
```

Add a note under the hints table:

```markdown
**Query composition for roaming (if `roam_route` not yet available):**
1. `local_area(origin, max_jumps=25, include_realtime=true)` -- gives ratting banks + threats + escapes
2. `route(origin, destination=<farthest ratting target>)` -- gives backbone with neighbor topology
3. Design detours from backbone neighbor data. Do NOT call `hotspots`, `activity`, or `systems` separately.
```

---

### Change 5: Add `_covers` metadata to MCP responses

**Priority:** P3 (nice-to-have)
**Effort:** Low
**Files:** `context.py`, `_actions_intel.py`

#### Concept

When a response contains data that makes other queries redundant, include a `_covers` field in `_meta`:

```python
"_meta": {
    "count": 28,
    "timestamp": "2026-03-18T20:07:19+00:00",
    "_covers": [
        "hotspots(origin='{origin}', activity_type='ratting', max_jumps<={radius})",
        "hotspots(origin='{origin}', activity_type='kills', max_jumps<={radius})",
        "activity(systems=[<any system in response>])"
    ]
}
```

#### Implementation

Add to `wrap_output_multi` an optional `covers` parameter (appended after existing `source` and `as_of` params):

```python
def wrap_output_multi(
    data: dict[str, Any],
    items_config: list[tuple[str, int]],
    source: str | None = None,            # existing
    as_of: str | None = None,             # existing
    covers: list[str] | None = None,      # NEW
) -> dict[str, Any]:
    ...
    if covers:
        result["_meta"]["_covers"] = covers
    return result
```

In `_local_area`, pass covers:

```python
return wrap_output_multi(
    result.model_dump(),
    [
        ("hotspots", 10),
        ("quiet_zones", 10),
        ("ratting_banks", 10),
        ("escape_routes", 5),
        ("borders", 10),
        ("fw_systems", 10),
    ],
    covers=[
        f"hotspots(origin='{origin_resolved.canonical_name}', activity_type='ratting', max_jumps<={effective_max_jumps})",
        f"hotspots(origin='{origin_resolved.canonical_name}', activity_type='kills', max_jumps<={effective_max_jumps})",
    ],
)
```

#### Trade-off

This is the least impactful change. The model may not reliably check `_covers` metadata. The documentation changes (Changes 2 and 4) achieve the same goal more reliably through prompt-level guidance. Include this only if model behavior testing shows the prompt-level hints are insufficient.

---

### Change 6: Enrich `route` responses with activity data

**Priority:** P1 (high impact, low effort)
**Effort:** Low
**Files:** `_helpers_route.py`, `utils.py` (`build_system_info`), `models.py` (`SystemInfo`)

#### Current Behavior

`route` responses include full `SystemInfo` per system with neighbors, sovereignty, constellation, and region -- but no activity data. The model must call `activity` separately for route systems to get NPC kills, ship kills, and jump counts.

#### Proposed Change

Add optional activity enrichment to route responses.

**New parameter on `route` action:**

```python
async def _route(
    origin: str | None,
    destination: str | None,
    mode: str,
    avoid_systems: list[str] | None,
    prefer_territory: str | None = None,
    avoid_territory: str | None = None,
    include_activity: bool = False,        # NEW
) -> dict:
```

**Model change (`SystemInfo`):**

```python
class SystemInfo(BaseModel):
    name: str
    system_id: int
    security: float
    security_class: str
    constellation: str
    constellation_id: int
    region: str
    region_id: int
    neighbors: list[NeighborInfo]
    is_border: bool
    adjacent_lowsec: list[str]
    sovereignty: SovereigntyInfo | None = None
    # NEW - optional activity fields (populated when include_activity=True)
    npc_kills: int | None = None
    ship_kills: int | None = None
    pod_kills: int | None = None
    ship_jumps: int | None = None
    activity_level: str | None = None
```

**Enrichment in `_build_route_result`:**

`SystemInfo` inherits from `MCPModel` which sets `frozen=True`. Direct attribute assignment will raise `ValidationError`. Use `model_copy(update=...)` to produce enriched copies.

```python
async def _build_route_result(
    universe: UniverseGraph,
    path: list[int],
    origin: str,
    destination: str,
    mode: str,
    corrections: dict[str, str] | None = None,
    include_activity: bool = False,         # NEW
) -> RouteResult:
    systems = [build_system_info(universe, idx) for idx in path]

    if include_activity:
        cache = get_activity_cache()
        enriched: list[SystemInfo] = []
        for system_info in systems:
            activity = await cache.get_activity(system_info.system_id)
            enriched.append(system_info.model_copy(update={
                "npc_kills": activity.npc_kills,
                "ship_kills": activity.ship_kills,
                "pod_kills": activity.pod_kills,
                "ship_jumps": activity.ship_jumps,
                "activity_level": classify_activity(
                    activity.ship_kills + activity.pod_kills, "kills"
                ),
            }))
        systems = enriched

    ...rest unchanged...
```

**`classify_activity` reference:** Import from `aria_esi.store.activity` (`src/aria_esi/store/activity.py:301`). Already used by `_actions_intel.py` for `SystemActivity.activity_level` population. Thresholds: kills 0=none, <5=low, <20=medium, <50=high, >=50=extreme.

**Async propagation:** `_build_route_result` is currently sync (`_helpers_route.py:92`). This change makes it `async`. All call sites must add `await`. **Caller audit required:** verify all callers of `_build_route_result` (known: `_route` in `_actions_navigation.py`; grep for others before implementing). The `_route` function is already `async`, so adding `await` there is mechanical — but any sync callers discovered during audit will need async propagation.

**Activity cache miss behavior:** When `get_activity()` returns a cache miss (system with no hourly data), all kill/jump fields default to 0 and `activity_level` will be `"none"` via `classify_activity(0, "kills")`. This is the correct behavior — no special handling needed.

#### Docstring Update

```
Route params (action="route"):
    ...existing params...
    include_activity: Embed NPC/ship kill data per system (default False).
                      Eliminates need for separate activity() call on route systems.
```

#### Performance Impact

The activity cache (`get_activity_cache()`) stores hourly data in memory. Enriching a 20-system route adds ~20 dict lookups -- negligible overhead. No additional ESI or network calls.

---

## Implementation Order

| Phase | Changes | Effort | Impact |
|-------|---------|--------|--------|
| **Phase 1** (immediate) | #2 (doc composite), #4 (routing hints) | Documentation only | Eliminates 2-3 redundant calls per roaming session |
| **Phase 2** (quick win) | #6 (route activity enrichment) | ~2 hours | Eliminates follow-up `activity` calls for any route |
| **Phase 3** (main feature) | #1 (`roam_route` action) | ~1 day | Single-call resolution for all roaming/hunting queries |
| **Phase 4** (cleanup) | #3 (linear waypoints), #5 (`_covers` metadata) | ~4 hours | Edge case improvements |

Phase 1 ships as a documentation commit with zero risk. Phase 2 is additive (new optional param, backward compatible). Phase 3 is the significant feature work. Phase 4 is polish.

---

## Testing Strategy

**Topology fixture:** Tests run against the real `UniverseGraph` loaded from SDE (integration tests), consistent with the existing test patterns in `tests/mcp/`. Topology-dependent assertions (e.g., "block both exits from 7BIX-A") use real system names verified against current SDE data. If an SDE update changes gate topology, these tests may need system name updates — this is acceptable for the low frequency of such changes.

**Activity fixture:** Activity data (NPC kills, ship kills, ship jumps) comes from `ActivityCache` (ESI hourly data), not SDE. Tests requiring deterministic activity assertions must mock `ActivityCache` with fixture data. Follow the existing pattern in `tests/mcp/` for cache mocking. The fixture must seed at least:

- **3+ systems** in 7BIX-A BFS range with `npc_kills >= 50` (for `hunt` classification at default ratting threshold)
- **1+ system** with `ship_kills + pod_kills >= 5` (for hotspot avoidance assertions)
- **Remaining systems** with zero activity (for transit classification and cache-miss behavior)

Topology-only tests (`test_roam_route_degenerate_topology`, `test_roam_route_avoid_systems_blocks_forward`, `test_linear_*`) do not depend on activity values and can use an empty or zero-activity cache — their assertions are structural (no duplicates, correct system count, warnings emitted).

### Change 1: `roam_route`

```python
async def test_roam_route_linear_no_backtrack():
    """Linear mode must never revisit a system."""
    result = await _roam_route(origin="7BIX-A", target_jumps=15, mode="linear")
    system_names = [s["name"] for s in result["systems"]]
    assert len(system_names) == len(set(system_names)), "Route contains duplicate systems"

async def test_roam_route_sweep_minimal_retrace():
    """Sweep mode may retrace but only transit systems."""
    result = await _roam_route(origin="7BIX-A", target_jumps=20, mode="sweep")
    for name in result["retrace_systems"]:
        system = next(s for s in result["systems"] if s["name"] == name)
        assert system["phase"] == "retrace"

async def test_roam_route_targets_ratting():
    """Route should pass through high-NPC systems when activity_type=ratting."""
    result = await _roam_route(origin="7BIX-A", target_jumps=20, activity_type="ratting")
    hunt_systems = [s for s in result["systems"] if s["phase"] == "hunt"]
    assert len(hunt_systems) >= 3
    assert all(s["npc_kills"] > 0 for s in hunt_systems)

async def test_roam_route_avoids_pvp_hotspots():
    """Route should not pass through high-PVP systems."""
    result = await _roam_route(
        origin="7BIX-A", target_jumps=20, hotspot_threshold=5
    )
    for system in result["systems"]:
        assert system["ship_kills"] + system["pod_kills"] < 5

async def test_roam_route_respects_target_jumps():
    """Route length should be within +-5 of target."""
    result = await _roam_route(origin="7BIX-A", target_jumps=20)
    assert 15 <= result["total_jumps"] <= 25

async def test_roam_route_direction_bias():
    """When direction is specified, route endpoint should be closer to target than origin."""
    result = await _roam_route(
        origin="7BIX-A", target_jumps=20, direction="1DQ1-A"
    )
    # Verify endpoint is closer to direction target than origin is.
    # Use universe graph BFS distance for both measurements.
    universe = get_universe()
    origin_dist = universe.shortest_path_length("7BIX-A", "1DQ1-A")
    endpoint = result["systems"][-1]["name"]
    endpoint_dist = universe.shortest_path_length(endpoint, "1DQ1-A")
    assert endpoint_dist < origin_dist, (
        f"Route did not trend toward 1DQ1-A: origin {origin_dist}j, endpoint {endpoint_dist}j"
    )

async def test_roam_route_degenerate_topology():
    """When topology constrains the route, return shorter route rather than error."""
    # Use a system in a small dead-end pocket where 20 jumps isn't achievable
    result = await _roam_route(origin="F-88PJ", target_jumps=20, mode="linear")
    # Should succeed with a shorter route, not raise
    assert result["total_jumps"] > 0
    assert result["total_jumps"] <= 20
    # No duplicate systems in linear mode
    names = [s["name"] for s in result["systems"]]
    assert len(names) == len(set(names))

async def test_roam_route_avoid_systems_blocks_forward():
    """When avoid_systems cuts off all forward paths, return partial route."""
    result = await _roam_route(
        origin="7BIX-A", target_jumps=20, mode="linear",
        avoid_systems=["G-UTHL", "TU-Y2A"],  # Block both exits from origin
    )
    # Should return origin-only route (0 jumps) rather than error
    assert result["total_jumps"] == 0
    assert len(result["systems"]) == 1

async def test_roam_route_sweep_retrace_limit_hard():
    """Sweep mode must not retrace more than 2 transit systems total."""
    result = await _roam_route(origin="7BIX-A", target_jumps=25, mode="sweep")
    assert len(result["retrace_systems"]) <= 2

async def test_roam_route_sweep_no_hunt_retrace():
    """Sweep mode must never retrace through a hunt-classified system."""
    result = await _roam_route(origin="7BIX-A", target_jumps=20, mode="sweep")
    for name in result["retrace_systems"]:
        # Find FIRST occurrence (the original visit) — it should be transit, not hunt
        first_visit = next(s for s in result["systems"] if s["name"] == name and s["phase"] != "retrace")
        assert first_visit["phase"] == "transit", f"Retrace through hunt system: {name}"

async def test_roam_route_targets_kills():
    """Kill-based routing should pass through PVP-active systems, not ratting systems."""
    result = await _roam_route(origin="7BIX-A", target_jumps=20, activity_type="kills")
    hunt_systems = [s for s in result["systems"] if s["phase"] == "hunt"]
    assert len(hunt_systems) >= 1
    # Hunt systems should have ship+pod kills, not just NPC kills
    assert all(s["ship_kills"] + s["pod_kills"] > 0 for s in hunt_systems)

async def test_roam_route_sweep_respects_avoid_systems():
    """Sweep mode retrace paths must not pass through avoided systems."""
    result = await _roam_route(
        origin="7BIX-A", target_jumps=20, mode="sweep",
        avoid_systems=["G-UTHL"],
    )
    route_names = [s["name"] for s in result["systems"]]
    assert "G-UTHL" not in route_names
    # Retrace paths also must not use avoided systems
    for name in result["retrace_systems"]:
        assert name != "G-UTHL"

async def test_roam_route_avoid_hotspots_not_overridable():
    """avoid_hotspots is hardcoded True and cannot be bypassed via dispatcher."""
    # Call the dispatcher entry point (not _roam_route directly) to verify
    # that avoid_hotspots is not exposed as a parameter.
    # Any system with ship_kills + pod_kills >= hotspot_threshold must be excluded.
    result = await _roam_route(
        origin="7BIX-A", target_jumps=20, hotspot_threshold=5
    )
    for system in result["systems"]:
        assert system["ship_kills"] + system["pod_kills"] < 5, (
            f"Route passed through PVP hotspot: {system['name']} "
            f"({system['ship_kills'] + system['pod_kills']} kills)"
        )
```

### Change 3: `optimize_waypoints` linear mode

```python
def test_linear_no_repeat():
    """Linear mode must not revisit systems."""
    result = _do_optimize_waypoints(
        ..., linear=True
    )
    route_names = [s["name"] for s in result["route_systems"]]
    assert len(route_names) == len(set(route_names))

def test_linear_skips_unreachable(fountain_graph):
    """Waypoints in separate dead-end pockets force skipping one pocket."""
    # F-88PJ and CHA2-Q are in different dead-end pockets off different hubs.
    # A linear path from F-88PJ cannot reach CHA2-Q without retracing through
    # 1-5GBW → O-PNSN → D-Q04X → ... — visiting previously visited systems.
    result = _do_optimize_waypoints(
        universe=fountain_graph,
        waypoints=["F-88PJ", "CHA2-Q"],
        origin="1-5GBW",
        linear=True,
    )
    assert len(result["skipped_waypoints"]) >= 1
    assert result["mode"] == "linear"

def test_linear_overrides_return_to_origin(fountain_graph):
    """linear=True + return_to_origin=True: linear wins, warning emitted."""
    result = _do_optimize_waypoints(
        universe=fountain_graph,
        waypoints=["7BIX-A", "Y-2ANO"],
        origin="1-5GBW",
        return_to_origin=True,
        linear=True,
    )
    assert result["mode"] == "linear"
    assert any("overrides return_to_origin" in w for w in result.get("warnings", []))
    # Route should NOT loop back to origin
    route_names = [s["name"] for s in result["route_systems"]]
    assert len(route_names) == len(set(route_names))
```

### Change 6: Route activity enrichment

```python
async def test_route_without_activity():
    """Default route has no activity fields."""
    result = await _route("Jita", "Amarr", "safe")
    system = result["systems"][0]
    assert "npc_kills" not in system or system.get("npc_kills") is None

async def test_route_with_activity():
    """include_activity=True populates kill/jump data."""
    result = await _route("Jita", "Amarr", "safe", include_activity=True)
    system = result["systems"][0]
    assert system["npc_kills"] is not None
    assert system["ship_jumps"] is not None

async def test_route_activity_cache_miss():
    """Systems with no hourly data get zero-filled activity fields, not None."""
    result = await _route("Jita", "Amarr", "safe", include_activity=True)
    for system in result["systems"]:
        # All fields should be int (0 for cache miss), never None when enriched
        assert isinstance(system["npc_kills"], int)
        assert isinstance(system["ship_jumps"], int)
        assert system["activity_level"] is not None

async def test_route_activity_survives_summarization():
    """Activity data on head/tail systems preserved after route summarization."""
    # Long route that triggers summarize_route truncation
    result = await _route("Jita", "Amarr", "shortest", include_activity=True)
    # If summarized, check that non-summary systems retain activity data
    for system in result["systems"]:
        if not system.get("_summary", False):
            assert "npc_kills" in system
```

---

## Success Criteria

- [ ] Hunting/roaming route queries resolve in 1-2 MCP rounds (down from 4+)
- [ ] Model does not call `hotspots` after `local_area` for the same area
- [ ] Model does not call `activity` after `route(include_activity=true)`
- [ ] `roam_route` produces valid linear routes through active ratting space
- [ ] `optimize_waypoints(linear=true)` produces non-repeating paths
- [ ] No regression in existing `route`, `local_area`, or `optimize_waypoints` behavior

---

## Summary

| # | Change | Priority | Effort | Impact |
|---|--------|----------|--------|--------|
| 1 | `roam_route` action | P0 | Medium | Eliminates 3-4 rounds -> 1 call for roaming queries |
| 2 | Document `local_area` as composite | P0 | Trivial | Eliminates 2-3 redundant calls per session |
| 3 | `linear` mode for `optimize_waypoints` | P2 | Medium | Prevents wrong-tool selection for no-backtrack routes |
| 4 | Routing hints for hunting queries | P0 | Trivial | Guides model to optimal query composition |
| 5 | `_covers` response metadata | P3 | Low | Defense-in-depth against redundant follow-up calls |
| 6 | Activity enrichment on `route` | P1 | Low | Eliminates follow-up `activity` calls for any route |

Changes 2 and 4 ship immediately as documentation. Change 6 is a small additive code change. Change 1 is the primary feature work. Changes 3 and 5 are polish.
