"""
Fitting Dispatcher for MCP Server.

Provides ship fitting calculation interface:
- calculate_stats: Calculate complete fit statistics
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ...core.logging import get_logger
from ..context import log_context, wrap_scalar_output
from ..errors import InvalidParameterError
from ..policy import CapabilityDenied, ConfirmationRequired, check_capability
from ..validation import add_validation_warnings, validate_action_params

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from aria_esi.universe.graph import UniverseGraph


logger = get_logger(__name__)

FittingAction = Literal[
    "calculate_stats", "check_requirements", "extract_requirements", "recommend"
]

VALID_ACTIONS: set[str] = {
    "calculate_stats",
    "check_requirements",
    "extract_requirements",
    "recommend",
}

# NOTE: keep in sync with VALID_ROLES in tests/test_archetype_integrity.py
VALID_ROLES: set[str] = {
    "missions-l1",
    "missions-l2",
    "missions-l3",
    "missions-l4",
    "exploration-data",
    "exploration-relic",
    "exploration-combat",
    "mining-ore",
    "mining-gas",
    "mining-ice",
    "hauling-hisec",
    "hauling-lowsec",
    "pvp-solo",
    "pvp-fleet-dps",
    "pvp-fleet-logi",
    "pvp-fleet-tackle",
    "abyssal",
    "ratting-anomaly",
    "salvaging",
}

# Canonical tier ordering (ascending). Sort descending for recommend results.
TIER_ORDER: list[str] = ["t1", "meta", "t2_budget", "t2_optimal"]


def _get_project_root() -> Path:
    """Find project root by searching for pyproject.toml marker file."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError(f"Could not find project root (no pyproject.toml found above {__file__})")


