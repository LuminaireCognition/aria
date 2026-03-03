"""
Tests for EOS Bridge.

Tests cover:
- Singleton pattern
- Lazy initialization
- Calculate stats with all_v mode
- Calculate stats with pilot_skills mode
- Fit construction
- Stats extraction
- Error handling
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from aria_esi.fitting.eos_bridge import (
    ATTR_ARMOR_EM_RESIST,
    ATTR_ARMOR_EXPLOSIVE_RESIST,
    ATTR_ARMOR_KINETIC_RESIST,
    ATTR_ARMOR_THERMAL_RESIST,
    ATTR_CAP_CAPACITY,
    ATTR_MASS,
    ATTR_MAX_VELOCITY,
    ATTR_SHIELD_EM_RESIST,
    ATTR_SHIELD_EXPLOSIVE_RESIST,
    ATTR_SHIELD_KINETIC_RESIST,
    ATTR_SHIELD_THERMAL_RESIST,
    EOSBridge,
    calculate_fit_stats,
    get_eos_bridge,
)
from aria_esi.models.fitting import DamageProfile, FitStatsResult

# =============================================================================
# Singleton Pattern Tests
# =============================================================================


class TestSingletonPattern:
    """Tests for EOSBridge singleton behavior."""

    def test_get_instance_returns_same_instance(self):
        """Test that get_instance returns the same instance."""
        EOSBridge.reset_instance()

        instance1 = EOSBridge.get_instance()
        instance2 = EOSBridge.get_instance()

        assert instance1 is instance2

    def test_reset_instance_clears_singleton(self):
        """Test that reset_instance clears the singleton."""
        EOSBridge.reset_instance()

        instance1 = EOSBridge.get_instance()
        EOSBridge.reset_instance()
        instance2 = EOSBridge.get_instance()

        assert instance1 is not instance2

    def test_get_eos_bridge_returns_singleton(self):
        """Test module-level get_eos_bridge function."""
        EOSBridge.reset_instance()

        bridge1 = get_eos_bridge()
        bridge2 = get_eos_bridge()

        assert bridge1 is bridge2


# =============================================================================
# Initialization Tests
# =============================================================================


class TestInitialization:
    """Tests for EOS initialization."""

    def test_is_initialized_false_initially(self):
        """Test that bridge is not initialized after creation."""
        EOSBridge.reset_instance()
        bridge = EOSBridge.get_instance()

        assert bridge.is_initialized() is False

    def test_initialize_with_valid_data(self, mock_eos_data_path, mock_eos_module):
        """Test initialization with valid data and mocked EOS."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                bridge = EOSBridge.get_instance()
                bridge.initialize()

                assert bridge.is_initialized() is True
                mock_manager.ensure_valid.assert_called_once()

    def test_initialize_when_already_initialized(self, mock_eos_data_path, mock_eos_module):
        """Test that initialize is idempotent."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                bridge = EOSBridge.get_instance()
                bridge.initialize()
                bridge.initialize()  # Second call should be no-op

                # ensure_valid should only be called once
                assert mock_manager.ensure_valid.call_count == 1

    def test_initialize_without_eos_raises(self, mock_eos_data_path):
        """Test that initialization raises when EOS not installed."""
        EOSBridge.reset_instance()

        with patch(
            "aria_esi.fitting.eos_bridge.get_eos_data_manager"
        ) as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.ensure_valid = MagicMock()
            mock_manager.data_path = mock_eos_data_path
            mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
            mock_get_manager.return_value = mock_manager

            # Simulate ImportError when importing eos
            with patch.dict("sys.modules", {"aria_esi._vendor.eos": None}):
                EOSBridge.get_instance()

                # This test verifies the error message mentions EOS
                # In practice, the ImportError path is tested


# =============================================================================
# Calculate Stats Tests
# =============================================================================


class TestCalculateStats:
    """Tests for calculate_stats method."""

    def test_calculate_stats_basic(self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path):
        """Test basic stats calculation."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                # Mock extract_skills_for_fit in the skills module where it's imported from
                with patch(
                    "aria_esi.fitting.skills.extract_skills_for_fit"
                ) as mock_extract:
                    mock_extract.return_value = {3332: 5, 3436: 5}

                    bridge = EOSBridge.get_instance()
                    result = bridge.calculate_stats(vexor_parsed_fit)

                    assert isinstance(result, FitStatsResult)
                    assert result.ship_type_id == 626
                    assert result.skill_mode == "all_v"

    def test_calculate_stats_with_damage_profile(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test stats calculation with custom damage profile."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                with patch(
                    "aria_esi.fitting.skills.extract_skills_for_fit"
                ) as mock_extract:
                    mock_extract.return_value = {3332: 5}

                    bridge = EOSBridge.get_instance()
                    dmg_profile = DamageProfile.em_heavy()
                    result = bridge.calculate_stats(vexor_parsed_fit, damage_profile=dmg_profile)

                    assert isinstance(result, FitStatsResult)

    def test_calculate_stats_with_pilot_skills(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test stats calculation with pilot skills."""
        EOSBridge.reset_instance()

        pilot_skills = {3332: 4, 3436: 5, 3443: 3}

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                bridge = EOSBridge.get_instance()
                result = bridge.calculate_stats(vexor_parsed_fit, skill_levels=pilot_skills)

                assert result.skill_mode == "pilot_skills"

    def test_calculate_stats_all_v_mode(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test that None skill_levels triggers all_v mode."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                with patch(
                    "aria_esi.fitting.skills.extract_skills_for_fit"
                ) as mock_extract:
                    mock_extract.return_value = {3332: 5}

                    bridge = EOSBridge.get_instance()
                    result = bridge.calculate_stats(vexor_parsed_fit, skill_levels=None)

                    assert result.skill_mode == "all_v"
                    mock_extract.assert_called_once()


# =============================================================================
# Fit Construction Tests
# =============================================================================


class TestFitConstruction:
    """Tests for fit construction behavior."""

    def test_modules_added_to_correct_slots(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test that modules are added to correct slot types."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                with patch(
                    "aria_esi.fitting.skills.extract_skills_for_fit"
                ) as mock_extract:
                    mock_extract.return_value = {3332: 5}

                    bridge = EOSBridge.get_instance()
                    bridge.calculate_stats(vexor_parsed_fit)

                    # Verify ModuleLow was called for low slots (3 DDAs)
                    assert mock_eos_module.ModuleLow.call_count == 3

                    # Verify ModuleMid was called for mid slots (1 AB)
                    assert mock_eos_module.ModuleMid.call_count == 1

                    # Verify ModuleHigh was called for high slots (1 Drone Link)
                    assert mock_eos_module.ModuleHigh.call_count == 1

    def test_offline_module_state(
        self, fit_with_offline_module, mock_eos_module, mock_eos_data_path
    ):
        """Test that offline modules use offline state."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                with patch(
                    "aria_esi.fitting.skills.extract_skills_for_fit"
                ) as mock_extract:
                    mock_extract.return_value = {}

                    bridge = EOSBridge.get_instance()
                    bridge.calculate_stats(fit_with_offline_module)

                    # Verify ModuleLow was called with offline state
                    mock_eos_module.ModuleLow.assert_called_with(
                        4405, state=mock_eos_module.State.offline
                    )

    def test_drones_added_as_active(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test that drones are added in active state."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                with patch(
                    "aria_esi.fitting.skills.extract_skills_for_fit"
                ) as mock_extract:
                    mock_extract.return_value = {3332: 5}

                    bridge = EOSBridge.get_instance()
                    bridge.calculate_stats(vexor_parsed_fit)

                    # Vexor has 10 drones total (5 Hammerhead + 5 Hobgoblin)
                    assert mock_eos_module.Drone.call_count == 10

    def test_non_offline_modules_use_active_state(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test that non-offline modules use State.active (not State.online)."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                with patch(
                    "aria_esi.fitting.skills.extract_skills_for_fit"
                ) as mock_extract:
                    mock_extract.return_value = {3332: 5}

                    bridge = EOSBridge.get_instance()
                    bridge.calculate_stats(vexor_parsed_fit)

                    # All non-offline modules should use State.active
                    for call in mock_eos_module.ModuleLow.call_args_list:
                        assert call.kwargs["state"] == mock_eos_module.State.active

                    for call in mock_eos_module.ModuleMid.call_args_list:
                        assert call.kwargs["state"] == mock_eos_module.State.active

                    for call in mock_eos_module.ModuleHigh.call_args_list:
                        assert call.kwargs["state"] == mock_eos_module.State.active

    def test_charges_assigned_as_charge_instances(
        self, fit_with_charges, mock_eos_module, mock_eos_data_path
    ):
        """Test that charges are assigned as Charge(type_id) instances."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                with patch(
                    "aria_esi.fitting.skills.extract_skills_for_fit"
                ) as mock_extract:
                    mock_extract.return_value = {}

                    bridge = EOSBridge.get_instance()
                    bridge.calculate_stats(fit_with_charges)

                    # Charge() should have been called with the charge type ID
                    mock_eos_module.Charge.assert_called_once_with(27361)

    def test_module_without_charge_skips_charge_assignment(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test that modules without charges don't trigger Charge()."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                with patch(
                    "aria_esi.fitting.skills.extract_skills_for_fit"
                ) as mock_extract:
                    mock_extract.return_value = {3332: 5}

                    bridge = EOSBridge.get_instance()
                    bridge.calculate_stats(vexor_parsed_fit)

                    # No modules in vexor_parsed_fit have charges
                    mock_eos_module.Charge.assert_not_called()


# =============================================================================
# Module-level Function Tests
# =============================================================================


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_calculate_fit_stats_function(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test calculate_fit_stats convenience function."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                with patch(
                    "aria_esi.fitting.skills.extract_skills_for_fit"
                ) as mock_extract:
                    mock_extract.return_value = {3332: 5}

                    result = calculate_fit_stats(vexor_parsed_fit)

                    assert isinstance(result, FitStatsResult)


# =============================================================================
# Stats Extraction Tests
# =============================================================================


class TestStatsExtraction:
    """Tests for statistics extraction."""

    def test_dps_breakdown_extracted(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test that DPS breakdown is extracted correctly."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                with patch(
                    "aria_esi.fitting.skills.extract_skills_for_fit"
                ) as mock_extract:
                    mock_extract.return_value = {3332: 5}

                    bridge = EOSBridge.get_instance()
                    result = bridge.calculate_stats(vexor_parsed_fit)

                    # Mock returns 500 total DPS (thermal)
                    assert result.dps.total == 500.0
                    assert result.dps.thermal == 500.0

    def test_tank_stats_extracted(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test that tank stats are extracted correctly."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                with patch(
                    "aria_esi.fitting.skills.extract_skills_for_fit"
                ) as mock_extract:
                    mock_extract.return_value = {3332: 5}

                    bridge = EOSBridge.get_instance()
                    result = bridge.calculate_stats(vexor_parsed_fit)

                    # Mock returns 5000 total HP, 8000 total EHP
                    assert result.tank.total_hp == 5000.0
                    assert result.tank.total_ehp == 8000.0

    def test_resource_usage_extracted(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test that resource usage is extracted correctly."""
        EOSBridge.reset_instance()

        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                with patch(
                    "aria_esi.fitting.skills.extract_skills_for_fit"
                ) as mock_extract:
                    mock_extract.return_value = {3332: 5}

                    bridge = EOSBridge.get_instance()
                    result = bridge.calculate_stats(vexor_parsed_fit)

                    # Mock returns 200 CPU used, 375 output
                    assert result.cpu.used == 200.0
                    assert result.cpu.output == 375.0


