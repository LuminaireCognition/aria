"""
EFT (EVE Fitting Tool) Format Parser.

Parses EFT format ship fittings into structured data suitable for
EOS calculation. The EFT format is widely used for sharing ship
fittings and is exported by the EVE client and third-party tools.

EFT Format Example:
    [Vexor, My PvE Fit]
    Drone Damage Amplifier II
    Drone Damage Amplifier II
    Medium Armor Repairer II

    10MN Afterburner II
    Cap Recharger II

    Drone Link Augmentor I

    Medium Auxiliary Nano Pump I
    Medium Auxiliary Nano Pump I
    Medium Auxiliary Nano Pump I

    Hammerhead II x5
    Hobgoblin II x5

Sections are separated by blank lines in order:
1. Header: [Ship Type, Fit Name]
2. Low slots
3. Mid slots
4. High slots
5. Rigs
6. Subsystems (T3 cruisers only)
7. Drones (with "xN" quantity)
8. Cargo (with "xN" quantity)
"""

from __future__ import annotations

import re
from enum import Enum, auto
from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger
from aria_esi.models.fitting import ParsedDrone, ParsedFit, ParsedModule

if TYPE_CHECKING:
    from aria_esi.mcp.market.database import MarketDatabase

logger = get_logger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class EFTParseError(Exception):
    """Raised when EFT parsing fails."""

    def __init__(self, message: str, line_number: int | None = None):
        super().__init__(message)
        self.line_number = line_number


class TypeResolutionError(EFTParseError):
    """Raised when a type name cannot be resolved to an ID."""

    def __init__(self, type_name: str, suggestions: list[str] | None = None):
        super().__init__(f"Unknown type: {type_name}")
        self.type_name = type_name
        self.suggestions = suggestions or []


# =============================================================================
# Parser State
# =============================================================================


class ParseSection(Enum):
    """Current section being parsed in EFT format."""

    HEADER = auto()
    LOW_SLOTS = auto()
    MID_SLOTS = auto()
    HIGH_SLOTS = auto()
    RIGS = auto()
    SUBSYSTEMS = auto()
    DRONES = auto()
    CARGO = auto()


# =============================================================================
# Regex Patterns
# =============================================================================

# Header pattern: [Ship Type, Fit Name]
HEADER_PATTERN = re.compile(r"^\[(?P<ship_type>[^,\]]+),\s*(?P<fit_name>[^\]]+)\]$")

# Module pattern: Module Name, Charge Name /OFFLINE
# Handles optional charge and offline marker
MODULE_PATTERN = re.compile(
    r"^(?P<type_name>[^,/]+?)"
    r"(?:,\s*(?P<charge_name>[^/]+?))?"
    r"(?:\s*/\s*(?P<offline>OFFLINE|offline))?\s*$"
)

# Drone/Cargo pattern: Item Name x5
QUANTITY_PATTERN = re.compile(r"^(?P<type_name>.+?)\s+x(?P<quantity>\d+)\s*$")

# Empty slot marker
EMPTY_SLOT_PATTERN = re.compile(r"^\[empty\s+(low|med|high|rig|subsystem)\s+slot\]$", re.IGNORECASE)


# =============================================================================
# Section Detection
# =============================================================================

# Known module categories for section detection
# These are used as hints to determine which section a module belongs to
LOW_SLOT_GROUPS = {
    # Armor modules
    "Armor Reinforcer",
    "Armor Repair Unit",
    "Armor Coating",
    "Armor Hardener",
    "Armor Plate",
    "Energized Armor Resistance",
    # Damage modules
    "Damage Control",
    "Ballistic Control System",
    "Gyrostabilizer",
    "Heat Sink",
    "Magnetic Field Stabilizer",
    "Drone Damage Amplifier",
    "Tracking Enhancer",
    # Other low slot modules
    "Power Diagnostic System",
    "Co-Processor",
    "Capacitor Power Relay",
    "Reactor Control Unit",
    "Overdrive Injector System",
    "Inertial Stabilizers",
    "Nanofiber Internal Structure",
    "Cargo Hold Expander",
    "Expanded Cargohold",
    "Signal Amplifier",
    "Warp Core Stabilizer",
}

