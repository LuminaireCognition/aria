"""
Tests for Reactions Service.
"""

import pytest

from aria_esi.services.reactions import (
    calculate_fuel_block_cost,
    calculate_fuel_block_profit,
    calculate_reaction_time,
    format_fuel_block_summary,
    get_fuel_block_info,
    get_material_sources,
    get_refinery_info,
    list_fuel_blocks,
)


class TestFuelBlockInfo:
    """Test fuel block information retrieval."""

    @pytest.mark.unit
    def test_get_nitrogen_fuel_block(self):
        """Nitrogen Fuel Block should have Caldari isotopes."""
        info = get_fuel_block_info("Nitrogen Fuel Block")
        assert info is not None
        assert info["faction"] == "Caldari"
        assert info["isotope"] == "Nitrogen Isotopes"
        assert "inputs" in info
        assert info["output_quantity"] == 40

    @pytest.mark.unit
    def test_get_fuel_block_partial_match(self):
        """Should match partial names."""
        info = get_fuel_block_info("Nitrogen")
        assert info is not None
        assert "Nitrogen" in info["name"]

    @pytest.mark.unit
    def test_get_fuel_block_case_insensitive(self):
        """Lookup should be case insensitive."""
        info1 = get_fuel_block_info("NITROGEN FUEL BLOCK")
        info2 = get_fuel_block_info("nitrogen fuel block")
        assert info1 is not None
        assert info2 is not None
        assert info1["name"] == info2["name"]

    @pytest.mark.unit
    def test_get_unknown_fuel_block(self):
        """Unknown fuel block should return None."""
        info = get_fuel_block_info("Unknown Fuel Block")
        assert info is None

    @pytest.mark.unit
    def test_list_fuel_blocks(self):
        """Should list all four fuel block types."""
        blocks = list_fuel_blocks()
        assert len(blocks) == 4
        names = [b["name"] for b in blocks]
        assert "Nitrogen Fuel Block" in names
        assert "Hydrogen Fuel Block" in names
        assert "Helium Fuel Block" in names
        assert "Oxygen Fuel Block" in names

    @pytest.mark.unit
    def test_fuel_block_has_all_inputs(self):
        """Fuel block should have all required inputs."""
        info = get_fuel_block_info("Nitrogen Fuel Block")
        required_inputs = [
            "Coolant",
            "Enriched Uranium",
            "Mechanical Parts",
            "Oxygen",
            "Heavy Water",
            "Liquid Ozone",
            "Robotics",
        ]
        for inp in required_inputs:
            assert inp in info["inputs"], f"Missing input: {inp}"


class TestRefineryInfo:
    """Test refinery information retrieval."""

    @pytest.mark.unit
    def test_get_athanor(self):
        """Athanor should have no time bonus."""
        info = get_refinery_info("Athanor")
        assert info["name"] == "Athanor"
        assert info["reaction_time_bonus"] == 0

    @pytest.mark.unit
    def test_get_tatara(self):
        """Tatara should have 25% time bonus."""
        info = get_refinery_info("Tatara")
        assert info["name"] == "Tatara"
        assert info["reaction_time_bonus"] == 0.25

    @pytest.mark.unit
    def test_unknown_refinery_defaults_to_athanor(self):
        """Unknown refinery should default to Athanor."""
        info = get_refinery_info("UnknownRefinery")
        assert info["name"] == "Athanor"
        assert info["reaction_time_bonus"] == 0


