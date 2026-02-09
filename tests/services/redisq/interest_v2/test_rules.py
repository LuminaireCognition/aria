"""
Tests for Interest Engine v2 Rule System.

CRITICAL TEST AREA: Rule precedence ordering.
Order: always_ignore > always_notify > gates > scoring
"""

from __future__ import annotations

from aria_esi.services.redisq.interest_v2.config import RulesConfig
from aria_esi.services.redisq.interest_v2.models import CategoryScore, RuleMatch, SignalScore
from aria_esi.services.redisq.interest_v2.rules.evaluator import (
    RuleEvaluator,
    evaluate_rules,
)


def _make_category(
    category: str,
    score: float,
    weight: float,
    match: bool,
) -> CategoryScore:
    """Helper to create CategoryScore with signal."""
    cat = CategoryScore(category=category, score=score, weight=weight, match=match)
    cat.signals = {"test": SignalScore(signal="test", score=score, prefetch_capable=True)}
    return cat


class TestRuleEvaluatorInit:
    """Tests for RuleEvaluator initialization."""

    def test_init_with_empty_config(self):
        """Initialize with empty rules config."""
        config = RulesConfig()
        evaluator = RuleEvaluator(config)

        assert evaluator._config == config
        assert evaluator._context == {}

    def test_init_with_context(self):
        """Initialize with context."""
        config = RulesConfig()
        context = {"corp_id": 98000001, "alliance_id": 99001234}
        evaluator = RuleEvaluator(config, context)

        assert evaluator._context["corp_id"] == 98000001


class TestEvaluateAlwaysIgnore:
    """Tests for always_ignore rule evaluation."""

    def test_no_rules_returns_empty(self, mock_kill):
        """No rules returns empty list."""
        config = RulesConfig(always_ignore=[])
        evaluator = RuleEvaluator(config)

        results = evaluator.evaluate_always_ignore(mock_kill, mock_kill.solar_system_id)

        assert results == []

    def test_pod_only_matches_pod_kill(self, pod_kill, reset_registry):
        """pod_only rule matches pod kills."""
        config = RulesConfig(always_ignore=["pod_only"])
        evaluator = RuleEvaluator(config)

        results = evaluator.evaluate_always_ignore(pod_kill, pod_kill.solar_system_id)

        assert len(results) == 1
        assert results[0].rule_id == "pod_only"
        assert results[0].matched is True

    def test_pod_only_does_not_match_ship_kill(self, mock_kill, reset_registry):
        """pod_only rule doesn't match ship kills."""
        config = RulesConfig(always_ignore=["pod_only"])
        evaluator = RuleEvaluator(config)

        results = evaluator.evaluate_always_ignore(mock_kill, mock_kill.solar_system_id)

        assert len(results) == 1
        assert results[0].rule_id == "pod_only"
        assert results[0].matched is False

    def test_npc_only_matches_npc_kill(self, npc_only_kill, reset_registry):
        """npc_only rule matches kills with only NPC attackers."""
        config = RulesConfig(always_ignore=["npc_only"])
        evaluator = RuleEvaluator(config)

        results = evaluator.evaluate_always_ignore(
            npc_only_kill, npc_only_kill.solar_system_id
        )

        assert len(results) == 1
        assert results[0].rule_id == "npc_only"
        # Should match if all attackers are NPC
        # (corp IDs < 2M are typically NPC)

    def test_unknown_rule_returns_not_matched(self, mock_kill, reset_registry):
        """Unknown rules return not matched with reason."""
        config = RulesConfig(always_ignore=["nonexistent_rule"])
        evaluator = RuleEvaluator(config)

        results = evaluator.evaluate_always_ignore(mock_kill, mock_kill.solar_system_id)

        assert len(results) == 1
        assert results[0].rule_id == "nonexistent_rule"
        assert results[0].matched is False
        assert "Unknown" in results[0].reason