MID_SLOT_GROUPS = {
    # Propulsion
    "Afterburner",
    "Microwarpdrive",
    # Shield modules
    "Shield Booster",
    "Shield Hardener",
    "Shield Extender",
    "Shield Resistance Amplifier",
    "Shield Recharger",
    # Electronic warfare
    "Warp Scrambler",
    "Warp Disruptor",
    "Stasis Webifier",
    "Target Painter",
    "Sensor Booster",
    "Remote Sensor Booster",
    "Tracking Computer",
    "Guidance Computer",
    "Signal Amplifier",
    # Capacitor
    "Capacitor Recharger",
    "Capacitor Booster",
    "Cap Recharger",
    # Other mid slot modules
    "Survey Scanner",
    "Cargo Scanner",
    "Ship Scanner",
}

HIGH_SLOT_GROUPS = {
    # Weapons
    "Hybrid Weapon",
    "Projectile Weapon",
    "Energy Weapon",
    "Missile Launcher",
    "Bomb Launcher",
    # Drones
    "Drone Link Augmentor",
    # Mining
    "Mining Laser",
    "Strip Miner",
    "Ice Harvester",
    "Gas Cloud Harvester",
    # Utility
    "Remote Armor Repairer",
    "Remote Shield Booster",
    "Remote Capacitor Transmitter",
    "Energy Neutralizer",
    "Energy Nosferatu",
    "Tractor Beam",
    "Salvager",
    "Cloaking Device",
    "Cynosural Field Generator",
    # Probing
    "Probe Launcher",
}


# =============================================================================
# EFT Parser
# =============================================================================


