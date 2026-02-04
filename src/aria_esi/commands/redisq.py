"""
RedisQ CLI Commands.

Commands for controlling the RedisQ real-time kill streaming service.
"""

from __future__ import annotations

import argparse
import asyncio
import signal
from typing import TYPE_CHECKING

from ..core import get_utc_timestamp
from ..core.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def cmd_redisq_start(args: argparse.Namespace) -> dict:
    """
    Start the RedisQ poller service.

    Runs as a foreground process. Use Ctrl+C to stop.
    """
    from ..core.config import get_settings
    from ..services.redisq.backfill import startup_recovery
    from ..services.redisq.database import get_realtime_database
    from ..services.redisq.models import RedisQConfig
    from ..services.redisq.poller import get_poller, reset_poller

    settings = get_settings()
    db = get_realtime_database()

    # Build config from args and settings
    regions = args.regions if args.regions else settings.redisq_regions
    min_value = args.min_value if args.min_value is not None else settings.redisq_min_value
    retention = args.retention if args.retention else settings.redisq_retention_hours

    # Get or create queue ID
    queue_id = db.get_queue_id() or ""

    config = RedisQConfig(
        enabled=True,
        queue_id=queue_id,
        poll_interval_seconds=10,
        filter_regions=regions,
        min_value_isk=min_value,
        retention_hours=retention,
    )

    # Reset any existing poller
    reset_poller()

    async def run_poller():
        poller = await get_poller(config)

        # Handle shutdown signals
        stop_event = asyncio.Event()

        def signal_handler():
            logger.info("Shutdown signal received")
            stop_event.set()

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, signal_handler)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

        # Perform startup recovery if needed
        if not args.no_recovery:
            print("Checking for data gaps...")
            recovery = await startup_recovery(config)
            if recovery.get("recovery_needed"):
                print(f"Recovered {recovery.get('kills_recovered', 0)} kills from backfill")
            else:
                print(f"No recovery needed: {recovery.get('reason')}")

        # Start poller
        await poller.start()

        filter_desc = f"regions={regions}" if regions else "all regions"
        print(f"\nRedisQ poller started ({filter_desc})")
        print(f"Queue ID: {config.queue_id}")
        print("Press Ctrl+C to stop\n")

        # Wait for stop signal or periodic status updates
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=60)
            except asyncio.TimeoutError:
                # Print periodic status
                status = poller.get_status()
                if status.kills_processed > 0:
                    print(
                        f"Status: {status.kills_processed} processed, "
                        f"{status.kills_filtered} filtered, "
                        f"queue: {status.fetch_queue_size}"
                    )

        # Stop poller
        await poller.stop()
        print("\nPoller stopped")

    try:
        asyncio.run(run_poller())
        return {}
    except KeyboardInterrupt:
        print("\nInterrupted")
        return {}


def cmd_redisq_stop(args: argparse.Namespace) -> dict:
    """
    Stop a running RedisQ poller.

    Note: This command is a placeholder. In practice, the poller
    runs as a foreground process and is stopped with Ctrl+C.
    """
    return {
        "status": "info",
        "message": "The RedisQ poller runs as a foreground process. Use Ctrl+C to stop it.",
        "query_timestamp": get_utc_timestamp(),
    }


def cmd_redisq_status(args: argparse.Namespace) -> dict:
    """
    Show RedisQ service status and statistics.
    """
    from ..services.redisq.database import get_realtime_database

    db = get_realtime_database()
    stats = db.get_stats()

    return {
        "status": "ok",
        "service": "redisq",
        "database_stats": stats,
        "query_timestamp": get_utc_timestamp(),
    }


def cmd_redisq_backfill(args: argparse.Namespace) -> dict:
    """
    Manually trigger a backfill from zKillboard.
    """
    from datetime import datetime, timedelta

    from ..services.redisq.backfill import backfill_from_zkillboard

    # Parse time range
    hours = args.hours if args.hours else 1
    since = datetime.utcnow() - timedelta(hours=hours)

    regions = args.regions if args.regions else None
    max_kills = args.limit if args.limit else 500

    async def run_backfill():
        return await backfill_from_zkillboard(
            regions=regions,
            since=since,
            max_kills=max_kills,
        )

    print(f"Backfilling kills from last {hours} hour(s)...")
    kills = asyncio.run(run_backfill())

    return {
        "status": "ok",
        "kills_backfilled": len(kills),
        "since": since.isoformat(),
        "regions": regions if regions else "all",
        "query_timestamp": get_utc_timestamp(),
    }


def cmd_redisq_recent(args: argparse.Namespace) -> dict:
    """
    Show recent kills from the realtime database.
    """
    from ..services.redisq.database import get_realtime_database

    db = get_realtime_database()
    minutes = args.minutes if args.minutes else 60
    limit = args.limit if args.limit else 20
    system_id = args.system if args.system else None

    kills = db.get_recent_kills(
        system_id=system_id,
        since_minutes=minutes,
        limit=limit,
    )

    kill_dicts = []
    for kill in kills:
        kill_dicts.append(
            {
                "kill_id": kill.kill_id,
                "kill_time": kill.kill_time.isoformat(),
                "solar_system_id": kill.solar_system_id,
                "victim_ship_type_id": kill.victim_ship_type_id,
                "attacker_count": kill.attacker_count,
                "total_value": kill.total_value,
                "is_pod_kill": kill.is_pod_kill,
            }
        )

    return {
        "status": "ok",
        "kills": kill_dicts,
        "count": len(kill_dicts),
        "query": {
            "since_minutes": minutes,
            "limit": limit,
            "system_id": system_id,
        },
        "query_timestamp": get_utc_timestamp(),
    }


