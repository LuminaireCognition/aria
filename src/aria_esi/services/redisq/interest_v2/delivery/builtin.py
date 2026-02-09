"""
Built-in Delivery Providers for Interest Engine v2.

Providers:
- DiscordDelivery: Send notifications to Discord webhooks
- WebhookDelivery: Send to generic HTTP webhooks
- LogDelivery: Log notifications for testing/debugging
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..providers.base import BaseDeliveryProvider

if TYPE_CHECKING:
    from ..models import InterestResultV2

logger = logging.getLogger(__name__)


class DiscordDelivery(BaseDeliveryProvider):
    """
    Discord webhook delivery provider.

    Formats notifications as Discord embeds and sends to webhook URL.

    Config:
        webhook_url: Discord webhook URL (required)
        username: Bot username override
        avatar_url: Bot avatar URL override
        color: Embed color (hex string or int)
        mention_role: Role ID to mention for priority notifications
    """

    _name = "discord"

    async def deliver(
        self,
        result: InterestResultV2,
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> bool:
        """
        Deliver notification to Discord.

        Args:
            result: Interest result with scoring details
            payload: Pre-formatted notification payload
            config: Delivery configuration

        Returns:
            True if delivery succeeded
        """
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            logger.error("Discord delivery requires webhook_url")
            return False

        try:
            import httpx
        except ImportError:
            logger.error("httpx not available for Discord delivery")
            return False

        # Build Discord embed
        embed = self._build_embed(result, payload, config)

        # Build webhook payload
        discord_payload: dict[str, Any] = {
            "embeds": [embed],
        }

        if config.get("username"):
            discord_payload["username"] = config["username"]
        if config.get("avatar_url"):
            discord_payload["avatar_url"] = config["avatar_url"]

        # Add mention for priority
        if result.is_priority and config.get("mention_role"):
            discord_payload["content"] = f"<@&{config['mention_role']}>"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=discord_payload,
                    timeout=10.0,
                )
                response.raise_for_status()
                logger.debug(f"Discord delivery succeeded for kill {result.kill_id}")
                return True
        except Exception as e:
            logger.error(f"Discord delivery failed: {e}")
            return False

    def _build_embed(
        self,
        result: InterestResultV2,
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Build Discord embed from result."""
        # Determine color based on tier
        tier_colors = {
            "priority": 0xFF0000,  # Red
            "notify": 0x00FF00,  # Green
            "digest": 0xFFFF00,  # Yellow
            "log_only": 0x808080,  # Gray
        }
        color = config.get("color", tier_colors.get(result.tier.value, 0x0099FF))

        embed: dict[str, Any] = {
            "title": payload.get("title", f"Kill in System {result.system_id}"),
            "color": color,
            "fields": [],
        }

        # Add description if present
        if payload.get("description"):
            embed["description"] = payload["description"]

        # Add score breakdown field
        if result.category_scores:
            breakdown = self._format_breakdown(result)
            embed["fields"].append(
                {
                    "name": "Score Breakdown",
                    "value": breakdown,
                    "inline": False,
                }
            )

        # Add tier and interest
        embed["fields"].append(
            {
                "name": "Interest",
                "value": f"{result.interest:.2f}",
                "inline": True,
            }
        )
        embed["fields"].append(
            {
                "name": "Tier",
                "value": result.tier.value.upper(),
                "inline": True,
            }
        )

        # Add footer with engine info
        embed["footer"] = {
            "text": f"Interest Engine {result.engine_version} | {result.mode.value}",
        }

        return embed

    def _format_breakdown(self, result: InterestResultV2) -> str:
        """Format category score breakdown."""
        lines = []
        for cat, score, weight, match in result.get_category_breakdown():
            match_char = "✓" if match else "○"
            lines.append(f"{match_char} {cat}: {score:.2f} (w={weight:.1f})")
        return "\n".join(lines) or "No categories scored"

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate Discord config."""
        errors = []
        if not config.get("webhook_url"):
            errors.append("webhook_url is required for Discord delivery")
        return errors


class WebhookDelivery(BaseDeliveryProvider):
    """
    Generic HTTP webhook delivery provider.

    Sends JSON payload to configured URL via POST.

    Config:
        url: Webhook URL (required)
        method: HTTP method (default: POST)
        headers: Additional headers to send
        include_result: Include full result in payload (default: False)
    """

    _name = "webhook"

    async def deliver(
        self,
        result: InterestResultV2,
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> bool:
        """
        Deliver notification via HTTP webhook.

        Args:
            result: Interest result
            payload: Notification payload
            config: Delivery configuration

        Returns:
            True if delivery succeeded
        """
        url = config.get("url")
        if not url:
            logger.error("Webhook delivery requires url")
            return False

        try:
            import httpx
        except ImportError:
            logger.error("httpx not available for webhook delivery")
            return False

        # Build request payload
        request_payload = dict(payload)
        if config.get("include_result", False):
            request_payload["_result"] = result.to_dict()

        method = config.get("method", "POST").upper()
        headers = config.get("headers", {})

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method,
                    url,
                    json=request_payload,
                    headers=headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                logger.debug(f"Webhook delivery succeeded for kill {result.kill_id}")
                return True
        except Exception as e:
            logger.error(f"Webhook delivery failed: {e}")
            return False

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate webhook config."""
        errors = []
        if not config.get("url"):
            errors.append("url is required for webhook delivery")
        return errors


class LogDelivery(BaseDeliveryProvider):
    """
    Log delivery provider for testing and debugging.

    Logs notifications to the Python logger instead of sending externally.

    Config:
        level: Log level (default: INFO)
        include_breakdown: Include score breakdown (default: True)
    """

    _name = "log"

    async def deliver(
        self,
        result: InterestResultV2,
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> bool:
        """
        Log notification.

        Args:
            result: Interest result
            payload: Notification payload
            config: Delivery configuration

        Returns:
            Always True
        """
        level_name = config.get("level", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)

        # Format message
        parts = [
            f"[{result.tier.value.upper()}]",
            f"Kill {result.kill_id}" if result.kill_id else f"System {result.system_id}",
            f"interest={result.interest:.2f}",
        ]

        if config.get("include_breakdown", True) and result.dominant_category:
            parts.append(f"dominant={result.dominant_category}")

        if result.bypassed_scoring:
            parts.append("(always_notify)")

        message = " | ".join(parts)
        logger.log(level, message)

        return True

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate log config."""
        errors = []
        level = config.get("level", "INFO").upper()
        if not hasattr(logging, level):
            errors.append(f"Invalid log level: {level}")
        return errors
