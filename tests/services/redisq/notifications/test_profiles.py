"""
Tests for notification profiles.
"""

from __future__ import annotations

from aria_esi.services.redisq.notifications.config import QuietHoursConfig, TriggerConfig
from aria_esi.services.redisq.notifications.profiles import SCHEMA_VERSION, NotificationProfile


class TestNotificationProfile:
    """Tests for NotificationProfile dataclass."""

    def test_create_minimal(self):
        """Create profile with minimal required fields."""
        profile = NotificationProfile(name="test-profile")

        assert profile.name == "test-profile"
        assert profile.display_name == "Test Profile"  # Auto-generated
        assert profile.enabled is True
        assert profile.webhook_url == ""
        assert profile.topology == {}
        assert profile.schema_version == SCHEMA_VERSION

    def test_create_full(self):
        """Create profile with all fields."""
        profile = NotificationProfile(
            name="market-intel",
            display_name="Market Intel Channel",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            topology={
                "geographic": {
                    "systems": [
                        {"name": "Jita", "classification": "hunting"},
                        {"name": "Perimeter", "classification": "transit"},
                    ]
                }
            },
            triggers=TriggerConfig(
                watchlist_activity=True,
                gatecamp_detected=True,
                high_value_threshold=500_000_000,
            ),
            throttle_minutes=2,
            quiet_hours=QuietHoursConfig(enabled=False),
            description="Test profile",
        )

        assert profile.name == "market-intel"
        assert profile.display_name == "Market Intel Channel"
        assert profile.has_topology is True
        assert profile.system_count == 2

    def test_display_name_auto_generated(self):
        """Display name is auto-generated from name if not provided."""
        profile = NotificationProfile(name="my-test-profile")
        assert profile.display_name == "My Test Profile"

        profile2 = NotificationProfile(name="gank_pipes")
        assert profile2.display_name == "Gank Pipes"

    def test_has_topology_empty(self):
        """has_topology is False for empty topology."""
        profile = NotificationProfile(name="test", topology={})
        assert profile.has_topology is False

        profile2 = NotificationProfile(name="test", topology={"geographic": {}})
        assert profile2.has_topology is False

    def test_has_topology_with_systems(self):
        """has_topology is True when systems are configured."""
        profile = NotificationProfile(
            name="test",
            topology={"geographic": {"systems": [{"name": "Jita"}]}},
        )
        assert profile.has_topology is True

    def test_has_topology_with_routes(self):
        """has_topology is True when routes are configured."""
        profile = NotificationProfile(
            name="test",
            topology={"routes": [{"origin": "Jita", "destination": "Amarr"}]},
        )
        assert profile.has_topology is True

    def test_system_count(self):
        """system_count returns correct count."""
        profile = NotificationProfile(
            name="test",
            topology={
                "geographic": {
                    "systems": [
                        {"name": "Jita"},
                        {"name": "Perimeter"},
                        {"name": "Dodixie"},
                    ]
                }
            },
        )
        assert profile.system_count == 3


