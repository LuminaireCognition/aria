"""
Simulation Tool for Interest Engine v2.

Replays historical kills through the v2 engine to:
- Compare v1 vs v2 scoring
- Test configuration changes before deployment
- Identify potential notification changes
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...models import ProcessedKill
    from ..engine import InterestEngineV2

logger = logging.getLogger(__name__)


@dataclass
class SimulationKillResult:
    """Result for a single kill in simulation."""

    kill_id: int
    system_id: int
    timestamp: datetime | None
    v2_tier: str
    v2_interest: float
    v1_triggered: bool | None = None  # From original evaluation
    v1_trigger_types: list[str] = field(default_factory=list)
    dominant_category: str | None = None
    bypassed: bool = False
    ignored: bool = False

    @property
    def would_notify(self) -> bool:
        """Check if v2 would send notification."""
        return self.v2_tier in ("notify", "priority")

    @property
    def tier_changed(self) -> bool:
        """Check if notification status changed from v1."""
        if self.v1_triggered is None:
            return False
        return self.would_notify != self.v1_triggered


@dataclass
class SimulationSummary:
    """Summary of simulation run."""

    profile_name: str
    total_kills: int
    v2_notify: int
    v2_priority: int
    v2_digest: int
    v2_filter: int
    v1_triggered: int = 0
    tier_changes: int = 0
    new_notifications: int = 0  # Would notify in v2 but not v1
    lost_notifications: int = 0  # Would not notify in v2 but did in v1
    start_time: datetime | None = None
    end_time: datetime | None = None

    @property
    def v2_total_notify(self) -> int:
        """Total kills that would generate notifications."""
        return self.v2_notify + self.v2_priority

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "profile": self.profile_name,
            "total_kills": self.total_kills,
            "v2": {
                "notify": self.v2_notify,
                "priority": self.v2_priority,
                "digest": self.v2_digest,
                "filter": self.v2_filter,
            },
            "v1_triggered": self.v1_triggered,
            "tier_changes": self.tier_changes,
            "new_notifications": self.new_notifications,
            "lost_notifications": self.lost_notifications,
        }


@dataclass
class SimulationResult:
    """Complete simulation result."""

    summary: SimulationSummary
    kills: list[SimulationKillResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def get_tier_breakdown(self) -> dict[str, list[SimulationKillResult]]:
        """Group kills by v2 tier."""
        breakdown: dict[str, list[SimulationKillResult]] = {
            "priority": [],
            "notify": [],
            "digest": [],
            "log_only": [],
            "filter": [],
        }
        for kill in self.kills:
            tier = kill.v2_tier
            if tier in breakdown:
                breakdown[tier].append(kill)
        return breakdown

    def get_changed_kills(self) -> list[SimulationKillResult]:
        """Get kills where notification status changed."""
        return [k for k in self.kills if k.tier_changed]


def simulate_profile(
    engine: InterestEngineV2,
    kills: list[ProcessedKill],
    profile_name: str = "simulation",
    v1_results: dict[int, bool] | None = None,
) -> SimulationResult:
    """
    Simulate v2 scoring on a list of kills.

    Args:
        engine: Configured InterestEngineV2
        kills: List of ProcessedKill to evaluate
        profile_name: Name for summary
        v1_results: Optional dict of kill_id -> v1_triggered for comparison

    Returns:
        SimulationResult with per-kill results and summary
    """
    kill_results: list[SimulationKillResult] = []
    errors: list[str] = []

    # Initialize counters
    tier_counts = {
        "priority": 0,
        "notify": 0,
        "digest": 0,
        "log_only": 0,
        "filter": 0,
    }

    v1_triggered_count = 0
    tier_changes = 0
    new_notifications = 0
    lost_notifications = 0

    timestamps: list[datetime] = []

    for kill in kills:
        try:
            # Run v2 evaluation
            result = engine.calculate_interest(
                kill=kill,
                system_id=kill.solar_system_id,
                is_prefetch=False,
            )

            # Get v1 comparison if available
            v1_triggered = None
            if v1_results is not None:
                v1_triggered = v1_results.get(kill.kill_id)

            # Create kill result
            kill_result = SimulationKillResult(
                kill_id=kill.kill_id,
                system_id=kill.solar_system_id,
                timestamp=kill.kill_time,
                v2_tier=result.tier.value,
                v2_interest=result.interest,
                v1_triggered=v1_triggered,
                dominant_category=result.dominant_category,
                bypassed=result.bypassed_scoring,
                ignored=result.was_ignored,
            )

            kill_results.append(kill_result)

            # Update counters
            tier = result.tier.value
            if tier in tier_counts:
                tier_counts[tier] += 1

            if v1_triggered is not None:
                if v1_triggered:
                    v1_triggered_count += 1

                if kill_result.tier_changed:
                    tier_changes += 1

                    if kill_result.would_notify and not v1_triggered:
                        new_notifications += 1
                    elif not kill_result.would_notify and v1_triggered:
                        lost_notifications += 1

            if kill.kill_time:
                timestamps.append(kill.kill_time)

        except Exception as e:
            errors.append(f"Kill {kill.kill_id}: {e}")
            logger.warning(f"Simulation error for kill {kill.kill_id}: {e}")

    # Build summary
    summary = SimulationSummary(
        profile_name=profile_name,
        total_kills=len(kills),
        v2_notify=tier_counts["notify"],
        v2_priority=tier_counts["priority"],
        v2_digest=tier_counts["digest"],
        v2_filter=tier_counts["filter"] + tier_counts["log_only"],
        v1_triggered=v1_triggered_count,
        tier_changes=tier_changes,
        new_notifications=new_notifications,
        lost_notifications=lost_notifications,
        start_time=min(timestamps) if timestamps else None,
        end_time=max(timestamps) if timestamps else None,
    )

    return SimulationResult(
        summary=summary,
        kills=kill_results,
        errors=errors,
    )


def format_simulation_report(result: SimulationResult, verbose: bool = False) -> str:
    """
    Format simulation result as human-readable report.

    Args:
        result: SimulationResult to format
        verbose: Include per-kill details

    Returns:
        Formatted report string
    """
    lines = []
    summary = result.summary

    # Header
    lines.append("╔═══════════════════════════════════════════╗")
    lines.append(f"║  Simulation Report: {summary.profile_name:20} ║")
    lines.append("╚═══════════════════════════════════════════╝")
    lines.append("")

    # Time range
    if summary.start_time and summary.end_time:
        duration = summary.end_time - summary.start_time
        lines.append(f"📅 Time Range: {summary.start_time} to {summary.end_time}")
        lines.append(f"   Duration: {duration}")
        lines.append("")

    # v2 tier breakdown
    lines.append("📊 v2 Engine Results:")
    lines.append("─" * 40)
    lines.append(f"  Total kills analyzed: {summary.total_kills}")
    lines.append("")
    lines.append(f"  PRIORITY:  {summary.v2_priority:4d}  ████████")
    lines.append(f"  NOTIFY:    {summary.v2_notify:4d}  ████████")
    lines.append(f"  DIGEST:    {summary.v2_digest:4d}  ████")
    lines.append(f"  FILTER:    {summary.v2_filter:4d}  ██")
    lines.append("")
    lines.append(
        f"  Would notify: {summary.v2_total_notify} ({_pct(summary.v2_total_notify, summary.total_kills)})"
    )
    lines.append("")

    # v1 comparison if available
    if summary.v1_triggered > 0 or summary.tier_changes > 0:
        lines.append("🔄 v1 Comparison:")
        lines.append("─" * 40)
        lines.append(f"  v1 triggered: {summary.v1_triggered}")
        lines.append(f"  v2 would notify: {summary.v2_total_notify}")
        lines.append("")
        lines.append(f"  Tier changes: {summary.tier_changes}")
        lines.append(f"    New notifications: +{summary.new_notifications}")
        lines.append(f"    Lost notifications: -{summary.lost_notifications}")
        lines.append("")

        # Net change indicator
        net_change = summary.new_notifications - summary.lost_notifications
        if net_change > 0:
            lines.append(f"  📈 Net: +{net_change} more notifications with v2")
        elif net_change < 0:
            lines.append(f"  📉 Net: {net_change} fewer notifications with v2")
        else:
            lines.append("  ➡️ Net: Same notification count")
        lines.append("")

    # Errors
    if result.errors:
        lines.append(f"⚠️  Errors: {len(result.errors)}")
        for err in result.errors[:5]:
            lines.append(f"    {err}")
        if len(result.errors) > 5:
            lines.append(f"    ... and {len(result.errors) - 5} more")
        lines.append("")

    # Verbose kill details
    if verbose and result.kills:
        lines.append("📋 Kill Details:")
        lines.append("─" * 40)

        # Show changed kills first
        changed = result.get_changed_kills()
        if changed:
            lines.append("")
            lines.append("  Changed notifications:")
            for k in changed[:10]:
                v1_str = "✓" if k.v1_triggered else "✗"
                v2_str = "✓" if k.would_notify else "✗"
                lines.append(
                    f"    Kill {k.kill_id}: v1={v1_str} → v2={v2_str} "
                    f"({k.v2_tier}, {k.v2_interest:.2f})"
                )
            if len(changed) > 10:
                lines.append(f"    ... and {len(changed) - 10} more")

        # Show priority kills
        breakdown = result.get_tier_breakdown()
        if breakdown["priority"]:
            lines.append("")
            lines.append("  Priority kills:")
            for k in breakdown["priority"][:5]:
                lines.append(
                    f"    Kill {k.kill_id}: {k.v2_interest:.2f} (dominant: {k.dominant_category})"
                )
            if len(breakdown["priority"]) > 5:
                lines.append(f"    ... and {len(breakdown['priority']) - 5} more")

    return "\n".join(lines)


def _pct(part: int, total: int) -> str:
    """Calculate percentage string."""
    if total == 0:
        return "0%"
    return f"{part / total * 100:.1f}%"


async def simulate_from_store(
    engine: InterestEngineV2,
    hours: int = 24,
    profile_name: str = "simulation",
) -> SimulationResult:
    """
    Run simulation using kills from the kill store.

    Args:
        engine: Configured InterestEngineV2
        hours: Hours of history to simulate
        profile_name: Name for summary

    Returns:
        SimulationResult
    """
    # This would integrate with the kill store
    # For now, return empty result
    logger.warning("simulate_from_store not yet implemented")

    return SimulationResult(
        summary=SimulationSummary(
            profile_name=profile_name,
            total_kills=0,
            v2_notify=0,
            v2_priority=0,
            v2_digest=0,
            v2_filter=0,
        ),
        errors=["simulate_from_store not yet implemented"],
    )
