"""
Interest Engine v2 - Main Orchestrator.

The engine coordinates signal scoring, rule evaluation, and aggregation
to produce a final interest result for notification filtering.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .aggregation import aggregate_scores
from .config import InterestConfigV2
from .models import (
    CANONICAL_CATEGORIES,
    CategoryScore,
    InterestResultV2,
    NotificationTier,
    SignalScore,
)
from .rules.evaluator import RuleEvaluator

if TYPE_CHECKING:
    from ..models import ProcessedKill
    from .prefetch import PrefetchDecision, PrefetchScorer
    from .providers.base import SignalProvider

logger = logging.getLogger(__name__)


class InterestEngineV2:
    """
    Interest Engine v2 - Weighted signal-based notification filtering.

    The engine orchestrates:
    1. Signal scoring across configured categories
    2. Category score aggregation (RMS/linear/max)
    3. Rule evaluation (always_ignore, always_notify, gates)
    4. Threshold checking for notification tier assignment

    Usage:
        config = InterestConfigV2.from_dict(profile.interest)
        engine = InterestEngineV2(config, context)
        result = engine.calculate_interest(kill, system_id)
    """

    def __init__(
        self,
        config: InterestConfigV2,
        context: dict[str, Any] | None = None,
    ):
        """
        Initialize the engine with configuration.

        Args:
            config: InterestConfigV2 configuration
            context: Additional context (corp_id, alliance_id, get_distance, etc.)
        """
        self._config = config
        self._context = context or {}
        self._rule_evaluator = RuleEvaluator(config.rules, context)

        # Resolve effective weights (from preset + customize or explicit)
        self._weights = self._resolve_weights()

        # Cache signal providers
        self._signal_providers: dict[str, dict[str, SignalProvider]] = {}

        # Lazy-initialized prefetch scorer
        self._prefetch_scorer: PrefetchScorer | None = None

    def calculate_interest(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        is_prefetch: bool = False,
    ) -> InterestResultV2:
        """
        Calculate interest score for a kill.

        Args:
            kill: ProcessedKill with full data, or None for prefetch
            system_id: Solar system ID
            is_prefetch: Whether this is a prefetch evaluation

        Returns:
            InterestResultV2 with complete scoring breakdown
        """
        result = InterestResultV2(
            system_id=system_id,
            kill_id=kill.kill_id if kill else None,
            mode=self._config.mode,
            config_tier=self._config.tier,
            preset=self._config.preset,
            is_prefetch=is_prefetch,
            thresholds=self._config.thresholds.to_dict(),
        )

        # Step 1: Check always_ignore rules
        ignore_matches = self._rule_evaluator.evaluate_always_ignore(kill, system_id)
        result.always_ignore_matched = ignore_matches

        if any(m.matched for m in ignore_matches):
            result.tier = NotificationTier.FILTER
            result.interest = 0.0
            return result

        # Step 2: Check always_notify rules
        notify_matches = self._rule_evaluator.evaluate_always_notify(kill, system_id)
        result.always_notify_matched = notify_matches
        always_notify = any(m.matched for m in notify_matches)

        # Step 3: Score all configured categories
        category_scores = self._score_categories(kill, system_id)
        result.category_scores = category_scores

        # Step 4: Evaluate gates (if not bypassed by always_notify)
        if not always_notify:
            all_passed, any_passed, reason = self._rule_evaluator.evaluate_gates(category_scores)
            result.require_all_passed = all_passed
            result.require_any_passed = any_passed
            result.gate_failure_reason = reason

            if not all_passed or not any_passed:
                result.tier = NotificationTier.FILTER
                result.interest = 0.0
                return result

        # Step 5: Aggregate scores
        interest = aggregate_scores(category_scores, self._config.mode)
        result.interest = interest

        # Step 6: Determine tier
        if always_notify:
            # Bypass thresholds, but still respect tier ordering
            if interest >= self._config.thresholds.priority:
                result.tier = NotificationTier.PRIORITY
            else:
                result.tier = NotificationTier.NOTIFY
        else:
            result.tier = self._determine_tier(interest)

        return result

    def should_fetch(self, system_id: int, redisq_data: dict[str, Any] | None = None) -> bool:
        """
        Quick check whether a kill should be fetched from ESI.

        This uses the prefetch scorer for optimized early filtering.

        Args:
            system_id: Solar system ID
            redisq_data: Optional RedisQ notification data

        Returns:
            True if the kill should be fetched
        """
        decision = self.prefetch_evaluate(system_id, redisq_data)
        return decision.should_fetch

    def prefetch_evaluate(
        self,
        system_id: int,
        redisq_data: dict[str, Any] | None = None,
    ) -> PrefetchDecision:
        """
        Evaluate prefetch decision with full details.

        Uses the prefetch scorer to determine whether a kill should be
        fetched from ESI, with detailed reasoning.

        Args:
            system_id: Solar system ID
            redisq_data: Optional RedisQ notification data

        Returns:
            PrefetchDecision with fetch recommendation and reasoning
        """
        if self._prefetch_scorer is None:
            from .prefetch import PrefetchScorer

            self._prefetch_scorer = PrefetchScorer(self._config, self)
        return self._prefetch_scorer.evaluate(system_id, redisq_data)

    @property
    def prefetch_scorer(self) -> PrefetchScorer:
        """Get the prefetch scorer, creating if needed."""
        if self._prefetch_scorer is None:
            from .prefetch import PrefetchScorer

            self._prefetch_scorer = PrefetchScorer(self._config, self)
        return self._prefetch_scorer

    def _resolve_weights(self) -> dict[str, float]:
        """
        Resolve effective weights from config.

        Handles:
        - Explicit weights
        - Preset defaults
        - Customize slider adjustments
        """
        from .config import parse_customize_adjustment

        # Start with explicit weights or default to empty
        weights = dict(self._config.weights or {})

        # If using a preset, apply preset defaults for missing categories
        if self._config.preset and not self._config.weights:
            # Load preset weights (will be implemented in presets module)
            # For now, use balanced defaults
            for cat in CANONICAL_CATEGORIES:
                if cat not in weights:
                    weights[cat] = 0.5  # Default weight

        # Apply customize adjustments
        if self._config.customize:
            for cat, adjustment in self._config.customize.items():
                if cat in weights:
                    multiplier = parse_customize_adjustment(adjustment)
                    weights[cat] = weights[cat] * multiplier

        # Normalize weights if any are set
        if weights:
            total = sum(weights.values())
            if total > 0:
                # Note: We don't normalize to 1.0 here - that would
                # change the RMS behavior. Weights are relative.
                pass

        return weights

    def _score_categories(
        self,
        kill: ProcessedKill | None,
        system_id: int,
    ) -> dict[str, CategoryScore]:
        """
        Score all configured categories.

        Args:
            kill: ProcessedKill or None
            system_id: Solar system ID

        Returns:
            Dict of category name -> CategoryScore
        """
        from .providers.registry import get_provider_registry

        registry = get_provider_registry()
        category_scores: dict[str, CategoryScore] = {}

        for category in CANONICAL_CATEGORIES:
            weight = self._weights.get(category, 0.0)

            # Create category score object
            cat_score = CategoryScore(
                category=category,
                score=0.0,
                weight=weight,
                match=False,
            )

            if weight <= 0:
                # Category disabled
                category_scores[category] = cat_score
                continue

            # Get signal configuration for this category
            signals_config = {}
            if self._config.signals:
                signals_config = self._config.signals.get(category, {})

            # Score signals for this category
            signal_scores = self._score_category_signals(
                category, kill, system_id, signals_config, registry
            )

            if signal_scores:
                cat_score.signals = signal_scores

                # Aggregate signal scores within category
                signal_sum = sum(s.score * s.weight for s in signal_scores.values())
                weight_sum = sum(s.weight for s in signal_scores.values())

                if weight_sum > 0:
                    cat_score.score = signal_sum / weight_sum
                    # Determine match based on penalized score
                    cat_score.match = cat_score.penalized_score >= 0.3

            category_scores[category] = cat_score

        return category_scores

    def _score_category_signals(
        self,
        category: str,
        kill: ProcessedKill | None,
        system_id: int,
        signals_config: dict[str, Any],
        registry: Any,
    ) -> dict[str, SignalScore]:
        """
        Score all signals for a category.

        Args:
            category: Category name
            kill: ProcessedKill or None
            system_id: Solar system ID
            signals_config: Per-signal configuration
            registry: Provider registry

        Returns:
            Dict of signal name -> SignalScore
        """
        signal_scores: dict[str, SignalScore] = {}

        # Get all registered signals for this category
        providers = registry.get_signals_for_category(category)

        for signal_name, provider in providers.items():
            # Get signal-specific config
            signal_config = signals_config.get(signal_name, {})
            if signal_config is None:
                signal_config = {}

            # Merge with context
            merged_config = {**self._context, **signal_config}

            try:
                score = provider.score(kill, system_id, merged_config)
                signal_scores[signal_name] = score
            except Exception as e:
                logger.warning(f"Signal {category}.{signal_name} scoring failed: {e}")
                signal_scores[signal_name] = SignalScore(
                    signal=signal_name,
                    score=0.0,
                    reason=f"Scoring error: {e}",
                    prefetch_capable=provider.prefetch_capable,
                )

        return signal_scores

    def _determine_tier(self, interest: float) -> NotificationTier:
        """
        Determine notification tier from interest score.

        Args:
            interest: Final interest score

        Returns:
            NotificationTier enum value
        """
        thresholds = self._config.thresholds

        if interest >= thresholds.priority:
            return NotificationTier.PRIORITY
        elif interest >= thresholds.notify:
            return NotificationTier.NOTIFY
        elif interest >= thresholds.digest:
            return NotificationTier.DIGEST
        elif interest > 0:
            return NotificationTier.LOG_ONLY
        else:
            return NotificationTier.FILTER

    def validate(self) -> list[str]:
        """
        Validate engine configuration.

        Returns:
            List of validation errors
        """
        errors = self._config.validate()
        errors.extend(self._rule_evaluator.validate())
        return errors


def create_engine(
    interest_config: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> InterestEngineV2:
    """
    Factory function to create an interest engine from config dict.

    Args:
        interest_config: interest section from profile YAML
        context: Additional context for scoring

    Returns:
        Configured InterestEngineV2 instance
    """
    config = InterestConfigV2.from_dict(interest_config)
    return InterestEngineV2(config, context)
