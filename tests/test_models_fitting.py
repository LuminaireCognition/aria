"""
Tests for fitting models.
"""

from __future__ import annotations

from aria_esi.models.fitting import (
    DamageProfile,
    DroneStats,
    ParsedFit,
    ResourceUsage,
)


class TestResourceUsage:
    """Tests for ResourceUsage model."""

    def test_percent_with_positive_output(self):
        """Should calculate percent correctly."""
        usage = ResourceUsage(used=50.0, output=100.0)
        assert usage.percent == 50.0

    def test_percent_with_zero_output(self):
        """Should return 0% when output is zero."""
        usage = ResourceUsage(used=50.0, output=0.0)
        assert usage.percent == 0.0

    def test_percent_with_negative_output(self):
        """Should return 0% when output is negative."""
        usage = ResourceUsage(used=50.0, output=-10.0)
        assert usage.percent == 0.0

    def test_remaining(self):
        """Should calculate remaining correctly."""
        usage = ResourceUsage(used=30.0, output=100.0)
        assert usage.remaining == 70.0

    def test_is_overloaded_true(self):
        """Should detect overloaded state."""
        usage = ResourceUsage(used=150.0, output=100.0)
        assert usage.is_overloaded is True

    def test_is_overloaded_false(self):
        """Should not be overloaded when under capacity."""
        usage = ResourceUsage(used=50.0, output=100.0)
        assert usage.is_overloaded is False


class TestDroneStats:
    """Tests for DroneStats model."""

    def test_bandwidth_percent_with_positive_output(self):
        """Should calculate bandwidth percent correctly."""
        stats = DroneStats(
            bandwidth_used=25.0,
            bandwidth_output=50.0,
            bay_used=100.0,
            bay_output=200.0,
            drones_launched=5,
            drones_max=5,
        )
        assert stats.bandwidth_percent == 50.0

    def test_bandwidth_percent_with_zero_output(self):
        """Should return 0% when bandwidth output is zero."""
        stats = DroneStats(
            bandwidth_used=25.0,
            bandwidth_output=0.0,
            bay_used=100.0,
            bay_output=200.0,
            drones_launched=5,
            drones_max=5,
        )
        assert stats.bandwidth_percent == 0.0


class TestParsedFit:
    """Tests for ParsedFit model."""

    def test_to_dict(self):
        """Should serialize to dictionary."""
        fit = ParsedFit(
            ship_type_id=24690,
            ship_type_name="Vexor",
            fit_name="Test Fit",
            low_slots=["Damage Control II"],
            mid_slots=["10MN Afterburner II"],
            high_slots=["Drone Link Augmentor I"],
            rigs=["Medium Auxiliary Nano Pump I"],
        )
        result = fit.to_dict()

        assert result["ship_type_id"] == 24690
        assert result["ship_type_name"] == "Vexor"
        assert result["fit_name"] == "Test Fit"
        assert result["low_slots"] == 1
        assert result["mid_slots"] == 1
        assert result["high_slots"] == 1
        assert result["rigs"] == 1


class TestDamageProfile:
    """Tests for DamageProfile model."""

    def test_default_is_omni(self):
        """Default profile should be omni (25% each)."""
        profile = DamageProfile()
        assert profile.em == 25.0
        assert profile.thermal == 25.0
        assert profile.kinetic == 25.0
        assert profile.explosive == 25.0

    def test_validate_valid(self):
        """Should validate when percentages sum to 100."""
        profile = DamageProfile()
        assert profile.validate() is True

    def test_validate_invalid(self):
        """Should fail validation when percentages don't sum to 100."""
        profile = DamageProfile(em=50.0, thermal=50.0, kinetic=50.0, explosive=50.0)
        assert profile.validate() is False

    def test_to_dict(self):
        """Should serialize to dictionary."""
        profile = DamageProfile(em=50.0, thermal=40.0, kinetic=5.0, explosive=5.0)
        result = profile.to_dict()

        assert result["em"] == 50.0
        assert result["thermal"] == 40.0
        assert result["kinetic"] == 5.0
        assert result["explosive"] == 5.0

    def test_omni_factory(self):
        """omni() should return standard omni profile."""
        profile = DamageProfile.omni()
        assert profile.em == 25.0
        assert profile.thermal == 25.0
        assert profile.kinetic == 25.0
        assert profile.explosive == 25.0

    def test_em_heavy_factory(self):
        """em_heavy() should return EM-focused profile."""
        profile = DamageProfile.em_heavy()
        assert profile.em == 50.0
        assert profile.thermal == 40.0
        assert profile.kinetic == 5.0
        assert profile.explosive == 5.0
        assert profile.validate() is True

    def test_kinetic_heavy_factory(self):
        """kinetic_heavy() should return kinetic-focused profile."""
        profile = DamageProfile.kinetic_heavy()
        assert profile.em == 5.0
        assert profile.thermal == 15.0
        assert profile.kinetic == 60.0
        assert profile.explosive == 20.0
        assert profile.validate() is True

    def test_thermal_heavy_factory(self):
        """thermal_heavy() should return thermal-focused profile."""
        profile = DamageProfile.thermal_heavy()
        assert profile.em == 10.0
        assert profile.thermal == 50.0
        assert profile.kinetic == 30.0
        assert profile.explosive == 10.0
        assert profile.validate() is True

    def test_explosive_heavy_factory(self):
        """explosive_heavy() should return explosive-focused profile."""
        profile = DamageProfile.explosive_heavy()
        assert profile.em == 5.0
        assert profile.thermal == 15.0
        assert profile.kinetic == 20.0
        assert profile.explosive == 60.0
        assert profile.validate() is True