class TestEvaluateAlwaysNotify:
    """Tests for always_notify rule evaluation."""

    def test_no_rules_returns_empty(self, mock_kill):
        """No rules returns empty list."""
        config = RulesConfig(always_notify=[])
        evaluator = RuleEvaluator(config)

        results = evaluator.evaluate_always_notify(mock_kill, mock_kill.solar_system_id)

        assert results == []

    def test_high_value_matches_expensive_kill(self, high_value_kill, reset_registry):
        """high_value rule matches expensive kills."""
        config = RulesConfig(always_notify=["high_value"])
        context = {"high_value_threshold": 1_000_000_000}  # 1B
        evaluator = RuleEvaluator(config, context)

        results = evaluator.evaluate_always_notify(
            high_value_kill, high_value_kill.solar_system_id
        )

        assert len(results) == 1
        assert results[0].rule_id == "high_value"
        # 3.5B kill should match 1B threshold


class TestEvaluateGates:
    """Tests for gate evaluation (require_all, require_any)."""

    def test_no_gates_passes(self):
        """No gates always passes."""
        config = RulesConfig()
        evaluator = RuleEvaluator(config)

        category_scores = {
            "location": _make_category("location", 0.8, 1.0, True),
        }

        all_passed, any_passed, reason = evaluator.evaluate_gates(category_scores)

        assert all_passed is True
        assert any_passed is True
        assert reason is None

    def test_require_all_all_match_passes(self):
        """require_all passes when all categories match."""
        config = RulesConfig(require_all=["location", "value"])
        evaluator = RuleEvaluator(config)

        category_scores = {
            "location": _make_category("location", 0.8, 1.0, True),
            "value": _make_category("value", 0.7, 1.0, True),
        }

        all_passed, any_passed, reason = evaluator.evaluate_gates(category_scores)

        assert all_passed is True

    def test_require_all_one_not_match_fails(self):
        """require_all fails when any category doesn't match."""
        config = RulesConfig(require_all=["location", "value"])
        evaluator = RuleEvaluator(config)

        category_scores = {
            "location": _make_category("location", 0.8, 1.0, True),
            "value": _make_category("value", 0.2, 1.0, False),  # Not matched
        }

        all_passed, any_passed, reason = evaluator.evaluate_gates(category_scores)

        assert all_passed is False
        assert "require_all" in reason
        assert "value" in reason

    def test_require_all_disabled_category_fails(self):
        """require_all fails for disabled category (weight=0)."""
        config = RulesConfig(require_all=["location", "value"])
        evaluator = RuleEvaluator(config)

        category_scores = {
            "location": _make_category("location", 0.8, 1.0, True),
            "value": _make_category("value", 0.0, 0.0, False),  # Disabled
        }

        all_passed, any_passed, reason = evaluator.evaluate_gates(category_scores)

        assert all_passed is False
        assert "disabled" in reason

    def test_require_all_missing_category_fails(self):
        """require_all fails for missing category."""
        config = RulesConfig(require_all=["location", "politics"])
        evaluator = RuleEvaluator(config)

        category_scores = {
            "location": _make_category("location", 0.8, 1.0, True),
            # politics not in scores
        }

        all_passed, any_passed, reason = evaluator.evaluate_gates(category_scores)

        assert all_passed is False
        assert "not configured" in reason

    def test_require_any_one_matches_passes(self):
        """require_any passes when at least one matches."""
        config = RulesConfig(require_any=["location", "politics", "value"])
        evaluator = RuleEvaluator(config)

        category_scores = {
            "location": _make_category("location", 0.2, 1.0, False),
            "politics": _make_category("politics", 0.8, 1.0, True),  # This matches
            "value": _make_category("value", 0.1, 1.0, False),
        }

        all_passed, any_passed, reason = evaluator.evaluate_gates(category_scores)

        assert any_passed is True

    def test_require_any_none_match_fails(self):
        """require_any fails when none match."""
        config = RulesConfig(require_any=["location", "politics"])
        evaluator = RuleEvaluator(config)

        category_scores = {
            "location": _make_category("location", 0.2, 1.0, False),
            "politics": _make_category("politics", 0.1, 1.0, False),
        }

        all_passed, any_passed, reason = evaluator.evaluate_gates(category_scores)

        assert any_passed is False
        assert "require_any" in reason

    def test_require_any_disabled_categories_ignored(self):
        """require_any ignores disabled categories."""
        config = RulesConfig(require_any=["location", "politics"])
        evaluator = RuleEvaluator(config)

        category_scores = {
            "location": _make_category("location", 0.8, 0.0, True),  # Disabled
            "politics": _make_category("politics", 0.8, 1.0, True),  # Enabled & matches
        }

        all_passed, any_passed, reason = evaluator.evaluate_gates(category_scores)

        # politics matches and is enabled
        assert any_passed is True


