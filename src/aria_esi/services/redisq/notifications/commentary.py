"""
LLM Commentary Generation for Discord Notifications.

Generates tactical commentary using Claude API when patterns
warrant additional insight.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from ....core.logging import get_logger

# Import shared types to avoid circular imports with prompts.py
from .types import (
    DEFAULT_MAX_CHARS,
    SEVERITY_STRESS_MAP,
    STRESS_SEVERITY_ORDER,
    CommentaryStyle,
    PatternSeverity,
    StressLevel,
)

if TYPE_CHECKING:
    from .llm_providers._protocol import LLMProvider
    from .patterns import PatternContext
    from .persona import PersonaLoader

logger = get_logger(__name__)

# Re-export types for backward compatibility
__all__ = [
    "CommentaryStyle",
    "StressLevel",
    "PatternSeverity",
    "DEFAULT_MAX_CHARS",
    "PATTERN_STRESS_MAP",
    "STRESS_SEVERITY",
    "CommentaryMetrics",
    "CommentaryGenerator",
    "create_commentary_generator",
    "NO_COMMENTARY_SIGNAL",
    "DEFAULT_MODEL",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TIMEOUT_MS",
    "COST_PER_1K_INPUT_TOKENS",
    "COST_PER_1K_OUTPUT_TOKENS",
    "AVG_INPUT_TOKENS",
    "AVG_OUTPUT_TOKENS",
    "get_stress_level",
    "validate_preserved_tokens",
    "extract_protected_tokens",
]

# =============================================================================
# Constants
# =============================================================================

# Signal for LLM to indicate no commentary is needed
NO_COMMENTARY_SIGNAL = "NO_COMMENTARY"

# Default model configuration
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 100
DEFAULT_TIMEOUT_MS = 3000

# Cost estimation (approximate, for tracking)
COST_PER_1K_INPUT_TOKENS = 0.00025  # Haiku input
COST_PER_1K_OUTPUT_TOKENS = 0.00125  # Haiku output
AVG_INPUT_TOKENS = 500  # Typical prompt size
AVG_OUTPUT_TOKENS = 50  # Typical response size


# =============================================================================
# Stress Level Mapping
# =============================================================================

# Pattern type → stress level mapping (legacy, for backward compatibility)
# New patterns should use PatternSeverity instead
PATTERN_STRESS_MAP: dict[str, StressLevel] = {
    "repeat_attacker": StressLevel.MODERATE,
    "gank_rotation": StressLevel.HIGH,
    "unusual_victim": StressLevel.MODERATE,
    "war_target_activity": StressLevel.HIGH,
    "npc_faction_activity": StressLevel.LOW,
}

# Backward compatibility alias
STRESS_SEVERITY: dict[StressLevel, int] = STRESS_SEVERITY_ORDER


def get_stress_level(pattern_context: PatternContext) -> StressLevel:
    """
    Derive stress level from pattern context.

    Uses severity metadata when available, falling back to pattern-type map.
    Always selects the highest-severity stress level when multiple patterns exist.

    Args:
        pattern_context: Pattern detection results

    Returns:
        Appropriate stress level for the patterns
    """
    if not pattern_context.patterns:
        return StressLevel.MODERATE

    highest_severity = -1
    stress_level = StressLevel.MODERATE

    for pattern in pattern_context.patterns:
        # Try severity-based derivation first (future-proof)
        if pattern.severity is not None:
            pattern_stress = SEVERITY_STRESS_MAP.get(pattern.severity, StressLevel.MODERATE)
        else:
            # Fall back to pattern-type map (backward compatible)
            pattern_stress = PATTERN_STRESS_MAP.get(pattern.pattern_type, StressLevel.MODERATE)

        severity_order = STRESS_SEVERITY_ORDER[pattern_stress]
        if severity_order > highest_severity:
            highest_severity = severity_order
            stress_level = pattern_stress

    return stress_level


# =============================================================================
# Protected Token Validation
# =============================================================================


def extract_protected_tokens(
    pattern_context: PatternContext,
    system_display: str | None = None,
    ship_display: str | None = None,
) -> set[str]:
    """
    Extract tokens that must be preserved in commentary output.

    Protected tokens include:
    - System display string (passed explicitly from manager)
    - Ship display string (passed explicitly from manager)
    - Additional names from pattern context dicts (e.g., faction_display)

    Display strings may be resolved names ("Tama", "Vexor") or fallback
    strings ("System 30002813", "Ship 17740", "Capsule") depending on
    whether SDE lookup succeeded. Both forms are protected.

    Note: ISK values are intentionally excluded because the abbreviated format
    (e.g., "2.1B") involves lossy rounding, making exact string matching
    impractical. Prompt-based preservation is sufficient for numeric values.

    Args:
        pattern_context: Pattern detection results containing kill data
        system_display: System display string used in notification_text
        ship_display: Ship display string used in notification_text

    Returns:
        Set of tokens that must appear unchanged in output
    """
    tokens: set[str] = set()

    # Add display strings passed from manager
    if system_display:
        tokens.add(system_display)
    if ship_display:
        tokens.add(ship_display)

    # Extract additional names from pattern context dicts
    for pattern in pattern_context.patterns:
        ctx = pattern.context
        if "system_name" in ctx and ctx["system_name"]:
            tokens.add(ctx["system_name"])
        if "ship_name" in ctx and ctx["ship_name"]:
            tokens.add(ctx["ship_name"])
        if "faction_display" in ctx and ctx["faction_display"]:
            tokens.add(ctx["faction_display"])

    return tokens


def validate_preserved_tokens(
    output: str,
    pattern_context: PatternContext,
    protected_tokens: set[str] | None = None,
    system_display: str | None = None,
    ship_display: str | None = None,
) -> bool:
    """
    Validate that critical tokens from context appear unchanged in output.

    This is a whitelist check: if a protected value is referenced but not
    present verbatim, the output is considered invalid. The validator is
    cheap (string containment) and deterministic, providing a hard guarantee
    that prompt guidance alone cannot offer.

    Note: This check is conservative - it only fails if a token that SHOULD
    appear in the output is corrupted (case mismatch). If the LLM simply
    doesn't mention a value, that's acceptable (NO_COMMENTARY is always an option).

    Protected tokens are display strings (system names, ship names, faction
    names, or their fallbacks). ISK values are excluded because the abbreviated
    format involves lossy rounding, making exact string matching impractical.

    Args:
        output: The generated commentary text
        pattern_context: Pattern context containing protected tokens
        protected_tokens: Optional pre-extracted tokens (for testing)
        system_display: System display string used in notification_text
        ship_display: Ship display string used in notification_text

    Returns:
        True if output is valid, False if protected tokens are corrupted
    """
    if not output or output.upper() == NO_COMMENTARY_SIGNAL:
        return True

    tokens = protected_tokens or extract_protected_tokens(
        pattern_context, system_display=system_display, ship_display=ship_display
    )

    # Check each token that appears to be referenced
    for token in tokens:
        # Skip empty tokens
        if not token:
            continue

        # Use word-boundary matching to detect if token is referenced
        # This prevents false positives when token is substring of another word
        # e.g., "Jita" shouldn't match "Jitaesque"
        try:
            pattern = rf"\b{re.escape(token)}\b"
            regex_match = re.search(pattern, output, re.IGNORECASE)
        except re.error:
            # If regex fails (shouldn't happen with escape), fall back to substring
            regex_match = re.search(re.escape(token), output, re.IGNORECASE)

        if regex_match and token not in output:
            # Token is referenced (as whole word) but not exact - likely corrupted
            logger.debug(
                "Token validation failed: '%s' referenced but not exact in output",
                token,
            )
            return False

    return True


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CommentaryMetrics:
    """
    Metrics for commentary generation.

    Tracks success/failure rates and cost estimates.
    """

    generated_count: int = 0
    timeout_count: int = 0
    error_count: int = 0
    no_commentary_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    provider_name: str = "anthropic"
    _daily_date: date | None = field(default=None, repr=False)

    def record_generation(self, input_tokens: int, output_tokens: int) -> None:
        """Record a successful generation."""
        self._check_daily_reset()
        self.generated_count += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def record_timeout(self) -> None:
        """Record a timeout."""
        self._check_daily_reset()
        self.timeout_count += 1

    def record_error(self) -> None:
        """Record an error."""
        self._check_daily_reset()
        self.error_count += 1

    def record_no_commentary(self) -> None:
        """Record LLM declining to comment."""
        self._check_daily_reset()
        self.no_commentary_count += 1

    def _check_daily_reset(self) -> None:
        """Reset counters if it's a new day."""
        today = date.today()
        if self._daily_date != today:
            self.generated_count = 0
            self.timeout_count = 0
            self.error_count = 0
            self.no_commentary_count = 0
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self._daily_date = today

    @property
    def daily_cost_estimate(self) -> float:
        """
        Estimate daily cost based on token usage.

        Returns:
            Estimated cost in USD
        """
        from .llm_providers import COST_PER_1K_TOKENS

        costs = COST_PER_1K_TOKENS.get(
            self.provider_name,
            {"input": COST_PER_1K_INPUT_TOKENS, "output": COST_PER_1K_OUTPUT_TOKENS},
        )
        input_cost = (self.total_input_tokens / 1000) * costs["input"]
        output_cost = (self.total_output_tokens / 1000) * costs["output"]
        return input_cost + output_cost

    def check_daily_limit(self, limit_usd: float) -> bool:
        """
        Check if daily cost limit has been reached.

        Args:
            limit_usd: Daily cost limit in USD

        Returns:
            True if within limit, False if exceeded
        """
        self._check_daily_reset()
        return self.daily_cost_estimate < limit_usd

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "generated_count": self.generated_count,
            "timeout_count": self.timeout_count,
            "error_count": self.error_count,
            "no_commentary_count": self.no_commentary_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "daily_cost_estimate_usd": round(self.daily_cost_estimate, 4),
        }


