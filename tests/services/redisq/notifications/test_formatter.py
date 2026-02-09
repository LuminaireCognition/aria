"""
Tests for Discord message formatter.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aria_esi.services.redisq.models import ProcessedKill
from aria_esi.services.redisq.notifications.formatter import (
    MessageFormatter,
    format_isk,
    format_time_ago,
)
from aria_esi.services.redisq.notifications.triggers import TriggerResult, TriggerType


class TestFormatIsk:
    """Tests for ISK formatting."""

    def test_format_billions(self):
        """Test billion ISK formatting."""
        assert format_isk(1_000_000_000) == "1.0B"
        assert format_isk(12_400_000_000) == "12.4B"
        assert format_isk(999_000_000_000) == "999.0B"

    def test_format_millions(self):
        """Test million ISK formatting."""
        assert format_isk(1_000_000) == "1.0M"
        assert format_isk(350_000_000) == "350.0M"
        assert format_isk(999_999_999) == "1000.0M"

    def test_format_thousands(self):
        """Test thousand ISK formatting."""
        assert format_isk(1_000) == "1.0K"
        assert format_isk(45_000) == "45.0K"
        assert format_isk(999_999) == "1000.0K"

    def test_format_small(self):
        """Test small ISK values."""
        assert format_isk(500) == "500"
        assert format_isk(0) == "0"


class TestFormatTimeAgo:
    """Tests for time ago formatting."""

    def test_format_seconds(self):
        """Test seconds ago."""
        now = datetime.now(tz=timezone.utc)
        kill_time = now - timedelta(seconds=30)
        assert format_time_ago(kill_time) == "30 sec ago"

    def test_format_minutes(self):
        """Test minutes ago."""
        now = datetime.now(tz=timezone.utc)
        kill_time = now - timedelta(minutes=5)
        assert format_time_ago(kill_time) == "5 min ago"

    def test_format_hours(self):
        """Test hours ago."""
        now = datetime.now(tz=timezone.utc)
        kill_time = now - timedelta(hours=2)
        assert format_time_ago(kill_time) == "2 hours ago"

        kill_time = now - timedelta(hours=1)
        assert format_time_ago(kill_time) == "1 hour ago"

    def test_format_days(self):
        """Test days ago."""
        now = datetime.now(tz=timezone.utc)
        kill_time = now - timedelta(days=3)
        assert format_time_ago(kill_time) == "3 days ago"

        kill_time = now - timedelta(days=1)
        assert format_time_ago(kill_time) == "1 day ago"

    def test_format_naive_datetime_treated_as_utc(self):
        """Test that naive datetimes are treated as UTC (ESI standard)."""
        # Simulate ESI-style naive datetime that represents UTC
        now_utc = datetime.now(tz=timezone.utc)
        naive_kill_time = (now_utc - timedelta(minutes=5)).replace(tzinfo=None)
        assert format_time_ago(naive_kill_time) == "5 min ago"

    def test_format_future_time_shows_just_now(self):
        """Test that slight future times (clock drift) show 'just now'."""
        now = datetime.now(tz=timezone.utc)
        future_time = now + timedelta(seconds=5)
        assert format_time_ago(future_time) == "just now"


class TestMessageFormatter:
    """Tests for MessageFormatter."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return MessageFormatter()

    @pytest.fixture
    def sample_kill(self):
        """Create sample ProcessedKill."""
        return ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now() - timedelta(minutes=2),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=99000001,
            attacker_count=8,
            attacker_corps=[98000002],
            attacker_alliances=[99000002],
            attacker_ship_types=[11993, 11989, 17740, 11995],
            final_blow_ship_type_id=11989,
            total_value=12_400_000_000,
            is_pod_kill=False,
        )

    def test_format_watchlist_kill(self, formatter, sample_kill):
        """Test formatting watchlist activity kill."""
        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.WATCHLIST_ACTIVITY],
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
            system_name="Tama",
            ship_name="Proteus",
            attacker_group="Snuffed Out",
        )

        assert "embeds" in payload
        embed = payload["embeds"][0]

        # Check title
        assert "INTEL:" in embed["title"]
        assert "Tama" in embed["title"]

        # Check description
        assert "Proteus" in embed["description"]
        assert "8 attackers" in embed["description"]
        assert "Snuffed Out" in embed["description"]
        assert "12.4B" in embed["description"]

        # Check URL
        assert embed["url"] == "https://zkillboard.com/kill/12345678/"

        # Check color (orange for watchlist)
        assert embed["color"] == 0xFF6600

    def test_format_gatecamp_kill(self, formatter, sample_kill):
        """Test formatting gatecamp detection kill."""
        from aria_esi.services.redisq.threat_cache import GatecampStatus

        gatecamp = GatecampStatus(
            system_id=30002813,
            system_name="Tama",
            kill_count=5,
            confidence="high",
        )

        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.GATECAMP_DETECTED],
            gatecamp_status=gatecamp,
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
            system_name="Tama",
            ship_name="Proteus",
        )

        embed = payload["embeds"][0]

        # Check title
        assert "CAMP:" in embed["title"]

        # Check gatecamp context
        assert "gatecamp" in embed["description"].lower()
        assert "5 kills" in embed["description"]

        # Check color (red for gatecamp)
        assert embed["color"] == 0xFF0000

    def test_format_high_value_kill(self, formatter, sample_kill):
        """Test formatting high value kill."""
        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.HIGH_VALUE],
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
            system_name="Jita",
            ship_name="Titan",
        )

        embed = payload["embeds"][0]

        # Check title
        assert "HIGH VALUE:" in embed["title"]

        # Check color (gold for high value)
        assert embed["color"] == 0xFFD700

    def test_format_pod_kill(self, formatter):
        """Test formatting pod kill."""
        pod_kill = ProcessedKill(
            kill_id=12345679,
            kill_time=datetime.now() - timedelta(minutes=1),
            solar_system_id=30002813,
            victim_ship_type_id=670,  # Capsule
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=1,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=True,
        )

        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.WATCHLIST_ACTIVITY],
        )

        payload = formatter.format_kill(
            kill=pod_kill,
            trigger_result=trigger_result,
        )

        embed = payload["embeds"][0]
        assert "Capsule" in embed["description"]

    def test_format_test_message(self, formatter):
        """Test test message formatting."""
        payload = formatter.format_test_message()

        assert "embeds" in payload
        embed = payload["embeds"][0]

        assert "Test" in embed["title"]
        assert "working" in embed["description"].lower()
        assert embed["color"] == 0x00FF00  # Green

    def test_message_length(self, formatter, sample_kill):
        """Test message stays within Discord limits."""
        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.WATCHLIST_ACTIVITY],
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
            system_name="Tama",
            ship_name="Proteus",
            attacker_group="Some Very Long Alliance Name That Is Quite Excessive",
        )

        embed = payload["embeds"][0]

        # Discord embed description limit is 4096
        assert len(embed["description"]) <= 4096
        # Discord embed title limit is 256
        assert len(embed["title"]) <= 256