def cmd_redisq_watched(args: argparse.Namespace) -> dict:
    """
    Show kills involving watched entities.
    """
    import json

    from ..services.redisq.database import get_realtime_database

    db = get_realtime_database()
    minutes = args.minutes if args.minutes else 60
    limit = args.limit if args.limit else 20

    # Get system IDs if specified
    system_ids = None
    if hasattr(args, "system") and args.system:
        system_ids = [args.system] if isinstance(args.system, int) else args.system

    kills = db.get_watched_entity_kills(
        since_minutes=minutes,
        system_ids=system_ids,
        limit=limit,
    )

    # Get total count for stats
    total_count = db.get_watched_entity_kill_count(since_minutes=minutes)

    # Build kill data with entity match info
    kill_dicts = []
    for kill in kills:
        # Get watched entity IDs from database
        conn = db._get_connection()
        row = conn.execute(
            "SELECT watched_entity_ids FROM realtime_kills WHERE kill_id = ?",
            (kill.kill_id,),
        ).fetchone()
        watched_ids = (
            json.loads(row["watched_entity_ids"]) if row and row["watched_entity_ids"] else []
        )

        kill_dicts.append(
            {
                "kill_id": kill.kill_id,
                "kill_time": kill.kill_time.isoformat(),
                "solar_system_id": kill.solar_system_id,
                "victim_ship_type_id": kill.victim_ship_type_id,
                "victim_corporation_id": kill.victim_corporation_id,
                "victim_alliance_id": kill.victim_alliance_id,
                "attacker_corps": kill.attacker_corps,
                "attacker_alliances": kill.attacker_alliances,
                "attacker_count": kill.attacker_count,
                "total_value": kill.total_value,
                "is_pod_kill": kill.is_pod_kill,
                "watched_entity_ids": watched_ids,
            }
        )

    return {
        "status": "ok",
        "kills": kill_dicts,
        "count": len(kill_dicts),
        "total_watched_kills": total_count,
        "query": {
            "since_minutes": minutes,
            "limit": limit,
            "system_ids": system_ids,
        },
        "query_timestamp": get_utc_timestamp(),
    }


def cmd_redisq_follow(args: argparse.Namespace) -> dict | None:
    """
    Stream realtime kills to stdout (tail -f style).

    Outputs one event per kill, optionally with Discord-style payload
    formatting and LLM commentary.
    """
    import asyncio
    import json
    import sys
    from datetime import datetime

    from ..services.redisq.database import get_realtime_database
    from ..services.redisq.name_resolver import get_name_resolver
    from ..services.redisq.notifications.commentary import create_commentary_generator
    from ..services.redisq.notifications.formatter import MessageFormatter, format_isk
    from ..services.redisq.notifications.patterns import PatternDetector
    from ..services.redisq.notifications.persona import VOICE_SUMMARIES, PersonaLoader
    from ..services.redisq.notifications.triggers import TriggerResult
    from ..services.redisq.threat_cache import ThreatCache

    # Validate arguments
    if args.minutes <= 0:
        return {
            "error": "invalid_minutes",
            "message": "--minutes must be > 0",
            "query_timestamp": get_utc_timestamp(),
        }
    if args.interval <= 0:
        return {
            "error": "invalid_interval",
            "message": "--interval must be > 0",
            "query_timestamp": get_utc_timestamp(),
        }
    if args.limit <= 0:
        return {
            "error": "invalid_limit",
            "message": "--limit must be > 0",
            "query_timestamp": get_utc_timestamp(),
        }
    if args.warrant_threshold < 0 or args.warrant_threshold > 1:
        return {
            "error": "invalid_warrant_threshold",
            "message": "--warrant-threshold must be between 0 and 1",
            "query_timestamp": get_utc_timestamp(),
        }

    if args.persona and args.persona not in VOICE_SUMMARIES:
        valid = ", ".join(sorted(VOICE_SUMMARIES.keys()))
        return {
            "error": "invalid_persona",
            "message": f"Unknown persona '{args.persona}'. Valid options: {valid}",
            "query_timestamp": get_utc_timestamp(),
        }

    # Commentary setup (optional)
    commentary_enabled = bool(args.commentary)
    persona_loader = None
    commentary_generator = None
    if commentary_enabled:
        persona_loader = PersonaLoader(persona_override=args.persona)
        commentary_generator = create_commentary_generator(
            persona_loader=persona_loader,
            config={
                "style": args.style,
                "model": args.model,
            },
        )

        if not commentary_generator.is_configured:
            print(
                "Commentary disabled: ANTHROPIC_API_KEY not configured",
                file=sys.stderr,
            )
            commentary_generator = None

    async def run_follow() -> None:
        db = get_realtime_database()
        resolver = get_name_resolver()
        formatter = MessageFormatter()
        threat_cache = ThreatCache()
        pattern_detector = PatternDetector(threat_cache) if commentary_generator else None

        seen_ids: set[int] = set()

        # Tail semantics: skip current window unless backfill requested
        if not args.backfill:
            initial = db.get_recent_kills(
                system_id=args.system,
                since_minutes=args.minutes,
                limit=args.limit,
            )
            for kill in initial:
                seen_ids.add(kill.kill_id)

        while True:
            kills = db.get_recent_kills(
                system_id=args.system,
                since_minutes=args.minutes,
                limit=args.limit,
            )

            if kills:
                kills_sorted = sorted(
                    kills,
                    key=lambda k: (k.kill_time or datetime.min, k.kill_id),
                )
                for kill in kills_sorted:
                    if kill.kill_id in seen_ids:
                        continue
                    seen_ids.add(kill.kill_id)

                    system_display = resolver.resolve_system_with_fallback(kill.solar_system_id)
                    ship_display = (
                        "Capsule"
                        if kill.is_pod_kill
                        else resolver.resolve_type_with_fallback(kill.victim_ship_type_id)
                    )

                    gatecamp_status = None
                    if args.gatecamp:
                        gatecamp_status = threat_cache.get_gatecamp_status(
                            system_id=kill.solar_system_id,
                            system_name=system_display,
                        )

                    trigger_result = TriggerResult(
                        should_notify=True,
                        gatecamp_status=gatecamp_status,
                    )

                    commentary = None
                    persona_name = None

                    if commentary_generator and pattern_detector:
                        try:
                            pattern_context = await pattern_detector.detect_patterns(kill=kill)
                            if pattern_context.warrant_score() >= args.warrant_threshold:
                                notification_text = (
                                    f"{ship_display} destroyed in {system_display}, "
                                    f"{kill.attacker_count} attackers, "
                                    f"{format_isk(kill.total_value)} ISK"
                                )
                                commentary = await commentary_generator.generate_commentary(
                                    pattern_context=pattern_context,
                                    notification_text=notification_text,
                                    style=None,
                                    system_display=system_display,
                                    ship_display=ship_display,
                                )
                                if commentary and persona_loader:
                                    persona_name = persona_loader.get_persona_name()
                        except Exception as e:
                            logger.warning("Commentary generation failed: %s", e)
                            commentary = None
                            persona_name = None

                    if commentary:
                        payload = formatter.format_kill_with_commentary(
                            kill=kill,
                            trigger_result=trigger_result,
                            commentary=commentary,
                            persona_name=persona_name,
                            system_name=system_display,
                            ship_name=ship_display,
                        )
                    else:
                        payload = formatter.format_kill(
                            kill=kill,
                            trigger_result=trigger_result,
                            system_name=system_display,
                            ship_name=ship_display,
                        )

                    kill_url = f"https://zkillboard.com/kill/{kill.kill_id}/"

                    if args.format == "text":
                        value_display = f"{format_isk(kill.total_value)} ISK"
                        line = (
                            f"{kill.kill_time.isoformat()} | {system_display} | {ship_display} | "
                            f"{kill.attacker_count} attackers | {value_display} | {kill_url}"
                        )
                        print(line, flush=True)
                        if commentary:
                            tag = persona_name or "ARIA"
                            print(f"  {tag}: {commentary}", flush=True)
                    else:
                        output = {
                            "kill_id": kill.kill_id,
                            "kill_time": kill.kill_time.isoformat(),
                            "solar_system_id": kill.solar_system_id,
                            "system_name": system_display,
                            "ship_name": ship_display,
                            "total_value": kill.total_value,
                            "attacker_count": kill.attacker_count,
                            "zkillboard_url": kill_url,
                            "payload": payload,
                        }
                        if commentary:
                            output["commentary"] = commentary
                            output["persona"] = persona_name or "ARIA"

                        if args.pretty:
                            print(json.dumps(output, indent=2), flush=True)
                        else:
                            print(json.dumps(output, separators=(",", ":")), flush=True)

            await asyncio.sleep(args.interval)

    try:
        asyncio.run(run_follow())
        return {}
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        return {}