# =============================================================================
# Commentary Generator
# =============================================================================


class CommentaryGenerator:
    """
    Generates LLM commentary for killmail notifications.

    Uses Claude API with configurable model, timeouts, and cost limits.
    """

    def __init__(
        self,
        persona_loader: PersonaLoader,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        default_timeout_ms: int = DEFAULT_TIMEOUT_MS,
        cost_limit_daily_usd: float = 1.0,
        provider: LLMProvider | None = None,
        provider_name: str = "anthropic",
        style: CommentaryStyle = CommentaryStyle.CONVERSATIONAL,
        max_chars: int = DEFAULT_MAX_CHARS,
    ):
        """
        Initialize commentary generator.

        Args:
            persona_loader: PersonaLoader for voice context
            model: Model identifier for the selected provider
            max_tokens: Maximum tokens in response
            default_timeout_ms: Default timeout in milliseconds
            cost_limit_daily_usd: Daily cost limit in USD
            provider: LLM provider instance (if None, generator is unconfigured)
            provider_name: Provider name for cost tracking
            style: Commentary style preset (conversational or radio)
            max_chars: Soft upper bound for radio style character limit
        """
        self._persona_loader = persona_loader
        self._model = model
        self._max_tokens = max_tokens
        self._default_timeout_ms = default_timeout_ms
        self._cost_limit_daily_usd = cost_limit_daily_usd
        self._provider = provider
        self._provider_name = provider_name
        self._metrics = CommentaryMetrics(provider_name=provider_name)
        self._style = style
        self._max_chars = max_chars

    async def generate_commentary(
        self,
        pattern_context: PatternContext,
        notification_text: str,
        timeout_ms: int | None = None,
        style: CommentaryStyle | None = None,
        max_chars: int | None = None,
        system_display: str | None = None,
        ship_display: str | None = None,
    ) -> str | None:
        """
        Generate tactical commentary for a kill notification.

        Args:
            pattern_context: Pattern detection results
            notification_text: The notification being sent
            timeout_ms: Timeout in milliseconds (None = use default)
            style: Override style for this call (None = use instance default)
            max_chars: Override max_chars for this call (None = use instance default)
            system_display: System display string for token validation (may be
                resolved name like "Tama" or fallback like "System 30002813")
            ship_display: Ship display string for token validation (may be
                resolved name like "Vexor" or fallback like "Ship 17740" or "Capsule")

        Returns:
            Commentary string, or None if:
            - Timeout exceeded
            - LLM returned NO_COMMENTARY
            - Error occurred
            - Daily cost limit exceeded
        """
        # Check cost limit
        if not self._metrics.check_daily_limit(self._cost_limit_daily_usd):
            logger.warning("Daily cost limit exceeded, skipping commentary")
            return None

        timeout_ms = timeout_ms or self._default_timeout_ms
        timeout_seconds = timeout_ms / 1000

        if not self._provider:
            logger.error("No LLM provider configured")
            self._metrics.record_error()
            return None

        # Use instance defaults with per-call overrides
        effective_style = style or self._style
        effective_max_chars = max_chars if max_chars is not None else self._max_chars

        # Derive stress level from pattern context (uses severity metadata when available)
        stress_level = get_stress_level(pattern_context)

        # Build prompts
        from .prompts import build_system_prompt, build_user_prompt

        voice_summary = self._persona_loader.get_voice_summary()
        system_prompt = build_system_prompt(
            voice_summary,
            style=effective_style,
            stress_level=stress_level,
            max_chars=effective_max_chars,
        )
        user_prompt = build_user_prompt(notification_text, pattern_context)

        try:
            # Call LLM via provider
            response = await self._provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self._model,
                max_tokens=self._max_tokens,
                timeout_seconds=timeout_seconds,
            )

            text = response.text
            input_tokens = response.input_tokens
            output_tokens = response.output_tokens

            # Check for NO_COMMENTARY signal
            if text.upper() == NO_COMMENTARY_SIGNAL or not text:
                self._metrics.record_no_commentary()
                logger.debug("LLM declined commentary: %s", text or "(empty)")
                return None

            # Validate protected tokens before returning (defense-in-depth)
            if not validate_preserved_tokens(
                text,
                pattern_context,
                system_display=system_display,
                ship_display=ship_display,
            ):
                self._metrics.record_no_commentary()
                logger.warning(
                    "Commentary failed token validation, returning None",
                    extra={
                        "pattern_type": pattern_context.patterns[0].pattern_type
                        if pattern_context.patterns
                        else "unknown"
                    },
                )
                return None

            self._metrics.record_generation(input_tokens, output_tokens)
            logger.debug("Generated commentary: %s", text[:100])
            return text

        except TimeoutError:
            self._metrics.record_timeout()
            logger.debug("Commentary generation timed out after %dms", timeout_ms)
            return None

        except Exception as e:
            self._metrics.record_error()
            logger.error("Commentary generation failed: %s", e)
            return None

    def get_metrics(self) -> CommentaryMetrics:
        """
        Get current metrics.

        Returns:
            CommentaryMetrics instance
        """
        return self._metrics

    @property
    def is_configured(self) -> bool:
        """Check if an LLM provider is configured."""
        return self._provider is not None

    async def close(self) -> None:
        """Close the LLM provider."""
        if self._provider is not None:
            await self._provider.close()
            self._provider = None


