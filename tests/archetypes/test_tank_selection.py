"""
Tests for tank variant selection constraints and fallbacks.
"""

from __future__ import annotations

from aria_esi.archetypes.tank_selection import TankVariantConfig, select_tank_variant


class TestSelectTankVariant:
    """Tests for select_tank_variant."""

    def test_single_variant_ignores_shield_heavy_skills(self) -> None:
        """Single-variant configs should never select an unavailable shield path."""
        config = TankVariantConfig(
            available=["armor_active"],
            default="armor_active",
            selection_strategy="skill_based",
            skill_comparison={
                "armor": {
                    "skills": [
                        "Hull Upgrades",
                        "Mechanics",
                        "Repair Systems",
                        "Armor Rigging",
                    ],
                    "weight": 1.0,
                },
                "shield": {
                    "skills": [
                        "Shield Management",
                        "Shield Operation",
                        "Shield Upgrades",
                        "Tactical Shield Manipulation",
                    ],
                    "weight": 1.0,
                },
                "tie_breaker": "armor",
            },
            tie_breaker="armor",
        )
        # Shield-heavy pilot profile.
        pilot_skills = {3416: 5, 3419: 5, 21059: 5, 3420: 5}

        result = select_tank_variant(config, pilot_skills)

        assert result.variant == "armor_active"
        assert result.variant_path == "armor"
        assert result.selection_reason == "single_variant"

    def test_unavailable_override_falls_back_to_available_default(self) -> None:
        """Override to unavailable path should degrade to available variant."""
        config = TankVariantConfig(
            available=["armor_active"],
            default="armor_active",
            selection_strategy="skill_based",
            tie_breaker="armor",
        )

        result = select_tank_variant(config, pilot_skills={}, override="shield")

        assert result.variant == "armor_active"
        assert result.variant_path == "armor"
        assert result.selection_reason == "override_unavailable"

    def test_discovered_paths_constrain_selection(self) -> None:
        """Selection should honor discovered filesystem variant paths."""
        config = TankVariantConfig(
            available=["armor_active", "shield_buffer"],
            default="armor_active",
            selection_strategy="skill_based",
            skill_comparison={
                "armor": {"skills": ["Hull Upgrades"], "weight": 1.0},
                "shield": {"skills": ["Shield Management"], "weight": 1.0},
                "tie_breaker": "armor",
            },
            tie_breaker="armor",
        )
        # Shield-heavy pilot profile.
        pilot_skills = {3416: 5}

        result = select_tank_variant(
            config,
            pilot_skills,
            available_variant_paths=["armor"],
        )

        assert result.variant == "armor_active"
        assert result.variant_path == "armor"
        assert result.selection_reason == "single_variant"
