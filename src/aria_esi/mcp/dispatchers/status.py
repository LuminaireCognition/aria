"""
Unified Status Tool for MCP Server.

Aggregates status from all domains:
- Activity cache (kills, jumps, FW data)
- Market cache (Fuzzwork, ESI orders, ESI history)
- SDE database
- EOS fitting engine
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.logging import get_logger
from ..policy import check_capability

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger(__name__)


def register_status_tool(server: FastMCP) -> None:
    """
    Register the unified status tool with MCP server.

    Args:
        server: MCP Server instance
    """

    @server.tool()
    async def status() -> dict:
        """
        Get unified status across all ARIA domains.

        Returns aggregated status for:
        - Activity cache: Kills, jumps, and FW data freshness
        - Market cache: Fuzzwork, ESI orders, and history cache status
        - SDE database: Type count and database health
        - Fitting engine: EOS data availability and version

        Returns:
            Dictionary with status for each domain:
            - activity: Cache status for kills, jumps, FW data
            - market: Fuzzwork, ESI orders, ESI history cache status
            - sde: Database stats, type count, availability
            - fitting: EOS data validity, version, available files
            - summary: Overall health indicator

        Example response:
            {
                "activity": {
                    "kills": {"cached_systems": 5000, "stale": false, ...},
                    "jumps": {"cached_systems": 5000, "stale": false, ...},
                    "fw": {"cached_systems": 200, "stale": false, ...}
                },
                "market": {
                    "fuzzwork": {"cached_types": 1000, "stale": false, ...},
                    "esi_orders": {"cached_types": 50, "stale": true, ...},
                    ...
                },
                "sde": {
                    "is_available": true,
                    "type_count": 45678,
                    "database_size_mb": 15.2
                },
                "fitting": {
                    "is_valid": true,
                    "version": "2548611",
                    "total_records": 45678
                },
                "summary": {
                    "all_healthy": true,
                    "issues": []
                }
            }
        """
        # Policy check - verify status tool is allowed
        check_capability("status", "_default")

        result: dict = {
            "activity": {},
            "market": {},
            "sde": {},
            "fitting": {},
            "summary": {"all_healthy": True, "issues": []},
        }
        issues: list[str] = []

        # Activity cache status
        try:
            from ..activity import get_activity_cache

            cache = get_activity_cache()
            activity_status = cache.get_cache_status()

            result["activity"] = {
                "kills": {
                    "cached_systems": activity_status["kills"]["cached_systems"],
                    "age_seconds": activity_status["kills"]["age_seconds"],
                    "ttl_seconds": activity_status["kills"]["ttl_seconds"],
                    "stale": activity_status["kills"]["stale"],
                },
                "jumps": {
                    "cached_systems": activity_status["jumps"]["cached_systems"],
                    "age_seconds": activity_status["jumps"]["age_seconds"],
                    "ttl_seconds": activity_status["jumps"]["ttl_seconds"],
                    "stale": activity_status["jumps"]["stale"],
                },
                "fw": {
                    "cached_systems": activity_status["fw"]["cached_systems"],
                    "age_seconds": activity_status["fw"]["age_seconds"],
                    "ttl_seconds": activity_status["fw"]["ttl_seconds"],
                    "stale": activity_status["fw"]["stale"],
                },
            }

            # Check for staleness
            if activity_status["kills"]["stale"]:
                issues.append("Activity kill data is stale")
        except Exception as e:
            logger.warning("Failed to get activity cache status: %s", e)
            result["activity"] = {"error": str(e)}
            issues.append("Activity cache unavailable")

        # Market cache status
        try:
            from ..market.cache import get_market_cache
            from ..market.database import get_market_database

            market_cache = get_market_cache()
            market_status = market_cache.get_cache_status()

            db = get_market_database()
            db_stats = db.get_stats()

            result["market"] = {
                "fuzzwork": {
                    "cached_types": market_status.get("fuzzwork", {}).get("cached_types", 0),
                    "age_seconds": market_status.get("fuzzwork", {}).get("age_seconds"),
                    "ttl_seconds": market_status.get("fuzzwork", {}).get("ttl_seconds", 900),
                    "stale": market_status.get("fuzzwork", {}).get("stale", True),
                },
                "esi_orders": {
                    "cached_types": market_status.get("esi_orders", {}).get("cached_types", 0),
                    "age_seconds": market_status.get("esi_orders", {}).get("age_seconds"),
                    "ttl_seconds": market_status.get("esi_orders", {}).get("ttl_seconds", 300),
                    "stale": market_status.get("esi_orders", {}).get("stale", True),
                },
                "database": {
                    "path": db_stats.get("database_path"),
                    "size_mb": round(db_stats.get("database_size_mb", 0), 2),
                    "type_count": db_stats.get("type_count", 0),
                },
            }
        except Exception as e:
            logger.warning("Failed to get market cache status: %s", e)
            result["market"] = {"error": str(e)}
            issues.append("Market cache unavailable")

        # SDE database status
        try:
            from ..market.database import get_market_database

            db = get_market_database()
            stats = db.get_stats()

            type_count = stats.get("type_count", 0)
            result["sde"] = {
                "is_available": type_count > 0,
                "database_path": stats.get("database_path"),
                "database_size_mb": round(stats.get("database_size_mb", 0), 2),
                "type_count": type_count,
            }

            if type_count == 0:
                issues.append("SDE data not seeded - run 'aria-esi sde-seed'")
        except Exception as e:
            logger.warning("Failed to get SDE status: %s", e)
            result["sde"] = {"is_available": False, "error": str(e)}
            issues.append("SDE database unavailable")

        # Fitting engine status
        try:
            from aria_esi.fitting import get_eos_data_manager

            data_manager = get_eos_data_manager()
            fit_status = data_manager.validate()

            result["fitting"] = {
                "is_valid": fit_status.is_valid,
                "data_path": str(fit_status.data_path) if fit_status.data_path else None,
                "version": fit_status.version,
                "total_records": fit_status.total_records,
                "missing_files": fit_status.missing_files,
            }

            if not fit_status.is_valid:
                issues.append("EOS fitting data missing - run 'aria-esi eos-seed'")
        except Exception as e:
            logger.warning("Failed to get fitting status: %s", e)
            result["fitting"] = {"is_valid": False, "error": str(e)}
            issues.append("Fitting engine unavailable")

        # Discord webhook status
        try:
            from aria_esi.services.redisq.notifications import get_notification_manager

            manager = get_notification_manager()
            if manager and manager.is_configured:
                health = manager.get_health_status()
                result["discord"] = {
                    "is_configured": True,
                    "is_healthy": health.is_healthy,
                    "is_paused": health.is_paused,
                    "is_quiet_hours": health.is_quiet_hours,
                    "success_rate": health.success_rate,
                    "queue_depth": health.queue_depth,
                    "active_throttles": health.active_throttles,
                    "last_success": health.last_success.isoformat()
                    if health.last_success
                    else None,
                    "next_active_time": health.next_active_time.isoformat()
                    if health.next_active_time
                    else None,
                }
                if not health.is_healthy:
                    issues.append("Discord webhook unhealthy")
            else:
                result["discord"] = {"is_configured": False}
        except Exception as e:
            logger.debug("Failed to get Discord notification status: %s", e)
            result["discord"] = {"is_configured": False, "error": str(e)}

        # Killmail store status
        try:
            from datetime import datetime

            from aria_esi.core.config import get_settings
            from aria_esi.services.killmail_store import SQLiteKillmailStore, StoreStats

            store_path = get_settings().killmail_db_path
            if store_path.exists():
                store = SQLiteKillmailStore(db_path=store_path, read_only=True)
                await store.initialize()
                try:
                    store_stats: StoreStats = await store.get_stats()
                    result["killmails"] = {
                        "store": {
                            "total_killmails": store_stats.total_killmails,
                            "total_esi_details": store_stats.total_esi_details,
                            "oldest_killmail": datetime.fromtimestamp(
                                store_stats.oldest_killmail_time
                            ).isoformat()
                            if store_stats.oldest_killmail_time
                            else None,
                            "newest_killmail": datetime.fromtimestamp(
                                store_stats.newest_killmail_time
                            ).isoformat()
                            if store_stats.newest_killmail_time
                            else None,
                            "database_size_mb": round(
                                store_stats.database_size_bytes / 1024 / 1024, 2
                            ),
                        },
                    }
                finally:
                    await store.close()
            else:
                result["killmails"] = {"store": {"initialized": False}}
        except Exception as e:
            logger.debug("Failed to get killmail store status: %s", e)
            result["killmails"] = {"error": str(e)}

        # Ingest metrics from poller
        try:
            from aria_esi.services.redisq.poller import _poller

            if _poller and _poller._running:
                poller_status = _poller.get_status()
                if "killmails" not in result:
                    result["killmails"] = {}
                if poller_status.ingest:
                    result["killmails"]["ingest"] = {
                        "received_total": poller_status.ingest.received_total,
                        "written_total": poller_status.ingest.written_total,
                        "dropped_total": poller_status.ingest.dropped_total,
                        "queue_depth": poller_status.ingest.queue_depth,
                    }
                result["killmails"]["poller"] = {
                    "is_running": poller_status.is_running,
                    "last_poll_time": poller_status.last_poll_time.isoformat()
                    if poller_status.last_poll_time
                    else None,
                    "kills_processed": poller_status.kills_processed,
                }
        except Exception as e:
            logger.debug("Poller status unavailable: %s", e)

        # Worker metrics from notification manager supervisor
        try:
            from aria_esi.services.redisq.notifications import get_notification_manager

            manager = get_notification_manager()
            if manager and hasattr(manager, "_supervisor") and manager._supervisor:
                supervisor_status = manager._supervisor.get_status()
                if "killmails" not in result:
                    result["killmails"] = {}
                result["killmails"]["workers"] = {
                    "total": supervisor_status["workers"]["total"],
                    "active": supervisor_status["workers"]["active"],
                    "metrics": supervisor_status["metrics"],
                }
        except Exception as e:
            logger.debug("Worker status unavailable: %s", e)

        # Build summary
        result["summary"] = {
            "all_healthy": len(issues) == 0,
            "issues": issues,
        }

        return result
