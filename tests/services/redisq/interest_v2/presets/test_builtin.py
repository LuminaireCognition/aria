"""
Tests for builtin presets module.

Tests PresetDefinition dataclass and all 7 built-in preset instances.
"""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.interest_v2.presets.builtin import (
    BALANCED,
    BUILTIN_PRESETS,
    HUNTER,
    INDUSTRIAL,
    POLITICAL,
    SOVEREIGNTY,
    TRADE_HUB,
    WORMHOLE,
    PresetDefinition,
    get_builtin_preset,
    list_builtin_presets,
)


class TestPresetDefinition:
    """Tests for PresetDefinition dataclass."""

    def test_create_minimal_preset(self) -> None:
        """Test creating a preset with minimal required fields."""
        preset = PresetDefinition(
            name="test",
            description="Test preset",
            weights={"location": 0.5},
        )
        assert preset.name == "test"
        assert preset.description == "Test preset"
        assert preset.weights == {"location": 0.5}
        assert preset.signals == {}
        assert preset.rules == {}
        assert preset.thresholds is None

    def test_create_full_preset(self) -> None:
        """Test creating a preset with all fields."""
        preset = PresetDefinition(
            name="full",
            description="Full preset",
            weights={"location": 0.5, "value": 0.7},
            signals={"location": {"systems": [1, 2, 3]}},
            rules={"always_notify": ["high_value"]},
            thresholds={"notify": 0.7, "priority": 0.9},
        )
        assert preset.signals == {"location": {"systems": [1, 2, 3]}}
        assert preset.rules == {"always_notify": ["high_value"]}
        assert preset.thresholds == {"notify": 0.7, "priority": 0.9}

    def test_to_dict_minimal(self) -> None:
        """Test to_dict() with minimal preset."""
        preset = PresetDefinition(
            name="minimal",
            description="Minimal",
            weights={"location": 0.5},
        )
        result = preset.to_dict()
        assert result == {
            "name": "minimal",
            "description": "Minimal",
            "weights": {"location": 0.5},
        }
        # Should not include empty signals/rules
        assert "signals" not in result
        assert "rules" not in result
        assert "thresholds" not in result

    def test_to_dict_full(self) -> None:
        """Test to_dict() with all fields populated."""
        preset = PresetDefinition(
            name="full",
            description="Full",
            weights={"location": 0.5},
            signals={"location": {"home_weight": 1.0}},
            rules={"always_notify": ["test_rule"]},
            thresholds={"notify": 0.6},
        )
        result = preset.to_dict()
        assert result["signals"] == {"location": {"home_weight": 1.0}}
        assert result["rules"] == {"always_notify": ["test_rule"]}
        assert result["thresholds"] == {"notify": 0.6}

    def test_to_dict_returns_copy(self) -> None:
        """Test that to_dict() returns a copy of weights."""
        preset = PresetDefinition(
            name="test",
            description="Test",
            weights={"location": 0.5},
        )
        result = preset.to_dict()
        result["weights"]["location"] = 9.9
        # Original should be unchanged
        assert preset.weights["location"] == 0.5


class TestBuiltinPresets:
    """Tests for built-in preset instances."""

    @pytest.mark.parametrize(
        "preset,expected_name",
        [
            (TRADE_HUB, "trade-hub"),
            (POLITICAL, "political"),
            (INDUSTRIAL, "industrial"),
            (HUNTER, "hunter"),
            (SOVEREIGNTY, "sovereignty"),
            (WORMHOLE, "wormhole"),
            (BALANCED, "balanced"),
        ],
    )
    def test_preset_has_correct_name(
        self, preset: PresetDefinition, expected_name: str
    ) -> None:
        """Test each preset has correct name."""
        assert preset.name == expected_name

    @pytest.mark.parametrize(
        "preset_name",
        ["trade-hub", "political", "industrial", "hunter", "sovereignty", "wormhole", "balanced"],
    )
    def test_preset_in_registry(self, preset_name: str) -> None:
        """Test all presets are registered in BUILTIN_PRESETS."""
        assert preset_name in BUILTIN_PRESETS
        assert isinstance(BUILTIN_PRESETS[preset_name], PresetDefinition)

    def test_builtin_presets_count(self) -> None:
        """Test expected number of built-in presets."""
        assert len(BUILTIN_PRESETS) == 7

    @pytest.mark.parametrize(
        "preset_name",
        ["trade-hub", "political", "industrial", "hunter", "sovereignty", "wormhole", "balanced"],
    )
    def test_preset_has_description(self, preset_name: str) -> None:
        """Test all presets have non-empty descriptions."""
        preset = BUILTIN_PRESETS[preset_name]
        assert preset.description
        assert len(preset.description) > 10

    @pytest.mark.parametrize(
        "preset_name",
        ["trade-hub", "political", "industrial", "hunter", "sovereignty", "wormhole", "balanced"],
    )
    def test_preset_has_nine_categories(self, preset_name: str) -> None:
        """Test all presets define weights for all 9 canonical categories."""
        preset = BUILTIN_PRESETS[preset_name]
        expected_categories = {
            "location",
            "value",
            "politics",
            "activity",
            "time",
            "routes",
            "assets",
            "war",
            "ship",
        }
        assert set(preset.weights.keys()) == expected_categories


