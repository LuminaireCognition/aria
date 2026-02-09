# Context-Aware Topology Proposal

## Executive Summary

ARIA's current operational topology calculates system interest based purely on **geographic distance**—BFS expansion from configured operational systems with decay weights at each hop. While effective at reducing API calls (~80-90%), this approach fails to capture what actually matters to a corporation: **who** is involved, **what** routes are at risk, **where** assets are located, and **how** activity patterns evolve.

A Retriever dying 15 jumps away in an irrelevant system generates no notification. A war target ganking your corp mate 30 jumps away in nullsec generates no notification either—because geography says it's irrelevant. But the second scenario is exactly what a corp director needs to know.

This proposal introduces **layered interest calculation** where geographic proximity is just one signal among many. Entity relationships, route dependencies, asset locations, and activity patterns each contribute to a unified interest score, enabling truly operational intelligence.

**Key capabilities:**

| Capability | Current State | Proposed |
|------------|---------------|----------|
| Interest basis | Geography only (hop distance) | Multi-layer: geography + entity + route + asset + pattern |
| Corp member losses | Only if in topology | **Always notify** regardless of location |
| War target tracking | Via watchlist (manual) | Automatic interest boost for watched entities |
| Route awareness | None | Named routes with per-route ship type filters |
| Asset proximity | None | Auto-include systems with corp structures |
| Pattern detection | Separate system (Phase 6B) | Integrated escalation multipliers |
| Configuration | Single operational system list | Archetype presets with per-corp customization |

**Design principle:** Interest is calculated as `max(layer_scores)`, not `sum`. A system is interesting if *any* layer deems it so. This prevents dilution and ensures high-priority events (corp member death, war target activity) always surface.

---

## Problem Statement

### Current Algorithm Limitations

The existing topology algorithm (`src/aria_esi/services/redisq/topology.py`) implements:

```
interest(system) = weight[hop_level]
where hop_level = BFS_distance(system, nearest_operational_system)
```

**Default weights:**
- Hop 0 (operational): 1.0
- Hop 1 (neighbors): 1.0
- Hop 2 (2-hop): 0.7
- Hop 3+: 0.0 (filtered out)

This works for a solo pilot operating in a small area. It fails for corporations because:

### Failure Mode 1: Corp Member Losses Anywhere

**Scenario:** Industrial corp based in Ashab. Member takes a Retriever to nullsec for "adventure mining." Gets ganked in Syndicate.

**Current behavior:** Kill filtered (Syndicate not in topology). Director never knows.

**Desired behavior:** Corp member losses **always** generate notifications regardless of location. This is fundamental corp management.

### Failure Mode 2: War Target Activity

**Scenario:** Corp is wardecced. War targets are camping Jita 4-4 undock, 8 jumps from operational area.

**Current behavior:** If Jita isn't within 2 hops, no notification.

**Desired behavior:** War target activity anywhere in operational regions should notify, with boosted interest for activity on known routes.

### Failure Mode 3: Route Dependencies

**Scenario:** FW corp stages in Tama, runs logistics from Jita. Uedama is 12 jumps from Tama (well outside topology) but every freighter passes through it.

**Current behavior:** Gank fleet in Uedama generates no notification.

**Desired behavior:** Named routes (e.g., "Jita logistics") make all waypoint systems high-interest, regardless of hop distance.

### Failure Mode 4: Asset Concentration

**Scenario:** Wormhole corp with a Raitaru in J123456. That system is their *entire* operational footprint—but it's not "near" anything in k-space terms.

**Current behavior:** Must manually configure the J-sig as an operational system.

**Desired behavior:** Systems containing corp structures are automatically highest interest.

### Failure Mode 5: Pattern Blindness

**Scenario:** Normally quiet system has 3 kills in 10 minutes. Classic gatecamp formation.

**Current behavior:** Each kill is treated independently. No escalation.

**Desired behavior:** Activity spikes boost interest dynamically. A forming gatecamp should trigger enhanced monitoring.

### What Corps Actually Need

Different corporation archetypes have fundamentally different intel requirements:

| Archetype | Primary Concerns | Secondary Concerns |
|-----------|------------------|-------------------|
| **FW/Piracy** | Hunting grounds activity, war targets, hostile militia | Route safety, escape routes |
| **Null-sec** | Home constellation defense, hostile alliance movement | Intel channel correlation, structure timers |
| **Industrial** | Gank activity on trade routes, corp member safety | War target movements, market hub activity |
| **Wormhole** | Hole control, eviction indicators | K-space exit security |

A single geographic topology cannot serve all these needs.