class EFTParser:
    """
    Parser for EFT format ship fittings.

    Requires a MarketDatabase for resolving type names to IDs.
    """

    def __init__(self, db: MarketDatabase):
        """
        Initialize the parser.

        Args:
            db: MarketDatabase for type name resolution
        """
        self._db = db

    def parse(self, eft_string: str) -> ParsedFit:
        """
        Parse an EFT format fitting string.

        Args:
            eft_string: EFT format fitting string

        Returns:
            ParsedFit with ship and module data

        Raises:
            EFTParseError: If the format is invalid
            TypeResolutionError: If a type name cannot be resolved
        """
        lines = eft_string.strip().split("\n")
        if not lines:
            raise EFTParseError("Empty fitting string")

        # Parse header
        header_match = HEADER_PATTERN.match(lines[0].strip())
        if not header_match:
            raise EFTParseError("Invalid header format. Expected: [Ship Type, Fit Name]", 1)

        ship_type_name = header_match.group("ship_type").strip()
        fit_name = header_match.group("fit_name").strip()

        # Resolve ship type
        ship_type = self._db.resolve_type_name(ship_type_name)
        if not ship_type:
            suggestions = self._db.find_type_suggestions(ship_type_name)
            raise TypeResolutionError(ship_type_name, suggestions)

        # Initialize fit
        fit = ParsedFit(
            ship_type_id=ship_type.type_id,
            ship_type_name=ship_type.type_name,
            fit_name=fit_name,
        )

        # Parse sections
        current_section = ParseSection.LOW_SLOTS
        section_started = False

        for line_num, line in enumerate(lines[1:], start=2):
            line = line.strip()

            # Empty line marks section transition
            if not line:
                if section_started:
                    current_section = self._next_section(current_section)
                    section_started = False
                continue

            # Skip empty slot markers
            if EMPTY_SLOT_PATTERN.match(line):
                section_started = True
                continue

            section_started = True

            # Try to parse as quantity item (drones/cargo)
            quantity_match = QUANTITY_PATTERN.match(line)
            if quantity_match:
                type_name = quantity_match.group("type_name").strip()
                quantity = int(quantity_match.group("quantity"))

                type_info = self._db.resolve_type_name(type_name)
                if not type_info:
                    suggestions = self._db.find_type_suggestions(type_name)
                    raise TypeResolutionError(type_name, suggestions)

                drone = ParsedDrone(
                    type_id=type_info.type_id,
                    type_name=type_info.type_name,
                    quantity=quantity,
                )

                # Determine if drone or cargo based on section
                if current_section == ParseSection.CARGO:
                    fit.cargo.append(drone)
                else:
                    # Assume drones until we hit cargo section
                    fit.drones.append(drone)
                continue

            # Parse as module
            module_match = MODULE_PATTERN.match(line)
            if module_match:
                type_name = module_match.group("type_name").strip()
                charge_name = module_match.group("charge_name")
                is_offline = module_match.group("offline") is not None

                if charge_name:
                    charge_name = charge_name.strip()

                type_info = self._db.resolve_type_name(type_name)
                if not type_info:
                    suggestions = self._db.find_type_suggestions(type_name)
                    raise TypeResolutionError(type_name, suggestions)

                # Resolve charge if present
                charge_type_id = None
                if charge_name:
                    charge_info = self._db.resolve_type_name(charge_name)
                    if charge_info:
                        charge_type_id = charge_info.type_id

                module = ParsedModule(
                    type_id=type_info.type_id,
                    type_name=type_info.type_name,
                    charge_type_id=charge_type_id,
                    charge_name=charge_name,
                    is_offline=is_offline,
                )

                # Add to appropriate slot based on current section
                self._add_module_to_section(fit, module, current_section)
                continue

            # Line didn't match any pattern - might be a simple module name
            type_info = self._db.resolve_type_name(line)
            if type_info:
                module = ParsedModule(
                    type_id=type_info.type_id,
                    type_name=type_info.type_name,
                )
                self._add_module_to_section(fit, module, current_section)
            else:
                # Unknown line - log warning but continue
                logger.warning("Could not parse line %d: %s", line_num, line)

        return fit

    def _next_section(self, current: ParseSection) -> ParseSection:
        """Get the next section in EFT order."""
        section_order = [
            ParseSection.LOW_SLOTS,
            ParseSection.MID_SLOTS,
            ParseSection.HIGH_SLOTS,
            ParseSection.RIGS,
            ParseSection.SUBSYSTEMS,
            ParseSection.DRONES,
            ParseSection.CARGO,
        ]

        try:
            idx = section_order.index(current)
            if idx < len(section_order) - 1:
                return section_order[idx + 1]
        except ValueError:
            pass

        return current

    def _add_module_to_section(
        self, fit: ParsedFit, module: ParsedModule, section: ParseSection
    ) -> None:
        """Add a module to the appropriate slot list."""
        if section == ParseSection.LOW_SLOTS:
            fit.low_slots.append(module)
        elif section == ParseSection.MID_SLOTS:
            fit.mid_slots.append(module)
        elif section == ParseSection.HIGH_SLOTS:
            fit.high_slots.append(module)
        elif section == ParseSection.RIGS:
            fit.rigs.append(module)
        elif section == ParseSection.SUBSYSTEMS:
            fit.subsystems.append(module)
        # Drones and cargo are handled separately with quantity pattern


# =============================================================================
# Module-level Functions
# =============================================================================


def parse_eft(eft_string: str, db: MarketDatabase | None = None) -> ParsedFit:
    """
    Parse an EFT format fitting string.

    Convenience function that creates a parser with the default database.

    Args:
        eft_string: EFT format fitting string
        db: Optional MarketDatabase. Uses singleton if not provided.

    Returns:
        ParsedFit with ship and module data

    Raises:
        EFTParseError: If the format is invalid
        TypeResolutionError: If a type name cannot be resolved
    """
    if db is None:
        from aria_esi.mcp.market.database import get_market_database

        db = get_market_database()

    parser = EFTParser(db)
    return parser.parse(eft_string)
