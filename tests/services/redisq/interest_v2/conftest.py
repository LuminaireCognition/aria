"""
Pytest fixtures for Interest Engine v2 tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class MockProcessedKill:
    """Mock ProcessedKill for testing."""

    kill_id: int = 12345678
    solar_system_id: int = 30000142  # Jita
    victim_ship_type_id: int | None = 24690  # Vexor
    victim_corporation_id: int | None = 98000001
    victim_alliance_id: int | None = 99001234
    is_pod_kill: bool = False
    attacker_count: int = 3
    attacker_corps: list[int] = field(default_factory=lambda: [98000002, 98000003])
    attacker_alliances: list[int] = field(default_factory=lambda: [99005678])
    attacker_ship_types: list[int] = field(default_factory=lambda: [17703, 17703])  # Astero
    final_blow_ship_type_id: int | None = 17703
    total_value: float = 150_000_000.0  # 150M ISK


@pytest.fixture
def mock_kill() -> MockProcessedKill:
    """Create a basic mock kill for testing."""
    return MockProcessedKill()


@pytest.fixture
def high_value_kill() -> MockProcessedKill:
    """Create a high-value mock kill."""
    return MockProcessedKill(
        kill_id=12345679,
        victim_ship_type_id=28606,  # Orca
        total_value=3_500_000_000.0,  # 3.5B ISK
    )


@pytest.fixture
def pod_kill() -> MockProcessedKill:
    """Create a pod kill."""
    return MockProcessedKill(
        kill_id=12345680,
        victim_ship_type_id=670,  # Capsule
        is_pod_kill=True,
        total_value=50_000_000.0,  # 50M implants
    )


@pytest.fixture
def npc_only_kill() -> MockProcessedKill:
    """Create a kill with only NPC attackers."""
    return MockProcessedKill(
        kill_id=12345681,
        attacker_count=5,
        attacker_corps=[1000125, 1000127],  # NPC corps (< 2M)
        attacker_alliances=[],
        total_value=10_000_000.0,
    )


@pytest.fixture
def solo_kill() -> MockProcessedKill:
    """Create a solo kill."""
    return MockProcessedKill(
        kill_id=12345682,
        attacker_count=1,
        attacker_corps=[98000002],
        attacker_alliances=[99005678],
    )


@pytest.fixture
def sample_interest_config() -> dict[str, Any]:
    """Create a sample interest configuration."""
    return {
        "engine": "v2",
        "preset": "trade-hub",
        "weights": {
            "location": 0.8,
            "value": 0.7,
            "politics": 0.2,
        },
        "thresholds": {
            "notify": 0.6,
            "priority": 0.85,
        },
    }


@pytest.fixture
def simple_tier_config() -> dict[str, Any]:
    """Create a simple tier configuration."""
    return {
        "engine": "v2",
        "preset": "trade-hub",
        "customize": {
            "location": "+20%",
            "value": "-10%",
        },
    }


@pytest.fixture
def advanced_tier_config() -> dict[str, Any]:
    """Create an advanced tier configuration."""
    return {
        "engine": "v2",
        "mode": "weighted",
        "weights": {
            "location": 0.7,
            "value": 0.7,
            "politics": 0.2,
        },
        "signals": {
            "location": {
                "geographic": {
                    "systems": [
                        {"name": "Jita", "classification": "home"},
                    ]
                }
            },
            "value": {
                "min": 50_000_000,
                "scale": "sigmoid",
            },
        },
        "rules": {
            "always_notify": ["corp_member_victim"],
            "always_ignore": ["npc_only"],
        },
    }


@pytest.fixture
def reset_registry():
    """Reset the global provider registry before/after test."""
    from aria_esi.services.redisq.interest_v2.providers.registry import reset_registry

    reset_registry()
    yield
    reset_registry()


# =============================================================================
# Delivery Testing Fixtures
# =============================================================================


@dataclass
class MockCategoryScore:
    """Mock CategoryScore for testing delivery providers."""

    category: str = "location"
    score: float = 0.75
    weight: float = 0.8
    match: bool = True
    penalty_factor: float = 1.0

    @property
    def penalized_score(self) -> float:
        return self.score * self.penalty_factor

    @property
    def is_enabled(self) -> bool:
        return self.weight > 0


@dataclass
class MockInterestResultV2:
    """Mock InterestResultV2 for testing delivery providers."""

    system_id: int = 30000142
    kill_id: int | None = 12345678
    interest: float = 0.75
    tier: Any = None  # NotificationTier
    mode: Any = None  # AggregationMode
    engine_version: str = "v2"
    is_priority: bool = False
    dominant_category: str | None = "location"
    bypassed_scoring: bool = False
    category_scores: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Import and set defaults for tier and mode
        from aria_esi.services.redisq.interest_v2.models import (
            AggregationMode,
            NotificationTier,
        )

        if self.tier is None:
            self.tier = NotificationTier.NOTIFY
        if self.mode is None:
            self.mode = AggregationMode.WEIGHTED

    def get_category_breakdown(self) -> list[tuple[str, float, float, bool]]:
        """Return mock category breakdown."""
        return [
            (cat, cs.penalized_score, cs.weight, cs.match)
            for cat, cs in self.category_scores.items()
            if cs.is_enabled
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for testing."""
        return {
            "system_id": self.system_id,
            "kill_id": self.kill_id,
            "interest": self.interest,
            "tier": self.tier.value if hasattr(self.tier, "value") else str(self.tier),
            "mode": self.mode.value if hasattr(self.mode, "value") else str(self.mode),
            "engine_version": self.engine_version,
        }


