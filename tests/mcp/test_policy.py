"""
Tests for MCP tool capability policy engine.

Security: These tests verify the capability gating that limits blast radius
from prompt injection attacks. See dev/reviews/SECURITY_000.md #5.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aria_esi.mcp.policy import (
    CapabilityDenied,
    ConfirmationRequired,
    PolicyConfig,
    PolicyEngine,
    SensitivityLevel,
    check_capability,
    get_policy_status,
)


@pytest.fixture(autouse=True)
def reset_policy_singleton():
    """Reset policy singleton between tests."""
    PolicyEngine.reset_instance()
    yield
    PolicyEngine.reset_instance()


class TestSensitivityLevel:
    """Test sensitivity level enum."""

    def test_public_level(self):
        """Public level exists."""
        assert SensitivityLevel.PUBLIC.value == "public"

    def test_aggregate_level(self):
        """Aggregate level exists."""
        assert SensitivityLevel.AGGREGATE.value == "aggregate"

    def test_market_level(self):
        """Market level exists."""
        assert SensitivityLevel.MARKET.value == "market"

    def test_authenticated_level(self):
        """Authenticated level exists."""
        assert SensitivityLevel.AUTHENTICATED.value == "authenticated"

    def test_restricted_level(self):
        """Restricted level exists."""
        assert SensitivityLevel.RESTRICTED.value == "restricted"


class TestPolicyConfig:
    """Test policy configuration."""

    def test_default_config(self):
        """Default config allows safe levels, excludes authenticated/restricted."""
        config = PolicyConfig()

        assert SensitivityLevel.PUBLIC in config.allowed_levels
        assert SensitivityLevel.AGGREGATE in config.allowed_levels
        assert SensitivityLevel.MARKET in config.allowed_levels
        # Authenticated and restricted not allowed by default (security)
        assert SensitivityLevel.AUTHENTICATED not in config.allowed_levels
        assert SensitivityLevel.RESTRICTED not in config.allowed_levels

    def test_from_dict(self):
        """Config can be loaded from dict."""
        data = {
            "allowed_levels": ["public"],
            "denied_actions": ["universe.test"],
            "audit_logging": False,
        }

        config = PolicyConfig.from_dict(data)

        assert config.allowed_levels == {SensitivityLevel.PUBLIC}
        assert "universe.test" in config.denied_actions
        assert config.audit_logging is False

    def test_to_dict(self):
        """Config can be serialized to dict."""
        config = PolicyConfig()
        data = config.to_dict()

        assert "allowed_levels" in data
        assert "denied_actions" in data
        assert "audit_logging" in data


class TestPolicyEngine:
    """Test policy engine."""

    def test_singleton_pattern(self):
        """Engine uses singleton pattern."""
        engine1 = PolicyEngine.get_instance()
        engine2 = PolicyEngine.get_instance()

        assert engine1 is engine2

    def test_loads_default_config(self, tmp_path: Path):
        """Engine loads default config when no file exists."""
        missing_path = tmp_path / "nonexistent.json"
        engine = PolicyEngine(policy_path=missing_path)

        # Should have default config
        assert SensitivityLevel.PUBLIC in engine.config.allowed_levels

    def test_loads_config_from_file(self, tmp_path: Path):
        """Engine loads config from file."""
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "policy": {
                        "allowed_levels": ["public"],
                        "denied_actions": ["market.orders"],
                    }
                }
            )
        )

        engine = PolicyEngine(policy_path=policy_file)

        assert engine.config.allowed_levels == {SensitivityLevel.PUBLIC}
        assert "market.orders" in engine.config.denied_actions

    def test_get_action_sensitivity(self):
        """Engine returns correct sensitivity for actions."""
        engine = PolicyEngine.get_instance()

        # Public actions
        assert engine.get_action_sensitivity("universe", "route") == SensitivityLevel.PUBLIC
        assert engine.get_action_sensitivity("sde", "item_info") == SensitivityLevel.PUBLIC

        # Aggregate actions
        assert engine.get_action_sensitivity("universe", "activity") == SensitivityLevel.AGGREGATE

        # Market actions
        assert engine.get_action_sensitivity("market", "prices") == SensitivityLevel.MARKET

    def test_check_capability_allows_public(self):
        """Public actions are allowed by default."""
        engine = PolicyEngine.get_instance()

        # Should not raise
        engine.check_capability("universe", "route")
        engine.check_capability("sde", "search")

    def test_check_capability_denies_explicit(self, tmp_path: Path):
        """Explicitly denied actions are rejected."""
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "policy": {
                        "denied_actions": ["universe.route"],
                    }
                }
            )
        )

        engine = PolicyEngine(policy_path=policy_file)

        with pytest.raises(CapabilityDenied) as exc:
            engine.check_capability("universe", "route")

        assert exc.value.dispatcher == "universe"
        assert exc.value.action == "route"
        assert "explicitly denied" in str(exc.value)

    def test_check_capability_denies_restricted(self, tmp_path: Path):
        """Restricted sensitivity actions are denied by default."""
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "policy": {
                        "allowed_levels": ["public"],  # Only public allowed
                    }
                }
            )
        )

        engine = PolicyEngine(policy_path=policy_file)

        # Market level should be denied
        with pytest.raises(CapabilityDenied) as exc:
            engine.check_capability("market", "prices")

        assert "Sensitivity level" in str(exc.value)

    def test_bypass_mode(self, tmp_path: Path, monkeypatch):
        """Bypass mode allows all actions."""
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "policy": {
                        "denied_actions": ["universe.route"],
                    }
                }
            )
        )

        monkeypatch.setenv("ARIA_MCP_BYPASS_POLICY", "1")
        engine = PolicyEngine(policy_path=policy_file)

        # Should not raise even though explicitly denied
        engine.check_capability("universe", "route")


class TestKillmailsSensitivity:
    """Test killmails dispatcher sensitivity classification.

    Security: SECURITY_001.md Finding #5 - killmails actions must be
    classified in the default sensitivity map for policy clarity.
    """

    def test_killmails_query_is_aggregate(self):
        """killmails.query should be AGGREGATE sensitivity."""
        engine = PolicyEngine.get_instance()
        sensitivity = engine.get_action_sensitivity("killmails", "query")
        assert sensitivity == SensitivityLevel.AGGREGATE

    def test_killmails_stats_is_aggregate(self):
        """killmails.stats should be AGGREGATE sensitivity."""
        engine = PolicyEngine.get_instance()
        sensitivity = engine.get_action_sensitivity("killmails", "stats")
        assert sensitivity == SensitivityLevel.AGGREGATE

    def test_killmails_recent_is_aggregate(self):
        """killmails.recent should be AGGREGATE sensitivity."""
        engine = PolicyEngine.get_instance()
        sensitivity = engine.get_action_sensitivity("killmails", "recent")
        assert sensitivity == SensitivityLevel.AGGREGATE

    def test_killmails_actions_allowed_by_default(self):
        """killmails actions should be allowed by default policy."""
        engine = PolicyEngine.get_instance()

        # Should not raise - AGGREGATE is in default allowed_levels
        engine.check_capability("killmails", "query")
        engine.check_capability("killmails", "stats")
        engine.check_capability("killmails", "recent")

    def test_killmails_denied_when_aggregate_not_allowed(self, tmp_path: Path):
        """killmails actions should be denied when AGGREGATE not in allowed_levels."""
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "policy": {
                        "allowed_levels": ["public"],  # No aggregate
                    }
                }
            )
        )

        engine = PolicyEngine(policy_path=policy_file)

        with pytest.raises(CapabilityDenied) as exc:
            engine.check_capability("killmails", "query")

        assert exc.value.sensitivity == SensitivityLevel.AGGREGATE


class TestCapabilityDenied:
    """Test CapabilityDenied exception."""

    def test_stores_dispatcher_and_action(self):
        """Exception stores dispatcher and action."""
        exc = CapabilityDenied("universe", "route", "test reason")

        assert exc.dispatcher == "universe"
        assert exc.action == "route"
        assert "test reason" in str(exc)

    def test_stores_sensitivity(self):
        """Exception stores sensitivity level."""
        exc = CapabilityDenied(
            "market", "prices", "test", sensitivity=SensitivityLevel.MARKET
        )

        assert exc.sensitivity == SensitivityLevel.MARKET


class TestContextAwareSensitivity:
    """Test context-aware sensitivity escalation."""

    def test_fitting_with_pilot_skills_escalates_to_authenticated(self):
        """Fitting with use_pilot_skills=True escalates to AUTHENTICATED."""
        engine = PolicyEngine.get_instance()

        sensitivity = engine.get_action_sensitivity(
            "fitting", "calculate_stats", context={"use_pilot_skills": True}
        )

        assert sensitivity == SensitivityLevel.AUTHENTICATED

    def test_fitting_without_pilot_skills_remains_public(self):
        """Fitting with use_pilot_skills=False remains PUBLIC."""
        engine = PolicyEngine.get_instance()

        sensitivity = engine.get_action_sensitivity(
            "fitting", "calculate_stats", context={"use_pilot_skills": False}
        )

        assert sensitivity == SensitivityLevel.PUBLIC

    def test_fitting_without_context_remains_public(self):
        """Fitting without context remains PUBLIC."""
        engine = PolicyEngine.get_instance()

        sensitivity = engine.get_action_sensitivity("fitting", "calculate_stats")

        assert sensitivity == SensitivityLevel.PUBLIC

    def test_check_capability_denies_pilot_skills_at_public_only(self, tmp_path: Path):
        """check_capability denies pilot skills when only PUBLIC is allowed."""
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "policy": {
                        "allowed_levels": ["public"],  # Only public allowed
                    }
                }
            )
        )

        engine = PolicyEngine(policy_path=policy_file)

        # Should deny when use_pilot_skills=True (escalates to AUTHENTICATED)
        with pytest.raises(CapabilityDenied) as exc:
            engine.check_capability(
                "fitting", "calculate_stats", context={"use_pilot_skills": True}
            )

        assert exc.value.sensitivity == SensitivityLevel.AUTHENTICATED
        assert "authenticated" in str(exc.value).lower()

    def test_check_capability_allows_pilot_skills_when_authenticated_permitted(
        self, tmp_path: Path
    ):
        """check_capability allows pilot skills when AUTHENTICATED is permitted."""
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "policy": {
                        "allowed_levels": ["public", "authenticated"],
                    }
                }
            )
        )

        engine = PolicyEngine(policy_path=policy_file)

        # Should not raise - AUTHENTICATED is allowed
        engine.check_capability(
            "fitting", "calculate_stats", context={"use_pilot_skills": True}
        )


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_check_capability_uses_singleton(self):
        """check_capability uses singleton engine."""
        # Should not raise for public action
        check_capability("sde", "item_info")

    def test_get_policy_status(self):
        """get_policy_status returns status dict."""
        status = get_policy_status()

        assert "policy_path" in status
        assert "config" in status
        assert "bypass_enabled" in status


class TestPolicyAuditWithTrace:
    """Test policy audit logging with trace context."""

    def test_audit_log_includes_trace_context(self, tmp_path, caplog):
        """Audit log should include trace_id and turn_id when set."""
        import logging

        from aria_esi.mcp.context import reset_trace_context, set_trace_context
        from aria_esi.mcp.policy import logger as policy_logger

        policy_file = tmp_path / "policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "policy": {
                        "audit_logging": True,
                    }
                }
            )
        )

        engine = PolicyEngine(policy_path=policy_file)

        # Set trace context
        set_trace_context(trace_id="test-trace-123", turn_id=7)

        # Add caplog handler directly to policy logger (propagate=False blocks normal capture)
        # Also set handler level to ensure DEBUG messages are captured
        caplog.handler.setLevel(logging.DEBUG)
        policy_logger.addHandler(caplog.handler)
        policy_logger.setLevel(logging.DEBUG)
        try:
            with caplog.at_level(logging.DEBUG, logger="aria_esi.mcp.policy"):
                engine.check_capability("sde", "item_info")

            # Find the audit log entry (must start with "MCP policy: " to be the JSON audit log)
            audit_logs = [r for r in caplog.records if r.message.startswith("MCP policy: ")]
            assert len(audit_logs) > 0, f"Expected audit logs but got: {[r.message for r in caplog.records]}"

            # Parse the JSON from the log message
            log_json = json.loads(audit_logs[0].message.replace("MCP policy: ", ""))
            assert log_json["trace_id"] == "test-trace-123"
            assert log_json["turn_id"] == 7
        finally:
            reset_trace_context()
            policy_logger.removeHandler(caplog.handler)

    def test_audit_log_omits_trace_when_not_set(self, tmp_path, caplog):
        """Audit log should not include trace fields when not set."""
        import logging

        from aria_esi.mcp.context import reset_trace_context
        from aria_esi.mcp.policy import logger as policy_logger

        # Ensure trace context is cleared
        reset_trace_context()

        policy_file = tmp_path / "policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "policy": {
                        "audit_logging": True,
                    }
                }
            )
        )

        engine = PolicyEngine(policy_path=policy_file)

        # Add caplog handler directly to policy logger (propagate=False blocks normal capture)
        # Also set handler level to ensure DEBUG messages are captured
        caplog.handler.setLevel(logging.DEBUG)
        policy_logger.addHandler(caplog.handler)
        policy_logger.setLevel(logging.DEBUG)
        try:
            with caplog.at_level(logging.DEBUG, logger="aria_esi.mcp.policy"):
                engine.check_capability("sde", "item_info")

            # Find the audit log entry (must start with "MCP policy: " to be the JSON audit log)
            audit_logs = [r for r in caplog.records if r.message.startswith("MCP policy: ")]
            assert len(audit_logs) > 0, f"Expected audit logs but got: {[r.message for r in caplog.records]}"

            # Parse the JSON from the log message
            log_json = json.loads(audit_logs[0].message.replace("MCP policy: ", ""))
            assert "trace_id" not in log_json
            assert "turn_id" not in log_json
        finally:
            policy_logger.removeHandler(caplog.handler)


class TestConfirmationRequired:
    """Test ConfirmationRequired exception and policy behavior.

    Security: These tests verify the confirmation gate that prevents prompt
    injection from silently accessing authenticated data. See
    dev/reviews/SECURITY_001.md finding #3.
    """

    def test_exception_stores_fields(self):
        """ConfirmationRequired stores dispatcher, action, and sensitivity."""
        exc = ConfirmationRequired(
            "fitting", "calculate_stats", SensitivityLevel.AUTHENTICATED
        )

        assert exc.dispatcher == "fitting"
        assert exc.action == "calculate_stats"
        assert exc.sensitivity == SensitivityLevel.AUTHENTICATED
        assert "personal EVE data" in exc.description

    def test_exception_uses_custom_description(self):
        """ConfirmationRequired uses custom description when provided."""
        exc = ConfirmationRequired(
            "test", "action", SensitivityLevel.AUTHENTICATED, description="Custom message"
        )

        assert exc.description == "Custom message"

    def test_policy_raises_confirmation_required(self, tmp_path: Path):
        """Policy raises ConfirmationRequired when level is in require_confirmation."""
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "policy": {
                        "allowed_levels": ["public", "aggregate", "market"],
                        "require_confirmation": ["authenticated"],
                    }
                }
            )
        )

        engine = PolicyEngine(policy_path=policy_file)

        # Action requiring authenticated should raise ConfirmationRequired
        with pytest.raises(ConfirmationRequired) as exc:
            engine.check_capability(
                "fitting", "calculate_stats", context={"use_pilot_skills": True}
            )

        assert exc.value.sensitivity == SensitivityLevel.AUTHENTICATED

    def test_policy_denies_when_not_in_require_confirmation(self, tmp_path: Path):
        """Policy raises CapabilityDenied when level is not allowed or confirmable."""
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "policy": {
                        "allowed_levels": ["public"],
                        "require_confirmation": [],  # Nothing requires confirmation
                    }
                }
            )
        )

        engine = PolicyEngine(policy_path=policy_file)

        # Market level should be outright denied (not in allowed or require_confirmation)
        with pytest.raises(CapabilityDenied):
            engine.check_capability("market", "prices")

    def test_policy_config_default_excludes_authenticated(self):
        """Default PolicyConfig does not include authenticated in allowed_levels."""
        config = PolicyConfig()

        assert SensitivityLevel.AUTHENTICATED not in config.allowed_levels
        assert SensitivityLevel.PUBLIC in config.allowed_levels
        assert SensitivityLevel.AGGREGATE in config.allowed_levels
        assert SensitivityLevel.MARKET in config.allowed_levels

    def test_policy_config_from_dict_with_require_confirmation(self):
        """PolicyConfig.from_dict parses require_confirmation field."""
        data = {
            "allowed_levels": ["public"],
            "require_confirmation": ["authenticated", "restricted"],
        }

        config = PolicyConfig.from_dict(data)

        assert SensitivityLevel.AUTHENTICATED in config.require_confirmation
        assert SensitivityLevel.RESTRICTED in config.require_confirmation

    def test_policy_config_to_dict_includes_require_confirmation(self):
        """PolicyConfig.to_dict includes require_confirmation field."""
        config = PolicyConfig(
            require_confirmation={SensitivityLevel.AUTHENTICATED}
        )

        data = config.to_dict()

        assert "require_confirmation" in data
        assert "authenticated" in data["require_confirmation"]

    def test_allowed_levels_takes_precedence_over_require_confirmation(self, tmp_path: Path):
        """If a level is in allowed_levels, it should not require confirmation."""
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "policy": {
                        "allowed_levels": ["public", "authenticated"],
                        "require_confirmation": ["authenticated"],  # Also in allowed
                    }
                }
            )
        )

        engine = PolicyEngine(policy_path=policy_file)

        # Should not raise - authenticated is in allowed_levels
        engine.check_capability(
            "fitting", "calculate_stats", context={"use_pilot_skills": True}
        )