class TestMessageFormatterWarEngagement:
    """Tests for war engagement formatting."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return MessageFormatter()

    @pytest.fixture
    def sample_kill(self):
        """Create sample ProcessedKill."""
        return ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now() - timedelta(minutes=2),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=99000001,
            attacker_count=8,
            attacker_corps=[98000002],
            attacker_alliances=[99000002],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11989,
            total_value=1_000_000_000,
            is_pod_kill=False,
        )

    def test_format_war_engagement(self, formatter, sample_kill):
        """Test war engagement formatting."""
        from unittest.mock import MagicMock

        war_context = MagicMock()
        war_context.is_war_engagement = True
        war_context.relationship = MagicMock()
        war_context.relationship.is_mutual = False
        war_context.relationship.kill_count = 5

        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.WAR_ENGAGEMENT],
            war_context=war_context,
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
            system_name="Tama",
            ship_name="Proteus",
        )

        embed = payload["embeds"][0]

        # Check title includes WAR prefix
        assert "WAR:" in embed["title"]

        # Check color is purple for war
        assert embed["color"] == 0x9400D3

        # Check war context in description
        assert "Wardec" in embed["description"] or "5 kills" in embed["description"]

    def test_format_mutual_war(self, formatter, sample_kill):
        """Test mutual war formatting."""
        from unittest.mock import MagicMock

        war_context = MagicMock()
        war_context.is_war_engagement = True
        war_context.relationship = MagicMock()
        war_context.relationship.is_mutual = True
        war_context.relationship.kill_count = 1

        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.WAR_ENGAGEMENT],
            war_context=war_context,
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
        )

        embed = payload["embeds"][0]
        assert "Mutual War" in embed["description"]

    def test_format_war_with_kill_count(self, formatter, sample_kill):
        """Test war formatting includes kill count when > 1."""
        from unittest.mock import MagicMock

        war_context = MagicMock()
        war_context.is_war_engagement = True
        war_context.relationship = MagicMock()
        war_context.relationship.is_mutual = False
        war_context.relationship.kill_count = 10

        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.WAR_ENGAGEMENT],
            war_context=war_context,
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
        )

        embed = payload["embeds"][0]
        assert "10 kills tracked" in embed["description"]


class TestMessageFormatterNPCFaction:
    """Tests for NPC faction formatting."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return MessageFormatter()

    @pytest.fixture
    def sample_kill(self):
        """Create sample ProcessedKill."""
        return ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now() - timedelta(minutes=2),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=3,
            attacker_corps=[1000125],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=100_000_000,
            is_pod_kill=False,
        )

    def test_format_serpentis_faction_color(self, formatter, sample_kill):
        """Serpentis faction uses green color."""
        from unittest.mock import MagicMock

        npc_faction = MagicMock()
        npc_faction.matched = True
        npc_faction.faction = "serpentis"
        npc_faction.corporation_name = "Serpentis Corporation"
        npc_faction.role = "attacker"

        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.NPC_FACTION_KILL],
            npc_faction=npc_faction,
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
        )

        embed = payload["embeds"][0]

        # Serpentis color is green (0x00FF00)
        assert embed["color"] == 0x00FF00
        assert "SERPENTIS OPERATIONS:" in embed["title"]

    def test_format_angel_cartel_color(self, formatter, sample_kill):
        """Angel Cartel uses orange color."""
        from unittest.mock import MagicMock

        npc_faction = MagicMock()
        npc_faction.matched = True
        npc_faction.faction = "angel_cartel"
        npc_faction.corporation_name = "Angel Cartel"
        npc_faction.role = "attacker"

        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.NPC_FACTION_KILL],
            npc_faction=npc_faction,
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
        )

        embed = payload["embeds"][0]
        assert embed["color"] == 0xFF6600  # Orange
        assert "ANGEL CARTEL OPERATIONS:" in embed["title"]

    def test_format_guristas_color(self, formatter, sample_kill):
        """Guristas uses gray color."""
        from unittest.mock import MagicMock

        npc_faction = MagicMock()
        npc_faction.matched = True
        npc_faction.faction = "guristas"
        npc_faction.corporation_name = "Guristas"
        npc_faction.role = "attacker"

        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.NPC_FACTION_KILL],
            npc_faction=npc_faction,
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
        )

        embed = payload["embeds"][0]
        assert embed["color"] == 0x808080  # Gray

    def test_format_blood_raiders_color(self, formatter, sample_kill):
        """Blood Raiders uses dark red color."""
        from unittest.mock import MagicMock

        npc_faction = MagicMock()
        npc_faction.matched = True
        npc_faction.faction = "blood_raiders"
        npc_faction.corporation_name = "Blood Raiders"
        npc_faction.role = "attacker"

        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.NPC_FACTION_KILL],
            npc_faction=npc_faction,
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
        )

        embed = payload["embeds"][0]
        assert embed["color"] == 0x8B0000  # Dark red

    def test_format_npc_attacker_context(self, formatter, sample_kill):
        """NPC attacker context is shown in description."""
        from unittest.mock import MagicMock

        npc_faction = MagicMock()
        npc_faction.matched = True
        npc_faction.faction = "serpentis"
        npc_faction.corporation_name = "Serpentis Corporation"
        npc_faction.role = "attacker"

        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.NPC_FACTION_KILL],
            npc_faction=npc_faction,
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
        )

        embed = payload["embeds"][0]
        assert "Attacker: Serpentis Corporation" in embed["description"]

    def test_format_npc_victim_context(self, formatter, sample_kill):
        """NPC victim context is shown in description."""
        from unittest.mock import MagicMock

        npc_faction = MagicMock()
        npc_faction.matched = True
        npc_faction.faction = "serpentis"
        npc_faction.corporation_name = "Serpentis Corporation"
        npc_faction.role = "victim"

        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.NPC_FACTION_KILL],
            npc_faction=npc_faction,
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
        )

        embed = payload["embeds"][0]
        assert "Victim: Serpentis Corporation" in embed["description"]


