"""
Notification Manager.

Orchestrates Discord webhook notifications for kill events,
including LLM-generated tactical commentary when patterns warrant.

Supports multi-webhook routing for sending notifications to different
Discord channels based on region, trigger type, and value thresholds.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ....core.logging import get_logger
from .commentary import CommentaryGenerator, CommentaryStyle, create_commentary_generator
from .discord_client import DiscordClient
from .formatter import MessageFormatter, format_isk
from .patterns import PatternContext, PatternDetector
from .profile_evaluator import ProfileEvaluator
from .profile_loader import ProfileLoader
from .queue import WebhookQueue

if TYPE_CHECKING:
    from ..entity_filter import EntityMatchResult
    from ..models import ProcessedKill
    from ..threat_cache import GatecampStatus, ThreatCache
    from ..war_context import KillWarContext
    from .npc_factions import NPCFactionTriggerResult
    from .profiles import NotificationProfile

logger = get_logger(__name__)


@dataclass
class NotificationHealth:
    """Health status of the notification system."""

    is_configured: bool
    is_healthy: bool
    is_paused: bool
    is_quiet_hours: bool
    success_rate: float
    queue_depth: int
    active_throttles: int
    last_success: datetime | None
    next_active_time: datetime | None = None
    webhook_count: int = 1
    webhooks_healthy: dict[str, bool] = field(default_factory=dict)


@dataclass
class NotificationManager:
    """
    Orchestrates the notification pipeline.

    Flow:
    1. Evaluate kill against all profiles
    2. Check topology filter (per profile)
    3. Check triggers (per profile)
    4. Check throttle (per profile, system, trigger)
    5. Check quiet hours (per profile)
    6. Detect patterns for commentary
    7. Generate LLM commentary if warranted
    8. Format message with commentary
    9. Queue for sending to each matched profile's webhook
    10. Process queues (rate limited)

    Uses YAML notification profiles from userdata/notifications/.
    """

    threat_cache: ThreatCache | None = None

    # Profile-based notification system
    _profiles: list[NotificationProfile] = field(default_factory=list, repr=False)
    _evaluator: ProfileEvaluator | None = field(default=None, repr=False)

    # Webhook clients and queues (keyed by URL)
    _clients: dict[str, DiscordClient] = field(default_factory=dict, repr=False)
    _queues: dict[str, WebhookQueue] = field(default_factory=dict, repr=False)

    # Message formatter
    _formatter: MessageFormatter = field(default_factory=MessageFormatter)

    # Pattern detection and commentary generation
    _pattern_detector: PatternDetector | None = field(default=None, repr=False)
    _commentary_generators: dict[str, CommentaryGenerator] = field(default_factory=dict, repr=False)

    # Background task
    _process_task: asyncio.Task | None = field(default=None, repr=False)
    _running: bool = False

    def __post_init__(self) -> None:
        """Initialize components from profiles."""
        self._init_profiles()
        self._init_pattern_detector()

    def _init_profiles(self) -> None:
        """
        Initialize from notification profiles.

        Loads profiles from userdata/notifications/. If no profiles exist,
        the manager will be unconfigured.
        """
        try:
            profiles = ProfileLoader.load_enabled_profiles()
            if not profiles:
                logger.info("No enabled notification profiles found")
                return

            self._profiles = profiles
            self._evaluator = ProfileEvaluator(profiles)

            # Initialize webhook clients for each profile
            self._init_profile_webhooks()

            logger.info(
                "Notification manager initialized with %d profiles",
                len(self._profiles),
            )

        except Exception as e:
            logger.error("Failed to load notification profiles: %s", e)
            self._profiles = []
            self._evaluator = None

    def _init_profile_webhooks(self) -> None:
        """Initialize Discord clients and queues for profile webhooks."""
        urls_seen: set[str] = set()

        for profile in self._profiles:
            url = profile.webhook_url
            if url and url not in urls_seen:
                urls_seen.add(url)
                client = DiscordClient(webhook_url=url)
                self._clients[url] = client
                self._queues[url] = WebhookQueue(client=client)
                logger.debug(
                    "Initialized webhook client for profile '%s'",
                    profile.name,
                )

        logger.info(
            "Initialized %d webhook client(s) for %d profiles",
            len(self._clients),
            len(self._profiles),
        )

    def _init_pattern_detector(self) -> None:
        """Initialize pattern detector if threat cache is available."""
        if self.threat_cache:
            self._pattern_detector = PatternDetector(self.threat_cache)
            logger.debug("Pattern detector initialized")

    def _get_commentary_generator(self, profile: NotificationProfile) -> CommentaryGenerator | None:
        """
        Get or create a commentary generator for a profile.

        Args:
            profile: Notification profile with commentary config

        Returns:
            CommentaryGenerator if commentary is enabled, None otherwise
        """
        if not profile.commentary or not profile.commentary.enabled:
            return None

        # Check if we already have a generator for this profile
        if profile.name in self._commentary_generators:
            return self._commentary_generators[profile.name]

        # Create new generator from profile config
        config = {
            "model": profile.commentary.model,
            "max_tokens": profile.commentary.max_tokens,
            "timeout_ms": profile.commentary.timeout_ms,
            "cost_limit_daily_usd": profile.commentary.cost_limit_daily_usd,
            "persona": profile.commentary.persona,
            "style": profile.commentary.style,
            "max_chars": profile.commentary.max_chars,
        }

        try:
            generator = create_commentary_generator(config=config)
            if generator.is_configured:
                self._commentary_generators[profile.name] = generator
                logger.info(
                    "Commentary generator created for profile '%s' (style=%s)",
                    profile.name,
                    profile.commentary.style or "conversational",
                )
                return generator
            else:
                logger.warning(
                    "Commentary enabled for profile '%s' but API key not configured",
                    profile.name,
                )
                return None
        except Exception as e:
            logger.error(
                "Failed to create commentary generator for profile '%s': %s",
                profile.name,
                e,
            )
            return None

    async def _generate_commentary_for_profile(
        self,
        profile: NotificationProfile,
        pattern_context: PatternContext,
        notification_text: str,
        npc_faction_result: NPCFactionTriggerResult | None = None,
        system_display: str | None = None,
        ship_display: str | None = None,
    ) -> tuple[str | None, str | None]:
        """
        Generate commentary for a profile if warranted.

        Args:
            profile: Notification profile
            pattern_context: Detected patterns
            notification_text: The notification being sent
            npc_faction_result: NPC faction result if applicable
            system_display: System display string for token validation (may be
                resolved name like "Tama" or fallback like "System 30002813")
            ship_display: Ship display string for token validation (may be
                resolved name like "Vexor" or fallback like "Ship 17740" or "Capsule")

        Returns:
            Tuple of (commentary text, persona name) or (None, None)
        """
        if not profile.commentary or not profile.commentary.enabled:
            return None, None

        # Check warrant threshold
        warrant_score = pattern_context.warrant_score()
        if warrant_score < profile.commentary.warrant_threshold:
            logger.debug(
                "Kill %d: warrant score %.2f below threshold %.2f for profile '%s'",
                pattern_context.kill.kill_id,
                warrant_score,
                profile.commentary.warrant_threshold,
                profile.name,
            )
            return None, None

        generator = self._get_commentary_generator(profile)
        if not generator:
            return None, None

        # Determine style override from profile config
        style = None
        if profile.commentary.style:
            try:
                style = CommentaryStyle(profile.commentary.style)
            except ValueError:
                pass

        try:
            commentary = await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text=notification_text,
                style=style,
                system_display=system_display,
                ship_display=ship_display,
            )

            if commentary:
                # Get persona name from generator
                persona_name = generator._persona_loader.get_persona_name()
                logger.debug(
                    "Generated commentary for kill %d, profile '%s': %s",
                    pattern_context.kill.kill_id,
                    profile.name,
                    commentary[:50] + "..." if len(commentary) > 50 else commentary,
                )
                return commentary, persona_name

        except Exception as e:
            logger.error(
                "Commentary generation failed for profile '%s': %s",
                profile.name,
                e,
            )

        return None, None

    @property
    def is_configured(self) -> bool:
        """Check if notifications are configured."""
        return len(self._profiles) > 0

    async def start(self) -> None:
        """Start the background queue processor."""
        if not self.is_configured:
            logger.debug("Notifications not configured, skipping start")
            return

        if self._running:
            return

        self._running = True
        self._process_task = asyncio.create_task(self._process_loop())
        logger.info("Notification manager started")

    async def stop(self) -> None:
        """Stop the background queue processor."""
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
            self._process_task = None

        # Close all webhook clients
        for url, client in self._clients.items():
            try:
                await client.close()
            except Exception as e:
                logger.warning("Error closing webhook client for %s: %s", url[:50], e)

        # Close all commentary generators
        for name, generator in self._commentary_generators.items():
            try:
                await generator.close()
            except Exception as e:
                logger.warning("Error closing commentary generator for %s: %s", name, e)

        self._clients.clear()
        self._queues.clear()
        self._commentary_generators.clear()

        logger.info("Notification manager stopped")

    async def _process_loop(self) -> None:
        """Background loop to process queued notifications across all webhooks."""
        while self._running:
            try:
                total_sent = 0

                # Process all webhook queues
                for _url, queue in self._queues.items():
                    if queue.depth > 0:
                        sent = await queue.process_queue()
                        if sent > 0:
                            total_sent += sent

                if total_sent > 0:
                    logger.debug("Processed %d webhook notifications", total_sent)

                # Clean up throttle entries periodically
                if self._evaluator:
                    self._evaluator.cleanup_throttles()

                # Sleep briefly between iterations
                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in notification process loop: %s", e)
                await asyncio.sleep(5)  # Back off on error

    async def process_kill(
        self,
        kill: ProcessedKill,
        entity_match: EntityMatchResult | None = None,
        gatecamp_status: GatecampStatus | None = None,
        war_context: KillWarContext | None = None,
        system_name: str | None = None,
        ship_name: str | None = None,
        attacker_group: str | None = None,
    ) -> bool:
        """
        Process a kill for notification.

        Evaluates the kill against all enabled profiles and sends notifications
        to each matching profile's webhook.

        Args:
            kill: The processed killmail
            entity_match: Entity match result from watchlist filter
            gatecamp_status: Gatecamp status for the system
            war_context: Optional war context for the kill
            system_name: Optional system name for display
            ship_name: Optional ship name for display
            attacker_group: Optional attacker group name

        Returns:
            True if notification was queued to at least one profile, False otherwise
        """
        if not self.is_configured:
            return False

        if not self._evaluator:
            logger.error("Profile evaluator not initialized")
            return False

        # Evaluate kill against all profiles
        eval_result = self._evaluator.evaluate(
            kill=kill,
            entity_match=entity_match,
            gatecamp_status=gatecamp_status,
            war_context=war_context,
        )

        if not eval_result.has_matches:
            logger.debug(
                "Kill %d: no profile matches (filtered: topology=%d, throttle=%d, "
                "quiet_hours=%d, triggers=%d)",
                kill.kill_id,
                len(eval_result.filtered_by_topology),
                len(eval_result.filtered_by_throttle),
                len(eval_result.filtered_by_quiet_hours),
                len(eval_result.filtered_by_triggers),
            )
            return False

        # Detect patterns for commentary (once, shared across profiles)
        pattern_context: PatternContext | None = None
        any_profile_wants_commentary = any(
            m.profile.commentary and m.profile.commentary.enabled for m in eval_result.matches
        )

        if any_profile_wants_commentary and self._pattern_detector:
            # Get NPC faction result from first match that has it
            npc_faction_result = None
            for match in eval_result.matches:
                if match.trigger_result.npc_faction:
                    npc_faction_result = match.trigger_result.npc_faction
                    break

            try:
                pattern_context = await self._pattern_detector.detect_patterns(
                    kill=kill,
                    entity_match=entity_match,
                    npc_faction_result=npc_faction_result,
                )
                if pattern_context.has_patterns:
                    logger.debug(
                        "Kill %d: detected %d patterns (warrant=%.2f)",
                        kill.kill_id,
                        len(pattern_context.patterns),
                        pattern_context.warrant_score(),
                    )
            except Exception as e:
                logger.error("Pattern detection failed for kill %d: %s", kill.kill_id, e)
                pattern_context = None

        # Send to each matching profile's webhook
        queued_count = 0

        for match in eval_result.matches:
            profile = match.profile
            trigger_result = match.trigger_result

            # Generate commentary if profile has it enabled and patterns warrant it
            commentary = None
            persona_name = None

            if pattern_context and profile.commentary and profile.commentary.enabled:
                # Build notification text for LLM context (matches embed format exactly)
                ship_display = (
                    "Capsule"
                    if kill.is_pod_kill
                    else (ship_name or f"Ship {kill.victim_ship_type_id}")
                )
                system_display = system_name or f"System {kill.solar_system_id}"
                notification_text = (
                    f"{ship_display} destroyed in {system_display}, "
                    f"{kill.attacker_count} attackers, {format_isk(kill.total_value)} ISK"
                )

                # Pass display strings for token validation
                # This ensures fallback strings like "Ship 17740" are also protected
                commentary, persona_name = await self._generate_commentary_for_profile(
                    profile=profile,
                    pattern_context=pattern_context,
                    notification_text=notification_text,
                    npc_faction_result=trigger_result.npc_faction,
                    system_display=system_display,
                    ship_display=ship_display,
                )

            # Format message for this profile (with or without commentary)
            if commentary:
                payload = self._formatter.format_kill_with_commentary(
                    kill=kill,
                    trigger_result=trigger_result,
                    commentary=commentary,
                    persona_name=persona_name,
                    entity_match=entity_match,
                    system_name=system_name,
                    ship_name=ship_name,
                    attacker_group=attacker_group,
                )
            else:
                payload = self._formatter.format_kill(
                    kill=kill,
                    trigger_result=trigger_result,
                    entity_match=entity_match,
                    system_name=system_name,
                    ship_name=ship_name,
                    attacker_group=attacker_group,
                )

            # Queue for profile's webhook
            queue = self._queues.get(profile.webhook_url)
            if queue:
                primary_trigger = trigger_result.primary_trigger
                queue.enqueue(
                    payload=payload,
                    kill_id=kill.kill_id,
                    trigger_type=primary_trigger.value if primary_trigger else "unknown",
                )
                queued_count += 1
                logger.debug(
                    "Queued kill %d to profile '%s' (triggers: %s, commentary=%s)",
                    kill.kill_id,
                    profile.name,
                    [t.value for t in trigger_result.trigger_types]
                    if trigger_result.trigger_types
                    else [],
                    "yes" if commentary else "no",
                )
            else:
                logger.warning(
                    "No queue found for profile '%s' webhook",
                    profile.name,
                )

        if queued_count > 0:
            logger.info(
                "Queued notification for kill %d to %d profile(s) (system=%d)",
                kill.kill_id,
                queued_count,
                kill.solar_system_id,
            )

        return queued_count > 0

    async def test_webhook(self, profile_name: str | None = None) -> tuple[bool, str]:
        """
        Send a test message to validate webhook configuration.

        Args:
            profile_name: Optional profile name to test (uses first profile if None)

        Returns:
            Tuple of (success, message)
        """
        if not self.is_configured:
            return False, "No notification profiles configured"

        # Find profile to test
        profile = None
        if profile_name:
            profile = next((p for p in self._profiles if p.name == profile_name), None)
            if not profile:
                return False, f"Profile not found: {profile_name}"
        else:
            profile = self._profiles[0] if self._profiles else None

        if not profile:
            return False, "No profiles available"

        client = self._clients.get(profile.webhook_url)
        if not client:
            return False, f"No client for profile: {profile.name}"

        payload = self._formatter.format_test_message()
        result = await client.send(payload)

        if result.success:
            return True, f"Test message sent to profile '{profile.name}'"
        else:
            return False, f"Failed to send test message: {result.error}"

    def get_health_status(self) -> NotificationHealth:
        """Get current health status of the notification system."""
        if not self.is_configured:
            return NotificationHealth(
                is_configured=False,
                is_healthy=False,
                is_paused=False,
                is_quiet_hours=False,
                success_rate=0.0,
                queue_depth=0,
                active_throttles=0,
                last_success=None,
            )

        # Aggregate health across all webhook queues
        total_queue_depth = 0
        total_sent = 0
        total_failed = 0
        any_paused = False
        all_healthy = True
        latest_success: datetime | None = None
        webhooks_healthy: dict[str, bool] = {}

        for url, queue in self._queues.items():
            queue_health = queue.get_health()
            total_queue_depth += queue_health.queue_depth

            if queue_health.is_paused:
                any_paused = True

            client = self._clients.get(url)
            if client:
                total_sent += client._total_sent
                total_failed += client._total_failed
                is_healthy = client.is_healthy
                all_healthy = all_healthy and is_healthy

                # Track health by webhook name (find name from profile)
                webhook_name = self._get_webhook_name_for_url(url)
                webhooks_healthy[webhook_name] = is_healthy

                if client._last_success:
                    if latest_success is None or client._last_success > latest_success:
                        latest_success = client._last_success

        # Calculate overall success rate
        total_attempts = total_sent + total_failed
        success_rate = total_sent / total_attempts if total_attempts > 0 else 1.0

        # Get active throttles from evaluator
        active_throttles = 0
        if self._evaluator:
            active_throttles = self._evaluator.get_metrics().get("active_throttles", 0)

        return NotificationHealth(
            is_configured=True,
            is_healthy=all_healthy and not any_paused,
            is_paused=any_paused,
            is_quiet_hours=False,  # Quiet hours handled per-profile now
            success_rate=success_rate,
            queue_depth=total_queue_depth,
            active_throttles=active_throttles,
            last_success=latest_success,
            next_active_time=None,
            webhook_count=len(self._clients),
            webhooks_healthy=webhooks_healthy,
        )

    def _get_webhook_name_for_url(self, url: str) -> str:
        """Get webhook config name for a URL."""
        for profile in self._profiles:
            if profile.webhook_url == url:
                return f"profile:{profile.name}"
        return url[:30] + "..."

    def get_routing_summary(self) -> dict[str, Any]:
        """
        Get summary of webhook routing configuration.

        Returns:
            Dict with routing configuration details
        """
        if not self.is_configured:
            return {"configured": False}

        return {
            "configured": True,
            "profile_count": len(self._profiles),
            "webhook_count": len(self._clients),
            "profiles": [
                {
                    "name": p.name,
                    "display_name": p.display_name,
                    "enabled": p.enabled,
                    "system_count": p.system_count,
                }
                for p in self._profiles
            ],
        }


# Module-level singleton
_notification_manager: NotificationManager | None = None


def get_notification_manager() -> NotificationManager | None:
    """
    Get or create the notification manager singleton.

    Returns:
        NotificationManager instance, or None if not configured
    """
    global _notification_manager

    if _notification_manager is None:
        _notification_manager = NotificationManager()

    return _notification_manager


def reset_notification_manager() -> None:
    """Reset the notification manager singleton (for testing)."""
    global _notification_manager
    _notification_manager = None
