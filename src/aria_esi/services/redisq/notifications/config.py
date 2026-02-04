"""
Discord Notification Configuration.

Configuration models for trigger settings, quiet hours support, LLM commentary,
and topology configuration used by notification profiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import DEFAULT_MAX_CHARS

# =============================================================================
# Commentary Configuration
# =============================================================================


@dataclass
class CommentaryConfig:
    """
    Configuration for LLM-generated commentary on notifications.

    When enabled, interesting kill patterns (repeat attackers, gank rotations)
    trigger LLM-generated tactical commentary appended to notifications.
    """

    enabled: bool = False
    model: str = "claude-sonnet-4-5-20241022"
    timeout_ms: int = 3000
    max_tokens: int = 100
    warrant_threshold: float = 0.3
    cost_limit_daily_usd: float = 1.0
    persona: str | None = None  # Override persona (e.g., "paria-s" for Serpentis)
    style: str | None = None  # Commentary style: "conversational" or "radio"
    max_chars: int = DEFAULT_MAX_CHARS  # Soft upper bound for radio style

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CommentaryConfig:
        """Create from configuration dict."""
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", False),
            model=data.get("model", "claude-sonnet-4-5-20241022"),
            timeout_ms=data.get("timeout_ms", 3000),
            max_tokens=data.get("max_tokens", 100),
            warrant_threshold=data.get("warrant_threshold", 0.3),
            cost_limit_daily_usd=data.get("cost_limit_daily_usd", 1.0),
            persona=data.get("persona"),
            style=data.get("style"),
            max_chars=data.get("max_chars", DEFAULT_MAX_CHARS),
        )

    def validate(self) -> list[str]:
        """
        Validate commentary configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if self.timeout_ms < 500:
            errors.append("timeout_ms must be >= 500")
        if self.timeout_ms > 10000:
            errors.append("timeout_ms must be <= 10000 (10 seconds)")
        if self.warrant_threshold < 0 or self.warrant_threshold > 1:
            errors.append("warrant_threshold must be between 0 and 1")
        if self.cost_limit_daily_usd < 0:
            errors.append("cost_limit_daily_usd must be non-negative")

        # Validate persona if specified
        if self.persona:
            from .persona import VOICE_SUMMARIES

            if self.persona not in VOICE_SUMMARIES:
                valid = ", ".join(sorted(VOICE_SUMMARIES.keys()))
                errors.append(f"Unknown persona '{self.persona}'. Valid: {valid}")

        # Validate style
        if self.style and self.style not in ("conversational", "radio"):
            errors.append(f"Unknown style '{self.style}'. Valid: conversational, radio")

        # Validate max_chars
        if self.max_chars < 50 or self.max_chars > 500:
            errors.append("max_chars must be between 50 and 500")

        return errors


@dataclass
class QuietHoursConfig:
    """
    Quiet hours configuration for suppressing notifications.

    Uses zoneinfo-compatible timezone strings.
    """

    enabled: bool = False
    start: str = "02:00"  # HH:MM format
    end: str = "08:00"  # HH:MM format
    timezone: str = "America/New_York"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> QuietHoursConfig:
        """Create from configuration dict."""
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", False),
            start=data.get("start", "02:00"),
            end=data.get("end", "08:00"),
            timezone=data.get("timezone", "America/New_York"),
        )


@dataclass
class NPCFactionKillConfig:
    """
    Configuration for NPC faction kill trigger.

    Triggers notifications when NPC faction corporations (Serpentis, Angel Cartel, etc.)
    are involved in kills. Designed for RP immersion where faction-aligned pilots
    want "corporate intelligence briefings" about their faction's operations.
    """

    enabled: bool = False
    factions: list[str] = field(default_factory=list)  # ["serpentis", "angel_cartel"]
    as_attacker: bool = True  # Notify when NPC kills someone
    as_victim: bool = False  # Notify when someone kills the NPC
    ignore_topology: bool = True  # Default: cluster-wide (ignore profile topology)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> NPCFactionKillConfig:
        """Create from configuration dict."""
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", False),
            factions=data.get("factions", []),
            as_attacker=data.get("as_attacker", True),
            as_victim=data.get("as_victim", False),
            ignore_topology=data.get("ignore_topology", True),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "enabled": self.enabled,
            "factions": self.factions,
            "as_attacker": self.as_attacker,
            "as_victim": self.as_victim,
            "ignore_topology": self.ignore_topology,
        }

    def validate(self, valid_factions: list[str] | None = None) -> list[str]:
        """
        Validate NPC faction kill configuration.

        Args:
            valid_factions: Optional list of valid faction keys for validation

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if self.enabled and not self.factions:
            errors.append("npc_faction_kill.factions must not be empty when enabled")

        if self.enabled and not (self.as_attacker or self.as_victim):
            errors.append(
                "npc_faction_kill must have at least one of as_attacker or as_victim enabled"
            )

        # Validate faction names if reference list provided
        if valid_factions:
            for faction in self.factions:
                if faction.lower() not in [f.lower() for f in valid_factions]:
                    valid = ", ".join(sorted(valid_factions))
                    errors.append(
                        f"Unknown faction '{faction}' in npc_faction_kill.factions. "
                        f"Valid factions: {valid}"
                    )

        return errors


@dataclass
class PoliticalEntityKillConfig:
    """
    Configuration for political entity kill trigger.

    Triggers notifications when specific player corporations or alliances
    are involved in kills. Designed for tracking war targets, rivals,
    or entities of strategic interest.
    """

    enabled: bool = False
    corporations: list[int | str] = field(default_factory=list)  # Corp IDs or names
    alliances: list[int | str] = field(default_factory=list)  # Alliance IDs or names
    as_attacker: bool = True  # Notify when entity is attacking
    as_victim: bool = True  # Notify when entity is victim
    min_value: int = 0  # Minimum kill value to trigger

    # Resolved IDs (populated at load time if names were provided)
    _resolved_corp_ids: set[int] = field(default_factory=set, repr=False)
    _resolved_alliance_ids: set[int] = field(default_factory=set, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PoliticalEntityKillConfig:
        """Create from configuration dict."""
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", False),
            corporations=data.get("corporations", []),
            alliances=data.get("alliances", []),
            as_attacker=data.get("as_attacker", True),
            as_victim=data.get("as_victim", True),
            min_value=data.get("min_value", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "enabled": self.enabled,
            "corporations": self.corporations,
            "alliances": self.alliances,
            "as_attacker": self.as_attacker,
            "as_victim": self.as_victim,
            "min_value": self.min_value,
        }

    def validate(self) -> list[str]:
        """
        Validate political entity kill configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if self.enabled and not self.corporations and not self.alliances:
            errors.append(
                "political_entity: must have at least one corporation or alliance when enabled"
            )

        if self.enabled and not (self.as_attacker or self.as_victim):
            errors.append(
                "political_entity: must have at least one of as_attacker or as_victim enabled"
            )

        if self.min_value < 0:
            errors.append("political_entity.min_value must be non-negative")

        return errors

    @property
    def has_entities(self) -> bool:
        """Check if any entities are configured."""
        return bool(self.corporations or self.alliances)