# ===========================================================================
# Entity Watchlist Command Implementations
# ===========================================================================


def cmd_watchlist_list(args: argparse.Namespace) -> dict:
    """List all entity watchlists."""
    from ..services.redisq.entity_watchlist import get_entity_watchlist_manager

    manager = get_entity_watchlist_manager()
    watchlists = manager.list_watchlists(
        watchlist_type=args.type if hasattr(args, "type") else None,
    )

    result = []
    for wl in watchlists:
        entity_count = manager.get_entity_count(wl.watchlist_id)
        result.append(
            {
                "name": wl.name,
                "type": wl.watchlist_type,
                "description": wl.description,
                "entity_count": entity_count,
                "owner_character_id": wl.owner_character_id,
            }
        )

    return {
        "status": "ok",
        "watchlists": result,
        "count": len(result),
        "query_timestamp": get_utc_timestamp(),
    }


def cmd_watchlist_show(args: argparse.Namespace) -> dict:
    """Show entities in a watchlist."""
    from ..services.redisq.entity_watchlist import get_entity_watchlist_manager

    manager = get_entity_watchlist_manager()
    watchlist = manager.get_watchlist(args.name)

    if watchlist is None:
        return {
            "status": "error",
            "error": f"Watchlist '{args.name}' not found",
            "query_timestamp": get_utc_timestamp(),
        }

    entities = manager.get_entities(watchlist.watchlist_id)
    entity_list = [
        {
            "entity_id": e.entity_id,
            "entity_type": e.entity_type,
            "entity_name": e.entity_name,
            "added_reason": e.added_reason,
        }
        for e in entities
    ]

    return {
        "status": "ok",
        "watchlist": {
            "name": watchlist.name,
            "type": watchlist.watchlist_type,
            "description": watchlist.description,
        },
        "entities": entity_list,
        "count": len(entity_list),
        "query_timestamp": get_utc_timestamp(),
    }


def cmd_watchlist_create(args: argparse.Namespace) -> dict:
    """Create a new entity watchlist."""
    from ..services.redisq.entity_watchlist import get_entity_watchlist_manager

    manager = get_entity_watchlist_manager()

    try:
        watchlist = manager.create_watchlist(
            name=args.name,
            description=args.description if hasattr(args, "description") else None,
        )
        return {
            "status": "ok",
            "message": f"Created watchlist '{args.name}'",
            "watchlist_id": watchlist.watchlist_id,
            "query_timestamp": get_utc_timestamp(),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "query_timestamp": get_utc_timestamp(),
        }