---

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Interest Calculator                           │
│                                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  Geographic │  │   Entity    │  │    Route    │  │    Asset    │ │
│  │    Layer    │  │    Layer    │  │    Layer    │  │    Layer    │ │
│  │             │  │             │  │             │  │             │ │
│  │ BFS from    │  │ Corp/ally   │  │ Named route │  │ Structure   │ │
│  │ operational │  │ watchlist   │  │ waypoints   │  │ locations   │ │
│  │ systems     │  │ war targets │  │ ship filter │  │ offices     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
│         │                │                │                │         │
│         └────────────────┴────────────────┴────────────────┘         │
│                                   │                                   │
│                                   ▼                                   │
│                        ┌─────────────────┐                           │
│                        │  max(scores)    │                           │
│                        │  + escalation   │                           │
│                        └────────┬────────┘                           │
│                                 │                                     │
└─────────────────────────────────┼─────────────────────────────────────┘
                                  │
                                  ▼
                        ┌─────────────────┐
                        │ Pattern Layer   │
                        │ (Multiplier)    │
                        │                 │
                        │ Activity spikes │
                        │ Gatecamp forming│
                        │ Sustained threat│
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │ Final Interest  │
                        │ Score           │
                        └─────────────────┘
```

### Interest Calculation Model

```python
def calculate_interest(
    system_id: int,
    kill: ProcessedKill | None = None,
) -> InterestScore:
    """
    Calculate unified interest score for a system/kill combination.

    The score is the maximum across all layers, optionally boosted
    by pattern-based escalation multipliers.
    """
    scores = []

    # Layer 1: Geographic (existing logic, refined)
    geo_score = self.geographic_layer.score(system_id)
    scores.append(LayerScore("geographic", geo_score))

    # Layer 2: Entity (if kill provided)
    if kill:
        entity_score = self.entity_layer.score(kill)
        scores.append(LayerScore("entity", entity_score))

    # Layer 3: Route
    route_score = self.route_layer.score(system_id, kill)
    scores.append(LayerScore("route", route_score))

    # Layer 4: Asset
    asset_score = self.asset_layer.score(system_id)
    scores.append(LayerScore("asset", asset_score))

    # Base interest = max of all layers
    base_interest = max(s.score for s in scores)
    dominant_layer = max(scores, key=lambda s: s.score).layer

    # Layer 5: Pattern escalation (multiplier, not additive)
    escalation = self.pattern_layer.get_escalation(system_id)

    final_interest = min(base_interest * escalation.multiplier, 1.0)

    return InterestScore(
        system_id=system_id,
        interest=final_interest,
        base_interest=base_interest,
        dominant_layer=dominant_layer,
        layer_scores=scores,
        escalation=escalation,
    )
```

---

## Layer Design

### Layer 1: Geographic (Refined)

Extends current BFS expansion with security-aware weighting.

**Current behavior:**
```python
weights = {"operational": 1.0, "hop_1": 1.0, "hop_2": 0.7}
```

**Proposed enhancement:** Differentiate by system classification:

```python
@dataclass
class GeographicConfig:
    """Per-classification hop weights."""

    # Home systems (staging, HQ)
    home_weights: dict[int, float] = field(default_factory=lambda: {
        0: 1.0,   # Home system itself
        1: 0.95,  # Immediate neighbors
        2: 0.8,   # 2-hop
        3: 0.5,   # 3-hop (new)
    })

    # Hunting grounds (systems you actively roam)
    hunting_weights: dict[int, float] = field(default_factory=lambda: {
        0: 1.0,
        1: 0.85,
        2: 0.5,
        3: 0.0,
    })

    # Transit waypoints (passing through, not dwelling)
    transit_weights: dict[int, float] = field(default_factory=lambda: {
        0: 0.7,
        1: 0.3,
        2: 0.0,
    })
```

**Configuration:**

```yaml
geographic:
  systems:
    - name: Tama
      classification: home
    - name: Kedama
      classification: hunting
    - name: Nourvukaiken
      classification: transit
```

**Rationale:** Your home constellation matters more than a system you pass through. Uniform weighting doesn't capture this.

---

### Layer 2: Entity-Based Interest

**Critical addition:** Interest based on *who* is involved, not just *where*.

```python
@dataclass
class EntityLayerConfig:
    """Entity relationship weights."""

    # Corp member is victim
    corp_member_victim: float = 1.0      # ALWAYS NOTIFY

    # Corp member is attacker (we got a kill)
    corp_member_attacker: float = 0.9

    # Alliance member involved
    alliance_member: float = 0.8

    # War target (attacker or victim)
    war_target: float = 0.95

    # Watchlist entity (manually tracked corps/alliances)
    watchlist_entity: float = 0.9

    # Blue standing (friendly)
    blue_standing: float = 0.6

    # Neutral in home space (potential threat)
    neutral_in_home: float = 0.7