@dataclass
class TriggerConfig:
    """
    Notification trigger configuration.

    Controls which events generate Discord notifications.
    """

    watchlist_activity: bool = True
    gatecamp_detected: bool = True
    high_value_threshold: int = 1_000_000_000  # 1B ISK

    # War engagement triggers
    war_activity: bool = False  # Opt-in: notify on war engagements
    war_suppress_gatecamp: bool = True  # Suppress gatecamp trigger for war kills

    # NPC faction kill trigger
    npc_faction_kill: NPCFactionKillConfig = field(default_factory=NPCFactionKillConfig)

    # Political entity kill trigger (player corps/alliances)
    political_entity: PoliticalEntityKillConfig = field(default_factory=PoliticalEntityKillConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TriggerConfig:
        """Create from configuration dict."""
        if not data:
            return cls()

        # Parse npc_faction_kill config
        npc_faction_data = data.get("npc_faction_kill")
        npc_faction_kill = (
            NPCFactionKillConfig.from_dict(npc_faction_data)
            if npc_faction_data
            else NPCFactionKillConfig()
        )

        # Parse political_entity config
        political_entity_data = data.get("political_entity")
        political_entity = (
            PoliticalEntityKillConfig.from_dict(political_entity_data)
            if political_entity_data
            else PoliticalEntityKillConfig()
        )

        return cls(
            watchlist_activity=data.get("watchlist_activity", True),
            gatecamp_detected=data.get("gatecamp_detected", True),
            high_value_threshold=data.get("high_value_threshold", 1_000_000_000),
            war_activity=data.get("war_activity", False),
            war_suppress_gatecamp=data.get("war_suppress_gatecamp", True),
            npc_faction_kill=npc_faction_kill,
            political_entity=political_entity,
        )


# =============================================================================
# Topology Configuration
# =============================================================================


@dataclass
class TopologyConfig:
    """
    Operational topology configuration for pre-filtering kills.

    When enabled, only kills in systems within the operational topology
    (operational systems + N-hop neighbors) are fetched from ESI.
    This significantly reduces API quota usage.
    """

    enabled: bool = False
    operational_systems: list[str] = field(default_factory=list)
    interest_weights: dict[str, float] = field(
        default_factory=lambda: {
            "operational": 1.0,
            "hop_1": 1.0,
            "hop_2": 0.7,
        }
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TopologyConfig:
        """Create from configuration dict."""
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", False),
            operational_systems=data.get("operational_systems", []),
            interest_weights=data.get(
                "interest_weights",
                {"operational": 1.0, "hop_1": 1.0, "hop_2": 0.7},
            ),
        )

    def validate(self) -> list[str]:
        """
        Validate topology configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if self.enabled and not self.operational_systems:
            errors.append("operational_systems must be non-empty when topology is enabled")

        # Validate weight keys
        valid_weights = {"operational", "hop_1", "hop_2"}
        for key in self.interest_weights:
            if key not in valid_weights:
                errors.append(f"Unknown interest weight key: {key}")

        # Validate weight values
        for key, value in self.interest_weights.items():
            if not isinstance(value, (int, float)) or value < 0 or value > 1:
                errors.append(f"Interest weight '{key}' must be between 0 and 1")

        return errors

    @classmethod
    def load(cls) -> TopologyConfig:
        """
        Load topology configuration from userdata/config.json.

        Returns:
            TopologyConfig instance (empty if not configured)
        """
        import json
        from pathlib import Path

        config_path = Path("userdata/config.json")
        if not config_path.exists():
            return cls()

        try:
            with open(config_path) as f:
                config = json.load(f)
            topology = config.get("redisq", {}).get("topology", {})
            return cls.from_dict(topology)
        except (json.JSONDecodeError, OSError):
            return cls()