class TestTradeHubPreset:
    """Tests specific to trade-hub preset."""

    def test_trade_hub_weights(self) -> None:
        """Test trade-hub preset prioritizes location and value."""
        assert TRADE_HUB.weights["location"] == 0.8
        assert TRADE_HUB.weights["value"] == 0.7
        # Low politics/war weight for trade hub
        assert TRADE_HUB.weights["politics"] == 0.1
        assert TRADE_HUB.weights["war"] == 0.0

    def test_trade_hub_signals(self) -> None:
        """Test trade-hub has location and ship signals configured."""
        assert "location" in TRADE_HUB.signals
        assert TRADE_HUB.signals["location"]["geographic"]["trade_hub_weight"] == 1.0
        assert "ship" in TRADE_HUB.signals
        assert "freighter" in TRADE_HUB.signals["ship"]["prefer"]

    def test_trade_hub_rules(self) -> None:
        """Test trade-hub has always_notify for high_value."""
        assert "always_notify" in TRADE_HUB.rules
        assert "high_value" in TRADE_HUB.rules["always_notify"]


class TestPoliticalPreset:
    """Tests specific to political preset."""

    def test_political_weights(self) -> None:
        """Test political preset prioritizes politics category."""
        assert POLITICAL.weights["politics"] == 1.0
        # Low location/value weight
        assert POLITICAL.weights["location"] == 0.1
        assert POLITICAL.weights["value"] == 0.1

    def test_political_signals(self) -> None:
        """Test political has politics signals configured."""
        assert "politics" in POLITICAL.signals
        assert "require_any" in POLITICAL.signals["politics"]
        assert "enemies" in POLITICAL.signals["politics"]["require_any"]
        assert "friendlies" in POLITICAL.signals["politics"]["require_any"]


class TestIndustrialPreset:
    """Tests specific to industrial preset."""

    def test_industrial_weights(self) -> None:
        """Test industrial preset prioritizes ship category."""
        assert INDUSTRIAL.weights["ship"] == 0.8
        assert INDUSTRIAL.weights["value"] == 0.6

    def test_industrial_ship_signals(self) -> None:
        """Test industrial has ship signals for industrial ships."""
        assert "ship" in INDUSTRIAL.signals
        preferred = INDUSTRIAL.signals["ship"]["prefer"]
        assert "orca" in preferred
        assert "mining_barge" in preferred
        assert "freighter" in preferred

    def test_industrial_rules(self) -> None:
        """Test industrial ignores pod-only kills."""
        assert "always_ignore" in INDUSTRIAL.rules
        assert "pod_only" in INDUSTRIAL.rules["always_ignore"]


class TestHunterPreset:
    """Tests specific to hunter preset."""

    def test_hunter_weights(self) -> None:
        """Test hunter preset prioritizes activity."""
        assert HUNTER.weights["activity"] == 0.8
        assert HUNTER.weights["location"] == 0.6
        assert HUNTER.weights["routes"] == 0.5

    def test_hunter_activity_signals(self) -> None:
        """Test hunter has activity signals configured."""
        assert "activity" in HUNTER.signals
        assert HUNTER.signals["activity"]["min_kills_hour"] == 3
        assert HUNTER.signals["activity"]["prefer_active"] is True


