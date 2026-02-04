"""
Tests for MCP Pydantic response models.

STP-002: Response Models Tests
"""

import pytest
from pydantic import ValidationError

from aria_esi.mcp.models import (
    BorderSearchResult,
    BorderSystem,
    DangerZone,
    LoopResult,
    NeighborInfo,
    RouteAnalysis,
    RouteResult,
    SecuritySummary,
    SystemInfo,
    SystemSearchResult,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def neighbor_info() -> NeighborInfo:
    """Create a sample NeighborInfo."""
    return NeighborInfo(name="Perimeter", security=0.9, security_class="HIGH")


@pytest.fixture
def system_info(neighbor_info: NeighborInfo) -> SystemInfo:
    """Create a sample SystemInfo."""
    return SystemInfo(
        name="Jita",
        system_id=30000142,
        security=0.95,
        security_class="HIGH",
        constellation="Kimotoro",
        constellation_id=20000020,
        region="The Forge",
        region_id=10000002,
        neighbors=[neighbor_info],
        is_border=False,
        adjacent_lowsec=[],
    )


@pytest.fixture
def security_summary() -> SecuritySummary:
    """Create a sample SecuritySummary."""
    return SecuritySummary(
        total_jumps=10,
        highsec_jumps=8,
        lowsec_jumps=2,
        nullsec_jumps=0,
        lowest_security=0.3,
        lowest_security_system="Sivala",
    )


@pytest.fixture
def border_system() -> BorderSystem:
    """Create a sample BorderSystem."""
    return BorderSystem(
        name="Uedama",
        system_id=30002768,
        security=0.5,
        jumps_from_origin=5,
        adjacent_lowsec=["Sivala"],
        region="The Citadel",
    )


# =============================================================================
# MCPModel Base Tests
# =============================================================================


class TestMCPModelConfig:
    """Test MCPModel base configuration."""

    def test_frozen_config(self):
        """Models are frozen by default."""
        info = NeighborInfo(name="Jita", security=0.9, security_class="HIGH")
        with pytest.raises(ValidationError):
            info.name = "Amarr"

    def test_extra_forbid(self):
        """Extra fields are forbidden."""
        with pytest.raises(ValidationError):
            NeighborInfo(
                name="Jita", security=0.9, security_class="HIGH", unknown_field="test"
            )


# =============================================================================
# NeighborInfo Tests
# =============================================================================


class TestNeighborInfo:
    """Test NeighborInfo model."""

    def test_valid_construction(self, neighbor_info: NeighborInfo):
        """Valid NeighborInfo constructs correctly."""
        assert neighbor_info.name == "Perimeter"
        assert neighbor_info.security == 0.9
        assert neighbor_info.security_class == "HIGH"

    def test_security_validation_min(self):
        """Security below -1.0 is rejected."""
        with pytest.raises(ValidationError):
            NeighborInfo(name="Test", security=-1.5, security_class="NULL")

    def test_security_validation_max(self):
        """Security above 1.0 is rejected."""
        with pytest.raises(ValidationError):
            NeighborInfo(name="Test", security=1.5, security_class="HIGH")

    def test_security_at_boundaries(self):
        """Security at -1.0 and 1.0 is valid."""
        low = NeighborInfo(name="Low", security=-1.0, security_class="NULL")
        high = NeighborInfo(name="High", security=1.0, security_class="HIGH")
        assert low.security == -1.0
        assert high.security == 1.0

    def test_security_class_literal(self):
        """Only valid security classes accepted."""
        with pytest.raises(ValidationError):
            NeighborInfo(name="Test", security=0.5, security_class="MEDIUM")

    def test_serialization(self, neighbor_info: NeighborInfo):
        """NeighborInfo serializes to JSON."""
        json_str = neighbor_info.model_dump_json()
        assert "Perimeter" in json_str
        assert "0.9" in json_str
        assert "HIGH" in json_str


# =============================================================================
# SystemInfo Tests
# =============================================================================


class TestSystemInfo:
    """Test SystemInfo model."""

    def test_valid_construction(self, system_info: SystemInfo):
        """Valid SystemInfo constructs correctly."""
        assert system_info.name == "Jita"
        assert system_info.system_id == 30000142
        assert system_info.security == 0.95
        assert len(system_info.neighbors) == 1

    def test_nested_serialization(self, system_info: SystemInfo):
        """SystemInfo with nested models serializes correctly."""
        data = system_info.model_dump()
        assert "neighbors" in data
        assert isinstance(data["neighbors"], list)
        assert len(data["neighbors"]) == 1
        assert data["neighbors"][0]["name"] == "Perimeter"

    def test_json_serialization(self, system_info: SystemInfo):
        """SystemInfo serializes to valid JSON."""
        json_str = system_info.model_dump_json()
        assert "Jita" in json_str
        assert "30000142" in json_str
        assert "Kimotoro" in json_str

    def test_default_adjacent_lowsec(self):
        """adjacent_lowsec defaults to empty list."""
        info = SystemInfo(
            name="Jita",
            system_id=30000142,
            security=0.95,
            security_class="HIGH",
            constellation="Kimotoro",
            constellation_id=20000020,
            region="The Forge",
            region_id=10000002,
            neighbors=[],
            is_border=False,
        )
        assert info.adjacent_lowsec == []

    def test_border_system_with_lowsec(self):
        """Border system can have adjacent low-sec."""
        info = SystemInfo(
            name="Uedama",
            system_id=30002768,
            security=0.5,
            security_class="HIGH",
            constellation="Saatuban",
            constellation_id=20000404,
            region="The Citadel",
            region_id=10000033,
            neighbors=[],
            is_border=True,
            adjacent_lowsec=["Sivala", "Haatomo"],
        )
        assert info.is_border is True
        assert len(info.adjacent_lowsec) == 2


# =============================================================================
# SecuritySummary Tests
# =============================================================================


class TestSecuritySummary:
    """Test SecuritySummary model."""

    def test_valid_construction(self, security_summary: SecuritySummary):
        """Valid SecuritySummary constructs correctly."""
        assert security_summary.total_jumps == 10
        assert security_summary.highsec_jumps == 8
        assert security_summary.lowsec_jumps == 2
        assert security_summary.nullsec_jumps == 0

    def test_jump_validation_negative(self):
        """Negative jump counts are rejected."""
        with pytest.raises(ValidationError):
            SecuritySummary(
                total_jumps=-1,
                highsec_jumps=0,
                lowsec_jumps=0,
                nullsec_jumps=0,
                lowest_security=0.5,
                lowest_security_system="Jita",
            )

    def test_serialization(self, security_summary: SecuritySummary):
        """SecuritySummary serializes correctly."""
        data = security_summary.model_dump()
        assert data["total_jumps"] == 10
        assert data["lowest_security_system"] == "Sivala"


# =============================================================================
# RouteResult Tests
# =============================================================================


class TestRouteResult:
    """Test RouteResult model."""

    def test_valid_construction(
        self, system_info: SystemInfo, security_summary: SecuritySummary
    ):
        """Valid RouteResult constructs correctly."""
        route = RouteResult(
            origin="Jita",
            destination="Amarr",
            mode="shortest",
            jumps=10,
            systems=[system_info],
            security_summary=security_summary,
        )
        assert route.origin == "Jita"
        assert route.destination == "Amarr"
        assert route.mode == "shortest"
        assert route.jumps == 10

    def test_mode_validation(
        self, system_info: SystemInfo, security_summary: SecuritySummary
    ):
        """Only valid route modes accepted."""
        with pytest.raises(ValidationError):
            RouteResult(
                origin="Jita",
                destination="Amarr",
                mode="invalid",
                jumps=10,
                systems=[system_info],
                security_summary=security_summary,
            )

    def test_warnings_default(
        self, system_info: SystemInfo, security_summary: SecuritySummary
    ):
        """warnings defaults to empty list."""
        route = RouteResult(
            origin="Jita",
            destination="Amarr",
            mode="safe",
            jumps=10,
            systems=[system_info],
            security_summary=security_summary,
        )
        assert route.warnings == []

    def test_nested_serialization(
        self, system_info: SystemInfo, security_summary: SecuritySummary
    ):
        """Nested models serialize correctly."""
        route = RouteResult(
            origin="Jita",
            destination="Amarr",
            mode="shortest",
            jumps=10,
            systems=[system_info],
            security_summary=security_summary,
            warnings=["Route passes through low-sec"],
        )
        data = route.model_dump()
        assert "security_summary" in data
        assert isinstance(data["security_summary"], dict)
        assert data["security_summary"]["total_jumps"] == 10


# =============================================================================
# BorderSystem Tests
# =============================================================================


class TestBorderSystem:
    """Test BorderSystem model."""

    def test_valid_construction(self, border_system: BorderSystem):
        """Valid BorderSystem constructs correctly."""
        assert border_system.name == "Uedama"
        assert border_system.jumps_from_origin == 5
        assert "Sivala" in border_system.adjacent_lowsec

    def test_serialization(self, border_system: BorderSystem):
        """BorderSystem serializes correctly."""
        json_str = border_system.model_dump_json()
        assert "Uedama" in json_str
        assert "Sivala" in json_str


# =============================================================================
# LoopResult Tests
# =============================================================================


class TestLoopResult:
    """Test LoopResult model."""

    def test_valid_construction(
        self, system_info: SystemInfo, border_system: BorderSystem
    ):
        """Valid LoopResult constructs correctly."""
        loop = LoopResult(
            systems=[system_info],
            total_jumps=20,
            unique_systems=18,
            border_systems_visited=[border_system],
            backtrack_jumps=2,
            efficiency=0.9,
        )
        assert loop.total_jumps == 20
        assert loop.efficiency == 0.9

    def test_efficiency_validation(
        self, system_info: SystemInfo, border_system: BorderSystem
    ):
        """Efficiency must be between 0 and 1."""
        with pytest.raises(ValidationError):
            LoopResult(
                systems=[system_info],
                total_jumps=20,
                unique_systems=18,
                border_systems_visited=[border_system],
                backtrack_jumps=2,
                efficiency=1.5,
            )


# =============================================================================
# DangerZone Tests
# =============================================================================


class TestDangerZone:
    """Test DangerZone model."""

    def test_valid_construction(self):
        """Valid DangerZone constructs correctly."""
        zone = DangerZone(
            start_system="Rancer",
            end_system="Crielere",
            jump_count=3,
            min_security=0.2,
        )
        assert zone.start_system == "Rancer"
        assert zone.jump_count == 3

    def test_jump_count_min(self):
        """jump_count must be at least 1."""
        with pytest.raises(ValidationError):
            DangerZone(
                start_system="Rancer",
                end_system="Crielere",
                jump_count=0,
                min_security=0.2,
            )


# =============================================================================
# RouteAnalysis Tests
# =============================================================================


class TestRouteAnalysis:
    """Test RouteAnalysis model."""

    def test_valid_construction(
        self, system_info: SystemInfo, security_summary: SecuritySummary
    ):
        """Valid RouteAnalysis constructs correctly."""
        analysis = RouteAnalysis(
            systems=[system_info],
            security_summary=security_summary,
        )
        assert len(analysis.systems) == 1
        assert analysis.chokepoints == []
        assert analysis.danger_zones == []

    def test_with_optional_fields(
        self, system_info: SystemInfo, security_summary: SecuritySummary
    ):
        """RouteAnalysis with all optional fields."""
        danger = DangerZone(
            start_system="Rancer",
            end_system="Crielere",
            jump_count=3,
            min_security=0.2,
        )
        analysis = RouteAnalysis(
            systems=[system_info],
            security_summary=security_summary,
            chokepoints=[system_info],
            danger_zones=[danger],
        )
        assert len(analysis.chokepoints) == 1
        assert len(analysis.danger_zones) == 1


# =============================================================================
# SystemSearchResult Tests
# =============================================================================


class TestSystemSearchResult:
    """Test SystemSearchResult model."""

    def test_valid_construction(self):
        """Valid SystemSearchResult constructs correctly."""
        result = SystemSearchResult(
            name="Jita",
            system_id=30000142,
            security=0.95,
            security_class="HIGH",
            region="The Forge",
        )
        assert result.jumps_from_origin is None

    def test_with_distance(self):
        """SystemSearchResult with distance."""
        result = SystemSearchResult(
            name="Jita",
            system_id=30000142,
            security=0.95,
            security_class="HIGH",
            region="The Forge",
            jumps_from_origin=5,
        )
        assert result.jumps_from_origin == 5


# =============================================================================
# BorderSearchResult Tests
# =============================================================================


class TestBorderSearchResult:
    """Test BorderSearchResult model."""

    def test_valid_construction(self, border_system: BorderSystem):
        """Valid BorderSearchResult constructs correctly."""
        result = BorderSearchResult(
            systems=[border_system],
            search_origin="Dodixie",
            max_jumps_searched=15,
            total_found=1,
        )
        assert result.search_origin == "Dodixie"
        assert len(result.systems) == 1


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestModuleExports:
    """Test that all models are exported correctly."""

    def test_all_models_exported(self):
        """All models are exported from mcp module."""
        from aria_esi.mcp import (
            BorderSearchResult,
            BorderSystem,
            DangerZone,
            LoopResult,
            MCPModel,
            NeighborInfo,
            RouteAnalysis,
            RouteResult,
            SecuritySummary,
            SystemInfo,
            SystemSearchResult,
        )

        # Just verify imports work
        assert MCPModel is not None
        assert NeighborInfo is not None
        assert SystemInfo is not None
        assert SecuritySummary is not None
        assert RouteResult is not None
        assert BorderSystem is not None
        assert LoopResult is not None
        assert DangerZone is not None
        assert RouteAnalysis is not None
        assert SystemSearchResult is not None
        assert BorderSearchResult is not None


# =============================================================================
# Additional Model Imports for Extended Tests
# =============================================================================

from aria_esi.mcp.models import (
    ActivityLevel,
    ActivityResult,
    CacheLayerStatus,
    CacheStatusResult,
    ChokepointType,
    EscapeDestinationType,
    EscapeRoute,
    FWContestedStatus,
    FWFrontlinesResult,
    FWSystem,
    GatecampRisk,
    GatecampRiskResult,
    HotspotSystem,
    HotspotsResult,
    LocalAreaResult,
    LocalSystemActivity,
    OptimizedWaypointResult,
    RiskLevel,
    SecurityBorder,
    SystemActivity,
    ThreatLevel,
    ThreatSummary,
    WaypointInfo,
)


# =============================================================================
# WaypointInfo Tests
# =============================================================================


class TestWaypointInfo:
    """Test WaypointInfo model."""

    def test_valid_construction(self):
        """Valid WaypointInfo constructs correctly."""
        waypoint = WaypointInfo(
            name="Jita",
            system_id=30000142,
            security=0.95,
            security_class="HIGH",
            region="The Forge",
            visit_order=0,
        )
        assert waypoint.name == "Jita"
        assert waypoint.visit_order == 0

    def test_serialization(self):
        """WaypointInfo serializes correctly."""
        waypoint = WaypointInfo(
            name="Amarr",
            system_id=30002187,
            security=1.0,
            security_class="HIGH",
            region="Domain",
            visit_order=1,
        )
        data = waypoint.model_dump()
        assert data["visit_order"] == 1


# =============================================================================
# OptimizedWaypointResult Tests
# =============================================================================


class TestOptimizedWaypointResult:
    """Test OptimizedWaypointResult model."""

    def test_valid_construction(self, system_info: SystemInfo):
        """Valid OptimizedWaypointResult constructs correctly."""
        waypoint = WaypointInfo(
            name="Jita",
            system_id=30000142,
            security=0.95,
            security_class="HIGH",
            region="The Forge",
            visit_order=0,
        )
        result = OptimizedWaypointResult(
            origin="Jita",
            waypoints=[waypoint],
            total_jumps=10,
            route_systems=[system_info],
            is_loop=True,
        )
        assert result.origin == "Jita"
        assert result.is_loop is True

    def test_null_origin(self, system_info: SystemInfo):
        """OptimizedWaypointResult can have null origin."""
        waypoint = WaypointInfo(
            name="Dodixie",
            system_id=30002659,
            security=0.87,
            security_class="HIGH",
            region="Sinq Laison",
            visit_order=0,
        )
        result = OptimizedWaypointResult(
            origin=None,
            waypoints=[waypoint],
            total_jumps=5,
            route_systems=[system_info],
            is_loop=False,
        )
        assert result.origin is None

    def test_defaults(self, system_info: SystemInfo):
        """OptimizedWaypointResult has correct defaults."""
        result = OptimizedWaypointResult(
            origin="Jita",
            waypoints=[],
            total_jumps=0,
            route_systems=[system_info],
            is_loop=False,
        )
        assert result.unresolved_waypoints == []
        assert result.warnings == []
        assert result.corrections == {}


# =============================================================================
# SystemActivity Tests
# =============================================================================


class TestSystemActivity:
    """Test SystemActivity model."""

    def test_valid_construction(self):
        """Valid SystemActivity constructs correctly."""
        activity = SystemActivity(
            name="Tama",
            system_id=30002813,
            security=0.3,
            security_class="LOW",
            ship_kills=15,
            pod_kills=8,
            npc_kills=50,
            ship_jumps=200,
            activity_level="high",
        )
        assert activity.ship_kills == 15
        assert activity.activity_level == "high"

    def test_defaults(self):
        """SystemActivity has correct defaults."""
        activity = SystemActivity(
            name="Jita",
            system_id=30000142,
            security=0.95,
            security_class="HIGH",
        )
        assert activity.ship_kills == 0
        assert activity.pod_kills == 0
        assert activity.npc_kills == 0
        assert activity.ship_jumps == 0
        assert activity.activity_level == "none"


# =============================================================================
# ActivityResult Tests
# =============================================================================


class TestActivityResult:
    """Test ActivityResult model."""

    def test_valid_construction(self):
        """Valid ActivityResult constructs correctly."""
        system = SystemActivity(
            name="Jita",
            system_id=30000142,
            security=0.95,
            security_class="HIGH",
        )
        result = ActivityResult(
            systems=[system],
            cache_age_seconds=60,
        )
        assert len(result.systems) == 1
        assert result.cache_age_seconds == 60

    def test_defaults(self):
        """ActivityResult has correct defaults."""
        result = ActivityResult(systems=[], cache_age_seconds=None)
        assert result.data_period == "last_hour"
        assert result.warnings == []


# =============================================================================
# HotspotSystem Tests
# =============================================================================


class TestHotspotSystem:
    """Test HotspotSystem model."""

    def test_valid_construction(self):
        """Valid HotspotSystem constructs correctly."""
        hotspot = HotspotSystem(
            name="Tama",
            system_id=30002813,
            security=0.3,
            security_class="LOW",
            region="The Citadel",
            jumps_from_origin=5,
            activity_value=50,
            activity_level="high",
        )
        assert hotspot.activity_value == 50


# =============================================================================
# HotspotsResult Tests
# =============================================================================


class TestHotspotsResult:
    """Test HotspotsResult model."""

    def test_valid_construction(self):
        """Valid HotspotsResult constructs correctly."""
        result = HotspotsResult(
            origin="Jita",
            activity_type="kills",
            hotspots=[],
            search_radius=15,
            systems_scanned=100,
            cache_age_seconds=30,
        )
        assert result.origin == "Jita"
        assert result.activity_type == "kills"


# =============================================================================
# GatecampRisk Tests
# =============================================================================


class TestGatecampRisk:
    """Test GatecampRisk model."""

    def test_valid_construction(self):
        """Valid GatecampRisk constructs correctly."""
        risk = GatecampRisk(
            system="Rancer",
            system_id=30002813,
            security=0.4,
            chokepoint_type="lowsec_entry",
            recent_kills=10,
            recent_pods=5,
            risk_level="high",
            warning="Known gank system",
        )
        assert risk.risk_level == "high"
        assert risk.warning == "Known gank system"

    def test_no_warning(self):
        """GatecampRisk can have null warning."""
        risk = GatecampRisk(
            system="Uedama",
            system_id=30002768,
            security=0.5,
            chokepoint_type="pipe",
            recent_kills=2,
            recent_pods=0,
            risk_level="low",
        )
        assert risk.warning is None


# =============================================================================
# GatecampRiskResult Tests
# =============================================================================


class TestGatecampRiskResult:
    """Test GatecampRiskResult model."""

    def test_valid_construction(self):
        """Valid GatecampRiskResult constructs correctly."""
        result = GatecampRiskResult(
            origin="Jita",
            destination="Amarr",
            total_jumps=10,
            overall_risk="medium",
            chokepoints=[],
            cache_age_seconds=60,
        )
        assert result.overall_risk == "medium"

    def test_defaults(self):
        """GatecampRiskResult has correct defaults."""
        result = GatecampRiskResult(
            origin="Jita",
            destination="Amarr",
            total_jumps=10,
            overall_risk="low",
            chokepoints=[],
            cache_age_seconds=None,
        )
        assert result.high_risk_systems == []
        assert result.recommendation == ""


# =============================================================================
# FWSystem Tests
# =============================================================================


class TestFWSystem:
    """Test FWSystem model."""

    def test_valid_construction(self):
        """Valid FWSystem constructs correctly."""
        fw = FWSystem(
            name="Tama",
            system_id=30002813,
            security=0.3,
            region="The Citadel",
            owner_faction="Caldari State",
            occupier_faction="Gallente Federation",
            contested="contested",
            contested_percentage=65.5,
            victory_points=3000,
            victory_points_threshold=5000,
        )
        assert fw.contested == "contested"
        assert fw.contested_percentage == 65.5


# =============================================================================
# FWFrontlinesResult Tests
# =============================================================================


class TestFWFrontlinesResult:
    """Test FWFrontlinesResult model."""

    def test_valid_construction(self):
        """Valid FWFrontlinesResult constructs correctly."""
        result = FWFrontlinesResult(
            faction_filter="Caldari State",
            contested=[],
            vulnerable=[],
            stable=[],
            summary={"total": 10},
            cache_age_seconds=120,
        )
        assert result.faction_filter == "Caldari State"


# =============================================================================
# CacheLayerStatus Tests
# =============================================================================


class TestCacheLayerStatus:
    """Test CacheLayerStatus model."""

    def test_valid_construction(self):
        """Valid CacheLayerStatus constructs correctly."""
        status = CacheLayerStatus(
            cached_systems=5000,
            age_seconds=60,
            ttl_seconds=3600,
            stale=False,
        )
        assert status.cached_systems == 5000
        assert status.stale is False


# =============================================================================
# CacheStatusResult Tests
# =============================================================================


class TestCacheStatusResult:
    """Test CacheStatusResult model."""

    def test_valid_construction(self):
        """Valid CacheStatusResult constructs correctly."""
        layer = CacheLayerStatus(
            cached_systems=5000,
            age_seconds=60,
            ttl_seconds=3600,
            stale=False,
        )
        result = CacheStatusResult(
            kills=layer,
            jumps=layer,
            fw=layer,
        )
        assert result.kills.cached_systems == 5000


# =============================================================================
# ThreatSummary Tests
# =============================================================================


class TestThreatSummary:
    """Test ThreatSummary model."""

    def test_valid_construction(self):
        """Valid ThreatSummary constructs correctly."""
        summary = ThreatSummary(
            level="HIGH",
            total_kills=50,
            total_pods=20,
            active_camps=["Tama", "Rancer"],
            hotspot_count=3,
        )
        assert summary.level == "HIGH"
        assert len(summary.active_camps) == 2


# =============================================================================
# LocalSystemActivity Tests
# =============================================================================


class TestLocalSystemActivity:
    """Test LocalSystemActivity model."""

    def test_valid_construction(self):
        """Valid LocalSystemActivity constructs correctly."""
        activity = LocalSystemActivity(
            system="Tama",
            system_id=30002813,
            security=0.3,
            security_class="LOW",
            region="The Citadel",
            jumps=3,
            ship_kills=10,
            reason="gatecamp",
        )
        assert activity.reason == "gatecamp"

    def test_defaults(self):
        """LocalSystemActivity has correct defaults."""
        activity = LocalSystemActivity(
            system="Jita",
            system_id=30000142,
            security=0.95,
            security_class="HIGH",
            region="The Forge",
            jumps=0,
        )
        assert activity.ship_kills == 0
        assert activity.activity_level == "none"
        assert activity.reason is None


# =============================================================================
# EscapeRoute Tests
# =============================================================================


class TestEscapeRoute:
    """Test EscapeRoute model."""

    def test_valid_construction(self):
        """Valid EscapeRoute constructs correctly."""
        route = EscapeRoute(
            destination="Jita",
            destination_type="trade_hub",
            jumps=5,
            via_system="Perimeter",
            route_security="highsec",
        )
        assert route.destination_type == "trade_hub"
        assert route.route_security == "highsec"

    def test_defaults(self):
        """EscapeRoute has correct defaults."""
        route = EscapeRoute(
            destination="Somewhere",
            destination_type="highsec",
            jumps=2,
        )
        assert route.via_system is None
        assert route.route_security == "mixed"


# =============================================================================
# SecurityBorder Tests
# =============================================================================


class TestSecurityBorder:
    """Test SecurityBorder model."""

    def test_valid_construction(self):
        """Valid SecurityBorder constructs correctly."""
        border = SecurityBorder(
            system="Uedama",
            system_id=30002768,
            security=0.5,
            jumps=3,
            border_type="high_to_low",
            adjacent_system="Sivala",
            adjacent_security=0.4,
        )
        assert border.border_type == "high_to_low"


# =============================================================================
# LocalAreaResult Tests
# =============================================================================


class TestLocalAreaResult:
    """Test LocalAreaResult model."""

    def test_valid_construction(self):
        """Valid LocalAreaResult constructs correctly."""
        threat = ThreatSummary(
            level="LOW",
            total_kills=5,
            total_pods=1,
            hotspot_count=0,
        )
        result = LocalAreaResult(
            origin="Jita",
            origin_id=30000142,
            security=0.95,
            security_class="HIGH",
            region="The Forge",
            constellation="Kimotoro",
            threat_summary=threat,
            systems_scanned=50,
            search_radius=10,
        )
        assert result.origin == "Jita"
        assert result.threat_summary.level == "LOW"

    def test_defaults(self):
        """LocalAreaResult has correct defaults."""
        threat = ThreatSummary(
            level="LOW",
            total_kills=0,
            total_pods=0,
            hotspot_count=0,
        )
        result = LocalAreaResult(
            origin="Jita",
            origin_id=30000142,
            security=0.95,
            security_class="HIGH",
            region="The Forge",
            constellation="Kimotoro",
            threat_summary=threat,
            systems_scanned=10,
            search_radius=5,
        )
        assert result.hotspots == []
        assert result.quiet_zones == []
        assert result.ratting_banks == []
        assert result.escape_routes == []
        assert result.borders == []
        assert result.realtime_healthy is False
        assert result.warnings == []


# =============================================================================
# Type Alias Validation Tests
# =============================================================================


class TestTypeAliases:
    """Test type alias validation."""

    def test_activity_level_values(self):
        """ActivityLevel accepts valid values."""
        for level in ["none", "low", "medium", "high", "extreme"]:
            activity = SystemActivity(
                name="Test",
                system_id=1,
                security=0.5,
                security_class="HIGH",
                activity_level=level,
            )
            assert activity.activity_level == level

    def test_risk_level_values(self):
        """RiskLevel accepts valid values."""
        for level in ["low", "medium", "high", "extreme"]:
            risk = GatecampRisk(
                system="Test",
                system_id=1,
                security=0.5,
                chokepoint_type="pipe",
                recent_kills=0,
                recent_pods=0,
                risk_level=level,
            )
            assert risk.risk_level == level

    def test_chokepoint_type_values(self):
        """ChokepointType accepts valid values."""
        for ctype in ["lowsec_entry", "lowsec_exit", "pipe", "hub"]:
            risk = GatecampRisk(
                system="Test",
                system_id=1,
                security=0.5,
                chokepoint_type=ctype,
                recent_kills=0,
                recent_pods=0,
                risk_level="low",
            )
            assert risk.chokepoint_type == ctype