class TestReactionTime:
    """Test reaction time calculations."""

    @pytest.mark.unit
    def test_base_time_no_bonuses(self):
        """No bonuses should use base time."""
        result = calculate_reaction_time(
            base_cycle_seconds=900,  # 15 minutes
            reactions_skill=0,
            refinery_name="Athanor",
            runs=1,
        )
        assert result["effective_cycle_seconds"] == 900
        assert result["skill_reduction_percent"] == 0
        assert result["refinery_reduction_percent"] == 0

    @pytest.mark.unit
    def test_reactions_skill_reduction(self):
        """Reactions skill should reduce time by 4% per level."""
        result = calculate_reaction_time(
            base_cycle_seconds=900,
            reactions_skill=5,  # Max skill
            refinery_name="Athanor",
            runs=1,
        )
        # 5 * 4% = 20% reduction
        expected = 900 * 0.80
        assert result["effective_cycle_seconds"] == expected
        assert result["skill_reduction_percent"] == 20.0

    @pytest.mark.unit
    def test_tatara_bonus(self):
        """Tatara should provide 25% reduction."""
        result = calculate_reaction_time(
            base_cycle_seconds=900,
            reactions_skill=0,
            refinery_name="Tatara",
            runs=1,
        )
        expected = 900 * 0.75
        assert result["effective_cycle_seconds"] == expected
        assert result["refinery_reduction_percent"] == 25.0

    @pytest.mark.unit
    def test_combined_bonuses(self):
        """Skill and refinery bonuses should stack multiplicatively."""
        result = calculate_reaction_time(
            base_cycle_seconds=900,
            reactions_skill=5,  # 20% reduction
            refinery_name="Tatara",  # 25% reduction
            runs=1,
        )
        # Multiplicative: 900 * 0.80 * 0.75 = 540
        expected = 900 * 0.80 * 0.75
        assert result["effective_cycle_seconds"] == expected
        # Total reduction: 1 - (0.80 * 0.75) = 40%
        assert result["total_reduction_percent"] == 40.0

    @pytest.mark.unit
    def test_multiple_runs(self):
        """Multiple runs should scale time linearly."""
        result = calculate_reaction_time(
            base_cycle_seconds=900,
            reactions_skill=0,
            refinery_name="Athanor",
            runs=10,
        )
        assert result["total_time_seconds"] == 9000
        assert result["runs"] == 10

    @pytest.mark.unit
    def test_skill_clamps_to_valid_range(self):
        """Skill level should be clamped to 0-5."""
        result_negative = calculate_reaction_time(
            base_cycle_seconds=900,
            reactions_skill=-5,
            refinery_name="Athanor",
            runs=1,
        )
        assert result_negative["skill_reduction_percent"] == 0

        result_excessive = calculate_reaction_time(
            base_cycle_seconds=900,
            reactions_skill=10,
            refinery_name="Athanor",
            runs=1,
        )
        assert result_excessive["skill_reduction_percent"] == 20.0  # Max is 5


class TestFuelBlockCost:
    """Test fuel block cost calculations."""

    @pytest.fixture
    def sample_prices(self):
        """Sample material prices for testing."""
        return {
            "Coolant": 10000.0,
            "Enriched Uranium": 8000.0,
            "Mechanical Parts": 9000.0,
            "Oxygen": 500.0,
            "Heavy Water": 100.0,
            "Liquid Ozone": 150.0,
            "Nitrogen Isotopes": 900.0,
            "Robotics": 80000.0,
        }

    @pytest.mark.unit
    def test_calculate_cost_basic(self, sample_prices):
        """Basic cost calculation should work."""
        result = calculate_fuel_block_cost(
            fuel_block_name="Nitrogen Fuel Block",
            material_prices=sample_prices,
            reactions_skill=0,
            refinery_name="Athanor",
            runs=1,
        )
        assert result["fuel_block"] == "Nitrogen Fuel Block"
        assert result["runs"] == 1
        assert result["total_output"] == 40
        assert result["total_input_cost"] > 0
        assert result["cost_per_unit"] > 0
        assert result["is_complete"] is True

    @pytest.mark.unit
    def test_cost_scales_with_runs(self, sample_prices):
        """Cost should scale linearly with runs."""
        result_1 = calculate_fuel_block_cost(
            fuel_block_name="Nitrogen Fuel Block",
            material_prices=sample_prices,
            runs=1,
        )
        result_10 = calculate_fuel_block_cost(
            fuel_block_name="Nitrogen Fuel Block",
            material_prices=sample_prices,
            runs=10,
        )
        # Cost should be ~10x
        assert result_10["total_input_cost"] == pytest.approx(
            result_1["total_input_cost"] * 10, rel=0.001
        )
        # Cost per unit should be the same
        assert result_10["cost_per_unit"] == pytest.approx(
            result_1["cost_per_unit"], rel=0.001
        )

    @pytest.mark.unit
    def test_cost_with_missing_prices(self):
        """Missing prices should be flagged."""
        partial_prices = {
            "Coolant": 10000.0,
            # Missing everything else
        }
        result = calculate_fuel_block_cost(
            fuel_block_name="Nitrogen Fuel Block",
            material_prices=partial_prices,
            runs=1,
        )
        assert result["is_complete"] is False
        assert len(result["missing_prices"]) > 0

    @pytest.mark.unit
    def test_unknown_fuel_block_returns_error(self):
        """Unknown fuel block should return error."""
        result = calculate_fuel_block_cost(
            fuel_block_name="Unknown Block",
            material_prices={},
            runs=1,
        )
        assert "error" in result