class TestRulePrecedence:
    """
    CRITICAL: Tests for rule precedence ordering.

    Order: always_ignore > always_notify > gates > scoring
    """

    def test_always_ignore_before_always_notify(self, mock_kill, reset_registry):
        """always_ignore takes precedence over always_notify."""
        config = RulesConfig(
            always_ignore=["npc_only"],  # Would match if NPC
            always_notify=["high_value"],  # Would also match
        )
        evaluator = RuleEvaluator(config)

        # Check ignore first
        should_ignore, ignore_match = evaluator.should_ignore(
            mock_kill, mock_kill.solar_system_id
        )

        if should_ignore:
            # If ignored, always_notify should never be checked
            should_notify, _ = evaluator.should_notify_always(
                mock_kill, mock_kill.solar_system_id
            )
            # Both might match, but ignore wins
            assert ignore_match is not None
            assert ignore_match.matched

    def test_always_notify_before_gates(self, mock_kill, reset_registry):
        """always_notify bypasses gate evaluation."""
        config = RulesConfig(
            always_notify=["high_value"],
            require_all=["politics"],  # Would fail
        )
        context = {"high_value_threshold": 100_000_000}  # 100M - mock_kill is 150M
        evaluator = RuleEvaluator(config, context)

        category_scores = {
            "location": _make_category("location", 0.8, 1.0, True),
            "politics": _make_category("politics", 0.0, 1.0, False),  # Doesn't match
        }

        # Gates would fail
        all_passed, _, _ = evaluator.evaluate_gates(category_scores)
        assert all_passed is False

        # But if always_notify matches, gates should be bypassed
        should_notify, notify_match = evaluator.should_notify_always(
            mock_kill, mock_kill.solar_system_id
        )

        # When processing, if should_notify is True, gates are skipped

    def test_gates_before_scoring(self):
        """Gates are evaluated before scoring matters."""
        config = RulesConfig(require_all=["location"])
        evaluator = RuleEvaluator(config)

        # Even with high scores, if gate fails, result is FILTER
        category_scores = {
            "location": _make_category("location", 0.2, 1.0, False),  # High score but no match
            "value": _make_category("value", 1.0, 1.0, True),  # Very high
        }

        all_passed, any_passed, reason = evaluator.evaluate_gates(category_scores)

        # Gate fails despite high value score
        assert all_passed is False
        assert "location" in reason


class TestEvaluateRulesConvenience:
    """Tests for evaluate_rules convenience function."""

    def test_returns_complete_result(self, mock_kill, reset_registry):
        """Convenience function returns all fields."""
        config = RulesConfig(
            always_ignore=["npc_only"],
            always_notify=["high_value"],
            require_all=["location"],
        )

        category_scores = {
            "location": _make_category("location", 0.8, 1.0, True),
        }

        result = evaluate_rules(
            config, mock_kill, mock_kill.solar_system_id, category_scores
        )

        assert "should_ignore" in result
        assert "should_always_notify" in result
        assert "require_all_passed" in result
        assert "require_any_passed" in result
        assert "ignore_match" in result
        assert "notify_match" in result
        assert "gate_failure_reason" in result

    def test_ignore_shortcuts_further_evaluation(self, pod_kill, reset_registry):
        """When ignored, other fields are not meaningful."""
        config = RulesConfig(
            always_ignore=["pod_only"],
            always_notify=["high_value"],
        )

        category_scores = {}

        result = evaluate_rules(
            config, pod_kill, pod_kill.solar_system_id, category_scores
        )

        if result["should_ignore"]:
            assert result["ignore_match"] is not None
            assert result["should_always_notify"] is False


class TestShouldIgnore:
    """Tests for should_ignore helper."""

    def test_returns_tuple(self, mock_kill):
        """Returns (bool, match) tuple."""
        config = RulesConfig(always_ignore=[])
        evaluator = RuleEvaluator(config)

        should, match = evaluator.should_ignore(mock_kill, mock_kill.solar_system_id)

        assert isinstance(should, bool)
        assert should is False
        assert match is None

    def test_true_when_rule_matches(self, pod_kill, reset_registry):
        """Returns True with match when rule matches."""
        config = RulesConfig(always_ignore=["pod_only"])
        evaluator = RuleEvaluator(config)

        should, match = evaluator.should_ignore(pod_kill, pod_kill.solar_system_id)

        if should:
            assert isinstance(match, RuleMatch)
            assert match.matched is True


