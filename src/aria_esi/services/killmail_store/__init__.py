"""
Killmail Store - Persistent Storage for zKillboard Kills.

This module provides persistent storage for killmails received from zKillboard's
RedisQ service. It implements the Ingest-Store-Worker architecture described in
KILLMAIL_STORE_REDESIGN_PROPOSAL.md.

Key Components:
- SQLiteKillmailStore: SQLite implementation with WAL mode for concurrent access
- BoundedKillQueue: Memory-bounded queue with drop-oldest backpressure
- ExpungeTask: Background task for data cleanup and retention management
- Protocol classes: KillmailRecord, ESIKillmail, WorkerState, etc.

Usage:
    from aria_esi.services.killmail_store import (
        SQLiteKillmailStore,
        BoundedKillQueue,
        ExpungeTask,
        KillmailRecord,
    )

    # Initialize store
    store = SQLiteKillmailStore()
    await store.initialize()

    # Start expunge task
    expunge = ExpungeTask(store, retention_days=7)
    expunge.start()

    # Insert kills
    await store.insert_kill(kill_record)

    # Query kills
    kills = await store.query_kills(systems=[30000142], limit=50)
"""

from .expunge import ExpungeStats, ExpungeTask
from .protocol import (
    ESIClaim,
    ESIKillmail,
    KillmailRecord,
    KillmailStore,
    StoreStats,
    WorkerState,
)
from .queue import BoundedKillQueue, IngestMetrics
from .sqlite import SQLiteKillmailStore

__all__ = [
    # Store implementation
    "SQLiteKillmailStore",
    # Queue
    "BoundedKillQueue",
    "IngestMetrics",
    # Expunge
    "ExpungeTask",
    "ExpungeStats",
    # Protocol
    "KillmailStore",
    "KillmailRecord",
    "ESIKillmail",
    "WorkerState",
    "ESIClaim",
    "StoreStats",
]