class TestNotificationProfileSerialization:
    """Tests for profile serialization/deserialization."""

    def test_from_dict_minimal(self):
        """Create profile from minimal dict."""
        data = {
            "name": "test-profile",
        }
        profile = NotificationProfile.from_dict(data)

        assert profile.name == "test-profile"
        assert profile.enabled is True
        assert profile.throttle_minutes == 5

    def test_from_dict_full(self):
        """Create profile from full dict."""
        data = {
            "schema_version": 1,
            "name": "market-hubs",
            "display_name": "Market Hub Intel",
            "enabled": True,
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
            "description": "Trade hub monitoring",
            "topology": {
                "geographic": {"systems": [{"name": "Jita", "classification": "hunting"}]}
            },
            "triggers": {
                "watchlist_activity": True,
                "gatecamp_detected": False,
                "high_value_threshold": 500_000_000,
            },
            "throttle_minutes": 2,
            "quiet_hours": {
                "enabled": True,
                "start": "02:00",
                "end": "08:00",
                "timezone": "UTC",
            },
        }
        profile = NotificationProfile.from_dict(data)

        assert profile.name == "market-hubs"
        assert profile.display_name == "Market Hub Intel"
        assert profile.description == "Trade hub monitoring"
        assert profile.triggers.high_value_threshold == 500_000_000
        assert profile.throttle_minutes == 2
        assert profile.quiet_hours.enabled is True
        assert profile.quiet_hours.timezone == "UTC"

    def test_from_dict_name_override(self):
        """Name parameter overrides dict name."""
        data = {"name": "original"}
        profile = NotificationProfile.from_dict(data, name="override")
        assert profile.name == "override"

    def test_to_dict(self):
        """Profile converts to dict correctly."""
        profile = NotificationProfile(
            name="test-profile",
            display_name="Test Profile",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            topology={"geographic": {"systems": [{"name": "Jita"}]}},
            throttle_minutes=3,
        )
        data = profile.to_dict()

        assert data["name"] == "test-profile"
        assert data["display_name"] == "Test Profile"
        assert data["enabled"] is True
        assert data["webhook_url"] == "https://discord.com/api/webhooks/123/abc"
        assert data["throttle_minutes"] == 3
        assert data["topology"] == {"geographic": {"systems": [{"name": "Jita"}]}}

    def test_roundtrip(self):
        """Profile survives dict roundtrip."""
        original = NotificationProfile(
            name="roundtrip-test",
            display_name="Roundtrip Test",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            topology={"geographic": {"systems": [{"name": "Jita"}]}},
            throttle_minutes=5,
        )
        data = original.to_dict()
        restored = NotificationProfile.from_dict(data)

        assert restored.name == original.name
        assert restored.display_name == original.display_name
        assert restored.enabled == original.enabled
        assert restored.webhook_url == original.webhook_url
        assert restored.throttle_minutes == original.throttle_minutes

    def test_commentary_style_roundtrip(self):
        """Commentary style and max_chars survive to_dict/from_dict cycle."""
        from aria_esi.services.redisq.notifications.config import CommentaryConfig

        original = NotificationProfile(
            name="style-test",
            display_name="Style Test",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            commentary=CommentaryConfig(
                enabled=True,
                style="radio",
                max_chars=150,
                persona="paria",
            ),
        )
        data = original.to_dict()

        # Verify fields are in serialized data
        assert data["commentary"]["style"] == "radio"
        assert data["commentary"]["max_chars"] == 150
        assert data["commentary"]["persona"] == "paria"

        # Verify round-trip
        restored = NotificationProfile.from_dict(data)
        assert restored.commentary is not None
        assert restored.commentary.style == "radio"
        assert restored.commentary.max_chars == 150
        assert restored.commentary.persona == "paria"

    def test_commentary_default_max_chars_not_serialized(self):
        """Default max_chars (200) is not serialized to keep YAML clean."""
        from aria_esi.services.redisq.notifications.config import CommentaryConfig

        profile = NotificationProfile(
            name="default-test",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            commentary=CommentaryConfig(
                enabled=True,
                style="radio",
                max_chars=200,  # Default value
            ),
        )
        data = profile.to_dict()

        # max_chars should not be in output when it's the default
        assert "max_chars" not in data["commentary"]
        # style should be present
        assert data["commentary"]["style"] == "radio"


class TestNotificationProfileValidation:
    """Tests for profile validation."""

    def test_validate_valid_profile(self):
        """Valid profile has no errors."""
        profile = NotificationProfile(
            name="valid-profile",
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )
        errors = profile.validate()
        assert errors == []

    def test_validate_missing_name(self):
        """Missing name is an error."""
        profile = NotificationProfile(
            name="",
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )
        errors = profile.validate()
        assert any("name is required" in e for e in errors)

    def test_validate_invalid_name_chars(self):
        """Invalid characters in name is an error."""
        profile = NotificationProfile(
            name="invalid name!",
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )
        errors = profile.validate()
        assert any("alphanumeric" in e for e in errors)

    def test_validate_valid_name_formats(self):
        """Valid name formats pass validation."""
        valid_names = ["test", "test-profile", "test_profile", "test-123"]
        for name in valid_names:
            profile = NotificationProfile(
                name=name,
                webhook_url="https://discord.com/api/webhooks/123/abc",
            )
            errors = profile.validate()
            name_errors = [e for e in errors if "name" in e.lower()]
            assert name_errors == [], f"Name '{name}' should be valid but got: {name_errors}"

    def test_validate_missing_webhook(self):
        """Missing webhook URL is an error."""
        profile = NotificationProfile(name="test")
        errors = profile.validate()
        assert any("Webhook URL is required" in e for e in errors)

    def test_validate_invalid_webhook(self):
        """Invalid webhook URL is an error."""
        profile = NotificationProfile(
            name="test",
            webhook_url="https://example.com/not-a-webhook",
        )
        errors = profile.validate()
        assert any("Discord webhook URL" in e for e in errors)

    def test_validate_negative_throttle(self):
        """Negative throttle is an error."""
        profile = NotificationProfile(
            name="test",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            throttle_minutes=-1,
        )
        errors = profile.validate()
        assert any("non-negative" in e for e in errors)

    def test_validate_excessive_throttle(self):
        """Excessive throttle is an error."""
        profile = NotificationProfile(
            name="test",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            throttle_minutes=120,
        )
        errors = profile.validate()
        assert any("exceed 60" in e for e in errors)

    def test_validate_negative_threshold(self):
        """Negative high_value_threshold is an error."""
        profile = NotificationProfile(
            name="test",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            triggers=TriggerConfig(high_value_threshold=-100),
        )
        errors = profile.validate()
        assert any("non-negative" in e for e in errors)


