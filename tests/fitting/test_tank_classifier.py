"""
Tests for Tank Type Classifier.

Tests tank classification, resist analysis, and damage profiling.
"""

from __future__ import annotations

import pytest

from aria_esi.models.fitting import ParsedFit, ParsedModule


# =============================================================================
# Fixtures
# =============================================================================


def make_fit(
    low_slots: list[str] | None = None,
    mid_slots: list[str] | None = None,
    high_slots: list[str] | None = None,
    rigs: list[str] | None = None,
    fit_name: str = "Test Fit",
) -> ParsedFit:
    """Create a ParsedFit with the given module names."""
    return ParsedFit(
        ship_type_id=123,
        ship_type_name="Test Ship",
        fit_name=fit_name,
        low_slots=[ParsedModule(type_id=i, type_name=name) for i, name in enumerate(low_slots or [])],
        mid_slots=[ParsedModule(type_id=i + 100, type_name=name) for i, name in enumerate(mid_slots or [])],
        high_slots=[ParsedModule(type_id=i + 200, type_name=name) for i, name in enumerate(high_slots or [])],
        rigs=[ParsedModule(type_id=i + 300, type_name=name) for i, name in enumerate(rigs or [])],
    )


# =============================================================================
# Pattern Matching Tests
# =============================================================================


class TestMatchesAnyPattern:
    """Test _matches_any_pattern function."""

    def test_matches_armor_repairer(self):
        """Matches armor repairer pattern."""
        from aria_esi.fitting.tank_classifier import _matches_any_pattern, ACTIVE_TANK_PATTERNS

        assert _matches_any_pattern("Medium Armor Repairer II", ACTIVE_TANK_PATTERNS)
        assert _matches_any_pattern("Large Armor Repairer II", ACTIVE_TANK_PATTERNS)

    def test_matches_shield_booster(self):
        """Matches shield booster pattern."""
        from aria_esi.fitting.tank_classifier import _matches_any_pattern, ACTIVE_TANK_PATTERNS

        assert _matches_any_pattern("Medium Shield Booster II", ACTIVE_TANK_PATTERNS)
        assert _matches_any_pattern("X-Large Shield Booster II", ACTIVE_TANK_PATTERNS)

    def test_matches_armor_plate(self):
        """Matches armor plate pattern."""
        from aria_esi.fitting.tank_classifier import _matches_any_pattern, BUFFER_TANK_PATTERNS

        # Module name must contain "armor plate" to match
        assert _matches_any_pattern("1600mm Rolled Tungsten Compact Armor Plate", BUFFER_TANK_PATTERNS)
        # Also test reinforced bulkhead
        assert _matches_any_pattern("Reinforced Bulkheads II", BUFFER_TANK_PATTERNS)

    def test_matches_shield_extender(self):
        """Matches shield extender pattern."""
        from aria_esi.fitting.tank_classifier import _matches_any_pattern, BUFFER_TANK_PATTERNS

        assert _matches_any_pattern("Large Shield Extender II", BUFFER_TANK_PATTERNS)

    def test_matches_shield_power_relay(self):
        """Matches shield power relay pattern."""
        from aria_esi.fitting.tank_classifier import _matches_any_pattern, PASSIVE_TANK_PATTERNS

        assert _matches_any_pattern("Shield Power Relay II", PASSIVE_TANK_PATTERNS)

    def test_case_insensitive(self):
        """Pattern matching is case-insensitive."""
        from aria_esi.fitting.tank_classifier import _matches_any_pattern, ACTIVE_TANK_PATTERNS

        assert _matches_any_pattern("MEDIUM ARMOR REPAIRER II", ACTIVE_TANK_PATTERNS)
        assert _matches_any_pattern("medium armor repairer ii", ACTIVE_TANK_PATTERNS)

    def test_no_match(self):
        """Returns False for non-matching module."""
        from aria_esi.fitting.tank_classifier import _matches_any_pattern, ACTIVE_TANK_PATTERNS

        assert not _matches_any_pattern("Damage Control II", ACTIVE_TANK_PATTERNS)
        assert not _matches_any_pattern("Magnetic Field Stabilizer II", ACTIVE_TANK_PATTERNS)


# =============================================================================
# Tank Classification Tests
# =============================================================================


