"""
ARIA ESI Archetype Commands

Commands for managing and querying the archetype fittings library.
"""

import argparse
from typing import Any

from ..core import get_utc_timestamp

# =============================================================================
# Command: archetype list
# =============================================================================


def cmd_archetype_list(args: argparse.Namespace) -> dict[str, Any]:
    """
    List available archetypes.

    Lists all archetypes or filters by hull name.
    """
    from ..archetypes import list_archetypes, load_hull_manifest

    query_ts = get_utc_timestamp()
    hull = getattr(args, "hull", None)
    _show_details = getattr(args, "details", False)  # Reserved for future use

    archetypes = list_archetypes(hull)

    if not archetypes:
        if hull:
            print(f"No archetypes found for hull: {hull}")
        else:
            print("No archetypes found")
        return {
            "command": "archetype-list",
            "archetypes": [],
            "count": 0,
            "filter_hull": hull,
            "query_timestamp": query_ts,
        }

    # Group by hull
    by_hull: dict[str, list[str]] = {}
    for path in archetypes:
        hull_name = path.split("/")[0]
        if hull_name not in by_hull:
            by_hull[hull_name] = []
        by_hull[hull_name].append(path)

    print("=" * 60)
    print("AVAILABLE ARCHETYPES")
    print("=" * 60)

    for hull_name in sorted(by_hull.keys()):
        manifest = load_hull_manifest(hull_name)
        hull_display = manifest.hull if manifest else hull_name.title()
        ship_class = manifest.ship_class if manifest else "unknown"

        print(f"\n{hull_display} ({ship_class}):")
        for path in sorted(by_hull[hull_name]):
            # Remove hull prefix for cleaner display
            activity_path = "/".join(path.split("/")[1:])
            print(f"  - {activity_path}")

    print(f"\nTotal: {len(archetypes)} archetypes")

    return {
        "command": "archetype-list",
        "archetypes": archetypes,
        "count": len(archetypes),
        "filter_hull": hull,
        "query_timestamp": query_ts,
    }


# =============================================================================
# Command: archetype show
# =============================================================================


def cmd_archetype_show(args: argparse.Namespace) -> dict[str, Any]:
    """
    Show archetype details.

    Displays the full archetype including EFT, stats, and notes.
    """
    from ..archetypes import load_archetype, load_hull_manifest

    query_ts = get_utc_timestamp()
    path = args.path
    eft_only = getattr(args, "eft", False)

    archetype = load_archetype(path)

    if not archetype:
        print(f"Archetype not found: {path}")
        return {
            "error": "not_found",
            "message": f"Archetype not found: {path}",
            "query_timestamp": query_ts,
        }

    # EFT-only output
    if eft_only:
        print(archetype.eft)
        return {
            "command": "archetype-show",
            "path": path,
            "eft": archetype.eft,
            "query_timestamp": query_ts,
        }

    # Full output
    manifest = load_hull_manifest(archetype.archetype.hull)

    print("=" * 60)
    print(f"ARCHETYPE: {path}")
    print("=" * 60)

    print(f"\nHull: {archetype.archetype.hull}")
    print(f"Skill Tier: {archetype.archetype.skill_tier}")

    if manifest:
        print(f"Ship Class: {manifest.ship_class}")
        print(f"Tank Type: {manifest.fitting_rules.tank_type}")

    print("\n--- EFT ---")
    print(archetype.eft)

    print("\n--- Stats ---")
    stats = archetype.stats
    print(f"DPS: {stats.dps}")
    print(f"EHP: {stats.ehp}")
    if stats.tank_sustained:
        print(f"Tank (sustained): {stats.tank_sustained} HP/s")
    if stats.capacitor_stable is not None:
        print(f"Cap Stable: {'Yes' if stats.capacitor_stable else 'No'}")
    if stats.validated_date:
        print(f"Validated: {stats.validated_date}")

    print("\n--- Skill Requirements ---")
    if archetype.skill_requirements.required:
        print("Required:")
        for skill, level in archetype.skill_requirements.required.items():
            print(f"  {skill}: {level}")
    if archetype.skill_requirements.recommended:
        print("Recommended:")
        for skill, level in archetype.skill_requirements.recommended.items():
            print(f"  {skill}: {level}")

    if archetype.notes:
        print("\n--- Notes ---")
        print(f"Purpose: {archetype.notes.purpose}")
        if archetype.notes.engagement:
            print(f"Engagement: {archetype.notes.engagement}")
        if archetype.notes.warnings:
            print("Warnings:")
            for warning in archetype.notes.warnings:
                print(f"  - {warning}")

    return {
        "command": "archetype-show",
        "path": path,
        "archetype": archetype.to_dict(),
        "query_timestamp": query_ts,
    }