```

**Implementation:**

```python
class EntityLayer:
    """Calculates interest based on entity relationships."""

    def __init__(
        self,
        config: EntityLayerConfig,
        corp_id: int,
        alliance_id: int | None,
        watchlist: EntityWatchlist,
        war_targets: set[int],
    ):
        self.config = config
        self.corp_id = corp_id
        self.alliance_id = alliance_id
        self.watchlist = watchlist
        self.war_targets = war_targets

    def score(self, kill: ProcessedKill) -> float:
        """
        Calculate entity-based interest for a kill.

        Returns highest matching relationship score.
        """
        scores = []

        # Check victim
        if kill.victim_corporation_id == self.corp_id:
            scores.append(self.config.corp_member_victim)
        elif kill.victim_alliance_id == self.alliance_id:
            scores.append(self.config.alliance_member)
        elif kill.victim_corporation_id in self.war_targets:
            scores.append(self.config.war_target)
        elif self.watchlist.is_watched(kill.victim_corporation_id):
            scores.append(self.config.watchlist_entity)

        # Check attackers
        for attacker_corp in kill.attacker_corps:
            if attacker_corp == self.corp_id:
                scores.append(self.config.corp_member_attacker)
            elif attacker_corp in self.war_targets:
                scores.append(self.config.war_target)
            elif self.watchlist.is_watched(attacker_corp):
                scores.append(self.config.watchlist_entity)

        return max(scores) if scores else 0.0
```

**Critical behavior:** `corp_member_victim: 1.0` ensures **all corp member losses are notified**, regardless of location. This is the most important change for corp operations.

---

### Layer 3: Route-Based Interest

Define named routes; all systems along the route are high-interest.

```python
@dataclass
class RouteDefinition:
    """A named route with optional ship type filtering."""

    name: str
    waypoints: list[str]          # System names
    interest: float = 0.95        # Interest for route systems
    ship_filter: list[str] | None = None  # Only notify for these ship types
    bidirectional: bool = True    # Both directions, or origin→dest only


class RouteLayer:
    """Calculates interest based on route membership."""

    def __init__(
        self,
        routes: list[RouteDefinition],
        universe_graph: UniverseGraph,
    ):
        self.routes = routes
        self.graph = universe_graph
        self._route_systems: dict[str, set[int]] = {}
        self._build_route_systems()

    def _build_route_systems(self) -> None:
        """Pre-compute all systems along each route."""
        for route in self.routes:
            systems = set()
            for i in range(len(route.waypoints) - 1):
                origin = route.waypoints[i]
                dest = route.waypoints[i + 1]
                path = self.graph.shortest_path(origin, dest)
                systems.update(self.graph.resolve_ids(path))
            self._route_systems[route.name] = systems

    def score(
        self,
        system_id: int,
        kill: ProcessedKill | None = None,
    ) -> float:
        """
        Calculate route-based interest.

        Returns interest if system is on any route and kill matches
        ship filter (if configured).
        """
        for route in self.routes:
            if system_id not in self._route_systems[route.name]:
                continue

            # Check ship filter if configured
            if route.ship_filter and kill:
                ship_name = self._resolve_ship_name(kill.victim_ship_type_id)
                if not self._matches_filter(ship_name, route.ship_filter):
                    continue

            return route.interest

        return 0.0
```

**Configuration:**

```yaml
routes:
  jita_logistics:
    waypoints: [Tama, Nourvukaiken, Jita]
    interest: 0.95
    ship_filter: [Freighter, Industrial, Transport Ship, Blockade Runner]

  fw_roam:
    waypoints: [Tama, Sujarento, Nennamaila, Aivonen]
    interest: 0.85
    ship_filter: null  # All ships

  escape_route:
    waypoints: [Tama, Ishomilken, Mara]
    interest: 0.7
    bidirectional: true
```

**Use case:** A hauler corp cares about Uedama even if it's 15 jumps from their home—because every freighter passes through it. Route-based interest captures this.

---

### Layer 4: Asset-Based Interest

Auto-include systems containing corp assets.

```python
@dataclass
class AssetLayerConfig:
    """Asset types that generate interest."""

    structures: bool = True       # Corp structures (Raitaru, Azbel, etc.)
    offices: bool = True          # Corp offices in NPC stations
    clones: bool = False          # Member jump clone locations (optional)
    pos: bool = False             # Legacy POS (rarely relevant)

    structure_interest: float = 1.0
    office_interest: float = 0.8
    clone_interest: float = 0.6


