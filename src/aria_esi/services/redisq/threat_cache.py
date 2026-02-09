"""
Threat Cache for Real-Time Intel.

Provides threat analysis, gatecamp detection, and queryable
real-time kill data for ARIA skills.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from ...core.logging import get_logger

if TYPE_CHECKING:
    from .models import ProcessedKill
    from .war_context import WarContextProvider

logger = get_logger(__name__)

# =============================================================================
# Constants - Gatecamp Detection
# =============================================================================

# Detection windows
GATECAMP_WINDOW_SECONDS = 600  # 10 minutes
GATECAMP_MIN_KILLS = 3
SMARTBOMB_WINDOW_SECONDS = 60  # Multiple kills within 60s window

# Force asymmetry threshold (attackers vs victims)
FORCE_ASYMMETRY_THRESHOLD = 5.0  # 5:1 attacker ratio = camp behavior

# Common smartbomb platform type IDs
SMARTBOMB_SHIP_TYPES = {
    24690,  # Rokh
    24688,  # Apocalypse
    17740,  # Machariel
    17738,  # Nightmare
    24694,  # Hyperion
    645,  # Dominix
    641,  # Armageddon
    643,  # Megathron
}

# Health check constants
POLLER_HEALTHY_MAX_POLL_AGE_SECONDS = 300  # 5 minutes


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class GatecampStatus:
    """
    Active gatecamp detection result.

    Contains all data needed for threat assessment display.
    """

    system_id: int
    system_name: str | None = None
    kill_count: int = 0
    window_minutes: int = 10
    attacker_corps: list[int] = field(default_factory=list)
    attacker_alliances: list[int] = field(default_factory=list)
    attacker_ships: list[int] = field(default_factory=list)
    confidence: str = "low"  # low, medium, high
    last_kill_time: datetime | None = None
    is_smartbomb_camp: bool = False
    force_asymmetry: float = 0.0

    # War context fields
    is_war_engagement: bool = False
    war_attacker_alliance: int | None = None
    war_defender_alliance: int | None = None
    war_kills_filtered: int = 0  # Number of kills identified as war-related

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        result = {
            "system_id": self.system_id,
            "system_name": self.system_name,
            "kill_count": self.kill_count,
            "window_minutes": self.window_minutes,
            "attacker_corps": self.attacker_corps,
            "attacker_alliances": self.attacker_alliances,
            "attacker_ships": self.attacker_ships,
            "confidence": self.confidence,
            "last_kill_time": self.last_kill_time.isoformat() if self.last_kill_time else None,
            "is_smartbomb_camp": self.is_smartbomb_camp,
            "force_asymmetry": self.force_asymmetry,
        }

        # Include war context if present
        if self.is_war_engagement:
            result["is_war_engagement"] = True
            if self.war_attacker_alliance:
                result["war_attacker_alliance"] = self.war_attacker_alliance
            if self.war_defender_alliance:
                result["war_defender_alliance"] = self.war_defender_alliance
        if self.war_kills_filtered > 0:
            result["war_kills_filtered"] = self.war_kills_filtered

        return result


@dataclass
class RealtimeActivitySummary:
    """
    Real-time activity summary for a system.

    Extends hourly aggregates with minute-level kill data.
    """

    system_id: int
    kills_10m: int = 0
    kills_1h: int = 0
    pod_kills_10m: int = 0
    pod_kills_1h: int = 0
    recent_kills: list[dict] = field(default_factory=list)  # Last 5 kills
    gatecamp: GatecampStatus | None = None

    # Watched entity tracking
    watched_entity_kills_1h: int = 0
    watched_entity_details: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        result = {
            "kills_10m": self.kills_10m,
            "kills_1h": self.kills_1h,
            "pod_kills_10m": self.pod_kills_10m,
            "pod_kills_1h": self.pod_kills_1h,
            "recent_kills": self.recent_kills,
        }
        if self.gatecamp:
            result["gatecamp"] = self.gatecamp.to_dict()
        if self.watched_entity_kills_1h > 0:
            result["watched_entity_kills_1h"] = self.watched_entity_kills_1h
            result["watched_entity_details"] = self.watched_entity_details
        return result


# =============================================================================
# Gatecamp Detection Algorithm
# =============================================================================


def detect_smartbomb_camp(kills: list[ProcessedKill], attacker_ships: set[int]) -> bool:
    """
    Detect smartbomb camps via ship types + timing patterns.

    Smartbomb camps have characteristic signatures:
    - Known smartbomb platform ships (Rokh, Apocalypse, Machariel, etc.)
    - Multiple distinct victims dying within a tight window (chain smartbombing)

    Args:
        kills: List of kills to analyze
        attacker_ships: Set of all attacker ship type IDs

    Returns:
        True if pattern matches smartbomb camp
    """
    # Check for characteristic smartbomb ships in attackers
    has_smartbomb_ships = bool(attacker_ships & SMARTBOMB_SHIP_TYPES)

    if not has_smartbomb_ships:
        return False

    if len(kills) < 3:
        return False

    # Check timing: 3+ kills within 60s window suggests smartbomb chain
    kill_times = sorted(k.kill_time for k in kills)
    window_duration = (kill_times[-1] - kill_times[0]).total_seconds()

    return window_duration <= SMARTBOMB_WINDOW_SECONDS


def detect_gatecamp(
    system_id: int,
    kills: list[ProcessedKill],
    system_name: str | None = None,
    war_context: WarContextProvider | None = None,
) -> GatecampStatus | None:
    """
    Detect active gatecamp based on recent kill clustering.

    Heuristics:
    - 3+ kills in same system within 10 minutes = likely camp
    - Force asymmetry: attackers consistently outnumber victims 5:1+
    - Multiple victim corps OR high force asymmetry = camp (not fleet fight)
    - High pod:ship ratio increases confidence (camps kill pods)
    - Consistent attackers across kills increases confidence
    - Smartbomb detection via ship type + timing analysis

    War Context Integration:
    - If war_context is provided, kills between known belligerents are
      filtered out before gatecamp analysis
    - If ALL kills are war-related, no gatecamp is detected
    - Returns war engagement metadata for notification purposes

    Args:
        system_id: System ID to check
        kills: Recent kills in the system
        system_name: Optional system name for display
        war_context: Optional war context provider for filtering war kills

    Returns:
        GatecampStatus if camp detected, None otherwise
    """
    # Filter out war kills if war context is provided
    war_kills_filtered = 0
    war_attacker_alliance = None
    war_defender_alliance = None

    if war_context:
        war_kills, non_war_kills = war_context.filter_war_kills(kills)
        war_kills_filtered = len(war_kills)

        # If ALL kills are war-related, this is not a gatecamp
        if len(war_kills) == len(kills) and len(kills) > 0:
            # Return None - pure war engagement, not a camp
            # Caller can use war_context separately to get war details
            logger.debug(
                "System %d: All %d kills are war engagements, not a gatecamp",
                system_id,
                len(kills),
            )
            return None

        # Extract war relationship info from first war kill for metadata
        if war_kills:
            first_war_context = war_context.check_kill(war_kills[0])
            if first_war_context.relationship:
                war_attacker_alliance = first_war_context.relationship.aggressor_id
                war_defender_alliance = first_war_context.relationship.defender_id

        # Continue analysis with only non-war kills
        kills = non_war_kills

    if len(kills) < GATECAMP_MIN_KILLS:
        return None

    # Analyze kill pattern
    victim_corps: set[int] = set()
    attacker_corps: set[int] = set()
    attacker_alliances: set[int] = set()
    attacker_corp_counts: Counter[int] = Counter()
    all_attacker_ships: set[int] = set()
    total_attacker_count = 0

    for kill in kills:
        if kill.victim_corporation_id:
            victim_corps.add(kill.victim_corporation_id)

        attacker_corps.update(kill.attacker_corps)
        attacker_alliances.update(kill.attacker_alliances)
        all_attacker_ships.update(kill.attacker_ship_types)
        total_attacker_count += kill.attacker_count

        for corp in kill.attacker_corps:
            attacker_corp_counts[corp] += 1

    # Calculate force asymmetry (average attackers per kill)
    avg_attacker_count = total_attacker_count / len(kills) if kills else 0
    high_force_asymmetry = avg_attacker_count >= FORCE_ASYMMETRY_THRESHOLD

    # Camp detection: multiple victim corps OR high force asymmetry
    # Single victim corp with similar-sized forces = fleet fight
    # Single victim corp but 5:1 attacker ratio = still a camp
    is_camp = len(victim_corps) > 1 or high_force_asymmetry

    if not is_camp:
        return None

    # Calculate confidence factors
    confidence_score = 0

    # Factor 1: Kill count
    if len(kills) >= 5:
        confidence_score += 2
    else:
        confidence_score += 1

    # Factor 2: Pod kill ratio (camps kill pods, fights often don't)
    pod_kills = sum(1 for k in kills if k.is_pod_kill)
    ship_kills = len(kills) - pod_kills
    if ship_kills > 0 and pod_kills / ship_kills >= 0.5:
        confidence_score += 1

    # Factor 3: Attacker consistency (same group across kills)
    if attacker_corp_counts:
        most_common_count = attacker_corp_counts.most_common(1)[0][1]
        if most_common_count >= len(kills) * 0.7:
            confidence_score += 1

    # Factor 4: Smartbomb camp detection
    is_smartbomb = detect_smartbomb_camp(kills, all_attacker_ships)
    if is_smartbomb:
        confidence_score += 1

    # Factor 5: Force asymmetry bonus
    if high_force_asymmetry:
        confidence_score += 1

    # Map score to confidence level
    if confidence_score >= 4:
        confidence = "high"
    elif confidence_score >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    return GatecampStatus(
        system_id=system_id,
        system_name=system_name,
        kill_count=len(kills),
        window_minutes=GATECAMP_WINDOW_SECONDS // 60,
        attacker_corps=list(attacker_corps),
        attacker_alliances=list(attacker_alliances),
        attacker_ships=list(all_attacker_ships),
        confidence=confidence,
        last_kill_time=max(k.kill_time for k in kills),
        is_smartbomb_camp=is_smartbomb,
        force_asymmetry=round(avg_attacker_count, 1),
        war_kills_filtered=war_kills_filtered,
        war_attacker_alliance=war_attacker_alliance,
        war_defender_alliance=war_defender_alliance,
    )


# =============================================================================
# Threat Cache Class
# =============================================================================


class ThreatCache:
    """
    Real-time threat intelligence cache.

    Provides high-level query methods for threat assessment,
    gatecamp detection, and activity summaries.
    """

    def __init__(self):
        """Initialize the threat cache."""
        self._db = None

    def _get_db(self):
        """Lazy-load database connection."""
        if self._db is None:
            from .database import get_realtime_database

            self._db = get_realtime_database()
        return self._db

    def is_healthy(self) -> bool:
        """
        Check if real-time data is available and fresh.

        Healthy means:
        - Database is accessible
        - Poller has received data within last 5 minutes

        Returns:
            True if real-time data is available
        """
        try:
            db = self._get_db()
            last_poll = db.get_last_poll_time()

            if last_poll is None:
                return False

            age = (datetime.now(timezone.utc).replace(tzinfo=None) - last_poll).total_seconds()
            return age <= POLLER_HEALTHY_MAX_POLL_AGE_SECONDS

        except Exception as e:
            logger.debug("ThreatCache health check failed: %s", e)
            return False

    def get_recent_kills(
        self,
        system_id: int | None = None,
        since_minutes: int = 60,
        limit: int = 100,
    ) -> list[ProcessedKill]:
        """
        Get recent kills, optionally filtered by system.

        Args:
            system_id: Filter to specific system (None = all systems)
            since_minutes: How far back to look
            limit: Maximum results to return

        Returns:
            List of ProcessedKill objects, newest first
        """
        db = self._get_db()
        return db.get_recent_kills(
            system_id=system_id,
            since_minutes=since_minutes,
            limit=limit,
        )

    def get_kills_in_systems(
        self,
        system_ids: list[int],
        since_minutes: int = 60,
    ) -> list[ProcessedKill]:
        """
        Get recent kills in multiple systems.

        Args:
            system_ids: System IDs to query
            since_minutes: How far back to look

        Returns:
            List of ProcessedKill objects, newest first
        """
        db = self._get_db()
        return db.get_kills_in_systems(system_ids, since_minutes)

    def get_gatecamp_status(
        self,
        system_id: int,
        system_name: str | None = None,
        war_context: WarContextProvider | None = None,
    ) -> GatecampStatus | None:
        """
        Check for active gatecamp in a system.

        Args:
            system_id: System ID to check
            system_name: Optional system name for display
            war_context: Optional war context provider for filtering war kills

        Returns:
            GatecampStatus if camp detected, None otherwise
        """
        # Get kills from detection window
        db = self._get_db()
        kills = db.get_recent_kills(
            system_id=system_id,
            since_minutes=GATECAMP_WINDOW_SECONDS // 60,
        )

        result = detect_gatecamp(system_id, kills, system_name, war_context)

        # Save detection to tracking table if detected
        if result:
            self._save_detection(result)

        return result

    def get_activity_summary(
        self,
        system_id: int,
        system_name: str | None = None,
    ) -> RealtimeActivitySummary:
        """
        Get real-time activity summary for a system.

        Args:
            system_id: System ID to query
            system_name: Optional system name for display

        Returns:
            RealtimeActivitySummary with kill counts and gatecamp status
        """
        db = self._get_db()

        # Get kills for different time windows
        kills_1h = db.get_recent_kills(system_id=system_id, since_minutes=60)
        kills_10m = [
            k
            for k in kills_1h
            if k.kill_time
            >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        ]

        # Count pod kills separately
        pod_kills_1h = sum(1 for k in kills_1h if k.is_pod_kill)
        pod_kills_10m = sum(1 for k in kills_10m if k.is_pod_kill)

        # Get recent kills for display (non-pod, limit 5)
        recent_kills = []
        for kill in kills_1h[:10]:  # Check first 10
            if not kill.is_pod_kill:
                recent_kills.append(
                    {
                        "kill_id": kill.kill_id,
                        "kill_time": kill.kill_time.isoformat(),
                        "victim_ship_type_id": kill.victim_ship_type_id,
                        "attacker_count": kill.attacker_count,
                        "total_value": kill.total_value,
                    }
                )
                if len(recent_kills) >= 5:
                    break

        # Check for gatecamp
        gatecamp = detect_gatecamp(system_id, kills_10m, system_name) if kills_10m else None

        if gatecamp:
            self._save_detection(gatecamp)

        # Get watched entity kill data
        watched_kills = db.get_watched_entity_kills(
            since_minutes=60,
            system_ids=[system_id],
            limit=10,
        )
        watched_entity_details = []
        for wk in watched_kills[:5]:  # Limit details to 5
            watched_entity_details.append(
                {
                    "kill_id": wk.kill_id,
                    "kill_time": wk.kill_time.isoformat(),
                    "victim_ship_type_id": wk.victim_ship_type_id,
                    "attacker_count": wk.attacker_count,
                }
            )

        return RealtimeActivitySummary(
            system_id=system_id,
            kills_10m=len(kills_10m),
            kills_1h=len(kills_1h),
            pod_kills_10m=pod_kills_10m,
            pod_kills_1h=pod_kills_1h,
            recent_kills=recent_kills,
            gatecamp=gatecamp,
            watched_entity_kills_1h=len(watched_kills),
            watched_entity_details=watched_entity_details,
        )

    def get_activity_for_systems(
        self,
        system_ids: list[int],
        system_names: dict[int, str] | None = None,
    ) -> dict[int, RealtimeActivitySummary]:
        """
        Get activity summaries for multiple systems.

        Args:
            system_ids: System IDs to query
            system_names: Optional mapping of system IDs to names

        Returns:
            Dict mapping system_id to RealtimeActivitySummary
        """
        names = system_names or {}
        return {
            system_id: self.get_activity_summary(
                system_id,
                system_name=names.get(system_id),
            )
            for system_id in system_ids
        }

    def detect_activity_spike(
        self,
        system_id: int,
        spike_threshold: float = 2.0,
    ) -> tuple[bool, float, float] | None:
        """
        Detect if current activity is significantly above baseline.

        Compares kills in the last hour against the previous 24-hour average
        to identify activity spikes that may indicate forming threats.

        Args:
            system_id: System ID to check
            spike_threshold: Multiplier threshold (current > baseline * threshold = spike)

        Returns:
            (is_spike, current_hourly_rate, baseline_rate) if sufficient data,
            None if insufficient historical data (<24 hours)
        """
        db = self._get_db()

        # Get kills from last hour
        kills_1h = db.get_recent_kills(system_id=system_id, since_minutes=60)
        current_hourly_rate = float(len(kills_1h))

        # Get kills from last 24 hours (for baseline calculation)
        kills_24h = db.get_recent_kills(system_id=system_id, since_minutes=1440)

        # Need at least some historical data beyond the current hour
        # If we only have data from the last hour, we can't calculate a baseline
        if len(kills_24h) <= len(kills_1h):
            # Not enough historical data - the 24h kills are all from the last hour
            return None

        # Calculate baseline: average hourly rate over 24h excluding current hour
        # This prevents the current spike from inflating the baseline
        historical_kills = len(kills_24h) - len(kills_1h)
        historical_hours = 23  # 24 hours minus the current hour
        baseline_rate = historical_kills / historical_hours

        # Avoid division by zero and require meaningful baseline
        if baseline_rate < 0.1:
            # System is normally very quiet - use a minimum baseline
            # to avoid false positives from single kills
            baseline_rate = 0.1

        # Detect spike
        is_spike = current_hourly_rate > (baseline_rate * spike_threshold)

        return (is_spike, current_hourly_rate, baseline_rate)

    def _save_detection(self, status: GatecampStatus) -> None:
        """
        Save gatecamp detection for backtesting analysis.

        Deduplicates by checking if a detection for the same system
        exists within the last 5 minutes.

        Args:
            status: Detected gatecamp status
        """
        try:
            db = self._get_db()
            conn = db._get_connection()

            now = int(time.time())
            dedup_window = now - 300  # 5 minutes

            # Check for recent detection of same system
            existing = conn.execute(
                """
                SELECT 1 FROM gatecamp_detections
                WHERE system_id = ? AND detected_at > ?
                LIMIT 1
                """,
                (status.system_id, dedup_window),
            ).fetchone()

            if existing:
                # Already have a recent detection for this system
                return

            conn.execute(
                """
                INSERT INTO gatecamp_detections (
                    system_id, detected_at, confidence, kill_count,
                    attacker_corps, force_asymmetry, is_smartbomb
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    status.system_id,
                    now,
                    status.confidence,
                    status.kill_count,
                    json.dumps(status.attacker_corps),
                    status.force_asymmetry,
                    1 if status.is_smartbomb_camp else 0,
                ),
            )
            conn.commit()
        except Exception as e:
            # Non-critical - don't fail on tracking errors
            logger.debug("Failed to save gatecamp detection: %s", e)

    def cleanup_old_data(
        self,
        kill_retention_hours: int = 24,
        detection_retention_days: int = 7,
    ) -> tuple[int, int]:
        """
        Clean up old kills and detections.

        Args:
            kill_retention_hours: Hours to retain kills
            detection_retention_days: Days to retain detections

        Returns:
            Tuple of (kills_deleted, detections_deleted)
        """
        db = self._get_db()
        conn = db._get_connection()

        # Clean kills (delegate to existing method)
        kills_deleted = db.cleanup_old_kills(kill_retention_hours)

        # Clean detections
        cutoff = int(time.time()) - (detection_retention_days * 86400)
        cursor = conn.execute(
            "DELETE FROM gatecamp_detections WHERE detected_at < ?",
            (cutoff,),
        )
        conn.commit()
        detections_deleted = cursor.rowcount

        if detections_deleted > 0:
            logger.info(
                "Cleaned up %d old detections (retention: %dd)",
                detections_deleted,
                detection_retention_days,
            )

        return kills_deleted, detections_deleted


# =============================================================================
# Module-level singleton
# =============================================================================

_threat_cache: ThreatCache | None = None


def get_threat_cache() -> ThreatCache:
    """Get or create the threat cache singleton."""
    global _threat_cache
    if _threat_cache is None:
        _threat_cache = ThreatCache()
    return _threat_cache


def reset_threat_cache() -> None:
    """Reset the threat cache singleton."""
    global _threat_cache
    _threat_cache = None
