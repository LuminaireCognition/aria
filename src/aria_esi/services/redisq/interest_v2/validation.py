"""
Unified Configuration Validation for Interest Engine v2.

Provides comprehensive validation of interest configuration including:
- Weight constraints
- Threshold ordering
- Rule references
- Signal configuration
- Prefetch compatibility
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import InterestConfigV2
from .models import CANONICAL_CATEGORIES


@dataclass
class ValidationError:
    """Structured validation error with context."""

    field: str  # Field path (e.g., "weights.location")
    code: str  # Error code (e.g., "NEGATIVE_WEIGHT")
    message: str  # Human-readable message
    suggestion: str | None = None  # How to fix it

    def __str__(self) -> str:
        result = f"{self.field}: {self.message}"
        if self.suggestion:
            result += f" ({self.suggestion})"
        return result


@dataclass
class ValidationResult:
    """Complete validation result."""

    valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]

    @property
    def error_messages(self) -> list[str]:
        """Get error messages as strings."""
        return [str(e) for e in self.errors]

    @property
    def warning_messages(self) -> list[str]:
        """Get warning messages as strings."""
        return [str(w) for w in self.warnings]


def validate_interest_config(config: dict[str, Any]) -> ValidationResult:
    """
    Validate an interest configuration dictionary.

    Args:
        config: interest section from profile YAML

    Returns:
        ValidationResult with errors and warnings
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    # Parse config
    try:
        parsed = InterestConfigV2.from_dict(config)
    except Exception as e:
        errors.append(
            ValidationError(
                field="interest",
                code="PARSE_ERROR",
                message=f"Failed to parse configuration: {e}",
            )
        )
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    # Get structured validation
    config_errors = parsed.validate()
    for err in config_errors:
        errors.append(
            ValidationError(
                field="interest",
                code="CONFIG_ERROR",
                message=err,
            )
        )

    # Additional validation
    _validate_weights(parsed, errors, warnings)
    _validate_rules(parsed, errors, warnings)
    _validate_signals(parsed, errors, warnings)
    _validate_prefetch(parsed, errors, warnings)

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def _validate_weights(
    config: InterestConfigV2,
    errors: list[ValidationError],
    warnings: list[ValidationError],
) -> None:
    """Validate weight configuration."""
    if not config.weights:
        return

    # Check for disabled categories with signals
    if config.signals:
        for category in config.signals:
            weight = config.weights.get(category, 0)
            if weight == 0:
                warnings.append(
                    ValidationError(
                        field=f"weights.{category}",
                        code="DISABLED_WITH_SIGNALS",
                        message=f"Category '{category}' has signals configured but weight=0",
                        suggestion="Set weight > 0 or remove signals block",
                    )
                )


def _validate_rules(
    config: InterestConfigV2,
    errors: list[ValidationError],
    warnings: list[ValidationError],
) -> None:
    """Validate rule configuration."""
    from .providers.registry import get_provider_registry

    registry = get_provider_registry()

    # Check built-in rule references
    for rule_list_name in ("always_notify", "always_ignore"):
        rule_list = getattr(config.rules, rule_list_name, [])

        for rule_id in rule_list:
            # Check if it's a built-in rule or custom rule
            provider = registry.get_rule(rule_id)

            if provider is None and rule_id not in config.rules.custom:
                errors.append(
                    ValidationError(
                        field=f"rules.{rule_list_name}",
                        code="UNKNOWN_RULE",
                        message=f"Unknown rule: '{rule_id}'",
                        suggestion="Use a built-in rule ID or define in rules.custom",
                    )
                )

    # Check high_value rule dependency
    if "high_value" in config.rules.always_notify:
        has_value_min = False
        if config.signals and "value" in config.signals:
            has_value_min = "min" in config.signals["value"]

        if not has_value_min:
            warnings.append(
                ValidationError(
                    field="rules.always_notify",
                    code="HIGH_VALUE_NO_MIN",
                    message="'high_value' rule used but signals.value.min not set",
                    suggestion="Add signals.value.min or rule will use default 1B ISK",
                )
            )


def _validate_signals(
    config: InterestConfigV2,
    errors: list[ValidationError],
    warnings: list[ValidationError],
) -> None:
    """Validate signal configuration."""
    if not config.signals:
        return

    # Check for unknown categories
    for category in config.signals:
        if category not in CANONICAL_CATEGORIES:
            errors.append(
                ValidationError(
                    field=f"signals.{category}",
                    code="UNKNOWN_CATEGORY",
                    message=f"Unknown signal category: '{category}'",
                    suggestion=f"Valid categories: {', '.join(CANONICAL_CATEGORIES)}",
                )
            )

    # Check politics groups
    politics_config = config.signals.get("politics", {})
    groups = politics_config.get("groups", {})

    if config.preset == "political" and not groups:
        warnings.append(
            ValidationError(
                field="signals.politics.groups",
                code="POLITICAL_NO_GROUPS",
                message="Political preset used but no groups configured",
                suggestion="Add groups or NPC faction defaults will be used",
            )
        )

    # Check require_any/require_all reference defined groups
    for gate in ("require_any", "require_all"):
        gate_groups = politics_config.get(gate, [])
        for group_name in gate_groups:
            if group_name not in groups:
                errors.append(
                    ValidationError(
                        field=f"signals.politics.{gate}",
                        code="UNKNOWN_GROUP",
                        message=f"References unknown group: '{group_name}'",
                        suggestion="Define group in signals.politics.groups",
                    )
                )


def _validate_prefetch(
    config: InterestConfigV2,
    errors: list[ValidationError],
    warnings: list[ValidationError],
) -> None:
    """Validate prefetch configuration."""
    from .providers.registry import get_provider_registry

    prefetch_mode = config.prefetch.mode

    if prefetch_mode == "strict":
        # Check if any always_notify rules require post-fetch data
        registry = get_provider_registry()

        for rule_id in config.rules.always_notify:
            provider = registry.get_rule(rule_id)
            if provider and not provider.prefetch_capable:
                warnings.append(
                    ValidationError(
                        field="prefetch.mode",
                        code="STRICT_POST_FETCH_RULE",
                        message=(f"Strict mode with post-fetch rule '{rule_id}' in always_notify"),
                        suggestion=(
                            "Will be coerced to conservative mode; "
                            "set mode: conservative to suppress warning"
                        ),
                    )
                )

    if prefetch_mode == "bypass":
        warnings.append(
            ValidationError(
                field="prefetch.mode",
                code="BYPASS_WARNING",
                message="Prefetch bypass fetches all kills from ESI",
                suggestion="This increases API usage; use only if needed",
            )
        )


def format_validation_result(result: ValidationResult) -> str:
    """
    Format validation result for display.

    Args:
        result: ValidationResult to format

    Returns:
        Human-readable validation summary
    """
    lines = []

    if result.valid:
        lines.append("✓ Configuration is valid")
    else:
        lines.append("✗ Configuration has errors")

    if result.errors:
        lines.append(f"\nErrors ({len(result.errors)}):")
        for err in result.errors:
            lines.append(f"  • {err}")

    if result.warnings:
        lines.append(f"\nWarnings ({len(result.warnings)}):")
        for warn in result.warnings:
            lines.append(f"  ⚠ {warn}")

    return "\n".join(lines)
