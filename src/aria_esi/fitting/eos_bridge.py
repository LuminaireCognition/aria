"""
EOS Bridge - Wrapper for standalone EOS fitting calculations.

Provides a high-level interface to the EOS library for calculating
ship fitting statistics. Handles source management, fit construction,
and statistics extraction.

The EOS library is lazily initialized on first use to avoid import
overhead when the fitting module is not needed.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger
from aria_esi.fitting.eos_data import get_eos_data_manager
from aria_esi.models.fitting import (
    CapacitorStats,
    DamageProfile,
    DPSBreakdown,
    DroneStats,
    FitStatsResult,
    LayerStats,
    MobilityStats,
    ParsedFit,
    ResistProfile,
    ResourceUsage,
    SlotUsage,
    TankStats,
)

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class EOSBridgeError(Exception):
    """Base exception for EOS bridge errors."""

    pass


class EOSNotInitializedError(EOSBridgeError):
    """Raised when EOS has not been initialized."""

    pass


class EOSFitError(EOSBridgeError):
    """Raised when fit construction or calculation fails."""

    pass


# =============================================================================
# Attribute IDs
# =============================================================================

# Common attribute IDs used for extracting stats
# These are defined in EVE's dogma system
ATTR_MASS = 4
ATTR_CAPACITY = 38
ATTR_AGILITY = 70
ATTR_MAX_VELOCITY = 37
ATTR_WARP_SPEED_MULTIPLIER = 600
ATTR_CAP_CAPACITY = 482
ATTR_CAP_RECHARGE_TIME = 55

# Resist attributes (armor)
ATTR_ARMOR_EM_RESIST = 267
ATTR_ARMOR_THERMAL_RESIST = 268
ATTR_ARMOR_KINETIC_RESIST = 269
ATTR_ARMOR_EXPLOSIVE_RESIST = 270

# Resist attributes (shield)
ATTR_SHIELD_EM_RESIST = 271
ATTR_SHIELD_THERMAL_RESIST = 272
ATTR_SHIELD_KINETIC_RESIST = 273
ATTR_SHIELD_EXPLOSIVE_RESIST = 274

# Resist attributes (hull)
ATTR_HULL_EM_RESIST = 974
ATTR_HULL_THERMAL_RESIST = 975
ATTR_HULL_KINETIC_RESIST = 976
ATTR_HULL_EXPLOSIVE_RESIST = 977


# =============================================================================
# Tank Coherence Detection
# =============================================================================

# Patterns in module type names that indicate armor tank commitment
ARMOR_MODULE_PATTERNS = (
    "Armor Repairer",
    "Armor Hardener",
    "Energized Adaptive Nano Membrane",
    "Energized Kinetic Membrane",
    "Energized Thermal Membrane",
    "Energized EM Membrane",
    "Energized Explosive Membrane",
    "Reactive Armor Hardener",
)

ARMOR_RIG_PATTERNS = (
    "Auxiliary Nano Pump",
    "Nanobot Accelerator",
    "Trimark Armor Pump",
    "Remote Repair Augmentor",  # Armor remote rep rigs
)

# Patterns in module type names that indicate shield tank commitment
SHIELD_MODULE_PATTERNS = (
    "Shield Booster",
    "Shield Hardener",
    "Shield Extender",
    "Invulnerability Field",
    "Adaptive Invulnerability",
    "Shield Amplifier",
)

SHIELD_RIG_PATTERNS = (
    "Core Defense Field Extender",
    "Core Defense Field Purger",
    "Core Defense Capacitor Safeguard",
    "Core Defense Charge Economizer",
    "Core Defense Operational Solidifier",
    "Anti-EM Screen Reinforcer",
    "Anti-Thermal Screen Reinforcer",
    "Anti-Kinetic Screen Reinforcer",
    "Anti-Explosive Screen Reinforcer",
)


def _detect_tank_type(parsed_fit: ParsedFit) -> tuple[bool, bool, bool, bool]:
    """
    Detect tank type indicators in a parsed fit.

    Returns:
        Tuple of (has_armor_modules, has_armor_rigs, has_shield_modules, has_shield_rigs)
    """
    has_armor_modules = False
    has_armor_rigs = False
    has_shield_modules = False
    has_shield_rigs = False

    # Check low and mid slot modules
    all_modules = parsed_fit.low_slots + parsed_fit.mid_slots
    for module in all_modules:
        name = module.type_name
        if any(pattern in name for pattern in ARMOR_MODULE_PATTERNS):
            has_armor_modules = True
        if any(pattern in name for pattern in SHIELD_MODULE_PATTERNS):
            has_shield_modules = True

    # Check rigs
    for rig in parsed_fit.rigs:
        name = rig.type_name
        if any(pattern in name for pattern in ARMOR_RIG_PATTERNS):
            has_armor_rigs = True
        if any(pattern in name for pattern in SHIELD_RIG_PATTERNS):
            has_shield_rigs = True

    return has_armor_modules, has_armor_rigs, has_shield_modules, has_shield_rigs


def _check_tank_coherence(parsed_fit: ParsedFit) -> list[str]:
    """
    Check for mixed tank configurations and return warnings.

    Mixed tank warnings are generated when:
    - Armor rigs are used with shield active modules
    - Shield rigs are used with armor active modules
    - Both armor and shield active tank modules are present
    """
    warnings = []

    armor_mods, armor_rigs, shield_mods, shield_rigs = _detect_tank_type(parsed_fit)

    # Armor rigs + shield modules = mixed tank
    if armor_rigs and shield_mods:
        warnings.append(
            "Mixed tank detected: Armor rigs with shield modules. "
            "Shield hardeners/boosters are ineffective once shields are depleted. "
            "Consider replacing shield modules with utility or more armor tank."
        )

    # Shield rigs + armor modules = mixed tank
    if shield_rigs and armor_mods:
        warnings.append(
            "Mixed tank detected: Shield rigs with armor modules. "
            "Consider committing to one tank type for efficiency."
        )

    # Both active tank types without rig commitment (less severe)
    if armor_mods and shield_mods and not armor_rigs and not shield_rigs:
        warnings.append(
            "Mixed active tank: Both armor and shield tank modules fitted. "
            "This splits tank effectiveness. Consider committing to one type."
        )

    return warnings


# =============================================================================
# EOS Bridge
# =============================================================================


class EOSBridge:
    """
    Bridge to the standalone EOS library.

    Implements a singleton pattern with lazy initialization.
    The EOS source manager is initialized only when first needed.

    Usage:
        bridge = EOSBridge.get_instance()
        result = bridge.calculate_stats(parsed_fit)
    """

    _instance: EOSBridge | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        """Initialize the bridge (do not call directly, use get_instance())."""
        self._initialized = False
        self._source_name = "tq"

    @classmethod
    def get_instance(cls) -> EOSBridge:
        """Get the singleton instance of EOSBridge."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = EOSBridge()
                    cls._instance = instance
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        with cls._lock:
            if cls._instance is not None and cls._instance._initialized:
                try:
                    cls._instance._cleanup()
                except Exception as e:
                    logger.warning("Error during EOS cleanup: %s", e)
            cls._instance = None

    def initialize(self) -> None:
        """
        Initialize the EOS library with data from the data manager.

        This loads the JSON data files and prepares the source manager.
        Called lazily on first calculation.

        Raises:
            EOSDataError: If data files are missing or invalid
            EOSBridgeError: If EOS initialization fails
        """
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            # Validate data files
            data_manager = get_eos_data_manager()
            data_manager.ensure_valid()

            try:
                # Import EOS modules
                from aria_esi._vendor.eos import JsonCacheHandler, JsonDataHandler, SourceManager

                # Create data handler pointing to our data directory
                data_handler = JsonDataHandler(str(data_manager.data_path))

                # Create cache handler
                cache_handler = JsonCacheHandler(str(data_manager.cache_path))

                # Register source
                SourceManager.add(self._source_name, data_handler, cache_handler, make_default=True)

                self._initialized = True
                logger.info(
                    "EOS initialized with source '%s' from %s",
                    self._source_name,
                    data_manager.data_path,
                )

            except ImportError as e:
                raise EOSBridgeError(
                    "Vendored EOS library failed to import. Check installation."
                ) from e
            except Exception as e:
                raise EOSBridgeError(f"Failed to initialize EOS: {e}") from e

    def _cleanup(self) -> None:
        """Clean up EOS resources."""
        if not self._initialized:
            return

        try:
            from aria_esi._vendor.eos import SourceManager

            if self._source_name in SourceManager.list():
                SourceManager.remove(self._source_name)
            self._initialized = False
            logger.debug("EOS source '%s' removed", self._source_name)
        except Exception as e:
            logger.warning("Error during EOS cleanup: %s", e)

    def is_initialized(self) -> bool:
        """Check if EOS has been initialized."""
        return self._initialized

    def calculate_stats(
        self,
        parsed_fit: ParsedFit,
        damage_profile: DamageProfile | None = None,
        skill_levels: dict[int, int] | None = None,
    ) -> FitStatsResult:
        """
        Calculate statistics for a parsed fit.

        Args:
            parsed_fit: Parsed fit from EFT parser
            damage_profile: Incoming damage profile for EHP calculation
            skill_levels: Optional dict of skill_id -> level. If None, all skills
                         are assumed to be level 5.

        Returns:
            FitStatsResult with complete statistics

        Raises:
            EOSFitError: If fit construction or calculation fails
        """
        # Initialize if needed
        if not self._initialized:
            self.initialize()

        if damage_profile is None:
            damage_profile = DamageProfile.omni()

        try:
            # Import EOS modules
            from aria_esi._vendor.eos import (
                DmgProfile,
                Drone,
                Fit,
                ModuleHigh,
                ModuleLow,
                ModuleMid,
                Restriction,
                Rig,
                Ship,
                Skill,
                State,
                Subsystem,
            )

            # Create fit
            fit = Fit()

            # Set ship first (needed for skill extraction)
            fit.ship = Ship(parsed_fit.ship_type_id)

            # Add skills
            skill_mode = "all_v"
            if skill_levels is not None:
                skill_mode = "pilot_skills"
                for skill_id, level in skill_levels.items():
                    fit.skills.add(Skill(skill_id, level=level))
            else:
                # Extract required and bonus skills from the fit at level 5
                from aria_esi.fitting.skills import extract_skills_for_fit

                extracted_skills = extract_skills_for_fit(parsed_fit, level=5)
                for skill_id, level in extracted_skills.items():
                    fit.skills.add(Skill(skill_id, level=level))
                logger.debug("Added %d skills at level 5 for all-V mode", len(extracted_skills))

            # Add modules - low slots
            for module in parsed_fit.low_slots:
                state = State.offline if module.is_offline else State.online
                mod = ModuleLow(module.type_id, state=state)
                if module.charge_type_id:
                    mod.charge = module.charge_type_id
                fit.modules.low.equip(mod)

            # Add modules - mid slots
            for module in parsed_fit.mid_slots:
                state = State.offline if module.is_offline else State.online
                # For active modules like afterburners, we might want State.active
                # For now, default to online (passive effects apply)
                mod = ModuleMid(module.type_id, state=state)
                if module.charge_type_id:
                    mod.charge = module.charge_type_id
                fit.modules.mid.equip(mod)

            # Add modules - high slots
            for module in parsed_fit.high_slots:
                state = State.offline if module.is_offline else State.online
                mod = ModuleHigh(module.type_id, state=state)
                if module.charge_type_id:
                    mod.charge = module.charge_type_id
                fit.modules.high.equip(mod)

            # Add rigs (rigs use .add() not .equip())
            for rig in parsed_fit.rigs:
                fit.rigs.add(Rig(rig.type_id))

            # Add subsystems (for T3 cruisers)
            for subsystem in parsed_fit.subsystems:
                fit.subsystems.add(Subsystem(subsystem.type_id))

            # Add drones
            for drone in parsed_fit.drones:
                for _ in range(drone.quantity):
                    # Active drones contribute to DPS
                    fit.drones.add(Drone(drone.type_id, state=State.active))

            # Validate fit (skip skill requirements for flexibility)
            validation_errors = []
            warnings = []
            try:
                skip_checks = (
                    Restriction.skill_requirement,
                    Restriction.launched_drone,
                )
                fit.validate(skip_checks=skip_checks)
            except Exception as e:
                warnings.append(f"Fit validation warning: {e}")

            # Tank coherence check (semantic validation)
            tank_warnings = _check_tank_coherence(parsed_fit)
            warnings.extend(tank_warnings)

            # Extract statistics
            stats = fit.stats

            # DPS
            dps_result = stats.get_dps(reload=True)
            dps = DPSBreakdown(
                total=dps_result.total,
                em=dps_result.em,
                thermal=dps_result.thermal,
                kinetic=dps_result.kinetic,
                explosive=dps_result.explosive,
            )

            # Tank - HP
            hp = stats.hp

            # Tank - EHP with damage profile
            eos_dmg_profile = DmgProfile(
                em=damage_profile.em,
                thermal=damage_profile.thermal,
                kinetic=damage_profile.kinetic,
                explosive=damage_profile.explosive,
            )
            ehp = stats.get_ehp(eos_dmg_profile)

            # Extract resist values from ship attributes
            ship_attrs = fit.ship.attrs if fit.ship else {}

            def get_resist_pct(attr_id: int) -> float:
                """Convert resistance multiplier to percentage."""
                value = ship_attrs.get(attr_id, 1.0)
                return (1 - value) * 100 if value is not None else 0.0

            shield_resists = ResistProfile(
                em=get_resist_pct(ATTR_SHIELD_EM_RESIST),
                thermal=get_resist_pct(ATTR_SHIELD_THERMAL_RESIST),
                kinetic=get_resist_pct(ATTR_SHIELD_KINETIC_RESIST),
                explosive=get_resist_pct(ATTR_SHIELD_EXPLOSIVE_RESIST),
            )

            armor_resists = ResistProfile(
                em=get_resist_pct(ATTR_ARMOR_EM_RESIST),
                thermal=get_resist_pct(ATTR_ARMOR_THERMAL_RESIST),
                kinetic=get_resist_pct(ATTR_ARMOR_KINETIC_RESIST),
                explosive=get_resist_pct(ATTR_ARMOR_EXPLOSIVE_RESIST),
            )

            hull_resists = ResistProfile(
                em=get_resist_pct(ATTR_HULL_EM_RESIST),
                thermal=get_resist_pct(ATTR_HULL_THERMAL_RESIST),
                kinetic=get_resist_pct(ATTR_HULL_KINETIC_RESIST),
                explosive=get_resist_pct(ATTR_HULL_EXPLOSIVE_RESIST),
            )

            tank = TankStats(
                shield=LayerStats(hp=hp.shield, ehp=ehp.shield, resists=shield_resists),
                armor=LayerStats(hp=hp.armor, ehp=ehp.armor, resists=armor_resists),
                hull=LayerStats(hp=hp.hull, ehp=ehp.hull, resists=hull_resists),
                total_hp=hp.total,
                total_ehp=ehp.total,
            )

            # Resources
            cpu = ResourceUsage(used=stats.cpu.used, output=stats.cpu.output)
            powergrid = ResourceUsage(used=stats.powergrid.used, output=stats.powergrid.output)
            calibration = ResourceUsage(
                used=stats.calibration.used, output=stats.calibration.output
            )

            # Capacitor
            cap_capacity = ship_attrs.get(ATTR_CAP_CAPACITY, 0) or 0
            cap_recharge = ship_attrs.get(ATTR_CAP_RECHARGE_TIME, 1) or 1
            cap_recharge_rate = cap_capacity / (cap_recharge / 1000) if cap_recharge else 0

            capacitor = CapacitorStats(
                capacity=cap_capacity,
                recharge_time=cap_recharge / 1000,  # Convert ms to seconds
                recharge_rate=cap_recharge_rate,
            )

            # Mobility
            max_velocity = ship_attrs.get(ATTR_MAX_VELOCITY, 0) or 0
            agility = stats.agility_factor
            align_time = stats.align_time
            mass = ship_attrs.get(ATTR_MASS, 0) or 0
            warp_speed = ship_attrs.get(ATTR_WARP_SPEED_MULTIPLIER, 1) or 1

            mobility = MobilityStats(
                max_velocity=max_velocity,
                agility=agility,
                align_time=align_time,
                mass=mass,
                warp_speed=warp_speed * 3,  # Base warp speed is 3 AU/s
            )

            # Drones
            drones = DroneStats(
                bandwidth_used=stats.drone_bandwidth.used,
                bandwidth_output=stats.drone_bandwidth.output,
                bay_used=stats.dronebay.used,
                bay_output=stats.dronebay.output,
                drones_launched=stats.launched_drones.used,
                drones_max=stats.launched_drones.total,
            )

            # Slots
            slots = SlotUsage(
                high_used=len(list(fit.modules.high)),
                high_total=fit.ship.attrs.get(14, 0) if fit.ship else 0,  # hiSlots
                mid_used=len(list(fit.modules.mid)),
                mid_total=fit.ship.attrs.get(13, 0) if fit.ship else 0,  # medSlots
                low_used=len(list(fit.modules.low)),
                low_total=fit.ship.attrs.get(12, 0) if fit.ship else 0,  # lowSlots
                rig_used=len(list(fit.rigs)),
                rig_total=fit.ship.attrs.get(1137, 0) if fit.ship else 0,  # rigSlots
            )

            # Empty slot warnings
            if slots.high_total and slots.high_used < slots.high_total:
                empty = slots.high_total - slots.high_used
                warnings.append(f"Empty high slots: {empty} of {slots.high_total} unused")
            if slots.mid_total and slots.mid_used < slots.mid_total:
                empty = slots.mid_total - slots.mid_used
                warnings.append(f"Empty mid slots: {empty} of {slots.mid_total} unused")
            if slots.low_total and slots.low_used < slots.low_total:
                empty = slots.low_total - slots.low_used
                warnings.append(f"Empty low slots: {empty} of {slots.low_total} unused")

            return FitStatsResult(
                ship_type_id=parsed_fit.ship_type_id,
                ship_type_name=parsed_fit.ship_type_name,
                fit_name=parsed_fit.fit_name,
                dps=dps,
                tank=tank,
                cpu=cpu,
                powergrid=powergrid,
                calibration=calibration,
                capacitor=capacitor,
                mobility=mobility,
                drones=drones,
                slots=slots,
                skill_mode=skill_mode,
                validation_errors=validation_errors,
                warnings=warnings,
            )

        except ImportError as e:
            raise EOSBridgeError(
                "EOS library not installed. Install with: "
                "pip install 'eos @ git+https://github.com/pyfa-org/eos.git'"
            ) from e
        except Exception as e:
            raise EOSFitError(f"Failed to calculate fit stats: {e}") from e


# =============================================================================
# Module-level Functions
# =============================================================================


def get_eos_bridge() -> EOSBridge:
    """Get the singleton EOS bridge instance."""
    return EOSBridge.get_instance()


def calculate_fit_stats(
    parsed_fit: ParsedFit,
    damage_profile: DamageProfile | None = None,
    skill_levels: dict[int, int] | None = None,
) -> FitStatsResult:
    """
    Calculate statistics for a parsed fit.

    Convenience function that uses the singleton bridge.

    Args:
        parsed_fit: Parsed fit from EFT parser
        damage_profile: Incoming damage profile for EHP calculation
        skill_levels: Optional dict of skill_id -> level

    Returns:
        FitStatsResult with complete statistics
    """
    bridge = get_eos_bridge()
    return bridge.calculate_stats(parsed_fit, damage_profile, skill_levels)
