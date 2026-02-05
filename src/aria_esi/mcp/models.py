"""
Pydantic response models for MCP Universe Server.

These models define the API contract between the MCP server and Claude,
providing type-safe, serializable responses for all universe query tools.

STP-002: Response Models
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Type Aliases for Tool Parameters
# =============================================================================

SecurityFilter = Literal["highsec", "lowsec", "any"]
"""
Security filter for route and loop planning:
- "highsec": Only traverse high-sec systems (>= 0.45 security)
- "lowsec": Allow low-sec but avoid null-sec
- "any": No security restrictions
"""

VALID_SECURITY_FILTERS: set[str] = {"highsec", "lowsec", "any"}

OptimizeMode = Literal["density", "coverage"]
"""
Optimization mode for loop planning:
- "density": Pack as many borders as possible within jump budget (default)
- "coverage": Select spatially diverse borders for geographic spread
"""

VALID_OPTIMIZE_MODES: set[str] = {"density", "coverage"}


class MCPModel(BaseModel):
    """
    Base model with MCP-friendly serialization.

    Configuration:
    - frozen: Prevents accidental mutation, enables hashing
    - extra="forbid": Catches typos in field names during construction
    - ser_json_inf_nan="constants": Serializes inf/nan as JSON constants
    """

    model_config = ConfigDict(frozen=True, extra="forbid", ser_json_inf_nan="constants")


# =============================================================================
# System Information Models
# =============================================================================


class NeighborInfo(MCPModel):
    """Adjacent system summary for neighbor queries."""

    name: str
    security: float = Field(ge=-1.0, le=1.0)
    security_class: Literal["HIGH", "LOW", "NULL"]


class SovereigntyInfo(MCPModel):
    """Sovereignty information for null-sec systems."""

    alliance_id: int | None = Field(default=None, description="Alliance holding sovereignty")
    alliance_name: str | None = Field(default=None, description="Alliance name with ticker")
    coalition_id: str | None = Field(default=None, description="Coalition ID if alliance is in a coalition")
    coalition_name: str | None = Field(default=None, description="Coalition display name")
    faction_id: int | None = Field(default=None, description="NPC faction ID for NPC null-sec")
    faction_name: str | None = Field(default=None, description="NPC faction name")


class SystemInfo(MCPModel):
    """Complete system information including neighbors and border status."""

    name: str
    system_id: int
    security: float = Field(ge=-1.0, le=1.0)
    security_class: Literal["HIGH", "LOW", "NULL"]
    constellation: str
    constellation_id: int
    region: str
    region_id: int
    neighbors: list[NeighborInfo]
    is_border: bool = Field(description="High-sec system adjacent to low-sec")
    adjacent_lowsec: list[str] = Field(default_factory=list)
    sovereignty: SovereigntyInfo | None = Field(
        default=None, description="Sovereignty info for null-sec systems"
    )


# =============================================================================
# Route Models
# =============================================================================


class SecuritySummary(MCPModel):
    """Security breakdown for a route or system list."""

    total_jumps: int = Field(ge=0)
    highsec_jumps: int = Field(ge=0)
    lowsec_jumps: int = Field(ge=0)
    nullsec_jumps: int = Field(ge=0)
    lowest_security: float = Field(ge=-1.0, le=1.0)
    lowest_security_system: str


class RouteResult(MCPModel):
    """Complete route with full system details and security analysis."""

    origin: str
    destination: str
    mode: Literal["shortest", "safe", "unsafe"]
    jumps: int = Field(ge=0)
    systems: list[SystemInfo]
    security_summary: SecuritySummary
    warnings: list[str] = Field(default_factory=list)
    corrections: dict[str, str] = Field(
        default_factory=dict,
        description="Auto-corrected system names: {input: canonical}",
    )


# =============================================================================
# Border System Models
# =============================================================================


class BorderSystem(MCPModel):
    """Border system with distance and adjacent low-sec information."""

    name: str
    system_id: int
    security: float = Field(ge=-1.0, le=1.0)
    jumps_from_origin: int = Field(ge=0)
    adjacent_lowsec: list[str]
    region: str


class LoopResult(MCPModel):
    """Circular route through multiple border systems."""

    systems: list[SystemInfo]
    total_jumps: int = Field(ge=0)
    unique_systems: int = Field(ge=0)
    border_systems_visited: list[BorderSystem]
    backtrack_jumps: int = Field(ge=0)
    efficiency: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    corrections: dict[str, str] = Field(
        default_factory=dict,
        description="Auto-corrected system names: {input: canonical}",
    )


# =============================================================================
# Route Analysis Models
# =============================================================================


class DangerZone(MCPModel):
    """Consecutive dangerous segment in a route."""

    start_system: str
    end_system: str
    jump_count: int = Field(ge=1)
    min_security: float = Field(ge=-1.0, le=1.0)


class RouteAnalysis(MCPModel):
    """Detailed security analysis of a route with chokepoints and danger zones."""

    systems: list[SystemInfo]
    security_summary: SecuritySummary
    chokepoints: list[SystemInfo] = Field(
        default_factory=list, description="Low-sec entry/exit points"
    )
    danger_zones: list[DangerZone] = Field(
        default_factory=list, description="Consecutive low/null segments"
    )


# =============================================================================
# Search Result Models
# =============================================================================


class SystemSearchResult(MCPModel):
    """System matching search criteria."""

    name: str
    system_id: int
    security: float = Field(ge=-1.0, le=1.0)
    security_class: Literal["HIGH", "LOW", "NULL"]
    region: str
    jumps_from_origin: int | None = None


class BorderSearchResult(MCPModel):
    """Results from a border system search."""

    systems: list[BorderSystem]
    search_origin: str
    max_jumps_searched: int = Field(ge=0)
    total_found: int = Field(ge=0)
    corrections: dict[str, str] = Field(
        default_factory=dict,
        description="Auto-corrected system names: {input: canonical}",
    )


# =============================================================================
# Waypoint Optimization Models
# =============================================================================


class WaypointInfo(MCPModel):
    """Waypoint in an optimized route with visit order."""

    name: str
    system_id: int
    security: float = Field(ge=-1.0, le=1.0)
    security_class: Literal["HIGH", "LOW", "NULL"]
    region: str
    visit_order: int = Field(ge=0, description="Order in optimized route (0-indexed)")


class OptimizedWaypointResult(MCPModel):
    """Result of waypoint optimization (TSP solution)."""

    origin: str | None = Field(
        description="Starting system if specified, null for pure waypoint optimization"
    )
    waypoints: list[WaypointInfo] = Field(description="Waypoints in optimized visit order")
    total_jumps: int = Field(ge=0, description="Total jumps to complete the route")
    route_systems: list[SystemInfo] = Field(description="Full route with all intermediate systems")
    is_loop: bool = Field(description="True if route returns to origin")
    unresolved_waypoints: list[str] = Field(
        default_factory=list, description="Waypoint names that could not be resolved"
    )
    warnings: list[str] = Field(default_factory=list)
    corrections: dict[str, str] = Field(
        default_factory=dict,
        description="Auto-corrected system names: {input: canonical}",
    )


# =============================================================================
# Activity Overlay Models (STP-013)
# =============================================================================

ActivityLevel = Literal["none", "low", "medium", "high", "extreme"]
"""Activity level classification based on kills/jumps/ratting thresholds."""

RiskLevel = Literal["low", "medium", "high", "extreme"]
"""Risk level for gatecamp analysis."""

ChokepointType = Literal["lowsec_entry", "lowsec_exit", "pipe", "hub"]
"""Type of chokepoint in route analysis."""

FWContestedStatus = Literal["uncontested", "contested", "vulnerable"]
"""Faction Warfare contested status."""


class SystemActivity(MCPModel):
    """Activity data for a single system."""

    name: str
    system_id: int
    security: float = Field(ge=-1.0, le=1.0)
    security_class: Literal["HIGH", "LOW", "NULL"]
    ship_kills: int = Field(default=0, ge=0)
    pod_kills: int = Field(default=0, ge=0)
    npc_kills: int = Field(default=0, ge=0)
    ship_jumps: int = Field(default=0, ge=0)
    activity_level: ActivityLevel = "none"


class ActivityResult(MCPModel):
    """Result from universe_activity tool."""

    systems: list[SystemActivity]
    cache_age_seconds: int | None = Field(description="Age of activity data in seconds")
    data_period: str = "last_hour"
    warnings: list[str] = Field(default_factory=list)


class HotspotSystem(MCPModel):
    """A high-activity system from hotspots search."""

    name: str
    system_id: int
    security: float = Field(ge=-1.0, le=1.0)
    security_class: Literal["HIGH", "LOW", "NULL"]
    region: str
    jumps_from_origin: int = Field(ge=0)
    activity_value: int = Field(ge=0)
    activity_level: ActivityLevel


class HotspotsResult(MCPModel):
    """Result from universe_hotspots tool."""

    origin: str
    activity_type: str
    hotspots: list[HotspotSystem]
    search_radius: int = Field(ge=0)
    systems_scanned: int = Field(ge=0)
    cache_age_seconds: int | None
    corrections: dict[str, str] = Field(
        default_factory=dict,
        description="Auto-corrected system names: {input: canonical}",
    )


class GatecampRisk(MCPModel):
    """Risk assessment for a single chokepoint."""

    system: str
    system_id: int
    security: float = Field(ge=-1.0, le=1.0)
    chokepoint_type: ChokepointType
    recent_kills: int = Field(ge=0)
    recent_pods: int = Field(ge=0)
    risk_level: RiskLevel
    warning: str | None = None


class GatecampRiskResult(MCPModel):
    """Result from universe_gatecamp_risk tool."""

    origin: str
    destination: str
    total_jumps: int = Field(ge=0)
    overall_risk: RiskLevel
    chokepoints: list[GatecampRisk]
    high_risk_systems: list[str] = Field(
        default_factory=list,
        description="Systems with risk_level >= high, for avoid_systems param",
    )
    recommendation: str = ""
    cache_age_seconds: int | None
    corrections: dict[str, str] = Field(
        default_factory=dict,
        description="Auto-corrected system names: {input: canonical}",
    )


class FWSystem(MCPModel):
    """Faction Warfare system status."""

    name: str
    system_id: int
    security: float = Field(ge=-1.0, le=1.0)
    region: str
    owner_faction: str
    occupier_faction: str
    contested: FWContestedStatus
    contested_percentage: float = Field(ge=0.0, le=100.0)
    victory_points: int = Field(ge=0)
    victory_points_threshold: int = Field(ge=0)
    recent_kills: int | None = None


class FWFrontlinesResult(MCPModel):
    """Result from fw_frontlines tool."""

    faction_filter: str | None
    contested: list[FWSystem]
    vulnerable: list[FWSystem]
    stable: list[FWSystem]
    summary: dict
    cache_age_seconds: int | None


class CacheLayerStatus(MCPModel):
    """Status of a single cache layer."""

    cached_systems: int = Field(ge=0)
    age_seconds: int | None
    ttl_seconds: int = Field(ge=0)
    stale: bool


class CacheStatusResult(MCPModel):
    """Result from activity_cache_status tool."""

    kills: CacheLayerStatus
    jumps: CacheLayerStatus
    fw: CacheLayerStatus


# =============================================================================
# Local Area / Orient Models (STP-014)
# =============================================================================

ThreatLevel = Literal["LOW", "MEDIUM", "HIGH", "EXTREME"]
"""Threat level classification for local area assessment."""

BorderType = Literal["null_to_low", "low_to_high", "high_to_low", "low_to_null"]
"""Security transition type at a border."""

EscapeDestinationType = Literal["lowsec", "highsec", "npc_station", "trade_hub"]
"""Type of escape destination."""


class ThreatSummary(MCPModel):
    """Aggregated threat assessment for a local area."""

    level: ThreatLevel
    total_kills: int = Field(ge=0, description="Total ship kills in search radius")
    total_pods: int = Field(ge=0, description="Total pod kills in search radius")
    active_camps: list[str] = Field(
        default_factory=list, description="System names with detected gatecamps"
    )
    hotspot_count: int = Field(ge=0, description="Number of high-activity systems")


class LocalSystemActivity(MCPModel):
    """Activity data for a system in local area context."""

    system: str
    system_id: int
    security: float = Field(ge=-1.0, le=1.0)
    security_class: Literal["HIGH", "LOW", "NULL"]
    region: str
    jumps: int = Field(ge=0, description="Distance from origin")
    ship_kills: int = Field(default=0, ge=0)
    pod_kills: int = Field(default=0, ge=0)
    npc_kills: int = Field(default=0, ge=0)
    ship_jumps: int = Field(default=0, ge=0)
    activity_level: ActivityLevel = "none"
    reason: str | None = Field(
        default=None, description="Classification reason: 'gatecamp', 'ratting bank', etc."
    )


class EscapeRoute(MCPModel):
    """An escape route to safer space."""

    destination: str = Field(description="Destination system name")
    destination_type: EscapeDestinationType
    jumps: int = Field(ge=0, description="Total jumps to destination")
    via_system: str | None = Field(
        default=None, description="First waypoint system (border crossing)"
    )
    route_security: Literal["highsec", "lowsec", "mixed"] = Field(
        default="mixed", description="Security profile of the route"
    )


class SecurityBorder(MCPModel):
    """A security transition point in the local area."""

    system: str
    system_id: int
    security: float = Field(ge=-1.0, le=1.0)
    jumps: int = Field(ge=0, description="Distance from origin")
    border_type: BorderType
    adjacent_system: str = Field(description="The system on the other side of the border")
    adjacent_security: float = Field(ge=-1.0, le=1.0)


class LocalAreaResult(MCPModel):
    """Complete local area intelligence for orient command."""

    origin: str
    origin_id: int
    security: float = Field(ge=-1.0, le=1.0)
    security_class: Literal["HIGH", "LOW", "NULL"]
    region: str
    constellation: str

    threat_summary: ThreatSummary
    hotspots: list[LocalSystemActivity] = Field(
        default_factory=list, description="High PvP activity systems to avoid or hunt"
    )
    quiet_zones: list[LocalSystemActivity] = Field(
        default_factory=list, description="Low/zero activity systems for stealth ops"
    )
    ratting_banks: list[LocalSystemActivity] = Field(
        default_factory=list, description="High NPC kill systems indicating ratting activity"
    )
    escape_routes: list[EscapeRoute] = Field(
        default_factory=list, description="Routes to safer space"
    )
    borders: list[SecurityBorder] = Field(
        default_factory=list, description="Security transition points"
    )

    systems_scanned: int = Field(ge=0)
    search_radius: int = Field(ge=0)
    cache_age_seconds: int | None = Field(
        default=None, description="Age of activity data in seconds"
    )
    realtime_healthy: bool = Field(
        default=False, description="Whether real-time gatecamp detection was available"
    )
    warnings: list[str] = Field(default_factory=list)
    corrections: dict[str, str] = Field(
        default_factory=dict,
        description="Auto-corrected system names: {input: canonical}",
    )
