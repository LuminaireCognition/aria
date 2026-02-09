"""
Tests for Invention Cost Calculations.
"""

import pytest

from aria_esi.services.industry_costs import (
    calculate_invention_cost,
    calculate_invention_success_rate,
    calculate_t2_bpc_stats,
    estimate_t2_production_cost,
    get_datacore_type_id,
    get_decryptor_info,
    list_decryptors,
)


class TestDecryptorInfo:
    """Test decryptor data retrieval."""

    @pytest.mark.unit
    def test_get_decryptor_info_exists(self):
        """Should return info for valid decryptor."""
        info = get_decryptor_info("Attainment Decryptor")
        assert info is not None
        assert info["success_modifier"] == 1.8
        assert "me_modifier" in info
        assert "te_modifier" in info
        assert "runs_modifier" in info

    @pytest.mark.unit
    def test_get_decryptor_info_case_insensitive(self):
        """Should handle case-insensitive lookup."""
        info = get_decryptor_info("attainment decryptor")
        assert info is not None
        assert info["success_modifier"] == 1.8

    @pytest.mark.unit
    def test_get_decryptor_info_none(self):
        """Should return None when no decryptor specified."""
        assert get_decryptor_info(None) is None
        assert get_decryptor_info("") is None

    @pytest.mark.unit
    def test_get_decryptor_info_unknown(self):
        """Should return None for unknown decryptor."""
        assert get_decryptor_info("Fake Decryptor") is None

    @pytest.mark.unit
    def test_list_decryptors_returns_all(self):
        """Should return list of all decryptors."""
        decryptors = list_decryptors()
        assert len(decryptors) >= 8
        # Should be sorted by success_modifier descending
        modifiers = [d["success_modifier"] for d in decryptors]
        assert modifiers == sorted(modifiers, reverse=True)


class TestInventionSuccessRate:
    """Test invention success rate calculations."""

    @pytest.mark.unit
    def test_base_rate_no_bonuses(self):
        """Should return base rate without skills or decryptor."""
        result = calculate_invention_success_rate(base_rate=0.26)
        assert result["final_rate"] == 0.26
        assert result["skill_bonus"] == 0
        assert result["decryptor_modifier"] == 1.0

    @pytest.mark.unit
    def test_with_max_skills(self):
        """Should calculate with max skills (5 each)."""
        result = calculate_invention_success_rate(
            base_rate=0.26,
            encryption_skill=5,
            science_skill_1=5,
            science_skill_2=5,
        )
        # skill_bonus = 15 * 0.01 = 0.15
        # final = 0.26 * (1 + 0.15) = 0.299
        assert result["skill_bonus"] == 0.15
        assert abs(result["final_rate"] - 0.299) < 0.001

    @pytest.mark.unit
    def test_with_decryptor(self):
        """Should apply decryptor modifier."""
        result = calculate_invention_success_rate(
            base_rate=0.26,
            decryptor="Attainment Decryptor",
        )
        # Attainment has 1.8x modifier
        # final = 0.26 * 1.0 * 1.8 = 0.468
        assert result["decryptor_modifier"] == 1.8
        assert abs(result["final_rate"] - 0.468) < 0.001

    @pytest.mark.unit
    def test_with_skills_and_decryptor(self):
        """Should combine skills and decryptor."""
        result = calculate_invention_success_rate(
            base_rate=0.26,
            encryption_skill=4,
            science_skill_1=4,
            science_skill_2=4,
            decryptor="Accelerant Decryptor",  # 1.2x
        )
        # skill_bonus = 12 * 0.01 = 0.12
        # final = 0.26 * 1.12 * 1.2 = 0.34944
        assert result["skill_bonus"] == 0.12
        assert result["decryptor_modifier"] == 1.2
        assert abs(result["final_rate"] - 0.3494) < 0.001

    @pytest.mark.unit
    def test_rate_capped_at_100(self):
        """Should cap success rate at 100%."""
        result = calculate_invention_success_rate(
            base_rate=0.80,  # Artificially high
            encryption_skill=5,
            science_skill_1=5,
            science_skill_2=5,
            decryptor="Attainment Decryptor",
        )
        assert result["final_rate"] == 1.0  # Capped

    @pytest.mark.unit
    def test_expected_attempts(self):
        """Should calculate expected attempts correctly."""
        result = calculate_invention_success_rate(base_rate=0.25)
        # 1 / 0.25 = 4 attempts
        assert result["expected_attempts"] == 4.0