class AssetLayer:
    """Calculates interest based on corp asset locations."""

    def __init__(
        self,
        config: AssetLayerConfig,
        esi_client: ESIClient,
        corp_id: int,
    ):
        self.config = config
        self.esi = esi_client
        self.corp_id = corp_id
        self._asset_systems: dict[int, str] = {}  # system_id → asset_type
        self._last_refresh: float = 0

    async def refresh_assets(self) -> None:
        """
        Refresh corp asset locations from ESI.

        Should be called periodically (e.g., hourly) or on demand.
        """
        systems = {}

        if self.config.structures:
            structures = await self.esi.get_corp_structures(self.corp_id)
            for s in structures:
                systems[s.solar_system_id] = "structure"

        if self.config.offices:
            # ESI endpoint for corp assets, filter to offices
            offices = await self.esi.get_corp_offices(self.corp_id)
            for o in offices:
                if o.solar_system_id not in systems:
                    systems[o.solar_system_id] = "office"

        self._asset_systems = systems
        self._last_refresh = time.time()

    def score(self, system_id: int) -> float:
        """Calculate asset-based interest for a system."""
        asset_type = self._asset_systems.get(system_id)

        if asset_type == "structure":
            return self.config.structure_interest
        elif asset_type == "office":
            return self.config.office_interest

        return 0.0
```

**Use case:** A wormhole corp's Raitaru system is automatically highest priority. An industrial corp's Azbel system gets full attention even if it's not explicitly configured.

**Refresh strategy:**
- On poller startup
- Every 4 hours (structures don't move often)
- On explicit refresh command (`aria-esi topology-refresh`)

---

### Layer 5: Pattern-Based Escalation

Activity patterns boost interest via a multiplier (not additive).

```python
@dataclass
class PatternEscalation:
    """Escalation state for a system."""

    multiplier: float = 1.0
    reason: str | None = None
    expires_at: float | None = None


class PatternLayer:
    """Tracks activity patterns and provides escalation multipliers."""

    # Thresholds
    GATECAMP_THRESHOLD_KILLS = 3
    GATECAMP_THRESHOLD_MINUTES = 10
    SPIKE_MULTIPLIER_THRESHOLD = 2.0  # 2x historical average

    # Multipliers
    GATECAMP_MULTIPLIER = 1.5
    SPIKE_MULTIPLIER = 1.3
    SUSTAINED_ACTIVITY_MULTIPLIER = 1.2

    def __init__(self, threat_cache: ThreatCache):
        self.cache = threat_cache
        self._escalations: dict[int, PatternEscalation] = {}

    def get_escalation(self, system_id: int) -> PatternEscalation:
        """
        Get current escalation state for a system.

        Recalculates if expired or missing.
        """
        cached = self._escalations.get(system_id)
        if cached and cached.expires_at and cached.expires_at > time.time():
            return cached

        return self._calculate_escalation(system_id)

    def _calculate_escalation(self, system_id: int) -> PatternEscalation:
        """Calculate escalation based on recent activity patterns."""
        recent_kills = self.cache.get_recent_kills(
            system_id=system_id,
            since_minutes=self.GATECAMP_THRESHOLD_MINUTES,
        )

        # Check for gatecamp pattern
        if len(recent_kills) >= self.GATECAMP_THRESHOLD_KILLS:
            # Additional gatecamp heuristics (from existing algorithm)
            if self._is_likely_gatecamp(recent_kills):
                escalation = PatternEscalation(
                    multiplier=self.GATECAMP_MULTIPLIER,
                    reason="Active gatecamp detected",
                    expires_at=time.time() + 300,  # 5 min expiry
                )
                self._escalations[system_id] = escalation
                return escalation

        # Check for activity spike
        historical_avg = self.cache.get_historical_avg(system_id)
        hourly_kills = self.cache.get_recent_kills(
            system_id=system_id,
            since_minutes=60,
        )

        if historical_avg > 0:
            spike_ratio = len(hourly_kills) / historical_avg
            if spike_ratio >= self.SPIKE_MULTIPLIER_THRESHOLD:
                escalation = PatternEscalation(
                    multiplier=self.SPIKE_MULTIPLIER,
                    reason=f"Activity spike ({spike_ratio:.1f}x normal)",
                    expires_at=time.time() + 600,  # 10 min expiry
                )
                self._escalations[system_id] = escalation
                return escalation

        # No escalation
        return PatternEscalation(multiplier=1.0)
