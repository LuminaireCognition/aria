"""
ARIA ESI Models

Data structures and response builders for ESI operations.
"""

from aria_esi.models.fitting import (
    CapacitorStats,
    DamageProfile,
    DPSBreakdown,
    DroneStats,
    FitStatsResult,
    LayerStats,
    MobilityStats,
    ParsedDrone,
    ParsedFit,
    ParsedModule,
    ResistProfile,
    ResourceUsage,
    SlotUsage,
    TankStats,
)
from aria_esi.models.market import (
    TRADE_HUBS,
    DailyPrice,
    FreshnessLevel,
    ItemPrice,
    ItemSpread,
    MarketCacheLayerStatus,
    MarketCacheStatusResult,
    MarketHistoryResult,
    MarketModel,
    MarketOrder,
    MarketOrdersResult,
    MarketPricesResult,
    MarketSpreadResult,
    OrderType,
    PriceAggregate,
    PriceType,
    RegionPrice,
    RouteValueResult,
    SystemRisk,
    ValuationItem,
    ValuationResult,
    resolve_trade_hub,
)
from aria_esi.models.sde import (
    CATEGORY_ASTEROID,
    CATEGORY_BLUEPRINT,
    CATEGORY_CHARGE,
    CATEGORY_DRONE,
    CATEGORY_MODULE,
    CATEGORY_SHIP,
    CATEGORY_SKILL,
    ORE_CORPORATION_ID,
    ORE_CORPORATION_NAME,
    BlueprintInfo,
    BlueprintInfoResult,
    BlueprintMaterial,
    BlueprintSource,
    ItemCategory,
    ItemGroup,
    ItemInfo,
    ItemInfoResult,
    SDEModel,
    SDESearchResult,
    SDEStatusResult,
    SearchResultItem,
)

__all__ = [
    # Base
    "MarketModel",
    "SDEModel",
    # Type aliases
    "PriceType",
    "FreshnessLevel",
    "OrderType",
    # Price models
    "PriceAggregate",
    "ItemPrice",
    "MarketPricesResult",
    # Order models
    "MarketOrder",
    "MarketOrdersResult",
    # Valuation models
    "ValuationItem",
    "ValuationResult",
    # Analysis models
    "RegionPrice",
    "ItemSpread",
    "MarketSpreadResult",
    # Route models
    "SystemRisk",
    "RouteValueResult",
    # History models
    "DailyPrice",
    "MarketHistoryResult",
    # Cache status
    "MarketCacheLayerStatus",
    "MarketCacheStatusResult",
    # Market constants
    "TRADE_HUBS",
    "resolve_trade_hub",
    # SDE item models
    "ItemCategory",
    "ItemGroup",
    "ItemInfo",
    "ItemInfoResult",
    # SDE blueprint models
    "BlueprintSource",
    "BlueprintMaterial",
    "BlueprintInfo",
    "BlueprintInfoResult",
    # SDE search models
    "SearchResultItem",
    "SDESearchResult",
    # SDE status models
    "SDEStatusResult",
    # SDE constants
    "CATEGORY_SHIP",
    "CATEGORY_MODULE",
    "CATEGORY_CHARGE",
    "CATEGORY_BLUEPRINT",
    "CATEGORY_SKILL",
    "CATEGORY_DRONE",
    "CATEGORY_ASTEROID",
    "ORE_CORPORATION_ID",
    "ORE_CORPORATION_NAME",
    # Fitting models
    "DPSBreakdown",
    "ResistProfile",
    "LayerStats",
    "TankStats",
    "ResourceUsage",
    "CapacitorStats",
    "MobilityStats",
    "DroneStats",
    "SlotUsage",
    "ParsedModule",
    "ParsedDrone",
    "ParsedFit",
    "FitStatsResult",
    "DamageProfile",
]
