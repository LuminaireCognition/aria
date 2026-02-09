"""
Tests for Industry Cost Service.
"""

import pytest

from aria_esi.services.industry_costs import (
    apply_facility_me,
    apply_me,
    calculate_job_cost,
    calculate_profit_per_hour,
    estimate_total_build_cost,
    format_isk,
    format_time_duration,
    get_facility_info,
    get_typical_system_index,
    list_facilities,
)


class TestMaterialEfficiency:
    """Test ME application functions."""

    @pytest.mark.unit
    def test_apply_me_zero(self):
        """ME 0 should not reduce materials."""
        result = apply_me(base_qty=1000, me_level=0)
        assert result == 1000

    @pytest.mark.unit
    def test_apply_me_ten(self):
        """ME 10 should reduce materials by 10%."""
        result = apply_me(base_qty=1000, me_level=10)
        assert result == 900

    @pytest.mark.unit
    def test_apply_me_five(self):
        """ME 5 should reduce materials by 5%."""
        result = apply_me(base_qty=1000, me_level=5)
        assert result == 950

    @pytest.mark.unit
    def test_apply_me_rounds_up(self):
        """ME reduction should ceil fractional results."""
        # 100 * 0.95 = 95 (no rounding needed)
        assert apply_me(100, 5) == 95
        # 99 * 0.95 = 94.05 -> ceil = 95
        assert apply_me(99, 5) == 95

    @pytest.mark.unit
    def test_apply_me_clamps_negative(self):
        """Negative ME should be treated as 0."""
        result = apply_me(base_qty=1000, me_level=-5)
        assert result == 1000

    @pytest.mark.unit
    def test_apply_me_clamps_excessive(self):
        """ME > 10 should be clamped to 10."""
        result = apply_me(base_qty=1000, me_level=15)
        assert result == 900  # Same as ME 10


class TestFacilityME:
    """Test facility ME bonus application."""

    @pytest.mark.unit
    def test_facility_me_zero_bonus(self):
        """Zero bonus should not change quantity."""
        result = apply_facility_me(qty=900, facility_me_bonus=0)
        assert result == 900

    @pytest.mark.unit
    def test_facility_me_one_percent(self):
        """1% facility bonus should reduce by 1%."""
        result = apply_facility_me(qty=1000, facility_me_bonus=1)
        # 1000 * 0.99 = 990
        assert result == 990

    @pytest.mark.unit
    def test_facility_me_rounds_up(self):
        """Facility ME should ceil fractional results."""
        # 999 * 0.99 = 989.01 -> ceil = 990
        result = apply_facility_me(qty=999, facility_me_bonus=1)
        assert result == 990


class TestFacilityInfo:
    """Test facility information retrieval."""

    @pytest.mark.unit
    def test_get_npc_station(self):
        """NPC Station should have no bonuses."""
        info = get_facility_info("NPC Station")
        assert info["me_bonus"] == 0
        assert info["te_bonus"] == 0

    @pytest.mark.unit
    def test_get_raitaru(self):
        """Raitaru should have 1% ME, 15% TE."""
        info = get_facility_info("Raitaru")
        assert info["me_bonus"] == 1
        assert info["te_bonus"] == 15

    @pytest.mark.unit
    def test_get_azbel(self):
        """Azbel should have 1% ME, 20% TE."""
        info = get_facility_info("Azbel")
        assert info["me_bonus"] == 1
        assert info["te_bonus"] == 20

    @pytest.mark.unit
    def test_get_sotiyo(self):
        """Sotiyo should have 1% ME, 30% TE."""
        info = get_facility_info("Sotiyo")
        assert info["me_bonus"] == 1
        assert info["te_bonus"] == 30

    @pytest.mark.unit
    def test_case_insensitive(self):
        """Facility lookup should be case-insensitive."""
        info1 = get_facility_info("RAITARU")
        info2 = get_facility_info("raitaru")
        assert info1["me_bonus"] == info2["me_bonus"]

    @pytest.mark.unit
    def test_unknown_defaults_to_npc(self):
        """Unknown facility should default to NPC Station."""
        info = get_facility_info("UnknownFacility")
        assert info["name"] == "NPC Station"
        assert info["me_bonus"] == 0

    @pytest.mark.unit
    def test_list_facilities(self):
        """list_facilities should return all facilities."""
        facilities = list_facilities()
        names = [f["name"] for f in facilities]
        assert "NPC Station" in names
        assert "Raitaru" in names
        assert len(facilities) >= 4