class TestNotificationProfileMasking:
    """Tests for webhook URL masking."""

    def test_mask_webhook_url_standard(self):
        """Standard webhook URL is masked correctly."""
        profile = NotificationProfile(
            name="test",
            webhook_url="https://discord.com/api/webhooks/1234567890/abcdefghijklmnopqrstuvwxyz",
        )
        masked = profile.mask_webhook_url()
        assert "1234567890" in masked
        assert "abcd" in masked
        assert "wxyz" in masked
        assert "mnop" not in masked

    def test_mask_webhook_url_empty(self):
        """Empty webhook URL shows not configured."""
        profile = NotificationProfile(name="test", webhook_url="")
        masked = profile.mask_webhook_url()
        assert "not configured" in masked

    def test_mask_webhook_url_short_token(self):
        """Short token is fully masked."""
        profile = NotificationProfile(
            name="test",
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )
        masked = profile.mask_webhook_url()
        assert "..." in masked


class TestNotificationProfileInterest:
    """Tests for Interest Engine v2 related properties."""

    def test_uses_interest_v2_true(self):
        """uses_interest_v2 is True when engine is v2."""
        profile = NotificationProfile(
            name="v2-profile",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={"engine": "v2", "preset": "lowsec-pvp"},
        )
        assert profile.uses_interest_v2 is True

    def test_uses_interest_v2_false_no_interest(self):
        """uses_interest_v2 is False when no interest config."""
        profile = NotificationProfile(
            name="no-interest",
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )
        assert profile.uses_interest_v2 is False

    def test_uses_interest_v2_false_v1_engine(self):
        """uses_interest_v2 is False when engine is v1."""
        profile = NotificationProfile(
            name="v1-profile",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={"engine": "v1"},
        )
        assert profile.uses_interest_v2 is False

    def test_uses_interest_v2_false_no_engine_key(self):
        """uses_interest_v2 is False when engine key is missing."""
        profile = NotificationProfile(
            name="no-engine",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={"preset": "lowsec-pvp"},  # No engine key
        )
        assert profile.uses_interest_v2 is False

    def test_interest_engine_v2(self):
        """interest_engine returns v2 when configured."""
        profile = NotificationProfile(
            name="v2-profile",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={"engine": "v2"},
        )
        assert profile.interest_engine == "v2"

    def test_interest_engine_v1_explicit(self):
        """interest_engine returns v1 when explicitly set."""
        profile = NotificationProfile(
            name="v1-profile",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={"engine": "v1"},
        )
        assert profile.interest_engine == "v1"

    def test_interest_engine_default(self):
        """interest_engine defaults to v1."""
        profile = NotificationProfile(
            name="default-profile",
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )
        assert profile.interest_engine == "v1"

    def test_interest_engine_missing_key(self):
        """interest_engine returns v1 when engine key is missing."""
        profile = NotificationProfile(
            name="missing-key",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={"preset": "something"},  # No engine key
        )
        assert profile.interest_engine == "v1"


