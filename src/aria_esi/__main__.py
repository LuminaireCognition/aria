#!/usr/bin/env python3
"""
ARIA ESI CLI Entry Point

Provides command-line interface for ESI operations.
Run with: python -m aria_esi <command> [args]
"""

import argparse
import json
import sys

from .core import get_utc_timestamp


def output_json(data: dict, indent: int = 2) -> None:
    """Print JSON output to stdout."""
    print(json.dumps(data, indent=indent))


def output_error(message: str, exit_code: int = 1, **kwargs) -> None:
    """Print error JSON and exit."""
    error_data = {
        "error": kwargs.pop("error_type", "error"),
        "message": message,
        "query_timestamp": get_utc_timestamp(),
    }
    error_data.update(kwargs)
    output_json(error_data)
    sys.exit(exit_code)


# =============================================================================
# Built-in Commands
# =============================================================================


def cmd_help(args: argparse.Namespace) -> dict:
    """Show help message."""
    help_text = """
═══════════════════════════════════════════════════════════════════
ARIA ESI Interface (Python)
───────────────────────────────────────────────────────────────────

Status: Phase 13 Complete - All commands ready

Navigation Commands:
  route <from> <to> [flags]  Calculate route between systems
                             Flags: --safe, --shortest (default), --risky
  activity <system>          Live system activity intel (kills/jumps)
  loop <origin> [opts]       Plan circular mining route through border systems
                             --target-jumps N, --min-borders N, --max-borders N
                             --security highsec|lowsec|any, --avoid <systems>

Market Commands:
  price <item> [--region]    Market price lookup (ESI)
                             Regions: --jita, --amarr, --dodixie, --rens, --hek
  market-seed                Download bulk Fuzzwork data into local database
  market-status              Show market database status and freshness
  price-batch <file> [opts]  Batch price lookup from file (Fuzzwork)
                             --jita, --amarr, --dodixie, --rens, --hek

Identity Commands:
  pilot [name|id]            Pilot identity lookup (or 'me' for self)

Character Commands (authenticated):
  profile                    Fetch pilot profile + standings
  location                   Fetch current location and ship
  standings                  Fetch faction/corp standings

Wallet Commands (authenticated):
  wallet                     Fetch ISK balance
  wallet-journal [opts]      Fetch wallet journal
                             --days N, --type <bounty|market|industry|...>

Skills Commands (authenticated):
  skills [filter]            Fetch trained skills
  skillqueue                 Skill training queue with ETA

Industry Commands (authenticated):
  industry-jobs [opts]       Manufacturing/research jobs
                             --active, --completed, --history, --all

Assets Commands (authenticated):
  assets [opts]              Asset inventory
                             --ships, --type <name>, --location <name>
  fitting <ship>             Extract ship fitting (EFT format)
  blueprints                 BPO/BPC library

Corporation Commands (CEO/Director role required):
  corp                       Corporation dashboard (default: status)
  corp status                Full corp overview
  corp info [name|id]        Public corporation lookup
  corp wallet [--journal]    Wallet balances and transactions
  corp assets [--ships]      Corporation hangar inventory
  corp blueprints [--bpos]   Corporation blueprint library
  corp jobs [--active]       Manufacturing/research status

Loyalty Points Commands:
  lp                         Fetch LP balances across all corporations
  lp-offers <corp> [opts]    Browse LP store offers for a corporation
                             --search <term>, --max-lp N, --affordable
  lp-analyze <corp>          Analyze LP store for self-sufficient items

Clone Commands (authenticated):
  clones                     Full clone status (home, jumps, implants)
  implants                   Active implants in current clone
  jump-clones                Jump clone locations and cooldown

Killmail Commands (authenticated):
  killmails [opts]           List recent kills and losses
                             --losses, --kills, --limit N
  killmail <id> [hash]       Detailed analysis of a killmail
  last-loss                  Analyze your most recent ship loss
  loss-analysis              Analyze patterns across recent losses

Contract Commands (authenticated):
  contracts [opts]           List personal contracts
                             --issued, --received, --type <type>, --active
  contract <id>              Detailed view of a specific contract

Research Agent Commands (authenticated):
  agents-research            List research agents and accumulated RP

Mining Commands (authenticated):
  mining [opts]              Mining ledger (ore extraction history)
                             --days N, --system <name>, --ore <type>
  mining-summary [opts]      Aggregated mining totals by ore/system
                             --days N

Market Order Commands (authenticated):
  orders [opts]              List market orders (buy/sell)
                             --buy, --sell, --history, --limit N

Saved Fittings Commands (authenticated):
  fittings [opts]            List saved ship fittings
                             --ship <hull>
  fittings-detail <id>       Show fitting details with EFT export
                             --eft (output EFT format only)

Mail Commands (authenticated):
  mail [opts]                List EVE mail headers
                             --unread, --limit N
  mail-read <id>             Read specific mail body
  mail-labels                List mail labels

Profile Sync Commands:
  sync-profile [opts]        Sync standings from ESI to profile.md
                             --dry-run (preview changes only)

Persona Commands:
  persona-context [opts]     Regenerate persona_context in profile
                             --all (all pilots), --dry-run
  validate-overlays [opts]   Validate persona files and skill overlays
                             --all (all pilots)

SDE Commands:
  sde-seed [opts]            Download and import SDE from Fuzzwork
                             --check (status only, no download)
  sde-status                 Show SDE database status and counts
  sde-item <name>            Look up item information from SDE
  sde-blueprint <name>       Look up blueprint info (materials, sources)

Validation Commands:
  validate-sites [opts]      Validate site composition data against SDE
                             --file <path>, --verbose

Fitting Commands:
  eos-seed [opts]            Download EOS fitting data from Pyfa
                             --force (re-download), --check (status only)
  eos-status                 Show EOS fitting data status

Archetype Commands:
  archetype list [hull]      List available archetypes
  archetype show <path>      Show archetype details
                             --eft (EFT format only)
  archetype generate <path>  Generate faction-tuned fit
                             --faction <name>
  archetype validate [path]  Validate archetype(s)
                             --all, --eos, --hull <name>

Notification Commands:
  notifications list         List all notification profiles
  notifications show <name>  Show profile details
  notifications create       Create profile from template
    <name> --template <t> --webhook <url>
  notifications enable       Enable a profile
  notifications disable      Disable a profile
  notifications test <name>  Send test notification
  notifications validate     Validate all profiles
  notifications templates    List available templates
  notifications migrate      Migrate legacy config to profile
  notifications delete       Delete profile (--force required)

System Commands:
  help                       Show this help message
  test-core                  Test core module imports

Examples:
  aria-esi route Dodixie Jita
  aria-esi route Amarr Hek --safe
  aria-esi loop Sortet --target-jumps 20 --min-borders 3
  aria-esi loop Jita --avoid Uedama Niarja
  aria-esi price Tritanium --jita
  aria-esi market-seed
  aria-esi market-status
  aria-esi price-batch minerals.txt --jita
  aria-esi pilot
  aria-esi location
  aria-esi wallet
  aria-esi assets --ships
  aria-esi fitting Vexor
  aria-esi corp
  aria-esi corp info "Pandemic Legion"
  aria-esi corp wallet --journal
  aria-esi lp
  aria-esi lp-offers "Federation Navy"
  aria-esi lp-offers "fed navy" --search implant
  aria-esi lp-analyze 1000120
  aria-esi clones
  aria-esi implants
  aria-esi jump-clones
  aria-esi killmails --losses
  aria-esi last-loss
  aria-esi loss-analysis
  aria-esi contracts
  aria-esi contracts --type courier
  aria-esi contract 123456789
  aria-esi agents-research
  aria-esi mining
  aria-esi mining --days 7 --ore Veldspar
  aria-esi mining-summary
  aria-esi orders
  aria-esi orders --sell --limit 10
  aria-esi fittings
  aria-esi fittings --ship Vexor
  aria-esi fittings-detail 123456 --eft
  aria-esi mail
  aria-esi mail --unread
  aria-esi mail-read 987654321
  aria-esi sync-profile
  aria-esi sync-profile --dry-run
  aria-esi persona-context
  aria-esi validate-overlays
  aria-esi validate-overlays --all
  aria-esi sde-seed
  aria-esi sde-status
  aria-esi sde-item Pioneer
  aria-esi sde-blueprint Venture
  aria-esi validate-sites
  aria-esi validate-sites --verbose
  aria-esi eos-seed
  aria-esi eos-status
  aria-esi archetype list
  aria-esi archetype list vexor
  aria-esi archetype show vexor/pve/missions/l2/medium
  aria-esi archetype generate vexor/pve/missions/l2/medium --faction serpentis
  aria-esi archetype validate --all --eos
  aria-esi notifications list
  aria-esi notifications templates
  aria-esi notifications create my-intel --template market-hubs --webhook <url>
  aria-esi notifications test my-intel
  aria-esi notifications validate
  aria-esi notifications migrate

Usage:
  python3 -m aria_esi <command> [args]

═══════════════════════════════════════════════════════════════════
"""
    print(help_text)
    return {}