class TestJobCostCalculation:
    """Test job cost calculation."""

    @pytest.mark.unit
    def test_basic_job_cost(self):
        """Basic job cost calculation."""
        result = calculate_job_cost(
            estimated_item_value=100_000_000,  # 100M ISK
            system_cost_index=0.05,  # 5%
            facility_name="NPC Station",
        )

        # Base cost: 100M * 0.05 = 5M
        assert result["base_cost"] == 5_000_000
        # SCC: 100M * 0.04 = 4M
        assert result["scc_surcharge"] == 4_000_000
        # NPC tax: 100M * 0.0025 = 250K
        assert result["npc_tax"] == 250_000
        # Total: 5M + 4M + 0.25M = 9.25M
        assert result["total"] == 9_250_000

    @pytest.mark.unit
    def test_player_structure_job_cost(self):
        """Player structure uses structure tax instead of NPC tax."""
        result = calculate_job_cost(
            estimated_item_value=100_000_000,
            system_cost_index=0.02,  # 2%
            facility_name="Raitaru",
            facility_tax=0.05,  # 5% structure tax
        )

        # Base cost: 100M * 0.02 = 2M
        assert result["base_cost"] == 2_000_000
        # SCC: 100M * 0.04 = 4M
        assert result["scc_surcharge"] == 4_000_000
        # NPC tax should be 0 for player structure
        assert result["npc_tax"] == 0
        # Structure tax: 100M * 0.05 = 5M
        assert result["structure_tax"] == 5_000_000

    @pytest.mark.unit
    def test_job_cost_without_scc(self):
        """Job cost without SCC surcharge."""
        result = calculate_job_cost(
            estimated_item_value=100_000_000,
            system_cost_index=0.05,
            facility_name="NPC Station",
            include_scc=False,
        )

        assert result["scc_surcharge"] == 0
        # Total without SCC
        assert result["total"] == 5_000_000 + 250_000


class TestTotalBuildCost:
    """Test total build cost estimation."""

    @pytest.mark.unit
    def test_estimate_total_build_cost(self):
        """Total cost should be materials + job fees."""
        result = estimate_total_build_cost(
            material_cost=150_000_000,  # 150M in materials
            estimated_item_value=100_000_000,  # 100M EIV
            system_cost_index=0.02,
            facility_name="Raitaru",
            facility_tax=0.05,
        )

        assert result["material_cost"] == 150_000_000
        assert result["job_cost"] > 0
        assert result["total_cost"] == result["material_cost"] + result["job_cost"]
        assert "cost_breakdown" in result


class TestSystemIndex:
    """Test system cost index lookup."""

    @pytest.mark.unit
    def test_jita_index(self):
        """Jita should have high index."""
        index = get_typical_system_index("Jita")
        assert 0.08 <= index <= 0.15

    @pytest.mark.unit
    def test_unknown_system_default(self):
        """Unknown system should return default."""
        index = get_typical_system_index("RandomSystem123")
        assert index == 0.01