def cmd_watchlist_add(args: argparse.Namespace) -> dict:
    """Add an entity to a watchlist."""
    from ..services.redisq.entity_watchlist import get_entity_watchlist_manager

    manager = get_entity_watchlist_manager()
    watchlist = manager.get_watchlist(args.name)

    if watchlist is None:
        return {
            "status": "error",
            "error": f"Watchlist '{args.name}' not found",
            "query_timestamp": get_utc_timestamp(),
        }

    try:
        entity = manager.add_entity(
            watchlist_id=watchlist.watchlist_id,
            entity_id=args.entity_id,
            entity_type=args.type,
            entity_name=args.entity_name if hasattr(args, "entity_name") else None,
            added_reason=args.reason if hasattr(args, "reason") else None,
        )
        return {
            "status": "ok",
            "message": f"Added {args.type} {args.entity_id} to '{args.name}'",
            "entity": {
                "entity_id": entity.entity_id,
                "entity_type": entity.entity_type,
                "entity_name": entity.entity_name,
            },
            "query_timestamp": get_utc_timestamp(),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "query_timestamp": get_utc_timestamp(),
        }


def cmd_watchlist_remove(args: argparse.Namespace) -> dict:
    """Remove an entity from a watchlist."""
    from ..services.redisq.entity_watchlist import get_entity_watchlist_manager

    manager = get_entity_watchlist_manager()
    watchlist = manager.get_watchlist(args.name)

    if watchlist is None:
        return {
            "status": "error",
            "error": f"Watchlist '{args.name}' not found",
            "query_timestamp": get_utc_timestamp(),
        }

    removed = manager.remove_entity(
        watchlist_id=watchlist.watchlist_id,
        entity_id=args.entity_id,
        entity_type=args.type,
    )

    if removed:
        return {
            "status": "ok",
            "message": f"Removed {args.type} {args.entity_id} from '{args.name}'",
            "query_timestamp": get_utc_timestamp(),
        }
    else:
        return {
            "status": "error",
            "error": f"Entity {args.entity_id} not found in watchlist",
            "query_timestamp": get_utc_timestamp(),
        }


def cmd_watchlist_delete(args: argparse.Namespace) -> dict:
    """Delete a watchlist."""
    from ..services.redisq.entity_watchlist import get_entity_watchlist_manager

    manager = get_entity_watchlist_manager()
    watchlist = manager.get_watchlist(args.name)

    if watchlist is None:
        return {
            "status": "error",
            "error": f"Watchlist '{args.name}' not found",
            "query_timestamp": get_utc_timestamp(),
        }

    deleted = manager.delete_watchlist(watchlist.watchlist_id)

    if deleted:
        return {
            "status": "ok",
            "message": f"Deleted watchlist '{args.name}'",
            "query_timestamp": get_utc_timestamp(),
        }
    else:
        return {
            "status": "error",
            "error": "Failed to delete watchlist",
            "query_timestamp": get_utc_timestamp(),
        }


def cmd_sync_wars(args: argparse.Namespace) -> dict:
    """Sync war targets from ESI."""
    from ..services.redisq.entity_watchlist import (
        WarTargetSyncer,
        get_entity_watchlist_manager,
    )

    # Get character and corporation IDs
    character_id = args.character_id if hasattr(args, "character_id") else None
    corporation_id = args.corporation_id if hasattr(args, "corporation_id") else None

    if character_id is None or corporation_id is None:
        return {
            "status": "error",
            "error": "Both --character-id and --corporation-id are required",
            "query_timestamp": get_utc_timestamp(),
        }

    manager = get_entity_watchlist_manager()
    syncer = WarTargetSyncer(manager)

    print(f"Syncing wars for corporation {corporation_id}...")

    async def run_sync():
        return await syncer.sync_wars(character_id, corporation_id)

    result = asyncio.run(run_sync())

    if result.success:
        return {
            "status": "ok",
            "wars_checked": result.wars_checked,
            "entities_added": result.entities_added,
            "entities_removed": result.entities_removed,
            "query_timestamp": get_utc_timestamp(),
        }
    else:
        return {
            "status": "error",
            "error": result.error,
            "query_timestamp": get_utc_timestamp(),
        }


# ===========================================================================
# Topology Commands
# ===========================================================================


