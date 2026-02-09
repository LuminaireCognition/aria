"""
Tests for Interest Engine v2 Validation Module.

Tests configuration validation, error formatting, and warning detection.
"""

from __future__ import annotations

from typing import Any

import pytest

from aria_esi.services.redisq.interest_v2.models import CANONICAL_CATEGORIES
from aria_esi.services.redisq.interest_v2.validation import (
    ValidationError,
    ValidationResult,
    format_validation_result,
    validate_interest_config,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def valid_simple_config() -> dict[str, Any]:
    """Create a valid simple-tier configuration."""
    return {
        "engine": "v2",
        "preset": "trade-hub",
    }


@pytest.fixture
def valid_intermediate_config() -> dict[str, Any]:
    """Create a valid intermediate-tier configuration."""
    return {
        "engine": "v2",
        "preset": "trade-hub",
        "weights": {
            "location": 0.8,
            "value": 0.7,
            "politics": 0.3,
        },
    }


@pytest.fixture
def valid_advanced_config() -> dict[str, Any]:
    """Create a valid advanced-tier configuration."""
    return {
        "engine": "v2",
        "preset": "custom",
        "weights": {
            "location": 0.8,
            "value": 0.7,
        },
        "signals": {
            "location": {
                "geographic": {
                    "systems": [{"name": "Jita", "classification": "home"}],
                },
            },
        },
    }


@pytest.fixture
def malformed_config() -> dict[str, Any]:
    """Create a configuration that will cause validation errors."""
    return {
        "engine": "v2",
        "preset": "trade-hub",
        "rules": {
            "always_notify": ["nonexistent_rule_xyz"],  # Unknown rule
        },
    }


@pytest.fixture
def config_with_unknown_category() -> dict[str, Any]:
    """Create a config with unknown signal category."""
    return {
        "engine": "v2",
        "preset": "custom",
        "weights": {"location": 0.8},
        "signals": {
            "unknown_category": {"some": "config"},
        },
    }


# =============================================================================
# TestValidationError
# =============================================================================


class TestValidationError:
    """Tests for ValidationError dataclass."""

    def test_str_with_suggestion(self):
        """String representation includes parenthetical suggestion."""
        err = ValidationError(
            field="weights.location",
            code="NEGATIVE_WEIGHT",
            message="Weight must be non-negative",
            suggestion="Set a value >= 0",
        )

        result = str(err)

        assert "weights.location" in result
        assert "Weight must be non-negative" in result
        assert "(Set a value >= 0)" in result

    def test_str_without_suggestion(self):
        """String representation works without suggestion."""
        err = ValidationError(
            field="engine",
            code="INVALID_ENGINE",
            message="Invalid engine version",
            suggestion=None,
        )

        result = str(err)

        assert "engine" in result
        assert "Invalid engine version" in result
        assert "(" not in result

    def test_field_and_message_separate(self):
        """Field and message are separated by colon."""
        err = ValidationError(
            field="rules.always_notify",
            code="UNKNOWN_RULE",
            message="Unknown rule referenced",
        )

        result = str(err)

        assert "rules.always_notify: Unknown rule referenced" in result


# =============================================================================
# TestValidationResult
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_error_messages_property(self):
        """error_messages property returns list of strings."""
        result = ValidationResult(
            valid=False,
            errors=[
                ValidationError(
                    field="weights.x",
                    code="ERR1",
                    message="Error 1",
                ),
                ValidationError(
                    field="weights.y",
                    code="ERR2",
                    message="Error 2",
                    suggestion="Fix it",
                ),
            ],
            warnings=[],
        )

        messages = result.error_messages

        assert len(messages) == 2
        assert "Error 1" in messages[0]
        assert "Error 2" in messages[1]
        assert "(Fix it)" in messages[1]

    def test_warning_messages_property(self):
        """warning_messages property returns list of strings."""
        result = ValidationResult(
            valid=True,
            errors=[],
            warnings=[
                ValidationError(
                    field="signals.value",
                    code="WARN1",
                    message="Warning 1",
                ),
            ],
        )

        messages = result.warning_messages

        assert len(messages) == 1
        assert "Warning 1" in messages[0]

    def test_valid_when_no_errors(self):
        """valid is True when errors list is empty."""
        result = ValidationResult(
            valid=True,
            errors=[],
            warnings=[
                ValidationError(field="x", code="W", message="warning"),
            ],
        )

        assert result.valid is True
        assert len(result.warnings) == 1

    def test_invalid_when_errors_present(self):
        """valid is False when errors list has items."""
        result = ValidationResult(
            valid=False,
            errors=[
                ValidationError(field="x", code="E", message="error"),
            ],
            warnings=[],
        )

        assert result.valid is False


# =============================================================================
# TestValidateInterestConfig
# =============================================================================


class TestValidateInterestConfig:
    """Tests for validate_interest_config function."""

    def test_parse_error_handling(self):
        """Malformed config produces parse error."""
        # This config has a truly malformed structure that will fail parsing
        config_with_bad_thresholds = {
            "engine": "v2",
            "preset": "trade-hub",
            "thresholds": "not_a_dict",  # Will cause type error
        }
        result = validate_interest_config(config_with_bad_thresholds)

        assert result.valid is False
        assert len(result.errors) >= 1
        # Should have a parse error
        error_codes = [e.code for e in result.errors]
        assert any("PARSE" in code or "CONFIG" in code for code in error_codes)

    def test_valid_config_no_errors(self, valid_simple_config: dict[str, Any]):
        """Valid simple config produces no errors."""
        result = validate_interest_config(valid_simple_config)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_valid_intermediate_config(self, valid_intermediate_config: dict[str, Any]):
        """Valid intermediate config produces no errors."""
        result = validate_interest_config(valid_intermediate_config)

        assert result.valid is True

    def test_valid_advanced_config(self, valid_advanced_config: dict[str, Any]):
        """Valid advanced config produces no errors."""
        result = validate_interest_config(valid_advanced_config)

        assert result.valid is True


# =============================================================================
# TestValidateWeights
# =============================================================================


class TestValidateWeights:
    """Tests for weight validation."""

    def test_disabled_with_signals_warning(self):
        """Warning when category has signals but weight=0."""
        config = {
            "engine": "v2",
            "preset": "custom",
            "weights": {
                "location": 0.0,  # Disabled
                "value": 0.8,
            },
            "signals": {
                "location": {
                    "geographic": {"systems": []},
                },
            },
        }

        result = validate_interest_config(config)

        # Should have a warning about disabled category with signals
        warning_codes = [w.code for w in result.warnings]
        assert "DISABLED_WITH_SIGNALS" in warning_codes

    def test_no_warning_when_weight_positive(self):
        """No warning when category with signals has positive weight."""
        config = {
            "engine": "v2",
            "preset": "custom",
            "weights": {
                "location": 0.8,
                "value": 0.5,
            },
            "signals": {
                "location": {
                    "geographic": {"systems": []},
                },
            },
        }

        result = validate_interest_config(config)

        # Should not have the warning
        warning_codes = [w.code for w in result.warnings]
        assert "DISABLED_WITH_SIGNALS" not in warning_codes


# =============================================================================
# TestValidateRules
# =============================================================================


class TestValidateRules:
    """Tests for rule validation."""

    def test_unknown_rule_error(self):
        """Error when referencing unknown rule ID."""
        config = {
            "engine": "v2",
            "preset": "trade-hub",
            "rules": {
                "always_notify": ["nonexistent_rule"],
            },
        }

        result = validate_interest_config(config)

        assert result.valid is False
        error_messages = result.error_messages
        assert any("nonexistent_rule" in msg for msg in error_messages)

    def test_custom_rule_valid(self):
        """Custom rules defined in rules.custom are valid."""
        config = {
            "engine": "v2",
            "preset": "custom",
            "weights": {"location": 0.8},
            "signals": {"location": {}},
            "rules": {
                "always_notify": ["my_custom_rule"],
                "custom": {
                    "my_custom_rule": {
                        "type": "value_threshold",
                        "threshold": 1_000_000_000,
                    },
                },
            },
        }

        result = validate_interest_config(config)

        # Custom rule should be recognized
        error_codes = [e.code for e in result.errors]
        assert "UNKNOWN_RULE" not in error_codes

    def test_high_value_no_min_warning(self):
        """Warning when using high_value rule without signals.value.min."""
        config = {
            "engine": "v2",
            "preset": "trade-hub",
            "rules": {
                "always_notify": ["high_value"],
            },
        }

        result = validate_interest_config(config)

        warning_codes = [w.code for w in result.warnings]
        assert "HIGH_VALUE_NO_MIN" in warning_codes

    def test_high_value_with_min_no_warning(self):
        """No warning when high_value rule has signals.value.min."""
        config = {
            "engine": "v2",
            "preset": "custom",
            "weights": {"value": 0.8},
            "signals": {
                "value": {"min": 500_000_000},
            },
            "rules": {
                "always_notify": ["high_value"],
            },
        }

        result = validate_interest_config(config)

        warning_codes = [w.code for w in result.warnings]
        assert "HIGH_VALUE_NO_MIN" not in warning_codes


# =============================================================================
# TestValidateSignals
# =============================================================================


class TestValidateSignals:
    """Tests for signal validation."""

    def test_unknown_category_error(self, config_with_unknown_category: dict[str, Any]):
        """Error when using unknown signal category."""
        result = validate_interest_config(config_with_unknown_category)

        assert result.valid is False
        error_codes = [e.code for e in result.errors]
        assert "UNKNOWN_CATEGORY" in error_codes

    def test_valid_categories_accepted(self):
        """All canonical categories are accepted."""
        for category in CANONICAL_CATEGORIES:
            config = {
                "engine": "v2",
                "preset": "custom",
                "weights": {category: 0.5},
                "signals": {
                    category: {},
                },
            }
            result = validate_interest_config(config)

            # Should not have UNKNOWN_CATEGORY error for valid categories
            error_codes = [e.code for e in result.errors]
            assert "UNKNOWN_CATEGORY" not in error_codes, f"Category {category} rejected"

    def test_political_no_groups_warning(self):
        """Warning when using political preset without groups."""
        config = {
            "engine": "v2",
            "preset": "political",
            "signals": {
                "politics": {},  # No groups defined
            },
        }

        result = validate_interest_config(config)

        warning_codes = [w.code for w in result.warnings]
        assert "POLITICAL_NO_GROUPS" in warning_codes

    def test_require_any_unknown_group_error(self):
        """Error when require_any references undefined group."""
        config = {
            "engine": "v2",
            "preset": "custom",
            "weights": {"politics": 0.8},
            "signals": {
                "politics": {
                    "groups": {
                        "allies": {"alliances": [99001234]},
                    },
                    "require_any": ["enemies"],  # Not defined
                },
            },
        }

        result = validate_interest_config(config)

        assert result.valid is False
        error_codes = [e.code for e in result.errors]
        assert "UNKNOWN_GROUP" in error_codes

    def test_require_all_unknown_group_error(self):
        """Error when require_all references undefined group."""
        config = {
            "engine": "v2",
            "preset": "custom",
            "weights": {"politics": 0.8},
            "signals": {
                "politics": {
                    "groups": {
                        "allies": {"alliances": [99001234]},
                    },
                    "require_all": ["hostiles"],  # Not defined
                },
            },
        }

        result = validate_interest_config(config)

        assert result.valid is False
        error_codes = [e.code for e in result.errors]
        assert "UNKNOWN_GROUP" in error_codes

    def test_valid_group_references(self):
        """No error when group references are valid."""
        config = {
            "engine": "v2",
            "preset": "custom",
            "weights": {"politics": 0.8},
            "signals": {
                "politics": {
                    "groups": {
                        "allies": {"alliances": [99001234]},
                        "enemies": {"alliances": [99005678]},
                    },
                    "require_any": ["allies", "enemies"],
                },
            },
        }

        result = validate_interest_config(config)

        error_codes = [e.code for e in result.errors]
        assert "UNKNOWN_GROUP" not in error_codes


# =============================================================================
# TestValidatePrefetch
# =============================================================================


class TestValidatePrefetch:
    """Tests for prefetch validation."""

    def test_strict_with_post_fetch_rule_warning(self):
        """Warning when strict mode uses post-fetch rule in always_notify."""
        config = {
            "engine": "v2",
            "preset": "trade-hub",
            "prefetch": {
                "mode": "strict",
            },
            "rules": {
                # war_target_activity is NOT prefetch capable
                "always_notify": ["war_target_activity"],
            },
        }

        result = validate_interest_config(config)

        warning_codes = [w.code for w in result.warnings]
        assert "STRICT_POST_FETCH_RULE" in warning_codes

    def test_bypass_mode_warning(self):
        """Warning when using bypass prefetch mode."""
        config = {
            "engine": "v2",
            "preset": "trade-hub",
            "prefetch": {
                "mode": "bypass",
            },
        }

        result = validate_interest_config(config)

        warning_codes = [w.code for w in result.warnings]
        assert "BYPASS_WARNING" in warning_codes

    def test_auto_mode_no_warning(self):
        """No prefetch warning for auto mode."""
        config = {
            "engine": "v2",
            "preset": "trade-hub",
            "prefetch": {
                "mode": "auto",
            },
        }

        result = validate_interest_config(config)

        warning_codes = [w.code for w in result.warnings]
        assert "BYPASS_WARNING" not in warning_codes
        assert "STRICT_POST_FETCH_RULE" not in warning_codes

    def test_conservative_mode_no_warning(self):
        """No prefetch warning for conservative mode."""
        config = {
            "engine": "v2",
            "preset": "trade-hub",
            "prefetch": {
                "mode": "conservative",
            },
        }

        result = validate_interest_config(config)

        warning_codes = [w.code for w in result.warnings]
        assert "BYPASS_WARNING" not in warning_codes


# =============================================================================
# TestFormatValidationResult
# =============================================================================


class TestFormatValidationResult:
    """Tests for format_validation_result function."""

    def test_format_valid(self, valid_simple_config: dict[str, Any]):
        """Valid configuration shows success message."""
        result = validate_interest_config(valid_simple_config)
        formatted = format_validation_result(result)

        assert "✓" in formatted
        assert "valid" in formatted.lower()

    def test_format_with_errors(self, malformed_config: dict[str, Any]):
        """Errors are listed in formatted output."""
        result = validate_interest_config(malformed_config)
        formatted = format_validation_result(result)

        assert "✗" in formatted
        assert "error" in formatted.lower()
        assert "•" in formatted  # Bullet points

    def test_format_with_warnings(self):
        """Warnings are listed in formatted output."""
        config = {
            "engine": "v2",
            "preset": "trade-hub",
            "prefetch": {"mode": "bypass"},
        }
        result = validate_interest_config(config)
        formatted = format_validation_result(result)

        assert "Warning" in formatted
        assert "⚠" in formatted

    def test_format_with_both(self):
        """Both errors and warnings shown when present."""
        config = {
            "engine": "v2",
            "preset": "trade-hub",
            "prefetch": {"mode": "bypass"},
            "rules": {
                "always_notify": ["nonexistent_rule"],
            },
        }
        result = validate_interest_config(config)
        formatted = format_validation_result(result)

        assert "Error" in formatted
        assert "Warning" in formatted

    def test_format_shows_counts(self, malformed_config: dict[str, Any]):
        """Formatted output shows error/warning counts."""
        result = validate_interest_config(malformed_config)
        formatted = format_validation_result(result)

        # Should show count like "Errors (1):" or "Errors (2):"
        assert "Errors (" in formatted