def register_fitting_dispatcher(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register the unified fitting dispatcher with MCP server.

    Args:
        server: MCP Server instance
        universe: UniverseGraph (not used by fitting tools, kept for consistency)
    """

    @server.tool()
    @log_context("fitting")
    async def fitting(
        action: str,
        # calculate_stats params
        eft: str | None = None,
        damage_profile: dict | None = None,
        use_pilot_skills: bool = False,
        # check_requirements params
        pilot_skills: dict | None = None,
        # recommend params
        role: str | None = None,
        hull: str | None = None,
        budget_isk: int | None = None,
        skill_tier: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """
        Unified ship fitting interface.

        Actions:
        - calculate_stats: Calculate complete statistics for a ship fitting
        - check_requirements: Check if pilot can fly a fit
        - extract_requirements: Extract skill requirements from a fit
        - recommend: Search archetype library for fits matching constraints

        Args:
            action: The operation to perform

            Calculate stats params (action="calculate_stats"):
                eft: Ship fitting in EFT format. Example:
                     [Vexor, My Fit]
                     Drone Damage Amplifier II
                     ...
                damage_profile: Optional incoming damage profile for EHP
                               {"em": 25, "thermal": 25, "kinetic": 25, "explosive": 25}
                use_pilot_skills: Use pilot's cached skills (default False).
                                 Set True to use pilot-specific stats.

            Check requirements params (action="check_requirements"):
                eft: Ship fitting in EFT format
                pilot_skills: Dict mapping skill_id (int) to level (int)
                             e.g., {3436: 5, 33699: 4} for Drones V, Medium Drone Op IV

            Extract requirements params (action="extract_requirements"):
                eft: Ship fitting in EFT format

            Recommend params (action="recommend"):
                role: Required. Canonical role (e.g. "missions-l2", "exploration-data")
                hull: Optional. Filter to specific hull name
                budget_isk: Optional. Maximum total fit cost in ISK
                skill_tier: Optional. One of t1, meta, t2_budget, t2_optimal
                limit: Optional. Max results (default 5, minimum 1)

        Returns:
            For calculate_stats:
            - ship: Ship type and fit name
            - dps: Total and per-damage-type DPS breakdown
            - tank: HP, EHP, and resist percentages
            - resources: CPU, powergrid, and calibration usage
            - capacitor: Capacity, recharge time, rate
            - mobility: Velocity, agility, align time, warp speed
            - drones: Bandwidth, bay, launched counts
            - slots: High/mid/low/rig slot usage
            - metadata: Skill mode, validation errors, warnings

            For check_requirements:
            - can_fly: bool - True if pilot meets all requirements
            - missing_skills: List of {skill_id, skill_name, required, current}
            - total_skills_checked: int

            For extract_requirements:
            - skills: List of "Skill Name Level" strings
            - skill_ids: Dict mapping skill_id to required level
            - total_skills: int

            For recommend:
            - results: List of {hull, path, tier, roles, estimated_cost}
            - message: Optional string (null on success, info message on no-match)

        Examples:
            fitting(action="calculate_stats", eft="[Vexor, Test]\\nDrone Damage Amplifier II...")
            fitting(action="check_requirements", eft="[Vexor, ...]", pilot_skills={3436: 5})
            fitting(action="extract_requirements", eft="[Vexor, ...]")
            fitting(action="recommend", role="missions-l2", budget_isk=20000000)
        """
        if action not in VALID_ACTIONS:
            raise InvalidParameterError(
                "action",
                action,
                f"Must be one of: {', '.join(sorted(VALID_ACTIONS))}",
            )

        # Policy check - verify action is allowed
        # Pass use_pilot_skills context for context-aware sensitivity escalation
        # If policy denies authenticated access, fall back to all-V calculation
        policy_fallback_warning = None
        effective_use_pilot_skills = use_pilot_skills

        try:
            check_capability("fitting", action, context={"use_pilot_skills": use_pilot_skills})
        except ConfirmationRequired as e:
            if use_pilot_skills:
                # User needs to explicitly opt-in for authenticated access
                # Fall back to all-V skills for now
                logger.info(
                    "Authenticated fitting access requires confirmation, falling back to all-V: %s",
                    e,
                )
                check_capability("fitting", action, context={"use_pilot_skills": False})
                effective_use_pilot_skills = False
                policy_fallback_warning = (
                    "Pilot skill data requires explicit consent (security policy). "
                    "Stats calculated with all skills at V - actual performance may vary. "
                    "Use /fit-check or /skillplan for pilot-specific analysis."
                )
            else:
                raise
        except CapabilityDenied as e:
            if use_pilot_skills and e.sensitivity and e.sensitivity.value == "authenticated":
                # Retry without pilot skills (falls back to PUBLIC sensitivity)
                logger.warning(
                    "Policy denied authenticated fitting access, falling back to all-V: %s",
                    e,
                )
                check_capability("fitting", action, context={"use_pilot_skills": False})
                effective_use_pilot_skills = False
                policy_fallback_warning = (
                    "Pilot skill data unavailable (policy: authenticated not allowed). "
                    "Stats calculated with all skills at V - actual performance may vary. "
                    "To enable: add 'authenticated' to allowed_levels in reference/mcp-policy.json"
                )
            else:
                raise

        # Validate parameters for this action
        # Warns when irrelevant parameters are passed
        validation_warnings = validate_action_params(
            "fitting",
            action,
            {
                "eft": eft,
                "damage_profile": damage_profile,
                "use_pilot_skills": use_pilot_skills,
                "pilot_skills": pilot_skills,
                "role": role,
                "hull": hull,
                "budget_isk": budget_isk,
                "skill_tier": skill_tier,
                "limit": limit,
            },
        )

        # Execute action
        match action:
            case "calculate_stats":
                result = await _calculate_stats(eft, damage_profile, effective_use_pilot_skills)
                # Add policy warning to result if we fell back
                if policy_fallback_warning and isinstance(result, dict):
                    if "metadata" not in result:
                        result["metadata"] = {}
                    if "warnings" not in result["metadata"]:
                        result["metadata"]["warnings"] = []
                    result["metadata"]["warnings"].append(policy_fallback_warning)
            case "check_requirements":
                result = await _check_requirements(eft, pilot_skills)
            case "extract_requirements":
                result = await _extract_requirements(eft)
            case "recommend":
                result = await _recommend(role, hull, budget_isk, skill_tier, limit)
            case _:
                raise InvalidParameterError("action", action, f"Unknown action: {action}")

        # Add validation warnings to result if any
        return add_validation_warnings(result, validation_warnings)


async def _calculate_stats(
    eft: str | None,
    damage_profile: dict | None,
    use_pilot_skills: bool,
) -> dict:
    """Calculate stats action - compute fit statistics."""
    if not eft:
        raise InvalidParameterError("eft", eft, "Required for action='calculate_stats'")

    try:
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
    except ImportError as e:
        return {
            "error": "fitting_not_available",
            "message": f"Fitting module dependencies not installed: {e}",
            "hint": "Install with: uv pip install 'aria[fitting]'",
        }

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
    skill_source = "all_v"
    skill_warning = None

    if use_pilot_skills:
        from aria_esi.fitting import SkillFetchError, fetch_pilot_skills

        try:
            fetch_result = fetch_pilot_skills()
            skill_levels = fetch_result.skills
            skill_source = fetch_result.source
            logger.info(
                "Using pilot skills (%d skills, source: %s)", len(skill_levels), skill_source
            )
        except SkillFetchError as e:
            if e.is_auth_error:
                return {
                    "error": "authentication_required",
                    "message": str(e),
                    "hint": "Run 'aria-esi pilot' to check authentication status",
                }
            logger.warning("Could not fetch pilot skills, using all V: %s", e)
            skill_levels = None
            skill_source = "all_v"
            skill_warning = (
                "Using All-V: could not fetch pilot skills. "
                "Run 'uv run aria-esi sync-skills' to cache your skills."
            )
    else:
        # Explicitly requested all-V mode
        skill_source = "all_v"

    # Check if we fell back to all-V unexpectedly (requested pilot skills but none found)
    if use_pilot_skills and skill_levels is None and skill_warning is None:
        skill_warning = (
            "Using All-V: no cached skills found. "
            "Run 'uv run aria-esi sync-skills' to cache your skills."
        )

    # Calculate statistics
    try:
        result = calc_stats(parsed_fit, dmg_profile, skill_levels)
        result_dict = result.to_dict()

        # Add skill source to metadata
        if "metadata" not in result_dict:
            result_dict["metadata"] = {}
        result_dict["metadata"]["skill_mode"] = "pilot_skills" if skill_levels else "all_v"
        result_dict["metadata"]["skill_source"] = skill_source
        if skill_warning:
            result_dict["metadata"]["skill_warning"] = skill_warning

        return wrap_scalar_output(result_dict, count=1, source="eos")
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


async def _check_requirements(
    eft: str | None,
    pilot_skills: dict | None,
) -> dict:
    """Check if pilot meets skill requirements for a fit."""
    if not eft:
        raise InvalidParameterError("eft", eft, "Required for action='check_requirements'")
    if not pilot_skills:
        raise InvalidParameterError(
            "pilot_skills", pilot_skills, "Required for action='check_requirements'"
        )

    try:
        from aria_esi.fitting import (
            EFTParseError,
            EOSDataError,
            TypeResolutionError,
            get_eos_data_manager,
            parse_eft,
        )
        from aria_esi.fitting.skills import _load_skill_requirements
    except ImportError as e:
        return {
            "error": "fitting_not_available",
            "message": f"Fitting module dependencies not installed: {e}",
            "hint": "Install with: uv pip install 'aria[fitting]'",
        }

    # Validate EOS data is available
    try:
        data_manager = get_eos_data_manager()
        data_manager.ensure_valid()
    except EOSDataError as e:
        return {
            "error": "eos_data_missing",
            "message": str(e),
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
        }
    except EFTParseError as e:
        return {
            "error": "eft_parse_error",
            "message": str(e),
            "line_number": e.line_number,
        }

    # Convert pilot_skills keys to integers
    pilot_skill_levels: dict[int, int] = {}
    for skill_id, level in pilot_skills.items():
        try:
            pilot_skill_levels[int(skill_id)] = int(level)
        except (ValueError, TypeError):
            logger.warning("Invalid skill entry: %s -> %s", skill_id, level)

    # Load skill requirements database
    skill_reqs = _load_skill_requirements()

    # Collect all type IDs from the fit
    type_ids: list[int] = [parsed_fit.ship_type_id]
    for module in parsed_fit.low_slots + parsed_fit.mid_slots + parsed_fit.high_slots:
        type_ids.append(module.type_id)
        if module.charge_type_id:
            type_ids.append(module.charge_type_id)
    for rig in parsed_fit.rigs:
        type_ids.append(rig.type_id)
    for subsystem in parsed_fit.subsystems:
        type_ids.append(subsystem.type_id)
    for drone in parsed_fit.drones:
        type_ids.append(drone.type_id)

    # Collect the highest required level per skill across all items
    max_required: dict[int, int] = {}
    for type_id in type_ids:
        reqs = skill_reqs.get(type_id, {})
        for skill_id, required_level in reqs.items():
            if required_level > max_required.get(skill_id, 0):
                max_required[skill_id] = required_level

    # Check against pilot skills
    missing_skills: list[dict] = []
    for skill_id, required_level in max_required.items():
        current_level = pilot_skill_levels.get(skill_id, 0)
        if current_level < required_level:
            skill_name = _resolve_skill_name(skill_id)
            missing_skills.append(
                {
                    "skill_id": skill_id,
                    "skill_name": skill_name,
                    "required": required_level,
                    "current": current_level,
                }
            )

    can_fly = len(missing_skills) == 0

    return wrap_scalar_output(
        {
            "can_fly": can_fly,
            "missing_skills": sorted(missing_skills, key=lambda x: x["skill_name"]),
            "total_skills_checked": len(max_required),
        },
        count=len(max_required),
        source="eos",
    )


async def _extract_requirements(eft: str | None) -> dict:
    """Extract all skill requirements from a fit."""
    if not eft:
        raise InvalidParameterError("eft", eft, "Required for action='extract_requirements'")

    try:
        from aria_esi.fitting import (
            EFTParseError,
            EOSDataError,
            TypeResolutionError,
            get_eos_data_manager,
            parse_eft,
        )
        from aria_esi.fitting.skills import extract_skills_for_fit
    except ImportError as e:
        return {
            "error": "fitting_not_available",
            "message": f"Fitting module dependencies not installed: {e}",
            "hint": "Install with: uv pip install 'aria[fitting]'",
        }

    # Validate EOS data is available
    try:
        data_manager = get_eos_data_manager()
        data_manager.ensure_valid()
    except EOSDataError as e:
        return {
            "error": "eos_data_missing",
            "message": str(e),
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
        }
    except EFTParseError as e:
        return {
            "error": "eft_parse_error",
            "message": str(e),
            "line_number": e.line_number,
        }

    # Extract skills (returns skill_id -> level mapping)
    skill_ids = extract_skills_for_fit(parsed_fit, level=5)

    # Format as "Skill Name Level" strings
    skills: list[str] = []
    for skill_id, level in sorted(skill_ids.items()):
        skill_name = _resolve_skill_name(skill_id)
        skills.append(f"{skill_name} {level}")

    return wrap_scalar_output(
        {
            "skills": sorted(skills),
            "skill_ids": skill_ids,
            "total_skills": len(skill_ids),
        },
        count=len(skill_ids),
        source="eos",
    )


async def _recommend(
    role: str | None,
    hull: str | None,
    budget_isk: int | None,
    skill_tier: str | None,
    limit: int | None,
) -> dict:
    """Recommend archetypes from INDEX.md matching constraints."""
    # --- Parameter validation ---
    if not role:
        raise InvalidParameterError("role", role, "Required for action='recommend'")
    if role not in VALID_ROLES:
        raise InvalidParameterError(
            "role",
            role,
            f"Invalid role '{role}', must be one of: {', '.join(sorted(VALID_ROLES))}",
        )
    if skill_tier is not None and skill_tier not in VALID_SKILL_TIERS:
        raise InvalidParameterError(
            "skill_tier",
            skill_tier,
            f"Must be one of: {', '.join(sorted(VALID_SKILL_TIERS))}",
        )
    if budget_isk is not None and budget_isk <= 0:
        raise InvalidParameterError("budget_isk", budget_isk, "Must be a positive integer")

    effective_limit = limit if limit is not None else 5
    if effective_limit <= 0:
        raise InvalidParameterError("limit", limit, "Must be a positive integer")

    # --- Parse INDEX.md ---
    project_root = _get_project_root()
    index_path = project_root / "reference" / "archetypes" / "INDEX.md"

    if not index_path.exists():
        raise InvalidParameterError(
            "action",
            "recommend",
            "Archetype INDEX.md not found at reference/archetypes/INDEX.md",
        )

    index_text = index_path.read_text()
    entries: list[dict] = []

    for line in index_text.splitlines():
        m = re.match(
            r"\|\s*(\w[\w\s]*?)\s*\|\s*(\w+)\s*\|\s*(\S+)\s*\|\s*(\w+)\s*\|\s*([^|]*?)\s*\|\s*`([^`]+)`\s*\|",
            line,
        )
        if not m or m.group(1).strip() == "Hull":
            continue
        entry_roles_str = m.group(5).strip()
        entry_roles = entry_roles_str.split(",") if entry_roles_str else []

        entries.append(
            {
                "hull": m.group(1).strip(),
                "tier": m.group(4).strip(),
                "roles": entry_roles,
                "path": m.group(6).strip(),
            }
        )

    if not entries:
        return {"results": [], "message": "Archetype index is empty or malformed."}

    # --- Filter ---
    filtered = []
    for entry in entries:
        if role not in entry["roles"]:
            continue
        if hull and entry["hull"].lower() != hull.lower():
            continue
        if skill_tier and entry["tier"] != skill_tier:
            continue
        filtered.append(entry)

    if not filtered:
        return {"results": [], "message": "No archetypes match the given constraints."}

    # --- Sort by tier (descending: t2_optimal > t2_budget > meta > t1) ---
    tier_rank = {t: i for i, t in enumerate(TIER_ORDER)}
    filtered.sort(key=lambda e: tier_rank.get(e["tier"], -1), reverse=True)

    # --- Estimate costs ---
    results: list[dict] = []
    all_null_cost = True

    for entry in filtered:
        estimated_cost = _estimate_cost(project_root, entry["path"])

        if estimated_cost is not None:
            all_null_cost = False

        # Budget filtering: omit null-cost entries when budget specified
        if budget_isk is not None:
            if estimated_cost is None:
                continue
            if estimated_cost > budget_isk:
                continue

        results.append(
            {
                "hull": entry["hull"],
                "path": entry["path"],
                "tier": entry["tier"],
                "roles": entry["roles"],
                "estimated_cost": estimated_cost,
            }
        )

        if len(results) >= effective_limit:
            break

    # --- Determine message ---
    if not results:
        if budget_isk is not None and all_null_cost and filtered:
            return {
                "results": [],
                "message": (
                    "Archetypes exist for this role but market data is unavailable "
                    "to verify budget. Try without a budget constraint."
                ),
            }
        if budget_isk is not None and filtered:
            return {
                "results": [],
                "message": "No archetypes match the given constraints.",
            }
        return {"results": [], "message": "No archetypes match the given constraints."}

    return {"results": results, "message": None}


# Valid skill tiers (mirrors test constant)
VALID_SKILL_TIERS: set[str] = {"t1", "meta", "t2_budget", "t2_optimal"}


def _estimate_cost(project_root: Path, archetype_path: str) -> int | None:
    """
    Estimate total fit cost from an archetype's EFT block.

    Returns estimated cost in ISK, or None if pricing is unavailable.
    """
    import yaml

    yaml_path = project_root / "reference" / "archetypes" / archetype_path
    if not yaml_path.exists():
        return None

    try:
        data = yaml.safe_load(yaml_path.read_text())
    except (yaml.YAMLError, OSError):
        logger.warning("Failed to parse archetype YAML: %s", archetype_path)
        return None

    eft_string = data.get("eft")
    if not eft_string:
        return None

    try:
        from aria_esi.fitting import EFTParseError, TypeResolutionError, parse_eft
    except ImportError:
        return None

    try:
        parsed_fit = parse_eft(eft_string.strip())
    except (EFTParseError, TypeResolutionError):
        logger.warning("Failed to parse EFT for cost estimation: %s", archetype_path)
        return None

    # Collect all type IDs
    type_ids: list[int] = [parsed_fit.ship_type_id]
    for module in (
        parsed_fit.low_slots
        + parsed_fit.mid_slots
        + parsed_fit.high_slots
        + parsed_fit.rigs
        + parsed_fit.subsystems
    ):
        type_ids.append(module.type_id)
    for drone in parsed_fit.drones:
        type_ids.append(drone.type_id)

    # Get prices from market database
    try:
        from aria_esi.store.market.database import get_market_database

        db = get_market_database()
        aggregates = db.get_aggregates_batch(type_ids, region_id=10000002)
    except (ImportError, RuntimeError, OSError):
        logger.debug("Market database unavailable for cost estimation")
        return None

    # Sum sell_min across all items; all must be priced or return None
    total: float = 0
    for type_id in type_ids:
        agg = aggregates.get(type_id)
        if agg is None or agg.sell_min is None:
            return None
        total += agg.sell_min

    # Account for drone quantities (type_ids has one entry per drone type)
    drone_adjustment: float = 0
    for drone in parsed_fit.drones:
        agg = aggregates.get(drone.type_id)
        if agg is None or agg.sell_min is None:
            return None
        # Already counted once above; add extra copies
        drone_adjustment += agg.sell_min * (drone.quantity - 1)

    return int(total + drone_adjustment)


def _resolve_skill_name(skill_id: int) -> str:
    """Resolve skill ID to name via SDE."""
    try:
        from aria_esi.store.market.database import get_market_database

        db = get_market_database()
        type_info = db.resolve_type_id(skill_id)
        if type_info:
            return type_info.type_name
    except (ImportError, RuntimeError) as e:
        logger.debug("Could not resolve skill name for %d: %s", skill_id, e)

    return f"Unknown Skill ({skill_id})"
