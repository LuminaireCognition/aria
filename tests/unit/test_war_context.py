"""
Unit tests for war context provider.

Tests war relationship detection, inference, and caching.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from aria_esi.services.redisq.models import ProcessedKill
from aria_esi.services.redisq.war_context import (
    WAR_INFERENCE_MIN_KILLS,
    WAR_RELATIONSHIP_TTL_SECONDS,
    KillWarContext,
    WarContextProvider,
    WarRelationship,
)


def make_kill(
    kill_id: int = 1,
    kill_time: datetime | None = None,
    system_id: int = 30000142,  # Jita
    victim_corp: int = 1,
    victim_alliance: int | None = None,
    attacker_count: int = 1,
    attacker_corps: list[int] | None = None,
    attacker_alliances: list[int] | None = None,
    attacker_ship_types: list[int] | None = None,
    is_pod: bool = False,
    value: float = 10_000_000,
) -> ProcessedKill:
    """Create a test kill with sensible defaults."""
    if kill_time is None:
        kill_time = datetime.utcnow()
    if attacker_corps is None:
        attacker_corps = [100]
    if attacker_alliances is None:
        attacker_alliances = []
    if attacker_ship_types is None:
        attacker_ship_types = [587]  # Rifter

    return ProcessedKill(
        kill_id=kill_id,
        kill_time=kill_time,
        solar_system_id=system_id,
        victim_ship_type_id=670 if is_pod else 587,  # Capsule vs Rifter
        victim_corporation_id=victim_corp,
        victim_alliance_id=victim_alliance,
        attacker_count=attacker_count,
        attacker_corps=attacker_corps,
        attacker_alliances=attacker_alliances,
        attacker_ship_types=attacker_ship_types,
        final_blow_ship_type_id=attacker_ship_types[0] if attacker_ship_types else None,
        total_value=value,
        is_pod_kill=is_pod,
    )


class TestWarRelationship:
    """Tests for WarRelationship dataclass."""

    def test_relationship_not_stale_when_fresh(self):
        """Fresh relationships should not be stale."""
        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=1000002,
            first_observed=datetime.utcnow(),
            last_observed=datetime.utcnow(),
        )
        assert rel.is_stale() is False

    def test_relationship_stale_after_ttl(self):
        """Relationships older than TTL should be stale."""
        old_time = datetime.utcnow() - timedelta(
            seconds=WAR_RELATIONSHIP_TTL_SECONDS + 100
        )
        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=1000002,
            first_observed=old_time,
            last_observed=old_time,
        )
        assert rel.is_stale() is True

    def test_touch_updates_last_observed(self):
        """Touch should update last_observed and increment kill_count."""
        old_time = datetime.utcnow() - timedelta(hours=1)
        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=1000002,
            first_observed=old_time,
            last_observed=old_time,
            kill_count=1,
        )

        original_count = rel.kill_count
        rel.touch()

        assert rel.kill_count == original_count + 1
        assert rel.last_observed > old_time


class TestKillWarContext:
    """Tests for KillWarContext dataclass."""

    def test_is_mutual_war_with_mutual_relationship(self):
        """Mutual war property should reflect relationship."""
        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=1000002,
            is_mutual=True,
        )
        ctx = KillWarContext(
            is_war_engagement=True,
            relationship=rel,
        )
        assert ctx.is_mutual_war is True

    def test_is_mutual_war_with_non_mutual_relationship(self):
        """Non-mutual war should return False."""
        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=1000002,
            is_mutual=False,
        )
        ctx = KillWarContext(
            is_war_engagement=True,
            relationship=rel,
        )
        assert ctx.is_mutual_war is False

    def test_is_mutual_war_without_relationship(self):
        """Without relationship, is_mutual_war should be False."""
        ctx = KillWarContext(is_war_engagement=False)
        assert ctx.is_mutual_war is False


class TestWarContextProvider:
    """Tests for WarContextProvider class."""

    def test_check_kill_no_war_relationship(self):
        """Kill without war relationship returns not war engagement."""
        provider = WarContextProvider()
        kill = make_kill(
            kill_id=1,
            victim_alliance=2000001,
            attacker_alliances=[1000001],
        )

        result = provider.check_kill(kill)

        assert result.is_war_engagement is False
        assert result.relationship is None

    def test_check_kill_with_existing_relationship(self):
        """Kill with existing war relationship returns war engagement."""
        provider = WarContextProvider()

        # Add a war relationship
        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=2000001,
        )
        provider.add_relationship(rel)

        # Create a kill matching the war
        kill = make_kill(
            kill_id=1,
            victim_alliance=2000001,
            attacker_alliances=[1000001],
        )

        result = provider.check_kill(kill)

        assert result.is_war_engagement is True
        assert result.relationship is not None
        assert result.attacker_side == "aggressor"
        assert result.victim_side == "defender"

    def test_check_kill_defender_side(self):
        """Kill where victim is aggressor returns correct sides."""
        provider = WarContextProvider()

        # Add a war relationship
        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=2000001,
        )
        provider.add_relationship(rel)

        # Create a kill where the aggressor is the victim (they shot back)
        kill = make_kill(
            kill_id=1,
            victim_alliance=1000001,  # Victim is the aggressor alliance
            attacker_alliances=[2000001],  # Attacker is the defender alliance
        )

        result = provider.check_kill(kill)

        assert result.is_war_engagement is True
        assert result.attacker_side == "defender"
        assert result.victim_side == "aggressor"

    def test_is_war_kill_shortcut(self):
        """is_war_kill should return boolean quickly."""
        provider = WarContextProvider()

        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=2000001,
        )
        provider.add_relationship(rel)

        kill_in_war = make_kill(
            kill_id=1,
            victim_alliance=2000001,
            attacker_alliances=[1000001],
        )
        kill_not_in_war = make_kill(
            kill_id=2,
            victim_alliance=3000001,
            attacker_alliances=[4000001],
        )

        assert provider.is_war_kill(kill_in_war) is True
        assert provider.is_war_kill(kill_not_in_war) is False

    def test_filter_war_kills(self):
        """filter_war_kills should separate war and non-war kills."""
        provider = WarContextProvider()

        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=2000001,
        )
        provider.add_relationship(rel)

        war_kill = make_kill(
            kill_id=1,
            victim_alliance=2000001,
            attacker_alliances=[1000001],
        )
        non_war_kill = make_kill(
            kill_id=2,
            victim_alliance=3000001,
            attacker_alliances=[4000001],
        )

        war_kills, non_war_kills = provider.filter_war_kills([war_kill, non_war_kill])

        assert len(war_kills) == 1
        assert len(non_war_kills) == 1
        assert war_kills[0].kill_id == 1
        assert non_war_kills[0].kill_id == 2

    def test_war_inference_not_triggered_with_few_kills(self):
        """War should not be inferred with fewer than minimum kills."""
        provider = WarContextProvider()

        # Create kills between same alliances (fewer than threshold)
        for i in range(WAR_INFERENCE_MIN_KILLS - 1):
            kill = make_kill(
                kill_id=i + 1,
                victim_alliance=2000001,
                attacker_alliances=[1000001],
            )
            provider.check_kill(kill)

        # Should not have inferred a war yet
        stats = provider.get_stats()
        assert stats["total_relationships"] == 0

    def test_war_inference_triggered_with_enough_kills(self):
        """War should be inferred after minimum kills threshold."""
        provider = WarContextProvider()

        # Create kills between same alliances (at threshold)
        for i in range(WAR_INFERENCE_MIN_KILLS):
            kill = make_kill(
                kill_id=i + 1,
                victim_alliance=2000001,
                attacker_alliances=[1000001],
            )
            provider.check_kill(kill)

        # Should have inferred a war
        stats = provider.get_stats()
        assert stats["total_relationships"] == 1
        assert stats["inferred_wars"] == 1

    def test_key_normalization(self):
        """Relationship key should be normalized for consistent lookup."""
        provider = WarContextProvider()

        # Add relationship in one order
        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=2000001,
        )
        provider.add_relationship(rel)

        # Check kill with alliances in opposite order
        kill = make_kill(
            kill_id=1,
            victim_alliance=1000001,
            attacker_alliances=[2000001],
        )

        result = provider.check_kill(kill)

        # Should still find the relationship
        assert result.is_war_engagement is True

    def test_get_stats(self):
        """get_stats should return accurate cache statistics."""
        provider = WarContextProvider()

        # Add some relationships
        rel1 = WarRelationship(
            aggressor_id=1000001,
            defender_id=2000001,
            source="inferred",
        )
        rel2 = WarRelationship(
            aggressor_id=3000001,
            defender_id=4000001,
            source="esi_sync",
        )
        provider.add_relationship(rel1)
        provider.add_relationship(rel2)

        stats = provider.get_stats()

        assert stats["total_relationships"] == 2
        assert stats["inferred_wars"] == 1
        assert stats["esi_wars"] == 1

    def test_stale_relationship_ignored(self):
        """Stale relationships should not match kills."""
        provider = WarContextProvider()

        # Add a stale relationship
        old_time = datetime.utcnow() - timedelta(
            seconds=WAR_RELATIONSHIP_TTL_SECONDS + 100
        )
        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=2000001,
            first_observed=old_time,
            last_observed=old_time,
        )
        provider.add_relationship(rel)

        # Create a kill matching the war
        kill = make_kill(
            kill_id=1,
            victim_alliance=2000001,
            attacker_alliances=[1000001],
        )

        result = provider.check_kill(kill)

        # Should not match because relationship is stale
        assert result.is_war_engagement is False

    def test_corp_fallback_when_no_alliance(self):
        """Should fall back to corp IDs when alliance IDs are missing."""
        provider = WarContextProvider()

        # Add relationship using corp IDs
        rel = WarRelationship(
            aggressor_id=100001,
            defender_id=200001,
            aggressor_type="corporation",
            defender_type="corporation",
        )
        provider.add_relationship(rel)

        # Create a kill without alliance but with matching corps
        kill = make_kill(
            kill_id=1,
            victim_corp=200001,
            victim_alliance=None,
            attacker_corps=[100001],
            attacker_alliances=[],
        )

        result = provider.check_kill(kill)

        assert result.is_war_engagement is True


class TestWarContextIntegrationWithGatecamp:
    """Integration tests for war context with gatecamp detection."""

    def test_pure_war_engagement_not_gatecamp(self):
        """When all kills are war-related, detect_gatecamp should return None."""
        from aria_esi.services.redisq.threat_cache import detect_gatecamp

        provider = WarContextProvider()

        # Add war relationship
        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=2000001,
        )
        provider.add_relationship(rel)

        # Create multiple war kills (would trigger gatecamp without war context)
        war_kills = [
            make_kill(
                kill_id=i + 1,
                victim_corp=i + 100,
                victim_alliance=2000001,
                attacker_count=10,
                attacker_alliances=[1000001],
            )
            for i in range(5)
        ]

        # Without war context, would detect gatecamp
        result_without_war = detect_gatecamp(
            system_id=30000142,
            kills=war_kills,
            war_context=None,
        )
        assert result_without_war is not None

        # With war context, should NOT detect gatecamp
        result_with_war = detect_gatecamp(
            system_id=30000142,
            kills=war_kills,
            war_context=provider,
        )
        assert result_with_war is None

    def test_mixed_war_and_camp_kills(self):
        """When some kills are war-related, camp detection uses remaining kills."""
        from aria_esi.services.redisq.threat_cache import detect_gatecamp

        provider = WarContextProvider()

        # Add war relationship
        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=2000001,
        )
        provider.add_relationship(rel)

        # Create mixed kills - some war, some not
        war_kills = [
            make_kill(
                kill_id=i + 1,
                victim_corp=i + 100,
                victim_alliance=2000001,
                attacker_count=10,
                attacker_alliances=[1000001],
            )
            for i in range(2)
        ]
        # Use different attacker/victim pairs to avoid triggering war inference
        # (WAR_INFERENCE_MIN_KILLS = 3, so same pair 3 times would infer a war)
        camp_kills = [
            make_kill(
                kill_id=i + 100,
                victim_corp=i + 1000,
                victim_alliance=3000001 + i,  # Different victim alliance each time
                attacker_count=10,
                attacker_alliances=[4000001 + i],  # Different attacker each time
            )
            for i in range(4)
        ]

        all_kills = war_kills + camp_kills

        # With war context, should still detect gatecamp from non-war kills
        result = detect_gatecamp(
            system_id=30000142,
            kills=all_kills,
            war_context=provider,
        )

        assert result is not None
        assert result.war_kills_filtered == 2
        assert result.kill_count == 4  # Only non-war kills counted

    def test_gatecamp_status_includes_war_metadata(self):
        """GatecampStatus should include war metadata when applicable."""
        from aria_esi.services.redisq.threat_cache import detect_gatecamp

        provider = WarContextProvider()

        # Add war relationship
        rel = WarRelationship(
            aggressor_id=1000001,
            defender_id=2000001,
        )
        provider.add_relationship(rel)

        # Create mixed kills
        war_kills = [
            make_kill(
                kill_id=1,
                victim_alliance=2000001,
                attacker_count=10,
                attacker_alliances=[1000001],
            )
        ]
        camp_kills = [
            make_kill(
                kill_id=i + 100,
                victim_corp=i + 1000,
                attacker_count=10,
            )
            for i in range(4)
        ]

        result = detect_gatecamp(
            system_id=30000142,
            kills=war_kills + camp_kills,
            war_context=provider,
        )

        assert result is not None
        assert result.war_kills_filtered == 1
        assert result.war_attacker_alliance == 1000001
        assert result.war_defender_alliance == 2000001

        # Verify it's in the dict output
        result_dict = result.to_dict()
        assert result_dict["war_kills_filtered"] == 1
