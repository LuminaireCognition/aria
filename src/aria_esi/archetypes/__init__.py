"""
ARIA Archetype Fittings Library.

Provides hierarchical ship archetypes organized by hull/activity/tier
with support for faction tuning, validation, and skill-aware selection.
"""

from .loader import (
    ArchetypeLoader,
    get_archetypes_path,
    list_archetypes,
    load_archetype,
    load_hull_manifest,
    load_shared_config,
)
from .models import (
    Archetype,
    ArchetypePath,
    DamageTuning,
    DroneConfig,
    EmptySlotConfig,
    FittingRules,
    HullManifest,
    MissionContext,
    ModuleSubstitution,
    SkillRequirements,
    SkillTier,
    Stats,
    TankProfile,
    TankType,
    UpgradePath,
)
from .pricing import (
    estimate_fit_price,
    update_archetype_price,
)
from .selection import (
    SelectionResult,
    can_fly_archetype,
    get_recommended_fit,
    select_fits,
)
from .tank_selection import (
    TankSelectionResult,
    TankVariantConfig,
    discover_tank_variants,
    load_tank_variant_config,
    select_tank_variant,
)
from .tuning import apply_faction_tuning
from .validator import (
    ArchetypeValidator,
    ValidationResult,
    validate_all_archetypes,
    validate_archetype,
)

__all__ = [
    # Models
    "SkillTier",
    "TankProfile",
    "TankType",
    "HullManifest",
    "Archetype",
    "ArchetypePath",
    "DamageTuning",
    "DroneConfig",
    "EmptySlotConfig",
    "FittingRules",
    "MissionContext",
    "ModuleSubstitution",
    "SkillRequirements",
    "Stats",
    "UpgradePath",
    # Loader
    "ArchetypeLoader",
    "get_archetypes_path",
    "list_archetypes",
    "load_archetype",
    "load_hull_manifest",
    "load_shared_config",
    # Tuning
    "apply_faction_tuning",
    # Selection
    "SelectionResult",
    "can_fly_archetype",
    "get_recommended_fit",
    "select_fits",
    # Tank Selection
    "TankSelectionResult",
    "TankVariantConfig",
    "discover_tank_variants",
    "load_tank_variant_config",
    "select_tank_variant",
    # Pricing
    "estimate_fit_price",
    "update_archetype_price",
    # Validator
    "ArchetypeValidator",
    "ValidationResult",
    "validate_archetype",
    "validate_all_archetypes",
]
