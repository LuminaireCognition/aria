"""
ARIA ESI Freshness Commands

CLI interface for the freshness-gated auto-sync library.
"""

import argparse

from ..core.freshness import SECTION_REGISTRY, check_freshness, ensure_fresh


def cmd_ensure_fresh(args: argparse.Namespace) -> tuple[dict | list[dict], int]:
    """
    Check freshness and optionally sync stale data.

    Returns:
        Tuple of (payload, exit_code). Exit code 0 if fresh, 1 if stale.
    """
    section = args.section
    check_only = getattr(args, "check_only", False)
    force = getattr(args, "force", False)

    if section == "all":
        results = []
        any_stale = False
        for name in SECTION_REGISTRY:
            if check_only:
                result = check_freshness(name)
            else:
                result = ensure_fresh(name, force=force)
            results.append(result.to_dict())
            if not result.fresh:
                any_stale = True
        return results, 1 if any_stale else 0

    # Single section
    if check_only:
        result = check_freshness(section)
    else:
        result = ensure_fresh(section, force=force)

    return result.to_dict(), 1 if not result.fresh else 0


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register freshness command parsers."""
    parser = subparsers.add_parser(
        "ensure-fresh",
        help="Check data freshness and optionally sync stale sections",
    )

    parser.add_argument(
        "section",
        choices=list(SECTION_REGISTRY.keys()) + ["all"],
        help="Data section to check (or 'all')",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check-only",
        action="store_true",
        default=False,
        help="Only check freshness, do not sync",
    )
    group.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force sync even if data is fresh",
    )

    parser.set_defaults(func=cmd_ensure_fresh)