```

**Integration with existing gatecamp detection:** This layer reuses the gatecamp detection logic from Phase 2, applying it as an interest multiplier rather than a separate trigger.

---

## Configuration Presets

### Archetype Profiles

Provide preset configurations for common corp types:

```python
ARCHETYPE_PRESETS = {
    "hunter": {
        "description": "FW/Piracy corps focused on PvP",
        "geographic": {
            "home_systems": [],  # User configures
            "hunting_systems": [],
            "hop_weights": {"home": {0: 1.0, 1: 0.9, 2: 0.7}, "hunting": {0: 1.0, 1: 0.8, 2: 0.4}},
        },
        "entity": {
            "show_neutral_kills": True,
            "war_target_interest": 0.95,
        },
        "patterns": {
            "gatecamp_detection": True,
            "activity_spike_detection": True,
        },
    },

    "sovereignty": {
        "description": "Null-sec corps with sov holdings",
        "geographic": {
            "home_constellation": None,  # User configures
            "hop_weights": {"home": {0: 1.0, 1: 0.85, 2: 0.6, 3: 0.3}},
        },
        "entity": {
            "alliance_intel": True,
            "hostile_alliances": [],  # User configures
        },
        "assets": {
            "structures": True,
            "sov_systems": True,
        },
        "patterns": {
            "capital_kills_escalate": True,
        },
    },

    "industrial": {
        "description": "Industry/trade focused corps",
        "geographic": {
            "home_systems": [],
            "hop_weights": {"home": {0: 1.0, 1: 0.5, 2: 0.2}},  # Tight radius
        },
        "routes": [],  # User configures trade routes
        "entity": {
            "corp_losses_always": True,
            "war_targets": True,
        },
        "patterns": {
            "gank_detection": True,  # Catalyst swarms
        },
    },

    "wormhole": {
        "description": "W-space corps",
        "assets": {
            "structures": True,  # Auto-detect hole
            "structure_interest": 1.0,
        },
        "entity": {
            "corp_losses_always": True,
        },
        "kspace_exits": {
            "enabled": True,  # Track k-space exit security
            "min_exit_interest": 0.6,
        },
    },
}
```

### Configuration Example

Full configuration for an FW corp:

```json
{
  "redisq": {
    "topology": {
      "enabled": true,
      "archetype": "hunter",

      "geographic": {
        "systems": [
          {"name": "Tama", "classification": "home"},
          {"name": "Kedama", "classification": "hunting"},
          {"name": "Sujarento", "classification": "hunting"}
        ]
      },

      "entity": {
        "corp_id": 98000001,
        "alliance_id": 99000001,
        "watchlist_corps": [98506879, 98326526],
        "auto_sync_war_targets": true
      },

      "routes": [
        {
          "name": "jita_logistics",
          "waypoints": ["Tama", "Nourvukaiken", "Jita"],
          "ship_filter": ["Freighter", "Transport Ship"]
        }
      ],

      "assets": {
        "structures": true,
        "offices": true,
        "refresh_hours": 4
      },

      "patterns": {
        "gatecamp_detection": true,
        "spike_threshold": 2.0,
        "gatecamp_multiplier": 1.5
      }
    }
  }
}
```

---

## Notification Behavior

### Interest-Based Notification Tiers

Rather than binary pass/fail, use interest scores to drive notification behavior:

| Interest Score | Behavior |
|----------------|----------|
| 0.0 | Filter out (no ESI fetch) |
| 0.0 - 0.3 | Log only (debug, no notification) |
| 0.3 - 0.6 | Digest mode (batch into summaries) |
| 0.6 - 0.8 | Standard notification |
| 0.8 - 1.0 | Priority notification (commentary warranted) |
| 1.0 (corp member loss) | Immediate priority notification |

### Digest Mode

For systems with interest 0.3-0.6, batch kills into periodic summaries:

```
📊 Activity Summary (Last 15 min)
├─ Aunsou: 3 kills (SAFETY. gank rotation)
├─ Bherdasopt: 1 kill (neutral traffic)
└─ Dodixie: 2 kills (market PvP)
```

**Rationale:** Not every kill needs individual attention. Lower-interest systems contribute to situational awareness without notification spam.

### Priority Escalation

When pattern layer applies escalation multiplier:

```
🚨 PRIORITY: Tama
Gatecamp forming on Nourvukaiken gate
3 kills in 8 minutes • Snuffed Out (12 pilots)
Last kill: Proteus (4.2B ISK)