# =============================================================================
# Command: archetype generate
# =============================================================================


def cmd_archetype_generate(args: argparse.Namespace) -> dict[str, Any]:
    """
    Generate faction-tuned fit from archetype.

    Applies faction-specific module and drone substitutions.
    """
    from ..archetypes import apply_faction_tuning, load_archetype
    from ..archetypes.tuning import get_faction_damage_profile, list_supported_factions

    query_ts = get_utc_timestamp()
    path = args.path
    faction = getattr(args, "faction", None)

    archetype = load_archetype(path)

    if not archetype:
        print(f"Archetype not found: {path}")
        return {
            "error": "not_found",
            "message": f"Archetype not found: {path}",
            "query_timestamp": query_ts,
        }

    # If no faction specified, output base fit
    if not faction:
        print("# Base archetype (no faction tuning)")
        print(f"# Path: {path}")
        print()
        print(archetype.eft)
        return {
            "command": "archetype-generate",
            "path": path,
            "faction": None,
            "eft": archetype.eft,
            "query_timestamp": query_ts,
        }

    # Validate faction
    supported = list_supported_factions()
    faction_lower = faction.lower().replace(" ", "_")
    if faction_lower not in supported:
        print(f"Unknown faction: {faction}")
        print(f"Supported factions: {', '.join(supported)}")
        return {
            "error": "invalid_faction",
            "message": f"Unknown faction: {faction}",
            "supported_factions": supported,
            "query_timestamp": query_ts,
        }

    # Apply faction tuning
    result = apply_faction_tuning(archetype, faction_lower)

    # Get faction damage info
    damage_profile = get_faction_damage_profile(faction_lower)

    # Output
    print(f"# Tuned for {faction.title()}")
    if damage_profile:
        print(f"# Damage dealt: {damage_profile.get('damage_dealt', {})}")
        print(f"# Weakness: {damage_profile.get('weakness', 'unknown')}")
    print(f"# Base: {path}")
    print(f"# Tank profile: {result.tank_profile}")
    print()

    if result.substitutions:
        print("# Module changes:")
        for sub in result.substitutions:
            print(f"#   {sub.get('from', '?')} -> {sub.get('to', '?')}")

    if result.drone_changes:
        print("# Drone changes:")
        for change in result.drone_changes:
            print(
                f"#   {change.get('role', '?')}: {change.get('from_damage', '?')} -> {change.get('to_damage', '?')}"
            )

    if result.warnings:
        print("# Warnings:")
        for warning in result.warnings:
            print(f"#   {warning}")

    print()
    print(result.tuned_eft)

    return {
        "command": "archetype-generate",
        "path": path,
        "faction": faction_lower,
        "eft": result.tuned_eft,
        "tuning": result.to_dict(),
        "query_timestamp": query_ts,
    }


# =============================================================================
# Command: archetype validate
# =============================================================================


