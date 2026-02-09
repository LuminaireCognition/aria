"""Fixtures for killmail_store tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio

from aria_esi.services.killmail_store import (
    ESIKillmail,
    KillmailRecord,
    SQLiteKillmailStore,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test_killmails.db"


@pytest_asyncio.fixture
async def store(temp_db_path: Path) -> AsyncGenerator[SQLiteKillmailStore, None]:
    """Create and initialize a test store."""
    store = SQLiteKillmailStore(db_path=temp_db_path)
    await store.initialize()
    yield store
    await store.close()


@pytest.fixture
def sample_kill() -> KillmailRecord:
    """Create a sample killmail record."""
    return KillmailRecord(
        kill_id=123456789,
        kill_time=int(datetime(2026, 1, 26, 12, 0, 0).timestamp()),
        solar_system_id=30000142,  # Jita
        zkb_hash="abc123def456",
        zkb_total_value=1_500_000_000.0,
        zkb_points=100,
        zkb_is_npc=False,
        zkb_is_solo=False,
        zkb_is_awox=False,
        ingested_at=int(datetime(2026, 1, 26, 12, 0, 5).timestamp()),
        victim_ship_type_id=670,  # Capsule
        victim_corporation_id=98000001,
        victim_alliance_id=None,
    )


@pytest.fixture
def sample_kills() -> list[KillmailRecord]:
    """Create a list of sample killmail records."""
    base_time = int(datetime(2026, 1, 26, 12, 0, 0).timestamp())
    return [
        KillmailRecord(
            kill_id=123456789 + i,
            kill_time=base_time + i * 60,
            solar_system_id=30000142 if i % 2 == 0 else 30000143,
            zkb_hash=f"hash{i}",
            zkb_total_value=100_000_000.0 * (i + 1),
            zkb_points=10 * (i + 1),
            zkb_is_npc=False,
            zkb_is_solo=i == 0,
            zkb_is_awox=False,
            ingested_at=base_time + i * 60 + 5,
            victim_ship_type_id=670 + i,
            victim_corporation_id=98000001 + i,
            victim_alliance_id=99000001 if i % 2 == 0 else None,
        )
        for i in range(10)
    ]


@pytest.fixture
def sample_esi_details() -> ESIKillmail:
    """Create sample ESI killmail details."""
    return ESIKillmail(
        kill_id=123456789,
        fetched_at=int(datetime(2026, 1, 26, 12, 0, 10).timestamp()),
        fetch_status="success",
        fetch_attempts=1,
        victim_character_id=12345678,
        victim_ship_type_id=670,
        victim_corporation_id=98000001,
        victim_alliance_id=None,
        victim_damage_taken=1000,
        attacker_count=5,
        final_blow_character_id=87654321,
        final_blow_ship_type_id=24690,
        final_blow_corporation_id=98000002,
        attackers_json='[{"character_id": 87654321, "damage_done": 1000}]',
        items_json='[{"type_id": 123, "quantity_destroyed": 1}]',
        position_json='{"x": 1.0, "y": 2.0, "z": 3.0}',
    )
