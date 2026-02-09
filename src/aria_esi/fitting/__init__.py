"""
ARIA Fitting Module

Ship fitting calculation services using the standalone EOS library.
"""

from aria_esi.fitting.eft_parser import (
    EFTParseError,
    EFTParser,
    TypeResolutionError,
    parse_eft,
)
from aria_esi.fitting.eos_bridge import (
    EOSBridge,
    EOSBridgeError,
    EOSFitError,
    EOSNotInitializedError,
    calculate_fit_stats,
    get_eos_bridge,
)
from aria_esi.fitting.eos_data import (
    EOSDataError,
    EOSDataManager,
    EOSDataStatus,
    get_eos_data_manager,
)
from aria_esi.fitting.skills import (
    SkillFetchError,
    SkillFetchResult,
    extract_skills_for_fit,
    fetch_pilot_skills,
    get_all_v_skills,
    get_relevant_skills_for_fit,
)
from aria_esi.fitting.tank_classifier import (
    analyze_tank,
    calculate_tank_regen,
    classify_tank,
    derive_primary_damage,
    derive_primary_resists,
)

__all__ = [
    # Data management
    "EOSDataManager",
    "EOSDataStatus",
    "EOSDataError",
    "get_eos_data_manager",
    # EOS bridge
    "EOSBridge",
    "EOSBridgeError",
    "EOSFitError",
    "EOSNotInitializedError",
    "get_eos_bridge",
    "calculate_fit_stats",
    # EFT parser
    "EFTParser",
    "EFTParseError",
    "TypeResolutionError",
    "parse_eft",
    # Skills
    "SkillFetchError",
    "SkillFetchResult",
    "extract_skills_for_fit",
    "fetch_pilot_skills",
    "get_all_v_skills",
    "get_relevant_skills_for_fit",
    # Tank classifier
    "analyze_tank",
    "calculate_tank_regen",
    "classify_tank",
    "derive_primary_damage",
    "derive_primary_resists",
]