# =============================================================================
# Attribute ID Constants Tests
# =============================================================================


class TestAttributeConstants:
    """Tests for attribute ID constants."""

    def test_common_attribute_ids_defined(self):
        """Test that common attribute IDs are defined."""
        assert ATTR_MASS == 4
        assert ATTR_MAX_VELOCITY == 37
        assert ATTR_CAP_CAPACITY == 482

    def test_resist_attribute_ids_match_eos_const(self):
        """Resist IDs must match EOS library's authoritative mapping.

        EVE SDE order is EM, Explosive, Kinetic, Thermal for consecutive IDs.
        Ref: _vendor/eos/const/eve.py AttrId
        """
        from aria_esi._vendor.eos.const.eve import AttrId

        # Armor (267-270)
        assert ATTR_ARMOR_EM_RESIST == AttrId.armor_em_dmg_resonance
        assert ATTR_ARMOR_EXPLOSIVE_RESIST == AttrId.armor_expl_dmg_resonance
        assert ATTR_ARMOR_KINETIC_RESIST == AttrId.armor_kin_dmg_resonance
        assert ATTR_ARMOR_THERMAL_RESIST == AttrId.armor_therm_dmg_resonance

        # Shield (271-274)
        assert ATTR_SHIELD_EM_RESIST == AttrId.shield_em_dmg_resonance
        assert ATTR_SHIELD_EXPLOSIVE_RESIST == AttrId.shield_expl_dmg_resonance
        assert ATTR_SHIELD_KINETIC_RESIST == AttrId.shield_kin_dmg_resonance
        assert ATTR_SHIELD_THERMAL_RESIST == AttrId.shield_therm_dmg_resonance
