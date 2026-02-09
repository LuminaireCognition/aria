"""
Discord Notification Module.

Push notifications via Discord webhooks for real-time kill intel.

Components:
- NotificationProfile: YAML-based notification profile
- NotificationManager: Main orchestration
- ProfileEvaluator: Evaluates kills against profiles
- TriggerType: Notification trigger types
- ThrottleManager: Per-system/trigger throttling
- WebhookQueue: Rate-limited queue
- QuietHoursChecker: Timezone-aware quiet hours
- DiscordClient: HTTP client with retry logic
- MessageFormatter: Kill → Discord message formatting

Commentary:
- PatternDetector: Detect tactical patterns
- WarrantChecker: Decide when to generate commentary
- PersonaLoader: Load persona voice summaries
- CommentaryGenerator: LLM-generated tactical commentary

Usage:
    from aria_esi.services.redisq.notifications import get_notification_manager

    manager = get_notification_manager()
    if manager and manager.is_configured:
        await manager.process_kill(kill, entity_match)
"""

from .commentary import CommentaryGenerator, CommentaryMetrics, create_commentary_generator
from .config import (
    CommentaryConfig,
    NPCFactionKillConfig,
    PoliticalEntityKillConfig,
    QuietHoursConfig,
    TopologyConfig,
    TriggerConfig,
)
from .discord_client import DiscordClient, SendResult
from .formatter import MessageFormatter, format_isk, format_time_ago
from .manager import (
    NotificationHealth,
    NotificationManager,
    get_notification_manager,
    reset_notification_manager,
)
from .npc_factions import (
    NPCFactionMapper,
    NPCFactionTriggerResult,
    get_npc_faction_mapper,
    reset_npc_faction_mapper,
)
from .patterns import DetectedPattern, PatternContext, PatternDetector
from .persona import PersonaLoader, PersonaVoiceSummary, get_persona_loader, reset_persona_loader
from .political_entities import (
    PoliticalEntityTriggerResult,
    resolve_entity_names,
)
from .profile_evaluator import EvaluationResult, ProfileEvaluator, ProfileMatch
from .profile_loader import ProfileLoader, get_profiles_summary
from .profiles import SCHEMA_VERSION, NotificationProfile
from .queue import QueuedMessage, QueueHealth, WebhookQueue
from .quiet_hours import QuietHoursChecker
from .throttle import ThrottleManager
from .triggers import TriggerResult, TriggerType, evaluate_triggers
from .warrant import CommentaryDecision, WarrantChecker

__all__ = [
    # Config
    "TriggerConfig",
    "QuietHoursConfig",
    "CommentaryConfig",
    "TopologyConfig",
    "NPCFactionKillConfig",
    "PoliticalEntityKillConfig",
    # NPC Faction Mapping
    "NPCFactionMapper",
    "NPCFactionTriggerResult",
    "get_npc_faction_mapper",
    "reset_npc_faction_mapper",
    # Political Entity Tracking
    "PoliticalEntityTriggerResult",
    "resolve_entity_names",
    # Profiles
    "NotificationProfile",
    "SCHEMA_VERSION",
    "ProfileLoader",
    "ProfileEvaluator",
    "ProfileMatch",
    "EvaluationResult",
    "get_profiles_summary",
    # Manager
    "NotificationManager",
    "NotificationHealth",
    "get_notification_manager",
    "reset_notification_manager",
    # Triggers
    "TriggerType",
    "TriggerResult",
    "evaluate_triggers",
    # Components
    "ThrottleManager",
    "WebhookQueue",
    "QueuedMessage",
    "QueueHealth",
    "QuietHoursChecker",
    "DiscordClient",
    "SendResult",
    "MessageFormatter",
    # Commentary
    "PatternDetector",
    "DetectedPattern",
    "PatternContext",
    "WarrantChecker",
    "CommentaryDecision",
    "PersonaLoader",
    "PersonaVoiceSummary",
    "get_persona_loader",
    "reset_persona_loader",
    "CommentaryGenerator",
    "CommentaryMetrics",
    "create_commentary_generator",
    # Utilities
    "format_isk",
    "format_time_ago",
]
