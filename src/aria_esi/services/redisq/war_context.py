"""
War Context Layer for Gatecamp Detection.

Provides war relationship tracking to distinguish between gatecamps
and war engagements. War engagements between known belligerents
should not be classified as gatecamps.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from ...core.logging import get_logger

if TYPE_CHECKING:
    from .models import ProcessedKill

logger = get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# War inference thresholds
WAR_INFERENCE_MIN_KILLS = 3  # Minimum kills to infer a war
WAR_INFERENCE_WINDOW_SECONDS = 3600  # 1 hour window for inference
WAR_RELATIONSHIP_TTL_SECONDS = 86400  # 24 hours before inferred wars expire

# Cleanup intervals
WAR_CLEANUP_INTERVAL_SECONDS = 3600  # Check for stale wars every hour


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class WarRelationship:
    """
    Cached war relationship between two entities.

    Represents either a known war (from ESI) or an inferred war
    based on repeated kill patterns.
    """

    aggressor_id: int  # Alliance or corp ID
    defender_id: int  # Alliance or corp ID
    aggressor_type: str = "alliance"  # "alliance" or "corporation"
    defender_type: str = "alliance"  # "alliance" or "corporation"
    is_mutual: bool = False
    source: str = "inferred"  # "esi_sync" or "inferred"
    first_observed: datetime = field(default_factory=datetime.utcnow)
    last_observed: datetime = field(default_factory=datetime.utcnow)
    kill_count: int = 1

    def is_stale(self, ttl_seconds: int = WAR_RELATIONSHIP_TTL_SECONDS) -> bool:
        """Check if this relationship has not been observed recently."""
        age = (datetime.utcnow() - self.last_observed).total_seconds()
        return age > ttl_seconds

    def touch(self) -> None:
        """Update last observed time and increment kill count."""
        self.last_observed = datetime.utcnow()
        self.kill_count += 1


@dataclass
class KillWarContext:
    """
    War context for a specific kill.

    Indicates whether a kill is part of a known war engagement
    and provides relationship details.
    """

    is_war_engagement: bool = False
    relationship: WarRelationship | None = None
    attacker_side: str | None = None  # "aggressor", "defender", or None
    victim_side: str | None = None  # "aggressor", "defender", or None

    @property
    def is_mutual_war(self) -> bool:
        """Check if this is a mutual war (both parties declared)."""
        return self.relationship.is_mutual if self.relationship else False


# =============================================================================
# War Context Provider
# =============================================================================


class WarContextProvider:
    """
    Provides war context for kill analysis.

    Maintains an in-memory cache of known war relationships and
    infers new wars from repeated attacker/victim patterns.
    """

    def __init__(self):
        """Initialize the war context provider."""
        # In-memory cache: (entity1_id, entity2_id) -> WarRelationship
        # Keys are always ordered (min, max) for consistent lookup
        self._relationships: dict[tuple[int, int], WarRelationship] = {}

        # Pending observations for war inference
        # Key: (attacker_alliance, victim_alliance) -> list of (kill_id, timestamp)
        self._pending_observations: dict[tuple[int, int], list[tuple[int, float]]] = defaultdict(
            list
        )

        # Database reference (lazy loaded)
        self._db = None

        # Last cleanup time
        self._last_cleanup: float = 0.0

    def _get_db(self):
        """Lazy-load database connection."""
        if self._db is None:
            from .database import get_realtime_database

            self._db = get_realtime_database()
        return self._db

    def _make_key(self, id1: int, id2: int) -> tuple[int, int]:
        """Create a normalized key for relationship lookup."""
        return (min(id1, id2), max(id1, id2))

    # =========================================================================
    # War Relationship Management
    # =========================================================================

    def refresh_from_database(self) -> int:
        """
        Load known wars from database into memory cache.

        Returns:
            Number of relationships loaded
        """
        try:
            db = self._get_db()
            conn = db._get_connection()

            # Check if table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='known_wars'"
            )
            if not cursor.fetchone():
                logger.debug("known_wars table does not exist yet")
                return 0

            rows = conn.execute(
                """
                SELECT aggressor_alliance_id, aggressor_corp_id,
                       defender_alliance_id, defender_corp_id,
                       is_mutual, source, first_observed, last_observed, kill_count
                FROM known_wars
                WHERE last_observed > ?
                """,
                (int(time.time()) - WAR_RELATIONSHIP_TTL_SECONDS,),
            ).fetchall()

            loaded = 0
            for row in rows:
                # Prefer alliance IDs, fall back to corp IDs
                aggressor_id = row["aggressor_alliance_id"] or row["aggressor_corp_id"]
                defender_id = row["defender_alliance_id"] or row["defender_corp_id"]
                aggressor_type = "alliance" if row["aggressor_alliance_id"] else "corporation"
                defender_type = "alliance" if row["defender_alliance_id"] else "corporation"

                if not aggressor_id or not defender_id:
                    continue

                relationship = WarRelationship(
                    aggressor_id=aggressor_id,
                    defender_id=defender_id,
                    aggressor_type=aggressor_type,
                    defender_type=defender_type,
                    is_mutual=bool(row["is_mutual"]),
                    source=row["source"],
                    first_observed=datetime.fromtimestamp(row["first_observed"]),
                    last_observed=datetime.fromtimestamp(row["last_observed"]),
                    kill_count=row["kill_count"],
                )

                key = self._make_key(aggressor_id, defender_id)
                self._relationships[key] = relationship
                loaded += 1

            logger.info("Loaded %d war relationships from database", loaded)
            return loaded

        except Exception as e:
            logger.warning("Failed to load war relationships: %s", e)
            return 0

    def save_relationship(self, relationship: WarRelationship) -> None:
        """
        Persist a war relationship to database.

        Args:
            relationship: The relationship to save
        """
        try:
            db = self._get_db()
            conn = db._get_connection()

            # Check if table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='known_wars'"
            )
            if not cursor.fetchone():
                logger.debug("known_wars table does not exist yet, skipping save")
                return

            # Determine which ID fields to use
            aggressor_alliance_id = (
                relationship.aggressor_id if relationship.aggressor_type == "alliance" else None
            )
            aggressor_corp_id = (
                relationship.aggressor_id if relationship.aggressor_type == "corporation" else None
            )
            defender_alliance_id = (
                relationship.defender_id if relationship.defender_type == "alliance" else None
            )
            defender_corp_id = (
                relationship.defender_id if relationship.defender_type == "corporation" else None
            )

            conn.execute(
                """
                INSERT INTO known_wars (
                    aggressor_alliance_id, aggressor_corp_id,
                    defender_alliance_id, defender_corp_id,
                    is_mutual, source, first_observed, last_observed, kill_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(aggressor_alliance_id, defender_alliance_id)
                DO UPDATE SET
                    last_observed = excluded.last_observed,
                    kill_count = excluded.kill_count,
                    is_mutual = excluded.is_mutual
                """,
                (
                    aggressor_alliance_id,
                    aggressor_corp_id,
                    defender_alliance_id,
                    defender_corp_id,
                    1 if relationship.is_mutual else 0,
                    relationship.source,
                    int(relationship.first_observed.timestamp()),
                    int(relationship.last_observed.timestamp()),
                    relationship.kill_count,
                ),
            )
            conn.commit()

        except Exception as e:
            logger.debug("Failed to save war relationship: %s", e)

    def add_relationship(self, relationship: WarRelationship) -> None:
        """
        Add or update a war relationship in memory and database.

        Args:
            relationship: The relationship to add
        """
        key = self._make_key(relationship.aggressor_id, relationship.defender_id)

        existing = self._relationships.get(key)
        if existing:
            # Update existing relationship
            existing.touch()
            existing.is_mutual = existing.is_mutual or relationship.is_mutual
            if relationship.source == "esi_sync":
                existing.source = "esi_sync"  # ESI source takes precedence
            self.save_relationship(existing)
        else:
            # Add new relationship
            self._relationships[key] = relationship
            self.save_relationship(relationship)
            logger.info(
                "New war relationship: %d vs %d (source=%s)",
                relationship.aggressor_id,
                relationship.defender_id,
                relationship.source,
            )

    # =========================================================================
    # Kill Analysis
    # =========================================================================

    def check_kill(self, kill: ProcessedKill) -> KillWarContext:
        """
        Check if a kill is part of a war engagement.

        Args:
            kill: The processed kill to analyze

        Returns:
            KillWarContext with war engagement status
        """
        # Get alliance IDs (prefer alliance over corp for war matching)
        attacker_alliances = set(kill.attacker_alliances)
        victim_alliance = kill.victim_alliance_id

        # If no alliance info, fall back to corp matching
        if not attacker_alliances and kill.attacker_corps:
            attacker_alliances = set(kill.attacker_corps)
        if not victim_alliance:
            victim_alliance = kill.victim_corporation_id

        if not attacker_alliances or not victim_alliance:
            return KillWarContext(is_war_engagement=False)

        # Check for existing war relationship
        for attacker_id in attacker_alliances:
            key = self._make_key(attacker_id, victim_alliance)
            relationship = self._relationships.get(key)

            if relationship and not relationship.is_stale():
                # Found active war relationship
                relationship.touch()

                # Determine sides
                if attacker_id == relationship.aggressor_id:
                    attacker_side = "aggressor"
                    victim_side = "defender"
                else:
                    attacker_side = "defender"
                    victim_side = "aggressor"

                return KillWarContext(
                    is_war_engagement=True,
                    relationship=relationship,
                    attacker_side=attacker_side,
                    victim_side=victim_side,
                )

        # No existing relationship - record observation for potential inference
        self._record_observation(kill, attacker_alliances, victim_alliance)

        return KillWarContext(is_war_engagement=False)

    def is_war_kill(self, kill: ProcessedKill) -> bool:
        """
        Quick check if a kill is a war engagement.

        Args:
            kill: The kill to check

        Returns:
            True if kill is part of a war engagement
        """
        return self.check_kill(kill).is_war_engagement

    def _record_observation(
        self,
        kill: ProcessedKill,
        attacker_alliances: set[int],
        victim_alliance: int,
    ) -> None:
        """
        Record an observation for potential war inference.

        If we see the same attacker/victim pattern multiple times
        within a short window, we infer an active war.

        Args:
            kill: The kill observation
            attacker_alliances: Attacker alliance IDs
            victim_alliance: Victim alliance ID
        """
        now = time.time()
        kill_id = kill.kill_id

        for attacker_id in attacker_alliances:
            pair = (attacker_id, victim_alliance)

            # Add observation
            self._pending_observations[pair].append((kill_id, now))

            # Clean old observations
            cutoff = now - WAR_INFERENCE_WINDOW_SECONDS
            self._pending_observations[pair] = [
                (kid, ts) for kid, ts in self._pending_observations[pair] if ts > cutoff
            ]

            # Check if we have enough observations to infer a war
            if len(self._pending_observations[pair]) >= WAR_INFERENCE_MIN_KILLS:
                self._infer_war(attacker_id, victim_alliance)

    def _infer_war(self, attacker_id: int, defender_id: int) -> None:
        """
        Infer a war relationship from repeated kill patterns.

        Args:
            attacker_id: The attacking alliance/corp ID
            defender_id: The defending alliance/corp ID
        """
        # Check if already have this relationship
        key = self._make_key(attacker_id, defender_id)
        if key in self._relationships:
            return

        # Create inferred war relationship
        relationship = WarRelationship(
            aggressor_id=attacker_id,
            defender_id=defender_id,
            aggressor_type="alliance",
            defender_type="alliance",
            is_mutual=False,  # Inferred wars are assumed one-sided initially
            source="inferred",
            kill_count=WAR_INFERENCE_MIN_KILLS,
        )

        self.add_relationship(relationship)
        logger.info(
            "Inferred war: %d vs %d from %d kills",
            attacker_id,
            defender_id,
            WAR_INFERENCE_MIN_KILLS,
        )

        # Clear pending observations for this pair
        pair = (attacker_id, defender_id)
        if pair in self._pending_observations:
            del self._pending_observations[pair]

    # =========================================================================
    # Batch Analysis
    # =========================================================================

    def filter_war_kills(
        self, kills: list[ProcessedKill]
    ) -> tuple[list[ProcessedKill], list[ProcessedKill]]:
        """
        Separate kills into war and non-war kills.

        Args:
            kills: List of kills to analyze

        Returns:
            Tuple of (war_kills, non_war_kills)
        """
        war_kills = []
        non_war_kills = []

        for kill in kills:
            if self.is_war_kill(kill):
                war_kills.append(kill)
            else:
                non_war_kills.append(kill)

        return war_kills, non_war_kills

    def get_war_context_for_kills(self, kills: list[ProcessedKill]) -> dict[int, KillWarContext]:
        """
        Get war context for a batch of kills.

        Args:
            kills: List of kills to analyze

        Returns:
            Dict mapping kill_id to KillWarContext
        """
        return {kill.kill_id: self.check_kill(kill) for kill in kills}

    # =========================================================================
    # Maintenance
    # =========================================================================

    def cleanup_stale(self) -> int:
        """
        Remove stale war relationships.

        Returns:
            Number of relationships removed
        """
        now = time.time()

        # Only run cleanup periodically
        if now - self._last_cleanup < WAR_CLEANUP_INTERVAL_SECONDS:
            return 0

        self._last_cleanup = now

        # Find stale relationships
        stale_keys = [
            key
            for key, rel in self._relationships.items()
            if rel.is_stale() and rel.source == "inferred"
        ]

        # Remove from memory
        for key in stale_keys:
            del self._relationships[key]

        # Remove from database
        if stale_keys:
            try:
                db = self._get_db()
                conn = db._get_connection()

                # Check if table exists
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='known_wars'"
                )
                if cursor.fetchone():
                    cutoff = int(time.time()) - WAR_RELATIONSHIP_TTL_SECONDS
                    conn.execute(
                        """
                        DELETE FROM known_wars
                        WHERE source = 'inferred' AND last_observed < ?
                        """,
                        (cutoff,),
                    )
                    conn.commit()
            except Exception as e:
                logger.debug("Failed to cleanup war relationships: %s", e)

        if stale_keys:
            logger.info("Cleaned up %d stale war relationships", len(stale_keys))

        return len(stale_keys)

    def get_stats(self) -> dict:
        """
        Get statistics about war context cache.

        Returns:
            Dict with cache statistics
        """
        total = len(self._relationships)
        inferred = sum(1 for r in self._relationships.values() if r.source == "inferred")
        esi = total - inferred

        return {
            "total_relationships": total,
            "inferred_wars": inferred,
            "esi_wars": esi,
            "pending_observations": sum(len(obs) for obs in self._pending_observations.values()),
        }


# =============================================================================
# Module-level singleton
# =============================================================================

_war_context_provider: WarContextProvider | None = None


def get_war_context_provider() -> WarContextProvider:
    """Get or create the war context provider singleton."""
    global _war_context_provider
    if _war_context_provider is None:
        _war_context_provider = WarContextProvider()
        _war_context_provider.refresh_from_database()
    return _war_context_provider


def reset_war_context_provider() -> None:
    """Reset the war context provider singleton."""
    global _war_context_provider
    _war_context_provider = None