def cmd_test_core(args: argparse.Namespace) -> dict:
    """Test core module imports and basic functionality."""
    from typing import Any

    results: dict[str, Any] = {
        "query_timestamp": get_utc_timestamp(),
        "test": "core_module_imports",
        "status": "running",
        "checks": [],
    }

    # Test core imports
    try:
        from .core import ESIClient, ESIError

        results["checks"].append({"module": "core.client", "status": "ok"})
    except ImportError as e:
        results["checks"].append({"module": "core.client", "status": "error", "message": str(e)})

    try:
        from .core import Credentials, CredentialsError, get_credentials

        results["checks"].append({"module": "core.auth", "status": "ok"})
    except ImportError as e:
        results["checks"].append({"module": "core.auth", "status": "error", "message": str(e)})

    try:
        from .core import format_duration, format_isk, parse_datetime, to_roman

        results["checks"].append({"module": "core.formatters", "status": "ok"})
    except ImportError as e:
        results["checks"].append(
            {"module": "core.formatters", "status": "error", "message": str(e)}
        )

    try:
        from .core import ACTIVITY_TYPES, SHIP_GROUP_IDS, TRADE_HUB_REGIONS

        results["checks"].append({"module": "core.constants", "status": "ok"})
    except ImportError as e:
        results["checks"].append({"module": "core.constants", "status": "error", "message": str(e)})

    # Test Phase 2 command imports
    try:
        from .commands import market, navigation, pilot

        results["checks"].append({"module": "commands.navigation", "status": "ok"})
        results["checks"].append({"module": "commands.market", "status": "ok"})
        results["checks"].append({"module": "commands.pilot", "status": "ok"})
    except ImportError as e:
        results["checks"].append(
            {"module": "commands.phase2", "status": "error", "message": str(e)}
        )

    # Test Phase 3 command imports
    try:
        from .commands import assets, character, industry, skills, wallet

        results["checks"].append({"module": "commands.character", "status": "ok"})
        results["checks"].append({"module": "commands.wallet", "status": "ok"})
        results["checks"].append({"module": "commands.skills", "status": "ok"})
        results["checks"].append({"module": "commands.industry", "status": "ok"})
        results["checks"].append({"module": "commands.assets", "status": "ok"})
    except ImportError as e:
        results["checks"].append(
            {"module": "commands.phase3", "status": "error", "message": str(e)}
        )

    # Test Phase 4 command imports
    try:
        from .commands import corporation

        results["checks"].append({"module": "commands.corporation", "status": "ok"})
    except ImportError as e:
        results["checks"].append(
            {"module": "commands.phase4", "status": "error", "message": str(e)}
        )

    # Test basic formatter functionality
    try:
        from .core import format_duration, format_isk, to_roman

        assert format_isk(1_500_000_000) == "1.50B"
        assert format_isk(250_000_000) == "250.00M"
        assert format_isk(15_000) == "15.00K"
        assert format_duration(3661) == "1h 1m"
        assert to_roman(5) == "V"
        results["checks"].append({"test": "formatters_basic", "status": "ok"})
    except AssertionError as e:
        results["checks"].append({"test": "formatters_basic", "status": "error", "message": str(e)})
    except Exception as e:
        results["checks"].append({"test": "formatters_basic", "status": "error", "message": str(e)})

    # Test ESI client (public endpoint)
    try:
        from .core import ESIClient

        client = ESIClient()
        system = client.get_dict_safe("/universe/systems/30000142/")
        if system and system.get("name") == "Jita":
            results["checks"].append(
                {"test": "esi_client_public", "status": "ok", "system": "Jita"}
            )
        else:
            results["checks"].append(
                {"test": "esi_client_public", "status": "warning", "message": "Unexpected response"}
            )
    except Exception as e:
        results["checks"].append(
            {"test": "esi_client_public", "status": "error", "message": str(e)}
        )

    # Test credential resolution
    try:
        from .core import Credentials

        creds = Credentials.resolve()
        if creds:
            results["checks"].append(
                {
                    "test": "credentials",
                    "status": "ok",
                    "character_id": creds.character_id,
                    "scopes_count": len(creds.scopes),
                }
            )
        else:
            results["checks"].append(
                {
                    "test": "credentials",
                    "status": "skipped",
                    "message": "No credentials configured (expected for first run)",
                }
            )
    except Exception as e:
        results["checks"].append({"test": "credentials", "status": "error", "message": str(e)})

    # Determine overall status
    errors = [c for c in results["checks"] if c.get("status") == "error"]
    results["status"] = "failed" if errors else "passed"
    results["error_count"] = len(errors)

    return results


