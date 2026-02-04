"""
Notification Profile Data Model.

A NotificationProfile is a self-contained notification configuration that can be
loaded from YAML files. Each profile has its own webhook, topology filter,
triggers, throttle settings, and quiet hours.

Multiple profiles can run in parallel, allowing different Discord channels
to receive different types of intel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .config import CommentaryConfig, QuietHoursConfig, TriggerConfig

if TYPE_CHECKING:
    from ..interest import InterestCalculator
    from ..interest_v2 import InterestEngineV2
    from .throttle import ThrottleManager

# Current schema version for profile YAML files
# v2 = store-based polling, v3 = interest engine v2
SCHEMA_VERSION = 3


@dataclass
class PollingConfig:
    """Configuration for worker polling behavior."""

    interval_seconds: float = 5.0  # How often to poll the store
    batch_size: int = 50  # Max kills per poll iteration
    overlap_window_seconds: int = 60  # Look back window for duplicate safety

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PollingConfig:
        """Create from dictionary."""
        if not data:
            return cls()
        return cls(
            interval_seconds=data.get("interval_seconds", 5.0),
            batch_size=data.get("batch_size", 50),
            overlap_window_seconds=data.get("overlap_window_seconds", 60),
        )


@dataclass
class RateLimitStrategy:
    """Configuration for handling Discord rate limits."""

    rollup_threshold: int = 10  # Pending kills to trigger rollup
    max_rollup_kills: int = 20  # Max kills in a single rollup message
    backoff_seconds: float = 30.0  # Backoff time on rate limit

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RateLimitStrategy:
        """Create from dictionary."""
        if not data:
            return cls()
        return cls(
            rollup_threshold=data.get("rollup_threshold", 10),
            max_rollup_kills=data.get("max_rollup_kills", 20),
            backoff_seconds=data.get("backoff_seconds", 30.0),
        )


@dataclass
class DeliveryConfig:
    """Configuration for message delivery retry behavior."""

    max_attempts: int = 3  # Max delivery attempts before marking failed
    retry_delay_seconds: float = 5.0  # Delay between retries

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DeliveryConfig:
        """Create from dictionary."""
        if not data:
            return cls()
        return cls(
            max_attempts=data.get("max_attempts", 3),
            retry_delay_seconds=data.get("retry_delay_seconds", 5.0),
        )


@dataclass
class NotificationProfile:
    """
    A self-contained notification configuration.

    Profiles are loaded from YAML files in userdata/notifications/.
    Each profile operates independently with its own:
    - Discord webhook
    - Topology filter (which systems to monitor)
    - Trigger configuration (what events to notify on)
    - Throttle settings (per-profile rate limiting)
    - Quiet hours (per-profile suppression windows)

    Runtime state (_topology_filter, _throttle) is initialized by the
    ProfileEvaluator and not persisted to YAML.
    """

    # Identity
    name: str  # Unique identifier (filename stem, e.g., "market-hubs")
    display_name: str = ""  # Human-readable name for display

    # Enable/disable without deleting
    enabled: bool = True

    # Discord webhook URL for this profile
    webhook_url: str = ""

    # Topology configuration (same structure as context_topology in config.json)
    # Contains: geographic, routes, entity, etc.
    topology: dict[str, Any] = field(default_factory=dict)

    # Trigger configuration
    triggers: TriggerConfig = field(default_factory=TriggerConfig)

    # Per-profile throttle (minutes between notifications for same system/trigger)
    throttle_minutes: int = 5

    # Per-profile quiet hours
    quiet_hours: QuietHoursConfig = field(default_factory=QuietHoursConfig)

    # Optional commentary configuration (overrides global if set)
    commentary: CommentaryConfig | None = None

    # Schema version for forward compatibility
    schema_version: int = SCHEMA_VERSION

    # Optional description for templates
    description: str = ""

    # v2 fields: Store-based polling configuration
    polling: PollingConfig = field(default_factory=PollingConfig)
    rate_limit_strategy: RateLimitStrategy = field(default_factory=RateLimitStrategy)
    delivery: DeliveryConfig = field(default_factory=DeliveryConfig)

    # v3 field: Interest Engine v2 configuration
    # Contains: engine, preset, customize, weights, signals, rules, thresholds, prefetch
    # See interest_v2/config.py for InterestConfigV2 structure
    interest: dict[str, Any] = field(default_factory=dict)

    # Runtime state (not persisted to YAML)
    _topology_filter: InterestCalculator | None = field(default=None, repr=False)
    _throttle: ThrottleManager | None = field(default=None, repr=False)
    _interest_engine_v2: InterestEngineV2 | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Set defaults after initialization."""
        if not self.display_name:
            # Convert name to title case: "market-hubs" -> "Market Hubs"
            self.display_name = self.name.replace("-", " ").replace("_", " ").title()

    @property
    def has_topology(self) -> bool:
        """Check if profile has topology configuration."""
        if not self.topology:
            return False
        # Check for geographic systems (most common)
        geographic = self.topology.get("geographic", {})
        if geographic.get("systems"):
            return True
        # Check for routes
        if self.topology.get("routes"):
            return True
        # Check for entity watching
        if self.topology.get("entity"):
            return True
        return False

    @property
    def system_count(self) -> int:
        """Get approximate count of systems in topology."""
        count = 0
        geographic = self.topology.get("geographic", {})
        systems = geographic.get("systems", [])
        count += len(systems)
        return count

    @classmethod
    def from_dict(cls, data: dict[str, Any], name: str | None = None) -> NotificationProfile:
        """
        Create a NotificationProfile from a dictionary.

        Args:
            data: Dictionary from parsed YAML
            name: Profile name (overrides data["name"] if provided)

        Returns:
            NotificationProfile instance
        """
        profile_name = name or data.get("name", "unnamed")

        # Parse triggers
        triggers_data = data.get("triggers")
        triggers = TriggerConfig.from_dict(triggers_data) if triggers_data else TriggerConfig()

        # Parse quiet hours
        quiet_hours_data = data.get("quiet_hours")
        quiet_hours = (
            QuietHoursConfig.from_dict(quiet_hours_data) if quiet_hours_data else QuietHoursConfig()
        )

        # Parse commentary (optional)
        commentary_data = data.get("commentary")
        commentary = CommentaryConfig.from_dict(commentary_data) if commentary_data else None

        # Parse v2 polling configuration
        polling = PollingConfig.from_dict(data.get("polling"))
        rate_limit_strategy = RateLimitStrategy.from_dict(data.get("rate_limit_strategy"))
        delivery = DeliveryConfig.from_dict(data.get("delivery"))

        return cls(
            name=profile_name,
            display_name=data.get("display_name", ""),
            enabled=data.get("enabled", True),
            webhook_url=data.get("webhook_url", ""),
            topology=data.get("topology", {}),
            triggers=triggers,
            throttle_minutes=data.get("throttle_minutes", 5),
            quiet_hours=quiet_hours,
            commentary=commentary,
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            description=data.get("description", ""),
            polling=polling,
            rate_limit_strategy=rate_limit_strategy,
            delivery=delivery,
            interest=data.get("interest", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for YAML serialization.

        Returns:
            Dictionary suitable for YAML output
        """
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "name": self.name,
            "display_name": self.display_name,
            "enabled": self.enabled,
            "webhook_url": self.webhook_url,
        }

        # Add description if present (useful for templates)
        if self.description:
            result["description"] = self.description

        # Add topology if configured
        if self.topology:
            result["topology"] = self.topology

        # Add triggers
        triggers_dict: dict[str, Any] = {
            "watchlist_activity": self.triggers.watchlist_activity,
            "gatecamp_detected": self.triggers.gatecamp_detected,
            "high_value_threshold": self.triggers.high_value_threshold,
        }

        # Add war activity triggers if enabled
        if self.triggers.war_activity:
            triggers_dict["war_activity"] = self.triggers.war_activity
            triggers_dict["war_suppress_gatecamp"] = self.triggers.war_suppress_gatecamp

        # Add NPC faction kill config if enabled
        if self.triggers.npc_faction_kill.enabled:
            triggers_dict["npc_faction_kill"] = self.triggers.npc_faction_kill.to_dict()

        # Add political entity config if enabled
        if self.triggers.political_entity.enabled:
            triggers_dict["political_entity"] = self.triggers.political_entity.to_dict()

        result["triggers"] = triggers_dict

        # Add throttle
        result["throttle_minutes"] = self.throttle_minutes

        # Add quiet hours if enabled
        if self.quiet_hours.enabled:
            result["quiet_hours"] = {
                "enabled": self.quiet_hours.enabled,
                "start": self.quiet_hours.start,
                "end": self.quiet_hours.end,
                "timezone": self.quiet_hours.timezone,
            }

        # Add commentary if configured
        if self.commentary and self.commentary.enabled:
            commentary_dict: dict[str, Any] = {
                "enabled": self.commentary.enabled,
                "model": self.commentary.model,
                "timeout_ms": self.commentary.timeout_ms,
                "max_tokens": self.commentary.max_tokens,
                "warrant_threshold": self.commentary.warrant_threshold,
                "cost_limit_daily_usd": self.commentary.cost_limit_daily_usd,
            }
            # Include optional fields if specified
            if self.commentary.persona:
                commentary_dict["persona"] = self.commentary.persona
            if self.commentary.style:
                commentary_dict["style"] = self.commentary.style
            if self.commentary.max_chars != 200:  # Only include if non-default
                commentary_dict["max_chars"] = self.commentary.max_chars
            result["commentary"] = commentary_dict

        # Add v2 polling configuration (only if non-default values)
        if self.schema_version >= 2:
            result["polling"] = {
                "interval_seconds": self.polling.interval_seconds,
                "batch_size": self.polling.batch_size,
                "overlap_window_seconds": self.polling.overlap_window_seconds,
            }
            result["rate_limit_strategy"] = {
                "rollup_threshold": self.rate_limit_strategy.rollup_threshold,
                "max_rollup_kills": self.rate_limit_strategy.max_rollup_kills,
                "backoff_seconds": self.rate_limit_strategy.backoff_seconds,
            }
            result["delivery"] = {
                "max_attempts": self.delivery.max_attempts,
                "retry_delay_seconds": self.delivery.retry_delay_seconds,
            }

        # Add interest configuration if present (v3)
        if self.interest:
            result["interest"] = self.interest

        return result

    def validate(self) -> list[str]:
        """
        Validate the profile configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        # Name validation
        if not self.name:
            errors.append("Profile name is required")
        elif not self.name.replace("-", "").replace("_", "").isalnum():
            errors.append("Profile name must be alphanumeric with hyphens/underscores only")

        # Webhook validation
        if not self.webhook_url:
            errors.append("Webhook URL is required")
        elif not self.webhook_url.startswith("https://discord.com/api/webhooks/"):
            errors.append("Webhook URL must be a Discord webhook URL")

        # Throttle validation
        if self.throttle_minutes < 0:
            errors.append("throttle_minutes must be non-negative")
        if self.throttle_minutes > 60:
            errors.append("throttle_minutes should not exceed 60")

        # Schema version validation
        if self.schema_version > SCHEMA_VERSION:
            errors.append(
                f"Profile schema version {self.schema_version} is newer than "
                f"supported version {SCHEMA_VERSION}"
            )

        # Validate triggers
        if self.triggers.high_value_threshold < 0:
            errors.append("high_value_threshold must be non-negative")

        # Validate quiet hours time format
        if self.quiet_hours.enabled:
            for time_field, time_value in [
                ("start", self.quiet_hours.start),
                ("end", self.quiet_hours.end),
            ]:
                if not _is_valid_time_format(time_value):
                    errors.append(f"quiet_hours.{time_field} must be in HH:MM format")

        # Validate commentary if present
        if self.commentary:
            commentary_errors = self.commentary.validate()
            for err in commentary_errors:
                errors.append(f"commentary: {err}")

        # Validate NPC faction kill config if enabled
        if self.triggers.npc_faction_kill.enabled:
            from .npc_factions import get_npc_faction_mapper

            mapper = get_npc_faction_mapper()
            valid_factions = mapper.get_all_faction_keys() if mapper.is_loaded else None
            npc_errors = self.triggers.npc_faction_kill.validate(valid_factions)
            for err in npc_errors:
                errors.append(f"triggers: {err}")

        # Validate political entity config if enabled
        if self.triggers.political_entity.enabled:
            political_errors = self.triggers.political_entity.validate()
            for err in political_errors:
                errors.append(f"triggers: {err}")

        # Validate interest configuration if present (v3)
        if self.interest:
            interest_errors = self._validate_interest()
            for err in interest_errors:
                errors.append(f"interest: {err}")

        return errors

    def _validate_interest(self) -> list[str]:
        """
        Validate interest engine v2 configuration.

        Returns:
            List of validation error messages
        """
        if not self.interest:
            return []

        try:
            from ..interest_v2.config import InterestConfigV2

            config = InterestConfigV2.from_dict(self.interest)
            return config.validate()
        except Exception as e:
            return [f"Failed to parse interest config: {e}"]

    @property
    def uses_interest_v2(self) -> bool:
        """Check if this profile uses Interest Engine v2."""
        if not self.interest:
            return False
        return self.interest.get("engine") == "v2"

    @property
    def interest_engine(self) -> str:
        """Get the interest engine version for this profile."""
        if not self.interest:
            return "v1"
        return self.interest.get("engine", "v1")

    def mask_webhook_url(self) -> str:
        """
        Return masked webhook URL for display.

        Returns:
            Masked URL showing only first/last parts
        """
        if not self.webhook_url:
            return "(not configured)"

        # Discord webhook format: https://discord.com/api/webhooks/{id}/{token}
        if "/webhooks/" in self.webhook_url:
            parts = self.webhook_url.split("/webhooks/")
            if len(parts) == 2:
                webhook_parts = parts[1].split("/")
                if len(webhook_parts) >= 2:
                    webhook_id = webhook_parts[0]
                    token = webhook_parts[1]
                    masked_token = token[:4] + "..." + token[-4:] if len(token) > 8 else "..."
                    return f"...webhooks/{webhook_id}/{masked_token}"

        # Fallback: show first and last 10 chars
        if len(self.webhook_url) > 24:
            return self.webhook_url[:10] + "..." + self.webhook_url[-10:]
        return self.webhook_url


def _is_valid_time_format(time_str: str) -> bool:
    """
    Check if a string is in HH:MM format.

    Args:
        time_str: Time string to validate

    Returns:
        True if valid HH:MM format
    """
    if not time_str or len(time_str) != 5:
        return False
    if time_str[2] != ":":
        return False
    try:
        hours = int(time_str[:2])
        minutes = int(time_str[3:])
        return 0 <= hours <= 23 and 0 <= minutes <= 59
    except ValueError:
        return False
