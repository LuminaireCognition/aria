"""
Template-Based Custom Rules for Interest Engine v2.

Templates provide predefined rule patterns with parameters.
Each template has known prefetch capability - no derivation required.

Template Registry:
| Template       | Parameters             | Description                      | Prefetch |
|----------------|------------------------|----------------------------------|----------|
| group_role     | group, role            | Entity from group in role        | victim   |
| category_match | category               | Category passes match_threshold  | varies   |
| category_score | category, min, max?    | Category score in range          | varies   |
| value_above    | min                    | Kill value >= amount             | ✓        |
| value_below    | max                    | Kill value < amount              | ✓        |
| ship_class     | classes[]              | Victim ship class in list        | ✓        |
| ship_group     | groups[]               | Victim ship group ID in list     | ✓        |
| security_band  | bands[]                | System security band             | ✓        |
| system_match   | systems[]              | Kill in listed systems           | ✓        |
| attacker_count | min?, max?             | Number of attackers in range     | ✗        |
| solo_kill      | -                      | Exactly one attacker             | ✗        |
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..models import RuleMatch
from ..providers.base import BaseRuleProvider

if TYPE_CHECKING:
    from ...models import ProcessedKill

logger = logging.getLogger(__name__)


# =============================================================================
# Template Registry
# =============================================================================


@dataclass
class TemplateSpec:
    """Specification for a rule template."""

    name: str
    description: str
    required_params: list[str]
    optional_params: list[str]
    prefetch_capable: bool | str  # True, False, or "victim" for partial


# Built-in templates
TEMPLATE_REGISTRY: dict[str, TemplateSpec] = {
    "group_role": TemplateSpec(
        name="group_role",
        description="Entity from group in specified role",
        required_params=["group", "role"],
        optional_params=[],
        prefetch_capable="victim",  # Only victim role is prefetch-capable
    ),
    "category_match": TemplateSpec(
        name="category_match",
        description="Category passes match_threshold",
        required_params=["category"],
        optional_params=["threshold"],
        prefetch_capable=False,  # Depends on category
    ),
    "category_score": TemplateSpec(
        name="category_score",
        description="Category score in range",
        required_params=["category", "min"],
        optional_params=["max"],
        prefetch_capable=False,  # Depends on category
    ),
    "value_above": TemplateSpec(
        name="value_above",
        description="Kill value >= amount",
        required_params=["min"],
        optional_params=[],
        prefetch_capable=True,
    ),
    "value_below": TemplateSpec(
        name="value_below",
        description="Kill value < amount",
        required_params=["max"],
        optional_params=[],
        prefetch_capable=True,
    ),
    "ship_class": TemplateSpec(
        name="ship_class",
        description="Victim ship class in list",
        required_params=["classes"],
        optional_params=[],
        prefetch_capable=True,
    ),
    "ship_group": TemplateSpec(
        name="ship_group",
        description="Victim ship group ID in list",
        required_params=["groups"],
        optional_params=[],
        prefetch_capable=True,
    ),
    "security_band": TemplateSpec(
        name="security_band",
        description="System security band (high/low/null/wh)",
        required_params=["bands"],
        optional_params=[],
        prefetch_capable=True,
    ),
    "system_match": TemplateSpec(
        name="system_match",
        description="Kill in listed systems",
        required_params=["systems"],
        optional_params=[],
        prefetch_capable=True,
    ),
    "attacker_count": TemplateSpec(
        name="attacker_count",
        description="Number of attackers in range",
        required_params=[],
        optional_params=["min", "max"],
        prefetch_capable=False,
    ),
    "solo_kill": TemplateSpec(
        name="solo_kill",
        description="Exactly one attacker",
        required_params=[],
        optional_params=[],
        prefetch_capable=False,
    ),
}


def get_template_spec(name: str) -> TemplateSpec | None:
    """Get template specification by name."""
    return TEMPLATE_REGISTRY.get(name)


def list_templates() -> list[str]:
    """List all available template names."""
    return list(TEMPLATE_REGISTRY.keys())


# =============================================================================
# Template Rule Providers
# =============================================================================


class ValueAboveRule(BaseRuleProvider):
    """Template: value_above - Kill value >= amount."""

    _name = "value_above"
    _prefetch_capable = True

    def __init__(self, params: dict[str, Any]):
        self._min = params.get("min", 0)

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        if kill is None:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No kill data",
                prefetch_capable=True,
            )

        if kill.total_value >= self._min:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason=f"Value {kill.total_value:,.0f} >= {self._min:,.0f}",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason=f"Value {kill.total_value:,.0f} < {self._min:,.0f}",
        )

    def validate(self, config: dict[str, Any]) -> list[str]:
        errors = []
        if self._min < 0:
            errors.append("min must be non-negative")
        return errors


class ValueBelowRule(BaseRuleProvider):
    """Template: value_below - Kill value < amount."""

    _name = "value_below"
    _prefetch_capable = True

    def __init__(self, params: dict[str, Any]):
        self._max = params.get("max", float("inf"))

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        if kill is None:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No kill data",
                prefetch_capable=True,
            )

        if kill.total_value < self._max:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason=f"Value {kill.total_value:,.0f} < {self._max:,.0f}",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason=f"Value {kill.total_value:,.0f} >= {self._max:,.0f}",
        )


class SoloKillRule(BaseRuleProvider):
    """Template: solo_kill - Exactly one attacker."""

    _name = "solo_kill"
    _prefetch_capable = False  # Attacker count requires ESI

    def __init__(self, params: dict[str, Any] | None = None):
        pass

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        if kill is None:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No kill data",
                prefetch_capable=False,
            )

        if kill.attacker_count == 1:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason="Solo kill (1 attacker)",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason=f"Not solo ({kill.attacker_count} attackers)",
        )


class AttackerCountRule(BaseRuleProvider):
    """Template: attacker_count - Number of attackers in range."""

    _name = "attacker_count"
    _prefetch_capable = False

    def __init__(self, params: dict[str, Any]):
        self._min = params.get("min", 0)
        self._max = params.get("max", float("inf"))

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        if kill is None:
            return RuleMatch(
                rule_id=self._name,
                matched=False,
                reason="No kill data",
                prefetch_capable=False,
            )

        count = kill.attacker_count

        if self._min <= count <= self._max:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason=f"Attacker count {count} in range [{self._min}, {self._max}]",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason=f"Attacker count {count} outside range [{self._min}, {self._max}]",
        )


class SystemMatchRule(BaseRuleProvider):
    """Template: system_match - Kill in listed systems."""

    _name = "system_match"
    _prefetch_capable = True

    def __init__(self, params: dict[str, Any]):
        systems = params.get("systems", [])
        # Accept both system IDs and names
        self._system_ids: set[int] = set()
        self._system_names: set[str] = set()

        for s in systems:
            if isinstance(s, int):
                self._system_ids.add(s)
            elif isinstance(s, str):
                self._system_names.add(s.lower())

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        # Check by ID
        if system_id in self._system_ids:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason=f"System {system_id} in match list",
            )

        # Check by name if available in context
        system_name = config.get("system_name", "").lower()
        if system_name and system_name in self._system_names:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason=f"System '{system_name}' in match list",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason="System not in match list",
        )


class SecurityBandRule(BaseRuleProvider):
    """Template: security_band - System security band."""

    _name = "security_band"
    _prefetch_capable = True

    def __init__(self, params: dict[str, Any]):
        bands = params.get("bands", [])
        self._bands = {b.lower() for b in bands}

    def evaluate(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> RuleMatch:
        # Get security status from config/context
        security = config.get("security_status", 0.5)

        # Determine band
        if security >= 0.5:
            band = "high"
        elif security > 0.0:
            band = "low"
        elif security <= -0.5:
            band = "wh"  # Wormhole (typically -1.0)
        else:
            band = "null"

        if band in self._bands:
            return RuleMatch(
                rule_id=self._name,
                matched=True,
                reason=f"Security band '{band}' matches",
            )

        return RuleMatch(
            rule_id=self._name,
            matched=False,
            reason=f"Security band '{band}' not in {self._bands}",
        )


# =============================================================================
# Template Factory
# =============================================================================


def create_template_rule(
    template_name: str,
    params: dict[str, Any],
) -> BaseRuleProvider | None:
    """
    Create a rule provider from a template.

    Args:
        template_name: Template name from TEMPLATE_REGISTRY
        params: Template parameters

    Returns:
        RuleProvider instance or None if template unknown
    """
    if template_name == "value_above":
        return ValueAboveRule(params)
    elif template_name == "value_below":
        return ValueBelowRule(params)
    elif template_name == "solo_kill":
        return SoloKillRule(params)
    elif template_name == "attacker_count":
        return AttackerCountRule(params)
    elif template_name == "system_match":
        return SystemMatchRule(params)
    elif template_name == "security_band":
        return SecurityBandRule(params)
    # Add more templates as needed

    logger.warning(f"Unknown template: {template_name}")
    return None


def validate_template_params(
    template_name: str,
    params: dict[str, Any],
) -> list[str]:
    """
    Validate template parameters.

    Args:
        template_name: Template name
        params: Template parameters

    Returns:
        List of validation errors
    """
    errors = []

    spec = get_template_spec(template_name)
    if spec is None:
        errors.append(f"Unknown template: {template_name}")
        return errors

    # Check required params
    for param in spec.required_params:
        if param not in params:
            errors.append(f"Template '{template_name}' requires parameter '{param}'")

    return errors


def get_template_prefetch_capability(
    template_name: str,
    params: dict[str, Any],
) -> bool:
    """
    Get prefetch capability for a template with params.

    Args:
        template_name: Template name
        params: Template parameters

    Returns:
        True if rule can evaluate at prefetch stage
    """
    spec = get_template_spec(template_name)
    if spec is None:
        return False

    # Handle partial prefetch capability
    if spec.prefetch_capable == "victim":
        # Only prefetch-capable if role is victim
        role = params.get("role", "any")
        return role == "victim"

    return bool(spec.prefetch_capable)
