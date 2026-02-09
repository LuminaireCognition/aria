"""
Fixtures for RedisQ tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def sample_redisq_package() -> dict[str, Any]:
    """Sample RedisQ package response."""
    return {
        "package": {
            "killmail": {
                "killmail_id": 123456789,
                "killmail_time": "2024-01-15T12:34:56Z",
            },
            "zkb": {
                "hash": "abc123def456",
                "totalValue": 150000000.0,
                "points": 10,
            },
        }
    }


@pytest.fixture
def sample_esi_killmail() -> dict[str, Any]:
    """Sample ESI killmail response."""
    return {
        "killmail_id": 123456789,
        "killmail_time": "2024-01-15T12:34:56Z",
        "solar_system_id": 30000142,  # Jita
        "victim": {
            "ship_type_id": 17740,  # Hurricane
            "corporation_id": 98000001,
            "alliance_id": 99000001,
            "character_id": 95000001,
        },
        "attackers": [
            {
                "ship_type_id": 17812,  # Brutix
                "corporation_id": 98000002,
                "alliance_id": 99000002,
                "character_id": 95000002,
                "final_blow": True,
                "damage_done": 5000,
            },
            {
                "ship_type_id": 24690,  # Talos
                "corporation_id": 98000002,
                "alliance_id": 99000002,
                "character_id": 95000003,
                "final_blow": False,
                "damage_done": 3000,
            },
        ],
    }


@pytest.fixture
def sample_zkb_data() -> dict[str, Any]:
    """Sample zKillboard metadata."""
    return {
        "hash": "abc123def456",
        "totalValue": 150000000.0,
        "points": 10,
        "fittedValue": 120000000.0,
        "droppedValue": 30000000.0,
        "destroyedValue": 120000000.0,
    }


@pytest.fixture
def sample_pod_killmail() -> dict[str, Any]:
    """Sample pod kill ESI response."""
    return {
        "killmail_id": 123456790,
        "killmail_time": "2024-01-15T12:35:00Z",
        "solar_system_id": 30000142,
        "victim": {
            "ship_type_id": 670,  # Capsule
            "corporation_id": 98000001,
            "alliance_id": None,
            "character_id": 95000001,
        },
        "attackers": [
            {
                "ship_type_id": 17812,
                "corporation_id": 98000002,
                "final_blow": True,
                "damage_done": 100,
            },
        ],
    }


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Temporary database path for testing."""
    return tmp_path / "test_aria.db"


@pytest.fixture
def mock_settings(temp_db_path: Path, monkeypatch):
    """Mock settings with temp database path."""
    from aria_esi.core.config import reset_settings

    monkeypatch.setenv("ARIA_DB", str(temp_db_path))
    reset_settings()

    yield

    reset_settings()