def cmd_topology_build(args: argparse.Namespace) -> dict:
    """
    Build or rebuild the operational topology.
    """
    from ..services.redisq.interest.config import ContextAwareTopologyConfig
    from ..services.redisq.notifications.config import TopologyConfig
    from ..services.redisq.topology import build_topology

    # Get systems from args or config
    systems: list[str] = []
    weights: dict[str, float] | None = None

    if args.systems:
        systems = args.systems
    else:
        # Try context-aware config first
        context_config = ContextAwareTopologyConfig.load()
        if context_config.has_geographic:
            # Extract system names from geographic.systems
            systems = [
                s.get("name") for s in context_config.geographic.get("systems", []) if s.get("name")
            ]
            # Convert home_weights to legacy format if present
            home_weights = context_config.geographic.get("home_weights", {})
            if home_weights:
                weights = {
                    "operational": home_weights.get(0, home_weights.get("0", 1.0)),
                    "hop_1": home_weights.get(1, home_weights.get("1", 1.0)),
                    "hop_2": home_weights.get(2, home_weights.get("2", 0.7)),
                }

        # Fall back to legacy config
        if not systems:
            legacy_config = TopologyConfig.load()
            if legacy_config.operational_systems:
                systems = legacy_config.operational_systems
                weights = legacy_config.interest_weights if legacy_config.interest_weights else None

    if not systems:
        return {
            "status": "error",
            "error": "No operational systems specified. Use --systems or configure in config.json",
            "query_timestamp": get_utc_timestamp(),
        }

    print(f"Building topology for: {', '.join(systems)}")

    try:
        interest_map = build_topology(systems, weights, save_cache=True)
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "query_timestamp": get_utc_timestamp(),
        }

    # Build summary
    hop_0 = interest_map.get_systems_by_hop(0)
    hop_1 = interest_map.get_systems_by_hop(1)
    hop_2 = interest_map.get_systems_by_hop(2)
    special = interest_map.get_special_systems()

    print("\n" + "=" * 64)
    print("OPERATIONAL TOPOLOGY")
    print("=" * 64)
    print(f"Base Systems (1.0): {', '.join(s.system_name for s in hop_0)}")
    print("-" * 64)

    if interest_map.routes:
        print("Routes:")
        for route_name, route_path in interest_map.routes.items():
            print(
                f"  {route_name}: {len(route_path) - 1} jumps ({' -> '.join(route_path[1:-1] or ['direct'])})"
            )
        print("-" * 64)

    print(f"1-Hop Neighbors (1.0): {len(hop_1)} systems")
    if hop_1:
        # Group by from_system
        by_source: dict[str, list[str]] = {}
        for s in hop_1:
            src = s.from_system or "unknown"
            if src not in by_source:
                by_source[src] = []
            by_source[src].append(s.system_name)
        for src, names in by_source.items():
            print(f"  From {src}: {', '.join(sorted(names)[:5])}{'...' if len(names) > 5 else ''}")
    print("-" * 64)

    print(f"2-Hop Neighbors (0.7): {len(hop_2)} systems")
    if hop_2:
        by_source = {}
        for s in hop_2:
            src = s.from_system or "unknown"
            if src not in by_source:
                by_source[src] = []
            by_source[src].append(s.system_name)
        for src, names in list(by_source.items())[:3]:
            print(f"  From {src}: {', '.join(sorted(names)[:5])}{'...' if len(names) > 5 else ''}")
        if len(by_source) > 3:
            print(f"  ... and {len(by_source) - 3} more sources")
    print("-" * 64)

    print("Special Systems:")
    if special["gank_pipes"]:
        print(f"  ⚠️  Gank Pipes: {', '.join(special['gank_pipes'])}")
    else:
        print("  ⚠️  Gank Pipes: (none in area)")

    if special["trade_hubs"]:
        print(f"  🏪 Trade Hubs: {', '.join(special['trade_hubs'])}")
    else:
        print("  🏪 Trade Hubs: (none in area)")

    if special["border_systems"]:
        print(
            f"  🔶 Border Systems: {', '.join(special['border_systems'][:5])}{'...' if len(special['border_systems']) > 5 else ''}"
        )
    else:
        print("  🔶 Border Systems: (none in area)")

    print("=" * 64)
    print(f"Total: {interest_map.total_systems} systems tracked | Cache: cache/topology_map.json")

    return {
        "status": "ok",
        "operational_systems": systems,
        "total_systems": interest_map.total_systems,
        "hop_0_count": len(hop_0),
        "hop_1_count": len(hop_1),
        "hop_2_count": len(hop_2),
        "special_systems": special,
        "routes": interest_map.routes,
        "query_timestamp": get_utc_timestamp(),
    }


def cmd_topology_show(args: argparse.Namespace) -> dict:
    """
    Show the current operational topology.
    """
    from ..services.redisq.topology import InterestMap

    interest_map = InterestMap.load()

    if interest_map is None:
        return {
            "status": "error",
            "error": "No topology found. Run 'uv run aria-esi topology-build' to create one.",
            "query_timestamp": get_utc_timestamp(),
        }

    # Build summary similar to topology-build output
    hop_0 = interest_map.get_systems_by_hop(0)
    hop_1 = interest_map.get_systems_by_hop(1)
    hop_2 = interest_map.get_systems_by_hop(2)
    special = interest_map.get_special_systems()

    from datetime import datetime

    built_time = (
        datetime.fromtimestamp(interest_map.built_at).isoformat()
        if interest_map.built_at
        else "unknown"
    )

    print("\n" + "=" * 64)
    print("OPERATIONAL TOPOLOGY")
    print("=" * 64)
    print(f"Built: {built_time}")
    print(f"Base Systems: {', '.join(s.system_name for s in hop_0)}")
    print("-" * 64)
    print(f"1-Hop Neighbors: {len(hop_1)} systems")
    print(f"2-Hop Neighbors: {len(hop_2)} systems")
    print(f"Total: {interest_map.total_systems} systems")
    print("-" * 64)

    if special["border_systems"]:
        print(f"Border Systems: {', '.join(special['border_systems'][:10])}")
    if special["gank_pipes"]:
        print(f"Gank Pipes in Area: {', '.join(special['gank_pipes'])}")
    if special["trade_hubs"]:
        print(f"Trade Hubs in Area: {', '.join(special['trade_hubs'])}")

    print("=" * 64)

    return {
        "status": "ok",
        "built_at": built_time,
        "operational_systems": interest_map.operational_systems,
        "total_systems": interest_map.total_systems,
        "hop_0_count": len(hop_0),
        "hop_1_count": len(hop_1),
        "hop_2_count": len(hop_2),
        "special_systems": special,
        "query_timestamp": get_utc_timestamp(),
    }