class TestMessageFormatterCommentary:
    """Tests for commentary formatting."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return MessageFormatter()

    @pytest.fixture
    def sample_kill(self):
        """Create sample ProcessedKill."""
        return ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now() - timedelta(minutes=2),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=99000001,
            attacker_count=8,
            attacker_corps=[98000002],
            attacker_alliances=[99000002],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11989,
            total_value=1_000_000_000,
            is_pod_kill=False,
        )

    def test_format_with_commentary(self, formatter, sample_kill):
        """Test commentary is appended to description."""
        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.WATCHLIST_ACTIVITY],
        )

        payload = formatter.format_kill_with_commentary(
            kill=sample_kill,
            trigger_result=trigger_result,
            commentary="Another gank on the Tama pipe. Classic.",
            persona_name="ARIA",
            system_name="Tama",
        )

        embed = payload["embeds"][0]

        assert "Another gank on the Tama pipe" in embed["description"]
        assert "ARIA" in embed["description"]
        assert "---" in embed["description"]  # Separator

    def test_format_with_commentary_default_persona(self, formatter, sample_kill):
        """Test default ARIA persona when none specified."""
        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.WATCHLIST_ACTIVITY],
        )

        payload = formatter.format_kill_with_commentary(
            kill=sample_kill,
            trigger_result=trigger_result,
            commentary="Test commentary",
            persona_name=None,  # No persona
        )

        embed = payload["embeds"][0]
        assert "ARIA" in embed["description"]

    def test_format_with_custom_persona(self, formatter, sample_kill):
        """Test custom persona name in attribution."""
        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.WATCHLIST_ACTIVITY],
        )

        payload = formatter.format_kill_with_commentary(
            kill=sample_kill,
            trigger_result=trigger_result,
            commentary="Serpentis approved.",
            persona_name="PARIA",
        )

        embed = payload["embeds"][0]
        assert "PARIA" in embed["description"]

    def test_format_no_commentary(self, formatter, sample_kill):
        """Test with None commentary returns base format."""
        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.WATCHLIST_ACTIVITY],
        )

        payload = formatter.format_kill_with_commentary(
            kill=sample_kill,
            trigger_result=trigger_result,
            commentary=None,
            system_name="Tama",
        )

        embed = payload["embeds"][0]

        # Should not have commentary section
        assert "---" not in embed["description"]
        # But should have base content
        assert "Tama" in embed["title"]

    def test_format_commentary_italic(self, formatter, sample_kill):
        """Test commentary is formatted in italics."""
        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.WATCHLIST_ACTIVITY],
        )

        payload = formatter.format_kill_with_commentary(
            kill=sample_kill,
            trigger_result=trigger_result,
            commentary="Test commentary text",
            persona_name="ARIA",
        )

        embed = payload["embeds"][0]

        # Commentary should be wrapped in asterisks for italics
        assert "*Test commentary text*" in embed["description"]


class TestMessageFormatterSmartbomb:
    """Tests for smartbomb gatecamp formatting."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return MessageFormatter()

    @pytest.fixture
    def sample_kill(self):
        """Create sample ProcessedKill."""
        return ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now() - timedelta(minutes=1),
            solar_system_id=30002813,
            victim_ship_type_id=670,  # Capsule
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=1,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[17740],
            final_blow_ship_type_id=17740,
            total_value=50_000_000,
            is_pod_kill=True,
        )

    def test_format_smartbomb_camp(self, formatter, sample_kill):
        """Test smartbomb camp indicator in message."""
        from aria_esi.services.redisq.threat_cache import GatecampStatus

        gatecamp = GatecampStatus(
            system_id=30002813,
            system_name="Tama",
            kill_count=8,
            confidence="high",
            is_smartbomb_camp=True,
        )

        trigger_result = TriggerResult(
            should_notify=True,
            trigger_types=[TriggerType.GATECAMP_DETECTED],
            gatecamp_status=gatecamp,
        )

        payload = formatter.format_kill(
            kill=sample_kill,
            trigger_result=trigger_result,
        )

        embed = payload["embeds"][0]
        assert "Smartbomb" in embed["description"]
