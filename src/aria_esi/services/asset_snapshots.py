"""
ARIA Asset Snapshot Service.

Manages point-in-time snapshots of asset inventory for trend tracking.
Snapshots are stored as YAML files in the pilot's assets directory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml


class AssetSnapshotService:
    """
    Service for managing asset inventory snapshots.

    Snapshots allow tracking asset value changes over time,
    identifying high-water marks, and analyzing trends.
    """

    def __init__(self, pilot_dir: Path | str):
        """
        Initialize snapshot service for a pilot.

        Args:
            pilot_dir: Path to pilot's userdata directory
        """
        self.pilot_dir = Path(pilot_dir)
        self.snapshots_dir = self.pilot_dir / "assets" / "snapshots"

    def ensure_dir(self) -> None:
        """Ensure snapshots directory exists."""
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(
        self,
        total_value: float,
        by_category: dict[str, float],
        by_location: dict[int, float],
        top_items: list[dict[str, Any]],
        timestamp: Optional[datetime] = None,
        insights: Optional[dict[str, Any]] = None,
    ) -> Path:
        """
        Save an asset snapshot.

        Args:
            total_value: Total portfolio value in ISK
            by_category: Value breakdown by category (ships, modules, etc.)
            by_location: Value breakdown by location_id
            top_items: List of highest-value items with type_id, name, value
            timestamp: Snapshot time (defaults to now)
            insights: Optional insights summary (forgotten assets, consolidations, duplicates)

        Returns:
            Path to saved snapshot file
        """
        self.ensure_dir()

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        snapshot: dict[str, Any] = {
            "timestamp": timestamp.isoformat(),
            "total_value": total_value,
            "by_category": by_category,
            "by_location": {str(k): v for k, v in by_location.items()},
            "top_items": top_items[:20],  # Store top 20 items
        }

        # Include insights if provided
        if insights:
            snapshot["insights"] = insights

        # Use date as filename for daily snapshots
        filename = f"{timestamp.strftime('%Y-%m-%d')}.yaml"
        filepath = self.snapshots_dir / filename

        with open(filepath, "w") as f:
            yaml.safe_dump(snapshot, f, default_flow_style=False, sort_keys=False)

        return filepath

    def load_snapshot(self, date: str) -> Optional[dict[str, Any]]:
        """
        Load a snapshot by date.

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            Snapshot data or None if not found
        """
        filepath = self.snapshots_dir / f"{date}.yaml"
        if not filepath.exists():
            return None

        with open(filepath) as f:
            return yaml.safe_load(f)

    def list_snapshots(self) -> list[str]:
        """
        List all available snapshot dates.

        Returns:
            List of date strings (YYYY-MM-DD), sorted newest first
        """
        if not self.snapshots_dir.exists():
            return []

        snapshots = []
        for f in self.snapshots_dir.glob("*.yaml"):
            # Extract date from filename
            date = f.stem
            snapshots.append(date)

        return sorted(snapshots, reverse=True)

    def get_latest_snapshot(self) -> Optional[dict[str, Any]]:
        """
        Get the most recent snapshot.

        Returns:
            Latest snapshot data or None if no snapshots exist
        """
        dates = self.list_snapshots()
        if not dates:
            return None
        return self.load_snapshot(dates[0])

    def get_high_water_mark(self) -> Optional[dict[str, Any]]:
        """
        Find the snapshot with highest total value.

        Returns:
            Snapshot with highest total_value, or None if no snapshots
        """
        dates = self.list_snapshots()
        if not dates:
            return None

        highest: Optional[dict[str, Any]] = None
        highest_value: float = 0.0

        for date in dates:
            snapshot = self.load_snapshot(date)
            if snapshot and snapshot.get("total_value", 0) > highest_value:
                highest = snapshot
                highest_value = snapshot["total_value"]

        return highest

    def calculate_trends(
        self, days: int = 7
    ) -> dict[str, Any]:
        """
        Calculate value trends over specified period.

        Args:
            days: Number of days to analyze (default 7)

        Returns:
            Trend analysis including:
            - current_value: Latest snapshot value
            - previous_value: Value from `days` ago (or oldest available)
            - change_absolute: ISK change
            - change_percent: Percentage change
            - high_water_mark: Highest value in period
            - snapshots_in_period: Number of snapshots analyzed
        """
        dates = self.list_snapshots()
        if not dates:
            return {
                "error": "no_snapshots",
                "message": "No snapshots available for trend analysis",
            }

        # Get current (most recent) snapshot
        current = self.load_snapshot(dates[0])
        if not current:
            return {"error": "snapshot_error", "message": "Could not load latest snapshot"}

        current_value = current.get("total_value", 0)
        current_date = dates[0]

        # Find snapshot from `days` ago (or oldest if fewer days available)
        from datetime import timedelta

        target_date = (
            datetime.strptime(current_date, "%Y-%m-%d") - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        # Find closest available date to target
        previous_date = None
        for date in dates:
            if date <= target_date:
                previous_date = date
                break

        # If no date before target, use oldest available
        if previous_date is None and len(dates) > 1:
            previous_date = dates[-1]

        # Calculate stats for the period
        period_values = []
        period_dates = []
        for date in dates:
            if date >= target_date or (previous_date and date == previous_date):
                snapshot = self.load_snapshot(date)
                if snapshot:
                    period_values.append(snapshot.get("total_value", 0))
                    period_dates.append(date)

        # Calculate change
        if previous_date:
            previous = self.load_snapshot(previous_date)
            previous_value = previous.get("total_value", 0) if previous else 0
        else:
            previous_value = current_value

        change_absolute = current_value - previous_value
        change_percent = (
            (change_absolute / previous_value * 100) if previous_value > 0 else 0
        )

        # Find high water mark in period
        high_water = max(period_values) if period_values else current_value

        return {
            "current_value": current_value,
            "current_date": current_date,
            "previous_value": previous_value,
            "previous_date": previous_date or current_date,
            "change_absolute": change_absolute,
            "change_percent": round(change_percent, 2),
            "high_water_mark": high_water,
            "snapshots_in_period": len(period_values),
            "period_days": days,
        }

    def cleanup_old_snapshots(self, keep_days: int = 90) -> int:
        """
        Remove snapshots older than specified days.

        Args:
            keep_days: Days of history to retain (default 90)

        Returns:
            Number of snapshots removed
        """
        if not self.snapshots_dir.exists():
            return 0

        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).strftime(
            "%Y-%m-%d"
        )

        removed = 0
        for f in self.snapshots_dir.glob("*.yaml"):
            date = f.stem
            if date < cutoff:
                f.unlink()
                removed += 1

        return removed


def get_snapshot_service(pilot_dir: Path | str) -> AssetSnapshotService:
    """
    Factory function to create snapshot service.

    Args:
        pilot_dir: Path to pilot's userdata directory

    Returns:
        AssetSnapshotService instance
    """
    return AssetSnapshotService(pilot_dir)