def cmd_archetype_validate(args: argparse.Namespace) -> dict[str, Any]:
    """
    Validate archetype(s).

    Checks schema, alpha restrictions, and optionally EOS fit validity.
    """
    from ..archetypes import validate_all_archetypes, validate_archetype

    query_ts = get_utc_timestamp()
    path = getattr(args, "path", None)
    validate_all = getattr(args, "all", False)
    use_eos = getattr(args, "eos", False)
    hull_filter = getattr(args, "hull", None)

    print("=" * 60)
    print("ARCHETYPE VALIDATION")
    print("=" * 60)
    if use_eos:
        print("EOS validation: ENABLED")
    else:
        print("EOS validation: disabled (use --eos to enable)")
    print()

    if validate_all:
        results = validate_all_archetypes(hull=hull_filter, use_eos=use_eos)
    elif path:
        result = validate_archetype(path, use_eos=use_eos)
        results = [result]
    else:
        print("Specify a path or use --all to validate all archetypes")
        return {
            "error": "missing_argument",
            "message": "Specify a path or use --all",
            "query_timestamp": query_ts,
        }

    # Summarize results
    total = len(results)
    passed = sum(1 for r in results if r.is_valid)
    failed = total - passed
    total_errors = sum(len(r.errors) for r in results)
    total_warnings = sum(len(r.warnings) for r in results)

    for result in results:
        status = "PASS" if result.is_valid else "FAIL"
        errors = len(result.errors)
        warnings = len(result.warnings)

        if result.is_valid and warnings == 0:
            print(f"[{status}] {result.path}")
        else:
            print(f"[{status}] {result.path} ({errors} errors, {warnings} warnings)")

            for issue in result.issues:
                prefix = "  ERROR:" if issue.level == "error" else "  WARN:"
                print(f"{prefix} [{issue.category}] {issue.message}")

    print()
    print("-" * 60)
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
    print(f"Errors: {total_errors} | Warnings: {total_warnings}")

    return {
        "command": "archetype-validate",
        "total": total,
        "passed": passed,
        "failed": failed,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "results": [r.to_dict() for r in results],
        "query_timestamp": query_ts,
    }


# =============================================================================
# Command: archetype migrate
# =============================================================================


def cmd_archetype_recommend(args: argparse.Namespace) -> dict[str, Any]:
    """
    Recommend fit based on pilot skills with tank variant selection.

    Uses pilot's actual skill levels to:
    1. Select the most appropriate tank variant (armor vs shield)
    2. Choose the highest tier fit the pilot can fly
    """
    from ..archetypes import (
        select_fits,
    )

    query_ts = get_utc_timestamp()
    path = args.path
    tank_override = getattr(args, "tank", None)
    clone_status = getattr(args, "clone", "omega")
    skip_skills = getattr(args, "no_skills", False)

    # Fetch pilot skills (unless --no-skills flag)
    pilot_skills: dict[int, int] = {}
    if not skip_skills:
        try:
            from ..fitting.skills import fetch_pilot_skills

            pilot_skills = fetch_pilot_skills()
            print(f"Loaded {len(pilot_skills)} trained skills from ESI")
        except Exception as e:
            print(f"Failed to fetch pilot skills: {e}")
            print("Using empty skill set (will use tie_breaker for variant selection)")
    else:
        print("Skipping skill fetch (--no-skills)")

    # Run selection with tank variant support
    result = select_fits(
        archetype_path=path,
        pilot_skills=pilot_skills,
        clone_status=clone_status,
        tank_override=tank_override,
    )

    # Display results
    print("=" * 60)
    print(f"ARCHETYPE RECOMMENDATION: {path}")
    print("=" * 60)

    # Show tank variant selection if applicable
    if result.tank_selection:
        ts = result.tank_selection
        print("\nTank Variant Selection:")
        print(f"  Selected: {ts.variant_path} ({ts.selection_reason})")

        if ts.skill_details:
            armor_skills = ts.skill_details.get("armor", {})
            shield_skills = ts.skill_details.get("shield", {})

            if armor_skills:
                armor_breakdown = ", ".join(
                    f"{name} {level}" for name, level in armor_skills.items() if level > 0
                )
                print(f"  Armor Score: {ts.armor_score:.1f}  ({armor_breakdown or 'no skills'})")

            if shield_skills:
                shield_breakdown = ", ".join(
                    f"{name} {level}" for name, level in shield_skills.items() if level > 0
                )
                print(f"  Shield Score: {ts.shield_score:.1f}  ({shield_breakdown or 'no skills'})")

    elif result.tank_variants_available:
        print(f"\nTank variants available: {', '.join(result.tank_variants_available)}")
        print("  (No meta.yaml found - use --tank to specify)")

    # Show filters applied
    if result.filters_applied:
        print(f"\nFilters: {' -> '.join(result.filters_applied)}")

    # Show warnings
    for warning in result.warnings:
        print(f"\nWARNING: {warning}")

    # Show recommendation
    if result.selection_mode == "none":
        print("\nNo suitable fit found.")
        if result.recommended:
            print(f"\nClosest option ({result.recommended.tier}):")
            print(f"  Missing skills: {len(result.recommended.missing_skills)}")
    elif result.selection_mode == "single":
        rec = result.recommended
        if rec:
            print(f"\nRecommended Fit: {rec.tier}")
            if rec.estimated_isk:
                print(f"  Estimated cost: {rec.estimated_isk:,} ISK")
            print(f"\n{rec.archetype.eft}")
    elif result.selection_mode == "dual":
        print("\nDual Options Available:")
        if result.efficient:
            print(f"\n[EFFICIENT] {result.efficient.tier}")
            if result.efficient.estimated_isk:
                print(f"  Cost: {result.efficient.estimated_isk:,} ISK")
        if result.premium:
            print(f"\n[PREMIUM] {result.premium.tier}")
            if result.premium.estimated_isk:
                print(f"  Cost: {result.premium.estimated_isk:,} ISK")

        # Show the premium fit by default
        if result.premium:
            print(f"\n--- Premium Fit ({result.premium.tier}) ---")
            print(result.premium.archetype.eft)

    return {
        "command": "archetype-recommend",
        "path": path,
        "tank_override": tank_override,
        "result": result.to_dict(),
        "query_timestamp": query_ts,
    }