class TestInventionCost:
    """Test invention cost calculations."""

    @pytest.mark.unit
    def test_basic_invention_cost(self):
        """Should calculate basic invention cost."""
        result = calculate_invention_cost(
            datacore_costs={
                "Datacore - Mechanical Engineering": 50000,
                "Datacore - Electronic Engineering": 40000,
            },
            datacore_quantities={
                "Datacore - Mechanical Engineering": 2,
                "Datacore - Electronic Engineering": 2,
            },
            success_rate=0.26,
        )
        # Per attempt: (50000*2) + (40000*2) = 180000
        # Expected cost: 180000 / 0.26 = ~692308
        assert result["per_attempt_cost"] == 180000
        assert result["datacore_cost"] == 180000
        assert abs(result["expected_cost"] - 692307.69) < 1

    @pytest.mark.unit
    def test_with_t1_bpc_cost(self):
        """Should include T1 BPC cost."""
        result = calculate_invention_cost(
            datacore_costs={"Datacore - Mechanical Engineering": 50000},
            datacore_quantities={"Datacore - Mechanical Engineering": 2},
            t1_bpc_cost=10000,
            success_rate=0.26,
        )
        # Per attempt: 100000 + 10000 = 110000
        assert result["per_attempt_cost"] == 110000
        assert result["t1_bpc_cost"] == 10000

    @pytest.mark.unit
    def test_with_decryptor(self):
        """Should include decryptor cost."""
        result = calculate_invention_cost(
            datacore_costs={"Datacore - Mechanical Engineering": 50000},
            datacore_quantities={"Datacore - Mechanical Engineering": 2},
            decryptor="Attainment Decryptor",
            decryptor_cost=500000,
            success_rate=0.26,
        )
        # Per attempt: 100000 + 500000 = 600000
        assert result["per_attempt_cost"] == 600000
        assert result["decryptor_cost"] == 500000
        assert result["decryptor_name"] == "Attainment Decryptor"

    @pytest.mark.unit
    def test_cost_breakdown(self):
        """Should provide itemized cost breakdown."""
        result = calculate_invention_cost(
            datacore_costs={
                "Datacore - Mechanical Engineering": 50000,
                "Datacore - Electronic Engineering": 40000,
            },
            datacore_quantities={
                "Datacore - Mechanical Engineering": 2,
                "Datacore - Electronic Engineering": 3,
            },
            success_rate=0.26,
        )
        breakdown = result["cost_breakdown"]
        assert len(breakdown) == 2

        mech = next(d for d in breakdown if "Mechanical" in d["name"])
        assert mech["quantity"] == 2
        assert mech["unit_cost"] == 50000
        assert mech["total_cost"] == 100000


class TestT2BPCStats:
    """Test T2 BPC statistics calculation."""

    @pytest.mark.unit
    def test_default_stats(self):
        """Should return default T2 BPC stats."""
        result = calculate_t2_bpc_stats(base_runs=10)
        assert result["runs"] == 10
        assert result["me"] == -2
        assert result["te"] == 0
        assert result["decryptor"] is None

    @pytest.mark.unit
    def test_with_attainment_decryptor(self):
        """Should apply Attainment decryptor modifiers."""
        result = calculate_t2_bpc_stats(
            base_runs=10,
            decryptor="Attainment Decryptor",
        )
        # Attainment: me=-1, te=4, runs=+2
        assert result["runs"] == 12
        assert result["me"] == -3  # -2 + -1
        assert result["te"] == 4

    @pytest.mark.unit
    def test_with_augmentation_decryptor(self):
        """Should apply Augmentation decryptor modifiers."""
        result = calculate_t2_bpc_stats(
            base_runs=10,
            decryptor="Augmentation Decryptor",
        )
        # Augmentation: me=-2, te=2, runs=+9
        assert result["runs"] == 19
        assert result["me"] == -4  # -2 + -2
        assert result["te"] == 2

    @pytest.mark.unit
    def test_ship_base_runs(self):
        """Should use ship base runs of 1."""
        result = calculate_t2_bpc_stats(base_runs=1)
        assert result["runs"] == 1

    @pytest.mark.unit
    def test_runs_minimum_1(self):
        """Should not allow runs below 1."""
        # This shouldn't happen with real decryptors, but test the guard
        result = calculate_t2_bpc_stats(base_runs=1)
        assert result["runs"] >= 1


class TestT2ProductionCost:
    """Test T2 production cost estimation."""

    @pytest.mark.unit
    def test_basic_t2_cost(self):
        """Should estimate T2 production cost."""
        result = estimate_t2_production_cost(
            invention_cost=700000,
            t2_material_cost=500000,
            t2_job_cost=100000,
            t2_bpc_runs=10,
        )
        # Invention per unit: 700000 / 10 = 70000
        # Job per unit: 100000 / 10 = 10000
        # Total per unit: 70000 + 500000 + 10000 = 580000
        assert result["invention_cost_per_unit"] == 70000
        assert result["job_cost_per_unit"] == 10000
        assert result["total_cost_per_unit"] == 580000

    @pytest.mark.unit
    def test_batch_cost(self):
        """Should calculate total batch cost."""
        result = estimate_t2_production_cost(
            invention_cost=700000,
            t2_material_cost=500000,
            t2_job_cost=100000,
            t2_bpc_runs=10,
        )
        # Batch: 700000 + (500000 * 10) + 100000 = 5800000
        assert result["total_batch_cost"] == 5800000

    @pytest.mark.unit
    def test_single_run_ship(self):
        """Should handle single-run ship BPCs."""
        result = estimate_t2_production_cost(
            invention_cost=50000000,  # Higher for ships
            t2_material_cost=100000000,
            t2_job_cost=5000000,
            t2_bpc_runs=1,
        )
        # All costs apply to single unit
        assert result["total_cost_per_unit"] == 155000000


class TestDatacoreTypeIds:
    """Test datacore type ID lookup."""

    @pytest.mark.unit
    def test_known_datacore(self):
        """Should return type ID for known datacore."""
        type_id = get_datacore_type_id("Datacore - Mechanical Engineering")
        assert type_id == 20419

    @pytest.mark.unit
    def test_unknown_datacore(self):
        """Should return None for unknown datacore."""
        type_id = get_datacore_type_id("Fake Datacore")
        assert type_id is None