class TestProfitPerHour:
    """Test profit per hour calculation."""

    @pytest.mark.unit
    def test_basic_profit_per_hour(self):
        """Basic profit/hour with no TE bonuses."""
        # 10M profit over 4 hours = 2.5M/hr
        result = calculate_profit_per_hour(
            gross_profit=10_000_000,
            manufacturing_time_seconds=14400,  # 4 hours
            runs=1,
            te_level=0,
            facility_te_bonus=0,
        )
        assert result["profit_per_hour"] == 2_500_000
        assert result["effective_time_hours"] == 4.0
        assert result["time_per_run_seconds"] == 14400
        assert result["te_savings_percent"] == 0.0

    @pytest.mark.unit
    def test_profit_per_hour_with_blueprint_te(self):
        """Blueprint TE should reduce time and increase profit/hr."""
        # TE 20 = 20% time reduction
        # 4 hours * 0.80 = 3.2 hours
        # 10M / 3.2 = 3.125M/hr
        result = calculate_profit_per_hour(
            gross_profit=10_000_000,
            manufacturing_time_seconds=14400,
            runs=1,
            te_level=20,
            facility_te_bonus=0,
        )
        assert result["effective_time_hours"] == 3.2
        assert result["profit_per_hour"] == 3_125_000
        assert result["te_savings_percent"] == 20.0

    @pytest.mark.unit
    def test_profit_per_hour_with_facility_te(self):
        """Facility TE bonus should stack with blueprint TE."""
        # Blueprint TE 10 = 10% reduction, Raitaru TE 15 = 15% reduction
        # Combined: 1 - (0.90 * 0.85) = 1 - 0.765 = 23.5%
        # 4 hours * 0.90 * 0.85 = 3.06 hours
        result = calculate_profit_per_hour(
            gross_profit=10_000_000,
            manufacturing_time_seconds=14400,
            runs=1,
            te_level=10,
            facility_te_bonus=15,
        )
        assert result["effective_time_hours"] == 3.06
        assert result["te_savings_percent"] == 23.5

    @pytest.mark.unit
    def test_profit_per_hour_multiple_runs(self):
        """Multiple runs should scale time linearly."""
        result = calculate_profit_per_hour(
            gross_profit=100_000_000,  # Total profit for 10 runs
            manufacturing_time_seconds=14400,
            runs=10,
            te_level=0,
            facility_te_bonus=0,
        )
        # 10 runs * 4 hours = 40 hours
        assert result["effective_time_hours"] == 40.0
        # 100M / 40 = 2.5M/hr
        assert result["profit_per_hour"] == 2_500_000
        # Time per run stays the same
        assert result["time_per_run_seconds"] == 14400

    @pytest.mark.unit
    def test_profit_per_hour_clamps_te(self):
        """TE should be clamped to 0-20 range."""
        # TE -5 should be treated as 0
        result_negative = calculate_profit_per_hour(
            gross_profit=10_000_000,
            manufacturing_time_seconds=14400,
            runs=1,
            te_level=-5,
            facility_te_bonus=0,
        )
        assert result_negative["te_savings_percent"] == 0.0

        # TE 25 should be clamped to 20
        result_excessive = calculate_profit_per_hour(
            gross_profit=10_000_000,
            manufacturing_time_seconds=14400,
            runs=1,
            te_level=25,
            facility_te_bonus=0,
        )
        assert result_excessive["te_savings_percent"] == 20.0

    @pytest.mark.unit
    def test_profit_per_hour_zero_time(self):
        """Zero manufacturing time should return 0 profit/hr."""
        result = calculate_profit_per_hour(
            gross_profit=10_000_000,
            manufacturing_time_seconds=0,
            runs=1,
            te_level=0,
            facility_te_bonus=0,
        )
        assert result["profit_per_hour"] == 0
        assert result["effective_time_hours"] == 0

    @pytest.mark.unit
    def test_profit_per_hour_negative_profit(self):
        """Negative profit should result in negative profit/hr."""
        result = calculate_profit_per_hour(
            gross_profit=-5_000_000,  # Loss
            manufacturing_time_seconds=14400,
            runs=1,
            te_level=0,
            facility_te_bonus=0,
        )
        assert result["profit_per_hour"] == -1_250_000


class TestFormatTimeDuration:
    """Test time duration formatting."""

    @pytest.mark.unit
    def test_format_hours_and_minutes(self):
        """Format hours and minutes correctly."""
        # 4 hours 30 minutes = 16200 seconds
        assert format_time_duration(16200) == "4h 30m"

    @pytest.mark.unit
    def test_format_days_and_hours(self):
        """Format days and hours, no minutes."""
        # 2 days 6 hours = 194400 seconds
        assert format_time_duration(194400) == "2d 6h"

    @pytest.mark.unit
    def test_format_hours_only(self):
        """Format exact hours."""
        assert format_time_duration(3600) == "1h"
        assert format_time_duration(7200) == "2h"

    @pytest.mark.unit
    def test_format_minutes_only(self):
        """Format minutes when less than an hour."""
        assert format_time_duration(1200) == "20m"
        assert format_time_duration(60) == "1m"

    @pytest.mark.unit
    def test_format_zero(self):
        """Zero seconds should return 0m."""
        assert format_time_duration(0) == "0m"

    @pytest.mark.unit
    def test_format_very_short(self):
        """Very short durations under a minute."""
        assert format_time_duration(30) == "< 1m"


class TestFormatIsk:
    """Test ISK amount formatting."""

    @pytest.mark.unit
    def test_format_billions(self):
        """Format billions."""
        assert format_isk(1_500_000_000) == "1.5B ISK"
        assert format_isk(10_000_000_000) == "10.0B ISK"

    @pytest.mark.unit
    def test_format_millions(self):
        """Format millions."""
        assert format_isk(4_100_000) == "4.1M ISK"
        assert format_isk(150_000_000) == "150.0M ISK"

    @pytest.mark.unit
    def test_format_thousands(self):
        """Format thousands."""
        assert format_isk(69_500) == "69.5K ISK"
        assert format_isk(5_000) == "5.0K ISK"

    @pytest.mark.unit
    def test_format_small_amounts(self):
        """Format amounts under 1000."""
        assert format_isk(500) == "500 ISK"
        assert format_isk(42) == "42 ISK"

    @pytest.mark.unit
    def test_format_negative(self):
        """Format negative amounts."""
        assert format_isk(-5_000_000) == "-5.0M ISK"

    @pytest.mark.unit
    def test_format_precision(self):
        """Custom precision."""
        assert format_isk(4_123_456, precision=2) == "4.12M ISK"
        assert format_isk(4_123_456, precision=0) == "4M ISK"
