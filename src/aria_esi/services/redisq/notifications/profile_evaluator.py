"""
Profile Evaluator.

Evaluates kills against multiple notification profiles, returning which
profiles should send notifications for a given kill.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ....core.logging import get_logger
from .quiet_hours import QuietHoursChecker
from .throttle import ThrottleManager
from .triggers import TriggerResult, TriggerType, evaluate_triggers

if TYPE_CHECKING:
    from ..entity_filter import EntityMatchResult
    from ..interest import InterestCalculator
    from ..interest_v2 import InterestEngineV2, InterestResultV2
    from ..models import ProcessedKill
    from ..threat_cache import GatecampStatus
    from ..war_context import KillWarContext
    from .npc_factions import NPCFactionMapper
    from .profiles import NotificationProfile

logger = get_logger(__name__)

# Maximum profiles to load (soft limit)
MAX_PROFILES_SOFT = 10
MAX_PROFILES_HARD = 25


@dataclass
class ProfileMatch:
    """A profile that matched a kill, with trigger context."""

    profile: NotificationProfile
    trigger_result: TriggerResult
    interest_result: InterestResultV2 | None = None  # v2 engine result


@dataclass
class EvaluationResult:
    """Result of evaluating a kill against all profiles."""

    kill_id: int
    matches: list[ProfileMatch] = field(default_factory=list)
    filtered_by_topology: list[str] = field(default_factory=list)
    filtered_by_throttle: list[str] = field(default_factory=list)
    filtered_by_quiet_hours: list[str] = field(default_factory=list)
    filtered_by_triggers: list[str] = field(default_factory=list)
    filtered_by_interest: list[str] = field(default_factory=list)  # v2 engine filtering

    @property
    def has_matches(self) -> bool:
        """Check if any profiles matched."""
        return len(self.matches) > 0

    @property
    def match_count(self) -> int:
        """Get count of matching profiles."""
        return len(self.matches)


class ProfileEvaluator:
    """
    Evaluates kills against multiple notification profiles.

    Each profile has its own:
    - Topology filter (which systems to monitor)
    - Trigger configuration (what events to notify on)
    - Throttle settings (per-profile rate limiting)
    - Quiet hours (per-profile suppression windows)

    The evaluator initializes runtime state for each profile and provides
    O(profiles) evaluation per kill.
    """

    def __init__(self, profiles: list[NotificationProfile]):
        """
        Initialize evaluator with profiles.

        Args:
            profiles: List of enabled notification profiles
        """
        self.profiles = profiles
        self._initialized = False
        self._npc_faction_mapper: NPCFactionMapper | None = None

        # Warn about profile count
        if len(profiles) > MAX_PROFILES_SOFT:
            logger.warning(
                "Large number of profiles (%d) may impact performance. "
                "Consider consolidating profiles.",
                len(profiles),
            )

        if len(profiles) > MAX_PROFILES_HARD:
            logger.error(
                "Too many profiles (%d), limiting to %d",
                len(profiles),
                MAX_PROFILES_HARD,
            )
            self.profiles = profiles[:MAX_PROFILES_HARD]

        self._initialize_runtime_state()

    def _initialize_runtime_state(self) -> None:
        """Initialize runtime state for all profiles."""
        for profile in self.profiles:
            self._init_profile_state(profile)

        # Initialize NPC faction mapper if any profile uses npc_faction_kill trigger
        needs_npc_mapper = any(p.triggers.npc_faction_kill.enabled for p in self.profiles)
        if needs_npc_mapper:
            from .npc_factions import get_npc_faction_mapper

            self._npc_faction_mapper = get_npc_faction_mapper()
            logger.debug("Initialized NPC faction mapper for profile evaluator")

        self._initialized = True
        logger.info("Initialized runtime state for %d profiles", len(self.profiles))

    def _init_profile_state(self, profile: NotificationProfile) -> None:
        """
        Initialize runtime state for a single profile.

        Sets up:
        - TopologyFilter / InterestCalculator (v1) or InterestEngineV2 (v2)
        - ThrottleManager
        - QuietHoursChecker
        """
        # Initialize interest engine based on version
        if profile.uses_interest_v2:
            try:
                engine = self._build_v2_engine(profile)
                profile._interest_engine_v2 = engine
                profile._topology_filter = None  # v2 handles its own filtering
                logger.debug(
                    "Built v2 interest engine for profile '%s' (preset: %s)",
                    profile.name,
                    profile.interest.get("preset"),
                )
            except Exception as e:
                logger.warning(
                    "Failed to build v2 engine for profile '%s': %s, falling back to v1",
                    profile.name,
                    e,
                )
                profile._interest_engine_v2 = None
                # Try v1 as fallback
                if profile.has_topology:
                    try:
                        calculator = self._build_calculator(profile.topology)
                        profile._topology_filter = calculator
                    except Exception as e2:
                        logger.warning("v1 fallback also failed: %s", e2)
                        profile._topology_filter = None
        elif profile.has_topology:
            # v1 engine
            try:
                calculator = self._build_calculator(profile.topology)
                profile._topology_filter = calculator
                logger.debug(
                    "Built topology filter for profile '%s'",
                    profile.name,
                )
            except Exception as e:
                logger.warning(
                    "Failed to build topology for profile '%s': %s",
                    profile.name,
                    e,
                )
                profile._topology_filter = None

        # Initialize throttle manager
        profile._throttle = ThrottleManager(throttle_minutes=profile.throttle_minutes)

    def _build_calculator(self, topology: dict[str, Any]) -> InterestCalculator:
        """
        Build an InterestCalculator from topology config.

        Args:
            topology: Topology configuration dict

        Returns:
            InterestCalculator instance
        """
        from ..interest import ContextAwareTopologyConfig

        config = ContextAwareTopologyConfig.from_dict(topology)
        config.enabled = True  # Force enabled for profile topology
        return config.build_calculator()

    def _build_v2_engine(self, profile: NotificationProfile) -> InterestEngineV2:
        """
        Build an InterestEngineV2 from profile interest config.

        Args:
            profile: Notification profile with interest config

        Returns:
            InterestEngineV2 instance
        """
        from ..interest_v2 import InterestConfigV2, InterestEngineV2

        config = InterestConfigV2.from_dict(profile.interest)

        # Build context from profile
        context: dict[str, Any] = {}

        # Add topology context if available
        if profile.has_topology:
            topology = profile.topology
            systems = topology.get("geographic", {}).get("systems", [])
            if systems:
                home_systems = [s.get("id") for s in systems if s.get("id")]
                context["home_systems"] = home_systems

            # Add distance function if topology provides it
            # This will be resolved by the signal providers

        return InterestEngineV2(config, context)

    def evaluate(
        self,
        kill: ProcessedKill,
        entity_match: EntityMatchResult | None = None,
        gatecamp_status: GatecampStatus | None = None,
        war_context: KillWarContext | None = None,
    ) -> EvaluationResult:
        """
        Evaluate a kill against all profiles.

        Args:
            kill: ProcessedKill to evaluate
            entity_match: Entity match result from watchlist
            gatecamp_status: Gatecamp detection status
            war_context: Optional war context for the kill

        Returns:
            EvaluationResult with matching profiles
        """
        result = EvaluationResult(kill_id=kill.kill_id)

        for profile in self.profiles:
            if not profile.enabled:
                continue

            match_result = self._evaluate_profile(
                profile=profile,
                kill=kill,
                entity_match=entity_match,
                gatecamp_status=gatecamp_status,
                war_context=war_context,
            )

            if match_result is None:
                # Profile was filtered
                continue

            # Record filtering reason if available
            filter_reason = match_result.get("filtered_by")
            if filter_reason == "topology":
                result.filtered_by_topology.append(profile.name)
            elif filter_reason == "throttle":
                result.filtered_by_throttle.append(profile.name)
            elif filter_reason == "quiet_hours":
                result.filtered_by_quiet_hours.append(profile.name)
            elif filter_reason == "triggers":
                result.filtered_by_triggers.append(profile.name)
            elif filter_reason == "interest":
                result.filtered_by_interest.append(profile.name)
            elif "trigger_result" in match_result:
                # Profile matched
                result.matches.append(
                    ProfileMatch(
                        profile=profile,
                        trigger_result=match_result["trigger_result"],
                        interest_result=match_result.get("interest_result"),
                    )
                )

        return result

    def _evaluate_profile(
        self,
        profile: NotificationProfile,
        kill: ProcessedKill,
        entity_match: EntityMatchResult | None,
        gatecamp_status: GatecampStatus | None,
        war_context: KillWarContext | None = None,
    ) -> dict[str, Any] | None:
        """
        Evaluate a kill against a single profile.

        Routes to v1 or v2 evaluation based on profile configuration.

        Args:
            profile: Profile to evaluate against
            kill: Kill to evaluate
            entity_match: Entity match result
            gatecamp_status: Gatecamp status
            war_context: Optional war context for the kill

        Returns:
            Dict with trigger_result if matched, filtered_by key if filtered, None if error
        """
        # Check for v2 engine
        if hasattr(profile, "_interest_engine_v2") and profile._interest_engine_v2 is not None:
            return self._evaluate_profile_v2(
                profile=profile,
                kill=kill,
                entity_match=entity_match,
                gatecamp_status=gatecamp_status,
                war_context=war_context,
            )

        # v1 evaluation path
        return self._evaluate_profile_v1(
            profile=profile,
            kill=kill,
            entity_match=entity_match,
            gatecamp_status=gatecamp_status,
            war_context=war_context,
        )

    def _evaluate_profile_v2(
        self,
        profile: NotificationProfile,
        kill: ProcessedKill,
        entity_match: EntityMatchResult | None,
        gatecamp_status: GatecampStatus | None,
        war_context: KillWarContext | None = None,
    ) -> dict[str, Any] | None:
        """
        Evaluate a kill using v2 interest engine.

        The v2 engine handles:
        - Signal scoring across categories
        - Rule evaluation (always_notify, always_ignore, gates)
        - Interest aggregation
        - Tier determination

        Args:
            profile: Profile with v2 engine
            kill: Kill to evaluate
            entity_match: Entity match result
            gatecamp_status: Gatecamp status
            war_context: War context

        Returns:
            Dict with trigger_result and interest_result, or filtered_by key
        """
        try:
            engine = profile._interest_engine_v2
            if engine is None:
                return {"filtered_by": "no_engine"}

            # Calculate interest using v2 engine
            interest_result: InterestResultV2 = engine.calculate_interest(
                kill=kill,
                system_id=kill.solar_system_id,
                is_prefetch=False,
            )

            # Check if filtered by interest engine
            if not interest_result.should_notify:
                logger.debug(
                    "Profile '%s': kill %d filtered by interest (tier=%s, interest=%.2f)",
                    profile.name,
                    kill.kill_id,
                    interest_result.tier.value,
                    interest_result.interest,
                )
                return {"filtered_by": "interest"}

            # Check throttle
            primary_trigger = TriggerType.INTEREST_V2
            if profile._throttle is not None:
                if not profile._throttle.should_send(kill.solar_system_id, primary_trigger):
                    logger.debug(
                        "Profile '%s': kill %d throttled",
                        profile.name,
                        kill.kill_id,
                    )
                    return {"filtered_by": "throttle"}

            # Check quiet hours
            if profile.quiet_hours.enabled:
                checker = QuietHoursChecker(config=profile.quiet_hours)
                if checker.is_quiet_time():
                    logger.debug(
                        "Profile '%s': kill %d filtered by quiet hours",
                        profile.name,
                        kill.kill_id,
                    )
                    return {"filtered_by": "quiet_hours"}

            # Profile matched!
            logger.debug(
                "Profile '%s': kill %d matched via v2 (tier=%s, interest=%.2f)",
                profile.name,
                kill.kill_id,
                interest_result.tier.value,
                interest_result.interest,
            )

            # Record throttle
            if profile._throttle is not None:
                profile._throttle.record_sent(kill.solar_system_id, primary_trigger)

            # Create a minimal trigger result for compatibility
            trigger_result = TriggerResult(
                should_notify=True,
                trigger_types=[],  # v2 doesn't use trigger types
            )

            return {
                "trigger_result": trigger_result,
                "interest_result": interest_result,
            }

        except Exception as e:
            logger.error(
                "Error evaluating v2 profile '%s' for kill %d: %s",
                profile.name,
                kill.kill_id,
                e,
            )
            return None

    def _evaluate_profile_v1(
        self,
        profile: NotificationProfile,
        kill: ProcessedKill,
        entity_match: EntityMatchResult | None,
        gatecamp_status: GatecampStatus | None,
        war_context: KillWarContext | None = None,
    ) -> dict[str, Any] | None:
        """
        Evaluate a kill using v1 topology + triggers.

        This is the legacy evaluation path for profiles without v2 interest config.
        """
        try:
            # Determine if we should skip topology for NPC faction kills
            # If npc_faction_kill is enabled with ignore_topology=True, we evaluate
            # the NPC trigger first to see if it would match before applying topology
            skip_topology_for_npc = (
                profile.triggers.npc_faction_kill.enabled
                and profile.triggers.npc_faction_kill.ignore_topology
            )

            # Check topology filter (unless we're potentially bypassing for NPC faction)
            topology_passed = True
            if profile._topology_filter is not None:
                if not profile._topology_filter.should_fetch(kill.solar_system_id):
                    if not skip_topology_for_npc:
                        # Topology check failed and we're not bypassing
                        logger.debug(
                            "Profile '%s': kill %d filtered by topology",
                            profile.name,
                            kill.kill_id,
                        )
                        return {"filtered_by": "topology"}
                    else:
                        # Mark that topology didn't pass - we'll check NPC trigger
                        topology_passed = False

            # Evaluate triggers
            trigger_result = self._evaluate_triggers_for_profile(
                profile=profile,
                kill=kill,
                entity_match=entity_match,
                gatecamp_status=gatecamp_status,
                war_context=war_context,
            )

            # If topology didn't pass, only allow NPC_FACTION_KILL trigger
            if not topology_passed:
                from .triggers import TriggerType

                if not trigger_result.is_npc_faction_kill:
                    # Not an NPC faction kill, enforce topology filtering
                    logger.debug(
                        "Profile '%s': kill %d filtered by topology (not NPC faction)",
                        profile.name,
                        kill.kill_id,
                    )
                    return {"filtered_by": "topology"}

                # Filter out non-NPC triggers since they didn't pass topology
                if trigger_result.trigger_types:
                    trigger_result.trigger_types = [
                        t for t in trigger_result.trigger_types if t == TriggerType.NPC_FACTION_KILL
                    ]
                    if not trigger_result.trigger_types:
                        trigger_result.should_notify = False

            if not trigger_result.should_notify:
                return {"filtered_by": "triggers"}

            primary_trigger = trigger_result.primary_trigger
            if not primary_trigger:
                return {"filtered_by": "triggers"}

            # Check throttle
            if profile._throttle is not None:
                if not profile._throttle.should_send(kill.solar_system_id, primary_trigger):
                    logger.debug(
                        "Profile '%s': kill %d throttled",
                        profile.name,
                        kill.kill_id,
                    )
                    return {"filtered_by": "throttle"}

            # Check quiet hours
            if profile.quiet_hours.enabled:
                checker = QuietHoursChecker(config=profile.quiet_hours)
                if checker.is_quiet_time():
                    logger.debug(
                        "Profile '%s': kill %d filtered by quiet hours",
                        profile.name,
                        kill.kill_id,
                    )
                    return {"filtered_by": "quiet_hours"}

            # Profile matched!
            logger.debug(
                "Profile '%s': kill %d matched (triggers: %s)",
                profile.name,
                kill.kill_id,
                [t.value for t in trigger_result.trigger_types]
                if trigger_result.trigger_types
                else [],
            )

            # Record throttle
            if profile._throttle is not None:
                profile._throttle.record_sent(kill.solar_system_id, primary_trigger)

            return {"trigger_result": trigger_result}

        except Exception as e:
            logger.error(
                "Error evaluating profile '%s' for kill %d: %s",
                profile.name,
                kill.kill_id,
                e,
            )
            return None

    def _evaluate_triggers_for_profile(
        self,
        profile: NotificationProfile,
        kill: ProcessedKill,
        entity_match: EntityMatchResult | None,
        gatecamp_status: GatecampStatus | None,
        war_context: KillWarContext | None = None,
    ) -> TriggerResult:
        """
        Evaluate triggers for a profile.

        Passes profile triggers directly to evaluate_triggers.
        """
        return evaluate_triggers(
            kill=kill,
            entity_match=entity_match,
            gatecamp_status=gatecamp_status,
            triggers=profile.triggers,
            war_context=war_context,
            npc_faction_mapper=self._npc_faction_mapper,
        )

    def cleanup_throttles(self) -> int:
        """
        Clean up expired throttle entries across all profiles.

        Returns:
            Total entries removed
        """
        total_removed = 0
        for profile in self.profiles:
            if profile._throttle is not None:
                removed = profile._throttle.cleanup_expired()
                total_removed += removed
        return total_removed

    def get_metrics(self) -> dict[str, Any]:
        """
        Get evaluator metrics.

        Returns:
            Dict with profile counts and throttle stats
        """
        active_throttles = 0
        for profile in self.profiles:
            if profile._throttle is not None:
                active_throttles += profile._throttle.active_throttles

        return {
            "profile_count": len(self.profiles),
            "initialized": self._initialized,
            "active_throttles": active_throttles,
            "profiles": [
                {
                    "name": p.name,
                    "has_topology": p._topology_filter is not None,
                    "throttle_minutes": p.throttle_minutes,
                    "quiet_hours_enabled": p.quiet_hours.enabled,
                }
                for p in self.profiles
            ],
        }

    def get_profile_by_name(self, name: str) -> NotificationProfile | None:
        """
        Get a profile by name.

        Args:
            name: Profile name

        Returns:
            Profile or None if not found
        """
        for profile in self.profiles:
            if profile.name == name:
                return profile
        return None

    def reload_profiles(self, profiles: list[NotificationProfile]) -> None:
        """
        Reload profiles (for hot-reload support).

        Args:
            profiles: New list of profiles
        """
        self.profiles = profiles[:MAX_PROFILES_HARD]
        self._initialized = False
        self._initialize_runtime_state()
        logger.info("Reloaded %d profiles", len(self.profiles))