# =============================================================================
# Main Entry Point
# =============================================================================


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="aria-esi",
        description="ARIA ESI Interface - EVE Online API access",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Built-in commands
    help_parser = subparsers.add_parser("help", help="Show help message")
    help_parser.set_defaults(func=cmd_help)

    test_parser = subparsers.add_parser("test-core", help="Test core module imports")
    test_parser.set_defaults(func=cmd_test_core)

    # Phase 2: Register public command parsers
    from .commands import market, navigation, pilot

    navigation.register_parsers(subparsers)
    market.register_parsers(subparsers)
    pilot.register_parsers(subparsers)

    # Phase 3: Register personal command parsers (authentication required)
    from .commands import assets, character, industry, skills, wallet

    character.register_parsers(subparsers)
    wallet.register_parsers(subparsers)
    skills.register_parsers(subparsers)
    industry.register_parsers(subparsers)
    assets.register_parsers(subparsers)

    # Phase 4: Corporation commands
    from .commands import corporation

    corporation.register_parsers(subparsers)

    # Phase 5: Loyalty Points commands
    from .commands import loyalty

    loyalty.register_parsers(subparsers)

    # Phase 6: Clone commands
    from .commands import clones

    clones.register_parsers(subparsers)

    # Phase 7: Killmail commands
    from .commands import killmails

    killmails.register_parsers(subparsers)

    # Phase 7b: Killmail analysis (zKillboard integration)
    from .commands import killmail

    killmail.register_parsers(subparsers)

    # Phase 8: Contract commands
    from .commands import contracts

    contracts.register_parsers(subparsers)

    # Phase 9: Research Agents commands
    from .commands import agents_research

    agents_research.register_parsers(subparsers)

    # Phase 10: Mining commands
    from .commands import mining

    mining.register_parsers(subparsers)

    # Phase 11: Market Orders commands
    from .commands import orders

    orders.register_parsers(subparsers)

    # Phase 12: Saved Fittings commands
    from .commands import fittings

    fittings.register_parsers(subparsers)

    # Phase 13: Mail commands
    from .commands import mail

    mail.register_parsers(subparsers)

    # Phase 14: Universe cache commands
    from .commands import universe

    universe.register_parsers(subparsers)

    # Phase 15: Persona context commands
    from .commands import persona

    persona.register_parsers(subparsers)

    # Phase 16: Profile sync commands
    from .commands import sync_profile

    sync_profile.register_parsers(subparsers)

    # Phase 17: SDE commands
    from .commands import sde

    sde.register_parsers(subparsers)

    # Phase 18: Validation commands
    from .commands import validation

    validation.register_parsers(subparsers)

    # Phase 20: Fitting commands (EOS)
    from .commands import fitting

    fitting.register_parsers(subparsers)

    # Phase 21: Archetype commands
    from .commands import archetypes

    archetypes.register_parsers(subparsers)

    # Phase 22: Fit selection commands
    from .commands import fit

    fit.register_parsers(subparsers)

    # Phase 23: RedisQ real-time intel commands
    from .commands import redisq

    redisq.register_parsers(subparsers)

    # Phase 24: Notification profile commands
    from .commands import notifications

    notifications.register_parsers(subparsers)

    # Phase 25: PI location planning commands
    from .commands import pi

    pi.register_parsers(subparsers)

    # Phase 26: Sovereignty commands
    from .commands import sovereignty

    sovereignty.register_parsers(subparsers)

    return parser


def main() -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    # Default to help if no command
    if not args.command:
        cmd_help(args)
        return 0

    # Check if command has a handler function
    if not hasattr(args, "func"):
        output_error(
            f"Unknown command: {args.command}",
            error_type="unknown_command",
            hint="Run 'aria-esi help' for usage",
        )

    # Execute command
    try:
        result = args.func(args)

        # Output result if it's a dict (JSON response)
        if isinstance(result, dict) and result:
            output_json(result)

            # Return non-zero exit code if result contains error
            if "error" in result:
                return 1

        return 0

    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        return 130
    except Exception as e:
        output_error(str(e), error_type="command_error", command=args.command)
        return 1


if __name__ == "__main__":
    sys.exit(main())