⚠️ This is on your Jita logistics route.
```

---

## Implementation Phases

### Phase 7A: Interest Calculator Core

**Goal:** Implement the multi-layer interest calculation framework.

**Deliverables:**
- [ ] `InterestCalculator` class with layer architecture
- [ ] `InterestScore` model with layer breakdown
- [ ] Layer interface (`BaseInterestLayer`)
- [ ] Unit tests for calculation logic

**Complexity:** Medium

**Files:**
- `src/aria_esi/services/redisq/interest/calculator.py` (new)
- `src/aria_esi/services/redisq/interest/models.py` (new)
- `src/aria_esi/services/redisq/interest/layers/base.py` (new)
- `tests/services/redisq/interest/test_calculator.py` (new)

### Phase 7B: Geographic Layer Refinement

**Goal:** Enhance existing geographic layer with classification support.

**Deliverables:**
- [ ] System classification (home/hunting/transit)
- [ ] Per-classification hop weights
- [ ] Migration from flat `operational_systems` to classified systems
- [ ] Backward compatibility with existing config

**Complexity:** Low-Medium

**Files:**
- `src/aria_esi/services/redisq/interest/layers/geographic.py` (new)
- `src/aria_esi/services/redisq/topology.py` (modify for compatibility)

### Phase 7C: Entity Layer

**Goal:** Implement entity-based interest calculation.

**Deliverables:**
- [ ] `EntityLayer` class with relationship scoring
- [ ] Integration with existing `EntityWatchlist`
- [ ] War target auto-sync from ESI
- [ ] Corp/alliance membership resolution
- [ ] **Corp member losses always notify** behavior

**Complexity:** Medium

**Dependencies:** Requires corp_id/alliance_id configuration

**Files:**
- `src/aria_esi/services/redisq/interest/layers/entity.py` (new)
- `tests/services/redisq/interest/test_entity_layer.py` (new)

### Phase 7D: Route Layer

**Goal:** Implement route-based interest with ship type filtering.

**Deliverables:**
- [ ] `RouteLayer` class with route membership scoring
- [ ] Named route configuration
- [ ] Ship type filtering per route
- [ ] Route pre-computation using universe graph
- [ ] CLI command to visualize routes

**Complexity:** Medium

**Files:**
- `src/aria_esi/services/redisq/interest/layers/route.py` (new)
- `tests/services/redisq/interest/test_route_layer.py` (new)

### Phase 7E: Asset Layer

**Goal:** Auto-include systems with corp assets.

**Deliverables:**
- [ ] `AssetLayer` class with ESI integration
- [ ] Structure location tracking
- [ ] Office location tracking
- [ ] Periodic refresh logic
- [ ] Manual refresh CLI command

**Complexity:** Medium

**ESI Scopes Required:**
- `esi-corporations.read_structures.v1`
- `esi-corporations.read_corporation_membership.v1`

**Files:**
- `src/aria_esi/services/redisq/interest/layers/asset.py` (new)
- `tests/services/redisq/interest/test_asset_layer.py` (new)

### Phase 7F: Pattern Escalation Layer

**Goal:** Integrate pattern detection as interest multiplier.

**Deliverables:**
- [ ] `PatternLayer` class with escalation logic
- [ ] Integration with existing gatecamp detection
- [ ] Activity spike detection
- [ ] Escalation expiry and refresh
- [ ] Metrics for escalation frequency

**Complexity:** Low (mostly integration)

**Files:**
- `src/aria_esi/services/redisq/interest/layers/pattern.py` (new)
- `tests/services/redisq/interest/test_pattern_layer.py` (new)

### Phase 7G: Topology Filter Migration

**Goal:** Replace binary topology filter with interest-based filtering.

**Deliverables:**
- [ ] Modify `TopologyFilter` to use `InterestCalculator`
- [ ] Implement interest tiers (filter/log/digest/notify/priority)
- [ ] Update notification manager for tiered behavior
- [ ] Digest mode implementation
- [ ] Backward compatibility with existing config

**Complexity:** Medium

**Files:**
- `src/aria_esi/services/redisq/topology.py` (modify)
- `src/aria_esi/services/redisq/notifications/manager.py` (modify)

### Phase 7H: Archetype Presets & CLI

**Goal:** User-friendly configuration with presets.

**Deliverables:**
- [ ] Archetype preset definitions
- [ ] CLI wizard for initial configuration (`aria-esi topology-setup`)
- [ ] Route visualization command (`aria-esi topology-routes`)
- [ ] Interest debugging command (`aria-esi topology-explain <system>`)
- [ ] Documentation: `docs/CONTEXT_AWARE_TOPOLOGY.md`

**Complexity:** Low-Medium

**Files:**
- `src/aria_esi/services/redisq/interest/presets.py` (new)
- `src/aria_esi/commands/redisq.py` (extend)
- `docs/CONTEXT_AWARE_TOPOLOGY.md` (new)

---

## Data Model Extensions

### Enhanced InterestMap

```python
@dataclass
class EnhancedInterestMap:
    """
    Extended interest map with multi-layer scoring.

    Replaces the current InterestMap while maintaining
    backward compatibility.
    """

    # Layer configurations
    geographic_config: GeographicLayerConfig
    entity_config: EntityLayerConfig
    route_config: RouteLayerConfig
    asset_config: AssetLayerConfig
    pattern_config: PatternLayerConfig

    # Pre-computed layer data
    geographic_systems: dict[int, float]      # system_id → base interest
    route_systems: dict[str, set[int]]        # route_name → system_ids
    asset_systems: dict[int, str]             # system_id → asset_type

    # Runtime state
    pattern_escalations: dict[int, PatternEscalation]

    # Metadata
    built_at: float
    version: str = "2.0"
    archetype: str | None = None

    def get_interest(
        self,
        system_id: int,
        kill: ProcessedKill | None = None,
    ) -> InterestScore:
        """Calculate full interest score for system/kill."""
        # ... implementation