class TestClassifyTank:
    """Test classify_tank function."""

    def test_active_armor_tank(self):
        """Classifies fit with armor repairer as active."""
        from aria_esi.fitting.tank_classifier import classify_tank

        fit = make_fit(
            low_slots=["Medium Armor Repairer II", "Damage Control II"],
            mid_slots=["10MN Afterburner II"],
        )

        assert classify_tank(fit) == "active"

    def test_active_shield_tank(self):
        """Classifies fit with shield booster as active."""
        from aria_esi.fitting.tank_classifier import classify_tank

        fit = make_fit(
            mid_slots=["Large Shield Booster II", "Adaptive Invulnerability Field II"],
        )

        assert classify_tank(fit) == "active"

    def test_buffer_armor_tank(self):
        """Classifies fit with armor plates as buffer."""
        from aria_esi.fitting.tank_classifier import classify_tank

        fit = make_fit(
            low_slots=["1600mm Rolled Tungsten Compact Armor Plate", "Energized Adaptive Nano Membrane II"],
        )

        assert classify_tank(fit) == "buffer"

    def test_buffer_shield_tank(self):
        """Classifies fit with shield extenders as buffer."""
        from aria_esi.fitting.tank_classifier import classify_tank

        fit = make_fit(
            mid_slots=["Large Shield Extender II", "Large Shield Extender II"],
        )

        assert classify_tank(fit) == "buffer"

    def test_passive_shield_tank(self):
        """Classifies fit with shield power relays as passive."""
        from aria_esi.fitting.tank_classifier import classify_tank

        fit = make_fit(
            low_slots=["Shield Power Relay II", "Shield Power Relay II"],
            mid_slots=["Large Shield Extender II"],
        )

        assert classify_tank(fit) == "passive"

    def test_active_takes_precedence_over_buffer(self):
        """Active modules take precedence over buffer."""
        from aria_esi.fitting.tank_classifier import classify_tank

        fit = make_fit(
            low_slots=["Medium Armor Repairer II", "1600mm Rolled Tungsten Compact Armor Plate"],
        )

        assert classify_tank(fit) == "active"

    def test_buffer_with_rigs(self):
        """Buffer tank with rigs is classified correctly."""
        from aria_esi.fitting.tank_classifier import classify_tank

        fit = make_fit(
            low_slots=["Damage Control II"],
            rigs=["Large Trimark Armor Pump I", "Large Trimark Armor Pump I"],
        )

        assert classify_tank(fit) == "buffer"

    def test_passive_with_rigs(self):
        """Passive tank with rigs is classified correctly."""
        from aria_esi.fitting.tank_classifier import classify_tank

        fit = make_fit(
            low_slots=[],
            rigs=["Large Core Defense Field Purifier I"],
        )

        assert classify_tank(fit) == "passive"

    def test_default_to_buffer(self):
        """Defaults to buffer when no clear tank type detected."""
        from aria_esi.fitting.tank_classifier import classify_tank

        fit = make_fit(
            low_slots=["Damage Control II"],
            mid_slots=["10MN Afterburner II"],
        )

        assert classify_tank(fit) == "buffer"

    def test_empty_fit(self):
        """Empty fit defaults to buffer."""
        from aria_esi.fitting.tank_classifier import classify_tank

        fit = make_fit()

        assert classify_tank(fit) == "buffer"

    def test_ancillary_armor_repairer(self):
        """Ancillary armor repairer is classified as active."""
        from aria_esi.fitting.tank_classifier import classify_tank

        fit = make_fit(
            low_slots=["Medium Ancillary Armor Repairer"],
        )

        assert classify_tank(fit) == "active"

    def test_ancillary_shield_booster(self):
        """Ancillary shield booster is classified as active."""
        from aria_esi.fitting.tank_classifier import classify_tank

        fit = make_fit(
            mid_slots=["Large Ancillary Shield Booster"],
        )

        assert classify_tank(fit) == "active"


# =============================================================================
# Resist Profile Tests
# =============================================================================


