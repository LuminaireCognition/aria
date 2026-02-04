"""
ARIA ESI Fit Selection Commands

Commands for skill-aware fit selection from the archetype library.
"""

import argparse
from typing import Any, Literal

from ..core import format_isk, get_utc_timestamp

# =============================================================================
# Command: fit select
# =============================================================================


def cmd_fit_select(args: argparse.Namespace) -> dict[str, Any]:
    """
    Select appropriate fit(s) based on pilot skills.

    Analyzes pilot skills and returns recommended fit(s) from the
    archetype library.
    """
    from ..archetypes.selection import select_fits
    from ..fitting.skills import SkillFetchError, fetch_pilot_skills

    query_ts = get_utc_timestamp()
    archetype_path = args.archetype
    mission = getattr(args, "mission", None)

    print("=" * 60)
    print("FIT SELECTION")
    print("=" * 60)
    print(f"Archetype: {archetype_path}")

    # Fetch pilot skills
    print("\nFetching pilot skills...")
    try:
        pilot_skills = fetch_pilot_skills()
        print(f"Loaded {len(pilot_skills)} trained skills")
    except SkillFetchError as e:
        print(f"Error fetching skills: {e}")
        return {
            "error": "skill_fetch_failed",
            "message": str(e),
            "query_timestamp": query_ts,
        }

    # Determine clone status
    # TODO: Fetch from ESI when clone endpoint available
    clone_status: Literal["alpha", "omega"] = "omega"
    print(f"Clone status: {clone_status}")

    # Build mission context if provided
    mission_context = None
    if mission:
        from ..archetypes.models import MissionContext

        # Parse mission level from path (e.g., "vexor/pve/missions/l2" -> level 2)
        level = 2  # Default
        if "/l1" in archetype_path.lower():
            level = 1
        elif "/l2" in archetype_path.lower():
            level = 2
        elif "/l3" in archetype_path.lower():
            level = 3
        elif "/l4" in archetype_path.lower():
            level = 4

        mission_context = MissionContext(
            mission_level=level,
            mission_name=mission,
        )
        print(f"Mission context: Level {level} - {mission}")

    # Perform selection
    print("\nEvaluating fits...")
    result = select_fits(
        archetype_path=archetype_path,
        pilot_skills=pilot_skills,
        clone_status=clone_status,
        mission_context=mission_context,
    )

    # Display results
    print()
    print("-" * 60)
    print(f"Selection mode: {result.selection_mode}")
    print(f"Candidates evaluated: {len(result.candidates)}")

    if result.filters_applied:
        print(f"Filters: {', '.join(result.filters_applied)}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    if result.selection_mode == "none":
        print("\nNo suitable fits found.")
        if result.recommended:
            print("\nClosest option (not currently flyable):")
            _display_candidate(result.recommended)

    elif result.selection_mode == "single":
        print("\nRecommended fit:")
        _display_candidate(result.recommended)
        if result.recommended and result.recommended.archetype:
            print("\n--- EFT ---")
            print(result.recommended.archetype.eft)

    elif result.selection_mode == "dual":
        print("\nEfficient option (lower cost):")
        _display_candidate(result.efficient)

        print("\nPremium option (better stats):")
        _display_candidate(result.premium)

        print("\nUse --tier <tier> to see full EFT for a specific option")

    return {
        "command": "fit-select",
        "archetype_path": archetype_path,
        "clone_status": clone_status,
        "result": result.to_dict(),
        "query_timestamp": query_ts,
    }


def _display_candidate(candidate) -> None:
    """Display a fit candidate summary."""
    if not candidate:
        print("  (none)")
        return

    arch = candidate.archetype
    if not arch:
        print(f"  Tier: {candidate.tier}")
        return

    print(f"  Tier: {candidate.tier}")
    print(f"  Can fly: {'Yes' if candidate.can_fly else 'No'}")

    if not candidate.can_fly:
        print(f"  Missing skills: {len(candidate.missing_skills)}")

    print(f"  DPS: {arch.stats.dps}")
    print(f"  EHP: {arch.stats.ehp}")

    if arch.stats.tank_sustained:
        print(f"  Tank: {arch.stats.tank_sustained} HP/s")

    if arch.stats.estimated_isk:
        print(f"  Est. cost: {format_isk(arch.stats.estimated_isk)}")


# =============================================================================
# Command: fit check
# =============================================================================


def cmd_fit_check(args: argparse.Namespace) -> dict[str, Any]:
    """
    Check if pilot can fly a specific archetype/tier.
    """
    from ..archetypes.selection import can_fly_archetype
    from ..fitting.skills import SkillFetchError, fetch_pilot_skills

    query_ts = get_utc_timestamp()
    archetype_path = args.archetype

    print("=" * 60)
    print("FIT REQUIREMENTS CHECK")
    print("=" * 60)
    print(f"Archetype: {archetype_path}")

    # Fetch pilot skills
    print("\nFetching pilot skills...")
    try:
        pilot_skills = fetch_pilot_skills()
        print(f"Loaded {len(pilot_skills)} trained skills")
    except SkillFetchError as e:
        print(f"Error fetching skills: {e}")
        return {
            "error": "skill_fetch_failed",
            "message": str(e),
            "query_timestamp": query_ts,
        }

    # Check requirements
    can_fly, missing = can_fly_archetype(archetype_path, pilot_skills)

    print()
    print("-" * 60)

    if can_fly:
        print("Result: CAN FLY")
        print("All skill requirements met!")
    else:
        print("Result: CANNOT FLY")
        print(f"\nMissing {len(missing)} skill(s):")

        for skill in missing:
            skill_id = skill.get("skill_id", "?")
            required = skill.get("required", "?")
            current = skill.get("current", 0)
            print(f"  - Skill ID {skill_id}: need {required}, have {current}")

    return {
        "command": "fit-check",
        "archetype_path": archetype_path,
        "can_fly": can_fly,
        "missing_skills": missing,
        "query_timestamp": query_ts,
    }


# =============================================================================
# Command: fit refresh-prices
# =============================================================================


def cmd_fit_refresh_prices(args: argparse.Namespace) -> dict[str, Any]:
    """
    Refresh ISK estimates for archetype fits.
    """
    from ..archetypes import list_archetypes, load_archetype
    from ..archetypes.pricing import estimate_fit_price

    query_ts = get_utc_timestamp()
    archetype_path = args.archetype
    region = getattr(args, "region", "jita")

    print("=" * 60)
    print("FIT PRICE REFRESH")
    print("=" * 60)
    print(f"Region: {region}")

    # Determine paths to refresh
    if archetype_path:
        # Single archetype or base path
        if "/" in archetype_path:
            parts = archetype_path.split("/")
            if parts[-1] in (
                "t1",
                "meta",
                "t2_budget",
                "t2_optimal",
                "low",
                "medium",
                "high",
                "alpha",
            ):
                # Full path with tier
                paths = [archetype_path]
            else:
                # Base path - find all tiers
                all_archetypes = list_archetypes()
                paths = [p for p in all_archetypes if p.startswith(archetype_path)]
        else:
            # Just hull name
            all_archetypes = list_archetypes(archetype_path)
            paths = all_archetypes
    else:
        # All archetypes
        paths = list_archetypes()

    print(f"Archetypes to price: {len(paths)}")
    print()

    results = []
    total_updated = 0
    total_errors = 0

    for path in paths:
        archetype = load_archetype(path)
        if not archetype:
            print(f"[SKIP] {path} - not found")
            total_errors += 1
            continue

        estimate = estimate_fit_price(archetype.eft, region)

        if estimate.total_isk > 0:
            print(f"[OK] {path}: {format_isk(estimate.total_isk)}")
            total_updated += 1
            results.append(
                {
                    "path": path,
                    "estimated_isk": estimate.total_isk,
                    "status": "ok",
                }
            )
        else:
            print(f"[WARN] {path}: price unavailable")
            if estimate.warnings:
                for w in estimate.warnings[:3]:  # Show first 3 warnings
                    print(f"       {w}")
            results.append(
                {
                    "path": path,
                    "estimated_isk": 0,
                    "status": "unavailable",
                    "warnings": estimate.warnings,
                }
            )

    print()
    print("-" * 60)
    print(f"Total: {len(paths)}")
    print(f"Priced: {total_updated}")
    print(f"Errors: {total_errors}")

    return {
        "command": "fit-refresh-prices",
        "region": region,
        "total": len(paths),
        "updated": total_updated,
        "errors": total_errors,
        "results": results,
        "query_timestamp": query_ts,
    }


# =============================================================================
# Command: fit update-stats
# =============================================================================


def cmd_fit_update_stats(args: argparse.Namespace) -> dict[str, Any]:
    """
    Update stats section in archetype YAML files using EOS calculations.

    Calculates DPS, EHP, tank type, resist profiles, and optionally ISK
    estimates, then writes them back to the archetype YAML files.
    """
    from datetime import datetime, timezone

    from ..archetypes import list_archetypes, load_archetype
    from ..archetypes.loader import get_archetype_yaml_path, update_archetype_stats
    from ..archetypes.models import Stats
    from ..archetypes.pricing import estimate_fit_price
    from ..fitting import (
        analyze_tank,
        calculate_fit_stats,
        derive_primary_damage,
        parse_eft,
    )

    query_ts = get_utc_timestamp()
    archetype_path = getattr(args, "archetype", None)
    hull_filter = getattr(args, "hull", None)
    update_all = getattr(args, "all", False)
    dry_run = getattr(args, "dry_run", False)
    skip_prices = getattr(args, "no_prices", False)
    region = getattr(args, "region", "jita")

    print("=" * 60)
    print("FIT STATS UPDATE")
    print("=" * 60)

    if dry_run:
        print("[DRY RUN - no files will be modified]")

    # Determine paths to update
    paths: list[str] = []

    if update_all:
        paths = list_archetypes()
        print(f"Updating all archetypes: {len(paths)} files")
    elif hull_filter:
        paths = list_archetypes(hull_filter)
        print(f"Updating archetypes for hull '{hull_filter}': {len(paths)} files")
    elif archetype_path:
        # Single archetype or base path
        if "/" in archetype_path:
            parts = archetype_path.split("/")
            if parts[-1] in (
                "t1",
                "meta",
                "t2_budget",
                "t2_optimal",
                "low",
                "medium",
                "high",
                "alpha",
            ):
                # Full path with tier
                paths = [archetype_path]
            else:
                # Base path - find all tiers
                all_archetypes = list_archetypes()
                paths = [p for p in all_archetypes if p.startswith(archetype_path)]
        else:
            # Just hull name
            paths = list_archetypes(archetype_path)
        print(f"Archetypes to update: {len(paths)}")
    else:
        print("Error: Specify an archetype path, --hull, or --all")
        return {
            "error": "no_target",
            "message": "No archetype target specified",
            "query_timestamp": query_ts,
        }

    if not paths:
        print("No archetypes found matching criteria")
        return {
            "error": "no_archetypes",
            "message": "No archetypes found",
            "query_timestamp": query_ts,
        }

    print()

    # Process each archetype
    results: list[dict[str, Any]] = []
    total_updated = 0
    total_errors = 0
    total_skipped = 0

    for path in paths:
        archetype = load_archetype(path)
        if not archetype:
            print(f"[SKIP] {path} - not found")
            total_skipped += 1
            results.append({"path": path, "status": "not_found"})
            continue

        # Parse EFT for EOS calculation
        try:
            parsed_fit = parse_eft(archetype.eft)
            if not parsed_fit:
                print(f"[SKIP] {path} - failed to parse EFT")
                total_skipped += 1
                results.append({"path": path, "status": "parse_error"})
                continue
        except Exception as e:
            print(f"[ERR] {path} - EFT parse error: {e}")
            total_errors += 1
            results.append({"path": path, "status": "parse_error", "error": str(e)})
            continue

        # Calculate stats via EOS
        try:
            fit_stats = calculate_fit_stats(parsed_fit)
        except Exception as e:
            print(f"[ERR] {path} - EOS calculation failed: {e}")
            total_errors += 1
            results.append({"path": path, "status": "eos_error", "error": str(e)})
            continue

        # Analyze tank
        tank_analysis = analyze_tank(parsed_fit, fit_stats.to_dict())

        # Derive primary damage types from DPS breakdown
        dps_by_type = {
            "em": fit_stats.dps.em,
            "thermal": fit_stats.dps.thermal,
            "kinetic": fit_stats.dps.kinetic,
            "explosive": fit_stats.dps.explosive,
        }
        primary_damage = derive_primary_damage(dps_by_type)

        # Get current date for validated_date
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Get resists from primary tank layer
        tank_dict = fit_stats.tank.to_dict()
        armor_ehp = tank_dict["armor"]["ehp"]
        shield_ehp = tank_dict["shield"]["ehp"]

        if armor_ehp > shield_ehp:
            resists = tank_dict["armor"]["resists"]
        else:
            resists = tank_dict["shield"]["resists"]

        # Estimate price if enabled
        estimated_isk = None
        isk_updated = None
        if not skip_prices:
            try:
                price_estimate = estimate_fit_price(archetype.eft, region)
                if price_estimate.total_isk > 0:
                    estimated_isk = price_estimate.total_isk
                    isk_updated = today
            except Exception as e:
                print(f"  [WARN] {path} - price estimation failed: {e}")

        # Build new Stats object
        new_stats = Stats(
            dps=fit_stats.dps.total,
            ehp=fit_stats.tank.total_ehp,
            tank_sustained=tank_analysis.get("tank_regen"),
            capacitor_stable=archetype.stats.capacitor_stable,  # Preserve existing
            align_time=fit_stats.mobility.align_time,
            speed_mwd=archetype.stats.speed_mwd,  # Preserve - needs MWD active
            speed_ab=archetype.stats.speed_ab,  # Preserve - needs AB active
            drone_control_range=archetype.stats.drone_control_range,  # Preserve
            missile_range=archetype.stats.missile_range,  # Preserve
            validated_date=today,
            # New fields
            tank_type=tank_analysis.get("tank_type"),
            tank_regen=tank_analysis.get("tank_regen"),
            primary_resists=tank_analysis.get("primary_resists", []),
            primary_damage=primary_damage,
            dps_by_type=dps_by_type,
            resists=resists,
            estimated_isk=estimated_isk,
            isk_updated=isk_updated,
        )

        # Display update summary
        isk_str = f", {format_isk(estimated_isk)}" if estimated_isk else ""
        print(
            f"[OK] {path}: DPS={int(new_stats.dps)}, "
            f"EHP={int(new_stats.ehp)}, "
            f"tank={new_stats.tank_type}{isk_str}"
        )

        if dry_run:
            results.append(
                {
                    "path": path,
                    "status": "dry_run",
                    "stats": new_stats.to_dict(),
                }
            )
            total_updated += 1
            continue

        # Write stats back to YAML
        yaml_path = get_archetype_yaml_path(path)
        if not yaml_path:
            print(f"  [ERR] Could not resolve YAML path for {path}")
            total_errors += 1
            results.append({"path": path, "status": "path_error"})
            continue

        try:
            update_archetype_stats(yaml_path, new_stats)
            total_updated += 1
            results.append(
                {
                    "path": path,
                    "status": "updated",
                    "stats": new_stats.to_dict(),
                }
            )
        except Exception as e:
            print(f"  [ERR] Failed to write {path}: {e}")
            total_errors += 1
            results.append({"path": path, "status": "write_error", "error": str(e)})

    # Summary
    print()
    print("-" * 60)
    print(f"Total: {len(paths)}")
    print(f"Updated: {total_updated}")
    print(f"Skipped: {total_skipped}")
    print(f"Errors: {total_errors}")

    return {
        "command": "fit-update-stats",
        "dry_run": dry_run,
        "region": region,
        "total": len(paths),
        "updated": total_updated,
        "skipped": total_skipped,
        "errors": total_errors,
        "results": results,
        "query_timestamp": query_ts,
    }


# =============================================================================
# Command: fit validate
# =============================================================================


def cmd_fit_validate(args: argparse.Namespace) -> dict[str, Any]:
    """
    Validate archetype fits including omega_required consistency.
    """
    from ..archetypes.validator import ArchetypeValidator, validate_all_archetypes

    query_ts = get_utc_timestamp()
    archetype_path = getattr(args, "archetype", None)
    hull_filter = getattr(args, "hull", None)
    use_eos = getattr(args, "eos", False)

    print("=" * 60)
    print("FIT VALIDATION")
    print("=" * 60)

    if archetype_path:
        # Single archetype
        validator = ArchetypeValidator(use_eos=use_eos)
        result = validator.validate_archetype(archetype_path)
        results = [result]
        print(f"Validating: {archetype_path}")
    else:
        # All archetypes (optionally filtered by hull)
        results = validate_all_archetypes(hull=hull_filter, use_eos=use_eos)
        if hull_filter:
            print(f"Validating all archetypes for hull: {hull_filter}")
        else:
            print("Validating all archetypes")

    print()

    total_errors = 0
    total_warnings = 0

    for result in results:
        if not result.is_valid or result.warnings:
            status = "FAIL" if not result.is_valid else "WARN"
            print(f"[{status}] {result.path}")

            for issue in result.issues:
                prefix = "  ERROR" if issue.level == "error" else "  WARN"
                print(f"  {prefix}: {issue.message}")

            total_errors += len(result.errors)
            total_warnings += len(result.warnings)
        else:
            print(f"[OK] {result.path}")

    print()
    print("-" * 60)
    print(f"Total archetypes: {len(results)}")
    print(f"Valid: {sum(1 for r in results if r.is_valid)}")
    print(f"Invalid: {sum(1 for r in results if not r.is_valid)}")
    print(f"Total errors: {total_errors}")
    print(f"Total warnings: {total_warnings}")

    return {
        "command": "fit-validate",
        "total": len(results),
        "valid": sum(1 for r in results if r.is_valid),
        "invalid": sum(1 for r in results if not r.is_valid),
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "results": [r.to_dict() for r in results],
        "query_timestamp": query_ts,
    }


# =============================================================================
# Parser Registration
# =============================================================================


def register_parsers(subparsers) -> None:
    """Register fit command parsers."""

    # fit command group
    fit_parser = subparsers.add_parser(
        "fit",
        help="Fit selection commands (use 'fit select', 'fit check', etc.)",
        description="Skill-aware fit selection from archetype library",
    )

    fit_subparsers = fit_parser.add_subparsers(dest="fit_command")

    # fit select
    select_cmd = fit_subparsers.add_parser(
        "select",
        help="Select appropriate fit(s) based on pilot skills",
    )
    select_cmd.add_argument(
        "archetype",
        help="Archetype base path (e.g., vexor/pve/missions/l2)",
    )
    select_cmd.add_argument(
        "--mission",
        "-m",
        help="Mission name for context-aware selection",
    )
    select_cmd.add_argument(
        "--tier",
        "-t",
        help="Show specific tier's EFT",
    )
    select_cmd.set_defaults(func=cmd_fit_select)

    # fit check
    check_cmd = fit_subparsers.add_parser(
        "check",
        help="Check if pilot can fly specific archetype/tier",
    )
    check_cmd.add_argument(
        "archetype",
        help="Full archetype path including tier (e.g., vexor/pve/missions/l2/meta)",
    )
    check_cmd.set_defaults(func=cmd_fit_check)

    # fit refresh-prices
    prices_cmd = fit_subparsers.add_parser(
        "refresh-prices",
        help="Refresh ISK estimates for archetype fits",
    )
    prices_cmd.add_argument(
        "archetype",
        nargs="?",
        help="Archetype path to price (or all if omitted)",
    )
    prices_cmd.add_argument(
        "--region",
        "-r",
        default="jita",
        help="Trade hub for prices (default: jita)",
    )
    prices_cmd.set_defaults(func=cmd_fit_refresh_prices)

    # fit update-stats
    update_stats_cmd = fit_subparsers.add_parser(
        "update-stats",
        help="Update stats section in archetype YAML files using EOS calculations",
    )
    update_stats_cmd.add_argument(
        "archetype",
        nargs="?",
        help="Archetype path (e.g., vexor/pve/missions/l2/t1)",
    )
    update_stats_cmd.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Update all archetypes",
    )
    update_stats_cmd.add_argument(
        "--hull",
        help="Filter to specific hull (e.g., vexor, drake)",
    )
    update_stats_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without writing to files",
    )
    update_stats_cmd.add_argument(
        "--no-prices",
        action="store_true",
        help="Skip ISK estimation (faster)",
    )
    update_stats_cmd.add_argument(
        "--region",
        "-r",
        default="jita",
        help="Trade hub for prices (default: jita)",
    )
    update_stats_cmd.set_defaults(func=cmd_fit_update_stats)

    # fit validate
    validate_cmd = fit_subparsers.add_parser(
        "validate",
        help="Validate archetype fits including omega_required consistency",
    )
    validate_cmd.add_argument(
        "archetype",
        nargs="?",
        help="Archetype path to validate (or all if omitted)",
    )
    validate_cmd.add_argument(
        "--hull",
        help="Filter to specific hull",
    )
    validate_cmd.add_argument(
        "--eos",
        action="store_true",
        help="Use EOS for additional validation",
    )
    validate_cmd.set_defaults(func=cmd_fit_validate)

    # Default handler
    fit_parser.set_defaults(
        func=lambda args: print(
            "Use 'fit select', 'fit check', 'fit refresh-prices', "
            "'fit update-stats', or 'fit validate'"
        )
    )
