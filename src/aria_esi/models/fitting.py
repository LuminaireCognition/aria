"""
Pydantic Models for Ship Fitting Calculations.

Defines the data structures for fit statistics returned by the EOS bridge.
These models are used by the MCP tools and can be serialized to JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# =============================================================================
# DPS Models
# =============================================================================


@dataclass(frozen=True)
class DPSBreakdown:
    """
    Damage per second breakdown by damage type.

    All values are in DPS (damage per second).
    """

    total: float
    em: float = 0.0
    thermal: float = 0.0
    kinetic: float = 0.0
    explosive: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total": round(self.total, 2),
            "em": round(self.em, 2),
            "thermal": round(self.thermal, 2),
            "kinetic": round(self.kinetic, 2),
            "explosive": round(self.explosive, 2),
        }


# =============================================================================
# Tank Models
# =============================================================================


@dataclass(frozen=True)
class ResistProfile:
    """
    Resistance profile for a layer (shield/armor/hull).

    Values are percentages (0-100).
    """

    em: float = 0.0
    thermal: float = 0.0
    kinetic: float = 0.0
    explosive: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "em": round(self.em, 1),
            "thermal": round(self.thermal, 1),
            "kinetic": round(self.kinetic, 1),
            "explosive": round(self.explosive, 1),
        }


@dataclass(frozen=True)
class LayerStats:
    """
    Stats for a single tank layer (shield/armor/hull).
    """

    hp: float
    ehp: float
    resists: ResistProfile

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "hp": round(self.hp, 0),
            "ehp": round(self.ehp, 0),
            "resists": self.resists.to_dict(),
        }


@dataclass(frozen=True)
class TankStats:
    """
    Complete tank statistics including HP, EHP, and resists.
    """

    shield: LayerStats
    armor: LayerStats
    hull: LayerStats
    total_hp: float
    total_ehp: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "shield": self.shield.to_dict(),
            "armor": self.armor.to_dict(),
            "hull": self.hull.to_dict(),
            "total_hp": round(self.total_hp, 0),
            "total_ehp": round(self.total_ehp, 0),
        }


# =============================================================================
# Resource Models
# =============================================================================


@dataclass(frozen=True)
class ResourceUsage:
    """
    Resource usage (CPU, Powergrid, Calibration, etc.).
    """

    used: float
    output: float

    @property
    def percent(self) -> float:
        """Percentage of resource used."""
        if self.output <= 0:
            return 0.0
        return (self.used / self.output) * 100

    @property
    def remaining(self) -> float:
        """Remaining resource."""
        return self.output - self.used

    @property
    def is_overloaded(self) -> bool:
        """True if resource is overloaded (used > output)."""
        return self.used > self.output

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "used": round(self.used, 2),
            "output": round(self.output, 2),
            "percent": round(self.percent, 1),
            "remaining": round(self.remaining, 2),
            "overloaded": self.is_overloaded,
        }


# =============================================================================
# Capacitor Models
# =============================================================================


@dataclass(frozen=True)
class CapacitorStats:
    """
    Capacitor statistics.

    Note: Capacitor simulation (get_capacitor) is not available in standalone EOS.
    These values are basic stats from attributes.
    """

    capacity: float
    recharge_time: float  # seconds
    recharge_rate: float  # GJ/s

    @property
    def peak_recharge_rate(self) -> float:
        """Peak recharge rate (at 25% cap)."""
        # Peak recharge is at 25% capacitor, approximately 2.5x base rate
        return self.recharge_rate * 2.5

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "capacity": round(self.capacity, 1),
            "recharge_time": round(self.recharge_time, 1),
            "recharge_rate": round(self.recharge_rate, 2),
            "peak_recharge_rate": round(self.peak_recharge_rate, 2),
        }


# =============================================================================
# Mobility Models
# =============================================================================


@dataclass(frozen=True)
class MobilityStats:
    """
    Ship mobility statistics.
    """

    max_velocity: float  # m/s
    agility: float  # agility factor (lower is better)
    align_time: float  # seconds to align
    mass: float  # kg
    warp_speed: float  # AU/s

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "max_velocity": round(self.max_velocity, 1),
            "agility": round(self.agility, 3),
            "align_time": round(self.align_time, 2),
            "mass": round(self.mass, 0),
            "warp_speed": round(self.warp_speed, 2),
        }


# =============================================================================
# Drone Models
# =============================================================================


@dataclass(frozen=True)
class DroneStats:
    """
    Drone bay and bandwidth statistics.
    """

    bandwidth_used: float
    bandwidth_output: float
    bay_used: float
    bay_output: float
    drones_launched: int
    drones_max: int

    @property
    def bandwidth_percent(self) -> float:
        """Percentage of bandwidth used."""
        if self.bandwidth_output <= 0:
            return 0.0
        return (self.bandwidth_used / self.bandwidth_output) * 100

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "bandwidth": {
                "used": round(self.bandwidth_used, 0),
                "output": round(self.bandwidth_output, 0),
                "percent": round(self.bandwidth_percent, 1),
            },
            "bay": {
                "used": round(self.bay_used, 0),
                "output": round(self.bay_output, 0),
            },
            "launched": self.drones_launched,
            "max_active": self.drones_max,
        }


# =============================================================================
# Slot Usage Models
# =============================================================================


@dataclass
class SlotUsage:
    """
    Module slot usage statistics.
    """

    high_used: int = 0
    high_total: int = 0
    mid_used: int = 0
    mid_total: int = 0
    low_used: int = 0
    low_total: int = 0
    rig_used: int = 0
    rig_total: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "high": {"used": self.high_used, "total": self.high_total},
            "mid": {"used": self.mid_used, "total": self.mid_total},
            "low": {"used": self.low_used, "total": self.low_total},
            "rig": {"used": self.rig_used, "total": self.rig_total},
        }


# =============================================================================
# Parsed Fit Models (from EFT parser)
# =============================================================================


@dataclass
class ParsedModule:
    """
    A module parsed from EFT format.
    """

    type_id: int
    type_name: str
    charge_type_id: int | None = None
    charge_name: str | None = None
    is_offline: bool = False


@dataclass
class ParsedDrone:
    """
    A drone entry parsed from EFT format.
    """

    type_id: int
    type_name: str
    quantity: int


@dataclass
class ParsedFit:
    """
    A ship fitting parsed from EFT format.

    Contains the ship type and all modules/drones in a structured format
    suitable for building an EOS Fit object.
    """

    ship_type_id: int
    ship_type_name: str
    fit_name: str
    low_slots: list[ParsedModule] = field(default_factory=list)
    mid_slots: list[ParsedModule] = field(default_factory=list)
    high_slots: list[ParsedModule] = field(default_factory=list)
    rigs: list[ParsedModule] = field(default_factory=list)
    subsystems: list[ParsedModule] = field(default_factory=list)
    drones: list[ParsedDrone] = field(default_factory=list)
    cargo: list[ParsedDrone] = field(default_factory=list)  # Items in cargo (quantity format)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "ship_type_id": self.ship_type_id,
            "ship_type_name": self.ship_type_name,
            "fit_name": self.fit_name,
            "low_slots": len(self.low_slots),
            "mid_slots": len(self.mid_slots),
            "high_slots": len(self.high_slots),
            "rigs": len(self.rigs),
            "subsystems": len(self.subsystems),
            "drones": sum(d.quantity for d in self.drones),
            "cargo": len(self.cargo),
        }


# =============================================================================
# Complete Fit Stats Result
# =============================================================================


@dataclass
class FitStatsResult:
    """
    Complete statistics for a ship fitting.

    This is the main result type returned by the MCP tool.
    """

    # Identity
    ship_type_id: int
    ship_type_name: str
    fit_name: str

    # Combat
    dps: DPSBreakdown
    tank: TankStats

    # Resources
    cpu: ResourceUsage
    powergrid: ResourceUsage
    calibration: ResourceUsage

    # Capacitor
    capacitor: CapacitorStats

    # Mobility
    mobility: MobilityStats

    # Drones
    drones: DroneStats

    # Slots
    slots: SlotUsage

    # Metadata
    skill_mode: str = "all_v"  # "all_v" or "pilot_skills"
    validation_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "ship": {
                "type_id": self.ship_type_id,
                "type_name": self.ship_type_name,
                "fit_name": self.fit_name,
            },
            "dps": self.dps.to_dict(),
            "tank": self.tank.to_dict(),
            "resources": {
                "cpu": self.cpu.to_dict(),
                "powergrid": self.powergrid.to_dict(),
                "calibration": self.calibration.to_dict(),
            },
            "capacitor": self.capacitor.to_dict(),
            "mobility": self.mobility.to_dict(),
            "drones": self.drones.to_dict(),
            "slots": self.slots.to_dict(),
            "metadata": {
                "skill_mode": self.skill_mode,
                "validation_errors": self.validation_errors,
                "warnings": self.warnings,
            },
        }


# =============================================================================
# Damage Profile
# =============================================================================


@dataclass(frozen=True)
class DamageProfile:
    """
    Incoming damage profile for EHP calculations.

    Values should sum to 100 (percentages).
    Default is omni damage (25% each).
    """

    em: float = 25.0
    thermal: float = 25.0
    kinetic: float = 25.0
    explosive: float = 25.0

    def validate(self) -> bool:
        """Validate that percentages sum to 100."""
        total = self.em + self.thermal + self.kinetic + self.explosive
        return abs(total - 100.0) < 0.1  # Allow small floating point error

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "em": self.em,
            "thermal": self.thermal,
            "kinetic": self.kinetic,
            "explosive": self.explosive,
        }

    @classmethod
    def omni(cls) -> DamageProfile:
        """Standard omni damage profile (25% each)."""
        return cls()

    @classmethod
    def em_heavy(cls) -> DamageProfile:
        """EM-heavy damage (Amarr NPCs, etc.)."""
        return cls(em=50.0, thermal=40.0, kinetic=5.0, explosive=5.0)

    @classmethod
    def kinetic_heavy(cls) -> DamageProfile:
        """Kinetic-heavy damage (Caldari NPCs, missiles, etc.)."""
        return cls(em=5.0, thermal=15.0, kinetic=60.0, explosive=20.0)

    @classmethod
    def thermal_heavy(cls) -> DamageProfile:
        """Thermal-heavy damage (Gallente NPCs, etc.)."""
        return cls(em=10.0, thermal=50.0, kinetic=30.0, explosive=10.0)

    @classmethod
    def explosive_heavy(cls) -> DamageProfile:
        """Explosive-heavy damage (Minmatar NPCs, etc.)."""
        return cls(em=5.0, thermal=15.0, kinetic=20.0, explosive=60.0)