def cmd_topology_explain(args: argparse.Namespace) -> dict:
    """
    Explain interest calculation for a specific system.

    Shows breakdown of how each layer contributes to the final interest score.
    """
    from ..services.redisq.interest import ContextAwareTopologyConfig
    from ..services.redisq.topology import InterestMap
    from ..universe import load_universe_graph

    system_name = args.system
    graph = load_universe_graph()

    # Resolve system name to ID
    idx = graph.resolve_name(system_name)
    if idx is None:
        return {
            "status": "error",
            "error": f"Unknown system: {system_name}",
            "query_timestamp": get_utc_timestamp(),
        }

    system_id = graph.get_system_id(idx)
    system_sec = float(graph.security[idx])

    print("\n" + "=" * 64)
    print(f"INTEREST CALCULATION: {system_name}")
    print(f"System ID: {system_id} | Security: {system_sec:.2f}")
    print("=" * 64)

    # Try context-aware config first
    ctx_config = ContextAwareTopologyConfig.load()

    if ctx_config.enabled:
        print("\nMode: Context-Aware Topology")
        print("-" * 64)

        try:
            calculator = ctx_config.build_calculator(graph=graph)

            # Calculate interest
            score = calculator.calculate_system_interest(system_id)

            print(f"\nFinal Interest: {score.interest:.3f} (tier: {score.tier})")
            print(f"Base Interest:  {score.base_interest:.3f}")
            print(f"Dominant Layer: {score.dominant_layer}")

            if score.escalation and score.escalation.multiplier != 1.0:
                print(f"Escalation:     {score.escalation.multiplier}x ({score.escalation.reason})")

            print("\nLayer Breakdown:")
            for layer_name, layer_score in sorted(
                score.layer_scores.items(),
                key=lambda x: x[1].score,
                reverse=True,
            ):
                marker = "→" if layer_name == score.dominant_layer else " "
                reason = f" ({layer_score.reason})" if layer_score.reason else ""
                print(f"  {marker} {layer_name}: {layer_score.score:.3f}{reason}")

            return {
                "status": "ok",
                "mode": "context_aware",
                "system": {
                    "name": system_name,
                    "id": system_id,
                    "security": system_sec,
                },
                "score": score.to_dict(),
                "query_timestamp": get_utc_timestamp(),
            }

        except Exception as e:
            print(f"\nError building calculator: {e}")
            print("Falling back to legacy topology...")

    # Fall back to legacy topology
    interest_map = InterestMap.load()

    if interest_map is None:
        print("\nNo topology configured.")
        print("Configure context_topology in config.json or run 'topology-build'")
        return {
            "status": "error",
            "error": "No topology configured",
            "query_timestamp": get_utc_timestamp(),
        }

    print("\nMode: Legacy Topology")
    print("-" * 64)

    system_info = interest_map.get_system_info(system_id)

    if system_info is None:
        print(f"\n{system_name} is NOT in the operational topology")
        print("Interest: 0.0 (filtered)")
        return {
            "status": "ok",
            "mode": "legacy",
            "system": {
                "name": system_name,
                "id": system_id,
                "security": system_sec,
            },
            "in_topology": False,
            "interest": 0.0,
            "query_timestamp": get_utc_timestamp(),
        }

    print(f"\nInterest: {system_info.interest:.2f}")
    print(f"Hop Level: {system_info.hop_level}")
    if system_info.from_system:
        print(f"Connected via: {system_info.from_system}")

    flags = []
    if system_info.is_border:
        flags.append("border system")
    if system_info.is_gank_pipe:
        flags.append("gank pipe")
    if system_info.is_trade_hub:
        flags.append("trade hub")

    if flags:
        print(f"Flags: {', '.join(flags)}")

    print("=" * 64)

    return {
        "status": "ok",
        "mode": "legacy",
        "system": {
            "name": system_name,
            "id": system_id,
            "security": system_sec,
        },
        "in_topology": True,
        "interest": system_info.interest,
        "hop_level": system_info.hop_level,
        "from_system": system_info.from_system,
        "is_border": system_info.is_border,
        "is_gank_pipe": system_info.is_gank_pipe,
        "is_trade_hub": system_info.is_trade_hub,
        "query_timestamp": get_utc_timestamp(),
    }


def cmd_topology_migrate(args: argparse.Namespace) -> dict:
    """
    Migrate legacy topology configuration to context-aware format.

    Reads the current legacy topology config and outputs the equivalent
    context_topology configuration.
    """
    import json

    from ..services.redisq.interest import list_presets, migrate_legacy_config
    from ..services.redisq.notifications.config import TopologyConfig

    legacy_config = TopologyConfig.load()

    if not legacy_config.operational_systems:
        print("No legacy topology configuration found.")
        print("\nTo configure context-aware topology, add to userdata/config.json:")
        print(
            """
{
  "redisq": {
    "context_topology": {
      "enabled": true,
      "geographic": {
        "systems": [
          {"name": "YourHome", "classification": "home"},
          {"name": "HuntingGround", "classification": "hunting"}
        ]
      },
      "entity": {
        "corp_id": YOUR_CORP_ID
      }
    }
  }
}
"""
        )
        return {
            "status": "info",
            "message": "No legacy config to migrate",
            "query_timestamp": get_utc_timestamp(),
        }

    # Migrate the configuration
    new_config = migrate_legacy_config(
        {
            "enabled": legacy_config.enabled,
            "operational_systems": legacy_config.operational_systems,
            "interest_weights": legacy_config.interest_weights,
        }
    )

    # Suggest an archetype if requested
    archetype = args.archetype if hasattr(args, "archetype") and args.archetype else None

    print("\n" + "=" * 64)
    print("LEGACY TO CONTEXT-AWARE MIGRATION")
    print("=" * 64)

    print("\nLegacy Configuration:")
    print(f"  Operational Systems: {', '.join(legacy_config.operational_systems)}")
    print(f"  Interest Weights: {legacy_config.interest_weights}")

    print("\n" + "-" * 64)
    print("Migrated Configuration:")

    migrated_dict = new_config.to_dict()
    if archetype:
        migrated_dict["archetype"] = archetype

    # Pretty print the migrated config
    print("\nAdd this to userdata/config.json under redisq.context_topology:")
    print(json.dumps(migrated_dict, indent=2))

    print("\n" + "-" * 64)
    print("Available Archetypes (optional):")
    for name, desc in list_presets():
        print(f"  {name}: {desc}")

    print('\nTo apply an archetype, add "archetype": "<name>" to your config.')
    print("=" * 64)

    return {
        "status": "ok",
        "legacy_config": {
            "operational_systems": legacy_config.operational_systems,
            "interest_weights": legacy_config.interest_weights,
        },
        "migrated_config": migrated_dict,
        "query_timestamp": get_utc_timestamp(),
    }


