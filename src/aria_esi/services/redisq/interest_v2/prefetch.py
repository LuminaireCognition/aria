"""
Prefetch Scorer for Interest Engine v2.

Implements prefetch-stage scoring for ESI fetch optimization.
The prefetch scorer uses only RedisQ data (system_id, victim ship_type_id,
victim character_id, etc.) to make early fetch/drop decisions.

Prefetch Modes:
- strict: Only fetch if prefetch-capable categories exceed threshold
- conservative: Fetch if upper bound could exceed threshold (accounts for unknowns)
- bypass: Always fetch (disable prefetch optimization)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .aggregation import calculate_prefetch_bounds
from .models import (
    CANONICAL_CATEGORIES,
    CategoryScore,
    SignalScore,
    rms_safety_factor,
)

if TYPE_CHECKING:
    from .config import InterestConfigV2
    from .engine import InterestEngineV2

logger = logging.getLogger(__name__)


@dataclass
class PrefetchDecision:
    """
    Result of prefetch evaluation.

    Contains the decision (fetch/drop), scores, and reasoning.
    """

    should_fetch: bool
    prefetch_score: float | None  # Score from prefetch-capable signals only
    lower_bound: float  # Conservative lower bound
    upper_bound: float  # Conservative upper bound
    threshold_used: float  # Effective threshold after safety adjustment
    mode: str  # strict, conservative, bypass
    reason: str  # Human-readable explanation
    prefetch_capable_count: int  # Number of prefetch-capable categories
    total_categories: int  # Total enabled categories

    # Rule overrides
    always_notify_triggered: bool = False
    always_ignore_triggered: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "should_fetch": self.should_fetch,
            "prefetch_score": (
                round(self.prefetch_score, 3) if self.prefetch_score is not None else None
            ),
            "lower_bound": round(self.lower_bound, 3),
            "upper_bound": round(self.upper_bound, 3),
            "threshold_used": round(self.threshold_used, 3),
            "mode": self.mode,
            "reason": self.reason,
            "prefetch_capable_count": self.prefetch_capable_count,
            "total_categories": self.total_categories,
            "always_notify_triggered": self.always_notify_triggered,
            "always_ignore_triggered": self.always_ignore_triggered,
        }


class PrefetchScorer:
    """
    Prefetch stage scorer for ESI fetch optimization.

    The prefetch scorer evaluates kills using only data available from
    RedisQ notifications (before ESI fetch). It determines whether a
    full ESI fetch is warranted based on:

    1. Prefetch-capable signal scores
    2. RMS safety margin for unknown signals
    3. Always-notify/always-ignore rule evaluation
    4. Configured prefetch mode

    Modes:
        strict: Only fetch if prefetch score alone exceeds threshold
        conservative: Fetch if upper bound (assuming unknowns score 1.0) exceeds threshold
        bypass: Always fetch (disable optimization)
        auto: Derive mode based on configuration
    """

    def __init__(
        self,
        config: InterestConfigV2,
        engine: InterestEngineV2,
    ) -> None:
        """
        Initialize prefetch scorer.

        Args:
            config: Interest configuration
            engine: Parent interest engine for signal scoring
        """
        self._config = config
        self._engine = engine
        self._effective_mode = self._derive_mode()

    def _derive_mode(self) -> str:
        """
        Auto-derive prefetch mode from configuration.

        Returns:
            Effective mode: strict, conservative, or bypass
        """
        explicit_mode = self._config.prefetch.mode

        if explicit_mode != "auto":
            return explicit_mode

        # Auto-derivation logic:
        # 1. No prefetch-capable categories → conservative
        # 2. Any always_notify rule requires post-fetch data → conservative
        # 3. Otherwise → strict

        from .providers.registry import get_provider_registry

        registry = get_provider_registry()

        # Check if we have any prefetch-capable categories
        has_prefetch_capable = False
        weights = self._engine._weights

        for category in CANONICAL_CATEGORIES:
            if weights.get(category, 0) <= 0:
                continue

            providers = registry.get_signals_for_category(category)
            if any(p.prefetch_capable for p in providers.values()):
                has_prefetch_capable = True
                break

        if not has_prefetch_capable:
            logger.debug("No prefetch-capable categories, using conservative mode")
            return "conservative"

        # Check always_notify rules
        for rule_id in self._config.rules.always_notify:
            provider = registry.get_rule(rule_id)
            if provider and not provider.prefetch_capable:
                logger.debug(
                    f"always_notify rule '{rule_id}' not prefetch-capable, using conservative"
                )
                return "conservative"

        return "strict"

    def evaluate(
        self,
        system_id: int,
        redisq_data: dict[str, Any] | None = None,
    ) -> PrefetchDecision:
        """
        Evaluate prefetch decision for a kill.

        Args:
            system_id: Solar system ID
            redisq_data: Optional RedisQ notification data for victim matching

        Returns:
            PrefetchDecision with fetch/drop recommendation
        """
        # Bypass mode - always fetch
        if self._effective_mode == "bypass":
            return PrefetchDecision(
                should_fetch=True,
                prefetch_score=None,
                lower_bound=0.0,
                upper_bound=1.0,
                threshold_used=0.0,
                mode="bypass",
                reason="Prefetch bypass enabled",
                prefetch_capable_count=0,
                total_categories=len(CANONICAL_CATEGORIES),
            )

        # Score prefetch-capable categories
        category_scores = self._score_prefetch_categories(system_id, redisq_data)

        # Count categories
        weights = self._engine._weights
        total_enabled = sum(1 for c in CANONICAL_CATEGORIES if weights.get(c, 0) > 0)
        prefetch_capable = sum(
            1 for c, cs in category_scores.items() if cs.prefetch_capable and cs.is_enabled
        )

        # Check rules first
        ignore_result = self._check_ignore_rules(system_id, redisq_data)
        if ignore_result:
            return PrefetchDecision(
                should_fetch=False,
                prefetch_score=None,
                lower_bound=0.0,
                upper_bound=0.0,
                threshold_used=0.0,
                mode=self._effective_mode,
                reason=f"Blocked by always_ignore: {ignore_result}",
                prefetch_capable_count=prefetch_capable,
                total_categories=total_enabled,
                always_ignore_triggered=True,
            )

        notify_result = self._check_notify_rules(system_id, redisq_data)
        if notify_result:
            return PrefetchDecision(
                should_fetch=True,
                prefetch_score=None,
                lower_bound=1.0,
                upper_bound=1.0,
                threshold_used=0.0,
                mode=self._effective_mode,
                reason=f"Triggered by always_notify: {notify_result}",
                prefetch_capable_count=prefetch_capable,
                total_categories=total_enabled,
                always_notify_triggered=True,
            )

        # Calculate bounds
        prefetch_score, lower_bound, upper_bound = calculate_prefetch_bounds(
            category_scores, weights
        )

        # Apply RMS safety margin for strict mode
        if self._effective_mode == "strict":
            safety_factor = rms_safety_factor(total_enabled)
            threshold = self._config.thresholds.digest * safety_factor
            threshold_used = threshold

            # Strict: only use prefetch-capable score
            if prefetch_score is not None and prefetch_score >= threshold:
                return PrefetchDecision(
                    should_fetch=True,
                    prefetch_score=prefetch_score,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    threshold_used=threshold_used,
                    mode="strict",
                    reason=f"Prefetch score {prefetch_score:.2f} >= threshold {threshold:.2f}",
                    prefetch_capable_count=prefetch_capable,
                    total_categories=total_enabled,
                )
            else:
                return PrefetchDecision(
                    should_fetch=False,
                    prefetch_score=prefetch_score,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    threshold_used=threshold_used,
                    mode="strict",
                    reason=f"Prefetch score {prefetch_score:.2f if prefetch_score else 0:.2f} < threshold {threshold:.2f}",
                    prefetch_capable_count=prefetch_capable,
                    total_categories=total_enabled,
                )

        else:  # conservative mode
            # Use digest threshold without safety margin
            threshold = self._config.thresholds.digest
            threshold_used = threshold

            # Conservative: use upper bound
            if upper_bound >= threshold:
                return PrefetchDecision(
                    should_fetch=True,
                    prefetch_score=prefetch_score,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    threshold_used=threshold_used,
                    mode="conservative",
                    reason=f"Upper bound {upper_bound:.2f} >= threshold {threshold:.2f}",
                    prefetch_capable_count=prefetch_capable,
                    total_categories=total_enabled,
                )
            else:
                return PrefetchDecision(
                    should_fetch=False,
                    prefetch_score=prefetch_score,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    threshold_used=threshold_used,
                    mode="conservative",
                    reason=f"Upper bound {upper_bound:.2f} < threshold {threshold:.2f}",
                    prefetch_capable_count=prefetch_capable,
                    total_categories=total_enabled,
                )

    def _score_prefetch_categories(
        self,
        system_id: int,
        redisq_data: dict[str, Any] | None,
    ) -> dict[str, CategoryScore]:
        """
        Score categories using only prefetch-capable signals.

        Args:
            system_id: Solar system ID
            redisq_data: Optional RedisQ data for victim matching

        Returns:
            Dict of category -> CategoryScore (prefetch only)
        """
        from .providers.registry import get_provider_registry

        registry = get_provider_registry()
        category_scores: dict[str, CategoryScore] = {}
        weights = self._engine._weights

        for category in CANONICAL_CATEGORIES:
            weight = weights.get(category, 0.0)

            cat_score = CategoryScore(
                category=category,
                score=0.0,
                weight=weight,
                match=False,
            )

            if weight <= 0:
                category_scores[category] = cat_score
                continue

            # Get signal configuration
            signals_config = {}
            if self._config.signals:
                signals_config = self._config.signals.get(category, {})

            # Score only prefetch-capable signals
            providers = registry.get_signals_for_category(category)
            signal_scores: dict[str, SignalScore] = {}

            for signal_name, provider in providers.items():
                if not provider.prefetch_capable:
                    # Skip non-prefetch signals - they'll be evaluated post-fetch
                    continue

                signal_config = signals_config.get(signal_name, {}) or {}
                merged_config = {**self._engine._context, **signal_config}

                # Add redisq data to config for victim matching
                if redisq_data:
                    merged_config["redisq_data"] = redisq_data

                try:
                    score = provider.score(None, system_id, merged_config)
                    signal_scores[signal_name] = score
                except Exception as e:
                    logger.warning(f"Prefetch signal {category}.{signal_name} failed: {e}")
                    signal_scores[signal_name] = SignalScore(
                        signal=signal_name,
                        score=0.0,
                        reason=f"Scoring error: {e}",
                        prefetch_capable=True,
                    )

            if signal_scores:
                cat_score.signals = signal_scores

                # Aggregate signal scores
                signal_sum = sum(s.score * s.weight for s in signal_scores.values())
                weight_sum = sum(s.weight for s in signal_scores.values())

                if weight_sum > 0:
                    cat_score.score = signal_sum / weight_sum
                    cat_score.match = cat_score.penalized_score >= 0.3

            # Category has mix of prefetch and post-fetch signals
            # Individual signals already marked with prefetch_capable flag

            category_scores[category] = cat_score

        return category_scores

    def _check_ignore_rules(
        self,
        system_id: int,
        redisq_data: dict[str, Any] | None,
    ) -> str | None:
        """
        Check always_ignore rules at prefetch stage.

        Returns:
            Rule ID if ignored, None otherwise
        """
        from .providers.registry import get_provider_registry

        registry = get_provider_registry()

        for rule_id in self._config.rules.always_ignore:
            provider = registry.get_rule(rule_id)
            if not provider:
                continue
            if not provider.prefetch_capable:
                continue

            try:
                match = provider.evaluate(None, system_id, self._engine._context)
                if match.matched:
                    return rule_id
            except Exception as e:
                logger.warning(f"Prefetch rule {rule_id} evaluation failed: {e}")

        return None

    def _check_notify_rules(
        self,
        system_id: int,
        redisq_data: dict[str, Any] | None,
    ) -> str | None:
        """
        Check always_notify rules at prefetch stage.

        Returns:
            Rule ID if matched, None otherwise
        """
        from .providers.registry import get_provider_registry

        registry = get_provider_registry()

        for rule_id in self._config.rules.always_notify:
            provider = registry.get_rule(rule_id)
            if not provider:
                continue
            if not provider.prefetch_capable:
                continue

            try:
                match = provider.evaluate(None, system_id, self._engine._context)
                if match.matched:
                    return rule_id
            except Exception as e:
                logger.warning(f"Prefetch rule {rule_id} evaluation failed: {e}")

        return None

    @property
    def effective_mode(self) -> str:
        """Get the effective prefetch mode (after auto-derivation)."""
        return self._effective_mode

    def get_stats(self) -> dict[str, Any]:
        """Get prefetch scorer statistics."""
        from .providers.registry import get_provider_registry

        registry = get_provider_registry()
        weights = self._engine._weights

        prefetch_capable_categories = []
        post_fetch_categories = []

        for category in CANONICAL_CATEGORIES:
            if weights.get(category, 0) <= 0:
                continue

            providers = registry.get_signals_for_category(category)
            all_prefetch = all(p.prefetch_capable for p in providers.values())

            if all_prefetch:
                prefetch_capable_categories.append(category)
            else:
                post_fetch_categories.append(category)

        total_enabled = len(prefetch_capable_categories) + len(post_fetch_categories)
        safety_factor = rms_safety_factor(total_enabled) if total_enabled > 0 else 1.0

        return {
            "effective_mode": self._effective_mode,
            "config_mode": self._config.prefetch.mode,
            "prefetch_capable_categories": prefetch_capable_categories,
            "post_fetch_categories": post_fetch_categories,
            "total_enabled": total_enabled,
            "rms_safety_factor": round(safety_factor, 3),
            "adjusted_threshold": round(self._config.thresholds.digest * safety_factor, 3),
        }


def create_prefetch_scorer(
    config: InterestConfigV2,
    engine: InterestEngineV2,
) -> PrefetchScorer:
    """
    Factory function to create a prefetch scorer.

    Args:
        config: Interest configuration
        engine: Parent interest engine

    Returns:
        Configured PrefetchScorer instance
    """
    return PrefetchScorer(config, engine)