def cmd_archetype_migrate(args: argparse.Namespace) -> dict[str, Any]:
    """
    Migrate archetype files to new tier naming scheme.

    Renames tier files:
    - low.yaml -> t1.yaml
    - medium.yaml -> meta.yaml
    - high.yaml -> t2_optimal.yaml
    - alpha.yaml -> merged into t1.yaml with omega_required=false

    Also adds omega_required flag based on T2 module detection.
    """
    from ..archetypes.migration import run_migration

    query_ts = get_utc_timestamp()
    dry_run = not getattr(args, "execute", False)
    force = getattr(args, "force", False)
    hull = getattr(args, "hull", None)

    print("=" * 60)
    print("ARCHETYPE MIGRATION")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print(f"Force overwrite: {'Yes' if force else 'No'}")
    if hull:
        print(f"Hull filter: {hull}")
    print()

    result = run_migration(dry_run=dry_run, force=force, hull=hull)

    # Display results
    for action in result.get("actions", []):
        action_type = action.get("action", "unknown")
        source = action.get("source", "")
        target = action.get("target", "")
        changes = action.get("changes", [])
        error = action.get("error", "")

        if action_type == "rename":
            symbol = "[MIGRATE]" if not dry_run else "[WOULD MIGRATE]"
            print(f"{symbol} {source}")
            print(f"         -> {target}")
            for change in changes:
                print(f"            {change}")
        elif action_type == "skip":
            if error:
                print(f"[ERROR] {source}")
                print(f"        {error}")
            else:
                print(f"[SKIP] {source}")
                if changes:
                    print(f"       {changes[0]}")
        print()

    # Summary
    print("-" * 60)
    print(f"Total files: {result.get('total_files', 0)}")
    print(f"{'Would migrate' if dry_run else 'Migrated'}: {result.get('migrated', 0)}")
    print(f"Skipped: {result.get('skipped', 0)}")
    print(f"Errors: {result.get('errors', 0)}")

    if dry_run and result.get("migrated", 0) > 0:
        print()
        print("Run with --execute to apply changes")

    result["query_timestamp"] = query_ts
    result["command"] = "archetype-migrate"
    return result


