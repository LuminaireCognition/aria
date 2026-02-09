"""
Integration Tests for Fitting Module.

Tests the complete pipeline:
- EFT string -> parse -> extract skills -> calculate stats
- Pilot skills path with mocked ESI
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aria_esi.fitting import (
    EFTParser,
    EOSBridge,
    calculate_fit_stats,
    extract_skills_for_fit,
    fetch_pilot_skills,
)
from aria_esi.models.fitting import FitStatsResult, ParsedFit

# =============================================================================
# Full Pipeline Integration Tests
# =============================================================================


class TestFullPipeline:
    """Tests for complete EFT -> Stats pipeline."""

    def test_eft_to_parsed_fit(self, eft_vexor_string, mock_market_db):
        """Test EFT string to ParsedFit conversion."""
        parser = EFTParser(mock_market_db)
        fit = parser.parse(eft_vexor_string)

        assert isinstance(fit, ParsedFit)
        assert fit.ship_type_name == "Vexor"
        assert len(fit.low_slots) == 3
        assert len(fit.drones) == 2

    def test_parsed_fit_to_skills(self, vexor_parsed_fit, mock_skill_requirements_data):
        """Test ParsedFit to skill extraction."""
        with patch("aria_esi.fitting.skills._load_skill_requirements") as mock_load:
            requirements = {
                int(k): {int(sk): v for sk, v in skills.items()}
                for k, skills in mock_skill_requirements_data.items()
            }
            mock_load.return_value = requirements

            import aria_esi.fitting.skills as skills_module

            skills_module._skill_requirements = None

            skills = extract_skills_for_fit(vexor_parsed_fit, level=5)

            assert isinstance(skills, dict)
            assert len(skills) > 0
            # All skills should be at level 5
            assert all(level == 5 for level in skills.values())

    def test_full_pipeline_with_mocked_eos(
        self, eft_vexor_string, mock_market_db, mock_eos_module, mock_eos_data_path
    ):
        """Test full pipeline: EFT -> Parse -> Calculate."""
        EOSBridge.reset_instance()

        # Step 1: Parse EFT
        parser = EFTParser(mock_market_db)
        parsed_fit = parser.parse(eft_vexor_string)

        # Step 2: Calculate stats with mocked EOS
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
                    mock_extract.return_value = {3332: 5, 3436: 5}

                    result = calculate_fit_stats(parsed_fit)

                    assert isinstance(result, FitStatsResult)
                    assert result.ship_type_name == "Vexor"
                    assert result.skill_mode == "all_v"


# =============================================================================
# Pilot Skills Integration Tests
# =============================================================================


class TestPilotSkillsIntegration:
    """Tests for pilot skills integration path."""

    def test_pilot_skills_mode_with_mocked_esi(
        self,
        vexor_parsed_fit,
        mock_credentials,
        mock_esi_skills_response,
        mock_eos_module,
        mock_eos_data_path,
    ):
        """Test full pilot skills path with mocked ESI."""
        EOSBridge.reset_instance()

        # Step 1: Fetch pilot skills (mocked)
        with patch("aria_esi.core.get_authenticated_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_esi_skills_response
            mock_get_client.return_value = (mock_client, mock_credentials)

            fetch_result = fetch_pilot_skills()
            pilot_skills = fetch_result.skills

            assert len(pilot_skills) == 10
            assert fetch_result.source == "esi"
            assert pilot_skills[3332] == 5  # Gallente Cruiser

        # Step 2: Calculate stats with pilot skills
        with patch.dict("sys.modules", {"aria_esi._vendor.eos": mock_eos_module}):
            with patch(
                "aria_esi.fitting.eos_bridge.get_eos_data_manager"
            ) as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.ensure_valid = MagicMock()
                mock_manager.data_path = mock_eos_data_path
                mock_manager.cache_path = mock_eos_data_path / "cache.json.bz2"
                mock_get_manager.return_value = mock_manager

                result = calculate_fit_stats(vexor_parsed_fit, skill_levels=pilot_skills)

                assert result.skill_mode == "pilot_skills"

    def test_pilot_skills_fallback_to_all_v(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test that missing pilot skills falls back to all_v mode."""
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

                    # Pass None for skills - should use all_v mode
                    result = calculate_fit_stats(vexor_parsed_fit, skill_levels=None)

                    assert result.skill_mode == "all_v"


# =============================================================================
# Error Path Integration Tests
# =============================================================================


class TestErrorPaths:
    """Tests for error handling in integration paths."""

    def test_invalid_eft_raises_parse_error(self, mock_market_db):
        """Test that invalid EFT raises appropriate error."""
        from aria_esi.fitting import EFTParseError

        parser = EFTParser(mock_market_db)

        with pytest.raises(EFTParseError):
            parser.parse("Not valid EFT format")

    def test_unknown_type_raises_resolution_error(self, mock_market_db):
        """Test that unknown types raise TypeResolutionError."""
        from aria_esi.fitting import TypeResolutionError

        eft = """[UnknownShip123, Test]
Unknown Module ABC
"""
        parser = EFTParser(mock_market_db)

        with pytest.raises(TypeResolutionError):
            parser.parse(eft)

    def test_esi_auth_error_during_skill_fetch(self):
        """Test that ESI auth errors are properly wrapped."""
        from aria_esi.core import CredentialsError
        from aria_esi.fitting import SkillFetchError

        with patch("aria_esi.core.get_authenticated_client") as mock_get_client:
            mock_get_client.side_effect = CredentialsError("Token expired")

            with pytest.raises(SkillFetchError) as exc_info:
                fetch_pilot_skills()

            assert exc_info.value.is_auth_error is True


# =============================================================================
# Result Validation Tests
# =============================================================================


class TestResultValidation:
    """Tests for result data validation."""

    def test_result_contains_required_fields(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test that result contains all required fields."""
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

                    # Check all required fields are present
                    assert result.ship_type_id is not None
                    assert result.ship_type_name is not None
                    assert result.fit_name is not None
                    assert result.dps is not None
                    assert result.tank is not None
                    assert result.cpu is not None
                    assert result.powergrid is not None
                    assert result.calibration is not None
                    assert result.capacitor is not None
                    assert result.mobility is not None
                    assert result.drones is not None
                    assert result.slots is not None

    def test_result_to_dict_is_serializable(
        self, vexor_parsed_fit, mock_eos_module, mock_eos_data_path
    ):
        """Test that result.to_dict() is JSON-serializable."""
        import json

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
                    result_dict = result.to_dict()

                    # Should be JSON-serializable
                    serialized = json.dumps(result_dict)
                    assert isinstance(serialized, str)

                    # Should round-trip
                    deserialized = json.loads(serialized)
                    assert deserialized["ship"]["type_name"] == "Vexor"
