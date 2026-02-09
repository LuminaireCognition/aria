"""
Discord Message Formatter.

Formats kill notifications as Discord webhook embeds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..entity_filter import EntityMatchResult
    from ..models import ProcessedKill
    from .triggers import TriggerResult


# Color codes for Discord embeds (decimal format)
COLORS = {
    "watchlist": 0xFF6600,  # Orange - watched entity
    "gatecamp": 0xFF0000,  # Red - gatecamp detected
    "high_value": 0xFFD700,  # Gold - high value
    "war_engagement": 0x9400D3,  # Purple - war engagement
    "npc_faction": 0x808080,  # Gray - NPC faction (default)
    "default": 0x3498DB,  # Blue - default
}

# Faction-specific colors for NPC faction kill notifications
FACTION_COLORS = {
    "serpentis": 0x00FF00,  # Green (Serpentis brand color)
    "angel_cartel": 0xFF6600,  # Orange (Angel Cartel)
    "guristas": 0x808080,  # Gray (Guristas)
    "blood_raiders": 0x8B0000,  # Dark red (Blood Raiders)
    "sansha": 0x800080,  # Purple (Sansha's Nation)
}


def format_isk(value: float) -> str:
    """
    Format ISK value in human-readable format.

    Args:
        value: ISK amount

    Returns:
        Formatted string (e.g., "1.5B", "350M", "45K")
    """
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.1f}K"
    else:
        return f"{value:.0f}"


def format_time_ago(kill_time: datetime) -> str:
    """
    Format kill time as relative time.

    Args:
        kill_time: When the kill occurred (expected to be UTC)

    Returns:
        Human-readable relative time (e.g., "2 min ago", "1 hour ago")
    """
    from datetime import timezone

    # ESI/RedisQ times are UTC - ensure we compare in UTC
    if kill_time.tzinfo is None:
        # Assume naive datetime is UTC (ESI standard)
        kill_time = kill_time.replace(tzinfo=timezone.utc)

    now = datetime.now(tz=timezone.utc)
    delta = now - kill_time

    seconds = int(delta.total_seconds())

    # Handle edge case where kill_time might be slightly in the future
    # due to clock drift between servers
    if seconds < 0:
        return "just now"

    if seconds < 60:
        return f"{seconds} sec ago"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} min ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"


@dataclass
class MessageFormatter:
    """
    Formats kills as Discord webhook messages.

    Uses embeds for rich formatting with color-coded severity.
    """

    def format_kill(
        self,
        kill: ProcessedKill,
        trigger_result: TriggerResult,
        entity_match: EntityMatchResult | None = None,
        system_name: str | None = None,
        ship_name: str | None = None,
        attacker_group: str | None = None,
    ) -> dict[str, Any]:
        """
        Format a kill as a Discord webhook payload.

        Args:
            kill: The processed killmail
            trigger_result: Result of trigger evaluation
            entity_match: Optional entity match details
            system_name: Optional system name (falls back to ID)
            ship_name: Optional ship name (falls back to type ID)
            attacker_group: Optional primary attacker group name

        Returns:
            Discord webhook payload dict
        """
        # Determine embed color based on trigger type
        from .triggers import TriggerType

        primary_trigger = trigger_result.primary_trigger
        if primary_trigger == TriggerType.NPC_FACTION_KILL and trigger_result.npc_faction:
            # Use faction-specific color and title
            npc = trigger_result.npc_faction
            faction_upper = npc.faction.replace("_", " ").upper()
            color = FACTION_COLORS.get(npc.faction, COLORS["npc_faction"])
            emoji = "\u2694\ufe0f"  # Crossed swords for faction ops
            title_prefix = f"{faction_upper} OPERATIONS: "
        elif primary_trigger == TriggerType.WAR_ENGAGEMENT:
            color = COLORS["war_engagement"]
            emoji = "\u2694\ufe0f"  # Crossed swords
            title_prefix = "WAR: "
        elif primary_trigger == TriggerType.WATCHLIST_ACTIVITY:
            color = COLORS["watchlist"]
            emoji = "\u26a0\ufe0f"  # Warning sign
            title_prefix = "INTEL: "
        elif primary_trigger == TriggerType.GATECAMP_DETECTED:
            color = COLORS["gatecamp"]
            emoji = "\U0001f6a8"  # Rotating light
            title_prefix = "CAMP: "
        elif primary_trigger == TriggerType.HIGH_VALUE:
            color = COLORS["high_value"]
            emoji = "\U0001f4b0"  # Money bag
            title_prefix = "HIGH VALUE: "
        else:
            color = COLORS["default"]
            emoji = "\u2139\ufe0f"  # Information
            title_prefix = "KILL: "

        # Format system display
        system_display = system_name or f"System {kill.solar_system_id}"

        # Format ship display
        ship_display = ship_name or f"Ship {kill.victim_ship_type_id}"
        if kill.is_pod_kill:
            ship_display = "Capsule"

        # Format attacker info
        attacker_info = f"{kill.attacker_count} attacker{'s' if kill.attacker_count != 1 else ''}"
        if attacker_group:
            attacker_info = f"{kill.attacker_count} attackers ({attacker_group})"

        # Build description
        description_parts = [
            f"**{ship_display}** down \u2022 {attacker_info}",
            f"{format_isk(kill.total_value)} ISK \u2022 {format_time_ago(kill.kill_time)}",
        ]

        # Add gatecamp context if present
        if trigger_result.gatecamp_status:
            camp = trigger_result.gatecamp_status
            if camp.confidence in ("medium", "high"):
                camp_info = f"Part of active gatecamp ({camp.kill_count} kills in 10 min)"
                if camp.is_smartbomb_camp:
                    camp_info += " \u2622 Smartbomb"
                description_parts.append(f"\n\u26a0\ufe0f {camp_info}")

        # Add watchlist context if present
        if entity_match and entity_match.has_match:
            match_types = entity_match.match_types
            if match_types:
                context = f"Watched entity: {', '.join(match_types)}"
                description_parts.append(f"\n\U0001f441 {context}")

        # Add war context if present
        if trigger_result.war_context and trigger_result.war_context.is_war_engagement:
            war_ctx = trigger_result.war_context
            if war_ctx.relationship:
                rel = war_ctx.relationship
                war_status = "Mutual War" if rel.is_mutual else "Wardec"
                # Include kill count as an indicator of war activity
                if rel.kill_count > 1:
                    war_info = f"{war_status} ({rel.kill_count} kills tracked)"
                else:
                    war_info = war_status
                description_parts.append(f"\n\u2694\ufe0f {war_info}")

        # Add NPC faction context if present
        if trigger_result.npc_faction and trigger_result.npc_faction.matched:
            npc = trigger_result.npc_faction
            npc_info = f"{npc.corporation_name}"
            if npc.role == "attacker":
                description_parts.append(f"\n\u2694\ufe0f Attacker: {npc_info}")
            else:
                description_parts.append(f"\n\U0001f480 Victim: {npc_info}")

        # Build embed
        embed = {
            "title": f"{emoji} {title_prefix}{system_display}",
            "description": "\n".join(description_parts),
            "color": color,
            "url": f"https://zkillboard.com/kill/{kill.kill_id}/",
            "footer": {
                "text": f"Kill ID: {kill.kill_id}",
            },
            "timestamp": kill.kill_time.isoformat() if kill.kill_time.tzinfo else None,
        }

        return {"embeds": [embed]}

    def format_kill_with_commentary(
        self,
        kill: ProcessedKill,
        trigger_result: TriggerResult,
        commentary: str | None = None,
        persona_name: str | None = None,
        entity_match: EntityMatchResult | None = None,
        system_name: str | None = None,
        ship_name: str | None = None,
        attacker_group: str | None = None,
    ) -> dict[str, Any]:
        """
        Format a kill with optional LLM-generated commentary.

        Args:
            kill: The processed killmail
            trigger_result: Result of trigger evaluation
            commentary: Optional LLM-generated commentary
            persona_name: Persona name for attribution (e.g., "ARIA", "PARIA")
            entity_match: Optional entity match details
            system_name: Optional system name
            ship_name: Optional ship name
            attacker_group: Optional primary attacker group name

        Returns:
            Discord webhook payload dict with commentary appended
        """
        # Get base payload
        payload = self.format_kill(
            kill=kill,
            trigger_result=trigger_result,
            entity_match=entity_match,
            system_name=system_name,
            ship_name=ship_name,
            attacker_group=attacker_group,
        )

        # Append commentary if present
        if commentary and payload.get("embeds"):
            embed = payload["embeds"][0]
            attribution = f"\u2014 {persona_name}" if persona_name else "\u2014 ARIA"

            # Append to description with separator
            current_desc = embed.get("description", "")
            embed["description"] = f"{current_desc}\n\n---\n*{commentary}*\n{attribution}"

        return payload

    def format_test_message(self) -> dict[str, Any]:
        """
        Format a test message for webhook validation.

        Returns:
            Discord webhook payload for test message
        """
        embed = {
            "title": "\u2705 ARIA Webhook Test",
            "description": "Discord webhook integration is working correctly.",
            "color": 0x00FF00,  # Green
            "footer": {
                "text": "ARIA Intel System",
            },
        }

        return {"embeds": [embed]}