```

### Configuration Schema

```python
@dataclass
class ContextAwareTopologyConfig:
    """Full configuration for context-aware topology."""

    enabled: bool = False
    archetype: str | None = None  # "hunter", "sovereignty", "industrial", "wormhole"

    # Layer configs
    geographic: GeographicLayerConfig = field(default_factory=GeographicLayerConfig)
    entity: EntityLayerConfig = field(default_factory=EntityLayerConfig)
    routes: list[RouteDefinition] = field(default_factory=list)
    assets: AssetLayerConfig = field(default_factory=AssetLayerConfig)
    patterns: PatternLayerConfig = field(default_factory=PatternLayerConfig)

    # Notification tiers
    filter_threshold: float = 0.0       # Below this: don't fetch
    log_threshold: float = 0.3          # Below this: log only
    digest_threshold: float = 0.6       # Below this: batch into digests
    priority_threshold: float = 0.8     # Above this: priority notification

    @classmethod
    def from_archetype(cls, archetype: str) -> "ContextAwareTopologyConfig":
        """Create config from archetype preset."""
        preset = ARCHETYPE_PRESETS.get(archetype)
        if not preset:
            raise ValueError(f"Unknown archetype: {archetype}")
        return cls(**preset, archetype=archetype)
```

---

## Testing Strategy

### Unit Tests

**Interest Calculator:**
```python
def test_max_layer_wins():
    """Interest is max of layer scores, not sum."""
    calculator = InterestCalculator(config)

    # System has low geographic interest but high entity interest
    kill = make_kill(victim_corp=OUR_CORP_ID)
    score = calculator.calculate_interest(system_id=999, kill=kill)

    assert score.interest == 1.0  # Corp member loss
    assert score.dominant_layer == "entity"

def test_corp_member_loss_always_notifies():
    """Corp member losses get max interest regardless of location."""
    calculator = InterestCalculator(config)

    # System not in any layer
    kill = make_kill(
        system_id=30000142,  # Jita (not configured)
        victim_corp=OUR_CORP_ID,
    )
    score = calculator.calculate_interest(kill.solar_system_id, kill)

    assert score.interest == 1.0
    assert score.dominant_layer == "entity"

def test_route_with_ship_filter():
    """Route interest only applies when ship type matches filter."""
    calculator = InterestCalculator(config_with_freighter_route)

    # Frigate on logistics route - should not match
    frigate_kill = make_kill(ship_type_id=587)  # Rifter
    score = calculator.calculate_interest(ROUTE_SYSTEM, frigate_kill)
    assert score.layer_scores["route"] == 0.0

    # Freighter on logistics route - should match
    freighter_kill = make_kill(ship_type_id=20185)  # Charon
    score = calculator.calculate_interest(ROUTE_SYSTEM, freighter_kill)
    assert score.layer_scores["route"] == 0.95
```

**Pattern Escalation:**
```python
def test_gatecamp_escalation():
    """Gatecamp pattern applies multiplier."""
    layer = PatternLayer(threat_cache_with_gatecamp)

    escalation = layer.get_escalation(GATECAMP_SYSTEM)

    assert escalation.multiplier == 1.5
    assert "gatecamp" in escalation.reason.lower()

def test_escalation_expires():
    """Escalation returns to 1.0 after expiry."""
    layer = PatternLayer(threat_cache)

    # Force expired escalation
    layer._escalations[SYSTEM] = PatternEscalation(
        multiplier=1.5,
        expires_at=time.time() - 100,
    )

    escalation = layer.get_escalation(SYSTEM)
    assert escalation.multiplier == 1.0
