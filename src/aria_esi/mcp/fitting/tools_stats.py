"""
MCP Tool: calculate_fit_stats

Calculates complete statistics for an EVE Online ship fitting
provided in EFT (EVE Fitting Tool) format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.logging import get_logger

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger(__name__)


def register_stats_tools(server: FastMCP) -> None:
    """Register fit stats calculation tools with MCP server."""

    @server.tool()
    async def calculate_fit_stats(
        eft: str,
        damage_profile: dict | None = None,
        use_pilot_skills: bool = False,
    ) -> dict:
        """
        Calculate complete statistics for an EVE Online ship fitting.

        Takes an EFT (EVE Fitting Tool) format string and returns detailed
        statistics including DPS, tank (HP/EHP), resources (CPU/PG), capacitor,
        mobility, and drone stats.

        Args:
            eft: Ship fitting in EFT format. Example:
                 [Vexor, My Fit]
                 Drone Damage Amplifier II
                 Drone Damage Amplifier II
                 Medium Armor Repairer II

                 10MN Afterburner II
                 Cap Recharger II

                 Drone Link Augmentor I

                 Medium Auxiliary Nano Pump I

                 Hammerhead II x5

            damage_profile: Optional incoming damage profile for EHP calculation.
                           Dict with keys: em, thermal, kinetic, explosive
                           Values should sum to 100 (percentages).
                           Default is omni damage (25% each).
                           Example: {"em": 50, "thermal": 40, "kinetic": 5, "explosive": 5}

            use_pilot_skills: If True, attempts to use authenticated pilot's skills.
                             If False (default), assumes all skills at level 5.

        Returns:
            Dictionary with complete fit statistics:
            - ship: Ship type and fit name
            - dps: Total and per-damage-type DPS breakdown
            - tank: HP, EHP, and resist percentages for shield/armor/hull
            - resources: CPU, powergrid, and calibration usage
            - capacitor: Capacity, recharge time, and recharge rate
            - mobility: Max velocity, agility, align time, warp speed
            - drones: Bandwidth, bay, and launched drone counts
            - slots: High/mid/low/rig slot usage
            - metadata: Skill mode, validation errors, warnings

        Examples:
            # Basic fit calculation with omni damage
            calculate_fit_stats(eft="[Vexor, Test]\\nDrone Damage Amplifier II...")

            # With custom damage profile (Amarr NPCs)
            calculate_fit_stats(
                eft="[Vexor, Test]\\n...",
                damage_profile={"em": 50, "thermal": 40, "kinetic": 5, "explosive": 5}
            )
        """
        from aria_esi.fitting import (
            EFTParseError,
            EOSBridgeError,
            EOSDataError,
            TypeResolutionError,
            get_eos_data_manager,
            parse_eft,
        )
        from aria_esi.fitting import (
            calculate_fit_stats as calc_stats,
        )
        from aria_esi.models.fitting import DamageProfile

        # Validate EOS data is available
        try:
            data_manager = get_eos_data_manager()
            data_manager.ensure_valid()
        except EOSDataError as e:
            return {
                "error": "eos_data_missing",
                "message": str(e),
                "missing_files": e.missing_files,
                "hint": "Run 'uv run aria-esi eos-seed' to download EOS data",
            }

        # Parse EFT string
        try:
            parsed_fit = parse_eft(eft)
        except TypeResolutionError as e:
            return {
                "error": "type_resolution_error",
                "message": str(e),
                "type_name": e.type_name,
                "suggestions": e.suggestions,
                "hint": "Check the type name spelling or run 'uv run aria-esi sde-seed' to update type data",
            }
        except EFTParseError as e:
            return {
                "error": "eft_parse_error",
                "message": str(e),
                "line_number": e.line_number,
                "hint": "Check the EFT format. Expected: [Ship Type, Fit Name] followed by modules",
            }

        # Build damage profile
        dmg_profile = DamageProfile.omni()
        if damage_profile:
            try:
                dmg_profile = DamageProfile(
                    em=float(damage_profile.get("em", 25)),
                    thermal=float(damage_profile.get("thermal", 25)),
                    kinetic=float(damage_profile.get("kinetic", 25)),
                    explosive=float(damage_profile.get("explosive", 25)),
                )
                if not dmg_profile.validate():
                    logger.warning("Damage profile doesn't sum to 100, using as-is")
            except (KeyError, ValueError, TypeError) as e:
                return {
                    "error": "invalid_damage_profile",
                    "message": f"Invalid damage profile: {e}",
                    "hint": "Damage profile should have keys: em, thermal, kinetic, explosive (percentages)",
                }

        # Get skill levels if using pilot skills
        skill_levels = None
        if use_pilot_skills:
            from aria_esi.fitting import SkillFetchError, fetch_pilot_skills

            try:
                fetch_result = fetch_pilot_skills()
                skill_levels = fetch_result.skills
                logger.info(
                    "Using pilot skills (%d skills loaded, source: %s)",
                    len(skill_levels),
                    fetch_result.source,
                )
            except SkillFetchError as e:
                if e.is_auth_error:
                    return {
                        "error": "authentication_required",
                        "message": str(e),
                        "hint": "Run 'aria-esi pilot' to check authentication status",
                    }
                # Fall back to all-V on other errors
                logger.warning("Could not fetch pilot skills, using all V: %s", e)
                skill_levels = None

        # Calculate statistics
        try:
            result = calc_stats(parsed_fit, dmg_profile, skill_levels)
            return result.to_dict()
        except EOSBridgeError as e:
            return {
                "error": "eos_calculation_error",
                "message": str(e),
                "hint": "EOS calculation failed. Check if EOS library is installed correctly.",
            }
        except Exception as e:
            logger.exception("Unexpected error calculating fit stats")
            return {
                "error": "calculation_error",
                "message": str(e),
            }
