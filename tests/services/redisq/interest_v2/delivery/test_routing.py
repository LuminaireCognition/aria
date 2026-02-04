"""
Tests for Tier-based Delivery Routing in Interest Engine v2.

Coverage target: 90%+ for src/aria_esi/services/redisq/interest_v2/delivery/routing.py
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.services.redisq.interest_v2.delivery.routing import (
    DeliveryRouter,
    TierRouting,
    create_default_router,
)
from aria_esi.services.redisq.interest_v2.models import (
    AggregationMode,
    NotificationTier,
)

# =============================================================================
# Mock Data Classes
# =============================================================================


@dataclass
class MockInterestResultForRouting:
    """Mock InterestResultV2 for testing routing."""

    system_id: int = 30000142
    kill_id: int | None = 12345678
    interest: float = 0.75
    tier: NotificationTier = NotificationTier.NOTIFY
    mode: AggregationMode = AggregationMode.WEIGHTED
    engine_version: str = "v2"
    dominant_category: str | None = "location"
    bypassed_scoring: bool = False
    is_priority: bool = False
    category_scores: dict[str, Any] = dataclass_field(default_factory=dict)

    def get_category_breakdown(self) -> list[tuple[str, float, float, bool]]:
        """Return empty breakdown."""
        return []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "system_id": self.system_id,
            "kill_id": self.kill_id,
            "interest": self.interest,
            "tier": self.tier.value,
        }


@dataclass
class MockDeliveryProvider:
    """Mock delivery provider for testing."""

    name: str = "mock"
    deliver_result: bool = True
    should_raise: bool = False

    async def deliver(
        self,
        result: Any,
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> bool:
        if self.should_raise:
            raise Exception("Provider error")
        return self.deliver_result


# =============================================================================
# Test TierRouting
# =============================================================================


class TestTierRouting:
    """Tests for TierRouting dataclass."""

    def test_default_values(self) -> None:
        """Default values should be sensible."""
        routing = TierRouting(tier="notify")

        assert routing.tier == "notify"
        assert routing.destinations == []
        assert routing.fallback_on_failure is True
        assert routing.require_all is False

    def test_from_dict_basic(self) -> None:
        """from_dict should create routing from config."""
        routing = TierRouting.from_dict(
            "priority",
            {
                "destinations": [
                    {"provider": "discord", "webhook_url": "https://example.com"},
                    {"provider": "log"},
                ],
            },
        )

        assert routing.tier == "priority"
        assert len(routing.destinations) == 2
        assert routing.destinations[0]["provider"] == "discord"
        assert routing.destinations[1]["provider"] == "log"

    def test_from_dict_empty_destinations(self) -> None:
        """from_dict with no destinations key should default to empty list."""
        routing = TierRouting.from_dict("notify", {})

        assert routing.tier == "notify"
        assert routing.destinations == []

    def test_from_dict_fallback_override(self) -> None:
        """fallback_on_failure can be disabled."""
        routing = TierRouting.from_dict(
            "priority", {"destinations": [], "fallback_on_failure": False}
        )

        assert routing.fallback_on_failure is False

    def test_from_dict_require_all_override(self) -> None:
        """require_all can be enabled."""
        routing = TierRouting.from_dict(
            "priority", {"destinations": [], "require_all": True}
        )

        assert routing.require_all is True


# =============================================================================
# Test DeliveryRouter
# =============================================================================


class TestDeliveryRouter:
    """Tests for DeliveryRouter class."""

    @pytest.fixture
    def mock_result(self) -> MockInterestResultForRouting:
        return MockInterestResultForRouting()

    def test_init_empty_routing(self) -> None:
        """Router should initialize with empty routing."""
        router = DeliveryRouter()
        assert router.list_configured_tiers() == []

    def test_init_with_routing(self) -> None:
        """Router should accept initial routing config."""
        routing = {
            "notify": TierRouting(tier="notify", destinations=[{"provider": "log"}])
        }
        router = DeliveryRouter(routing)

        assert "notify" in router.list_configured_tiers()

    def test_from_config_basic(self) -> None:
        """from_config should create router from dict."""
        config = {
            "priority": {
                "destinations": [{"provider": "discord"}],
            },
            "notify": {
                "destinations": [{"provider": "log"}],
            },
        }
        router = DeliveryRouter.from_config(config)

        assert "priority" in router.list_configured_tiers()
        assert "notify" in router.list_configured_tiers()

    def test_from_config_skips_non_dict(self) -> None:
        """from_config should skip non-dict tier configs."""
        config = {
            "priority": {
                "destinations": [{"provider": "discord"}],
            },
            "invalid": "not a dict",  # Should be skipped
            "another": 123,  # Should be skipped
        }
        router = DeliveryRouter.from_config(config)

        assert router.list_configured_tiers() == ["priority"]

    @pytest.mark.asyncio
    async def test_deliver_no_routing_for_tier(
        self, mock_result: MockInterestResultForRouting
    ) -> None:
        """Deliver should return True when no routing configured."""
        router = DeliveryRouter()
        result = await router.deliver(mock_result, {"title": "Test"})

        assert result is True

    @pytest.mark.asyncio
    async def test_deliver_empty_destinations(
        self, mock_result: MockInterestResultForRouting
    ) -> None:
        """Deliver should return True when destinations list is empty."""
        router = DeliveryRouter(
            {"notify": TierRouting(tier="notify", destinations=[])}
        )
        result = await router.deliver(mock_result, {"title": "Test"})

        assert result is True

    @pytest.mark.asyncio
    async def test_deliver_first_success(
        self, mock_result: MockInterestResultForRouting
    ) -> None:
        """First successful delivery should return True."""
        mock_provider = MockDeliveryProvider(deliver_result=True)

        with patch(
            "aria_esi.services.redisq.interest_v2.providers.registry.get_provider_registry"
        ) as mock_registry_fn:
            mock_registry = MagicMock()
            mock_registry.get_delivery.return_value = mock_provider
            mock_registry_fn.return_value = mock_registry

            router = DeliveryRouter(
                {
                    "notify": TierRouting(
                        tier="notify", destinations=[{"provider": "mock"}]
                    )
                }
            )
            result = await router.deliver(mock_result, {"title": "Test"})

            assert result is True

    @pytest.mark.asyncio
    async def test_deliver_fallback_on_failure(
        self, mock_result: MockInterestResultForRouting
    ) -> None:
        """Should try next destination on failure when fallback enabled."""
        failing_provider = MockDeliveryProvider(deliver_result=False)
        success_provider = MockDeliveryProvider(deliver_result=True)

        with patch(
            "aria_esi.services.redisq.interest_v2.providers.registry.get_provider_registry"
        ) as mock_registry_fn:
            mock_registry = MagicMock()
            # First call returns failing, second returns success
            mock_registry.get_delivery.side_effect = [
                failing_provider,
                success_provider,
            ]
            mock_registry_fn.return_value = mock_registry

            router = DeliveryRouter(
                {
                    "notify": TierRouting(
                        tier="notify",
                        destinations=[
                            {"provider": "first"},
                            {"provider": "second"},
                        ],
                        fallback_on_failure=True,
                    )
                }
            )
            result = await router.deliver(mock_result, {"title": "Test"})

            assert result is True

    @pytest.mark.asyncio
    async def test_deliver_fallback_disabled_stops(
        self, mock_result: MockInterestResultForRouting
    ) -> None:
        """Should not try next destination when fallback disabled."""
        failing_provider = MockDeliveryProvider(deliver_result=False)
        success_provider = MockDeliveryProvider(deliver_result=True)

        with patch(
            "aria_esi.services.redisq.interest_v2.providers.registry.get_provider_registry"
        ) as mock_registry_fn:
            mock_registry = MagicMock()
            # Even if second would succeed, shouldn't be called
            mock_registry.get_delivery.side_effect = [
                failing_provider,
                success_provider,
            ]
            mock_registry_fn.return_value = mock_registry

            router = DeliveryRouter(
                {
                    "notify": TierRouting(
                        tier="notify",
                        destinations=[
                            {"provider": "first"},
                            {"provider": "second"},
                        ],
                        fallback_on_failure=False,
                    )
                }
            )
            result = await router.deliver(mock_result, {"title": "Test"})

            # Should fail because fallback is disabled
            assert result is False

    @pytest.mark.asyncio
    async def test_deliver_require_all_success(
        self, mock_result: MockInterestResultForRouting
    ) -> None:
        """require_all=True should need all destinations to succeed."""
        provider_one = MockDeliveryProvider(deliver_result=True)
        provider_two = MockDeliveryProvider(deliver_result=True)

        with patch(
            "aria_esi.services.redisq.interest_v2.providers.registry.get_provider_registry"
        ) as mock_registry_fn:
            mock_registry = MagicMock()
            mock_registry.get_delivery.side_effect = [provider_one, provider_two]
            mock_registry_fn.return_value = mock_registry

            router = DeliveryRouter(
                {
                    "notify": TierRouting(
                        tier="notify",
                        destinations=[
                            {"provider": "first"},
                            {"provider": "second"},
                        ],
                        require_all=True,
                    )
                }
            )
            result = await router.deliver(mock_result, {"title": "Test"})

            assert result is True

    @pytest.mark.asyncio
    async def test_deliver_require_all_partial_failure(
        self, mock_result: MockInterestResultForRouting
    ) -> None:
        """require_all=True should fail if any destination fails."""
        provider_one = MockDeliveryProvider(deliver_result=True)
        provider_two = MockDeliveryProvider(deliver_result=False)

        with patch(
            "aria_esi.services.redisq.interest_v2.providers.registry.get_provider_registry"
        ) as mock_registry_fn:
            mock_registry = MagicMock()
            mock_registry.get_delivery.side_effect = [provider_one, provider_two]
            mock_registry_fn.return_value = mock_registry

            router = DeliveryRouter(
                {
                    "notify": TierRouting(
                        tier="notify",
                        destinations=[
                            {"provider": "first"},
                            {"provider": "second"},
                        ],
                        require_all=True,
                    )
                }
            )
            result = await router.deliver(mock_result, {"title": "Test"})

            assert result is False

    @pytest.mark.asyncio
    async def test_deliver_unknown_provider(
        self, mock_result: MockInterestResultForRouting
    ) -> None:
        """Unknown provider should be skipped with fallback."""
        success_provider = MockDeliveryProvider(deliver_result=True)

        with patch(
            "aria_esi.services.redisq.interest_v2.providers.registry.get_provider_registry"
        ) as mock_registry_fn:
            mock_registry = MagicMock()
            # First provider unknown (None), second works
            mock_registry.get_delivery.side_effect = [None, success_provider]
            mock_registry_fn.return_value = mock_registry

            router = DeliveryRouter(
                {
                    "notify": TierRouting(
                        tier="notify",
                        destinations=[
                            {"provider": "unknown"},
                            {"provider": "fallback"},
                        ],
                        fallback_on_failure=True,
                    )
                }
            )
            result = await router.deliver(mock_result, {"title": "Test"})

            assert result is True

    @pytest.mark.asyncio
    async def test_deliver_provider_exception(
        self, mock_result: MockInterestResultForRouting
    ) -> None:
        """Provider exceptions should be caught and logged."""
        raising_provider = MockDeliveryProvider(should_raise=True)
        success_provider = MockDeliveryProvider(deliver_result=True)

        with patch(
            "aria_esi.services.redisq.interest_v2.providers.registry.get_provider_registry"
        ) as mock_registry_fn:
            mock_registry = MagicMock()
            mock_registry.get_delivery.side_effect = [raising_provider, success_provider]
            mock_registry_fn.return_value = mock_registry

            router = DeliveryRouter(
                {
                    "notify": TierRouting(
                        tier="notify",
                        destinations=[
                            {"provider": "raises"},
                            {"provider": "fallback"},
                        ],
                        fallback_on_failure=True,
                    )
                }
            )
            result = await router.deliver(mock_result, {"title": "Test"})

            assert result is True

    def test_get_routing_for_tier(self) -> None:
        """get_routing_for_tier should return routing or None."""
        routing = TierRouting(tier="notify", destinations=[{"provider": "log"}])
        router = DeliveryRouter({"notify": routing})

        assert router.get_routing_for_tier("notify") == routing
        assert router.get_routing_for_tier("nonexistent") is None

    def test_add_routing(self) -> None:
        """add_routing should add or update tier routing."""
        router = DeliveryRouter()
        assert router.list_configured_tiers() == []

        routing = TierRouting(tier="priority", destinations=[{"provider": "discord"}])
        router.add_routing(routing)

        assert "priority" in router.list_configured_tiers()
        assert router.get_routing_for_tier("priority") == routing

    def test_list_configured_tiers(self) -> None:
        """list_configured_tiers should return all configured tier names."""
        router = DeliveryRouter(
            {
                "priority": TierRouting(tier="priority"),
                "notify": TierRouting(tier="notify"),
                "digest": TierRouting(tier="digest"),
            }
        )

        tiers = router.list_configured_tiers()
        assert len(tiers) == 3
        assert "priority" in tiers
        assert "notify" in tiers
        assert "digest" in tiers


# =============================================================================
# Test create_default_router
# =============================================================================


class TestCreateDefaultRouter:
    """Tests for create_default_router function."""

    def test_creates_all_tiers(self) -> None:
        """Should create routing for all standard tiers."""
        router = create_default_router()

        tiers = router.list_configured_tiers()
        assert "priority" in tiers
        assert "notify" in tiers
        assert "digest" in tiers
        assert "log_only" in tiers

    def test_all_tiers_use_log_provider(self) -> None:
        """All default tiers should use log provider."""
        router = create_default_router()

        for tier in ["priority", "notify", "digest", "log_only"]:
            routing = router.get_routing_for_tier(tier)
            assert routing is not None
            assert len(routing.destinations) == 1
            assert routing.destinations[0]["provider"] == "log"

    def test_returns_delivery_router(self) -> None:
        """Should return a DeliveryRouter instance."""
        router = create_default_router()
        assert isinstance(router, DeliveryRouter)


# =============================================================================
# Integration Tests
# =============================================================================


class TestDeliveryRouterIntegration:
    """Integration tests for delivery routing with real provider registry."""

    @pytest.fixture
    def reset_registry(self):
        """Reset the global provider registry before/after test."""
        from aria_esi.services.redisq.interest_v2.providers.registry import (
            reset_registry,
        )

        reset_registry()
        yield
        reset_registry()

    @pytest.mark.asyncio
    async def test_deliver_with_log_provider(
        self, reset_registry, caplog
    ) -> None:
        """Should successfully deliver with real log provider."""
        import logging

        result = MockInterestResultForRouting(tier=NotificationTier.NOTIFY)
        router = create_default_router()

        with caplog.at_level(logging.INFO):
            success = await router.deliver(result, {"title": "Integration Test"})

        assert success is True
        assert "[NOTIFY]" in caplog.text

    @pytest.mark.asyncio
    async def test_multiple_tiers_have_correct_routing(
        self, reset_registry
    ) -> None:
        """Each tier should have its routing correctly configured."""
        router = create_default_router()

        for tier_name in ["priority", "notify", "digest", "log_only"]:
            routing = router.get_routing_for_tier(tier_name)
            assert routing is not None
            assert routing.tier == tier_name