def cmd_topology_presets(args: argparse.Namespace) -> dict:
    """
    List available archetype presets for context-aware topology.
    """
    from ..services.redisq.interest import ARCHETYPE_PRESETS, list_presets

    print("\n" + "=" * 64)
    print("CONTEXT-AWARE TOPOLOGY ARCHETYPES")
    print("=" * 64)

    for name, description in list_presets():
        preset = ARCHETYPE_PRESETS[name]

        print(f"\n{name.upper()}")
        print(f"  {description}")
        print()

        # Show key thresholds
        fetch = preset.get("fetch_threshold", 0.0)
        log = preset.get("log_threshold", 0.3)
        digest = preset.get("digest_threshold", 0.6)
        priority = preset.get("priority_threshold", 0.8)

        print(f"  Thresholds: fetch={fetch}, log={log}, digest={digest}, priority={priority}")

        # Show enabled patterns
        patterns = preset.get("patterns", {})
        pattern_flags = []
        if patterns.get("gatecamp_detection"):
            pattern_flags.append("gatecamp")
        if patterns.get("spike_detection"):
            pattern_flags.append("spike")
        if pattern_flags:
            print(f"  Pattern Detection: {', '.join(pattern_flags)}")

        # Show key entity weights
        entity = preset.get("entity", {})
        corp_vic = entity.get("corp_member_victim", 1.0)
        war = entity.get("war_target", 0.95)
        print(f"  Corp Loss Interest: {corp_vic}, War Target: {war}")

    print("\n" + "=" * 64)
    print('Usage: Add "archetype": "<name>" to context_topology config')
    print("=" * 64)

    return {
        "status": "ok",
        "presets": [{"name": name, "description": desc} for name, desc in list_presets()],
        "query_timestamp": get_utc_timestamp(),
    }