class TestDerivePrimaryResists:
    """Test derive_primary_resists function."""

    def test_all_above_threshold(self):
        """All resists above threshold are returned."""
        from aria_esi.fitting.tank_classifier import derive_primary_resists

        resists = {"em": 75.0, "thermal": 70.0, "kinetic": 65.0, "explosive": 62.0}

        result = derive_primary_resists(resists, threshold=60.0)

        assert set(result) == {"em", "thermal", "kinetic", "explosive"}

    def test_some_above_threshold(self):
        """Only resists above threshold are returned."""
        from aria_esi.fitting.tank_classifier import derive_primary_resists

        resists = {"em": 75.0, "thermal": 50.0, "kinetic": 40.0, "explosive": 30.0}

        result = derive_primary_resists(resists, threshold=60.0)

        assert result == ["em"]

    def test_none_above_threshold(self):
        """Empty list when no resists above threshold."""
        from aria_esi.fitting.tank_classifier import derive_primary_resists

        resists = {"em": 40.0, "thermal": 35.0, "kinetic": 30.0, "explosive": 25.0}

        result = derive_primary_resists(resists, threshold=60.0)

        assert result == []

    def test_custom_threshold(self):
        """Custom threshold is respected."""
        from aria_esi.fitting.tank_classifier import derive_primary_resists

        resists = {"em": 75.0, "thermal": 70.0, "kinetic": 65.0, "explosive": 60.0}

        result = derive_primary_resists(resists, threshold=75.0)

        assert result == ["em"]

    def test_missing_damage_types(self):
        """Missing damage types default to 0."""
        from aria_esi.fitting.tank_classifier import derive_primary_resists

        resists = {"em": 75.0}

        result = derive_primary_resists(resists, threshold=60.0)

        assert result == ["em"]


# =============================================================================
# Damage Profile Tests
# =============================================================================


class TestDerivePrimaryDamage:
    """Test derive_primary_damage function."""

    def test_single_dominant_type(self):
        """Single dominant damage type is returned."""
        from aria_esi.fitting.tank_classifier import derive_primary_damage

        dps = {"em": 0, "thermal": 200, "kinetic": 50, "explosive": 0}

        result = derive_primary_damage(dps, threshold_pct=50.0)

        assert result == ["thermal"]

    def test_multiple_types_above_threshold(self):
        """Multiple types above threshold are returned."""
        from aria_esi.fitting.tank_classifier import derive_primary_damage

        dps = {"em": 0, "thermal": 150, "kinetic": 150, "explosive": 0}

        result = derive_primary_damage(dps, threshold_pct=50.0)

        assert set(result) == {"thermal", "kinetic"}

    def test_no_type_above_threshold_returns_highest(self):
        """Returns highest type when none above threshold."""
        from aria_esi.fitting.tank_classifier import derive_primary_damage

        dps = {"em": 30, "thermal": 30, "kinetic": 30, "explosive": 10}

        result = derive_primary_damage(dps, threshold_pct=50.0)

        # One of the highest should be returned
        assert len(result) == 1
        assert result[0] in ["em", "thermal", "kinetic"]

    def test_zero_total_dps(self):
        """Returns empty list for zero total DPS."""
        from aria_esi.fitting.tank_classifier import derive_primary_damage

        dps = {"em": 0, "thermal": 0, "kinetic": 0, "explosive": 0}

        result = derive_primary_damage(dps, threshold_pct=50.0)

        assert result == []

    def test_custom_threshold(self):
        """Custom threshold is respected."""
        from aria_esi.fitting.tank_classifier import derive_primary_damage

        dps = {"em": 0, "thermal": 100, "kinetic": 0, "explosive": 0}

        result = derive_primary_damage(dps, threshold_pct=100.0)

        assert result == ["thermal"]


# =============================================================================
# Tank Regen Tests
# =============================================================================


class TestCalculateTankRegen:
    """Test calculate_tank_regen function."""

    def test_buffer_returns_zero(self):
        """Buffer tank returns 0 regen."""
        from aria_esi.fitting.tank_classifier import calculate_tank_regen

        result = calculate_tank_regen("buffer", {})

        assert result == 0.0

    def test_passive_uses_recharge(self):
        """Passive tank uses shield recharge rate."""
        from aria_esi.fitting.tank_classifier import calculate_tank_regen

        fit_stats = {
            "capacitor": {"recharge_rate": 10.0}
        }

        result = calculate_tank_regen("passive", fit_stats)

        assert result == 25.0  # 10.0 * 2.5

    def test_passive_no_data(self):
        """Passive tank with no recharge data returns 0."""
        from aria_esi.fitting.tank_classifier import calculate_tank_regen

        result = calculate_tank_regen("passive", {})

        assert result == 0.0

    def test_active_with_tank_sustained(self):
        """Active tank uses tank_sustained if available."""
        from aria_esi.fitting.tank_classifier import calculate_tank_regen

        fit_stats = {
            "stats": {"tank_sustained": 150.0}
        }

        result = calculate_tank_regen("active", fit_stats)

        assert result == 150.0

    def test_active_no_data(self):
        """Active tank with no data returns 0."""
        from aria_esi.fitting.tank_classifier import calculate_tank_regen

        result = calculate_tank_regen("active", {})

        assert result == 0.0


