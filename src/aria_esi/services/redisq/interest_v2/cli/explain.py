"""
Explain Command for Interest Engine v2.

Provides detailed breakdown of interest scoring for a specific kill,
showing how each signal and category contributed to the final score.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models import InterestResultV2


def explain_kill(
    result: InterestResultV2,
    verbose: bool = False,
) -> str:
    """
    Generate human-readable explanation of interest scoring.

    Args:
        result: InterestResultV2 from engine.calculate_interest()
        verbose: Include raw signal values

    Returns:
        Formatted multi-line explanation
    """
    lines = []

    # Header
    _add_header(lines, result)

    # Check for early exits
    if result.was_ignored:
        _add_ignored_section(lines, result)
        return "\n".join(lines)

    if result.bypassed_scoring:
        _add_always_notify_section(lines, result)
        return "\n".join(lines)

    # Gate failures
    if not result.require_all_passed or not result.require_any_passed:
        _add_gate_failure_section(lines, result)
        return "\n".join(lines)

    # Category breakdown
    _add_category_breakdown(lines, result, verbose)

    # Aggregation
    _add_aggregation_section(lines, result)

    # Final decision
    _add_decision_section(lines, result)

    return "\n".join(lines)


def format_explanation(result: InterestResultV2) -> dict[str, Any]:
    """
    Format explanation as structured data for JSON output.

    Args:
        result: InterestResultV2 from engine

    Returns:
        Dict with structured explanation
    """
    explanation: dict[str, Any] = {
        "system_id": result.system_id,
        "kill_id": result.kill_id,
        "tier": result.tier.value,
        "interest": round(result.interest, 3),
        "mode": result.mode.value,
    }

    # Early exits
    if result.was_ignored:
        matched = [m for m in result.always_ignore_matched if m.matched]
        explanation["ignored_by"] = [m.rule_id for m in matched]
        return explanation

    if result.bypassed_scoring:
        matched = [m for m in result.always_notify_matched if m.matched]
        explanation["always_notify"] = [m.rule_id for m in matched]
        return explanation

    # Gate status
    if not result.require_all_passed or not result.require_any_passed:
        explanation["gates"] = {
            "require_all_passed": result.require_all_passed,
            "require_any_passed": result.require_any_passed,
            "failure_reason": result.gate_failure_reason,
        }
        return explanation

    # Category breakdown
    categories = []
    for cat, score, weight, match in result.get_category_breakdown():
        cat_obj = result.category_scores[cat]
        cat_data = {
            "category": cat,
            "score": round(score, 3),
            "weight": weight,
            "match": match,
            "contribution": round(score * weight, 3),
        }

        # Signal details
        signals = []
        for sig_name, sig in cat_obj.signals.items():
            sig_data = {
                "signal": sig_name,
                "score": round(sig.score, 3),
                "match": sig.matches,
                "reason": sig.reason,
            }
            if sig.raw_value is not None:
                sig_data["raw_value"] = sig.raw_value
            signals.append(sig_data)

        if signals:
            cat_data["signals"] = signals

        categories.append(cat_data)

    explanation["categories"] = categories

    # Thresholds
    explanation["thresholds"] = result.thresholds

    return explanation


def _add_header(lines: list[str], result: InterestResultV2) -> None:
    """Add header section."""
    if result.kill_id:
        lines.append(f"╔═══ Kill {result.kill_id} in System {result.system_id} ═══╗")
    else:
        lines.append(f"╔═══ System {result.system_id} (Prefetch) ═══╗")

    lines.append(f"║ Engine: v2 | Mode: {result.mode.value} | Preset: {result.preset or 'none'}")
    lines.append("╚" + "═" * 45 + "╝")
    lines.append("")


def _add_ignored_section(lines: list[str], result: InterestResultV2) -> None:
    """Add section for ignored kills."""
    matched = [m for m in result.always_ignore_matched if m.matched]
    lines.append("❌ IGNORED")
    lines.append("─" * 40)
    for m in matched:
        reason = f" ({m.reason})" if m.reason else ""
        lines.append(f"  Rule: {m.rule_id}{reason}")
    lines.append("")
    lines.append("Result: FILTER (not fetched from ESI)")


def _add_always_notify_section(lines: list[str], result: InterestResultV2) -> None:
    """Add section for always_notify bypass."""
    matched = [m for m in result.always_notify_matched if m.matched]
    lines.append("⚡ ALWAYS NOTIFY (threshold bypass)")
    lines.append("─" * 40)
    for m in matched:
        reason = f" ({m.reason})" if m.reason else ""
        lines.append(f"  Rule: {m.rule_id}{reason}")
    lines.append("")
    lines.append(f"Result: {result.tier.value.upper()}")


def _add_gate_failure_section(lines: list[str], result: InterestResultV2) -> None:
    """Add section for gate failures."""
    lines.append("🚫 GATE FAILED")
    lines.append("─" * 40)

    if not result.require_all_passed:
        lines.append("  require_all: FAILED")
    if not result.require_any_passed:
        lines.append("  require_any: FAILED")

    if result.gate_failure_reason:
        lines.append(f"  Reason: {result.gate_failure_reason}")

    lines.append("")
    lines.append("Result: FILTER")


def _add_category_breakdown(
    lines: list[str],
    result: InterestResultV2,
    verbose: bool,
) -> None:
    """Add category score breakdown."""
    lines.append("📊 Category Scores")
    lines.append("─" * 40)

    for cat, score, weight, match in result.get_category_breakdown():
        cat_obj = result.category_scores[cat]

        # Category line
        match_char = "✓" if match else "○"
        weight_pct = f"{weight * 100:.0f}%"
        contribution = score * weight
        lines.append(
            f"  {match_char} {cat.capitalize():12} "
            f"score={score:.2f} weight={weight_pct:>4} "
            f"contrib={contribution:.3f}"
        )

        # Signal details
        for sig_name, sig in cat_obj.signals.items():
            sig_match = "✓" if sig.matches else "○"
            reason = f" [{sig.reason}]" if sig.reason else ""
            lines.append(f"      └─ {sig_name}: {sig_match} {sig.score:.2f}{reason}")

            if verbose and sig.raw_value is not None:
                lines.append(f"          raw: {sig.raw_value}")

    lines.append("")


def _add_aggregation_section(lines: list[str], result: InterestResultV2) -> None:
    """Add aggregation explanation."""
    from ..aggregation import compare_aggregation_modes

    lines.append("🔢 Aggregation")
    lines.append("─" * 40)

    # Compare modes
    comparison = compare_aggregation_modes(result.category_scores)

    lines.append(f"  RMS:    {comparison['rms']:.3f}")
    lines.append(f"  Linear: {comparison['linear']:.3f}")
    lines.append(f"  Max:    {comparison['max']:.3f}")
    lines.append("")
    lines.append(f"  Selected mode: {result.mode.value}")
    lines.append(f"  Final score:   {result.interest:.3f}")
    lines.append("")


def _add_decision_section(lines: list[str], result: InterestResultV2) -> None:
    """Add final decision section."""
    lines.append("📋 Decision")
    lines.append("─" * 40)

    # Threshold comparison
    thresholds = result.thresholds
    lines.append(f"  Interest: {result.interest:.3f}")
    lines.append("")
    lines.append("  Thresholds:")
    lines.append(f"    priority: {thresholds.get('priority', 0.85):.2f}")
    lines.append(f"    notify:   {thresholds.get('notify', 0.60):.2f}")
    lines.append(f"    digest:   {thresholds.get('digest', 0.40):.2f}")
    lines.append("")

    # Result
    tier = result.tier.value.upper()
    if result.should_notify:
        lines.append(f"  ✓ Result: {tier}")
    else:
        lines.append(f"  ✗ Result: {tier}")

    # Dominant category
    if result.dominant_category:
        lines.append(f"  Dominant: {result.dominant_category}")


def explain_prefetch(
    result: InterestResultV2,
    prefetch_decision: Any | None = None,
) -> str:
    """
    Generate explanation for prefetch evaluation.

    Args:
        result: InterestResultV2 from prefetch evaluation
        prefetch_decision: Optional PrefetchDecision with bounds

    Returns:
        Formatted explanation
    """
    lines = []

    lines.append(f"╔═══ Prefetch Evaluation: System {result.system_id} ═══╗")
    lines.append("")

    if prefetch_decision:
        lines.append("📡 Prefetch Analysis")
        lines.append("─" * 40)
        lines.append(f"  Mode: {prefetch_decision.mode}")
        lines.append(f"  Prefetch score: {prefetch_decision.prefetch_score or 'N/A'}")
        lines.append(f"  Lower bound: {prefetch_decision.lower_bound:.3f}")
        lines.append(f"  Upper bound: {prefetch_decision.upper_bound:.3f}")
        lines.append(f"  Threshold: {prefetch_decision.threshold_used:.3f}")
        lines.append("")
        lines.append(f"  Categories (prefetch): {prefetch_decision.prefetch_capable_count}")
        lines.append(f"  Categories (total): {prefetch_decision.total_categories}")
        lines.append("")

        if prefetch_decision.always_notify_triggered:
            lines.append("  ⚡ always_notify rule triggered")
        if prefetch_decision.always_ignore_triggered:
            lines.append("  ❌ always_ignore rule triggered")

        lines.append("")
        decision = "FETCH" if prefetch_decision.should_fetch else "DROP"
        lines.append(f"  Decision: {decision}")
        lines.append(f"  Reason: {prefetch_decision.reason}")
    else:
        lines.append(f"  Decision: {'FETCH' if result.should_fetch else 'DROP'}")

    return "\n".join(lines)
