"""
Rule Evaluator for Interest Engine v2.

Handles rule precedence and evaluation order:
1. always_ignore wins (if matched, drop notification)
2. always_notify bypasses gates and thresholds
3. require_all / require_any gates
4. Interest scoring + thresholds
5. Rate limits
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..models import CategoryScore, RuleMatch

if TYPE_CHECKING:
    from ...models import ProcessedKill
    from ..config import RulesConfig
    from ..providers.base import RuleProvider

logger = logging.getLogger(__name__)


class RuleEvaluator:
    """
    Evaluates hard rules against kills.

    Manages rule loading, caching, and precedence enforcement.
    """

    def __init__(self, config: RulesConfig, context: dict[str, Any] | None = None):
        """
        Initialize rule evaluator.

        Args:
            config: Rules configuration from profile
            context: Context for rule evaluation (corp_id, alliance_id, etc.)
        """
        self._config = config
        self._context = context or {}
        self._custom_rules: dict[str, RuleProvider] = {}

    def evaluate_always_ignore(
        self,
        kill: ProcessedKill | None,
        system_id: int,
    ) -> list[RuleMatch]:
        """
        Evaluate always_ignore rules.

        Args:
            kill: ProcessedKill or None for prefetch
            system_id: Solar system ID

        Returns:
            List of RuleMatch for each rule (matched or not)
        """
        results = []

        for rule_id in self._config.always_ignore:
            match = self._evaluate_rule(rule_id, kill, system_id)
            results.append(match)

        return results

    def evaluate_always_notify(
        self,
        kill: ProcessedKill | None,
        system_id: int,
    ) -> list[RuleMatch]:
        """
        Evaluate always_notify rules.

        Args:
            kill: ProcessedKill or None for prefetch
            system_id: Solar system ID

        Returns:
            List of RuleMatch for each rule
        """
        results = []

        for rule_id in self._config.always_notify:
            match = self._evaluate_rule(rule_id, kill, system_id)
            results.append(match)

        return results

    def evaluate_gates(
        self,
        category_scores: dict[str, CategoryScore],
    ) -> tuple[bool, bool, str | None]:
        """
        Evaluate require_all and require_any gates.

        Args:
            category_scores: Category scores with match flags

        Returns:
            (require_all_passed, require_any_passed, failure_reason)
        """
        require_all_passed = True
        require_any_passed = True
        failure_reason = None

        # Evaluate require_all (all listed categories must match)
        if self._config.require_all:
            for cat_name in self._config.require_all:
                if cat_name not in category_scores:
                    require_all_passed = False
                    failure_reason = f"require_all: category '{cat_name}' not configured"
                    break

                cat = category_scores[cat_name]
                if not cat.is_enabled:
                    require_all_passed = False
                    failure_reason = f"require_all: category '{cat_name}' is disabled (weight=0)"
                    break

                if not cat.match:
                    require_all_passed = False
                    failure_reason = f"require_all: category '{cat_name}' did not match"
                    break

        # Evaluate require_any (at least one must match)
        if self._config.require_any:
            any_matched = False
            for cat_name in self._config.require_any:
                if cat_name not in category_scores:
                    continue

                cat = category_scores[cat_name]
                if cat.is_enabled and cat.match:
                    any_matched = True
                    break

            if not any_matched:
                require_any_passed = False
                if not failure_reason:
                    failure_reason = (
                        f"require_any: no category matched from {self._config.require_any}"
                    )

        return require_all_passed, require_any_passed, failure_reason

    def should_ignore(
        self,
        kill: ProcessedKill | None,
        system_id: int,
    ) -> tuple[bool, RuleMatch | None]:
        """
        Check if any always_ignore rule matches.

        Args:
            kill: ProcessedKill or None
            system_id: Solar system ID

        Returns:
            (should_ignore, matched_rule)
        """
        matches = self.evaluate_always_ignore(kill, system_id)

        for match in matches:
            if match.matched:
                return True, match

        return False, None

    def should_notify_always(
        self,
        kill: ProcessedKill | None,
        system_id: int,
    ) -> tuple[bool, RuleMatch | None]:
        """
        Check if any always_notify rule matches.

        Note: always_ignore takes precedence and should be checked first.

        Args:
            kill: ProcessedKill or None
            system_id: Solar system ID

        Returns:
            (should_always_notify, matched_rule)
        """
        matches = self.evaluate_always_notify(kill, system_id)

        for match in matches:
            if match.matched:
                return True, match

        return False, None

    def can_prefetch_evaluate_always_notify(self) -> bool:
        """
        Check if all always_notify rules can be evaluated at prefetch.

        If any rule is not prefetch-capable, conservative prefetch mode
        should be used to avoid missing notifications.
        """
        from ..providers.registry import get_provider_registry

        registry = get_provider_registry()

        for rule_id in self._config.always_notify:
            # Check custom rules first
            if rule_id in self._custom_rules:
                if not self._custom_rules[rule_id].prefetch_capable:
                    return False
                continue

            # Check built-in rules
            provider = registry.get_rule(rule_id)
            if provider is None:
                # Unknown rule - assume not prefetch capable
                return False
            if not provider.prefetch_capable:
                return False

        return True

    def _evaluate_rule(
        self,
        rule_id: str,
        kill: ProcessedKill | None,
        system_id: int,
    ) -> RuleMatch:
        """
        Evaluate a single rule by ID.

        Args:
            rule_id: Rule identifier
            kill: ProcessedKill or None
            system_id: Solar system ID

        Returns:
            RuleMatch with result
        """
        from ..providers.registry import get_provider_registry

        # Check custom rules first
        if rule_id in self._custom_rules:
            provider = self._custom_rules[rule_id]
            return provider.evaluate(kill, system_id, self._context)

        # Check built-in rules
        registry = get_provider_registry()
        builtin_provider = registry.get_rule(rule_id)

        if builtin_provider is None:
            logger.warning(f"Unknown rule: {rule_id}")
            return RuleMatch(
                rule_id=rule_id,
                matched=False,
                reason=f"Unknown rule: {rule_id}",
            )

        return builtin_provider.evaluate(kill, system_id, self._context)

    def register_custom_rule(self, rule_id: str, provider: RuleProvider) -> None:
        """
        Register a custom rule provider.

        Args:
            rule_id: Rule identifier
            provider: RuleProvider instance
        """
        self._custom_rules[rule_id] = provider

    def validate(self) -> list[str]:
        """
        Validate rule configuration.

        Returns:
            List of validation errors
        """
        errors = []
        from ..providers.registry import get_provider_registry

        registry = get_provider_registry()

        # Validate always_ignore rules exist
        for rule_id in self._config.always_ignore:
            if rule_id not in self._custom_rules:
                provider = registry.get_rule(rule_id)
                if provider is None:
                    errors.append(f"Unknown rule in always_ignore: {rule_id}")

        # Validate always_notify rules exist
        for rule_id in self._config.always_notify:
            if rule_id not in self._custom_rules:
                provider = registry.get_rule(rule_id)
                if provider is None:
                    errors.append(f"Unknown rule in always_notify: {rule_id}")

        # Check for conflicts (same rule in both)
        conflicts = set(self._config.always_ignore) & set(self._config.always_notify)
        for rule_id in conflicts:
            errors.append(
                f"Rule '{rule_id}' in both always_ignore and always_notify. "
                "always_ignore takes precedence, but this may be unintended."
            )

        return errors


def evaluate_rules(
    config: RulesConfig,
    kill: ProcessedKill | None,
    system_id: int,
    category_scores: dict[str, CategoryScore],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Convenience function to evaluate all rules.

    Args:
        config: Rules configuration
        kill: ProcessedKill or None
        system_id: Solar system ID
        category_scores: Category scores for gate evaluation
        context: Additional context for rules

    Returns:
        Dict with:
        - should_ignore: bool
        - should_always_notify: bool
        - require_all_passed: bool
        - require_any_passed: bool
        - ignore_match: RuleMatch or None
        - notify_match: RuleMatch or None
        - gate_failure_reason: str or None
    """
    evaluator = RuleEvaluator(config, context)

    # Check always_ignore first (highest precedence)
    should_ignore, ignore_match = evaluator.should_ignore(kill, system_id)

    if should_ignore:
        return {
            "should_ignore": True,
            "should_always_notify": False,
            "require_all_passed": True,
            "require_any_passed": True,
            "ignore_match": ignore_match,
            "notify_match": None,
            "gate_failure_reason": None,
        }

    # Check always_notify (bypasses gates if matched)
    should_always_notify, notify_match = evaluator.should_notify_always(kill, system_id)

    # Evaluate gates (only matters if not always_notify)
    require_all_passed, require_any_passed, gate_reason = evaluator.evaluate_gates(category_scores)

    return {
        "should_ignore": False,
        "should_always_notify": should_always_notify,
        "require_all_passed": require_all_passed,
        "require_any_passed": require_any_passed,
        "ignore_match": None,
        "notify_match": notify_match,
        "gate_failure_reason": gate_reason,
    }
