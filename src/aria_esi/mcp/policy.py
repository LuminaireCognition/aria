"""
MCP Tool Capability Policy Engine.

Provides capability gating for MCP tools to limit blast radius from prompt
injection attacks. Tools are classified by sensitivity level and can be
enabled/disabled via policy configuration.

Security finding: #5 from dev/reviews/SECURITY_000.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from ..core.config import get_settings
from ..core.logging import get_logger

if TYPE_CHECKING:
    from typing import Any

logger = get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Default policy file location
DEFAULT_POLICY_PATH = Path(__file__).parent.parent.parent.parent / "reference" / "mcp-policy.json"


# =============================================================================
# Sensitivity Levels
# =============================================================================


class SensitivityLevel(str, Enum):
    """Tool/action sensitivity classification."""

    PUBLIC = "public"  # Static data, no auth needed
    AGGREGATE = "aggregate"  # Aggregated data (activity stats)
    MARKET = "market"  # Market prices/orders
    AUTHENTICATED = "authenticated"  # Requires ESI auth
    RESTRICTED = "restricted"  # Personal data (wallet, assets)


# Default sensitivity for each dispatcher's actions
DEFAULT_ACTION_SENSITIVITY: dict[str, dict[str, SensitivityLevel]] = {
    "universe": {
        "route": SensitivityLevel.PUBLIC,
        "systems": SensitivityLevel.PUBLIC,
        "borders": SensitivityLevel.PUBLIC,
        "search": SensitivityLevel.PUBLIC,
        "loop": SensitivityLevel.PUBLIC,
        "analyze": SensitivityLevel.PUBLIC,
        "nearest": SensitivityLevel.PUBLIC,
        "optimize_waypoints": SensitivityLevel.PUBLIC,
        "activity": SensitivityLevel.AGGREGATE,
        "hotspots": SensitivityLevel.AGGREGATE,
        "gatecamp_risk": SensitivityLevel.AGGREGATE,
        "fw_frontlines": SensitivityLevel.AGGREGATE,
    },
    "market": {
        "prices": SensitivityLevel.MARKET,
        "orders": SensitivityLevel.MARKET,
        "valuation": SensitivityLevel.MARKET,
        "spread": SensitivityLevel.MARKET,
        "history": SensitivityLevel.MARKET,
        "find_nearby": SensitivityLevel.MARKET,
        "npc_sources": SensitivityLevel.PUBLIC,
        "arbitrage_scan": SensitivityLevel.MARKET,
        "arbitrage_detail": SensitivityLevel.MARKET,
        "route_value": SensitivityLevel.MARKET,
        "watchlist_create": SensitivityLevel.PUBLIC,
        "watchlist_add_item": SensitivityLevel.PUBLIC,
        "watchlist_list": SensitivityLevel.PUBLIC,
        "watchlist_get": SensitivityLevel.PUBLIC,
        "watchlist_delete": SensitivityLevel.PUBLIC,
        "scope_create": SensitivityLevel.PUBLIC,
        "scope_list": SensitivityLevel.PUBLIC,
        "scope_delete": SensitivityLevel.PUBLIC,
        "scope_refresh": SensitivityLevel.MARKET,
    },
    "sde": {
        "item_info": SensitivityLevel.PUBLIC,
        "blueprint_info": SensitivityLevel.PUBLIC,
        "search": SensitivityLevel.PUBLIC,
        "skill_requirements": SensitivityLevel.PUBLIC,
        "corporation_info": SensitivityLevel.PUBLIC,
        "agent_search": SensitivityLevel.PUBLIC,
        "agent_divisions": SensitivityLevel.PUBLIC,
        "cache_status": SensitivityLevel.PUBLIC,
    },
    "skills": {
        "training_time": SensitivityLevel.PUBLIC,
        "easy_80_plan": SensitivityLevel.PUBLIC,
        "get_multipliers": SensitivityLevel.PUBLIC,
        "get_breakpoints": SensitivityLevel.PUBLIC,
        "t2_requirements": SensitivityLevel.PUBLIC,
        "activity_plan": SensitivityLevel.PUBLIC,
        "activity_list": SensitivityLevel.PUBLIC,
        "activity_search": SensitivityLevel.PUBLIC,
        "activity_compare": SensitivityLevel.PUBLIC,
    },
    "fitting": {
        "calculate_stats": SensitivityLevel.PUBLIC,
        # Note: use_pilot_skills=True escalates to AUTHENTICATED
    },
    "status": {
        "_default": SensitivityLevel.PUBLIC,
    },
    "killmails": {
        # Killmail data is aggregated from public zKillboard data
        # Security: SECURITY_001.md Finding #5
        "query": SensitivityLevel.AGGREGATE,
        "stats": SensitivityLevel.AGGREGATE,
        "recent": SensitivityLevel.AGGREGATE,
    },
}


# =============================================================================
# Exceptions
# =============================================================================


class PolicyError(Exception):
    """Base exception for policy errors."""

    pass


class CapabilityDenied(PolicyError):
    """Raised when a tool/action is denied by policy."""

    def __init__(
        self,
        dispatcher: str,
        action: str,
        reason: str,
        sensitivity: SensitivityLevel | None = None,
    ):
        self.dispatcher = dispatcher
        self.action = action
        self.reason = reason
        self.sensitivity = sensitivity
        super().__init__(f"Capability denied: {dispatcher}.{action} - {reason}")


class ConfirmationRequired(PolicyError):
    """
    Raised when an action requires user confirmation before proceeding.

    This is distinct from CapabilityDenied - the action is not forbidden,
    but requires explicit user consent. Callers should catch this exception
    and prompt the user for confirmation.

    Security: This is a defense-in-depth measure against prompt injection.
    Even if an attacker injects a request for authenticated data, the user
    sees an explicit confirmation prompt before any data is accessed.
    """

    def __init__(
        self,
        dispatcher: str,
        action: str,
        sensitivity: SensitivityLevel,
        description: str | None = None,
    ):
        self.dispatcher = dispatcher
        self.action = action
        self.sensitivity = sensitivity
        self.description = description or self._default_description(sensitivity)
        super().__init__(
            f"Confirmation required for {dispatcher}.{action}: {self.description}"
        )

    @staticmethod
    def _default_description(sensitivity: SensitivityLevel) -> str:
        """Get default description for sensitivity level."""
        descriptions = {
            SensitivityLevel.AUTHENTICATED: "This action accesses your personal EVE data (wallet, skills, assets).",
            SensitivityLevel.RESTRICTED: "This action accesses sensitive personal data (contracts, mail).",
        }
        return descriptions.get(sensitivity, f"This action has {sensitivity.value} sensitivity.")


# =============================================================================
# Policy Configuration
# =============================================================================


@dataclass
class PolicyConfig:
    """Policy configuration loaded from file."""

    # Which sensitivity levels are allowed without confirmation
    allowed_levels: set[SensitivityLevel] = field(
        default_factory=lambda: {
            SensitivityLevel.PUBLIC,
            SensitivityLevel.AGGREGATE,
            SensitivityLevel.MARKET,
        }
    )

    # Sensitivity levels that require user confirmation before access
    # Actions at these levels will raise ConfirmationRequired instead of CapabilityDenied
    require_confirmation: set[SensitivityLevel] = field(default_factory=set)

    # Explicitly denied actions (dispatcher.action format)
    denied_actions: set[str] = field(default_factory=set)

    # Explicitly allowed actions (overrides sensitivity)
    allowed_actions: set[str] = field(default_factory=set)

    # Enable audit logging
    audit_logging: bool = True

    # Rate limit settings (calls per minute, 0 = unlimited)
    rate_limit_per_minute: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyConfig:
        """Create PolicyConfig from dictionary."""
        return cls(
            allowed_levels={
                SensitivityLevel(level)
                for level in data.get("allowed_levels", ["public", "aggregate", "market"])
            },
            require_confirmation={
                SensitivityLevel(level)
                for level in data.get("require_confirmation", [])
            },
            denied_actions=set(data.get("denied_actions", [])),
            allowed_actions=set(data.get("allowed_actions", [])),
            audit_logging=data.get("audit_logging", True),
            rate_limit_per_minute=data.get("rate_limit_per_minute", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "allowed_levels": sorted(level.value for level in self.allowed_levels),
            "require_confirmation": sorted(level.value for level in self.require_confirmation),
            "denied_actions": sorted(self.denied_actions),
            "allowed_actions": sorted(self.allowed_actions),
            "audit_logging": self.audit_logging,
            "rate_limit_per_minute": self.rate_limit_per_minute,
        }


# =============================================================================
# Policy Engine
# =============================================================================


class PolicyEngine:
    """
    Capability policy engine for MCP tools.

    Checks tool calls against policy configuration and logs access.
    """

    _instance: PolicyEngine | None = None

    def __init__(self, policy_path: Path | None = None):
        """
        Initialize the policy engine.

        Args:
            policy_path: Path to policy configuration file
        """
        self.policy_path = policy_path or self._get_policy_path()
        self.config = self._load_config()
        self._call_counts: dict[str, list[datetime]] = {}

    @classmethod
    def get_instance(cls) -> PolicyEngine:
        """Get singleton instance of policy engine."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None

    def _get_policy_path(self) -> Path:
        """Get policy file path from environment or default."""
        settings = get_settings()
        if settings.mcp_policy:
            return settings.mcp_policy
        return DEFAULT_POLICY_PATH

    def _load_config(self) -> PolicyConfig:
        """Load policy configuration from file."""
        if not self.policy_path.exists():
            logger.info("No policy file found at %s, using defaults", self.policy_path)
            return PolicyConfig()

        try:
            with open(self.policy_path, encoding="utf-8") as f:
                data = json.load(f)
            config = PolicyConfig.from_dict(data.get("policy", {}))
            logger.info("Loaded MCP policy from %s", self.policy_path)
            return config
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to load policy file: %s, using defaults", e)
            return PolicyConfig()

    def reload_config(self) -> None:
        """Reload policy configuration from file."""
        self.config = self._load_config()

    def is_bypass_enabled(self) -> bool:
        """Check if policy bypass is enabled via environment."""
        return get_settings().is_break_glass_enabled("policy")

    def get_action_sensitivity(
        self, dispatcher: str, action: str, context: dict[str, Any] | None = None
    ) -> SensitivityLevel:
        """
        Get the sensitivity level for a dispatcher action.

        Args:
            dispatcher: Dispatcher name (universe, market, etc.)
            action: Action name within the dispatcher
            context: Optional context for context-aware escalation

        Returns:
            SensitivityLevel for the action
        """
        # Context-aware escalation: fitting with pilot skills requires auth
        if dispatcher == "fitting" and action == "calculate_stats" and context:
            if context.get("use_pilot_skills"):
                return SensitivityLevel.AUTHENTICATED

        # Default lookup
        dispatcher_actions = DEFAULT_ACTION_SENSITIVITY.get(dispatcher, {})
        return dispatcher_actions.get(
            action, dispatcher_actions.get("_default", SensitivityLevel.PUBLIC)
        )

    def check_capability(
        self,
        dispatcher: str,
        action: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Check if a tool action is allowed by policy.

        Args:
            dispatcher: Dispatcher name (universe, market, etc.)
            action: Action name within the dispatcher
            context: Optional context for logging (parameters, etc.)

        Raises:
            CapabilityDenied: If the action is not allowed
        """
        full_action = f"{dispatcher}.{action}"

        # Check bypass mode
        if self.is_bypass_enabled():
            logger.warning("Policy bypass enabled, allowing %s", full_action)
            self._audit_log(dispatcher, action, "allowed", "bypass", context)
            return

        # Check explicit deny list
        if full_action in self.config.denied_actions:
            self._audit_log(dispatcher, action, "denied", "explicit_deny", context)
            raise CapabilityDenied(dispatcher, action, "Action explicitly denied by policy")

        # Check explicit allow list (overrides sensitivity)
        if full_action in self.config.allowed_actions:
            self._audit_log(dispatcher, action, "allowed", "explicit_allow", context)
            return

        # Check sensitivity level (context-aware)
        sensitivity = self.get_action_sensitivity(dispatcher, action, context)
        if sensitivity not in self.config.allowed_levels:
            # Check if this level requires confirmation (vs outright denial)
            if sensitivity in self.config.require_confirmation:
                self._audit_log(
                    dispatcher, action, "confirmation_required", f"sensitivity_{sensitivity.value}", context
                )
                raise ConfirmationRequired(
                    dispatcher,
                    action,
                    sensitivity,
                )
            # Otherwise, deny outright
            self._audit_log(
                dispatcher, action, "denied", f"sensitivity_{sensitivity.value}", context
            )
            raise CapabilityDenied(
                dispatcher,
                action,
                f"Sensitivity level '{sensitivity.value}' not allowed by policy",
                sensitivity=sensitivity,
            )

        # Check rate limit
        if self.config.rate_limit_per_minute > 0:
            self._check_rate_limit(dispatcher, action)

        self._audit_log(dispatcher, action, "allowed", f"sensitivity_{sensitivity.value}", context)

    def _check_rate_limit(self, dispatcher: str, action: str) -> None:
        """Check and enforce rate limits."""
        full_action = f"{dispatcher}.{action}"
        now = datetime.now(timezone.utc)
        minute_ago = now.replace(second=0, microsecond=0)

        # Get call history for this action
        if full_action not in self._call_counts:
            self._call_counts[full_action] = []

        # Remove old entries
        self._call_counts[full_action] = [
            t for t in self._call_counts[full_action] if t >= minute_ago
        ]

        # Check limit
        if len(self._call_counts[full_action]) >= self.config.rate_limit_per_minute:
            raise CapabilityDenied(
                dispatcher, action, f"Rate limit exceeded ({self.config.rate_limit_per_minute}/min)"
            )

        # Record this call
        self._call_counts[full_action].append(now)

    def _audit_log(
        self,
        dispatcher: str,
        action: str,
        result: str,
        reason: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log tool access for audit trail."""
        if not self.config.audit_logging:
            return

        # Import trace context here to avoid circular imports
        from .context import get_trace_context

        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dispatcher": dispatcher,
            "action": action,
            "result": result,
            "reason": reason,
        }

        # Add trace context if available
        trace_ctx = get_trace_context()
        if trace_ctx["trace_id"] is not None:
            log_entry["trace_id"] = trace_ctx["trace_id"]
        if trace_ctx["turn_id"] is not None:
            log_entry["turn_id"] = trace_ctx["turn_id"]

        if context:
            # Sanitize context to avoid logging sensitive data
            safe_context = {
                k: v for k, v in context.items() if k not in ("password", "token", "secret")
            }
            log_entry["context"] = safe_context

        if result == "denied":
            logger.warning("MCP policy: %s", json.dumps(log_entry))
        else:
            logger.debug("MCP policy: %s", json.dumps(log_entry))


# =============================================================================
# Convenience Functions
# =============================================================================


def check_capability(
    dispatcher: str,
    action: str,
    *,
    context: dict[str, Any] | None = None,
) -> None:
    """
    Check if a tool action is allowed by policy.

    Convenience function that uses the singleton PolicyEngine.

    Args:
        dispatcher: Dispatcher name (universe, market, etc.)
        action: Action name within the dispatcher
        context: Optional context for logging

    Raises:
        CapabilityDenied: If the action is not allowed
    """
    PolicyEngine.get_instance().check_capability(dispatcher, action, context=context)


def get_policy_status() -> dict[str, Any]:
    """
    Get current policy configuration status.

    Returns:
        Dictionary with policy status information
    """
    engine = PolicyEngine.get_instance()
    return {
        "policy_path": str(engine.policy_path),
        "policy_exists": engine.policy_path.exists(),
        "bypass_enabled": engine.is_bypass_enabled(),
        "config": engine.config.to_dict(),
    }