# =============================================================================
# Factory Function
# =============================================================================


def create_commentary_generator(
    persona_loader: PersonaLoader | None = None,
    config: dict | None = None,
) -> CommentaryGenerator:
    """
    Create a CommentaryGenerator from configuration.

    Args:
        persona_loader: Optional PersonaLoader instance (created if None)
        config: Optional configuration dict with:
            - provider: LLM provider ("anthropic", "openai", "gemini")
            - model: Model name (provider-specific)
            - max_tokens: Max response tokens
            - timeout_ms: Default timeout
            - cost_limit_daily_usd: Daily cost limit
            - persona: Optional persona override (e.g., "paria-s")
            - style: Commentary style ("conversational" or "radio")
            - max_chars: Soft upper bound for radio style

    Returns:
        CommentaryGenerator instance
    """
    from .llm_providers import PROVIDER_DEFAULTS, create_provider

    config = config or {}

    # Create PersonaLoader with override if specified
    if persona_loader is None:
        from .persona import PersonaLoader as PL

        persona_override = config.get("persona")
        persona_loader = PL(persona_override=persona_override)

    # Resolve provider
    provider_name = config.get("provider", "anthropic")

    # Default model per provider if not specified
    model = config.get("model")
    if not model and provider_name in PROVIDER_DEFAULTS:
        model = PROVIDER_DEFAULTS[provider_name]["model"]
    model = model or DEFAULT_MODEL

    # Create provider (may return None if API key missing)
    provider = None
    try:
        provider = create_provider(provider_name, api_key=config.get("api_key"))
    except (RuntimeError, ValueError) as e:
        logger.warning("Failed to create LLM provider '%s': %s", provider_name, e)

    # Parse style from config
    style_str = config.get("style")
    style = CommentaryStyle(style_str) if style_str else CommentaryStyle.CONVERSATIONAL

    return CommentaryGenerator(
        persona_loader=persona_loader,
        model=model,
        max_tokens=config.get("max_tokens", DEFAULT_MAX_TOKENS),
        default_timeout_ms=config.get("timeout_ms", DEFAULT_TIMEOUT_MS),
        cost_limit_daily_usd=config.get("cost_limit_daily_usd", 1.0),
        provider=provider,
        provider_name=provider_name,
        style=style,
        max_chars=config.get("max_chars", DEFAULT_MAX_CHARS),
    )