# =============================================================================
# Parser Registration
# =============================================================================


def register_parsers(subparsers) -> None:
    """Register archetype command parsers."""

    # archetype list
    list_parser = subparsers.add_parser(
        "archetype",
        help="Archetype commands (use 'archetype list', 'archetype show', etc.)",
        description="Manage and query the archetype fittings library",
    )

    archetype_subparsers = list_parser.add_subparsers(dest="archetype_command")

    # archetype list
    list_cmd = archetype_subparsers.add_parser(
        "list",
        help="List available archetypes",
    )
    list_cmd.add_argument(
        "hull",
        nargs="?",
        help="Filter by hull name (e.g., vexor, drake)",
    )
    list_cmd.add_argument(
        "--details",
        "-d",
        action="store_true",
        help="Show additional details",
    )
    list_cmd.set_defaults(func=cmd_archetype_list)

    # archetype show
    show_cmd = archetype_subparsers.add_parser(
        "show",
        help="Show archetype details",
    )
    show_cmd.add_argument(
        "path",
        help="Archetype path (e.g., vexor/pve/missions/l2/medium)",
    )
    show_cmd.add_argument(
        "--eft",
        action="store_true",
        help="Output EFT format only",
    )
    show_cmd.set_defaults(func=cmd_archetype_show)

    # archetype generate
    gen_cmd = archetype_subparsers.add_parser(
        "generate",
        help="Generate faction-tuned fit",
    )
    gen_cmd.add_argument(
        "path",
        help="Archetype path (e.g., vexor/pve/missions/l2/medium)",
    )
    gen_cmd.add_argument(
        "--faction",
        "-f",
        help="Target faction (e.g., serpentis, guristas, blood_raiders)",
    )
    gen_cmd.set_defaults(func=cmd_archetype_generate)

    # archetype validate
    val_cmd = archetype_subparsers.add_parser(
        "validate",
        help="Validate archetype(s)",
    )
    val_cmd.add_argument(
        "path",
        nargs="?",
        help="Archetype path to validate (or use --all)",
    )
    val_cmd.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Validate all archetypes",
    )
    val_cmd.add_argument(
        "--hull",
        help="Filter validation to specific hull",
    )
    val_cmd.add_argument(
        "--eos",
        action="store_true",
        help="Include EOS fit validation",
    )
    val_cmd.set_defaults(func=cmd_archetype_validate)

    # archetype migrate
    mig_cmd = archetype_subparsers.add_parser(
        "migrate",
        help="Migrate archetype files to new tier naming scheme",
    )
    mig_cmd.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform migration (default is dry-run)",
    )
    mig_cmd.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing target files",
    )
    mig_cmd.add_argument(
        "--hull",
        help="Only migrate files for specific hull",
    )
    mig_cmd.set_defaults(func=cmd_archetype_migrate)

    # archetype recommend
    rec_cmd = archetype_subparsers.add_parser(
        "recommend",
        help="Recommend fit based on pilot skills with tank variant selection",
    )
    rec_cmd.add_argument(
        "path",
        help="Archetype path (e.g., vexor/pve/missions/l3)",
    )
    rec_cmd.add_argument(
        "--tank",
        choices=["armor", "shield"],
        help="Override tank variant selection",
    )
    rec_cmd.add_argument(
        "--clone",
        choices=["alpha", "omega"],
        default="omega",
        help="Clone status (default: omega)",
    )
    rec_cmd.add_argument(
        "--no-skills",
        action="store_true",
        help="Skip skill fetch, use empty skills (faster, uses tie_breaker)",
    )
    rec_cmd.set_defaults(func=cmd_archetype_recommend)

    # Default command handler
    list_parser.set_defaults(
        func=lambda args: cmd_archetype_list(args)
        if not hasattr(args, "archetype_command") or not args.archetype_command
        else None
    )