def register_parsers(subparsers) -> None:
    """Register RedisQ command parsers."""

    # redisq-start
    start_parser = subparsers.add_parser(
        "redisq-start",
        help="Start RedisQ real-time kill streaming",
    )
    start_parser.add_argument(
        "--regions",
        type=int,
        nargs="+",
        help="Region IDs to filter (default: all)",
    )
    start_parser.add_argument(
        "--min-value",
        type=int,
        help="Minimum kill value in ISK",
    )
    start_parser.add_argument(
        "--retention",
        type=int,
        help="Hours to retain kill data (default: 24)",
    )
    start_parser.add_argument(
        "--no-recovery",
        action="store_true",
        help="Skip startup gap recovery",
    )
    start_parser.set_defaults(func=cmd_redisq_start)

    # redisq-stop
    stop_parser = subparsers.add_parser(
        "redisq-stop",
        help="Stop RedisQ service (info only)",
    )
    stop_parser.set_defaults(func=cmd_redisq_stop)

    # redisq-status
    status_parser = subparsers.add_parser(
        "redisq-status",
        help="Show RedisQ service status",
    )
    status_parser.set_defaults(func=cmd_redisq_status)

    # redisq-backfill
    backfill_parser = subparsers.add_parser(
        "redisq-backfill",
        help="Manually backfill kills from zKillboard",
    )
    backfill_parser.add_argument(
        "--hours",
        type=int,
        default=1,
        help="Hours to backfill (default: 1)",
    )
    backfill_parser.add_argument(
        "--regions",
        type=int,
        nargs="+",
        help="Region IDs to backfill",
    )
    backfill_parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum kills to fetch (default: 500)",
    )
    backfill_parser.set_defaults(func=cmd_redisq_backfill)

    # redisq-recent
    recent_parser = subparsers.add_parser(
        "redisq-recent",
        help="Show recent kills from realtime database",
    )
    recent_parser.add_argument(
        "--minutes",
        type=int,
        default=60,
        help="Minutes to look back (default: 60)",
    )
    recent_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum results (default: 20)",
    )
    recent_parser.add_argument(
        "--system",
        type=int,
        help="Filter to specific system ID",
    )
    recent_parser.set_defaults(func=cmd_redisq_recent)

    # redisq-follow
    follow_parser = subparsers.add_parser(
        "redisq-follow",
        help="Stream realtime kills to stdout (tail -f style)",
    )
    follow_parser.add_argument(
        "--minutes",
        type=int,
        default=5,
        help="Minutes to look back per poll (default: 5)",
    )
    follow_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum results per poll (default: 50)",
    )
    follow_parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Poll interval in seconds (default: 5)",
    )
    follow_parser.add_argument(
        "--system",
        type=int,
        help="Filter to specific system ID",
    )
    follow_parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )
    follow_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    follow_parser.add_argument(
        "--backfill",
        action="store_true",
        help="Include existing kills on startup",
    )
    follow_parser.add_argument(
        "--commentary",
        action="store_true",
        help="Enable LLM commentary (requires ANTHROPIC_API_KEY)",
    )
    follow_parser.add_argument(
        "--persona",
        type=str,
        help="Persona override for commentary (e.g., paria-s)",
    )
    follow_parser.add_argument(
        "--style",
        choices=["conversational", "radio"],
        help="Commentary style",
    )
    follow_parser.add_argument(
        "--model",
        type=str,
        default="claude-sonnet-4-5-20241022",
        help="LLM model for commentary (default: claude-sonnet-4-5-20241022)",
    )
    follow_parser.add_argument(
        "--warrant-threshold",
        type=float,
        default=0.3,
        help="Warrant score threshold for commentary (default: 0.3)",
    )
    follow_parser.add_argument(
        "--gatecamp",
        action="store_true",
        help="Include gatecamp detection context",
    )
    follow_parser.set_defaults(func=cmd_redisq_follow)

    # redisq-watched
    watched_parser = subparsers.add_parser(
        "redisq-watched",
        help="Show kills involving watched entities",
    )
    watched_parser.add_argument(
        "--minutes",
        type=int,
        default=60,
        help="Minutes to look back (default: 60)",
    )
    watched_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum results (default: 20)",
    )
    watched_parser.add_argument(
        "--system",
        type=int,
        help="Filter to specific system ID",
    )
    watched_parser.set_defaults(func=cmd_redisq_watched)

    # ===========================================================================
    # Entity Watchlist Commands
    # ===========================================================================

    # watchlist-list
    wl_list_parser = subparsers.add_parser(
        "watchlist-list",
        help="List entity watchlists",
    )
    wl_list_parser.add_argument(
        "--type",
        choices=["manual", "war_targets", "contacts"],
        help="Filter by watchlist type",
    )
    wl_list_parser.set_defaults(func=cmd_watchlist_list)

    # watchlist-show
    wl_show_parser = subparsers.add_parser(
        "watchlist-show",
        help="Show entities in a watchlist",
    )
    wl_show_parser.add_argument("name", help="Watchlist name")
    wl_show_parser.set_defaults(func=cmd_watchlist_show)

    # watchlist-create
    wl_create_parser = subparsers.add_parser(
        "watchlist-create",
        help="Create a new entity watchlist",
    )
    wl_create_parser.add_argument("name", help="Watchlist name")
    wl_create_parser.add_argument("--description", help="Optional description")
    wl_create_parser.set_defaults(func=cmd_watchlist_create)

    # watchlist-add
    wl_add_parser = subparsers.add_parser(
        "watchlist-add",
        help="Add a corporation or alliance to a watchlist",
    )
    wl_add_parser.add_argument("name", help="Watchlist name")
    wl_add_parser.add_argument("entity_id", type=int, help="Corporation or alliance ID")
    wl_add_parser.add_argument(
        "--type",
        choices=["corporation", "alliance"],
        default="corporation",
        help="Entity type (default: corporation)",
    )
    wl_add_parser.add_argument("--entity-name", help="Optional entity name for display")
    wl_add_parser.add_argument("--reason", help="Optional reason for adding")
    wl_add_parser.set_defaults(func=cmd_watchlist_add)

    # watchlist-remove
    wl_remove_parser = subparsers.add_parser(
        "watchlist-remove",
        help="Remove an entity from a watchlist",
    )
    wl_remove_parser.add_argument("name", help="Watchlist name")
    wl_remove_parser.add_argument("entity_id", type=int, help="Entity ID to remove")
    wl_remove_parser.add_argument(
        "--type",
        choices=["corporation", "alliance"],
        default="corporation",
        help="Entity type",
    )
    wl_remove_parser.set_defaults(func=cmd_watchlist_remove)

    # watchlist-delete
    wl_delete_parser = subparsers.add_parser(
        "watchlist-delete",
        help="Delete a watchlist",
    )
    wl_delete_parser.add_argument("name", help="Watchlist name to delete")
    wl_delete_parser.set_defaults(func=cmd_watchlist_delete)

    # sync-wars
    sync_wars_parser = subparsers.add_parser(
        "sync-wars",
        help="Sync war targets from ESI",
    )
    sync_wars_parser.add_argument(
        "--character-id",
        type=int,
        help="Character ID (uses active pilot if not specified)",
    )
    sync_wars_parser.add_argument(
        "--corporation-id",
        type=int,
        help="Corporation ID (required if character-id specified)",
    )
    sync_wars_parser.set_defaults(func=cmd_sync_wars)

    # ===========================================================================
    # Topology Commands
    # ===========================================================================

    # topology-build
    topo_build_parser = subparsers.add_parser(
        "topology-build",
        help="Build operational topology for kill pre-filtering",
    )
    topo_build_parser.add_argument(
        "--systems",
        nargs="+",
        help="Operational systems (overrides config)",
    )
    topo_build_parser.set_defaults(func=cmd_topology_build)

    # topology-show
    topo_show_parser = subparsers.add_parser(
        "topology-show",
        help="Show current operational topology",
    )
    topo_show_parser.set_defaults(func=cmd_topology_show)

    # topology-explain
    topo_explain_parser = subparsers.add_parser(
        "topology-explain",
        help="Explain interest calculation for a system",
    )
    topo_explain_parser.add_argument(
        "system",
        help="System name to explain",
    )
    topo_explain_parser.set_defaults(func=cmd_topology_explain)

    # topology-migrate
    topo_migrate_parser = subparsers.add_parser(
        "topology-migrate",
        help="Migrate legacy topology config to context-aware format",
    )
    topo_migrate_parser.add_argument(
        "--archetype",
        choices=["hunter", "industrial", "sovereignty", "wormhole", "mission_runner"],
        help="Suggest an archetype preset",
    )
    topo_migrate_parser.set_defaults(func=cmd_topology_migrate)

    # topology-presets
    topo_presets_parser = subparsers.add_parser(
        "topology-presets",
        help="List available archetype presets",
    )
    topo_presets_parser.set_defaults(func=cmd_topology_presets)
