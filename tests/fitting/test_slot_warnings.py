"""Tests for empty slot warnings in fitting stats."""

from __future__ import annotations

from aria_esi.models.fitting import (
    CapacitorStats,
    DPSBreakdown,
    DroneStats,
    FitStatsResult,
    LayerStats,
    MobilityStats,
    ResistProfile,
    ResourceUsage,
    SlotUsage,
    TankStats,
)

_ZERO_RESISTS = ResistProfile()
_ZERO_LAYER = LayerStats(hp=0, ehp=0, resists=_ZERO_RESISTS)


def _make_result(slots: SlotUsage, warnings: list[str] | None = None) -> FitStatsResult:
    """Build a minimal FitStatsResult with the given slot usage."""
    return FitStatsResult(
        ship_type_id=626,
        ship_type_name="Vexor",
        fit_name="Test",
        dps=DPSBreakdown(total=0),
        tank=TankStats(
            shield=_ZERO_LAYER, armor=_ZERO_LAYER, hull=_ZERO_LAYER,
            total_hp=0, total_ehp=0,
        ),
        cpu=ResourceUsage(used=0, output=0),
        powergrid=ResourceUsage(used=0, output=0),
        calibration=ResourceUsage(used=0, output=0),
        capacitor=CapacitorStats(capacity=0, recharge_time=0, recharge_rate=0),
        mobility=MobilityStats(
            max_velocity=0, agility=0, align_time=0, warp_speed=0, mass=0,
        ),
        drones=DroneStats(
            bandwidth_used=0, bandwidth_output=0,
            bay_used=0, bay_output=0,
            drones_launched=0, drones_max=0,
        ),
        slots=slots,
        warnings=warnings or [],
    )


class TestSlotWarnings:
    """Test that empty slot conditions are represented in warnings."""

    def test_empty_rigs_produces_warning(self):
        """A fit with 0/3 rigs should warn about empty rig slots."""
        result = _make_result(
            SlotUsage(
                high_used=4, high_total=4,
                mid_used=4, mid_total=4,
                low_used=4, low_total=4,
                rig_used=0, rig_total=3,
            ),
            warnings=["Empty rig slots: 3 of 3 unused — rigs are cheap and always beneficial"],
        )
        rig_warnings = [w for w in result.warnings if "rig" in w.lower()]
        assert len(rig_warnings) == 1
        assert "rig slots" in rig_warnings[0].lower()

    def test_full_slots_no_slot_warning(self):
        """A fully fitted ship should have no slot warnings."""
        result = _make_result(
            SlotUsage(
                high_used=4, high_total=4,
                mid_used=4, mid_total=4,
                low_used=4, low_total=4,
                rig_used=3, rig_total=3,
            ),
        )
        slot_warnings = [w for w in result.warnings if "slot" in w.lower()]
        assert len(slot_warnings) == 0

    def test_empty_highs_produces_warning(self):
        """A fit with 1/4 highs should warn about empty high slots."""
        result = _make_result(
            SlotUsage(
                high_used=1, high_total=4,
                mid_used=4, mid_total=4,
                low_used=4, low_total=4,
                rig_used=3, rig_total=3,
            ),
            warnings=["Empty high slots: 3 of 4 unused"],
        )
        high_warnings = [w for w in result.warnings if "high" in w.lower()]
        assert len(high_warnings) == 1
        assert "high slots" in high_warnings[0].lower()