class TestSovereigntyPreset:
    """Tests specific to sovereignty preset."""

    def test_sovereignty_weights(self) -> None:
        """Test sovereignty preset prioritizes war and politics."""
        assert SOVEREIGNTY.weights["war"] == 0.9
        assert SOVEREIGNTY.weights["politics"] == 0.7
        assert SOVEREIGNTY.weights["assets"] == 0.6

    def test_sovereignty_ship_signals(self) -> None:
        """Test sovereignty prefers capital ships."""
        assert "ship" in SOVEREIGNTY.signals
        preferred = SOVEREIGNTY.signals["ship"]["prefer"]
        assert "carrier" in preferred
        assert "titan" in preferred


class TestWormholePreset:
    """Tests specific to wormhole preset."""

    def test_wormhole_weights(self) -> None:
        """Test wormhole preset prioritizes location."""
        assert WORMHOLE.weights["location"] == 1.0
        # No routes in wormhole space
        assert WORMHOLE.weights["routes"] == 0.0

    def test_wormhole_location_signals(self) -> None:
        """Test wormhole has location signals for wormhole space."""
        assert "location" in WORMHOLE.signals
        assert WORMHOLE.signals["location"]["security"]["prefer_wormhole"] is True


class TestBalancedPreset:
    """Tests specific to balanced preset."""

    def test_balanced_weights(self) -> None:
        """Test balanced preset has moderate weights."""
        # Core categories at 0.5
        assert BALANCED.weights["location"] == 0.5
        assert BALANCED.weights["value"] == 0.5
        assert BALANCED.weights["politics"] == 0.5
        assert BALANCED.weights["activity"] == 0.5
        # Secondary categories at 0.3
        assert BALANCED.weights["routes"] == 0.3
        assert BALANCED.weights["assets"] == 0.3
        assert BALANCED.weights["war"] == 0.3
        assert BALANCED.weights["ship"] == 0.3
        # Time always zero
        assert BALANCED.weights["time"] == 0.0

    def test_balanced_no_signals(self) -> None:
        """Test balanced preset has no custom signals."""
        assert BALANCED.signals == {}

    def test_balanced_no_rules(self) -> None:
        """Test balanced preset has no custom rules."""
        assert BALANCED.rules == {}


class TestGetBuiltinPreset:
    """Tests for get_builtin_preset function."""

    def test_get_existing_preset(self) -> None:
        """Test retrieving existing preset."""
        preset = get_builtin_preset("trade-hub")
        assert preset is not None
        assert preset.name == "trade-hub"

    def test_get_nonexistent_preset(self) -> None:
        """Test retrieving nonexistent preset returns None."""
        preset = get_builtin_preset("nonexistent")
        assert preset is None

    def test_get_case_insensitive(self) -> None:
        """Test preset lookup is case-insensitive."""
        # The function does .lower() on input
        preset1 = get_builtin_preset("Trade-Hub")
        preset2 = get_builtin_preset("TRADE-HUB")
        preset3 = get_builtin_preset("trade-hub")
        # All should find the same preset
        assert preset1 is not None
        assert preset2 is not None
        assert preset3 is not None
        assert preset1 is preset2 is preset3

    def test_get_with_uppercase(self) -> None:
        """Test uppercase lookup finds preset."""
        preset = get_builtin_preset("HUNTER")
        assert preset is not None
        assert preset.name == "hunter"

    def test_get_returns_same_instance(self) -> None:
        """Test get returns the same instance from registry."""
        preset1 = get_builtin_preset("balanced")
        preset2 = get_builtin_preset("balanced")
        assert preset1 is preset2


class TestListBuiltinPresets:
    """Tests for list_builtin_presets function."""

    def test_list_returns_all_names(self) -> None:
        """Test list returns all preset names."""
        names = list_builtin_presets()
        expected = {
            "trade-hub",
            "political",
            "industrial",
            "hunter",
            "sovereignty",
            "wormhole",
            "balanced",
        }
        assert set(names) == expected

    def test_list_returns_list_type(self) -> None:
        """Test list returns a list."""
        names = list_builtin_presets()
        assert isinstance(names, list)

    def test_list_count_matches_registry(self) -> None:
        """Test list count matches registry."""
        names = list_builtin_presets()
        assert len(names) == len(BUILTIN_PRESETS)

    def test_list_all_names_are_strings(self) -> None:
        """Test all names in list are strings."""
        names = list_builtin_presets()
        assert all(isinstance(name, str) for name in names)