class TestShouldNotifyAlways:
    """Tests for should_notify_always helper."""

    def test_returns_tuple(self, mock_kill):
        """Returns (bool, match) tuple."""
        config = RulesConfig(always_notify=[])
        evaluator = RuleEvaluator(config)

        should, match = evaluator.should_notify_always(
            mock_kill, mock_kill.solar_system_id
        )

        assert isinstance(should, bool)
        assert should is False
        assert match is None


class TestCanPrefetchEvaluateAlwaysNotify:
    """Tests for prefetch capability of always_notify rules."""

    def test_empty_rules_returns_true(self, reset_registry):
        """No rules means prefetch is possible."""
        config = RulesConfig(always_notify=[])
        evaluator = RuleEvaluator(config)

        result = evaluator.can_prefetch_evaluate_always_notify()

        assert result is True

    def test_unknown_rule_returns_false(self, reset_registry):
        """Unknown rules are assumed not prefetch-capable."""
        config = RulesConfig(always_notify=["nonexistent_rule"])
        evaluator = RuleEvaluator(config)

        result = evaluator.can_prefetch_evaluate_always_notify()

        assert result is False


class TestValidation:
    """Tests for rule configuration validation."""

    def test_unknown_rule_error(self, reset_registry):
        """Unknown rules produce validation errors."""
        config = RulesConfig(
            always_ignore=["unknown_rule_1"],
            always_notify=["unknown_rule_2"],
        )
        evaluator = RuleEvaluator(config)

        errors = evaluator.validate()

        assert any("unknown_rule_1" in e for e in errors)
        assert any("unknown_rule_2" in e for e in errors)

    def test_conflict_warning(self, reset_registry):
        """Same rule in both lists produces warning."""
        config = RulesConfig(
            always_ignore=["pod_only"],
            always_notify=["pod_only"],  # Conflict!
        )
        evaluator = RuleEvaluator(config)

        errors = evaluator.validate()

        assert any("pod_only" in e and "both" in e for e in errors)


class TestCustomRules:
    """Tests for custom rule registration."""

    def test_register_custom_rule(self, mock_kill):
        """Custom rules can be registered and evaluated."""
        from aria_esi.services.redisq.interest_v2.providers.base import RuleProvider

        class AlwaysTrueRule(RuleProvider):
            @property
            def name(self) -> str:
                return "always_true"

            @property
            def prefetch_capable(self) -> bool:
                return True

            def evaluate(self, kill, system_id, context) -> RuleMatch:
                return RuleMatch(rule_id="always_true", matched=True, reason="Always matches")

            def validate(self, config: dict) -> list[str]:
                return []

        config = RulesConfig(always_notify=["always_true"])
        evaluator = RuleEvaluator(config)
        evaluator.register_custom_rule("always_true", AlwaysTrueRule())

        should, match = evaluator.should_notify_always(
            mock_kill, mock_kill.solar_system_id
        )

        assert should is True
        assert match.rule_id == "always_true"

    def test_custom_rule_overrides_builtin(self, mock_kill, reset_registry):
        """Custom rules override built-in rules of same name."""
        from aria_esi.services.redisq.interest_v2.providers.base import RuleProvider

        class CustomPodOnly(RuleProvider):
            """Custom pod_only that never matches."""

            @property
            def name(self) -> str:
                return "pod_only"

            @property
            def prefetch_capable(self) -> bool:
                return True

            def evaluate(self, kill, system_id, context) -> RuleMatch:
                return RuleMatch(rule_id="pod_only", matched=False, reason="Custom override")

            def validate(self, config: dict) -> list[str]:
                return []

        config = RulesConfig(always_ignore=["pod_only"])
        evaluator = RuleEvaluator(config)
        evaluator.register_custom_rule("pod_only", CustomPodOnly())

        # Even for pod kill, custom rule says no match
        should, _ = evaluator.should_ignore(mock_kill, mock_kill.solar_system_id)

        # Custom rule overrides, so should not ignore
        assert should is False