@pytest.fixture
def mock_result_notify() -> MockInterestResultV2:
    """Create a mock result at NOTIFY tier."""
    from aria_esi.services.redisq.interest_v2.models import NotificationTier

    return MockInterestResultV2(
        system_id=30000142,
        kill_id=12345678,
        interest=0.65,
        tier=NotificationTier.NOTIFY,
        is_priority=False,
    )


@pytest.fixture
def mock_result_priority() -> MockInterestResultV2:
    """Create a mock result at PRIORITY tier."""
    from aria_esi.services.redisq.interest_v2.models import NotificationTier

    return MockInterestResultV2(
        system_id=30000142,
        kill_id=12345679,
        interest=0.90,
        tier=NotificationTier.PRIORITY,
        is_priority=True,
    )


@pytest.fixture
def mock_result_with_categories() -> MockInterestResultV2:
    """Create a mock result with category scores."""
    from aria_esi.services.redisq.interest_v2.models import NotificationTier

    return MockInterestResultV2(
        system_id=30000142,
        kill_id=12345680,
        interest=0.72,
        tier=NotificationTier.NOTIFY,
        category_scores={
            "location": MockCategoryScore(category="location", score=0.8, weight=0.7),
            "value": MockCategoryScore(category="value", score=0.6, weight=0.5),
        },
        dominant_category="location",
    )


@pytest.fixture
def mock_result_bypassed() -> MockInterestResultV2:
    """Create a mock result that bypassed scoring."""
    from aria_esi.services.redisq.interest_v2.models import NotificationTier

    return MockInterestResultV2(
        system_id=30000142,
        kill_id=12345681,
        interest=1.0,
        tier=NotificationTier.PRIORITY,
        is_priority=True,
        bypassed_scoring=True,
    )


@pytest.fixture
def sample_discord_config() -> dict[str, Any]:
    """Sample Discord delivery configuration."""
    return {
        "webhook_url": "https://discord.com/api/webhooks/123456/abcdef",
        "username": "ARIA Intel",
        "avatar_url": "https://example.com/avatar.png",
        "mention_role": "987654321",
    }


@pytest.fixture
def sample_webhook_config() -> dict[str, Any]:
    """Sample generic webhook configuration."""
    return {
        "url": "https://example.com/webhook",
        "method": "POST",
        "headers": {"Authorization": "Bearer token123"},
        "include_result": True,
    }


@pytest.fixture
def sample_delivery_config() -> dict[str, Any]:
    """Sample tier-based delivery configuration."""
    return {
        "priority": {
            "destinations": [
                {
                    "provider": "discord",
                    "webhook_url": "https://discord.com/api/webhooks/priority/abc",
                    "mention_role": "111222333",
                },
            ],
            "fallback_on_failure": True,
            "require_all": False,
        },
        "notify": {
            "destinations": [
                {"provider": "log", "level": "INFO"},
            ],
        },
    }