class TestFuelBlockProfit:
    """Test fuel block profit calculations."""

    @pytest.fixture
    def sample_prices(self):
        """Sample material prices for testing."""
        return {
            "Coolant": 10000.0,
            "Enriched Uranium": 8000.0,
            "Mechanical Parts": 9000.0,
            "Oxygen": 500.0,
            "Heavy Water": 100.0,
            "Liquid Ozone": 150.0,
            "Nitrogen Isotopes": 900.0,
            "Robotics": 80000.0,
        }

    @pytest.mark.unit
    def test_profit_calculation(self, sample_prices):
        """Profit calculation should work."""
        result = calculate_fuel_block_profit(
            fuel_block_name="Nitrogen Fuel Block",
            material_prices=sample_prices,
            fuel_block_price=150000.0,  # High profit price
            reactions_skill=4,
            refinery_name="Tatara",
            runs=10,
        )
        assert result["gross_profit"] > 0
        assert result["margin_percent"] > 0
        assert result["profit_per_hour"] > 0

    @pytest.mark.unit
    def test_negative_profit(self, sample_prices):
        """Should show negative profit if selling below cost."""
        result = calculate_fuel_block_profit(
            fuel_block_name="Nitrogen Fuel Block",
            material_prices=sample_prices,
            fuel_block_price=1.0,  # Way below cost
            runs=1,
        )
        assert result["gross_profit"] < 0
        assert result["margin_percent"] < 0


class TestFormatSummary:
    """Test markdown formatting."""

    @pytest.mark.unit
    def test_format_with_profit(self):
        """Format should include profit metrics."""
        sample_result = {
            "fuel_block": "Nitrogen Fuel Block",
            "faction": "Caldari",
            "isotope": "Nitrogen Isotopes",
            "runs": 10,
            "total_output": 400,
            "material_costs": [
                {
                    "material": "Coolant",
                    "quantity_per_run": 150,
                    "total_quantity": 1500,
                    "unit_price": 10000.0,
                    "total_cost": 15000000.0,
                }
            ],
            "total_input_cost": 50000000.0,
            "cost_per_unit": 125000.0,
            "production_time": {
                "base_cycle_seconds": 900,
                "effective_cycle_seconds": 540,
                "total_time_seconds": 5400,
                "total_time_hours": 1.5,
                "runs": 10,
                "skill_reduction_percent": 20.0,
                "refinery_reduction_percent": 25.0,
                "total_reduction_percent": 40.0,
                "refinery": "Tatara",
            },
            "missing_prices": [],
            "is_complete": True,
            "fuel_block_price": 150000.0,
            "revenue": 60000000.0,
            "gross_profit": 10000000.0,
            "margin_percent": 16.7,
            "profit_per_hour": 6666666.67,
        }

        output = format_fuel_block_summary(sample_result)

        assert "Nitrogen Fuel Block" in output
        assert "Caldari" in output
        assert "Profitability" in output
        assert "Gross Profit" in output
        assert "Profit/Hour" in output

    @pytest.mark.unit
    def test_format_with_missing_prices(self):
        """Format should show warnings for missing prices."""
        sample_result = {
            "fuel_block": "Test Block",
            "faction": "Test",
            "isotope": "Test",
            "runs": 1,
            "total_output": 40,
            "material_costs": [],
            "total_input_cost": 0,
            "cost_per_unit": 0,
            "production_time": {
                "base_cycle_seconds": 900,
                "effective_cycle_seconds": 900,
                "total_time_seconds": 900,
                "total_time_hours": 0.25,
                "runs": 1,
                "skill_reduction_percent": 0,
                "refinery_reduction_percent": 0,
                "total_reduction_percent": 0,
                "refinery": "Athanor",
            },
            "missing_prices": ["Coolant", "Robotics"],
            "is_complete": False,
        }

        output = format_fuel_block_summary(sample_result)

        assert "Warnings" in output
        assert "Missing prices" in output
        assert "Coolant" in output
        assert "Robotics" in output


class TestMaterialSources:
    """Test material source information."""

    @pytest.mark.unit
    def test_get_material_sources(self):
        """Should return sources for common materials."""
        sources = get_material_sources()
        assert "Coolant" in sources
        assert "Heavy Water" in sources
        assert "Nitrogen Isotopes" in sources