# =============================================================================
# Full Analysis Tests
# =============================================================================


class TestAnalyzeTank:
    """Test analyze_tank function."""

    def test_basic_analysis(self):
        """Basic analysis returns tank type."""
        from aria_esi.fitting.tank_classifier import analyze_tank

        fit = make_fit(
            low_slots=["Medium Armor Repairer II"],
        )

        result = analyze_tank(fit)

        assert result["tank_type"] == "active"
        assert "tank_regen" in result
        assert "primary_resists" in result

    def test_analysis_without_stats(self):
        """Analysis without fit_stats uses defaults."""
        from aria_esi.fitting.tank_classifier import analyze_tank

        fit = make_fit(
            low_slots=["1600mm Rolled Tungsten Compact Armor Plate"],
        )

        result = analyze_tank(fit)

        assert result["tank_type"] == "buffer"
        assert result["tank_regen"] == 0.0
        assert result["primary_resists"] == []

    def test_analysis_with_armor_stats(self):
        """Analysis with armor tank stats."""
        from aria_esi.fitting.tank_classifier import analyze_tank

        fit = make_fit(
            low_slots=["1600mm Rolled Tungsten Compact Armor Plate"],
        )
        fit_stats = {
            "tank": {
                "armor": {
                    "ehp": 50000,
                    "resists": {"em": 75, "thermal": 65, "kinetic": 55, "explosive": 45}
                },
                "shield": {
                    "ehp": 10000,
                    "resists": {"em": 0, "thermal": 20, "kinetic": 40, "explosive": 50}
                }
            }
        }

        result = analyze_tank(fit, fit_stats)

        assert result["tank_type"] == "buffer"
        assert "resists" in result
        assert result["resists"]["em"] == 75
        assert "em" in result["primary_resists"]  # 75% is above 60% threshold

    def test_analysis_with_shield_stats(self):
        """Analysis with shield tank stats."""
        from aria_esi.fitting.tank_classifier import analyze_tank

        fit = make_fit(
            mid_slots=["Large Shield Extender II", "Large Shield Extender II"],
        )
        fit_stats = {
            "tank": {
                "armor": {
                    "ehp": 10000,
                    "resists": {"em": 50, "thermal": 45, "kinetic": 35, "explosive": 10}
                },
                "shield": {
                    "ehp": 60000,
                    "resists": {"em": 0, "thermal": 55, "kinetic": 70, "explosive": 75}
                }
            }
        }

        result = analyze_tank(fit, fit_stats)

        assert result["tank_type"] == "buffer"
        assert "resists" in result
        # Shield is primary (higher EHP), so use shield resists
        assert result["resists"]["kinetic"] == 70
        assert "kinetic" in result["primary_resists"]
        assert "explosive" in result["primary_resists"]


# =============================================================================
# Constants Tests
# =============================================================================


class TestPatternConstants:
    """Test pattern constant definitions."""

    def test_active_patterns_defined(self):
        """Active tank patterns are defined."""
        from aria_esi.fitting.tank_classifier import ACTIVE_TANK_PATTERNS

        assert len(ACTIVE_TANK_PATTERNS) > 0
        assert any("armor repair" in p for p in ACTIVE_TANK_PATTERNS)
        assert any("shield booster" in p for p in ACTIVE_TANK_PATTERNS)

    def test_buffer_patterns_defined(self):
        """Buffer tank patterns are defined."""
        from aria_esi.fitting.tank_classifier import BUFFER_TANK_PATTERNS

        assert len(BUFFER_TANK_PATTERNS) > 0
        assert any("armor plate" in p for p in BUFFER_TANK_PATTERNS)
        assert any("shield extender" in p for p in BUFFER_TANK_PATTERNS)

    def test_passive_patterns_defined(self):
        """Passive tank patterns are defined."""
        from aria_esi.fitting.tank_classifier import PASSIVE_TANK_PATTERNS

        assert len(PASSIVE_TANK_PATTERNS) > 0
        assert any("shield power relay" in p for p in PASSIVE_TANK_PATTERNS)