```

### Integration Tests

```python
@pytest.mark.integration
async def test_full_interest_pipeline():
    """End-to-end test of interest calculation and notification."""
    config = load_test_config()
    calculator = InterestCalculator(config)

    # Corp member loss in distant system
    kill = make_kill(
        system_id=30003458,  # Far from configured systems
        victim_corp=config.entity.corp_id,
    )

    score = calculator.calculate_interest(kill.solar_system_id, kill)

    assert score.interest == 1.0
    assert score.dominant_layer == "entity"

    # Should trigger priority notification
    with patch_discord_webhook() as mock:
        await notification_manager.process_kill(kill)

    assert mock.called
    payload = mock.call_args[1]["json"]
    assert "PRIORITY" in payload["embeds"][0]["title"]

@pytest.mark.integration
async def test_archetype_preset_loads():
    """Archetype presets produce valid configurations."""
    for archetype in ["hunter", "sovereignty", "industrial", "wormhole"]:
        config = ContextAwareTopologyConfig.from_archetype(archetype)
        calculator = InterestCalculator(config)

        # Should not raise
        score = calculator.calculate_interest(30000142, None)
        assert isinstance(score, InterestScore)
```

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Corp member loss coverage | 100% | All corp losses generate notifications |
| War target detection rate | >95% | Kills involving war targets are notified |
| Route coverage accuracy | 100% | All waypoint systems included |
| False negative rate (interesting kills missed) | <5% | Manual review of filtered kills |
| Notification volume change | -20% to +10% | Compared to geographic-only baseline |
| Configuration time (new corp) | <10 minutes | Using archetype wizard |
| Interest calculation latency | <10ms p99 | Inline with kill processing |

---

## Alternatives Considered

### Alternative 1: Machine Learning Interest Prediction

**Approach:** Train a model to predict kill relevance based on historical user engagement.

**Pros:**
- Could capture complex patterns automatically
- Adapts to individual corp preferences

**Cons:**
- Requires significant training data
- Black box (hard to explain why something was/wasn't interesting)
- Cold start problem for new corps
- Overkill for well-understood domain

**Decision:** Rejected. Explicit layer rules are more predictable and debuggable.

### Alternative 2: Full Real-Time ESI Polling

**Approach:** Poll ESI for all relevant data (wars, structures, corp members) in real-time.

**Pros:**
- Always up-to-date
- No stale data

**Cons:**
- ESI rate limits would be problematic
- Significant latency for cache refreshes
- Most data changes infrequently

**Decision:** Rejected. Periodic refresh (4h for assets) is sufficient.

### Alternative 3: Per-Pilot Topology

**Approach:** Each pilot has their own topology configuration.

**Pros:**
- Maximum personalization
- Pilots can customize without affecting corp

**Cons:**
- Doesn't match corp use case (shared intel)
- Duplication of war targets, routes, etc.
- Management overhead

**Decision:** Rejected for this proposal. Corps need unified intel. Individual pilots already have watchlists.

---

## Migration Path

### From Current Topology

Existing configurations will continue to work:

```json
// Old format (still supported)
{
  "redisq": {
    "topology": {
      "enabled": true,
      "operational_systems": ["Simela", "Masalle"],
      "interest_weights": {"operational": 1.0, "hop_1": 1.0, "hop_2": 0.7}
    }
  }
}
```

Internally converted to:

```json
// Equivalent new format
{
  "redisq": {
    "topology": {
      "enabled": true,
      "geographic": {
        "systems": [
          {"name": "Simela", "classification": "home"},
          {"name": "Masalle", "classification": "home"}
        ]
      }
    }
  }
}
```

### Migration CLI

```bash
# Check current config and suggest upgrades
uv run aria-esi topology-migrate --dry-run

# Apply migration
uv run aria-esi topology-migrate

# Interactive setup with archetype selection
uv run aria-esi topology-setup
```

---

## Summary

| Aspect | Current | Proposed |
|--------|---------|----------|
| **Interest model** | Geographic distance only | Multi-layer: geo + entity + route + asset + pattern |
| **Corp member losses** | Only in topology | **Always notify** |
| **War target tracking** | Manual watchlist | Automatic interest boost |
| **Route awareness** | None | Named routes with ship filters |
| **Asset proximity** | None | Auto-include structure systems |
| **Pattern integration** | Separate system | Unified escalation multipliers |
| **Configuration** | Flat system list | Archetype presets + customization |
| **Notification tiers** | Binary (pass/fail) | Five tiers (filter/log/digest/notify/priority) |

Context-aware topology transforms ARIA's kill filtering from "is this system nearby?" to "does this kill matter to my corp?" Geographic proximity becomes one signal among many, ensuring that high-priority events—corp member losses, war target activity, route threats—always surface regardless of location.

The layered architecture allows incremental adoption: corps can start with geographic-only (current behavior) and progressively enable entity, route, and asset layers as their needs evolve.