class TestNotificationProfileInterestValidation:
    """Tests for interest configuration validation."""

    def test_validate_interest_valid(self):
        """Valid interest config passes validation."""
        profile = NotificationProfile(
            name="valid-interest",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={
                "engine": "v2",
                "preset": "lowsec-pvp",
            },
        )
        errors = profile.validate()
        # Should not have interest errors
        assert not any("interest" in e.lower() for e in errors)

    def test_validate_interest_empty(self):
        """Empty interest config is valid (uses v1 fallback)."""
        profile = NotificationProfile(
            name="empty-interest",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={},
        )
        errors = profile.validate()
        assert not any("interest" in e.lower() for e in errors)

    def test_interest_roundtrip(self):
        """Interest config survives to_dict/from_dict roundtrip."""
        original = NotificationProfile(
            name="interest-roundtrip",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={
                "engine": "v2",
                "preset": "lowsec-pvp",
                "customize": {
                    "weights": {"kill_value": 1.5},
                },
            },
        )

        data = original.to_dict()
        restored = NotificationProfile.from_dict(data)

        assert restored.interest == original.interest
        assert restored.uses_interest_v2 is True

    def test_interest_not_serialized_when_empty(self):
        """Empty interest config is still serialized for completeness."""
        profile = NotificationProfile(
            name="no-interest",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={},
        )
        data = profile.to_dict()
        # Empty dict is still present but empty
        assert "interest" not in data or data.get("interest") == {}


class TestNotificationProfileV2Fields:
    """Tests for v2 polling configuration fields."""

    def test_polling_config_defaults(self):
        """Polling config has sensible defaults."""
        from aria_esi.services.redisq.notifications.profiles import PollingConfig

        config = PollingConfig()
        assert config.interval_seconds == 5.0
        assert config.batch_size == 50
        assert config.overlap_window_seconds == 60

    def test_polling_config_from_dict(self):
        """Polling config parses from dict."""
        from aria_esi.services.redisq.notifications.profiles import PollingConfig

        data = {
            "interval_seconds": 10.0,
            "batch_size": 100,
            "overlap_window_seconds": 120,
        }
        config = PollingConfig.from_dict(data)

        assert config.interval_seconds == 10.0
        assert config.batch_size == 100
        assert config.overlap_window_seconds == 120

    def test_rate_limit_strategy_defaults(self):
        """Rate limit strategy has sensible defaults."""
        from aria_esi.services.redisq.notifications.profiles import RateLimitStrategy

        config = RateLimitStrategy()
        assert config.rollup_threshold == 10
        assert config.max_rollup_kills == 20
        assert config.backoff_seconds == 30.0

    def test_rate_limit_strategy_from_dict(self):
        """Rate limit strategy parses from dict."""
        from aria_esi.services.redisq.notifications.profiles import RateLimitStrategy

        data = {
            "rollup_threshold": 5,
            "max_rollup_kills": 10,
            "backoff_seconds": 60.0,
        }
        config = RateLimitStrategy.from_dict(data)

        assert config.rollup_threshold == 5
        assert config.max_rollup_kills == 10
        assert config.backoff_seconds == 60.0

    def test_delivery_config_defaults(self):
        """Delivery config has sensible defaults."""
        from aria_esi.services.redisq.notifications.profiles import DeliveryConfig

        config = DeliveryConfig()
        assert config.max_attempts == 3
        assert config.retry_delay_seconds == 5.0

    def test_profile_with_v2_fields(self):
        """Profile parses v2 fields correctly."""
        data = {
            "name": "v2-profile",
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
            "schema_version": 2,
            "polling": {
                "interval_seconds": 3.0,
                "batch_size": 25,
            },
            "rate_limit_strategy": {
                "rollup_threshold": 15,
            },
            "delivery": {
                "max_attempts": 5,
            },
        }
        profile = NotificationProfile.from_dict(data)

        assert profile.polling.interval_seconds == 3.0
        assert profile.polling.batch_size == 25
        assert profile.rate_limit_strategy.rollup_threshold == 15
        assert profile.delivery.max_attempts == 5

    def test_profile_v2_fields_roundtrip(self):
        """V2 fields survive roundtrip."""
        from aria_esi.services.redisq.notifications.profiles import (
            DeliveryConfig,
            PollingConfig,
            RateLimitStrategy,
        )

        original = NotificationProfile(
            name="roundtrip-v2",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            schema_version=2,
            polling=PollingConfig(
                interval_seconds=2.0,
                batch_size=30,
            ),
            rate_limit_strategy=RateLimitStrategy(
                rollup_threshold=8,
            ),
            delivery=DeliveryConfig(
                max_attempts=4,
            ),
        )

        data = original.to_dict()
        restored = NotificationProfile.from_dict(data)

        assert restored.polling.interval_seconds == 2.0
        assert restored.polling.batch_size == 30
        assert restored.rate_limit_strategy.rollup_threshold == 8
        assert restored.delivery.max_attempts == 4
