"""
Build cost CLI command — wraps the MCP build_cost action for CLI fallback.

Usage:
    aria-esi build-cost "Dominix" --me 10
    aria-esi build-cost "Rifter" --runs 5 --region amarr
"""

import argparse
import asyncio


def cmd_build_cost(args: argparse.Namespace) -> dict:
    """Calculate manufacturing cost from blueprint."""
    from aria_esi.mcp.dispatchers.market import _build_cost

    result = asyncio.run(
        _build_cost(
            item=args.item_name,
            me_level=args.me,
            runs=args.runs,
            facility=args.facility,
            region=args.region,
        )
    )
    return result


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register build-cost subcommand."""
    p = subparsers.add_parser("build-cost", help="Calculate manufacturing cost")
    p.add_argument("item_name", help="Item to calculate build cost for")
    p.add_argument("--me", type=int, default=0, help="ME research level (0-10)")
    p.add_argument("--runs", type=int, default=1, help="Number of manufacturing runs")
    p.add_argument("--facility", default=None, help="Facility name (e.g., Azbel)")
    p.add_argument("--region", default="jita", help="Price region (default: jita)")
    p.set_defaults(func=cmd_build_cost)
